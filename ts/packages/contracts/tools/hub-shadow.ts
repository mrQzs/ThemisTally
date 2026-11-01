// ⑤-影子（迁移计划第 ⑤ 步）：Python hub 照常办事，影子把同一份快照交给 python_probe.py 与 ts_probe.ts（Bun），逐字比带标签的
// 结果，攒“TS hub 会做出同样决定”的证据。只读：不拿 hub 的锁、不写信箱，结果写到 <仓库>/.agent/runs/_shadow/。
// 用法（外面套 backup_privilege.py off：与以后经 Start-Process 起的 TS hub 同一种令牌，读不穿别的进程的独占打开）：
//   python ts/packages/contracts/probes/backup_privilege.py off bun ts/packages/contracts/tools/hub-shadow.ts --repo <仓库> --once
//   ……同上，--watch [--interval 30] [--rounds N]（算满 N 轮就停，给契约用）
// 比什么：状态（读出与账本）；每个主任务的只读结论与 guard 的整张表；每封信的读出、解析、往返、形状校验；写给协调人的信单独成批时
// 的内核代办与任务书；账本里每次 route.kernel 的那批信重算的下一步（还要与账本记的一致，partial 时是它的前缀）；已结束回合的审计、
// 半截会话与生效档位。--watch 时只算变了的部分，另比新出现的 letter.rejected：上一份与这一份快照的状态各算一次 guard，对上一个
// 就算一致，都对不上记成“时序”交给人看；watch 开始以后才结束的回合，TS 的审计还要与 hub 当时写下的 result.json 比（只比同一版
// 内核写下的）。前面几类是两边探针彼此一致，这两类是 TS 与真实 hub 的决定一致。
// 探针不开在用的文件：状态与账本复制进临时的快照仓库，信件与事件流由这里经 fs 读出、按原始字节传过去，会话文件按会话号复制进
// 临时目录，用完删掉。结果只写数量、对不上的键（主任务号、信的文件名、回合号）与快照的哈希，不写内容。
// --watch 的某一轮出错（探针失败、回合目录在列出与读取之间被清掉……）只记错误的类型，接着跑；出错的那一轮不算数，下一轮从上一次
// 成功的那份快照比起。退出码：0 一致，1 有对不上的，2 出错（--once），3 快照不稳。
// 对不上的那一轮另存一份快照（<输出目录>/snapshots/<时刻>/），给事后重放：同一个差异键只存第一次，最多 10 份、合计 2 GB，到了只记报告；
// 回合几类对不上才带那几个回合的事件流与会话文件。会话文件是工人的完整对话，敏感程度与信箱一样：只放在本机的 .agent/runs/_shadow/ 下
// （Git 忽略），查完就删（只删 _shadow/snapshots/ 下的目录），不提交、不外传。重放：……同上，--snapshot <另存的目录>，先复制到临时目录，两边照常探、
// 照常比，报告写进那个目录的 replay.json；另存时与现在的 kit_hub.py 不同就报出来，退出码 4。
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { sleepSync } from "@themis/base/fsutil";
import { jsonlLines } from "@themis/base/jsonl";
import { type PyValue, dumps, loads } from "@themis/base/pyjson";
import {
  COORDINATOR, COORDINATOR_TYPES, DELIVER_TOOL, KERNEL, KERNEL_TYPES, OWNER, OWNER_TYPES, ROSTER, STAGE_ORDER, STAGE_WORKER,
  STRUCTURED_TOOL, WORKER_TYPES,
} from "@themis/hub/constants";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";

const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);
const TEXT = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
const PROBES = resolve(dirname(fileURLToPath(import.meta.url)), "..", "probes");
const PYTHON = [process.env["THEMIS_PYTHON"] ?? "python", join(PROBES, "python_probe.py")];
const TS = [process.execPath, join(PROBES, "ts_probe.ts")];
const SNAPSHOT_TRIES = 5;
// 回合按事件流的字节数分批：每批 30 MB 时 Bun 探针的峰值到过 1.6 GB，降到 10 MB（今天内存紧过两次）
const BATCH_BYTES = 10 * 1024 * 1024;

type Item = Record<string, unknown>;
interface Mismatch {
  readonly category: string;
  readonly key: string;
  readonly state_sha256: string;
}
interface Snapshot {
  readonly state: Buffer;
  readonly stateSha: string;
  readonly ledger: Buffer;
  /** 信箱里的信：相对 .agent/mailbox 的路径（正斜杠）→ 原始字节。 */
  readonly letters: Map<string, Buffer>;
}

const sha256 = (bytes: Buffer | string): string => createHash("sha256").update(bytes).digest("hex");

// --- 快照 ------------------------------------------------------------------------------------------------------

function readOr(path: string): Buffer {
  try {
    return readFileSync(path);
  } catch {
    return Buffer.alloc(0);
  }
}

/** 信箱里各收信人 new 与 cur 下的信的相对路径，排好序。 */
function letterPaths(mailbox: string): string[] {
  const inbox = join(mailbox, "inbox");
  if (!existsSync(inbox)) return [];
  const found: string[] = [];
  for (const agent of readdirSync(inbox)) {
    for (const box of ["new", "cur"]) {
      const dir = join(inbox, agent, box);
      if (!existsSync(dir)) continue;
      for (const name of readdirSync(dir)) if (name.endsWith(".md")) found.push(`inbox/${agent}/${box}/${name}`);
    }
  }
  return found.sort();
}

function fingerprint(mailbox: string): string {
  const ledger = join(mailbox, "ledger", "events.jsonl");
  return [sha256(readOr(join(mailbox, "ledger", "state.json"))), existsSync(ledger) ? statSync(ledger).size : 0, ...letterPaths(mailbox)].join(LF);
}

/**
 * 取一份前后一致的快照：读之前与读之后各核一次 state.json 的哈希、账本的长度与信件的文件名，不一致就重取，最多 SNAPSHOT_TRIES 次；
 * 一直不一致时交回 null（这一轮记成“快照不稳，跳过”，不拿撕裂的快照去比）。THEMIS_SHADOW_PAUSE 给了一个目录时，每次读完先写
 * paused-<次>，等 go-<次> 出现再核对：只给契约造冲突用。
 */
