// 文件锁（kit_hub.file_lock 与 @themis/base/native）的契约与 ④a 的验证用例（迁移计划第 8.2 节）。
// 三套实现（Python 的 msvcrt.locking、Bun 进程内的 LockFileEx、Node 经辅助进程）必须锁的是同一把操作系统锁：
//   F1 空闲时拿到、放掉，哨兵文件建好；F2 被占时等满报“等文件锁超时：<路径>”（文字进 HubError，逐字比较）；
//   F3 两两互斥，各个方向；F4 持锁进程被强杀后，等待方在超时之内拿到锁。
// POSIX 的 flock 互通还没有在 Linux 或 WSL 上实测：本机只有 Windows，这些用例在 POSIX 上跑过之前标“未实机验证”。
import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { IMPLS, type Impl, removeDir, runProbe, scratchDir, startProbe } from "./harness.ts";

const pairs = IMPLS.flatMap((holder) => IMPLS.filter((waiter) => waiter !== holder).map((waiter) => [holder, waiter] as const));

describe.each(IMPLS)("文件锁契约 impl=$name", (impl) => {
  it("F1 空闲时拿到、放掉；锁文件（和它的目录）不存在就建", () => {
    const dir = scratchDir(`flock-${impl.name}`);
    try {
      const path = join(dir, "ledger", ".events.lock");
      expect(runProbe(impl, { op: "filelock.run", path, wait: 5 })).toMatchObject({ ok: true });
      expect(existsSync(path)).toBe(true);
      expect(runProbe(impl, { op: "filelock.run", path, wait: 5 })).toMatchObject({ ok: true }); // 放掉了，能再拿
    } finally {
      removeDir(dir);
    }
  });

  it("F2 被 Python 占着：等满报“等文件锁超时：<路径>”", async () => {
    const dir = scratchDir(`flock-busy-${impl.name}`);
    const path = join(dir, ".state.lock");
    const holder = startProbe(IMPLS[0] as Impl, { op: "filelock.run", path, hold_ms: 4000, signal: true });
    try {
      await holder.ready;
      expect(runProbe(impl, { op: "filelock.run", path, wait: 1 })).toEqual({ ok: false, error: "timeout", message: `等文件锁超时：${path}` });
      await holder.result;
    } finally {
      holder.stop();
      removeDir(dir);
    }
  });
});

describe("文件锁对照：三套实现锁的是同一把操作系统锁", () => {
  it.each(pairs.map(([holder, waiter]) => [holder.name, waiter.name, holder, waiter] as const))(
    "F3 %s 持有期间 %s 拿不到，放了才拿到",
    async (_h, _w, holder, waiter) => {
      const dir = scratchDir("flock-race");
      const path = join(dir, ".events.lock");
      const held = startProbe(holder, { op: "filelock.run", path, hold_ms: 1500, signal: true });
      try {
        await held.ready;
        const waited = runProbe(waiter, { op: "filelock.run", path, wait: 15 });
        const first = await held.result;
        expect(first).toMatchObject({ ok: true });
        expect(waited).toMatchObject({ ok: true });
        expect(Number(waited["acquired_ms"])).toBeGreaterThanOrEqual(Number(first["released_ms"]) - 50);
      } finally {
        held.stop();
        removeDir(dir);
      }
    },
  );

  it.each(IMPLS.map((holder) => [holder.name, holder] as const))(
    "F4 %s 持锁时被强杀：操作系统放锁，等待方在超时之内拿到",
    async (_h, holder) => {
      const dir = scratchDir("flock-kill");
      const path = join(dir, ".events.lock");
      const held = startProbe(holder, { op: "filelock.run", path, hold_ms: 60_000, signal: true });
      try {
        await held.ready;
        held.stop(); // TerminateProcess：Node 那一路杀的是 Node 进程，它的辅助进程靠 stdin 关闭自行退出
        const waiter = IMPLS.find((impl) => impl !== holder) as Impl;
        const started = Date.now();
        const waited = runProbe(waiter, { op: "filelock.run", path, wait: 20 });
        expect(waited).toMatchObject({ ok: true });
        expect(Date.now() - started).toBeLessThan(20_000);
        await held.result.catch(() => undefined);
      } finally {
        removeDir(dir);
      }
    },
  );
});
