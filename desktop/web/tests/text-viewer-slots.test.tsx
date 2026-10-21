import { cleanup, render, fireEvent } from '@testing-library/react';
import * as React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TextViewer } from '../src/components/TextViewer';

// 甲（站主 Q1）：TextViewer 的 6 个可选属性（合同 §4）——不传时 DOM 同 T007，传时各自生效。
afterEach(cleanup);

const ESC = '\u001b';
const JPAGES = [
  {
    mode: 'jsonl' as const,
    lines: [
      { n: 1, text: 'Hello World' },
      { n: 2, text: 'second LINE' },
      { n: 3, hidden: 'not_json' },
      { n: 4, text: ESC + '[31mred ERROR' + ESC + '[0m here' },
      { n: 5, text: 'tail line', part: 1, parts: 2 },
    ],
  },
];
const TEXT_PAGES = [{ mode: 'text' as const, text: 'one\ntwo\nthree\n' }];

function mountTv(props: Record<string, unknown> = {}) {
  const onCopy = vi.fn();
  const r = render(<TextViewer title="t" pages={TEXT_PAGES} hasMore={false} onCopy={onCopy} {...props} />);
  const root = r.container.querySelector('.tt-viewer') as HTMLElement;
  return {
    ...r,
    root,
    onCopy,
    head: root.querySelector('.tt-viewer__head') as HTMLElement,
    body: root.querySelector('.tt-viewer__body') as HTMLElement,
    foot: root.querySelector('.tt-viewer__foot') as HTMLElement,
  };
}
const FOLLOWING = Node.DOCUMENT_POSITION_FOLLOWING;
const norm = (html: string) => html.replace(/:r[0-9a-z]+:/g, ':rX:');
const nums = (root: HTMLElement) =>
  Array.from(root.querySelectorAll('.tt-viewer__row')).map((r) => (r.querySelector('.tt-viewer__num')?.textContent || '').trim());
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();

describe('不传时 DOM 同 T007', () => {
  it('根只有 head、body、foot；主体 class 就是 tt-viewer__body；全传 undefined 与 filter 空串都逐字相同', () => {
    const a = mountTv();
    expect(a.root.className).toBe('tt-viewer');
    expect(Array.from(a.root.children).map((c) => c.className)).toEqual(['tt-viewer__head', 'tt-viewer__body', 'tt-viewer__foot']);
    expect(a.body.className).toBe('tt-viewer__body');
    expect(Array.from(a.head.children).map((c) => c.className)).toEqual(['tt-viewer__title', 'tt-viewer__tools']);
    expect(Array.from(a.body.children).every((c) => c.className === 'tt-viewer__row')).toBe(true);
    const htmlA = norm(a.container.innerHTML);
    a.unmount();
    const b = mountTv({ bodyRef: undefined, onBodyScroll: undefined, bodyClassName: undefined, headerExtra: undefined, bottomBar: undefined, filter: undefined });
    expect(norm(b.container.innerHTML)).toBe(htmlA);
    b.unmount();
    const c = mountTv({ filter: '' });
    expect(norm(c.container.innerHTML)).toBe(htmlA);
  });
});

