// 只读页面二的纯函数自测：千分位、本地与 UTC 时间、保留 mock 的地址、复制三结果之外的字面规则，
// 以及凭据、日志、插件、历史四页的取值映射（合同 Steps 2–9 的纯函数部分）。
import { describe, expect, it } from 'vitest';
import {
  formatLocalUtc,
  formatThousands,
  hrefWithMock,
} from '../src/pages/readonly2/common-format';
import { SOURCE_LEGEND, sourceTag, usedBySegments } from '../src/pages/readonly2/secrets-logic';
import {
  canHighlight,
  excerptSegments,
  groupMatches,
  sharePercent,
  shareText,
  taskOptions,
  usageStatusTone,
} from '../src/pages/readonly2/logs-logic';
import {
  drawerWarning,
  enabledView,
  joinList,
  lockView,
  pluginAction,
  statusTone,
} from '../src/pages/readonly2/plugins-logic';
import {
  actionTitle,
  actorTone,
  diffKind,
  drawerTitle,
  resourceLabel,
  rollbackNote,
  sortedEntries,
  stateText,
  timeCell,
  type HistoryEntry,
} from '../src/pages/readonly2/history-logic';

const entry = (o: Partial<HistoryEntry>): HistoryEntry => ({
  number: 1,
  resource: 'config',
  at: '2026-10-18T02:00:00Z',
  action: 'config.set',
  target: 'x',
  actor: 'user',
  confirmation: 'none',
  state: 'published',
  changed_keys: null,
  note: null,
  external_changes: 0,
  ...o,
});

describe('公共件：千分位与时间', () => {
  it('千分位手写；缺失显示「未知」', () => {
    expect(formatThousands(0)).toBe('0');
    expect(formatThousands(543)).toBe('543');
    expect(formatThousands(7654321)).toBe('7,654,321');
    expect(formatThousands(22031448)).toBe('22,031,448');
    expect(formatThousands(-1234)).toBe('-1,234');
    expect(formatThousands(null)).toBe('未知');
    expect(formatThousands(undefined)).toBe('未知');
    expect(formatThousands('12')).toBe('未知');
    expect(formatThousands(Number.NaN)).toBe('未知');
  });

  it('formatLocalUtc 返回本地加 UTC；解析不了返回 null', () => {
    const d = new Date('2026-10-18T02:02:11Z');
    const pad = (n: number) => String(n).padStart(2, '0');
    const want =
      `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` +
      `（UTC ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}）`;
    expect(formatLocalUtc('2026-10-18T02:02:11Z')).toBe(want);
    expect(formatLocalUtc('not-a-time')).toBeNull();
  });
});

describe('公共件：保留 mock 的地址', () => {
  it('当前地址带 ?mock= 时一并带上，否则不带查询', () => {
    window.location.hash = '#/logs?mock=data';
    expect(hrefWithMock('/settings')).toBe('#/settings?mock=data');
    window.location.hash = '#/logs?mock=offline';
    expect(hrefWithMock('/settings')).toBe('#/settings?mock=offline');
    window.location.hash = '#/logs';
    expect(hrefWithMock('/settings')).toBe('#/settings');
    window.location.hash = '#/logs?mock=bogus';
    expect(hrefWithMock('/settings')).toBe('#/settings?mock=bogus');
    window.location.hash = '';
  });
});

