// 配置里有疑似凭据（切换 c1；覆盖审计列的安全缺口：prepare、metrics、branch 没有契约）。内核读配置的唯一入口先过整份的
// 疑似凭据检查，下游拿不到这些取值。每条调度器命令各在一份新夹具上跑：attempt-fixtures 的 fullAttempt（各门禁都能通过的
// attempt），另放好 t1.v1 的合同供 prepare，dispatch.config.json 里放一个假令牌。四种 runner 比退出码、两路输出与 .agent
// 下的全部文件；另核对令牌的中段不出现在 stdout、stderr 与 .agent 下除配置文件本身以外的任何文件里。pi 一律是 stub_pi，
// 只用假令牌。node、bun 两种 runner 的参数由 pi_dispatch.dispatcher_handoff 从真的 argparse 结果生成。不写转义序列。
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, realpathSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { PYTHON, fullAttempt, json, state } from "./attempt-fixtures.ts";
import { REPO as KIT, runPythonCli } from "./harness.ts";
import { jsonOf, mdOf } from "./plan-fixtures.ts";
import { LF, RUNNERS, type Runner, git, newRepo, pyargsOf, normalize, put, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const TOKEN = "sk-" + "q7".repeat(12);
/** 令牌的中段：脱敏只遮掉一部分时也搜得到。 */
const CORE = "q7".repeat(6);
const PLACES: Record<string, Record<string, unknown>> = {
  commit_trailers: { commit_trailers: [`Reviewed-By: ${TOKEN}`] },
  pricing: { pricing: { "p/m": { input: 1, output: 1, source: TOKEN, as_of: "2026-10-18" } } },
  kill_grace_seconds: { kill_grace_seconds: TOKEN },
  键名: { [TOKEN]: 1 },
  // 键名像凭据、值只是普通文字：只能靠键名认出来，redact_tokens 认不出（themistally-15 复核 c1 时提出）
  键名像凭据的普通值: { notes: { password: `plain-${"q7".repeat(12)}` } },
};
const ENV: Record<string, string> = {
  PI_DISPATCH_PI_CMD: JSON.stringify([PYTHON, join(KIT, "tests", "stub_pi.py")]),
  PI_CODING_AGENT_DIR: tempDir("sc-agent"),
  GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid",
  GIT_AUTHOR_DATE: "2026-01-02T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-02T00:00:00+00:00",
};
const SPEC = {
  command: [PYTHON, "-c", "pass"], cwd: ".", timeout_seconds: 60,
  mutations: [{ name: "M1", file: "src/a.ts", old: "a = 2", new: "a = 3" }],
};
const BRANCHABLE = {
  meta: { attempt_id: "t1.v1.a001" },
  contract: { authorization: { executor: ["local_edit", "local_test"], integration: ["local_branch"] } },
  files: { "verdicts/1.json": { verdict: "PASS" } },
};

function withEnv<T>(env: Record<string, string>, body: () => T): T {
  const saved = Object.fromEntries(Object.keys(env).map((key) => [key, process.env[key]]));
  Object.assign(process.env, env);
  try {
    return body();
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function filesUnder(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? filesUnder(full) : [full];
  });
}

/** Python 的 prepare 建的 attempt（工作树干净，run 的 G0 才放行），之后才把令牌写进配置。 */
function preparedAttempt(repo: string, runner: Runner, config: Record<string, unknown>): Record<string, string> {
  const wtRoot = realpathSync.native(tempDir(`sc-wtr-${runner}`));
  put(repo, ".agent/dispatch.config.json", json({ worktree_root: wtRoot, kill_grace_seconds: 1 }));
  const prep = runPythonCli(["--repo", repo, "prepare", "t1.v1"], repo);
  if (prep.status !== 0) throw new Error(`prepare 失败：${prep.stdout.toString("utf8")}${prep.stderr.toString("utf8")}`);
  const wt = (JSON.parse(readFileSync(join(repo, ".agent", "runs", "t1", "attempt-001", "meta.json"), "utf8")) as { worktree: string }).worktree;
  put(repo, ".agent/dispatch.config.json", json({ worktree_root: wtRoot, kill_grace_seconds: 1, ...config }));
  return { "<WT>": wt, "<WTROOT>": wtRoot };
}

interface Setup {
  /** 夹具要补的证据文件（状态补到这条命令放行的那一种，才走得到读配置那一步）。 */
  readonly files?: Record<string, unknown>;
  /** 用 Python 的 prepare 建 attempt，而不是 fullAttempt。 */
  readonly prepared?: boolean;
}

/** 跑一条命令，四种 runner 的结果要相同；返回其中一份，供各用例另加断言。 */
function runScenario(argv: readonly string[], config: Record<string, unknown>, setup: Setup = {}): { status: number; stderr: string; evidence: Record<string, string> } {
  const results = RUNNERS.map((runner) => {
    // 配置里有各自的 worktree_root：忽略它与证据目录，主工作区的内容树才与路径无关
    const { repo, head } = newRepo(`sc-${runner}`, { ".gitignore": [".agent/runs/", ".agent/dispatch.config.json", ""].join(LF) });
    put(repo, ".agent/plans/t1.v1.md", mdOf("t1", head));
    put(repo, ".agent/plans/t1.v1.json", json(jsonOf("t1", head)));
    put(repo, "spec.json", json(SPEC));
    // 有结论 PASS、合同授权 local_branch：branch、integrate 这些先核对授权与结论的命令也走得到读配置那一步
    const paths: Record<string, string> = {
      "<REPO>": repo,
      ...(setup.prepared ? preparedAttempt(repo, runner, config)
        : fullAttempt(repo, head, runner, { config, ...BRANCHABLE, files: { ...BRANCHABLE.files, ...setup.files } })),
    };
    const result = withEnv(ENV, () => runCommand(runner, repo, argv, pyargsOf(repo, argv)));
    const stdout = result.stdout.toString("utf8");
    const stderr = result.stderr.toString("utf8");
    const agent = join(repo, ".agent");
    const wt = paths["<WT>"] ?? "";
    const leaks = [
      ...(stdout.includes(CORE) ? ["stdout"] : []),
      ...(stderr.includes(CORE) ? ["stderr"] : []),
      ...filesUnder(agent).filter((file) => relative(agent, file) !== "dispatch.config.json" && readFileSync(file).includes(CORE))
        .map((file) => relative(repo, file)),
      // attempt 的工作树（不含 .git）；提交说明进的是压缩过的对象，按子串搜不到，另用 git log 读出来
      ...(existsSync(wt) ? filesUnder(wt).filter((file) => !relative(wt, file).startsWith(".git") && readFileSync(file).includes(CORE)).map((file) => `<WT>/${relative(wt, file)}`) : []),
      ...(git(repo, "log", "--all", "--format=%B").includes(CORE) ? ["git log"] : []),
    ];
    return { status: result.status, stdout: normalize(stdout, paths), stderr: normalize(stderr, paths), evidence: snapshotDir(agent, paths), leaks };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.leaks, "令牌不能出现在输出与证据里").toEqual([]);
  return first;
}

describe("覆盖审计点名的三条命令：四处放法都拒绝", () => {
  for (const argv of [["prepare", "t1.v1"], ["metrics"], ["branch", "t1"]]) {
    for (const [place, config] of Object.entries(PLACES)) {
      it(`${argv[0]}：令牌在 ${place}`, () => {
        const first = runScenario(argv, config);
        expect(first.status, first.stderr).toBe(2);
        expect(first.stderr).toContain("疑似凭据");
      }, 120_000);
    }
  }
});

describe("collect --recover：配置读不了就失败收尾", () => {
  // collect 读两次配置：范围门禁的受保护路径（attempt_protected_paths），主工作区变化的规划路径（planner_paths）。配置有
  // 疑似凭据、读不了时，不能当作没有受保护路径去算范围：读出错记下来，状态 INFRA_FAILURE（themistally-15 复核 c1 时指出）
  it("状态 INFRA_FAILURE，证据里记下读配置出错", () => {
    const first = runScenario(["collect", "t1", "--recover"], PLACES["commit_trailers"] as Record<string, unknown>,
      { files: { "state.json": state("RUNNING") } });
    expect(first.evidence["runs/t1/attempt-001/state.json"]).toContain("INFRA_FAILURE");
    expect(Object.entries(first.evidence).filter(([, text]) => text.includes("疑似凭据")).map(([rel]) => rel), "读配置出错记进了证据").not.toEqual([]);
  }, 120_000);
});

describe("其余调度器命令：读配置的拒绝，不读的照常；四边相同，令牌不外露", () => {
  // [argv, 读不读配置, 夹具]
  const COMMANDS: [string[], boolean, Setup][] = [
    [["run", "t1"], true, { prepared: true }],
    [["check", "t1"], true, {}],
    [["baseline", "t1.v1"], true, {}],
    [["integrate", "t1", "--dry-run"], true, { files: { "state.json": state("PASS") } }],
    [["release-check"], true, {}],
    [["mutate", "t1", "--spec", "spec.json"], true, {}],
    [["verdict", "t1", "--verdict", "PASS", "--review", "review.md"], false, {}],
    [["review-draft", "t1"], false, {}],
    [["mark", "t1", "ABANDONED"], false, {}],
    [["wait", "t1", "--timeout", "1"], false, {}],
    [["status", "--assess"], false, {}],
    [["decisions", "replay"], false, {}],
  ];
  for (const [argv, reads, setup] of COMMANDS) {
    it(`${argv.join(" ")}${reads ? "：拒绝" : "：不读配置"}`, () => {
      const first = runScenario(argv, PLACES["commit_trailers"] as Record<string, unknown>, setup);
      if (reads) {
        expect(first.status, first.stderr).toBe(2);
        expect(first.stderr).toContain("疑似凭据");
      } else {
        expect(first.stderr).not.toContain("疑似凭据");
      }
    }, 120_000);
  }
});
