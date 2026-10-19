// 陈列页字体样张：三组字重、每组四行、每行去两端 | 后 26 列（汉字 2 列 + ASCII 1 列），守住样张结构（T003）。
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import App from '../src/App';

afterEach(cleanup);

// 与 App.tsx 里约定的四行样张一致（不含两端 |）。
const SPECIMENS = [
  '一个汉字正好两个英文字符宽',
  'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  '12345678901234567890123456',
  '日志 attempt-001 已通过 OK',
];
const LABELS = ['Regular 400', '500 按 Regular', 'SemiBold 600'];

// 汉字算 2 列，可打印 ASCII 算 1 列。
function columns(text: string): number {
  let n = 0;
  for (const ch of text) n += /[\u4e00-\u9fff]/.test(ch) ? 2 : 1;
  return n;
}

describe('陈列页字体样张', () => {
  it('节根带 data-font-specimen 属性', () => {
    const { container } = render(<App />);
    expect(container.querySelector('[data-font-specimen]')).not.toBeNull();
  });

  it('400、500、600 三组字重都存在，组旁标签符合约定', () => {
    const { container } = render(<App />);
    const weights = Array.from(container.querySelectorAll('[data-font-weight]')).map((el) =>
      el.getAttribute('data-font-weight'),
    );
    expect(weights).toEqual(['400', '500', '600']);
    const labels = Array.from(
      container.querySelectorAll('[data-font-specimen] .showcase__label'),
    ).map((el) => el.textContent);
    expect(labels).toEqual(LABELS);
  });

  it('每组四行，每行去两端 | 后都是 26 列，且含汉字行与 ASCII 行', () => {
    const { container } = render(<App />);
    const groups = container.querySelectorAll('[data-font-weight]');
    expect(groups).toHaveLength(3);
    for (const group of groups) {
      const rows = group.querySelectorAll('[data-specimen-row]');
      expect(rows).toHaveLength(4);
      let hasCjk = false;
      let hasAsciiLetters = false;
      for (const row of rows) {
        const text = row.textContent ?? '';
        expect(text.startsWith('|')).toBe(true);
        expect(text.endsWith('|')).toBe(true);
        expect(columns(text.slice(1, -1))).toBe(26);
        if (/[\u4e00-\u9fff]/.test(text)) hasCjk = true;
        if (/[A-Za-z]/.test(text)) hasAsciiLetters = true;
      }
      expect(hasCjk).toBe(true);
      expect(hasAsciiLetters).toBe(true);
    }
  });

  it('三组样张文字与约定一致', () => {
    const { container } = render(<App />);
    for (const weight of ['400', '500', '600']) {
      const rows = container.querySelectorAll(`[data-font-weight="${weight}"] [data-specimen-row]`);
      const got = Array.from(rows).map((r) => (r.textContent ?? '').slice(1, -1));
      expect(got).toEqual(SPECIMENS);
    }
  });
});
