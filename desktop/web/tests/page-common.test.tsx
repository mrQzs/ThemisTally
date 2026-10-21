// 通用组件测试（合同第 9 节）：RelativeTime 四档与边界、title、解析不了、now；ActorTag 五色；Section 结构与 aria。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { RelativeTime } from '../src/components/RelativeTime';
import { ActorTag } from '../src/components/ActorTag';
import { Section } from '../src/pages/readonly1/common-Section';

const NOW = '2026-10-18T03:00:00.000Z';
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(NOW));
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const text = (c: any) => (c.textContent || '').replace(/\s+/g, ' ').trim();
function isoAgo(sec: number): string {
  return new Date(Date.parse(NOW) - sec * 1000).toISOString();
}
function expectedTitle(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}` +
    `（UTC ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}）`
  );
}

describe('RelativeTime', () => {
  it('四档与边界', () => {
    const cases: Array<[number, string]> = [
      [0, '0 秒前'], [59, '59 秒前'], [60, '1 分钟前'], [3599, '59 分钟前'],
      [3600, '1 小时前'], [86399, '23 小时前'], [86400, '1 天前'], [172800, '2 天前'],
    ];
    for (const [sec, want] of cases) {
      const { container } = render(<RelativeTime iso={isoAgo(sec)} />);
      expect(text(container), `${sec} 秒前`).toBe(want);
      cleanup();
    }
  });

  it('渲染 time：dateTime 为原文，title 为本地时间加全角括号 UTC，className 落在 time 上', () => {
    const iso = '2026-10-18T02:02:11Z';
    const { container } = render(<RelativeTime iso={iso} className="x" />);
    const el = container.querySelector('time') as HTMLTimeElement;
    expect(el).not.toBeNull();
    expect(el.getAttribute('datetime')).toBe(iso);
    expect(el.getAttribute('title')).toBe(expectedTitle(iso));
    expect(el.classList.contains('x')).toBe(true);
  });

  it('解析不了原样显示，不带 title 与 dateTime', () => {
    const { container } = render(<RelativeTime iso="not-a-date" />);
    expect(text(container)).toBe('not-a-date');
    const el = (container.querySelector('time') || container.firstElementChild) as Element;
    expect(el.getAttribute('title')).toBeNull();
    expect(el.getAttribute('datetime')).toBeNull();
  });

  it('now 属性按 now 算，缺省按系统时间', () => {
    const later = Date.parse(NOW) + 2 * 3600 * 1000;
    expect(text(render(<RelativeTime iso={isoAgo(30)} now={later} />).container)).toBe('2 小时前');
    cleanup();
    expect(text(render(<RelativeTime iso={isoAgo(30)} />).container)).toBe('30 秒前');
  });
});

describe('ActorTag', () => {
  it('五种色调且等宽', () => {
    const cases: Array<[string, string]> = [
      ['user-ui', 'brand'], ['user', 'neutral'], ['agent:planning_review', 'info'],
      ['undeclared', 'warning'], ['whoever', 'neutral'],
    ];
    for (const [actor, tone] of cases) {
      const { container } = render(<ActorTag actor={actor} />);
      const tag = container.querySelector('.tt-tag') as HTMLElement;
      expect(tag.getAttribute('data-tone'), actor).toBe(tone);
      expect(tag.classList.contains('tt-tag--mono')).toBe(true);
      expect(text(tag)).toBe(actor);
      cleanup();
    }
  });
});

describe('Section', () => {
  it('section 加 aria-labelledby 指 h2，说明、h2 后元素与右侧链接都渲染', () => {
    const { container } = render(
      <Section title="方案" description="一组角色绑定" afterTitle={<span>pill</span>} action={<a href="#/history">查看全部历史</a>}>
        <p>body</p>
      </Section>,
    );
    const sec = container.querySelector('section') as HTMLElement;
    expect(sec).not.toBeNull();
    const id = sec.getAttribute('aria-labelledby') as string;
    const h2 = document.getElementById(id) as HTMLElement;
    expect(h2.tagName).toBe('H2');
    expect(text(h2)).toBe('方案');
    expect(text(sec)).toContain('一组角色绑定');
    expect(text(sec)).toContain('pill');
    expect(sec.querySelector('a')?.textContent).toBe('查看全部历史');
  });
});