export function takeSnapshot(repo: string): { snapshot: Snapshot | null; tries: number } {
  const mailbox = join(repo, ".agent", "mailbox");
  for (let attempt = 1; attempt <= SNAPSHOT_TRIES; attempt += 1) {
    const before = fingerprint(mailbox);
    const state = readOr(join(mailbox, "ledger", "state.json"));
    const ledgerSize = Number(before.split(LF)[1]);
    const ledger = readOr(join(mailbox, "ledger", "events.jsonl")).subarray(0, ledgerSize);
    const letters = new Map<string, Buffer>();
    let torn = false;
    for (const rel of letterPaths(mailbox)) {
      try {
        letters.set(rel, readFileSync(join(mailbox, ...rel.split("/"))));
      } catch {
        torn = true; // 读的时候被收走了（new 移到 cur）
      }
    }
    pauseForTest(attempt);
    if (!torn && fingerprint(mailbox) === before && sha256(state) === before.split(LF)[0]) {
      return { snapshot: { state, stateSha: sha256(state), ledger, letters }, tries: attempt };
    }
  }
  return { snapshot: null, tries: SNAPSHOT_TRIES };
}

function pauseForTest(attempt: number): void {
  const dir = process.env["THEMIS_SHADOW_PAUSE"];
  if (!dir) return;
  writeFileSync(join(dir, `paused-${attempt}`), "");
  const until = Date.now() + 60_000;
  while (!existsSync(join(dir, `go-${attempt}`)) && Date.now() < until) sleepSync(20);
}

// --- 探针 ------------------------------------------------------------------------------------------------------

class ProbeFailed extends Error {
  override name = "ProbeFailed";
}

/** 一批请求交给一边的探针：（结果，探针进程的峰值内存，字节；拿不到是 0）。 */
function batchWithPeak(argv: readonly string[], items: readonly Item[]): { results: Item[]; peak: number } {
  const done = spawnSync(argv[0] as string, argv.slice(1), {
    input: JSON.stringify({ op: "batch", items }), encoding: "utf8", maxBuffer: 2 * 1024 * 1024 * 1024, timeout: 1_800_000,
  });
  if (done.status !== 0) throw new ProbeFailed(`探针退出码 ${done.status}（${argv[0]}）`);
  const reply = JSON.parse(done.stdout) as { results: Item[]; peak_bytes?: number | null };
  return { results: reply.results, peak: reply.peak_bytes ?? 0 };
}

function batch(argv: readonly string[], items: readonly Item[]): Item[] {
  return batchWithPeak(argv, items).results;
}

/** 每一类的数：比了几个、几个对不上、用时（秒）、两边探针进程的峰值内存（MB，取这一类各批里最大的）。 */
interface Count {
  compared: number;
  mismatched: number;
  seconds: number;
  peak_mb_python: number;
  peak_mb_ts: number;
}

class Comparison {
  readonly counts = new Map<string, Count>();
  readonly mismatches: Mismatch[] = [];

  readonly stateSha: string;

  constructor(stateSha: string) {
    this.stateSha = stateSha;
  }

  /** 同一批请求交给两边，逐个比带标签的结果；交回 TS 的结果（再与 hub 记下的决定比时，比的是 TS 会不会做出同样的决定）。 */
  run(category: string, keys: readonly string[], items: readonly Item[]): Item[] {
    const start = Date.now();
    const python = batchWithPeak(PYTHON, items);
    const ts = batchWithPeak(TS, items);
    keys.forEach((key, index) => {
      if (JSON.stringify(python.results[index]) !== JSON.stringify(ts.results[index])) this.miss(category, key);
    });
    this.count(category, keys.length, Date.now() - start, python.peak, ts.peak);
    return ts.results;
  }

  miss(category: string, key: string): void {
    this.mismatches.push({ category, key, state_sha256: this.stateSha });
    const entry = this.entry(category);
    entry.mismatched += 1;
    this.counts.set(category, entry);
  }

  count(category: string, compared: number, millis: number, pythonPeak = 0, tsPeak = 0): void {
    const entry = this.entry(category);
    entry.compared += compared;
    entry.seconds = Math.round((entry.seconds * 1000 + millis) / 10) / 100;
    entry.peak_mb_python = Math.max(entry.peak_mb_python, Math.round(pythonPeak / 1048576));
    entry.peak_mb_ts = Math.max(entry.peak_mb_ts, Math.round(tsPeak / 1048576));
  }

  private entry(category: string): Count {
    let entry = this.counts.get(category);
    if (entry === undefined) {
      entry = { compared: 0, mismatched: 0, seconds: 0, peak_mb_python: 0, peak_mb_ts: 0 };
      this.counts.set(category, entry);
    }
    return entry;
  }
}

/** JSON 字面量写成 Python 的值：整数是 int。 */
function py(value: unknown): PyValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(py);
  return new Map(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, py(item)]));
}

// --- 各类比较 -----------------------------------------------------------------------------------------------------

/** guard 的整张表：信件类型 × 收信人 × 主任务号与各阶段号（另加不存在的阶段号与空号）。 */
function guardMetas(task: string): Record<string, string>[] {
  const types = [...new Set([...WORKER_TYPES, ...COORDINATOR_TYPES, ...OWNER_TYPES, ...KERNEL_TYPES])];
  const receivers = [...Object.keys(ROSTER), OWNER, KERNEL, "nobody"];
  const ids = [task, ...STAGE_ORDER.map((suffix) => `${task}-${suffix}`), `${task}-9-x`, ""];
  return types.flatMap((type) => receivers.flatMap((to) => ids.map((id) => ({ from: COORDINATOR, to, "task-id": id, type }))));
}

function taskNames(state: Buffer): string[] {
  try {
    return Object.keys((JSON.parse(state.toString("utf8")) as { tasks?: Record<string, unknown> }).tasks ?? {}).sort();
  } catch {
    return [];
  }
}

interface LedgerEvent {
  /** 账本里的行号（从 1 起）：对不上的键写“账本第 N 行”，事后照行号重查。 */
  readonly line: number;
  readonly event: Record<string, unknown>;
}

/** 账本里以换行结尾的完整行（正在写的半行不算，下一轮再看）：（解析出来的事件，完整行的行数）。 */
function ledgerEvents(ledger: Buffer): { events: LedgerEvent[]; lines: number } {
  const lines = ledger.toString("utf8").split(LF).slice(0, -1);
  const events: LedgerEvent[] = [];
  lines.forEach((text, index) => {
    try {
      const event = JSON.parse(text) as unknown;
      if (event && typeof event === "object" && !Array.isArray(event)) events.push({ line: index + 1, event: event as Record<string, unknown> });
    } catch {
      // 坏行由“状态”一类里的 ledger_events 两边各自跳过，这里不管
    }
  });
  return { events, lines: lines.length };
}

