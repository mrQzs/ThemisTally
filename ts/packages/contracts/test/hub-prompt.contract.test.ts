// 第 ⑤d1 片的契约（迁移计划第 ⑤ 步）：回合输入与交差核对。kit_hub.py 的 render_template、role_prompt、engineering_rules、
// transitional_section（含 E6 的前端过渡用例）、external_facts_section、input_path、turn_prompt、letter_from_output、delivered_output、
// interface_problem、delivery_problem、worker_file_problem、worker_env、regression_gates、next_contract_version、budget_usage 交给
// Python、Node、Bun，逐字比带标签的结果（崩溃比类型，HubError 比文字与退出码）。语料：
//   - tests/test_kit_hub.py 里用到这些函数的用例：Python 探针跑一遍、记下顶层调用（Hub 记成仓库路径），三边在同一份文件上重放；
//     用例里改过的内核全局（模板目录、HERE、read_text 的替身）重放时已经撤销，要点在那上面的几条另有手写的对照；
//   - 手写的对照：模板目录与内核仓库两边设同一个值；模板读到空文件、文件正被替换；worker_env 在设了假 key 的环境里只比名字
//     （迁移计划第 0 节：不比值，比对失败时 vitest 会把两边打印出来）；
//   - 按种子生成：第 ⑤a 片的随机主任务状态再加回合输入用到的字段，乘全部岗位、有无输入目录、四种续接、报错与代办说明；临时仓库里
//     有任务书、state.md、runs 证据、提交过的门禁基准（含 Unicode 数字的文件名：ls-tree 照 Git 缺省给它加引号，不算回归测试）；
//   - transitional_section：生成的门禁测试与前端测试（三种引号、链式调用、多行参数、说明行的前缀，标题与空白里带 U+FEFF、
//     0x1c–0x1f、0x85、U+2028、U+2029 与非 ASCII 字母）。
import { spawn } from "node:child_process";
import { mkdirSync, readdirSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { COORDINATOR, ENGINEERING_HEADING, OWNER, ROSTER, STAGE_ORDER, STAGE_WORKER } from "@themis/hub/constants";
import { DELIVER_EXTENSION, GUARD_EXTENSION, SCHEMA_DIR } from "@themis/hub/kernel";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, type Impl, PYTHON, type ProbeRequest, type ProbeResult, REPO, prng, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { taskStateKit } from "./hub-fixtures.ts";
import { newRepo, put, removeCreated } from "./repo-fixtures.ts";

const C = (...codes: number[]): string => String.fromCodePoint(...codes);
const TAB = C(9);
const LF = C(10);
const CR = C(13);
const DQ = C(34);
const BT = C(96);
const FACE = C(0x1f600);
const ROOT = scratchDir("prompt");
const LONG = realpathSync.native(ROOT);
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

/** 字面量写成 Python 的值：整数是 int，带 F() 的是 float，对象是 dict。 */
class Float {
  readonly value: number;
  constructor(value: number) {
    this.value = value;
  }
}
const F = (value: number): Float => new Float(value);
function py(value: unknown): PyValue {
  if (value instanceof Float) return value.value;
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "bigint") return value;
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(py);
  if (value instanceof Map) return value as PyDict;
  return new Map(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, py(item)]));
}
const dict = (...entries: [string, PyValue][]): PyDict => new Map(entries);
const call = (fn: string, args: readonly unknown[], extra: Record<string, unknown> = {}): ProbeRequest => ({ op: "hub.prompt", fn, args: args.map((arg) => toTagged(py(arg))), ...extra });
const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

/** 三边各跑一遍、逐个比；交回 Python 的结果。okShare：至少这一份比例的请求要正常交回（别让两边一样地早早失败也算一致）。 */
function agree(requests: readonly ProbeRequest[], okShare = 0.5, impls: readonly Impl[] = IMPLS): ProbeResult[] {
  const [python, ...others] = impls.map((impl) => runBatch(impl, requests));
  for (const [index, other] of others.entries()) {
    const bad = requests.map((_, at) => at).filter((at) => JSON.stringify(python?.[at]) !== JSON.stringify(other[at]));
    // 提示词很长：从第一处不同的位置前后各取一段
    const window = (left: string, right: string): [string, string] => {
      let first = 0;
      while (first < left.length && left[first] === right[first]) first += 1;
      const from = Math.max(0, first - 300);
      return [left.slice(from, first + 300), right.slice(from, first + 300)];
    };
    const shown = bad.slice(0, 2).map((at) => {
      const [ours, theirs] = window(JSON.stringify(python?.[at]), JSON.stringify(other[at]));
      return { at, fn: requests[at]?.["fn"], python: ours, other: theirs };
    });
    expect(shown, `${impls[index + 1]?.name} 与 Python 不同（共 ${bad.length} 处）`).toEqual([]);
  }
  const ok = (python ?? []).filter((result) => result.ok).length;
  expect(ok, JSON.stringify((python ?? []).filter((result) => !result.ok).slice(0, 3))).toBeGreaterThanOrEqual(Math.ceil(requests.length * okShare));
  return python as ProbeResult[];
}

