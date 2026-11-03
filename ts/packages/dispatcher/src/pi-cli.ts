// pi_dispatch 里探测 CLI 的部分（迁移第 ③d 片）：child_env、run_capture、--help 与 --list-models 输出的解析、
// pi_model_readiness。配置中心的 runtime scan|probe、models、doctor 用它们，第 ④、⑤ 步的 doctor 与 kit_hub 也要用。
//   - run_capture 走第 ④a 步的 runSupervised（原生 CreateProcessW、Job Object）：PATH 上的 pi.CMD 是批处理，Node 不经
//     shell 起不了，CreateProcessW 的 lpApplicationName 传 NULL 时照 Python 隐式起 cmd.exe。标准流先写进临时目录里的
//     两个文件，结束后读回、删掉。
//   - 超时：Python 只结束直接子进程，之后不设时限地等管道关上（孙进程握着管道就一直挂着）；这里整棵树一起结束，按时返回
//     124。正常超时的输出两边相同（迁移文档第 10 节记为接受的差别）。
//   - os.environ 在 Windows 上把变量名转成大写；child_env 照着做，最后再强制带上 NoDefaultCurrentDirectoryInExePath。
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { SHARING_PAUSE_MS, SHARING_RETRIES, isPermissionError } from "@themis/base/fsutil";
import { EXE_SEARCH_GUARD } from "@themis/base/harden";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { D, S, W, WB, cmpCodePoints, codePoints, pyIntParse, pyRegex, pySplit, pySplitlines, pyStrip } from "@themis/base/pyre";
import { redactSecrets, stripAnsi } from "@themis/base/secrets";
import { runSupervised } from "@themis/base/supervise";
import { ensureArgvSafe } from "./argv.ts";
import { GIT_REDIRECT_VARS } from "./repo.ts";

const WIN = process.platform === "win32";

export const FALLBACK_THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"];
export const RESOURCE_FLAGS = ["--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-mcp"];
export const REQUIRED_PI_FLAGS = ["--provider", "--model", "--thinking", "--mode", "--no-session", "--tools", ...RESOURCE_FLAGS];
/** 与推送、发布或远程写入相关的变量，默认不传给执行器与检查命令（不是安全边界）。 */
export const DEFAULT_ENV_REMOVE = [
  "GITHUB_TOKEN", "GH_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GITLAB_TOKEN",
  "GL_TOKEN", "CI_JOB_TOKEN", "BITBUCKET_TOKEN", "NPM_TOKEN", "NODE_AUTH_TOKEN",
  "YARN_NPM_AUTH_TOKEN", "PYPI_TOKEN", "TWINE_USERNAME", "TWINE_PASSWORD", "CARGO_REGISTRY_TOKEN",
  "GEM_HOST_API_KEY", "NUGET_API_KEY", "SSH_AUTH_SOCK", "SSH_AGENT_PID", "VAULT_TOKEN",
  "CLAUDE_CODE_OAUTH_TOKEN",
];

/** 配置里的变量名数组（整份校验之后都是字符串）。 */
function names(config: PyDict, key: string): string[] {
  const value = config.get(key);
  return Array.isArray(value) ? value.map((name) => String(name).toUpperCase()) : [];
}

/** os.environ 的样子：Windows 上变量名是大写，大小写不同的同名变量留后一个的值、前一个的位置。 */
export function pyEnviron(): Map<string, string> {
  const environ = new Map<string, string>();
  for (const [name, value] of Object.entries(process.env)) {
    if (value !== undefined) environ.set(WIN ? name.toUpperCase() : name, value);
  }
  return environ;
}

