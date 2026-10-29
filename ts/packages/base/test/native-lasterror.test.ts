// GetLastError 偶尔被运行时清成 0（r3 §10 第 130 轮）：retryWin32 的规矩、native.ts 里一律经它取、Bun 下起不存在的
// 程序不再报成错误码 0。
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { bunExecutable, retryWin32 } from "../src/native.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const LF = String.fromCharCode(10);

/** attempt 依次交回 results，readError 依次交回 errors（用完了就重复最后一个），并记下各调了几次。 */
function scripted<T>(results: readonly T[], errors: readonly number[]) {
  const calls = { attempts: 0, reads: 0 };
  const attempt = (): T => results[Math.min(calls.attempts++, results.length - 1)] as T;
  const readError = (): number => errors[Math.min(calls.reads++, errors.length - 1)] as number;
  return { calls, attempt, readError };
}
const failed = (value: number): boolean => value === 0;

describe("retryWin32", () => {
  it("成功：交回值，不取错误码", () => {
    const { calls, attempt, readError } = scripted([7], [0]);
    expect(retryWin32(attempt, failed, readError)).toEqual({ value: 7 });
    expect(calls).toEqual({ attempts: 1, reads: 0 });
  });

  it("失败、第一次就取到真的错误码：交它，不重做", () => {
    const { calls, attempt, readError } = scripted([0], [2]);
    expect(retryWin32(attempt, failed, readError)).toEqual({ winerror: 2 });
    expect(calls).toEqual({ attempts: 1, reads: 1 });
  });

  it("失败却取到 0：重做，直到取到真的错误码", () => {
    const { calls, attempt, readError } = scripted([0], [0, 0, 216]);
    expect(retryWin32(attempt, failed, readError)).toEqual({ winerror: 216 });
    expect(calls).toEqual({ attempts: 3, reads: 3 });
  });

  it("重做成功：照成功走", () => {
    const { calls, attempt, readError } = scripted([0, 5], [0]);
    expect(retryWin32(attempt, failed, readError)).toEqual({ value: 5 });
    expect(calls).toEqual({ attempts: 2, reads: 1 });
  });

  it("一直取到 0：做 5 次，交 0", () => {
    const { calls, attempt, readError } = scripted([0], [0]);
    expect(retryWin32(attempt, failed, readError)).toEqual({ winerror: 0 });
    expect(calls).toEqual({ attempts: 5, reads: 5 });
  });
});

describe("native.ts 的源码", () => {
  it("GetLastError 只在两处 lastError 的定义里调，lastError 只交给 retryWin32、不直接调", () => {
    // 带点号的调用才算：FFI 符号表（GetLastError: {…}）、类型声明（GetLastError(): number;）与注释都不带点号
    const source = readFileSync(join(HERE, "..", "src", "native.ts"), "utf8");
    const calls = source.split(LF).filter((line) => line.includes(".GetLastError()")).map((line) => line.trim());
    expect(calls).toEqual([
      "const lastError = (): number => call.GetLastError();",
      "const lastError = (): number => k.GetLastError();",
    ]);
    expect(source).not.toContain("lastError()");
  });
});

describe.runIf(process.platform === "win32")("Bun 下起不存在的程序", () => {
  it("带着分配压力起 3000 次：错误码都是 2，没有一次是 0", () => {
    const done = spawnSync(bunExecutable(), [join(HERE, "fixtures", "spawn-missing.ts"), "3000"], { encoding: "utf8", timeout: 120_000 });
    expect(done.status, done.stderr).toBe(0);
    expect(JSON.parse(done.stdout)).toEqual({ 2: 3000 });
  }, 150_000);
});