/** 交回比过的 guard 组合数（写进报告：整张表少了哪一维，结果照样相等，只有数得出来）。 */
function compareTasks(cmp: Comparison, snapRepo: string, tasks: readonly string[]): number {
  const names = [...tasks, "T999"]; // 不存在的主任务：guard 收到 None
  const metas = names.map(guardMetas);
  cmp.run("主任务", names, names.map((task, at) => ({ op: "hub.shadow_task", repo: snapRepo, task, metas: metas[at] })));
  return metas.reduce((sum, list) => sum + list.length, 0);
}

/** 快照里的 tasks（照 Python 的值：整数是 int）；读不出时是空的。 */
function taskMap(state: Buffer): Map<string, PyValue> {
  try {
    const tasks = (loads(state.toString("utf8")) as Map<string, PyValue>).get("tasks");
    return tasks instanceof Map ? (tasks as Map<string, PyValue>) : new Map();
  } catch {
    return new Map();
  }
}

/**
 * 提示词（⑤d1，themistally-15 提的静态一类）：全部 pi、claude 岗位的 role_prompt，加上每个主任务（watch 时只算 ts 变了的）协调人的一份、
 * 各个不是 idle 的阶段那个工人的一份 turn_prompt；参数取典型的（没有新信、不续接、没有报错与代办说明、没有输入目录，工作目录是主仓库）。
 * 两边用同一份快照、同一批任务书，没有时间差。
 */
function comparePrompts(cmp: Comparison, source: Source, snapRepo: string, names: readonly string[]): void {
  const { state } = source.snapshot;
  copyPromptInputs(source.files, source.git, snapRepo, state, names);
  const agents = Object.keys(ROSTER).filter((agent) => ["pi", "claude"].includes(ROSTER[agent]?.adapter ?? ""));
  const items: Item[] = agents.map((agent) => ({ op: "hub.prompt", fn: "role_prompt", args: [toTagged(agent)] }));
  const keys = agents.map((agent) => `${agent} 角色`);
  const tasks = taskMap(state);
  for (const name of names) {
    const ts = tasks.get(name);
    if (!(ts instanceof Map)) continue;
    const turn = (agent: string, taskId: string): Item => ({
      op: "hub.prompt", fn: "turn_prompt", args: ([snapRepo, ts, agent, taskId, [], source.workspace, null, null, null, null] as PyValue[]).map((arg) => toTagged(arg)),
    });
    items.push(turn(COORDINATOR, name));
    keys.push(`${name} 协调人`);
    const stages = ts.get("stages");
    for (const [suffix, stage] of stages instanceof Map ? stages : []) {
      const agent = STAGE_WORKER[String(suffix)];
      if (agent === undefined || !agents.includes(agent) || !(stage instanceof Map) || stage.get("status") === "idle") continue;
      items.push(turn(agent, `${name}-${String(suffix)}`));
      keys.push(`${name}-${String(suffix)}`);
    }
  }
  cmp.run("提示词", keys, items);
}

/**
 * turn_prompt 在快照仓库里要读的：各主任务与阶段目录的 brief.md、state.md，合同任务 runs 目录里算预算用的 claim、run.json、
 * reservation.json；还有 .git，指向主仓库的 git 目录（ls-tree 只读对象库）。都由这里经 fs 读出复制过去，探针不开主仓库里在用的文件。
 * 快照仓库因此与主仓库共用 index、HEAD 与 refs：在这里只准跑只读对象库的 git 命令（ls-tree、show、cat-file）；要跑 status、diff、add、
 * worktree 这些（status 会顺手刷新 index、要拿 index.lock，可能撞上 hub 正在做的提交），先换成私有的 git 目录加 alternates。
 */
function copyPromptInputs(repo: string, gitDir: string, snapRepo: string, state: Buffer, names: readonly string[]): void {
  const tasksDir = join(repo, ".agent", "mailbox", "tasks");
  for (const dir of existsSync(tasksDir) ? readdirSync(tasksDir) : []) {
    for (const file of ["brief.md", "state.md"]) {
      const from = join(tasksDir, dir, file);
      if (!existsSync(from)) continue;
      mkdirSync(join(snapRepo, ".agent", "mailbox", "tasks", dir), { recursive: true });
      writeFileSync(join(snapRepo, ".agent", "mailbox", "tasks", dir, file), readFileSync(from));
    }
  }
  const tasks = taskMap(state);
  for (const name of names) {
    const ts = tasks.get(name);
    const contractTask = ts instanceof Map ? ts.get("contract_task") : null;
    if (typeof contractTask !== "string" || !contractTask) continue;
    const runs = join(repo, ".agent", "runs", contractTask);
    for (const attempt of existsSync(runs) ? readdirSync(runs) : []) {
      const from = join(runs, attempt);
      if (!statSync(from).isDirectory()) continue;
      const to = join(snapRepo, ".agent", "runs", contractTask, attempt);
      mkdirSync(existsSync(join(from, "claim")) ? join(to, "claim") : to, { recursive: true });
      for (const rel of ["run.json", join("claim", "reservation.json")]) if (existsSync(join(from, rel))) writeFileSync(join(to, rel), readFileSync(join(from, rel)));
    }
  }
  if (existsSync(gitDir)) writeFileSync(join(snapRepo, ".git"), statSync(gitDir).isDirectory() ? `gitdir: ${gitDir}${LF}` : readFileSync(gitDir));
}

function compareLetters(cmp: Comparison, snapshot: Snapshot, only?: ReadonlySet<string>): void {
  const rels = [...snapshot.letters.keys()].filter((rel) => !only || only.has(rel));
  cmp.run("信件", rels, rels.map((rel) => ({ op: "hub.shadow_letter", b64: (snapshot.letters.get(rel) as Buffer).toString("base64") })));
}

function compareRoutine(cmp: Comparison, snapRepo: string, snapshot: Snapshot, only?: ReadonlySet<string>): void {
  const rels = [...snapshot.letters.keys()].filter((rel) => rel.startsWith(`inbox/${COORDINATOR}/`) && (!only || only.has(rel)));
  cmp.run("代办", rels, rels.map((rel) => ({ op: "hub.shadow_routine", repo: snapRepo, b64: (snapshot.letters.get(rel) as Buffer).toString("base64") })));
}

