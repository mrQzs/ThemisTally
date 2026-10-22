// 任务列表视图自测（合同 Steps 4、D03）：搜索、分组胶囊与筛选、任务行与方向键、attempt 表 11 列、下一步与复制。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { TaskListView } from '../src/pages/tasks/TaskListView';
import type { StatusRow } from '../src/api';

afterEach(cleanup);

const row = (over: Record<string, unknown>): StatusRow => ({
  attempt: 't/attempt-001', task_id: 't', plan_version: 1, attempt_no: 1, state: 'RUNNING', started: true,
  exit_code: null, wall_seconds: null, events_ok: true, violations: null, checks: '-', check_mode: null,
  verdict: null, failure_class: null, human_minutes: null, tokens: null, cost: null, cost_status: 'unknown',
  ...over,
} as unknown as StatusRow);

const ROWS: StatusRow[] = [
  row({ attempt: 'alpha/attempt-003', task_id: 'alpha', plan_version: 2, attempt_no: 3, state: 'NEEDS_REVIEW',
    wall_seconds: 1719.4, checks: '8/8', check_mode: 'fresh', violations: 0, tokens: 4210385,
    effort_requested: 'max', effort_effective: 'high' }),
  row({ attempt: 'alpha/attempt-002', task_id: 'alpha', attempt_no: 2, state: 'REVISE', wall_seconds: 1102.4,
    checks: '6/8', check_mode: 'fresh', verdict: 'REVISE', failure_class: 'EXECUTION_ERROR', violations: 0,
    tokens: 5637968 }),
  row({ attempt: 'alpha/attempt-001', task_id: 'alpha', attempt_no: 1, state: 'RUNNING',
    live: { tool_calls: 37, elapsed_seconds: 1146 }, cost: '12.5' }),
  row({ attempt: 'beta/attempt-001', task_id: 'beta', attempt_no: 1, state: 'PASS', wall_seconds: 954.0,
    checks: '5/5', check_mode: 'fresh', verdict: 'PASS', violations: 2, tokens: 2981204 }),
  row({ attempt: 'run me/attempt-001', task_id: 'run me', attempt_no: 1, state: 'RUNNING' }),
  row({ attempt: 'can a/attempt-001', task_id: 'can a', attempt_no: 1, state: 'CANCELLED', wall_seconds: 59.9 }),
  row({ attempt: 'prep only/attempt-001', task_id: 'prep only', attempt_no: 1, state: 'PREPARED' }),
];

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: Element | null, sel: string) => Array.from((root ?? document).querySelectorAll(sel));
const options = () => qa(document, 'li[role="option"]');
const optionTask = (el: Element) => text(el).replace(/\s+attempt-[\s\S]*$/, '').trim();
const capsules = () => qa(document, '[role="group"][aria-label="按状态分组筛选"] button');
const pressedGroups = () => capsules()
  .filter((b) => b.getAttribute('aria-pressed') === 'true')
  .map((b) => b.getAttribute('data-group'));
const table = (task: string) => document.querySelector(`table[aria-label="${task} 的 attempt"]`);
const headersOf = (t: Element | null) => qa(t, 'thead th').map(text);
const rowsOf = (t: Element | null) => qa(t, 'tbody tr');
const cellsOf = (r: Element) => qa(r, 'td');
function cellText(t: Element | null, i: number, header: string) {
  const at = headersOf(t).indexOf(header);
  expect(at, `表头里没有「${header}」`).toBeGreaterThanOrEqual(0);
  return text(cellsOf(rowsOf(t)[i])[at]);
}

const opened: string[] = [];
const navigated: string[] = [];

/** 带状态的壳：像 TasksPage 那样把选中任务与分组存在状态里，回调只改状态。 */
function Harness({ mock = '' }: { mock?: string }) {
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [groups, setGroups] = useState<string[]>([]);
  return (
    <TaskListView
      rows={ROWS}
      selectedTask={selectedTask}
      groups={groups as never}
      onSelectTask={setSelectedTask}
      onGroupsChange={(next) => setGroups(next as string[])}
      onOpenAttempt={(task, attempt) => opened.push(`${task}/${attempt}`)}
      mock={mock}
      navigate={(path) => navigated.push(path)}
    />
  );
}

function mount(mock = '') {
  opened.length = 0;
  navigated.length = 0;
  return render(<Harness mock={mock} />);
}

