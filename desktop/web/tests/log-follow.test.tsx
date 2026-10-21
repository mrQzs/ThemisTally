import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LogFollow } from '../src/components/LogFollow';

// 日志跟随（合同 §5.3）：假计时器 + 主体打桩 scrollHeight/clientHeight/scrollTop；过滤走 TextViewer 的 filter。
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const ESC = '\u001b';
const BODY_CLASS = 'tt-viewer__body';
let SH = 1000;
let CH = 200;
const TOPS = new WeakMap<object, number>();
const maxTop = () => Math.max(0, SH - CH);
function installScrollStubs() {
  const proto: any = HTMLElement.prototype;
  Object.defineProperty(proto, 'scrollHeight', { configurable: true, get() { return (this as HTMLElement).classList.contains(BODY_CLASS) ? SH : 0; } });
  Object.defineProperty(proto, 'clientHeight', { configurable: true, get() { return (this as HTMLElement).classList.contains(BODY_CLASS) ? CH : 0; } });
  Object.defineProperty(proto, 'scrollTop', {
    configurable: true,
    get() { return TOPS.get(this) ?? 0; },
    set(v: number) { const cap = (this as HTMLElement).classList.contains(BODY_CLASS) ? maxTop() : Infinity; TOPS.set(this, Math.max(0, Math.min(Number(v), cap))); },
  });
}
function removeScrollStubs() {
  const proto: any = HTMLElement.prototype;
  delete proto.scrollHeight;
  delete proto.clientHeight;
  delete proto.scrollTop;
}
beforeEach(() => {
  SH = 1000;
  CH = 200;
  installScrollStubs();
  vi.useFakeTimers();
});
afterEach(() => {
  removeScrollStubs();
});

const pagesOf = (n: number) => Array.from({ length: n }, (_, i) => ({ mode: 'text' as const, text: 'event ' + (i + 1) + '\n' }));
function mountLog(props: Record<string, unknown> = {}) {
  const spies = { onCopy: vi.fn(), onLoadMore: vi.fn(), onReload: vi.fn() };
  let cur: Record<string, unknown> = { title: 'events.jsonl', pages: pagesOf(1), hasMore: false, ...props };
  const el = () => <LogFollow onCopy={spies.onCopy} onLoadMore={spies.onLoadMore} onReload={spies.onReload} {...(cur as any)} />;
  const r = render(el());
  const root = r.container.querySelector('.tt-log') as HTMLElement;
  expect(root).not.toBeNull();
  return {
    ...r,
    root,
    ...spies,
    update: (patch: Record<string, unknown>) => { cur = { ...cur, ...patch }; r.rerender(el()); },
    body: () => root.querySelector('.tt-viewer__body') as HTMLElement,
    status: () => root.querySelector('.tt-log__status') as HTMLElement,
    sw: () => root.querySelector('.tt-log__follow [role="switch"]') as HTMLElement,
    input: () => root.querySelector('.tt-log__filter-input') as HTMLInputElement,
    state: () => (root.querySelector('.tt-log__status') as HTMLElement | null)?.getAttribute('data-follow'),
  };
}
const userScroll = (el: HTMLElement, top: number) => { el.scrollTop = top; fireEvent.scroll(el); };
const advance = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const squash = (s: string | null | undefined) => (s || '').replace(/\s+/g, '');
const REASON = 'attempt 已结束，没有新事件';

