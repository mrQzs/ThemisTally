// 共用 CopyNote 与 copyText 的自测（T014 D03、D04）：三结果文字取自 COPY_RESULT_TEXT、null 不渲染、
// 类名 tt-copy-note、不设 role；copyText 三态与缺省取 navigator.clipboard。
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { CopyNote } from '../src/components/CopyNote';
import { COPY_RESULT_TEXT, copyText, type CopyResult } from '../src/components/copyText';

afterEach(cleanup);

const text = (el: Element | null | undefined) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();

/** 临时把 navigator.clipboard 换成给定值，跑完还原（jsdom 里默认没有剪贴板接口）。 */
async function withNavigatorClipboard(clip: unknown, run: () => Promise<CopyResult>): Promise<CopyResult> {
  const desc = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  Object.defineProperty(navigator, 'clipboard', { value: clip, configurable: true, writable: true });
  try {
    return await run();
  } finally {
    if (desc) Object.defineProperty(navigator, 'clipboard', desc);
    else delete (navigator as { clipboard?: unknown }).clipboard;
  }
}

describe('CopyNote：三结果文字取自 COPY_RESULT_TEXT', () => {
  it('三种 result 的文字依次等于 COPY_RESULT_TEXT 的值', () => {
    for (const result of ['copied', 'unavailable', 'failed'] as CopyResult[]) {
      const { container, unmount } = render(<CopyNote result={result} />);
      const note = container.querySelector('p');
      expect(note, `result=${result} 应渲染一个 p`).not.toBeNull();
      expect(text(note), `result=${result}`).toBe(COPY_RESULT_TEXT[result]);
      unmount();
    }
  });

  it('result 为 null 时不渲染任何元素', () => {
    const { container } = render(<CopyNote result={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('渲染 p、类名 tt-copy-note、不设 role、不写内联 style', () => {
    const { container, unmount } = render(<CopyNote result="copied" />);
    const note = container.firstElementChild as HTMLElement;
    expect(note.tagName).toBe('P');
    expect(note.className).toBe('tt-copy-note');
    expect(note.getAttribute('role')).toBeNull();
    expect(note.getAttribute('style')).toBeNull();
    unmount();
  });
});

describe('copyText：三态（共用件只有一份）', () => {
  it('成功 copied；没有 writeText 或没有接口 unavailable', async () => {
    expect(await copyText('a', { writeText: async () => {} })).toBe('copied');
    expect(await copyText('a', {})).toBe('unavailable');
    expect(await copyText('a', null)).toBe('unavailable');
    expect(await withNavigatorClipboard(undefined, () => copyText('a'))).toBe('unavailable');
  });

  it('抛错或被拒 failed；缺省读 navigator.clipboard 并原样传文字', async () => {
    expect(await copyText('a', { writeText: async () => { throw new Error('x'); } })).toBe('failed');
    expect(await copyText('a', { writeText: () => Promise.reject(new Error('x')) })).toBe('failed');
    const seen: string[] = [];
    const ok = await withNavigatorClipboard({ writeText: async (t: string) => { seen.push(t); } }, () => copyText('要复制的文字'));
    expect(ok).toBe('copied');
    expect(seen).toEqual(['要复制的文字']);
  });
});