// --- 一、pytest 的场景 -----------------------------------------------------------------------------------------

const TESTS = [
  "test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt", "test_planner_sees_the_transitional_gate_assertions",
  "test_planner_sees_the_transitional_frontend_cases", "test_planner_sizes_the_slice_against_one_attempt",
  "test_gate_rules_keep_the_regression_tests_valid_after_integration", "test_gate_post_judges_mutations_from_the_record",
  "test_gate_post_checks_the_anchors_before_mutating", "test_candidate_defects_go_to_the_final_review_which_cannot_pass_them",
  "test_review_history_survives_rework_and_seals_the_next_round", "test_kernel_writes_the_contract_version_and_base_it_assigns",
  "test_contract_runs_the_earlier_gates_as_regression_checks", "test_mutations_must_cover_the_changed_files",
  "test_unverified_external_facts_wait_for_the_owner", "test_legacy_task_without_external_facts_is_not_blocked",
  "test_a_turn_killed_midway_restarts_in_a_new_session_and_is_requeued_only_once", "test_requeue_leaves_unread_and_kernel_run_stages_alone",
  "test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline", "test_role_prompt_only_renders_the_workers_own_duties",
  "test_engineering_rules_from_committed_agents_md_reach_the_pi_roles", "test_the_committed_agents_md_has_the_engineering_rules",
  "test_planner_may_only_run_npm_view", "test_worker_env_drops_the_decision_key_and_host_session_vars",
  "test_template_read_waits_out_a_file_being_replaced", "test_new_attempt_gate_post_starts_from_the_previous_whitebox",
  "test_decisions_are_attached_to_the_contract_and_shown_to_the_contract_writer", "test_the_gate_hotfix_turn_carries_the_executors_words",
  "test_worker_prompts_state_the_turn_time_limit", "test_a_timed_out_voided_turn_is_resumed_not_restarted",
  "test_a_voided_turn_that_did_not_time_out_gets_no_resume_hint", "test_the_owners_rework_words_reach_the_reworked_stage_verbatim",
  "test_an_audit_turn_hands_in_through_deliver", "test_downstream_notes_ride_along_to_every_later_turn",
  "test_the_prompt_says_how_to_hand_in", "test_unreadable_lines_are_not_counted_as_unreadable_deliveries",
];
/** 当时的结果与 Python 重放对不上的用例（第一次跑出来的清单，覆盖审计里记 PARTIAL）；多了少了都要看过再改。 */
// 改过 HERE、换过 read_text 的两条另有手写的对照；经 Engine 的三条多回合之后文件已变，记 PARTIAL
const DRIFTED: string[] = [
  "test_a_timed_out_voided_turn_is_resumed_not_restarted",
  "test_engineering_rules_from_committed_agents_md_reach_the_pi_roles",
  "test_template_read_waits_out_a_file_being_replaced",
  "test_the_owners_rework_words_reach_the_reworked_stage_verbatim",
  "test_unverified_external_facts_wait_for_the_owner",
];
const FUNCTIONS = ["turn_prompt", "role_prompt", "engineering_rules", "render_template", "transitional_section", "external_facts_section", "input_path",
  "letter_from_output", "delivered_output", "interface_problem", "delivery_problem", "worker_file_problem", "worker_env", "regression_gates",
  "next_contract_version", "budget_usage"];

/** 采样当时的结果与 Python 重放对不上的用例：重放读的是用例跑完时的文件、用例改过的全局已经撤销，这几条不算重放过那个场景。 */
function drifted(calls: readonly { test: string; result: string }[], python: readonly ProbeResult[]): string[] {
  return [...new Set(calls.filter((item, at) => JSON.stringify(JSON.parse(item.result)) !== JSON.stringify(python[at])).map((item) => item.test))].sort();
}

