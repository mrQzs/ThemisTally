// --repo 校验（切换 c3a；覆盖审计列的缺口：test_legacy_cli 的 LB-EXIT-029、test_kit_v300 的 RepoArgument）：--repo 指向不是
// Git 仓库的目录、不存在的路径、一个文件时，一行 ERROR、退出 2，不冒堆栈。dispatcher 的转交不先找仓库，这一步由 TS 自己做
// （readonly 的转交先由 Python 找仓库，status、logs 经启动器时不碰 TS，这里不测它们）。几条有代表性的调度器命令，四种 runner
// 比退出码与两路输出（路径换成占位符）。进程的当前目录另放在一个空目录里。不写转义序列。
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { LF, RUNNERS, normalize, put, pyargsOf, removeCreated, runCommand, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const PLAIN = tempDir("ra-plain");
put(PLAIN, "README.md", `x${LF}`);
const KINDS: [string, string][] = [
  ["不是 Git 仓库的目录", PLAIN],
  ["不存在的路径", join(PLAIN, "no-such-dir")],
  ["一个文件", join(PLAIN, "README.md")],
];
const CWD = tempDir("ra-cwd");
const COMMANDS = [
  ["metrics"], ["status", "--assess"], ["validate", "t1.v1"], ["prepare", "t1.v1"], ["wait", "t1"],
  ["release-check"], ["sync-adapters", "--check"], ["decisions", "replay"],
];

describe("--repo 不对：一行 ERROR，退出 2", () => {
  for (const [kind, target] of KINDS) {
    for (const argv of COMMANDS) {
      it(`${kind}：${argv.join(" ")}`, () => {
        const results = RUNNERS.map((runner) => {
          const result = runCommand(runner, target, argv, pyargsOf(target, argv), CWD);
          const paths = { "<TARGET>": target, "<CWD>": CWD };
          return { status: result.status, stdout: normalize(result.stdout.toString("utf8"), paths), stderr: normalize(result.stderr.toString("utf8"), paths) };
        });
        for (const result of results.slice(1)) expect(result).toEqual(results[0]);
        const first = results[0] as (typeof results)[number];
        expect([first.status, first.stdout], first.stderr).toEqual([2, ""]);
        expect(first.stderr.trimEnd().split(LF).length, "只有一行 ERROR").toBe(1);
        expect(first.stderr.startsWith("ERROR: ")).toBe(true);
      }, 60_000);
    }
  }
});
