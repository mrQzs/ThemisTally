// 第 ⑤a 片的对照（迁移计划第 ⑤ 步）：kit_hub 的信件、schema 子集校验、主任务状态与守卫，与 @themis/hub 逐项比。
// 按种子随机生成主任务状态（各阶段状态、审核结论与退回对象、热修补、依赖、站主返工、落地预演……）、信件（全角冒号、续行、
// Python 认的各种行界与空白、补充平面字符）与 schema（真实的 scripts/hub/schemas 加随机子集），同一批请求交给 Python、
// Node、Bun 三边，结果逐个比（异常比类型，HubError 比文字与退出码）。影子运行比的正是这里的 guard 与允许的下一步。
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { loads, type PyDict, type PyValue } from "@themis/base/pyjson";
import * as constants from "@themis/hub/constants";
import { COORDINATOR, KERNEL, OWNER, STAGE_ORDER, STAGE_WORKER, WORKERS } from "@themis/hub/constants";
import { renderLetter } from "@themis/hub/letters";
import { invalidateAfter, newTaskState } from "@themis/hub/taskstate";
import { describe, expect, it } from "vitest";
import { IMPLS, type ProbeRequest, REPO as REPO_ROOT, prng, runBatch, runProbe } from "./harness.ts";
import { taskStateKit } from "./hub-fixtures.ts";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);
const C = (...cps: number[]): string => String.fromCodePoint(...cps);
const FACE = C(0x1f600);
const REPO = "C:/Code/repo";

function compare(items: ProbeRequest[]): void {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, items));
  for (const other of others) {
    const mismatches = (other ?? []).flatMap((result, index) =>
      JSON.stringify(result) === JSON.stringify(python?.[index]) ? [] : [{ request: items[index], python: python?.[index], other: result }],
    );
    expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  }
  // 别让两边一样地早早失败也算一致：至少一半的请求要正常交回
  const ok = (python ?? []).filter((result) => result.ok).length;
  expect(ok, "Python 一侧正常交回的请求太少").toBeGreaterThan(items.length / 2);
}

const call = (fn: string, args: PyValue[]): ProbeRequest => ({ op: "hub.call", fn, args: args.map(toTagged), repo: REPO });
const dict = (...entries: [string, PyValue][]): PyDict => new Map(entries);