function pytestCalls(): { test: string; fn: string; args: PyValue[]; result: string }[] {
  const tmp = join(ROOT, "samples");
  mkdirSync(tmp, { recursive: true });
  const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: FUNCTIONS, tmp });
  expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
  const value = valueOf(recorded) as PyDict;
  expect(value.get("skipped")).toEqual([]);
  return (value.get("calls") as PyDict[]).map((item) => ({ test: item.get("test") as string, fn: item.get("fn") as string, args: item.get("args") as PyValue[], result: item.get("result") as string }));
}

describe("第 ⑤d1 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("记到的顶层调用三边重放逐字相同", () => {
    const calls = pytestCalls();
    expect(new Set(calls.map((item) => item.fn)).size, "用到的函数").toBeGreaterThan(10);
    const python = agree(calls.map((item) => ({ op: "hub.prompt", fn: item.fn, args: item.args.map(toTagged) })), 0.8);
    expect(drifted(calls, python), "当时的结果与 Python 重放").toEqual(DRIFTED);
  }, 600_000);
});

// --- 二、手写的对照：模板目录、内核仓库、空模板、环境 ---------------------------------------------------------------

/** 一个提交过 AGENTS.md 的内核仓库；工作区里的 AGENTS.md 再改成没提交的样子（站主改了还没提交：不跟着变）。 */
function kernelRepo(name: string, committed: string): string {
  const { repo } = newRepo(`prompt-kernel-${name}`, { "AGENTS.md": committed });
  writeFileSync(join(repo, "AGENTS.md"), `没提交的改动${LF}`);
  return repo;
}

