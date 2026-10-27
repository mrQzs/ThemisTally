// 变异清单不悄悄过期（第 127 轮）：ts/mutations 下每份清单的每条变异，原文在目标文件里恰好出现 count 次（缺省 1）。
// 代码挪动、改写之后清单没跟上，mutate 跑到那一条只会报出错、不会算抓住，清单却一直看着是全的（2026-10-27 查出 12 条）；
// 这里在平常的测试里就拦下。数法照 pi_dispatch._apply_mutation：CRLF 先归一成 LF，不重叠地数。
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { REPO } from "./harness.ts";

const MUTATIONS = join(REPO, "ts", "mutations");
const CRLF = String.fromCharCode(13, 10);
const LF = String.fromCharCode(10);

interface Mutation {
  readonly name: string;
  readonly file: string;
  readonly old: string;
  readonly count?: number;
}

/** str.count(part)：不重叠；空串照 Python 是码点数加一（不然下面的循环停不下来，themistally-15 复核 127 轮提醒）。 */
function occurrences(text: string, part: string): number {
  if (!part) return Array.from(text).length + 1;
  let count = 0;
  for (let at = text.indexOf(part); at !== -1; at = text.indexOf(part, at + part.length)) count += 1;
  return count;
}

function readOrNull(path: string): string | null {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

describe("变异清单", () => {
  it("每条变异的原文在目标文件里恰好出现 count 次（缺省 1）", () => {
    const stale: string[] = [];
    const names = readdirSync(MUTATIONS).filter((name) => name.endsWith(".json")).sort();
    for (const name of names) {
      const spec = JSON.parse(readFileSync(join(MUTATIONS, name), "utf8")) as { mutations: Mutation[] };
      for (const item of spec.mutations) {
        const text = readOrNull(join(REPO, item.file));
        if (text === null) {
          stale.push(`${name} ${item.name}：${item.file} 不在`);
          continue;
        }
        const found = occurrences(text.split(CRLF).join(LF), item.old.split(CRLF).join(LF));
        if (found !== (item.count ?? 1)) stale.push(`${name} ${item.name}：原文出现 ${found} 次`);
      }
    }
    expect(names.length).toBeGreaterThan(20);
    expect(stale).toEqual([]);
  });
});
