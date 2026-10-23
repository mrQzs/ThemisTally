// runUi 的参数检查（§5.1）：骨架的部分。经调度器转交的端到端用例在 contracts/test/ui.contract.test.ts。
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PassThrough } from "node:stream";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { EXIT_USAGE, type UiArgs, checkArgs, runUi } from "../src/main.ts";

describe("ui 的参数", () => {
  let dir = "";
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "themis-ui-args-"));
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  const base = (): UiArgs => ({
    command: ["ui"], repo: dir, desktop: true, assets: dir, transcript: [], idle_timeout: null, python: "python", kernel: "pd.py",
  });

  it("不带 --desktop：退出 2，提示管理台只由桌面应用启动", async () => {
    const stderr = new PassThrough();
    const chunks: Buffer[] = [];
    stderr.on("data", (chunk: Buffer) => chunks.push(chunk));
    const code = await runUi({ ...base(), desktop: false }, { stdout: new PassThrough(), stderr });
    expect(code).toBe(EXIT_USAGE);
    expect(Buffer.concat(chunks).toString("utf8")).toBe("ERROR: 管理台只由桌面应用启动\n");
  });

  it("前端资源目录不在、不是目录、没给：用法错误", () => {
    expect(checkArgs({ ...base(), assets: join(dir, "missing") })).toMatch(/^找不到前端资源目录/u);
    expect(checkArgs({ ...base(), assets: null })).toMatch(/^找不到前端资源目录/u);
    expect(checkArgs(base())).toBeNull();
  });

  it("空闲时限必须是正整数", () => {
    expect(checkArgs({ ...base(), idle_timeout: 0 })).toMatch(/^--idle-timeout/u);
    expect(checkArgs({ ...base(), idle_timeout: -5n })).toMatch(/^--idle-timeout/u);
    expect(checkArgs({ ...base(), idle_timeout: 30 })).toBeNull();
    expect(checkArgs({ ...base(), idle_timeout: 30n })).toBeNull();
  });
});