/** 账本里每次 route.kernel：那批信重算的下一步两边一致，并且与账本记的相同（partial 时是重算结果的前缀）。 */
function compareRoutes(cmp: Comparison, snapshot: Snapshot, events: readonly LedgerEvent[], after = 0): number {
  const byName = new Map<string, Buffer>();
  for (const [rel, bytes] of snapshot.letters) if (rel.startsWith(`inbox/${COORDINATOR}/`)) byName.set(rel.split("/").at(-1) as string, bytes);
  const routes = events.filter(({ event, line }) => line > after && event["event"] === "route.kernel");
  const usable = routes.filter(({ event }) => ((event["letters"] as string[] | undefined) ?? []).every((name) => byName.has(name)));
  const keys = usable.map(({ line }) => `账本第 ${line} 行`);
  const results = cmp.run("route.kernel", keys, usable.map(({ event }) => ({
    op: "hub.shadow_route", b64s: (event["letters"] as string[]).map((name) => (byName.get(name) as Buffer).toString("base64")),
  })));
  usable.forEach(({ event }, at) => {
    const result = results[at] as { ok?: boolean; value?: Tagged };
    const recorded = (event["moves"] as string[] | undefined) ?? [];
    const moves = result.ok ? ((fromTagged(result.value as Tagged) as PyValue[])[0] as Map<string, PyValue>[]) : [];
    const ours = moves.map((move) => {
      const suffix = String(move.get("suffix"));
      return `${String(move.get("type"))} → ${STAGE_WORKER[suffix] ?? "?"}（${String(event["task"])}-${suffix}）`;
    });
    const fits = event["partial"] ? recorded.every((move, index) => ours[index] === move) && recorded.length <= ours.length
      : JSON.stringify(recorded) === JSON.stringify(ours);
    if (!fits) cmp.miss("route.kernel 与账本", keys[at] as string);
  });
  cmp.count("route.kernel 与账本", usable.length, 0);
  return routes.length - usable.length;
}

interface Turn {
  readonly id: string;
  readonly agent: string;
  readonly dir: string;
  readonly size: number;
}

/** 已经结束的回合（有 result.json）。 */
function endedTurns(repo: string): Turn[] {
  const root = join(repo, ".agent", "mailbox", "turns");
  if (!existsSync(root)) return [];
  const turns: Turn[] = [];
  for (const agent of readdirSync(root).sort()) {
    for (const id of readdirSync(join(root, agent)).sort()) {
      const dir = join(root, agent, id);
      if (existsSync(join(dir, "result.json")) && existsSync(join(dir, "stream.jsonl"))) turns.push({ id: `${agent}/${id}`, agent, dir, size: statSync(join(dir, "stream.jsonl")).size });
    }
  }
  return turns;
}

/** run_turn 原样写进 result.json 的审计字段（warnings、deliver_refusals 与生效档位另算；api_error、output_error 还会被 blocked、
 * interface_problem、delivered_output 改写，归 ⑤d）。 */
const RECORD_FIELDS = ["models", "tool_calls", "violations", "usage", "terminal", "thinking_chars", "thinking_tokens"];
/** 影子这棵树里 kit_hub.py 的哈希，算法与 kit_hub 的 HUB_SHA256 相同：result.json 是同一版内核写下的，才拿来比。 */
const KIT_HUB_SHA = sha256(readFileSync(resolve(PROBES, "..", "..", "..", "..", "scripts", "kit_hub.py")));

/** 一个要与 result.json 比的回合：它在这一批里的审计与生效档位是第几个请求。 */
interface Recorded {
  readonly id: string;
  readonly adapter: string;
  readonly record: Map<string, PyValue>;
  readonly audit: number;
  readonly effort: number | null;
  /** 这一批里 role_prompt 的请求是第几个，与 hub 写下的 role.md（读不到是 null）。 */
  readonly role: number;
  readonly roleMd: string | null;
  /** 会话文件在 result.json 写下之后又改过（claude 的会话被 --resume 接着写）：生效档位对不上算“时序”。 */
  readonly sessionMoved: boolean;
}

/** 一个回合比对时读到的文件（result.json、stream.jsonl，有的话 role.md）：原始字节与时刻。对不上的回合照这一份另存，不事后再读。 */
interface TurnFiles {
  readonly turn: Turn;
  readonly files: Map<string, { readonly bytes: Buffer; readonly atimeMs: number; readonly mtimeMs: number }>;
}

/** kit_hub.read_text 对一份已经读出来的字节：UTF-8（BOM 照留，坏字节报错）、通用换行。 */
function textOf(bytes: Buffer): string {
  return TEXT.decode(bytes).split(CR + LF).join(LF).split(CR).join(LF);
}

/**
 * 回合：审计重算、半截会话、claude 的生效档位。会话文件按会话号复制进临时的 home 与快照仓库，两边看同一份字节。
 * againstRecords（--watch 有了上一份快照之后，即 watch 开始以后才结束的回合）时，TS 的结果还要与 hub 当时写下的 result.json 比；
 * 别的内核写下的不比。交回别的内核写下的个数，与对不上的回合比对时读到的文件（每批比完只留对不上的，内存只占一批）。
 */
