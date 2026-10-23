// `pi_dispatch.py ui` 的转交（调度器第 73 轮，桌面端设计第 7 版 T6）：ui 只有 TS 实现、不进选择文件，readonly 选
// python 还是 ts 都转交；启动器交出的参数过 pyargs-v1 的 ui 一支。这里只钉 §5.1 定死的行为（用法错误退出 2 与提示），
// 服务本身的行为由 ts/packages/ui/test 覆盖（ui 包经 hub 派给执行器，本包在内核禁区里，执行器改不了这里）。
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { type CliRun, removeDir, runLauncherCli, runPythonCli, scratchDir } from "./harness.ts";
import { schemaErrors } from "./schemas.ts";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");

function makeRepo(name: string): string {
  const dir = scratchDir(name);
  const done = spawnSync("git", ["init", "-q", dir]);
  if (done.status !== 0) throw new Error(`git init 失败：${done.stderr.toString()}`);
  return dir;
}

const stderr = (run: CliRun): string => run.stderr.toString("utf8").replace(/\r\n/gu, "\n");

/** 启动器交给 TS 的参数：在独立的 Python 进程里把 run_handoff 换成“打印解码后的 --pyargs-b64”，选择文件钉成全部
 * python（指向不存在的文件），走真的 main、argparse、cmd_ui 与 ts_launch_command。 */
function launcherPyargs(argv: readonly string[], cwd: string): Record<string, unknown> {
  const program = [
    "import base64, sys",
    `sys.path.insert(0, ${JSON.stringify(join(REPO_ROOT, "scripts"))})`,
    "import pi_dispatch as pd",
    `pd.KERNEL_IMPL_PATH = pd.Path(${JSON.stringify(join(cwd, "absent-selector.json"))})`,
    "def capture(cmd, env=None):",
    "    sys.stdout.write(base64.b64decode(cmd[cmd.index('--pyargs-b64') + 1]).decode('utf-8'))",
    "    return 0",
    "pd.run_handoff = capture",
    `sys.exit(pd.main(${JSON.stringify(argv)}))`,
  ].join("\n");
  const done = spawnSync(process.env["THEMIS_PYTHON"] ?? "python", ["-c", program], { cwd, encoding: "utf8", timeout: 60_000 });
  expect(done.status, done.stderr).toBe(0);
  return JSON.parse(done.stdout) as Record<string, unknown>;
}

describe("ui 的转交", () => {
  it.each([["选择文件全是 python", runPythonCli], ["readonly 是 ts", runLauncherCli]] as const)(
    "%s：照样交给 TS；不带 --desktop 退出 2，提示管理台只由桌面应用启动",
    (_name, run) => {
      const repo = makeRepo("ui-desk");
      try {
        const done = run(["--repo", repo, "ui"], repo);
        expect(done.status).toBe(2);
        expect(done.stdout.length).toBe(0);
        expect(stderr(done)).toBe("ERROR: 管理台只由桌面应用启动\n");
      } finally {
        removeDir(repo);
      }
    },
  );

  it("找不到前端资源目录：退出 2", () => {
    const repo = makeRepo("ui-assets");
    try {
      const done = runPythonCli(["--repo", repo, "ui", "--desktop", "--assets", join(repo, "missing")], repo);
      expect(done.status).toBe(2);
      expect(stderr(done)).toMatch(/^ERROR: 找不到前端资源目录：/u);
    } finally {
      removeDir(repo);
    }
  });

  it("启动器交出的参数过 pyargs-v1，各项照 argparse 与 cmd_ui", () => {
    const repo = makeRepo("ui-args");
    try {
      mkdirSync(join(repo, "web"));
      const pyargs = launcherPyargs(["--repo", repo, "ui", "--desktop", "--assets", join(repo, "web"), "--transcript", "a.jsonl",
        "--transcript", "b", "--idle-timeout", "30"], repo);
      expect(schemaErrors("pyargs-v1", pyargs)).toEqual([]);
      expect(pyargs).toMatchObject({
        command: ["ui"], desktop: true, assets: join(repo, "web"), transcript: ["a.jsonl", "b"], idle_timeout: 30,
      });
      expect(String(pyargs["kernel"]).toLowerCase()).toBe(join(REPO_ROOT, "scripts", "pi_dispatch.py").toLowerCase());
      expect(spawnSync(String(pyargs["python"]), ["-c", "print(1)"]).status).toBe(0);
      const root = spawnSync("git", ["-C", repo, "rev-parse", "--show-toplevel"], { encoding: "utf8" }).stdout.trim();
      expect(resolve(String(pyargs["repo"])).toLowerCase()).toBe(resolve(root).toLowerCase());
      const bare = launcherPyargs(["--repo", repo, "ui"], repo);
      expect(schemaErrors("pyargs-v1", bare)).toEqual([]);
      expect(bare).toMatchObject({ desktop: false, assets: null, transcript: [], idle_timeout: null });
    } finally {
      removeDir(repo);
    }
  });

  it("不在 Git 仓库里：调度器照原文报错，不转交", () => {
    const plain = scratchDir("ui-plain");
    try {
      const done = runPythonCli(["--repo", plain, "ui", "--desktop"], plain);
      expect(done.status).not.toBe(0);
      expect(stderr(done)).toMatch(/^ERROR: /u);
      expect(stderr(done)).not.toMatch(/管理台|前端资源/u);
    } finally {
      removeDir(plain);
    }
  });
});