describe('左栏', () => {
  it('两个 section、搜索框、五颗胶囊与计数', () => {
    mount();
    expect(qa(document, 'section[aria-label="任务列表"]').length).toBe(1);
    expect(qa(document, 'section').length).toBe(2);
    const input = qa(document, 'input[type="search"]')[0];
    expect(input).toBeTruthy();
    expect(input.getAttribute('placeholder')).toBe('搜索任务…');
    expect(input.getAttribute('aria-label')).toBe('搜索任务');
    expect(qa(document, 'svg[width="16"]').length).toBeGreaterThan(0);
    expect(capsules().map((b) => [b.getAttribute('data-group'), text(b).replace(/\d+$/, '').trim()])).toEqual([
      ['running', '运行中'], ['review', '待验收'], ['decide', '要你决定'], ['integrate', '待集成'], ['ended', '已结束'],
    ]);
    expect(capsules().map((b) => text(b).replace(/[^\d]/g, ''))).toEqual(['1', '2', '0', '1', '0']);
    expect(pressedGroups()).toEqual([]);
  });

  it('搜索：不分大小写子串、先去首尾空白；没有匹配时写一行且右栏不渲染', () => {
    mount();
    const input = qa(document, 'input[type="search"]')[0];
    fireEvent.change(input, { target: { value: 'ALPHA' } });
    expect(options().map(optionTask)).toEqual(['alpha']);
    fireEvent.change(input, { target: { value: '  can a  ' } });
    expect(options().map(optionTask)).toEqual(['can a']);
    fireEvent.change(input, { target: { value: 'zzz' } });
    expect(options().length).toBe(0);
    expect(text(document.body)).toContain('没有符合条件的任务');
    expect(table('alpha')).toBeNull();
    expect(qa(document, 'h2').length).toBe(0);
  });

  it('PREPARED 只在没有按下胶囊时显示；计数不受搜索与选中影响', () => {
    mount();
    expect(options().map(optionTask)).toContain('prep only');
    fireEvent.click(capsules()[0]);
    expect(pressedGroups()).toEqual(['running']);
    expect(options().map(optionTask)).toEqual(['run me']);
    fireEvent.click(capsules()[0]);
    expect(pressedGroups()).toEqual([]);
    fireEvent.change(qa(document, 'input[type="search"]')[0], { target: { value: 'alpha' } });
    fireEvent.click(options()[0]);
    expect(capsules().map((b) => text(b).replace(/[^\d]/g, ''))).toEqual(['1', '2', '0', '1', '0']);
  });

  it('任务行：两行、右侧 StatusTag sm、roving tabindex、点击与方向键选中', () => {
    mount();
    const opts = options();
    expect(opts.map(optionTask)).toEqual(['alpha', 'beta', 'run me', 'can a', 'prep only']);
    const selected = opts.filter((o) => o.getAttribute('aria-selected') === 'true');
    expect(selected.length).toBe(1);
    expect(optionTask(selected[0])).toBe('alpha');
    expect(selected[0].getAttribute('tabindex')).toBe('0');
    expect(opts.filter((o) => o !== selected[0]).every((o) => o.getAttribute('tabindex') === '-1')).toBe(true);
    expect(qa(opts[0], '[data-size="sm"]').length).toBeGreaterThan(0);
    expect(text(opts[0])).toContain('attempt-003');
    fireEvent.click(opts[2]);
    expect(optionTask(options().filter((o) => o.getAttribute('aria-selected') === 'true')[0])).toBe('run me');
    const sel = () => options().filter((o) => o.getAttribute('aria-selected') === 'true')[0];
    sel().focus();
    fireEvent.keyDown(sel(), { key: 'ArrowDown' });
    expect(optionTask(sel())).toBe('can a');
    fireEvent.keyDown(sel(), { key: 'End' });
    expect(optionTask(sel())).toBe('prep only');
    fireEvent.keyDown(sel(), { key: 'Home' });
    expect(optionTask(sel())).toBe('alpha');
  });

  it('多值分组：逗号分隔按 ATTEMPT_GROUPS 的顺序写，读时都按下', () => {
    mount();
    fireEvent.click(capsules()[1]);
    fireEvent.click(capsules()[4]);
    expect(pressedGroups()).toEqual(['review', 'ended']);
    expect(options().map(optionTask)).toEqual(['alpha', 'can a']);
    fireEvent.click(capsules()[4]);
    expect(pressedGroups()).toEqual(['review']);
    expect(options().map(optionTask)).toEqual(['alpha', 'can a']);
  });

  it('选中任务时才有面包屑：第一项只带 mock，第二项是当前任务；点第一项跨视图回列表', () => {
    mount('offline');
    expect(qa(document, 'nav[aria-label="面包屑"]').length, '地址里没有任务时没有面包屑').toBe(0);
    fireEvent.click(options()[0]);
    const nav = qa(document, 'nav[aria-label="面包屑"]')[0];
    expect(nav, '地址里带了任务后有面包屑').toBeTruthy();
    const links = qa(nav, 'a');
    expect(links.map(text)).toEqual(['任务']);
    expect(links[0].getAttribute('href'), '面包屑第一项只带 mock').toBe('#/tasks?mock=offline');
    expect(text(qa(nav, '[aria-current="page"]')[0])).toBe('alpha');
    fireEvent.click(links[0]);
    expect(navigated, '无修饰键左键由应用拦下并同步换路由').toEqual(['/tasks?mock=offline']);
  });
});

