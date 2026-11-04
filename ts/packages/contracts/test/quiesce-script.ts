// 第 ⑤i2 片“跑到静止”的初始信箱与剧本（⑤i 设计稿第 5 节）：TS 一侧按种子生成一次，写成 JSON 交给三边（剧本只在这里生成，两边探针只照着用）。
// - 初始信箱：T001 已经走到结项，exec-step 的新信里有一封“通过”；T002 依赖 T001、规划已交付。第一步就是 land：handle_pass 结项、放行 T002，
//   内核写信叫协调人开工合同端；之后协调人与各工人的回合照剧本。
// - 回合按 agent 分开（"runner:<agent>"）：协调人从“开工下一步、返工、发错收件人、不附 brief、输出作废、什么都不发”里抽；工人从“合格交付、
//   违规、格式错、超时、限流、接口报错、阻塞信”里抽。限流的解除时刻落在 80 步之内（基准加不到 80 秒），到点放回那条路也走得到。
// - verify_delivery、run_exec、run_jev、finalize、rehearse_landing、apply_candidate、seed_whitebox 等照剧本交回；对 ts 的改动写成键路径加新值
//   （ts_set），两边只照着套用，不各写分支。
// 剧本只求两边走同一条路，不求走得通：用完了、对不上都在 step 里报错（写阻塞信给站主），两边一样。不写转义序列。
import { join } from "node:path";
import type { PyDict } from "@themis/base/pyjson";
import { COORDINATOR, OWNER } from "@themis/hub/constants";
import { Hub, canonicalState } from "@themis/hub/mailbox";
import { newTaskState } from "@themis/hub/taskstate";
import { toTagged } from "../src/tagged.ts";
import { AT, PIN, type Scene, flow, py, scene } from "./flow-fixtures.ts";
import { put } from "./repo-fixtures.ts";
import { BASE_FILES, BOX, SECONDS, letter, lines, turn, value } from "./engine-fixtures.ts";

/** mulberry32：种子相同，序列相同。 */
export function prng(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = Math.imul(state ^ (state >>> 15), state | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

const WORKERS = ["planner-opus", "contract-glm", "gate-sonnet", "audit-sonnet"];
const T002_STAGES: readonly (readonly [string, string])[] = [["2-contract", "contract-glm"], ["3-gate-pre", "gate-sonnet"], ["4-audit-pre", "audit-sonnet"],
  ["1-plan", "planner-opus"]];
const DONE = ["1-plan", "2-contract", "3-gate-pre", "3j-jev", "4-audit-pre", "5-exec", "6-gate-post", "6j-jev", "7-audit-post"];

/** 初始信箱：T001 走到结项、有一封给 exec-step 的“通过”；T002 依赖 T001、规划已交付。 */
export function quiesceScene(): Scene {
  return scene(BASE_FILES, (repo, _wt, head) => {
    new Hub(repo).ensure();
    const t001 = newTaskState("T001", "doc", "改文档", head, true, AT);
    for (const suffix of DONE) (t001.get("stages") as PyDict).set(suffix, py({ status: "delivered", delivered_at: AT }));
    t001.set("exec", py({ run_dir: join(repo, ".agent", "runs", "t001-doc", "attempt-001"), check_ok: true }));
    const t002 = newTaskState("T002", "next", "下一片", head, true, AT);
    t002.set("after", ["T001"]);
    (t002.get("stages") as PyDict).set("1-plan", py({ status: "delivered", delivered_at: AT }));
    put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map([["tasks", new Map([["T001", t001], ["T002", t002]])]])));
    letter(repo, "exec-step", "20261101T000000000000Z-coordinator-000000", COORDINATOR, "T001-5-exec", "通过");
    letter(repo, COORDINATOR, "20261101T000000000000Z-owner-000000", OWNER, "T002", "回复");
  });
}

const choose = <T>(rand: () => number, items: readonly T[]): T => items[Math.floor(rand() * items.length)] as T;

/**
 * 协调人的一个回合。“开工下一步”照阶段次序推进（cursor 从合同端起，每发一次往后挪），其余几种从全部阶段里随便挑：流程才走得下去，
 * 工人的回合、内核代办与扣信都走得到。
 */
