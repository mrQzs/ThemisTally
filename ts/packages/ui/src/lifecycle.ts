// 生命周期（桌面端设计第 7 版 §5.4）：空闲时限、stdin EOF 与信号的关停。stdin 是启动器原样继承下来的管道，写端一关
// 就读到 EOF（实测，F6）——不轮询 ppid，父进程走了服务自己也该在空闲时限到了之后退。关停只做一次：server、计时器、
// stdin、锁各收一次；另设一个 3 秒的看门狗，到时候还没退就强制退出，不挂住外壳。
import type { Readable } from "node:stream";

/** 空闲时限的缺省值：1800 秒。 */
export const IDLE_TIMEOUT_SECONDS = 1800;
/** setTimeout 每段的上限：2^31-1 毫秒，超过它 Node 与 Bun 会立刻触发。 */
export const MAX_TIMEOUT_MS = 2147483647;

/**
 * 空闲时限：null 是 1800 秒，其余按秒换算成毫秒并封顶 Number.MAX_SAFE_INTEGER（pyargs-v1 的整数经 pyjson 变成
 * bigint，可能是很大的值）。
 */
export function idleMs(idle_timeout: number | bigint | null): number {
  if (idle_timeout === null) return IDLE_TIMEOUT_SECONDS * 1000;
  const seconds = Number(idle_timeout);
  if (!Number.isFinite(seconds) || seconds <= 0) return IDLE_TIMEOUT_SECONDS * 1000;
  return Math.min(seconds * 1000, Number.MAX_SAFE_INTEGER);
}

/** 一段 setTimeout 最多这么多毫秒；剩下的留给下一段。 */
export function timeoutChunk(remainingMs: number): number {
  return Math.max(0, Math.min(remainingMs, MAX_TIMEOUT_MS));
}

/**
 * 空闲计时器：每次 touch 重新设；有进行中的请求时 hold 住（不算空闲），release 之后再接着算。分段重设，所以
 * 1800 秒、甚至 MAX_SAFE_INTEGER 毫秒都不会让 setTimeout 溢出。
 */
export class IdleTimer {
  private readonly ms: number;
  private readonly onIdle: () => void;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private holds = 0;
  private deadline = 0;
  private remaining = 0;
  private stopped = false;

  constructor(ms: number, onIdle: () => void) {
    this.ms = ms;
    this.onIdle = onIdle;
  }

  /** 有活动：把时限重新计（暂停期间的活动记下来，恢复之后重新算一整段）。 */
  touch(): void {
    if (this.stopped) return;
    this.remaining = this.ms;
    if (this.holds === 0) {
      this.deadline = Date.now() + this.ms;
      this.schedule();
    }
  }

  /** 有请求在进行中：先不算空闲（把剩下的时间记下来，计时器收掉）。 */
  hold(): void {
    this.holds += 1;
    if (this.holds === 1) {
      this.clear();
      this.remaining = Math.max(0, this.deadline - Date.now());
    }
  }

  /** 请求结束：接着算剩下的。 */
  release(): void {
    if (this.holds > 0) this.holds -= 1;
    if (this.holds === 0 && !this.stopped) {
      this.deadline = Date.now() + this.remaining;
      this.schedule();
    }
  }

  /** 收掉：关停时调一次。 */
  stop(): void {
    this.stopped = true;
    this.clear();
  }

  private schedule(): void {
    this.clear();
    const remaining = this.deadline - Date.now();
    if (remaining <= 0) {
      this.onIdle();
      return;
    }
    this.timer = setTimeout(() => {
      this.timer = null;
      if (this.stopped || this.holds > 0) return;
      this.schedule();
    }, timeoutChunk(remaining));
    this.timer.unref?.();
  }

  private clear(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}

/** 监视 stdin 的 EOF：把数据读空并丢弃，循环结束（EOF）或读出错都调一次 onEof。不轮询 ppid。 */
export async function watchStdinEof(stream: Readable | null | undefined, onEof: () => void): Promise<void> {
  if (stream === null || stream === undefined) return;
  try {
    for await (const _chunk of stream) {
      // 丢弃：stdin 只是外壳的寿命信号，不是输入
    }
  } catch {
    // 读出错也算对端走了
  }
  onEof();
}

/** 信号：SIGINT、SIGTERM（Windows 另加 SIGBREAK）都走同一个关停。返回摘监听器的函数。 */
export function watchSignals(onSignal: () => void): () => void {
  const names = process.platform === "win32" ? ["SIGINT", "SIGTERM", "SIGBREAK"] : ["SIGINT", "SIGTERM"];
  const attached = names.map((name) => {
    const listener = (): void => onSignal();
    process.on(name, listener);
    return { name, listener };
  });
  return () => {
    for (const one of attached) process.off(one.name, one.listener);
  };
}
