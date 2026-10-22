// Python 的 datetime.fromisoformat（CPython 3.12.10 Modules/_datetimemodule.c 的 C 实现，Python 实际用的就是它）逐段
// 移植，加 kit_logs._parse_iso 的换算：结尾的 Z 换成 +00:00、必须带时区、换成 UTC、换算溢出为“不可用”。
// C 版在字符串的 UTF-8 字节上按 C 字符串解析，怪癖照搬：读到串尾之后当 NUL（串中的 NUL 字符也当结尾，“Z”后面跟 NUL
// 照收）；日期与时间之间的分隔符可以是任意字符（多字节的按首字节跳过）；“HH:MM:SS:ff”的第三个冒号之后当小数；
// 小数点后面一位都没有也收；时区偏移的秒数为零时连带的微秒一并丢掉（直接当 UTC）。
// 时间点表示成 0001-01-01T00:00:00（UTC）起的微秒数（bigint），只用来比较先后。

const MINYEAR = 1;
const MAXYEAR = 9999;
const US_PER_DAY = 86_400_000_000n;
const DAYS_IN_MONTH = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const DAYS_BEFORE_MONTH = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
const DI400Y = 146097;
const DI100Y = 36524;
const DI4Y = 1461;

const isLeap = (year: number): boolean => year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
const daysInMonth = (year: number, month: number): number => (month === 2 && isLeap(year) ? 29 : DAYS_IN_MONTH[month] as number);

function daysBeforeYear(year: number): number {
  const y = year - 1;
  return y * 365 + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400);
}

const daysBeforeMonth = (year: number, month: number): number =>
  (DAYS_BEFORE_MONTH[month] as number) + (month > 2 && isLeap(year) ? 1 : 0);

/** ymd_to_ord：0001-01-01 是第 1 天。 */
const ymdToOrd = (year: number, month: number, day: number): number => daysBeforeYear(year) + daysBeforeMonth(year, month) + day;

/** weekday：星期一为 0。 */
const weekday = (year: number, month: number, day: number): number => (ymdToOrd(year, month, day) + 6) % 7;

/** ord_to_ymd。 */
function ordToYmd(ordinal: number): [number, number, number] {
  let n = ordinal - 1;
  const n400 = Math.floor(n / DI400Y);
  n %= DI400Y;
  let year = n400 * 400 + 1;
  const n100 = Math.floor(n / DI100Y);
  n %= DI100Y;
  const n4 = Math.floor(n / DI4Y);
  n %= DI4Y;
  const n1 = Math.floor(n / 365);
  n %= 365;
  year += n100 * 100 + n4 * 4 + n1;
  if (n1 === 4 || n100 === 4) return [year - 1, 12, 31];
  const leap = n1 === 3 && (n4 !== 24 || n100 === 3);
  let month = (n + 50) >> 5;
  let preceding = (DAYS_BEFORE_MONTH[month] as number) + (month > 2 && leap ? 1 : 0);
  if (preceding > n) {
    month -= 1;
    preceding -= (DAYS_IN_MONTH[month] as number) + (month === 2 && leap ? 1 : 0);
  }
  return [year, month, n - preceding + 1];
}

function isoWeek1Monday(year: number): number {
  const firstDay = ymdToOrd(year, 1, 1);
  const firstWeekday = (firstDay + 6) % 7;
  let monday = firstDay - firstWeekday;
  if (firstWeekday > 3) monday += 7;
  return monday;
}

/** iso_to_ymd：失败返回 null。 */
function isoToYmd(isoYear: number, isoWeek: number, isoDay: number): [number, number, number] | null {
  if (isoYear < MINYEAR || isoYear > MAXYEAR) return null;
  if (isoWeek <= 0 || isoWeek >= 53) {
    let outOfRange = true;
    if (isoWeek === 53) {
      const first = weekday(isoYear, 1, 1);
      if (first === 3 || (first === 2 && isLeap(isoYear))) outOfRange = false;
    }
    if (outOfRange) return null;
  }
  if (isoDay <= 0 || isoDay >= 8) return null;
  return ordToYmd(isoWeek1Monday(isoYear) + (isoWeek - 1) * 7 + isoDay - 1);
}

/** C 字符串：字节加一个结尾的 0，读到串尾之后一律当 0。 */
class CStr {
  readonly bytes: Uint8Array;
  readonly length: number;

  constructor(bytes: Uint8Array) {
    this.length = bytes.length;
    this.bytes = new Uint8Array(bytes.length + 1);
    this.bytes.set(bytes);
  }

  at(index: number): number {
    return index >= 0 && index < this.bytes.length ? (this.bytes[index] as number) : 0;
  }
}

const ZERO = 0x30;
const isDigit = (byte: number): boolean => byte - ZERO >= 0 && byte - ZERO < 10;

