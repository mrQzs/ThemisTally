// metrics、release-check、sync-adapters 的命令行契约（迁移第 ④b2 片）。每个场景按三份实现各建一份相同的仓库，跑同一条命令，
// 比较退出码、输出与跑完之后的目录；崩溃只比退出码。metrics 覆盖：int 与 float 混算、round、半数取偶的百分比（8 个任务通过 1 个
// 是 12.5%，Python 写 12%）、按配置单价估算、决策记录（含坏行与 mutations/ 下的）、--out 的 CRLF；release-check 覆盖三条模式的
// Unicode 语义（全角数字也算 \d）、BOM、CRLF、不合法的 UTF-8、二进制后缀、一个文件命中过多、允许规则、拒绝清单；
// sync-adapters 覆盖缺源、同步、检查、junction 与目标是文件。不写转义序列，反斜杠用 String.fromCharCode 拼。
import { mkdirSync, symlinkSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { CONTEXT, LF, RUNNERS, type Runner, type Shown, crashText, git, newRepo, put, removeCreated, runCommand, shownOf, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const ch = (...codes: number[]): string => String.fromCodePoint(...codes);
const BS = ch(92);
const CR = ch(13);
const json = (value: unknown): string => `${JSON.stringify(value, null, 2)}${LF}`;

interface Scenario {
  readonly label: string;
  readonly build: (repo: string, runner: Runner) => Record<string, string>;
  readonly argv: (repo: string, extra: Record<string, string>) => string[];
  readonly args: (repo: string, extra: Record<string, string>) => Record<string, unknown>;
  readonly snapshot: string;
  readonly status: number;
  readonly crash?: boolean;
  /** 崩溃时连“类型: 文字”也比（crashText）。 */
  readonly crashText?: boolean;
  readonly text?: string;
  readonly empty?: boolean;
  /** 输出里不许出现的片段（release-check 的假 key 在前缀之后的每一段）。 */
  readonly absent?: readonly string[];
}

function run(scenario: Scenario): void {
  const results = RUNNERS.map((runner) => {
    const repo = scenario.empty ? emptyRepo(runner) : newRepo(`rc-${runner}`).repo;
    const extra = scenario.build(repo, runner);
    const paths = { "<REPO>": repo, ...extra };
    const result = runCommand(runner, repo, scenario.argv(repo, extra), scenario.args(repo, extra));
    return {
      ...shownOf(result, paths, scenario.crash), after: scenario.crash ? {} : snapshotDir(join(repo, scenario.snapshot), paths),
      ...(scenario.crashText ? { crashText: crashText(result, paths) } : {}),
    };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  expect((results[0] as Shown).status, JSON.stringify(results[0]).slice(0, 2000)).toBe(scenario.status);
  const shown = `${(results[0] as Shown).stdout}${(results[0] as Shown).stderr}`;
  if (scenario.text) expect(shown).toContain(scenario.text);
  for (const piece of scenario.absent ?? []) expect(shown, piece).not.toContain(piece);
}

function emptyRepo(runner: Runner): string {
  const repo = tempDir(`rc-empty-${runner}`);
  git(repo, "init", "-q");
  return repo;
}

// --- metrics --------------------------------------------------------------------------------------

function task(repo: string, name: string, attempts: Record<string, unknown>[]): void {
  attempts.forEach((files, index) => {
    const dir = join(repo, ".agent", "runs", name, `attempt-${String(index + 1).padStart(3, "0")}`);
    mkdirSync(dir, { recursive: true });
    for (const [rel, content] of Object.entries(files)) {
      if (rel.endsWith("/")) mkdirSync(join(dir, rel), { recursive: true });
      else put(dir, rel, typeof content === "string" ? content : json(content));
    }
  });
}

const PRICING = {
  pricing: {
    "step/step-5-preview": { input: 0.5, output: 2, cache_read: 0.1, currency: "CNY", source: "价格页 2026-01-01", as_of: "2026-01-01" },
    "other/model-x": { input: 1000, output: 3000, currency: "USD", source: "手填", as_of: "2025-12-31" },
  },
};
const STEP = { provider: "step", model: "step-5-preview" };

function metricsTasks(repo: string): void {
  put(repo, ".agent/dispatch.config.json", JSON.stringify(PRICING));
  task(repo, "t1", [
    {
      "claim/": "", "state.json": { state: "REVISE" }, "verdicts/01.json": { verdict: "REVISE", failure_class: "EXECUTION_ERROR" },
      "run.json": { wall_seconds: 120.5 }, "scope.json": { violations: [] }, "executor.json": STEP,
      "events-summary.json": { ok: true, usage: { input: 1000, output: 500, cacheRead: 200, totalTokens: 1700 }, cost: { total: 0.0123, status: "estimated" } },
      "decisions.jsonl": [JSON.stringify({ status: "answered", usage: { input_tokens: 1200 } }), "{", JSON.stringify([1]),
        JSON.stringify({ status: "no_opinion", reason: "timeout", usage: { input_tokens: true } })].join(LF),
      "mutations/01/decisions.jsonl": JSON.stringify({ status: "answered", usage: { input_tokens: 300 } }),
    },
    {
      "claim/": "", "state.json": { state: "INTEGRATED", ref: "abcdef1234567890ab" }, "verdicts/01.json": { verdict: "PASS", human_minutes: 12.5 },
      "run.json": { wall_seconds: 60 }, "executor.json": STEP,
      "events-summary.json": { ok: true, usage: { input: 3000, output: 100, totalTokens: 3100 }, cost: { total: 0.02, status: "partial" } },
    },
  ]);
  task(repo, "t2", [{
    "claim/": "", "state.json": { state: "ABANDONED" }, "verdicts/01.json": { verdict: "BLOCKED", failure_class: "INFRA_FAILURE", human_minutes: 3 },
    "run.json": { wall_seconds: 30 }, "events-summary.json": { ok: false, usage: { input: 10 } },
  }]);
  task(repo, "t3", [{ "state.json": { state: "PREPARED" } }]);
  task(repo, "t4", [{
    "claim/": "", "state.json": { state: "SUPERSEDED", ref: "r-1" }, "verdicts/01.json": { verdict: "ACCEPTED_WITH_EXCEPTION" },
    "scope.json": { violations: ["src/x.ts"] }, "executor.json": { provider: "other", model: "model-x" }, "run.json": { wall_seconds: 1 },
    "events-summary.json": { ok: true, usage: { input: 500, output: 20, cacheWrite: 7 } },
  }]);
}

const metrics = (label: string, build: Scenario["build"], out: string | null, status: number, options: Partial<Scenario> = {}): Scenario => ({
  label, build,
  argv: () => ["metrics", ...(out ? ["--out", out] : [])],
  args: () => ({ command: ["metrics"], out }),
  snapshot: ".agent/runs", status, ...options,
});

// --- release-check --------------------------------------------------------------------------------

const KEY = `sk-${"a1B2".repeat(6)}`;
const AKIA = `AKIA${"Q".repeat(16)}`;
const GHP = `ghp_${"x".repeat(31)}`;
/** 假 key 在公开前缀之后的每一段（含紧跟前缀的第一个字符）：输出里一段也不许有（第 126 轮）。 */
function secretPieces(key: string, prefix: string): string[] {
  const rest = key.slice(prefix.length);
  return [prefix + rest.slice(0, 1), ...Array.from({ length: rest.length - 3 }, (_, index) => rest.slice(index, index + 4))];
}
const KEY_PIECES = [...secretPieces(KEY, "sk-"), ...secretPieces(AKIA, "AKIA"), ...secretPieces(GHP, "ghp_")];

function hitFiles(repo: string): void {
  put(repo, "cfg/keys.txt", [`token = ${KEY}`, `aws ${AKIA} end`, GHP].join(LF));
  put(repo, "docs/home.md", [`见 C:${BS}Users${BS}bob${BS}proj`, "/home/alice/work/x", `/Users/Carol/dev/`, "(/home/Bad/x)"].join(LF));
  put(repo, "docs/net.md", ["192.168.1.20 与 10.0.0.1", "100.64.1.2:80 和 172.16.0.1.5", `192.168.${ch(0xff11)}.${ch(0xff12)}`, "box.tail1.ts.net"].join(CR + LF));
  put(repo, "docs/bom.md", `${ch(0xfeff)}第一行${LF}第二行${LF}key ${KEY}`);
  put(repo, "docs/bytes.txt", Buffer.concat([Buffer.from("x"), Buffer.from([0xff, 0xfe, 0xc3]), Buffer.from(` ${KEY} 尾`)]));
  put(repo, "many.txt", Array.from({ length: 25 }, (_, index) => `${KEY}${index}`).join(LF));
  put(repo, "img/logo.PNG", "binary sk-not-scanned");
  put(repo, ".gitignore", `.agent/runs/${LF}# 10.0.0.1${LF}`);
  git(repo, "add", "-A");
  git(repo, "commit", "-q", "-m", "hits");
}

const release = (label: string, build: Scenario["build"], flags: { allow?: string[]; deny?: boolean }, status: number, options: Partial<Scenario> = {}): Scenario => ({
  label,
  build: (repo, runner) => {
    const extra = build(repo, runner);
    if (flags.deny === false) return extra;
    return { "<DENY>": extra["<DENY>"] ?? join(tempDir(`rc-deny-${runner}`), "none.txt"), ...extra };
  },
  argv: (_repo, extra) => ["release-check", ...(flags.allow ?? []).flatMap((rule) => ["--allow", rule]), ...(extra["<DENY>"] ? ["--denylist", extra["<DENY>"]] : [])],
  args: (_repo, extra) => ({ command: ["release-check"], allow: flags.allow ?? null, denylist: extra["<DENY>"] ?? null, context: CONTEXT }),
  snapshot: ".claude", status, ...options,
});

// --- sync-adapters --------------------------------------------------------------------------------

const SKILLS = ["check-pi-env", "plan-task", "dispatch-pi", "review-pi"];

function skillSources(repo: string, names = SKILLS): void {
  for (const name of names) {
    put(repo, `.agents/skills/${name}/SKILL.md`, `# ${name}${LF}`);
    put(repo, `.agents/skills/${name}/refs/a.md`, "a");
  }
}

const sync = (label: string, build: Scenario["build"], check: boolean, status: number, options: Partial<Scenario> = {}): Scenario => ({
  label, build,
  argv: () => ["sync-adapters", ...(check ? ["--check"] : [])],
  args: () => ({ command: ["sync-adapters"], check }),
  snapshot: ".claude", status, ...options,
});

const SCENARIOS: Scenario[] = [
  metrics("metrics：没有 attempt", () => ({}), null, 0, { text: "任务数：0" }),
  metrics("metrics：几个任务，混着 int、float、单价与决策记录", (repo) => {
    metricsTasks(repo);
    return {};
  }, null, 0, { text: "决策调用（Jev，2.6.0） | 3 次，有答案 2 · 输入 token 1501" }),
  metrics("metrics：8 个任务通过 1 个，百分比恰在中点", (repo) => {
    for (let index = 0; index < 8; index += 1) {
      task(repo, `p${index}`, [{ "claim/": "", "state.json": { state: index ? "REVISE" : "PASS" }, "verdicts/01.json": { verdict: index ? "REVISE" : "PASS" } }]);
    }
    return {};
  }, null, 0, { text: "首次验收通过率（PASS） | 12% |" }),
  // sum() 是补偿求和：0.1 加十次是 1.0、0.1+0.2+0.3 是 0.6，逐个相加会差在末位（themistally-15 复核 b29ab6c）
  metrics("metrics：人工分钟是 0.1 的倍数", (repo) => {
    task(repo, "q1", Array.from({ length: 10 }, () => ({ "claim/": "", "state.json": { state: "REVISE" }, "verdicts/01.json": { verdict: "REVISE", failure_class: "EXECUTION_ERROR", human_minutes: 0.1 }, "run.json": { wall_seconds: 0.1 } })));
    for (const [name, minutes] of [["q2", 0.1], ["q3", 0.2], ["q4", 0.3]] as const) {
      task(repo, name, [{ "claim/": "", "state.json": { state: "PASS" }, "verdicts/01.json": { verdict: "PASS", human_minutes: minutes }, "run.json": { wall_seconds: minutes } }]);
    }
    return {};
  }, null, 0, { text: "| 人工介入分钟 | 1.6 |" }),
  metrics("metrics：--out 写到 _reports", (repo) => {
    metricsTasks(repo);
    return {};
  }, ".agent/runs/_reports/m.md", 0, { text: "已写入" }),
  metrics("metrics：--out 指到别处", () => ({}), "notes/m.md", 2),
  metrics("metrics：wall_seconds 是字符串", (repo) => {
    task(repo, "t1", [{ "claim/": "", "state.json": { state: "PASS" }, "run.json": { wall_seconds: "1" } }]);
    return {};
  }, null, 1, { crash: true }),
  metrics("metrics：价格表无效", (repo) => {
    put(repo, ".agent/dispatch.config.json", JSON.stringify({ pricing: { "step/x": { input: 1 } } }));
    return {};
  }, null, 2),

  release("release-check：干净", () => ({}), {}, 0, { text: "clean: 3 个文本文件，没有拒绝清单" }),
  release("release-check：命中", (repo) => {
    hitFiles(repo);
    return {};
  }, {}, 1, { text: "cfg/keys.txt:1: api key: sk-…（27 字符）", absent: KEY_PIECES }),
  release("release-check：允许规则", (repo) => {
    hitFiles(repo);
    put(repo, ".agent/dispatch.config.json", JSON.stringify({ release_check: { allow: ["many.txt:*"] } }));
    return {};
  }, { allow: ["docs/**:home path", "cfg/:api key"] }, 1, { text: "NOT SCANNED（1 个二进制或不可读文件）：img/logo.PNG" }),
  release("release-check：拒绝清单", (repo, runner) => {
    put(repo, "notes/n.md", `Contains SECRET-word here${LF}`);
    git(repo, "add", "-A");
    git(repo, "commit", "-q", "-m", "n");
    const deny = join(tempDir(`rc-denyfile-${runner}`), "deny.txt");
    put(deny.slice(0, deny.length - "deny.txt".length), "deny.txt", ["# 注释", "", "  secret-word  ", "export const a"].join(LF));
    return { "<DENY>": deny };
  }, {}, 1, { text: "含拒绝清单第 1 项" }),
  release("release-check：拒绝清单在仓库里", (repo) => {
    put(repo, "deny.txt", "x");
    return { "<DENY>": join(repo, "deny.txt") };
  }, {}, 2),
  release("release-check：允许规则写错", () => ({}), { allow: ["no-colon"] }, 2),
  release("release-check：没有文件", () => ({}), {}, 1, { empty: true }),

  sync("sync-adapters：没有源", () => ({}), false, 3),
  sync("sync-adapters：部分缺源，照样同步其余的", (repo) => {
    skillSources(repo, ["plan-task", "review-pi"]);
    put(repo, ".agents/skills/plan-task/__pycache__/x.pyc", "c");
    put(repo, ".claude/skills/plan-task/old.md", "old");
    return {};
  }, false, 1, { text: "缺少源文件的技能没有同步：check-pi-env, dispatch-pi" }),
  sync("sync-adapters：已是最新", (repo) => {
    skillSources(repo);
    for (const name of SKILLS) {
      put(repo, `.claude/skills/${name}/SKILL.md`, `# ${name}${LF}`);
      put(repo, `.claude/skills/${name}/refs/a.md`, "a");
    }
    return {};
  }, false, 0, { text: "已是最新" }),
  sync("sync-adapters：--check 一致", (repo) => {
    skillSources(repo);
    for (const name of SKILLS) {
      put(repo, `.claude/skills/${name}/SKILL.md`, `# ${name}${LF}`);
      put(repo, `.claude/skills/${name}/refs/a.md`, "a");
    }
    return {};
  }, true, 0, { text: "一致" }),
  sync("sync-adapters：--check 不一致", (repo) => {
    skillSources(repo);
    put(repo, ".claude/skills/plan-task/SKILL.md", "# changed");
    put(repo, ".claude/skills/plan-task/extra.md", "e");
    return {};
  }, true, 1, { text: "DRIFT plan-task/extra.md：副本多出（源中没有）" }),
  sync("sync-adapters：源经过 junction", (repo, runner) => {
    skillSources(repo, ["plan-task"]);
    const outside = tempDir(`rc-junction-${runner}`);
    put(outside, "SKILL.md", "# outside");
    symlinkSync(outside, join(repo, ".agents", "skills", "review-pi"), "junction");
    return { "<OUT>": outside };
  }, false, 3, { text: "或其上级目录是符号链接或 junction" }),
  // 覆盖审计的缺口（切换 c3a；test_dispatch 1465、1483、1508）：副本目录或源技能里的链接
  sync("sync-adapters：副本目录是 junction：拒绝，不动它指向的目录", (repo, runner) => {
    skillSources(repo);
    const outside = tempDir(`rc-copy-link-${runner}`);
    put(outside, "plan-task/keep.md", "keep");
    mkdirSync(join(repo, ".claude"), { recursive: true });
    symlinkSync(outside, join(repo, ".claude", "skills"), "junction");
    return { "<OUT>": outside };
  }, false, 3, { text: "链接" }),
  sync("sync-adapters：--check 副本是 junction，内容相同也拒绝", (repo, runner) => {
    skillSources(repo);
    const mirror = tempDir(`rc-mirror-${runner}`);
    for (const name of SKILLS) {
      put(mirror, `${name}/SKILL.md`, `# ${name}${LF}`);
      put(mirror, `${name}/refs/a.md`, "a");
    }
    mkdirSync(join(repo, ".claude"), { recursive: true });
    symlinkSync(mirror, join(repo, ".claude", "skills"), "junction");
    return { "<OUT>": mirror };
  }, true, 3, { text: "链接", absent: ["一致。"] }),
  sync("sync-adapters：源技能里套了 junction：不跟随", (repo, runner) => {
    skillSources(repo);
    const secret = tempDir(`rc-nested-${runner}`);
    put(secret, "outside.md", "outside");
    symlinkSync(secret, join(repo, ".agents", "skills", "plan-task", "linked"), "junction");
    return { "<OUT>": secret };
  }, false, 0, { absent: ["outside.md"] }),
  sync("sync-adapters：目标是文件", (repo) => {
    skillSources(repo, ["plan-task"]);
    put(repo, ".claude/skills/plan-task", "file");
    return {};
  }, false, 1, { crash: true, crashText: true }), // shutil.rmtree 碰到文件：NotADirectoryError，带路径
];

describe("metrics、release-check、sync-adapters", () => {
  for (const scenario of SCENARIOS) it(scenario.label, () => run(scenario));
});
