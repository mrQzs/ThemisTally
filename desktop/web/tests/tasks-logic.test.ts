// 任务页纯函数自测（合同 Steps 2、D01）：分组表与 UI 文档 3.4、地址解析、受管参数的读写、格式化与下一步规则。
import { describe, expect, it } from 'vitest';
import { ATTEMPT_GROUPS, GROUP_LABELS, groupOfState } from '../src/pages/tasks/tasks-groups';
import {
  DEFAULT_TAB,
  TASK_TABS,
  crossViewPath,
  groupsOfQuery,
  hrefWithMock,
  listPath,
  detailPath,
  mockOfQuery,
  replaceInPage,
  tabOfQuery,
  tasksViewFromHash,
} from '../src/pages/tasks/tasks-route';
import {
  formatBytes,
  formatDuration,
  formatLocalTime,
  formatThousands,
  kilobytesOf,
} from '../src/pages/tasks/tasks-format';
import {
  attemptsOf,
  buildTasks,
  checksSummary,
  checksText,
  countTasksByGroup,
  durationText,
  filterTasks,
  nextStepOf,
  attemptSeg,
} from '../src/pages/tasks/tasks-model';
import type { StatusRow } from '../src/api';

const row = (over: Record<string, unknown>): StatusRow => ({
  attempt: 't/attempt-001', task_id: 't', plan_version: 1, attempt_no: 1, state: 'RUNNING',
  ...over,
} as unknown as StatusRow);

describe('分组表与 UI 文档 3.4', () => {
  it('五个分组 ID 的顺序与中文标签', () => {
    expect(Array.from(ATTEMPT_GROUPS)).toEqual(['running', 'review', 'decide', 'integrate', 'ended']);
    expect(GROUP_LABELS).toEqual({
      running: '运行中', review: '待验收', decide: '要你决定', integrate: '待集成', ended: '已结束',
    });
  });

  it('17 个状态里 16 个进组；PREPARED 与未知状态为 null', () => {
    expect(groupOfState('PREPARING')).toBe('running');
    expect(groupOfState('RUNNING')).toBe('running');
    expect(groupOfState('COLLECTING')).toBe('running');
    expect(groupOfState('NEEDS_REVIEW')).toBe('review');
    expect(groupOfState('TIMEOUT')).toBe('review');
    expect(groupOfState('CANCELLED')).toBe('review');
    expect(groupOfState('INFRA_FAILURE')).toBe('review');
    expect(groupOfState('ESCALATE')).toBe('decide');
    expect(groupOfState('BLOCKED')).toBe('decide');
    expect(groupOfState('PASS')).toBe('integrate');
    expect(groupOfState('ACCEPTED_WITH_EXCEPTION')).toBe('integrate');
    expect(groupOfState('INTEGRATED')).toBe('ended');
    expect(groupOfState('REVISE')).toBe('ended');
    expect(groupOfState('ABANDONED')).toBe('ended');
    expect(groupOfState('SUPERSEDED')).toBe('ended');
    expect(groupOfState('PREPARE_FAILED')).toBe('ended');
    expect(groupOfState('PREPARED')).toBeNull();
    expect(groupOfState('NO_SUCH_STATE')).toBeNull();
  });
});

