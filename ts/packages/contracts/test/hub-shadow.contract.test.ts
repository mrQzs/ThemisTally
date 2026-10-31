// ⑤-影子的契约（迁移计划第 ⑤ 步）：tools/hub-shadow.ts 在一个临时信箱上跑。
//   - --once：状态、主任务（含 guard 整张表的组合数）、提示词（⑤d1：各岗位的 role_prompt、各主任务协调人与不是 idle 的阶段的 turn_prompt）、信件、内核代办、route.kernel（整批与 partial）、回合（没结束的不审）都比到，零差异；
//   - Python 与 TS 真有差异时报得出来：回合事件流里一行嵌套 1500 层的对象（第 10 节的已知差异：Python 读得出，base 的 loads 在
//     1000 层报错、算读不出的行）；账本里 route.kernel 记的下一步被改过，只在“route.kernel 与账本”报一处；
//   - 取快照时 state.json 被改了（THEMIS_SHADOW_PAUSE 让影子在读完之后停住，测试趁机改）：改一次就重取，次次都改就“快照不稳，跳过”；
//   - --watch 两轮：第二轮只重算状态变了的主任务；新出现的 letter.rejected 用上一份与这一份快照各算一次 guard，原因只在上一份上
//     对得上的也算一致，都对不上的记“时序”；某一轮出错只记错误的类型、接着跑，那一轮不算数，下一轮补比；
//   - --watch 开始以后才结束的回合：TS 的审计与 Python 照 run_turn 写下的 result.json 比（审计带交差工具 deliver、事件流里有单独的
//     CR 分行），一致；result.json 被改过的报出来；hub_sha256 是别的内核的只计数、不比；
//   - 影子的输出放在 .agent/runs/_shadow/ 时，status --json、metrics、decisions replay --json 在 Python 与经启动器的 TS 下相同、
//     不提 _shadow（prepare 与 integrate 两处在各自的契约里带着 _shadow 跑）。
// 影子与探针都套 backup_privilege.py off；会话文件从临时的 USERPROFILE 与临时信箱里取，不碰真的家目录。
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { dumps } from "@themis/base/pyjson";
import { COORDINATOR, COORDINATOR_TYPES, KERNEL_TYPES, OWNER, OWNER_TYPES, ROSTER, STAGE_ORDER, STAGE_WORKER, WORKER_TYPES } from "@themis/hub/constants";
import { renderLetter } from "@themis/hub/letters";
import { guard, newTaskState, routineMoves } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { fullAttempt } from "./attempt-fixtures.ts";
import { BUN, REPO, removeDir, runLauncherCli, runPythonCli, scratchDir } from "./harness.ts";
import { LF, newRepo, normalize, put } from "./repo-fixtures.ts";

const CR = String.fromCharCode(13);
const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const PROBES = resolve(REPO, "ts", "packages", "contracts", "probes");
const TOOL = resolve(REPO, "ts", "packages", "contracts", "tools", "hub-shadow.ts");
const BASE = "b".repeat(40);
const AT = "2026-10-31T00:00:00Z";
const ROOT = scratchDir("shadow");
afterAll(() => removeDir(ROOT));

const sha256 = (bytes: Buffer | string): string => createHash("sha256").update(bytes).digest("hex");
const meta = (msgId: string, from: string, to: string, task: string, type: string): Map<string, string> =>
  new Map([["msg-id", msgId], ["from", from], ["to", to], ["task-id", task], ["in-reply-to", "none"], ["type", type]]);
const fields = (extra: Record<string, string> = {}): Map<string, PyValue> =>
  new Map<string, PyValue>(Object.entries({ 摘要: "做完了", 提交: "无", 验证: "无", 偏离: "无", 需协调人决定: "无", 证据: "无", ...extra }));