describe('凭据：用在哪里与来源', () => {
  it('相邻 profile 合并、决策模型、未知 kind 原样带 id', () => {
    expect(usedBySegments([{ kind: 'profile', id: 'p1' }, { kind: 'profile', id: 'p2' }, { kind: 'decisions' }]))
      .toEqual([{ kind: 'profiles', label: 'profile', ids: ['p1', 'p2'] }, { kind: 'decisions', label: '决策模型', ids: [] }]);
    expect(usedBySegments([{ kind: 'decisions' }, { kind: 'profile', id: 'p3' }, { kind: 'weird', id: 'w1' }, { kind: 'weird2' }]))
      .toEqual([
        { kind: 'decisions', label: '决策模型', ids: [] },
        { kind: 'profiles', label: 'profile', ids: ['p3'] },
        { kind: 'other', label: 'weird', ids: ['w1'] },
        { kind: 'other', label: 'weird2', ids: [] },
      ]);
    expect(usedBySegments([{ kind: 'profile', id: 'p1' }, { kind: 'decisions' }, { kind: 'profile', id: 'p2' }]))
      .toHaveLength(3);
    expect(usedBySegments(null)).toEqual([]);
  });

  it('来源四种取值与未知值', () => {
    expect(sourceTag('env')).toEqual({ label: '环境变量', tone: 'success', icon: null });
    expect(sourceTag('credential_store')).toEqual({ label: '系统凭据库', tone: 'success', icon: 'store' });
    expect(sourceTag('file')).toEqual({ label: '0600 文件', tone: 'success', icon: null });
    expect(sourceTag('none')).toEqual({ label: '没有', tone: 'danger', icon: 'missing' });
    expect(sourceTag('vault')).toEqual({ label: 'vault', tone: 'neutral', icon: null });
    expect(SOURCE_LEGEND.map((s) => s.tag.label)).toEqual(['环境变量', '系统凭据库', '0600 文件', '没有']);
  });
});

describe('日志与用量：选项、占比、分组与高亮', () => {
  const usage = {
    executor: {
      attempts: [
        { task: 't-one', attempt: 'a1' },
        { task: 't-two', attempt: 'a2' },
        { task: 't-one', attempt: 'a3' },
      ],
      by_model: [],
      totals: { totalTokens: 1000 },
      counts: {},
    },
  };

  it('任务下拉：首项全部任务，其余按首次出现去重', () => {
    expect(taskOptions(usage)).toEqual([
      { value: '', label: '全部任务' },
      { value: 't-one', label: 't-one' },
      { value: 't-two', label: 't-two' },
    ]);
    expect(taskOptions({})).toEqual([{ value: '', label: '全部任务' }]);
  });

  it('占比一位小数；分母为 0 或缺失显示「—」', () => {
    expect(shareText(250000, 1000000)).toBe('25.0%');
    expect(shareText(333333, 1000000)).toBe('33.3%');
    expect(shareText(0, 1000000)).toBe('0.0%');
    expect(shareText(1, 0)).toBe('—');
    expect(shareText(1, null)).toBe('—');
    expect(sharePercent(1, 0)).toBeNull();
  });

  it('状态色调与中文 title', () => {
    expect(usageStatusTone('known')).toEqual({ tone: 'success', title: '已回报' });
    expect(usageStatusTone('partial')).toEqual({ tone: 'warning', title: '部分回报' });
    expect(usageStatusTone('unknown')).toEqual({ tone: 'neutral', title: '未回报' });
    expect(usageStatusTone('mystery')).toEqual({ tone: 'neutral', title: null });
  });

  it('按 (task, attempt) 首次出现分组', () => {
    const groups = groupMatches([
      { task: 'ta', attempt: 'a1', path: 'a.md', line: 1, text: 'x' },
      { task: 'tb', attempt: 'a9', path: 'b.md', line: 2, text: 'x' },
      { task: 'ta', attempt: 'a1', path: 'c.md', line: 3, text: 'x' },
      { task: 'ta', attempt: 'a2', path: 'd.md', line: 4, text: 'x' },
    ]);
    expect(groups.map((g) => `${g.task}/${g.attempt}`)).toEqual(['ta/a1', 'tb/a9', 'ta/a2']);
    expect(groups[0].items).toHaveLength(2);
  });

  it('高亮：命中段切出来；编译失败与带量词的分组整行照常', () => {
    expect(excerptSegments('first logs_cat here', 'logs[_ ]cat')).toEqual([
      { text: 'first ', hit: false },
      { text: 'logs_cat', hit: true },
      { text: ' here', hit: false },
    ]);
    expect(canHighlight('logs[_ ]cat')).toBe(true);
    expect(canHighlight('(?P<n>logs)')).toBe(false);
    for (const q of ['(logs)+', '(logs)*', '(logs)?', '(logs){1}', '(l|x)+']) {
      expect(canHighlight(q), q).toBe(false);
      expect(excerptSegments('first logs_cat here', q)).toEqual([{ text: 'first logs_cat here', hit: false }]);
    }
    expect(canHighlight('logs[_ ]cat+')).toBe(true);
  });

  it('空匹配跳过，不生成 mark', () => {
    expect(excerptSegments('first logs_cat here', 'z*').every((s) => !s.hit)).toBe(true);
    expect(excerptSegments('abc', '').every((s) => !s.hit)).toBe(true);
  });
});

