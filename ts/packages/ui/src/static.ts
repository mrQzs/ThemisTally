// 静态资源的目录边界（桌面端设计第 7 版 §5.2、T13）：--assets 之外的任何一个字节都不许出去。顺序固定，且路径
// **只解码一次**：先在原始 pathname 里拒绝编码过的分隔符与 %00，之后 decodeURIComponent 只解一次，解码得到的
// 字面内容（例如 %252e%252e 解一次是 %2e%2e）当成一个不存在的文件名，绝不再解第二次。每一类拒绝都有自己的
// reason，纯函数、不碰进程状态，方便逐类钉住。
import { lstatSync, realpathSync, statSync, type Stats } from "node:fs";
import { basename, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { FILE_ATTRIBUTE_REPARSE_POINT, fileAttributes } from "@themis/base/native";

/** 解析的结果：要么是目录内的一个文件加它的媒体类型，要么是一类拒绝。 */
export type AssetResult =
  | { readonly ok: true; readonly path: string; readonly contentType: string }
  | { readonly ok: false; readonly status: 400 | 403 | 404; readonly reason: string };

/** 后缀到媒体类型的白名单：不在表里的后缀一律 404，不猜。 */
export const CONTENT_TYPES: Readonly<Record<string, string>> = {
  html: "text/html; charset=utf-8",
  js: "text/javascript; charset=utf-8",
  mjs: "text/javascript; charset=utf-8",
  css: "text/css; charset=utf-8",
  json: "application/json; charset=utf-8",
  txt: "text/plain; charset=utf-8",
  woff2: "font/woff2",
  woff: "font/woff",
  svg: "image/svg+xml",
  png: "image/png",
  ico: "image/x-icon",
};

/** 根路径对应的文件。 */
export const INDEX_FILE = "index.html";

/** 原始 pathname 里不许出现的东西（不分大小写）：编码过的点、编码过的分隔符与 NUL。 */
const ENCODED_REJECT = /%2f|%5c|%2e|%00/i;
/** NUL 单独一类：控制字符。 */
const ENCODED_NUL = /%00/i;

/** 盘符：一个字母加冒号（Windows 的 C:）。 */
const DRIVE_LETTER = /^[A-Za-z]:/;
/** 控制字符（含 NUL）。 */
const CONTROL_CHAR = /[\u0000-\u001f\u007f]/;

/**
 * 原始路径：交给 fetch 的 req.url 已经被 HTTP 层规范化过（.. 与 %2e%2e 解析掉、反斜杠换成 /，只有 %2f 保留
 * 编码），这里只是把它取出来，不再做任何规范化——规范化的后果由本文件的纯函数测试逐类钉住。
 */
export function rawPathOf(request: Request | URL | string): string {
  const url = typeof request === "string" ? new URL(request) : request instanceof URL ? request : new URL(request.url);
  return url.pathname;
}

/** full 是不是确实在 root 里面（不是 root 本身，也不是它的上级）。 */
export function isWithin(root: string, full: string): boolean {
  const rel = relative(resolve(root), resolve(full));
  return rel !== "" && !rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel);
}

/** 这个路径是不是重解析点（junction、符号链接）：先 Bun 的 FFI 绑定，拿不到退回 lstat。 */
export function isReparsePoint(path: string): boolean {
  const attributes = fileAttributes(path);
  if (attributes !== null) return (attributes & FILE_ATTRIBUTE_REPARSE_POINT) !== 0;
  try {
    return lstatSync(path).isSymbolicLink();
  } catch {
    return false;
  }
}

/** 解析时可注入的项（只给测试用）：stat 替身让「不是普通文件」这一类不依赖真实设备文件。 */
export interface ResolveAssetOptions {
  readonly stat?: (path: string) => Stats;
}

/**
 * 把 pathname 解析成 --assets 里的一个文件。步骤照合同：预解码拒绝、只解码一次、逐段检查、目录边界、重解析点、
 * realpath 边界、存在性、目录、普通文件（T18：设备与管道文件不是静态资源）、后缀白名单。
 */
export function resolveAsset(root: string, pathname: string, options: ResolveAssetOptions = {}): AssetResult {
  if (ENCODED_NUL.test(pathname)) return refuse(400, "control-char");
  if (ENCODED_REJECT.test(pathname)) return refuse(400, "encoded-dot-or-separator");
  let decoded: string;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return refuse(400, "bad-encoding");
  }
  const segments = decoded === "/" ? [INDEX_FILE] : decoded.slice(1).split("/");
  for (const [index, segment] of segments.entries()) {
    if (segment.includes("\\")) return refuse(400, "backslash");
    if (CONTROL_CHAR.test(segment)) return refuse(400, "control-char");
    if (segment === "") return refuse(400, "empty-segment");
    if (segment === "." || segment === "..") return refuse(400, "dot-segment");
    if (index === 0 && DRIVE_LETTER.test(segment)) return refuse(400, "drive-letter"); // 只有第一段
    if (segment.includes(":")) return refuse(400, "colon");
    if (/[. ]$/u.test(segment)) return refuse(400, "trailing-dot-or-space");
  }
  const full = join(resolve(root), ...segments);
  if (!isWithin(root, full)) return refuse(403, "outside-root");
  // 从 root 的下一级开始逐级看是不是重解析点（含目标本身）：root 自己是不是 junction 由下面的 realpath 判
  let walk = resolve(root);
  for (const segment of segments) {
    walk = join(walk, segment);
    if (isReparsePoint(walk)) return refuse(403, "reparse-point");
  }
  try {
    if (!isWithin(realpathSync(resolve(root)), realpathSync(full))) return refuse(403, "outside-root");
  } catch {
    // realpath 拿不到：交给下面的存在性检查说话
  }
  const stat = options.stat ?? statSync;
  let stats;
  try {
    stats = stat(full);
  } catch {
    return refuse(404, "not-found");
  }
  if (stats.isDirectory()) return refuse(404, "directory");
  if (!stats.isFile()) return refuse(404, "not-a-file"); // 设备、管道、套接字都不是静态资源（T18）
  const extension = extname(basename(full)).replace(".", "").toLowerCase();
  const contentType = CONTENT_TYPES[extension];
  if (contentType === undefined) return refuse(404, "type-not-allowed");
  return { ok: true, path: full, contentType };
}

function refuse(status: 400 | 403 | 404, reason: string): AssetResult {
  return { ok: false, status, reason };
}
