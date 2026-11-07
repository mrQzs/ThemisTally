// 信箱、账本与状态（迁移第 ⑤b 片，kit_hub.py 751–916 行加 hold_letters、release_held、ledger_events、keep_previous、
// letter_main）。落盘的写法逐字节照 Python：账本 sort_keys、state.json indent=2 sort_keys、agents/*.json 同上；锁与原子写用
// base 的原语（与 Python 的 msvcrt.locking 互斥，两套实现可以同时写一个信箱）。save_state 的三方合并里，几个键同时冲突时
// state.conflict 的先后照插入次序；Python 照 set 的迭代序（随哈希种子变），这个先后两边都不保证，契约不比。
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { utcNow } from "@themis/base/clock";
import { readText, writeTextAtomic } from "@themis/base/fsutil";
import { appendEvent as appendLedger, jsonlLines } from "@themis/base/jsonl";
import { DirLock as BaseDirLock, LockBusyError } from "@themis/base/locks";
import { withFileLock } from "@themis/base/native";
import { PyCrash, pyGet, pyItem, pyReprValue, pyStrValue, pyTypeName } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { pyPublishNew, pyRename, pyReplace } from "@themis/base/pyos";
import { purePathStr } from "@themis/base/pypath";
import { pyLower, pyStrip } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { EXIT_BLOCKED, KERNEL, OWNER, ROSTER, SENDER_ALIAS } from "./constants.ts";
import { HubError } from "./errors.ts";
import { type Meta, newMsgId, parseLetter, renderLetter, stageOf } from "./letters.ts";

const LF = String.fromCharCode(10);
const WIN = process.platform === "win32";

export const canonicalJson = (value: PyValue): string => dumps(value, { ensureAscii: false, sortKeys: true });
export const canonicalState = (state: PyValue): string => `${dumps(state, { ensureAscii: false, indent: 2, sortKeys: true })}${LF}`;
const sha256Text = (text: string): string => createHash("sha256").update(text, "utf8").digest("hex");
const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

/** load_state 读出来的状态：记着读出来时每个主任务各顶层键的样子，save_state 据此只写改过的键。 */
export class HubState {
  readonly data: PyDict;
  readonly seen: Map<string, Map<string, string>>;

  constructor(data: PyDict) {
    this.data = data;
    this.seen = HubState.snapshot(this.tasks());
  }

  tasks(): PyDict {
    return pyItem(this.data, "tasks") as PyDict;
  }

  static snapshot(tasks: PyValue): Map<string, Map<string, string>> {
    const seen = new Map<string, Map<string, string>>();
    if (!isDict(tasks)) throw new PyCrash("AttributeError", `'${pyTypeName(tasks)}' object has no attribute 'items'`);
    for (const [task, ts] of tasks) {
      if (isDict(ts)) seen.set(String(task), new Map([...ts].map(([key, value]) => [String(key), canonicalJson(value)])));
    }
    return seen;
  }
}

export class Hub {
  readonly repo: string;
  readonly root: string;

  constructor(repo: string) {
    this.repo = purePathStr(repo);
    this.root = join(this.repo, ".agent", "mailbox");
  }

  inbox(agent: string, box = "new"): string {
    return join(this.root, "inbox", agent, box);
  }

  taskDir(taskId: string): string {
    return join(this.root, "tasks", taskId);
  }

  ledger(): string {
    return join(this.root, "ledger", "events.jsonl");
  }

  statePath(): string {
    return join(this.root, "ledger", "state.json");
  }

  agentPath(agent: string): string {
    return join(this.root, "agents", `${SENDER_ALIAS[agent] ?? agent}.json`);
  }

  ensure(): void {
    for (const agent of [...Object.keys(ROSTER), OWNER]) for (const box of ["new", "cur"]) mkdirSync(this.inbox(agent, box), { recursive: true });
    for (const sub of ["tasks", "turns", "agents", "ledger", "sessions"]) mkdirSync(join(this.root, sub), { recursive: true });
  }

  // -- 账本与状态 --------------------------------------------------------------

  async appendEvent(event: string, data: readonly (readonly [string, PyValue])[] = []): Promise<void> {
    await appendLedger(this.ledger(), event, new Map(data));
  }

