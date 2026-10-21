// 纯函数测试（合同第 9 节）：分组计数、时长、行文字、下一步命令、配置变更排序截取、动作说明、
// 角色/模式名、被引用、方案角色名、绑定文字、来源标签、能担任、命令截断、地址拼接、copyText 三态。
import { describe, expect, it } from 'vitest';
import type { StatusRow } from '../src/api';
import {
  actionLabel,
  checksInfo,
  firstAttemptIn,
  formatDuration,
  idleDeltas,
  liveElapsed,
  longIdle,
  metricCounts,
  reviewCommand,
  rowName,
  rowsInGroups,
  toolCalls,
  topChanges,
} from '../src/pages/readonly1/overview-logic';
import {
  bindingText,
  modeName,
  normalizeRole,
  presetRoleTitle,
  profileRefs,
  resolvedProfile,
  roleName,
} from '../src/pages/readonly1/roles-logic';
import {
  canModels,
  canProbe,
  canServe,
  commandFull,
  commandText,
  shortCommand,
  sourceLabel,
  sourceTone,
} from '../src/pages/readonly1/runtimes-logic';
import { attemptSeg, evidencePath, eventsPath, groupPath } from '../src/pages/readonly1/common-links';
import { copyText } from '../src/pages/readonly1/common-copyText';

function row(over: Record<string, unknown>): StatusRow {
  return Object.assign({ attempt: 't/attempt-001', task_id: 't', state: 'RUNNING' }, over) as StatusRow;
}

describe('分组计数与分组行', () => {
  it('metricCounts 按分组逐行统计，ended 与未知状态不计', () => {
    const counts = metricCounts([
      row({ state: 'RUNNING' }),
      row({ state: 'NEEDS_REVIEW' }),
      row({ state: 'ESCALATE' }),
      row({ state: 'PASS' }),
      row({ state: 'INTEGRATED' }),
      row({ state: 'PREPARED' }),
    ]);
    expect(counts).toEqual({ running: 1, review: 1, decide: 1, integrate: 1 });
  });

  it('rowsInGroups 保持原顺序，多分组合并', () => {
    const rows = [row({ attempt: 'a/attempt-001', state: 'ESCALATE' }), row({ attempt: 'b/attempt-001', state: 'RUNNING' }), row({ attempt: 'c/attempt-001', state: 'BLOCKED' })];
    expect(rowsInGroups(rows, ['review', 'decide']).map((r) => r.attempt)).toEqual(['a/attempt-001', 'c/attempt-001']);
  });

  it('firstAttemptIn 取分组里显示顺序第一行', () => {
    const rows = [row({ attempt: 'a/attempt-001', state: 'BLOCKED' }), row({ attempt: 'b/attempt-001', state: 'NEEDS_REVIEW' })];
    expect(firstAttemptIn(rows, ['review'])).toBe('b/attempt-001');
    expect(firstAttemptIn(rows, ['running'])).toBeNull();
  });
});

describe('时长格式化', () => {
  it('秒向下取整；不足 1 分钟 N 秒，不足 1 小时 M 分 S 秒，否则 H 小时 M 分', () => {
    expect(formatDuration(1719.4)).toBe('28 分 39 秒');
    expect(formatDuration(1800)).toBe('30 分 0 秒');
    expect(formatDuration(1146)).toBe('19 分 6 秒');
    expect(formatDuration(640.2)).toBe('10 分 40 秒');
    expect(formatDuration(59.99)).toBe('59 秒');
    expect(formatDuration(0)).toBe('0 秒');
    expect(formatDuration(3599)).toBe('59 分 59 秒');
    expect(formatDuration(3600)).toBe('1 小时 0 分');
    expect(formatDuration(3725)).toBe('1 小时 2 分');
  });

  it('非数或负数不显示', () => {
    for (const v of [-5, null, undefined, NaN, 'x' as unknown as number]) {
      expect(formatDuration(v)).toBeNull();
    }
  });
});

