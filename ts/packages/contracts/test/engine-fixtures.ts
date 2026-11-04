// 第 ⑤i 片手写场景共用的辅助（从 hub-engine-scenes 挪出来，⑤i2 的场景文件也引）：临时仓库上摆信箱与 state.json、造回合、取调用之后的状态。
// 不写转义序列。
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { COORDINATOR, FIELDS } from "@themis/hub/constants";
import { renderLetter } from "@themis/hub/letters";
import { canonicalState } from "@themis/hub/mailbox";
import { newTaskState } from "@themis/hub/taskstate";
import { toTagged } from "../src/tagged.ts";
import { AT, LF, PIN, type Scene, flow, py, scene, text, written } from "./flow-fixtures.ts";
import { put } from "./repo-fixtures.ts";

export const lines = (...items: string[]): string => [...items, ""].join(LF);
export const GATE = "tests/test_gate_t001_baseline.py";
export const BASE_FILES = { "src/doc.py": lines("def title():", "    return 'old'"), [GATE]: lines("def test_title():", "    assert False") };
export const BOX = ".agent/mailbox";
export const STATE = `0/${BOX}/ledger/state.json`;
export const SECONDS = Math.floor(PIN / 1_000_000);

/** 信的各栏：缺省都是“无”，摘要另给。 */
export const fields = (extra: Record<string, string> = {}): Map<string, PyValue> =>
  new Map<string, PyValue>([...FIELDS.map((key) => [key, "无"] as const), ["摘要", "开工"], ...Object.entries(extra)]);

/** 在 agent 的 new（或 box 给的 cur）里放一封信，交回仓库里的路径。extra 是另加的栏（审计端的“结论”之类）。 */
export function letter(repo: string, agent: string, msgId: string, from: string, taskId: string, kind: string, box = "new",
  extra: Record<string, string> = {}): string {
  const meta = new Map([["msg-id", msgId], ["from", from], ["to", agent], ["task-id", taskId], ["in-reply-to", "none"], ["type", kind]]);
  const rel = `${BOX}/inbox/${agent}/${box}/${msgId}.md`;
  put(repo, rel, renderLetter(meta, fields(extra)));
  return join(repo, ...rel.split("/"));
}

/** T001 的状态：一个阶段停在 assigned（开工），其余缺省。 */
export function taskState(head: string, suffix: string, extra: Record<string, unknown> = {}): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", head, true, AT);
  (ts.get("stages") as PyDict).set(suffix, py({ status: "assigned", assigned_at: AT, kind: "开工" }));
  for (const [key, value] of Object.entries(extra)) ts.set(key, py(value));
  return ts;
}

/** 摆好信箱的场景：state.json 写进去，一封开工信放进 agent 的 new；交回场景、state 与信的路径。 */
export function mailboxScene(agent: string, taskId: string, build: (head: string) => Map<string, PyValue>, more: (repo: string) => void = () => undefined) {
  const box: { state: PyValue; path: string } = { state: null, path: "" };
  const sc = scene(BASE_FILES, (repo, _wt, head) => {
    const state = new Map<string, PyValue>([["tasks", build(head)]]);
    put(repo, `${BOX}/ledger/state.json`, canonicalState(state));
    box.path = letter(repo, agent, "20261101T000000000000Z-coordinator-000000", COORDINATOR, taskId, "开工");
    box.state = state;
    more(repo);
  });
  return { sc, state: box.state, path: box.path };
}

/** runner 交回的一个回合（FakeRunner 的形状）。 */
export function turn(id: string, output: unknown, extra: Record<string, unknown> = {}): unknown {
  return {
    value: toTagged(py({
      turn_id: id, turn_dir: `turns/${id}`, output, retry_of: null, violations: [], api_error: null, timed_out: false, rate_limited_until: null,
      output_error: output === null ? "没有代码块" : null, ...extra,
    })),
  };
}
export const planned = (report: string): unknown => ({
  letter: { type: "交付", in_reply_to: "m", 摘要: "拆成 3 步", 提交: "无", 验证: "读了文档", 偏离: "无", 需协调人决定: "无", 下游须知: "无", 证据: "report.md" },
  report, state: "交付", external_facts: [],
});
export const value = (item: unknown): unknown => ({ value: toTagged(py(item)) });