describe("第 ⑤d1 片：手写的对照", () => {
  it("全部岗位的角色提示词（真的模板与内核仓库）；没有这个岗位时报 KeyError", () => {
    const results = agree([...Object.keys(ROSTER), "nobody"].map((agent) => call("role_prompt", [agent])), 0.8);
    expect(results.at(-1)).toMatchObject({ ok: false, error: "KeyError" });
  });

  it("模板目录两边设同一个值：角色段只留自己的、占位符逐个代入（值里带 $& 与 $1）、CRLF、没有结尾换行的角色段", () => {
    const dir = join(LONG, "templates");
    const block = (role: string, body: string, end = LF): string => `<!-- 角色:${role} -->${LF}${body}<!-- /角色 -->${end}`;
    put(dir, "worker.md", ["# {{名字}}（{{角色}}）", "", block("gate", `门禁的职责 {{名字}}{{名字}}${LF}`), block("audit", `审核的职责${LF}`),
      block("contract", `合同的职责${CR}${LF}第二行${CR}${LF}`), "共同的规则：协调人是 {{协调人}}，仓库 {{仓库}}", block("planner", "末尾的规划段", "")].join(LF));
    put(dir, "coordinator.md", `协调人 {{名字}}：{{未知}} 原样留着${LF}`);
    put(dir, "odd.md", `${block("Gate", "大写的角色名不算")}${block("gate", "跨两段")}${block("gate", "第二段")}`);
    const values = dict(["名字", "gate-sonnet"], ["角色", "门禁端 $& $1 $$"], ["协调人", COORDINATOR], ["仓库", "{{名字}}"]);
    const extra = { template_dir: dir };
    agree([
      ...["gate", "audit", "contract", "planner", "nobody", null].map((role) => call("render_template", ["worker.md", values, role], extra)),
      call("render_template", ["coordinator.md", values, null], extra), call("render_template", ["odd.md", values, "gate"], extra),
      ...[...Object.keys(ROSTER)].map((agent) => call("role_prompt", [agent], { ...extra, kernel_root: kernelRepo("plain", `# AGENTS${LF}`) })),
    ]);
  });

  it("模板读不到（文件在但是空的、文件不在）：重读 TEMPLATE_READ_TRIES 次之后报 HubError，带模板的路径", () => {
    const dir = join(LONG, "templates-empty");
    put(dir, "worker.md", "");
    const results = agree([call("render_template", ["worker.md", dict(), null], { template_dir: dir }), call("render_template", ["gone.md", dict(), null], { template_dir: dir })], 0);
    expect(results.map((result) => result["error"])).toEqual(["HubError", "HubError"]);
  });

  it("模板正被替换（第 26 轮）：第一次读到空文件，0.3 秒后有了内容，重读拿到的是新内容", () => {
    const dir = join(LONG, "templates-replaced");
    const file = join(dir, "worker.md");
    const mark = join(dir, "started");
    const shown = IMPLS.map((impl) => {
      put(dir, "worker.md", "");
      rmSync(mark, { force: true });
      // 另起一个进程，等探针写下“开始了”的标记再过 0.3 秒写上内容：第一次读一定是空的，重读第二次之前有了内容
      // （探针是同步跑的，这个进程里的计时器等不到；不等标记的话，探针起得慢，第一次读就已经有内容了）
      const writer = `const fs = require("fs"); const wait = () => fs.existsSync(${JSON.stringify(mark)}) ? setTimeout(() => fs.writeFileSync(${JSON.stringify(file)}, "替换之后的 {{名字}}"), 300) : setTimeout(wait, 10); wait();`;
      spawn(process.execPath, ["-e", writer], { stdio: "ignore" });
      return runProbe(impl, call("render_template", ["worker.md", dict(["名字", "x"]), null], { template_dir: dir, started: mark }));
    });
    expect(shown.map((result) => (result.ok ? valueOf(result) : result))).toEqual(IMPLS.map(() => "替换之后的 x"));
  });

  it("内核仓库两边设同一个值：取已提交的“通用工程要求”一节；在文件末尾、标题后没有换行、不是仓库时报 HubError", () => {
    const rules = `${ENGINEERING_HEADING}${LF}${LF}- 测试测真实实现。${LF}- 少用 mock。${LF}`;
    const kernels = [
      kernelRepo("middle", `# AGENTS${LF}${LF}## 角色判定${LF}${LF}- 略${LF}${LF}${rules}${LF}## 规划端${LF}${LF}- 只给规划端${LF}`),
      kernelRepo("last", `# AGENTS${LF}${LF}${rules}`),
      kernelRepo("no-newline", `# AGENTS${LF}${LF}${ENGINEERING_HEADING}`),
      kernelRepo("crlf", `# AGENTS${CR}${LF}${CR}${LF}${ENGINEERING_HEADING}${CR}${LF}${CR}${LF}- 一条${CR}${LF}`),
    ];
    const plain = join(LONG, "not-a-repo");
    mkdirSync(plain, { recursive: true });
    const requests = [...kernels, plain].flatMap((kernel) => [
      call("engineering_rules", [], { kernel_root: kernel }),
      ...["contract-glm", "gate-sonnet", "audit-sonnet", "planner-opus", COORDINATOR].map((agent) => call("role_prompt", [agent], { kernel_root: kernel })),
    ]);
    const results = agree(requests, 0.4);
    expect(results.filter((result) => result["error"] === "HubError").length).toBeGreaterThanOrEqual(8);
  });

  it("worker_env：去掉决策 API 的 key、宿主会话变量与配置的 env_remove（只比名字，环境里的值是假的）", () => {
    const fake: Record<string, string> = {
      TYPESAFE_API_KEY: "fake-value", CLAUDECODE: "1", CLAUDE_CODE_ENTRYPOINT: "cli", CLAUDE_CODE_SSE_PORT: "1", THEMIS_TEST_DROP: "x", THEMIS_TEST_KEEP: "y",
    };
    const saved = Object.fromEntries(Object.keys(fake).map((name) => [name, process.env[name]]));
    Object.assign(process.env, fake);
    try {
      const results = agree([call("worker_env", [null]), call("worker_env", [dict()]), call("worker_env", [dict(["env_remove", ["THEMIS_TEST_DROP"]])])]);
      const names = valueOf(results[2]) as string[];
      expect(names).toContain("THEMIS_TEST_KEEP");
      expect(names.filter((name) => ["TYPESAFE_API_KEY", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "THEMIS_TEST_DROP"].includes(name))).toEqual([]);
    } finally {
      for (const [name, value] of Object.entries(saved)) {
        if (value === undefined) delete process.env[name];
        else process.env[name] = value;
      }
    }
  });
});

// --- 三、过渡断言 ---------------------------------------------------------------------------------------------

