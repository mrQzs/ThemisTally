// 第 ⑤e2a 片的契约（迁移计划第 ⑤ 步）：内核调调度器，以及战前门禁里读工作区与基线记录的几处。kit_hub.py 的 workspace_status、
// contract_digest、hollow_baseline_problems、run_pd、kernel_env、kernel_pytest_env、KERNEL_PYTEST 交给 Python、Node、Bun，逐字比带标签的
// 结果（崩溃比类型；HubError 比文字与退出码）。语料：
//   - tests/test_kit_hub.py 里调到这三个函数的 24 条用例：Python 探针记下顶层调用与调用当时的快照（带 .git；工作区是仓库外的
//     worktree 时连主仓库一起），三边先原地放回快照再重放，每一条都要与当时的结果相同；
//   - 临时仓库上的手写对照：git status 的各种状态（嵌套的未跟踪目录、带空格与非 ASCII 的名字、删除、修改、忽略、暂存的改名，旧路径
//     长短各一）与仓库外的 worktree；合同两个文件在与不在；基线检查记录的每个分支（记录行的写法、记录与日志的各种坏法、
//     pytest 的退出码与计数）；
//   - 真调度器上的 run_pd（经启动器，选择文件照常）：交回的文字与账本新增的一行；选择文件坏了时账本记 invalid；时限到了交回 124、
//     不记账本。Python 在 Windows 上超时后还要等握着管道的孙进程退出，TS 经 runSupervised 结束整棵树、按时交回：那种挂住的情形不比
//     （迁移计划第 10 节）。
import { createHash } from "node:crypto";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { TOOL_VERSION } from "@themis/dispatcher/prepare";
import { kernelPytest } from "@themis/hub/runpd";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";
import { git, newRepo, put, removeCreated, tempDir } from "./repo-fixtures.ts";

const C = (...codes: number[]): string => String.fromCodePoint(...codes);
const LF = C(10);
const CR = C(13);
const ROOT = scratchDir("contract-gate");
afterAll(() => {
  removeDir(ROOT);
  removeCreated();
});

function py(value: unknown): PyValue {
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "bigint") return value;
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(py);
  if (value instanceof Map) return value as PyDict;
  return new Map(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, py(item)]));
}
const call = (fn: string, args: readonly unknown[], extra: Record<string, unknown> = {}): ProbeRequest => ({ op: "hub.contract", fn, args: args.map((arg) => toTagged(py(arg))), ...extra });
const valueOf = (result: ProbeResult | undefined): PyValue => fromTagged(result?.["value"] as Tagged);

/** 三边各跑一遍、逐个比；交回 Python 的结果。okShare：至少这一份比例的请求要正常交回。 */
function agree(requests: readonly ProbeRequest[], okShare = 0.5): ProbeResult[] {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests, REPLAY_TIMEOUT));
  for (const [index, other] of others.entries()) {
    const bad = requests.map((_, at) => at).filter((at) => JSON.stringify(python?.[at]) !== JSON.stringify(other[at]));
    const shown = bad.slice(0, 3).map((at) => ({ at, fn: requests[at]?.["fn"], args: requests[at]?.["args"], python: python?.[at], other: other[at] }));
    expect(shown, `${IMPLS[index + 1]?.name} 与 Python 不同（共 ${bad.length} 处）`).toEqual([]);
  }
  const ok = (python ?? []).filter((result) => result.ok).length;
  expect(ok, JSON.stringify((python ?? []).filter((result) => !result.ok).slice(0, 3))).toBeGreaterThanOrEqual(Math.ceil(requests.length * okShare));
  return python as ProbeResult[];
}

// --- 一、pytest 的场景 -----------------------------------------------------------------------------------------

