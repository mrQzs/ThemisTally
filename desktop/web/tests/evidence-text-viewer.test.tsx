import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stripAnsi } from '../src/components/evidence/ansi';
import { pagesToLines } from '../src/components/evidence/viewerLines';
import { TextViewer } from '../src/components/TextViewer';

afterEach(cleanup);

const ESC = '\u001b';
const tp = (text: string, part?: number, parts?: number) => ({ mode: 'text' as const, text, part, parts });
const jp = (lines: readonly ({ n: number; text: string; part?: number; parts?: number } | { n: number; hidden: string })[]) =>
  ({ mode: 'jsonl' as const, lines });

function mountViewer(initial: Record<string, unknown> = {}, withLoad = true, withReload = true) {
  const spies = {
    onCopy: vi.fn(),
    onLoadMore: withLoad ? vi.fn() : undefined,
    onReload: withReload ? vi.fn() : undefined,
  };
  let cur: Record<string, unknown> = { pages: [], hasMore: false, ...initial };
  const el = () => (
    <TextViewer
      onCopy={spies.onCopy as (text: string) => void}
      onLoadMore={spies.onLoadMore as (() => void) | undefined}
      onReload={spies.onReload as (() => void) | undefined}
      {...cur}
    />
  );
  const r = render(el());
  const root = r.container.querySelector('.tt-viewer') as HTMLElement;
  expect(root, '应有根元素 div.tt-viewer').not.toBeNull();
  expect(root.tagName).toBe('DIV');
  const update = (patch: Record<string, unknown>) => {
    cur = { ...cur, ...patch };
    r.rerender(el());
  };
  return { ...r, root, ...spies, update };
}
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const numEls = (root: HTMLElement) => Array.from(root.querySelectorAll('.tt-num[aria-hidden="true"]')) as HTMLElement[];
const numbers = (root: HTMLElement) => numEls(root).map((e) => textOf(e));
const rowOf = (root: HTMLElement, num: HTMLElement) => {
  let el: HTMLElement = num;
  while (el.parentElement && el.parentElement !== root) {
    const p = el.parentElement;
    if (p.querySelectorAll('.tt-num[aria-hidden="true"]').length !== 1) break;
    if (p.querySelector('button[aria-pressed], .tt-banner')) break;
    if ((p.textContent || '').includes('已显示')) break;
    el = p;
  }
  return el;
};
const rows = (root: HTMLElement) => numEls(root).map((n) => rowOf(root, n));
const rowByNumber = (root: HTMLElement, n: number) => {
  const i = numbers(root).indexOf(String(n));
  expect(i, `找不到行号 ${n}`).toBeGreaterThanOrEqual(0);
  return rows(root)[i];
};
const copyBtn = (root: HTMLElement) =>
  root.querySelector('button[aria-label="复制已显示的文字"]') as HTMLButtonElement;
const copiedText = (root: HTMLElement, spy: { mock: { calls: unknown[][] } }) => {
  const before = spy.mock.calls.length;
  fireEvent.click(copyBtn(root));
  expect(spy.mock.calls.length).toBe(before + 1);
  return spy.mock.calls[spy.mock.calls.length - 1][0] as string;
};
const loadButtons = (root: HTMLElement) => {
  const all = Array.from(root.querySelectorAll('button')).filter((b) => textOf(b) === '继续加载') as HTMLButtonElement[];
  const rs = rows(root);
  return {
    all,
    inRows: all.filter((b) => rs.some((r) => r.contains(b))),
    inFooter: all.filter((b) => !rs.some((r) => r.contains(b))),
  };
};
const buttonByText = (root: ParentNode, text: string) => {
  const hit = Array.from(root.querySelectorAll('button')).find((b) => textOf(b) === text);
  expect(hit, `找不到「${text}」`).toBeTruthy();
  return hit as HTMLButtonElement;
};

const W1_LINES = [
  '## 执行报告',
  '',
  '<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字',
  '<script>alert(1)</script>',
  ESC + '[31m红色文字' + ESC + '[0m 尾部',
  'https://example.com/a?b=1&c=2',
  '<a href="https://x.example">链接</a><style>body{display:none}</style>',
  'a' + ESC + ']0;窗口标题\u0007b',
  'z',
];
const W1_SHOWN = [
  '## 执行报告',
  '',
  '<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字',
  '<script>alert(1)</script>',
  '红色文字 尾部',
  'https://example.com/a?b=1&c=2',
  '<a href="https://x.example">链接</a><style>body{display:none}</style>',
  'ab',
  'z',
];

