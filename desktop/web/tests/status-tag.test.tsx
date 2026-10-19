// StatusTag 的兜底：17 个已知状态以外的任意状态码原样显示、neutral、circle-help，不报错（T002 终审 B1）。
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { StatusTag } from '../src/components';
import { ATTEMPT_STATES, resolveAttemptState } from '../src/domain/attemptStates';

afterEach(cleanup);

const PROTOTYPE_NAMES = ['constructor', 'toString', 'hasOwnProperty', 'valueOf', '__proto__', 'isPrototypeOf',
  'toLocaleString'];

describe('StatusTag 兜底', () => {
  it.each(PROTOTYPE_NAMES)('与 Object.prototype 同名的状态码 %s 按未知状态显示', (code) => {
    const { container } = render(<StatusTag state={code} />);
    const tag = container.querySelector('.tt-status');
    expect(tag?.textContent).toBe(code);
    expect(tag?.getAttribute('title')).toBe(code);
    expect(tag?.getAttribute('data-tone')).toBe('neutral');
    expect(resolveAttemptState(code).known).toBe(false);
    // 图标与普通未知状态码相同，即兜底的 circle-help
    const unknown = render(<StatusTag state="NOT_A_STATE" />).container.querySelector('svg');
    expect(container.querySelector('svg')?.innerHTML).toBe(unknown?.innerHTML);
    expect(unknown?.innerHTML).not.toBe(render(<StatusTag state="PASS" />).container.querySelector('svg')?.innerHTML);
  });

  it('已知状态仍是 17 个自有键', () => {
    expect(Object.keys(ATTEMPT_STATES)).toHaveLength(17);
    expect(resolveAttemptState('PASS')).toMatchObject({ known: true, display: '通过', tone: 'success' });
  });
});