const line = (value: unknown): string => JSON.stringify(value);
const stateJson = (state: PyDict): string => `${dumps(state, { indent: 2, sortKeys: true, ensureAscii: false })}${LF}`;
/** 每个主任务的 guard 组合数：信件类型 × 收信人（名册、站主、内核、不存在的）× 主任务号、各阶段号、不存在的阶段号、空号。 */
const COMBOS = new Set([...WORKER_TYPES, ...COORDINATOR_TYPES, ...OWNER_TYPES, ...KERNEL_TYPES]).size * (Object.keys(ROSTER).length + 3) * (STAGE_ORDER.length + 3);

interface Fixture {
  readonly repo: string;
  readonly home: string;
  readonly state: PyDict;
  /** 账本里整批的 route.kernel 在第几行；测试追加的事件从第几行开始。 */
  readonly routeLine: number;
  readonly nextLine: number;
}

/**
 * 一个临时信箱：两个主任务；几封信（两封例行交付、站主的任务、坏信头、非 UTF-8、CRLF、带 U+2028）；两次 route.kernel（一次整批，
 * 一次 partial 只记了重算结果的前一步）；三个回合（pi 的门禁端、claude 的规划端、一个还没写 result.json 的）。deep 时再加一个回合，
 * 事件流里有一行嵌套 1500 层的对象。
 */