/** 一个带过渡断言的工作区：门禁测试里的 test_transitional_*，前端测试里标题带“（过渡）”的用例。 */
function transitionalWorkspace(name: string, oddDir = true): string {
  const root = join(LONG, name);
  put(root, "tests/test_gate_t001_a.py", [
    "def test_transitional_one():", `    ${DQ.repeat(3)}还没有字体文件${DQ.repeat(3)}`, "    assert True", "",
    "def test_transitional_two(tmp_path,", "                          monkeypatch) -> None:", "    r'''原始串的说明'''", "",
    "def test_transitional_three():  # 没有说明", "    pass", "",
    `${TAB}def test_transitional_tab(x): u${DQ.repeat(3)}同一行的不算说明${DQ.repeat(3)}`, "",
    "def test_transitional_four():", `    ${DQ}单个引号不算${DQ}`, "",
    "def test_transitional_ünï():", `    R${DQ.repeat(3)}  "带引号的说明" ${DQ.repeat(3)}`, "",
    "def test_transitional_five():   ", `${TAB}  U'''   '''`, "",
    // 说明以空白加引号开头：前缀认错时多留下的那个引号挡在空白前面，去引号时去不掉
    "def test_transitional_six():", `    u${DQ.repeat(3)} '带引号' ${DQ.repeat(3)}`, "",
    "def test_not_transitional():", "    pass", "",
  ].join(LF));
  put(root, "tests/test_gate_t002_b.py", `def test_transitional_crlf():${CR}${LF}    ${DQ.repeat(3)}CRLF 的说明${DQ.repeat(3)}${CR}${LF}`);
  put(root, "tests/other_test.py", ["def test_transitional_ignored():", "    pass", ""].join(LF));
  const specials = [C(0xfeff), C(0x1c), C(0x1d), C(0x1e), C(0x1f), C(0x85), C(0x2028), C(0x2029), "É", "ж"];
  put(root, "desktop/web/tests/a.test.tsx", [
    `describe(${DQ}分组（过渡）${DQ}, () => {`,
    `  it('单引号的（过渡）标题', () => {});`,
    `  test.only(${BT}反引号（过渡）${BT}, () => {});`,
    `  it.skip.each(${DQ}链式调用（过渡）${DQ})`,
    `  it(${DQ}没有标记${DQ}, () => {});`,
    `  it(${DQ}引号里有'别的'引号（过渡）${DQ}, () => {});`,
    `  it(${DQ}没闭合的（过渡）`,
    `  describe (${DQ}括号前有空格（过渡）${DQ})`,
    ...specials.map((char, index) => `${index % 2 ? TAB : " "}it(${char}${DQ}特殊字符 ${char} 在标题里（过渡）${char}${DQ})`),
    ...specials.map((char) => `it(${DQ}标题里 ${char}（过渡）${DQ})`),
  ].join(LF));
  put(root, "desktop/web/tests/sub/deep/b.test.ts", `${LF}${LF}test(${BT}深处的（过渡）${BT})${LF}`);
  put(root, "desktop/web/tests/c.test.tsx.bak", `it('备份文件也算（过渡）')${LF}`);
  put(root, "desktop/web/tests/plain.ts", `it('名字不像测试（过渡）')${LF}`);
  // 名字像测试文件的目录：Python 的 read_text 读它撞上 PermissionError、按共享冲突重试好几次才交回空串（TS 当场交回空串），
  // 结果一样；回合输入那一节一个状态就要读一次，不放
  if (oddDir) mkdirSync(join(root, "desktop", "web", "tests", "d.test.ts"), { recursive: true });
  return root;
}

describe("第 ⑤d1 片：过渡断言（门禁测试与前端测试，E6）", () => {
  it("生成的门禁测试与前端测试：用例名、说明行、标题与行号逐字相同；没有测试目录时是空的", () => {
    const results = agree([call("transitional_section", [transitionalWorkspace("trans")]), call("transitional_section", [join(LONG, "nothing")])]);
    const lines = valueOf(results[0]) as string[];
    expect(lines.filter((item) => item.startsWith("- " + BT)).length).toBeGreaterThan(15);
  });
});

// --- 四、按种子生成的回合输入 ---------------------------------------------------------------------------------------

interface PromptRepo {
  readonly repo: string;
  readonly head: string;
  readonly workspace: string;
  readonly inputs: string;
}

