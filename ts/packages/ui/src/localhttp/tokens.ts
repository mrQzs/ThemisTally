// 令牌与恒定时间比较（桌面端设计第 7 版 §5.2）：会话 cookie、引导 nonce 与控制令牌都用同一套随机数；控制令牌的
// 比较必须走恒定时间，否则试错的人能靠响应快慢逐位猜出令牌（T7c）。
import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

/** 随机令牌的字节数（base64url 之后 43 个字符）。 */
export const TOKEN_BYTES = 32;

/** 32 字节随机数的 base64url（43 个字符，没有填充）。 */
export function randomToken(): string {
  return randomBytes(TOKEN_BYTES).toString("base64url");
}

/**
 * 恒定时间比较：总是先算两份 SHA-256 摘要再走 timingSafeEqual，所以长度不同、缺头（given 为 null）都走同一条
 * 路，不抛错也不提前返回。摘要长度相同是 timingSafeEqual 的前提；原串长度不同这件事由最后的 given !== null
 * 与摘要不同共同表达，不进时序信道。
 */
export function constantTimeEqual(given: string | null, expected: string): boolean {
  const mine = createHash("sha256").update(expected).digest();
  const theirs = createHash("sha256").update(given ?? "").digest();
  return timingSafeEqual(theirs, mine) && given !== null;
}
