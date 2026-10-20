// ShellMenu（合同第 3 条 / P6、D02）：面板 role=menu 带 aria-label；单选项 menuitemradio 带 aria-checked、
// 禁用项 aria-disabled；打开后焦点到第一项，方向键循环、Home/End 到首尾、Enter 选中并还焦点、Esc 关并还焦点；
// 禁用项选不中、菜单也不关；分组标题与分隔线不可聚焦。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { Button } from '../src/components';
import { ShellMenu, type ShellMenuItem } from '../src/shell/ShellMenu';

afterEach(cleanup);

function focus(el: HTMLElement) { act(() => { el.focus(); }); }

function items(checked: string): ShellMenuItem[] {
  return [
    { kind: 'radio', id: 'a', label: '甲', checked: checked === 'a' },
    { kind: 'radio', id: 'b', label: '乙', checked: checked === 'b' },
    { kind: 'group', label: '分组标题' },
    { kind: 'item', id: 'c', label: '丙' },
    { kind: 'item', id: 'd', label: '丁（禁用）', disabled: true },
    { kind: 'separator' },
  ];
}

function Harness({ onSelect }: { onSelect: (id: string) => void }) {
  const [checked, setChecked] = useState('a');
  return (
    <ShellMenu
      label="测试菜单"
      onSelect={(id) => {
        onSelect(id);
        if (id === 'a' || id === 'b') setChecked(id);
      }}
      items={items(checked)}
    >
      {(trigger) => <Button {...trigger}>触发</Button>}
    </ShellMenu>
  );
}

const focusables = () =>
  Array.from(document.querySelectorAll<HTMLElement>('[role="menuitemradio"], [role="menuitem"]'));

describe('ShellMenu', () => {
  it('打开后面板带 aria-label、当前单选项 aria-checked、禁用项 aria-disabled', () => {
    const onSelect = vi.fn();
    const { getByText } = render(<Harness onSelect={onSelect} />);
    fireEvent.click(getByText('触发'));
    const menu = document.querySelector('[role="menu"]') as HTMLElement;
    expect(menu).not.toBeNull();
    expect(menu.getAttribute('aria-label')).toBe('测试菜单');
    expect(menu.querySelector('[role="menuitemradio"][aria-checked="true"]')?.textContent).toBe('甲');
    const disabled = Array.from(menu.querySelectorAll('[aria-disabled="true"]'));
    expect(disabled).toHaveLength(1);
    expect(disabled[0].textContent).toContain('丁');
    // 分组标题与分隔线不可聚焦
    expect(focusables()).toHaveLength(4);
  });

  it('打开后焦点到第一项；方向键循环、Home/End 到首尾', () => {
    const onSelect = vi.fn();
    const { getByText } = render(<Harness onSelect={onSelect} />);
    fireEvent.click(getByText('触发'));
    const els = focusables();
    expect(document.activeElement).toBe(els[0]);
    fireEvent.keyDown(els[0], { key: 'ArrowDown' });
    expect(document.activeElement).toBe(els[1]);
    fireEvent.keyDown(els[1], { key: 'ArrowDown' });
    expect(document.activeElement).toBe(els[2]);
    fireEvent.keyDown(els[2], { key: 'ArrowDown' });
    expect(document.activeElement).toBe(els[3]);
    fireEvent.keyDown(els[3], { key: 'ArrowDown' });
    expect(document.activeElement).toBe(els[0]); // 循环
    fireEvent.keyDown(els[0], { key: 'End' });
    expect(document.activeElement).toBe(els[3]);
    fireEvent.keyDown(els[3], { key: 'Home' });
    expect(document.activeElement).toBe(els[0]);
  });

  it('Enter 选中、关菜单、焦点回触发钮', () => {
    const onSelect = vi.fn();
    const { getByText } = render(<Harness onSelect={onSelect} />);
    const trigger = getByText('触发');
    fireEvent.click(trigger);
    const els = focusables();
    focus(els[1]);
    fireEvent.keyDown(els[1], { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('b');
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('Esc 关菜单、焦点回触发钮、不选中', () => {
    const onSelect = vi.fn();
    const { getByText } = render(<Harness onSelect={onSelect} />);
    const trigger = getByText('触发');
    fireEvent.click(trigger);
    const els = focusables();
    fireEvent.keyDown(els[0], { key: 'Escape' });
    expect(onSelect).not.toHaveBeenCalled();
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('禁用项 Enter 与点击都不选、菜单也不关', () => {
    const onSelect = vi.fn();
    const { getByText } = render(<Harness onSelect={onSelect} />);
    fireEvent.click(getByText('触发'));
    const els = focusables();
    focus(els[3]);
    fireEvent.keyDown(els[3], { key: 'Enter' });
    expect(onSelect).not.toHaveBeenCalled();
    expect(document.querySelector('[role="menu"]')).not.toBeNull();
    fireEvent.click(els[3]);
    expect(onSelect).not.toHaveBeenCalled();
    expect(document.querySelector('[role="menu"]')).not.toBeNull();
  });

  it('点击普通项选中并关闭', () => {
    const onSelect = vi.fn();
    const { getByText } = render(<Harness onSelect={onSelect} />);
    fireEvent.click(getByText('触发'));
    fireEvent.click(getByText('丙'));
    expect(onSelect).toHaveBeenCalledWith('c');
    expect(document.querySelector('[role="menu"]')).toBeNull();
  });
});
