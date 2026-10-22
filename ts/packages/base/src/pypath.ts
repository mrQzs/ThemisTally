// Python 路径函数的语义（os.path、pathlib，按本机平台）与 pi_dispatch 的路径小工具（迁移第 ② 步）。
//   abspath、normcase、relpath、Path.resolve（非严格）、is_within、display_path、is_link_or_junction、
//   first_link_component。
// 与 Python 的已知差异（迁移计划第 10 节）：
//   - normcase：Python 3.12 在 Windows 上用 LCMapStringEx 的不变区域小写，这里用 toLowerCase。只用于比较，
//     只在路径含特殊大小写字符（例如 İ）时才可能不同。
//   - abspath：Windows 的 GetFullPathNameW 会去掉段尾的点与空格，path.win32.resolve 不去。
//   - 链接：Node 后备没有 GetFileAttributesW，只认符号链接与 junction，认不出其他重解析点。
import { lstatSync, realpathSync } from "node:fs";
import path from "node:path";
import { FILE_ATTRIBUTE_REPARSE_POINT, fileAttributes } from "./native.ts";

const WIN = process.platform === "win32";
const SEP = path.sep;

/** os.path.abspath：相对当前目录、规范化（.、..、重复分隔符；Windows 上 / 换成 \）。 */
export function abspath(value: string): string {
  return path.resolve(value);
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
 * 盘符与各段按磁盘上的大小写），剩下不存在的段原样接上。
 */
export function pyResolve(value: string): string {
  const full = abspath(value);
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
