// 19 条读路由的 argv 模板都能被内核真正的解析器解析（桌面端 §5.3、D05、U4）：起真 Python，用内核自己的
// build_parser（pi_dispatch、kit_config、kit_logs、kit_plugins）逐条解析模板；解析不了即失败，模板带 --json 时
// 断言解析结果的 json 为真；--version 的 SystemExit(0) 算通过。不新增或修改内核的命令与选项。
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { READ_ROUTE_ARGV, READ_ROUTE_SPECS } from "../src/readroutes.ts";
import { REPO_ROOT } from "./harness.ts";

const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const SCRIPTS = join(REPO_ROOT, "scripts");
/** 模板里不取值的开关选项（长选项，但不写成 --opt=值）。 */
const VALUELESS_FLAGS = new Set(["--version", "--json"]);

/**
 * 用内核真正的解析器解析一条 argv；返回 {ok, json} 或 SystemExit 的退出码。命令行是
 * `<python> <kernel> --repo <仓库> <argv…>`：`status` 与 `--version` 由 pi_dispatch 自己的解析器接；`logs`、
 * `plugins`、`config` 在 argparse 之前被截获转发给 kit_logs、kit_plugins、kit_config，那三个模块的解析器不收
 * 组名（是 `list --json`，不是 `logs list --json`），所以按组名剥掉第一项再解析。
 */
function parseWithKernel(argv: readonly string[]): { status: number; stdout: string; stderr: string } {
  const program = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(SCRIPTS)})`,
    "import pi_dispatch as pd, kit_config, kit_logs, kit_plugins",
    "argv = json.loads(sys.argv[1])",
    "if argv[:1] in (['--version'], ['status']):",
    "    parser = pd.build_parser()",
    "elif argv[:1] == ['logs']:",
    "    parser = kit_logs.build_parser()",
    "    argv = argv[1:]",
    "elif argv[:1] == ['plugins']:",
    "    parser = kit_plugins.build_parser()",
    "    argv = argv[1:]",
    "elif argv[:1] == ['config']:",
    "    parser = kit_config.build_parser()",
    "    argv = argv[1:]",
    "else:",
    "    raise SystemExit('没有匹配的解析器：%r' % (argv[:1],))",
    "args = parser.parse_args(argv)",
    "sys.stdout.write(json.dumps({'json': bool(getattr(args, 'json', False))}))",
  ].join("\n");
  const done = spawnSync(PYTHON, ["-c", program, JSON.stringify([...argv])], { encoding: "utf8", timeout: 120_000 });
  return { status: done.status ?? -1, stdout: done.stdout ?? "", stderr: done.stderr ?? "" };
}

describe("argv 模板过内核真正的解析器（U4）", () => {
  it("每条模板都解析得了；带 --json 的解析结果 json 为真", () => {
    for (const [name, argv] of Object.entries(READ_ROUTE_ARGV)) {
      const done = parseWithKernel(argv);
      expect(done.status, `${name}（${argv.join(" ")}）解析失败：${done.stderr.slice(0, 400)}`).toBe(0);
      if (argv.includes("--json")) {
        expect(JSON.parse(done.stdout)["json"], `${name} 应带 --json`).toBe(true);
      }
    }
  });

  it("--version 的 SystemExit(0) 算通过（argparse 的 version 动作）", () => {
    const program = [
      "import sys",
      `sys.path.insert(0, ${JSON.stringify(SCRIPTS)})`,
      "import pi_dispatch as pd",
      "pd.build_parser().parse_args(['--version'])",
    ].join("\n");
    const done = spawnSync(PYTHON, ["-c", program], { encoding: "utf8", timeout: 120_000 });
    expect(done.status).toBe(0);
    expect(done.stdout).toContain("pi_dispatch");
  });

  it("19 条读路由一条不少，每条都有 argv 模板", () => {
    for (const spec of READ_ROUTE_SPECS) {
      expect(READ_ROUTE_ARGV[spec.name], spec.name).toBeDefined();
    }
    expect(READ_ROUTE_SPECS).toHaveLength(19);
  });

  it("模板里的选项值一律写成 --opt=值，位置参数不以 - 开头", () => {
    for (const [name, argv] of Object.entries(READ_ROUTE_ARGV)) {
      for (const [index, part] of argv.entries()) {
        // 取值的选项一律 --opt=值；不取值的开关（--version、--json）除外
        if (part.startsWith("--") && !VALUELESS_FLAGS.has(part)) expect(part, `${name} 的第 ${index} 项`).toContain("=");
      }
      for (const part of argv) {
        if (!part.startsWith("--")) expect(part.startsWith("-"), `${name} 的位置参数不应以 - 开头：${part}`).toBe(false);
      }
    }
  });
});