  readState(): PyDict {
    const path = this.statePath();
    const text = readText(path);
    if (!pyStrip(text) && isNonEmptyFile(path)) throw new HubError(`读不出 ${path}（文件在，内容读不到）`, EXIT_BLOCKED);
    const data = pyStrip(text) ? loads(text) : new Map();
    if (!isDict(data)) throw new PyCrash("AttributeError", `'${pyTypeName(data)}' object has no attribute 'setdefault'`);
    if (!data.has("tasks")) data.set("tasks", new Map());
    return data;
  }

  loadState(): HubState {
    return new HubState(this.readState());
  }

  /**
   * 按主任务、再按主任务的顶层键做三方合并，只写这一份 state 读出来之后改过的键；两边改了同一个键时以本次为准，
   * 记一条 state.conflict。不是 loadState 读出来的（测试里手搭的）照旧整份写。
   */
  async saveState(state: HubState | PyDict): Promise<void> {
    await withFileLock(join(dirname(this.statePath()), ".state.lock"), async () => {
      if (!(state instanceof HubState)) {
        writeTextAtomic(this.statePath(), canonicalState(state));
        return;
      }
      const disk = this.readState();
      const diskTasks = pyItem(disk, "tasks") as PyDict;
      const written: [string, string, string | null][] = [];
      for (const [taskKey, ts] of state.tasks()) {
        const task = String(taskKey);
        const seen = state.seen.get(task);
        const theirs = diskTasks.get(task);
        if (seen === undefined || !isDict(theirs)) {
          diskTasks.set(task, ts);
          if (!isDict(ts)) throw new PyCrash("AttributeError", `'${pyTypeName(ts)}' object has no attribute 'items'`);
          for (const [key, value] of ts) written.push([task, String(key), canonicalJson(value)]);
          continue;
        }
        if (!isDict(ts)) throw new PyCrash("TypeError", `'${pyTypeName(ts)}' object is not iterable`);
        const keys = [...new Set([...[...ts.keys()].map(String), ...seen.keys()])];
        for (const key of keys) {
          const mine = ts.has(key) ? canonicalJson(ts.get(key) as PyValue) : null;
          const before = seen.get(key) ?? null;
          if (mine === before) continue;
          const onDisk = theirs.has(key) ? canonicalJson(theirs.get(key) as PyValue) : null;
          if (onDisk !== before && onDisk !== mine) await this.appendEvent("state.conflict", [["task", task], ["key", key]]);
          if (ts.has(key)) theirs.set(key, ts.get(key) as PyValue);
          else theirs.delete(key);
          written.push([task, key, mine]);
        }
      }
      writeTextAtomic(this.statePath(), canonicalState(disk));
      for (const [task, key, mine] of written) {
        const seen = state.seen.get(task) ?? new Map<string, string>();
        state.seen.set(task, seen);
        if (mine === null) seen.delete(key);
        else seen.set(key, mine);
      }
    });
  }

  agentRecord(agent: string): PyDict {
    const text = readText(this.agentPath(agent));
    if (pyStrip(text)) return loads(text) as PyDict;
    return new Map<string, PyValue>([["name", agent], ["sessions", new Map()]]);
  }

  saveAgentRecord(agent: string, record: PyDict): void {
    writeTextAtomic(this.agentPath(agent), canonicalState(record));
  }

  /** 回合结束只写本回合的会话：同一个工人可能同时在两个主任务里跑，回合开始时读的整份记录早已过时。 */
  async saveAgentSession(agent: string, sessionKey: string, session: PyValue): Promise<void> {
    await withFileLock(join(dirname(this.agentPath(agent)), ".agents.lock"), () => {
      const record = this.agentRecord(agent);
      if (!record.has("sessions")) record.set("sessions", new Map());
      const sessions = record.get("sessions");
      if (!isDict(sessions)) throw new PyCrash("TypeError", `'${pyTypeName(sessions)}' object does not support item assignment`);
      sessions.set(sessionKey, session);
      record.set("last_turn_at", utcNow());
      this.saveAgentRecord(agent, record);
    });
  }

  // -- 投递与收信 --------------------------------------------------------------