function generator(seed: number) {
  const rnd = prng(seed);
  const { pick, maybe, int, hex, text, targets, state } = taskStateKit(rnd, REPO);
  const meta = (kind: string, to: string, taskId: string): PyDict => dict(["type", kind], ["to", to], ["task-id", taskId]);
  const stateRequests = (ts: PyDict): ProbeRequest[] => {
    const task = String(ts.get("task"));
    const items: ProbeRequest[] = [call("allowed_moves", [ts]), call("stage_status_table", [ts]), call("hotfix_reason", [ts]), call("move_base", [ts, hex(40)])];
    for (const suffix of STAGE_ORDER) {
      for (const kind of ["开工", "返工", "通过"]) items.push(call("guard", [ts, meta(kind, STAGE_WORKER[suffix] as string, `${task}-${suffix}`)]));
      items.push(call("upstream_notes", [ts, suffix]), call("invalidate_after", [ts, suffix]));
      const move = dict(["reply_to", "m1"], ["fields", dict(["阻塞项", pick<PyValue>(["1. 改 X", ""])])], ["from_task", `${task}-4-audit-pre`],
        ["type", pick(["开工", "返工", "通过"])], ["suffix", suffix]);
      items.push(call("render_routine_brief", [ts, move]));
    }
    items.push(call("upstream_notes", [ts, null]));
    for (let index = 0; index < 8; index += 1) {
      const kind = pick(["开工", "返工", "通过", "等待", "停止", "汇报", "提问", "催办"]);
      const to = pick([...WORKERS, OWNER, COORDINATOR, "nobody"]);
      const taskId = pick([task, `${task}-${pick(STAGE_ORDER)}`, "T9", `${task}-9-nope`, `${task}${LF}`]);
      items.push(call("guard", [ts, meta(kind, to, taskId)]));
    }
    items.push(call("guard", [null, meta("开工", "planner-opus", `${task}-1-plan`)]), call("guard", [null, meta("开工", "planner-opus", "bad")]));
    return items;
  };
  const letterText = (): string => {
    const nl = pick([LF, `${CR}${LF}`, CR, C(0x0b), C(0x1c), C(0x2028), C(0x85)]);
    const sender = pick([...WORKERS, OWNER, KERNEL, COORDINATOR, "nobody"]);
    const head = ["---", `msg-id: ${hex(6)}`, `from: ${sender}`, maybe(0.9) ? `to: ${pick([COORDINATOR, OWNER, "planner-opus"])}` : "to",
      `task-id: ${pick(["T001", "T001-4-audit-pre", "T001-5-exec", "T001-2-contract", "X1", `T${C(0x0661, 0x0662, 0x0663)}`])}`, "in-reply-to: none",
      `type: ${pick(["交付", "返工完成", "提问", "任务", "开工"])}`, pick(["---", " --- ", "--"])];
    const fieldNames = ["摘要", "提交", "验证", "偏离", "需协调人决定", "证据", "结论", "退回", "阻塞项", "下游须知", "内核核验", "未知字段", "Summary"];
    const body: string[] = [];
    for (let index = 0; index < 1 + Math.floor(rnd() * 9); index += 1) {
      const name = pick(fieldNames);
      const colon = pick([":", "：", ": ", "：　", ":" + String.fromCharCode(9)]);
      body.push(maybe(0.8) ? `${name}${colon}${pick(["无", "通过（3/3）", "返工", "合同端、门禁端", "核验没过：审核结论缺失", `值 ${FACE}`, ""])}` : pick([`  续行${FACE}`, "续行无缩进", "   三个空格", ""]));
    }
    if (maybe(0.3)) body.push("", "  ");
    return [...head, ...body].join(nl) + (maybe() ? nl : "");
  };
  const routineLetter = (): string => {
    const sender = pick([...WORKERS, OWNER, "jev-judge", COORDINATOR]);
    const suffix = pick(STAGE_ORDER);
    const fields = [`摘要: 交付`, `提交: 无`, `验证: 无`, `偏离: 无`, `需协调人决定: ${pick(["无", "无。", "请定 X", "  无  "])}`, "证据: 无",
      `内核核验: ${pick(["通过（全部）", "没过：缺 report", "没过：审核结论缺失", "通过"])}`];
    if (maybe(0.5)) fields.push(`结论: ${pick(["通过", "返工"])}`, `退回: ${pick(["合同端", "执行端、门禁端", "未知", "规划端"])}`);
    return ["---", `msg-id: m${hex(4)}`, `from: ${sender}`, `to: ${COORDINATOR}`, `task-id: ${pick([`T001-${suffix}`, "T001"])}`,
      "in-reply-to: none", `type: ${pick(["交付", "返工完成", "提问", "任务"])}`, "---", ...fields].join(LF) + LF;
  };
  const letterRequests = (): ProbeRequest[] => {
    const items: ProbeRequest[] = [];
    for (let index = 0; index < 40; index += 1) items.push(call("parse_letter", [letterText()]));
    for (let index = 0; index < 20; index += 1) {
      const metaDict = dict(["msg-id", hex(6)], ["from", pick([...WORKERS, OWNER, KERNEL, COORDINATOR, "", "nobody"])],
        ["to", pick([COORDINATOR, OWNER, "", "nobody", "constructor"])], ["task-id", pick(["T001", "T001-4-audit-pre", "", "X", `T001-4-audit-pre${LF}`])],
        ["in-reply-to", pick(["none", ""])], ["type", pick(["交付", "返工完成", "开工", "任务", "核验", ""])]);
      const fields = new Map<string, PyValue>([["摘要", text()], ["提交", "无"], ["验证", pick(["", "无"])], ["偏离", "无"], ["需协调人决定", "无"], ["证据", "无"]]);
      if (maybe()) fields.set("结论", pick(["通过", "返工", "无"])).set("退回", targets() ?? "").set("阻塞项", pick(["", "无", "1. 改"]));
      if (maybe(0.3)) fields.set("自定义", text());
      items.push(call("letter_errors", [metaDict, fields, int(45)]), call("render_letter", [metaDict, fields]));
    }
    for (let index = 0; index < 20; index += 1) items.push(call("routine_moves", [Array.from({ length: 1 + Math.floor(rnd() * 3) }, routineLetter)]));
    for (const value of ["合同端、门禁端", "执行端，规划端，执行端", ` 门禁端${C(0x3000)}战后门禁 `, "", null, 7n, "未知"]) items.push(call("return_stages", [value as PyValue]));
    for (const value of ["T001-3-gate-pre", "T001", `T001${LF}`, `T001-1-plan${LF}`, "T01", `T${C(0x0661, 0x0662, 0x0663)}-5-exec`, "", "T0001234567"]) items.push(call("stage_of", [value]));
    return items;
  };
  const schemaValue = (depth = 0): PyValue => {
    const leaf = pick<PyValue>(["abc", "", FACE, "٣", "a1", 1n, 4.0, 4.5, true, false, null, "x".repeat(70), `末尾换行${LF}`]);
    if (depth > 1 || maybe(0.6)) return leaf;
    return maybe() ? [schemaValue(depth + 1), schemaValue(depth + 1)] : dict(["type", schemaValue(depth + 1)], ["摘要", schemaValue(depth + 1)], ["extra", leaf]);
  };
  const randomSchema = (depth = 0): PyValue => {
    const schema = dict();
    if (maybe(0.7)) schema.set("type", pick<PyValue>(["string", "object", "array", "integer", "number", "boolean", "null", ["string", "null"], "bogus", 3n]));
    if (maybe(0.2)) schema.set("enum", pick<PyValue>([["a", "b"], ["通过", "返工"], "abc", [1n, 2.0]]));
    if (maybe(0.15)) schema.set("const", pick<PyValue>(["abc", 1n, true, null]));
    if (maybe(0.3)) schema.set("minLength", pick<PyValue>([1n, 3n, 2.5]));
    if (maybe(0.2)) schema.set("maxLength", pick<PyValue>([2n, 64n]));
    if (maybe(0.3)) schema.set("pattern", pick([`^[a-z]+$`, `${BS}d{2}`, `^${BS}w+$`, "(", "(?P<x>a)", `${BS}p{L}`, "é", "[$]", `a${BS}$`, "^.$"]));
    if (maybe(0.2)) schema.set("required", pick<PyValue>([["type"], ["type", "摘要"], []]));
    if (maybe(0.2)) schema.set("additionalProperties", pick<PyValue>([false, true, 0n]));
    if (maybe(0.1)) schema.set("bogus", 1n);
    if (depth < 2 && maybe(0.3)) schema.set("properties", dict(["type", randomSchema(depth + 1)], ["摘要", randomSchema(depth + 1)]));
    if (depth < 2 && maybe(0.2)) schema.set("items", randomSchema(depth + 1));
    return schema;
  };
  const schemaRequests = (real: PyValue[]): ProbeRequest[] => {
    const items: ProbeRequest[] = [];
    for (let index = 0; index < 40; index += 1) {
      const schema = randomSchema();
      items.push(call("schema_problems", [schema]), call("schema_errors", [schema, schemaValue()]));
    }
    for (const schema of real) {
      items.push(call("schema_problems", [schema]));
      // 照 schema 的属性生成一份值：嵌套对象照它的属性填，叶子随机；偶尔漏一项、多一项
      const fill = (node: PyValue): PyValue => {
        const properties = (node as PyDict).get("properties");
        if (!(properties instanceof Map)) return pick<PyValue>(["无", "", "交付", "通过", 3n, FACE, null]);
        return new Map([...properties].filter(() => maybe(0.9)).map(([key, sub]) => [key as string, fill(sub)]));
      };
      const value = fill(schema) as PyDict;
      if (maybe(0.3)) value.set("多余", "x");
      items.push(call("schema_errors", [schema, value]));
    }
    return items;
  };
  return { state, stateRequests, letterRequests, schemaRequests };
}