/** parse_digits：从 pos 起读 count 个数字累进 value；遇到非数字返回 null。 */
function parseDigits(str: CStr, pos: number, count: number, value: number): [number, number] | null {
  let p = pos;
  let v = value;
  for (let index = 0; index < count; index += 1) {
    const digit = str.at(p) - ZERO;
    p += 1;
    if (digit < 0 || digit > 9) return null;
    v = v * 10 + digit;
  }
  return [p, v];
}

/** parse_isoformat_date：成功返回 (年, 月, 日)。len 是日期部分的字节数（分隔符的位置）。 */
function parseIsoDate(str: CStr, len: number): [number, number, number] | null {
  const year = parseDigits(str, 0, 4, 0);
  if (year === null) return null;
  let p = year[0];
  const usesSeparator = str.at(p) === 0x2d;
  if (usesSeparator) p += 1;
  if (str.at(p) === 0x57) {
    // 周历写法：YYYY-Www[-D]
    p += 1;
    const week = parseDigits(str, p, 2, 0);
    if (week === null) return null;
    p = week[0];
    let isoDay = 0;
    if (p < len) {
      if (usesSeparator) {
        const separator = str.at(p);
        p += 1;
        if (separator !== 0x2d) return null;
      }
      const day = parseDigits(str, p, 1, 0);
      if (day === null) return null;
      isoDay = day[1];
    } else {
      isoDay = 1;
    }
    return isoToYmd(year[1], week[1], isoDay);
  }
  const month = parseDigits(str, p, 2, 0);
  if (month === null) return null;
  p = month[0];
  if (usesSeparator) {
    const separator = str.at(p);
    p += 1;
    if (separator !== 0x2d) return null;
  }
  const day = parseDigits(str, p, 2, 0);
  if (day === null) return null;
  return [year[1], month[1], day[1]];
}

/** parse_hh_mm_ss_ff：返回 (码, 时, 分, 秒, 微秒)；码 < 0 失败，1 表示后面还有东西。 */
function parseHhMmSsFf(str: CStr, start: number, end: number): [number, number, number, number, number] {
  const values = [0, 0, 0];
  let microsecond = 0;
  let p = start;
  let hasSeparator = true;
  for (let index = 0; index < 3; index += 1) {
    const parsed = parseDigits(str, p, 2, 0);
    if (parsed === null) return [-3, 0, 0, 0, 0];
    [p, values[index]] = parsed;
    const c = str.at(p);
    p += 1;
    if (index === 0) hasSeparator = c === 0x3a;
    if (p >= end) return [c !== 0 ? 1 : 0, values[0] as number, values[1] as number, values[2] as number, 0];
    if (hasSeparator && c === 0x3a) continue; // 秒后面的冒号也走这里：循环结束，接着当小数读
    if (c === 0x2e || c === 0x2c) break;
    if (!hasSeparator) {
      p -= 1;
    } else {
      return [-4, 0, 0, 0, 0];
    }
  }
  // 小数部分：最多读 6 位，不足 6 位补零，多的数字跳过
  const remains = end - p;
  const toParse = remains >= 6 ? 6 : remains;
  const parsed = parseDigits(str, p, toParse, 0);
  if (parsed === null) return [-3, 0, 0, 0, 0];
  [p, microsecond] = parsed;
  if (toParse > 0 && toParse < 6) microsecond *= 10 ** (6 - toParse); // toParse 为 0 时 C 乘的是越界读到的值，结果仍是 0
  while (isDigit(str.at(p))) p += 1;
  return [str.at(p) !== 0 ? 1 : 0, values[0] as number, values[1] as number, values[2] as number, microsecond];
}

interface TimeResult {
  readonly code: number; // 0 不带时区，1 带时区，< 0 失败
  readonly hour: number;
  readonly minute: number;
  readonly second: number;
  readonly microsecond: number;
  readonly tzOffset: number; // 秒
  readonly tzMicrosecond: number;
}

const failed = (code: number): TimeResult => ({ code, hour: 0, minute: 0, second: 0, microsecond: 0, tzOffset: 0, tzMicrosecond: 0 });

/** parse_isoformat_time：start 起 len 个字节。 */
function parseIsoTime(str: CStr, start: number, len: number): TimeResult {
  const end = start + len;
  let tz = start;
  do {
    const byte = str.at(tz);
    if (byte === 0x5a || byte === 0x2b || byte === 0x2d) break;
  } while (++tz < end);
  const [rv, hour, minute, second, microsecond] = parseHhMmSsFf(str, start, tz);
  if (rv < 0) return failed(rv);
  if (tz === end) return rv === 1 ? failed(-5) : { code: 0, hour, minute, second, microsecond, tzOffset: 0, tzMicrosecond: 0 };
  if (str.at(tz) === 0x5a) {
    if (str.at(tz + 1) !== 0) return failed(-5);
    return { code: 1, hour, minute, second, microsecond, tzOffset: 0, tzMicrosecond: 0 };
  }
  const sign = str.at(tz) === 0x2d ? -1 : 1;
  const [tzRv, tzHour, tzMinute, tzSecond, tzMicro] = parseHhMmSsFf(str, tz + 1, end);
  if (tzRv !== 0) return failed(-5);
  return { code: 1, hour, minute, second, microsecond, tzOffset: sign * (tzHour * 3600 + tzMinute * 60 + tzSecond), tzMicrosecond: tzMicro * sign };
}