function fixture(name: string, o: { tamperRoute?: boolean; deep?: boolean } = {}): Fixture {
  const repo = join(ROOT, name);
  const home = join(ROOT, `${name}-home`);
  const t1 = newTaskState("T001", "doc", "文档", BASE, true, AT);
  const t2 = newTaskState("T002", "ui", "界面", BASE, false, AT);
  ((t2.get("stages") as PyDict).get("1-plan") as PyDict).set("status", "assigned");
  const state: PyDict = new Map([["tasks", new Map<string, PyValue>([["T001", t1], ["T002", t2]])]]);
  put(repo, ".agent/mailbox/ledger/state.json", stateJson(state));
  const box = (agent: string, folder: string, file: string, content: string | Uint8Array): void => put(repo, `.agent/mailbox/inbox/${agent}/${folder}/${file}`, content);
  const plan = renderLetter(meta("20261031T000000000001Z-planner-000001", "planner-opus", COORDINATOR, "T002-1-plan", "交付"), fields({ 下游须知: `一${String.fromCharCode(0x2028)}二` }));
  const contract = renderLetter(meta("20261031T000000000007Z-contract-000007", "contract-glm", COORDINATOR, "T002-2-contract", "交付"), fields());
  box(COORDINATOR, "cur", "20261031T000000000001Z-planner-000001.md", plan);
  box(COORDINATOR, "cur", "20261031T000000000007Z-contract-000007.md", contract);
  box(COORDINATOR, "cur", "20261031T000000000002Z-owner-000002.md", renderLetter(meta("20261031T000000000002Z-owner-000002", OWNER, COORDINATOR, "T001", "任务"), fields()));
  box(COORDINATOR, "cur", "20261031T000000000003Z-x-000003.md", "没有信头的信" + LF);
  box(COORDINATOR, "new", "20261031T000000000004Z-x-000004.md", new Uint8Array([0xff, 0xfe, 0x41]));
  box(COORDINATOR, "new", "20261031T000000000005Z-owner-000005.md", renderLetter(meta("20261031T000000000005Z-owner-000005", OWNER, COORDINATOR, "T002", "回复"), fields()).split(LF).join(CR + LF));
  box("planner-opus", "new", "20261031T000000000006Z-womovie-000006.md", renderLetter(meta("20261031T000000000006Z-womovie-000006", COORDINATOR, "planner-opus", "T001-1-plan", "开工"), fields()));
  const moves = (texts: string[]): string[] => routineMoves(texts)[0].map((move) => {
    const suffix = String((move as PyDict).get("suffix"));
    return `${String((move as PyDict).get("type"))} → ${STAGE_WORKER[suffix]}（T002-${suffix}）`;
  });
  const whole = moves([plan]);
  if (o.tamperRoute) whole.push("返工 → gate-sonnet（T002-3-gate-pre）");
  const both = moves([plan, contract]);
  expect(both.length, "partial 那次要有两个下一步").toBeGreaterThan(1);
  const events = [
    line({ at: AT, event: "letter.delivered", msg_id: "20261031T000000000001Z-planner-000001" }),
    line({ at: AT, event: "route.kernel", task: "T002", letters: ["20261031T000000000001Z-planner-000001.md"], moves: whole, partial: false }),
    line({ at: AT, event: "route.kernel", task: "T002", letters: ["20261031T000000000001Z-planner-000001.md", "20261031T000000000007Z-contract-000007.md"], moves: both.slice(0, 1), partial: true }),
    "坏行",
  ];
  put(repo, ".agent/mailbox/ledger/events.jsonl", events.join(LF) + LF);
  const gate = ".agent/mailbox/turns/gate-sonnet/20261031T000000000000Z-aaaa";
  put(repo, `${gate}/stream.jsonl`, [
    line({ type: "tool_execution_start", toolName: "read", toolCallId: "c1", args: { path: join(repo, "src", "a.ts") } }),
    line({ type: "message_end", message: { role: "assistant", provider: "cc-switch-zhipu-glm", model: "glm-5.3", stopReason: "stop", content: [{ type: "text", text: "完" }] } }),
    line({ type: "agent_end" }),
  ].join(LF));
  put(repo, `${gate}/result.json`, line({ workspace: join(ROOT, "ws"), session_id: "p-sid-1" }));
  put(repo, ".agent/mailbox/sessions/gate-sonnet/20261031_p-sid-1.jsonl", line({ type: "message", message: { role: "assistant", stopReason: "toolUse" } }) + LF);
  put(repo, ".agent/mailbox/turns/gate-sonnet/20261031T000000000001Z-cccc/stream.jsonl", line({ type: "agent_end" })); // 还在跑：没有 result.json，不审
  const planner = ".agent/mailbox/turns/planner-opus/20261031T000000000000Z-bbbb";
  put(repo, `${planner}/stream.jsonl`, [
    line({ type: "system", subtype: "init", tools: ["Read", "Grep", "Glob", "LS"], model: "claude-opus-5-5", session_id: "c-sid-1" }),
    line({ type: "result", result: "ok" }),
  ].join(LF));
  put(repo, `${planner}/result.json`, line({ workspace: null, session_id: "c-sid-1" }));
  put(home, ".claude/projects/C--x/c-sid-1.jsonl", [line({ type: "assistant", effort: "max" }), ""].join(LF));
  if (o.deep) {
    const deep = ".agent/mailbox/turns/gate-sonnet/20261031T000000000002Z-dddd";
    put(repo, `${deep}/stream.jsonl`, `{"type":"x","deep":${"[".repeat(1500)}0${"]".repeat(1500)}}${LF}${line({ type: "agent_end" })}`);
    put(repo, `${deep}/result.json`, line({ workspace: null }));
  }
  return { repo, home, state, routeLine: 2, nextLine: 5 };
}

/** 照 kit_hub 的 run_turn 写一个 pi 回合的 result.json：审计用名册的工具表加 deliver、事件流按通用换行读，字段照 summary 的写法。 */
const RUN_TURN_RECORD = [
  "import sys",
  "from pathlib import Path",
  "sys.path.insert(0, sys.argv[1])",
  "import kit_hub as kh",
  "turn, agent, workspace, repo = Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), Path(sys.argv[5])",
  "spec = kh.ROSTER[agent]",
  "tools = list(spec['tools']) + [kh.DELIVER_TOOL]",
  "audit = kh.audit_pi_stream(kh.jsonl_lines(kh.read_text(turn / 'stream.jsonl')), dict(spec, tools=tools), workspace, repo)",
  "kh.pd.write_json(turn / 'result.json', {",
  "    'workspace': str(workspace), 'hub_sha256': kh.HUB_SHA256, 'models': audit.get('models'),",
  "    'effort_effective': ','.join(audit.get('effective_levels') or []) or None,",
  "    'tool_calls': audit['tool_calls'], 'violations': audit['violations'], 'usage': audit.get('usage'), 'terminal': audit.get('terminal'),",
  "    'warnings': audit.get('warnings') or [], 'deliver_refusals': len(audit.get('deliver_refusals') or []),",
  "    'deliver_refusal_chars': sum(audit.get('deliver_refusals') or []),",
  "    'thinking_chars': audit.get('thinking_chars'), 'thinking_tokens': audit.get('thinking_tokens'),",
  "}, exclusive=True)",
].join(LF);