const TESTS = [
  "test_a_cut_off_attempt_is_continued_instead_of_restarted", "test_a_finished_attempt_whose_checks_failed_is_continued_instead_of_restarted",
  "test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline", "test_a_hotfix_gate_redelivery_keeps_the_version_and_the_original_baseline",
  "test_a_timed_out_attempt_is_continued_instead_of_restarted", "test_an_unchanged_timed_out_attempt_keeps_the_same_rework_base",
  "test_an_unsent_contract_gets_the_rostered_executor_before_dispatch", "test_contract_title_is_the_registered_task_title",
  "test_exec_rework_continues_from_the_reviewed_candidate", "test_finished_tasks_remove_their_stage_worktrees",
  "test_gate_post_checks_the_anchors_before_mutating", "test_gate_post_judges_mutations_from_the_record",
  "test_gate_post_may_leave_the_candidate_red_with_evidence", "test_gate_post_reads_the_spec_file_and_names_entries_left_unchanged",
  "test_gate_pre_baseline_must_fail_on_assertions", "test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff",
  "test_gate_pre_rejects_a_baseline_that_does_not_collect", "test_gate_rework_resets_a_worktree_the_state_lost_track_of",
  "test_kernel_writes_the_contract_version_and_base_it_assigns", "test_owner_raises_the_attempt_budget",
  "test_post_gate_worktree_starts_from_the_attempt_base", "test_retry_after_failed_checks_tells_the_executor_why",
  "test_rework_contract_lets_the_executor_modify_files_added_earlier", "test_unsent_contracts_get_the_rostered_executor_line",
];
const FUNCTIONS = ["workspace_status", "contract_digest", "hollow_baseline_problems"];

describe("第 ⑤e2a 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("记到的顶层调用放回调用当时的快照后三边重放逐字相同，也与当时的结果相同；每个函数都有样本", () => {
    const tmp = join(ROOT, "samples");
    mkdirSync(tmp, { recursive: true });
    const recorded = runProbe(PYTHON, { op: "hub.audit_samples", tests: TESTS, functions: FUNCTIONS, snapshot_functions: FUNCTIONS, tmp }, 600_000);
    expect(recorded.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
    const value = valueOf(recorded) as PyDict;
    expect(value.get("skipped")).toEqual([]);
    const calls = (value.get("calls") as PyDict[]).map((item) => ({
      test: item.get("test") as string, fn: item.get("fn") as string, args: item.get("args") as PyValue[], result: item.get("result") as string,
      restores: item.get("restores") as string,
    }));
    const python = agree(calls.map((item) => ({ op: "hub.contract", fn: item.fn, args: item.args.map(toTagged), restores: JSON.parse(item.restores) })), 0.8);
    const drifted = calls.filter((item, at) => JSON.stringify(JSON.parse(item.result)) !== JSON.stringify(python[at])).map((item) => item.test);
    expect([...new Set(drifted)].sort(), "当时的结果与 Python 重放").toEqual([]);
    expect(FUNCTIONS.filter((fn) => !calls.some((item) => item.fn === fn)), "没有顶层调用").toEqual([]);
  }, 600_000);
});

// --- 二、临时仓库上的手写对照 ------------------------------------------------------------------------------------

