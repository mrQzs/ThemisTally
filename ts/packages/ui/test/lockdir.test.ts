// 每仓库一个的锁（桌面端 §5.4、T19）：mkdir 的原子性拿锁、owner.json 的判读、接管与 busy 的三种原因、释放只删自己
// 的锁；pid 活着时探 127.0.0.1 上的端口——连接被拒是 pid 被系统复用（接管），连上了、超时、别的错误都是对方在跑。
// 用系统临时目录当仓库，不写进工作区。
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer, type AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LOCK_DIR, LOCK_STARTUP_MS, PROBE_TAKEOVER_MIN_AGE_MS, acquireUiLock, busyMessage, probePort } from "../src/lockdir.ts";

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
  it("拿锁：建目录、写 owner.json、读回来一致", async () => {
    const result = await acquireUiLock(repo, { pid: 4242, pidAlive: neverAlive });
    if (!("lock" in result)) throw new Error("竟然被占了");
    result.lock.writeOwner(53123);
    expect(result.lock.readOwner()).toMatchObject({ pid: 4242, port: 53123 });
    expect(result.lock.readOwner()?.token).toBe(result.lock.token);
  });

  it("持有者活着：busy，提示原文带 pid 与端口（T19：端口连上了才算对方在跑）", async () => {
    writeOwner({ pid: 777, port: 45999, token: "live", at: 1 });
    const result = await acquireUiLock(repo, { pid: 1, pidAlive: alwaysAlive, probePort: async () => "connected" });
    expect(result).toEqual({ busy: { pid: 777, port: 45999, why: "running" } });
    expect(busyMessage((result as { busy: Parameters<typeof busyMessage>[0] }).busy)).toBe(
      "本仓库已有本机服务在运行（pid 777，端口 45999）",
    );
  });

  it("pidAlive 为 null：busy，不接管", async () => {
    writeOwner({ pid: 888, port: 1, token: "x", at: 1 });
    const result = await acquireUiLock(repo, { pid: 1, pidAlive: () => null });
    expect(result).toEqual({ busy: { pid: 888, port: 1, why: "unknown" } });
    expect(busyMessage((result as { busy: Parameters<typeof busyMessage>[0] }).busy)).toBe(
      "无法确认 .agent/.ui.lock 的持有者（pid 888）是否还在运行",
    );
  });

  it("pid 已经不在：接管（删掉重建）", async () => {
    writeOwner({ pid: 999, port: 1, token: "stale", at: 1 });
    const result = await acquireUiLock(repo, { pid: 4321, pidAlive: neverAlive });
    if (!("lock" in result)) throw new Error(`竟然被占了：${JSON.stringify(result)}`);
    result.lock.writeOwner(4321); // 接管之后由服务写 owner.json
    expect(result.lock.readOwner()).toMatchObject({ pid: 4321 });
    expect(result.lock.readOwner()?.token).toBe(result.lock.token);
  });

  it("owner.json 缺失且锁目录新建：busy（对方正在启动）", async () => {
    mkdirSync(lockDir(), { recursive: true });
    const result = await acquireUiLock(repo, { pid: 1, pidAlive: neverAlive, now: () => 1_000_000 });
    expect(result).toEqual({ busy: { pid: 0, port: null, why: "starting" } });
    expect(busyMessage((result as { busy: Parameters<typeof busyMessage>[0] }).busy)).toBe(
      "本仓库已有本机服务正在启动（.agent/.ui.lock）",
    );
  });

  it("owner.json 读不出（坏的 JSON）且锁目录老：接管", async () => {
    mkdirSync(lockDir(), { recursive: true });
    writeFileSync(join(lockDir(), "owner.json"), "{ 不是 JSON");
    const now = Date.now() + LOCK_STARTUP_MS + 60_000;
    const result = await acquireUiLock(repo, { pid: 5, pidAlive: neverAlive, now: () => now });
    if (!("lock" in result)) throw new Error(`竟然被占了：${JSON.stringify(result)}`);
    result.lock.writeOwner(5);
    expect(result.lock.readOwner()).toMatchObject({ pid: 5 });
  });

  it("owner.json 读不出且锁目录还新：busy", async () => {
    mkdirSync(lockDir(), { recursive: true });
    writeFileSync(join(lockDir(), "owner.json"), "{ 不是 JSON");
    const result = await acquireUiLock(repo, { pid: 5, pidAlive: neverAlive });
    expect(result).toEqual({ busy: { pid: 0, port: null, why: "starting" } });
  });

  it("三种 busy 的提示逐字固定（长期断言照这三句）", () => {
    expect(busyMessage({ pid: 777, port: 45999, why: "running" })).toBe("本仓库已有本机服务在运行（pid 777，端口 45999）");
    expect(busyMessage({ pid: 0, port: null, why: "starting" })).toBe("本仓库已有本机服务正在启动（.agent/.ui.lock）");
    // unknown 那条点名锁目录与 pid，且带上 .agent/ 这一级——漏掉这一级的简写不是原文
    const unknown = busyMessage({ pid: 888, port: null, why: "unknown" });
    expect(unknown).toBe(`无法确认 ${LOCK_DIR} 的持有者（pid 888）是否还在运行`);
    expect(unknown).not.toContain("无法确认 .ui.lock 的持有者");
  });

  it("释放只删自己的锁：令牌被换掉就不动", async () => {
    const first = await acquireUiLock(repo, { pid: 1, pidAlive: neverAlive });
    if (!("lock" in first)) throw new Error("拿不到锁");
    first.lock.writeOwner(1);
    first.lock.release();
    expect(existsSync(lockDir())).toBe(false);

    const second = await acquireUiLock(repo, { pid: 2, pidAlive: neverAlive });
    if (!("lock" in second)) throw new Error("拿不到锁");
    second.lock.writeOwner(2);
    const payload = JSON.parse(readFileSync(join(lockDir(), "owner.json"), "utf8")) as Record<string, unknown>;
    payload["token"] = "someone-else";
    writeFileSync(join(lockDir(), "owner.json"), JSON.stringify(payload));
    second.lock.release();
    expect(existsSync(lockDir())).toBe(true);
  });
});