describe('地址解析', () => {
  it('列表与详情的路径段', () => {
    expect(tasksViewFromHash('#/tasks')).toEqual({
      kind: 'list', task: null, attempt: null, groups: [], tab: 'summary', mock: '', query: '',
    });
    const one = tasksViewFromHash('#/tasks/logs-cat');
    expect(one.kind).toBe('list');
    expect(one.task).toBe('logs-cat');
    const two = tasksViewFromHash('#/tasks/logs-cat/attempt-002?mock=offline');
    expect(two.kind).toBe('detail');
    expect(two.task).toBe('logs-cat');
    expect(two.attempt).toBe('attempt-002');
    expect(two.mock).toBe('offline');
  });

  it('详情路径多于两段时只取前两段', () => {
    const view = tasksViewFromHash('#/tasks/a/b/c/d?mock=data');
    expect(view.task).toBe('a');
    expect(view.attempt).toBe('b');
  });

  it('地址里的任务经编码', () => {
    const view = tasksViewFromHash('#/tasks/can%20a');
    expect(view.task).toBe('can a');
  });

  it('tab 的六个取值、缺省与认不出', () => {
    expect(TASK_TABS).toEqual(['summary', 'patch', 'checks', 'report', 'events', 'files']);
    expect(DEFAULT_TAB).toBe('summary');
    for (const id of TASK_TABS) expect(tabOfQuery(`mock=data&tab=${id}`)).toBe(id);
    expect(tabOfQuery('')).toBe('summary');
    expect(tabOfQuery('tab=zzz')).toBe('summary');
  });

  it('group 多值与重复参数取并集，认不出的 ID 忽略', () => {
    expect(groupsOfQuery('group=review,ended&mock=data')).toEqual(['review', 'ended']);
    expect(groupsOfQuery('group=review&group=decide')).toEqual(['review', 'decide']);
    expect(groupsOfQuery('group=zzz&mock=data')).toEqual([]);
    expect(groupsOfQuery('group=ended,review')).toEqual(['review', 'ended']);
    expect(groupsOfQuery('')).toEqual([]);
  });

  it('mock 的读取', () => {
    expect(mockOfQuery('mock=offline&keep=1')).toBe('offline');
    expect(mockOfQuery('keep=1')).toBe('');
  });
});

describe('受管参数的读写与跨视图路径', () => {
  it('replaceInPage 只改受管的参数、保留其余、值为缺省时删掉', () => {
    window.location.hash = '#/tasks?mock=offline&keep=1';
    replaceInPage('/tasks', { groups: ['review'] });
    expect(window.location.hash).toBe('#/tasks?mock=offline&keep=1&group=review');
    replaceInPage('/tasks', { groups: ['review', 'ended'] });
    expect(window.location.hash).toBe('#/tasks?mock=offline&keep=1&group=review,ended');
    replaceInPage('/tasks', { groups: [] });
    expect(window.location.hash).toBe('#/tasks?mock=offline&keep=1');
    replaceInPage('/tasks/logs-cat', { tab: 'patch' });
    expect(window.location.hash).toBe('#/tasks/logs-cat?mock=offline&keep=1&tab=patch');
    replaceInPage('/tasks/logs-cat', { tab: 'summary' });
    expect(window.location.hash).toBe('#/tasks/logs-cat?mock=offline&keep=1');
    window.location.hash = '';
  });

  it('replaceInPage 不改路径之外的查询，也不加历史项', () => {
    window.location.hash = '#/tasks?mock=data';
    const len = window.history.length;
    replaceInPage('/tasks/can%20a', {});
    expect(window.location.hash).toBe('#/tasks/can%20a?mock=data');
    expect(window.history.length).toBe(len);
    window.location.hash = '';
  });

  it('跨视图路径把受管参数写成缺省值，只在有残留时写', () => {
    window.location.hash = '#/tasks/logs-cat/attempt-002?mock=offline&keep=1';
    expect(listPath('logs-cat')).toBe('/tasks/logs-cat');
    expect(listPath()).toBe('/tasks');
    window.location.hash = '#/tasks/logs-cat/attempt-002?group=review&tab=patch&mock=data';
    expect(listPath('logs-cat')).toBe('/tasks/logs-cat?group=&tab=');
    expect(detailPath('logs-cat', 'attempt-002')).toBe('/tasks/logs-cat/attempt-002?tab=summary&group=&tab=');
    window.location.hash = '';
  });

  it('href 只带 mock', () => {
    expect(hrefWithMock('/tasks', 'offline')).toBe('#/tasks?mock=offline');
    expect(hrefWithMock('/tasks/logs-cat', '')).toBe('#/tasks/logs-cat');
  });
});

