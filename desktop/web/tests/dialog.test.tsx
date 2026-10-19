import { useState } from 'react';
import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Dialog } from '../src/components/Dialog';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const FOOTER = (<><button type="button">取消</button><button type="button">确定</button></>);
function key(k: string, init: Record<string, unknown> = {}) {
  return fireEvent.keyDown(document.activeElement as Element, { key: k, ...init });
}
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), '
  + 'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
function focusables(root: Element) {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.hasAttribute('hidden'));
}

function Harness({ onClose }: { onClose: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" id="t" onClick={() => setOpen(true)}>打开</button>
      <Dialog open={open} onClose={() => { onClose(); setOpen(false); }} title="确认操作" footer={FOOTER}>
        <p>正文</p>
        <input aria-label="名称" />
      </Dialog>
    </div>
  );
}
function openDialog() {
  const onClose = vi.fn();
  const r = render(<Harness onClose={onClose} />);
  const trigger = r.container.querySelector('#t') as HTMLButtonElement;
  act(() => { trigger.focus(); });
  fireEvent.click(trigger);
  const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
  return { ...r, trigger, onClose, dialog };
}

describe('Dialog', () => {
  it('open 为 false 时不渲染', () => {
    render(<Dialog open={false} onClose={() => {}} title="标题">内容</Dialog>);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector('.tt-dialog-scrim')).toBeNull();
  });

  it('role=dialog、aria-modal=true、aria-labelledby 指向 h2，带 tt-dialog/tt-enter/tt-fc，遮罩含它', () => {
    const { dialog } = openDialog();
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const labelId = dialog.getAttribute('aria-labelledby')!;
    const title = document.getElementById(labelId)!;
    expect(title.tagName).toBe('H2');
    expect((title.textContent || '').trim()).toBe('确认操作');
    expect(dialog.classList.contains('tt-dialog')).toBe(true);
    expect(dialog.classList.contains('tt-enter')).toBe(true);
    expect(dialog.classList.contains('tt-fc')).toBe(true);
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    expect(scrim.contains(dialog)).toBe(true);
  });

  it('打开时焦点进框内第一个可聚焦元素（关闭钮「关闭（Esc）」）', () => {
    const { dialog } = openDialog();
    const list = focusables(dialog);
    expect(document.activeElement).toBe(list[0]);
    expect(list[0].getAttribute('aria-label')).toBe('关闭（Esc）');
  });

  it('焦点陷阱：末元素 Tab 回首、首元素 Shift+Tab 到末，均 preventDefault', () => {
    const { dialog } = openDialog();
    const list = focusables(dialog);
    const first = list[0];
    const last = list[list.length - 1];
    expect((last.textContent || '').trim()).toBe('确定');
    act(() => { last.focus(); });
    expect(key('Tab')).toBe(false);
    expect(document.activeElement).toBe(first);
    expect(key('Tab', { shiftKey: true })).toBe(false);
    expect(document.activeElement).toBe(last);
  });

  it('Esc 调一次 onClose、消失、焦点回触发按钮', () => {
    const { dialog, trigger, onClose } = openDialog();
    act(() => { (dialog.querySelector('input') as HTMLElement).focus(); });
    key('Escape');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('关闭钮关闭并还焦点；点遮罩不关闭', () => {
    const { dialog, trigger, onClose } = openDialog();
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    expect(fireEvent.mouseDown(scrim)).toBe(false);
    fireEvent.click(scrim);
    expect(onClose).not.toHaveBeenCalled();
    const close = dialog.querySelector('[aria-label="关闭（Esc）"]') as HTMLElement;
    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('卸载时也把焦点还给打开前的元素', () => {
    function Toggle() {
      const [mounted, setMounted] = useState(false);
      return (
        <div>
          <button type="button" id="t" onClick={() => setMounted(true)}>开</button>
          <button type="button" id="r" onClick={() => setMounted(false)}>拆</button>
          {mounted && (<Dialog open onClose={() => {}} title="T"><input aria-label="名称" /></Dialog>)}
        </div>
      );
    }
    const r = render(<Toggle />);
    const trigger = r.container.querySelector('#t') as HTMLButtonElement;
    act(() => { trigger.focus(); });
    fireEvent.click(trigger);
    expect((document.querySelector('[role="dialog"]') as HTMLElement).contains(document.activeElement)).toBe(true);
    fireEvent.click(r.container.querySelector('#r') as Element);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
