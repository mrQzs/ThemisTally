// 任务页的文字格式化（合同公共约定、§8）：时长、千分位、字节、本地时间。
// 千分位手写，不用 Intl 与 toLocaleString；时间按本地时区写「YYYY-MM-DD HH:mm」，UTC 原值另作 title。

/** 时长：秒向下取整；<60 秒写「N 秒」；<1 小时写「M 分 S 秒」；否则写「H 小时 M 分」；非数或负数返回 null。 */
export function formatDuration(sec: number | null | undefined): string | null {
  if (typeof sec !== 'number' || !Number.isFinite(sec) || sec < 0) return null;
  const s = Math.floor(sec);
  if (s < 60) return `${s} 秒`;
  if (s < 3600) return `${Math.floor(s / 60)} 分 ${s % 60} 秒`;
  return `${Math.floor(s / 3600)} 小时 ${Math.floor((s % 3600) / 60)} 分`;
}

/** 数字千分位；缺失（null、undefined、非数）写「未知」。 */
export function formatThousands(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '未知';
  const negative = value < 0;
  const digits = Math.floor(Math.abs(value)).toString();
  let out = '';
  for (let i = 0; i < digits.length; i += 1) {
    if (i > 0 && (digits.length - i) % 3 === 0) out += ',';
    out += digits[i];
  }
  return negative ? `-${out}` : out;
}

const KB = 1024;
const MB = 1024 * 1024;

/** 字节数：<1 KiB 写「N B」，否则一位小数写 KB / MB；非数写「—」。 */
export function formatBytes(bytes: unknown): string {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < KB) return `${Math.floor(bytes)} B`;
  if (bytes < MB) return `${(bytes / KB).toFixed(1)} KB`;
  return `${(bytes / MB).toFixed(1)} MB`;
}

/** KB 数（摘要截断提示用）：向下取整，至少 1。 */
export function kilobytesOf(bytes: number): number {
  if (!Number.isFinite(bytes) || bytes <= 0) return 1;
  return Math.max(1, Math.floor(bytes / KB));
}

const pad = (n: number) => String(n).padStart(2, '0');

/** 本地时间「YYYY-MM-DD HH:mm」；解析不了返回 null（UTC 原值由调用方另作 title）。 */
export function formatLocalTime(iso: string | null | undefined): string | null {
  if (typeof iso !== 'string' || iso === '') return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
