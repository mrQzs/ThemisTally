// run（迁移第 ④b7c2 片）：G0 核对、执行模型与 pi 的命令、预检与上下文取证、任务锁里的预算与领取、执行说明与运行前的证据、
// 在 worktree 里运行 Pi、collect。每个场景按三份实现各建一份相同的仓库（固定作者与时间，提交号相同）与合同对，先用 Python 的
// prepare 建好 attempt（三边相同），再跑同一条 run。pi 一律是 stub_pi（PI_DISPATCH_PI_CMD 或本机文件指向它），不调真实的 pi；
// PI_CODING_AGENT_DIR 指向临时目录。比退出码、标准输出与标准错误、.agent/runs 下的全部证据。路径、时间、pid、用时与 mkdtemp 的
// 随机后缀换成占位符；崩溃只比退出码与证据。不写转义序列。
import { readFileSync, realpathSync, rmSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { PYTHON, TS_CONTEXT, json, sha } from "./attempt-fixtures.ts";
import { REPO as KIT, runPythonCli } from "./harness.ts";
import { type Json, type MdOptions, jsonOf, mdOf } from "./plan-fixtures.ts";
import { LF, RUNNERS, type Runner, git, newRepo, normalize, put, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(() => removeCreated());

const STUB = join(KIT, "tests", "stub_pi.py");
const RUN_REL = ".agent/runs/t1/attempt-001";
/** stub_pi 的 commit 剧本照这个时间提交：三份实现的提交号才相同。 */
const FIXED_DATES = { GIT_AUTHOR_DATE: "2026-01-01T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-01T00:00:00+00:00" };
const AGENT_DIR = realpathSync.native(tempDir("run-agent"));
const SYSTEM_AGENT_DIR = realpathSync.native(tempDir("run-agent-sys"));
put(SYSTEM_AGENT_DIR, "SYSTEM.md", "系统提示词" + LF);

interface At {
  readonly repo: string;
  readonly wt: string;
  readonly runDir: string;
  readonly head: string;
}

interface Case {
  readonly label: string;
  readonly status: number;
  readonly text?: string | readonly string[];
  readonly scenario?: string;
  /** run 的 --timeout。 */
  readonly timeout?: number;
  /** 运行 run 时的环境变量：undefined 删掉。 */
  readonly env?: Record<string, string | undefined>;
  readonly json?: (data: Json) => void;
  readonly md?: MdOptions;
  readonly config?: Record<string, unknown>;
  /** prepare 之后、run 之前动手。 */
  readonly before?: (at: At) => void;
  readonly shows?: Record<string, string | readonly string[]>;
  readonly crash?: boolean;
}

function scrub(text: string): string {
  return text
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/"pid": [0-9]+/gu, '"pid": <PID>')
    .replace(/"latency_ms": [0-9]+/gu, '"latency_ms": <MS>')
    .replace(/用时 [0-9]+ ms/gu, "用时 <MS> ms")
    .replace(/用时 [0-9]+[.][0-9]+s/gu, "用时 <S>s")
    .replace(/pi-attach-[a-z0-9_]{8}/gu, "pi-attach-<R>")
    // 执行说明里写着各自的 worktree 路径：内容抹掉路径后另外比，哈希换成占位符
    .replace(/(instruction[.]md",[^"]*"sha256": ")[0-9a-f]{64}/gu, "$1<SHA>")
    .replace(/^[0-9]+$/gmu, "<PID>");
}

const crashed = (stderr: string): boolean => stderr.includes("Traceback (most recent call last)") || stderr.includes("崩溃（Python 在这里会打印堆栈）");

function withEnv<T>(env: Record<string, string | undefined>, body: () => T): T {
  const saved = Object.fromEntries(Object.keys(env).map((key) => [key, process.env[key]]));
  const apply = (values: Record<string, string | undefined>): void => {
    for (const [key, value] of Object.entries(values)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  apply(env);
  try {
    return body();
  } finally {
    apply(saved);
  }
}

/** 一份 PREPARED 的 attempt：Python 的 prepare 建的（三边相同），worktree 在仓库之外。 */
function prepared(runner: Runner, item: Case): { at: At; paths: Record<string, string> } {
  // 配置里有 worktree_root（三份实现各不相同），不进主工作区的指纹
  // stub_pi 的 hang 剧本把子进程号写进 worktree 的 child.pid：忽略它，候选树才三边相同
  const ignored = [".agent/runs/", ".agent/dispatch.config.json", ".agent/dispatch.local.json", "child.pid", ""];
  const { repo, head } = newRepo(`run-${runner}`, { ".gitignore": ignored.join(LF) });
  const wtRoot = realpathSync.native(tempDir(`rwt-${runner}`));
  const data = jsonOf("t1", head);
  item.json?.(data);
  put(repo, ".agent/plans/t1.v1.md", mdOf("t1", head, item.md));
  put(repo, ".agent/plans/t1.v1.json", json(data));
  const configText = json({ worktree_root: wtRoot, kill_grace_seconds: 1, ...item.config });
  put(repo, ".agent/dispatch.config.json", configText);
  const configSha = sha(configText);
  const prep = runPythonCli(["--repo", repo, "prepare", "t1.v1"], repo);
  if (prep.status !== 0) throw new Error(`prepare 失败：${prep.stdout.toString("utf8")}${prep.stderr.toString("utf8")}`);
  const runDir = join(repo, ...RUN_REL.split("/"));
  const wt = (JSON.parse(readFileSync(join(runDir, "meta.json"), "utf8")) as { worktree: string }).worktree;
  const at = { repo, wt, runDir, head };
  item.before?.(at);
  // 配置里有各自的 worktree_root：按角色时记下的配置哈希（全长与前 12 位）也各不相同
  const paths = { "<REPO>": repo, "<WT>": wt, "<WTROOT>": wtRoot, "<AGENT>": AGENT_DIR, "<AGENT_SYS>": SYSTEM_AGENT_DIR, "<CONFIG_SHA>": configSha, "<CONFIG_SHA12>": configSha.slice(0, 12) };
  return { at, paths };
}

function runCase(item: Case): void {
  const results = [];
  for (const runner of RUNNERS) {
    const { at, paths } = prepared(runner, item);
    const env = {
      PI_DISPATCH_PI_CMD: JSON.stringify([PYTHON, STUB]),
      PI_CODING_AGENT_DIR: AGENT_DIR,
      STUB_SCENARIO: item.scenario ?? "ok",
      STUB_MAIN_REPO: at.repo,
      ...FIXED_DATES,
      ...item.env,
    };
    const argv = ["run", RUN_REL, ...(item.timeout === undefined ? [] : ["--timeout", String(item.timeout)])];
    const result = withEnv(env, () => runCommand(runner, at.repo, argv, { command: ["run"], run_dir: RUN_REL, timeout: item.timeout ?? null, context: TS_CONTEXT }));
    const stderr = result.stderr.toString("utf8");
    results.push({
      status: result.status,
      stdout: item.crash ? "" : scrub(normalize(result.stdout.toString("utf8"), paths)),
      stderr: item.crash ? "" : scrub(normalize(stderr, paths)),
      crashed: item.crash ? crashed(stderr) : null,
      evidence: Object.fromEntries(Object.entries(snapshotDir(join(at.repo, ".agent", "runs"), paths)).map(([key, value]) => [key, scrub(value)])),
    });
  }
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify({ ...first, evidence: undefined })).toBe(item.status);
  if (item.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  for (const wanted of typeof item.text === "string" ? [item.text] : item.text ?? []) expect(first.stdout + first.stderr).toContain(wanted);
  for (const [rel, wanted] of Object.entries(item.shows ?? {})) {
    const content = first.evidence[`t1/attempt-001/${rel}`];
    expect(content, `证据 ${rel}`).toBeDefined();
    for (const piece of typeof wanted === "string" ? [wanted] : wanted) expect(content, `证据 ${rel}`).toContain(piece);
  }
}

/** 本任务另外领取过的 attempt（预算按它们算），用时各是 walls 里的一项。 */
const otherAttempts = (...walls: number[]) => ({ runDir }: At): void => {
  walls.forEach((wall, index) => {
    const other = join(runDir, "..", `attempt-00${9 - index}`);
    put(other, "claim/reservation.json", json({ timeout_seconds: 600, pid: 1, at: "2026-01-01T00:00:00Z" }));
    put(other, "run.json", json({ wall_seconds: wall }));
  });
};

const SETUP = [{ id: "S01", argv: [PYTHON, "-c", "print('setup ok')"], cwd: ".", timeout_seconds: 60 }];

// 按角色写的合同：prepare 发布版本记录，run 照记录取模型，pi 的命令来自本机文件（PI_DISPATCH_PI_CMD 不设）
const BOUND = {
  runtimes: { pi: { adapter: "pi" } },
  profiles: { exec: { runtime: "pi", model: { provider: "step", id: "step-5" }, options: { thinking: "high" }, credential_env: ["STEP_KEY"] } },
  roles: { execution: { mode: "headless", profile: "exec" } },
};
const ROLE_MD: MdOptions = { executor: "role:execution" };
const roleJson = (data: Json): void => void (data["executor"] = { role: "execution", tools: ["read", "edit", "bash"], context_files: "project" });
const LOCAL_FILE = json({ runtimes: { pi: { command: [PYTHON, STUB] }, ghost: { command: ["ghost"] } } });

const CASES: Case[] = [
  // --- 跑完 ---
  { label: "正常跑完：NEEDS_REVIEW，退出码 0", status: 0, text: ["RUNNING t1.v1.a001（时限 1200s）", "NEEDS_REVIEW t1.v1.a001", "Summary: "],
    shows: {
      "state.json": '"state": "NEEDS_REVIEW"', "claim/reservation.json": '"timeout_seconds": 1200', "executor.json": '"model": "step-5-preview"',
      "run-started.json": ['"attachments": [', "pi-attach-<R>", '"expects_agent_settled": true', '"--no-session"'],
      "run.json": ['"exit_code": 0', '"ended_at": '], "instruction.md": ["# 执行说明（调度器生成）", "单轮时限：1200 秒", "自检照抄"],
      "preflight/preflight.json": '"ok": true', "preflight/context-files.json": '"scope": "worktree"', "preflight/pi-version.txt": "0.87.0",
      "ignored-before.json": "[]", "pid.txt": "<PID>",
    } },
  { label: "--timeout 30：本轮时限收紧到 30 秒", status: 0, timeout: 30, text: "（时限 30s）",
    shows: { "claim/reservation.json": '"timeout_seconds": 30', "instruction.md": "单轮时限：30 秒" } },
  { label: "--timeout 是负数：时限 1 秒，挂住的 Pi 超时", status: 1, timeout: -5, scenario: "hang", text: ["（时限 1s）", "TIMEOUT t1.v1.a001"],
    shows: { "run.json": '"timed_out": true', "state.json": '"state": "TIMEOUT"' } },
  { label: "--timeout 0：不收紧", status: 0, timeout: 0, text: "（时限 1200s）" },
  { label: "模型从未回复：INFRA_FAILURE，退出码 1", status: 1, scenario: "startfail", text: "INFRA_FAILURE t1.v1.a001" },
  { label: "模型报错：退出码 1", status: 1, scenario: "error" },
  { label: "没有执行报告：照样 NEEDS_REVIEW", status: 0, scenario: "noreport", text: "NEEDS_REVIEW t1.v1.a001" },
  { label: "越界改文件：范围不通过", status: 0, scenario: "scope", shows: { "scope.json": '"ok": false' } },
  // --- 执行说明的内容 ---
  { label: "setup 跑过：执行说明里写准备阶段做过的事", status: 0, json: (data) => void (data["setup"] = SETUP),
    shows: { "instruction.md": ["## 准备阶段已经做过的事（prepare）", "S01 "] } },
  { label: "baseline 实测过：机器合同摘要写实测最长", status: 0,
    before: ({ runDir, head }) => {
      const argv = (jsonOf("t1", head)["checks"] as { argv: string[] }[])[0]?.argv;
      put(join(runDir, ".."), "baseline/b1/checks.json", json({ results: [{ id: "V01", argv, cwd: ".", timed_out: false, exit_code: 1, expected_exit_code: 1, wall_seconds: 41.5 }] }));
    },
    shows: { "instruction.md": "实测最长 42 秒" } },
  { label: "context_files 为 none：加 --no-context-files", status: 0,
    json: (data) => void ((data["executor"] as Json)["context_files"] = "none"),
    shows: { "run-started.json": '"--no-context-files"', "preflight/context-files.json": '"context_files": []' } },
  { label: "配置的 extra_protected_paths：执行说明里列为只读", status: 0, config: { extra_protected_paths: ["docs/**"] },
    shows: { "instruction.md": "本仓库只读的路径：`docs/**`" } },
  { label: "按角色：模型取自版本记录，pi 的命令取自本机文件（另一个 runtime 没登记，打 WARN）", status: 0, md: ROLE_MD, json: roleJson, config: BOUND,
    env: { PI_DISPATCH_PI_CMD: undefined, STUB_MODELS: "step step-5" }, before: ({ repo }) => put(repo, ".agent/dispatch.local.json", LOCAL_FILE),
    text: "WARN  .agent/dispatch.local.json 的 runtime", shows: { "executor.json": '"model": "step-5"', "run-started.json": "stub_pi.py" } },
  { label: "全局 SYSTEM.md：打 NOTE", status: 0, env: { PI_CODING_AGENT_DIR: SYSTEM_AGENT_DIR }, text: "NOTE  全局 SYSTEM.md 会改变执行器系统提示词：" },
  // --- 拒绝运行 ---
  { label: "已经不是 PREPARED：不运行", status: 3, before: ({ runDir }) => put(runDir, "state.json", json({ state: "RUNNING", at: "2026-01-01T00:00:00Z" })),
    text: "attempt 状态为 RUNNING，只能运行未领取的 PREPARED attempt；返工请重新 prepare。" },
  { label: "已经领取：不运行", status: 3, before: ({ runDir }) => put(runDir, "claim/x", ""), text: "attempt 状态为 PREPARED（已领取）" },
  { label: "worktree 里有未忽略的新文件：G0 拒绝", status: 3, before: ({ wt }) => put(wt, "stray.txt", "x"),
    text: "输入不一致（G0）：worktree 在运行前已有未忽略的变更", shows: { "history.jsonl": '"event": "run_refused"' } },
  { label: "worktree 的 HEAD 动了：G0 拒绝", status: 3,
    before: ({ wt }) => {
      put(wt, "moved.txt", "x");
      git(wt, "add", "-A");
      git(wt, "commit", "-q", "-m", "moved");
    },
    text: "worktree HEAD 已不是基线提交" },
  { label: "worktree 不在了：G0 拒绝", status: 3, before: ({ repo, wt }) => void git(repo, "worktree", "remove", "--force", wt), text: "worktree 不存在：" },
  { label: "冻结的 plan.md 被改过：G0 拒绝", status: 3, before: ({ runDir }) => put(runDir, "plan.md", "改过" + LF), text: "输入不一致（G0）：" },
  { label: "冻结合同改成 planner-v2：G0 连同发布门禁一起拒绝", status: 3,
    before: ({ runDir }) => {
      const data = JSON.parse(readFileSync(join(runDir, "contract.json"), "utf8")) as Json;
      put(runDir, "contract.json", json({ ...data, contract_family: "planner-v2" }));
    },
    text: "输入不一致（G0）：" },
  // --- 预算 ---
  { label: "次数用完：BUDGET_EXCEEDED", status: 3, before: otherAttempts(10, 20), text: "BUDGET_EXCEEDED：已达到 max_attempts_total=2。" },
  { label: "剩余墙钟不足 60 秒：BUDGET_EXCEEDED", status: 3, before: otherAttempts(2350.5), text: "BUDGET_EXCEEDED：剩余墙钟预算 50s，不足 60s。" },
  { label: "剩余墙钟比每轮上限少：时限取整", status: 0, before: otherAttempts(1500.4), text: "（时限 899s）" },
  // --- 预检与 pi 的命令 ---
  { label: "--list-models 失败：预检不通过，attempt 保持 PREPARED", status: 3, env: { STUB_LIST_FAIL: "1" },
    text: ["PREFLIGHT pi --list-models 失败：", "预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。"],
    shows: { "state.json": '"state": "PREPARED"', "history.jsonl": '"event": "preflight_failed"', "preflight/list-models.txt": "<redacted>" } },
  { label: "凭据没就绪：预检不通过", status: 3, env: { STUB_AUTH: "missing", STUB_AUTH_DETAIL: "api_key=sk-THEMISCONTRACTabcdefghijklmnop" },
    text: "PREFLIGHT pi auth check 未就绪（退出码 1）" },
  { label: "模型不在列表里：预检不通过", status: 3, env: { STUB_MODELS: "step step-5" }, text: "PREFLIGHT 模型 step/step-5-preview 不在本机可用模型列表中" },
  { label: "PI_DISPATCH_PI_CMD 写错：用法错误", status: 2, env: { PI_DISPATCH_PI_CMD: JSON.stringify(["", 1]) }, text: "PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组或单个可执行文件路径" },
  // --- 领取之后、启动之前出错 ---
  { label: "executor.json 已经在了：记 spawn_error、INFRA_FAILURE，照 Python 崩", status: 1, crash: true,
    before: ({ runDir }) => put(runDir, "executor.json", "{}"),
    shows: { "run.json": '"spawn_error": "领取后、启动前失败：FileExistsError: ', "state.json": '"state": "INFRA_FAILURE"' } },
];

describe("run", () => {
  for (const item of CASES) it(item.label, () => runCase(item), 240_000);
});

describe("run 的现场清理", () => {
  it("附件目录跑完删掉", () => {
    // 正常跑完的那条：run-started.json 记的附件目录已经不在
    const { at } = prepared("node", { label: "", status: 0 });
    withEnv({ PI_DISPATCH_PI_CMD: JSON.stringify([PYTHON, STUB]), PI_CODING_AGENT_DIR: AGENT_DIR, STUB_SCENARIO: "ok", STUB_MAIN_REPO: at.repo, ...FIXED_DATES }, () =>
      runCommand("node", at.repo, ["run", RUN_REL], { command: ["run"], run_dir: RUN_REL, timeout: null, context: TS_CONTEXT }),
    );
    const started = JSON.parse(readFileSync(join(at.runDir, "run-started.json"), "utf8")) as { attachments_dir: string };
    expect(() => readFileSync(join(started.attachments_dir, "plan.md"))).toThrow();
    rmSync(at.repo, { recursive: true, force: true });
  }, 120_000);
});
