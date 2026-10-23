// 每仓库一个的锁（桌面端 §5.4）：mkdir 的原子性拿锁、owner.json 的判读、接管与 busy 的三种原因、释放只删自己的锁。
// 用系统临时目录当仓库，不写进工作区。
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LOCK_STARTUP_MS, acquireUiLock, busyMessage } from "../src/lockdir.ts";

let repo = "";

beforeEach(() => {
  repo = mkdtempSync(join(tmpdir(), "themis-ui-lock-"));
});

afterEach(() => {
  rmSync(repo, { recursive: true, force: true });
});

const lockDir = (): string => join(repo, ".agent", ".ui.lock");
const writeOwner = (payload: Record<string, unknown>): void => {
  mkdirSync(lockDir(), { recursive: true });
  writeFileSync(join(lockDir(), "owner.json"), JSON.stringify(payload));
};
const neverAlive = (): boolean => false;
const alwaysAlive = (): boolean => true;

describe("锁目录", () => {
  it("拿锁：建目录、写 owner.json、读回来一致", () => {
    const result = acquireUiLock(repo, { pid: 4242, pidAlive: neverAlive });
    if (!("lock" in result)) throw new Error("竟然被占了");
    result.lock.writeOwner(53123);
    expect(result.lock.readOwner()).toMatchObject({ pid: 4242, port: 53123 });
    expect(result.lock.readOwner()?.token).toBe(result.lock.token);
  });

  it("持有者活着：busy，提示原文带 pid 与端口", () => {
    writeOwner({ pid: 777, port: 45999, token: "live", at: 1 });
    const result = acquireUiLock(repo, { pid: 1, pidAlive: alwaysAlive });
    expect(result).toEqual({ busy: { pid: 777, port: 45999, why: "running" } });
    expect(busyMessage((result as { busy: Parameters<typeof busyMessage>[0] }).busy)).toBe(
      "本仓库已有本机服务在运行（pid 777，端口 45999）",
    );
  });

  it("pidAlive 为 null：busy，不接管", () => {
    writeOwner({ pid: 888, port: 1, token: "x", at: 1 });
    const result = acquireUiLock(repo, { pid: 1, pidAlive: () => null });
    expect(result).toEqual({ busy: { pid: 888, port: 1, why: "unknown" } });
    expect(busyMessage((result as { busy: Parameters<typeof busyMessage>[0] }).busy)).toBe(
      "无法确认 .agent/.ui.lock 的持有者（pid 888）是否还在运行",
    );
  });

  it("pid 已经不在：接管（删掉重建）", () => {
    writeOwner({ pid: 999, port: 1, token: "stale", at: 1 });
    const result = acquireUiLock(repo, { pid: 4321, pidAlive: neverAlive });
    if (!("lock" in result)) throw new Error(`竟然被占了：${JSON.stringify(result)}`);
    result.lock.writeOwner(4321); // 接管之后由服务写 owner.json
    expect(result.lock.readOwner()).toMatchObject({ pid: 4321 });
    expect(result.lock.readOwner()?.token).toBe(result.lock.token);
  });

  it("owner.json 缺失且锁目录新建：busy（对方正在启动）", () => {
    mkdirSync(lockDir(), { recursive: true });
    const result = acquireUiLock(repo, { pid: 1, pidAlive: neverAlive, now: () => 1_000_000 });
    expect(result).toEqual({ busy: { pid: 0, port: null, why: "starting" } });
    expect(busyMessage((result as { busy: Parameters<typeof busyMessage>[0] }).busy)).toBe(
      "本仓库已有本机服务正在启动（.agent/.ui.lock）",
    );
  });

  it("owner.json 读不出（坏的 JSON）且锁目录老：接管", () => {
    mkdirSync(lockDir(), { recursive: true });
    writeFileSync(join(lockDir(), "owner.json"), "{ 不是 JSON");
    const now = Date.now() + LOCK_STARTUP_MS + 60_000;
    const result = acquireUiLock(repo, { pid: 5, pidAlive: neverAlive, now: () => now });
    if (!("lock" in result)) throw new Error(`竟然被占了：${JSON.stringify(result)}`);
    result.lock.writeOwner(5);
    expect(result.lock.readOwner()).toMatchObject({ pid: 5 });
  });

  it("owner.json 读不出且锁目录还新：busy", () => {
    mkdirSync(lockDir(), { recursive: true });
    writeFileSync(join(lockDir(), "owner.json"), "{ 不是 JSON");
    const result = acquireUiLock(repo, { pid: 5, pidAlive: neverAlive });
    expect(result).toEqual({ busy: { pid: 0, port: null, why: "starting" } });
  });

  it("释放只删自己的锁：令牌被换掉就不动", () => {
    const first = acquireUiLock(repo, { pid: 1, pidAlive: neverAlive });
    if (!("lock" in first)) throw new Error("拿不到锁");
    first.lock.writeOwner(1);
    first.lock.release();
    expect(existsSync(lockDir())).toBe(false);

    const second = acquireUiLock(repo, { pid: 2, pidAlive: neverAlive });
    if (!("lock" in second)) throw new Error("拿不到锁");
    second.lock.writeOwner(2);
    const payload = JSON.parse(readFileSync(join(lockDir(), "owner.json"), "utf8")) as Record<string, unknown>;
    payload["token"] = "someone-else";
    writeFileSync(join(lockDir(), "owner.json"), JSON.stringify(payload));
    second.lock.release();
    expect(existsSync(lockDir())).toBe(true);
  });
});
