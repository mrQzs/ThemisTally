// pi_dispatch 的 release-check（迁移第 ④b2 片）：推送前扫描已跟踪与未忽略的文件里有没有凭据形状、家目录路径、内网地址，
// 以及仓库之外拒绝清单里的字符串。三条模式照 Python 逐字译：\b \d \s 是 Unicode 的（pyre 的区间表），反斜杠在正则源码里
// 用 String.fromCharCode 拼。文件照 read_text(errors="replace") 读：通用换行、保留 BOM；行号与 24 个字符的摘录按 Python 算。
import { statSync } from "node:fs";
import path from "node:path";
import { PyCrash, type PyOut } from "@themis/base/pyfmt";
import { pyReadBytes, pyReadText } from "@themis/base/pyio";
import { displayPath, expanduser, isLinkOrJunction, isWithin, purePathStr, pyResolve } from "@themis/base/pypath";
import { D, S, WB, codePoints, pyLower, pyRegex, pySplitlines, pyStrip } from "@themis/base/pyre";
import { globRegex } from "./patterns.ts";
import { releaseAllowRules, repoConfig } from "./kernel-config.ts";
import { DispatchError, EXIT_FAIL, EXIT_OK, EXIT_USAGE, Repo, git } from "./repo.ts";

const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);
/** 正则源码里的一个反斜杠字面量（转义过的两个字符）。 */
const BACKSLASH = String.fromCharCode(92, 92);

/** RELEASE_PATTERNS：次序照 Python 的字典（api key、home path、private address）。 */
export const RELEASE_PATTERNS: [string, RegExp][] = [
  ["api key", pyRegex(
    `${WB}(?:apikey_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}` +
      `|AIza[0-9A-Za-z_-]{35}|xox[abprs]-[A-Za-z0-9-]{10,})${WB}`, true)],
  ["home path", pyRegex(
    `(?<![A-Za-z0-9_])(?:/Users/[A-Za-z][A-Za-z0-9_.-]*/|/home/[a-z][a-z0-9_.-]*/` +
      `|[A-Za-z]:[${BACKSLASH}/]+Users[${BACKSLASH}/]+(?:(?!${S})[^${BACKSLASH}/"'<>*?|])+[${BACKSLASH}/])`, true)],
  ["private address", pyRegex(
    `${WB}(?:100[.](?:6[4-9]|[7-9]${D}|1[01]${D}|12[0-7])|192[.]168|10|172[.](?:1[6-9]|2${D}|3[01]))` +
      `(?:[.](?:25[0-5]|2[0-4]${D}|1?${D}?${D})){2,3}${WB}(?![.]${D})|${WB}[a-z0-9-]+[.]ts[.]net${WB}`, true)],
];
const RELEASE_BINARY_SUFFIXES = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".pdf", ".ico", ".zip", ".gz", ".pyc"];
const RELEASE_DENYLIST_ENV = "CODEKIT_RELEASE_DENYLIST";

