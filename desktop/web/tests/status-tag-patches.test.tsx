import { cleanup, render } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { StatusTag } from '../src/components/StatusTag';

afterEach(cleanup);

function mountTag(state: string, size?: 'md' | 'sm') {
  const r = render(<StatusTag state={state} size={size} />);
  return { ...r, tag: r.container.firstElementChild as HTMLElement };
}

describe('状态补丁', () => {
  it('ACCEPTED_WITH_EXCEPTION 中号、小号都恰一个圆点：aria-hidden、无文字、非 svg、在第一个 svg 之后、包在 tt-status__icon', () => {
    for (const size of ['md', 'sm'] as const) {
      const { tag, unmount } = mountTag('ACCEPTED_WITH_EXCEPTION', size);
      const dots = tag.querySelectorAll('.tt-status__dot');
      expect(dots.length).toBe(1);
      expect(dots[0].getAttribute('aria-hidden')).toBe('true');
      expect((dots[0].textContent || '').trim()).toBe('');
      expect(dots[0].tagName.toLowerCase()).not.toBe('svg');
      const svg = tag.querySelector('svg')!;
      expect(svg.compareDocumentPosition(dots[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      const wrap = tag.querySelector('.tt-status__icon')!;
      expect(wrap.contains(svg)).toBe(true);
      expect(wrap.contains(dots[0])).toBe(true);
      expect((tag.textContent || '').trim()).toBe('带豁免通过');
      unmount();
    }
  });

  it('其余状态与未知状态码没有圆点，每个标签恰一个 svg', () => {
    for (const code of ['PASS', 'RUNNING', 'INFRA_FAILURE', 'REVISE', 'FUTURE_STATE', 'constructor']) {
      const { tag, unmount } = mountTag(code);
      expect(tag.querySelectorAll('.tt-status__dot').length).toBe(0);
      expect(tag.querySelectorAll('svg').length).toBe(1);
      unmount();
    }
  });

  it('INFRA_FAILURE 用 server-crash 路径（含 m13 6-4 6h6l-4 6），文字「基础设施故障」', () => {
    const { tag } = mountTag('INFRA_FAILURE');
    const paths = Array.from(tag.querySelectorAll('svg path')).map((p) => p.getAttribute('d'));
    expect(paths).toContain('m13 6-4 6h6l-4 6');
    expect((tag.textContent || '').trim()).toBe('基础设施故障');
  });

  it('圆点 CSS 用令牌（读 CSS 文本）', () => {
    const css = readFileSync(join(process.cwd(), 'src/components/StatusTag.css'), 'utf8');
    expect(css).toMatch(/\.tt-status__dot\s*\{[^}]*background:\s*var\(--tt-tone-warning-fg\)/);
    expect(css).toMatch(/box-shadow:[^;]*var\(--tt-tone-success-bg\)/);
    expect(css).toMatch(/border-radius:\s*var\(--tt-radius-full\)/);
  });
});
