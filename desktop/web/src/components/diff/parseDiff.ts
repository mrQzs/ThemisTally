// git 补丁解析（UI 文档 7.14）：纯函数，把 candidate.patch 的文本解析成文件、片段与行。
// 只做结构解析：行内容原样保留（不去 ANSI，由调用方显示前统一处理）；不碰 DOM、不引入 React。
// 解析规则见合同 §5.1 的 R1–R10；性能要求线性，1 MiB 的病态输入 2 秒内返回。

export type DiffStatus = 'modified' | 'added' | 'deleted' | 'renamed';

/** 片段里的一行：kind 区分上下文/增/删；text 去掉行首标记后的内容，原样；oldNo/newNo 没有就是 null。 */
export interface DiffLine {
  kind: 'context' | 'add' | 'del';
  text: string;
  oldNo: number | null;
  newNo: number | null;
  /** 这一行末尾带「\ No newline at end of file」标记。 */
  noNewline: boolean;
}

export interface DiffHunk {
  /** 整行片段头（含可有可无的余下文字）。 */
  header: string;
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: DiffLine[];
}

export interface DiffFile {
  oldPath: string | null;
  newPath: string | null;
  status: DiffStatus;
  binary: boolean;
  hunks: DiffHunk[];
  additions: number;
  deletions: number;
}

interface WorkFile {
  oldPath: string | null;
  newPath: string | null;
  newFileMode: boolean;
  deletedFileMode: boolean;
  renameFrom: string | null;
  renameTo: string | null;
  binary: boolean;
  skipBinary: boolean;
  hunks: DiffHunk[];
}

const DIFF_GIT = 'diff --git ';
// 片段头：@@ -a[,b] +c[,d] @@（b、d 缺省为 1）；锚定开头、无嵌套量词，病态数字行也线性。
const HUNK_RE = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;

/** R1：按换行切行，每行去掉一个末尾回车；文本以换行结尾时末尾的空串不算一行。 */
function splitLines(text: string): string[] {
  if (text === '') return [];
  const raw = text.split('\n');
  for (let i = 0; i < raw.length; i += 1) {
    if (raw[i].endsWith('\r')) raw[i] = raw[i].slice(0, -1);
  }
  if (raw.length > 1 && raw[raw.length - 1] === '') raw.pop();
  return raw;
}

