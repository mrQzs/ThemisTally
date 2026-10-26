// kit_config.py 的写入事务（迁移第 ③b 片，r2 设计 D7、D8，桌面端 D6、D13）：持配置锁读入资源、改好之后 publish。
// publish 的次序：整份校验 → 运行中切换的确认 → 补判本资源中断的事务 → 外部改动 → 快照 → intent → 替换 → commit。
// 审计只在配置锁内追加（两套实现共用这把锁）；快照按内容寻址，两套实现共用。
// 写模式：--dry-run --json 预览（不拿锁、什么也不写）；--expect-state 拿锁之后先比对令牌，对上了才写。
import { createHash, randomBytes } from "node:crypto";
import { closeSync, existsSync, fsyncSync, openSync, readSync, statSync, writeFileSync, writeSync } from "node:fs";
import { basename, dirname } from "node:path";
import { utcNow } from "@themis/base/clock";
import { ConfigLock, LockBusyError, LockWriteError } from "@themis/base/locks";
import { type PyOut, pyRepr } from "@themis/base/pyfmt";
import { pyOSErrorOf, pyReadBytes, PyOSError } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps, encodeUtf8 } from "@themis/base/pyjson";
import { PY_END, cmpCodePoints, pyRegex, pySplitlines } from "@themis/base/pyre";
import { PyWinError, pathMkdir, pyPublishNew, pyReplace } from "@themis/base/pyos";
import { secretLikePaths } from "@themis/base/secrets";
import { git } from "@themis/dispatcher/repo";
import { joinPath } from "./decisions.ts";
import { HISTORY_DIR, SECRET_SHOWN, auditPath, keyDiff, readAudit, secretReason } from "./history.ts";
import { bindingSwitchInFlight, bindingTuple, sameBinding } from "./roles-binding.ts";
import { ROLES, V3_KEYS } from "./roles-check.ts";
import { ConfigError, type Kit, type RepoLike, parseObject, validateConfig } from "./validate.ts";

export const RESOURCES: Readonly<Record<string, string>> = { config: "dispatch.config.json", local: "dispatch.local.json" };
const AUDIT_DIR = "audit";
const APPROVAL_NOTE = "P3 之前没有批准记录";
const ACTOR_ENV = "CODEKIT_ACTOR";
/** user-ui 是桌面端本机服务给子进程设的；和其余取值一样是自声明，不是认证。 */
const ACTOR_RE = pyRegex(`^(?:user|user-ui|agent:[a-z][a-z_]{0,31})${PY_END}`);
/** --expect-state 对不上的退出码：本机服务转成 409，界面要求重新预览。 */
export const EXIT_STALE = 4;
const EXIT_USAGE = 2;
const STATE_RE = pyRegex(`^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+${PY_END}`);
const BINDING_FIELDS = ["mode", "profile", "runtime", "adapter", "provider", "model", "thinking"];

/** 已经替换了配置、commit 却没写进审计：退出 1，下一次写入同一资源时补判。 */
export class AuditIncomplete extends ConfigError {}

/** 一条写命令的运行环境：仓库、kit、等配置锁的秒数（后两样来自启动器的 context）与输出。 */
export interface WriteContext {
  readonly repo: RepoLike & { readonly runsDir: string };
  readonly kit: Kit;
  readonly lockWaitSeconds: number;
  readonly out: PyOut;
}

const sha256 = (data: Uint8Array | null): string | null => (data === null ? null : createHash("sha256").update(data).digest("hex"));
const tokenHex = (bytes: number): string => randomBytes(bytes).toString("hex");
const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
/** (ref or {}).get("sha256")。 */
const refSha = (ref: PyValue | undefined): string | null => (isDict(ref) && typeof ref.get("sha256") === "string" ? (ref.get("sha256") as string) : null);
/** str(OSError)：认得的错误码照 open() 的写法，其余照 Node 的原文。 */
/** str(exc)：已经照 Python 构造好的（Win32 的 PyWinError、CRT 的 PyOSError）原样，Node 的文件错误换成 open() 的写法。 */
const osText = (error: unknown, path: string): string =>
  error instanceof PyWinError || error instanceof PyOSError ? error.message : (pyOSErrorOf(error, path)?.message ?? (error as Error).message);

// --- 写模式 ---------------------------------------------------------------------------------------

