// 运行健康判断与决策回放的契约（迁移第 ④b4b 片）：wait --assess、status --assess、decisions replay，以及 assess_run 跨 tick
// 的逻辑（连续提示、输出打转）。Python 与 TS（Node、Bun）跑同一场景，比退出码、输出、发给端点的请求与决策记录。
// 决策端点是单独进程的替身（probes/fake_endpoint.mjs）：被测命令照常用同步的 spawnSync 起。只用假 key（环境变量
// THEMIS_CONTRACT_DECISIONS_KEY），不碰凭据库；事件文件的修改时间放到将来，“静默秒数”恒为 0，要测静默的那条另外抹掉数字。
import { existsSync, readFileSync, utimesSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { KEY_NAME, type Reply, startEndpoint } from "./endpoint-fixtures.ts";
import { IMPLS, runBatch } from "./harness.ts";
import { CONTEXT, LF, RUNNERS, type Runner, newRepo, put, removeCreated, runCommand, shownOf, tempDir } from "./repo-fixtures.ts";

const PROBES = resolve(dirname(fileURLToPath(import.meta.url)), "..", "probes");
const REPO_ROOT = resolve(PROBES, "..", "..", "..", "..");
const savedKey = process.env[KEY_NAME];

beforeAll(() => {
  process.env[KEY_NAME] = "fake-key-for-contract";
});

afterAll(() => {
  if (savedKey === undefined) delete process.env[KEY_NAME];
  else process.env[KEY_NAME] = savedKey;
  removeCreated();
});

/** run-health 的回答：choice 是 argmax。 */
function healthReply(choice = "keep_waiting", confidence = 0.66): Reply {
  const others = ["keep_waiting", "prepare_next_contract", "collect"].filter((name) => name !== choice);
  const probabilities = { [choice]: 0.6, [others[0] as string]: 0.25, [others[1] as string]: 0.15 };
  return {
    status: 200,
    body: JSON.stringify({
      answers: {
        progressing: { type: "noul", noul: 0.8 }, blocked: { type: "noul", noul: 0.125 }, looping: { type: "noul", noul: 0.05 },
        done: { type: "noul", noul: 0.2 }, action: { type: "choice", choice, probabilities, confidence },
      },
      usage: { input_tokens: 321, output_tokens: 9 }, model: "jev-test",
    }),
  };
}
const FAILING: Reply = { status: 500, body: "{}" };

interface AttemptOptions {
  /** 事件文件的修改时间放到 5000 秒之前（静默很久）。 */
  readonly quietOld?: boolean;
  readonly started?: string;
}

/** 一个运行中的 attempt：事件里有 assistant 文本、工具调用与一行坏 JSON；plan.md 有 Goal。 */
function runningAttempt(repo: string, options: AttemptOptions = {}): string {
  const runDir = join(repo, ".agent", "runs", "t1", "attempt-001");
  const events = [
    JSON.stringify({ type: "agent_start" }),
    JSON.stringify({ type: "message_end", message: { role: "assistant", content: [{ type: "text", text: "正在跑测试。" }, { type: "text", text: "第二段" }] } }),
    JSON.stringify({ type: "tool_execution_end", toolName: "bash", isError: false }),
    JSON.stringify({ type: "tool_execution_end", toolName: "read", isError: true }),
    JSON.stringify({ type: "message_end", message: { role: "user", content: "不算" } }),
    "{坏 JSON",
    JSON.stringify({ type: "message_end", message: { role: "assistant", content: "  " } }),
  ];
  put(runDir, "events.jsonl", events.join(LF) + LF);
  put(runDir, "state.json", JSON.stringify({ state: "RUNNING", at: "2026-10-27T00:00:00Z" }));
  put(runDir, "plan.md", `# TASK: t1${LF}${LF}## Goal${LF}让测试通过。${LF}${LF}## Scope${LF}x${LF}`);
  put(runDir, "meta.json", JSON.stringify({ task_id: "t1", attempt_no: 1 }));
  if (options.started) put(runDir, "run-started.json", JSON.stringify({ started_at: options.started }));
  const when = Date.now() / 1000 + (options.quietOld ? -5000 : 3600);
  utimesSync(join(runDir, "events.jsonl"), when, when);
  return runDir;
}

function decisionsConfig(repo: string, port: number, extra: Record<string, unknown> = {}): void {
  const decisions = { mode: "shadow", base_url: `http://127.0.0.1:${port}`, api_key_env: KEY_NAME, points: ["run-health"], ...extra };
  put(repo, ".agent/dispatch.config.json", JSON.stringify({ decisions }));
}

/** 随时间变的数：静默秒数、运行秒数、延迟。 */
const scrubNumbers = (text: string): string =>
  text
    .replace(/静默 [0-9]+ 秒/gu, "静默 <N> 秒")
    .replace(/[0-9]+ 秒没有新事件/gu, "<N> 秒没有新事件")
    .replace(/"latency_ms": [0-9]+/gu, `"latency_ms": -1`)
    .replace(/"(seconds_since_new_event|quiet_seconds|seconds_running|elapsed_seconds)": ?-?[0-9]+/gu, `"$1": -1`);

interface Scenario {
  readonly label: string;
  readonly replies: readonly Reply[];
  readonly config?: Record<string, unknown>;
  readonly attempt?: AttemptOptions;
  readonly argv: readonly string[];
  readonly args: Record<string, unknown>;
  readonly status: number;
  readonly text?: string | undefined;
  readonly absent?: string;
}

async function runScenario(scenario: Scenario): Promise<void> {
  const results = [];
  for (const runner of RUNNERS as readonly Runner[]) {
    const endpoint = await startEndpoint(scenario.replies);
    try {
      const { repo } = newRepo(`dcmd-${runner}`);
      decisionsConfig(repo, endpoint.port, scenario.config);
      const runDir = runningAttempt(repo, scenario.attempt);
      const result = runCommand(runner, repo, scenario.argv, { ...scenario.args, context: CONTEXT }, repo);
      const shown = shownOf(result, { "<REPO>": repo });
      const record = join(runDir, "decisions.jsonl");
      // 有 run-started、静默很久时，运行秒数、静默秒数每秒都变：live 那列的秒数与 state 的哈希另外抹掉（state 本身在 requests 里比）
      const running = (text: string): string => (scenario.attempt?.started || scenario.attempt?.quietOld ? text.replace(/live:([0-9]+t) [0-9]+s/gu, "live:$1 <N>s").replace(/"state_sha256": "[0-9a-f]+"/gu, `"state_sha256": "<H>"`) : text);
      results.push({
        status: shown.status,
        stdout: running(scrubNumbers(shown.stdout)),
        stderr: scrubNumbers(shown.stderr),
        requests: scrubNumbers(JSON.stringify(endpoint.requests())),
        record: existsSync(record) ? running(scrubNumbers(readFileSync(record, "utf8")).replace(/"at": "[^"]*"/gu, `"at": "<AT>"`)) : "",
      });
    } finally {
      endpoint.stop();
    }
  }
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify(first)).toBe(scenario.status);
  if (scenario.text) expect(first.stdout + first.stderr).toContain(scenario.text);
  if (scenario.absent) expect(first.stdout + first.stderr).not.toContain(scenario.absent);
}

const status = (label: string, replies: readonly Reply[], json: boolean, expected: Partial<Scenario> = {}): Scenario => ({
  label, replies,
  argv: ["status", "--assess", ...(json ? ["--json"] : [])],
  args: { command: ["status"], task_id: null, json, assess: true },
  status: 0, ...expected,
});

const wait = (label: string, replies: readonly Reply[], expected: Partial<Scenario> = {}): Scenario => ({
  label, replies,
  argv: ["wait", "t1", "--timeout", "1", "--interval", "0.2", "--assess", "--assess-interval", "60.5"],
  args: { command: ["wait"], run_dir: "t1", timeout: 1, interval: 0.2, assess: true, assess_interval: 60.5 },
  status: 3, ...expected,
});

const ASSESS: Scenario[] = [
  status("status --assess：有答案", [healthReply()], false, { text: "决策（run-health, shadow）：推进 0.80 · 被挡 0.12 · 打转 0.05 · 完成 0.20 · 建议 keep_waiting（置信度 0.66）" }),
  status("status --assess --json", [healthReply("collect", 0.71)], true, { text: "建议 collect（置信度 0.71）" }),
  status("status --assess：端点回 500，重试一次之后无意见", [FAILING], false, { text: "无意见（http_500），只按活动信号 · 静默 <N> 秒 · 重复 否 · 建议 keep_waiting" }),
  status("status --assess：模式 off 不问", [healthReply()], false, { config: { mode: "off" }, text: "RUNNING", absent: "决策（run-health" }),
  status("status --assess：run-health 没启用", [healthReply()], false, { config: { points: ["report-screen"] }, absent: "决策（run-health" }),
  status("status --assess：配置写错是用法错误", [healthReply()], false, { config: { mode: "loud" }, status: 2, text: "dispatch.config.json 的 decisions 无效" }),
  status("status --assess：运行了多久按 run-started 算", [healthReply()], false, { attempt: { started: "2026-10-01T00:00:00Z" }, text: "建议 keep_waiting" }),
  wait("wait --assess：问一次，到时仍在运行", [healthReply()], { text: "再次运行 wait 继续等待" }),
  wait("wait --assess：on 模式、置信度达到阈值，提示一次", [healthReply("prepare_next_contract", 0.9)], {
    config: { mode: "on" }, text: "决策模型提示：建议 prepare_next_contract（连续 1 次）。运行不会被停止",
  }),
  wait("wait --assess：模式 off，只按状态等", [healthReply()], { config: { mode: "off" }, text: "NOTE  --assess：决策模式为 off 或 run-health 未启用，只按状态等待" }),
  wait("wait --assess：静默很久，事实优先于模型", [healthReply()], { attempt: { quietOld: true }, text: "建议 prepare_next_contract（置信度 0.66）；<N> 秒没有新事件，事实优先于模型" }),
  wait("wait --assess：静默很久、端点也没意见", [FAILING], { attempt: { quietOld: true }, text: "无意见（http_500），只按活动信号 · 静默 <N> 秒 · 重复 否 · 建议 prepare_next_contract" }),
];

describe("wait --assess 与 status --assess", () => {
  for (const scenario of ASSESS) it(scenario.label, () => runScenario(scenario), 120_000);
});

/** 同一个 tracker 连问几次（探针直接调 assess_run）：连续 alert_after 次相同建议才提示；尾部输出不变三次算打转。 */
describe("assess_run 跨 tick", () => {
  const cases: [string, readonly Reply[], Record<string, unknown>, number, string][] = [
    ["on 模式、两次 prepare_next_contract（置信度不到阈值）：第二次提示", [healthReply("prepare_next_contract", 0.5)], { mode: "on" }, 2, "（连续 2 次）"],
    ["端点一直没意见：第三次起算打转", [FAILING], { mode: "on" }, 4, "重复 是 · 建议 prepare_next_contract"],
    ["shadow 模式不提示", [healthReply("prepare_next_contract", 0.95)], { mode: "shadow" }, 3, "建议 prepare_next_contract（置信度 0.95）"],
  ];
  for (const [label, replies, extra, ticks, text] of cases) {
    it(label, async () => {
      const values: string[] = [];
      for (const impl of IMPLS) {
        const endpoint = await startEndpoint(replies);
        try {
          const repo = tempDir("assess");
          const runDir = runningAttempt(repo);
          const config = { decisions: { mode: "shadow", base_url: `http://127.0.0.1:${endpoint.port}`, api_key_env: KEY_NAME, points: ["run-health"], ...extra } };
          const [result] = runBatch(impl, [{ op: "decisions.client", fn: "assess", config: JSON.stringify(config), kit_root: REPO_ROOT, record: join(runDir, "decisions.jsonl"), run_dir: runDir, ticks }]);
          values.push(scrubNumbers(String(result?.["value"] ?? JSON.stringify(result))));
        } finally {
          endpoint.stop();
        }
      }
      for (const value of values.slice(1)) expect(value).toBe(values[0]);
      expect(values[0]).toContain(text);
      if (extra["mode"] === "shadow") expect(values[0]).not.toContain("决策模型提示");
    }, 120_000);
  }
});

// ---------------------------------------------------------------------------
// decisions replay
// ---------------------------------------------------------------------------

const record = (fields: Record<string, unknown>): string => JSON.stringify({ at: "2026-10-27T00:00:00Z", latency_ms: 5, ...fields });

/** 两个任务的记录：report-screen 有答案（一份通过、一份没通过）、run-health 的几个 tick、mutations/01 下的 mutation-equivalence。 */
function replayRuns(repo: string): void {
  const runs = join(repo, ".agent", "runs");
  const screen = (claims: number, severity: number, mode = "shadow"): string => record({
    point: "report-screen", status: "answered", mode, usage: { input_tokens: 1000 },
    answers: { claims_unsupported: { type: "noul", noul: claims }, chose_interpretation: { type: "noul", noul: 0.125 },
      scope_creep: { type: "noul", noul: 0.3 }, weakened_tests: { type: "noul", noul: 0.05 }, severity: { type: "score", score: severity, levels: 4 } },
  });
  put(runs, "t1/attempt-001/decisions.jsonl", [
    screen(0.814, 1.255),
    record({ point: "run-health", status: "answered", answers: { action: { type: "choice", choice: "keep_waiting" } }, usage: { input_tokens: 200 } }),
    record({ point: "run-health", status: "no_opinion", reason: "timeout" }),
    record({ point: "run-health", status: "answered", answers: { action: { type: "choice", choice: "collect" } }, usage: { input_tokens: true } }),
    "{坏行",
  ].join(LF));
  put(runs, "t1/attempt-001/verdicts/01.json", JSON.stringify({ verdict: "PASS" }));
  put(runs, "t1/attempt-001/state.json", JSON.stringify({ state: "PASS" }));
  put(runs, "t2/attempt-001/decisions.jsonl", [screen(0.2, 2.5, "on"), record({ point: "report-screen", status: "no_opinion", reason: "budget" })].join(LF));
  put(runs, "t2/attempt-001/mutations/01/decisions.jsonl", record({
    point: "mutation-equivalence", status: "answered", context: { mutation: "M03", name: "去掉检查" },
    answers: { equivalent: { type: "noul", noul: 0.123 }, untested: { type: "noul", noul: 0.875 } }, usage: { input_tokens: 77 },
  }));
  put(runs, "t2/attempt-001/verdicts/01.json", JSON.stringify({ verdict: "REVISE" }));
  put(runs, "t2/attempt-001/state.json", JSON.stringify({ state: "REVISE" }));
  put(runs, "t3/attempt-001/state.json", JSON.stringify({ state: "PREPARED" }));
  // 带例外接受也算通过类
  put(runs, "t4/attempt-001/decisions.jsonl", screen(0.5, 0.75));
  put(runs, "t4/attempt-001/verdicts/01.json", JSON.stringify({ verdict: "ACCEPTED_WITH_EXCEPTION" }));
  put(runs, "t4/attempt-001/state.json", JSON.stringify({ state: "ACCEPTED_WITH_EXCEPTION" }));
}

interface ReplayCase {
  readonly label: string;
  readonly argv: readonly string[];
  readonly args: Record<string, unknown>;
  readonly status: number;
  readonly text?: string | undefined;
  readonly empty?: boolean;
  readonly file?: string;
}

const replay = (label: string, extra: readonly string[], args: Record<string, unknown>, status: number, text?: string, options: Partial<ReplayCase> = {}): ReplayCase => ({
  label, argv: ["decisions", "replay", ...extra],
  args: { command: ["decisions", "replay"], decisions_cmd: "replay", task_id: null, json: false, out: null, ...args }, status, text, ...options,
});

const REPLAYS: ReplayCase[] = [
  replay("文字", [], {}, 0, "| t1/attempt-001 | PASS | shadow | 0.81 | 0.12 | 0.3 | 0.05 | 1.25 |"),
  replay("--json", ["--json"], { json: true }, 0, `"estimated_cost_usd": `),
  replay("只看一个任务", ["t2"], { task_id: "t2" }, 0, "| t2/attempt-001 | M03 | 去掉检查 | 0.12 | 0.88 |"),
  replay("--out 写到 _reports", ["--out", ".agent/runs/_reports/replay.md"], { out: ".agent/runs/_reports/replay.md" }, 0, "已写入", { file: ".agent/runs/_reports/replay.md" }),
  replay("--out 指到别处", ["--out", "notes/replay.md"], { out: "notes/replay.md" }, 2, "--out 只能指向"),
  replay("没有记录", [], {}, 0, "没有有答案的 report-screen 记录。", { empty: true }),
  { label: "缺子命令", argv: ["decisions"], args: { command: ["decisions"], decisions_cmd: null }, status: 2, text: "decisions 需要子命令 replay" },
];

describe("decisions replay", () => {
  for (const item of REPLAYS) {
    it(item.label, () => {
      const results = (RUNNERS as readonly Runner[]).map((runner) => {
        const { repo } = newRepo(`replay-${runner}`);
        if (!item.empty) replayRuns(repo);
        const result = runCommand(runner, repo, item.argv, { ...item.args, context: CONTEXT }, repo);
        const shown = shownOf(result, { "<REPO>": repo });
        const written = item.file && existsSync(join(repo, item.file)) ? readFileSync(join(repo, item.file)).toString("utf8") : "";
        return { ...shown, written: written.replace(/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z/gu, "<AT>") };
      });
      for (const result of results.slice(1)) expect(result).toEqual(results[0]);
      const first = results[0] as (typeof results)[number];
      expect(first.status, JSON.stringify(first)).toBe(item.status);
      if (item.text) expect(first.stdout + first.stderr).toContain(item.text);
      if (item.file) expect(first.written).toContain("# 决策回放");
    }, 120_000);
  }
});