describe('右栏', () => {
  it('h2 与 attempt 计数、表头 11 列、行高 40、按 attempt_no 倒序', () => {
    mount();
    expect(text(qa(document, 'h2')[0])).toBe('alpha');
    expect(text(document.body)).toContain('3 个 attempt');
    const t = table('alpha');
    expect(t).not.toBeNull();
    expect(t!.getAttribute('data-row-height')).toBe('40');
    expect(headersOf(t)).toEqual(['attempt', '版本', '状态', '用时', '检查', '结论', '失败分类', '越界', 'token', '费用', '思考档位']);
    expect(rowsOf(t).map((r) => text(cellsOf(r)[0]))).toEqual(['attempt-003', 'attempt-002', 'attempt-001']);
  });

  it('11 列取值', () => {
    mount();
    const t = table('alpha');
    expect(cellText(t, 0, '版本')).toBe('v2');
    expect(cellText(t, 2, '版本')).toBe('v1');
    expect(cellText(t, 0, '用时')).toBe('28 分 39 秒');
    expect(cellText(t, 1, '用时')).toBe('18 分 22 秒');
    expect(cellText(t, 2, '用时')).toBe('已用 19 分 6 秒');
    expect(cellText(t, 0, '检查')).toBe('8/8 fresh');
    expect(cellText(t, 2, '检查')).toBe('—');
    expect(cellText(t, 0, '结论')).toBe('—');
    expect(qa(cellsOf(rowsOf(t)[1])[headersOf(t).indexOf('结论')], '[data-size="sm"]').length).toBeGreaterThan(0);
    expect(cellText(t, 1, '失败分类')).toBe('EXECUTION_ERROR');
    expect(cellText(t, 0, '失败分类')).toBe('—');
    expect(cellText(t, 0, '越界')).toBe('0');
    expect(cellText(t, 0, 'token')).toBe('4,210,385');
    expect(cellText(t, 2, 'token')).toBe('未知');
    expect(cellText(t, 0, '费用')).toBe('未知');
    expect(cellText(t, 2, '费用')).toBe('12.5');
    const effort = cellsOf(rowsOf(t)[0])[headersOf(t).indexOf('思考档位')];
    expect(qa(effort, '.tt-effort').length).toBe(1);
    expect(text(effort)).toContain('max');
    expect(text(effort)).toContain('high');
    expect(cellText(t, 2, '思考档位')).toBe('未知');
    fireEvent.click(options()[1]);
    const beta = table('beta');
    expect(cellText(beta, 0, '越界')).toBe('2');
    expect(qa(cellsOf(rowsOf(beta)[0])[headersOf(beta).indexOf('越界')], '.tasks-list__danger').length).toBe(1);
  });

  it('点行与行上按 Enter 打开这个 attempt 的详情', () => {
    mount();
    fireEvent.click(rowsOf(table('alpha'))[1]);
    expect(opened).toEqual(['alpha/attempt-002']);
    cleanup();
    mount();
    const row = rowsOf(table('alpha'))[2];
    row.focus();
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(opened).toEqual(['alpha/attempt-001']);
  });

  it('下一步四种规则与复制三种结果', async () => {
    mount();
    const next = () => qa(document, '.tt-next')[0];
    expect(text(next())).toContain('这个 attempt 等你验收。验收在规划端会话里进行。');
    expect(text(next())).toContain('/review-pi .agent/runs/alpha/attempt-003');
    expect(text(next())).toContain('下一步');
    const writeText = vi.fn(() => Promise.reject(new Error('no')));
    Object.defineProperty(window.navigator, 'clipboard', { value: { writeText }, configurable: true });
    await act(async () => {
      fireEvent.click(qa(next(), '[aria-label="复制命令"]')[0]);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(text(document.body)).toContain('复制失败');
    expect(writeText).toHaveBeenCalledWith('/review-pi .agent/runs/alpha/attempt-003');
    delete (window.navigator as unknown as { clipboard?: unknown }).clipboard;
    await act(async () => {
      fireEvent.click(qa(next(), '[aria-label="复制命令"]')[0]);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(text(document.body)).toContain('这个环境没有剪贴板接口');
  });

  it('已通过、返工、要你决定与运行中之外的状态不显示下一步', () => {
    const cases: Array<[string, string, string]> = [
      ['beta', '已通过，等待集成。集成在规划端会话里进行。', '/review-pi .agent/runs/beta/attempt-001'],
      ['can a', '这个 attempt 等你验收。验收在规划端会话里进行。', '/review-pi .agent/runs/can a/attempt-001'],
    ];
    for (const [task, want, command] of cases) {
      cleanup();
      mount();
      fireEvent.click(options().filter((o) => optionTask(o) === task)[0]);
      const next = qa(document, '.tt-next')[0];
      expect(text(next), task).toContain(want);
      expect(text(next), task).toContain(command);
    }
    cleanup();
    mount();
    fireEvent.click(options().filter((o) => optionTask(o) === 'run me')[0]);
    expect(qa(document, '.tt-next').length, '运行中不显示下一步').toBe(0);
    cleanup();
    mount();
    fireEvent.click(options().filter((o) => optionTask(o) === 'prep only')[0]);
    expect(qa(document, '.tt-next').length, 'PREPARED 不显示下一步').toBe(0);
  });
});