/** 在 gate-sonnet 下放一个已结束的回合：事件流调用 deliver，前两个事件之间用单独的 CR 分行；result.json 由 Python 照 run_turn 写下。 */
function recordedTurn(fx: Fixture, id: string): string {
  const dir = `.agent/mailbox/turns/gate-sonnet/${id}`;
  put(fx.repo, `${dir}/stream.jsonl`, [
    line({ type: "tool_execution_start", toolName: "deliver", toolCallId: "d1", args: { 摘要: "做完了" } }) + CR
      + line({ type: "message_end", message: { role: "assistant", provider: "cc-switch-zhipu-glm", model: "glm-5.3", stopReason: "stop", content: [{ type: "text", text: "完" }] } }),
    line({ type: "agent_end" }),
  ].join(LF));
  const done = spawnSync(PYTHON, ["-c", RUN_TURN_RECORD, join(REPO, "scripts"), join(fx.repo, dir), "gate-sonnet", join(ROOT, "ws"), fx.repo], {
    encoding: "utf8", env: { ...process.env, PYTHONUTF8: "1" },
  });
  expect(done.status, done.stderr).toBe(0);
  return join(fx.repo, dir, "result.json");
}

/** 套 backup_privilege.py off 起影子，交回退出码与 latest.json。 */
function runShadow(fx: Fixture, args: readonly string[], env: Record<string, string> = {}): { status: number; report: Record<string, unknown> } {
  const out = join(fx.repo, "shadow-out");
  const done = spawnSync(PYTHON, [join(PROBES, "backup_privilege.py"), "off", BUN, TOOL, "--repo", fx.repo, "--out", out, ...args], {
    encoding: "utf8", env: { ...process.env, USERPROFILE: fx.home, ...env }, timeout: 600_000,
  });
  expect(existsSync(join(out, "latest.json")), done.stderr).toBe(true);
  return { status: done.status ?? -1, report: JSON.parse(readFileSync(join(out, "latest.json"), "utf8")) as Record<string, unknown> };
}

const compared = (report: Record<string, unknown>): Record<string, number> =>
  Object.fromEntries(Object.entries(report["categories"] as Record<string, { compared: number }>).map(([name, entry]) => [name, entry.compared]));

describe("⑤-影子：静态重放", () => {
  it("--once：各类都比到（guard 的整张表、两次 route.kernel、没结束的回合不审），零差异", () => {
    const fx = fixture("clean");
    const { status, report } = runShadow(fx, ["--once"]);
    expect(report["mismatches"]).toEqual([]);
    expect(status).toBe(0);
    expect(compared(report)).toEqual({ 状态: 1, 主任务: 3, 提示词: 8, 信件: 7, 代办: 6, "route.kernel": 2, "route.kernel 与账本": 2, 回合: 5 });
    expect(report["guard_combos"]).toBe(3 * COMBOS);
    expect(report["state_sha256"]).toBe(sha256(readFileSync(join(fx.repo, ".agent", "mailbox", "ledger", "state.json"))));
  });

  it("两边真有差异时报得出来：嵌套 1500 层的那一行（第 10 节的已知差异）只在那个回合的审计上报一处", () => {
    const fx = fixture("deep", { deep: true });
    const { status, report } = runShadow(fx, ["--once"]);
    expect(status).toBe(1);
    expect(report["mismatches"]).toEqual([{ category: "回合", key: "gate-sonnet/20261031T000000000002Z-dddd 审计", state_sha256: report["state_sha256"] }]);
  });

  it("账本里 route.kernel 记的下一步被改过：只在“route.kernel 与账本”报一处，带上快照的哈希", () => {
    const fx = fixture("tampered", { tamperRoute: true });
    const { status, report } = runShadow(fx, ["--once"]);
    expect(status).toBe(1);
    expect(report["mismatches"]).toEqual([{ category: "route.kernel 与账本", key: `账本第 ${fx.routeLine} 行`, state_sha256: report["state_sha256"] }]);
  });
});

