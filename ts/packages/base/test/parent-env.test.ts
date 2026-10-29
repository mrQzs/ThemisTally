// 还原启动器换过名的变量（迁移计划 D3）：照名单还原、名单外的不动；还原要赶在别的模块的顶层代码之前，所以 cli 的 main.ts
// 第一个 import 必须是它，它和排第二的 harden 都不能 import 别的模块（themistally-15 复核切换 b 的设计时要求锁住这个次序）。
// 经真启动器、真 Bun 的端到端（TS 进程自己不受这几个变量影响、子进程拿到原值）在 tests/test_kernel_impl.py。
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { restoreParentEnv } from "../src/parent-env.ts";

const SRC = resolve(dirname(fileURLToPath(import.meta.url)), "..", "src");
const CLI_MAIN = resolve(SRC, "..", "..", "cli", "src", "main.ts");
const LF = String.fromCharCode(10);

/** 文件里 import 语句的行（包括 import(...) 与 require(...)）。 */
function importLines(path: string): string[] {
  return readFileSync(path, "utf8").split(LF).filter((line) => {
    const code = line.trimStart();
    return ["import ", 'import"', "import(", "import{"].some((head) => code.startsWith(head)) || code.includes("require(");
  });
}

describe("restoreParentEnv", () => {
  it("照名单还原成原名，删掉换过名的与名单本身", () => {
    const env: Record<string, string | undefined> = {
      KEEP: "1", THEMIS_PARENT_NODE_OPTIONS: "--x", THEMIS_PARENT_node_path: "D:/p", THEMIS_PARENT_NAMES: "NODE_OPTIONS,node_path",
    };
    restoreParentEnv(env);
    expect(env).toStrictEqual({ KEEP: "1", NODE_OPTIONS: "--x", node_path: "D:/p" });
  });

  it("名单外的 THEMIS_PARENT_ 变量原样留着；名单里有、值却不在的跳过", () => {
    const env: Record<string, string | undefined> = { THEMIS_PARENT_BUN_OPTIONS: "--y", THEMIS_PARENT_NAMES: "NODE_PATH" };
    restoreParentEnv(env);
    expect(env).toStrictEqual({ THEMIS_PARENT_BUN_OPTIONS: "--y" });
  });

  it("没有名单什么也不做", () => {
    const env: Record<string, string | undefined> = { THEMIS_PARENT_NODE_PATH: "D:/p" };
    restoreParentEnv(env);
    expect(env).toStrictEqual({ THEMIS_PARENT_NODE_PATH: "D:/p" });
  });
});

describe("入口的 import 次序", () => {
  it("cli 的 main.ts 先 import parent-env，再 import harden", () => {
    expect(importLines(CLI_MAIN).slice(0, 2).map((line) => line.split(";")[0])).toEqual([
      'import "@themis/base/parent-env"',
      'import "@themis/base/harden"',
    ]);
  });

  it("parent-env 与 harden 自己不 import 任何东西", () => {
    for (const name of ["parent-env.ts", "harden.ts"]) expect(importLines(join(SRC, name)), name).toEqual([]);
  });
});