describe('插件：取值映射', () => {
  it('启用三种写法加未知', () => {
    expect(enabledView('启用')).toEqual({ text: '启用', tone: 'brand' });
    expect(enabledView('是')).toEqual({ text: '是', tone: 'brand' });
    expect(enabledView('停用')).toEqual({ text: '停用', tone: 'neutral' });
    expect(enabledView('否')).toEqual({ text: '否', tone: 'neutral' });
    expect(enabledView('不限制')).toEqual({ text: '不限制', tone: null });
    expect(enabledView('怪值')).toEqual({ text: '怪值', tone: 'neutral' });
  });

  it('锁与资源四类取值', () => {
    expect(lockView('一致', '')).toEqual({ text: '一致', tone: 'success', icon: 'ok', title: null });
    expect(lockView('漂移', '锁与内容不一致')).toEqual({ text: '漂移', tone: 'warning', icon: 'warn', title: '锁与内容不一致' });
    expect(lockView('不一致', 'r')).toEqual({ text: '不一致', tone: 'warning', icon: 'warn', title: 'r' });
    expect(lockView('无效：manifest 读不出来', '被阻塞').tone).toBe('danger');
    expect(lockView('无效：manifest 读不出来', '被阻塞').icon).toBe('bad');
    expect(lockView('-', '')).toEqual({ text: '—', tone: 'neutral', icon: null, title: null });
    expect(lockView('其他怪值', '').tone).toBe('warning');
  });

  it('状态色调、操作入口、提示条与列表', () => {
    expect(statusTone('READY')).toBe('success');
    expect(statusTone('DRIFT')).toBe('warning');
    expect(statusTone('BLOCKED')).toBe('danger');
    expect(statusTone('WEIRD')).toBe('neutral');
    expect(pluginAction('启用')).toEqual({ kind: 'disable', label: '停用…' });
    expect(pluginAction('是')).toEqual({ kind: 'disable', label: '停用…' });
    expect(pluginAction('停用')).toEqual({ kind: 'enable', label: '启用…' });
    expect(pluginAction('否')).toEqual({ kind: 'enable', label: '启用…' });
    expect(pluginAction('不限制')).toEqual({ kind: 'detail' });
    expect(drawerWarning('DRIFT', '锁与内容不一致', ['fs.write', 'net.http']))
      .toBe('锁与内容不一致。缺的权限：fs.write、net.http。');
    expect(drawerWarning('DRIFT', '', ['fs.write'])).toBe('缺的权限：fs.write。');
    expect(drawerWarning('WEIRD', '', [])).toBe('WEIRD');
    expect(joinList(['a', 'b'])).toBe('a、b');
    expect(joinList([])).toBe('（无）');
    expect(joinList(null)).toBe('（无）');
  });
});

