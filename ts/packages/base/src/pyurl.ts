// Python 3.12.10 的 urllib.parse.urlsplit 与 SplitResult 的 hostname、port、username、password，以及 ipaddress.ip_address
// 认不认一个地址（迁移第 ③ 步：decisions.base_url 的校验只看“抛不抛 ValueError”与这几个字段，报错文字不进输出）。
// 照 CPython 源码逐段移植；分隔符都是 ASCII，按 UTF-16 下标切出来的子串与 Python 按码点切的相同。
import { pyLower, pyNfkc } from "./pyre.ts";

/** urlsplit 或 port 抛出的 ValueError（文字照 Python）。 */
export class PyValueError extends Error {}

export interface SplitResult {
  readonly scheme: string;
  readonly netloc: string;
  readonly path: string;
  readonly query: string;
  readonly fragment: string;
}

const C0_CONTROL_OR_SPACE = /^[\u0000- ]+/u;
const SCHEME_CHARS = /^[a-zA-Z0-9+\-.]*$/u;

export function urlsplit(input: string): SplitResult {
  let url = input.replace(C0_CONTROL_OR_SPACE, "").replace(/[\t\r\n]/gu, "");
  let scheme = "";
  let netloc = "";
  let query = "";
  let fragment = "";
  const colon = url.indexOf(":");
  if (colon > 0 && /^[a-zA-Z]/u.test(url) && SCHEME_CHARS.test(url.slice(0, colon))) {
    scheme = url.slice(0, colon).toLowerCase();
    url = url.slice(colon + 1);
  }
  if (url.startsWith("//")) {
    [netloc, url] = splitNetloc(url);
    if ((netloc.includes("[") && !netloc.includes("]")) || (netloc.includes("]") && !netloc.includes("["))) {
      throw new PyValueError("Invalid IPv6 URL");
    }
    if (netloc.includes("[") && netloc.includes("]")) checkBracketedNetloc(netloc);
  }
  const hash = url.indexOf("#");
  if (hash >= 0) [url, fragment] = [url.slice(0, hash), url.slice(hash + 1)];
  const question = url.indexOf("?");
  if (question >= 0) [url, query] = [url.slice(0, question), url.slice(question + 1)];
  checkNetloc(netloc);
  return { scheme, netloc, path: url, query, fragment };
}

/** SplitResult.hostname：没有时为 null；% 之后的区域标识不转小写。 */
export function urlHostname(result: SplitResult): string | null {
  const [hostname] = hostinfo(result.netloc);
  if (!hostname) return null;
  const percent = hostname.indexOf("%");
  return percent < 0 ? pyLower(hostname) : pyLower(hostname.slice(0, percent)) + hostname.slice(percent);
}

/** SplitResult.port：没有时为 null；不是 ASCII 数字或超出 0–65535 时抛 PyValueError。 */
export function urlPort(result: SplitResult): number | null {
  const [, port] = hostinfo(result.netloc);
  if (port === null) return null;
  if (!/^[0-9]+$/u.test(port)) throw new PyValueError(`Port could not be cast to integer value as ${port}`);
  const value = BigInt(port);
  if (value > 65535n) throw new PyValueError("Port out of range 0-65535");
  return Number(value);
}

/** SplitResult.username 与 password：netloc 里没有 @ 时都是 null；有 @ 没有 : 时 password 为 null。 */
export function urlUserinfo(result: SplitResult): { username: string | null; password: string | null } {
  const at = result.netloc.lastIndexOf("@");
  if (at < 0) return { username: null, password: null };
  const userinfo = result.netloc.slice(0, at);
  const colon = userinfo.indexOf(":");
  return colon < 0 ? { username: userinfo, password: null } : { username: userinfo.slice(0, colon), password: userinfo.slice(colon + 1) };
}

/** ipaddress.ip_address 认出的地址类型；两种都不是时为 null（Python 抛 ValueError）。 */
export function ipAddressKind(address: string): "v4" | "v6" | null {
  if (address.includes("/")) return null;
  if (ipv4Int(address) !== null) return "v4";
  const percent = address.indexOf("%");
  if (percent >= 0) {
    const scope = address.slice(percent + 1);
    if (!scope || scope.includes("%")) return null;
  }
  return ipv6Valid(percent < 0 ? address : address.slice(0, percent)) ? "v6" : null;
}

function splitNetloc(url: string): [string, string] {
  let delim = url.length;
  for (const char of "/?#") {
    const found = url.indexOf(char, 2);
    if (found >= 0) delim = Math.min(delim, found);
  }
  return [url.slice(2, delim), url.slice(delim)];
}