describe('stripAnsi', () => {
  it('去 CSI（含 0x9B 开头、私有参数、中间字节）与 OSC（BEL 或 ESC 加反斜杠收尾）', () => {
    expect(stripAnsi(ESC + '[31m红' + ESC + '[0m')).toBe('红');
    expect(stripAnsi('a' + ESC + '[1;38;5;200mb' + ESC + '[0m')).toBe('ab');
    expect(stripAnsi('x' + ESC + '[?25ly')).toBe('xy');
    expect(stripAnsi('x' + ESC + '[ qy')).toBe('xy');
    expect(stripAnsi('a\u009b31mb\u009b0m')).toBe('ab');
    expect(stripAnsi('a' + ESC + ']0;窗口标题\u0007b')).toBe('ab');
    expect(stripAnsi('a' + ESC + ']8;;https://x.example' + ESC + '\\链接' + ESC + ']8;;' + ESC + '\\')).toBe('a链接');
  });

  it('去其余 ESC 双字符序列；最后剩下的 ESC 与 U+009B 一律去掉', () => {
    expect(stripAnsi('a' + ESC + 'Mb')).toBe('ab');
    expect(stripAnsi(ESC + 'cX')).toBe('X');
    expect(stripAnsi('a' + ESC)).toBe('a');
    expect(stripAnsi('a\u009b')).toBe('a');
    for (const junk of [ESC + '[', ESC + '[31', ESC + ']0;abc', '\u009b', ESC + '\\', ESC + ESC, 'x' + ESC + '[;']) {
      const out = stripAnsi(junk);
      expect(out.includes(ESC), junk).toBe(false);
      expect(out.includes('\u009b'), junk).toBe(false);
    }
  });

  it('不动普通文字；256 KiB 的病态输入都在 1 秒内完成', () => {
    expect(stripAnsi('普通 [31m 文字 [0m')).toBe('普通 [31m 文字 [0m');
    expect(stripAnsi('a\tb\r\nc\n')).toBe('a\tb\r\nc\n');
    expect(stripAnsi('')).toBe('');
    const size = 256 * 1024;
    const inputs = {
      'ESC[ 重复': (ESC + '[').repeat(size / 2),
      'OSC 无终止': ESC + ']' + 'x'.repeat(size - 2),
      '全是 ESC': ESC.repeat(size),
      '0x9B 加参数重复': '\u009b0'.repeat(size / 2),
    };
    for (const [name, input] of Object.entries(inputs)) {
      const t0 = Date.now();
      const out = stripAnsi(input);
      expect(Date.now() - t0, name).toBeLessThan(1000);
      expect(out.includes(ESC), name).toBe(false);
    }
  }, 30000);
});