  async deliver(meta: Meta, fields: ReadonlyMap<string, PyValue>): Promise<string> {
    const head = new Map(meta);
    const field = (key: string): string => {
      const value = head.get(key);
      if (value === undefined) throw new PyCrash("KeyError", `'${key}'`);
      return value;
    };
    // 照 Python 的次序：有 msg-id 就不碰发信人；缺发信人时信照样发出去，记账本时才报 KeyError
    head.set("msg-id", head.get("msg-id") || newMsgId(field("from")));
    const msgId = head.get("msg-id") as string;
    const text = renderLetter(head, fields);
    const box = this.inbox(field("to"));
    mkdirSync(box, { recursive: true });
    if (!pyPublishNew(join(box, `${msgId}.md`), Buffer.from(text, "utf8"))) throw new HubError(`信件编号冲突：${msgId}`);
    await this.appendEvent("letter.delivered", [
      ["msg_id", msgId], ["sender", field("from")], ["to", field("to")], ["type", field("type")], ["task_id", field("task-id")], ["sha256", sha256Text(text)],
    ]);
    return msgId;
  }

  /** new 下的信，照 sorted(Path) 的次序（Windows 上不分大小写）。 */
  unread(agent: string): string[] {
    const box = this.inbox(agent);
    if (!isDirectory(box)) return [];
    return globSuffix(box, ".md").map((name) => join(box, name));
  }

  /** 读信：从 new 移到 cur（同盘改名，移动即回执；目标已在就照 os.rename 报错）。 */
  async take(path: string): Promise<string> {
    const agentDir = dirname(dirname(path));
    const target = join(agentDir, "cur", basename(path));
    mkdirSync(dirname(target), { recursive: true });
    pyRename(path, target);
    await this.appendEvent("letter.taken", [["msg_id", stem(path)], ["agent", basename(agentDir)]]);
    return target;
  }
}