/** 回合输入用的临时仓库：门禁基准（自己的、别的片的、Unicode 数字的）、任务书与 state.md、runs 证据。 */
function promptRepo(): PromptRepo {
  const digits = C(0x0661, 0x0662);
  const { repo, head } = newRepo("prompt-repo", {
    "tests/test_gate_t001_baseline.py": "x = 1", "tests/test_gate_t024_baseline.py": "x = 1", "tests/test_gate_t7_baseline.py": "x = 1",
    [`tests/test_gate_t${digits}_baseline.py`]: "x = 1", "tests/test_gate_t001_whitebox.py": "x = 1", "tests/other.py": "x = 1",
  });
  for (const task of ["T001", "T024", "T1000"]) {
    put(repo, `.agent/mailbox/tasks/${task}/brief.md`, `# 站主的任务书 ${task}${LF}做 X${LF}`);
    for (const [index, suffix] of STAGE_ORDER.entries()) {
      if (index % 2 === 0) put(repo, `.agent/mailbox/tasks/${task}-${suffix}/brief.md`, `# 任务书 ${suffix}${LF}${FACE}${LF}`);
      if (index % 3 === 0) put(repo, `.agent/mailbox/tasks/${task}-${suffix}/state.md`, `# 断点${LF}做到第 ${index} 步${LF}`);
    }
  }
  const runs = ".agent/runs/t001-desktop-ui";
  put(repo, `${runs}/attempt-001/claim/x`, "");
  put(repo, `${runs}/attempt-001/run.json`, `{"wall_seconds": 12.7}`);
  put(repo, `${runs}/attempt-002/claim/reservation.json`, `{"timeout_seconds": 600}`);
  put(repo, `${runs}/attempt-003/run.json`, `{"wall_seconds": 99}`);
  put(repo, `${runs}/attempt-x/claim/x`, "");
  put(repo, ".agent/runs/_shadow/latest.json", "{}");
  return { repo, head, workspace: transitionalWorkspace("prompt-ws", false), inputs: join(LONG, "inputs", "T001-x") };
}

function promptKit(seed: number, where: PromptRepo) {
  const rnd = prng(seed);
  const kit = taskStateKit(rnd, where.repo);
  const { pick, maybe, hex } = kit;
  const odd = <T>(items: readonly T[], strange: PyValue): PyValue => (maybe(0.08) ? strange : (pick(items) as PyValue));
  const state = (): PyDict => {
    const ts = kit.state();
    if (maybe(0.5)) ts.set("base_head", where.head);
    for (const [, record] of ts.get("stages") as PyDict) {
      if (maybe(0.15)) (record as PyDict).set("timed_out", maybe(0.8));
      if (maybe(0.1)) (record as PyDict).set("owner_text", dict(["msg", `m${hex(4)}`], ["text", odd(["只改 6 处", `两行${LF}原话`], 5n)]));
    }
    if (maybe(0.3)) {
      ts.set("routed", Array.from({ length: 1 + Math.floor(rnd() * 2) }, () => dict(["at", "2026-10-31T00:00:00Z"],
        ["moves", odd([["开工 → planner-opus（T001-1-plan）"], [], ["a", "b"]], [3n])], ["letters", pick<PyValue>([["m1.md"], ["m1.md", "m2.md"], []])])));
    }
    if (maybe(0.3)) ts.set("decisions", [dict(["msg", "m9"], ["text", odd(["Q1：用 A", `多行${LF}决定`], 4n)])]);
    if (maybe(0.3)) {
      ts.set("hotfix", dict(["claims", odd([[], ["测试 X 错了"], ["a", "b"]], [5n])],
        ["run_dir", pick<PyValue>([`${where.repo}/.agent/runs/t1/attempt-001`, "", null, "D:/x/attempt-002"])]));
    }
    const gatePost = ts.get("gate_post") as PyDict;
    if (maybe(0.4)) gatePost.set("whitebox_file", pick<PyValue>(["tests/test_gate_t001_whitebox.py", `${where.repo}/tests/x.py`]));
    if (maybe(0.4)) gatePost.set("mutate_record", ".agent/mailbox/tasks/T001-6-gate-post/mutate.json");
    if (maybe(0.4)) gatePost.set("whitebox_log", pick<PyValue>(["", ".agent/x.log", null]));
    if (maybe(0.5)) gatePost.set("defects", odd([[], [dict(["test", "test_a"], ["where", "src/a.ts:3"], ["contract", "要 X"])]], ["d1"]));
    for (const key of ["equivalent", "expect_missed", "unmutated"]) if (maybe(0.3)) gatePost.set(key, odd([[], ["M1：等价"], ["a", "b"]], [1n]));
    if (maybe(0.3)) gatePost.set("mutate_spec", pick<PyValue>([`${where.repo}/.agent/mailbox/tasks/T001-6-gate-post/mutation-spec.json`, ".agent/x.json"]));
    if (maybe(0.4)) {
      (ts.get("workspaces") as PyDict).set(pick(["post-attempt-001", "post-", "post-attempt-002"]), dict(["whitebox_seeded", pick<PyValue>(["tests/w.py", "", null])]));
    }
    if (maybe(0.4)) {
      const facts = dict(["items", pick<PyValue>([[], [dict(["fact", "库 X 有 Y"], ["source", pick<PyValue>(["官网", "", null])], ["verified", pick<PyValue>(["未核实", "npm view 看过", null])])]])]);
      if (maybe()) facts.set("checked_at", "2026-10-31T00:00:00Z").set("checked", pick<PyValue>([["f1"], [], null])).set("checked_msg", pick<PyValue>(["m7", null]));
      ts.set("external_facts", facts);
    }
    if (maybe(0.4)) {
      ts.set("audit_history", Array.from({ length: 1 + Math.floor(rnd() * 3) }, () => dict(["stage", pick(["4-audit-pre", "7-audit-post"])],
        ["verdict", pick(["通过", "返工"])], ["blockers", pick<PyValue>(["1. 改 X", "", null])])));
    }
    const contract = ts.get("contract") as PyDict;
    if (maybe(0.6)) contract.set("version", pick<PyValue>([1n, 3n, "2", 2.7, null, 0n, true]));
    if (maybe(0.4)) contract.set("dispatched", maybe());
    return ts;
  };
  const letter = (): string => ["---", "msg-id: m1", `from: ${pick([OWNER, "planner-opus"])}`, `to: ${COORDINATOR}`, "task-id: T001", "in-reply-to: none",
    `type: ${pick(["任务", "交付", "任务书"])}`, "---", "摘要: 做 X", ""].join(LF);
  const requests = (ts: PyDict): ProbeRequest[] => {
    const task = String(ts.get("task"));
    return Object.keys(ROSTER).map((agent) => {
      const own = STAGE_ORDER.filter((suffix) => STAGE_WORKER[suffix] === agent);
      const taskId = agent === COORDINATOR ? task : maybe(0.85) && own.length ? `${task}-${pick(own)}` : pick([task, `${task}-4-audit-pre`, `${task}-${pick(STAGE_ORDER)}`]);
      const resume = pick<PyValue>([null, null, dict(["routing", true]), dict(["session", "s1"], ["turn", "turn-1"]), dict(["turn", "turn-2"]), dict()]);
      return call("turn_prompt", [where.repo, ts, agent, taskId, Array.from({ length: Math.floor(rnd() * 3) }, letter), where.workspace,
        pick<PyValue>([null, "", "缺 report"]), maybe() ? where.inputs : null, resume, pick<PyValue>([null, "", "这一批有提问"])]);
    });
  };
  return { state, requests };
}

