// 原子发布、从不覆盖：pi_dispatch.py 的 publish_new 的 TS 实现（迁移第 ① 步的样板）。
//
// 先在目标同一目录写完一个独立的临时文件，再以“目标存在就失败”的方式换上去。正式文件因此只会从
// “不存在”变成“完整”。目标已经存在（哪怕是只读文件或目录）返回 false，目标不变；其余错误原样抛出，
// 不退回会覆盖的写法：调用方不能把它们当成“别人已抢先发布”。
//
// 与 Python 版的差别只在发布那一步：Python 在 Windows 上用 os.rename（目标存在时报错、不替换）。
// Node 与 Bun 的 renameSync 在 Windows 上会覆盖已有的目标，所以两个平台都用 linkSync：硬链接遇到已有
// 目标一律报 EEXIST，再删掉临时文件。行为由 packages/contracts 的契约测试与对照测试约束。
import { randomBytes } from "node:crypto";
import { closeSync, constants, linkSync, openSync, rmSync, writeSync } from "node:fs";
import { basename, dirname, join } from "node:path";

/** 临时文件放在目标同一目录：`<目标名>.<16 位十六进制>.tmp`，与 Python 版同名规则。 */
export function tmpPathFor(path: string, nonce: Uint8Array): string {
  return join(dirname(path), `${basename(path)}.${Buffer.from(nonce).toString("hex")}.tmp`);
}

function isErrno(error: unknown, code: string): boolean {
  return error instanceof Error && (error as NodeJS.ErrnoException).code === code;
}

/** 发布成功返回 true；目标已存在返回 false，目标字节不变；其余错误原样抛出。 */
export function publishNew(path: string, data: Uint8Array): boolean {
  const tmp = tmpPathFor(path, randomBytes(8));
  // O_EXCL：临时文件名撞上已有文件时报错，绝不写进别人的文件。Windows 没有 O_NOFOLLOW，取 0
  const fd = openSync(tmp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0), 0o666);
  try {
    try {
      let offset = 0;
      while (offset < data.length) offset += writeSync(fd, data, offset, data.length - offset);
    } finally {
      closeSync(fd);
    }
    try {
      linkSync(tmp, path);
    } catch (error) {
      if (isErrno(error, "EEXIST")) return false; // 只有发布这一步的“已存在”才算别人抢先发布
      throw error;
    }
    return true;
  } finally {
    rmSync(tmp, { force: true });
  }
}