describe('页转行', () => {
  it('text 模式先接后切；末尾换行不多空行；CRLF 去回车；以换行开头的页不多出空行', () => {
    expect(pagesToLines([tp('a\nb'), tp('c\nd\n')]).map((l) => l.text)).toEqual(['a', 'bc', 'd']);
    expect(pagesToLines([tp('x\ny\n')]).map((l) => l.text)).toEqual(['x', 'y']);
    expect(pagesToLines([tp('x\n\n')]).map((l) => l.text)).toEqual(['x', '']);
    expect(pagesToLines([tp('first\nlong-tail'), tp('\nsecond\n')]).map((l) => l.text))
      .toEqual(['first', 'long-tail', 'second']);
    expect(pagesToLines([tp('a\r\nb\r\n')]).map((l) => l.text)).toEqual(['a', 'b']);
    expect(pagesToLines([tp('\nx\n')]).map((l) => l.text)).toEqual(['', 'x']);
    expect(pagesToLines([tp('前' + ESC + '[3'), tp('1m红' + ESC + '[0m后\n')]).map((l) => l.text)).toEqual(['前红后']);
  });

  it('分片：每页开头落在第几行就把 part/parts 记到那一行，后来的页覆盖先前的', () => {
    const two = pagesToLines([tp('AAAA', 1, 3), tp('BBBB', 2, 3)]);
    expect(two.length).toBe(1);
    expect(two[0].text).toBe('AAAABBBB');
    expect([two[0].part, two[0].parts]).toEqual([2, 3]);
    const three = pagesToLines([tp('AAAA', 1, 3), tp('BBBB', 2, 3), tp('CCCC\nnext\n', 3, 3)]);
    expect(three.map((l) => l.text)).toEqual(['AAAABBBBCCCC', 'next']);
    expect([three[0].part, three[0].parts]).toEqual([3, 3]);
    expect(three[1].part).toBeUndefined();
  });

  it('jsonl 模式：行号用 n；同一个 n 的分片按到达顺序拼接，记最后一片的 part/parts', () => {
    const P1 = jp([{ n: 1, text: '{"a":1}' }, { n: 2, hidden: 'not_json' }, { n: 5, text: '{"b":', part: 1, parts: 3 }]);
    const P2 = jp([{ n: 5, text: '2,', part: 2, parts: 3 }]);
    const P3 = jp([{ n: 5, text: '3}', part: 3, parts: 3 }, { n: 6, text: '{"c":3}' }]);
    const two = pagesToLines([P1, P2]);
    expect(two.map((l) => l.n)).toEqual([1, 2, 5]);
    expect(two[2].text).toBe('{"b":2,');
    expect([two[2].part, two[2].parts]).toEqual([2, 3]);
    const all = pagesToLines([P1, P2, P3]);
    expect(all.map((l) => l.n)).toEqual([1, 2, 5, 6]);
    expect(all[2].text).toBe('{"b":2,3}');
    expect(all[1].hidden).toBe('not_json');
  });
});

