// kit_config.py 的写入历史（迁移第 ③a2 片）：读审计、按 intent 编号、快照与逐键差异。只读：不持锁、不补判。
// 审计记录 .agent/audit/management.jsonl 每行一个 JSON；快照 .agent/config-history/<sha256>.json 按内容寻址。
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { pyTruthy } from "@themis/base/pyfmt";
import { cmpCodePoints } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { redactSecrets, secretLikePaths } from "@themis/base/secrets";
import { joinPath } from "./decisions.ts";
import { ConfigError, type RepoLike } from "./validate.ts";

export const HISTORY_DIR = "config-history";
const AUDIT_DIR = "audit";
const AUDIT_NAME = "management.jsonl";
const AUDIT_PHASES = ["intent", "commit", "resolve", "observed"];
const RESOURCES = ["config", "local"];
export const SECRET_SHOWN = "（含疑似凭据，不显示）";
export const STATE_WORDS: ReadonlyMap<PyValue, string> = new Map<PyValue, string>([
  ["published", "已发布"],
  ["aborted", "未发布"],
  ["unknown", "未知"],
  [null, "进行中或已中断"],
]);

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

export function auditPath(repo: RepoLike): string {
  return joinPath(repo.agentDir, AUDIT_DIR, AUDIT_NAME);
}

function validRef(ref: PyValue | undefined): boolean {
  return ref === undefined || ref === null || (isDict(ref) && typeof ref.get("sha256") === "string");
}

/** 审计记录的结构：阶段与资源是已知值，事务记录有字符串的 txn，终结记录有字符串的 result，引用是 None 或带哈希的对象。 */
function validRecord(record: PyValue): record is PyDict {
  if (!isDict(record) || record.get("record_type") !== "management-audit") return false;
  const phase = record.get("phase");
  const resource = record.get("resource");
  if (typeof phase !== "string" || !AUDIT_PHASES.includes(phase) || typeof resource !== "string" || !RESOURCES.includes(resource)) return false;
  if (phase !== "observed" && typeof record.get("txn") !== "string") return false;
  if ((phase === "commit" || phase === "resolve") && typeof record.get("result") !== "string") return false;
  if (phase === "intent" && typeof record.get("action") !== "string") return false;
  return validRef(record.get("before_ref")) && validRef(record.get("after_ref"));
}

/** bytes.strip() 之后是不是空的（ASCII 空白：空格、\t \n \v \f \r）。 */
const blankBytes = (raw: Buffer): boolean => raw.every((byte) => byte === 0x20 || (byte >= 0x09 && byte <= 0x0d));

/** 审计记录（文件顺序）与损坏行的行号（从 1 起，空行也计数）。末尾的半行、解析不了的、结构不对的都记为损坏。 */
export function readAudit(repo: RepoLike): { records: PyDict[]; broken: number[] } {
  const file = auditPath(repo);
  let data: Buffer;
  try {
    data = pyReadBytes(file);
  } catch (error) {
    if (error instanceof PyOSError && error.errno === 2) return { records: [], broken: [] };
    if (error instanceof PyOSError) throw new ConfigError(`读不出审计 ${file}：${error.message}`);
    throw error;
  }
  const records: PyDict[] = [];
  const broken: number[] = [];
  let start = 0;
  for (let number = 1; start <= data.length; number += 1) {
    const end = data.indexOf(0x0a, start);
    const raw = data.subarray(start, end < 0 ? data.length : end);
    start = end < 0 ? data.length + 1 : end + 1;
    if (blankBytes(raw)) continue;
    let record: PyValue;
    try {
      record = loads(pyDecodeUtf8(raw));
    } catch (error) {
      if (error instanceof PyUnicodeDecodeError || error instanceof PyJsonError) {
        broken.push(number);
        continue;
      }
      throw error;
    }
    if (!validRecord(record)) {
      broken.push(number);
      continue;
    }
    records.push(record);
  }
  return { records, broken };
}

export interface HistoryEntry {
  readonly number: number;
  readonly resource: string;
  readonly txn: string;
  readonly at: PyValue;
  readonly action: PyValue;
  readonly target: PyValue;
  readonly actor: PyValue;
  readonly confirmation: PyValue;
  readonly beforeRef: PyValue;
  readonly afterRef: PyValue;
  state: PyValue;
  resolved: boolean;
  externalAfter: number;
}

/** 审计 intent 的 target 显示之前按现在的规则再查一次：像令牌的不显示，原日志不动。 */
function shownTarget(target: PyValue): PyValue {
  return typeof target === "string" && secretLikePaths(target).length ? SECRET_SHOWN : target;
}

const field = (record: PyDict, key: string): PyValue => (record.has(key) ? (record.get(key) as PyValue) : null);