describe("第 ⑤e2a 片：临时仓库上的手写对照", () => {
  it("workspace_status：各种状态；暂存的改名照抄 Python 的毛病（旧路径前两个字符当状态，不超过 3 个字符的整项丢掉）；仓库外的 worktree；不是仓库与不存在的目录", () => {
    const { repo } = newRepo("gate-status", {
      "a b.txt": `空格${LF}`, "中文/名字.md": `名字${LF}`, "keep.txt": `留着${LF}`, "both.txt": `一${LF}`,
      "long-old-name.txt": `长的旧名${LF}`, "ab": `两个字符${LF}`, "abc": `三个字符${LF}`, "abcd": `四个字符${LF}`,
    });
    // 请求到 agree 时才跑：干净的那一次要在改动之前单独跑
    expect(valueOf(agree([call("workspace_status", [repo])], 1)[0])).toEqual([]);
    put(repo, "new/deep/x.txt", `x${LF}`);
    put(repo, "new/y.txt", `y${LF}`);
    put(repo, "中文/新 的.md", `新${LF}`);
    put(repo, "a b.txt", `改过${LF}`);
    rmSync(join(repo, "keep.txt"));
    put(repo, ".agent/runs/z.log", `忽略${LF}`);
    put(repo, "staged.txt", `暂存${LF}`);
    git(repo, "add", "staged.txt");
    put(repo, "both.txt", `二${LF}`);
    git(repo, "add", "both.txt");
    put(repo, "both.txt", `三${LF}`);
    for (const [from, to] of [["long-old-name.txt", "renamed.txt"], ["ab", "ab-new"], ["abc", "abc-new"], ["abcd", "abcd-new"]]) git(repo, "mv", from as string, to as string);
    const worktree = join(tempDir("gate-wt"), "wt");
    git(repo, "worktree", "add", "-q", worktree, "-b", "side");
    put(worktree, "src/a.ts", `export const a = 2;${LF}`);
    put(worktree, "新文件.txt", `新${LF}`);
    const plain = tempDir("gate-plain");
    const results = agree([repo, worktree, plain, join(plain, "没有")].map((path) => call("workspace_status", [path])), 0.5);
    expect(valueOf(results[0])).toEqual([
      [" M", "a b.txt"], ["R ", "ab-new"], ["R ", "abc-new"], ["R ", "abcd-new"], ["ab", "d"], ["MM", "both.txt"], [" D", "keep.txt"], ["R ", "renamed.txt"],
      ["lo", "g-old-name.txt"], ["A ", "staged.txt"], ["??", "new/deep/x.txt"], ["??", "new/y.txt"], ["??", "中文/新 的.md"],
    ]);
    expect(valueOf(results[1])).toEqual([[" M", "src/a.ts"], ["??", "新文件.txt"]]);
    expect(results.slice(2).map((result) => result["error"])).toEqual(["HubError", "NotADirectoryError"]);
  });

  it("contract_digest：md 与 json 都在、只有一个、都不在（两个空串连起来的 sha256）、md 的位置是目录", () => {
    const repo = tempDir("gate-digest");
    put(repo, ".agent/plans/t001-doc.v1.md", `# TASK${LF}`);
    put(repo, ".agent/plans/t001-doc.v1.json", "{}");
    put(repo, ".agent/plans/t001-doc.v2.md", `# TASK${LF}`);
    put(repo, ".agent/plans/t001-doc.v3.json", "{}");
    mkdirSync(join(repo, ".agent/plans/t001-doc.v5.md"));
    put(repo, ".agent/plans/t001-doc.v5.json", "{}");
    const ts = (n: number): Record<string, unknown> => ({ contract: { key: `t001-doc.v${n}` } });
    const results = agree([1, 2, 3, 4, 5].map((n) => call("contract_digest", [repo, ts(n)])), 1);
    const sha = (text: string): string => createHash("sha256").update(text, "utf8").digest("hex");
    expect(valueOf(results[0])).toBe(sha(sha(`# TASK${LF}`) + sha("{}")));
    expect(valueOf(results[3])).toBe(sha(""));
    expect(valueOf(results[4])).toBe(valueOf(results[2]));
  });

  it("hollow_baseline_problems：记录行的写法、记录与日志的各种坏法、pytest 的退出码与计数", () => {
    const repo = tempDir("gate-hollow");
    const GATE = "tests/test_gate_t001_baseline.py";
    let n = 0;
    /** 写一份检查记录（字符串或字节原样写，别的转成 JSON），交回它的相对路径。 */
    const record = (content: unknown): string => {
      n += 1;
      const rel = `.agent/runs/t001-doc/baseline/${String(n).padStart(2, "0")}/checks.json`;
      put(repo, rel, typeof content === "string" || content instanceof Uint8Array ? content : JSON.stringify(content));
      return rel;
    };
    const line = (rel: string): string => `基线检查记录：${rel}`;
    const gate = (item: Record<string, unknown>): Record<string, unknown> => ({ id: "V01", argv: ["python", "-m", "pytest", GATE, "-q"], exit_code: 1, ...item });
    put(repo, ".agent/runs/t001-doc/baseline/logs/errors.log", `=== 1 failed, 2 errors in 0.12s ===${LF}`);
    put(repo, ".agent/runs/t001-doc/baseline/logs/passed.log", `=== 3 passed in 0.10s ===${LF}`);
    put(repo, ".agent/runs/t001-doc/baseline/logs/failed.log", `=== 2 failed in 0.10s ===${LF}`);
    put(repo, ".agent/runs/t001-doc/baseline/logs/empty.log", "");
    const ok = record({ results: [gate({ log: "logs/failed.log" })] });
    const hollow = (out: string, expected: unknown = GATE): ProbeRequest => call("hollow_baseline_problems", [repo, out, expected]);
    const requests = [
      // 记录行：没有、行首之外、只有空白、行尾的空白（含 Python 的空白类里的 U+001F 与全角空格）、CRLF、第二行、两行取第一行、绝对路径
      hollow(""), hollow(`前缀${line(ok)}`), hollow(`基线检查记录：   ${LF}`), hollow(`${line(ok)}   ${C(0x1f)}${C(0x3000)}`),
      hollow(`前一行${CR}${LF}${line(ok)}${CR}${LF}下一行`), hollow(`前一行${LF}${line(ok)}${LF}`), hollow(`${line(record({ results: [] }))}${LF}${line(ok)}`),
      hollow(line(join(repo, ok))),
      // 记录：不在、是目录、空文件、results 为 null、不是 JSON、顶层是列表、带 BOM、坏的 UTF-8、results 是字典、条目不是字典
      hollow(line(".agent/runs/没有.json")), hollow(line(".agent/runs/t001-doc")), hollow(line(record(""))), hollow(line(record({ results: null }))),
      hollow(line(record("{"))), hollow(line(record("[]"))), hollow(line(record(new Uint8Array([0xef, 0xbb, 0xbf, 0x7b, 0x7d])))),
      hollow(line(record(new Uint8Array([0x7b, 0xff, 0x7d])))), hollow(line(record({ results: { a: 1 } }))), hollow(line(record({ results: ["x"] }))),
      // 门禁检查：没有、argv 跨两个参数、argv 里有数字、expected 不是字符串（有条目时 TypeError，没有时照样报“没有跑”）
      hollow(line(record({ results: [{ id: "V02", argv: ["python", "-m", "pytest", "tests/other.py"] }] }))),
      hollow(line(record({ results: [gate({ argv: ["-m", "pytest", GATE], log: "logs/passed.log" })] })), `pytest ${GATE}`),
      hollow(line(record({ results: [gate({ argv: [1, 2, GATE], log: "logs/passed.log" })] }))),
      hollow(line(ok), 5), hollow(line(record({ results: [] })), 5),
      // 超时、中断、没起来（id 没写、是 0）；退出码 0、2–5、没写、字符串、1.0、true、2.0
      // 真实的记录里这几种的退出码是 null：报了这一条就不再接着报退出码
      hollow(line(record({ results: [gate({ timed_out: true, exit_code: null }), gate({ id: undefined, interrupted: true, exit_code: null }), gate({ id: 0, spawn_error: "起不来", exit_code: null })] }))),
      hollow(line(record({ results: [0, 2, 3, 4, 5, null, "1"].map((code) => gate({ exit_code: code })) }))),
      // 1.0 与 2.0 直接写成 JSON 文字（JSON.stringify 会把 1.0 写成 1）：Python 读到的是 float，1.0 等于 1、往下查日志，2.0 在消息里写成 2.0
      hollow(line(record(JSON.stringify({ results: [gate({ exit_code: "<F1>", log: "logs/passed.log" }), gate({ id: "V02", exit_code: true, log: "logs/passed.log" }), gate({ id: "V03", exit_code: "<F2>" })] })
        .replace(`"<F1>"`, "1.0").replace(`"<F2>"`, "2.0")))),
      // 日志：有 errors、没有 failed、有 failed、不在、空文件、没写（落到目录上）
      hollow(line(record({ results: [gate({ log: "logs/errors.log" }), gate({ id: "V02", log: "logs/passed.log" }), gate({ id: "V03", log: "logs/failed.log" })] }))),
      hollow(line(record({ results: [gate({ log: "logs/没有.log" }), gate({ id: "V02", log: "logs/empty.log" }), gate({ id: "V03" })] }))),
      // 条目不是字典、expected 也不是字符串：Python 先拼 argv（AttributeError），轮不到 in 报 TypeError
      hollow(line(record({ results: ["x"] })), 5),
    ];
    const results = agree(requests, 0.6);
    expect(valueOf(results[0])).toEqual(["baseline 没有留下检查记录，核对不了基准测试在基线上是怎样失败的"]);
    expect(results.slice(1, 8).map(valueOf), "记录行的几种写法都找到同一份记录").toEqual([valueOf(results[0]), valueOf(results[0]), [], [], [], ["baseline 的检查记录里没有跑 tests/test_gate_t001_baseline.py 的检查"], []]);
    expect(results.slice(8, 18).map((result) => result["error"] ?? valueOf(result))).toEqual([
      valueOf(results[0]), valueOf(results[0]), valueOf(results[6]), valueOf(results[6]), "JSONDecodeError", "AttributeError", "JSONDecodeError", "UnicodeDecodeError",
      "AttributeError", "AttributeError",
    ]);
    expect(results.slice(21, 23).map((result) => result["error"] ?? valueOf(result))).toEqual(["TypeError", ["baseline 的检查记录里没有跑 5 的检查"]]);
    expect(valueOf(results[23])).toEqual([
      "V01 在基线上超时或没有跑起来：卡住的测试也算“失败”，但什么也没证明", "? 在基线上超时或没有跑起来：卡住的测试也算“失败”，但什么也没证明",
      "? 在基线上超时或没有跑起来：卡住的测试也算“失败”，但什么也没证明",
    ]);
    expect((valueOf(results[24]) as string[]).map((text) => text.split("：")[0])).toEqual(["0", "2", "3", "4", "5", "None", "1"].map((code) => `V01 在基线上的 pytest 退出码是 ${code}`));
    expect(valueOf(results[25])).toEqual([
      "V01 在基线上没有失败的用例", "V02 在基线上没有失败的用例", "V03 在基线上的 pytest 退出码是 2.0：只有 1 是用例失败（2 中断、3 内部错误、4 用法错误、5 没有用例）",
    ]);
    expect(valueOf(results[26])).toEqual([
      "V01 在基线上有 2 个用例出错（setup 或夹具失败），不是断言失败：夹具在基线上做不成的事，把原因记下来，让用例断言它", "V02 在基线上没有失败的用例",
    ]);
    expect(valueOf(results[27])).toEqual([]);
    expect(results[28]?.["error"]).toBe("AttributeError");
  });
});