function compareTurns(cmp: Comparison, source: Source, snapRepo: string, home: string, turns: readonly Turn[], againstRecords: boolean): { otherKernel: number; missed: TurnFiles[] } {
  let otherKernel = 0;
  const missed: TurnFiles[] = [];
  let items: Item[] = [];
  let keys: string[] = [];
  let recorded: Recorded[] = [];
  let pending: TurnFiles[] = [];
  let size = 0;
  const flush = (): void => {
    if (items.length) {
      const before = cmp.mismatches.length;
      const results = cmp.run("回合", keys, items);
      for (const turn of recorded) compareRecord(cmp, turn, results);
      const fresh = cmp.mismatches.slice(before);
      missed.push(...pending.filter(({ turn }) => fresh.some(({ key }) => key.startsWith(`${turn.id} `) || key.startsWith(`${turn.id}：`))));
    }
    [items, keys, recorded, pending, size] = [[], [], [], [], 0];
  };
  for (const turn of turns) {
    const spec = ROSTER[turn.agent];
    if (!spec) continue;
    const files: TurnFiles["files"] = new Map();
    for (const name of ["result.json", "stream.jsonl", "role.md"]) {
      const path = join(turn.dir, name);
      if (name === "role.md" && !existsSync(path)) continue;
      const info = statSync(path);
      files.set(name, { bytes: readFileSync(path), atimeMs: info.atimeMs, mtimeMs: info.mtimeMs });
    }
    pending.push({ turn, files });
    const resultFile = files.get("result.json") as { bytes: Buffer; mtimeMs: number };
    const result = JSON.parse(resultFile.bytes.toString("utf8")) as { workspace?: string | null; session_id?: unknown; hub_sha256?: unknown };
    // 照 hub 的 run_turn：事件流按通用换行读，审计用的工具表加上交差用的工具（pi 的 deliver、claude 的 StructuredOutput）
    const lines = jsonlLines(textOf((files.get("stream.jsonl") as { bytes: Buffer }).bytes));
    const tools = [...(spec.tools ?? []), spec.adapter === "claude" ? STRUCTURED_TOOL : DELIVER_TOOL];
    const fn = spec.adapter === "claude" ? "audit_claude_stream" : "audit_pi_stream";
    const audit = (name: string, ...args: PyValue[]): Item => ({ op: "hub.audit", fn: name, args: args.map((arg) => toTagged(arg)), home });
    const auditAt = items.length;
    items.push(audit(fn, lines, py({ ...spec, tools }), result.workspace ?? null, source.workspace));
    keys.push(`${turn.id} 审计`);
    let effortAt: number | null = null;
    let sessionTime = 0;
    if (typeof result.session_id === "string" && result.session_id) {
      sessionTime = copySessions(turn.agent, spec.adapter, result.session_id, source.files, source.home, snapRepo, home);
      if (spec.adapter === "claude") {
        effortAt = items.length;
        items.push(audit("claude_session_effort", result.session_id));
        keys.push(`${turn.id} 生效档位`);
      }
      items.push(audit("session_cut_short", snapRepo, turn.agent, spec.adapter, result.session_id));
      keys.push(`${turn.id} 半截会话`);
    }
    if (againstRecords && result.hub_sha256 !== KIT_HUB_SHA) otherKernel += 1;
    else if (againstRecords) {
      const roleAt = items.length;
      items.push({ op: "hub.prompt", fn: "role_prompt", args: [toTagged(turn.agent)] });
      keys.push(`${turn.id} 角色`);
      const role = files.get("role.md");
      recorded.push({
        id: turn.id, adapter: spec.adapter, record: loads(textOf(resultFile.bytes)) as Map<string, PyValue>, audit: auditAt, effort: effortAt,
        role: roleAt, roleMd: role ? role.bytes.toString("utf8") : null, sessionMoved: sessionTime > resultFile.mtimeMs,
      });
    }
    size += turn.size;
    if (size > BATCH_BYTES) flush();
  }
  flush();
  return { otherKernel, missed };
}

/** TS 的审计按 run_turn 的写法折成 result.json 的那几个字段，逐个与记下的比；对不上的键只写字段名，不写值。 */
function compareRecord(cmp: Comparison, turn: Recorded, results: readonly Item[]): void {
  const value = (at: number): PyValue | undefined => {
    const result = results[at] as { ok?: boolean; value?: Tagged };
    return result.ok ? fromTagged(result.value as Tagged) : undefined;
  };
  const list = (item: PyValue | undefined): PyValue[] => (Array.isArray(item) ? item : []);
  // role.md 只依赖模板与已提交的 AGENTS.md：TS 的 role_prompt 重算，逐字节比（设计稿第 7 节：prompt.md、inputs.json 只在契约里比）
  cmp.count("回合与 role.md", 1, 0);
  if (value(turn.role) !== turn.roleMd) cmp.miss("回合与 role.md", `${turn.id}：role.md`);
  const audit = value(turn.audit);
  cmp.count("回合与 result.json", 1, 0);
  if (!(audit instanceof Map)) {
    cmp.miss("回合与 result.json", `${turn.id}：审计出错`);
    return;
  }
  const refusals = list(audit.get("deliver_refusals"));
  const ours = new Map<string, PyValue>([
    ...RECORD_FIELDS.map((name): [string, PyValue] => [name, audit.get(name) ?? null]),
    ["warnings", list(audit.get("warnings"))],
    ["deliver_refusals", BigInt(refusals.length)],
    ["deliver_refusal_chars", refusals.reduce<bigint>((sum, chars) => sum + BigInt(chars as bigint), 0n)],
  ]);
  if (turn.adapter !== "claude") ours.set("effort_effective", list(audit.get("effective_levels")).map(String).join(",") || null);
  else if (turn.effort !== null) ours.set("effort_effective", value(turn.effort) ?? null);
  const same = (name: string, item: PyValue): boolean => dumps(item, { sortKeys: true }) === dumps(turn.record.get(name) ?? null, { sortKeys: true });
  const differ = [...ours].filter(([name, item]) => !same(name, item)).map(([name]) => name);
  if (!differ.length) return;
  // 只有 claude 的生效档位取自会话文件；pi 的来自事件流，会话文件续接时变新也与它无关，对不上就是真的不一致
  if (turn.adapter === "claude" && turn.sessionMoved && differ.join() === "effort_effective") {
    cmp.count("时序", 1, 0);
    cmp.miss("时序", `${turn.id}：effort_effective`);
    return;
  }
  cmp.miss("回合与 result.json", `${turn.id}：${differ.join("、")}`);
}

/**
 * 按会话号复制会话文件：claude 的在 sourceHome/.claude/projects 下各目录里的“<号>.jsonl”（实时跑时是本机的 home），pi 的在 repo 的信箱
 * sessions/<工人> 下以“_<号>.jsonl”结尾的文件。
 * 交回复制的文件里最晚的修改时刻（毫秒，没有是 0）。
 */
function copySessions(agent: string, adapter: string, session: string, repo: string, sourceHome: string, snapRepo: string, home: string): number {
  let latest = 0;
  // 修改时刻照原文件设：从另存的快照重放时，“会话文件比 result.json 新”要与当时一样
  const copy = (from: string, to: string): void => {
    mkdirSync(dirname(to), { recursive: true });
    writeFileSync(to, readFileSync(from));
    const info = statSync(from);
    utimesSync(to, info.atimeMs / 1000, info.mtimeMs / 1000);
    latest = Math.max(latest, info.mtimeMs);
  };
  if (adapter === "claude") {
    const projects = join(sourceHome, ".claude", "projects");
    if (!existsSync(projects)) return latest;
    for (const dir of readdirSync(projects)) {
      const file = join(projects, dir, `${session}.jsonl`);
      if (existsSync(file)) copy(file, join(home, ".claude", "projects", dir, `${session}.jsonl`));
    }
    return latest;
  }
  const sessions = join(repo, ".agent", "mailbox", "sessions", agent);
  if (!existsSync(sessions)) return latest;
  for (const name of readdirSync(sessions)) {
    if (name.endsWith(`_${session}.jsonl`)) copy(join(sessions, name), join(snapRepo, ".agent", "mailbox", "sessions", agent, name));
  }
  return latest;
}

