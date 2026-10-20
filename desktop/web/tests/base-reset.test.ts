import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// 基础重置特异性（T005 7.4）：base.css 的元素重置一律包进 :where()，特异性降到 0，
// 同特异性下不会盖过组件的单类规则。这里带一个简化特异性计算器与对真实 base.css 的静态核对。

function splitTop(text: string, sep = ','): string[] {
  const parts: string[] = [];
  let buf = '';
  let depth = 0;
  let quote: string | null = null;
  for (const ch of text) {
    if (quote) { buf += ch; if (ch === quote) quote = null; continue; }
    if (ch === '"' || ch === "'") { quote = ch; buf += ch; continue; }
    if (ch === '(' || ch === '[') depth += 1;
    else if (ch === ')' || ch === ']') depth = Math.max(0, depth - 1);
    if (ch === sep && depth === 0) { parts.push(buf.trim()); buf = ''; continue; }
    buf += ch;
  }
  parts.push(buf.trim());
  return parts;
}

// 返回 [a, b, c]；#id 记 a，类/属性/伪类记 b，元素/伪元素记 c；:where() 记 0；:is()/:not()/:has() 取参数最大。
function specificity(selector: string): [number, number, number] {
  let a = 0;
  let b = 0;
  let c = 0;
  let i = 0;
  const n = selector.length;
  const name = () => {
    const m = /-?[A-Za-z_][\w-]*/.exec(selector.slice(i));
    return m ? m[0] : '';
  };
  while (i < n) {
    const ch = selector[i];
    if (ch === '#') { a += 1; i += 1; i += name().length; }
    else if (ch === '.') { b += 1; i += 1; i += name().length; }
    else if (ch === '[') { b += 1; const j = selector.indexOf(']', i); i = (j < 0 ? n : j + 1); }
    else if (ch === ':') {
      if (selector.startsWith('::', i)) { c += 1; i += 2; i += name().length; }
      else {
        i += 1;
        const nm = name();
        i += nm.length;
        if (selector[i] === '(') {
          let depth = 1;
          let j = i + 1;
          for (; j < n && depth > 0; j += 1) {
            if (selector[j] === '(') depth += 1;
            else if (selector[j] === ')') depth -= 1;
          }
          const arg = selector.slice(i + 1, j - 1);
          i = j;
          if (nm === 'where') { /* 记 0 */ }
          else if (['is', 'not', 'has', 'matches'].includes(nm)) {
            const inner = splitTop(arg).filter(Boolean).map((p) => specificity(p.replace(/^[\s>+~]+/, '')));
            const best = inner.reduce((m, v) => (v[0] > m[0] || (v[0] === m[0] && (v[1] > m[1] || (v[1] === m[1] && v[2] > m[2])))) ? v : m, [0, 0, 0]);
            a += best[0]; b += best[1]; c += best[2];
          } else { b += 1; }
        } else { b += 1; }
      }
    } else if (/\s|>|\+|\~|,|\*/.test(ch)) { i += 1; }
    else { const len = name().length; if (len > 0) { c += 1; i += len; } else { i += 1; } }
  }
  return [a, b, c];
}

const RESET_ELEMENTS = ['button', 'input', 'select', 'textarea', 'a', 'table'];

function subject(selector: string): string {
  const tokens: string[] = [];
  let buf = '';
  let depth = 0;
  let quote: string | null = null;
  for (const ch of selector) {
    if (quote) { buf += ch; if (ch === quote) quote = null; continue; }
    if (ch === '"' || ch === "'") { quote = ch; buf += ch; continue; }
    if (ch === '(' || ch === '[') depth += 1;
    else if (ch === ')' || ch === ']') depth = Math.max(0, depth - 1);
    if (depth === 0 && /\s|>|\+|\~/.test(ch)) { if (buf) { tokens.push(buf); buf = ''; } continue; }
    buf += ch;
  }
  if (buf) tokens.push(buf);
  return tokens[tokens.length - 1] ?? '';
}

function subjectElements(selector: string): Set<string> {
  const flat = subject(selector).replace(/\[[^\]]*\]/g, '');
  const found = new Set<string>();
  for (const m of flat.matchAll(/(?<![\w\-.#:\\])([A-Za-z][\w-]*)/g)) {
    if (RESET_ELEMENTS.includes(m[1])) found.add(m[1]);
  }
  return found;
}

const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '');

function rules(css: string): Array<{ selector: string; body: string }> {
  const out: Array<{ selector: string; body: string }> = [];
  const text = stripComments(css);
  let i = 0;
  while (i < text.length) {
    const j = text.indexOf('{', i);
    if (j < 0) break;
    const prelude = text.slice(i, j).trim();
    let depth = 1;
    let k = j + 1;
    for (; k < text.length && depth > 0; k += 1) {
      if (text[k] === '{') depth += 1;
      else if (text[k] === '}') depth -= 1;
    }
    const body = text.slice(j + 1, k - 1);
    if (!prelude.startsWith('@')) out.push({ selector: prelude.replace(/\s+/g, ' '), body });
    i = k;
  }
  return out;
}

describe('base.css 基础重置特异性', () => {
  it('自检样本：.tt-app button 为 (0,1,1)，:where 包裹后为 0', () => {
    expect(specificity('.tt-app button')).toEqual([0, 1, 1]);
    expect(specificity(':where(.tt-app) :where(button, input, select, textarea)')).toEqual([0, 0, 0]);
    expect(specificity(':where(.tt-app) :where(input)::placeholder')).toEqual([0, 0, 1]);
    expect(specificity('.tt-icon-btn:hover:not(:disabled)')).toEqual([0, 3, 0]);
  });

  it('base.css 里主体是元素重置且不含 :focus-visible 的规则，特异性都低于 (0,1,0)', () => {
    const base = read('src/styles/base.css');
    const offenders: string[] = [];
    for (const { selector } of rules(base)) {
      for (const item of splitTop(selector)) {
        if (item.includes(':focus-visible')) continue;
        if (subjectElements(item).size === 0) continue;
        const [a, b, c] = specificity(item);
        if (a > 0 || b >= 1) offenders.push(`${item} = (${a},${b},${c})`);
      }
    }
    expect(offenders, '元素重置应包进 :where()').toEqual([]);
  });

  it('仍有一条同时声明 font/color: inherit、margin: 0 并覆盖四种元素的规则', () => {
    const base = read('src/styles/base.css');
    const core = rules(base).some(({ selector, body }) => {
      const els = new Set<string>();
      for (const item of splitTop(selector)) {
        if (!item.includes(':focus-visible')) subjectElements(item).forEach((e) => els.add(e));
      }
      const low = body.toLowerCase();
      return ['button', 'input', 'select', 'textarea'].every((e) => els.has(e))
        && /font:\s*inherit/.test(low) && /color:\s*inherit/.test(low) && /margin:\s*0/.test(low);
    });
    expect(core).toBe(true);
  });

  it('组件单类规则压得过 base 的重置（交叉核对）', () => {
    const base = read('src/styles/base.css');
    const resetSpec = Math.max(
      ...rules(base).flatMap(({ selector }) =>
        splitTop(selector)
          .filter((item) => !item.includes(':focus-visible') && subjectElements(item).size > 0)
          .map((item) => specificity(item)[1]),
      ),
    );
    expect(resetSpec).toBe(0);
    expect(specificity('.tt-btn--primary')[1]).toBeGreaterThan(resetSpec);
  });
});
