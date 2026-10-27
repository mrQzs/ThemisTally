// check、baseline、verdict 的命令行契约（迁移第 ④b3 片）。每个场景按三份实现各建一份相同的仓库与 attempt（提交号相同；
// 工作树与临时副本的路径各不相同、换成占位符），跑同一条命令，比较退出码、输出、跑完之后的证据目录与登记的工作树数；
// 崩溃只比退出码。检查命令是真的子进程（python -c），wall_seconds、pid 与 mkdtemp 的随机后缀换成占位符。
// verdict 的场景按门禁逐项改证据，记录里整份 gates 都参与比较。不写转义序列。
import { spawnSync } from "node:child_process";
import { readFileSync, realpathSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { pythonCliCommand, tsCliCommand } from "./harness.ts";
import { FAIL, OK, PLATFORM, PYTHON, TS_CONTEXT, BREAK_INNER, BREAK_OUTER, fullAttempt, json, py, state, type AttemptOptions } from "./attempt-fixtures.ts";
import { jsonOf, mdOf } from "./plan-fixtures.ts";
import { CONTEXT, LF, RUNNERS, type Runner, type Shown, git, newRepo, normalize, put, removeCreated, runCommand, shownOf, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const BT = "`";
const CR = String.fromCharCode(13);

/** worktree_root 换成工作树旁边的 sub（④b3 补：建不出来时 Python 报 [WinError N]，照 os.mkdir）。 */
function rootBeside(repo: string, wt: string, parent: string): void {
  put(repo, ".agent/dispatch.config.json", json({ worktree_root: join(dirname(wt), parent, "sub"), kill_grace_seconds: 1 }));
}

/** 色码（CSI）与超链接（OSC，BEL 结尾与 ESC 反斜杠结尾各一处）。 */
const ANSI_CODE = [
  "E = chr(27)",
  "print(E + '[32mPASSED' + E + '[0m')",
  "print(E + ']8;;http://x' + chr(7) + 'link' + E + ']8;;' + chr(7))",
  "print(E + ']0;title' + E + chr(92) + 'tail')",
  "print(E + '[3 qcursor')",
].join("; ");

interface Scenario {
  readonly label: string;
  readonly build: (repo: string, head: string, runner: Runner) => Record<string, string>;
  readonly argv: readonly string[];
  readonly args: Record<string, unknown>;
  readonly status: number;
  readonly crash?: boolean;
  /** 输出里必须有的文字：证明走到了要测的分支。 */
  readonly text?: string | undefined;
  readonly files?: Record<string, string>;
}

interface CheckFlags {
  readonly only?: string;
  readonly fresh?: boolean;
  readonly keep?: boolean;
}

const check = (label: string, o: AttemptOptions, flags: CheckFlags, status: number, text?: string, crash = false): Scenario => ({
  label,
  build: (repo, head, runner) => fullAttempt(repo, head, runner, o),
  argv: ["check", "t1", ...(flags.only !== undefined ? ["--only", flags.only] : []), ...(flags.fresh ? ["--fresh"] : []), ...(flags.keep ? ["--keep-workspace"] : [])],
  args: { command: ["check"], run_dir: "t1", only: flags.only ?? null, fresh: flags.fresh ?? false, keep_workspace: flags.keep ?? false, context: TS_CONTEXT },
  status,
  text,
  crash,
});

interface VerdictFlags {
  readonly verdict: string;
  readonly review?: string;
  readonly failureClass?: string;
  readonly waive?: readonly string[];
  readonly decidedBy?: string;
  readonly note?: string;
}

const verdict = (label: string, o: AttemptOptions, flags: VerdictFlags, status: number, text?: string, crash = false): Scenario => ({
  label,
  build: (repo, head, runner) => fullAttempt(repo, head, runner, { review: `# 复审${LF}${LF}Verdict: ${flags.verdict}${LF}`, ...o }),
  argv: [
    "verdict", "t1", "--verdict", flags.verdict, "--review", flags.review ?? "review.md",
    ...(flags.failureClass ? ["--class", flags.failureClass] : []), ...(flags.waive ?? []).flatMap((item) => ["--waive", item]),
    ...(flags.decidedBy ? ["--decided-by", flags.decidedBy] : []), "--human-minutes", "1.5", ...(flags.note ? ["--note", flags.note] : []),
  ],
  args: {
    command: ["verdict"], run_dir: "t1", verdict: flags.verdict, review: flags.review ?? "review.md", failure_class: flags.failureClass ?? null,
    waive: flags.waive ? [...flags.waive] : null, decided_by: flags.decidedBy ?? null, human_minutes: 1.5, note: flags.note ?? null, context: TS_CONTEXT,
  },
  status,
  text,
  crash,
});

/** REVISE 加 --class：总会记下结论，记录里有整份 gates（按门禁改证据的场景用它）。 */
const gates = (label: string, o: AttemptOptions, text?: string): Scenario =>
  verdict(label, o, { verdict: "REVISE", failureClass: "EXECUTION_ERROR" }, 0, text);

const CHECKS: Scenario[] = [
  check("原地检查通过", {}, {}, 0, "检查结果（in_place）：全部必要检查通过"),
  check("退出码不对", { checks: [FAIL()] }, {}, 1, "CHECK V01 failed 退出码 1 ≠ 期望 0"),
  check("期望的退出码：1 与 True", { checks: [FAIL("V01", { expected_exit_code: 1 }), FAIL("V02", { expected_exit_code: true })] }, {}, 0, "CHECK V02 passed "),
  check("输出模式对着去掉色码之后的文本", {
    checks: [
      py("V01", ANSI_CODE, { output_must_match: ["^PASSED$", "^link$", "^tail$", "^cursor$"], output_must_not_match: ["^boom"] }),
      py("V02", ANSI_CODE, { output_must_match: ["^missing$", "passed"], output_must_not_match: ["PASSED", "^link"] }),
      // 一条命中一条没中：must 要全中，must_not 一条命中就算
      py("V03", ANSI_CODE, { output_must_match: ["^PASSED$", "^nope$"] }),
      py("V04", ANSI_CODE, { output_must_not_match: ["^zzz$", "PASSED"] }),
    ],
  }, {}, 1, "输出未匹配 ^missing$; 输出未匹配 passed; 输出命中禁止模式 PASSED; 输出命中禁止模式 ^link"),
  check("--only 选一项，没有覆盖全部必要检查", { checks: [OK(), FAIL("V02")] }, { only: " V01 ,," }, 0, "CHECK V01 passed"),
  check("--only 有未知的检查", { checks: [OK(), OK("V02")] }, { only: "V09,V01,V08" }, 2, "未知检查：V09, V08"),
  check("--only 只有逗号", {}, { only: ", ," }, 2, "合同没有可运行的检查"),
  check("合同没有检查", { checks: [] }, {}, 2, "合同没有可运行的检查"),
  check("状态不能检查", { files: { "state.json": state("RUNNING") } }, {}, 3, "状态 RUNNING 不能运行验收检查"),
  check("没有候选记录", { files: { "candidate.json": null } }, {}, 3, "没有候选记录（candidate.json）"),
  check("候选记录是列表", { files: { "candidate.json": [] } }, {}, 1, undefined, true),
  // 证据里 prepare 写的字符串字段被手改成别的类型：Python 在 Path()、git 参数、切片、%03d 上崩（④b3 补，themistally-15 复核 d14ea7c）
  check("证据类型不对：meta.worktree 是 null", { meta: { worktree: null } }, {}, 1, undefined, true),
  check("证据类型不对：meta.base_sha 是 null", { meta: { base_sha: null } }, {}, 1, undefined, true),
  check("证据类型不对：candidate.tree 是数字", { files: { "candidate.json": { tree: 123, patch_roundtrip_verified: true } } }, {}, 1, undefined, true),
  check("干净副本，证据类型不对：meta.base_sha 是数字", { meta: { base_sha: 7 } }, { fresh: true }, 1, undefined, true),
  check("干净副本，证据类型不对：meta.attempt_no 是 null", { meta: { attempt_no: null } }, { fresh: true }, 1, undefined, true),
  check("干净副本，证据类型不对：meta.task_id 是数字", { meta: { task_id: 5 } }, { fresh: true }, 1, undefined, true),
  check("干净副本：attempt_no 是 1.5、task_id 是列表，照 Python 写进副本的名字", { meta: { attempt_no: 1.5, task_id: ["t1"] } }, { fresh: true }, 0,
    "检查结果（fresh）"),
  check("检查项的 cwd 是 null", { checks: [OK("V01", { cwd: null })] }, {}, 1, undefined, true),
  check("工作树不在", { meta: { worktree: "Z:/no/such/worktree" } }, {}, 3, "worktree 已不存在：Z:"),
  check("工作树不在，attempt 在另一台机器上派遣", { meta: { worktree: "Z:/no/such/worktree", platform: "Linux-6.1.0-x86_64-with-glibc2.36" } }, {}, 3,
    "（attempt 不在本机派遣）；可用 --fresh"),
  check("另一处仓库派遣的提示", { meta: { repository: "D:/elsewhere/repo" } }, {}, 0, "NOTE  attempt 在另一处仓库派遣"),
  check("候选漂移：检查之前改了候选文件、多了新文件", {
    after: ({ wt }) => {
      put(wt, "src/a.ts", `export const a = 3;${LF}`);
      put(wt, "extra.txt", "x");
    },
  }, {}, 4, "工作副本与候选不一致"),
  check("检查改了候选文件", { checks: [py("V01", "open('src/a.ts', 'a').write('// x')")] }, {}, 1, "WARN  检查修改了候选文件：src/a.ts"),
  check("检查产生了新文件与缓存", {
    checks: [py("V01", "import os; open('junk.txt', 'w').write('x'); os.makedirs('__pycache__', exist_ok=True); open('__pycache__/m.pyc', 'w').write('x')")],
  }, {}, 1, "WARN  检查产生了候选之外的新文件：junk.txt"),
  check("缓存在检查之前就有", {
    after: ({ wt }) => put(wt, "pkg/__pycache__/m.pyc", "x"),
  }, {}, 0, "全部必要检查通过"),
  check("缓存在检查之前就有，检查把它删了：照样记进 artifact_files", {
    checks: [py("V01", "import shutil; shutil.rmtree('pkg/__pycache__')")],
    after: ({ wt }) => put(wt, "pkg/__pycache__/m.pyc", "x"),
  }, {}, 0, "全部必要检查通过"),
  check("cwd 跳出工作副本、不存在", { checks: [OK("V01", { cwd: ".." }), OK("V02", { cwd: "nope" })] }, {}, 1, "CHECK V01 blocked cwd 不存在或位于工作副本之外"),
  check("程序找不到：名字与带路径的", { checks: [{ ...OK(), argv: ["no-such-program-zz", "-x"] }, { ...OK("V02"), argv: ["bin/no-such.exe"] }] }, {}, 1, "CHECK V01 blocked"),
  check("批处理文件被拒绝", { checks: [{ ...OK(), argv: ["run.bat", "a&b"] }] }, {}, 1, "CHECK V01 blocked"),
  check("超时", { checks: [py("V01", "import time; time.sleep(30)", { timeout_seconds: 1 })] }, {}, 1, "CHECK V01 failed 超时"),
  // 外层的 CI 由 env_remove 去掉：变异测试与 CI 里跑契约时外层本来就有 CI，补 CI=1 那一句看不出来
  check("环境变量：CI 与检查项自己的", {
    config: { env_remove: ["CI"] },
    checks: [py("V01", "import os; print(os.environ['PROBE'], os.environ['CI'])", { env: { PROBE: "x" }, output_must_match: ["^x 1$"] })],
  }, {}, 0, "全部必要检查通过"),
  check("PATH 由检查项的 env 改写：按它找不到就原样交给系统", { checks: [OK("V01", { env: { PATH: "Z:/nowhere" } })] }, {}, 0, "全部必要检查通过"),
  check("原地检查加 --keep-workspace", {}, { keep: true }, 0, "检查结果（in_place）"),
  check("候选漂移：只多了新文件", { after: ({ wt }) => put(wt, "extra.txt", "x") }, {}, 4, "候选之外的新文件 ['extra.txt']"),
  check("非必要检查失败不影响结论", { checks: [OK(), FAIL("V02", { required: false })] }, {}, 0, "CHECK V02 failed 退出码 1 ≠ 期望 0"),
  check("干净副本，检查失败", { checks: [FAIL()] }, { fresh: true }, 1, "检查结果（fresh）：存在失败的必要检查"),
  check("干净副本，setup 不留文件", { setup: [OK("S1")] }, { fresh: true }, 0, "检查结果（fresh）：全部必要检查通过"),
  check("干净副本，保留", {}, { fresh: true, keep: true }, 0, "检查结果（fresh）：全部必要检查通过"),
  check("干净副本，补丁与候选树不符", {
    after: ({ repo, runDir, head }) => {
      const candidate = JSON.parse(readFileSync(join(runDir, "candidate.json"), "utf8")) as Record<string, unknown>;
      put(runDir, "candidate.json", json({ ...candidate, tree: git(repo, "rev-parse", `${head}^{tree}`) }));
    },
  }, { fresh: true }, 3, "无法建立干净的验收副本：干净副本与候选树不一致"),
  check("干净副本，补丁被改", { after: ({ runDir }) => put(runDir, "candidate.patch", "x") }, { fresh: true }, 3, "不能建立干净副本"),
  check("干净副本，setup 失败", { setup: [FAIL("S1")] }, { fresh: true }, 3, "无法建立干净的验收副本：干净副本的 setup S1 失败：退出码 1 ≠ 期望 0"),
  check("干净副本，setup 改了候选", { setup: [py("S1", "open('src/a.ts', 'a').write('// y')")] }, { fresh: true }, 3,
    "setup 改动了干净副本中的候选文件或产生了未忽略的新文件"),
  check("干净副本，worktree_root 在仓库里", { config: { worktree_root: "inside" } }, { fresh: true }, 3, "无法建立干净的验收副本：worktree_root 不能位于仓库内部"),
  check("干净副本，worktree_root 在一个文件下面", {
    after: ({ repo, wt }) => {
      put(dirname(wt), "blocker.txt", "x");
      rootBeside(repo, wt, "blocker.txt");
    },
  }, { fresh: true }, 3, "无法建立干净的验收副本：[WinError 183]"),
  check("干净副本，worktree_root 的名字不合法", { after: ({ repo, wt }) => rootBeside(repo, wt, "a|b") }, { fresh: true }, 3,
    "无法建立干净的验收副本：[WinError 123]"),
  check("planner-v2 的合同没有发布记录", { contract: { contract_family: "planner-v2" } }, {}, 3, "planner-v2 发布门禁拒绝验收检查"),
  check("第二次检查编号递增", { files: { "checks/01/checks.json": { aborted: "candidate_drift" } } }, {}, 0, ".agent/runs/t1/attempt-001/checks/02/checks.json"),
];

const REVIEW_PASS = `# 复审${LF}${LF}Verdict: PASS${LF}`;

const VERDICTS: Scenario[] = [
  verdict("PASS，各门禁都过", {}, { verdict: "PASS", note: "看过了" }, 0, "PASS 已记录（.agent/runs/t1/attempt-001/verdicts/01.json）。"),
  verdict("PASS，门禁未过", { files: { "run.json": { exit_code: 1 }, "scope.json": { violations: [{ kind: "modified", path: "src/b.ts" }] } } }, { verdict: "PASS" }, 1,
    "PASS 被拒绝：门禁 G1, G2 未通过"),
  verdict("PASS 带豁免", {}, { verdict: "PASS", waive: ["G2=范围已核"] }, 2, "PASS 不接受豁免"),
  verdict("ACCEPTED_WITH_EXCEPTION 缺豁免", { files: { "run.json": { exit_code: 2 } } }, { verdict: "ACCEPTED_WITH_EXCEPTION", decidedBy: "u" }, 2, "以下失败门禁没有豁免理由：G1"),
  verdict("ACCEPTED_WITH_EXCEPTION 齐全", { files: { "run.json": { exit_code: 2 } } },
    { verdict: "ACCEPTED_WITH_EXCEPTION", waive: ["G1=先写一次", "G1=  已知问题  "], decidedBy: "用户" }, 0, "未通过的门禁：G1"),
  verdict("ACCEPTED_WITH_EXCEPTION 缺 --decided-by", {}, { verdict: "ACCEPTED_WITH_EXCEPTION", waive: ["G4=x"] }, 2, "需要至少一项 --waive 与 --decided-by"),
  verdict("REVISE 缺 --class", {}, { verdict: "REVISE" }, 2, "REVISE 需要 --class（PLAN_ERROR, EXECUTION_ERROR"),
  verdict("--waive 门禁不对", {}, { verdict: "ACCEPTED_WITH_EXCEPTION", waive: ["G9=x"], decidedBy: "u" }, 2, "--waive 格式应为 G2=原因"),
  verdict("--waive 没有理由", {}, { verdict: "ACCEPTED_WITH_EXCEPTION", waive: ["G2=  "], decidedBy: "u" }, 2, "--waive 格式应为 G2=原因"),
  verdict("--waive 没有等号", {}, { verdict: "ACCEPTED_WITH_EXCEPTION", waive: ["G2"], decidedBy: "u" }, 2, "--waive 格式应为 G2=原因"),
  verdict("复审报告不存在", {}, { verdict: "PASS", review: "nope.md" }, 2, "找不到复审报告：nope.md"),
  verdict("复审报告是空的", { review: "" }, { verdict: "PASS" }, 2, "找不到复审报告：review.md"),
  verdict("复审报告是目录", {}, { verdict: "PASS", review: ".agent" }, 2, "找不到复审报告：.agent"),
  verdict("复审报告还有待填", { review: `Verdict: PASS${LF}  - 结论：【待填】  ${LF}REPLACE_WITH x${LF}` }, { verdict: "PASS" }, 2,
    "复审报告还有 2 处【待填】（review-draft 生成的骨架要填完再交），第一处：- 结论：【待填】"),
  verdict("Verdict 行与参数不同", { review: REVIEW_PASS }, { verdict: "BLOCKED", failureClass: "PLAN_ERROR" }, 2, "复审报告中的 'Verdict:' 行必须恰好是 BLOCKED"),
  verdict("Verdict 行带空白与 CRLF", { review: `# x${CR}${LF}${CR}${LF}   Verdict:   ESCALATE  ${CR}${LF}` }, { verdict: "ESCALATE", failureClass: "PLAN_ERROR" }, 0,
    "ESCALATE 已记录"),
  verdict("Verdict 行在行中间", { review: `结论 Verdict: PASS${LF}` }, { verdict: "PASS" }, 2, "复审报告中的 'Verdict:' 行必须恰好是 PASS"),
  verdict("复审报告不是 UTF-8", { review: "Verdict: PASS" + String.fromCharCode(10) }, { verdict: "PASS", review: "bad.md" }, 1, undefined, true),
  verdict("复审报告的路径写法", {}, { verdict: "PASS", review: "./notes//r.md" }, 0, "PASS 已记录"),
  verdict("状态不能记录结论", { files: { "state.json": state("RUNNING") } }, { verdict: "PASS" }, 3, "状态 RUNNING 不能记录验收结论"),
  verdict("INFRA_FAILURE 可以复审", { files: { "state.json": state("INFRA_FAILURE") } }, { verdict: "BLOCKED", failureClass: "INFRA_FAILURE" }, 0, "BLOCKED 已记录"),
  verdict("再次 verdict，编号递增", { files: { "state.json": state("REVISE"), "verdicts/01.md": "x", "verdicts/01.json": { verdict: "REVISE" } } }, { verdict: "PASS" }, 0,
    "verdicts/02.json"),
  verdict("候选记录是列表", { files: { "candidate.json": [] } }, { verdict: "PASS" }, 1, undefined, true),
  // 用 REVISE：门禁不挡结论，TS 不崩就会把结论记下来（退出码 0），与 Python 的崩溃分得开
  verdict("证据类型不对：meta.base_sha 是 null", { meta: { base_sha: null } }, { verdict: "REVISE", failureClass: "EXECUTION_ERROR" }, 1, undefined, true),
  verdict("证据类型不对：meta.worktree 是 null", { meta: { worktree: null } }, { verdict: "REVISE", failureClass: "EXECUTION_ERROR" }, 1, undefined, true),
  verdict("证据类型不对：candidate.tree 是数字", { files: { "candidate.json": { tree: 123, patch_roundtrip_verified: true } } }, { verdict: "REVISE", failureClass: "EXECUTION_ERROR" }, 1, undefined, true),

  gates("G0：合同被改、基线不可用、另一台机器与另一处仓库", {
    meta: { base_sha: "0".repeat(40), platform: "Linux-6.1.0-x86_64", repository: "D:/elsewhere" },
    after: ({ runDir }) => put(runDir, "plan.md", "changed"),
  }, "NOTE  G0 attempt 在另一台机器上派遣"),
  {
    ...gates("G0：同一系统的另一个版本、仓库路径只差大小写，都不算别处派遣", { meta: { platform: `${PLATFORM.split("-")[0]}-0-0.0.1-SP0` } }),
    build: (repo, head, runner) => ({
      ...fullAttempt(repo, head, runner, {
        review: `Verdict: REVISE${LF}`, meta: { platform: `${PLATFORM.split("-")[0]}-0-0.0.1-SP0`, repository: realpathSync.native(repo).toUpperCase() },
      }),
      "<REPO_UPPER>": realpathSync.native(repo).toUpperCase(),
    }),
  },
  gates("G0：不是按角色写的合同却有版本记录", { meta: { executor_binding: { role: "execution" } } }),
  gates("G0：按角色写的合同缺版本记录", { contract: { executor: { role: "execution" } } }),
  gates("G0：planner-v2 没有发布记录", { contract: { contract_family: "planner-v2" } }),
  gates("G1：缺 run.json 与事件摘要、执行报告", { files: { "run.json": null, "events-summary.json": null, "report-status.json": null } }),
  gates("G1：超时、中断、退出码、事件问题、思考级别", {
    files: {
      "run.json": { exit_code: 1, timed_out: true, interrupted: true },
      "events-summary.json": { problems: ["没有 agent_settled", "工具调用失败 3 次"], provider_thinking_levels: [], requested_model: { thinking: "high" } },
      "report-status.json": { status: "missing", contract_conflicts: 2 },
      "observations.json": { main_repo_changes: { head_changed: false, other_paths: ["notes.md"] } },
    },
  }),
  gates("G1：事件摘要是空对象、没有请求的模型", { files: { "events-summary.json": {}, "report-status.json": { status: "json_ok" } } }),
  gates("G3：提到歧义而报告没有列出", { files: { "events-summary.json": { problems: [], provider_thinking_levels: ["high"], ambiguity_mention_count: 2 } } }),
  gates("G3：提到歧义，报告列了解读", {
    files: { "events-summary.json": { problems: [], provider_thinking_levels: ["high"], ambiguity_mention_count: 2 }, "report-status.json": { status: "json_ok", interpretations: ["x"] } },
  }),
  gates("G2：范围违规、主工作区变化、工作副本外路径", {
    files: {
      "scope.json": { violations: [{ kind: "modified_outside_scope", path: "x.ts" }, { kind: "deleted", path: "y.ts" }] },
      "observations.json": { main_repo_changes: { head_changed: true, other_paths: [] } },
      "events-summary.json": {
        problems: [], provider_thinking_levels: ["high"], outside_worktree_paths: [
          { path: "C:/main/a.ts", tool: "bash", main_repo: true, failed: true, event_line: 3 },
          { path: "C:/main/b.ts", tool: "read", main_repo: true, failed: false },
          { path: "C:/main/c.ts", tool: "read", main_repo: true, failed: true },
          { path: "C:/other/d.ts", tool: "powershell", main_repo: false, event_line: 9 },
          { path: "C:/other/e.ts", tool: "edit" },
          { path: "C:/other/f.ts", tool: "read", failed: true },
        ],
      },
    },
  }),
  gates("G2：缺 scope.json，DoD 依赖范围证据", { files: { "scope.json": null }, dod: [{ id: "D01", text: "x", evidence: ["scope", "V01", "review"] }] }),
  gates("G4：没有检查记录", { files: { "checks/01/checks.json": null } }),
  gates("G4：最近一次检查 aborted", { files: { "checks/02/checks.json": { aborted: "fresh_workspace_failed" } } }),
  gates("G4：旧候选、没覆盖、改了候选、新文件、缓存、干净副本、必要检查失败与没跑", {
    checks: [OK(), OK("V02"), OK("V03", { required: false })],
    dod: [{ id: "D01", text: "x", evidence: ["V02", "V03"] }, { id: "D02", text: "y", evidence: ["V01"] }],
    files: {
      "checks/01/checks.json": {
        candidate_tree: "0".repeat(40), covers_all_required: false, modified_by_checks: true, candidate_files_modified: ["src/a.ts", "src/b.ts"],
        unexpected_files_by_checks: ["junk.txt"], artifact_files: ["__pycache__/m.pyc"], mode: "fresh",
        results: [{ id: "V01", passed: false, status: "failed" }, { id: "V03", passed: false, status: "blocked" }],
      },
    },
  }),
  gates("G6：记录之后改了候选、多了新文件", {
    after: ({ wt }) => {
      put(wt, "src/a.ts", `export const a = 9;${LF}`);
      put(wt, "new.txt", "x");
    },
  }),
  gates("G6：只差行尾", { after: ({ wt }) => put(wt, "src/a.ts", `export const a = 2;${CR}${LF}`) }),
  gates("G6：工作树不在", { meta: { worktree: "Z:/no/such/worktree" } }),
  gates("G6：补丁被改", { after: ({ runDir }) => put(runDir, "candidate.patch", "x") }),
  gates("G6：候选记录没有 tree", { files: { "candidate.json": { patch_roundtrip_verified: true } } }),
];

/** baseline 的合同：probe.py 在基线上的行为由场景定，V01 的基线期望由 mark 定。 */
function plan(repo: string, head: string, checks: readonly [string, string, string][], setup: readonly Record<string, unknown>[] = []): void {
  const lines = checks.map(([id, mark]) => `- ${id}（必要${mark ? `，${mark}` : ""}）：${BT}python probe.py ${id}${BT} · cwd：仓库根 · 超时：60s`);
  const md = mdOf("t1", head).replace(`- V01（必要，基线应失败）：${BT}python -m pytest tests -q${BT} · cwd：仓库根 · 超时：300s`, lines.join(LF));
  const expect = (mark: string): string => (mark === "基线应失败" ? "fail" : mark === "基线应通过" ? "pass" : "any");
  put(repo, ".agent/plans/t1.v1.md", md);
  put(repo, ".agent/plans/t1.v1.json", json({
    ...jsonOf("t1", head), setup,
    checks: checks.map(([id, mark]) => ({ id, argv: ["python", "probe.py", id], cwd: ".", timeout_seconds: 60, required: true, expected_exit_code: 0, expect_on_base: expect(mark) })),
  }));
}

interface BaselineFlags {
  readonly only?: string;
  readonly keep?: boolean;
  readonly config?: Record<string, unknown>;
}

/** probe.py：按 argv[1] 查表，打印并以给定的码退出。 */
const probe = (table: Record<string, [string, number]>): string =>
  [`import sys, time`, `TABLE = ${JSON.stringify(table)}`, `out, code = TABLE[sys.argv[1]]`, `print(out, flush=True)`, `if out == 'SLEEP': time.sleep(60)`, `sys.exit(code)`, ""].join(LF);

const baseline = (label: string, table: Record<string, [string, number]>, checks: readonly [string, string, string][], flags: BaselineFlags, status: number,
  text?: string, setup: readonly Record<string, unknown>[] = [], files: Record<string, string> = {}): Scenario => ({
  label,
  build: (repo, head, runner) => {
    plan(repo, head, checks, setup);
    const wtRoot = realpathSync.native(tempDir(`bwr-${runner}`));
    put(repo, ".agent/dispatch.config.json", json({ worktree_root: wtRoot, kill_grace_seconds: 1, ...flags.config }));
    return { "<WTROOT>": wtRoot };
  },
  argv: ["baseline", "t1.v1", ...(flags.only !== undefined ? ["--only", flags.only] : []), ...(flags.keep ? ["--keep-workspace"] : [])],
  args: { command: ["baseline"], plan_key: "t1.v1", only: flags.only ?? null, keep_workspace: flags.keep ?? false, context: CONTEXT },
  status,
  text,
  files: { "probe.py": probe(table), ...files },
});

const BASELINES: Scenario[] = [
  baseline("探针在基线上失败，符合预期", { V01: ["assert failed", 1] }, [["V01", "基线应失败", ""]], {}, 0, "V01    fail    failed  符合预期"),
  baseline("探针在基线上已通过", { V01: ["ok", 0] }, [["V01", "基线应失败", ""]], {}, 1, "不符：期望在基线上失败，实际已通过"),
  baseline("未标注：找不到用例与普通失败、已通过", { V01: ["NO TESTS RAN in 0.01s", 5], V02: ["boom", 1], V03: ["ok", 0] },
    [["V01", "", ""], ["V02", "", ""], ["V03", "", ""]], {}, 0, "只新增测试文件的合同在基线上本就如此"),
  baseline("回归保护没通过", { V01: ["boom", 1], V02: ["ok", 0] }, [["V01", "基线应通过", ""], ["V02", "基线应通过", ""]], {}, 1, "不符：期望在基线上通过（回归保护）"),
  baseline("--only 选一项", { V01: ["boom", 1], V02: ["ok", 0] }, [["V01", "基线应失败", ""], ["V02", "基线应失败", ""]], { only: "V01" }, 0, "BASELINE V01 ..."),
  baseline("--only 有未知的检查", { V01: ["boom", 1] }, [["V01", "", ""]], { only: "V7" }, 2, "未知检查：V7"),
  baseline("setup 失败", { V01: ["boom", 1] }, [["V01", "", ""]], {}, 3, "基线副本的 setup S1 失败：退出码 1 ≠ 期望 0",
    [{ id: "S1", argv: ["python", "-c", "raise SystemExit(1)"], cwd: ".", timeout_seconds: 60, required: true, expected_exit_code: 0 }]),
  baseline("worktree_root 在仓库里", { V01: ["boom", 1] }, [["V01", "", ""]], { config: { worktree_root: "inside" } }, 2, "worktree_root 不能位于仓库内部"),
  baseline("保留基线副本", { V01: ["boom", 1] }, [["V01", "基线应失败", ""]], { keep: true }, 0, "基线检查记录：.agent/runs/t1/baseline/01/checks.json"),
  baseline("合同无效", { V01: ["boom", 1] }, [["V01", "", ""]], {}, 2, "合同校验失败，无法运行基线检查。", [], {}),
];

/** 合同无效：JSON 删掉，validate 报缺文件。 */
const INVALID = BASELINES[BASELINES.length - 1] as Scenario;
BASELINES[BASELINES.length - 1] = {
  ...INVALID,
  build: (repo, head, runner) => {
    const paths = INVALID.build(repo, head, runner);
    rmSync(join(repo, ".agent", "plans", "t1.v1.json"));
    return paths;
  },
};

/** 输出与证据里随运行变化的部分：耗时、进程号、mkdtemp 的随机后缀。 */
function scrub(text: string): string {
  return text
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/"pid": [0-9]+/gu, '"pid": <PID>')
    .replace(/-(verify|baseline)-[a-z0-9_]{8}/gu, "-$1-<RND>");
}

function scrubAll(record: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(record).map(([key, value]) => [scrub(key), scrub(value)]));
}