const REAL_SCHEMAS: PyValue[] = readdirSync(join(REPO_ROOT, "scripts", "hub", "schemas"))
  .filter((name) => name.endsWith(".json"))
  .map((name) => loads(readFileSync(join(REPO_ROOT, "scripts", "hub", "schemas", name), "utf8")));

describe("第 ⑤a 片：信件、schema、主任务状态与守卫", () => {
  // 第 132 轮换审核端模型时补：名册等常量两边各写一份，原先只靠用到它们的函数间接对上，名册没有函数用到
  it("常量与 kit_hub 的同名常量逐项相同：名册、阶段、依赖、字段、上限，连键的次序", () => {
    const names = Object.keys(constants);
    const [python, ...others] = IMPLS.map((impl) => runProbe(impl, { op: "hub.constants", names }));
    expect(python?.ok, JSON.stringify(python)).toBe(true);
    const ours = JSON.stringify(JSON.parse(String(python?.["json"])));
    for (const other of others) expect(JSON.stringify(JSON.parse(String(other["json"])))).toBe(ours);
    expect(JSON.parse(ours)["ROSTER"]["audit-sonnet"]).toMatchObject({ provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "max" });
  });

  it("新主任务的状态、门禁文件名、依赖的闭包", () => {
    compare([
      call("new_task_state", ["T001", "desktop-ui", "标题", "abc", true, "2026-10-29T00:00:00Z"]),
      call("new_task_state", [`T${C(0x0130)}01`, "s", "t", "h", false, "x"]),
      ...STAGE_ORDER.map((suffix) => call("dependents", [suffix])),
      call("gate_pattern", [dict(["task", "T024"])]), call("gate_file", [dict(["task", "T024"]), "baseline"]),
      call("stage_busy", [dict(["status", "assigned"], ["last_letter", "提问"])]), call("stage_busy", [dict(["status", "assigned"])]),
      call("stage_busy", [dict(["last_letter", "提问"])]),
    ]);
  });

  it("手挑的信件与 schema：字段名后有空格、行首空白、制表符、末尾换行与 $、多个子集外关键字", () => {
    const letter = (...body: string[]): string => ["---", "msg-id: m1", "from: audit-sonnet", "to: womovie-c8", "task-id: T001-4-audit-pre", "in-reply-to: none", "type: 交付", "---", ...body].join(LF);
    compare([
      call("parse_letter", [letter("摘要 :x", " 摘要: y", "阻塞 项: z", "摘要::双冒号", ":开头冒号", "a:b:c", `摘要:${String.fromCharCode(9)}制表符`)]),
      call("parse_letter", [letter("摘要: 一", "  续行两空格", "   续行三空格", "续行无缩进", "", "")]),
      call("schema_errors", [dict(["type", "string"], ["pattern", "^[a-z]+$"]), `abc${LF}`]),
      call("schema_errors", [dict(["type", "string"], ["pattern", "abc$"]), `xabc${LF}`]),
      call("schema_problems", [dict(["zeta", 1n], ["alpha", 2n], ["type", "string"], [FACE, 3n], ["中", 4n])]),
      call("schema_problems", [dict(["type", "object"], ["additionalProperties", true], ["properties", dict(["a", dict(["bogus", 1n])])], ["items", "x"])]),
      call("schema_errors", [dict(["type", "object"], ["required", ["a", "b"]], ["additionalProperties", false], ["properties", dict(["a", dict(["type", "integer"])])]), dict(["a", 4.0], ["c", 1n])]),
      call("schema_errors", [dict(["type", "object"], ["properties", dict(["a", dict(["type", "integer"])])]), dict(["a", true])]),
    ]);
  });

  it.each([1, 2, 3])("随机主任务状态，种子 %i：60 个状态 × 守卫、允许的下一步、作废、任务书、状态表", (seed) => {
    const { state, stateRequests } = generator(seed);
    compare(Array.from({ length: 60 }, state).flatMap(stateRequests));
  });

  it.each([11, 12])("随机信件，种子 %i：解析、渲染、形状校验、例行流转", (seed) => {
    const { letterRequests } = generator(seed);
    compare(Array.from({ length: 5 }, letterRequests).flat());
  });

  it.each([21, 22])("schema 子集，种子 %i：真实的五份 schema 加随机子集", (seed) => {
    const { schemaRequests } = generator(seed);
    compare(Array.from({ length: 5 }, () => schemaRequests(REAL_SCHEMAS)).flat());
  });
});