// --- 三、真调度器上的 run_pd 与内核的几份环境 -----------------------------------------------------------------------

describe("第 ⑤e2a 片：run_pd 与内核的环境", () => {
  it("没设内核用的 Python 时 KERNEL_PYTEST、run_pd 不猜，直接报错（TS 才有的设定）", () => {
    expect(() => kernelPytest()).toThrow("没有设定内核用的 Python");
  });

  it("run_pd：交回的文字（标准错误并进标准输出）与账本新增的一行逐字相同；选择文件坏了记 invalid、hub 仓库里的选择文件不看；时限到了交回 124、不记账本", () => {
    const python = (valueOf(runProbe(PYTHON, call("kernel_pytest", []))) as string[])[0] as string;
    const { repo } = newRepo("gate-runpd");
    // hub 管的仓库里放一份坏的选择文件：账本记的是内核自己的选择（待办第 26 项），误读成这一份就成了 invalid
    const { repo: other } = newRepo("gate-runpd-impl", { "scripts/kernel-impl.json": "{" });
    const broken = join(tempDir("gate-impl"), "kernel-impl.json");
    writeFileSync(broken, "{");
    const pd = (args: string[], timeout: number, extra: Record<string, unknown> = {}, at = repo): ProbeRequest => call("run_pd", [at, args, timeout], { python, ...extra });
    const results = agree([
      pd(["--version"], 600), pd(["没有这个命令"], 600), pd(["status"], 600), pd(["validate", "t001-doc.v1"], 600),
      pd(["--version"], 600, { impl_path: broken }), pd(["--version"], 0.01), pd(["--version"], 600, {}, other),
    ], 1);
    const [version, unknown, , , invalid, timedOut, kernelSelector] = results.map((result) => valueOf(result) as PyDict);
    const event = (value: PyDict | undefined): PyValue => (value?.get("events") as PyDict[])[0]?.get("impl") ?? null;
    const [code, out] = version?.get("result") as [bigint, string];
    expect([code, out.includes(TOOL_VERSION), event(version), (version?.get("events") as PyDict[])[0]?.get("tool_version")]).toEqual([0n, true, "python", TOOL_VERSION]);
    expect((unknown?.get("result") as PyValue[])[0], "用法错误").toBe(2n);
    expect([event(invalid), event(kernelSelector)]).toEqual(["invalid", "python"]);
    expect([timedOut?.get("result"), timedOut?.get("events")]).toEqual([[124n, "超时（0 秒）：--version"], []]);
  }, 120_000);

  it("kernel_env 照 os.environ（Windows 上名字是大写），只去掉决策 API 的 key（不分大小写）；kernel_pytest_env 是工人的环境加 PYTHONDONTWRITEBYTECODE；KERNEL_PYTEST 带 -p no:cacheprovider", () => {
    const python = (valueOf(runProbe(PYTHON, call("kernel_pytest", []))) as string[])[0] as string;
    // PYTHONDONTWRITEBYTECODE 先设成 0：外面（例如 mutate 起的命令）可能本来就有它，只比名字看不出 kernel_pytest_env 有没有改成 1。
    // 名字原样比：大小写混写的那个在 Windows 上要成大写，同 dict(os.environ)
    const env = { THEMIS_E2A_ENV: "1", Themis_E2a_Mixed: "1", TYPESAFE_API_KEY: "dummy", PYTHONDONTWRITEBYTECODE: "0" };
    const results = agree([
      call("kernel_env", [], { env }), call("kernel_env", [], { env: { typesafe_api_key: "dummy" } }), call("kernel_pytest_env", [], { env }),
      call("kernel_pytest", [], { python }),
    ], 1);
    const [kernel, lower, pytest, argv] = results.map(valueOf) as [[string[], string], [string[], string], [string[], string], string[]];
    const mixed = process.platform === "win32" ? "THEMIS_E2A_MIXED" : "Themis_E2a_Mixed";
    expect([kernel[0].includes("THEMIS_E2A_ENV"), kernel[0].includes(mixed), kernel[0].includes("TYPESAFE_API_KEY"), lower[0].includes("TYPESAFE_API_KEY"), kernel[1]])
      .toEqual([true, true, false, false, "0"]);
    expect([pytest[0].includes("TYPESAFE_API_KEY"), pytest[1]]).toEqual([false, "1"]);
    expect(argv).toEqual([python, "-m", "pytest", "-p", "no:cacheprovider"]);
  });
});