describe('历史：文字与色调', () => {
  it('动作的中文说明；表外动作没有说明', () => {
    expect(actionTitle('config.set')).toBe('设置配置键');
    expect(actionTitle('config.unset')).toBe('删除配置键');
    expect(actionTitle('config.rollback')).toBe('回滚配置');
    expect(actionTitle('preset.use')).toBe('切换方案');
    expect(actionTitle('preset.save')).toBe('保存方案');
    expect(actionTitle('preset.remove')).toBe('删除方案');
    expect(actionTitle('role.set')).toBe('修改角色绑定');
    expect(actionTitle('profile.add')).toBe('新建 profile');
    expect(actionTitle('runtime.add')).toBe('登记 runtime');
    expect(actionTitle('external')).toBe('检测到界面与命令之外的改动');
    expect(actionTitle('custom.act')).toBeNull();
  });

  it('资源、状态、执行者', () => {
    expect(resourceLabel('config')).toBe('配置');
    expect(resourceLabel('local')).toBe('本机文件');
    expect(resourceLabel('weird-res')).toBe('weird-res');
    expect(stateText({ state: 'published' })).toBe('已发布');
    expect(stateText({ state: 'aborted' })).toBe('已中止');
    expect(stateText({ state: 'unknown' })).toBe('未知');
    expect(stateText({ state: null })).toBe('进行中或已中断');
    expect(stateText({ state: 'published', resolved: true })).toBe('已发布（补判）');
    expect(actorTone('user-ui')).toBe('brand');
    expect(actorTone('user')).toBe('neutral');
    expect(actorTone('agent:planning_review')).toBe('info');
    expect(actorTone('undeclared')).toBe('warning');
    expect(actorTone('something')).toBe('neutral');
  });

  it('倒序、时间格、标题与底栏说明', () => {
    expect(sortedEntries([entry({ number: 1 }), entry({ number: 8 }), entry({ number: 3 })]).map((e) => e.number))
      .toEqual([8, 3, 1]);
    const now = new Date('2026-10-18T03:00:00Z').getTime();
    expect(timeCell('2026-10-18T02:02:11Z', now).text).toBe('57 分钟前');
    expect(timeCell('2026-10-18T02:02:11Z', now).title).toBe(formatLocalUtc('2026-10-18T02:02:11Z'));
    expect(timeCell('not-a-time', now)).toEqual({ text: 'not-a-time', title: null });
    expect(drawerTitle(entry({ number: 42, action: 'preset.use', target: 'default' }))).toBe('#42 · preset.use default');
    expect(drawerTitle(entry({ number: 3, action: 'custom.act', target: '' }))).toBe('#3 · custom.act');
    expect(rollbackNote(entry({ number: 8 }), 8)).toBe('这是最新的一条，回滚后没有变化');
    expect(rollbackNote(entry({ number: 4, resource: 'local' }), 8)).toBe('本机文件不存快照，不能回滚');
    expect(rollbackNote(entry({ number: 5 }), 8)).toBe('');
  });

  it('键级差异五种情形按顺序取第一条成立的', () => {
    const local = entry({ number: 4, resource: 'local', changed_keys: ['k'], note: '（含疑似凭据，不显示）' });
    expect(diffKind(local, { diff: [{ key: 'k', old: 1, new: 2 }] })).toEqual({ kind: 'local' });
    expect(diffKind(entry({}), { diff: [{ key: 'k', old: 1, new: 2 }] })).toEqual({
      kind: 'keys',
      diff: [{ key: 'k', old: 1, new: 2 }],
    });
    expect(diffKind(entry({}), { diff: [] })).toEqual({ kind: 'empty' });
    expect(diffKind(entry({ changed_keys: ['pricing'], note: '（含疑似凭据，不显示）' }), { diff: null, note: '（含疑似凭据，不显示）' }))
      .toEqual({ kind: 'masked-keys', placeholder: '（含疑似凭据，不显示）', keys: ['pricing'] });
    expect(diffKind(entry({ changed_keys: null, note: '疑似凭据，不显示' }), { diff: null, note: '疑似凭据，不显示' }))
      .toEqual({ kind: 'masked-note', note: '疑似凭据，不显示' });
    expect(diffKind(entry({}), { diff: null, note: '快照太旧' })).toEqual({ kind: 'note', note: '快照太旧' });
    expect(diffKind(entry({}), { diff: null, note: null })).toEqual({ kind: 'note', note: null });
  });
});
