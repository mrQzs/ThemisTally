// pi_dispatch 的证据目录（迁移第 ④b2 片）：三张状态表、write_json、read_json、set_state、log_event、load_attempt、
// sha256_file、候选补丁的核对、检查可以产生的缓存类文件。history.jsonl 与 state.json 照 Python 写 LF、不加锁（kit_hub 的
// jsonl.appendEvent 加锁、排序键、落盘，是另一套写法）；state.json 先写同名 .tmp 再替换，不重试。证据坏了（缺文件、
// 不是 JSON、类型不对）时 Python 不接、命令崩溃，这里照样抛出。
import { createHash } from "node:crypto";
import { closeSync, openSync, statSync, writeSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { pyOSErrorOf, pyReadBytes, pyReadText } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps, encodeUtf8, loads } from "@themis/base/pyjson";
import { purePathStr } from "@themis/base/pypath";
import { pyReplace } from "@themis/base/pyos";
import type { SearchPattern } from "@themis/base/pyregex";
import { codePoints } from "@themis/base/pyre";
import { normalizeContract } from "./contract.ts";
import { compilePatterns, matches, patternError } from "./patterns.ts";
import { type Repo, git } from "./repo.ts";

export const VERDICTS = ["PASS", "ACCEPTED_WITH_EXCEPTION", "REVISE", "BLOCKED", "ESCALATE"];
export const PASSING_VERDICTS = ["PASS", "ACCEPTED_WITH_EXCEPTION"];
export const TERMINAL_STATES = [
  ...VERDICTS, "INTEGRATED", "ABANDONED", "SUPERSEDED", "TIMEOUT", "CANCELLED", "INFRA_FAILURE", "PREPARE_FAILED", "NEEDS_REVIEW",
];
export const DEFAULT_ARTIFACT_PATTERNS = ["**/__pycache__/**", "**/*.pyc", "**/.pytest_cache/**", "**/.mypy_cache/**", "**/.ruff_cache/**"];

const LF = String.fromCharCode(10);
const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

/** 证据里的值交给子进程（git 的 sha、tree）：不是字符串时 Python 抛 TypeError。prepare 写的都是字符串，手改才会出现。 */
export function strArg(value: PyValue): string {
  if (typeof value !== "string") throw new PyCrash("TypeError", `expected str, bytes or os.PathLike object, not ${pyTypeName(value)}`);
  return value;
}

/** Path(value)：不是字符串时 Python 3.12 抛 TypeError。 */
export function pathArg(value: PyValue): string {
  if (typeof value !== "string") {
    throw new PyCrash("TypeError", `argument should be a str or an os.PathLike object where __fspath__ returns a str, not '${pyTypeName(value)}'`);
  }
  return purePathStr(value);
}

/** 文件操作出错时照 Python 报 OSError 的子类与文字。 */
function withOSError<T>(file: string, body: () => T): T {
  try {
    return body();
  } catch (error) {
    throw pyOSErrorOf(error, file) ?? error;
  }
}

/** 照 Python 的 open(…, encoding="utf-8") 再 write：先打开（建出文件），再编码写入；有孤立代理项时编码失败，留下空文件。 */
function writeOpened(file: string, flags: string, text: string): void {
  const fd = withOSError(file, () => openSync(file, flags));
  try {
    const bytes = encodeUtf8(text);
    let offset = 0;
    while (offset < bytes.length) offset += withOSError(file, () => writeSync(fd, bytes, offset));
  } finally {
    closeSync(fd);
  }
}

/** write_json：indent=2、不转义非 ASCII、末尾一个换行；exclusive 时文件已存在就失败，否则先写同名 .tmp 再替换。 */
export function writeJson(file: string, data: PyValue, exclusive = false): void {
  const text = `${dumps(data, { ensureAscii: false, indent: 2 })}${LF}`;
  if (exclusive) {
    writeOpened(file, "wx", text);
    return;
  }
  const tmp = `${file}.tmp`;
  writeOpened(tmp, "w", text);
  pyReplace(tmp, file);
}

/** read_json：文本模式读（通用换行），严格解码；读不了、不是 JSON 都照 Python 抛出。 */
export const readJson = (file: string): PyValue => loads(pyReadText(file));

function appendHistory(runDir: string, record: PyDict): void {
  const file = path.join(runDir, "history.jsonl");
  writeOpened(file, "a", `${dumps(record, { ensureAscii: false })}${LF}`);
}

/** set_state：state、at，再按调用方给的次序加字段（值为 null 的也写）；history.jsonl 追加一行，state.json 整份换掉。 */
export function setState(runDir: string, state: string, info: readonly [string, PyValue][] = []): void {
  const record: PyDict = new Map<string, PyValue>([["state", state], ["at", utcNow()], ...info]);
  appendHistory(runDir, record);
  writeJson(path.join(runDir, "state.json"), record);
}

/** log_event：event、at，再按调用方给的次序加字段，只追加 history.jsonl。 */
export function logEvent(runDir: string, event: string, info: readonly [string, PyValue][] = []): void {
  appendHistory(runDir, new Map<string, PyValue>([["event", event], ["at", utcNow()], ...info]));
}

/** load_attempt：meta.json 与规整过的 contract.json；合同不是对象时 Python 在 setdefault 上抛 AttributeError。 */
export function loadAttempt(runDir: string): [PyValue, PyDict] {
  const meta = readJson(path.join(runDir, "meta.json"));
  const contract = readJson(path.join(runDir, "contract.json"));
  if (!isDict(contract)) throw new PyCrash("AttributeError", `'${pyTypeName(contract)}' object has no attribute 'setdefault'`);
  return [meta, normalizeContract(contract)];
}

export const sha256File = (file: string): string => createHash("sha256").update(pyReadBytes(file)).digest("hex");

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

/** candidate_patch_ok：候选做过往返校验、补丁文件在、摘要对得上。 */
export function candidatePatchOk(runDir: string, candidate: PyValue): boolean {
  if (!isDict(candidate)) throw new PyCrash("AttributeError", `'${pyTypeName(candidate)}' object has no attribute 'get'`);
  const patch = path.join(runDir, "candidate.patch");
  if (!pyTruthy(candidate.get("patch_roundtrip_verified") ?? null)) return false;
  return isFile(patch) && sha256File(patch) === (candidate.get("patch_sha256") ?? null);
}

/** list(value)：字符串拆成字符，字典取键，数字与布尔不可迭代。 */
function pyIterate(value: PyValue): PyValue[] {
  if (Array.isArray(value)) return value;
  if (typeof value === "string") return codePoints(value);
  if (isDict(value)) return [...value.keys()] as PyValue[];
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not iterable`);
}

/** artifact_matchers：检查可以产生、不算候选漂移的缓存类文件；配置的 check_artifact_patterns 只收合法的模式。 */
export function artifactMatchers(config: PyDict): SearchPattern[] {
  const configured = config.has("check_artifact_patterns") ? (config.get("check_artifact_patterns") as PyValue) : [];
  const extra = pyIterate(configured).filter((item): item is string => typeof item === "string" && !patternError(item));
  return compilePatterns([...DEFAULT_ARTIFACT_PATTERNS, ...extra]);
}

/** split_extras：（缓存类文件, 其余的）。 */
export function splitExtras(paths: readonly string[], artifacts: readonly SearchPattern[]): [string[], string[]] {
  return [paths.filter((item) => matches(artifacts, item)), paths.filter((item) => !matches(artifacts, item))];
}

export function removeWorktree(repo: Repo, worktree: string): void {
  git(["worktree", "remove", "--force", worktree], repo.root);
}