/** 调用之后的 state.json（Python 那边写下的），按主任务、阶段取。 */
export const stateAfter = (state: Record<string, unknown> | undefined): Record<string, Record<string, unknown>> =>
  (JSON.parse(text(state, STATE)) as { tasks: Record<string, Record<string, unknown>> }).tasks;
export const lettersTo = (state: Record<string, unknown> | undefined, agent: string): string[] =>
  Object.keys(written(state)).filter((key) => key.startsWith(`0/${BOX}/inbox/${agent}/new/`)).map((key) => text(state, key));
export const events = (state: Record<string, unknown> | undefined): Record<string, unknown>[] =>
  Buffer.from(String(state?.["ledger"]), "base64").toString("utf8").split(LF).filter(Boolean).map((line) => JSON.parse(line) as Record<string, unknown>);
export const runnerCalls = (state: Record<string, unknown> | undefined): Record<string, unknown>[] =>
  (state?.["scripted_calls"] as Record<string, unknown>[]).filter((call) => call["fn"] === "runner");

export type Stages = Record<string, Record<string, unknown>>;
export const stagesAfter = (state: Record<string, unknown> | undefined): Stages => stateAfter(state)["T001"]?.["stages"] as Stages;
export const stageOf = (ts: PyDict, suffix: string): PyDict => (ts.get("stages") as PyDict).get(suffix) as PyDict;
export const setStage = (ts: PyDict, suffix: string, stage: PyValue): void => void (ts.get("stages") as PyDict).set(suffix, stage);
export const failure = (state: Record<string, unknown> | undefined): unknown[] => {
  const result = state?.["result"] as Record<string, unknown>;
  return [result["error"], result["message"]];
};
/** 执行端交回的信（run_exec 照剧本交回的 fields）。 */
export const ran = (verify: string): Record<string, string> => ({ 摘要: "执行端跑完", 提交: "无", 验证: verify, 偏离: "无", 需协调人决定: "无", 证据: "attempt-001" });

/** 摆好信箱：state.json 里只有 build 建的 T001，kinds 每样一封信依次放进 agent 的 new；交回场景、state 与各封信的路径。 */
export function lettersScene(agent: string, taskId: string, kinds: readonly string[], build: (head: string) => PyDict,
  more: (repo: string, wt: string) => void = () => undefined) {
  const box: { state: PyValue; paths: string[] } = { state: null, paths: [] };
  const sc = scene(BASE_FILES, (repo, wt, head) => {
    const state = new Map<string, PyValue>([["tasks", new Map([["T001", build(head)]])]]);
    put(repo, `${BOX}/ledger/state.json`, canonicalState(state));
    box.paths = kinds.map((kind, index) => letter(repo, agent, `20261101T000000000000Z-coordinator-00000${index}`, COORDINATOR, taskId, kind));
    box.state = state;
    more(repo, wt);
  });
  return { sc, state: box.state, paths: box.paths };
}

/** 直接调 Engine 方法的场景：state.json 里只有 build 建的 T001。 */
export function stateScene(build: (head: string, repo: string) => PyDict): Scene {
  return scene(BASE_FILES, (repo, _wt, head) => put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map([["tasks", new Map([["T001", build(head, repo)]])]]))));
}

/** 规划端的一次 worker_job：剧本给回合，ensure_worktree 交回场景的 worktree，worktree_root 每建一次输入目录交回一次。 */
export function planJob(sc: ReturnType<typeof lettersScene>, runner: unknown[], roots: string, inputs = 1) {
  return {
    ...flow("Engine.worker_job", sc.sc, [null, sc.state, "planner-opus", sc.paths]),
    scripted: { runner, ensure_worktree: [value(sc.sc.wt)], worktree_root: Array.from({ length: inputs }, () => value(roots)) },
  };
}
export const planned1 = (head: string): PyDict => taskState(head, "1-plan");

// -- ⑤i2：回合出意外那封信的比法 ---------------------------------------------------------------------------------------------------------

