// pi_dispatch 用临时索引给工作副本拍快照、比较两棵树（迁移第 ④b2 片）：line_ending_args、snapshot_tree、unindexable_paths、
// diff_raw、tree_drift。不动工作副本的真实索引与 HEAD，也不建提交。git 调用照 Python 的缺省 check=True，失败就报错。
import { statSync, unlinkSync } from "node:fs";
import path from "node:path";
import { PyCrash } from "@themis/base/pyfmt";
import { pyDecodeUtf8, pyOSErrorOf } from "@themis/base/pyio";
import { type PyDict, type PyValue } from "@themis/base/pyjson";
import { PY_END, ci, cmpCodePoints, pyRegex } from "@themis/base/pyre";
import { gitChecked, gitText } from "./repo.ts";

const LF = String.fromCharCode(10);
const NUL = String.fromCharCode(0);
const REPLACEMENT = String.fromCharCode(0xfffd);

/** Windows 的保留设备名（不分大小写，带扩展名的也算）：git 在 Windows 上收不进。 */
const RESERVED_NAME_RE = pyRegex(
  `^(${ci("con")}|${ci("prn")}|${ci("aux")}|${ci("nul")}|${ci("com")}[1-9]|${ci("lpt")}[1-9])([.][^${LF}]*)?${PY_END}`,
);

/** line_ending_args：把 prepare 时记录的 core.autocrlf 固定进 git 命令；unset 当 false，没记录时不加。 */
export function lineEndingArgs(autocrlf: PyValue | undefined): string[] {
  if (autocrlf === "true" || autocrlf === "false" || autocrlf === "input") return ["-c", `core.autocrlf=${autocrlf}`];
  return autocrlf === "unset" ? ["-c", "core.autocrlf=false"] : [];
}

function exists(file: string): boolean {
  try {
    statSync(file);
    return true;
  } catch {
    return false;
  }
}

/** snapshot_tree：用临时索引记下工作副本的完整内容（已跟踪加没被忽略的新文件），交回树对象 ID。 */
export function snapshotTree(workDir: string, base: string, scratchDir: string, label: string, autocrlf: PyValue | undefined = null): string {
  const index = path.join(scratchDir, `.${label}.index`);
  const stale = [index, `${index}.lock`];
  for (const file of stale) {
    if (!exists(file)) continue;
    try {
      unlinkSync(file);
    } catch (error) {
      throw pyOSErrorOf(error, file) ?? error;
    }
  }
  try {
    gitChecked(["read-tree", base], workDir, { indexFile: index });
    // 保留设备名要在 read-tree 之后、拼 add 的参数时查（照 Python 的求值次序）
    const excludes = unindexablePaths(workDir).map((item) => `:(exclude,literal)${item}`);
    gitChecked([...lineEndingArgs(autocrlf), "add", "-A", "--", ".", ...excludes], workDir, { indexFile: index });
    return gitText(["write-tree"], workDir, { indexFile: index });
  } finally {
    for (const file of stale) {
      if (!exists(file)) continue;
      try {
        unlinkSync(file);
      } catch {
        // 照 Python：收尾时删不掉就算了
      }
    }
  }
}

/** unindexable_paths：工作副本里 git 在 Windows 上收不进的新增或改动的路径（保留设备名）；别的平台为空。 */
export function unindexablePaths(workDir: string): string[] {
  if (process.platform !== "win32") return [];
  const out = new TextDecoder("utf-8").decode(gitChecked(["status", "--porcelain=v1", "-z", "--untracked-files=all"], workDir).stdout);
  // 每段去掉前三个字符（两个状态字母与空格）；改名记录的旧路径没有前缀也照切，照 Python
  const paths = out.split(NUL).filter((item) => codeLength(item) > 3).map((item) => [...item].slice(3).join(""));
  return paths.filter((item) => RESERVED_NAME_RE.test(lastPart(item))).sort(cmpCodePoints);
}

const codeLength = (text: string): number => [...text].length;

/** path.rstrip("/").rsplit("/", 1)[-1]。 */
function lastPart(item: string): string {
  let end = item.length;
  while (end > 0 && item[end - 1] === "/") end -= 1;
  const trimmed = item.slice(0, end);
  return trimmed.slice(trimmed.lastIndexOf("/") + 1);
}

function splitBytes(data: Buffer, separator: number): Buffer[] {
  const parts: Buffer[] = [];
  let start = 0;
  for (let at = data.indexOf(separator); at >= 0; at = data.indexOf(separator, start)) {
    parts.push(data.subarray(start, at));
    start = at + 1;
  }
  parts.push(data.subarray(start));
  return parts;
}

/** bytes.decode("ascii", "replace")。 */
const asciiReplace = (data: Buffer): string => [...data].map((byte) => (byte < 128 ? String.fromCharCode(byte) : REPLACEMENT)).join("");

/** diff_raw：两棵树之间改动的路径、状态与模式；路径不是 UTF-8 时按替换解码并记 path_decode_error。 */
export function diffRaw(cwd: string, base: string, tree: string): PyDict[] {
  const out = gitChecked(["diff", "--raw", "-z", "--no-renames", "--no-abbrev", "--no-ext-diff", "--no-textconv", base, tree], cwd).stdout;
  const parts = splitBytes(out, 0);
  const changes: PyDict[] = [];
  let index = 0;
  while (index < parts.length - 1) {
    const meta = asciiReplace(parts[index] as Buffer);
    if (!meta.startsWith(":")) {
      index += 1;
      continue;
    }
    const raw = parts[index + 1] as Buffer;
    let file: string;
    let decodeError = false;
    try {
      file = pyDecodeUtf8(raw);
    } catch {
      file = new TextDecoder("utf-8").decode(raw);
      decodeError = true;
    }
    const fields = meta.slice(1).split(" ");
    if (fields.length !== 5) throw new PyCrash("ValueError", `too many values to unpack (expected 5, got ${fields.length})`);
    const [oldMode, newMode, , , status] = fields as [string, string, string, string, string];
    const item: PyDict = new Map<string, PyValue>([["path", file], ["status", [...status].slice(0, 1).join("")], ["old_mode", oldMode], ["new_mode", newMode]]);
    if (decodeError) item.set("path_decode_error", "true");
    changes.push(item);
    index += 2;
  }
  return changes;
}

/** tree_drift：修改或删除了候选里的文件是漂移；只新增的算检查或复审产生的额外产物。 */
export function treeDrift(cwd: string, candidateTree: string, currentTree: string): { modified: string[]; added: string[] } {
  if (candidateTree === currentTree) return { modified: [], added: [] };
  const changes = diffRaw(cwd, candidateTree, currentTree);
  return {
    modified: changes.filter((change) => change.get("status") !== "A").map((change) => change.get("path") as string),
    added: changes.filter((change) => change.get("status") === "A").map((change) => change.get("path") as string),
  };
}
