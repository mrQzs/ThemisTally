// native 的白盒测试（Vitest 跑在 Node 上，走的是辅助进程那一路）：契约观察不到的约定。
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { FileLockLost, acquireFileLock, withFileLock } from "../src/native.ts";

describe("native 文件锁（Node 经辅助进程）", () => {
  let dir = "";
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "themis-native-"));
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it("辅助进程在持锁期间死了：锁当作已丢，assertHeld 报 FileLockLost，不再开始新的写入", async () => {
    const lock = await acquireFileLock(join(dir, ".events.lock"), 5);
    expect(lock.helperPid).toBeGreaterThan(0);
    lock.assertHeld();
    process.kill(lock.helperPid ?? 0);
    const until = Date.now() + 10_000;
    for (;;) {
      try {
        lock.assertHeld();
      } catch (error) {
        expect(error).toBeInstanceOf(FileLockLost);
        break;
      }
      if (Date.now() > until) throw new Error("辅助进程死了，锁却还算持有");
      await new Promise((done) => setTimeout(done, 20));
    }
    await lock.release();
  });

  it("辅助进程手上有活动句柄时，stdin 一关照样在限时内退出，锁也放掉", async () => {
    const helper = resolve(dirname(fileURLToPath(import.meta.url)), "..", "src", "native-helper.ts");
    const child = spawn("bun", [helper, "__native"], { stdio: ["pipe", "pipe", "pipe"] });
    const answers: string[] = [];
    child.stdout.setEncoding("utf8").on("data", (chunk: string) => answers.push(...chunk.split("\n").filter(Boolean)));
    const exited = new Promise<number | null>((done) => child.on("exit", done));
    const waitFor = async (count: number): Promise<void> => {
      const until = Date.now() + 10_000;
      while (answers.length < count) {
        if (Date.now() > until) throw new Error(`辅助进程没有回话：${answers.join(" | ")}`);
        await new Promise((done) => setTimeout(done, 20));
      }
    };
    child.stdin.write(`${JSON.stringify({ op: "lock", path: join(dir, ".events.lock"), wait: 5 })}\n`);
    await waitFor(1);
    child.stdin.write(`${JSON.stringify({ op: "__test_keepalive" })}\n`);
    await waitFor(2);
    expect(answers).toEqual(['{"ok":true}', '{"ok":true}']);
    child.stdin.end(); // 父进程“死了”
    const code = await Promise.race([exited, new Promise<string>((done) => setTimeout(() => done("没退出"), 5000))]);
    child.kill();
    expect(code).toBe(0);
    const again = await acquireFileLock(join(dir, ".events.lock"), 2); // 锁放掉了
    await again.release();
  });

  it("withFileLock 做完就放；放掉之后 assertHeld 报 FileLockLost", async () => {
    let kept: { assertHeld(): void } | undefined;
    const value = await withFileLock(join(dir, ".state.lock"), (lock) => {
      kept = lock;
      return 42;
    }, 5);
    expect(value).toBe(42);
    expect(() => kept?.assertHeld()).toThrow(FileLockLost);
    // 放掉了：再拿一次立刻成功
    const again = await acquireFileLock(join(dir, ".state.lock"), 1);
    await again.release();
  });
});