/** 起影子（不等），交回等它退出的 Promise。 */
function startShadow(fx: Fixture, args: readonly string[], env: Record<string, string>): Promise<number> {
  const child = spawn(PYTHON, [join(PROBES, "backup_privilege.py"), "off", BUN, TOOL, "--repo", fx.repo, "--out", join(fx.repo, "shadow-out"), ...args], {
    env: { ...process.env, USERPROFILE: fx.home, ...env }, stdio: "ignore",
  });
  return new Promise((done) => child.on("close", (code) => done(code ?? -1)));
}

async function waitFor(path: string): Promise<void> {
  for (let tries = 0; tries < 3000 && !existsSync(path); tries += 1) await new Promise((wake) => setTimeout(wake, 20));
  expect(existsSync(path), path).toBe(true);
}

describe("⑤-影子：快照前后要一致", () => {
  // 每次都在末尾多加几个空白：哈希一定变，JSON 照样读得出
  const touch = (fx: Fixture, times: number): void => {
    const path = join(fx.repo, ".agent", "mailbox", "ledger", "state.json");
    writeFileSync(path, readFileSync(path, "utf8") + " ".repeat(times));
  };

  it("读完之后 state.json 被改了一次：重取，第二次对上", async () => {
    const fx = fixture("pause-once");
    const pause = join(ROOT, "pause-once-marks");
    mkdirSync(pause, { recursive: true });
    const exited = startShadow(fx, ["--once"], { THEMIS_SHADOW_PAUSE: pause });
    await waitFor(join(pause, "paused-1"));
    touch(fx, 1);
    writeFileSync(join(pause, "go-1"), "");
    await waitFor(join(pause, "paused-2"));
    writeFileSync(join(pause, "go-2"), "");
    expect(await exited).toBe(0);
    const report = JSON.parse(readFileSync(join(fx.repo, "shadow-out", "latest.json"), "utf8")) as Record<string, unknown>;
    expect([report["tries"], report["mismatches"]]).toEqual([2, []]);
  });

  it("次次都被改：记“快照不稳，跳过”，不拿撕裂的快照去比", async () => {
    const fx = fixture("pause-always");
    const pause = join(ROOT, "pause-always-marks");
    mkdirSync(pause, { recursive: true });
    const exited = startShadow(fx, ["--once"], { THEMIS_SHADOW_PAUSE: pause });
    for (let attempt = 1; attempt <= 5; attempt += 1) {
      await waitFor(join(pause, `paused-${attempt}`));
      touch(fx, attempt);
      writeFileSync(join(pause, `go-${attempt}`), "");
    }
    expect(await exited).toBe(3);
    const report = JSON.parse(readFileSync(join(fx.repo, "shadow-out", "latest.json"), "utf8")) as Record<string, unknown>;
    expect(report).toEqual({ skipped: "快照不稳，跳过", tries: 5 });
  }, 120_000);
});

