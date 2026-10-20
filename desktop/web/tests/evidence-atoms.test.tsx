import { cleanup, render, fireEvent, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CopyIcon, EyeOffIcon, LockIcon } from '../src/icons';
import { Banner } from '../src/components/Banner';
import { CommandLine, dispatchCommand } from '../src/components/CommandLine';
import { MaskedValue, isMaskedPlaceholder } from '../src/components/MaskedValue';
import { NextStep } from '../src/components/NextStep';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const advance = (ms: number) => { act(() => { vi.advanceTimersByTime(ms); }); };
const tipEl = () => document.querySelector('[role="tooltip"]');
const PLACEHOLDERS = ['（含疑似凭据，不显示）', '（值不显示）', '<redacted>', '（疑似凭据的键名）'];

describe('第 5 片的三个图标', () => {
  for (const [name, Icon, rect, paths] of [
    ['LockIcon', LockIcon, { width: '18', height: '11', x: '3', y: '11', rx: '2', ry: '2' }, ['M7 11V7a5 5 0 0 1 10 0v4']],
    ['CopyIcon', CopyIcon, { width: '14', height: '14', x: '8', y: '8', rx: '2', ry: '2' },
      ['M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2']],
    ['EyeOffIcon', EyeOffIcon, null, [
      'M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49',
      'M14.084 14.158a3 3 0 0 1-4.242-4.242',
      'M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143',
      'm2 2 20 20']] as const,
  ] as const) {
    it(name + '：沿用 Svg 包装，rect 属性与 path d 逐条等于合同', () => {
      const { container } = render(<Icon width={14} height={14} />);
      const svg = container.querySelector('svg') as SVGElement;
      expect(svg).not.toBeNull();
      expect(svg.getAttribute('aria-hidden')).toBe('true');
      expect(svg.classList.contains('tt-i')).toBe(true);
      expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
      expect(svg.getAttribute('width')).toBe('14');
      const rects = Array.from(svg.querySelectorAll('rect'));
      if (rect) {
        expect(rects.length).toBe(1);
        const got: Record<string, string> = {};
        for (const a of Array.from(rects[0].attributes)) got[a.name] = a.value;
        expect(got).toEqual(rect);
      } else {
        expect(rects.length).toBe(0);
      }
      expect(Array.from(svg.querySelectorAll('path')).map((p) => p.getAttribute('d'))).toEqual([...paths]);
      expect(svg.children.length).toBe(rects.length + paths.length);
    });
  }
});

describe('Banner 的可选 action', () => {
  const classes = (el: Element) => Array.from(el.children).map((c) => c.getAttribute('class'));

  it('不传 action 时结构与以前完全相同：图标、文字、关闭钮三格', () => {
    const onClose = vi.fn();
    const { container } = render(<Banner tone="info" onClose={onClose}>提示内容</Banner>);
    const banner = container.querySelector('.tt-banner') as HTMLElement;
    expect(classes(banner)).toEqual(['tt-i tt-banner__icon', 'tt-banner__text', 'tt-banner__close']);
    expect(banner.querySelector('.tt-banner__action')).toBeNull();
    fireEvent.click(banner.querySelector('.tt-banner__close')!);
    expect(onClose).toHaveBeenCalledTimes(1);
    const w = render(<Banner tone="warning">注意</Banner>);
    expect(classes(w.container.querySelector('.tt-banner')!)).toEqual(['tt-i tt-banner__icon', 'tt-banner__text']);
  });

  it('传了 action：span.tt-banner__action 在文字之后、关闭钮之前；点操作钮不触发关闭', () => {
    const onClose = vi.fn();
    const onAct = vi.fn();
    const { container } = render(
      <Banner tone="info" onClose={onClose} action={<button type="button" onClick={onAct}>从头读取</button>}>
        文件已变化
      </Banner>,
    );
    const banner = container.querySelector('.tt-banner') as HTMLElement;
    const kids = Array.from(banner.children);
    expect(kids.length).toBe(4);
    expect(kids[1].classList.contains('tt-banner__text')).toBe(true);
    expect(kids[2].tagName).toBe('SPAN');
    expect(kids[2].classList.contains('tt-banner__action')).toBe(true);
    expect(kids[3].classList.contains('tt-banner__close')).toBe(true);
    fireEvent.click(Array.from(kids[2].querySelectorAll('button')).find((b) => textOf(b) === '从头读取')!);
    expect(onAct).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
    const w = render(<Banner tone="warning" action={<button type="button">x</button>}>注意</Banner>);
    expect(classes(w.container.querySelector('.tt-banner')!)).toEqual(['tt-i tt-banner__icon', 'tt-banner__text', 'tt-banner__action']);
  });
});

