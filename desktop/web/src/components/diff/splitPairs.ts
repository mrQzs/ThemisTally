// 分屏配对（UI 文档 7.14）：把一个片段的行配成左右两列。纯函数，不碰 DOM、不引入 React。
// context 左右都是这一行；连续的非 context 行算一段，段内第 k 个删配第 k 个增，多出来的一侧为空。
import type { DiffLine } from './parseDiff';

export type SplitRow =
  | { kind: 'context'; line: DiffLine }
  | { kind: 'pair'; left: DiffLine | null; right: DiffLine | null };

/** 输入一个片段的 lines，输出分屏要显示的行；不改输入的行数组。 */
export function splitPairs(lines: readonly DiffLine[]): SplitRow[] {
  const out: SplitRow[] = [];
  let dels: DiffLine[] = [];
  let adds: DiffLine[] = [];

  const flush = () => {
    const n = Math.max(dels.length, adds.length);
    for (let k = 0; k < n; k += 1) {
      out.push({ kind: 'pair', left: k < dels.length ? dels[k] : null, right: k < adds.length ? adds[k] : null });
    }
    dels = [];
    adds = [];
  };

  for (const line of lines) {
    if (line.kind === 'context') {
      flush();
      out.push({ kind: 'context', line });
    } else if (line.kind === 'del') {
      dels.push(line);
    } else {
      adds.push(line);
    }
  }
  flush();
  return out;
}