/** pi_dispatch.child_env：移除仓库重定向变量与推送、发布类凭据，返回（环境，按码点排序的被移除的变量名）。 */
export function childEnv(config: PyDict, extra: ReadonlyMap<string, string> | null = null): [Map<string, string>, string[]] {
  const keep = new Set(names(config, "env_keep"));
  const remove = new Set([...DEFAULT_ENV_REMOVE, ...names(config, "env_remove")]);
  const env = new Map<string, string>();
  const removed: string[] = [];
  for (const [name, value] of pyEnviron()) {
    const upper = name.toUpperCase();
    if (GIT_REDIRECT_VARS.has(upper) || (remove.has(upper) && !keep.has(upper))) {
      removed.push(name);
      continue;
    }
    env.set(name, value);
  }
  env.set("GIT_TERMINAL_PROMPT", "0");
  env.set("GCM_INTERACTIVE", "never");
  if (!env.has("PYTHONDONTWRITEBYTECODE")) env.set("PYTHONDONTWRITEBYTECODE", "1");
  for (const [name, value] of extra ?? []) env.set(name, value);
  if (WIN) env.set(EXE_SEARCH_GUARD, "1");
  return [env, removed.sort(cmpCodePoints)];
}

export interface CaptureOptions {
  readonly cwd?: string | null;
  /** null 时继承当前环境。 */
  readonly env?: ReadonlyMap<string, string> | null;
  readonly timeout?: number;
}

/** bytes.decode("utf-8", "replace")：按最大子部分换成 U+FFFD，开头的 BOM 保留。 */
const decodeReplace = (path: string): string => new TextDecoder("utf-8", { ignoreBOM: true }).decode(readFileSync(path));

/** runSupervised 的 spawn_error 是 "类名: str(exc)"；Python 的 run_capture 分 FileNotFoundError（127）与其余 OSError（126）。 */
function spawnFailure(text: string): [number, string, string] {
  const match = /^([A-Za-z]+Error): /u.exec(text);
  if (match === null) return [126, "", text];
  return [match[1] === "FileNotFoundError" ? 127 : 126, "", text.slice(match[0].length)];
}

/** pi_dispatch.run_capture：运行短命令并捕获输出，stdin 接空设备。返回（退出码，stdout，stderr）。 */
export async function runCapture(cmd: readonly string[], options: CaptureOptions = {}): Promise<[number, string, string]> {
  const timeout = options.timeout ?? 60;
  const dir = mkdtempSync(join(tmpdir(), "themis-capture-"));
  try {
    const env = options.env ? [...options.env] : Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined);
    const result = await runSupervised(cmd, {
      cwd: options.cwd ?? process.cwd(),
      env,
      stdout: { path: join(dir, "stdout"), how: "create-new" },
      stderr: { path: join(dir, "stderr"), how: "create-new" },
      timeout,
      grace: 0,
      handleSignals: false,
    });
    if (result.spawn_error !== null) return spawnFailure(result.spawn_error);
    if (result.timed_out) return [124, "", `timeout after ${timeout}s`];
    return [result.exit_code as number, decodeReplace(join(dir, "stdout")), decodeReplace(join(dir, "stderr"))];
  } finally {
    await removeCaptureDir(dir);
  }
}

/**
 * 子进程树结束之后，还没退干净的进程可能仍拿着继承来的 stdout、stderr 句柄（Windows 上打开时不带 FILE_SHARE_DELETE），
 * 删除报 EPERM、EBUSY：照 fsutil 的共享冲突短暂重试，最后还失败照旧抛出。rmSync 的 maxRetries 在 Node 的同步版与 Bun 上都不管用（Node 24.19、Bun 1.4.2 实测）。
 */
async function removeCaptureDir(dir: string): Promise<void> {
  for (let attempt = 1; ; attempt += 1) {
    try {
      rmSync(dir, { recursive: true, force: true });
      return;
    } catch (error) {
      if (!isPermissionError(error) || attempt === SHARING_RETRIES) throw error;
      await new Promise((resolve) => setTimeout(resolve, SHARING_PAUSE_MS));
    }
  }
}