/** _find_isoformat_datetime_separator。 */
function findSeparator(str: CStr): number {
  const len = str.length;
  if (len === 7) return 7;
  if (str.at(4) === 0x2d) {
    if (str.at(5) === 0x57) {
      if (len < 8) return -1;
      if (len > 8 && str.at(8) === 0x2d) {
        if (len === 9) return -1;
        if (len > 10 && isDigit(str.at(10))) return 8;
        return 10;
      }
      return 8;
    }
    return 10;
  }
  if (str.at(4) === 0x57) {
    let index = 7;
    for (; index < len; index += 1) {
      if (!isDigit(str.at(index))) break;
    }
    if (index < 9) return index;
    return index % 2 === 0 ? 7 : 8;
  }
  return 8;
}

const isSurrogate = (cp: number): boolean => cp >= 0xd800 && cp <= 0xdfff;

/** 解析出的 aware 或 naive datetime：本地时间的微秒数（0001-01-01 起）与 UTC 偏移（微秒；naive 为 null）。 */
interface Parsed {
  readonly local: bigint;
  readonly offset: bigint | null;
}

/** datetime.fromisoformat：解析不了（Python 抛 ValueError）为 null。 */
export function fromIsoFormat(text: string): Parsed | null {
  const chars = Array.from(text);
  if (chars.length < 7) return null;
  // _sanitize_isoformat_str：分隔符只可能在第 7、8、10 个字符；是代理字符就换成 T
  for (const position of [7, 8, 10]) {
    if (position > chars.length) break;
    const cp = position < chars.length ? (chars[position] as string).codePointAt(0) as number : 0;
    if (isSurrogate(cp)) {
      chars[position] = "T";
      break;
    }
  }
  if (chars.some((char) => isSurrogate(char.codePointAt(0) as number))) return null; // 编码成 UTF-8 失败
  const str = new CStr(new TextEncoder().encode(chars.join("")));
  const separator = findSeparator(str);
  const date = parseIsoDate(str, separator);
  if (date === null) return null;
  let time: TimeResult = { code: 0, hour: 0, minute: 0, second: 0, microsecond: 0, tzOffset: 0, tzMicrosecond: 0 };
  if (str.length > separator) {
    // 跳过分隔符：多字节的按 UTF-8 首字节的长度跳
    let p = separator;
    const lead = str.at(p);
    if ((lead & 0x80) === 0) p += 1;
    else if ((lead & 0xf0) === 0xe0) p += 3;
    else if ((lead & 0xf0) === 0xf0) p += 4;
    else p += 2;
    time = parseIsoTime(str, p, str.length - p);
    if (time.code < 0) return null;
  }
  let offset: bigint | null = null;
  if (time.code === 1) {
    if (time.tzOffset === 0) {
      offset = 0n; // 秒数为零就是 UTC，连带的微秒丢掉（C 照此写）
    } else {
      offset = BigInt(time.tzOffset) * 1_000_000n + BigInt(time.tzMicrosecond);
      if (offset <= -US_PER_DAY || offset >= US_PER_DAY) return null; // 偏移要严格在正负 24 小时之内
    }
  }
  const [year, month, day] = date;
  if (year < MINYEAR || year > MAXYEAR || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) return null;
  if (time.hour > 23 || time.minute > 59 || time.second > 59 || time.microsecond > 999_999) return null;
  const local = BigInt(ymdToOrd(year, month, day) - 1) * US_PER_DAY
    + BigInt((time.hour * 60 + time.minute) * 60 + time.second) * 1_000_000n + BigInt(time.microsecond);
  return { local, offset };
}

const MAX_INSTANT = BigInt(ymdToOrd(MAXYEAR, 12, 31)) * US_PER_DAY - 1n;

/** kit_logs._parse_iso：结尾的 Z 换成 +00:00 后解析，带时区的换成 UTC；不是字符串、解析不了、不带时区、换算溢出都为 null。 */
export function parseIsoUtc(value: unknown): bigint | null {
  if (typeof value !== "string") return null;
  const parsed = fromIsoFormat(value.endsWith("Z") ? `${value.slice(0, -1)}+00:00` : value);
  if (parsed === null || parsed.offset === null) return null;
  const utc = parsed.local - parsed.offset;
  return utc < 0n || utc > MAX_INSTANT ? null : utc;
}