// --- tests/test_kit_hub.py 里第 ⑤a 片的场景（覆盖审计：同场景两边各跑）-------------------------------------------
// 参数化的样例由 Python 探针的 hub.samples 从 pytest 文件里取出，只有那一个来源；按步骤断言的守卫场景照步骤搭出每一步
// 的状态快照。会改状态的步骤用 TS 实现推进到下一步：它要是错了，这一步自己的请求先就对不上。

interface Samples {
  readonly shape: PyValue[];
  readonly routine: PyValue[];
  readonly exceptions: PyValue[];
  readonly schema: PyValue[];
  readonly fields: PyDict;
  readonly base: string;
}

function samples(): Samples {
  const [result] = runBatch(IMPLS[0] as (typeof IMPLS)[number], [{ op: "hub.samples" }]);
  expect(result?.ok, JSON.stringify(result)).toBe(true);
  const value = fromTagged((result as unknown as { value: Tagged }).value) as PyDict;
  return {
    shape: value.get("shape") as PyValue[], routine: value.get("routine") as PyValue[], exceptions: value.get("exceptions") as PyValue[],
    schema: value.get("schema") as PyValue[], fields: value.get("fields") as PyDict, base: value.get("base") as string,
  };
}

const metaOf = (kind: string, to: string, task: string): PyDict =>
  dict(["type", kind], ["to", to], ["task-id", task], ["from", COORDINATOR], ["in-reply-to", "none"]);
const part = (ts: PyDict, key: string): PyDict => ts.get(key) as PyDict;
const stageRec = (ts: PyDict, suffix: string): PyDict => part(ts, "stages").get(suffix) as PyDict;

