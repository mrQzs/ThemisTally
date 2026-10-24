// file 路由的句柄表（桌面端设计第 7 版 §5.3、D11）：界面拿到的 next_cursor 是随机不透明句柄，内核游标只存在服务
// 内存里——表项是「句柄 → {task, attempt, path, cursor}」，服务退出全部失效。句柄用 localhttp/tokens 的
// randomToken（32 字节 base64url，43 个字符）；最多 1024 项，用一次就挪到 Map 末尾，超容量淘汰最旧的一个。
import { randomToken } from "./localhttp/tokens.ts";

/** 句柄表最多多少项。 */
export const CURSOR_CAPACITY = 1024;
/** 句柄的形状：43 个 base64url 字符。 */
export const CURSOR_HANDLE_RE = /^[A-Za-z0-9_-]{43}$/u;

/** 一个句柄绑定的那次读取：换了 task、attempt 或 path 都不算同一个游标。 */
export interface CursorBinding {
  readonly task: string;
  readonly attempt: string;
  readonly path: string;
  readonly cursor: string;
}

/** 句柄的形状对不对（43 个 base64url 字符）。 */
export function validHandle(handle: string): boolean {
  return CURSOR_HANDLE_RE.test(handle);
}

/** 只在内存里的句柄表：Map 的插入次序就是最近使用的次序。 */
export class CursorTable {
  private readonly entries = new Map<string, CursorBinding>();

  /** 发一个句柄（表里没有的真游标由此进去）；超容量时淘汰最旧的一个。 */
  issue(binding: CursorBinding): string {
    const handle = randomToken();
    this.entries.delete(handle); // 撞上了先删掉，保证这一次插入落在末尾
    this.entries.set(handle, binding);
    while (this.entries.size > CURSOR_CAPACITY) {
      const oldest = this.entries.keys().next();
      if (oldest.done) break;
      this.entries.delete(oldest.value);
    }
    return handle;
  }

  /** 按句柄取表项：命中就挪到 Map 末尾（用一次算最近使用）；不在表里返回 null。 */
  take(handle: string): CursorBinding | null {
    const found = this.entries.get(handle);
    if (found === undefined) return null;
    this.entries.delete(handle);
    this.entries.set(handle, found);
    return found;
  }

  /** 丢掉一个句柄（内核报「游标对应的文件已变化」时用）。 */
  drop(handle: string): void {
    this.entries.delete(handle);
  }

  /** 表里现在多少项（测试用）。 */
  get size(): number {
    return this.entries.size;
  }
}
