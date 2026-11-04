// 时间与编号的格式（迁移第 ① 步，计划第 4 节 ① 的 clock）：与现行 Python 实现写出的格式一致。
//   utcNow        kit_hub.utc_now / pi_dispatch.utc_now    2026-10-22T01:02:03Z（秒，截断不进位）
//   utcCompact    kit_hub.utc_compact                      20261022T010203123456Z（微秒）
//   newMsgId      kit_hub.new_msg_id                       <utcCompact>-<发信人>-<6 位十六进制>，站主写 owner、内核写 kernel
//   newTurnId     kit_hub 回合编号（TurnRunner 里内联）      <utcCompact>-<4 位十六进制>
//   attemptDir    pi_dispatch.allocate_attempt（内联）      attempt-001，满 1000 照写 attempt-1000
//   auditId       kit_config 审计记录（内联）               aud-<32 位十六进制>
//   mtimeUtcSeconds kit_hub 3233、4271（内联）               文件修改时刻，2026-10-22T01:02:03Z（微秒半数取偶，会进位）
// 两套实现会同时往同一个信箱发信、写同一份账本：信箱按文件名排序，所以 utcCompact 必须定长、按时间单调。
import { randomBytes } from "node:crypto";
import { statSync } from "node:fs";

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

let pinned: number | null = null;
/** 钉住期间已经编出的信编号个数（newMsgId 的尾巴照次序编）。 */
let pinnedIds = 0;

/** 当前时刻的 Unix 微秒数（系统时钟，进程内单调递增）。 */
export function nowMicros(): number {
  return pinned ?? systemClock();
}

/**
 * 只给契约用，生产代码不调（迁移第 ⑤e2b 片）：fn 运行期间 nowMicros 固定交回 micros，utcNow、utcCompact 跟着走，对应 Python 那边把
 * kit_hub.utc_now、utc_compact 钉成同一个时刻。async 的 fn 等它结束；结束或抛错都在 finally 里还原。⑤h2：钉住期间 newMsgId 的尾巴照次序编
 * （000000 起），对应 python_probe 把 kit_hub.new_msg_id 换成按次序编的：流程函数里写的信两边才一样。
 */
export async function withPinnedClock<T>(micros: number, fn: () => T | Promise<T>): Promise<T> {
  const [before, beforeIds] = [pinned, pinnedIds];
  [pinned, pinnedIds] = [micros, 0];
  try {
    return await fn();
  } finally {
    [pinned, pinnedIds] = [before, beforeIds];
  }
}

/**
 * 只给契约用（⑤j2 跑到静止，对应 python_probe 换上的 time.sleep）：钉住期间把钉住的时刻往后挪 micros 微秒，信编号照次序接着编，不从头编；
 * 没钉住时什么都不做。
 */
export function advancePinnedClock(micros: number): void {
  if (pinned !== null) pinned += micros;
}

/** utc_now：秒精度，截断（Python 的 strftime 不进位）。 */
export function utcNow(micros: number = nowMicros()): string {
  const date = new Date(Math.floor(micros / 1000));
  return (
    `${pad(date.getUTCFullYear(), 4)}-${pad(date.getUTCMonth() + 1, 2)}-${pad(date.getUTCDate(), 2)}` +
    `T${pad(date.getUTCHours(), 2)}:${pad(date.getUTCMinutes(), 2)}:${pad(date.getUTCSeconds(), 2)}Z`
  );
}

/** C 的 round()：半数离零取整。 */
function roundHalfAway(value: number): number {
  const whole = Math.trunc(value);
  return Math.abs(value - whole) >= 0.5 ? whole + Math.sign(value) : whole;
}

/**
 * datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")（迁移第 ⑤g 片，kit_hub 3233、4271 两处）。
 * st_mtime 是 sec + nsec * 1e-9 的浮点；fromtimestamp 把小数部分乘 1e6 后按半数取偶（_PyTime_ROUND_HALF_EVEN），满 1e6 就进到下一秒。
 * 用 bigint 的 stat 拿 mtimeNs，不拿 mtimeMs 直接取整。
 */
export function mtimeUtcSeconds(path: string): string {
  const ns = statSync(path, { bigint: true }).mtimeNs;
  let sec = ns / 1_000_000_000n;
  let nsec = ns % 1_000_000_000n;
  if (nsec < 0n) {
    nsec += 1_000_000_000n;
    sec -= 1n;
  }
  const stamp = Number(sec) + Number(nsec) * 1e-9;
  let whole = Math.trunc(stamp);
  const scaled = (stamp - whole) * 1e6;
  let micros = roundHalfAway(scaled);
  if (Math.abs(scaled - micros) === 0.5) micros = 2 * roundHalfAway(scaled / 2);
  if (micros >= 1e6) whole += 1;
  else if (micros < 0) whole -= 1;
  return utcNow(whole * 1_000_000);
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
  const tail = pinned === null ? randomBytes(3).toString("hex") : (pinnedIds++).toString(16).padStart(6, "0");
  return `${utcCompact(micros)}-${SENDER_ALIAS[sender] ?? sender}-${tail}`;
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