describe('W1：不可信内容只按文本显示', () => {
  it('DOM 里没有 img、script、a 等元素；行里没有 style 属性；文字原样出现；ESC 与 [31m 都不出现', () => {
    const { root } = mountViewer({ pages: [tp(W1_LINES.join('\n') + '\n')] });
    expect(document.body.querySelectorAll('img, script, a, style, iframe, object, embed, link').length).toBe(0);
    expect(root.querySelectorAll('[onerror], [href], [src]').length).toBe(0);
    const text = root.textContent || '';
    for (const line of W1_SHOWN) if (line) expect(text).toContain(line);
    expect(text.includes(ESC)).toBe(false);
    expect(text.includes('[31m')).toBe(false);
    expect(text.includes('\u0007')).toBe(false);
    expect(text.includes('窗口标题')).toBe(false);
    expect(rows(root).length).toBe(9);
    for (const row of rows(root)) {
      expect(row.hasAttribute('style')).toBe(false);
      expect(row.querySelector('[style]')).toBeNull();
    }
    expect(document.querySelector('[role="status"]')).toBeNull();
  });

  it('网址不自动变链接：包着网址文字的祖先里没有 a、button、role=link', () => {
    const { root } = mountViewer({ pages: [tp(W1_LINES.join('\n') + '\n')] });
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    let seen = 0;
    while ((node = walker.nextNode())) {
      if ((node.textContent || '').includes('https://example.com')) {
        seen += 1;
        for (let el = node.parentElement; el && el !== root; el = el.parentElement) {
          expect(['A', 'BUTTON']).not.toContain(el.tagName);
          expect(el.getAttribute('role')).not.toBe('link');
        }
      }
    }
    expect(seen).toBeGreaterThan(0);
  });

  it('行号：每行一个，aria-hidden、tt-num，数字 1 到 9', () => {
    const { root } = mountViewer({ pages: [tp(W1_LINES.join('\n') + '\n')] });
    expect(numbers(root)).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9']);
    for (const n of numEls(root)) expect(n.getAttribute('aria-hidden')).toBe('true');
  });

  it('行号与换行两个文字按钮：type=button、aria-pressed 缺省 true/false；点一下翻转并改变样式钩子，再点恢复', () => {
    const { root } = mountViewer({ pages: [tp(W1_LINES.join('\n') + '\n')] });
    const lineBtn = buttonByText(root, '行号');
    const wrapBtn = buttonByText(root, '换行');
    expect(lineBtn.getAttribute('type')).toBe('button');
    expect(wrapBtn.getAttribute('type')).toBe('button');
    expect(lineBtn.getAttribute('aria-pressed')).toBe('true');
    expect(wrapBtn.getAttribute('aria-pressed')).toBe('false');
    expect(lineBtn.querySelector('svg')).toBeNull();
    expect(wrapBtn.querySelector('svg')).toBeNull();
    const hooks = () =>
      [root, ...Array.from(root.querySelectorAll('*'))]
        .map((e) =>
          e.tagName + '|' + e.getAttribute('class') + '|' + e.getAttribute('style') + '|' +
          Array.from(e.attributes).filter((a) => a.name.startsWith('data-')).map((a) => a.name + '=' + a.value).join(','))
        .join('\n');
    const before = hooks();
    fireEvent.click(wrapBtn);
    expect(wrapBtn.getAttribute('aria-pressed')).toBe('true');
    expect(hooks()).not.toBe(before);
    fireEvent.click(wrapBtn);
    expect(wrapBtn.getAttribute('aria-pressed')).toBe('false');
    expect(hooks()).toBe(before);
    fireEvent.click(lineBtn);
    expect(lineBtn.getAttribute('aria-pressed')).toBe('false');
    expect(numEls(root).length).toBe(0);
    expect(textOf(root)).toContain('红色文字 尾部');
    fireEvent.click(lineBtn);
    expect(numEls(root).length).toBe(9);
  });

  it('开关状态在换页（重新渲染）后保持', () => {
    const { root, update } = mountViewer({ pages: [tp(W1_LINES.join('\n') + '\n')] });
    fireEvent.click(buttonByText(root, '换行'));
    fireEvent.click(buttonByText(root, '行号'));
    update({ pages: [tp(W1_LINES.join('\n') + '\n'), tp('more\n')], hasMore: true });
    expect(buttonByText(root, '换行').getAttribute('aria-pressed')).toBe('true');
    expect(buttonByText(root, '行号').getAttribute('aria-pressed')).toBe('false');
    expect(numEls(root).length).toBe(0);
  });

  it('复制：回调收到的字符串逐字等于各文字行用换行连接，末尾不加换行', () => {
    const { root, onCopy } = mountViewer({ pages: [tp(W1_LINES.join('\n') + '\n')] });
    expect(copiedText(root, onCopy)).toBe(W1_SHOWN.join('\n'));
    expect(onCopy).toHaveBeenCalledTimes(1);
  });

  it('复制钮是 IconButton sm、名称「复制已显示的文字」，里面有 CopyIcon 的 rect 14', () => {
    const { root } = mountViewer({ pages: [tp('a\n')] });
    const btn = copyBtn(root);
    expect(btn.getAttribute('type')).toBe('button');
    expect(btn.classList.contains('tt-icon-btn')).toBe(true);
    expect(btn.classList.contains('tt-icon-btn--sm')).toBe(true);
    expect(btn.querySelector('svg rect[width="14"][height="14"]')).not.toBeNull();
  });

  it('页里先接后切：ANSI 序列被页边界切开时仍能去掉', () => {
    const { root, onCopy } = mountViewer({ pages: [tp('前' + ESC + '[3'), tp('1m红' + ESC + '[0m后\n')], hasMore: false });
    expect(copiedText(root, onCopy)).toBe('前红后');
    expect((root.textContent || '').includes(ESC)).toBe(false);
  });
});