function checkBracketedNetloc(netloc: string): void {
  const hostAndPort = netloc.slice(netloc.lastIndexOf("@") + 1);
  const open = hostAndPort.indexOf("[");
  let hostname: string;
  if (open >= 0) {
    if (open > 0) throw new PyValueError("Invalid IPv6 URL");
    const bracketed = hostAndPort.slice(open + 1);
    const close = bracketed.indexOf("]");
    hostname = close < 0 ? bracketed : bracketed.slice(0, close);
    const port = close < 0 ? "" : bracketed.slice(close + 1);
    if (port && !port.startsWith(":")) throw new PyValueError("Invalid IPv6 URL");
  } else {
    const colon = hostAndPort.indexOf(":");
    hostname = colon < 0 ? hostAndPort : hostAndPort.slice(0, colon);
  }
  if (hostname.startsWith("v")) {
    if (!/^v[a-fA-F0-9]+\.[^\n]+$/u.test(hostname)) throw new PyValueError("IPvFuture address is invalid");
    return;
  }
  const kind = ipAddressKind(hostname);
  if (kind === null) throw new PyValueError("does not appear to be an IPv4 or IPv6 address");
  if (kind === "v4") throw new PyValueError("An IPv4 address cannot be in brackets");
}

/** 网络位置里含非 ASCII 字符、NFKC 之后冒出 / ? # @ : 的拒绝（IDNA 用 NFKC 等价）。 */
function checkNetloc(netloc: string): void {
  if (!netloc || /^[\u0000-\u007f]*$/u.test(netloc)) return;
  const stripped = netloc.replace(/[@:#?]/gu, "");
  const normalized = pyNfkc(stripped);
  if (stripped === normalized) return;
  for (const char of "/?#@:") {
    if (normalized.includes(char)) throw new PyValueError(`netloc '${netloc}' contains invalid characters under NFKC normalization`);
  }
}

/** NetlocResultMixins._hostinfo：(hostname, port)，port 为空串时为 null。 */
function hostinfo(netloc: string): [string, string | null] {
  const info = netloc.slice(netloc.lastIndexOf("@") + 1);
  const open = info.indexOf("[");
  let hostname: string;
  let port: string;
  if (open >= 0) {
    const bracketed = info.slice(open + 1);
    const close = bracketed.indexOf("]");
    hostname = close < 0 ? bracketed : bracketed.slice(0, close);
    const after = close < 0 ? "" : bracketed.slice(close + 1);
    const colon = after.indexOf(":");
    port = colon < 0 ? "" : after.slice(colon + 1);
  } else {
    const colon = info.indexOf(":");
    hostname = colon < 0 ? info : info.slice(0, colon);
    port = colon < 0 ? "" : info.slice(colon + 1);
  }
  return [hostname, port || null];
}

/** IPv4Address._ip_int_from_string：四段十进制，不许前导零，每段不超过 255。 */
function ipv4Int(address: string): number | null {
  if (!address) return null;
  const octets = address.split(".");
  if (octets.length !== 4) return null;
  let value = 0;
  for (const octet of octets) {
    if (!/^[0-9]{1,3}$/u.test(octet) || (octet !== "0" && octet.startsWith("0"))) return null;
    const number = Number(octet);
    if (number > 255) return null;
    value = value * 256 + number;
  }
  return value;
}

/** IPv6Address._ip_int_from_string（不含区域标识）能不能解析。 */
function ipv6Valid(address: string): boolean {
  if (!address) return false;
  const parts = address.split(":");
  if (parts.length < 3) return false;
  if ((parts[parts.length - 1] ?? "").includes(".")) {
    const ipv4 = ipv4Int(parts.pop() ?? "");
    if (ipv4 === null) return false;
    parts.push(Math.floor(ipv4 / 65536).toString(16), (ipv4 % 65536).toString(16));
  }
  if (parts.length > 9) return false;
  let skip: number | null = null;
  for (let index = 1; index < parts.length - 1; index += 1) {
    if (!parts[index]) {
      if (skip !== null) return false;
      skip = index;
    }
  }
  let high: number;
  let low: number;
  if (skip !== null) {
    high = skip;
    low = parts.length - skip - 1;
    if (!parts[0]) {
      high -= 1;
      if (high) return false;
    }
    if (!parts[parts.length - 1]) {
      low -= 1;
      if (low) return false;
    }
    if (8 - (high + low) < 1) return false;
  } else {
    if (parts.length !== 8 || !parts[0] || !parts[parts.length - 1]) return false;
    high = parts.length;
    low = 0;
  }
  const used = [...parts.slice(0, high), ...(low ? parts.slice(-low) : [])];
  return used.every((hextet) => /^[0-9a-fA-F]{1,4}$/u.test(hextet));
}
