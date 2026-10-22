// 相对时间（合同第 3 节）：把 ISO 时刻显示成「N 秒/分钟/小时/天前」，挂 time 元素，title 为本地时间加全角括号里的 UTC。
// 差值取 max(0, now - t) 向下取整到秒；解析不了的原文原样显示，不带 title 与 dateTime；不每秒更新（无计时器）。
export interface RelativeTimeProps {
  /** ISO 8601 时刻原文，也作 dateTime。 */
  iso: string;
  /** 计算基准（毫秒时间戳），缺省 Date.now()。 */
  now?: number;
  className?: string;
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function relativeText(fromMs: number, nowMs: number): string {
  const sec = Math.max(0, Math.floor((nowMs - fromMs) / 1000));
  if (sec < 60) return `${sec} 秒前`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour} 小时前`;
  return `${Math.floor(hour / 24)} 天前`;
}

/** 「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」：本地时间加 UTC；解析不了返回 null。 */
export function formatLocalUtc(iso: string): string | null {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const d = new Date(t);
  return (
    `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ` +
    `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}` +
    `（UTC ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}:${pad2(d.getUTCSeconds())}）`
  );
}

export function RelativeTime({ iso, now, className }: RelativeTimeProps) {
  const title = formatLocalUtc(iso);
  if (title === null) {
    return <span className={className}>{iso}</span>;
  }
  return (
    <time className={className} dateTime={iso} title={title}>
      {relativeText(Date.parse(iso), now ?? Date.now())}
    </time>
  );
}
