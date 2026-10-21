// 凭据页视图自测（合同 D01）：四列、没有「值」列、用在哪里合并、来源四种取值、遮蔽占位、禁用录入、说明与来源小节。
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { CircleXIcon } from '../src/icons';
import { SecretsIcon } from '../src/icons/frame';
import { SecretsView } from '../src/pages/readonly2/secrets-SecretsView';
import type { SecretsData } from '../src/api';

afterEach(cleanup);

const DATA: SecretsData = {
  secrets: [
    { name: 'A_ENV', used_by: [{ kind: 'profile', id: 'p1' }, { kind: 'profile', id: 'p2' }, { kind: 'decisions' }], source: 'env' },
    { name: 'B_STORE', used_by: [{ kind: 'decisions' }, { kind: 'profile', id: 'p3' }, { kind: 'weird', id: 'w1' }, { kind: 'weird2' }], source: 'credential_store' },
    { name: 'C_FILE', used_by: [{ kind: 'profile', id: 'p1' }, { kind: 'decisions' }, { kind: 'profile', id: 'p2' }], source: 'file' },
    { name: 'D_NONE', used_by: [], source: 'none' },
    { name: 'E_VAULT', used_by: [{ kind: 'profile', id: '（值不显示）' }], source: 'vault' },
    { name: '（疑似凭据的键名）', used_by: [{ kind: 'profile', id: '<redacted>' }], source: 'env' },
  ],
} as unknown as SecretsData;

function mount() {
  const out = render(<SecretsView data={DATA} />);
  const table = out.container.querySelector('table[aria-label="凭据变量"]') as HTMLTableElement;
  return { ...out, table, rows: Array.from(table.querySelectorAll('tbody tr')) };
}
const cells = (row: Element) => Array.from(row.querySelectorAll('td'));
const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const rowByName = (rows: Element[], name: string) =>
  rows.find((r) => text(cells(r)[0]).includes(name)) as HTMLElement;

describe('凭据页：表', () => {
  it('四列、没有「值」列、rowHeight 44、每个变量一行', () => {
    const { table, rows } = mount();
    expect(Array.from(table.querySelectorAll('thead th')).map((th) => text(th))).toEqual(['变量名', '用在哪里', '来源', '操作']);
    expect(table.getAttribute('data-row-height')).toBe('44');
    expect(rows).toHaveLength(6);
    expect(Array.from(table.querySelectorAll('th, td')).some((c) => text(c) === '值')).toBe(false);
  });

  it('用在哪里按出现顺序、相邻 profile 合并、决策模型、未知 kind 原样带 id', () => {
    const { rows } = mount();
    expect(text(cells(rowByName(rows, 'A_ENV'))[1])).toBe('profile p1、p2、决策模型');
    expect(text(cells(rowByName(rows, 'B_STORE'))[1])).toBe('决策模型、profile p3、weird w1、weird2');
    expect(text(cells(rowByName(rows, 'C_FILE'))[1])).toBe('profile p1、决策模型、profile p2');
  });

  it('遮蔽占位用 span.tt-masked，只有变量名与 id 三处', () => {
    const { rows, container } = mount();
    const masked = Array.from(container.querySelectorAll('span.tt-masked'));
    expect(masked.map((m) => text(m))).toEqual(['（值不显示）', '（疑似凭据的键名）', '<redacted>']);
    for (const m of masked) expect(m.getAttribute('title')).toBe('内核已遮蔽');
    expect(text(cells(rowByName(rows, 'A_ENV'))[0]).includes('（')).toBe(false);
  });

  it('来源四种取值与未知值的文字、tone、图标、data-source', () => {
    const { rows } = mount();
    const cases: [string, string, string, string, typeof CircleXIcon | null][] = [
      ['A_ENV', 'env', '环境变量', 'success', null],
      ['B_STORE', 'credential_store', '系统凭据库', 'success', SecretsIcon],
      ['C_FILE', 'file', '0600 文件', 'success', null],
      ['D_NONE', 'none', '没有', 'danger', CircleXIcon],
      ['E_VAULT', 'vault', 'vault', 'neutral', null],
    ];
    for (const [name, source, label, tone] of cases) {
      const tag = cells(rowByName(rows, name))[2].querySelector('[data-source]') as HTMLElement;
      expect(tag, name).not.toBeNull();
      expect(tag.getAttribute('data-source')).toBe(source);
      expect(text(tag)).toBe(label);
      expect(tag.getAttribute('data-tone')).toBe(tone);
      const svg = tag.querySelector('svg');
      if (name === 'B_STORE') expect(svg?.getAttribute('width')).toBe('14');
      if (name === 'D_NONE') expect(svg?.getAttribute('width')).toBe('14');
      if (name === 'A_ENV' || name === 'C_FILE' || name === 'E_VAULT') expect(svg).toBeNull();
    }
  });

  it('每行一个禁用的 [录入…]；单元格里没有可聚焦元素', () => {
    const { table, rows } = mount();
    for (const r of rows) {
      const btn = cells(r)[3].querySelector('button') as HTMLButtonElement;
      expect(text(btn)).toBe('录入…');
      expect(btn.disabled).toBe(true);
      expect(btn.getAttribute('data-variant')).toBe('secondary');
      expect(btn.getAttribute('data-size')).toBe('sm');
      expect(btn.querySelector('svg')?.getAttribute('width')).toBe('14');
    }
    expect(table.querySelectorAll('tbody td a, tbody td input, tbody td select, tbody td [tabindex]').length).toBe(0);
    expect(table.querySelectorAll('tbody td button:not(:disabled)').length).toBe(0);
  });
});

describe('凭据页：说明、小节与视图结构', () => {
  it('表后一条不可关的 info 说明（不是 Banner、没有 role 与关闭钮）', () => {
    const { container, table } = mount();
    const note = Array.from(container.querySelectorAll('*')).find(
      (e) => text(e) === '录入只在单独的一次性页面里进行，值直接存进系统凭据库；这个界面拿不到值。',
    ) as HTMLElement;
    expect(note).toBeTruthy();
    expect(note.closest('.tt-banner')).toBeNull();
    expect(container.querySelector('button[aria-label="关闭提示"]')).toBeNull();
    expect(container.querySelector('[role="status"], [role="alert"]')).toBeNull();
    expect(table.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('「“来源”标签」小节列出四个标签，在表后', () => {
    const { container, table } = mount();
    const sec = Array.from(container.querySelectorAll('section')).find((s) => {
      const id = s.getAttribute('aria-labelledby');
      const h = id ? document.getElementById(id) : null;
      return !!h && h.tagName === 'H2' && text(h).includes('来源') && text(h).includes('标签');
    }) as HTMLElement;
    expect(sec).toBeTruthy();
    for (const label of ['环境变量', '系统凭据库', '0600 文件', '没有']) expect(text(sec)).toContain(label);
    expect(table.compareDocumentPosition(sec) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('视图根 data-page=secrets：不写 data-page-state、不渲染 h1、没有内联 style', () => {
    const { container } = mount();
    const root = container.querySelector('[data-page="secrets"]') as HTMLElement;
    expect(root).not.toBeNull();
    expect(root.hasAttribute('data-page-state')).toBe(false);
    expect(root.querySelector('[data-page-state]')).toBeNull();
    expect(root.querySelector('h1')).toBeNull();
    expect(root.querySelector('[style]')).toBeNull();
    for (const s of Array.from(root.querySelectorAll('section'))) {
      const id = s.getAttribute('aria-labelledby');
      expect(id).toBeTruthy();
      expect(document.getElementById(id as string)?.tagName).toBe('H2');
    }
  });
});
