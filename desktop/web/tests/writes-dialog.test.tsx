// 写确认框（合同第六节、UI 设计 7.11）的自测：结构、不能关闭（D08、M14–M16）、纯文本报错（D13、M20）、
// 焦点陷阱与关闭后焦点返回。执行中 Esc / 点遮罩 / [取消] / 头部关闭钮都不关框，外层抽屉也不关。
import { useState } from 'react';
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Drawer } from '../src/components/Drawer';
import { WriteConfirmDialog, type ConfirmContent, type FlowView } from '../src/writes/WriteConfirmDialog';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const dlg = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const dlgText = () => {
  const d = dlg();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const btn = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;
const closeBtn = () =>
  Array.from((dlg() as HTMLElement).querySelectorAll('button')).find((b) =>
    (b.getAttribute('aria-label') || '').includes('关闭'),
  ) as HTMLButtonElement;

const CONTENT: ConfirmContent = {
  command: 'config preset use economy',
  changes: [{ role: 'execution', from: 'step-high', to: 'step-low' }],
  warnings: [],
  running: [],
  notes: [],
};

const noop = () => {};

function Harness({ view, title = '切换到方案 economy？' }: { view: FlowView; title?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        打开
      </button>
      <WriteConfirmDialog
        open={open}
        title={title}
        view={view}
        onCancel={() => setOpen(false)}
        onConfirm={noop}
        onRepreview={noop}
        onAck={() => setOpen(false)}
        onHistory={noop}
      />
    </>
  );
}

describe('确认框的结构（UI 设计 7.11）', () => {
  it('标题、将运行的命令、变化、影响与风险；按钮 [取消] [确认…]；没有危险样式与「不再询问」', () => {
    const view: FlowView = {
      phase: 'confirmable',
      content: {
        ...CONTENT,
        warnings: ['WARN 有一个 attempt 在运行'],
        running: ['ui-readonly-api/attempt-001'],
        notes: ['roles 会被重写'],
      },
    };
    render(<Harness view={view} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    const t = dlgText();
    expect(t).toContain('切换到方案 economy？');
    expect(t).toContain('将运行的命令');
    expect(t).toContain('config preset use economy');
    expect(t).toContain('变化');
    expect(t).toContain('execution');
    expect(t).toContain('step-high');
    expect(t).toContain('step-low');
    expect(t).toContain('影响与风险');
    expect(t).toContain('WARN 有一个 attempt 在运行');
    expect(t).toContain('ui-readonly-api/attempt-001');
    expect(t).toContain('roles 会被重写');
    expect(btn(dlg() as HTMLElement, '取消')).toBeTruthy();
    expect(btn(dlg() as HTMLElement, '确认…')).toBeTruthy();
    expect(t).not.toContain('删除');
    expect(t).not.toContain('回滚');
    expect(t).not.toContain('不再询问');
    expect(Array.from((dlg() as HTMLElement).querySelectorAll('button')).some((b) => b.getAttribute('data-variant') === 'danger')).toBe(false);
  });

  it('变化区为空时写「预览没有列出变化」，不出现「没有变化」（W3b）', () => {
    const view: FlowView = { phase: 'confirmable', content: { ...CONTENT, changes: [] } };
    render(<Harness view={view} title="启用插件 code-change？" />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    const t = dlgText();
    expect(t).toContain('预览没有列出变化');
    expect(t, 'W3b：不许出现「没有变化」这个子串').not.toContain('没有变化');
    expect(t).not.toContain('影响与风险');
  });

  it('没有运行中的 attempt、没有 WARN 与备注时不画「影响与风险」小节', () => {
    render(<Harness view={{ phase: 'confirmable', content: CONTENT }} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    expect(dlgText()).not.toContain('影响与风险');
  });
});

describe('报错与 WARN 按纯文本显示（D13）', () => {
  it('失败：内核报错原文在 pre 里，<b>x</b> 原样显示成文字，另有原因标签', () => {
    const view: FlowView = { phase: 'failed', error: 'ERROR 内核拒绝：<b>x</b>', reason: '内核拒绝' };
    render(<Harness view={view} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    const d = dlg() as HTMLElement;
    const t = text(d);
    expect(t).toContain('ERROR 内核拒绝：<b>x</b>');
    expect(t).toContain('内核拒绝');
    expect(d.querySelector('b'), '不生成元素').toBeNull();
    expect(d.querySelector('pre')?.textContent).toContain('ERROR 内核拒绝：<b>x</b>');
    expect(btn(d, '重新预览')).toBeTruthy();
    expect(btn(d, '关闭')).toBeTruthy();
  });

  it('完成但有警告：warning 条列出 WARN 行，<b>x</b> 也是文字，按钮 [知道了]', () => {
    const view: FlowView = { phase: 'doneWithWarning', warnings: ['WARN 有一条 <b>x</b>'] };
    render(<Harness view={view} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    const d = dlg() as HTMLElement;
    expect(text(d)).toContain('WARN 有一条 <b>x</b>');
    expect(d.querySelector('b')).toBeNull();
    expect(d.querySelector('[data-tone="warning"]')).not.toBeNull();
    expect(btn(d, '知道了')).toBeTruthy();
  });

  it('成功但重读失败：warning 条写「命令已成功，但重新读取失败，请刷新」', () => {
    render(<Harness view={{ phase: 'rereadFailed', warnings: [] }} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    expect(dlgText()).toContain('命令已成功，但重新读取失败，请刷新');
    expect(btn(dlg() as HTMLElement, '关闭')).toBeTruthy();
  });

  it('已部分写入与结果未知各有各的按钮', () => {
    render(<Harness view={{ phase: 'partiallyWritten', error: 'ERROR 内核拒绝', reason: '内核拒绝' }} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    expect(dlgText()).toContain('已部分写入，结果待核实');
    expect(btn(dlg() as HTMLElement, '查看历史')).toBeTruthy();
    cleanup();
    render(<Harness view={{ phase: 'unknown' }} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    expect(dlgText()).toContain('结果未知，请在历史与审计里核对');
    expect(btn(dlg() as HTMLElement, '打开历史')).toBeTruthy();
  });

  it('两种 409 文案不同，都只有 [重新预览]', () => {
    render(<Harness view={{ phase: 'stale' }} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    expect(dlgText()).toContain('配置在你确认之前被改动了，请重新预览');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    cleanup();
    render(<Harness view={{ phase: 'expired' }} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    expect(dlgText()).toContain('确认已失效');
    expect(dlgText()).not.toContain('配置在你确认之前被改动了');
  });
});

describe('执行中关不掉（D08、M14–M16）', () => {
  const executing: FlowView = { phase: 'executing', content: CONTENT };

  it('Esc、点遮罩、[取消]、头部关闭钮都不关框；外层抽屉也不关', async () => {
    const onDrawerClose = vi.fn();
    const view = executing;
    render(
      <>
        <button type="button" onClick={noop}>
          打开
        </button>
        <Drawer open onClose={onDrawerClose} title="抽屉">
          <WriteConfirmDialog
            open
            title="切换到方案 economy？"
            view={view}
            onCancel={noop}
            onConfirm={noop}
            onRepreview={noop}
            onAck={noop}
            onHistory={noop}
          />
        </Drawer>
      </>,
    );
    const d = dlg() as HTMLElement;
    expect(d, '执行中框开着').not.toBeNull();
    expect(btn(d, '取消')?.disabled, '[取消] 禁用（M16）').toBe(true);
    const confirmBtn = Array.from(d.querySelectorAll('button')).find((b) => b.getAttribute('aria-busy') === 'true') as HTMLButtonElement;
    expect(confirmBtn, '确认钮转圈').toBeTruthy();
    expect(text(confirmBtn), '转圈时写 loadingText').toBe('执行中…');
    expect(closeBtn().disabled, '头部关闭钮禁用').toBe(true);
    fireEvent.keyDown(d, { key: 'Escape' });
    await act(async () => {
      for (let i = 0; i < 12; i += 1) await Promise.resolve();
    });
    expect(dlg(), 'Esc 不关框（M14）').not.toBeNull();
    expect(onDrawerClose, '外层抽屉也不关').not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"][aria-modal="false"]'), '外层抽屉还在').not.toBeNull();
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    expect(scrim, '应有遮罩').not.toBeNull();
    fireEvent.mouseDown(scrim);
    fireEvent.click(scrim);
    await act(async () => {
      for (let i = 0; i < 12; i += 1) await Promise.resolve();
    });
    expect(dlg(), '点遮罩不关框（M15）').not.toBeNull();
  });

  it('确认结果中与重读中同样关不掉', async () => {
    for (const phase of ['confirming', 'rereading'] as const) {
      render(<Harness view={{ phase, content: CONTENT }} />);
      fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
      const d = dlg() as HTMLElement;
      fireEvent.keyDown(d, { key: 'Escape' });
      await act(async () => {
        for (let i = 0; i < 12; i += 1) await Promise.resolve();
      });
      expect(dlg(), `${phase} 时 Esc 不关框`).not.toBeNull();
      expect(btn(d, '取消')?.disabled).toBe(true);
      cleanup();
    }
  });

  it('可确认状态 Esc 与遮罩照旧关框（dismissible 缺省 true）', async () => {
    render(<Harness view={{ phase: 'confirmable', content: CONTENT }} />);
    const trigger = btn(document.body, '打开') as HTMLButtonElement;
    act(() => { trigger.focus(); });
    fireEvent.click(trigger);
    const d = dlg() as HTMLElement;
    expect(d).not.toBeNull();
    expect(document.activeElement === d || d.contains(document.activeElement), '打开后焦点进框').toBe(true);
    fireEvent.keyDown(d, { key: 'Escape' });
    await act(async () => {
      for (let i = 0; i < 12; i += 1) await Promise.resolve();
    });
    expect(dlg(), '可确认时 Esc 照旧关框').toBeNull();
    expect(document.activeElement, '关框后焦点还给触发按钮').toBe(trigger);
  });

  it('框内 Tab 照旧困在框里（焦点陷阱不变）', () => {
    render(<Harness view={{ phase: 'executing', content: CONTENT }} />);
    fireEvent.click(btn(document.body, '打开') as HTMLButtonElement);
    const d = dlg() as HTMLElement;
    const inner = Array.from(d.querySelectorAll('button')).find((b) => !(b as HTMLButtonElement).disabled) as HTMLElement;
    inner.focus();
    fireEvent.keyDown(d, { key: 'Tab' });
    expect(document.activeElement === inner || d.contains(document.activeElement), '焦点仍在框内').toBe(true);
  });
});