describe('行文字与信息', () => {
  it('rowName：有 plan_version 写 .v，缺失只写 task_id', () => {
    expect(rowName(row({ task_id: 'rev-a', plan_version: 2, attempt: 'rev-a/attempt-002' }))).toBe('rev-a.v2 · attempt-002');
    expect(rowName(row({ task_id: 'run-b', attempt: 'run-b/attempt-001' }))).toBe('run-b · attempt-001');
  });

  it('checksInfo：用时与检查用 · 连，checks 为 - 视为没有', () => {
    expect(checksInfo(row({ state: 'ESCALATE', wall_seconds: 640.2, checks: '3/4' }))).toBe('10 分 40 秒 · 检查 3/4');
    expect(checksInfo(row({ state: 'TIMEOUT', wall_seconds: 1800, checks: '-' }))).toBe('30 分 0 秒');
    expect(checksInfo(row({ state: 'BLOCKED', wall_seconds: null, checks: '-' }))).toBe('');
  });

  it('运行中的已用、工具调用、long_idle 与增量', () => {
    const r = row({ live: { tool_calls: 37, elapsed_seconds: 1146, deltas_since_last_tool: 6420, long_idle: true } });
    expect(liveElapsed(r)).toBe('19 分 6 秒');
    expect(toolCalls(r)).toBe(37);
    expect(longIdle(r)).toBe(true);
    expect(idleDeltas(r)).toBe(6420);
    const r2 = row({ live: { tool_calls: 3, elapsed_seconds: 45.9, long_idle: false } });
    expect(longIdle(r2)).toBe(false);
    expect(idleDeltas(r2)).toBeNull();
  });

  it('reviewCommand 拼 /review-pi 命令', () => {
    expect(reviewCommand('rev-a/attempt-002')).toBe('/review-pi .agent/runs/rev-a/attempt-002');
  });
});

describe('配置变更', () => {
  const entry = (number: number, action = 'config.set') => ({ number, at: '2026-10-18T02:00:00Z', action, target: 'x', actor: 'user', external_changes: 0 });
  it('按 number 倒序取前 5', () => {
    const history = { entries: [entry(3), entry(9), entry(1), entry(12), entry(7), entry(5), entry(11)] } as any;
    expect(topChanges(history).map((e) => e.number)).toEqual([12, 11, 9, 7, 5]);
  });

  it('actionLabel：精确说明与动词+名词，未知返回 null', () => {
    expect(actionLabel('config.set')).toBe('设置配置键');
    expect(actionLabel('preset.use')).toBe('切换方案');
    expect(actionLabel('runtime.add')).toBe('登记 runtime');
    expect(actionLabel('config.rollback')).toBe('回滚配置');
    expect(actionLabel('config.unset')).toContain('删除');
    expect(actionLabel('config.unset')).toContain('配置键');
    expect(actionLabel('zzz.unknown')).toBeNull();
  });
});

describe('角色与模式', () => {
  it('roleName/modeName 映射，未知原样', () => {
    expect(roleName('execution')).toBe('执行端');
    expect(roleName('custom_role')).toBe('custom_role');
    expect(modeName('headless')).toBe('无头');
    expect(modeName('weird')).toBe('weird');
  });

  it('normalizeRole 收窄联合类型；resolvedProfile 取 role.profile 否则 binding.profile', () => {
    const r = normalizeRole({ role: 'contract', binding: { mode: 'headless', profile: 'p2' } } as any);
    expect(r.mode).toBe('headless');
    expect(resolvedProfile(r)).toBe('p2');
    const r2 = normalizeRole({ role: 'execution', binding: { mode: 'headless', profile: 'a' }, profile: 'b' } as any);
    expect(resolvedProfile(r2)).toBe('b');
  });

  it('profileRefs 只算当前无头角色，按顺序用、连', () => {
    const roles = [
      normalizeRole({ role: 'planning_review', binding: { mode: 'interactive_host', host: 'x', profile: 'step-high' } } as any),
      normalizeRole({ role: 'contract', binding: { mode: 'headless', profile: 'step-high' } } as any),
      normalizeRole({ role: 'execution', binding: { mode: 'headless', profile: 'step-high' }, profile: 'step-high' } as any),
    ];
    expect(profileRefs(roles, 'step-high')).toBe('合同端、执行端');
    expect(profileRefs(roles, 'none')).toBe('—');
  });

  it('presetRoleTitle 映射中文名用、连', () => {
    expect(presetRoleTitle(['contract', 'execution'])).toBe('合同端、执行端');
  });

  it('bindingText：无头/交互式宿主/手工/关闭/未知/缺失', () => {
    expect(bindingText({ mode: 'headless', profile: 'step-high' })).toBe('无头 · step-high');
    expect(bindingText({ mode: 'interactive_host', host: 'claude-code' })).toBe('交互式宿主 · claude-code');
    expect(bindingText({ mode: 'manual' })).toBe('手工');
    expect(bindingText({ mode: 'disabled' })).toBe('关闭');
    expect(bindingText({ mode: 'zzz' })).toBe('zzz');
    expect(bindingText(null)).toBe('—');
  });
});