describe('格式化', () => {
  it('时长：秒 / 分 秒 / 小时 分', () => {
    expect(formatDuration(0)).toBe('0 秒');
    expect(formatDuration(59.9)).toBe('59 秒');
    expect(formatDuration(61)).toBe('1 分 1 秒');
    expect(formatDuration(1719.4)).toBe('28 分 39 秒');
    expect(formatDuration(1102.4)).toBe('18 分 22 秒');
    expect(formatDuration(3725)).toBe('1 小时 2 分');
    expect(formatDuration(null)).toBeNull();
    expect(formatDuration(-1)).toBeNull();
  });

  it('千分位', () => {
    expect(formatThousands(4210385)).toBe('4,210,385');
    expect(formatThousands(2981204)).toBe('2,981,204');
    expect(formatThousands(null)).toBe('未知');
  });

  it('字节：B / KB / MB', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(18342)).toBe('17.9 KB');
    expect(formatBytes(1844)).toBe('1.8 KB');
    expect(formatBytes(2841107)).toBe('2.7 MB');
    expect(formatBytes(null)).toBe('—');
  });

  it('摘要截断的 KB 数向下取整', () => {
    expect(kilobytesOf(3000)).toBe(2);
    expect(kilobytesOf(2048)).toBe(2);
    expect(kilobytesOf(512)).toBe(1);
  });

  it('本地时间按本地时区写 YYYY-MM-DD HH:mm', () => {
    const iso = '2026-10-18T06:21:40Z';
    const d = new Date(iso);
    const p = (n: number) => String(n).padStart(2, '0');
    const want = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
    expect(formatLocalTime(iso)).toBe(want);
    expect(formatLocalTime('')).toBeNull();
    expect(formatLocalTime('不是时间')).toBeNull();
  });
});