function isNonEmptyFile(path: string): boolean {
  try {
    const stat = statSync(path);
    return stat.isFile() && stat.size > 0;
  } catch {
    return false;
  }
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

const stem = (path: string): string => {
  const name = basename(path);
  const at = name.lastIndexOf(".");
  return at > 0 ? name.slice(0, at) : name;
};

/** sorted(directory.glob("*" + suffix)) 的文件名：Windows 上匹配与排序都不分大小写（照 pathlib 的 normcase）。 */
function globSuffix(directory: string, suffix: string, prefix = ""): string[] {
  const fold = (text: string): string => (WIN ? pyLower(text) : text);
  return readdirSync(directory)
    .filter((name) => fold(name).endsWith(fold(suffix)) && fold(name).startsWith(fold(prefix)) && name.length >= prefix.length + suffix.length)
    .sort((a, b) => (fold(a) < fold(b) ? -1 : fold(a) > fold(b) ? 1 : 0));
}

/** kit_hub.DirLock：base 的目录锁，占用超时照 Python 报 HubError（持有者照 dict 的 repr）。 */
export class DirLock {
  private readonly lock: BaseDirLock;

  constructor(path: string, waitSeconds = 30) {
    this.lock = new BaseDirLock(path, waitSeconds);
  }

  get path(): string {
    return this.lock.path;
  }

  acquire(): this {
    try {
      this.lock.acquire();
    } catch (error) {
      if (!(error instanceof LockBusyError)) throw error;
      const owner = new Map(Object.entries(this.lock.owner())) as PyDict;
      throw new HubError(`锁被占用：${this.lock.path}（持有者 ${owner.size ? pyReprValue(owner) : "未知"}）`, EXIT_BLOCKED);
    }
    return this;
  }

  release(): void {
    this.lock.release();
  }
}

/** pi 岗位的限流不走 rate_limit_event：内核认的是接口报错（TurnRunner 的 THROTTLE 与 throttleReset）。 */
const PI_THROTTLE_EVIDENCE = "模型接口报错里的限流（429、额度用尽之类）：报错写了重置时刻就扣到那之后 1 分钟，没写就从 5 分钟起加倍退避";

/** 回合撞上额度限制或内核自己等一会儿：读掉的信先扣着，到时放回。交回解除的时刻（就地改 ts）。 */
export async function holdLetters(hub: Hub, ts: PyDict, agent: string, names: readonly string[], until: number,
  suffix: string | null, turnId: string, reason: string | null = null): Promise<string> {
  const at = utcNow(Math.trunc(until) * 1_000_000);
  if (!ts.has("held")) ts.set("held", []);
  const held = ts.get("held");
  if (!Array.isArray(held)) throw new PyCrash("AttributeError", `'${pyTypeName(held)}' object has no attribute 'append'`);
  held.push(new Map<string, PyValue>([["agent", agent], ["letters", [...names]], ["until", at], ["suffix", suffix], ["turn", turnId]]));
  if (suffix) {
    const stage = pyItem(pyItem(ts, "stages"), suffix) as PyDict;
    stage.set("status", "paused").set("note", `${reason || "额度限制"}：${at} 之后内核把信放回信箱，接着做`);
  }
  const task = pyStrValue(pyItem(ts, "task"));
  await hub.appendEvent("letters.held", [["task", pyItem(ts, "task")], ["agent", agent], ["letters", [...names]], ["until", at], ["reason", reason || "额度限制"]]);
  if (reason) return at;
  await hub.deliver(new Map([["from", KERNEL], ["to", OWNER], ["task-id", task], ["in-reply-to", "none"], ["type", "核验"]]), new Map<string, PyValue>([
    ["摘要", `${agent} 撞上模型接口的额度限制：${at} 之后内核自动接着做，不用回信`], ["提交", "无"],
    ["验证", Object.hasOwn(ROSTER, agent) && ROSTER[agent]?.adapter === "claude" ? "事件流里的 rate_limit_event（rejected，resetsAt）" : PI_THROTTLE_EVIDENCE], ["偏离", "无"],
    ["需协调人决定", `无。要提前接着做，就在解除之后用 kit_hub.py send ${task} --type 回复`], ["证据", `回合 ${turnId}`],
  ]));
  return at;
}

/** 到点的扣信放回信箱（cur 移回 new），停下的阶段回到 assigned；交回放回了哪些主任务的信。 */
export async function releaseHeld(hub: Hub): Promise<string[]> {
  const state = hub.loadState();
  const now = utcNow();
  const released: string[] = [];
  for (const [taskKey, ts] of state.tasks()) {
    const task = String(taskKey);
    const heldValue = pyGet(ts as PyValue, "held");
    const held = heldValue === null || heldValue === false ? [] : (heldValue as PyValue[]);
    const due = held.filter((item) => {
      const until = pyItem(item, "until");
      if (typeof until !== "string") throw new PyCrash("TypeError", `'<=' not supported between instances of '${pyTypeName(until)}' and 'str'`);
      return until <= now;
    });
    for (const item of due) {
      const suffixValue = pyGet(item, "suffix");
      const stage = pyGet(pyItem(ts as PyValue, "stages"), suffixValue === null || suffixValue === "" ? "" : pyStrValue(suffixValue));
      const agent = pyItem(item, "agent");
      const letters = pyItem(item, "letters");
      if (stage !== null && !pyEq(pyItem(stage, "status"), "paused")) {
        await hub.appendEvent("letters.dropped", [["task", task], ["agent", agent], ["letters", letters], ["stage_status", pyItem(stage, "status")]]);
        continue;
      }
      const box = hub.inbox(pyStrValue(agent));
      for (const name of letters as PyValue[]) {
        try {
          pyRename(join(dirname(box), "cur", pyStrValue(name)), join(box, pyStrValue(name)));
        } catch {
          // 几个进程同时放：挪不动的就是别人已经放回了
        }
      }
      if (stage !== null) (stage as PyDict).set("status", "assigned").set("note", "");
      await hub.appendEvent("letters.released", [["task", task], ["agent", agent], ["letters", letters]]);
    }
    if (due.length) {
      (ts as PyDict).set("held", held.filter((item) => !due.some((other) => pyEq(item, other))));
      released.push(task);
    }
  }
  if (released.length) await hub.saveState(state);
  return released;
}

/** 账本里的事件（坏行跳过）。 */
export function ledgerEvents(hub: Hub): PyValue[] {
  if (!existsSync(hub.ledger())) return [];
  const events: PyValue[] = [];
  for (const line of jsonlLines(readText(hub.ledger()))) {
    try {
      events.push(loads(line));
    } catch {
      // 照 Python：json.loads 报 ValueError 的行跳过
    }
  }
  return events;
}

/** 要覆盖的 brief.md、report.md 先改名留档：brief.1.md、brief.2.md…… */
export function keepPrevious(path: string): void {
  if (!existsSync(path)) return;
  const name = basename(path);
  const at = name.lastIndexOf(".");
  const [base, suffix] = at > 0 ? [name.slice(0, at), name.slice(at)] : [name, ""];
  const index = globSuffix(dirname(path), suffix, `${base}.`).length + 1;
  pyReplace(path, join(dirname(path), `${base}.${index}${suffix}`));
}

/** 信属于哪个主任务（读信头的 task-id）。 */
export function letterMain(path: string): string | null {
  return stageOf(parseLetter(readText(path))[0].get("task-id") ?? "")[0];
}
