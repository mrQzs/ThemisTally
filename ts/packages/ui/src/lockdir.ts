// 每仓库一个的本机服务锁（桌面端设计第 7 版 §5.2、§5.4、T19）：<repo>/.agent/.ui.lock 靠 mkdir 的原子性拿锁，拿到之后由
// 服务写 owner.json（pid、端口、锁令牌、时间戳）。锁已经存在时按 owner.json 判断：pid 活着且有端口时，先探
// 127.0.0.1 上的该端口（TCP 连接，1 秒时限）——连接被拒（ECONNREFUSED）说明这个 pid 已经是别人的进程（pid 被
// 系统复用），删锁重建；连上了、超时或别的错误一律 busy running。端口为 null 时只看 pid（活着就 busy，不活着就
// 接管）。pidAlive 为 null（判断不了）也 busy——不接管。owner.json 缺失或读不出时，锁目录建立不到 10 秒算对方
// 正在启动（busy），超过 10 秒才接管。释放只删自己的锁：owner.json 的令牌不是自己就不动。不记进程创建时间
// （base 没有该接口，ui 包不能改 base），防 pid 复用靠探端口。
import { mkdirSync, readFileSync, rmSync, statSync } from "node:fs";
import { connect } from "node:net";
import { join } from "node:path";
import { writeTextAtomic } from "@themis/base/fsutil";
import { randomToken } from "./localhttp/tokens.ts";

/** 锁目录（相对仓库根）。 */
export const LOCK_DIR = ".agent/.ui.lock";
/** owner.json 的名字。 */
export const OWNER_FILE = "owner.json";
/** 锁目录建立不到这么久且没有 owner.json：算对方正在启动。 */
export const LOCK_STARTUP_MS = 10000;
/** 接管时删掉重建最多试几次。 */
export const LOCK_TAKEOVER_ATTEMPTS = 3;
/** 探端口的时限（毫秒）：连不上就是连不上，不拖住拿锁。 */
export const PROBE_TIMEOUT_MS = 1000;

/** 探一个端口的结论：被拒（没人监听）、连上了、超时、别的错误。 */
export type ProbeVerdict = "refused" | "connected" | "timeout" | "other";

export interface LockOwner {
  readonly pid: number;
  readonly port: number | null;
  readonly token: string;
  readonly at: number;
}

/** 被占的原因：对方在跑、对方正在启动、判断不了对方还在不在。 */
export type BusyWhy = "running" | "starting" | "unknown";

export interface BusyLock {
  readonly pid: number;
  readonly port: number | null;
  readonly why: BusyWhy;
}

export interface UiLock {
  readonly dir: string;
  readonly token: string;
  /** 写 owner.json（pid 与令牌是拿锁时定下的）。 */
  writeOwner(port: number | null): void;
  /** 读 owner.json；缺失或读不出为 null。 */
  readOwner(): LockOwner | null;
  /** 释放：owner.json 的令牌是自己的才删。 */
  release(): void;
}

export type AcquireResult = { readonly lock: UiLock } | { readonly busy: BusyLock };

export interface AcquireOptions {
  readonly pid: number;
  readonly pidAlive: (pid: number | null | undefined) => boolean | null;
  readonly now?: (() => number) | undefined;
  /** 探端口（只给测试用）：缺省用 node:net 连 127.0.0.1，1 秒时限。 */
  readonly probePort?: ((port: number) => Promise<ProbeVerdict>) | undefined;
}

/** 被占时的提示原文（调用方加 ERROR: 前缀写进 stderr）。 */
export function busyMessage(busy: BusyLock): string {
  if (busy.why === "running") {
    const port = busy.port === null ? "未知" : String(busy.port);
    return `本仓库已有本机服务在运行（pid ${busy.pid}，端口 ${port}）`;
  }
  if (busy.why === "starting") return "本仓库已有本机服务正在启动（.agent/.ui.lock）";
  return `无法确认 .agent/.ui.lock 的持有者（pid ${busy.pid}）是否还在运行`;
}

