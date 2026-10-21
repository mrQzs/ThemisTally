// 只读页面二共用的文字格式化（合同「公共约定」）：数字千分位手写，不用 Intl、toLocaleString；
// 时间是「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」；站内地址保留当前 ?mock=。
import { parseHash, mockOfQuery } from '../../shell/router';
import { relativeTime } from '../../shell/relativeTime';

/** 数字千分位；缺失（null、undefined、非数）显示「未知」。 */
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

const pad = (n: number) => String(n).padStart(2, '0');

/**
 * 「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」：本地时间加 UTC；解析不了返回 null。
 */
export function formatLocalUtc(iso: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const local = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  const utc = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
  return `${local}（UTC ${utc}）`;
}

/** 相对时间（秒/分/时/天前）；解析不了返回 null。 */
export function relativeFrom(iso: string, now: number): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return relativeTime(d.getTime(), now);
}

/**
 * 站内地址：当前地址带 ?mock= 时一并带上（如 #/settings?mock=data），否则不带查询。
 */
export function hrefWithMock(path: string): string {
  const hash = typeof window !== 'undefined' ? window.location.hash : '';
  const mock = mockOfQuery(parseHash(hash).query);
  return mock ? `#${path}?mock=${mock}` : `#${path}`;
}