/** 新出现的 letter.rejected：上一份与这一份快照里那个主任务的状态各算一次 guard，对上一个就算一致，都对不上记“时序”。 */
function compareRejections(cmp: Comparison, events: readonly LedgerEvent[], after: number, states: readonly Buffer[]): void {
  const rejected = events.filter(({ event, line }) => line > after && event["event"] === "letter.rejected");
  if (!rejected.length) return;
  const items: Item[] = [];
  const keys: string[] = [];
  for (const { event, line } of rejected) {
    const meta = py({ from: String(event["sender"]), to: String(event["to"]), "task-id": String(event["task_id"]), type: String(event["type"]) });
    const main = String(event["task_id"]).split("-")[0] as string;
    for (const state of states) {
      const tasks = (loads(state.toString("utf8")) as Map<string, PyValue>).get("tasks") as Map<string, PyValue> | undefined;
      items.push({ op: "hub.call", fn: "guard", args: [toTagged(tasks?.get(main) ?? null), toTagged(meta)] });
      keys.push(`账本第 ${line} 行`);
    }
  }
  const results = batch(TS, items);
  rejected.forEach(({ event }, at) => {
    const reasons = states.map((_, which) => {
      const result = results[at * states.length + which] as { ok?: boolean; value?: Tagged };
      return result.ok ? fromTagged(result.value as Tagged) : null;
    });
    if (!reasons.includes(String(event["reason"]))) cmp.miss("时序", keys[at * states.length] as string);
  });
  cmp.count("时序", rejected.length, 0);
}

// --- 一轮 ------------------------------------------------------------------------------------------------------

interface Previous {
  readonly snapshot: Snapshot;
  /** 上一轮看过的账本完整行数。 */
  readonly ledgerLines: number;
  readonly taskHashes: Map<string, string>;
  readonly turns: Map<string, number>;
}

function taskHashes(state: Buffer): Map<string, string> {
  try {
    const tasks = (JSON.parse(state.toString("utf8")) as { tasks?: Record<string, unknown> }).tasks ?? {};
    return new Map(Object.entries(tasks).map(([name, ts]) => [name, sha256(JSON.stringify(ts))]));
  } catch {
    return new Map();
  }
}

/**
 * 一轮读的来源。实时跑时：快照取自主仓库；回合、会话文件、任务书与合同的 runs 记录从主仓库读（files），claude 的会话从本机的 home 读，
 * git 是主仓库的 .git，提示词与审计的工作目录参数是主仓库（workspace）。从另存的快照重放时，files、home 是快照目录里的 repo、home，
 * git 与 workspace 是当时记下的。
 */
interface Source {
  readonly snapshot: Snapshot;
  readonly tries: number;
  readonly files: string;
  readonly home: string;
  readonly git: string;
  readonly workspace: string;
}

function round(repo: string, previous: Previous | null, keep: string | null): { report: Record<string, unknown>; next: Previous | null } {
  const { snapshot, tries } = takeSnapshot(repo);
  if (snapshot === null) return { report: { skipped: "快照不稳，跳过", tries }, next: null }; // 与出错一样：下一轮重试
  return compare({ snapshot, tries, files: repo, home: homedir(), git: join(repo, ".git"), workspace: repo }, previous, keep);
}

/** 用一份快照比一轮；keep 是另存快照的目录（重放时是 null，不再另存）。 */
function compare(source: Source, previous: Previous | null, keep: string | null): { report: Record<string, unknown>; next: Previous | null } {
  const { snapshot, tries } = source;
  const snapRepo = mkdtempSync(join(tmpdir(), "themis-shadow-snap-"));
  const home = mkdtempSync(join(tmpdir(), "themis-shadow-home-")); // 回合的会话文件复制到这里；另存也取这一份，删在最后
  try {
    const ledgerDir = join(snapRepo, ".agent", "mailbox", "ledger");
    mkdirSync(ledgerDir, { recursive: true });
    writeFileSync(join(ledgerDir, "state.json"), snapshot.state);
    writeFileSync(join(ledgerDir, "events.jsonl"), snapshot.ledger);
    const cmp = new Comparison(snapshot.stateSha);
    cmp.run("状态", ["state"], [{ op: "hub.box", repo: snapRepo, steps: [["read_state"], ["ledger_events"]] }]);
    const hashes = taskHashes(snapshot.state);
    const changed = previous ? [...hashes].filter(([name, hash]) => previous.taskHashes.get(name) !== hash).map(([name]) => name) : [...hashes.keys()];
    const guardCombos = compareTasks(cmp, snapRepo, changed.sort());
    comparePrompts(cmp, source, snapRepo, changed);
    const fresh = previous ? new Set([...snapshot.letters.keys()].filter((rel) => !previous.snapshot.letters.has(rel))) : undefined;
    compareLetters(cmp, snapshot, fresh);
    compareRoutine(cmp, snapRepo, snapshot, fresh);
    const { events, lines } = ledgerEvents(snapshot.ledger);
    const missing = compareRoutes(cmp, snapshot, events, previous?.ledgerLines ?? 0);
    if (previous) compareRejections(cmp, events, previous.ledgerLines, [previous.snapshot.state, snapshot.state]);
    const turns = endedTurns(source.files).filter((turn) => previous?.turns.get(turn.id) !== turn.size);
    const { otherKernel, missed } = compareTurns(cmp, source, snapRepo, home, turns, previous !== null);
    const report: Record<string, unknown> = {
      at: new Date().toISOString(), state_sha256: snapshot.stateSha, ledger_bytes: snapshot.ledger.length, letters: snapshot.letters.size, tries,
      categories: Object.fromEntries(cmp.counts), shadow_peak_mb: Math.round(process.resourceUsage().maxRSS / 1024), guard_combos: guardCombos, mismatches: cmp.mismatches, route_letters_missing: missing,
      result_json_other_kernel: otherKernel,
    };
    if (keep !== null && cmp.mismatches.length) report["snapshot"] = keepSnapshot(keep, source, previous, snapRepo, home, missed, cmp.mismatches, String(report["at"]));
    const seen = new Map(previous?.turns ?? []);
    for (const turn of turns) seen.set(turn.id, turn.size);
    return { report, next: { snapshot, ledgerLines: lines, taskHashes: hashes, turns: seen } };
  } finally {
    rmSync(snapRepo, { recursive: true, force: true });
    rmSync(home, { recursive: true, force: true });
  }
}

// --- 另存的快照 ------------------------------------------------------------------------------------------------

