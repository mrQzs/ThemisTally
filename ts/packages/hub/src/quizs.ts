// quizs 载体（第 137 轮，P1：名册没换，协调人照旧走 pi；换载体要站主同意）：kit_hub.py 的 resolve_quizs_command、fenced_json、
// quizs_snapshot、audit_quizs_stream。交付是最后回答里的一个 json 代码块（Quizs 的 v1 交付：result 的 final_text 就是这段回答），
// 内核再按岗位 schema 核验；输入目录交 quizs snapshot capture 冻成只读快照，建 git 树的事在 Quizs 里做一次。
import { utcNow } from "@themis/base/clock";
import { findBunOnPath } from "@themis/base/native";
import { pyGet, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyJsonError, type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { jsonlLines } from "@themis/base/jsonl";
import { osPathJoin, purePathParent, purePathStr } from "@themis/base/pypath";
import { pyLower, pyStrip } from "@themis/base/pyre";
import { pyWhich } from "@themis/base/pyshutil";
import { type SuperviseResult, runSupervised } from "@themis/base/supervise";
import { writeJson } from "@themis/dispatcher/evidence";
import { runCapture } from "@themis/dispatcher/pi-cli";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join } from "node:path";
import {
  EXIT_BLOCKED, QUIZS_BEHAVIOR_ERRORS, QUIZS_CERT_MARGIN, QUIZS_DOWN_FILE, QUIZS_FENCE_CLOSE, QUIZS_FENCE_OPEN, QUIZS_LIVE_FILES, QUIZS_OUTPUT_CUT, QUIZS_OVERLOADED, QUIZS_PERMIT_HELD,
  QUIZS_FORMAT_NOTE, QUIZS_LIVE_NAMES, QUIZS_LIVE_ROOT, QUIZS_PROFILE_IDS, QUIZS_SCHEMA_NOTES, QUIZS_STATE_DIR,
  QUIZS_CACHE_DIR, QUIZS_CACHE_MARK, QUIZS_JOB_FILE, QUIZS_JOB_LIMITS, QUIZS_MAIN_TAIL, QUIZS_NATIVE_ENV, QUIZS_NATIVE_FILES, QUIZS_OUTPUT_FILE,
  QUIZS_OUTPUT_LIMITS, QUIZS_PREPARE_TIMEOUT, QUIZS_PROFILE_FILE, QUIZS_WORKTREE_LIMITS, QUIZS_WORKTREE_ROLES,
  ROSTER, THROTTLE_RESET_MARGIN,
  type RosterSpec,
} from "./constants.ts";
import { type HubBindings, boundSpec } from "./bindings.ts";
import { streamEvents } from "./audit.ts";
import { HubError } from "./errors.ts";
import { kernelEnv } from "./runpd.ts";

const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);

/** 第 145 轮：这一回合实际用的名册配置与退回的原因：quizs 岗位起不了就换成替补的字段。提示与起回合都按它，交差方式才对得上。
 *  hubRoot 给了信箱目录，才看得到“刚才自己没起来”的标记（第 150 轮）。
 *  第 154 轮：bindings 是配置中心里各岗位的绑定（hubBindings），给了就先叠到名册上。 */
