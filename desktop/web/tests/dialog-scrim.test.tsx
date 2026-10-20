import { useState } from 'react';
import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Dialog } from '../src/components/Dialog';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function Harness({ onClose }: { onClose: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" id="t" onClick={() => setOpen(true)}>打开</button>
      <Dialog open={open} onClose={() => { onClose(); setOpen(false); }} title="表单"
        footer={<><button type="button">取消</button><button type="button">确定</button></>}>
        <p id="body">正文</p>
        <input id="name" aria-label="名称" />
      </Dialog>
    </div>
  );
}
function openIt() {
  const onClose = vi.fn();
  const r = render(<Harness onClose={onClose} />);
  const trigger = r.container.querySelector('#t') as HTMLButtonElement;
  act(() => { trigger.focus(); });
  fireEvent.click(trigger);
  const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
  const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
  return { ...r, dialog, scrim, onClose };
}

describe('对话框遮罩（T005 7.1）', () => {
  it('框内输入框上的 mousedown 不被阻止，输入框能聚焦', () => {
    const { dialog } = openIt();
    const input = dialog.querySelector('#name') as HTMLInputElement;
    expect(fireEvent.mouseDown(input), '框内输入框上的 mousedown 不该被 preventDefault').toBe(true);
    act(() => { input.focus(); });
    expect(document.activeElement).toBe(input);
  });

  it('框内正文、标题、对话框根、正文容器、底栏按钮上的 mousedown 都不被阻止', () => {
    const { dialog } = openIt();
    const targets = [
      dialog,
      dialog.querySelector('#body') as Element,
      dialog.querySelector('h2') as Element,
      dialog.querySelector('.tt-dialog__body') as Element,
      Array.from(dialog.querySelectorAll('button')).find((b) => (b.textContent || '').trim() === '确定') as Element,
    ];
    for (const el of targets) {
      expect(el).toBeTruthy();
      expect(fireEvent.mouseDown(el), '框内 mousedown 不该被阻止').toBe(true);
    }
  });

  it('遮罩本身上的 mousedown 仍被阻止，点遮罩不关闭', () => {
    const { scrim, onClose } = openIt();
    expect(fireEvent.mouseDown(scrim), '遮罩本身的 mousedown 应被 preventDefault').toBe(false);
    fireEvent.click(scrim);
    expect(onClose).not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
  });
});
