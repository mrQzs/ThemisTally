import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const DEMOS = ['icon-button', 'menu', 'dialog', 'drawer', 'toast'];
function textOf(el: Element | null) { return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim(); }
function demo(name: string) {
  const nodes = document.querySelectorAll(`[data-demo="${name}"]`);
  expect(nodes.length, `应恰有一个 data-demo="${name}"`).toBe(1);
  return nodes[0] as HTMLElement;
}
function buttonByText(root: Element, text: string) {
  const hit = Array.from(root.querySelectorAll('button')).find((b) => textOf(b) === text);
  expect(hit, `找不到文字为「${text}」的按钮`).toBeTruthy();
  return hit as HTMLButtonElement;
}
function press(btn: HTMLElement) { act(() => { btn.focus(); }); fireEvent.click(btn); }
function key(k: string) { return fireEvent.keyDown(document.activeElement as Element, { key: k }); }

describe('陈列页的 5 节浮层演示', () => {
  it('5 个 data-demo 节都在，顺序是图标按钮、菜单、对话框、抽屉、轻提示', () => {
    render(<App />);
    const secs = DEMOS.map(demo);
    for (let i = 1; i < secs.length; i += 1) {
      expect(secs[i - 1].compareDocumentPosition(secs[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it('图标按钮演示有 3 个只有图标的按钮、其一禁用；页面上无文字的按钮都有 aria-label', () => {
    render(<App />);
    const sec = demo('icon-button');
    const iconOnly = Array.from(sec.querySelectorAll('button')).filter((b) => textOf(b) === '');
    expect(iconOnly.length).toBeGreaterThanOrEqual(3);
    expect(iconOnly.some((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    const bad = Array.from(document.querySelectorAll('button'))
      .filter((b) => textOf(b) === '')
      .filter((b) => !(b.getAttribute('aria-label') || '').trim());
    expect(bad.length).toBe(0);
  });

  it('菜单演示：「更多操作」打开菜单，Enter 选中后「上次选择：」变化', () => {
    render(<App />);
    const sec = demo('menu');
    const last = () => textOf(sec).split('上次选择：')[1];
    const before = last();
    expect(before).not.toBeUndefined();
    press(buttonByText(sec, '更多操作'));
    expect(document.querySelector('[role="menu"]')).not.toBeNull();
    key('Enter');
    expect(document.querySelector('[role="menu"]')).toBeNull();
    const after = last();
    expect(after).not.toBe('');
    expect(after).not.toBe(before);
  });

  it('对话框演示：「打开对话框」出现模态框，取消后焦点回触发按钮', () => {
    render(<App />);
    const sec = demo('dialog');
    const trigger = buttonByText(sec, '打开对话框');
    press(trigger);
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    buttonByText(dialog, '确定');
    fireEvent.click(buttonByText(dialog, '取消'));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('抽屉演示：「打开抽屉」出现非模态，Esc 关闭并回触发按钮', () => {
    render(<App />);
    const sec = demo('drawer');
    const trigger = buttonByText(sec, '打开抽屉');
    press(trigger);
    const drawer = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(drawer.getAttribute('aria-modal')).toBe('false');
    expect(drawer.querySelectorAll('button').length).toBeGreaterThanOrEqual(2);
    key('Escape');
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('轻提示演示：「弹出轻提示」后 role=status 出现文字与关闭钮，点关闭清空', () => {
    render(<App />);
    const sec = demo('toast');
    const status = document.querySelector('[role="status"]') as HTMLElement;
    expect(textOf(status)).toBe('');
    press(buttonByText(sec, '弹出轻提示'));
    expect(textOf(status)).not.toBe('');
    fireEvent.click(status.querySelector('button[aria-label="关闭提示"]') as HTMLElement);
    expect(textOf(status)).toBe('');
  });
});
