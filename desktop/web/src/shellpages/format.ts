// 时间与相对时间格式化（src/shellpages/format.ts）：本地时间写 YYYY-MM-DD HH:mm:ss，再附 UTC 原值；
// 相对时间用 shell/relativeTime 的 relativeTime。涉及时间的期望值由调用方用同一个 Date 现算，不写死时区。
import { clockTime, relativeTime } from '../shell/relativeTime';

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

/** 本地时间 YYYY-MM-DD HH:mm:ss。 */
export function localTime(at: number | string): string {
  const d = new Date(at);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/** 「上次打开」的 title：本地时间 · UTC 原值。 */
export function openedTitle(iso: string): string {
  return `${localTime(iso)} · UTC ${iso}`;
}

/** 相对时间（ISO 或时刻数）；null 写「—」。 */
export function relTime(iso: string | null, now: number): string {
  if (!iso) return '—';
  return relativeTime(new Date(iso).getTime(), now);
}

/** 时刻数转时:分:秒（服务状态页的退出时刻）。 */
export function clock(at: number): string {
  return clockTime(at);
}
