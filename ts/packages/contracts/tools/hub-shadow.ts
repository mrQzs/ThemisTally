// ⑤-影子（迁移计划第 ⑤ 步）：Python hub 照常办事，影子把同一份快照交给 python_probe.py 与 ts_probe.ts（Bun），逐字比带标签的
// 结果，攒“TS hub 会做出同样决定”的证据。只读：不拿 hub 的锁、不写信箱，结果写到 <仓库>/.agent/runs/_shadow/。
// 用法（外面套 backup_privilege.py off：与以后经 Start-Process 起的 TS hub 同一种令牌，读不穿别的进程的独占打开）：
//   python ts/packages/contracts/probes/backup_privilege.py off bun ts/packages/contracts/tools/hub-shadow.ts --repo <仓库> --once
//   ……同上，--watch [--interval 30] [--rounds N]（算满 N 轮就停，给契约用）
// 比什么：状态（读出与账本）；每个主任务的只读结论与 guard 的整张表；每封信的读出、解析、往返、形状校验；写给协调人的信单独成批时
// 的内核代办与任务书；账本里每次 route.kernel 的那批信重算的下一步（还要与账本记的一致，partial 时是它的前缀）；已结束回合的审计、
// 半截会话与生效档位。--watch 时只算变了的部分，另比新出现的 letter.rejected：上一份与这一份快照的状态各算一次 guard，对上一个
// 就算一致，都对不上记成“时序”交给人看。
// 探针不开在用的文件：状态与账本复制进临时的快照仓库，信件与事件流由这里经 fs 读出、按原始字节传过去，会话文件按会话号复制进
// 临时目录，用完删掉。结果只写数量、对不上的键（主任务号、信的文件名、回合号）与快照的哈希，不写内容。
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { sleepSync } from "@themis/base/fsutil";
import { type PyValue, loads } from "@themis/base/pyjson";
import {
  COORDINATOR, COORDINATOR_TYPES, KERNEL, KERNEL_TYPES, OWNER, OWNER_TYPES, ROSTER, STAGE_ORDER, STAGE_WORKER, WORKER_TYPES,
} from "@themis/hub/constants";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";

const LF = String.fromCharCode(10);
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

