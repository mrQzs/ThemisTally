// Python 路径函数的语义（os.path、pathlib，按本机平台）与 pi_dispatch 的路径小工具（迁移第 ② 步）。
//   abspath、normcase、relpath、Path.resolve（非严格）、is_within、display_path、is_link_or_junction、
//   first_link_component。
// 与 Python 的已知差异（迁移计划第 10 节）：
//   - normcase：Python 3.12 在 Windows 上用 LCMapStringEx 的不变区域小写，这里用 toLowerCase。只用于比较，
//     只在路径含特殊大小写字符（例如 İ）时才可能不同。
//   - abspath、Path.exists：Bun 下照 Python 调 GetFullPathNameW（去掉段尾的点与空格、末段的 nul 映射成设备）；Node 后备
//     没有原生调用，退回 path.resolve 与 existsSync，这两件都不做。
//   - 链接：Node 后备没有 GetFileAttributesW，只认符号链接与 junction，认不出其他重解析点。
import { existsSync, lstatSync, realpathSync } from "node:fs";
import path from "node:path";
import { FILE_ATTRIBUTE_REPARSE_POINT, fileAttributes, win32FullPathName } from "./native.ts";

const WIN = process.platform === "win32";
const SEP = path.sep;

/**
 * os.path.abspath。Windows 上照 ntpath.abspath：先 normpath，再调 GetFullPathNameW（Bun 下经 native.ts，入口先调过
 * initFileAttributes）；它会去掉段尾的点与空格、把末段的 nul 映射成 NUL 设备。调不了（Node 后备、路径里有 NUL 字符）时退回
 * path.resolve：相对当前目录、规范化（.、..、重复分隔符，/ 换成反斜杠），不做上面两件事。
 */
export function abspath(value: string): string {
  const full = WIN ? win32FullPathName(ntNormpath(value)) : null;
  return full ?? path.resolve(value);
}

/**
 * Path.exists()（跟随链接）。Windows 上 GetFullPathNameW 映射成设备的路径（末段是 nul 一类），上一级（文件或目录都行）在时也算存在：
 * Python 的 os.stat 打得开 NUL 设备，但上一级不在时报 FileNotFoundError（themistally-15 实测）；Node 的 existsSync 打不开设备。
 * Node 后备没有原生调用，这一条照旧是 false（第 10 节）。
 */
export function pyExists(value: string): boolean {
  if (existsSync(value)) return true;
  if (!WIN) return false;
  const norm = ntNormpath(value);
  return (win32FullPathName(norm) ?? "").startsWith(`${BS}${BS}.${BS}`) && existsSync(path.dirname(abspathPlain(norm)));
}

/** 不经 GetFullPathNameW 的绝对路径（只为取上一级：设备映射会把整条路径换掉）。 */
function abspathPlain(value: string): string {
  return path.resolve(value);
}

/** ntpath.normpath（Python 3.12）：/ 换成反斜杠，去掉空段与 .，按段消 ..（根下的 .. 丢掉），什么都不剩时写 .。 */
export function ntNormpath(value: string): string {
  const [drive, root, rest] = winSplitroot(value.replaceAll("/", BS));
  const comps = rest.split(BS);
  let index = 0;
  while (index < comps.length) {
    const comp = comps[index] as string;
    if (comp === "" || comp === ".") comps.splice(index, 1);
    else if (comp !== "..") index += 1;
    else if (index > 0 && comps[index - 1] !== "..") {
      comps.splice(index - 1, 2);
      index -= 1;
    } else if (index === 0 && root) comps.splice(index, 1);
    else index += 1;
  }
  if (!drive && !root && !comps.length) comps.push(".");
  return drive + root + comps.join(BS);
}