describe("⑤-影子：--watch", () => {
  it("第二轮只重算状态变了的主任务；拒信的原因只在上一份快照上对得上也算一致，对不上的记“时序”", async () => {
    const fx = fixture("watch");
    const out = join(fx.repo, "shadow-out");
    const exited = startShadow(fx, ["--watch", "--interval", "1", "--rounds", "2"], {});
    await waitFor(join(out, "latest.json"));
    const before = (fx.state.get("tasks") as PyDict).get("T002") as PyDict;
    const rejectMeta = new Map([["from", COORDINATOR], ["to", "planner-opus"], ["task-id", "T002-1-plan"], ["type", "开工"]]);
    const reason = guard(before, rejectMeta);
    expect(reason).not.toBeNull();
    // 第二轮之前 T002 的规划阶段又变了：同一封信在新状态上的拒收原因不同，只有上一份快照对得上
    const after = structuredClone(before);
    ((after.get("stages") as PyDict).get("1-plan") as PyDict).set("status", "delivered");
    expect(guard(after, rejectMeta)).not.toBe(reason);
    const changed: PyDict = new Map([["tasks", new Map([...(fx.state.get("tasks") as PyDict)].map(([name, ts]) => [name, name === "T002" ? after : ts]))]]);
    const ledger = join(fx.repo, ".agent", "mailbox", "ledger", "events.jsonl");
    const rejected = (why: string): string => line({ at: AT, event: "letter.rejected", sender: COORDINATOR, to: "planner-opus", type: "开工", task_id: "T002-1-plan", reason: why });
    writeFileSync(join(fx.repo, ".agent", "mailbox", "ledger", "state.json"), stateJson(changed));
    writeFileSync(ledger, readFileSync(ledger, "utf8") + rejected(String(reason)) + LF + rejected("编出来的原因") + LF);
    expect(await exited).toBe(0);
    const report = JSON.parse(readFileSync(join(out, "latest.json"), "utf8")) as Record<string, unknown>;
    const categories = report["categories"] as Record<string, { compared: number; mismatched: number }>;
    expect(categories["主任务"]?.compared, "只重算 T002 与不存在的主任务").toBe(2);
    expect(categories["时序"]).toMatchObject({ compared: 2, mismatched: 1 });
    expect(report["mismatches"]).toEqual([{ category: "时序", key: `账本第 ${fx.nextLine + 1} 行`, state_sha256: report["state_sha256"] }]);
  });

  it("watch 开始以后才结束的回合：TS 的审计与 hub 写下的 result.json 一致；被改过的报出来，别的内核写下的只计数", async () => {
    const fx = fixture("watch-record");
    const out = join(fx.repo, "shadow-out");
    const exited = startShadow(fx, ["--watch", "--interval", "1", "--rounds", "2"], {});
    await waitFor(join(out, "latest.json"));
    recordedTurn(fx, "20261031T000000000004Z-ffff");
    const tampered = recordedTurn(fx, "20261031T000000000005Z-gggg");
    const rewrite = (path: string, change: (record: Record<string, unknown>) => void): void => {
      const record = JSON.parse(readFileSync(path, "utf8")) as Record<string, unknown>;
      change(record);
      writeFileSync(path, JSON.stringify(record));
    };
    rewrite(tampered, (record) => (record["violations"] as string[]).push("编出来的违规"));
    rewrite(recordedTurn(fx, "20261031T000000000006Z-hhhh"), (record) => Object.assign(record, { hub_sha256: "0".repeat(64), violations: ["旧内核写的"] }));
    // pi 回合的会话文件比 result.json 新（下一回合续接了），生效档位被改过：pi 的档位来自事件流，照样算不一致，不算时序
    rewrite(recordedTurn(fx, "20261031T000000000007Z-iiii"), (record) => Object.assign(record, { session_id: "p-sid-9", effort_effective: "high" }));
    put(fx.repo, ".agent/mailbox/sessions/gate-sonnet/20261031_p-sid-9.jsonl", line({ type: "message", message: { role: "assistant", stopReason: "stop" } }) + LF);
    // 回合不在每轮先看的指纹里：照 hub 的样子在账本记一笔，第二轮才开始
    const ledger = join(fx.repo, ".agent", "mailbox", "ledger", "events.jsonl");
    writeFileSync(ledger, readFileSync(ledger, "utf8") + line({ at: AT, event: "turn.finished", turn_id: "20261031T000000000006Z-hhhh" }) + LF);
    expect(await exited).toBe(0);
    const report = JSON.parse(readFileSync(join(out, "latest.json"), "utf8")) as Record<string, unknown>;
    expect((report["categories"] as Record<string, unknown>)["回合与 result.json"]).toMatchObject({ compared: 3, mismatched: 2 });
    expect(report["result_json_other_kernel"]).toBe(1);
    expect(report["mismatches"]).toEqual([
      { category: "回合与 result.json", key: "gate-sonnet/20261031T000000000005Z-gggg：violations", state_sha256: report["state_sha256"] },
      { category: "回合与 result.json", key: "gate-sonnet/20261031T000000000007Z-iiii：effort_effective", state_sha256: report["state_sha256"] },
    ]);
  }, 120_000);

  it("某一轮出错（回合的 result.json 只写了一半）：只记错误的类型，接着跑；那一轮不算数，下一轮整份补比", async () => {
    const fx = fixture("watch-error");
    const half = ".agent/mailbox/turns/gate-sonnet/20261031T000000000003Z-eeee";
    put(fx.repo, `${half}/stream.jsonl`, line({ type: "agent_end" }));
    put(fx.repo, `${half}/result.json`, "{");
    const out = join(fx.repo, "shadow-out");
    const exited = startShadow(fx, ["--watch", "--interval", "3", "--rounds", "2"], {});
    await waitFor(join(out, "latest.json"));
    put(fx.repo, `${half}/result.json`, line({ workspace: null }));
    expect(await exited).toBe(0);
    const report = JSON.parse(readFileSync(join(out, "latest.json"), "utf8")) as Record<string, unknown>;
    expect([report["error"], report["mismatches"]]).toEqual([undefined, []]);
    expect(report["watch"]).toMatchObject({ rounds: 2, errors: 1, last_round: report["at"] });
    expect(compared(report), "第二轮从头比：三个主任务都算，补全的回合也审了").toMatchObject({ 主任务: 3, 回合: 6 });
    const kept = readdirSync(out).filter((name) => name !== "latest.json");
    expect(kept.length, kept.join(" ")).toBe(1);
    expect(JSON.parse(readFileSync(join(out, kept[0] as string), "utf8"))).toMatchObject({
      error: { type: "SyntaxError", code: null }, consecutive_errors: 1, watch: { rounds: 1, errors: 1 },
    });
  }, 120_000);
});