/** 一批请求交给一边的探针：（结果，探针进程的峰值内存，字节；拿不到是 0）。 */
function batchWithPeak(argv: readonly string[], items: readonly Item[]): { results: Item[]; peak: number } {
  const done = spawnSync(argv[0] as string, argv.slice(1), {
    input: JSON.stringify({ op: "batch", items }), encoding: "utf8", maxBuffer: 2 * 1024 * 1024 * 1024, timeout: 1_800_000,
  });
  if (done.status !== 0) throw new Error(`探针退出码 ${done.status}（${argv[0]}）`);
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

  /** 同一批请求交给两边，逐个比带标签的结果；交回 Python 的结果。 */
  run(category: string, keys: readonly string[], items: readonly Item[]): Item[] {
    const start = Date.now();
    const python = batchWithPeak(PYTHON, items);
    const ts = batchWithPeak(TS, items);
    keys.forEach((key, index) => {
      if (JSON.stringify(python.results[index]) !== JSON.stringify(ts.results[index])) this.miss(category, key);
    });
    this.count(category, keys.length, Date.now() - start, python.peak, ts.peak);
    return python.results;
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
  const python = cmp.run("route.kernel", keys, usable.map(({ event }) => ({
    op: "hub.shadow_route", b64s: (event["letters"] as string[]).map((name) => (byName.get(name) as Buffer).toString("base64")),
  })));
  usable.forEach(({ event }, at) => {
    const result = python[at] as { ok?: boolean; value?: Tagged };
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

/** 回合：审计重算、半截会话、claude 的生效档位。会话文件按会话号复制进临时的 USERPROFILE 与快照仓库，两边看同一份字节。 */
function compareTurns(cmp: Comparison, repo: string, snapRepo: string, turns: readonly Turn[]): void {
  const home = mkdtempSync(join(tmpdir(), "themis-shadow-home-"));
  try {
    let items: Item[] = [];
    let keys: string[] = [];
    let size = 0;
    const flush = (): void => {
      if (items.length) cmp.run("回合", keys, items);
      [items, keys, size] = [[], [], 0];
    };
    for (const turn of turns) {
      const spec = ROSTER[turn.agent];
      if (!spec) continue;
      const result = JSON.parse(readFileSync(join(turn.dir, "result.json"), "utf8")) as { workspace?: string | null; session_id?: unknown };
      const lines = readFileSync(join(turn.dir, "stream.jsonl")).toString("utf8").split(LF);
      const fn = spec.adapter === "claude" ? "audit_claude_stream" : "audit_pi_stream";
      const audit = (name: string, ...args: PyValue[]): Item => ({ op: "hub.audit", fn: name, args: args.map((arg) => toTagged(arg)), home });
      items.push(audit(fn, lines, py(spec), result.workspace ?? null, repo));
      keys.push(`${turn.id} 审计`);
      if (typeof result.session_id === "string" && result.session_id) {
        copySessions(turn.agent, spec.adapter, result.session_id, repo, snapRepo, home);
        if (spec.adapter === "claude") {
          items.push(audit("claude_session_effort", result.session_id));
          keys.push(`${turn.id} 生效档位`);
        }
        items.push(audit("session_cut_short", snapRepo, turn.agent, spec.adapter, result.session_id));
        keys.push(`${turn.id} 半截会话`);
      }
      size += turn.size;
      if (size > BATCH_BYTES) flush();
    }
    flush();
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
}

/** 按会话号复制会话文件：claude 的在 ~/.claude/projects 下各目录里的“<号>.jsonl”，pi 的在信箱 sessions/<工人> 下以“_<号>.jsonl”结尾的文件。 */
function copySessions(agent: string, adapter: string, session: string, repo: string, snapRepo: string, home: string): void {
  if (adapter === "claude") {
    const projects = join(homedir(), ".claude", "projects");
    if (!existsSync(projects)) return;
    for (const dir of readdirSync(projects)) {
      const file = join(projects, dir, `${session}.jsonl`);
      if (!existsSync(file)) continue;
      mkdirSync(join(home, ".claude", "projects", dir), { recursive: true });
      writeFileSync(join(home, ".claude", "projects", dir, `${session}.jsonl`), readFileSync(file));
    }
    return;
  }
  const sessions = join(repo, ".agent", "mailbox", "sessions", agent);
  if (!existsSync(sessions)) return;
  for (const name of readdirSync(sessions)) {
    if (!name.endsWith(`_${session}.jsonl`)) continue;
    mkdirSync(join(snapRepo, ".agent", "mailbox", "sessions", agent), { recursive: true });
    writeFileSync(join(snapRepo, ".agent", "mailbox", "sessions", agent, name), readFileSync(join(sessions, name)));
  }
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

function round(repo: string, previous: Previous | null): { report: Record<string, unknown>; next: Previous | null } {
  const { snapshot, tries } = takeSnapshot(repo);
  if (snapshot === null) return { report: { skipped: "快照不稳，跳过", tries }, next: previous };
  const snapRepo = mkdtempSync(join(tmpdir(), "themis-shadow-snap-"));
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
    const fresh = previous ? new Set([...snapshot.letters.keys()].filter((rel) => !previous.snapshot.letters.has(rel))) : undefined;
    compareLetters(cmp, snapshot, fresh);
    compareRoutine(cmp, snapRepo, snapshot, fresh);
    const { events, lines } = ledgerEvents(snapshot.ledger);
    const missing = compareRoutes(cmp, snapshot, events, previous?.ledgerLines ?? 0);
    if (previous) compareRejections(cmp, events, previous.ledgerLines, [previous.snapshot.state, snapshot.state]);
    const turns = endedTurns(repo).filter((turn) => previous?.turns.get(turn.id) !== turn.size);
    compareTurns(cmp, repo, snapRepo, turns);
    const report = {
      at: new Date().toISOString(), state_sha256: snapshot.stateSha, ledger_bytes: snapshot.ledger.length, letters: snapshot.letters.size, tries,
      categories: Object.fromEntries(cmp.counts), shadow_peak_mb: Math.round(process.resourceUsage().maxRSS / 1024), guard_combos: guardCombos, mismatches: cmp.mismatches, route_letters_missing: missing,
    };
    const seen = new Map(previous?.turns ?? []);
    for (const turn of turns) seen.set(turn.id, turn.size);
    return { report, next: { snapshot, ledgerLines: lines, taskHashes: hashes, turns: seen } };
  } finally {
    rmSync(snapRepo, { recursive: true, force: true });
  }
}

function write(out: string, report: Record<string, unknown>, keep: boolean): void {
  mkdirSync(out, { recursive: true });
  const text = `${JSON.stringify(report, null, 2)}${LF}`;
  writeFileSync(join(out, "latest.json"), text);
  if (keep) writeFileSync(join(out, `${String(report["at"] ?? new Date().toISOString()).replace(/[:.]/gu, "-")}.json`), text);
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
  if (!argv.includes("--watch")) {
    const { report } = round(repo, null);
    write(out, report, true);
    const mismatched = (report["mismatches"] as unknown[] | undefined)?.length ?? 0;
    process.stdout.write(`${JSON.stringify({ mismatches: mismatched, skipped: report["skipped"] ?? null, categories: report["categories"] ?? {} })}${LF}`);
    return report["skipped"] ? 3 : mismatched ? 1 : 0;
  }
  const interval = Number(option("--interval") ?? "30") * 1000;
  const rounds = Number(option("--rounds") ?? "0");
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
      const { report, next } = round(repo, previous);
      write(out, report, Boolean((report["mismatches"] as unknown[] | undefined)?.length));
      if (next) [previous, last] = [next, quick];
      done += 1;
      if (rounds && done >= rounds) return 0;
    }
    sleepSync(interval);
  }
}

if (resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) process.exit(main(process.argv.slice(2)));