/** 按 intent 在日志里的次序编号（两种资源共用一套编号），每条带终结状态；observed 记在它前面那一条上。 */
export function historyEntries(repo: RepoLike): { entries: HistoryEntry[]; broken: number[]; leadingExternal: number } {
  const { records, broken } = readAudit(repo);
  const entries: HistoryEntry[] = [];
  const byTxn = new Map<string, HistoryEntry>();
  let leadingExternal = 0;
  for (const record of records) {
    const phase = record.get("phase");
    const resource = record.get("resource") as string;
    if (phase === "intent") {
      const entry: HistoryEntry = {
        number: entries.length + 1,
        resource,
        txn: record.get("txn") as string,
        at: field(record, "at"),
        action: field(record, "action"),
        target: shownTarget(field(record, "target")),
        actor: field(record, "actor"),
        confirmation: field(record, "confirmation"),
        beforeRef: field(record, "before_ref"),
        afterRef: field(record, "after_ref"),
        state: null,
        resolved: false,
        externalAfter: 0,
      };
      entries.push(entry);
      byTxn.set(JSON.stringify([resource, entry.txn]), entry);
    } else if (phase === "commit" || phase === "resolve") {
      const entry = byTxn.get(JSON.stringify([resource, record.get("txn")]));
      if (entry !== undefined && entry.state === null) {
        entry.state = field(record, "result");
        entry.resolved = phase === "resolve";
      }
    } else if (entries.length) {
      (entries[entries.length - 1] as HistoryEntry).externalAfter += 1;
    } else {
      leadingExternal += 1;
    }
  }
  return { entries, broken, leadingExternal };
}

const sha256 = (data: Uint8Array): string => createHash("sha256").update(data).digest("hex");

/** 快照文件的字节（引用说已存、文件在、哈希相符）；否则 null。 */
function storedSnapshot(repo: RepoLike, ref: PyValue): Buffer | null {
  if (!isDict(ref) || !pyTruthy(ref.get("stored") ?? null) || typeof ref.get("sha256") !== "string") return null;
  const hash = ref.get("sha256") as string;
  let data: Buffer;
  try {
    data = readFileSync(joinPath(repo.agentDir, HISTORY_DIR, `${hash}.json`));
  } catch {
    return null;
  }
  return sha256(data) === hash ? data : null;
}

/** 快照存内容之前的凭据检查：疑似凭据时返回原因（只含键路径），否则 null。 */
export function secretReason(data: Uint8Array): string | null {
  let parsed: PyValue;
  try {
    parsed = loads(pyDecodeUtf8(data));
  } catch (error) {
    if (!(error instanceof PyUnicodeDecodeError || error instanceof PyJsonError)) throw error;
    const text = new TextDecoder("utf-8", { ignoreBOM: true }).decode(data);
    return redactSecrets(text) !== text ? "不是合法的 JSON，文本里有疑似凭据" : null;
  }
  const paths = secretLikePaths(parsed);
  return paths.length ? `疑似凭据：${paths.slice(0, 5).join("、")}` : null;
}

/** 可以显示、可以回滚的快照字节：按现在的规则再查一次凭据。 */
export function snapshotBytes(repo: RepoLike, ref: PyValue): Buffer | null {
  const data = storedSnapshot(repo, ref);
  return data !== null && secretReason(data) === null ? data : null;
}

/** {键路径: 值}；非空对象逐级展开，空对象与其他值是叶子。顶层是空对象时没有任何键。 */
function flatten(value: PyValue, prefix = ""): Map<string, PyValue> {
  if (isDict(value) && (value.size || !prefix)) {
    const flat = new Map<string, PyValue>();
    for (const [key, item] of value) for (const [path, leaf] of flatten(item, prefix ? `${prefix}.${String(key)}` : String(key))) flat.set(path, leaf);
    return flat;
  }
  return new Map([[prefix || "（顶层）", value]]);
}

export interface KeyChange {
  readonly key: string;
  readonly old: PyValue;
  readonly new: PyValue;
}

/** 逐键差异（键路径、旧值、新值，缺省的键记 None）；任一份内容不可用时为 null，不当作空配置比较。 */
export function keyDiff(before: Uint8Array | null, after: Uint8Array | null): KeyChange[] | null {
  if (before === null || after === null) return null;
  let old: PyValue;
  let next: PyValue;
  try {
    old = loads(pyDecodeUtf8(before));
    next = loads(pyDecodeUtf8(after));
  } catch (error) {
    if (error instanceof PyUnicodeDecodeError || error instanceof PyJsonError) return null;
    throw error;
  }
  const oldFlat = flatten(old);
  const newFlat = flatten(next);
  const keys = [...new Set([...oldFlat.keys(), ...newFlat.keys()])].sort(cmpCodePoints);
  return keys
    .filter((key) => oldFlat.has(key) !== newFlat.has(key) || !pyEq(oldFlat.get(key) as PyValue, newFlat.get(key) as PyValue))
    .map((key) => ({ key, old: oldFlat.get(key) ?? null, new: newFlat.get(key) ?? null }));
}

export function contentNote(resource: PyValue, ref: PyValue, repo: RepoLike | null): string | null {
  if (ref === null) return null;
  if (!isDict(ref) || !pyTruthy(ref.get("stored") ?? null)) return resource === "local" ? "本机配置只存哈希" : "疑似凭据，未存内容";
  const data = repo === null ? null : storedSnapshot(repo, ref);
  return data !== null && secretReason(data) !== null ? "疑似凭据，不显示" : null;
}

const EMPTY_OBJECT = Buffer.from("{}");

/** 一条写入的前后内容：before 缺省（资源原本不存在）时当作 {}。 */
export function entryBytes(repo: RepoLike, entry: HistoryEntry): [Buffer | null, Buffer | null] {
  return [pyTruthy(entry.beforeRef) ? snapshotBytes(repo, entry.beforeRef) : EMPTY_OBJECT, snapshotBytes(repo, entry.afterRef)];
}

export function findEntry(entries: readonly HistoryEntry[], number: bigint): HistoryEntry {
  const found = entries.find((entry) => BigInt(entry.number) === number);
  if (found === undefined) throw new ConfigError(`没有第 ${number} 条写入记录（用 config history 查看编号）`, 2);
  return found;
}