describe("第 ⑤d1 片：按种子生成的回合输入", () => {
  const where = promptRepo();
  it.each([1, 2, 3])("种子 %i：30 个主任务状态 × 全部岗位 × 输入目录、续接、报错与代办说明", (seed) => {
    const kit = promptKit(seed, where);
    agree(Array.from({ length: 30 }, () => kit.requests(kit.state())).flat(), 0.6);
  }, 600_000);

  it("回合输入的小件：路径换到输入目录、回归测试、合同版本、预算、仓库外事实", () => {
    const { repo, head, inputs } = where;
    const ts = (extra: [string, PyValue][] = []): PyDict => dict(["task", "T001"], ["base_head", head], ["contract_task", "t001-desktop-ui"], ...extra);
    agree([
      ...[join(repo, ".agent", "mailbox", "tasks", "T001", "brief.md"), repo, `${repo}/x/../../elsewhere`, "D:/other/x.md", "", "relative/x.md",
        repo.toLowerCase(), join(repo, ".."), `${repo}${C(0)}x`].flatMap((path) => [call("input_path", [repo, inputs, path]), call("input_path", [repo, null, path])]),
      call("regression_gates", [repo, ts()]), call("regression_gates", [repo, ts([["task", "T024"]])]), call("regression_gates", [repo, ts([["base_head", "deadbeef"]])]),
      ...[dict(), dict(["version", 2n]), dict(["version", 2n], ["validated", true]), dict(["version", "3"], ["dispatched", false]), dict(["version", 2.7], ["dispatched", true]),
        dict(["version", null]), dict(["version", "x"])].map((contract) => call("next_contract_version", [dict(["contract", contract])])),
      call("budget_usage", [repo, ts()]), call("budget_usage", [repo, ts([["contract_task", "none"]])]), call("budget_usage", [repo, ts([["contract_task", "_shadow"]])]),
      ...[null, dict(), dict(["items", []]), dict(["items", [dict(["fact", "f"], ["source", ""], ["verified", null])]], ["checked_at", "t"], ["checked", ["a", "b"]], ["checked_msg", "m"]),
        dict(["items", null], ["checked_at", ""]), ["列表"]].map((record) => call("external_facts_section", [dict(["external_facts", record as PyValue])])),
    ], 0.7);
  });
});

