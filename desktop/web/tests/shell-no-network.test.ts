// 不连服务的静态检查（合同第 12 条 / D08）：递归读 src 下全部文件（不论扩展名），按整词找
// fetch、XMLHttpRequest、EventSource、WebSocket（前后不是字母、数字、下划线或美元符；注释与字符串都算），
// 找到就失败并报 路径:行号。src/live/ 下的文件放行——那是接真实服务的传输层，本片只有它可以用浏览器
// 网络接口（别处一个都不许有）。自检样本：报 window.fetch(、new WebSocket(、globalThis 方括号取 fetch；
// 不报 prefetchAll、fetchedAt。
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

// npm test 的 cwd 是 desktop/web（门禁与自检都在这里跑）。
const SRC = join(process.cwd(), 'src');
const FORBIDDEN = ['fetch', 'XMLHttpRequest', 'EventSource', 'WebSocket'];
const RE = new RegExp(`(?<![A-Za-z0-9_$])(?:${FORBIDDEN.join('|')})(?![A-Za-z0-9_$])`);
// 传输层所在的目录：只有它放行。
const LIVE_DIR = 'live/';

// 扫描规则本身（相对 src 的路径 + 一行文本）：live/ 下放行，别处照旧照报。
function reports(rel: string, line: string): boolean {
  return !rel.startsWith(LIVE_DIR) && RE.test(line);
}

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue;
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

describe('不连服务的静态检查', () => {
  it('自检样本：报得准、不误报', () => {
    expect(RE.test('window.fetch(')).toBe(true);
    expect(RE.test('new WebSocket(')).toBe(true);
    expect(RE.test("globalThis['fetch']")).toBe(true);
    expect(RE.test('new EventSource(url)')).toBe(true);
    expect(RE.test('const x = new XMLHttpRequest()')).toBe(true);
    expect(RE.test('prefetchAll')).toBe(false);
    expect(RE.test('fetchedAt')).toBe(false);
    expect(RE.test('refetch_counter')).toBe(false);
  });

  it('自检样本：同一段带网络词的文本，live/ 下放行、别处照报', () => {
    // 成对样本：规则放行的是传输层，不是把网络词整个放开。
    expect(reports('live/transport.ts', 'await globalThis.fetch(url, { credentials: "same-origin" })')).toBe(false);
    expect(reports('live/connection.ts', 'const es = new EventSource(url)')).toBe(false);
    expect(reports('src/api.ts', 'await globalThis.fetch(url)')).toBe(true);
    expect(reports('src/pages/tasks/tasks-data.ts', 'const ws = new WebSocket(url)')).toBe(true);
  });

  it('src 下（src/live/ 除外）没有任何网络请求词', () => {
    const hits: string[] = [];
    for (const file of walk(SRC)) {
      const rel = relative(SRC, file).split('\\').join('/');
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (reports(rel, line)) hits.push(`${rel}:${i + 1}: ${line.trim()}`);
      });
    }
    expect(hits, `src 里出现网络请求词：\n${hits.join('\n')}`).toEqual([]);
  });
});
