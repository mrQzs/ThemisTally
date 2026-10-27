// difflib.SequenceMatcher（Python 3.12，isjunk=None）：mutate --check-anchors 的“最相近的行”、相似度与第一处不同
// （迁移第 ④b5a 片），hub 把这些行原样转进信里，所以逐行为照搬。元素是码点（Python 的 str 下标）。
// autojunk：b 有 200 个元素以上时，出现超过 n//100+1 次的元素算 popular，不进 b2j（不能作为匹配的起点），但两头扩展时照样
// 可以跨过它们（isjunk 为 None，bjunk 是空的；吸收 junk 的那两个循环因此不会执行）。

export type OpcodeTag = "replace" | "delete" | "insert" | "equal";
export type Opcode = readonly [tag: OpcodeTag, i1: number, i2: number, j1: number, j2: number];
export type Match = readonly [i: number, j: number, size: number];

export class SequenceMatcher {
  private readonly a: string[];
  private readonly b: string[];
  private readonly b2j = new Map<string, number[]>();
  private matchingBlocks: Match[] | null = null;

  constructor(a: string, b: string, autojunk = true) {
    this.a = Array.from(a);
    this.b = Array.from(b);
    this.b.forEach((element, index) => {
      const indices = this.b2j.get(element);
      if (indices) indices.push(index);
      else this.b2j.set(element, [index]);
    });
    const n = this.b.length;
    if (autojunk && n >= 200) {
      const ntest = Math.floor(n / 100) + 1;
      const popular = [...this.b2j].filter(([, indices]) => indices.length > ntest).map(([element]) => element);
      for (const element of popular) this.b2j.delete(element);
    }
  }

  /** find_longest_match：a[alo:ahi] 与 b[blo:bhi] 里最长的相同块，并列时取 a 里最靠前、再取 b 里最靠前的。 */
  findLongestMatch(alo: number, ahi: number, blo: number, bhi: number): Match {
    const { a, b, b2j } = this;
    let besti = alo;
    let bestj = blo;
    let bestsize = 0;
    let j2len = new Map<number, number>();
    for (let i = alo; i < ahi; i += 1) {
      const next = new Map<number, number>();
      for (const j of b2j.get(a[i] as string) ?? []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) ?? 0) + 1;
        next.set(j, k);
        if (k > bestsize) {
          besti = i - k + 1;
          bestj = j - k + 1;
          bestsize = k;
        }
      }
      j2len = next;
    }
    while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
      besti -= 1;
      bestj -= 1;
      bestsize += 1;
    }
    while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) bestsize += 1;
    return [besti, bestj, bestsize];
  }

  /** get_matching_blocks：按栈序（后进先出）递归找块，排序后合并相邻的，末尾补 (len(a), len(b), 0)。 */
  getMatchingBlocks(): Match[] {
    if (this.matchingBlocks !== null) return this.matchingBlocks;
    const la = this.a.length;
    const lb = this.b.length;
    const queue: [number, number, number, number][] = [[0, la, 0, lb]];
    const found: Match[] = [];
    while (queue.length) {
      const [alo, ahi, blo, bhi] = queue.pop() as [number, number, number, number];
      const match = this.findLongestMatch(alo, ahi, blo, bhi);
      const [i, j, k] = match;
      if (!k) continue;
      found.push(match);
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
    found.sort((x, y) => x[0] - y[0] || x[1] - y[1] || x[2] - y[2]);
    const blocks: Match[] = [];
    let [i1, j1, k1] = [0, 0, 0];
    for (const [i2, j2, k2] of found) {
      if (i1 + k1 === i2 && j1 + k1 === j2) {
        k1 += k2;
      } else {
        if (k1) blocks.push([i1, j1, k1]);
        [i1, j1, k1] = [i2, j2, k2];
      }
    }
    if (k1) blocks.push([i1, j1, k1]);
    blocks.push([la, lb, 0]);
    this.matchingBlocks = blocks;
    return blocks;
  }

  getOpcodes(): Opcode[] {
    let i = 0;
    let j = 0;
    const answer: Opcode[] = [];
    for (const [ai, bj, size] of this.getMatchingBlocks()) {
      const tag: OpcodeTag | "" = i < ai && j < bj ? "replace" : i < ai ? "delete" : j < bj ? "insert" : "";
      if (tag) answer.push([tag, i, ai, j, bj]);
      i = ai + size;
      j = bj + size;
      if (size) answer.push(["equal", ai, i, bj, j]);
    }
    return answer;
  }

  /** ratio：2·M / T，两边都空时为 1.0。 */
  ratio(): number {
    const matches = this.getMatchingBlocks().reduce((sum, [, , size]) => sum + size, 0);
    const length = this.a.length + this.b.length;
    return length ? (2.0 * matches) / length : 1.0;
  }
}
