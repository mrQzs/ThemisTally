import { useState } from 'react';
import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Drawer } from '../src/components/Drawer';

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
      <Drawer open={open} onClose={() => { onClose(); setOpen(false); }} title="详情" footer={FOOTER}>
        <p>说明</p>
        <input aria-label="备注" />
      </Drawer>
    </div>
  );
}
function openDrawer() {
  const onClose = vi.fn();
  const r = render(<Harness onClose={onClose} />);
  const trigger = r.container.querySelector('#t') as HTMLButtonElement;
  act(() => { trigger.focus(); });
  fireEvent.click(trigger);
  const drawer = document.querySelector('[role="dialog"]') as HTMLElement;
  return { ...r, trigger, onClose, drawer };
}

describe('Drawer', () => {
  it('role=dialog、aria-modal=false、aria-labelledby 指向标题，带 tt-drawer/tt-drawer-in/tt-fc，没有遮罩', () => {
    const { drawer } = openDrawer();
    expect(drawer.getAttribute('aria-modal')).toBe('false');
    const title = document.getElementById(drawer.getAttribute('aria-labelledby')!)!;
    expect((title.textContent || '').trim()).toBe('详情');
    expect(drawer.classList.contains('tt-drawer')).toBe(true);
    expect(drawer.classList.contains('tt-drawer-in')).toBe(true);
    expect(drawer.classList.contains('tt-fc')).toBe(true);
    expect(document.querySelector('[class*="scrim"]')).toBeNull();
    expect(document.querySelector('[aria-modal="true"]')).toBeNull();
  });

  it('打开时焦点进抽屉第一个可聚焦元素', () => {
    const { drawer } = openDrawer();
    expect(document.activeElement).toBe(focusables(drawer)[0]);
  });

  it('不困焦点：末元素 Tab、首元素 Shift+Tab 都不被拦', () => {
    const { drawer } = openDrawer();
    const list = focusables(drawer);
    act(() => { list[list.length - 1].focus(); });
    expect(key('Tab')).toBe(true);
    expect(document.activeElement).toBe(list[list.length - 1]);
    act(() => { list[0].focus(); });
    expect(key('Tab', { shiftKey: true })).toBe(true);
    expect(document.activeElement).toBe(list[0]);
  });

  it('Esc 关闭并还焦点；点抽屉外不关闭', () => {
    const { drawer, trigger, onClose } = openDrawer();
    fireEvent.mouseDown(document.body);
    fireEvent.click(document.body);
    expect(onClose).not.toHaveBeenCalled();
    act(() => { (drawer.querySelector('input') as HTMLElement).focus(); });
    key('Escape');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });
});
