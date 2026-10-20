import { cleanup, render } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { EffortPair } from '../src/components/EffortPair';

afterEach(cleanup);

const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();

function mount(props: { requested?: string | null; effective?: string | readonly string[] | null }) {
  const r = render(<EffortPair {...props} />);
  const root = r.container.querySelector('.tt-effort') as HTMLElement;
  expect(root, '应有根元素 span.tt-effort').not.toBeNull();
  expect(root.tagName).toBe('SPAN');
  return { ...r, root };
}
const warnTag = (root: HTMLElement) => root.querySelector('.tt-tag[data-tone="warning"]');

describe('思考档位 EffortPair', () => {
  it('一致：「要求 high · 生效 high」，data-state=same，没有警告标签与 title', () => {
    const { root } = mount({ requested: 'high', effective: 'high' });
    expect(textOf(root)).toBe('要求 high · 生效 high');
    expect(root.getAttribute('data-state')).toBe('same');
    expect(warnTag(root)).toBeNull();
    expect(root.querySelectorAll('[title]').length).toBe(0);
  });

  it('不同：「要求 max · 生效 high 与要求不同」，data-state=differs，warning 标签带 title，不用金色', () => {
    const { root } = mount({ requested: 'max', effective: 'high' });
    expect(textOf(root)).toBe('要求 max · 生效 high 与要求不同');
    expect(root.getAttribute('data-state')).toBe('differs');
    const tag = warnTag(root) as HTMLElement;
    expect(tag).not.toBeNull();
    expect(textOf(tag)).toBe('与要求不同');
    expect(tag.getAttribute('title')).toBe('内核记下的生效档位与要求不同');
    expect(root.querySelectorAll('.tt-tag--attention, .tt-tag--brand, [data-tone="attention"], [data-tone="brand"]').length).toBe(0);
  });

  it('未知：生效缺失（null、undefined、空数组、空串）→「生效 未知」，不显示成要求的档位', () => {
    for (const eff of [null, undefined, [], '']) {
      const { root, unmount } = mount({ requested: 'high', effective: eff });
      expect(textOf(root), JSON.stringify(eff)).toBe('要求 high · 生效 未知');
      expect(root.getAttribute('data-state'), JSON.stringify(eff)).toBe('unknown');
      expect(warnTag(root)).toBeNull();
      unmount();
    }
    expect(textOf(mount({ requested: 'high' }).root)).toBe('要求 high · 生效 未知');
  });

  it('没有要求（null、undefined、空串）：整格只显示「—」，生效有值也不显示', () => {
    for (const req of [null, undefined, '']) {
      for (const eff of ['high', null, ['a', 'b']]) {
        const { root, unmount } = mount({ requested: req, effective: eff });
        expect(textOf(root), JSON.stringify([req, eff])).toBe('—');
        expect(root.getAttribute('data-state')).toBe('none');
        expect(warnTag(root)).toBeNull();
        unmount();
      }
    }
    expect(textOf(mount({}).root)).toBe('—');
  });

  it('生效有多个：原样列出（顿号连接），任一不同即不一致；都相同算一致', () => {
    const a = mount({ requested: 'max', effective: ['high', 'max'] });
    expect(textOf(a.root)).toBe('要求 max · 生效 high、max 与要求不同');
    expect(a.root.getAttribute('data-state')).toBe('differs');
    expect(warnTag(a.root)).not.toBeNull();
    const b = mount({ requested: 'high', effective: ['high', 'high'] });
    expect(textOf(b.root)).toBe('要求 high · 生效 high、high');
    expect(b.root.getAttribute('data-state')).toBe('same');
    expect(warnTag(b.root)).toBeNull();
  });

  it('逐字相同才算一致：大小写不同算不同；单元素数组与字符串等价', () => {
    const a = mount({ requested: 'High', effective: 'high' });
    expect(textOf(a.root)).toBe('要求 High · 生效 high 与要求不同');
    expect(a.root.getAttribute('data-state')).toBe('differs');
    const b = mount({ requested: 'high', effective: ['high'] });
    expect(textOf(b.root)).toBe('要求 high · 生效 high');
    expect(b.root.getAttribute('data-state')).toBe('same');
  });

  it('「要求」「生效」是标签文字，档位名各自成元素', () => {
    const { root } = mount({ requested: 'high', effective: 'high' });
    const leaves = Array.from(root.querySelectorAll('*')).filter((e) => e.children.length === 0).map((e) => textOf(e));
    expect(leaves).toContain('要求');
    expect(leaves).toContain('生效');
    expect(leaves.filter((t) => t === 'high').length).toBe(2);
  });

  it('不渲染 role=status', () => {
    mount({ requested: 'high', effective: 'high' });
    expect(document.querySelector('[role="status"]')).toBeNull();
  });
});

describe('EffortPair.css 的取值（读 CSS 文本）', () => {
  const css = readFileSync(join(process.cwd(), 'src/components/EffortPair.css'), 'utf8');

  it('根是 inline-flex、居中、可换行、间距 space-1、text-sm；标签 text-3、档位名 mono-sm', () => {
    expect(css).toMatch(/\.tt-effort\s*\{[^}]*display:\s*inline-flex/);
    expect(css).toMatch(/\.tt-effort\s*\{[^}]*align-items:\s*center/);
    expect(css).toMatch(/\.tt-effort\s*\{[^}]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/\.tt-effort\s*\{[^}]*gap:\s*var\(--tt-space-1\)/);
    expect(css).toMatch(/\.tt-effort\s*\{[^}]*font:\s*var\(--tt-text-sm\)/);
    expect(css).toMatch(/\.tt-effort__label\s*\{[^}]*color:\s*var\(--tt-text-3\)/);
    expect(css).toMatch(/\.tt-effort__level\s*\{[^}]*font:\s*var\(--tt-mono-sm\)/);
  });

  it('不用金色令牌，也不写 px 字面量', () => {
    expect(css).not.toMatch(/--tt-gold|--tt-accent/);
    expect(css).not.toMatch(/(?<![\w.#-])(-?\d*\.?\d+)px\b/);
  });
});