/**
 * 另存的快照最多几份、合计多少字节（按盘上已有的算，不只算这个进程存的）：watch 一跑几个小时，回合的事件流动辄几十 MB，不设限会把盘
 * 写满。THEMIS_SHADOW_KEEP_BYTES 只给契约换小的字节上限（照 THEMIS_SHADOW_PAUSE 的先例）。
 */
const KEEP_MAX = 10;
const keepBytes = (): number => Number(process.env["THEMIS_SHADOW_KEEP_BYTES"] ?? 2 * 1024 * 1024 * 1024);

const keyOf = (item: Mismatch): string => JSON.stringify([item.category, item.key]);

function putFile(root: string, rel: string, bytes: Buffer | string, times?: { readonly atimeMs: number; readonly mtimeMs: number }): void {
  const path = join(root, ...rel.split("/"));
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, bytes);
  if (times) utimesSync(path, times.atimeMs / 1000, times.mtimeMs / 1000);
}

/** 目录下的文件（相对路径用正斜杠、排好序），交回 [路径, 字节数, sha256]：manifest 只记这些，不记内容。 */
function listFiles(root: string, prefix = ""): [string, number, string][] {
  if (!existsSync(join(root, prefix))) return [];
  const rows: [string, number, string][] = [];
  for (const name of readdirSync(join(root, prefix)).sort()) {
    const rel = prefix ? `${prefix}/${name}` : name;
    const path = join(root, ...rel.split("/"));
    if (lstatSync(path).isDirectory()) rows.push(...listFiles(root, rel));
    else rows.push([rel, statSync(path).size, sha256(readFileSync(path))]);
  }
  return rows;
}

function treeBytes(dir: string): number {
  if (!existsSync(dir)) return 0;
  let total = 0;
  for (const name of readdirSync(dir)) {
    const info = lstatSync(join(dir, name));
    total += info.isDirectory() ? treeBytes(join(dir, name)) : info.size;
  }
  return total;
}

/** 主仓库此刻的 HEAD（只读的 rev-parse，不碰 index）；拿不到是 null。 */
function headOf(repo: string): string | null {
  const done = spawnSync("git", ["-C", repo, "rev-parse", "HEAD"], { encoding: "utf8", timeout: 30_000 });
  return done.status === 0 ? done.stdout.trim() : null;
}

/**
 * 对不上时另存这一轮的快照（themistally-15 的条件）。同一个差异键只存第一次（index.json 记着存在哪一份）；盘上已有 KEEP_MAX 份或合计
 * keepBytes() 字节就不存，只记报告。目录按序号命名（001、002……），类与键写进 manifest.json：键里有“/”，长名字也会吃掉路径余量。
 * 存的都是比对时用的那份字节：快照本身（状态、账本、信件）、上一份快照里要用的几样（状态、信件的文件名、账本行数、主任务的哈希）、
 * 快照仓库里提示词读过的任务书与 runs 记录；回合几类对不上时，才带那几个回合比对时读到的文件，与快照仓库、临时 home 里复制过的会话
 * 文件（不事后去 ~/.claude 读：claude 的会话可能已被 --resume 续写）。不带快照仓库里指向主仓库 git 目录的 .git：留在盘上的目录里有它，
 * 谁在里面跑一次 git status 就会刷新主仓库的 index；路径与当时的 HEAD 记在 manifest 里，重放时只在临时的快照仓库里重建。
 * 交回写进报告的一句：另存的目录名，或者没存的原因。
 */
function keepSnapshot(dir: string, source: Source, previous: Previous | null, snapRepo: string, home: string, missed: readonly TurnFiles[], mismatches: readonly Mismatch[], at: string): string {
  const indexPath = join(dir, "index.json");
  const index = existsSync(indexPath) ? (JSON.parse(readFileSync(indexPath, "utf8")) as Record<string, string>) : {};
  const fresh = mismatches.filter((item) => !Object.hasOwn(index, keyOf(item)));
  if (!fresh.length) return "差异键都已存过";
  const kept = existsSync(dir) ? readdirSync(dir).filter((name) => lstatSync(join(dir, name)).isDirectory()) : [];
  if (kept.length >= KEEP_MAX || treeBytes(dir) >= keepBytes()) return "快照已达上限";
  const name = String(Math.max(0, ...kept.map((entry) => (/^[0-9]+$/u.test(entry) ? Number(entry) : 0))) + 1).padStart(3, "0");
  const target = join(dir, name);
  const { snapshot } = source;
  putFile(target, "state.json", snapshot.state);
  putFile(target, "events.jsonl", snapshot.ledger);
  for (const [rel, bytes] of snapshot.letters) putFile(target, `letters/${rel}`, bytes);
  if (previous) putFile(target, "previous-state.json", previous.snapshot.state);
  for (const rel of [".agent/mailbox/tasks", ".agent/runs"]) {
    const from = join(snapRepo, ...rel.split("/"));
    if (existsSync(from)) cpSync(from, join(target, "repo", ...rel.split("/")), { recursive: true });
  }
  for (const { turn, files } of missed) {
    for (const [file, entry] of files) putFile(target, `repo/.agent/mailbox/turns/${turn.id}/${file}`, entry.bytes, entry);
    const session = (JSON.parse((files.get("result.json") as { bytes: Buffer }).bytes.toString("utf8")) as { session_id?: unknown }).session_id;
    const adapter = ROSTER[turn.agent]?.adapter;
    if (typeof session === "string" && session && adapter) copySessions(turn.agent, adapter, session, snapRepo, home, join(target, "repo"), join(target, "home"));
  }
  const manifest = {
    repo: source.workspace, git: source.git, head: headOf(source.workspace), kit_hub_sha256: KIT_HUB_SHA, at, state_sha256: snapshot.stateSha, mismatches,
    previous: previous && { ledger_lines: previous.ledgerLines, letters: [...previous.snapshot.letters.keys()], task_hashes: Object.fromEntries(previous.taskHashes) },
    files: listFiles(target),
  };
  putFile(target, "manifest.json", `${JSON.stringify(manifest, null, 2)}${LF}`);
  for (const item of fresh) index[keyOf(item)] = name;
  writeFileSync(indexPath, `${JSON.stringify(index, null, 2)}${LF}`);
  return name;
}

interface KeptManifest {
  readonly repo: string;
  readonly git: string;
  readonly kit_hub_sha256: string;
  readonly previous: { readonly ledger_lines: number; readonly letters: string[]; readonly task_hashes: Record<string, string> } | null;
}

/**
 * --snapshot：另存的快照先复制到 work（时刻照留），再照当时的样子读回来，存下的那份不被探针碰；watch 时的上一份快照照记下的重建，
 * 回合只有另存的那几个，照当时那样与 result.json 比。
 */
