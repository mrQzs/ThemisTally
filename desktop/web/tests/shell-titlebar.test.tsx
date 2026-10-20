// 标题栏（合同第 2 条 / D02）：Logo、产品名、连接胶囊都在；仓库菜单当前项 aria-checked=true、禁用项 aria-disabled=true；
// 主题菜单三个单选项、当前项带勾；选主题回调；Esc 后焦点回触发钮。
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TitleBar } from '../src/shell/TitleBar';

beforeEach(() => { location.hash = '#/overview'; });
afterEach(cleanup);

describe('标题栏', () => {
  it('Logo、产品名、连接胶囊都在', () => {
    const { getByLabelText, getByText, container } = render(
      <TitleBar theme="dark" onThemeChange={() => {}} repoName="demo-repo" />,
    );
    expect(getByLabelText('Themis Tally 标识')).toBeTruthy();
    const logo = container.querySelector('svg.tt-logo') as SVGElement;
    expect(logo.getAttribute('viewBox')).toBe('0 0 937 1079');
    // 产品名与仓库名都渲染（span 文本）
    expect(getByText('Themis Tally')).toBeTruthy();
    expect(getByText('demo-repo')).toBeTruthy();
    // 连接胶囊：默认 data（未 offline）为 connected
    expect(container.querySelector('.tt-pill[data-state="connected"]')).not.toBeNull();
  });

  it('仓库菜单：当前项 aria-checked=true、禁用项 aria-disabled=true，选别的只关菜单', () => {
    const { getByTitle, getByText, container } = render(
      <TitleBar theme="dark" onThemeChange={() => {}} repoName="demo-repo" />,
    );
    fireEvent.click(getByTitle('切换仓库'));
    const menu = container.querySelector('[role="menu"]') as HTMLElement;
    expect(menu.getAttribute('aria-label')).toBe('仓库');
    const checked = menu.querySelector('[role="menuitemradio"][aria-checked="true"]');
    expect(checked?.textContent).toContain('demo-repo');
    const docsSite = Array.from(menu.querySelectorAll('[role="menuitemradio"]')).find(
      (el) => el.textContent?.includes('docs-site'),
    );
    expect(docsSite?.getAttribute('aria-checked')).toBe('false');
    const disabled = menu.querySelector('[aria-disabled="true"]');
    expect(disabled?.textContent).toContain('添加仓库');
    // 选别的仓库只关菜单
    fireEvent.click(docsSite as HTMLElement);
    expect(container.querySelector('[role="menu"]')).toBeNull();
  });

  it('主题菜单三个单选项、当前偏好带勾，选择后回调', () => {
    const onThemeChange = vi.fn();
    const { getByLabelText, container } = render(
      <TitleBar theme="dark" onThemeChange={onThemeChange} repoName="demo-repo" />,
    );
    const trigger = getByLabelText('主题：暗');
    fireEvent.click(trigger);
    const menu = container.querySelector('[role="menu"]') as HTMLElement;
    expect(menu.getAttribute('aria-label')).toBe('主题');
    const radios = Array.from(menu.querySelectorAll('[role="menuitemradio"]')).map((el) => el.textContent);
    expect(radios).toEqual(['跟随系统', '亮', '暗']);
    expect(menu.querySelector('[aria-checked="true"]')?.textContent).toBe('暗');
    fireEvent.click(Array.from(menu.querySelectorAll('[role="menuitemradio"]')).find((el) => el.textContent === '亮') as HTMLElement);
    expect(onThemeChange).toHaveBeenCalledWith('light');
  });

  it('触发钮名称随偏好变；Esc 后焦点回触发钮', () => {
    const { getByLabelText, rerender } = render(
      <TitleBar theme="light" onThemeChange={() => {}} repoName="demo-repo" />,
    );
    const trigger = getByLabelText('主题：亮');
    fireEvent.click(trigger);
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' });
    expect(document.activeElement).toBe(trigger);
    rerender(<TitleBar theme="system" onThemeChange={() => {}} repoName="demo-repo" />);
    expect(getByLabelText('主题：跟随系统')).toBeTruthy();
  });

  it('offline 时连接胶囊 disconnected', () => {
    location.hash = '#/overview?mock=offline';
    const { container } = render(<TitleBar theme="dark" onThemeChange={() => {}} repoName="demo-repo" />);
    expect(container.querySelector('.tt-pill[data-state="disconnected"]')).not.toBeNull();
  });
});