function guardScenarios(base: string): ProbeRequest[] {
  const items: ProbeRequest[] = [];
  const g = (ts: PyDict | null, kind: string, to: string, task: string): void => {
    items.push(call("guard", [ts, metaOf(kind, to, task)]));
  };
  const makeTs = (jev = true): PyDict => newTaskState("T001", "doc", "改桌面端文档", base, jev, "2026-10-29T00:00:00Z");
  const locked = (ts: PyDict): PyDict => {
    part(ts, "contract").set("validated", true).set("sha256", "c1").set("key", "t001-doc.v1").set("version", 1n);
    part(ts, "oracle").set("sha", "o".repeat(40)).set("locked", true);
    for (const suffix of ["1-plan", "2-contract", "3-gate-pre"]) stageRec(ts, suffix).set("status", "delivered");
    return ts;
  };
  // test_guard_owner_and_routing_rules
  let ts = makeTs();
  g(ts, "汇报", OWNER, "T001"); g(ts, "开工", OWNER, "T001"); g(ts, "汇报", "planner-opus", "T001-1-plan");
  g(ts, "开工", "gate-sonnet", "T001-2-contract"); g(ts, "开工", "planner-opus", "T001"); g(null, "开工", "planner-opus", "T001-1-plan");
  ts.set("status", "stopped"); g(ts, "开工", "planner-opus", "T001-1-plan");
  // test_guard_plan_contract_gate_and_jev_starts
  ts = makeTs();
  g(ts, "开工", "planner-opus", "T001-1-plan"); stageRec(ts, "1-plan").set("status", "assigned"); g(ts, "开工", "planner-opus", "T001-1-plan");
  g(ts, "开工", "contract-glm", "T001-2-contract"); stageRec(ts, "1-plan").set("status", "delivered"); g(ts, "开工", "contract-glm", "T001-2-contract");
  g(ts, "开工", "gate-sonnet", "T001-3-gate-pre"); g(ts, "开工", "jev-judge", "T001-3j-jev");
  part(ts, "contract").set("validated", true); stageRec(ts, "2-contract").set("status", "delivered");
  g(ts, "开工", "gate-sonnet", "T001-3-gate-pre"); g(ts, "开工", "jev-judge", "T001-3j-jev");
  // test_guard_audit_pre_needs_locked_baseline_and_jev
  ts = makeTs();
  part(ts, "contract").set("validated", true); g(ts, "开工", "audit-sonnet", "T001-4-audit-pre");
  locked(ts); g(ts, "开工", "audit-sonnet", "T001-4-audit-pre");
  part(ts, "jev").set("3j-jev", dict(["status", "no_opinion"])); g(ts, "开工", "audit-sonnet", "T001-4-audit-pre");
  g(locked(makeTs(false)), "开工", "audit-sonnet", "T001-4-audit-pre");
  // test_guard_exec_needs_passing_first_review_on_the_same_bytes
  ts = locked(makeTs());
  g(ts, "开工", "exec-step", "T001-5-exec");
  part(ts, "audit_pre").set("verdict", "返工").set("contract_sha256", "c1").set("oracle_sha", "o".repeat(40)); g(ts, "开工", "exec-step", "T001-5-exec");
  part(ts, "audit_pre").set("verdict", "通过"); g(ts, "开工", "exec-step", "T001-5-exec");
  part(ts, "contract").set("sha256", "c2"); g(ts, "开工", "exec-step", "T001-5-exec");
  part(ts, "contract").set("sha256", "c1"); part(ts, "oracle").set("sha", "p".repeat(40)); g(ts, "开工", "exec-step", "T001-5-exec");
  // test_guard_short_circuit_after_execution
  ts = locked(makeTs());
  part(ts, "exec").set("run_dir", "r").set("check_ok", false);
  for (const [task, worker] of [["T001-6-gate-post", "gate-sonnet"], ["T001-6j-jev", "jev-judge"], ["T001-7-audit-post", "audit-sonnet"]] as const) g(ts, "开工", worker, task);
  g(ts, "返工", "exec-step", "T001-5-exec");
  part(ts, "exec").set("check_ok", true); g(ts, "开工", "gate-sonnet", "T001-6-gate-post"); g(ts, "返工", "exec-step", "T001-5-exec");
  part(ts, "gate_post").set("ran", true).set("ok", false);
  g(ts, "开工", "jev-judge", "T001-6j-jev"); g(ts, "开工", "audit-sonnet", "T001-7-audit-post"); g(ts, "返工", "exec-step", "T001-5-exec");
  part(ts, "gate_post").set("ok", true); g(ts, "开工", "jev-judge", "T001-6j-jev"); g(ts, "开工", "audit-sonnet", "T001-7-audit-post");
  part(ts, "jev").set("6j-jev", dict(["status", "answered"])); g(ts, "开工", "audit-sonnet", "T001-7-audit-post");
  // test_guard_rework_targets
  ts = locked(makeTs());
  g(ts, "返工", "contract-glm", "T001-2-contract"); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  part(ts, "audit_pre").set("verdict", "返工").set("target", "门禁端"); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre"); g(ts, "返工", "contract-glm", "T001-2-contract");
  stageRec(ts, "2-contract").set("status", "failed"); g(ts, "返工", "contract-glm", "T001-2-contract"); g(ts, "返工", "planner-opus", "T001-1-plan");
  part(ts, "audit_pre").set("verdict", "返工").set("target", "规划端"); g(ts, "返工", "planner-opus", "T001-1-plan");
  part(ts, "audit_pre").set("verdict", "返工").set("target", "门禁端"); g(ts, "返工", "planner-opus", "T001-1-plan");
  part(ts, "audit_pre").set("fails", 3n); g(ts, "返工", "planner-opus", "T001-1-plan");
  part(ts, "audit_post").set("verdict", "返工").set("target", "执行端"); g(ts, "返工", "exec-step", "T001-5-exec");
  stageRec(ts, "4-audit-pre").set("status", "assigned"); g(ts, "返工", "audit-sonnet", "T001-4-audit-pre");
  // test_final_review_can_return_to_the_contract_and_to_the_post_gate
  ts = locked(makeTs());
  part(ts, "audit_pre").set("verdict", "通过"); g(ts, "返工", "contract-glm", "T001-2-contract"); g(ts, "返工", "gate-sonnet", "T001-6-gate-post");
  part(ts, "audit_post").set("verdict", "返工").set("target", "合同端"); g(ts, "返工", "contract-glm", "T001-2-contract"); g(ts, "返工", "gate-sonnet", "T001-6-gate-post");
  part(ts, "audit_post").set("target", "战后门禁"); g(ts, "返工", "gate-sonnet", "T001-6-gate-post"); g(ts, "返工", "contract-glm", "T001-2-contract");
  // test_guard_final_pass_needs_final_review
  ts = locked(makeTs());
  g(ts, "通过", "exec-step", "T001-5-exec"); part(ts, "audit_post").set("verdict", "通过"); g(ts, "通过", "exec-step", "T001-5-exec");
  g(ts, "通过", "audit-sonnet", "T001-7-audit-post"); g(ts, "等待", "audit-sonnet", "T001-7-audit-post");
  // test_guard_final_pass_waits_for_a_failed_rehearsal_of_this_candidate
  ts = locked(makeTs());
  const runDir = ["C:", "repo", ".agent", "runs", "t001-doc", "attempt-002"].join(BS);
  part(ts, "audit_post").set("verdict", "通过"); part(ts, "exec").set("run_dir", runDir);
  ts.set("rehearsal", dict(["head", "f".repeat(40)], ["run_dir", runDir], ["ok", false], ["at", "x"]));
  g(ts, "通过", "exec-step", "T001-5-exec"); items.push(call("allowed_moves", [ts]));
  part(ts, "rehearsal").set("run_dir", ["C:", "repo", ".agent", "runs", "t001-doc", "attempt-001"].join(BS)); g(ts, "通过", "exec-step", "T001-5-exec");
  part(ts, "rehearsal").set("run_dir", runDir).set("ok", true); g(ts, "通过", "exec-step", "T001-5-exec"); items.push(call("allowed_moves", [ts]));
  // test_upstream_redelivery_invalidates_only_dependents
  ts = locked(makeTs());
  part(ts, "jev").set("3j-jev", dict(["status", "answered"])); part(ts, "audit_pre").set("verdict", "通过").set("fails", 2n);
  items.push(call("invalidate_after", [ts, "3-gate-pre"])); invalidateAfter(ts, "3-gate-pre");
  part(ts, "exec").set("run_dir", "r").set("check_ok", true); stageRec(ts, "5-exec").set("status", "delivered"); part(ts, "audit_post").set("verdict", "通过");
  items.push(call("invalidate_after", [ts, "2-contract"]));
  // test_allowed_moves_lists_only_passing_letters
  items.push(call("allowed_moves", [makeTs()]));
  // test_routine_briefs_quote_each_path_on_its_own（engine_env 只提供仓库与状态：这里直接调）
  ts = makeTs();
  part(ts, "exec").set("run_dir", `${REPO}/.agent/runs/t001-doc/attempt-001`);
  part(ts, "oracle").set("files", ["tests/test_a.py", "tests/test_b.py"]);
  items.push(call("render_routine_brief", [ts, dict(["type", "开工"], ["suffix", "6-gate-post"], ["fields", dict()], ["from_task", "x"])]));
  return items;
}

