// Node 后备的辅助进程（themistally-15 复核 ④a 的第 2、5 条）：Bun 从哪里找、辅助进程起不来时报清楚的错而不是让调用方
// 崩掉、取消经辅助进程传到被监督的子进程。Vitest 跑在 Node 上，runSupervised 与 acquireFileLock 走的都是辅助进程。
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { acquireFileLock, bunExecutable, findBunOnPath } from "../src/native.ts";
import { runSupervised } from "../src/supervise.ts";

const onWindows = process.platform === "win32";
const PY = process.env["THEMIS_PYTHON"] ?? "python";
const STAMP = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "node_modules", ".themis-installed");
const ABORT_FIXTURE = resolve(dirname(fileURLToPath(import.meta.url)), "fixtures", "abort-through-helper.ts");

describe("Node 后备的辅助进程", () => {
  let dir = "";
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "themis-helper-"));
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it.skipIf(!onWindows)("PATH 上找 Bun 照 find_bun：任何一处的 bun.exe 优先，其次第一个 npm 垫片旁边那个；相对路径与空项跳过，找不到为 null", () => {
    const touch = (path: string): string => {
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, "");
      return path;
    };
    const direct = touch(join(dir, "direct", "bun.exe"));
    touch(join(dir, "npm", "bun.cmd"));
    const shimmed = touch(join(dir, "npm", "node_modules", "bun", "bin", "bun.exe"));
    touch(join(dir, "bare", "bun.cmd")); // 垫片旁边没有 bun.exe
    const rel = relative(process.cwd(), join(dir, "direct"));
    const npm = join(dir, "npm");
    expect(findBunOnPath({ PATH: [npm, join(dir, "direct")].join(";") })).toBe(direct); // 垫片在前也是 bun.exe 优先
    expect(findBunOnPath({ Path: ["", join(dir, "bare"), npm].join(";") })).toBeNull(); // 第一个垫片旁边没有就是没有
    expect(findBunOnPath({ Path: ["", npm, join(dir, "bare")].join(";") })).toBe(shimmed);
    expect(findBunOnPath({ PATH: [rel, npm].join(";") })).toBe(shimmed); // 相对路径里的 bun.exe 不算
    expect(findBunOnPath({ PATH: join(dir, "bare") })).toBeNull();
    expect(findBunOnPath({})).toBeNull();
  });

  it("起 Bun 用的可执行文件：THEMIS_BUN 优先，其次装好戳记里的 bun_path", () => {
    expect(bunExecutable({ THEMIS_BUN: "X:\\bun\\bun.exe" })).toBe("X:\\bun\\bun.exe");
    const stamp = JSON.parse(readFileSync(STAMP, "utf8")) as { bun_path: string };
    expect(bunExecutable({ PATH: "" })).toBe(stamp.bun_path);
  });

  it.skipIf(!onWindows)("辅助进程起不来：进程监督与文件锁都报清楚的错，调用方不崩", async () => {
    const saved = process.env["THEMIS_NATIVE_CMD"];
    process.env["THEMIS_NATIVE_CMD"] = JSON.stringify([join(dir, "no-such-bun.exe"), "helper.ts"]);
    try {
      await expect(runSupervised([PY, "-c", "pass"], {
        cwd: dir, env: [], timeout: 30, grace: 1,
        stdout: { path: join(dir, "out"), how: "create-new" }, stderr: { path: join(dir, "err"), how: "create-new" },
      })).rejects.toThrow(/起不了进程监督的辅助进程.*no-such-bun\.exe/u);
      await expect(acquireFileLock(join(dir, ".lock"), 1)).rejects.toThrow(/起不了文件锁的辅助进程.*no-such-bun\.exe/u);
    } finally {
      if (saved === undefined) delete process.env["THEMIS_NATIVE_CMD"];
      else process.env["THEMIS_NATIVE_CMD"] = saved;
    }
  });

  it.skipIf(!onWindows)("signal 取消经辅助进程传过去：照中断处理，子进程被结束；handleSignals 为 false 时不装监听器", () => {
    // 场景在单独的 Node 进程里跑，由 Python 包装器以 CREATE_NO_WINDOW 起、有自己的控制台（fixtures/abort-through-helper.ts）：
    // 进程监督有毛病时 CTRL_BREAK 会广播给整个控制台，不能打到 vitest 与外层的 mutate、shell（第 72 轮的起因）
    const wrapper = [
      "import json, subprocess, sys",
      "done = subprocess.run(json.loads(sys.argv[1]), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,",
      "                      creationflags=0x08000000, timeout=90)",
      "sys.stdout.buffer.write(done.stdout); sys.stderr.buffer.write(done.stderr)",
      "sys.exit(done.returncode)",
    ].join("\n");
    const done = spawnSync(PY, ["-c", wrapper, JSON.stringify([process.execPath, ABORT_FIXTURE, dir, PY])], {
      encoding: "utf8", timeout: 120_000,
    });
    expect(done.status, done.stderr).toBe(0);
    const outcome = JSON.parse(done.stdout) as { result: Record<string, unknown>; before: number; during: number; elapsed: number };
    expect(outcome.result).toMatchObject({ interrupted: true, timed_out: false, kill_method: "job-object" });
    expect(outcome.elapsed).toBeLessThan(15_000);
    expect(outcome.during).toBe(outcome.before);
  }, 150_000);
});
