// 文本查看器的「页转行」（UI 文档 7.12）：纯函数，只做拼接、切行、去 ANSI 与分片归属，不碰 DOM。
// text 模式把各页 text 依次接起来再按换行切行；jsonl 模式同一个 n 的分片按到达顺序拼接。
import { stripAnsi } from './ansi';

/** text 模式的一页。 */
export interface ViewerTextPage {
  mode: 'text';
  text: string;
  /** 这一页是同一行的第几片（可选）。 */
  part?: number;
  /** 同一行一共几片（可选）。 */
  parts?: number;
}

/** jsonl 模式里的一行：要么给文字（可分片），要么只给隐藏原因。 */
export type ViewerJsonlLine =
  | { n: number; text: string; part?: number; parts?: number }
  | { n: number; hidden: string };

/** jsonl 模式的一页。 */
export interface ViewerJsonlPage {
  mode: 'jsonl';
  lines: readonly ViewerJsonlLine[];
}

export type ViewerPage = ViewerTextPage | ViewerJsonlPage;

/** 转出来的一行：行号、已拼接并去掉 ANSI 的文字、分片归属或隐藏原因。 */
export interface ViewerLine {
  /** 行号（text 模式按切出顺序从 1 数；jsonl 模式用 n）。 */
  n: number;
  /** 显示与复制用的文字（已去 ANSI、已去末尾回车）。 */
  text: string;
  /** 已加载的最大片号。 */
  part?: number;
  /** 一共几片。 */
  parts?: number;
  /** 服务只给占位的隐藏行：隐藏原因。 */
  hidden?: string;
}

function countNewlines(text: string): number {
  let n = 0;
  for (let i = 0; i < text.length; i += 1) if (text.charCodeAt(i) === 10) n += 1;
  return n;
}

function textPagesToLines(pages: readonly ViewerTextPage[]): ViewerLine[] {
  const parts = new Map<number, { part?: number; parts?: number }>();
  let joined = '';
  for (const page of pages) {
    // 每页开头落在第几行：之前接起来的文本里换行的个数（从 0 数）。
    const at = countNewlines(joined);
    if (page.part != null) parts.set(at, { part: page.part, parts: page.parts });
    joined += page.text;
  }
  const raw = joined.split('\n');
  // 文本以换行结束时，split 出来的末尾空串不算一行。
  if (raw.length > 1 && raw[raw.length - 1] === '') raw.pop();
  return raw.map((line, i) => {
    const meta = parts.get(i);
    return {
      n: i + 1,
      text: stripAnsi(line.replace(/\r$/, '')),
      ...(meta ? { part: meta.part, parts: meta.parts } : {}),
    };
  });
}

function jsonlPagesToLines(pages: readonly ViewerJsonlPage[]): ViewerLine[] {
  const out: ViewerLine[] = [];
  const byN = new Map<number, ViewerLine>();
  for (const page of pages) {
    for (const entry of page.lines) {
      let line = byN.get(entry.n);
      if (!line) {
        line = { n: entry.n, text: '' };
        byN.set(entry.n, line);
        out.push(line);
      }
      if ('hidden' in entry) {
        line.hidden = entry.hidden;
        continue;
      }
      line.text += stripAnsi(entry.text);
      // 记最后一片的 part/parts。
      if (entry.part != null) {
        line.part = entry.part;
        line.parts = entry.parts;
      }
    }
  }
  return out;
}

/** 把各页转成要显示的行（分片已拼接、ANSI 已去）。 */
export function pagesToLines(pages: readonly ViewerPage[]): ViewerLine[] {
  const jsonl: ViewerJsonlPage[] = [];
  const text: ViewerTextPage[] = [];
  for (const page of pages) {
    if (page.mode === 'jsonl') jsonl.push(page);
    else text.push(page);
  }
  if (jsonl.length > 0) return jsonlPagesToLines(jsonl);
  return textPagesToLines(text);
}