function loadKept(dir: string, work: string): { source: Source; previous: Previous | null; manifest: KeptManifest } {
  cpSync(dir, work, { recursive: true, preserveTimestamps: true });
  const manifest = JSON.parse(readFileSync(join(work, "manifest.json"), "utf8")) as KeptManifest;
  const letters = new Map<string, Buffer>();
  for (const [rel] of listFiles(join(work, "letters"))) letters.set(rel, readFileSync(join(work, "letters", ...rel.split("/"))));
  const state = readFileSync(join(work, "state.json"));
  const snapshot: Snapshot = { state, stateSha: sha256(state), ledger: readFileSync(join(work, "events.jsonl")), letters };
  const before = manifest.previous;
  const previous: Previous | null = before === null ? null : {
    snapshot: { state: readFileSync(join(work, "previous-state.json")), stateSha: "", ledger: Buffer.alloc(0), letters: new Map(before.letters.map((rel): [string, Buffer] => [rel, Buffer.alloc(0)])) },
    ledgerLines: before.ledger_lines, taskHashes: new Map(Object.entries(before.task_hashes)), turns: new Map(),
  };
  return { source: { snapshot, tries: 0, files: join(work, "repo"), home: join(work, "home"), git: manifest.git, workspace: manifest.repo }, previous, manifest };
}

function write(out: string, report: Record<string, unknown>, keep: boolean): void {
  mkdirSync(out, { recursive: true });
  const text = `${JSON.stringify(report, null, 2)}${LF}`;
  writeFileSync(join(out, "latest.json"), text);
  if (keep) writeFileSync(join(out, `${String(report["at"] ?? new Date().toISOString()).replace(/[:.]/gu, "-")}.json`), text);
}

/** 只记错误的类型与 fs 的错误码，不记消息：消息里可能带着信件、事件流的片段或命令行。 */
function failure(error: unknown): Record<string, unknown> {
  const code = (error as { code?: unknown } | null)?.code;
  return { at: new Date().toISOString(), error: { type: error instanceof Error ? error.name : typeof error, code: typeof code === "string" ? code : null } };
}

/** --watch 每轮先看的指纹：state.json 的哈希与账本的长度，变了才重算。 */
function quickPrint(mailbox: string): string {
  const ledger = join(mailbox, "ledger", "events.jsonl");
  return `${sha256(readOr(join(mailbox, "ledger", "state.json")))}:${existsSync(ledger) ? statSync(ledger).size : 0}`;
}

function main(argv: readonly string[]): number {
  const option = (name: string): string | undefined => {
    const at = argv.indexOf(name);
    return at >= 0 ? argv[at + 1] : undefined;
  };
  const repo = resolve(option("--repo") ?? ".");
  const out = resolve(option("--out") ?? join(repo, ".agent", "runs", "_shadow"));
  const keep = join(out, "snapshots");
  const kept = option("--snapshot");
  if (kept !== undefined) {
    const dir = resolve(kept);
    const work = mkdtempSync(join(tmpdir(), "themis-shadow-replay-"));
    let report: Record<string, unknown>;
    try {
      const { source, previous, manifest } = loadKept(dir, work);
      report = compare(source, previous, null).report;
      // 另存时与现在的 kit_hub.py 不同：与 result.json 比的回合会被悄悄算成“别的内核”而不比，看起来像零差异
      if (manifest.kit_hub_sha256 !== KIT_HUB_SHA) report["kernel_changed"] = { recorded: manifest.kit_hub_sha256, current: KIT_HUB_SHA };
    } catch (error) {
      report = failure(error);
    } finally {
      rmSync(work, { recursive: true, force: true });
    }
    writeFileSync(join(dir, "replay.json"), `${JSON.stringify(report, null, 2)}${LF}`);
    const mismatched = (report["mismatches"] as unknown[] | undefined)?.length ?? 0;
    process.stdout.write(`${JSON.stringify({ mismatches: mismatched, error: report["error"] ?? null, kernel_changed: report["kernel_changed"] ?? null, categories: report["categories"] ?? {} })}${LF}`);
    return report["error"] ? 2 : report["kernel_changed"] ? 4 : mismatched ? 1 : 0;
  }
  if (!argv.includes("--watch")) {
    let report: Record<string, unknown>;
    try {
      report = round(repo, null, keep).report;
    } catch (error) {
      report = failure(error);
    }
    write(out, report, true);
    const mismatched = (report["mismatches"] as unknown[] | undefined)?.length ?? 0;
    process.stdout.write(`${JSON.stringify({ mismatches: mismatched, skipped: report["skipped"] ?? null, error: report["error"] ?? null, categories: report["categories"] ?? {} })}${LF}`);
    return report["error"] ? 2 : report["skipped"] ? 3 : mismatched ? 1 : 0;
  }
  const interval = Number(option("--interval") ?? "30") * 1000;
  const rounds = Number(option("--rounds") ?? "0");
  // 事后要能证明影子跟完了整段，中间没有空档：latest.json 每轮都带开始时刻、已跑与出错的轮数、最后一轮的时刻
  const watch = { started: new Date().toISOString(), rounds: 0, errors: 0, last_round: "" };
  let streak = 0;
  let done = 0;
  let previous: Previous | null = null;
  let last = "";
  for (;;) {
    const mailbox = join(repo, ".agent", "mailbox");
    let quick = quickPrint(mailbox);
    if (quick !== last) {
      // 一串写入（状态、账本、信）前后常差几毫秒：等指纹连着两次相同再取快照，别在半中间开始
      for (let settle = 0; settle < 10; settle += 1) {
        sleepSync(300);
        const again = quickPrint(mailbox);
        if (again === quick) break;
        quick = again;
      }
      let report: Record<string, unknown>;
      try {
        const result = round(repo, previous, keep);
        report = result.report;
        if (result.next) [previous, last] = [result.next, quick];
        streak = 0;
      } catch (error) {
        // 这一轮不算数：previous 与 last 都不动，下一轮照样重算，把这期间的变化一起比；同一串错误只另存第一份
        report = { ...failure(error), consecutive_errors: (streak += 1) };
        watch.errors += 1;
      }
      watch.rounds += 1;
      watch.last_round = String(report["at"] ?? new Date().toISOString());
      write(out, { ...report, watch }, Boolean((report["mismatches"] as unknown[] | undefined)?.length) || streak === 1);
      done += 1;
      if (rounds && done >= rounds) return 0;
    }
    sleepSync(interval);
  }
}

if (resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) process.exit(main(process.argv.slice(2)));
