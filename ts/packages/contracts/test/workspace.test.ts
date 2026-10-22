// 工作区的包名解析：包之间按包名 import（@themis/base/publish），两种运行方式都要解析到 ts/packages/ 下的
// 真实源文件。Node 不剥离 node_modules 里 .ts 的类型：要是解析停在 node_modules 的链接上，Node 后备就跑不起来。
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const CONTRACTS = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PUBLISH = resolve(CONTRACTS, "..", "base", "src", "publish.ts");
const PRINT = "process.stdout.write(import.meta.resolve('@themis/base/publish'))";

describe("工作区的包名解析", () => {
  it.each([
    ["node", ["--input-type=module", "-e", PRINT]],
    ["bun", ["-e", PRINT]],
  ] as const)("%s：@themis/base/publish 解析到 ts/packages/base/src/publish.ts，不经 node_modules", (command, args) => {
    const done = spawnSync(command, args, { cwd: CONTRACTS, encoding: "utf8" });
    expect(done.error).toBeUndefined();
    expect(done.status).toBe(0);
    const path = fileURLToPath(done.stdout.trim());
    expect(path.toLowerCase()).toBe(PUBLISH.toLowerCase()); // Windows 的盘符大小写可能不同
    expect(path).not.toMatch(/node_modules/);
  });
});