function letterScenarios(sample: Samples): ProbeRequest[] {
  const fieldsWith = (extra: Record<string, string>): PyDict => new Map([...sample.fields, ...Object.entries(extra)]);
  const items: ProbeRequest[] = sample.shape.map((item) => call("letter_errors", item as PyValue[]));
  // test_letter_round_trip_keeps_multiline_fields
  const head = dict(["msg-id", "m1"], ["from", "planner-opus"], ["to", COORDINATOR], ["task-id", "T001-1-plan"], ["in-reply-to", "none"], ["type", "交付"]);
  const body = fieldsWith({ 偏离: `第一行${LF}第二行：带冒号也算续行` });
  const text = renderLetter(new Map([...head].map(([key, value]) => [String(key), String(value)])), new Map([...body].map(([key, value]) => [String(key), value])));
  items.push(call("render_letter", [head, body]), call("parse_letter", [text]));
  // test_letter_body_limit_and_audit_verdict
  const audit = dict(["from", "audit-sonnet"], ["to", COORDINATOR], ["task-id", "T001-4-audit-pre"], ["in-reply-to", "none"], ["type", "交付"]);
  const cases: [PyDict, Record<string, string>, bigint][] = [
    [audit, { 结论: "通过" }, 41n], [audit, {}, 6n], [audit, { 结论: "返工" }, 7n], [audit, { 结论: "返工", 退回: "门禁端" }, 8n],
    [audit, { 结论: "返工", 退回: "门禁端", 阻塞项: "无" }, 9n], [audit, { 结论: "返工", 退回: "门禁端", 阻塞项: "1. 断言太松" }, 9n],
    [audit, { 结论: "返工", 退回: "执行端", 阻塞项: "x" }, 9n], [audit, { 结论: "返工", 退回: "战后门禁", 阻塞项: "x" }, 9n],
    [new Map([...audit, ["task-id", "T001-7-audit-post"]]), { 结论: "返工", 退回: "战后门禁", 阻塞项: "x" }, 9n],
  ];
  for (const [meta, extra, lines] of cases) items.push(call("letter_errors", [meta, fieldsWith(extra), lines]));
  // test_routine_letters_map_to_the_next_step、test_exceptions_go_to_the_coordinator
  for (const batch of [...sample.routine, ...sample.exceptions]) items.push(call("routine_moves", [batch]));
  return items;
}