/** 一条写命令的预览或带令牌的执行：CLI 层设进 currentMode，进事务时读它，handler 不用知道。 */
export class WriteMode {
  readonly dryRun: boolean;
  readonly expectState: string | null;
  entered = false;
  action: string | null = null;
  readonly snapshot = new Map<string, Buffer | null>();
  readonly preview: PyDict[] = [];
  readonly notes: string[] = [];

  constructor(dryRun: boolean, expectState: string | null) {
    this.dryRun = dryRun;
    this.expectState = expectState;
  }
}

let currentMode: WriteMode | null = null;

export function setWriteMode(mode: WriteMode | null): void {
  currentMode = mode;
}

/** handler 给预览加的说明（plugins 的权限差异）：不在预览时什么也不做。 */
export function previewNotes(lines: readonly string[]): void {
  if (currentMode !== null && currentMode.dryRun) currentMode.notes.push(...lines);
}

/** 同一条命令第二次进事务是内部错误：第二次会拿自己刚写的状态去比令牌，误报对不上。 */
function enterWriteMode(action: string): WriteMode | null {
  const mode = currentMode;
  if (mode === null) return null;
  if (mode.entered) throw new ConfigError(`内部错误：带 --dry-run 或 --expect-state 的命令只能进一次写入事务（${action}）`);
  mode.entered = true;
  mode.action = action;
  return mode;
}

/** 预览给的令牌：v1;<资源>=<原始字节的 sha256|absent>，资源按名字排序，只列这条命令会写的。 */
export function stateToken(snapshot: ReadonlyMap<string, Buffer | null>): string {
  const parts = [...snapshot.entries()].sort(([left], [right]) => cmpCodePoints(left, right)).map(([name, data]) => `${name}=${sha256(data) ?? "absent"}`);
  return ["v1", ...parts].join(";");
}

const resourceFiles = (names: readonly string[]): string => names.map((name) => `.agent/${RESOURCES[name] as string}`).join("、");

function readResource(repo: RepoLike, resource: string): Buffer | null {
  const path = joinPath(repo.agentDir, RESOURCES[resource] as string);
  if (!existsSync(path)) return null;
  try {
    return pyReadBytes(path);
  } catch (error) {
    if (error instanceof PyOSError) throw new ConfigError(`读不出 ${path}：${error.message}`);
    throw error;
  }
}

/** 拿锁之后、第一次 publish 之前：一次读齐这条命令要写的资源，与令牌比对，对上了返回这批字节。 */
function checkState(repo: RepoLike, token: string, resources: readonly string[]): Map<string, Buffer | null> {
  const parts = token.split(";").slice(1);
  const names = parts.map((part) => part.split("=")[0] as string);
  const unique = [...new Set(names)].sort(cmpCodePoints);
  if (!STATE_RE.test(token) || names.length !== unique.length || names.some((name, index) => name !== unique[index])) {
    throw new ConfigError("--expect-state 的令牌格式不对：只接受预览（--dry-run --json）给的 state", EXIT_USAGE);
  }
  const wanted = [...resources].sort(cmpCodePoints);
  if (names.length !== wanted.length || names.some((name, index) => name !== wanted[index])) {
    throw new ConfigError(
      `--expect-state 的令牌是预览写 ${resourceFiles(names)} 的命令时给的，这条命令要写 ${resourceFiles(wanted)}：什么也没写，按这条命令重新预览`,
      EXIT_STALE,
    );
  }
  const expected = new Map(parts.map((part) => [part.slice(0, part.indexOf("=")), part.slice(part.indexOf("=") + 1)]));
  const snapshot = new Map(names.map((name) => [name, readResource(repo, name)]));
  const changed = names.filter((name) => (sha256(snapshot.get(name) ?? null) ?? "absent") !== expected.get(name));
  if (changed.length) throw new ConfigError(`${resourceFiles(changed)} 在预览之后被改过：什么也没写，重新预览`, EXIT_STALE);
  return snapshot;
}

// --- 审计、快照与外部改动 ---------------------------------------------------------------------------