const FLAG_RE = pyRegex(`(?<!${W})(?<!-)(--[a-z][a-z0-9-]*)`, true);
const THINKING_RE = pyRegex(`--thinking${S}+<level>${S}+[^:\\n]*:${S}*([a-z, ]+)`);
// re.S 的 (.*?) 与 \Z；分节里的 ^ 照 re.M 只认 \n 之后（JS 的 m 标志还认 \r、U+2028、U+2029）
const TOOLS_SECTION_RE = pyRegex(`Built-in Tool Names:${S}*\\n([^]*?)(?:\\n${S}*\\n|$)`);
const TOOL_RE = pyRegex(`(?<![^\\n])${S}+([a-z_]+)${S}+-`, true);

export interface HelpInfo {
  readonly flags: string[];
  readonly thinking_levels: string[];
  readonly builtin_tools: string[];
}

/** pi_dispatch.parse_help：--help 里的长选项、思考级别（解析不出时用后备的七个）与内置工具名。 */
export function parseHelp(helpText: string): HelpInfo {
  const text = stripAnsi(helpText);
  const flags = [...new Set([...text.matchAll(FLAG_RE)].map((match) => match[1] as string))].sort(cmpCodePoints);
  let thinking = [...FALLBACK_THINKING_LEVELS];
  const levels = THINKING_RE.exec(text);
  if (levels) thinking = (levels[1] as string).split(",").map(pyStrip).filter(Boolean);
  const section = TOOLS_SECTION_RE.exec(text);
  const tools = section ? [...(section[1] as string).matchAll(TOOL_RE)].map((match) => match[1] as string) : [];
  return { flags, thinking_levels: thinking, builtin_tools: tools };
}

/** pi_dispatch.list_models_lines：表头之后每行的（provider，model，整行是否疑似凭据）。没有可用或匹配的模型时 Pi 输出的是
 * 一句说明，不是表格。 */
export function listModelsLines(output: string): [string, string, boolean][] {
  const rows: [string, string, boolean][] = [];
  let inTable = false;
  for (const line of pySplitlines(stripAnsi(output))) {
    const parts = pySplit(line);
    if (!inTable) {
      inTable = parts.length >= 2 && parts[0] === "provider" && parts[1] === "model";
      continue;
    }
    if (parts.length >= 2) rows.push([parts[0] as string, parts[1] as string, redactSecrets(line) !== line]);
  }
  return rows;
}

export function listModelsRows(output: string): [string, string][] {
  return listModelsLines(output).map(([provider, model]) => [provider, model]);
}

const NO_MODELS_RE = pyRegex(`(?<![^\\n])No models available${WB}`);
const NO_MATCH_RE = pyRegex(`(?<![^\\n])No models matching${WB}`);

/** pi_dispatch.list_models_empty_reason：no_models（没有任何可用模型）、no_match（有模型但没有匹配的）或 null。 */
export function listModelsEmptyReason(output: string): string | null {
  const text = stripAnsi(output);
  if (NO_MODELS_RE.test(text)) return "no_models";
  if (NO_MATCH_RE.test(text)) return "no_match";
  return null;
}

/** text[:n] 与 text[-n:]（按码点）。 */
const headOf = (text: string, size: number): string => codePoints(text).slice(0, size).join("");
const tailOf = (text: string, size: number): string => codePoints(text).slice(-size).join("");

/**
 * pi_dispatch.pi_model_readiness：一个执行模型的就绪事实与问题（列模型、auth check --no-refresh、思考级别），不调用模型。
 * env 为 null 时继承当前环境（调度器的 doctor），配置中心的 doctor 传 child_env(config)。
 */