describe("⑤-影子：_shadow 被调度器各处跳过", () => {
  // 这三条是只读命令：生产上经启动器转交 TS（选择文件的 readonly），对照的就是这条路与 Python 直跑
  it("status --json、metrics、decisions replay --json：Python 与经启动器的 TS 输出相同，不提 _shadow", () => {
    for (const argv of [["status", "--json"], ["metrics"], ["decisions", "replay", "--json"]]) {
      const shown = ([["python", runPythonCli], ["launcher", runLauncherCli]] as const).map(([runner, run]) => {
        const { repo, head } = newRepo(`shadow-skip-${runner}`);
        const paths = { "<REPO>": repo, ...fullAttempt(repo, head, runner) };
        put(repo, ".agent/runs/_shadow/latest.json", `{"mismatches": []}${LF}`);
        put(repo, ".agent/runs/_shadow/2026-10-31T00-00-00-000Z.json", `{"mismatches": []}${LF}`);
        const result = run(["--repo", repo, ...argv], repo);
        return { status: result.status, stdout: normalize(result.stdout.toString("utf8"), paths), stderr: normalize(result.stderr.toString("utf8"), paths) };
      });
      expect(shown[1], argv.join(" ")).toEqual(shown[0]);
      expect(shown[0]?.status, JSON.stringify(shown[0])).toBe(0);
      expect(JSON.stringify(shown[0]), argv.join(" ")).not.toContain("_shadow");
    }
  });
});