const SHA_MARK = '"sha256": "';

/** 内核发给站主的“阻塞”信，摘要以“<agent> 的回合出了意外”开头（report_step_error 写的）。只按这几样认，不按别的特征。 */
function crashLetter(text: string): boolean {
  const lines = text.split(LF);
  const end = lines.indexOf("---", 1);
  if (lines[0] !== "---" || end < 0) return false;
  const header = new Map(lines.slice(1, end).map((line) => {
    const at = line.indexOf(": ");
    return at < 0 ? [line, ""] : [line.slice(0, at), line.slice(at + 2)];
  }));
  if (header.get("from") !== "内核" || header.get("to") !== "站主" || header.get("type") !== "阻塞") return false;
  const summary = lines.find((line) => line.startsWith("摘要: "))?.slice("摘要: ".length) ?? "";
  const agent = summary.split(" ")[0] ?? "";
  return agent !== "" && summary.startsWith(`${agent} 的回合出了意外`);
}

/** “偏离”只留最后一行（续行以两个空格开头），开头的“kit_hub.”去掉：用例 import kit_hub，生产上 kit_hub 当脚本跑（__main__）。 */
function lastLineOnly(text: string): string {
  const lines = text.split(LF);
  const start = lines.findIndex((line) => line.startsWith("偏离: "));
  let end = start + 1;
  while (end < lines.length && (lines[end] as string).startsWith("  ")) end += 1;
  let last = end - 1 > start ? (lines[end - 1] as string).slice(2) : (lines[start] as string).slice("偏离: ".length);
  if (last.startsWith("kit_hub.")) last = last.slice("kit_hub.".length);
  return [...lines.slice(0, start), `偏离: ${last}`, ...lines.slice(end)].join(LF);
}

/** 账本里这几封信的 letter.delivered 事件，sha256 换成占位；别的字节不动。 */
function withoutSha(text: string, msgIds: readonly string[]): string {
  return text.split(LF).map((line) => {
    if (!line.includes('"event": "letter.delivered"') || !line.includes(SHA_MARK) || !msgIds.some((id) => line.includes(`"msg_id": "${id}"`))) return line;
    const start = line.indexOf(SHA_MARK) + SHA_MARK.length;
    return `${line.slice(0, start)}<回合出了意外的信>${line.slice(line.indexOf('"', start))}`;
  }).join(LF);
}

/**
 * ⑤i2：report_step_error 那封信的比法（⑤i 设计稿第 7 节；themistally-04 定的四个条件）。三份输出都过这一个函数：这封信的“偏离”只比最后一行，
 * 账本里它的 sha256 换成占位，改写了哪些 msg_id 记进 crash_letters 一起比（封数、msg_id 不同就算不同）。其余照旧逐字比：step.error 的 error、
 * 信里的“验证”、fail_stage 写的 note 都不改写。
 */
export function crashNormalized(state: Record<string, unknown>): Record<string, unknown> {
  const files = state["files"] as { write?: Record<string, string> } | undefined;
  const decode = (data: string): string => Buffer.from(data, "base64").toString("utf8");
  const encode = (data: string): string => Buffer.from(data, "utf8").toString("base64");
  const write = { ...(files?.write ?? {}) };
  const crashed: string[] = [];
  for (const [key, data] of Object.entries(write)) {
    if (!key.includes("/inbox/") || !key.endsWith(".md") || !crashLetter(decode(data))) continue;
    write[key] = encode(lastLineOnly(decode(data)));
    crashed.push(key.slice(key.lastIndexOf("/") + 1, -".md".length));
  }
  if (crashed.length === 0) return state;
  for (const key of Object.keys(write)) {
    if (key.endsWith("/ledger/events.jsonl")) write[key] = encode(withoutSha(decode(write[key] as string), crashed));
  }
  const ledger = typeof state["ledger"] === "string" && state["ledger"] ? encode(withoutSha(decode(state["ledger"]), crashed)) : state["ledger"];
  return { ...state, files: { ...files, write }, ledger, crash_letters: crashed.sort() };
}
