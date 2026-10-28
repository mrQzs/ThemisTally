// 运行之前的预检与上下文取证（迁移第 ④b7c1 片）：pi_preflight、context_evidence、pi_agent_dir。run 在领取之前调用：
// 预检核对参数、思考级别、工具名、版本、模型与凭据，把四份输出与 preflight.json 写进 attempt 的 preflight/；取证照 Pi 的
// 规则找执行器会读的上下文文件，结果由 run 写成 context-files.json。
//   - 四份输出照 Path.write_text 写：文本模式，Windows 上换行写成 CRLF（write_json、write_text 都不转换）。
import { statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { pyItem, pyIter, pyReprValue, pyStrValue } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { expanduser, isWithin, purePathParent, purePathStr, pyExists, pyResolve } from "@themis/base/pypath";
import { WB, cmpCodePoints, codePoints, pyRegex, pyStrip } from "@themis/base/pyre";
import { redactObj, redactSecrets, stripAnsi } from "@themis/base/secrets";
import { sha256File, writeJson } from "./evidence.ts";
import { MIN_PI_VERSION, REQUIRED_PI_FLAGS, RESOURCE_FLAGS, compareVersion, listModelsRows, parseHelp, parseVersion, runCapture } from "./pi-cli.ts";
import { readJsonOr } from "./repo.ts";

const WIN = process.platform === "win32";
const LF = String.fromCharCode(10);
const CRLF = String.fromCharCode(13, 10);

const CONTEXT_FILE_NAMES = ["AGENTS.override.md", "AGENTS.md", "AGENTS.MD", "CLAUDE.md", "CLAUDE.MD"];
const PROJECT_TRUST_RESOURCES = [
  ".pi/settings.json",
  ".pi/extensions",
  ".pi/skills",
  ".pi/prompts",
  ".pi/themes",
  ".pi/SYSTEM.md",
  ".pi/APPEND_SYSTEM.md",
  ".agents/skills",
];
const PI_AUTH_RE = pyRegex(`${WB}pi auth${WB}`);

const firstChars = (text: string, count: number): string => codePoints(text).slice(0, count).join("");

/** pi_agent_dir：PI_CODING_AGENT_DIR（展开 ~），没有就是家目录下的 .pi/agent。 */
export function piAgentDir(): string {
  const configured = process.env["PI_CODING_AGENT_DIR"];
  return configured ? purePathStr(expanduser(configured)) : purePathStr(expanduser("~"), ".pi", "agent");
}

/** 与 Pi 相同：每个目录只取第一个存在的上下文文件。 */
function contextFileIn(directory: string): string | null {
  for (const name of CONTEXT_FILE_NAMES) {
    const candidate = purePathStr(directory, name);
    if (isFile(candidate)) return candidate;
  }
  return null;
}

/** context_evidence：照 Pi 的发现规则，记下执行器会读的规则文件（路径与哈希）、全局的系统提示词文件与设置的键。 */
export function contextEvidence(workDir: string, contextMode: string): PyDict {
  const agentDir = piAgentDir();
  const files: PyDict[] = [];
  const warnings: string[] = [];
  if (contextMode === "project") {
    const globalFile = contextFileIn(agentDir);
    if (globalFile !== null) files.push(new Map([["scope", "global"], ["path", globalFile]]));
    const chain: [string, string][] = [];
    let current = pyResolve(workDir);
    for (;;) {
      const found = contextFileIn(current);
      if (found !== null) chain.push([current, found]);
      const parent = purePathParent(current);
      if (parent === current) break;
      current = parent;
    }
    for (const [directory, found] of chain.reverse()) {
      const inside = isWithin(directory, workDir);
      files.push(new Map([["scope", inside ? "worktree" : "ancestor"], ["path", found]]));
      if (!inside) warnings.push(`工作副本之外的上下文文件也会被执行器读取：${found}`);
    }
  }
  for (const item of files) {
    const file = item.get("path") as string;
    item.set("sha256", sha256File(file));
    item.set("bytes", BigInt(statSync(file).size));
  }
  const systemFiles: PyDict[] = [];
  for (const name of ["SYSTEM.md", "APPEND_SYSTEM.md"]) {
    const file = purePathStr(agentDir, name);
    if (!isFile(file)) continue;
    systemFiles.push(new Map([["path", file], ["sha256", sha256File(file)]]));
    warnings.push(`全局 ${name} 会改变执行器系统提示词：${file}`);
  }
  const ignoredResources = PROJECT_TRUST_RESOURCES.filter((name) => pyExists(purePathStr(workDir, name)));
  let settingsKeys: string[] = [];
  const settingsPath = purePathStr(agentDir, "settings.json");
  if (isFile(settingsPath)) {
    const data = readJsonOr(settingsPath, new Map());
    settingsKeys = data instanceof Map ? ([...data.keys()] as string[]).sort(cmpCodePoints) : [];
  }
  return new Map<string, PyValue>([
    ["context_mode", contextMode],
    ["agent_dir", agentDir],
    ["context_files", files],
    ["global_system_files", systemFiles],
    ["global_settings_keys", settingsKeys],
    ["project_resources_ignored_by_no_approve", ignoredResources],
    ["warnings", warnings],
  ]);
}

/** pi_preflight：运行模型之前核对参数支持、思考级别、工具名、版本、模型存在与凭据就绪；交回（并写进 preflight.json）脱敏后的结果。 */
export async function piPreflight(piCmd: readonly string[], cwd: string, executor: PyValue, outDir: string, env: ReadonlyMap<string, string>): Promise<PyDict> {
  pathMkdir(outDir, true, true);
  const problems: string[] = [];
  const notes: string[] = [];
  let [code, out, err] = await runCapture([...piCmd, ...RESOURCE_FLAGS, "--help"], { cwd, env, timeout: 90 });
  const helpText = redactSecrets(stripAnsi(out + err));
  writeTextMode(path.join(outDir, "pi-help.txt"), helpText);
  const info = parseHelp(out + err);
  if (code !== 0) problems.push(`pi --help 退出码 ${code}：${firstChars(redactSecrets(pyStrip(err || out)), 300)}`);
  const required = [...REQUIRED_PI_FLAGS, ...(pyItem(executor, "context_files") === "none" ? ["--no-context-files"] : [])];
  const missing = required.filter((flag) => !info.flags.includes(flag));
  if (missing.length) problems.push(`本机 pi 不支持参数：${missing.join(", ")}`);
  const thinking = pyItem(executor, "thinking");
  if (!info.thinking_levels.includes(thinking as string)) {
    problems.push(`思考级别 ${pyStrValue(thinking)} 不在本机 pi 支持列表 ${pyReprValue(info.thinking_levels)} 中（Pi 对无效值只警告并忽略）`);
  }
  if (info.builtin_tools.length) {
    const unknown = pyIter(pyItem(executor, "tools")).filter((tool) => !info.builtin_tools.includes(tool as string));
    if (unknown.length) problems.push(`本机 pi 没有这些内置工具：${unknown.join(", ")}（Pi 会静默忽略未知工具名）`);
  }
  [code, out, err] = await runCapture([...piCmd, "--version"], { cwd, env, timeout: 60 });
  const versionText = redactSecrets(pyStrip(out || err));
  writeTextMode(path.join(outDir, "pi-version.txt"), versionText + LF);
  const version = parseVersion(versionText);
  if (code !== 0 || version === null) problems.push(`无法读取 pi 版本：${firstChars(versionText, 200)}`);
  else if (compareVersion(version, MIN_PI_VERSION) < 0) notes.push(`pi ${versionText} 低于 ${MIN_PI_VERSION.join(".")}，缺少 agent_settled 事件；将退回用 agent_end 判断结束`);
  const provider = pyItem(executor, "provider") as string;
  const model = pyItem(executor, "model") as string;
  [code, out, err] = await runCapture([...piCmd, ...RESOURCE_FLAGS, "--list-models", model], { cwd, env, timeout: 90 });
  writeTextMode(path.join(outDir, "list-models.txt"), redactSecrets(stripAnsi(out + err)));
  const rows = listModelsRows(out);
  if (code !== 0) {
    problems.push(`pi --list-models 失败：${firstChars(redactSecrets(pyStrip(err || out)), 300)}`);
  } else if (!rows.some(([rowProvider, rowModel]) => rowProvider === provider && rowModel === model)) {
    problems.push(`模型 ${provider}/${model} 不在本机可用模型列表中（可能是拼写错误、缺少凭据或未在 models.json 定义；Pi 对未知模型可能只警告并按自定义 ID 发送）`);
  }
  // Python 把 pi-help.txt 读回来再找：读回来只差换行（CRLF 与单独的 CR 都成了 LF），不影响这个匹配
  if (PI_AUTH_RE.test(helpText)) {
    [code, out, err] = await runCapture([...piCmd, "auth", "check", "--provider", provider, "--model", model, "--json"], { cwd, env, timeout: 90 });
    writeTextMode(path.join(outDir, "auth-check.json"), redactSecrets(pyStrip(out) ? out : err));
    if (code !== 0) problems.push(`pi auth check 未就绪（退出码 ${code}）：${firstChars(redactSecrets(pyStrip(out || err)), 300)}`);
  } else {
    notes.push("本机 pi 没有 auth 子命令，跳过凭据检查");
  }
  const help: PyDict = new Map<string, PyValue>([
    ["flags", info.flags],
    ["thinking_levels", info.thinking_levels],
    ["builtin_tools", info.builtin_tools],
  ]);
  const result = redactObj(
    new Map<string, PyValue>([
      ["checked_at", utcNow()],
      ["pi_command", [...piCmd]],
      ["pi_version", versionText],
      ["help", help],
      ["problems", problems],
      ["notes", notes],
      ["ok", problems.length === 0],
    ]),
  ) as PyDict;
  writeJson(path.join(outDir, "preflight.json"), result);
  return result;
}

/** Path.write_text(text, encoding="utf-8")：文本模式，Windows 上换行写成 CRLF。 */
function writeTextMode(file: string, text: string): void {
  writeFileSync(file, Buffer.from(WIN ? text.replaceAll(LF, CRLF) : text, "utf8"));
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}