function readOwnerFile(dir: string): LockOwner | null {
  try {
    const parsed = JSON.parse(readFileSync(join(dir, OWNER_FILE), "utf8")) as Record<string, unknown>;
    const pid = parsed["pid"];
    if (typeof pid !== "number" || !Number.isFinite(pid)) return null;
    const port = parsed["port"];
    const token = parsed["token"];
    const at = parsed["at"];
    return {
      pid,
      port: typeof port === "number" ? port : null,
      token: typeof token === "string" ? token : "",
      at: typeof at === "number" ? at : 0,
    };
  } catch {
    return null;
  }
}

/** 锁目录的年纪（毫秒）：取不到就当作刚建。 */
function lockAge(dir: string, now: () => number): number {
  try {
    return Math.max(0, now() - statSync(dir).mtimeMs);
  } catch {
    return 0;
  }
}

function removeLock(dir: string): void {
  rmSync(dir, { recursive: true, force: true });
}

function makeLock(dir: string, pid: number): UiLock {
  const token = randomToken();
  return {
    dir,
    token,
    writeOwner(port: number | null): void {
      const owner: LockOwner = { pid, port, token, at: Date.now() };
      writeTextAtomic(join(dir, OWNER_FILE), JSON.stringify(owner));
    },
    readOwner(): LockOwner | null {
      return readOwnerFile(dir);
    },
    release(): void {
      const owner = readOwnerFile(dir);
      if (owner === null || owner.token !== token) return; // 不是自己的锁
      removeLock(dir);
    },
  };
}

/** 探一个端口：TCP 连 127.0.0.1，被拒是 refused，连上是 connected，超时是 timeout，其余错误是 other。 */
export function probePort(port: number): Promise<ProbeVerdict> {
  return new Promise((resolve) => {
    const socket = connect(port, "127.0.0.1");
    let settled = false;
    const done = (verdict: ProbeVerdict): void => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(verdict);
    };
    socket.setTimeout(PROBE_TIMEOUT_MS, () => done("timeout"));
    socket.once("connect", () => done("connected"));
    socket.once("error", (error: NodeJS.ErrnoException) => done(error.code === "ECONNREFUSED" ? "refused" : "other"));
  });
}

/** 拿锁：拿到返回 lock，被占返回 busy（带原因，调用方照 busyMessage 报告）。 */
export async function acquireUiLock(repo: string, options: AcquireOptions): Promise<AcquireResult> {
  const agentDir = join(repo, ".agent");
  const dir = join(agentDir, ".ui.lock");
  const now = options.now ?? Date.now;
  const probe = options.probePort ?? probePort;
  mkdirSync(agentDir, { recursive: true });
  for (let attempt = 0; attempt < LOCK_TAKEOVER_ATTEMPTS; attempt += 1) {
    try {
      mkdirSync(dir);
      return { lock: makeLock(dir, options.pid) };
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
      const owner = readOwnerFile(dir);
      if (owner === null) {
        // 没有 owner.json：正在启动（busy）还是没人要的旧锁（接管）
        if (lockAge(dir, now) < LOCK_STARTUP_MS) return { busy: { pid: 0, port: null, why: "starting" } };
        removeLock(dir);
        continue;
      }
      const alive = options.pidAlive(owner.pid);
      if (alive === true) {
        // pid 活着：有端口就探它，被拒说明 pid 已经被系统复用（接管）；连上了、超时、别的错误都是对方在跑
        if (owner.port === null) return { busy: { pid: owner.pid, port: null, why: "running" } };
        const verdict = await probe(owner.port);
        if (verdict === "refused") {
          removeLock(dir);
          continue;
        }
        return { busy: { pid: owner.pid, port: owner.port, why: "running" } };
      }
      if (alive === null) return { busy: { pid: owner.pid, port: owner.port, why: "unknown" } };
      removeLock(dir); // pid 已经不在：删掉重建
    }
  }
  return { busy: { pid: 0, port: null, why: "starting" } };
}
