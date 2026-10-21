// 总览视图测试（合同第 9 节，注入数据）：指标卡、需要你判断、运行中、待集成、配置变更、空区块不渲染。
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import type { StatusRow } from '../src/api';
import { OverviewView } from '../src/pages/readonly1/overview-OverviewView';

afterEach(cleanup);

function row(over: Record<string, unknown>): StatusRow {
  return Object.assign(
    { attempt: 't/attempt-001', task_id: 't', plan_version: 1, state: 'RUNNING', wall_seconds: null, checks: '-' },
    over,
  ) as StatusRow;
}
function env(entries: unknown[]): any {
  return { ok: true, exit_code: 0, data: { entries, broken_lines: [], external_before_first: 0 }, output: [], messages: [], command: ['config', 'history'], elapsed_ms: 0 };
}
const noNav = () => {};
const text = (el: any) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string) => Array.from(root.querySelectorAll(sel));
function sectionNamed(root: any, title: string): any {
  return qa(root, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    const h = id ? document.getElementById(id) : null;
    return text(h) === title;
  });
}
const rowsOf = (sec: any) => qa(sec, 'ul > li');

const ROWS: StatusRow[] = [
  row({ attempt: 'rev-a/attempt-002', task_id: 'rev-a', plan_version: 2, state: 'NEEDS_REVIEW', wall_seconds: 1719.4, checks: '8/8' }),
  row({ attempt: 'run-a/attempt-003', task_id: 'run-a', state: 'RUNNING', live: { tool_calls: 37, elapsed_seconds: 1146, deltas_since_last_tool: 6420, long_idle: true } }),
  row({ attempt: 'esc/attempt-001', task_id: 'esc', state: 'ESCALATE', wall_seconds: 640.2, checks: '3/4' }),
  row({ attempt: 'pass-a/attempt-001', task_id: 'pass-a', state: 'PASS', wall_seconds: 954, checks: '5/5' }),
];

describe('指标卡', () => {
  it('四张卡顺序与计数', () => {
    const { container } = render(<OverviewView status={ROWS} history={env([])} navigate={noNav} />);
    const cards = qa(container, '[data-metric]');
    expect(cards.map((c: any) => c.getAttribute('data-metric'))).toEqual(['running', 'review', 'decide', 'integrate']);
    expect(cards.map((c: any) => c.querySelector('.tt-num')?.textContent)).toEqual(['1', '1', '1', '1']);
    expect(cards[0].getAttribute('href')).toBe('#/tasks?group=running');
  });
});

describe('需要你判断', () => {
  it('待验收+要你决定两组、计数胶囊、下一步命令取待验收组第一行', () => {
    const { container } = render(<OverviewView status={ROWS} history={env([])} navigate={noNav} />);
    const sec = sectionNamed(container, '需要你判断');
    const lis = rowsOf(sec);
    expect(text(lis[0])).toContain('rev-a.v2 · attempt-002');
    expect(text(lis[1])).toContain('esc.v1 · attempt-001');
    expect(sec.querySelector('[aria-label="2 项"]')?.textContent).toBe('2');
    expect(text(sec.querySelector('.tt-next code'))).toBe('/review-pi .agent/runs/rev-a/attempt-002');
    expect(text(lis[0])).toContain('28 分 39 秒 · 检查 8/8');
    expect(sec.querySelector('[style]')).toBeNull();
  });

  it('只有要你决定时下一步不带命令', () => {
    const { container } = render(
      <OverviewView status={[row({ attempt: 'esc/attempt-001', task_id: 'esc', state: 'ESCALATE', wall_seconds: 640.2, checks: '3/4' })]} history={env([])} navigate={noNav} />,
    );
    const sec = sectionNamed(container, '需要你判断');
    expect(text(sec.querySelector('.tt-next'))).toContain('需要你做决定，见摘要里的阻塞点。');
    expect(sec.querySelector('.tt-next code')).toBeNull();
  });
});

