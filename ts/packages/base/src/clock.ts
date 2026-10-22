// 时间与编号的格式（迁移第 ① 步，计划第 4 节 ① 的 clock）：与现行 Python 实现写出的格式一致。
//   utcNow        kit_hub.utc_now / pi_dispatch.utc_now    2026-10-22T01:02:03Z（秒，截断不进位）
//   utcCompact    kit_hub.utc_compact                      20261022T010203123456Z（微秒）
//   newMsgId      kit_hub.new_msg_id                       <utcCompact>-<发信人>-<6 位十六进制>，站主写 owner、内核写 kernel
//   newTurnId     kit_hub 回合编号（TurnRunner 里内联）      <utcCompact>-<4 位十六进制>
//   attemptDir    pi_dispatch.allocate_attempt（内联）      attempt-001，满 1000 照写 attempt-1000
//   auditId       kit_config 审计记录（内联）               aud-<32 位十六进制>
// 两套实现会同时往同一个信箱发信、写同一份账本：信箱按文件名排序，所以 utcCompact 必须定长、按时间单调。
import { randomBytes } from "node:crypto";

/** 发信人的别名：信件编号与信箱目录用 ASCII 名字（kit_hub.SENDER_ALIAS）。 */
export const SENDER_ALIAS: Readonly<Record<string, string>> = { 站主: "owner", 内核: "kernel" };

function pad(value: number, width: number): string {
  return String(value).padStart(width, "0");
}

/**
 * 做一个“当前 Unix 微秒数”的时钟：以 wall（毫秒，跟随系统时钟与 NTP 校正，与 Python 的 datetime.now() 同源）为准，
 * fine（高精度的毫秒数）只补毫秒以下的三位；进程内单调夹紧：取 max(上一次 + 1, 本次)，系统时钟往回调也不倒退。
 * 不能直接用 performance.timeOrigin + performance.now()：那是单调时钟，不跟随系统时间校正，休眠期间也不走，
 * hub 一跑几天就会偏离系统时间，也偏离 Python 写的时间。
 */
export function makeClock(wall: () => number, fine: () => number): () => number {
  let last = 0;
  return () => {
    const subMillisecond = Math.floor((((fine() % 1) + 1) % 1) * 1000);
    last = Math.max(last + 1, Math.floor(wall()) * 1000 + subMillisecond);
    return last;
  };
}

const systemClock = makeClock(
  () => Date.now(),
  () => performance.now(),
);

/** 当前时刻的 Unix 微秒数（系统时钟，进程内单调递增）。 */
export function nowMicros(): number {
  return systemClock();
}

/** utc_now：秒精度，截断（Python 的 strftime 不进位）。 */
export function utcNow(micros: number = nowMicros()): string {
  const date = new Date(Math.floor(micros / 1000));
  return (
    `${pad(date.getUTCFullYear(), 4)}-${pad(date.getUTCMonth() + 1, 2)}-${pad(date.getUTCDate(), 2)}` +
    `T${pad(date.getUTCHours(), 2)}:${pad(date.getUTCMinutes(), 2)}:${pad(date.getUTCSeconds(), 2)}Z`
  );
}

/** utc_compact：%Y%m%dT%H%M%S%fZ，微秒六位。 */
export function utcCompact(micros: number = nowMicros()): string {
  const date = new Date(Math.floor(micros / 1000));
  return (
    `${pad(date.getUTCFullYear(), 4)}${pad(date.getUTCMonth() + 1, 2)}${pad(date.getUTCDate(), 2)}` +
    `T${pad(date.getUTCHours(), 2)}${pad(date.getUTCMinutes(), 2)}${pad(date.getUTCSeconds(), 2)}` +
    `${pad(micros % 1_000_000, 6)}Z`
  );
}

/** new_msg_id：<utcCompact>-<发信人别名>-<3 个随机字节的十六进制>。 */
export function newMsgId(sender: string, micros: number = nowMicros()): string {
  return `${utcCompact(micros)}-${SENDER_ALIAS[sender] ?? sender}-${randomBytes(3).toString("hex")}`;
}

/** 回合编号：<utcCompact>-<2 个随机字节的十六进制>。 */
export function newTurnId(micros: number = nowMicros()): string {
  return `${utcCompact(micros)}-${randomBytes(2).toString("hex")}`;
}

/** attempt 目录名："attempt-%03d"。 */
export function attemptDirName(number: number): string {
  if (!Number.isSafeInteger(number) || number < 0) throw new RangeError(`attempt 编号不对：${number}`);
  return `attempt-${pad(number, 3)}`;
}

/** 审计记录编号：aud-<16 个随机字节的十六进制>。 */
export function auditId(): string {
  return `aud-${randomBytes(16).toString("hex")}`;
}