describe('分页、分片与底栏', () => {
  it('已显示 N 页；hasMore 为假时另显示「已到末尾」；0 页也对', () => {
    const { root, update } = mountViewer({ pages: [tp('a\nb\n'), tp('c\n')], hasMore: true });
    expect(textOf(root)).toMatch(/已显示\s*2\s*页/);
    expect(textOf(root)).not.toContain('已到末尾');
    update({ hasMore: false });
    expect(textOf(root)).toContain('已到末尾');
    update({ pages: [], hasMore: false });
    expect(textOf(root)).toMatch(/已显示\s*0\s*页/);
  });

  it('hasMore 为真且给了 onLoadMore 时底栏有 [继续加载]，点一下调一次；否则没有', () => {
    const a = mountViewer({ pages: [tp('a\nb\n')], hasMore: true });
    expect(loadButtons(a.root).all.length).toBe(1);
    expect(loadButtons(a.root).inFooter.length).toBe(1);
    fireEvent.click(loadButtons(a.root).all[0]);
    expect(a.onLoadMore).toHaveBeenCalledTimes(1);
    a.update({ hasMore: false });
    expect(loadButtons(a.root).all.length).toBe(0);
    a.unmount();
    const b = mountViewer({ pages: [tp('a\nb\n')], hasMore: true }, false);
    expect(loadButtons(b.root).all.length).toBe(0);
  });

  it('loadingMore：底栏按钮用 Button 的 loading（文字「正在加载…」、禁用、aria-busy），点了不调 onLoadMore', () => {
    const { root, onLoadMore } = mountViewer({ pages: [tp('a\n')], hasMore: true, loadingMore: true });
    const btn = buttonByText(root, '正在加载…') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute('aria-busy')).toBe('true');
    expect(Array.from(root.querySelectorAll('button')).filter((b) => textOf(b) === '继续加载').length).toBe(0);
    fireEvent.click(btn);
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  it('分片行：第 k/n 片在文字前；加载完仍显示第 n/n 片；下一行没有分片提示', () => {
    const { root } = mountViewer({ pages: [tp('AAAA', 1, 3), tp('BBBB', 2, 3), tp('CCCC\nnext\n', 3, 3)], hasMore: false });
    const row = rowByNumber(root, 1);
    const text = row.textContent || '';
    expect(text).toContain('AAAABBBBCCCC');
    expect(textOf(row)).toMatch(/第\s*3\/3\s*片/);
    expect(text.search(/第\s*3\/3\s*片/)).toBeLessThan(text.indexOf('AAAABBBBCCCC'));
    expect(textOf(rowByNumber(root, 2))).not.toMatch(/第\s*\d+\/\d+\s*片/);
    const cap = Array.from(row.querySelectorAll('*')).find((e) => /^第\s*3\/3\s*片$/.test(textOf(e)));
    expect(cap).toBeTruthy();
    expect((cap as Element).closest('button')).toBeNull();
    expect((cap as Element).hasAttribute('tabindex')).toBe(false);
  });

  it('行尾 [继续加载] 只在最后一行没加载完且还有下一页时出现；k=n 或没有下一页就没有', () => {
    const a = mountViewer({ pages: [tp('AAAA', 1, 2)], hasMore: true });
    const lb = loadButtons(a.root);
    expect(lb.inRows.length).toBe(1);
    expect(lb.inFooter.length).toBe(1);
    expect(lb.inRows[0].classList.contains('tt-btn')).toBe(true);
    expect(lb.inRows[0].classList.contains('tt-btn--secondary')).toBe(true);
    expect(lb.inRows[0].classList.contains('tt-btn--sm')).toBe(true);
    fireEvent.click(lb.inRows[0]);
    expect(a.onLoadMore).toHaveBeenCalledTimes(1);
    a.unmount();
    const b = mountViewer({ pages: [tp('A\nB\n', 1, 2)], hasMore: true });
    expect(loadButtons(b.root).inRows.length).toBe(0);
    expect(loadButtons(b.root).inFooter.length).toBe(1);
    b.unmount();
    const c = mountViewer({ pages: [tp('AAAA', 1, 2)], hasMore: false });
    expect(loadButtons(c.root).all.length).toBe(0);
  });
});

describe('jsonl 与隐藏行', () => {
  const P1 = jp([
    { n: 1, text: '{"a":1}' },
    { n: 2, hidden: 'not_json' },
    { n: 3, hidden: 'too_long' },
    { n: 4, hidden: '<b>weird</b>' },
    { n: 5, text: '{"b":', part: 1, parts: 2 },
  ]);
  const P2 = jp([{ n: 5, text: '2}', part: 2, parts: 2 }, { n: 6, text: '{"c":3}' }]);

  it('行号用 n；同一个 n 的分片按到达顺序拼接；复制跳过隐藏行', () => {
    const { root, onCopy } = mountViewer({ pages: [P1, P2], hasMore: false });
    expect(numbers(root)).toEqual(['1', '2', '3', '4', '5', '6']);
    expect(rowByNumber(root, 5).textContent).toContain('{"b":2}');
    expect(textOf(rowByNumber(root, 5))).toMatch(/第\s*2\/2\s*片/);
    expect(loadButtons(root).all.length).toBe(0);
    expect(copiedText(root, onCopy)).toBe('{"a":1}\n{"b":2}\n{"c":3}');
  });

  it('隐藏行三种说明；EyeOffIcon 14 带 aria-hidden；行号照常；原值只当文字', () => {
    const { root } = mountViewer({ pages: [P1, P2] });
    expect(textOf(rowByNumber(root, 2))).toContain('这一行不是合法 JSON，已隐藏');
    expect(textOf(rowByNumber(root, 3))).toContain('这一行超过 4 MiB，已隐藏');
    expect(textOf(rowByNumber(root, 4))).toContain('这一行已隐藏：<b>weird</b>');
    expect(textOf(rowByNumber(root, 2))).not.toContain('超过 4 MiB');
    expect(root.querySelectorAll('b').length).toBe(0);
    for (const n of [2, 3, 4]) {
      const svg = rowByNumber(root, n).querySelector('svg');
      expect(svg).not.toBeNull();
      expect((svg as Element).getAttribute('width')).toBe('14');
      expect((svg as Element).getAttribute('aria-hidden')).toBe('true');
      const ds = Array.from((svg as Element).querySelectorAll('path')).map((p) => p.getAttribute('d'));
      expect(ds).toContain('m2 2 20 20');
    }
  });

  it('隐藏行不能展开：没有按钮、链接、tabindex；点击无反应', () => {
    const { root, onCopy, onLoadMore } = mountViewer({ pages: [P1], hasMore: false });
    const row = rowByNumber(root, 2);
    expect(row.querySelector('button, a, [tabindex], input, [role="button"], [role="link"]')).toBeNull();
    const before = root.innerHTML;
    fireEvent.click(row);
    fireEvent.doubleClick(row);
    expect(root.innerHTML).toBe(before);
    expect(onCopy).not.toHaveBeenCalled();
    expect(onLoadMore).not.toHaveBeenCalled();
  });
});

describe('文件已变化与属性缺省', () => {
  it('changed 为真时头部与行之间有 info 提示条，action 是 [从头读取]，点一下调 onReload', () => {
    const { root, onReload } = mountViewer({ pages: [tp('a\nb\n')], changed: true });
    const banner = root.querySelector('.tt-banner') as HTMLElement;
    expect(banner).not.toBeNull();
    expect(banner.getAttribute('data-tone')).toBe('info');
    expect(textOf(banner)).toContain('文件已变化');
    const action = banner.querySelector('.tt-banner__action') as HTMLElement;
    expect(action).not.toBeNull();
    fireEvent.click(buttonByText(action, '从头读取'));
    expect(onReload).toHaveBeenCalledTimes(1);
    const head = buttonByText(root, '行号');
    expect(head.compareDocumentPosition(banner) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(banner.compareDocumentPosition(numEls(root)[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('没给 onReload 时没有 [从头读取]；没 changed 时没有提示条', () => {
    const a = mountViewer({ pages: [tp('a\n')], changed: true }, true, false);
    expect(Array.from(a.root.querySelectorAll('button')).filter((b) => textOf(b) === '从头读取').length).toBe(0);
    expect(textOf(a.root)).toContain('文件已变化');
    a.unmount();
    const b = mountViewer({ pages: [tp('a\n')], changed: false });
    expect(b.root.querySelector('.tt-banner')).toBeNull();
  });

  it('点关闭先藏起来；changed 仍为真时不重新出现；变假再变真时重新出现', () => {
    const { root, update } = mountViewer({ pages: [tp('a\n')], changed: true });
    const close = (root.querySelector('.tt-banner') as HTMLElement)
      .querySelector('button[aria-label="关闭提示"]') as HTMLElement;
    fireEvent.click(close);
    expect(root.querySelector('.tt-banner')).toBeNull();
    update({ pages: [tp('a\n'), tp('b\n')] });
    expect(root.querySelector('.tt-banner')).toBeNull();
    update({ changed: false });
    expect(root.querySelector('.tt-banner')).toBeNull();
    update({ changed: true });
    expect(root.querySelector('.tt-banner')).not.toBeNull();
  });

  it('changed 为真时底栏与行尾的 [继续加载] 都禁用，点了不调 onLoadMore', () => {
    const { root, onLoadMore } = mountViewer({ pages: [tp('AAAA', 1, 2)], hasMore: true, changed: true });
    const lb = loadButtons(root);
    expect(lb.inRows.length).toBe(1);
    expect(lb.inFooter.length).toBe(1);
    for (const b of lb.all) {
      expect(b.disabled).toBe(true);
      fireEvent.click(b);
    }
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  it('defaultLineNumbers=false 行号关、defaultWrap=true 换行开；title 与 className 生效', () => {
    const a = mountViewer({ pages: [tp('a\nb\n')], defaultLineNumbers: false, defaultWrap: true });
    expect(buttonByText(a.root, '行号').getAttribute('aria-pressed')).toBe('false');
    expect(buttonByText(a.root, '换行').getAttribute('aria-pressed')).toBe('true');
    expect(numEls(a.root).length).toBe(0);
    a.unmount();
    const b = mountViewer({ pages: [tp('a\n')], title: 'executor-report.md', className: 'gate-extra' });
    expect(b.root.classList.contains('gate-extra')).toBe(true);
    expect(textOf(b.root)).toContain('executor-report.md');
  });
});

describe('TextViewer.css 的取值（读 CSS 文本）', () => {
  const css = readFileSync(join(process.cwd(), 'src/components/TextViewer.css'), 'utf8');

  it('根、头、切换钮、行号列、文字、底栏的关键取值在', () => {
    expect(css).toMatch(/\.tt-viewer\s*\{[^}]*background:\s*var\(--tt-surface-1\)/);
    expect(css).toMatch(/border:\s*1px solid var\(--tt-border\)/);
    expect(css).toMatch(/border-radius:\s*var\(--tt-radius-lg\)/);
    expect(css).toMatch(/\.tt-viewer\s*\{[^}]*overflow:\s*hidden/);
    expect(css).toMatch(/height:\s*40px/);
    expect(css).toMatch(/\.tt-viewer__toggle[^{]*\{[^}]*height:\s*28px/);
    expect(css).toMatch(/\.tt-viewer__toggle\[aria-pressed="true"\][^{]*\{[^}]*background:\s*var\(--tt-surface-3\)/);
    expect(css).toMatch(/\.tt-viewer__num[^{]*\{[^}]*width:\s*44px[^}]*text-align:\s*right/);
    expect(css).toMatch(/\.tt-viewer__num[^{]*\{[^}]*user-select:\s*none/);
    expect(css).toMatch(/\.tt-viewer__text[^{]*\{[^}]*min-height:\s*20px/);
    expect(css).toMatch(/\.tt-viewer--wrap \.tt-viewer__text[^{]*\{[^}]*white-space:\s*pre-wrap[^}]*word-break:\s*break-all/);
    expect(css).toMatch(/\.tt-viewer__body[^{]*\{[^}]*overflow-x:\s*auto/);
    expect(css).toMatch(/\.tt-viewer__foot[^{]*\{[^}]*background:\s*var\(--tt-surface-2\)/);
    expect(css).toMatch(/\.tt-viewer__foot \.tt-btn[^{]*\{[^}]*margin-left:\s*auto/);
    expect(css).toMatch(/\.tt-viewer \.tt-banner\s*\{[^}]*margin:\s*var\(--tt-space-2\) var\(--tt-space-3\)/);
    expect(css).toMatch(/\.tt-viewer__part[^{]*\{[^}]*font:\s*var\(--tt-text-caption\)[^}]*user-select:\s*none/);
    expect(css).toMatch(/\.tt-viewer__hidden[^{]*\{[^}]*font-style:\s*italic/);
  });

  it('带 px 的每一行都有同一行注释', () => {
    for (const [no, line] of css.split('\n').entries()) {
      const code = line.replace(/\/\*.*?\*\//g, '');
      const m = /(?<![\w.#-])(-?\d*\.?\d+)px\b/.exec(code);
      if (m && Math.abs(Number(m[1])) > 1) {
        expect(line, `第 ${no + 1} 行的 ${m[0]} 缺同一行注释`).toMatch(/\/\*[^*]*\*\//);
      }
    }
  });
});