describe("探端口：防 pid 复用（T19）", () => {
  it("自己的 pid 加一个关闭的端口：连接被拒 → 接管（pid 已经被系统复用）", async () => {
    writeOwner({ pid: process.pid, port: 45998, token: "mine", at: 1 });
    const result = await acquireUiLock(repo, {
      pid: 4321,
      pidAlive: alwaysAlive,
      probePort: async () => "refused",
      now: () => Date.now() + PROBE_TAKEOVER_MIN_AGE_MS + 60_000, // 锁已经有一会儿了：不是刚起步的那一个
    });
    if (!("lock" in result)) throw new Error(`竟然被占了：${JSON.stringify(result)}`);
    result.lock.writeOwner(4321); // 接管之后由服务写 owner.json
    expect(result.lock.readOwner()).toMatchObject({ pid: 4321 });
    expect(result.lock.readOwner()?.token).toBe(result.lock.token);
  });

  it("锁目录还新时端口连不上：先当对方在跑（busy running），不抢刚起步的锁", async () => {
    writeOwner({ pid: process.pid, port: 45994, token: "fresh", at: Date.now() });
    const result = await acquireUiLock(repo, { pid: 4321, pidAlive: alwaysAlive, probePort: async () => "refused" });
    expect(result).toEqual({ busy: { pid: process.pid, port: 45994, why: "running" } });
    expect(busyMessage((result as { busy: Parameters<typeof busyMessage>[0] }).busy)).toMatch(
      /^本仓库已有本机服务在运行（pid \d+，端口 45994）$/u,
    );
    expect(existsSync(lockDir())).toBe(true); // 没被删掉重建
  });

  it("端口有人监听：连上了 → busy running（不接管）", async () => {
    writeOwner({ pid: 777, port: 45997, token: "live", at: 1 });
    const result = await acquireUiLock(repo, { pid: 1, pidAlive: alwaysAlive, probePort: async () => "connected" });
    expect(result).toEqual({ busy: { pid: 777, port: 45997, why: "running" } });
  });

  it("探测超时：busy running（不接管）", async () => {
    writeOwner({ pid: 777, port: 45996, token: "live", at: 1 });
    const result = await acquireUiLock(repo, { pid: 1, pidAlive: alwaysAlive, probePort: async () => "timeout" });
    expect(result).toEqual({ busy: { pid: 777, port: 45996, why: "running" } });
  });

  it("别的错误也 busy running；端口为 null 时只看 pid、不探端口", async () => {
    writeOwner({ pid: 777, port: 45995, token: "live", at: 1 });
    const other = await acquireUiLock(repo, { pid: 1, pidAlive: alwaysAlive, probePort: async () => "other" });
    expect(other).toEqual({ busy: { pid: 777, port: 45995, why: "running" } });
    rmSync(lockDir(), { recursive: true, force: true });
    writeOwner({ pid: 777, port: null, token: "live", at: 1 });
    const noPort = await acquireUiLock(repo, {
      pid: 1,
      pidAlive: alwaysAlive,
      probePort: async () => {
        throw new Error("端口为 null 时不该探端口");
      },
    });
    expect(noPort).toEqual({ busy: { pid: 777, port: null, why: "running" } });
    expect(busyMessage((noPort as { busy: Parameters<typeof busyMessage>[0] }).busy)).toBe(
      "本仓库已有本机服务在运行（pid 777，端口 未知）",
    );
  });

  it("默认的 probePort：没人监听 refused，有人监听 connected", async () => {
    const server = createServer();
    await new Promise<void>((done) => server.listen(0, "127.0.0.1", () => done()));
    const address = server.address() as AddressInfo;
    try {
      expect(await probePort(address.port)).toBe("connected");
      await new Promise<void>((done) => server.close(() => done()));
      expect(await probePort(address.port)).toBe("refused");
    } finally {
      server.close();
    }
  });
});