describe('运行中与待集成', () => {
  it('运行中：已用、工具调用、long_idle 标签、data-long-idle、[跟随事件] 地址', () => {
    const { container } = render(<OverviewView status={ROWS} history={env([])} navigate={noNav} />);
    const lis = rowsOf(sectionNamed(container, '运行中'));
    expect(lis.length).toBe(1);
    expect(lis[0].textContent.replace(/\s+/g, '')).toContain('已用19分6秒');
    expect(lis[0].textContent.replace(/\s+/g, '')).toContain('工具调用37次');
    const tag = qa(lis[0], '.tt-tag').find((t: any) => text(t) === '长时间没有工具调用（6420 个增量）');
    expect(tag).toBeTruthy();
    expect((tag as any).getAttribute('data-tone')).toBe('warning');
    expect(lis[0].getAttribute('data-long-idle')).toBe('true');
    const link = qa(lis[0], 'a').find((a: any) => text(a) === '跟随事件');
    expect((link as any).getAttribute('href')).toBe('#/tasks/run-a/attempt-003?tab=events');
  });

  it('待集成：下一步集成命令', () => {
    const { container } = render(<OverviewView status={ROWS} history={env([])} navigate={noNav} />);
    const sec = sectionNamed(container, '待集成');
    expect(text(sec.querySelector('.tt-next'))).toContain('集成在规划端会话里进行：');
    expect(text(sec.querySelector('.tt-next code'))).toBe('/review-pi .agent/runs/pass-a/attempt-001');
  });

  it('没有行的区块整块不渲染', () => {
    const { container } = render(<OverviewView status={[ROWS[1]]} history={env([])} navigate={noNav} />);
    expect(sectionNamed(container, '需要你判断')).toBeUndefined();
    expect(sectionNamed(container, '待集成')).toBeUndefined();
    expect(sectionNamed(container, '运行中')).toBeTruthy();
  });
});

describe('配置变更', () => {
  it('最多 5 条倒序、外部改动标签、执行者色调、查看全部历史', () => {
    const entries = [3, 9, 1, 12, 7, 5, 11].map((n) => ({
      number: n, at: '2026-10-18T02:00:00Z', action: 'config.set', target: 'pricing',
      actor: n === 11 ? 'agent:planning_review' : 'user', external_changes: n === 11 ? 2 : 0,
    }));
    const { container } = render(<OverviewView status={ROWS} history={env(entries)} navigate={noNav} />);
    const sec = sectionNamed(container, '最近的配置变更');
    const lis = rowsOf(sec);
    expect(lis.map((li: any) => qa(li, '.ov-change__no')[0].textContent.replace('#', ''))).toEqual(['12', '11', '9', '7', '5']);
    expect(qa(sec, 'a').some((a: any) => text(a) === '查看全部历史')).toBe(true);
    const ext = qa(lis[1], '.tt-tag').find((t: any) => text(t) === '检测到外部改动');
    expect(ext).toBeTruthy();
    const actor = qa(lis[1], '.tt-tag').find((t: any) => text(t) === 'agent:planning_review');
    expect((actor as any).getAttribute('data-tone')).toBe('info');
  });

  it('entries 空显示还没有配置历史；出错显示命令与退出码', () => {
    const { container } = render(<OverviewView status={ROWS} history={env([])} navigate={noNav} />);
    expect(text(sectionNamed(container, '最近的配置变更'))).toContain('还没有配置历史');
    cleanup();
    const bad = { ok: false, exit_code: 3, data: null, output: [], messages: ['ERROR 坏了'], command: ['config', 'history', '--json'], elapsed_ms: 0 };
    const r2 = render(<OverviewView status={ROWS} history={bad as any} navigate={noNav} />);
    const sec = sectionNamed(r2.container, '最近的配置变更');
    expect(text(sec)).toContain('没能读到配置历史：命令 config history --json 返回退出码 3。');
    expect(sec.querySelector('pre')?.textContent).toBe('ERROR 坏了');
  });
});