function runScenario(scenario: Scenario): void {
  const results = RUNNERS.map((runner) => {
    const { repo, head } = newRepo(`ck-${runner}`, scenario.files ?? {});
    const paths = { "<REPO>": repo, ...scenario.build(repo, head, runner) };
    if (scenario.label === "复审报告不是 UTF-8") put(repo, "bad.md", new Uint8Array([0x56, 0xff, 0x0a]));
    if (scenario.label === "复审报告的路径写法") put(repo, "notes/r.md", REVIEW_PASS);
    const result = runCommand(runner, repo, scenario.argv, scenario.args);
    const shown: Shown = shownOf(result, paths, scenario.crash);
    // 崩溃只比退出码，另核对两边都真是崩溃（Python 打堆栈，TS 写“崩溃”那一行），免得报错退出 1 冒充崩溃
    const stderr = result.stderr.toString("utf8");
    const crashed = scenario.crash ? stderr.includes("Traceback (most recent call last)") || stderr.includes("崩溃（Python 在这里会打印堆栈）") : null;
    const evidence = scenario.crash ? {} : scrubAll(snapshotDir(join(repo, ".agent", "runs"), paths));
    const worktrees = git(repo, "worktree", "list", "--porcelain").split(LF).filter((line) => line.startsWith("worktree ")).length;
    return { status: shown.status, stdout: scrub(shown.stdout), stderr: scrub(shown.stderr), evidence, worktrees, crashed };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as Shown;
  expect(first.status, JSON.stringify(results[0])).toBe(scenario.status);
  if (scenario.crash) expect((results[0] as { crashed: boolean }).crashed, "崩溃场景两边都要真崩").toBe(true);
  if (scenario.text) expect(`${first.stdout}${first.stderr}`).toContain(scenario.text);
}

/**
 * 标准输出与标准错误进同一个文件时的次序（hub 就是这样读的）：Python 的标准输出写进文件时块缓冲，ERROR 行先落盘，
 * NOTE、GATE 等到退出才冲出；CHECK、BASELINE 两行 flush=True，连同之前攒着的一起冲出。
 */
const MERGED: Scenario[] = [
  check("合并输出：另一处仓库的提示在漂移报错之后", { meta: { repository: "D:/elsewhere/repo" }, after: ({ wt }) => put(wt, "extra.txt", "x") }, {}, 4),
  check("合并输出：CHECK 行冲出之前攒着的 NOTE", { meta: { repository: "D:/elsewhere/repo" }, checks: [FAIL()] }, {}, 1),
  verdict("合并输出：GATE 行在 PASS 被拒的报错之后", { meta: { worktree: "Z:/no/such/worktree" }, files: { "run.json": { exit_code: 3 } } }, { verdict: "PASS" }, 1),
  // 120 行 GATE 超过 8 KB：stdout 两层缓冲已经写出一部分，ERROR 落在某一行正文之后、它的换行之前（themistally-15 复核 d14ea7c）
  verdict("合并输出：120 行 GATE 之后 PASS 被拒", {
    files: {
      "events-summary.json": {
        problems: [], provider_thinking_levels: ["high"], requested_model: { thinking: "high" }, ambiguity_mention_count: 0,
        outside_worktree_paths: Array.from({ length: 120 }, (_, i) => ({ path: `C:/main/${"d".repeat(i % 37)}/f${String(i).padStart(3, "0")}.ts`, tool: "read", main_repo: true, failed: false })),
      },
    },
  }, { verdict: "PASS" }, 1),
  baseline("合并输出：WARN 在 setup 失败的报错之后", { V01: ["boom", 1], V02: ["ok", 0] }, [["V01", "", ""], ["V02", "", ""]], {}, 3, undefined,
    [{ id: "S1", argv: ["python", "-c", "raise SystemExit(1)"], cwd: ".", timeout_seconds: 60, required: true, expected_exit_code: 0 }]),
  baseline("合并输出：BASELINE 行与表格", { V01: ["boom", 1] }, [["V01", "", ""]], {}, 0),
];

function runMerged(scenario: Scenario): void {
  const results = RUNNERS.map((runner) => {
    const { repo, head } = newRepo(`mg-${runner}`, scenario.files ?? {});
    const paths = { "<REPO>": repo, ...scenario.build(repo, head, runner) };
    const result = runCommand(runner, repo, scenario.argv, scenario.args, repo, true);
    return { status: result.status, output: scrub(normalize(result.stdout.toString("utf8"), paths)) };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  expect((results[0] as { status: number }).status, JSON.stringify(results[0])).toBe(scenario.status);
}

describe("合并输出的次序", () => {
  for (const scenario of MERGED) it(scenario.label, () => runMerged(scenario));
});

function runBreak(scenario: Scenario, marker: string): void {
  const results = RUNNERS.map((runner) => {
    const { repo, head } = newRepo(`br-${runner}`, scenario.files ?? {});
    const paths = { "<REPO>": repo, ...scenario.build(repo, head, runner) };
    const command = runner === "python" ? pythonCliCommand(["--repo", repo, ...scenario.argv]) : tsCliCommand(runner, { repo, ...scenario.args });
    const done = spawnSync(PYTHON, ["-c", BREAK_OUTER, BREAK_INNER, JSON.stringify(command), repo, marker], { encoding: "utf8", timeout: 150_000 });
    if (done.status !== 0) throw new Error(`${runner} 中断用例的包装进程退出码 ${String(done.status)}：${done.stderr}`);
    const run = JSON.parse(done.stdout) as { status: number; stdout: string; stderr: string };
    const evidence = scrubAll(snapshotDir(join(repo, ".agent", "runs"), paths));
    return { status: run.status, stdout: scrub(normalize(run.stdout, paths)), stderr: scrub(normalize(run.stderr, paths)), evidence };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as { status: number; stdout: string };
  expect(first.status, JSON.stringify(results[0])).toBe(scenario.status);
  if (scenario.text) expect(first.stdout).toContain(scenario.text);
}

/** D2：检查跑到一半，命令的进程组收到 CTRL_BREAK：这一项记被取消，后面的照跑，照常收尾。 */
const SLEEPY = py("V01", "import time; time.sleep(60)");

describe("D2：命令的进程组收到 CTRL_BREAK", () => {
  it("check：这一项记被取消，后面的照跑", () => {
    runBreak(check("中断", { checks: [SLEEPY, OK("V02")] }, {}, 1, "CHECK V01 failed 被取消"), "CHECK V01 ...");
  }, 300_000);

  it("baseline：这一项记被取消，表格照常打印", () => {
    runBreak(baseline("中断", { V01: ["SLEEP", 1] }, [["V01", "", ""]], {}, 0, "V01    any     failed  基线上未通过"), "BASELINE V01 ...");
  }, 300_000);
});

describe("check", () => {
  for (const scenario of CHECKS) it(scenario.label, () => runScenario(scenario));
});

describe("verdict", () => {
  for (const scenario of VERDICTS) it(scenario.label, () => runScenario(scenario));
});

describe("baseline", () => {
  for (const scenario of BASELINES) it(scenario.label, () => runScenario(scenario));
});
