// 三把目录锁：mkdir 成功就持有，owner.json 记持有者。照现行三份实现各自的规则移植（迁移第 ① 步）：
//
//   | 锁         | 现行实现              | 等待间隔 | 被占时                                   | 释放                   |
//   |------------|-----------------------|----------|------------------------------------------|------------------------|
//   | DirLock    | kit_hub.DirLock       | 0.5 秒   | 持有者 pid 确定已死（pidAlive 为 false）才接管 | 令牌一致才删           |
//   | TaskLock   | pi_dispatch.TaskLock  | 0.2 秒   | 锁目录的 mtime 超过 stale 秒就接管        | 无条件删               |
//   | ConfigLock | kit_config.ConfigLock | 0.1 秒   | 从不接管，等满就报错                      | 令牌一致才删           |
//
// owner.json 的字节也照抄（两套实现会互相读对方写的锁）：键的顺序、json.dumps 的缺省写法、末尾换行；
// ConfigLock 用 Path.write_text 写，Windows 上换行是 \r\n。
// DirLock 的接管有竞争（两个等待者同时看到持有者已死，后删的会删掉先建的锁），现行实现如此，照样保留；
// 要修另开内核轮次。kit_hub.file_lock（操作系统的文件锁）不在这里，等原生层定了再做。
import { mkdirSync, rmSync, statSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { hostname } from "node:os";
import { dirname, join } from "node:path";
import { utcNow } from "./clock.ts";
import { readText, sleepSync, writeText, writeTextAtomic } from "./fsutil.ts";
import { pidAlive } from "./process.ts";
import { PyOSError, PyUnicodeDecodeError, pyOSErrorOf, pyReadText } from "./pyio.ts";
import { pyStrValue } from "./pyfmt.ts";
import { type PyDict, PyJsonError, type PyValue, dumps, loads } from "./pyjson.ts";

/** 锁被占用、等满了还没拿到。 */
export class LockBusyError extends Error {
  override readonly name = "LockBusyError";
}

/** 只建最后一级目录：已经存在就返回 false（Python 的 Path.mkdir 抛 FileExistsError）。 */
function makeDir(path: string): boolean {
  try {
    mkdirSync(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "EEXIST") return false;
    throw error;
  }
}

function removeTree(path: string): void {
  rmSync(path, { recursive: true, force: true }); // shutil.rmtree(..., ignore_errors=True)
}

/** owner.json 读成普通对象；读不到、不是对象返回 {}。 */
function readOwner(path: string): Record<string, PyValue> {
  try {
    const value = loads(readText(join(path, "owner.json")) || "{}");
    return value instanceof Map ? Object.fromEntries([...(value as PyDict).entries()].map(([k, v]) => [String(k), v])) : {};
  } catch {
    return {};
  }
}

function ownerJson(fields: readonly (readonly [string, PyValue])[]): string {
  return dumps(new Map(fields)) + "\n"; // json.dumps 缺省写法：ensure_ascii=True、", " 与 ": "
}

/** kit_hub.DirLock：mkdir 加 owner.json；持有者进程确定已死才接管，令牌一致才释放。 */
export class DirLock {
  readonly path: string;
  readonly waitSeconds: number;
  readonly token = randomBytes(8).toString("hex");

  constructor(path: string, waitSeconds = 30) {
    this.path = path;
    this.waitSeconds = waitSeconds;
  }

  acquire(): this {
    const deadline = performance.now() + this.waitSeconds * 1000;
    for (;;) {
      mkdirSync(dirname(this.path), { recursive: true });
      if (makeDir(this.path)) {
        writeTextAtomic(join(this.path, "owner.json"), ownerJson([["pid", BigInt(process.pid)], ["token", this.token], ["at", utcNow()]]));
        return this;
      }
      const owner = this.owner();
      const pid = owner["pid"];
      if (typeof pid === "bigint" && pid > 0n && pidAlive(Number(pid)) === false) {
        removeTree(this.path);
        continue;
      }
      if (performance.now() >= deadline) {
        throw new LockBusyError(`锁被占用：${this.path}（持有者 ${JSON.stringify(owner, (_k, v) => (typeof v === "bigint" ? Number(v) : v))}）`);
      }
      sleepSync(500);
    }
  }

  owner(): Record<string, PyValue> {
    return readOwner(this.path);
  }

  release(): void {
    if (this.owner()["token"] === this.token) removeTree(this.path);
  }
}

/** pi_dispatch.TaskLock：<runs>/<task>/.task.lock；锁目录的 mtime 超过 stale 秒就接管，释放时无条件删。 */
export class TaskLock {
  readonly path: string;
  readonly waitSeconds: number;
  readonly staleSeconds: number;

  constructor(runsDir: string, taskId: string, waitSeconds = 30, staleSeconds = 300) {
    this.path = join(runsDir, taskId, ".task.lock");
    this.waitSeconds = waitSeconds;
    this.staleSeconds = staleSeconds;
  }

  acquire(): this {
    mkdirSync(dirname(this.path), { recursive: true });
    const deadline = performance.now() + this.waitSeconds * 1000;
    for (;;) {
      if (makeDir(this.path)) {
        writeText(join(this.path, "owner.json"), ownerJson([["pid", BigInt(process.pid)], ["at", utcNow()]]));
        return this;
      }
      let age = 0;
      try {
        age = Date.now() / 1000 - statSync(this.path).mtimeMs / 1000;
      } catch {
        age = 0;
      }
      if (age > this.staleSeconds) {
        removeTree(this.path); // 临界区只需毫秒级；超过阈值视为持有者已崩溃
        continue;
      }
      if (performance.now() > deadline) {
        throw new LockBusyError(`任务锁被占用：${this.path}（另一个 run 正在领取；如确认无人使用可删除该目录）`);
      }
      sleepSync(200);
    }
  }

  release(): void {
    removeTree(this.path);
  }
}

/** 配置锁的 owner.json 写不进去：Python 报“写不进配置锁 <路径>：<OSError>”。 */
export class LockWriteError extends Error {
  override readonly name = "LockWriteError";
}

/** kit_config._read_owner：读不出、不是合法 JSON 或不是对象时为 null（与 readOwner 的“读不出当作 {}”不同）。 */
function readConfigOwner(path: string): PyDict | null {
  try {
    const value = loads(pyReadText(join(path, "owner.json")));
    return value instanceof Map ? value : null;
  } catch (error) {
    if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError) return null;
    if (error instanceof PyJsonError && error.kind !== "RecursionError") return null;
    throw error;
  }
}

