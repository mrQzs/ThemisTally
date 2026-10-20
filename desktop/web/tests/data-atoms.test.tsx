import { cleanup, render, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { KeyValueList } from '../src/components/KeyValueList';
import { EmptyState } from '../src/components/EmptyState';
import { Breadcrumb } from '../src/components/Breadcrumb';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('键值列表', () => {
  it('dl 里每项一对 dt、dd，顺序对；mono 值结构不同', () => {
    const { container } = render(
      <KeyValueList items={[
        { label: '分支', value: 'main' },
        { label: '提交', value: 'a1b2c3d', mono: true },
        { label: '状态', value: '已通过' },
      ]} />,
    );
    const dl = container.querySelector('dl')!;
    const dts = Array.from(dl.querySelectorAll('dt')).map((el) => (el.textContent || '').trim());
    const dds = Array.from(dl.querySelectorAll('dd')).map((el) => (el.textContent || '').trim());
    expect(dts).toEqual(['分支', '提交', '状态']);
    expect(dds).toEqual(['main', 'a1b2c3d', '已通过']);
    const ddList = Array.from(dl.querySelectorAll('dd'));
    expect(ddList[1].className).not.toBe(ddList[0].className);
  });
});

describe('空状态', () => {
  it('缺省 ListChecksIcon aria-hidden、标题说明与操作区；无 action 不留空元素', () => {
    const onClick = vi.fn();
    const withAction = render(
      <EmptyState title="还没有任务" description="创建第一个任务开始"
        action={<button type="button" onClick={onClick}>新建任务</button>} />,
    );
    const svg = withAction.container.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(Array.from(svg.querySelectorAll('path')).length).toBe(5);
    const btn = withAction.container.querySelector('button') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
    withAction.unmount();

    const bare = render(<EmptyState title="还没有任务" description="创建第一个任务开始" />);
    const empties = Array.from(bare.container.querySelectorAll('*')).filter(
      (el) => !el.closest('svg') && el.children.length === 0 && (el.textContent || '').trim() === '',
    );
    expect(empties.length).toBe(0);
    expect(bare.container.querySelectorAll('button').length).toBe(0);
  });
});

describe('面包屑', () => {
  it('nav 面包屑、前项 a/button、末项 span aria-current=page、分隔图标 aria-hidden', () => {
    const onClick = vi.fn();
    const { container } = render(
      <Breadcrumb items={[
        { label: '项目', href: '/projects' },
        { label: '任务', onClick },
        { label: '详情' },
      ]} />,
    );
    const nav = container.querySelector('nav')!;
    expect(nav.getAttribute('aria-label')).toBe('面包屑');
    expect(nav.querySelectorAll('ol').length).toBe(1);
    const link = nav.querySelector('a') as HTMLAnchorElement;
    expect((link.textContent || '').trim()).toBe('项目');
    const btn = nav.querySelector('button') as HTMLButtonElement;
    expect(btn.getAttribute('type')).toBe('button');
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(Array.from(nav.querySelectorAll('svg')).every((s) => s.getAttribute('aria-hidden') === 'true')).toBe(true);
    const current = container.querySelectorAll('[aria-current]');
    expect(current.length).toBe(1);
    expect(current[0].getAttribute('aria-current')).toBe('page');
    expect(current[0].tagName).toBe('SPAN');
    expect(current[0].closest('a, button')).toBeNull();
  });
});