// --- 五、交差核对与写给协调人的信 ---------------------------------------------------------------------------------

const ROLES: string[] = readdirSync(SCHEMA_DIR).filter((name) => name.endsWith(".json")).map((name) => name.slice(0, -5));

describe("第 ⑤d1 片：交差核对与写给协调人的信", () => {
  it("每个岗位的 schema 复核交上来的参数；没交时的说明；内核读不到参数、pi 一条回复都没有的接口报错", () => {
    const rnd = prng(41);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
    const fill = (node: PyValue, depth = 0): PyValue => {
      const properties = (node as PyDict).get("properties");
      if (!(properties instanceof Map) || depth > 3) return pick<PyValue>(["无", "", "交付", "通过", 3n, FACE, null, ["a"], "x".repeat(70)]);
      return new Map([...properties].filter(() => rnd() < 0.9).map(([key, sub]) => [key as string, fill(sub, depth + 1)]));
    };
    expect(ROLES.length, "协调人与各工人岗位的 schema").toBeGreaterThanOrEqual(5);
    const requests: ProbeRequest[] = [];
    for (const role of [...ROLES, "nobody"]) {
      requests.push(call("delivered_output", [role, null]), call("delivery_problem", [role]), call("role_schema", [role]));
      const schema = ROLES.includes(role) ? (valueOf(runProbe(PYTHON, call("role_schema", [role]))) as PyDict) : dict();
      for (let index = 0; index < 6; index += 1) requests.push(call("delivered_output", [role, fill(schema)]));
    }
    for (const adapter of ["pi", "claude"]) {
      for (const audit of [dict(["delivered", null], ["delivered_unreadable", "details 不是对象"]), dict(["delivered_unreadable", ""]), dict(["models", []]), dict(["models", ["m"]]), dict()]) {
        for (const result of [dict(["exit_code", 1n]), dict(["exit_code", 0n]), dict(["exit_code", null]), dict(["exit_code", 2n], ["timed_out", true]), dict(["exit_code", false]), dict(["exit_code", 0]), dict()]) {
          requests.push(call("interface_problem", [dict(["adapter", adapter]), audit, result]));
        }
      }
    }
    agree(requests, 0.6);
  });

  it("交差工具的文件：原样、不在、被改过（载入时的哈希只取前 12 位）、不是交差工具的文件", () => {
    const changed = join(LONG, "changed", "deliver.ts");
    put(join(LONG, "changed"), "deliver.ts", "被改过的扩展");
    put(join(LONG, "changed"), "other.ts", "别的文件");
    agree([DELIVER_EXTENSION, GUARD_EXTENSION, changed, join(LONG, "changed", "gone.ts"), join(LONG, "changed", "other.ts")].map((path) => call("worker_file_problem", [path])), 0.2);
  });

  it("工人的输出折成信：信头、各字段去掉两头空白、结论三项有才加；letter 不是对象、值不是字符串", () => {
    const rnd = prng(43);
    const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
    const value = (): PyValue => pick<PyValue>(["  有空白  ", "", "无", FACE, 3n, null, ["列", "表"], `多行${LF}值`, 1.5, true]);
    const requests: ProbeRequest[] = [];
    for (let index = 0; index < 60; index += 1) {
      const letter = new Map<string, PyValue>([...["type", "in_reply_to", "摘要", "提交", "验证", "偏离", "需协调人决定", "证据", "结论", "退回", "阻塞项", "下游须知", "多余"]]
        .filter(() => rnd() < 0.7).map((key) => [key, value()]));
      const data = pick<PyValue>([dict(["letter", letter]), dict(["letter", "不是对象"]), dict(), dict(["letter", letter], ["report", "r"])]);
      requests.push(call("letter_from_output", [pick(Object.keys(ROSTER)), pick(["T001-1-plan", "T001", ""]), data]));
    }
    requests.push(call("letter_from_output", ["planner-opus", "T001", ["不是字典"]]));
    agree(requests, 0.8);
  });
});