describe('MaskedValue 遮蔽值', () => {
  it('结构：span，title=内核已遮蔽，LockIcon 14（aria-hidden）在前，后面是原样的占位文字', () => {
    for (const value of PLACEHOLDERS) {
      const { container, unmount } = render(<MaskedValue>{value}</MaskedValue>);
      const root = container.firstElementChild as HTMLElement;
      expect(root.tagName).toBe('SPAN');
      expect(root.getAttribute('title')).toBe('内核已遮蔽');
      expect(root.textContent).toBe(value);
      const svg = root.firstElementChild as SVGElement;
      expect(svg && svg.tagName.toLowerCase()).toBe('svg');
      expect(svg.getAttribute('width')).toBe('14');
      expect(svg.getAttribute('height')).toBe('14');
      expect(svg.getAttribute('aria-hidden')).toBe('true');
      expect(svg.querySelector('rect[width="18"][height="11"]')).not.toBeNull();
      expect(root.querySelectorAll('[title]').length).toBe(0);
      unmount();
    }
    expect(document.querySelector('[role="status"]')).toBeNull();
  });

  it('isMaskedPlaceholder：四种占位逐字比较为真，其余为假（括号是全角）', () => {
    for (const v of PLACEHOLDERS) expect(isMaskedPlaceholder(v), v).toBe(true);
    for (const v of ['(值不显示)', '（值不显示） ', ' <redacted>', '<REDACTED>', '', 'abc', '（含疑似凭据，不显示', '值不显示', '（疑似凭据的键名）。']) {
      expect(isMaskedPlaceholder(v), JSON.stringify(v)).toBe(false);
    }
  });
});

describe('CommandLine 命令行', () => {
  it('dispatchCommand：bash scripts/dispatch-pi.sh 加空格连接的参数；无参数时末尾没有空格；原样不加引号不转义', () => {
    expect(dispatchCommand([])).toBe('bash scripts/dispatch-pi.sh');
    expect(dispatchCommand(['logs', 'cat'])).toBe('bash scripts/dispatch-pi.sh logs cat');
    expect(dispatchCommand(['config', 'preset', 'use', 'economy'])).toBe('bash scripts/dispatch-pi.sh config preset use economy');
    expect(dispatchCommand(['a b', '"c"', "d'e", '$X;y'])).toBe('bash scripts/dispatch-pi.sh a b "c" d\'e $X;y');
    expect(dispatchCommand(['one'])).toBe('bash scripts/dispatch-pi.sh one');
  });

  it('md（缺省）：code 里是命令文字，复制钮名称「复制命令」，点击调 onCopy(command)', () => {
    const onCopy = vi.fn();
    const command = 'bash scripts/dispatch-pi.sh config rollback 42';
    const { container } = render(<CommandLine command={command} onCopy={onCopy} />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.classList.contains('tt-cmd--sm')).toBe(false);
    expect(root.querySelector('code')!.textContent).toBe(command);
    const btn = root.querySelector('button[aria-label="复制命令"]') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.getAttribute('type')).toBe('button');
    expect(btn.classList.contains('tt-icon-btn--sm')).toBe(true);
    expect(btn.querySelector('svg rect[width="14"][height="14"]')).not.toBeNull();
    expect(root.querySelectorAll('button').length).toBe(1);
    fireEvent.click(btn);
    expect(onCopy).toHaveBeenCalledTimes(1);
    expect(onCopy).toHaveBeenCalledWith(command);
    expect(document.querySelector('[role="status"]')).toBeNull();
  });

  it('sm：根上带 tt-cmd--sm，结构与行为同 md；复制钮悬停 400ms 提示「复制」', () => {
    const onCopy = vi.fn();
    const { container } = render(<CommandLine size="sm" command="/plan-task logs-cat" onCopy={onCopy} />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.classList.contains('tt-cmd--sm')).toBe(true);
    expect(root.querySelector('code')!.textContent).toBe('/plan-task logs-cat');
    const btn = root.querySelector('button[aria-label="复制命令"]') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onCopy).toHaveBeenCalledWith('/plan-task logs-cat');
    fireEvent.mouseEnter(btn);
    advance(399);
    expect(tipEl()).toBeNull();
    advance(1);
    expect(textOf(tipEl())).toBe('复制');
  });
});