describe('LogFollow 结构', () => {
  it('根带 tt-log 与 tt-viewer；主体带 tt-log__body；过滤框与跟随在复制钮之后；底部状态在主体与底栏之间；不设 role/aria-live', () => {
    const m = mountLog({ className: 'extra-y' });
    expect(m.root.classList.contains('tt-viewer')).toBe(true);
    expect(m.root.classList.contains('extra-y')).toBe(true);
    expect(m.root.className.indexOf('tt-log')).toBeLessThan(m.root.className.indexOf('extra-y'));
    const body = m.body();
    expect(body.classList.contains('tt-log__body')).toBe(true);
    expect(body.classList.contains('tt-viewer__body')).toBe(true);
    const filter = m.root.querySelector('label.tt-log__filter') as HTMLElement;
    const icon = filter.querySelector('svg') as SVGElement;
    expect(icon.getAttribute('width')).toBe('14');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    const input = filter.querySelector('input.tt-log__filter-input') as HTMLInputElement;
    expect(input.getAttribute('type')).toBe('text');
    expect(input.getAttribute('aria-label')).toBe('过滤事件');
    expect(input.getAttribute('placeholder')).toBe('按文字包含过滤…');
    const follow = m.root.querySelector('span.tt-log__follow') as HTMLElement;
    expect(textOf(m.sw())).toBe('跟随');
    expect(follow.hasAttribute('title')).toBe(false);
    const head = m.root.querySelector('.tt-viewer__head') as HTMLElement;
    const copy = head.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement;
    expect(copy.compareDocumentPosition(filter) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const status = m.status();
    const foot = m.root.querySelector('.tt-viewer__foot') as HTMLElement;
    expect(body.contains(status)).toBe(false);
    expect(body.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(status.compareDocumentPosition(foot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(status.hasAttribute('role')).toBe(false);
    expect(m.root.querySelectorAll('[aria-live]').length).toBe(0);
    expect(document.querySelector('[role="status"]')).toBeNull();
  });

  it('其余属性透传：复制、[继续加载]、已显示 N 页', () => {
    const m = mountLog({ pages: pagesOf(2), hasMore: true });
    fireEvent.click(m.root.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement);
    expect(m.onCopy).toHaveBeenCalledWith('event 1\nevent 2');
    expect(textOf(m.root.querySelector('.tt-viewer__foot'))).toContain('已显示 2 页');
    fireEvent.click(Array.from(m.root.querySelectorAll('button')).find((b) => textOf(b) === '继续加载') as HTMLElement);
    expect(m.onLoadMore).toHaveBeenCalledTimes(1);
  });

  it('四种状态的文字与 data-follow', () => {
    const m = mountLog();
    expect(m.state()).toBe('following');
    expect(squash(textOf(m.status()))).toBe('正在跟随最新内容');
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    expect(squash(textOf(m.status()))).toBe('已暂停跟随：你在往上看回到底部');
    const icon = m.status().querySelector('svg') as SVGElement;
    expect(icon.getAttribute('width')).toBe('16');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    expect(squash(textOf(m.status()))).toBe('已关闭跟随');
    m.update({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    expect(textOf(m.status())).toBe(REASON);
  });
});

describe('LogFollow 跟随状态机', () => {
  it('挂载与 following 中追加页后滚到底', () => {
    const m = mountLog();
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(1300);
    expect(m.state()).toBe('following');
  });

  it('往上滚且离底超过 40 暂停并计时；暂停中追加页不滚动', () => {
    const m = mountLog();
    const base = vi.getTimerCount();
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    expect(vi.getTimerCount()).toBeGreaterThan(base);
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(500);
    expect(m.state()).toBe('paused');
  });

  it('往上滚但离底不超过 40 不暂停；d=41 才暂停', () => {
    const m = mountLog();
    userScroll(m.body(), 770);
    expect(m.state()).toBe('following');
    userScroll(m.body(), 760);
    expect(m.state()).toBe('following');
    userScroll(m.body(), 759);
    expect(m.state()).toBe('paused');
  });

  it('scrollTop 没变小（内容变长）时即使离底超过 40 也不暂停', () => {
    const a = mountLog();
    SH = 2000;
    fireEvent.scroll(a.body());
    expect(a.state()).toBe('following');
    a.unmount();
    const b = mountLog();
    SH = 1500;
    b.update({ pages: pagesOf(2) });
    expect(b.body().scrollTop).toBe(1300);
    SH = 2500;
    fireEvent.scroll(b.body());
    expect(b.state()).toBe('following');
  });

  it('d 为 40 时 149ms 仍 paused、150ms 恢复并滚到底；d 为 41 时仍 paused', () => {
    const a = mountLog();
    userScroll(a.body(), 500);
    userScroll(a.body(), 760);
    expect(a.state()).toBe('paused');
    advance(149);
    expect(a.state()).toBe('paused');
    expect(a.body().scrollTop).toBe(760);
    advance(1);
    expect(a.state()).toBe('following');
    expect(a.body().scrollTop).toBe(800);
    a.unmount();
    const b = mountLog();
    userScroll(b.body(), 500);
    userScroll(b.body(), 759);
    advance(1000);
    expect(b.state()).toBe('paused');
    expect(b.body().scrollTop).toBe(759);
  });

  it('paused 中每个滚动事件都重新计时', () => {
    const m = mountLog();
    userScroll(m.body(), 500);
    userScroll(m.body(), 760);
    advance(100);
    userScroll(m.body(), 760);
    advance(100);
    expect(m.state()).toBe('paused');
    advance(49);
    expect(m.state()).toBe('paused');
    advance(1);
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
  });

  it('[回到底部] 立即恢复并滚到底、焦点到开关；之后往上滚仍能再暂停', () => {
    const m = mountLog();
    userScroll(m.body(), 500);
    fireEvent.click(Array.from(m.status().querySelectorAll('button')).find((b) => textOf(b) === '回到底部') as HTMLElement);
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
    expect(document.activeElement).toBe(m.sw());
    advance(1000);
    expect(m.state()).toBe('following');
    userScroll(m.body(), 600);
    expect(m.state()).toBe('paused');
  });

  it('开关关→off、开→following；paused 时点开关也是关', () => {
    const m = mountLog();
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(800);
    userScroll(m.body(), 100);
    advance(1000);
    expect(m.state()).toBe('off');
    fireEvent.click(m.sw());
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(1300);
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    userScroll(m.body(), 1260);
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    advance(1000);
    expect(m.state()).toBe('off');
  });

  it('键盘空格切换；defaultFollow=false 挂载为 off 且不滚动', () => {
    const m = mountLog({ defaultFollow: false });
    expect(m.state()).toBe('off');
    expect(m.body().scrollTop).toBe(0);
    fireEvent.keyDown(m.sw(), { key: ' ' });
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
  });

  it('followDisabledReason 非空→disabled：开关 aria-disabled 不可聚焦、title 与底部文字都是原因；变回空→following', () => {
    const m = mountLog({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    expect(textOf(m.status())).toBe(REASON);
    expect(m.root.querySelector('.tt-log__follow')!.getAttribute('title')).toBe(REASON);
    const sw = m.sw();
    expect(sw.getAttribute('aria-disabled')).toBe('true');
    expect(sw.hasAttribute('tabindex')).toBe(false);
    expect(sw.getAttribute('aria-checked')).toBe('false');
    expect(m.body().scrollTop).toBe(0);
    act(() => { sw.focus(); });
    expect(document.activeElement).not.toBe(sw);
    fireEvent.click(sw);
    expect(m.state()).toBe('disabled');
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(0);
    m.update({ followDisabledReason: '' });
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(1300);
    expect(m.root.querySelector('.tt-log__follow')!.hasAttribute('title')).toBe(false);
  });

  it('paused 或 off 时设了原因再清掉，都回到 following', () => {
    const m = mountLog();
    userScroll(m.body(), 500);
    m.update({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    advance(1000);
    expect(m.state()).toBe('disabled');
    m.update({ followDisabledReason: undefined });
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    m.update({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    m.update({ followDisabledReason: '' });
    expect(m.state()).toBe('following');
  });

  it('following 中过滤变化后滚到底；paused 中过滤变化不滚动', () => {
    const m = mountLog({ pages: pagesOf(3) });
    m.body().scrollTop = 100;
    fireEvent.change(m.input(), { target: { value: 'event' } });
    expect(m.input().value).toBe('event');
    expect(m.body().scrollTop).toBe(800);
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    fireEvent.change(m.input(), { target: { value: 'event 2' } });
    expect(m.input().value).toBe('event 2');
    expect(m.body().scrollTop).toBe(500);
  });

  it('只用 setTimeout：计时不堆积；卸载后没有挂起的计时器', () => {
    const m = mountLog();
    const base = vi.getTimerCount();
    userScroll(m.body(), 500);
    const paused = vi.getTimerCount();
    expect(paused).toBeGreaterThan(base);
    for (const top of [510, 520, 530, 540]) userScroll(m.body(), top);
    expect(vi.getTimerCount()).toBeLessThanOrEqual(paused);
    m.unmount();
    expect(vi.getTimerCount()).toBeLessThanOrEqual(base);
    advance(1000);
  });
});

describe('LogFollow 过滤', () => {
  const JPAGES = [
    { mode: 'jsonl' as const, lines: [
      { n: 1, text: 'Hello World' },
      { n: 2, text: 'second LINE' },
      { n: 3, hidden: 'not_json' },
      { n: 4, text: ESC + '[31mred ERROR' + ESC + '[0m here' },
      { n: 5, text: 'part-A ', part: 1, parts: 2 },
    ] },
    { mode: 'jsonl' as const, lines: [{ n: 5, text: 'part-B', part: 2, parts: 2 }, { n: 6, text: 'tail line' }] },
  ];
  function mountFilter(props: Record<string, unknown> = {}) {
    const spies = { onCopy: vi.fn(), onLoadMore: vi.fn() };
    let cur: Record<string, unknown> = { title: 't', pages: JPAGES, hasMore: false, ...props };
    const el = () => <LogFollow onCopy={spies.onCopy} onLoadMore={spies.onLoadMore} {...(cur as any)} />;
    const r = render(el());
    const root = r.container.querySelector('.tt-log') as HTMLElement;
    return {
      ...r, root, ...spies,
      update: (patch: Record<string, unknown>) => { cur = { ...cur, ...patch }; r.rerender(el()); },
      type: (v: string) => fireEvent.change(root.querySelector('.tt-log__filter-input') as HTMLInputElement, { target: { value: v } }),
    };
  }
  const nums = (root: HTMLElement) => Array.from(root.querySelectorAll('.tt-viewer__row')).map((r) => textOf(r.querySelector('.tt-viewer__num')));
  const copied = (m: any) => { const before = m.onCopy.mock.calls.length; fireEvent.click(m.root.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement); return m.onCopy.mock.calls[m.onCopy.mock.calls.length - 1][0]; };

  it('空串不过滤；不分大小写；拼好分片、去 ANSI 后匹配；行号不变', () => {
    const m = mountFilter();
    expect(nums(m.root)).toEqual(['1', '2', '3', '4', '5', '6']);
    const cases: Array<[string, string[]]> = [
      ['hello', ['1']], ['HELLO WORLD', ['1']], ['second line', ['2']], ['red error', ['4']],
      ['a part-b', ['5']], ['line', ['2', '6']], [' ', ['1', '2', '4', '5', '6']],
    ];
    for (const [value, want] of cases) { m.type(value); expect(nums(m.root), value).toEqual(want); }
    m.type('');
    expect(nums(m.root)).toEqual(['1', '2', '3', '4', '5', '6']);
  });

  it('隐藏行在非空过滤下不显示；清空后还原', () => {
    const m = mountFilter();
    expect(textOf(m.root)).toContain('这一行不是合法 JSON，已隐藏');
    m.type(' ');
    expect(m.root.querySelectorAll('.tt-viewer__hidden').length).toBe(0);
    m.type('');
    expect(m.root.querySelectorAll('.tt-viewer__hidden').length).toBe(1);
  });

  it('一行也没有时显示「没有匹配的行」；已显示 N 页不变', () => {
    const m = mountFilter();
    m.type('zzz-no-such');
    expect(nums(m.root)).toEqual([]);
    expect(textOf(m.root.querySelector('.tt-viewer__body'))).toContain('没有匹配的行');
    expect(textOf(m.root.querySelector('.tt-viewer__foot'))).toContain('已显示 2 页');
    m.type('');
    expect(textOf(m.root)).not.toContain('没有匹配的行');
  });

  it('复制只含显示的行；pages 更新后新行按过滤显示', () => {
    const m = mountFilter();
    expect(copied(m)).toBe('Hello World\nsecond LINE\nred ERROR here\npart-A part-B\ntail line');
    m.type('line');
    expect(copied(m)).toBe('second LINE\ntail line');
    m.update({ pages: [...JPAGES, { mode: 'jsonl', lines: [{ n: 7, text: 'Another Line' }, { n: 8, text: 'nothing' }] }] });
    expect(nums(m.root)).toEqual(['2', '6', '7']);
    expect(copied(m)).toBe('second LINE\ntail line\nAnother Line');
    expect(textOf(m.root.querySelector('.tt-viewer__foot'))).toContain('已显示 3 页');
  });

  it('行尾 [继续加载] 跟着那一行：被滤掉时不显示，底栏照常', () => {
    const pages = [{ mode: 'jsonl' as const, lines: [{ n: 1, text: 'alpha' }, { n: 2, text: 'beta start', part: 1, parts: 2 }] }];
    const m = mountFilter({ pages, hasMore: true });
    const split = () => {
      const all = Array.from(m.root.querySelectorAll('button')).filter((b) => textOf(b) === '继续加载');
      const rs = Array.from(m.root.querySelectorAll('.tt-viewer__row'));
      return { inRow: all.filter((b) => rs.some((r) => r.contains(b))), inFoot: all.filter((b) => !rs.some((r) => r.contains(b))) };
    };
    expect(split().inRow.length).toBe(1);
    expect(split().inFoot.length).toBe(1);
    m.type('alpha');
    expect(nums(m.root)).toEqual(['1']);
    expect(split().inRow.length).toBe(0);
    expect(split().inFoot.length).toBe(1);
    m.type('beta');
    expect(nums(m.root)).toEqual(['2']);
    expect(split().inRow.length).toBe(1);
    fireEvent.click(split().inRow[0]);
    expect(m.onLoadMore).toHaveBeenCalledTimes(1);
  });
});
