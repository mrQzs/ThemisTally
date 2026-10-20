// 安全 Markdown 的解析（UI 文档 7.12、合同第 9 条）：纯函数，不引入 React，输出纯数据块节点与行内节点。
// 不支持的语法（引用块、分隔线、Setext 标题、缩进代码块、图片、HTML、自动链接、删除线、脚注、任务列表、
// 带标题的链接、引用式链接、列表项里除段落与子列表以外的块）一律当文字。
// 性能：行内扫描预先算好定界符位置，不用嵌套量词；256 KiB 的病态输入也能在秒级返回。

export type MdAlign = 'left' | 'right' | 'center' | null;

export type MdInline =
  | { type: 'text'; value: string }
  | { type: 'code'; value: string }
  | { type: 'strong'; children: MdInline[] }
  | { type: 'em'; children: MdInline[] }
  | { type: 'link'; children: MdInline[]; url: string };

export interface MdHeading { type: 'heading'; level: number; inlines: MdInline[] }
export interface MdParagraph { type: 'paragraph'; inlines: MdInline[] }
export interface MdCodeBlock { type: 'code'; text: string }
export interface MdListItem { inlines: MdInline[]; children: MdBlock[] }
export interface MdList { type: 'list'; ordered: boolean; start: number | null; items: MdListItem[] }
export interface MdCell { inlines: MdInline[]; align: MdAlign }
export interface MdTable { type: 'table'; header: MdCell[]; rows: MdCell[][]; aligns: MdAlign[] }

export type MdBlock = MdHeading | MdParagraph | MdCodeBlock | MdList | MdTable;

// ---------------------------------------------------------------------------
// 行首形态
// ---------------------------------------------------------------------------