describe('NextStep 下一步', () => {
  it('不带命令：InfoIcon 16（aria-hidden）、strong 标题、说明文字；不设 role，不是提示条', () => {
    const { container } = render(<NextStep title="下一步">需要出新版本合同返工。</NextStep>);
    const root = container.firstElementChild as HTMLElement;
    expect(root.hasAttribute('role')).toBe(false);
    expect(root.querySelector('.tt-banner, [role]')).toBeNull();
    const svg = root.firstElementChild as SVGElement;
    expect(svg && svg.tagName.toLowerCase()).toBe('svg');
    expect(svg.getAttribute('width')).toBe('16');
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(Array.from(svg.querySelectorAll('path')).map((p) => p.getAttribute('d'))).toContain('M12 16v-4');
    expect(root.querySelector('strong')!.textContent).toBe('下一步');
    expect(textOf(root)).toContain('需要出新版本合同返工。');
    expect(root.querySelectorAll('button, code').length).toBe(0);
  });

  it('没有 title 时没有 strong', () => {
    const { container } = render(<NextStep>只有说明</NextStep>);
    expect(container.querySelector('strong')).toBeNull();
    expect(textOf(container)).toBe('只有说明');
  });

  it('带命令：末尾是 CommandLine size=sm，复制钮调 onCopy(command)', () => {
    const onCopy = vi.fn();
    const { container } = render(
      <NextStep title="下一步" command="/plan-task logs-cat" onCopy={onCopy}>
        在规划端会话里进行：
      </NextStep>,
    );
    const root = container.firstElementChild as HTMLElement;
    const cmd = root.querySelector('.tt-cmd--sm') as HTMLElement;
    expect(cmd).not.toBeNull();
    expect(cmd.querySelector('code')!.textContent).toBe('/plan-task logs-cat');
    const last = root.lastElementChild as HTMLElement;
    expect(last === cmd || last.contains(cmd)).toBe(true);
    fireEvent.click(cmd.querySelector('button[aria-label="复制命令"]')!);
    expect(onCopy).toHaveBeenCalledWith('/plan-task logs-cat');
    expect(root.hasAttribute('role')).toBe(false);
  });
});

describe('components/index 的运行时导出', () => {
  it('六个新组件与两个函数都从 index 导出，原来的组件仍在，内部纯函数不导出', async () => {
    const idx: Record<string, unknown> = await import('../src/components');
    for (const name of ['TextViewer', 'SafeMarkdown', 'EffortPair', 'MaskedValue', 'CommandLine', 'NextStep',
      'isMaskedPlaceholder', 'dispatchCommand', 'Button', 'Tag', 'StatusTag', 'Card', 'Banner', 'IconButton', 'Tooltip',
      'Menu', 'Dialog', 'Drawer', 'Toast', 'SegmentedControl', 'Switch', 'Checkbox', 'Tabs', 'TextField', 'Select', 'Table',
      'KeyValueList', 'EmptyState', 'Skeleton', 'ConnectionPill', 'Breadcrumb']) {
      expect(typeof idx[name], name).toBe('function');
    }
    for (const hidden of ['stripAnsi', 'parseMarkdown', 'pagesToLines']) {
      expect(idx[hidden], hidden).toBeUndefined();
    }
  });
});
