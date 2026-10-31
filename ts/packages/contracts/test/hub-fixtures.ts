// 第 ⑤ 步几片共用的夹具：随机主任务状态（第 ⑤a 片的生成器原样搬来，⑤d 的回合输入在它上面再加字段）。
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { STAGE_ORDER } from "@themis/hub/constants";

const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const BS = C(92);
const LF = C(10);
const CR = C(13);
const FACE = C(0x1f600);
const dict = (...entries: [string, PyValue][]): PyDict => new Map(entries);

/** rnd 是 [0, 1) 的伪随机数；repo 只用在 exec.run_dir 的几种写法里。 */
export function taskStateKit(rnd: () => number, REPO: string) {
  const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
  const maybe = (chance = 0.5): boolean => rnd() < chance;
  const int = (max: number): bigint => BigInt(Math.floor(rnd() * (max + 1)));
  const hex = (length: number): string => Array.from({ length }, () => "0123456789abcdef"[Math.floor(rnd() * 16)]).join("");
  const text = (): string => pick(["", "无", "无。", "  注意 X  ", `第一行${LF}第二行`, `带 ${FACE} 的说明`, "x".repeat(200), `含${CR}${LF}回车`, `尾随${LF}`]);
  const targets = (): PyValue =>
    pick<PyValue>([null, "", "合同端", "门禁端", "执行端", "规划端", "战后门禁", "合同端、门禁端", "执行端，规划端", "门禁端 战后门禁", "未知、合同端", "执行端/门禁端", 5n]);
  const stage = (): PyDict => {
    const record = dict(["status", pick(["idle", "idle", "assigned", "delivered", "delivered", "failed", "paused"])]);
    if (maybe(0.4)) record.set("last_letter", pick(["交付", "返工完成", "提问", "阻塞", "交接", "进度"]));
    if (maybe(0.3)) record.set("note", text());
    if (maybe(0.2)) record.set("problems", [text(), "缺 report.md"]);
    if (maybe(0.15)) record.set("redelivered", true);
    if (maybe(0.4)) record.set("fields", dict(["下游须知", text()], ["摘要", "交了"]));
    return record;
  };
  const audit = (pre: boolean): PyDict => {
    const record = pre ? dict(["fails", int(4)]) : dict();
    if (maybe(0.7)) record.set("verdict", pick<PyValue>(["通过", "返工", null]));
    if (maybe(0.6)) record.set("target", targets());
    if (maybe(0.5)) record.set("contract_sha256", pick(["c1", "c2"]));
    if (maybe(0.5)) record.set("oracle_sha", pick(["o1", "o2"]));
    return record;
  };
  const runDir = (): PyValue =>
    pick<PyValue>([null, "", `${REPO}/.agent/runs/t1/attempt-001`, `c:${BS}code${BS}REPO${BS}.agent${BS}runs${BS}t1${BS}attempt-002`, ".agent/runs/t1/attempt-003", `D:/elsewhere/attempt-001`, "C:/Code/other/.agent/runs/t1/attempt-004"]);
  const state = (): PyDict => {
    const task = pick(["T001", "T024", "T1000"]);
    const ts = dict(
      ["task", task], ["slug", "desktop-ui"], ["title", "标题"], ["status", pick(["active", "active", "active", "active", "done", "stopped"])],
      ["created_at", "2026-10-29T00:00:00Z"], ["base_head", hex(40)], ["contract_task", `${task.toLowerCase()}-desktop-ui`],
      ["jev_enabled", maybe()], ["stages", new Map(STAGE_ORDER.map((suffix) => [suffix, stage()]))],
    );
    const contract = dict();
    if (maybe(0.6)) contract.set("validated", maybe(0.7));
    if (maybe(0.6)) contract.set("sha256", pick(["c1", "c2"]));
    if (maybe(0.5)) contract.set("md", ".agent/plans/t1.v1.md");
    if (maybe(0.5)) contract.set("key", pick<PyValue>(["t1.v1", "", null]));
    const oracle = dict();
    if (maybe(0.6)) oracle.set("locked", maybe(0.7));
    if (maybe(0.7)) oracle.set("sha", pick(["o1", "o2", hex(40)]));
    if (maybe(0.5)) oracle.set("files", pick<PyValue>([["tests/test_gate_t001_a.py"], [], null, ["a.py", "b.py"]]));
    const execution = dict();
    if (maybe(0.6)) execution.set("run_dir", runDir());
    if (maybe(0.5)) execution.set("check_ok", maybe());
    if (maybe(0.15)) execution.set("conflicts", pick<PyValue>([0n, 2n, 3.0]));
    if (maybe(0.15)) execution.set("gate_claim", maybe(0.7));
    if (maybe(0.1)) execution.set("collect_failed", true);
    if (maybe(0.1)) execution.set("stalled", true);
    if (maybe(0.3)) execution.set("attempts_left", pick<PyValue>([0n, 1n, 2n, 0.0]));
    const gatePost = dict();
    if (maybe(0.5)) gatePost.set("ran", maybe(0.7));
    if (maybe(0.5)) gatePost.set("ok", maybe());
    if (maybe(0.3)) gatePost.set("defects", pick<PyValue>([[], ["d1"], ["d1", "d2"]]));
    const jev = dict();
    if (maybe(0.4)) jev.set("3j-jev", dict(["ok", true]));
    if (maybe(0.4)) jev.set("6j-jev", dict(["ok", true]));
    ts.set("contract", contract).set("oracle", oracle).set("audit_pre", audit(true)).set("exec", execution).set("gate_post", gatePost)
      .set("jev", jev).set("audit_post", audit(false))
      .set("workspaces", new Map(([["base", "w1"], ["stage:3-gate-pre", "w2"], ["gate", "w3"]] as [string, PyValue][]).filter(() => maybe(0.6))))
      .set("notes", []).set("coordinator_rejections", 0n);
    // 键的次序打乱：状态表要按键排序，插入次序刚好有序就测不出来
    if (maybe(0.3)) ts.set("reworks", new Map(STAGE_ORDER.filter(() => maybe(0.4)).sort(() => rnd() - 0.5).map((suffix) => [suffix, int(4)])));
    if (maybe(0.2)) ts.set("owner_rework", dict(["suffix", pick(STAGE_ORDER)]));
    if (maybe(0.15)) ts.set("external_facts", dict(["pending", pick<PyValue>([[], ["f1"], ["f1", "f2"]])]));
    if (maybe(0.2)) ts.set("after", pick<PyValue>([["T001"], ["T001", "T002"]]));
    if (maybe(0.15)) ts.set("after_released", dict(["previous", hex(40)], ["head", hex(40)]));
    if (maybe(0.2)) ts.set("rehearsal", dict(["ok", pick<PyValue>([false, true, null])], ["run_dir", runDir()], ["head", pick<PyValue>([hex(40), null, ""])]));
    if (maybe(0.15)) ts.set("rework_chain", [dict(["from", "attempt-001"], ["commit", hex(40)], ["contract", "t1.v2"])]);
    if (maybe(0.1)) ts.set("closed_by_owner", dict(["ref", hex(40)], ["note", "站主接手"]));
    // 一到三条：任务书取最后一条，只有一条时取哪条都一样
    if (maybe(0.3)) ts.set("audit_history", Array.from({ length: 1 + Math.floor(rnd() * 3) }, () => dict(["verdict", pick(["通过", "返工"])], ["target", targets()], ["blockers", pick<PyValue>(["1. 改 X", "", null, "2. 改 Y"])])));
    return ts;
  };
  return { pick, maybe, int, hex, text, targets, state };
}