/** os.path.normcase：Windows 上小写并把 / 换成 \；POSIX 上原样。 */
export function normcase(value: string): string {
  return WIN ? value.replace(/\//gu, "\\").toLowerCase() : value;
}

/** pi_dispatch.norm_case：normcase(abspath(path))。 */
export function normCase(value: string): string {
  return normcase(abspath(value));
}

/** pi_dispatch.is_within。 */
export function isWithin(child: string, root: string): boolean {
  const a = normCase(child);
  const b = normCase(root);
  return a === b || a.startsWith(b.replace(/[\\/]+$/u, "") + SEP);
}

function rootAndParts(value: string): [string, string[]] {
  const parsed = path.parse(value);
  return [parsed.root, value.slice(parsed.root.length).split(/[\\/]/u).filter(Boolean)];
}

/** os.path.relpath(target, start)。 */
export function relpath(target: string, start: string): string {
  const [targetRoot, targetParts] = rootAndParts(abspath(target));
  const [startRoot, startParts] = rootAndParts(abspath(start));
  if (normcase(targetRoot) !== normcase(startRoot)) {
    throw new Error(`path is on mount ${targetRoot}, start on mount ${startRoot}`);
  }
  let common = 0;
  while (common < targetParts.length && common < startParts.length
    && normcase(targetParts[common] as string) === normcase(startParts[common] as string)) common += 1;
  const parts = [...Array<string>(startParts.length - common).fill(".."), ...targetParts.slice(common)];
  return parts.length === 0 ? "." : parts.join(SEP);
}

/** pi_dispatch.display_path：在 root 之下就写相对路径（正斜杠），否则写 str(path)。 */
export function displayPath(value: string, root?: string): string {
  if (root !== undefined && isWithin(value, root)) return relpath(value, root).replace(/\\/gu, "/");
  return value;
}

/**
 * Path.resolve()（非严格）：先规范化成绝对路径，再从最长的存在前缀求真实路径（展开链接、junction 与 8.3 短名，
 * 盘符与各段按磁盘上的大小写），剩下不存在的段原样接上。Windows 上照 ntpath.realpath（Python 3.12）：只 normpath、相对的接上
 * 当前目录，不调 GetFullPathNameW；规范化之后就是 nul 时是 NUL 设备；带着长路径前缀的，结果也带着（themistally-15 复核 ④b6 查出）。
 */
export function pyResolve(value: string): string {
  if (!WIN) return resolveExisting(abspath(value));
  const norm = ntNormpath(value);
  if (normcase(norm) === "nul") return `${BS}${BS}.${BS}NUL`;
  const verbatim = `${BS}${BS}?${BS}`;
  if (!norm.startsWith(verbatim)) return resolveExisting(ntIsabs(norm) ? norm : winJoin(process.cwd(), norm));
  const real = resolveExisting(norm);
  if (real.startsWith(verbatim)) return real;
  return real.startsWith(`${BS}${BS}`) ? `${verbatim}UNC${BS}${real.slice(2)}` : verbatim + real;
}

/** ntpath.isabs（Python 3.12）：以分隔符开头（含 UNC 与设备路径），或第二、三个字符是冒号加分隔符。/x 也算（Python 的老毛病）。 */
function ntIsabs(value: string): boolean {
  const head = value.slice(0, 3).replaceAll("/", BS);
  return head.startsWith(BS) || head.slice(1).startsWith(`:${BS}`);
}

/** 从最长的存在前缀求真实路径，剩下不存在的段原样接上；一路都不存在时原样交回。 */
function resolveExisting(full: string): string {
  const tail: string[] = [];
  let head = full;
  for (;;) {
    try {
      const real = realpathSync.native(head);
      return tail.length === 0 ? real : path.join(real, ...tail.reverse());
    } catch {
      const parent = path.dirname(head);
      if (parent === head) return full;
      tail.push(path.basename(head));
      head = parent;
    }
  }
}

/** pi_dispatch.is_link_or_junction：符号链接、junction，以及（Windows）一切带 REPARSE_POINT 属性的条目；出错为假。 */
export function isLinkOrJunction(value: string): boolean {
  if (value.includes("\0")) return false;
  try {
    if (lstatSync(value).isSymbolicLink()) return true;
  } catch {
    return false;
  }
  const attributes = fileAttributes(value);
  return attributes !== null && (attributes & FILE_ATTRIBUTE_REPARSE_POINT) !== 0;
}

/** pi_dispatch.first_link_component：root 之下 rel 从根往下第一个是链接的那一级（POSIX 写法），没有为 null。 */
export function firstLinkComponent(root: string, rel: string): string | null {
  const text = rel.replace(/\\/gu, "/");
  const parts = text.split("/").filter((part) => part !== "" && part !== ".");
  if (text.startsWith("/") || path.isAbsolute(rel) || /^[A-Za-z]:/u.test(rel) || parts.includes("..")) {
    throw new Error(`first_link_component 需要 root 之下不含 .. 的相对路径：${rel}`);
  }
  let current = root;
  for (let index = 0; index < parts.length; index += 1) {
    current = path.join(current, parts[index] as string);
    if (isLinkOrJunction(current)) return parts.slice(0, index + 1).join("/");
  }
  return null;
}

const BS = String.fromCharCode(92);

// --- pathlib 的规整写法（迁移第 ③ 步：配置中心把 str(Path(...)) 写进输出）---------------------------------

interface ParsedPath {
  readonly drive: string;
  readonly root: string;
  readonly tail: readonly string[];
}

/** ntpath.splitroot（Python 3.12）：(盘符或 UNC 前缀, 根, 其余)。下标按码点算：盘符的冒号是“第二个字符”。 */
function winSplitroot(value: string): [string, string, string] {
  const sep = BS;
  const norm = value.replaceAll("/", sep);
  const chars = Array.from(norm);
  if (chars[0] === sep) {
    if (chars[1] === sep) {
      const start = norm.slice(0, 8).toUpperCase() === `${sep}${sep}?${sep}UNC${sep}` ? 8 : 2;
      const index = norm.indexOf(sep, start);
      if (index < 0) return [value, "", ""];
      const second = norm.indexOf(sep, index + 1);
      if (second < 0) return [value, "", ""];
      return [value.slice(0, second), value.slice(second, second + 1), value.slice(second + 1)];
    }
    return ["", value.slice(0, 1), value.slice(1)];
  }
  if (chars[1] === ":") {
    const driveLength = (chars[0] as string).length + 1;
    return chars[2] === sep
      ? [value.slice(0, driveLength), value.slice(driveLength, driveLength + 1), value.slice(driveLength + 1)]
      : [value.slice(0, driveLength), "", value.slice(driveLength)];
  }
  return ["", "", value];
}

/** PurePath._parse_path：Windows 上 / 换成 \、UNC 的 \server\share 补上根；去掉空段与 "."，".." 照留。 */
function parsePurePath(value: string): ParsedPath {
  if (!value) return { drive: "", root: "", tail: [] };
  const sep = WIN ? BS : "/";
  const text = WIN ? value.replaceAll("/", sep) : value;
  let drive = "";
  let root = "";
  let rest = text;
  if (WIN) {
    [drive, root, rest] = winSplitroot(text);
    if (!root && drive.startsWith(sep) && !drive.endsWith(sep)) {
      const parts = drive.split(sep);
      if ((parts.length === 4 && !"?.".includes(parts[2] as string)) || parts.length === 6) root = sep;
    }
  } else if (text.startsWith("/")) {
    root = text.startsWith("//") && !text.startsWith("///") ? "//" : "/";
    rest = text.slice(root.length);
  }
  return { drive, root, tail: rest.split(sep).filter((part) => part !== "" && part !== ".") };
}

function formatPurePath(parsed: ParsedPath): string {
  const sep = WIN ? BS : "/";
  if (parsed.drive || parsed.root) return parsed.drive + parsed.root + parsed.tail.join(sep);
  const tail = WIN && parsed.tail.length && winSplitroot(parsed.tail[0] as string)[0] ? [".", ...parsed.tail] : parsed.tail;
  return tail.join(sep) || ".";
}

/** ntpath.join（Python 3.12）：后一段带根时替换前面的；UNC 前缀与不带根的部分之间补一个分隔符。 */
function winJoin(first: string, ...rest: string[]): string {
  const seps = BS + "/";
  let [drive, root, tail] = winSplitroot(first);
  for (const part of rest) {
    const [partDrive, partRoot, partTail] = winSplitroot(part);
    if (partRoot) {
      if (partDrive || !drive) drive = partDrive;
      root = partRoot;
      tail = partTail;
      continue;
    }
    if (partDrive && partDrive !== drive) {
      if (partDrive.toLowerCase() !== drive.toLowerCase()) {
        [drive, root, tail] = [partDrive, partRoot, partTail];
        continue;
      }
      drive = partDrive;
    }
    if (tail && !seps.includes(tail[tail.length - 1] as string)) tail += BS;
    tail += partTail;
  }
  if (tail && !root && drive && !`:${seps}`.includes(drive[drive.length - 1] as string)) return drive + BS + tail;
  return drive + root + tail;
}

/** PurePath(value).is_absolute()：Windows 上要同时有盘符（或 UNC 前缀）与根，POSIX 上以 / 开头。 */
export function purePathIsAbsolute(value: string): boolean {
  if (!WIN) return value.startsWith("/");
  const parsed = parsePurePath(value);
  return Boolean(parsed.drive && parsed.root);
}

/** str(PurePath(value, *parts))：几段先照 os.path.join 拼起来（pathlib 就是这么做的），再规整。 */
export function purePathStr(value: string, ...parts: string[]): string {
  const joined = parts.length === 0 ? value : WIN ? winJoin(value, ...parts) : path.posix.join(value, ...parts);
  return formatPurePath(parsePurePath(joined));
}

/** str(PurePath(value).parent)：没有可去的段时是它自己。 */
export function purePathParent(value: string): string {
  const parsed = parsePurePath(value);
  return formatPurePath(parsed.tail.length ? { ...parsed, tail: parsed.tail.slice(0, -1) } : parsed);
}

/** os.path.join：Windows 上是 ntpath.join（不规整），其余照 posixpath.join。 */
export function osPathJoin(first: string, ...rest: string[]): string {
  if (WIN) return winJoin(first, ...rest);
  let joined = first;
  for (const part of rest) joined = part.startsWith("/") ? part : !joined || joined.endsWith("/") ? joined + part : `${joined}/${part}`;
  return joined;
}

/** os.path.split（Python 3.12 的 ntpath.split）：(目录部分, 最后一段)；根先分出去，目录部分末尾的分隔符全部去掉。 */
export function osPathSplit(value: string): [string, string] {
  const seps = WIN ? BS + "/" : "/";
  const rootLength = value.length - value.replace(/^\/+/u, "").length;
  const [drive, root, rest] = WIN ? winSplitroot(value) : ["", value.slice(0, rootLength), value.slice(rootLength)];
  let index = rest.length;
  while (index && !seps.includes(rest[index - 1] as string)) index -= 1;
  let end = index;
  while (end && seps.includes(rest[end - 1] as string)) end -= 1;
  return [drive + root + rest.slice(0, end), rest.slice(index)];
}

/** ntpath.expanduser：~ 与 ~user 换成用户目录；拿不到用户目录时原样。 */
export function expanduser(value: string): string {
  if (!value.startsWith("~")) return value;
  if (process.platform !== "win32") {
    const home = process.env["HOME"];
    return home && (value === "~" || value.startsWith("~/")) ? home.replace(/\/+$/u, "") + value.slice(1) || "/" : value;
  }
  let end = 1;
  while (end < value.length && value[end] !== "\\" && value[end] !== "/") end += 1;
  let home: string;
  if (process.env["USERPROFILE"] !== undefined) home = process.env["USERPROFILE"];
  else if (process.env["HOMEPATH"] === undefined) return value;
  else home = path.win32.join(process.env["HOMEDRIVE"] ?? "", process.env["HOMEPATH"]);
  if (end !== 1) {
    const target = value.slice(1, end);
    const current = process.env["USERNAME"];
    if (target !== current) {
      if (current !== path.win32.basename(home)) return value;
      home = path.win32.join(path.win32.dirname(home), target);
    }
  }
  return home + value.slice(end);
}
