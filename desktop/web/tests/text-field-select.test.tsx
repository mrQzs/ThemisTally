import * as React from 'react';
import { cleanup, render, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TextField } from '../src/components/TextField';
import { Select } from '../src/components/Select';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

const OPTIONS = [
  { value: 'dev', label: '开发' },
  { value: 'prod', label: '生产' },
  { value: 'test', label: '测试' },
];
function describedTexts(el: HTMLElement): string[] {
  return (el.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean)
    .map((id) => (document.getElementById(id)?.textContent || '').trim());
}
function mountField(props: any = {}) {
  const r = render(<TextField label="用户名" value="" onChange={() => {}} {...props} />);
  return { ...r, input: r.container.querySelector('input') as HTMLInputElement, label: r.container.querySelector('label') as HTMLLabelElement };
}
function SelectShell({ onChange, ...rest }: any) {
  const [v, setV] = React.useState('dev');
  return <Select label="环境" options={OPTIONS} value={v}
    onChange={(arg: any) => { onChange(arg); setV(typeof arg === 'string' ? arg : arg.target.value); }} {...rest} />;
}
function mountSelect(props: any = {}) {
  const onChange = vi.fn();
  const r = render(<SelectShell onChange={onChange} {...props} />);
  return { ...r, select: r.container.querySelector('select') as HTMLSelectElement, onChange };
}

describe('输入框', () => {
  it('label 关联、placeholder/value/disabled 透传', () => {
    const { input, label } = mountField({ placeholder: '输入名称' });
    expect((label.textContent || '').trim()).toBe('用户名');
    expect(label.htmlFor).toBe(input.id);
    expect(input.getAttribute('placeholder')).toBe('输入名称');
    const d = mountField({ value: 'abc', disabled: true });
    expect(d.input.value).toBe('abc');
    expect(d.input.disabled).toBe(true);
  });

  it('aria-describedby 依次出错、帮助；出错 aria-invalid=true；mono 结构不同', () => {
    expect(describedTexts(mountField({ help: '三到十六个字符' }).input)).toEqual(['三到十六个字符']);
    const err = mountField({ error: '名称已被占用' });
    expect(describedTexts(err.input)).toEqual(['名称已被占用']);
    expect(err.input.getAttribute('aria-invalid')).toBe('true');
    const both = mountField({ help: '帮', error: '错' });
    expect(describedTexts(both.input)).toEqual(['错', '帮']);
    const none = mountField();
    expect((none.input.getAttribute('aria-describedby') || '').trim()).toBe('');
    const mono = mountField({ mono: true });
    expect(mono.input.className).not.toBe(none.input.className);
  });
});

describe('下拉', () => {
  it('原生 select、label 关联、选项与值、箭头 aria-hidden 不在 select 里', () => {
    const { select } = mountSelect();
    expect(select.tagName).toBe('SELECT');
    const options = Array.from(select.querySelectorAll('option'));
    expect(options.map((o) => o.getAttribute('value'))).toEqual(['dev', 'prod', 'test']);
    expect(options.map((o) => (o.textContent || '').trim())).toEqual(['开发', '生产', '测试']);
    expect(select.value).toBe('dev');
    const chevron = document.querySelector('svg[aria-hidden="true"]');
    expect(chevron).not.toBeNull();
    expect(select.contains(chevron)).toBe(false);
  });

  it('改选调 onChange；帮助与出错接线；disabled 透传', () => {
    const a = mountSelect();
    fireEvent.change(a.select, { target: { value: 'prod' } });
    expect(a.onChange).toHaveBeenCalledTimes(1);
    expect(a.select.value).toBe('prod');
    const b = mountSelect({ help: '决定部署位置', error: '请选择生产以外的环境' });
    expect(describedTexts(b.select)).toEqual(['请选择生产以外的环境', '决定部署位置']);
    expect(b.select.getAttribute('aria-invalid')).toBe('true');
    const c = mountSelect({ disabled: true });
    expect(c.select.disabled).toBe(true);
  });
});