describe('bodyRef、onBodyScroll、bodyClassName', () => {
  it('bodyRef（对象与回调）指向 div.tt-viewer__body；卸载后对象 ref 置空', () => {
    const ref = React.createRef<HTMLDivElement>();
    const a = mountTv({ bodyRef: ref });
    expect(ref.current).toBe(a.body);
    expect(ref.current!.classList.contains('tt-viewer__body')).toBe(true);
    a.unmount();
    expect(ref.current).toBeNull();
    let got: HTMLElement | null = null;
    const b = mountTv({ bodyRef: (el: HTMLElement | null) => { if (el) got = el; } });
    expect(got).toBe(b.body);
  });

  it('onBodyScroll 收到主体自己的 scroll，别处滚动不触发', () => {
    const spy = vi.fn();
    const a = mountTv({ onBodyScroll: spy });
    fireEvent.scroll(a.body);
    expect(spy).toHaveBeenCalledTimes(1);
    fireEvent.scroll(a.head);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('bodyClassName 加在主体上，不动根与别的元素', () => {
    const a = mountTv({ bodyClassName: 'extra-body second' });
    expect(a.body.classList.contains('tt-viewer__body')).toBe(true);
    expect(a.body.classList.contains('extra-body')).toBe(true);
    expect(a.body.classList.contains('second')).toBe(true);
    expect(a.root.className).toBe('tt-viewer');
  });
});

describe('headerExtra、bottomBar', () => {
  it('headerExtra 在头部、复制钮之后；不在主体里', () => {
    const a = mountTv({ headerExtra: <i data-testid="hx">额外</i> });
    const hx = a.root.querySelector('[data-testid="hx"]') as HTMLElement;
    expect(a.head.contains(hx)).toBe(true);
    expect(a.body.contains(hx)).toBe(false);
    const copy = a.head.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement;
    expect(copy.compareDocumentPosition(hx) & FOLLOWING).toBeTruthy();
    expect(a.head.querySelectorAll('[data-testid="hx"]').length).toBe(1);
  });

  it('bottomBar 在主体与底栏之间、不在主体或底栏里', () => {
    const a = mountTv({ bottomBar: <div data-testid="bb">底部条</div>, changed: true });
    const bb = a.root.querySelector('[data-testid="bb"]') as HTMLElement;
    expect(a.body.contains(bb)).toBe(false);
    expect(a.foot.contains(bb)).toBe(false);
    expect(a.body.compareDocumentPosition(bb) & FOLLOWING).toBeTruthy();
    expect(bb.compareDocumentPosition(a.foot) & FOLLOWING).toBeTruthy();
    const kids = Array.from(a.root.children);
    const holder = kids.find((k) => k === bb || k.contains(bb)) as Element;
    expect(kids.indexOf(holder)).toBe(kids.indexOf(a.body) + 1);
    expect(kids.indexOf(holder)).toBe(kids.indexOf(a.foot) - 1);
  });
});

describe('filter', () => {
  it('不分大小写；拼好分片、去 ANSI 后匹配；行号不变；隐藏行不显示；没有匹配显示提示', () => {
    const cases: Array<[string, string[]]> = [
      ['', ['1', '2', '3', '4', '5']],
      ['hello', ['1']],
      ['SECOND line', ['2']],
      ['red error here', ['4']],
      ['LINE', ['2', '5']],
      [' ', ['1', '2', '4', '5']],
    ];
    for (const [value, want] of cases) {
      const a = mountTv({ pages: JPAGES, filter: value });
      expect(nums(a.root), '过滤「' + value + '」').toEqual(want);
      expect(textOf(a.foot)).toContain('已显示 1 页');
      a.unmount();
    }
    const none = mountTv({ pages: JPAGES, filter: '31m' });
    expect(nums(none.root)).toEqual([]);
    expect(textOf(none.body)).toContain('没有匹配的行');
    const hidden = mountTv({ pages: JPAGES, filter: 'e' });
    expect(textOf(hidden.root)).not.toContain('这一行不是合法 JSON，已隐藏');
  });

  it('text 模式行号保持原值；复制只含显示的行；清空后还原', () => {
    const a = mountTv({ pages: TEXT_PAGES, filter: 'T' });
    expect(nums(a.root)).toEqual(['2', '3']);
    fireEvent.click(a.root.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement);
    expect(a.onCopy).toHaveBeenCalledWith('two\nthree');
    a.rerender(<TextViewer title="t" pages={TEXT_PAGES} hasMore={false} onCopy={a.onCopy} filter="three" />);
    expect(nums(a.root)).toEqual(['3']);
    a.rerender(<TextViewer title="t" pages={TEXT_PAGES} hasMore={false} onCopy={a.onCopy} filter="" />);
    expect(nums(a.root)).toEqual(['1', '2', '3']);
  });

  it('六个属性一起传不互相干扰；已有属性照旧', () => {
    const ref = React.createRef<HTMLDivElement>();
    const onBodyScroll = vi.fn();
    const a = mountTv({
      bodyRef: ref, onBodyScroll, bodyClassName: 'bc', headerExtra: <i data-testid="hx" />, bottomBar: <i data-testid="bb" />, filter: 'o',
      changed: true, onReload: vi.fn(),
    });
    expect(ref.current).toBe(a.body);
    expect(nums(a.root)).toEqual(['1', '2']);
    expect(a.root.querySelector('.tt-banner')).not.toBeNull();
    fireEvent.click(Array.from(a.head.querySelectorAll('button')).find((b) => textOf(b) === '行号') as HTMLElement);
    expect(a.root.classList.contains('tt-viewer--no-num')).toBe(true);
    fireEvent.scroll(a.body);
    expect(onBodyScroll).toHaveBeenCalledTimes(1);
  });
});