function pushUtf8(bytes: number[], code: number): void {
  if (code < 0x80) bytes.push(code);
  else if (code < 0x800) bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
  else if (code < 0x10000) bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
  else bytes.push(0xf0 | (code >> 18), 0x80 | ((code >> 12) & 0x3f), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
}

function utf8Decode(bytes: number[]): string {
  if (bytes.length === 0) return '';
  // 非 fatal：解不出的字节按 UTF-8 替换字符处理（R5）。
  return new TextDecoder('utf-8', { fatal: false }).decode(new Uint8Array(bytes));
}

function isOctal(ch: string): boolean {
  return ch >= '0' && ch <= '7';
}

/** R5：以双引号开头的路径按 C 风格还原；返回还原后的文字与结束下标（闭引号之后）。 */
function parseQuoted(s: string, start: number): { value: string; end: number } {
  const bytes: number[] = [];
  const n = s.length;
  let i = start + 1;
  while (i < n) {
    const ch = s[i];
    if (ch === '"') return { value: utf8Decode(bytes), end: i + 1 };
    if (ch === '\\') {
      const next = s[i + 1];
      if (next === undefined) {
        bytes.push(0x5c);
        i += 1;
        continue;
      }
      if (next === '\\') { bytes.push(0x5c); i += 2; continue; }
      if (next === '"') { bytes.push(0x22); i += 2; continue; }
      if (next === 'a') { bytes.push(0x07); i += 2; continue; }
      if (next === 'b') { bytes.push(0x08); i += 2; continue; }
      if (next === 'f') { bytes.push(0x0c); i += 2; continue; }
      if (next === 'n') { bytes.push(0x0a); i += 2; continue; }
      if (next === 'r') { bytes.push(0x0d); i += 2; continue; }
      if (next === 't') { bytes.push(0x09); i += 2; continue; }
      if (next === 'v') { bytes.push(0x0b); i += 2; continue; }
      const oct = s.slice(i + 1, i + 4);
      if (oct.length === 3 && isOctal(oct[0]) && isOctal(oct[1]) && isOctal(oct[2])) {
        bytes.push(parseInt(oct, 8));
        i += 4;
        continue;
      }
      bytes.push(0x5c);
      pushUtf8(bytes, next.codePointAt(0)!);
      i += 1 + next.length;
      continue;
    }
    pushUtf8(bytes, ch.codePointAt(0)!);
    i += ch.length;
  }
  return { value: utf8Decode(bytes), end: n };
}

/** R5：一个路径记号——带引号按 C 风格还原，不带引号截到第一个制表符。 */
function decodeToken(token: string): string {
  if (token.startsWith('"')) return parseQuoted(token, 0).value;
  const tab = token.indexOf('\t');
  return tab >= 0 ? token.slice(0, tab) : token;
}

/** 去掉一个 a/ 或 b/ 前缀。 */
function stripAB(p: string): string {
  if (p.startsWith('a/')) return p.slice(2);
  if (p.startsWith('b/')) return p.slice(2);
  return p;
}

/** --- / +++ 行的路径：R5 还原、去一个 a/ b/ 前缀，/dev/null 记为 null。 */
function dashPath(token: string): string | null {
  const stripped = stripAB(decodeToken(token));
  return stripped === '/dev/null' ? null : stripped;
}

/** R4：没有 ---、+++、rename 行时，从 diff --git 行的余下部分取路径。 */
function parseGitPaths(remainder: string): { old: string | null; new: string | null } {
  if (remainder.startsWith('"')) {
    const first = parseQuoted(remainder, 0);
    let j = first.end;
    while (j < remainder.length && (remainder[j] === ' ' || remainder[j] === '\t')) j += 1;
    let second: string | null = null;
    if (j < remainder.length && remainder[j] === '"') second = parseQuoted(remainder, j).value;
    return { old: stripAB(first.value), new: second == null ? null : stripAB(second) };
  }
  const len = remainder.length;
  const mid = len >> 1;
  if (remainder[mid] === ' ') {
    const left = stripAB(remainder.slice(0, mid));
    const right = stripAB(remainder.slice(mid + 1));
    if (left === right) return { old: left, new: right };
  }
  const idx = remainder.indexOf(' b/');
  if (idx >= 0) return { old: stripAB(remainder.slice(0, idx)), new: remainder.slice(idx + 3) };
  const sp = remainder.indexOf(' ');
  if (sp >= 0) return { old: stripAB(remainder.slice(0, sp)), new: stripAB(remainder.slice(sp + 1)) };
  const only = stripAB(remainder);
  return { old: only, new: only };
}

function countKind(hunks: DiffHunk[], kind: 'add' | 'del'): number {
  let n = 0;
  for (const h of hunks) for (const l of h.lines) if (l.kind === kind) n += 1;
  return n;
}

function computeStatus(f: WorkFile): DiffStatus {
  if (f.newFileMode || f.oldPath === null) return 'added';
  if (f.deletedFileMode || f.newPath === null) return 'deleted';
  if (f.renameFrom !== null || f.renameTo !== null || (f.oldPath !== null && f.newPath !== null && f.oldPath !== f.newPath)) {
    return 'renamed';
  }
  return 'modified';
}

/** 解析一份 git 补丁文本，返回文件列表（R1–R10）。 */
export function parseDiff(patch: string): DiffFile[] {
  const lines = splitLines(patch);
  const files: DiffFile[] = [];
  let file: WorkFile | null = null;
  let hunk: DiffHunk | null = null;
  let oldRem = 0;
  let newRem = 0;
  let oldNo = 0;
  let newNo = 0;

  const finalize = () => {
    if (file == null) return;
    files.push({
      oldPath: file.oldPath,
      newPath: file.newPath,
      status: computeStatus(file),
      binary: file.binary,
      hunks: file.hunks,
      additions: file.binary ? 0 : countKind(file.hunks, 'add'),
      deletions: file.binary ? 0 : countKind(file.hunks, 'del'),
    });
    file = null;
    hunk = null;
  };

  const startFile = (gitLine: string) => {
    finalize();
    const paths = parseGitPaths(gitLine.slice(DIFF_GIT.length));
    file = {
      oldPath: paths.old,
      newPath: paths.new,
      newFileMode: false,
      deletedFileMode: false,
      renameFrom: null,
      renameTo: null,
      binary: false,
      skipBinary: false,
      hunks: [],
    };
    hunk = null;
  };

  const startHunk = (line: string, m: RegExpExecArray) => {
    hunk = {
      header: line,
      oldStart: parseInt(m[1], 10),
      oldLines: m[2] !== undefined ? parseInt(m[2], 10) : 1,
      newStart: parseInt(m[3], 10),
      newLines: m[4] !== undefined ? parseInt(m[4], 10) : 1,
      lines: [],
    };
    file!.hunks.push(hunk);
    oldRem = hunk.oldLines;
    newRem = hunk.newLines;
    oldNo = hunk.oldStart;
    newNo = hunk.newStart;
  };

  const markNoNewline = () => {
    if (hunk && hunk.lines.length > 0) hunk.lines[hunk.lines.length - 1].noNewline = true;
  };

  const handleHeader = (line: string) => {
    if (line.startsWith('GIT binary patch')) {
      file!.binary = true;
      file!.skipBinary = true;
      return;
    }
    if (line.startsWith('Binary files') && line.endsWith('differ')) {
      file!.binary = true;
      return;
    }
    if (line.startsWith('new file mode')) {
      file!.newFileMode = true;
      return;
    }
    if (line.startsWith('deleted file mode')) {
      file!.deletedFileMode = true;
      return;
    }
    if (line.startsWith('rename from ')) {
      file!.renameFrom = decodeToken(line.slice('rename from '.length));
      file!.oldPath = file!.renameFrom;
      return;
    }
    if (line.startsWith('rename to ')) {
      file!.renameTo = decodeToken(line.slice('rename to '.length));
      file!.newPath = file!.renameTo;
      return;
    }
    if (line.startsWith('--- ')) {
      file!.oldPath = dashPath(line.slice(4));
      return;
    }
    if (line.startsWith('+++ ')) {
      file!.newPath = dashPath(line.slice(4));
      return;
    }
    const hm = HUNK_RE.exec(line);
    if (hm) startHunk(line, hm);
  };

  for (const line of lines) {
    if (line.startsWith(DIFF_GIT)) {
      startFile(line);
      continue;
    }
    const f = file as WorkFile | null;
    if (f == null || f.skipBinary) continue;
    const h = hunk as DiffHunk | null;
    const active = h != null && (oldRem > 0 || newRem > 0);
    if (h != null && active) {
      if (line.startsWith('\\')) {
        markNoNewline();
        continue;
      }
      if (line === '') {
        h.lines.push({ kind: 'context', text: '', oldNo: oldNo++, newNo: newNo++, noNewline: false });
        oldRem -= 1;
        newRem -= 1;
        continue;
      }
      const c = line[0];
      if (c === ' ') {
        h.lines.push({ kind: 'context', text: line.slice(1), oldNo: oldNo++, newNo: newNo++, noNewline: false });
        oldRem -= 1;
        newRem -= 1;
        continue;
      }
      if (c === '+') {
        h.lines.push({ kind: 'add', text: line.slice(1), oldNo: null, newNo: newNo++, noNewline: false });
        newRem -= 1;
        continue;
      }
      if (c === '-') {
        h.lines.push({ kind: 'del', text: line.slice(1), oldNo: oldNo++, newNo: null, noNewline: false });
        oldRem -= 1;
        continue;
      }
      // 其余行：片段结束，按文件头重新处理这一行。
      hunk = null;
      handleHeader(line);
      continue;
    }
    if (h != null) {
      // 行数已用完：反斜杠行照样记给上一行，@@ 开始下一片段，其余忽略。
      if (line.startsWith('\\')) {
        markNoNewline();
        continue;
      }
      const hm = HUNK_RE.exec(line);
      if (hm) startHunk(line, hm);
      continue;
    }
    handleHeader(line);
  }
  finalize();
  return files;
}