/** kit_config.ConfigLock._busy_message：写明持有者是否还在运行；同一台主机上才判断，pid 不是 int 时写 None。 */
function configLockBusyMessage(path: string): string {
  const owner = readConfigOwner(path);
  let who = "持有者信息读不出来";
  if (owner !== null) {
    const raw = owner.get("pid");
    const pid = typeof raw === "bigint" || typeof raw === "boolean" ? raw : null; // isinstance(x, int)：bool 也算
    const host = owner.has("host") ? (owner.get("host") as PyValue) : null;
    let state = "在另一台主机上，无法判断是否在运行";
    if (host === hostname()) {
      // pid_alive(True) 查的是 "PID eq 1"，再找字符串 "True"：永远找不到
      const alive = pid === true ? false : pidAlive(pid === null || pid === false ? null : Number(pid));
      state = alive === true ? "仍在运行" : alive === false ? "已退出" : "无法判断是否在运行";
    }
    const created = owner.has("created_at") ? (owner.get("created_at") as PyValue) : null;
    who = `进程 ${pyStrValue(pid)}（主机 ${pyStrValue(host)}，${state}，${pyStrValue(created)} 起持有）`;
  }
  return `配置锁被占用：${path}，${who}。确认没有别的写配置的命令在运行之后，删除这个目录再重试（锁从不自动清除）`;
}

/** kit_config 的 LOCK_NAME 与 LOCK_WAIT_SECONDS。 */
export const CONFIG_LOCK_NAME = ".config.lock";
export const CONFIG_LOCK_WAIT_SECONDS = 30;

/** kit_config.ConfigLock：<.agent>/.config.lock；从不自动接管，令牌一致才释放。 */
export class ConfigLock {
  readonly path: string;
  readonly waitSeconds: number;
  readonly token = randomBytes(16).toString("hex");

  constructor(agentDir: string, waitSeconds: number = CONFIG_LOCK_WAIT_SECONDS) {
    this.path = join(agentDir, CONFIG_LOCK_NAME);
    this.waitSeconds = waitSeconds;
  }

  acquire(): this {
    mkdirSync(dirname(this.path), { recursive: true });
    const deadline = performance.now() + this.waitSeconds * 1000;
    while (!makeDir(this.path)) {
      if (performance.now() >= deadline) {
        throw new LockBusyError(configLockBusyMessage(this.path));
      }
      sleepSync(100);
    }
    const ownerFile = join(this.path, "owner.json");
    try {
      const text = ownerJson([
        ["pid", BigInt(process.pid)],
        ["host", hostname()],
        ["token", this.token],
        ["created_at", utcNow()],
      ]);
      // Path.write_text 用文本模式：Windows 上 \n 写成 \r\n
      writeText(ownerFile, process.platform === "win32" ? text.replace(/\n/g, "\r\n") : text, false);
    } catch (error) {
      removeTree(this.path); // 目录已建、初始化没完成：删掉锁，否则它永远不会被自动清除
      const os = pyOSErrorOf(error, ownerFile);
      if (os !== null) throw new LockWriteError(`写不进配置锁 ${this.path}：${os.message}`);
      throw error;
    }
    return this;
  }

  release(): void {
    if (readOwner(this.path)["token"] === this.token) removeTree(this.path);
  }
}

/** 拿着锁做一件事，做完（或出错）释放。 */
export function withLock<T>(lock: { acquire(): unknown; release(): void }, action: () => T): T {
  lock.acquire();
  try {
    return action();
  } finally {
    lock.release();
  }
}