const FENCE_RE = /^ {0,3}(`{3,}|~{3,})(.*)$/;
const ATX_RE = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$/;
const ALIGN_ROW_RE = /^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$/;
const ITEM_RE = /^( *)([-*+]|\d{1,9}[.)])([ \t]+.*|[ \t]*)$/;
const ASCII_PUNCT_RE = /[!-/:-@[-`{-~]/;
const URL_RE = /^https?:\/\/[^\s]+$/i;
const WORDISH_RE = /[\p{L}\p{N}]/u;

const MAX_LIST_DEPTH = 8;

function expandLeadingTabs(line: string): string {
  let i = 0;
  while (i < line.length && line.charCodeAt(i) === 9) i += 1;
  return ' '.repeat(4 * i) + line.slice(i);
}

function isBlank(line: string): boolean {
  return line.trim() === '';
}

function indentOf(line: string): number {
  let i = 0;
  while (i < line.length && line[i] === ' ') i += 1;
  return i;
}

interface ItemMatch { indent: number; marker: string; contentCol: number; content: string; ordered: boolean; start: number | null }

function matchItem(line: string): ItemMatch | null {
  const m = ITEM_RE.exec(line);
  if (!m) return null;
  const indent = m[1].length;
  const marker = m[2];
  const rest = m[3].replace(/^[ \t]+/, '');
  const spaces = m[3].length - m[3].replace(/^[ \t]+/, '').length;
  const ordered = marker >= '0' && marker <= '9';
  return {
    indent,
    marker,
    contentCol: indent + marker.length + Math.min(spaces, 4),
    content: rest,
    ordered,
    start: ordered ? Number(marker.slice(0, -1)) : null,
  };
}

function fenceInfo(line: string): { char: string; len: number; info: string } | null {
  const m = FENCE_RE.exec(line);
  if (!m) return null;
  return { char: m[1][0], len: m[1].length, info: m[2] };
}

function atxLevel(line: string): { level: number; text: string } | null {
  const m = ATX_RE.exec(line);
  if (!m) return null;
  const text = (m[2] ?? '').replace(/^[ \t]+/, '').replace(/[ \t]+#+[ \t]*$/, '');
  return { level: m[1].length, text };
}

function hasUnescapedPipe(line: string): boolean {
  for (let i = 0; i < line.length; i += 1) {
    if (line[i] === '\\') { i += 1; continue; }
    if (line[i] === '|') return true;
  }
  return false;
}

function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|') && !s.endsWith('\\|')) s = s.slice(0, -1);
  const cells: string[] = [];
  let cur = '';
  for (let i = 0; i < s.length; i += 1) {
    const ch = s[i];
    if (ch === '\\' && s[i + 1] === '|') { cur += '\\|'; i += 1; continue; }
    if (ch === '|') { cells.push(cur); cur = ''; continue; }
    cur += ch;
  }
  cells.push(cur);
  return cells.map((c) => c.trim());
}

function alignOf(cell: string): MdAlign {
  const c = cell.trim();
  if (/^:-+:$/.test(c)) return 'center';
  if (/^:-+$/.test(c)) return 'left';
  if (/^-+:$/.test(c)) return 'right';
  return null;
}

/** 这一行是不是表格开头（表头有未转义竖线，下一行是对齐行且格数相同）。 */
function tableStart(lines: string[], i: number): boolean {
  if (!hasUnescapedPipe(lines[i])) return false;
  const next = lines[i + 1];
  if (next === undefined || !ALIGN_ROW_RE.test(next)) return false;
  return splitRow(next).length === splitRow(lines[i]).length;
}

// ---------------------------------------------------------------------------
// 行内
// ---------------------------------------------------------------------------

function isSpace(ch: string | undefined): boolean {
  return ch === undefined || /\s/.test(ch);
}

function findBacktickRun(src: string, from: number, run: number): number {
  let i = from;
  while (i < src.length) {
    if (src[i] !== '`') { i += 1; continue; }
    let j = i;
    while (j < src.length && src[j] === '`') j += 1;
    if (j - i === run) return i;
    i = j;
  }
  return -1;
}

/** 每个位置后面（含自己）最近的 ]：链接判定用，避免在每个 [ 处回头扫全文。 */
function nextCloseBrackets(src: string): Int32Array {
  const out = new Int32Array(src.length + 1);
  out[src.length] = -1;
  for (let k = src.length - 1; k >= 0; k -= 1) out[k] = src[k] === ']' ? k : out[k + 1];
  return out;
}

function isSpaceChar(ch: string): boolean {
  return ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r' || ch === '\f' || ch === '\v';
}

/** 行内解析：从左到右扫；转义、代码段、链接、粗体、斜体，其余都是文字。 */
export function parseInlines(src: string): MdInline[] {
  const out: MdInline[] = [];
  const closeAt = src.indexOf('[') >= 0 ? nextCloseBrackets(src) : null;
  let pending = '';
  const flush = () => {
    if (pending !== '') { out.push({ type: 'text', value: pending }); pending = ''; }
  };
  let i = 0;
  const n = src.length;
  // 缓存 src[i] 起的同字符连续长度：只有「定界符配不上、往前跳 delim 个字符」这条热路径会复用，
  // 避免一整段同一个字符时每次重数长度（那会是平方时间）。
  let runCache = 0;
  while (i < n) {
    const ch = src[i];
    if (ch === '\\' && i + 1 < n) {
      const next = src[i + 1];
      if (ASCII_PUNCT_RE.test(next)) { pending += next; i += 2; continue; }
      pending += ch;
      i += 1;
      runCache = 0;
      continue;
    }
    if (ch === '`') {
      let run = 0;
      while (i + run < n && src[i + run] === '`') run += 1;
      const close = findBacktickRun(src, i + run, run);
      if (close >= 0) {
        let content = src.slice(i + run, close);
        if (content.length > 1 && content[0] === ' ' && content[content.length - 1] === ' ' && content.trim() !== '') {
          content = content.slice(1, -1);
        }
        flush();
        out.push({ type: 'code', value: content });
        i = close + run;
        runCache = 0;
        continue;
      }
      pending += src.slice(i, i + run);
      i += run;
      runCache = 0;
      continue;
    }
    if (ch === '*' || ch === '_') {
      let run = runCache;
      if (run === 0) {
        while (i + run < n && src[i + run] === ch) run += 1;
        runCache = run;
      }
      const delim = run >= 2 ? 2 : 1;
      // 下划线的开头前面不能是字母或数字（蛇形名不变斜体）。
      if (ch === '_' && i > 0 && WORDISH_RE.test(src[i - 1])) {
        pending += src.slice(i, i + delim);
        i += delim;
        runCache = run - delim;
        continue;
      }
      const close = src.indexOf(ch.repeat(delim), i + delim);
      const content = close > i + delim ? src.slice(i + delim, close) : '';
      let ok = content !== '' && !isSpace(src[i + delim]) && !isSpace(src[close - 1]);
      if (ok && ch === '_') {
        const after = src[close + delim];
        if (after !== undefined && WORDISH_RE.test(after)) ok = false;
      }
      if (ok) {
        flush();
        out.push(delim === 2 ? { type: 'strong', children: parseInlines(content) } : { type: 'em', children: parseInlines(content) });
        i = close + delim;
        runCache = 0;
        continue;
      }
      pending += src.slice(i, i + delim);
      i += delim;
      runCache = run - delim;
      continue;
    }
    runCache = 0;
    if (ch === '[') {
      const prev = i > 0 ? src[i - 1] : '';
      const close = closeAt ? closeAt[i + 1] : -1;
      let linked = false;
      if (close >= 0 && prev !== '!' && src[close + 1] === '(') {
        // 网址到下一个括号或空白为止；只有正好以 ) 收尾才算链接写法。
        let k = close + 2;
        while (k < n && !isSpaceChar(src[k]) && src[k] !== '(' && src[k] !== ')') k += 1;
        const text = src.slice(i + 1, close);
        if (k < n && src[k] === ')' && text !== '') {
          flush();
          const inner = parseInlines(text);
          const url = src.slice(close + 2, k);
          if (URL_RE.test(url)) out.push({ type: 'link', children: inner, url });
          else out.push(...inner);
          i = k + 1;
          linked = true;
        }
      }
      if (!linked) {
        pending += ch;
        i += 1;
      }
      runCache = 0;
      continue;
    }
    pending += ch;
    i += 1;
    runCache = 0;
  }
  flush();
  return out;
}

// ---------------------------------------------------------------------------
// 块
// ---------------------------------------------------------------------------

interface Level {
  base: number;
  contentCol: number;
  ordered: boolean;
  start: number | null;
  list: MdList;
  item: MdListItem | null;
  para: string[] | null;
}

function parseList(lines: string[], start: number): { blocks: MdList[]; next: number } {
  const blocks: MdList[] = [];
  const stack: Level[] = [];
  let i = start;

  const closePara = (level: Level) => {
    const para = level.para;
    level.para = null;
    if (!para || para.length === 0 || !level.item) return;
    const inlines = parseInlines(para.join('\n'));
    if (level.item.inlines.length === 0 && level.item.children.length === 0) level.item.inlines = inlines;
    else level.item.children.push({ type: 'paragraph', inlines });
  };
  const closeAllParas = () => { for (const level of stack) closePara(level); };

  const newLevel = (m: ItemMatch) => {
    const list: MdList = {
      type: 'list',
      ordered: m.ordered,
      start: m.ordered && m.start !== 1 ? m.start : null,
      items: [],
    };
    if (stack.length === 0) blocks.push(list);
    else stack[stack.length - 1].item!.children.push(list);
    const level: Level = { base: m.indent, contentCol: m.contentCol, ordered: m.ordered, start: m.start, list, item: null, para: null };
    stack.push(level);
    return level;
  };
  const addItem = (level: Level, content: string) => {
    const item: MdListItem = { inlines: [], children: [] };
    level.list.items.push(item);
    level.item = item;
    level.para = [content];
  };

  while (i < lines.length) {
    const line = lines[i];
    if (isBlank(line)) {
      let j = i;
      while (j < lines.length && isBlank(lines[j])) j += 1;
      if (j >= lines.length) break;
      const top = stack[stack.length - 1];
      if (!top) break;
      const nxt = lines[j];
      const ind = indentOf(nxt);
      const again = matchItem(nxt);
      // 空行之后：列表项（且缩进不小于最外层那一切的起始列）或缩进够的行，列表继续；否则结束。
      const keep = again ? ind >= stack[0].base : ind >= top.contentCol;
      if (!keep) break;
      closeAllParas();
      i = j;
      continue;
    }
    const m = matchItem(line);
    if (m) {
      while (stack.length > 0 && m.indent < stack[stack.length - 1].base) {
        closePara(stack[stack.length - 1]);
        stack.pop();
      }
      if (stack.length === 0) {
        const level = newLevel(m);
        addItem(level, m.content);
      } else {
        const top = stack[stack.length - 1];
        if (m.indent >= top.contentCol) {
          if (stack.length < MAX_LIST_DEPTH) {
            closePara(top);
            const level = newLevel(m);
            addItem(level, m.content);
          } else {
            // 超过 8 层：当作第 8 层的兄弟。
            closePara(top);
            addItem(top, m.content);
          }
        } else if (top.ordered !== m.ordered) {
          // 同层有序、无序换了：另起一个列表。
          closePara(top);
          stack.pop();
          const level = newLevel(m);
          addItem(level, m.content);
        } else {
          closePara(top);
          addItem(top, m.content);
        }
      }
      i += 1;
      continue;
    }
    const top = stack[stack.length - 1];
    if (!top) break;
    if (fenceInfo(line) || atxLevel(line)) break;
    const ind = indentOf(line);
    if (top.item && ind >= top.contentCol) {
      if (top.para === null) top.para = [];
      top.para.push(line.slice(top.contentCol));
      i += 1;
      continue;
    }
    // 不缩进的惰性续行接到当前项的段落里。
    if (top.para === null) break;
    top.para.push(line);
    i += 1;
  }
  closeAllParas();
  return { blocks, next: i };
}

function parseBlocks(lines: string[], raws: string[], from: number, to: number): MdBlock[] {
  const out: MdBlock[] = [];
  let i = from;
  while (i < to) {
    const line = lines[i];
    if (isBlank(line)) { i += 1; continue; }
    const fence = fenceInfo(line);
    if (fence && !(fence.char === '`' && fence.info.indexOf('`') >= 0)) {
      let j = i + 1;
      let end = to;
      while (j < to) {
        const close = fenceInfo(lines[j]);
        if (close && close.char === fence.char && close.len >= fence.len && close.info.trim() === '') { end = j; break; }
        j += 1;
      }
      out.push({ type: 'code', text: raws.slice(i + 1, end).join('\n') });
      i = end + 1;
      continue;
    }
    const atx = atxLevel(line);
    if (atx) {
      out.push({ type: 'heading', level: atx.level, inlines: parseInlines(atx.text) });
      i += 1;
      continue;
    }
    if (tableStart(lines, i)) {
      const headerCells = splitRow(lines[i]);
      const aligns = splitRow(lines[i + 1]).map(alignOf);
      const header = headerCells.map((text, k) => ({ inlines: parseInlines(text), align: aligns[k] ?? null }));
      const rows: MdCell[][] = [];
      let j = i + 2;
      while (j < to && !isBlank(lines[j]) && hasUnescapedPipe(lines[j])) {
        const cells = splitRow(lines[j]);
        const row: MdCell[] = [];
        for (let k = 0; k < headerCells.length; k += 1) {
          row.push({ inlines: parseInlines(cells[k] ?? ''), align: aligns[k] ?? null });
        }
        rows.push(row);
        j += 1;
      }
      out.push({ type: 'table', header, rows, aligns });
      i = j;
      continue;
    }
    // 行首 4 个空格以上不是列表项（本片不支持缩进代码块，当段落文字）。
    const item = matchItem(line);
    if (item && item.indent <= 3) {
      const list = parseList(lines, i);
      out.push(...list.blocks);
      i = list.next;
      continue;
    }
    // 段落：连续非空行，遇到空行或能打断段落的行就结束。
    const para: string[] = [];
    while (i < to && !isBlank(lines[i])) {
      const cur = lines[i];
      if (para.length > 0 && (fenceInfo(cur) || atxLevel(cur) || (matchItem(cur)?.indent ?? 4) <= 3 || tableStart(lines, i))) break;
      para.push(cur.trim());
      i += 1;
    }
    out.push({ type: 'paragraph', inlines: parseInlines(para.join('\n')) });
  }
  return out;
}

/** 解析 Markdown 源码，输出纯数据块节点（渲染与安全策略由组件负责）。 */
export function parseMarkdown(source: string): MdBlock[] {
  const text = source.replace(/\r\n?/g, '\n');
  const rawLines = text.split('\n');
  const lines = rawLines.map(expandLeadingTabs);
  return parseBlocks(lines, rawLines, 0, lines.length);
}