function coordinatorTurn(rand: () => number, id: string, cursor: { at: number }): unknown {
  const roll = rand();
  const next = roll < 0.45;
  const [suffix, worker] = next ? T002_STAGES[Math.min(cursor.at, T002_STAGES.length - 1)] as readonly [string, string] : choose(rand, T002_STAGES);
  const letterOf = (kind: string, to: string, brief: boolean) => ({
    to, type: kind, task_id: `T002-${suffix}`, in_reply_to: "none", 摘要: `${kind} ${suffix}`, 提交: "无", 验证: "无", 偏离: "无", 需协调人决定: "无", 证据: "无",
    ...(brief ? { brief: lines("# 任务书", `做 ${suffix}`) } : {}),
  });
  if (next) {
    cursor.at += 1;
    return turn(id, { letters: [letterOf("开工", worker, true)], state: "推进" });
  }
  if (roll < 0.6) return turn(id, { letters: [letterOf("返工", worker, true)] });
  if (roll < 0.7) return turn(id, { letters: [letterOf("开工", worker === "planner-opus" ? "gate-sonnet" : "planner-opus", true)] }); // 发错收件人
  if (roll < 0.8) return turn(id, { letters: [letterOf("开工", worker, false)] }); // 不附 brief
  if (roll < 0.88) return turn(id, null, { violations: ["改了工作目录外的文件"] });
  return turn(id, { letters: [] });
}

/** 工人的一个回合：合格交付占四成多，其余是违规、格式错、超时、限流（80 步之内解除）、接口报错、阻塞信。 */
function workerTurn(rand: () => number, agent: string, id: string): unknown {
  const letterOf = (kind: string) => ({
    letter: { type: kind, in_reply_to: "m", 摘要: `${agent} ${kind}`, 提交: "无", 验证: "跑了检查", 偏离: "无", 需协调人决定: "无", 证据: "report.md",
      ...(agent === "audit-sonnet" ? { 结论: "通过" } : {}) },
    report: "# 报告", state: kind, external_facts: [],
  });
  const roll = rand();
  if (roll < 0.45) return turn(id, letterOf("交付"));
  if (roll < 0.53) return turn(id, letterOf("交付"), { violations: ["改了工作目录外的文件"] });
  if (roll < 0.61) return turn(id, null); // 格式错：没有代码块
  if (roll < 0.69) return turn(id, null, { timed_out: true });
  if (roll < 0.82) return turn(id, null, { api_error: "rate_limit", rate_limited_until: SECONDS + 1 + Math.floor(rand() * 70) });
  if (roll < 0.9) return turn(id, null, { api_error: "403 Forbidden" });
  return turn(id, letterOf("阻塞"));
}

/** 照剧本交回的一项，带对 ts 的改动（键路径加新值）。 */
const withTs = (item: unknown, changes: readonly (readonly [string[], unknown])[]): unknown =>
  ({ ...(value(item) as object), ts_set: changes.map(([path, data]) => [path, toTagged(py(data))]) });

/** 一个种子的跑到静止请求：只办全部主任务（串行，only_task 是 None），最多 80 步。 */
export function quiesceRequest(seed: number, sc: Scene, roots: string) {
  const rand = prng(seed);
  const repeat = <T>(count: number, make: (index: number) => T): T[] => Array.from({ length: count }, (_, index) => make(index));
  const cursor = { at: 0 };
  const scripted: Record<string, unknown[]> = {
    [`runner:${COORDINATOR}`]: repeat(10, (index) => coordinatorTurn(rand, `c${index}`, cursor)),
    "Engine.verify_delivery": repeat(8, () => value(rand() < 0.6 ? [] : ["核验没过：报告缺“风险”一节"])),
    run_exec: repeat(2, () => {
      const ok = rand() < 0.5;
      return withTs({ 摘要: "执行端跑完", 提交: "无", 验证: ok ? "检查都过了" : "检查没过", 偏离: "无", 需协调人决定: "无", 证据: "attempt-002" },
        [[["exec", "check_ok"], ok], [["exec", "run_dir"], join(sc.repo, ".agent", "runs", "t002-next", "attempt-002")]]);
    }),
    run_jev: repeat(3, () => value({ 摘要: "JEV 跑完", 提交: "无", 验证: "决策 API", 偏离: "无", 需协调人决定: "无", 证据: "jev.json" })),
    finalize: [value([true, lines("verdict PASS", "integrate ok")])],
    tidy_finished: [value([])],
    rehearse_landing: repeat(3, () => value(choose(rand, [null, [true, "通过"], [false, "落地预演撞上冲突"]]))),
    regression_sweep: [value([true, "门禁基准都过了"])],
    ensure_worktree: repeat(60, () => value(sc.wt)),
    worktree_root: repeat(90, () => value(roots)),
    apply_candidate: repeat(6, () => value(sc.wt)),
    seed_whitebox: repeat(6, () => value(null)),
  };
  for (const agent of WORKERS) scripted[`runner:${agent}`] = repeat(5, (index) => workerTurn(rand, agent, `${agent}-${index}`));
  return { ...flow("quiesce", sc, [null, 80]), pin: PIN, scripted };
}