export function effectiveSpec(agent: string, now: number, hubRoot: string | null = null, bindings: HubBindings | null = null): [RosterSpec, string | null] {
  const { fallback: substitute, ...listed } = boundSpec(agent, bindings?.get(String((ROSTER[agent] as RosterSpec).role)));
  const stateDir = hubRoot === null ? null : join(hubRoot, QUIZS_STATE_DIR);
  // 第 198 轮：工作区模式的岗位另要原生组件与命令档案的程序
  const reason = listed.adapter === "quizs" && substitute
    ? (quizsUnready(now, listed.timeout ?? 1800, stateDir, pyStrValue(listed.provider ?? null))
      ?? (QUIZS_WORKTREE_ROLES.includes(String(listed.role)) ? quizsWorktreeUnready() : null))
    : null;
  return [reason === null ? listed : { ...listed, ...substitute }, reason];
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** 第 156 轮：kit_hub.quizs_live_files：这个提供方的三份 live 文件，交回 [{旗标: 路径}, 问题]。先找信箱的 quizs-live/<提供方>/，三份都在就用；
 *  不全时退回环境变量给的那一套（第 141 轮），它的提供方档案认得出是别家的就不用。 */
export function quizsLiveFiles(hubRoot: string | null, provider: string): [Map<string, string> | null, string | null] {
  if (hubRoot !== null) {
    const folder = join(hubRoot, QUIZS_LIVE_ROOT, provider);
    const found = new Map(QUIZS_LIVE_NAMES.map(([flag, name]) => [flag, join(folder, name)] as [string, string]));
    if ([...found.values()].every((path) => isFile(path))) return [found, null];
  }
  for (const [, name] of QUIZS_LIVE_FILES) {
    if (!process.env[name]) return [null, `没有设 ${name}`];
  }
  let owner: PyValue = null;
  try {
    const profile = loads(readFileSync(process.env["QUIZS_PROVIDER_PROFILE"] as string, "utf-8"));
    owner = profile instanceof Map ? (profile.get("id") ?? null) : null;
  } catch (error) {
    if (!(error instanceof PyJsonError) && !(error instanceof Error && "code" in error)) throw error;
  }
  if (typeof owner === "string" && Object.values(QUIZS_PROFILE_IDS).includes(owner) && owner !== QUIZS_PROFILE_IDS[provider]) {
    return [null, `环境给的 live 文件是 ${owner} 的，没有 ${provider} 的（信箱的 ${QUIZS_LIVE_ROOT}/${provider}/ 不全）`];
  }
  return [new Map(QUIZS_LIVE_FILES.map(([flag, name]) => [flag, process.env[name] as string] as [string, string])), null];
}

/** 第 148 轮：这个提供方的那份 live plan（第 156 轮起不只看环境），交回 [plan, 问题]。 */
export function quizsLivePlan(path: string): [PyDict | null, string | null] {
  let plan: PyValue;
  try {
    plan = loads(readFileSync(path, "utf-8"));
  } catch (error) {
    if (!(error instanceof PyJsonError) && !(error instanceof Error && "code" in error)) throw error;
    return [null, `读不出 live plan ${path}`];
  }
  if (!(plan instanceof Map) || typeof pyGet(plan, "plan_id") !== "string") return [null, "live plan 里没有 plan_id"];
  return [plan, null];
}

/** 第 150 轮：这个提供方的 quizs 刚才自己没起来、还在歇着时的原因；没有标记、标记读不出或已经到点是 null。 */
export function quizsDown(now: number, stateDir: string | null, provider: string): string | null {
  if (stateDir === null) return null;
  let mark: PyValue;
  try {
    mark = loads(readFileSync(join(stateDir, QUIZS_DOWN_FILE.replace("%s", provider)), "utf-8"));
  } catch (error) {
    if (!(error instanceof PyJsonError) && !(error instanceof Error && "code" in error)) throw error;
    return null;
  }
  const [until, reason] = mark instanceof Map ? [pyGet(mark, "until"), pyGet(mark, "reason")] : [null, null];
  if (typeof until !== "bigint" || typeof reason !== "string" || BigInt(now) >= until) return null;
  return `quizs 刚才自己没起来（${reason}），到纪元秒 ${until} 为止用替补`;
}

/** 第 143 轮：quizs 回合起不了的原因（命令没设，这个提供方没有 live 文件，证书读不出或撑不完这一回合，live plan 读不出，
 *  刚才自己没起来还在歇着）；起得了是 null。第 156 轮：按这一回合的提供方找（stateDir 的上一层是信箱目录）。 */
export function quizsUnready(now: number, timeout: number, stateDir: string | null, provider: string): string | null {
  if (!process.env["QUIZS_CMD"]) return "没有设 QUIZS_CMD";
  const [files, problem] = quizsLiveFiles(stateDir === null ? null : dirname(stateDir), provider);
  if (files === null) return problem;
  const path = files.get("--qualification") as string;
  let data: PyValue;
  try {
    data = loads(readFileSync(path, "utf-8"));
  } catch (error) {
    if (!(error instanceof PyJsonError) && !(error instanceof Error && "code" in error)) throw error;
    return `读不出资格证书 ${path}`;
  }
  const expires = data instanceof Map ? pyGet(data, "expires_at_ms") : null;
  if (typeof expires !== "bigint") return "资格证书里没有到期时刻";
  if (expires < BigInt((now + timeout + QUIZS_CERT_MARGIN) * 1000)) return `资格证书撑不完这一回合（${expires} 毫秒时到期）`;
  return quizsLivePlan(files.get("--live-plan") as string)[1] ?? quizsDown(now, stateDir, provider);
}

/** 第 198 轮：kit_hub.ICACLS_EXE（给缓存根打 Low 标签；用绝对路径起，同 codekit.secrets）。 */
const ICACLS_EXE = osPathJoin(process.env["SystemRoot"] || "C:\\Windows", "System32", "icacls.exe");
const BS = String.fromCharCode(92);

/** 第 198 轮：kit_hub.quizs_native_dir：Quizs 原生组件所在的目录（QUIZS_NATIVE_FILES 都在才算），找不到是 null。 */
export function quizsNativeDir(): string | null {
  const raw = process.env[QUIZS_NATIVE_ENV];
  let candidates: string[];
  if (raw) {
    candidates = [raw];
  } else {
    let command: string[] = [];
    try {
      command = resolveQuizsCommand();
    } catch (error) {
      if (!(error instanceof HubError) && !(error instanceof PyJsonError)) throw error;
    }
    candidates = command.filter((part) => part.split(BS).join("/").endsWith(QUIZS_MAIN_TAIL)).map((part) => {
      let root = part;
      for (let step = 0; step < 6; step++) root = purePathParent(root);
      return purePathStr(root, "dist", "native");
    });
  }
  return candidates.find((folder) => QUIZS_NATIVE_FILES.every((name) => isFile(purePathStr(folder, name)))) ?? null;
}

/** 第 198 轮：kit_hub.quizs_worktree_unready：工作区模式起不了的原因（原生组件找不到，命令档案要的程序不在 PATH 上）；起得了是 null。 */
export function quizsWorktreeUnready(): string | null {
  if (quizsNativeDir() === null) {
    return `找不到 Quizs 的原生组件（${QUIZS_NATIVE_FILES.join("、")}）：设 ${QUIZS_NATIVE_ENV} 指向放它们的目录，或让 QUIZS_CMD 指向 Quizs 源码入口`;
  }
  const missing = ["python", "git", "node"].filter((name) => !pyWhich(name));
  return missing.length > 0 ? `门禁的命令档案缺程序：${missing.join("、")} 不在 PATH 上` : null;
}

/** 第 198 轮：kit_hub.quizs_cache_root：门禁的 npm、bun 缓存根（信箱下 quizs-cache/gate，跨回合保留）。第一次用时建好、用 icacls 打上
 *  Low 标签（执行域的低完整性子进程才写得进），打好了留个标记；打不上照常开回合，问题写进回合记录。 */
export async function quizsCacheRoot(hubRoot: string): Promise<[string, string | null]> {
  const root = purePathStr(hubRoot, QUIZS_CACHE_DIR, "gate");
  if (isFile(purePathStr(root, QUIZS_CACHE_MARK))) return [root, null];
  mkdirSync(root, { recursive: true });
  const [code] = await runCapture([ICACLS_EXE, root, "/setintegritylevel", "(OI)(CI)low"], { timeout: 60 });
  if (code !== 0) return [root, `门禁的缓存根打不上 Low 标签（icacls 退出码 ${code === null ? "None" : code}）：执行域里 npm、bun 写不了缓存`];
  writeFileSync(purePathStr(root, QUIZS_CACHE_MARK), utcNow() + LF, "utf-8");
  return [root, null];
}

/** 第 198 轮：kit_hub.quizs_command_profile：门禁在 quizs 上的命令档案（Quizs M11）：python 脚本与 node，node、bun、git 的目录进 PATH，
 *  npm、bun 的缓存指到缓存根；git 照工作目录实际的 core.autocrlf 钉住（Quizs 藏起了系统与全局的 git 配置）。 */
export async function quizsCommandProfile(workspace: string, cacheRoot: string): Promise<PyDict> {
  const [python, git, node] = ["python", "git", "node"].map((name) => pyStrValue(pyWhich(name))) as [string, string, string];
  const bun = findBunOnPath(Object.fromEntries(kernelEnv()));
  const [code, out] = await runCapture([git, "-C", workspace, "config", "--get", "core.autocrlf"], { timeout: 60 });
  const autocrlf = pyLower(pyStrip(out));
  const folders = [node, ...(bun !== null ? [bun] : []), git].map((path) => purePathParent(path));
  const gitConfig: PyDict = code === 0 && ["true", "false", "input"].includes(autocrlf) ? new Map([["core.autocrlf", autocrlf]]) : new Map();
  return new Map<string, PyValue>([["python", python], ["git", git], ["gitConfig", gitConfig], ["pythonScripts", true], ["node", node],
    ["pathEntries", [...new Set(folders)]], ["cacheRoot", cacheRoot]]);
}

/** 第 198 轮：kit_hub.quizs_gate_prepare：开 quizs 上的门禁回合之前在 Medium 预装 ts/node_modules（11-19 实测三：执行域的低完整性令牌建不了
 *  symlink，门禁流水线里的 bun install 只在已经装好时才是空操作）。没有 ts/package.json 就不装；装不好只写进回合记录，照常开回合。 */
export async function quizsGatePrepare(workspace: string): Promise<string | null> {
  if (!isFile(purePathStr(workspace, "ts", "package.json"))) return null;
  const bun = findBunOnPath(Object.fromEntries(kernelEnv()));
  if (bun === null) return "找不到 Bun，门禁工作目录的 ts 依赖没有预装：执行域里门禁流水线的 bun install 会失败";
  const dir = mkdtempSync(join(tmpdir(), "themis-gate-prepare-"));
  let result: SuperviseResult;
  try {
    result = await runSupervised([bun, "install", "--frozen-lockfile"], {
      cwd: purePathStr(workspace, "ts"), env: [...kernelEnv()], stdout: { path: join(dir, "output"), how: "create-new" }, stderr: "stdout",
      timeout: QUIZS_PREPARE_TIMEOUT,
    });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  if (result.exit_code === 0 && !result.timed_out) return null;
  return `门禁工作目录的 ts 依赖没装好（bun install 退出码 ${result.exit_code === null ? "None" : result.exit_code}${result.timed_out ? "，超时" : ""}）：`
    + "执行域里门禁流水线的 bun install 会失败";
}

/** 第 198 轮：kit_hub.quizs_worktree_args：工作区模式的参数（Quizs M11），交回 [参数, 起不了的原因]：写命令档案与两份上限进回合目录、
 *  备好缓存根、预装 ts 依赖；备不好的写进 notes（回合记录的 warnings），照常开回合。 */
export async function quizsWorktreeArgs(hubRoot: string, workspace: string, turnDir: string, notes: string[]): Promise<[string[], string | null]> {
  const native = quizsNativeDir();
  if (native === null) return [[], quizsWorktreeUnready()];
  const [cache, problem] = await quizsCacheRoot(hubRoot);
  writeJson(purePathStr(turnDir, QUIZS_PROFILE_FILE), await quizsCommandProfile(workspace, cache));
  // 整数照 Python 写成整数（PyValue 的整数是 bigint；常量表里是数字，常量对照用 JSON.stringify 取它）
  const asPy = (table: Readonly<Record<string, number | string>>): PyDict =>
    new Map<string, PyValue>(Object.entries(table).map(([key, value]) => [key, typeof value === "number" ? BigInt(value) : value]));
  writeJson(purePathStr(turnDir, QUIZS_OUTPUT_FILE), asPy(QUIZS_OUTPUT_LIMITS));
  writeJson(purePathStr(turnDir, QUIZS_JOB_FILE), asPy(QUIZS_JOB_LIMITS));
  const prepared = await quizsGatePrepare(workspace);
  notes.push(...[problem, prepared].filter((note): note is string => note !== null && note !== ""));
  return [["--worktree", "--worktree-runner", purePathStr(native, QUIZS_NATIVE_FILES[0]), "--worktree-fs", purePathStr(native, QUIZS_NATIVE_FILES[1]),
    "--command-profile", purePathStr(turnDir, QUIZS_PROFILE_FILE), "--output-limits", purePathStr(turnDir, QUIZS_OUTPUT_FILE),
    "--job-limits", purePathStr(turnDir, QUIZS_JOB_FILE), ...QUIZS_WORKTREE_LIMITS.flat()], null];
}

/** quizs 的命令：QUIZS_CMD 是 JSON 的字符串列表（测试与开发时指向源码入口），缺省是 PATH 里的 quizs。 */
export function resolveQuizsCommand(): string[] {
  const raw = process.env["QUIZS_CMD"];
  if (!raw) return [pyWhich("quizs") ?? "quizs"];
  const value = loads(raw);
  if (!Array.isArray(value) || value.length === 0 || !value.every((item) => typeof item === "string" && item !== "")) {
    throw new HubError("QUIZS_CMD 要是非空的字符串列表（JSON）", EXIT_BLOCKED);
  }
  return value as string[];
}

/** quizs 回合的交付：最后的回答里恰好一个 json 代码块，内容是 JSON 对象；别的一律 null。 */
export function fencedJson(text: string): PyDict | null {
  const blocks: string[] = [];
  let current: string[] | null = null;
  for (const line of text.split(CR + LF).join(LF).split(LF)) {
    if (current === null) {
      if (pyStrip(line) === QUIZS_FENCE_OPEN) current = [];
    } else if (pyStrip(line) === QUIZS_FENCE_CLOSE) {
      blocks.push(current.join(LF));
      current = null;
    } else {
      current.push(line);
    }
  }
  if (blocks.length !== 1 || current !== null) return null;
  let value: PyValue;
  try {
    value = loads(blocks[0] as string);
  } catch (error) {
    if (error instanceof PyJsonError) return null;
    throw error;
  }
  return value instanceof Map ? value : null;
}

/** 第 156 轮：kit_hub.workspace_tree：工作目录此刻的整棵树（已跟踪的改动与没被忽略的新文件都算），交回 [树的 id, 问题]。用一份临时索引：
 *  先抄工作目录自己的索引（git add 只重算变了的文件），工作目录与它的索引都不动。 */
export async function workspaceTree(gitExe: string, workspace: string, index: string): Promise<[string | null, string | null]> {
  const [found, out] = await runCapture([gitExe, "-C", workspace, "rev-parse", "--git-path", "index"], { timeout: 60 });
  const named = pyStrip(out);
  const own = isAbsolute(named) ? named : join(workspace, named);
  const env = new Map(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
  env.set("GIT_INDEX_FILE", index);
  let code = found;
  let tree = "";
  try {
    if (code === 0 && isFile(own)) copyFileSync(own, index);
    [code] = await runCapture([gitExe, "-C", workspace, "add", "-A"], { env, timeout: 300 });
    if (code === 0) [code, tree] = await runCapture([gitExe, "-C", workspace, "write-tree"], { env, timeout: 120 });
  } finally {
    rmSync(index, { force: true });
  }
  if (code !== 0 || !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(pyStrip(tree))) {
    return [null, `算不出工作目录的树（git add 或 write-tree 退出码 ${code}），quizs 冻结不了这一回合的仓库，没有起这一回合`];
  }
  return [pyStrip(tree), null];
}

/** 这一回合的输入目录交给 quizs snapshot capture 冻成只读快照：交回（manifest_ref, 问题）。
 *  第 156 轮：给了 view（读仓库的岗位的工作目录）就冻那个目录此刻的整棵树，输入目录叠在上面（index 是算树用的临时索引）。 */
export async function quizsSnapshot(quizsCmd: readonly string[], sessionsDir: string, inputs: string, env: Map<string, string>,
  view: string | null = null, index: string | null = null): Promise<[string | null, string | null]> {
  const gitExe = pyWhich("git");
  if (gitExe === null) return [null, "找不到 git，quizs 冻结不了这一回合的输入，没有起这一回合"];
  let source = ["--dir", inputs];
  if (view !== null && index !== null) {
    const [tree, problem] = await workspaceTree(gitExe, view, index);
    if (tree === null) return [null, problem];
    source = ["--repository", view, "--oid", tree, "--all-files", "--overlay-dir", inputs];
  }
  const [code, out] = await runCapture([...quizsCmd, "snapshot", "capture", "--session-dir", sessionsDir, ...source, "--git-executable", gitExe],
    { env, timeout: 180 });
  const lines = jsonlLines(out).filter((line) => pyStrip(line) !== ""); // 输出以换行结尾：最后一个是空串
  let last: PyValue = null;
  try {
    last = lines.length > 0 ? loads(lines[lines.length - 1] as string) : null;
  } catch (error) {
    if (!(error instanceof PyJsonError)) throw error;
  }
  if (code !== 0 || !(last instanceof Map) || typeof last.get("manifest_ref") !== "string") {
    const reason = last instanceof Map ? pyGet(last, "error_class") : null;
    return [null, `quizs 冻结不了这一回合的输入（snapshot capture 退出码 ${code}，${pyTruthy(reason) ? pyStrValue(reason) : "读不出结果"}），没有起这一回合`];
  }
  return [last.get("manifest_ref") as string, null];
}

/** 第 152 轮：Quizs 在 result 的 error_details 里写的具体原因，都是 Quizs 自己的固定字面量：provider_code 的 OUTPUT_TOKEN_LIMIT
 *  与 overloaded_error（第 181 轮）、format_reason（回应完整之后哪一项检查没过，可带出问题的工具名）、decoder_reason（流解码出的
 *  毛病）。没有就是空串。 */
function quizsErrorReason(result: PyValue): string {
  const details = pyGet(result, "error_details");
  if (!(details instanceof Map)) return "";
  const code = pyGet(details, "provider_code");
  if (code === QUIZS_OUTPUT_CUT || code === QUIZS_OVERLOADED) return code;
  const reason = pyTruthy(pyGet(details, "format_reason")) ? pyGet(details, "format_reason") : pyGet(details, "decoder_reason");
  if (typeof reason !== "string") return "";
  const tool = pyGet(details, "tool_name");
  const named = typeof tool === "string";
  return named ? `${reason}，工具 ${tool}` : reason;
}

/**
 * quizs 回合的审计：逐行读 Quizs 的 JSONL。init 与 tool_call 里名册之外的工具算越权；result 给出退出码、模型、思考档位、用量与
 * 最后的回答（交付是其中一个 json 代码块）。退出码 3 带 retry_at 时直接扣到那时，不带时照第 38 轮的限流退避。
 */
export function auditQuizsStream(lines: readonly string[], spec: PyValue): PyDict {
  const allowed = new Set((pyGet(spec, "tools") as PyValue[]).map((tool) => pyStrValue(tool)));
  const violations: string[] = [];
  const warnings: string[] = [];
  const toolCalls: PyDict = new Map();
  const audit: PyDict = new Map<string, PyValue>([["violations", violations], ["tool_calls", toolCalls], ["models", []], ["effective_levels", []],
    ["usage", null], ["cost_usd", null], ["delivered", null], ["delivery_error", null], ["api_error", null], ["terminal", false], ["warnings", warnings],
    ["deliver_refusals", []], ["deliver_last_refusal", null], ["thinking_chars", null], ["thinking_tokens", null], ["rate_limited_until", null]]);
  let result: PyDict | null = null;
  // 第 175 轮：与 pi、claude 的审计一样用 streamEvents：空行不算（事件流以换行结尾，原来每个 Quizs 回合都报一条读不出，候选 #48），
  // 读不出的非空行（回合被收掉时最后一行没写完）记个数
  const [events, unreadable] = streamEvents(lines);
  if (unreadable) warnings.push(`quizs 的事件流里有 ${unreadable} 行读不出`);
  for (const event of events) {
    const kind = event.get("type");
    if (kind === "init") {
      const tools = pyGet(event, "tools");
      for (const tool of pyTruthy(tools) ? (tools as PyValue[]) : []) {
        const name = tool instanceof Map ? pyGet(tool, "name") : null;
        if (!allowed.has(name as string)) violations.push(`quizs 给模型的工具里有名册之外的 ${pyStrValue(name)}`);
      }
    } else if (kind === "tool_call") {
      const name = pyGet(event, "name");
      toolCalls.set(name as string, ((toolCalls.get(name as string) as bigint | undefined) ?? 0n) + 1n);
      if (!allowed.has(name as string)) violations.push(`调了名册之外的工具 ${pyStrValue(name)}`);
    } else if (kind === "final_schema_rejected" && typeof event.get("action") === "string" && Object.hasOwn(QUIZS_SCHEMA_NOTES, event.get("action") as string)) { // 第 175 轮
      const errors = Array.isArray(event.get("errors")) ? (event.get("errors") as PyValue[]) : [];
      const text = errors.slice(0, 3).map((error) => pyStrValue(error)).join("；");
      warnings.push((QUIZS_SCHEMA_NOTES[event.get("action") as string] as string).replace("%s", () => text));
    } else if (kind === "final_format_rejected") { // 第 177 轮
      const errors = Array.isArray(event.get("errors")) ? (event.get("errors") as PyValue[]) : [];
      const text = errors.slice(0, 3).map((error) => pyStrValue(error)).join("；");
      warnings.push(QUIZS_FORMAT_NOTE.replace("%s", () => text));
    } else if (kind === "result") {
      result = event;
    }
  }
  if (result === null) {
    audit.set("api_error", "quizs 没有交回 result 事件（看这一回合的 stderr.log）");
    return audit;
  }
  audit.set("terminal", true);
  if (pyTruthy(pyGet(result, "actual_model"))) audit.set("models", [pyGet(result, "actual_model")]);
  const thinking = pyGet(result, "thinking");
  const effective = thinking instanceof Map ? pyGet(thinking, "effective") : null;
  if (pyTruthy(effective)) audit.set("effective_levels", [effective]);
  // 第 168 轮：Quizs 照提供方档案把要求的档位映射成实际发出的那一档（档案不支持时封顶），生效要提供方回报了才有
  const mapped = thinking instanceof Map ? pyGet(thinking, "mapped") : null;
  audit.set("mapped_level", pyTruthy(mapped) ? mapped : null);
  const usage = pyGet(result, "usage");
  if (usage instanceof Map && pyGet(usage, "total_input") !== null) {
    const count = (key: string): bigint => (pyTruthy(pyGet(usage, key)) ? (pyGet(usage, key) as bigint) : 0n);
    audit.set("usage", new Map<string, PyValue>([["input", (pyGet(usage, "total_input") as bigint) - count("cache_read") - count("cache_write")],
      ["cacheRead", count("cache_read")], ["cacheWrite", count("cache_write")], ["output", count("output")]]));
  }
  const code = pyGet(result, "exit_code");
  if (code !== 0n) {
    const errorClass = pyStrValue(pyGet(result, "error_class"));
    const reason = quizsErrorReason(result); // 第 152 轮：具体原因接在错误类别后面，带给重交的回合与站主
    const shown = reason ? `${errorClass}，${reason}` : errorClass;
    const kind = reason === QUIZS_OUTPUT_CUT ? QUIZS_OUTPUT_CUT : errorClass;
    if (Object.hasOwn(QUIZS_BEHAVIOR_ERRORS, kind)) {
      audit.set("delivery_error", `quizs 退出码 ${pyStrValue(code)}（${shown}）：${QUIZS_BEHAVIOR_ERRORS[kind] as string}`);
      return audit;
    }
    audit.set("api_error", errorClass === "QUEUE_TIMEOUT" ? QUIZS_PERMIT_HELD : `quizs 退出码 ${pyStrValue(code)}（${shown}）`);
    audit.set("quizs_down", code === 2n); // 第 150 轮：配置类问题，请求没有发出去
    const retryAt = pyGet(result, "retry_at");
    if (code === 3n && typeof retryAt === "string") audit.set("rate_limited_until", BigInt(Math.floor(Date.parse(retryAt) / 1000) + THROTTLE_RESET_MARGIN));
    return audit;
  }
  const text = pyGet(result, "final_text");
  audit.set("delivered", fencedJson(pyTruthy(text) ? pyStrValue(text) : ""));
  if (audit.get("delivered") === null) audit.set("delivery_error", "最后的回答里没有恰好一个能解析成 JSON 对象的 json 代码块（quizs 用代码块交差）");
  return audit;
}