function schemaScenarios(sample: Samples): ProbeRequest[] {
  // test_the_schema_subset_validator、test_role_schemas_only_use_the_subset_and_match_the_kernel
  return [
    ...sample.schema.map((item) => call("schema_errors", item as PyValue[])),
    ...REAL_SCHEMAS.map((schema) => call("schema_problems", [schema])),
    call("schema_problems", [dict(["type", "object"], ["format", "date"], ["properties", dict(["a", dict(["$ref", "#/x"])])])]),
    call("schema_problems", [dict(["additionalProperties", true], ["pattern", "中"])]),
    call("schema_problems", [dict(["type", "string"], ["pattern", `^${BS}p{L}+$`])]),
    call("schema_problems", [dict(["type", "string"], ["pattern", "(?<n>x)"])]),
  ];
}

function hotfixScenarios(sample: Samples): ProbeRequest[] {
  const items: ProbeRequest[] = [];
  const g = (ts: PyDict, kind: string, to: string, task: string): void => {
    items.push(call("guard", [ts, metaOf(kind, to, task)]));
  };
  const hot = (ts: PyDict): void => {
    items.push(call("hotfix_reason", [ts]));
  };
  const fieldsWith = (extra: Record<string, string>): PyDict => new Map([...sample.fields, ...Object.entries(extra)]);
  const makeTs = (): PyDict => newTaskState("T001", "doc", "改桌面端文档", sample.base, true, "2026-10-29T00:00:00Z");
  const locked = (ts: PyDict): PyDict => {
    part(ts, "contract").set("validated", true).set("sha256", "c1").set("key", "t001-doc.v1").set("version", 1n);
    part(ts, "oracle").set("sha", "o".repeat(40)).set("locked", true);
    for (const suffix of ["1-plan", "2-contract", "3-gate-pre"]) stageRec(ts, suffix).set("status", "delivered");
    return ts;
  };
  // test_gate_hotfix_needs_the_executors_evidence_or_a_final_review_return
  let ts = locked(makeTs());
  part(ts, "audit_pre").set("verdict", "通过").set("contract_sha256", "c1").set("oracle_sha", "o".repeat(40));
  part(ts, "exec").set("run_dir", "r").set("check_ok", false).set("conflicts", 0n);
  g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  part(ts, "exec").set("conflicts", 2n); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  part(ts, "exec").set("conflicts", 0n); part(ts, "audit_post").set("verdict", "返工").set("target", "执行端"); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  part(ts, "audit_post").set("target", "门禁端"); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  items.push(call("invalidate_after", [ts, "3-gate-pre"])); invalidateAfter(ts, "3-gate-pre");
  hot(ts); g(ts, "开工", "exec-step", "T001-5-exec");
  // test_legacy_task_without_external_facts_is_not_blocked
  ts = makeTs();
  stageRec(ts, "1-plan").set("status", "delivered"); g(ts, "开工", "contract-glm", "T001-2-contract");
  // test_audit_may_return_several_stages_and_the_upstream_one_goes_first
  const head = dict(["from", "audit-sonnet"], ["to", COORDINATOR], ["task-id", "T001-4-audit-pre"], ["in-reply-to", "m"], ["type", "交付"]);
  for (const value of ["合同端、门禁端", "合同端，门禁端", "合同端, 门禁端", "合同端/门禁端", "合同端 门禁端"]) {
    items.push(call("letter_errors", [head, fieldsWith({ 结论: "返工", 退回: value, 阻塞项: "1. D09" }), 9n]), call("return_stages", [value]));
  }
  for (const value of ["门禁端、合同端、门禁端", "", null, "乱写"]) items.push(call("return_stages", [value]));
  for (const value of ["合同端、乱写", "、", ""]) items.push(call("letter_errors", [head, fieldsWith({ 结论: "返工", 退回: value, 阻塞项: "x" }), 9n]));
  items.push(call("letter_errors", [head, fieldsWith({ 结论: "返工", 退回: "合同端、执行端", 阻塞项: "x" }), 9n]));
  items.push(call("letter_errors", [new Map([...head, ["task-id", "T001-7-audit-post"]]), fieldsWith({ 结论: "返工", 退回: "门禁端、执行端", 阻塞项: "x" }), 9n]));
  ts = locked(makeTs());
  stageRec(ts, "4-audit-pre").set("status", "delivered"); part(ts, "audit_pre").set("verdict", "返工").set("target", "门禁端、合同端");
  g(ts, "返工", "gate-sonnet", "T001-3-gate-pre"); g(ts, "返工", "contract-glm", "T001-2-contract");
  ts.set("owner_rework", dict(["suffix", "3-gate-pre"])); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  ts.delete("owner_rework"); part(ts, "audit_pre").set("target", "门禁端");
  g(ts, "返工", "gate-sonnet", "T001-3-gate-pre"); g(ts, "返工", "contract-glm", "T001-2-contract");
  ts = locked(makeTs());
  part(ts, "audit_post").set("verdict", "返工").set("target", "门禁端、执行端");
  hot(ts); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre"); g(ts, "返工", "exec-step", "T001-5-exec");
  part(ts, "audit_post").set("target", "合同端、门禁端"); hot(ts);
  part(ts, "audit_post").set("target", "合同端、门禁端、执行端"); g(ts, "返工", "exec-step", "T001-5-exec");
  part(ts, "audit_post").set("target", "执行端"); hot(ts); g(ts, "返工", "exec-step", "T001-5-exec");
  part(ts, "audit_post").set("target", "合同端、执行端"); g(ts, "返工", "contract-glm", "T001-2-contract"); g(ts, "返工", "exec-step", "T001-5-exec");
  part(ts, "audit_post").set("verdict", "通过"); g(ts, "返工", "exec-step", "T001-5-exec");
  // test_owner_ordered_gate_rework_is_a_hotfix_and_holds_the_executor_back
  ts = locked(makeTs());
  part(ts, "audit_pre").set("verdict", "通过").set("contract_sha256", "c1").set("oracle_sha", "o".repeat(40));
  stageRec(ts, "4-audit-pre").set("status", "delivered");
  part(ts, "exec").set("run_dir", "r").set("check_ok", false).set("conflicts", 0n); stageRec(ts, "5-exec").set("status", "failed");
  hot(ts); g(ts, "返工", "exec-step", "T001-5-exec");
  ts.set("owner_rework", dict(["suffix", "3-gate-pre"])); hot(ts);
  g(ts, "返工", "exec-step", "T001-5-exec"); g(ts, "开工", "audit-sonnet", "T001-4-audit-pre"); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  ts.set("exec", dict()); hot(ts);
  // test_a_gate_claim_opens_the_hotfix_and_holds_the_executor_until_the_gate_redelivers
  ts = locked(makeTs());
  part(ts, "audit_pre").set("verdict", "通过").set("contract_sha256", "c1").set("oracle_sha", "o".repeat(40));
  part(ts, "exec").set("run_dir", "r").set("check_ok", false).set("conflicts", 0n);
  hot(ts); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre");
  part(ts, "exec").set("gate_claim", true).set("gate_claims", ["V01 均为门禁端缺陷"]);
  hot(ts); g(ts, "返工", "gate-sonnet", "T001-3-gate-pre"); g(ts, "返工", "exec-step", "T001-5-exec");
  items.push(call("invalidate_after", [ts, "3-gate-pre"])); invalidateAfter(ts, "3-gate-pre"); hot(ts);
  return items;
}

describe("第 ⑤a 片：tests/test_kit_hub.py 的场景", () => {
  it("守卫：开工、返工、通过的各条前置条件，作废与允许的下一步（按步骤）", () => {
    compare(guardScenarios(samples().base));
  });

  it("守卫：热修补、多处退回、站主指定门禁返工、执行端举证、旧主任务没有仓库外事实（按步骤）", () => {
    compare(hotfixScenarios(samples()));
  });

  it("信件：往返、形状校验的样例、审核结论与退回范围、例行流转与例外", () => {
    compare(letterScenarios(samples()));
  });

  it("schema 子集：校验器的样例、五份岗位 schema、子集外的写法", () => {
    compare(schemaScenarios(samples()));
  });
});