describe('行模型', () => {
  const rows = [
    row({ attempt: 'alpha/attempt-003', task_id: 'alpha', plan_version: 2, attempt_no: 3, state: 'NEEDS_REVIEW' }),
    row({ attempt: 'alpha/attempt-001', task_id: 'alpha', attempt_no: 1, state: 'RUNNING' }),
    row({ attempt: 'beta/attempt-002', task_id: 'beta', attempt_no: 2, state: 'PASS' }),
    row({ attempt: 'beta/attempt-001', task_id: 'beta', attempt_no: 1, state: 'REVISE' }),
    row({ attempt: 'prep only/attempt-001', task_id: 'prep only', attempt_no: 1, state: 'PREPARED' }),
    row({ attempt: 'gamma/attempt-001', task_id: 'gamma', attempt_no: 1, state: 'RUNNING' }),
    row({ attempt: 'delta/attempt-001', task_id: 'delta', attempt_no: 1, state: 'ESCALATE' }),
    row({ attempt: 'epsilon/attempt-002', task_id: 'epsilon', attempt_no: 2, state: 'INTEGRATED' }),
    row({ attempt: 'epsilon/attempt-001', task_id: 'epsilon', attempt_no: 1, state: 'RUNNING' }),
  ];

  it('按 task_id 归组、顺序按首次出现、最新 attempt 取 attempt_no 最大', () => {
    const tasks = buildTasks(rows);
    expect(tasks.map((t) => t.task_id)).toEqual(['alpha', 'beta', 'prep only', 'gamma', 'delta', 'epsilon']);
    expect(tasks[0].latest.attempt).toBe('alpha/attempt-003');
    expect(tasks[0].rows.length).toBe(2);
    expect(attemptSeg('alpha/attempt-003')).toBe('attempt-003');
  });

  it('attempt_no 相同时取在 getStatus 里靠前的', () => {
    const tasks = buildTasks([
      row({ attempt: 'g/attempt-001', task_id: 'g', attempt_no: 1, state: 'PASS' }),
      row({ attempt: 'g/attempt-001b', task_id: 'g', attempt_no: 1, state: 'REVISE' }),
    ]);
    expect(tasks[0].latest.state).toBe('PASS');
  });

  it('五组计数按每个任务的最新 attempt', () => {
    const counts = countTasksByGroup(buildTasks(rows));
    expect(counts).toEqual({ running: 1, review: 1, decide: 1, integrate: 1, ended: 1 });
  });

  it('搜索：不分大小写子串、先去首尾空白', () => {
    const tasks = buildTasks(rows);
    expect(filterTasks(tasks, 'ALPHA').map((t) => t.task_id)).toEqual(['alpha']);
    expect(filterTasks(tasks, '  beta  ').map((t) => t.task_id)).toEqual(['beta']);
    expect(filterTasks(tasks, '').length).toBe(6);
    expect(filterTasks(tasks, 'zzz')).toEqual([]);
  });

  it('attempt 表按 attempt_no 倒序', () => {
    const tasks = buildTasks(rows);
    expect(attemptsOf(tasks[0]).map((r) => attemptSeg(r.attempt))).toEqual(['attempt-003', 'attempt-001']);
  });

  it('用时：wall / live / —', () => {
    expect(durationText(row({ wall_seconds: 1719.4 }))).toBe('28 分 39 秒');
    expect(durationText(row({ wall_seconds: null, live: { elapsed_seconds: 1146 } }))).toBe('已用 19 分 6 秒');
    expect(durationText(row({ wall_seconds: null }))).toBe('—');
  });

  it('检查列与页头汇总', () => {
    expect(checksText(row({ checks: '8/8', check_mode: 'fresh' }))).toBe('8/8 fresh');
    expect(checksText(row({ checks: '-', check_mode: null }))).toBe('—');
    expect(checksText(row({ checks: null }))).toBe('—');
    expect(checksSummary(row({ checks: '8/8', check_mode: 'fresh' }))).toBe('8/8（fresh）');
    expect(checksSummary(row({ checks: '-', check_mode: null }))).toBe('—');
    expect(checksSummary(null)).toBe('—');
  });

  it('下一步四种规则与不显示的情形', () => {
    expect(nextStepOf('NEEDS_REVIEW', 'alpha', 'alpha/attempt-003')).toEqual({
      text: '这个 attempt 等你验收。验收在规划端会话里进行。',
      command: '/review-pi .agent/runs/alpha/alpha/attempt-003',
    });
    expect(nextStepOf('TIMEOUT', 't', 't/attempt-001')?.command).toBe('/review-pi .agent/runs/t/t/attempt-001');
    expect(nextStepOf('PASS', 'beta', 'beta/attempt-001')).toEqual({
      text: '已通过，等待集成。集成在规划端会话里进行。',
      command: '/review-pi .agent/runs/beta/beta/attempt-001',
    });
    expect(nextStepOf('ACCEPTED_WITH_EXCEPTION', 't', 't/attempt-001')?.command)
      .toBe('/review-pi .agent/runs/t/t/attempt-001');
    expect(nextStepOf('ESCALATE', 't', 't/attempt-001')).toEqual({
      text: '需要你做决定，见摘要里的阻塞点。', command: null,
    });
    expect(nextStepOf('BLOCKED', 't', 't/attempt-001')?.command).toBeNull();
    expect(nextStepOf('REVISE', 'redo', 'redo/attempt-001')).toEqual({
      text: '需要出新版本合同返工。', command: '/plan-task redo',
    });
    expect(nextStepOf('RUNNING', 't', 't/attempt-001')).toBeNull();
    expect(nextStepOf('INTEGRATED', 't', 't/attempt-001')).toBeNull();
    expect(nextStepOf('PREPARED', 't', 't/attempt-001')).toBeNull();
  });
});
