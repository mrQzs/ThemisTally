// 视觉修整的 DOM 测试（T013 D05、D07）：指标卡纵向、色调条贴左缘、标签行 16px 图标；方案表 aria-controls 只在展开时给。
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { MetricCard } from '../src/pages/readonly1/overview-MetricCard';
import { OverviewView } from '../src/pages/readonly1/overview-OverviewView';
import { PresetsTable } from '../src/pages/readonly1/roles-PresetsTable';
import { ScaleIcon } from '../src/icons';
import type { StatusRow } from '../src/api';

afterEach(cleanup);

const noNav = () => {};
const text = (el: Element | null | undefined) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: Element, sel: string) => Array.from(root.querySelectorAll(sel));

const CARDS: [string, string][] = [['running', '运行中'], ['review', '待验收'], ['decide', '要你决定'], ['integrate', '待集成']];

function row(over: Record<string, unknown>): StatusRow {
  return Object.assign({ attempt: 't/attempt-001', task_id: 't', plan_version: 1, state: 'RUNNING', wall_seconds: null, checks: '-' }, over) as StatusRow;
}
const ROWS: StatusRow[] = [
  row({ attempt: 'rev-a/attempt-002', task_id: 'rev-a', plan_version: 2, state: 'NEEDS_REVIEW', wall_seconds: 1719.4, checks: '8/8' }),
  row({ attempt: 'run-a/attempt-003', task_id: 'run-a', state: 'RUNNING' }),
];
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}

describe('指标卡：纵向、色调条贴左缘、标签行带 16px 图标', () => {
  it('a 里依次是色调条（aria-hidden）、标签行（16px 图标 aria-hidden + 标签文字）、数字（tt-num）', () => {
    for (const [group, label] of CARDS) {
      const { container, unmount } = render(<MetricCard group={group as 'running'} label={label} count={3} navigate={noNav} />);
      const card = container.querySelector('a.ov-metric') as HTMLElement;
      expect(card.getAttribute('data-metric')).toBe(group);
      const kids = Array.from(card.children) as HTMLElement[];
      expect(kids.map((k) => k.className)).toEqual(['ov-metric__bar', 'ov-metric__label', 'ov-metric__num tt-num']);
      expect(kids[0].getAttribute('aria-hidden')).toBe('true');
      expect(kids[0].textContent).toBe('');
      expect(kids[2].textContent).toBe('3');
      expect(text(kids[1])).toBe(label);
      const icon = kids[1].querySelector('svg') as SVGElement;
      expect(icon.getAttribute('aria-hidden')).toBe('true');
      expect(icon.getAttribute('width')).toBe('16');
      expect(icon.getAttribute('height')).toBe('16');
      expect(icon.getAttribute('class')).toContain('ov-metric__icon');
      expect(qa(card, '[style]')).toEqual([]);
      expect(qa(card, '.tt-num').length).toBe(1);
      unmount();
    }
  });

  it('待验收卡的图标是 ScaleIcon（Q1：待验收 ScaleIcon、--tt-accent-text），换成别的图标会红', () => {
    const { container, unmount } = render(<MetricCard group={'review'} label="待验收" count={3} navigate={noNav} />);
    const ref = render(<ScaleIcon width={16} height={16} className="ov-metric__icon" aria-hidden="true" />);
    const drawn = container.querySelector('.ov-metric__label svg') as SVGElement;
    const want = ref.container.querySelector('svg') as SVGElement;
    expect(drawn.innerHTML).toBe(want.innerHTML);
    expect(drawn.getAttribute('class')).toBe('tt-i ov-metric__icon');
    unmount();
    ref.unmount();
  });

  it('整页里四张卡都只有计数一个数字，标签行在数字之前', () => {
    const { container } = render(<OverviewView status={ROWS} history={{ ok: true, exit_code: 0, data: { entries: [], broken_lines: [], external_before_first: 0 }, output: [], messages: [], command: [], elapsed_ms: 0 } as never} navigate={noNav} />);
    const cards = qa(container, '[data-metric]') as HTMLElement[];
    expect(cards.map((c) => c.getAttribute('data-metric'))).toEqual(['running', 'review', 'decide', 'integrate']);
    for (const card of cards) {
      const label = card.querySelector('.ov-metric__label') as HTMLElement;
      const num = card.querySelector('.ov-metric__num') as HTMLElement;
      expect(label.compareDocumentPosition(num) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(qa(card, '.tt-num').length).toBe(1);
      expect(card.querySelector('.ov-metric__label svg')).not.toBeNull();
    }
  });
});

const presets = [
  { name: 'default', description: 'x', roles: ['contract', 'execution'], active: true },
  { name: 'has space', description: 'y', roles: ['execution'], active: false },
  { name: 'economy', description: 'z', roles: ['execution'], active: false },
] as unknown as Parameters<typeof PresetsTable>[0]['presets'];
const diffEnv = (a: string, b: string) => ({
  ok: true, exit_code: 0, data: { a, b, roles: [{ role: 'execution', a: { mode: 'headless', profile: 'step-high' }, b: { mode: 'headless', profile: 'step-low' }, same: false }] },
  output: [], messages: [], command: ['config', 'preset', 'diff', a, b], elapsed_ms: 0,
});

describe('方案表：aria-controls 只在展开时给', () => {
  it('收起的按钮没有 aria-controls；展开后指向存在的面板，值不含空白，各行面板 id 互不相同', async () => {
    const { container } = render(<PresetsTable presets={presets} active="default" totalRoles={2} onDiff={(a: string, b: string) => Promise.resolve(diffEnv(a, b) as never)} />);
    const buttons = qa(container, 'button').filter((b) => text(b) === '查看差异') as HTMLElement[];
    expect(buttons.length).toBe(2);
    for (const b of buttons) expect(b.getAttribute('aria-controls')).toBeNull();
    const seen: string[] = [];
    for (const b of buttons) {
      fireEvent.click(b);
      await flush();
      const controls = b.getAttribute('aria-controls') as string;
      expect(controls, '展开后应给 aria-controls').toBeTruthy();
      expect(/\s/.test(controls), 'aria-controls 不含空白').toBe(false);
      const panel = document.getElementById(controls) as HTMLElement | null;
      expect(panel, `aria-controls 指向的面板应在文档里：${controls}`).not.toBeNull();
      expect(panel!.getAttribute('id')).toBe(controls);
      expect(text(panel)).toContain('的差异');
      expect(seen).not.toContain(controls);
      seen.push(controls);
      fireEvent.click(b);
      await flush();
      expect(b.getAttribute('aria-controls')).toBeNull();
      expect(document.getElementById(controls)).toBeNull();
    }
    expect(seen.length).toBe(2);
  });

  it('方案名带空格时同样成立（id 不用方案名拼）', async () => {
    const { container } = render(<PresetsTable presets={presets} active="default" totalRoles={2} onDiff={(a: string, b: string) => Promise.resolve(diffEnv(a, b) as never)} />);
    const spaced = qa(container, 'button').find((b) => text(b) === '查看差异') as HTMLElement;
    fireEvent.click(spaced);
    await flush();
    const controls = spaced.getAttribute('aria-controls') as string;
    expect(controls).toBeTruthy();
    expect(controls).not.toContain(' ');
    expect(controls.toLowerCase()).not.toContain('space');
    expect(document.getElementById(controls)).not.toBeNull();
  });
});