export async function piModelReadiness(
  piCmd: readonly string[],
  provider: string,
  model: string,
  thinking: string | null,
  thinkingLevels: readonly string[],
  env: ReadonlyMap<string, string> | null,
): Promise<[PyDict, string[]]> {
  const facts: PyDict = new Map();
  const problems: string[] = [];
  const listCmd = [...piCmd, ...RESOURCE_FLAGS, "--list-models", model];
  const authCmd = [...piCmd, "auth", "check", "--provider", provider, "--model", model, "--json", "--no-refresh"];
  for (const cmd of [listCmd, authCmd]) ensureArgvSafe(cmd);
  const [listCode, listOut, listErr] = await runCapture(listCmd, { env, timeout: 90 });
  const rows = listModelsRows(listOut);
  const empty = rows.length ? null : listModelsEmptyReason(listOut);
  // 错误输出先脱敏再截取：Pi 转述 models.json 的解析错误时可能带出其中的凭据
  facts.set("executor_model_list", new Map<string, PyValue>([
    ["exit_code", BigInt(listCode)],
    ["rows", BigInt(rows.length)],
    ["empty_reason", empty],
    ["stderr_tail", tailOf(redactSecrets(pyStrip(listErr)), 300)],
  ]));
  if (listCode !== 0) {
    facts.set("executor_model_listed", null);
    problems.push(
      `pi --list-models 执行失败（退出码 ${listCode}）：${headOf(redactSecrets(pyStrip(listErr || listOut)), 200)}。在 Codex 等沙箱中运行时，` +
        "沙箱可能阻止了 pi 读取配置或联网：改在沙箱外运行 doctor 再判断",
    );
  } else {
    const listed = rows.some(([rowProvider, rowModel]) => rowProvider === provider && rowModel === model);
    facts.set("executor_model_listed", listed);
    if (!listed) {
      const reason =
        empty === "no_models"
          ? "（pi 没有任何可用模型：可能读不到 ~/.pi/agent 的配置或凭据，例如在沙箱中运行；改在沙箱外运行 doctor 再判断）"
          : empty === "no_match"
            ? `（pi 有可用模型，但没有与 ${model} 匹配的）`
            : "";
      problems.push(`执行模型 ${provider}/${model} 不在可用模型列表中${reason}`);
    }
  }
  // --no-refresh：不刷新、不改写凭据；过期的 OAuth 令牌会在真正运行时刷新
  const [authCode, authOut, authErr] = await runCapture(authCmd, { env, timeout: 90 });
  facts.set("executor_auth_check", new Map<string, PyValue>([
    ["exit_code", BigInt(authCode)],
    ["output", headOf(redactSecrets(pyStrip(authOut || authErr)), 2000)],
    ["refresh", false],
  ]));
  if (authCode !== 0) problems.push(`执行模型凭据未就绪（pi auth check --no-refresh 退出码 ${authCode}）`);
  if (thinking && !thinkingLevels.includes(thinking)) problems.push(`思考级别 ${thinking} 不受本机 pi 支持`);
  return [facts, problems];
}

/** agent_settled 事件自 pi 0.80.4 起提供。 */
export const MIN_PI_VERSION: readonly bigint[] = [0n, 80n, 4n];
const VERSION_RE = pyRegex(`(${D}+)[.](${D}+)[.](${D}+)`);

/** parse_version：文字里第一个 x.y.z（数字照 Python 正则的数字类，含其他文字的数字）。 */
export function parseVersion(text: string): bigint[] | null {
  const match = VERSION_RE.exec(text);
  return match ? [1, 2, 3].map((group) => pyIntParse(match[group] as string) as bigint) : null;
}

/** 元组比较：负数表示 a 小于 b。 */
export function compareVersion(a: readonly bigint[], b: readonly bigint[]): number {
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
    const [x, y] = [a[index] as bigint, b[index] as bigint];
    if (x !== y) return x < y ? -1 : 1;
  }
  return a.length - b.length;
}

/** _expects_settled：这个版本的 pi 会不会发 agent_settled；版本号读不出来时不知道（null）。 */
export function expectsSettled(versionText: string): boolean | null {
  const version = parseVersion(versionText);
  return version === null ? null : compareVersion(version, MIN_PI_VERSION) >= 0;
}