describe('运行时', () => {
  it('canServe：pi/claude-code/codex/opencode/其他', () => {
    expect(canServe('pi')).toBe('执行端、合同端');
    expect(canServe('claude-code')).toBe('交互式宿主');
    expect(canServe('codex')).toBe('交互式宿主');
    expect(canServe('opencode')).toBe('未接通');
    expect(canServe('custom')).toBe('—');
  });

  it('sourceLabel/sourceTone：四种加未知', () => {
    expect(sourceLabel('env')).toBe('环境变量');
    expect(sourceLabel('local')).toBe('本机文件');
    expect(sourceLabel('path')).toBe('PATH');
    expect(sourceLabel('missing')).toBe('找不到');
    expect(sourceLabel('zzz')).toBe('zzz');
    expect(sourceTone('missing')).toBe('danger');
    expect(sourceTone('env')).toBe('neutral');
  });

  it('shortCommand 按码点截断：40 不截，41 截', () => {
    const c40 = 'a'.repeat(40);
    const c41 = 'a'.repeat(41);
    expect(shortCommand(c40)).toBe(c40);
    expect(shortCommand(c41)).toBe('a'.repeat(22) + ' … ' + 'a'.repeat(15));
  });

  it('commandText：null 显示 —，否则连起来截断；commandFull 为全文', () => {
    expect(commandText(null)).toBe('—');
    expect(commandText(['a', 'b'])).toBe('a b');
    expect(commandFull(['a', 'b'])).toBe('a b');
    expect(commandFull(null)).toBeNull();
  });

  it('canProbe/canModels：来源非 missing；adapter pi 且来源非 missing', () => {
    expect(canProbe('env')).toBe(true);
    expect(canProbe('missing')).toBe(false);
    expect(canModels('pi', 'env')).toBe(true);
    expect(canModels('pi', 'missing')).toBe(false);
    expect(canModels('claude-code', 'env')).toBe(false);
  });
});

describe('地址拼接', () => {
  it('attemptSeg 取最后一段；evidence/events/group 路径经编码', () => {
    expect(attemptSeg('nest/x/attempt-007')).toBe('attempt-007');
    expect(evidencePath('can a', 'can a/attempt-001')).toBe('/tasks/can%20a/attempt-001');
    expect(eventsPath('run-a', 'run-a/attempt-003')).toBe('/tasks/run-a/attempt-003?tab=events');
    expect(groupPath('review')).toBe('/tasks?group=review');
  });
});

describe('copyText 三态', () => {
  it('成功 copied、无 writeText unavailable、抛错或拒绝 failed', async () => {
    expect(await copyText('a', { writeText: async () => {} })).toBe('copied');
    expect(await copyText('a', {})).toBe('unavailable');
    expect(await copyText('a', { writeText: async () => { throw new Error('x'); } })).toBe('failed');
    expect(await copyText('a', { writeText: () => Promise.reject(new Error('x')) })).toBe('failed');
  });
});