/** 只在配置锁内调用：同一时间只有一个追加者。文件不以换行结尾时先补一个，中断留下的半行单独成行。 */
function appendAudit(repo: RepoLike, record: PyDict): void {
  const path = auditPath(repo);
  pathMkdir(dirname(path), true, true); // Path.mkdir(parents=True, exist_ok=True)：Win32，报错照 [WinError N]
  let prefix = "";
  if (existsSync(path) && statSync(path).size) {
    const fd = openSync(path, "r");
    try {
      const last = Buffer.alloc(1);
      readSync(fd, last, 0, 1, statSync(path).size - 1);
      prefix = last[0] === 0x0a ? "" : "\n";
    } finally {
      closeSync(fd);
    }
  }
  const line = encodeUtf8(`${prefix}${dumps(record, { ensureAscii: false, sortKeys: true })}\n`);
  const fd = openSync(path, "a");
  try {
    let offset = 0;
    while (offset < line.length) offset += writeSync(fd, line, offset, line.length - offset);
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
}

/** 一份内容在审计里的引用；store 为真且是 config、没有疑似凭据时，按内容寻址存进 config-history/。 */
function snapshotRef(repo: RepoLike, resource: string, data: Buffer | null, store: boolean): PyDict | null {
  if (data === null) return null;
  const sha = sha256(data) as string;
  if (resource !== "config") return refOf([["kind", "local-file"], ["sha256", sha], ["stored", false]]);
  const target = joinPath(repo.agentDir, HISTORY_DIR, `${sha}.json`);
  // 先查凭据再看是否已存：规则变严之前存下的同一内容，同样不算“已存”
  const reason = secretReason(data);
  if (reason !== null) return refOf([["kind", "config-snapshot"], ["sha256", sha], ["stored", false], ["reason", reason]]);
  if (isFile(target)) return refOf([["kind", "config-snapshot"], ["sha256", sha], ["stored", true]]);
  if (!store) return refOf([["kind", "config-snapshot"], ["sha256", sha], ["stored", false]]);
  pathMkdir(dirname(target), true, true);
  pyPublishNew(target, data); // 已存在（同一内容）返回 false，无妨
  return refOf([["kind", "config-snapshot"], ["sha256", sha], ["stored", true]]);
}

const refOf = (fields: [string, PyValue][]): PyDict => new Map<string, PyValue>(fields);

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

interface Ledger {
  readonly intents: Map<string, PyDict>;
  readonly pending: string[];
  readonly lastKnown: string | null;
}

/** 一个资源的账：intent、未终结的 txn（日志顺序）与最后一条“已知内容”的哈希（已发布事务的 after 或 observed 的 after）。 */
function ledgerOf(records: readonly PyDict[], resource: string): Ledger {
  const intents = new Map<string, PyDict>();
  const order: string[] = [];
  const terminal = new Set<string>();
  let lastKnown: string | null = null;
  for (const record of records) {
    if (record.get("resource") !== resource) continue;
    const phase = record.get("phase");
    const txn = record.get("txn");
    if (phase === "intent" && typeof txn === "string" && !intents.has(txn)) {
      intents.set(txn, record);
      order.push(txn);
    } else if ((phase === "commit" || phase === "resolve") && typeof txn === "string" && intents.has(txn) && !terminal.has(txn)) {
      terminal.add(txn);
      if (record.get("result") === "published") lastKnown = refSha((intents.get(txn) as PyDict).get("after_ref"));
    } else if (phase === "observed") {
      lastKnown = refSha(record.get("after_ref"));
    }
  }
  return { intents, pending: order.filter((txn) => !terminal.has(txn)), lastKnown };
}

/** 历史与审计目录没被忽略时提示：它们会作为未跟踪文件出现，运行期间写配置会进复审关注。 */
function warnUnignored(ctx: WriteContext): void {
  for (const name of [HISTORY_DIR, AUDIT_DIR]) {
    if (git(["check-ignore", "-q", `.agent/${name}/probe`], ctx.repo.root).status !== 0) {
      ctx.out.printErr(`WARN  .agent/${name}/ 没有被 .gitignore 忽略：运行 kit_install update 补上 kit 的忽略规则`);
    }
  }
}

/** CODEKIT_ACTOR 的自声明（user、user-ui 或 agent:<角色>），没设记 undeclared。这不是认证。 */
function actor(ctx: WriteContext): string {
  const value = process.env[ACTOR_ENV];
  if (!value) return "undeclared";
  if (ACTOR_RE.test(value)) return value;
  ctx.out.printErr(`WARN  ${ACTOR_ENV}=${pyRepr(value)} 不是 user、user-ui 或 agent:<角色>，审计记为 undeclared`);
  return "undeclared";
}

// --- 运行中切换（D8）--------------------------------------------------------------------------------

const hasV3 = (configs: readonly PyDict[]): boolean => configs.some((config) => V3_KEYS.some((key) => config.has(key)));

/** 运行中切换的确认：返回审计的 confirmation（flag / none）。写入前后都没有 v3 键时不用比较。 */
function bindingSwitchConfirmation(ctx: WriteContext, oldConfig: PyDict, newConfig: PyDict, confirm: boolean): string {
  if (!hasV3([oldConfig, newConfig])) return "none";
  const [inFlight, unreadable] = bindingSwitchInFlight(ctx.repo.runsDir, oldConfig, newConfig);
  if (!inFlight.length && !unreadable.length) return "none";
  if (!confirm) {
    if (inFlight.length) {
      throw new ConfigError(
        `有 attempt 在运行，这次写入会改变 execution 或 contract 的生效绑定：${inFlight.join("、")}。运行中的 attempt 不受影响（执行模型已固定）；确认要切换就加 --yes`,
      );
    }
    // 列不出来就判断不了有没有在运行的：不当作“没有”
    throw new ConfigError(`这次写入会改变 execution 或 contract 的生效绑定，但无法确认有没有在运行的 attempt（列不出来：${unreadable.join("、")}）；确认要切换就加 --yes`);
  }
  return "flag";
}

/** 预览里的运行中切换（与 D8 同一个判定，只扫描、不拒绝），以及各角色生效绑定的前后。 */
function switchPreview(ctx: WriteContext, oldConfig: PyDict, newConfig: PyDict): [string, PyValue][] {
  if (!hasV3([oldConfig, newConfig])) return [["binding_changes", []], ["running_attempts", []], ["unreadable", []]];
  const changes: PyValue[] = [];
  for (const role of ROLES) {
    const before = bindingTuple(oldConfig, role);
    const after = bindingTuple(newConfig, role);
    if (!sameBinding(before, after)) {
      const asDict = (tuple: (string | null)[] | null): PyValue => (tuple === null ? null : new Map(BINDING_FIELDS.map((field, index) => [field, tuple[index] ?? null])));
      changes.push(new Map<string, PyValue>([["role", role], ["before", asDict(before)], ["after", asDict(after)]]));
    }
  }
  const [inFlight, unreadable] = bindingSwitchInFlight(ctx.repo.runsDir, oldConfig, newConfig);
  return [["binding_changes", changes], ["running_attempts", inFlight], ["unreadable", unreadable]];
}

// --- 事务 ------------------------------------------------------------------------------------------

/** 一次写入：在配置锁内读入资源，调用方修改后 publish；不 publish 就什么也不写。preview 不为 null 是预览。 */
export class ConfigTransaction {
  readonly ctx: WriteContext;
  readonly lock: ConfigLock | null;
  readonly resource: string;
  readonly action: string;
  readonly target: string | null;
  readonly confirm: boolean;
  readonly before: Buffer | null;
  readonly preview: PyDict[] | null;
  readonly path: string;
  /** 写入前的样子（供 D8 比较）；调用方改的是 config，由同一份字节另外解析。 */
  readonly original: PyDict;
  readonly config: PyDict;
  published = false;

  constructor(ctx: WriteContext, lock: ConfigLock | null, resource: string, action: string, target: string | null, confirm: boolean, before: Buffer | null, preview: PyDict[] | null) {
    this.ctx = ctx;
    this.lock = lock;
    this.resource = resource;
    this.action = action;
    this.target = target;
    this.confirm = confirm;
    this.before = before;
    this.preview = preview;
    this.path = joinPath(ctx.repo.agentDir, RESOURCES[resource] as string);
    this.original = before === null ? new Map() : parseObject(this.path, before);
    this.config = before === null ? new Map() : parseObject(this.path, before);
  }

  private record(phase: string, fields: [string, PyValue][]): PyDict {
    return new Map<string, PyValue>([
      ["record_type", "management-audit"],
      ["schema_version", 1n],
      ["phase", phase],
      ["resource", this.resource],
      ["audit_id", `aud-${tokenHex(16)}`],
      ["at", utcNow()],
      ...fields,
    ]);
  }

  private append(record: PyDict): void {
    try {
      appendAudit(this.ctx.repo, record);
    } catch (error) {
      if (error instanceof ConfigError) throw error;
      throw new ConfigError(`没有写入：审计写不进去（${osText(error, auditPath(this.ctx.repo))}）`);
    }
  }

  private snapshot(data: Buffer | null, store: boolean): PyDict | null {
    try {
      return snapshotRef(this.ctx.repo, this.resource, data, store);
    } catch (error) {
      throw new ConfigError(`没有写入：快照存不下（${osText(error, this.path)}）`);
    }
  }

  /** 校验并写入；新字节与当前相同时什么也不写、返回 false。rawText 给定时原样写这份字节（rollback 用）。 */
  publish(newConfig: PyDict, rawText?: Buffer): boolean {
    const data = rawText ?? Buffer.from(encodeUtf8(`${dumps(newConfig, { ensureAscii: false, indent: 2 })}\n`));
    if (this.resource === "config") {
      // 先整份校验，再看有没有变化：无效的配置不会因为“没有变化”而被放过
      const errors = validateConfig(newConfig, this.ctx.repo, this.ctx.kit);
      if (errors.length) throw new ConfigError(`没有写入：${errors.join("；")}`);
    }
    if (this.preview !== null) return this.previewEntry(newConfig, data);
    if (this.before !== null && data.equals(this.before)) return false;
    const confirmation = this.resource === "config" ? bindingSwitchConfirmation(this.ctx, this.original, newConfig, this.confirm) : "none";
    const ledger = ledgerOf(readAudit(this.ctx.repo).records, this.resource);
    const current = sha256(this.before);
    let lastKnown = ledger.lastKnown;
    // 持锁者总会先写完自己的事务再放锁、锁又不自动清除，所以未终结的都是中断者留下的
    for (const txn of ledger.pending) {
      const intent = ledger.intents.get(txn) as PyDict;
      const after = refSha(intent.get("after_ref"));
      const before = refSha(intent.get("before_ref"));
      const result = current === after ? "published" : current === before ? "aborted" : "unknown";
      this.append(this.record("resolve", [["txn", txn], ["result", result]]));
      if (result === "published") lastKnown = after;
    }
    if (current !== lastKnown) this.append(this.record("observed", [["action", "external"], ["after_ref", this.snapshot(this.before, true)]]));
    const afterRef = this.snapshot(data, true);
    const beforeRef = this.snapshot(this.before, false);
    const txn = tokenHex(16);
    // target 来自命令行（例如 unset 的键路径）：有令牌形状时不记原文
    const target = this.target !== null && secretLikePaths(this.target).length ? SECRET_SHOWN : this.target;
    const intent = this.record("intent", [
      ["txn", txn],
      ["action", this.action],
      ["target", target],
      ["actor", actor(this.ctx)],
      ["confirmation", confirmation],
      ["before_ref", beforeRef],
      ["after_ref", afterRef],
      ["invalidated_approvals", []],
      ["note", APPROVAL_NOTE],
    ]);
    this.append(intent);
    const temp = joinPath((this.lock as ConfigLock).path, `${basename(this.path)}.${tokenHex(8)}.tmp`);
    try {
      writeFileSync(temp, data); // temp.write_bytes：CRT 的 open，报 [Errno N]
      pyReplace(temp, this.path); // os.replace：Win32 的 MoveFileExW，报 [WinError N] …: '临时文件' -> '配置'
    } catch (error) {
      throw new ConfigError(`写入失败：${osText(error, temp)}`);
    }
    try {
      appendAudit(this.ctx.repo, this.record("commit", [["txn", txn], ["result", "published"]]));
    } catch (error) {
      throw new AuditIncomplete(`已写入 ${this.path}，但审计记录不全（${osText(error, auditPath(this.ctx.repo))}）：下一次写入时补判`);
    }
    this.published = true;
    warnUnignored(this.ctx);
    return true;
  }

  /** 预览这次写入：只给键路径不给取值，与 history 的 changed_keys 一致；运行中切换只扫描、不拒绝。 */
  private previewEntry(newConfig: PyDict, data: Buffer): boolean {
    const changed = this.before === null || !data.equals(this.before);
    const entry = new Map<string, PyValue>([
      ["resource", this.resource],
      ["changed", changed],
    ]);
    if (this.resource === "config") {
      const diff = keyDiff(this.before ?? Buffer.from("{}"), data);
      entry.set("changed_keys", diff === null ? null : diff.map((change) => change.key));
      for (const [key, value] of switchPreview(this.ctx, this.original, newConfig)) entry.set(key, value);
    }
    (this.preview as PyDict[]).push(entry);
    return changed;
  }
}

function acquireLock(ctx: WriteContext): ConfigLock {
  const lock = new ConfigLock(ctx.repo.agentDir, ctx.lockWaitSeconds);
  try {
    return lock.acquire();
  } catch (error) {
    if (error instanceof LockBusyError || error instanceof LockWriteError) throw new ConfigError(error.message);
    throw error;
  }
}

export interface TransactionOptions {
  readonly resource?: string;
  readonly confirm?: boolean;
}

/** kit_config.config_transaction：持配置锁读入资源（config 或 local），交给 body 修改并 publish。所有写配置的入口都经过这里。 */
export function withConfigTransaction<T>(ctx: WriteContext, action: string, target: string | null, options: TransactionOptions, body: (txn: ConfigTransaction) => T): T {
  const resource = options.resource ?? "config";
  const confirm = options.confirm ?? false;
  const mode = enterWriteMode(action);
  if (mode !== null && mode.dryRun) {
    const before = readResource(ctx.repo, resource);
    mode.snapshot.set(resource, before);
    return body(new ConfigTransaction(ctx, null, resource, action, target, confirm, before, mode.preview));
  }
  const lock = acquireLock(ctx);
  try {
    const before = mode !== null ? (checkState(ctx.repo, String(mode.expectState), [resource]).get(resource) ?? null) : readResource(ctx.repo, resource);
    return body(new ConfigTransaction(ctx, lock, resource, action, target, confirm, before, null));
  } finally {
    lock.release();
  }
}

/**
 * kit_config.config_transactions：同一把配置锁里按资源各开一个事务（runtime add --command 与 remove 先改配置、再改本机文件，
 * 中间不放锁）。resources 是这条命令可能写的资源，也就是令牌覆盖的：写模式下一开始就读齐。
 */
export function withConfigTransactions<T>(
  ctx: WriteContext,
  action: string,
  target: string | null,
  options: { readonly confirm?: boolean; readonly resources?: readonly string[] },
  body: (open: (resource: string) => ConfigTransaction) => T,
): T {
  const confirm = options.confirm ?? false;
  const resources = options.resources ?? ["config", "local"];
  const mode = enterWriteMode(action);
  const declared = (snapshot: ReadonlyMap<string, Buffer | null>, resource: string): Buffer | null => {
    if (!snapshot.has(resource)) throw new ConfigError(`内部错误：${action} 写了没有声明的资源 ${resource}`); // 令牌没有覆盖它：写了就绕过了比对
    return snapshot.get(resource) ?? null;
  };
  if (mode !== null && mode.dryRun) {
    for (const name of resources) mode.snapshot.set(name, readResource(ctx.repo, name));
    return body((resource) => new ConfigTransaction(ctx, null, resource, action, target, confirm, declared(mode.snapshot, resource), mode.preview));
  }
  const lock = acquireLock(ctx);
  try {
    if (mode === null) return body((resource) => new ConfigTransaction(ctx, lock, resource, action, target, confirm, readResource(ctx.repo, resource), null));
    const snapshot = checkState(ctx.repo, String(mode.expectState), resources);
    return body((resource) => new ConfigTransaction(ctx, lock, resource, action, target, confirm, declared(snapshot, resource), null));
  } finally {
    lock.release();
  }
}

/** --dry-run --json 的预览：stdout 只有这一份 JSON。 */
export function previewPayload(mode: WriteMode, captured: string): PyDict {
  if (!mode.entered) throw new ConfigError("内部错误：这条命令没有进写入事务，给不出预览");
  const entries = mode.preview;
  const listOf = (key: string): PyValue[] => entries.flatMap((entry) => (entry.get(key) as PyValue[] | undefined) ?? []);
  const running = listOf("running_attempts");
  const unreadable = listOf("unreadable");
  return new Map<string, PyValue>([
    ["dry_run", true],
    ["action", mode.action],
    ["changed", entries.some((entry) => entry.get("changed") === true)],
    ["resources", entries.map((entry) => new Map([...entry].filter(([key]) => ["resource", "changed", "changed_keys"].includes(key as string))))],
    ["binding_changes", listOf("binding_changes")],
    ["running_attempts", running],
    ["unreadable", unreadable],
    ["needs_yes", running.length > 0 || unreadable.length > 0],
    ["warnings", pySplitlines(captured).filter((line) => line.startsWith("WARN  ")).map((line) => line.slice(6))],
    ["notes", [...mode.notes]],
    ["state", stateToken(mode.snapshot)],
  ]);
}
