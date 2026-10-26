// 第 ③ 步的切换：config、plugins 的每个叶子命令都经真的启动器跑一遍（选择文件 config 为 ts），与钉成 Python 的 pd.main
// 逐字节比较（themistally-15 复核切换提纲时要求）。名单里每条路径、交给 TS 的键名、command_option、TS 有没有这条命令，
// 都只有逐条走一遍才查得出。四种环境：
//   (a) 不在 Git 仓库里的目录；(b) --repo 指向一个文件；(c) linked worktree 里——Repo.discover 的三种报错；
//   (d) 带示例配置的临时仓库：读命令照常跑；有预览选项的写命令带 --dry-run --json；没有预览选项的照常跑（会写）。
// 每种环境 Python 与启动器各一份（路径不同，比较时各自换成占位符），(d) 另比最后的配置、快照与审计。
// 本机 CLI 用 fake-cli.ts 的假 pi、claude、codex；凭据库设 off。
import { spawnSync } from "node:child_process";
import { mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { gitRepo, normalize, state } from "./config-cli.ts";
import { installFakeCli } from "./fake-cli.ts";
import { type CliRun, removeDir, runConfigLauncherCli, runPythonCli, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("config-launcher"));
const BIN = join(ROOT, "bin");
const BS = String.fromCharCode(92);

const SAVED: Record<string, string | undefined> = {};
beforeAll(() => {
  const env: Record<string, string | undefined> = {
    PATH: installFakeCli(BIN),
    CODEKIT_SECRET_STORE: "off",
    CODEKIT_ACTOR: "user",
    PI_DISPATCH_PI_CMD: undefined,
    PI_DISPATCH_WORKTREE_ROOT: undefined,
    FAKE_PI_LOG: undefined,
  };
  for (const [name, value] of Object.entries(env)) {
    SAVED[name] = process.env[name];
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
  writeFileSync(join(BIN, "fake-pi.json"), JSON.stringify({ version: { out: "pi 0.80.4" }, help: { out: "--provider --model" }, list: { out: "provider model" }, auth: { code: 1 } }));
});
afterAll(() => {
  for (const [name, value] of Object.entries(SAVED)) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
  removeDir(ROOT);
});

/** 每条转交的命令各一条（与 schemas.test.ts、tests/test_kernel_impl.py 的样例相同），另加 --command 的值像子命令名的两条。 */
const SAMPLES: readonly string[][] = [
  ["config", "show"], ["config", "validate", "--json"], ["config", "set", "kill_grace_seconds", "20"], ["config", "unset", "kill_grace_seconds", "--yes"],
  ["config", "history", "show", "3", "--json"], ["config", "rollback", "2"], ["config", "init"],
  ["config", "decisions", "marker", "on"], ["config", "secret", "check", "SOME_NAME"], ["config", "secret", "remove", "SOME_NAME"], ["config", "runtime", "list"],
  ["config", "runtime", "scan", "--add"], ["config", "runtime", "add", "pi", "--adapter", "pi", "--command", '["C:/pi.exe"]'],
  ["config", "runtime", "add", "r1", "--adapter", "pi", "--command", "decisions"], ["config", "runtime", "add", "r2", "--adapter", "pi", "--command", "show"],
  ["config", "runtime", "remove", "pi", "--yes"], ["config", "runtime", "probe", "pi", "--json"], ["config", "models", "pi"],
  ["config", "profile", "show"], ["config", "profile", "add", "p", "--runtime", "pi", "--model", "a/b", "--thinking", "high", "--credential-env", "K"],
  ["config", "profile", "edit", "p", "--model", "a/c"], ["config", "profile", "remove", "p"], ["config", "role", "show", "--json"],
  ["config", "role", "set", "scheduler_agent", "p", "--cadence-seconds", "60"], ["config", "preset", "list"], ["config", "preset", "show", "day"],
  ["config", "preset", "save", "day", "--description", "d", "--roles", "execution"], ["config", "preset", "use", "day"],
  ["config", "preset", "diff", "a", "b"], ["config", "preset", "remove", "day"], ["config", "doctor", "--record", "t.v1"], ["config", "doctor"],
  ["plugins", "list", "--json"], ["plugins", "show", "code-change"], ["plugins", "verify"], ["plugins", "enable", "x", "--allow-permission", "a"],
  ["plugins", "disable", "code-change"],
];

/** 有预览选项的命令（TS_CONFIG_COMMANDS 里带 dry_run 的）：在 (d) 里加 --dry-run --json。 */
const PREVIEW = new Set(["config rollback", "config runtime add", "config runtime remove", "config profile add", "config profile edit", "config profile remove",
  "config role set", "config preset save", "config preset use", "config preset remove", "plugins enable", "plugins disable"]);
const FAMILIES = new Set(["runtime", "profile", "role", "preset"]);
const pathOf = (argv: readonly string[]): string => (argv[0] === "config" && FAMILIES.has(argv[1] as string) ? argv.slice(0, 3) : argv.slice(0, 2)).join(" ");

interface Place {
  /** --repo 的值与当前目录。 */
  readonly repo: string;
  readonly cwd: string;
  /** 输出里要换成占位符的路径。 */
  readonly paths: readonly string[];
}

function git(args: string[]): void {
  const done = spawnSync("git", ["-c", "user.name=contract", "-c", "user.email=contract@example.invalid", ...args], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
}

const PLACES: Record<string, (root: string) => Place> = {
  "(a) 不在 Git 仓库里": (root) => {
    mkdirSync(root, { recursive: true });
    return { repo: root, cwd: root, paths: [root] };
  },
  "(b) --repo 指向一个文件": (root) => {
    mkdirSync(root, { recursive: true });
    const file = join(root, "not-a-dir.txt");
    writeFileSync(file, "x");
    return { repo: file, cwd: root, paths: [file, root] };
  },
  "(c) linked worktree 里": (root) => {
    const main = gitRepo(join(root, "main"));
    git(["-C", main, "commit", "-q", "--allow-empty", "-m", "init"]);
    const tree = join(root, "tree");
    git(["-C", main, "worktree", "add", "-q", tree]);
    return { repo: tree, cwd: tree, paths: [tree, main] };
  },
  "(d) 带示例配置的临时仓库": (root) => {
    const repo = gitRepo(root);
    const done = runPythonCli(["--repo", repo, "config", "init"], repo);
    if (done.status !== 0) throw new Error(`config init 失败：${done.stderr.toString("utf8")}`);
    return { repo, cwd: repo, paths: [repo] };
  },
};

const shownWith = (result: CliRun, paths: readonly string[]): Record<string, unknown> => {
  // git 报的路径用正斜杠（例如 worktree 的那句报错），也换掉
  const scrub = (text: string): string => paths.reduce((acc, path) => normalize(acc, path).replaceAll(path.replaceAll(BS, "/"), "<REPO>"), text);
  return { status: result.status, stdout: scrub(result.stdout.toString("utf8")), stderr: scrub(result.stderr.toString("utf8")) };
};

describe.runIf(process.platform === "win32")("每个叶子命令经真的启动器（第 ③ 步的切换）", () => {
  for (const [name, make] of Object.entries(PLACES)) {
    it(name, () => {
      const writes = name.startsWith("(d)");
      const results = (["python", "launcher"] as const).map((runner) => {
        const place = make(join(ROOT, `${name.slice(1, 2)}-${runner}`));
        const steps = SAMPLES.map((sample) => {
          const argv = writes && PREVIEW.has(pathOf(sample)) ? [...sample, "--dry-run", "--json"] : sample;
          const full = ["--repo", place.repo, ...argv];
          const result = runner === "python" ? runPythonCli(full, place.cwd) : runConfigLauncherCli(full, place.cwd);
          return { argv: argv.join(" "), ...shownWith(result, place.paths) };
        });
        return { steps, state: writes ? state(place.repo) : null };
      });
      const [python, launcher] = results as [(typeof results)[number], (typeof results)[number]];
      const differ = launcher.steps.findIndex((step, at) => JSON.stringify(step) !== JSON.stringify(python.steps[at]));
      expect(differ === -1 ? null : { python: python.steps[differ], launcher: launcher.steps[differ] }, name).toEqual(null);
      expect(launcher.state, `${name}：最后的状态`).toEqual(python.state);
      // (d) 里多数命令确实走到了正常路径，不是一页报错
      if (writes) expect(python.steps.filter((step) => (step as Record<string, unknown>)["status"] === 0).length, "(d) 退出 0 的条数").toBeGreaterThanOrEqual(20);
      // 经启动器的那一份确实是 TS 答的：没有一条报“TS 实现还没有这条命令”，也没有一条报找不到入口、没装好
      const output = JSON.stringify(launcher.steps);
      for (const marker of ["TS 实现还没有这条命令", "找不到 TS 入口", "TS 实现没装好", "Traceback"]) expect(output, marker).not.toContain(marker);
    });
  }
});
