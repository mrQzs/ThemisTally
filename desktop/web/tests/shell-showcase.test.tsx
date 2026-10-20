// 陈列页（合同第 11 条 / D12、P11）：data-showcase 的值与顺序等于目录里 *Showcase.tsx 文件名的排序结果（每次现读目录）；
// BaseShowcase 原样搬、五节原子带 data-demo；ShellShowcase 两节；整页只有一个 role=status；无文字按钮都有 aria-label。
import { cleanup, render } from '@testing-library/react';
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from '../src/App';

beforeEach(() => { location.hash = '#/showcase'; });
afterEach(cleanup);

const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();

describe('陈列页', () => {
  it('data-showcase 的值与顺序等于目录排序结果', () => {
    const files = readdirSync(join(process.cwd(), 'src/showcase'))
      .filter((f) => f.endsWith('Showcase.tsx'))
      .sort()
      .map((f) => f.replace(/\.tsx$/, ''));
    const { container } = render(<App />);
    const got = Array.from(container.querySelectorAll('[data-showcase]')).map((el) => el.getAttribute('data-showcase'));
    expect(got).toEqual(files);
    expect(files).toContain('BaseShowcase');
    expect(files).toContain('FormsShowcase');
    expect(files).toContain('ShellShowcase');
  });

  it('BaseShowcase 五节原子带 data-demo（button/tag/status-tag/card/banner）', () => {
    const { container } = render(<App />);
    for (const name of ['button', 'tag', 'status-tag', 'card', 'banner']) {
      expect(container.querySelector(`[data-demo="${name}"]`), name).not.toBeNull();
    }
  });

  it('ShellShowcase 两节：page-states 与 disabled-action', () => {
    const { container } = render(<App />);
    const states = container.querySelector('[data-demo="page-states"]') as HTMLElement;
    expect(states).not.toBeNull();
    const links = Array.from(states.querySelectorAll('a')).map((a) => a.getAttribute('href'));
    expect(links).toEqual([
      '#/overview?mock=loading',
      '#/overview?mock=data',
      '#/overview?mock=empty',
      '#/overview?mock=error',
      '#/overview?mock=offline',
    ]);
    const disabled = container.querySelector('[data-demo="disabled-action"]') as HTMLElement;
    const buttons = Array.from(disabled.querySelectorAll('button'));
    expect(buttons.length).toBe(4);
    for (const b of buttons) expect((b as HTMLButtonElement).disabled).toBe(true);
  });

  it('整页只有一个 role=status；无文字按钮都有 aria-label；没有主题按钮', () => {
    render(<App />);
    // 轻提示经 MountLayer 挂到 body，用 document 查。
    expect(document.querySelectorAll('[role="status"]').length).toBe(1);
    const bad = Array.from(document.querySelectorAll('button'))
      .filter((b) => textOf(b) === '')
      .filter((b) => !(b.getAttribute('aria-label') || '').trim());
    expect(bad.length).toBe(0);
    const themed = Array.from(document.querySelectorAll('button')).filter((b) => ['亮', '暗', '跟随系统'].includes(textOf(b)));
    expect(themed.length).toBe(0);
  });
});
