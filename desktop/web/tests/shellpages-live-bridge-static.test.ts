// 执行端静态测试（D01、D10）：window.themisShell / globalThis.themisShell 的读取与 themisShell 的全局声明
// 只出现在 src/shellpages/shellBridge.ts（唯一读取点与唯一声明点）；shellBridge.ts 连注释里都没有四个网络词整词。
// 只判「themisShell 的读取与全局声明」，不判别的文件有没有 declare global（src/live/transport.ts 里有一份给 themisHost 的）。
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(process.cwd(), 'src');
const BRIDGE = 'src/shellpages/shellBridge.ts';

const READ_RE = /(?:window|globalThis)\s*\.\s*themisShell/;
const DECLARE_RE = /declare\s+global/g;
const MEMBER_RE = /\bthemisShell\s*\??\s*:/;
const NETWORK_RE = /(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])/;

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else if (e.name.endsWith('.ts') || e.name.endsWith('.tsx')) out.push(p);
  }
  return out;
}
function stripComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/[^\n]*/gm, '$1');
}
// 剥注释后文本里对 themisShell 的读取与全局声明（与门禁的判据一致）。
function readOrDeclareHits(text: string): string[] {
  const code = stripComments(text);
  const hits: string[] = [];
  if (READ_RE.test(code)) hits.push('读取 window/globalThis.themisShell');
  for (const m of code.matchAll(DECLARE_RE)) {
    const start = m.index ?? 0;
    const end = code.indexOf('}', start + m[0].length);
    const block = code.slice(start + m[0].length, end >= 0 ? end : start + m[0].length + 300);
    if (MEMBER_RE.test(block)) {
      hits.push('themisShell 的全局声明');
      break;
    }
  }
  return hits;
}

describe('D01 themisShell 的唯一读取点与唯一声明点', () => {
  it('读取与全局声明只出现在 shellBridge.ts', () => {
    const offenders: string[] = [];
    for (const f of walk(SRC)) {
      const rel = relative(process.cwd(), f).replace(/\\/g, '/');
      if (rel === BRIDGE) continue;
      for (const hit of readOrDeclareHits(readFileSync(f, 'utf8'))) offenders.push(`${rel}：${hit}`);
    }
    expect(offenders).toEqual([]);
  });

  it('shellBridge.ts 自己就是那一个读取点与声明点', () => {
    const hits = readOrDeclareHits(readFileSync(join(process.cwd(), BRIDGE), 'utf8'));
    expect(hits).toContain('读取 window/globalThis.themisShell');
    expect(hits).toContain('themisShell 的全局声明');
  });

  it('shellBridge.ts 连注释里都没有四个网络词整词', () => {
    const raw = readFileSync(join(process.cwd(), BRIDGE), 'utf8');
    const hits = raw
      .split('\n')
      .flatMap((line, i) => (NETWORK_RE.test(line) ? [`${BRIDGE}:${i + 1}`] : []));
    expect(hits).toEqual([]);
  });
});