export interface ReleaseCheckArgs {
  readonly repo: string | null;
  readonly allow: readonly string[] | null;
  readonly denylist: string | null;
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

/** PurePath.suffix：最后一段里最后一个点之后的部分；点在开头或结尾时没有后缀（.gitignore 没有后缀）。 */
function suffixOf(name: string): string {
  const last = codePoints(name.slice(name.lastIndexOf("/") + 1));
  const at = last.lastIndexOf(".");
  return at > 0 && at < last.length - 1 ? last.slice(at).join("") : "";
}

/** fnmatch_path：仓库相对路径对 glob 的匹配；以 / 结尾的写法是目录前缀。 */
export function fnmatchPath(name: string, pattern: string): boolean {
  const posixName = name.split(path.sep).join("/");
  const posixPattern = pattern.split(path.sep).join("/");
  if (posixPattern.endsWith("/")) return posixName.startsWith(posixPattern);
  return globRegex(posixPattern, false).test(posixName);
}

/** read_text(encoding="utf-8", errors="replace")：不合法的字节换成 U+FFFD，保留 BOM，通用换行。 */
function readReplacing(file: string): string {
  return new TextDecoder("utf-8", { ignoreBOM: true }).decode(pyReadBytes(file)).replace(new RegExp(`${CR}${LF}?`, "gu"), LF);
}

/** 拒绝清单的路径：--denylist，否则环境变量（空串当没设），再否则 ~/.config/code-kit/release-denylist.txt。 */
function denylistPath(arg: string | null): string {
  if (arg) return arg;
  const configured = process.env[RELEASE_DENYLIST_ENV];
  if (configured) return configured;
  const home = expanduser("~");
  if (home === "~") throw new PyCrash("RuntimeError", "Could not determine home directory.");
  return path.join(home, ".config", "code-kit", "release-denylist.txt");
}

export function cmdReleaseCheck(args: ReleaseCheckArgs, out: PyOut, kitRoot: string): number {
  const repo = Repo.discover(args.repo);
  const rules = releaseAllowRules(repoConfig(repo), args.allow ?? []);
  const proc = git(["ls-files", "-co", "--exclude-standard", "-z"], repo.root);
  const decoder = new TextDecoder("utf-8", { ignoreBOM: true });
  const names = splitNul(proc.stdout).map((item) => decoder.decode(item));
  if (proc.status !== 0 || !names.length) throw new DispatchError("release-check 没有扫描任何文件（不是 Git 检出，或 git 失败）：这不是通过", EXIT_FAIL);
  const denyArg = denylistPath(args.denylist);
  const denyPath = path.resolve(process.cwd(), denyArg);
  if (isWithin(pyResolve(denyPath), repo.root)) throw new DispatchError(`拒绝清单不能放在仓库里面：${purePathStr(denyArg)}`, EXIT_USAGE);
  const deny = isFile(denyPath)
    ? pySplitlines(pyReadText(denyPath)).filter((line) => pyStrip(line) && !line.startsWith("#")).map((line) => pyLower(pyStrip(line)))
    : [];
  const selfName = displayPath(pyResolve(path.join(kitRoot, "scripts", "pi_dispatch.py")), repo.root).split(path.sep).join("/");
  const problems: string[] = [];
  const unscanned: string[] = [];
  let scanned = 0;
  for (const name of names) {
    const file = path.join(repo.root, name);
    if (!isFile(file) || isLinkOrJunction(file)) continue;
    if (RELEASE_BINARY_SUFFIXES.includes(pyLower(suffixOf(name)))) {
      unscanned.push(name);
      continue;
    }
    let content: string;
    try {
      content = readReplacing(file);
    } catch {
      unscanned.push(name);
      continue;
    }
    scanned += 1;
    const allowed = new Set(rules.filter(([pattern]) => fnmatchPath(name, pattern)).map(([, label]) => label));
    scanPatterns(name, content, allowed, selfName, problems);
    if (!deny.length) continue; // 没有拒绝清单就不必算小写（Python 照样算，结果用不上）
    const lowered = pyLower(content);
    deny.forEach((entry, index) => {
      if (lowered.includes(entry)) problems.push(`${name}: 含拒绝清单第 ${index + 1} 项`);
    });
  }
  if (unscanned.length) out.print(`NOT SCANNED（${unscanned.length} 个二进制或不可读文件）：${unscanned.slice(0, 30).join(", ")}——推送前人眼看一遍`);
  for (const problem of problems) out.print(problem);
  if (problems.length) {
    out.print(`release-check：${problems.length} 处命中，${scanned} 个文本文件。确认是假阳性的，用 --allow '<glob>:<模式名>' 或 ` +
      "dispatch.config.json 的 release_check.allow 放过");
    return EXIT_FAIL;
  }
  out.print(`clean: ${scanned} 个文本文件${deny.length ? `，拒绝清单 ${deny.length} 项` : "，没有拒绝清单"}`);
  return EXIT_OK;
}

/** api key 命中时输出里只给这些公开的前缀与长度，前缀之后一个字符也不显示（第 126 轮）。 */
const RELEASE_KEY_PREFIX_RE = /^(?:apikey_|sk-|gh[pousr]_|AKIA|AIza|xox[abprs]-)/u;

/** _release_excerpt：api key 只给公开前缀与长度；家目录路径、内网地址不是秘密，照旧给前 24 个字符。 */
function releaseExcerpt(label: string, text: string): string {
  if (label !== "api key") return `${codePoints(text).slice(0, 24).join("")}…`;
  const prefix = RELEASE_KEY_PREFIX_RE.exec(text);
  return `${prefix ? prefix[0] : ""}…（${codePoints(text).length} 字符）`;
}

/** 一个文件按三条模式扫：一个文件命中满 20 条（连同先前模式的）就记一行“命中过多”，其余模式也不再扫。 */
function scanPatterns(name: string, content: string, allowed: Set<string>, selfName: string, problems: string[]): void {
  for (const [label, pattern] of RELEASE_PATTERNS) {
    if (allowed.has("*") || allowed.has(label) || name === selfName) continue;
    for (const match of content.matchAll(pattern)) {
      const lineNo = content.slice(0, match.index).split(LF).length;
      problems.push(`${name}:${lineNo}: ${label}: ${releaseExcerpt(label, match[0])}`);
      if (problems.filter((problem) => problem.startsWith(`${name}:`)).length >= 20) {
        problems.push(`${name}: 命中过多，其余省略`);
        return;
      }
    }
  }
}

function splitNul(data: Buffer): Buffer[] {
  const parts: Buffer[] = [];
  let start = 0;
  for (let at = data.indexOf(0); at >= 0; at = data.indexOf(0, start)) {
    if (at > start) parts.push(data.subarray(start, at));
    start = at + 1;
  }
  if (start < data.length) parts.push(data.subarray(start));
  return parts;
}
