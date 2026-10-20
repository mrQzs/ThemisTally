// 数据层（合同第 7 条 / D06、D07）：13 个读函数返回夹具与信封字段；?mock= 五态；getMeta 不受开关影响；
// empty 只对五个列表资源生效；夹具外参数返回 ok:false；每次返回新深拷贝。
import { beforeEach, describe, expect, it } from 'vitest';
import * as api from '../src/api';
import metaJson from '../src/mock/meta.json';
import statusJson from '../src/mock/status.json';
import attemptJson from '../src/mock/attempt.json';
import fileReportJson from '../src/mock/file-executor-report.json';
import fileEventsJson from '../src/mock/file-events.json';
import rolesJson from '../src/mock/roles.json';
import profilesJson from '../src/mock/profiles.json';
import presetsJson from '../src/mock/presets.json';
import presetDiffJson from '../src/mock/preset-diff.json';
import runtimesJson from '../src/mock/runtimes.json';
import pluginsJson from '../src/mock/plugins.json';
import historyJson from '../src/mock/history.json';
import usageJson from '../src/mock/usage.json';
import secretsJson from '../src/mock/secrets.json';

function setMock(mode: string | null) {
  location.hash = mode ? `#/overview?mock=${mode}` : '#/overview';
}

const ERROR_MESSAGE = 'ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied';

describe('数据层：夹具与信封', () => {
  beforeEach(() => setMock('data'));

  it('getMeta 返回 meta 夹具、信封字段齐全、command 为 --version', async () => {
    const env = await api.getMeta();
    expect(env).toEqual({ ok: true, exit_code: 0, data: metaJson, output: [], messages: [], command: ['--version'], elapsed_ms: 0 });
  });

  it('getStatus 返回 status 夹具、command 为 [status]', async () => {
    const env = await api.getStatus();
    expect(env.ok).toBe(true);
    expect(env.data).toEqual(statusJson);
    expect(env.command).toEqual(['status']);
  });

  it('getAttempt 命中 logs-cat/attempt-002，command 为 logs show', async () => {
    const env = await api.getAttempt('logs-cat', 'attempt-002');
    expect(env.ok).toBe(true);
    expect(env.data).toEqual(attemptJson);
    expect(env.command).toEqual(['logs', 'show', 'logs-cat/attempt-002']);
  });

  it('readFile 命中 executor-report.md 与 events.jsonl，command 为 logs cat', async () => {
    const report = await api.readFile('logs-cat', 'attempt-002', 'executor-report.md');
    expect(report.ok).toBe(true);
    expect(report.data).toEqual(fileReportJson);
    expect(report.command).toEqual(['logs', 'cat', 'logs-cat/attempt-002', 'executor-report.md']);
    const events = await api.readFile('logs-cat', 'attempt-002', 'events.jsonl');
    expect(events.ok).toBe(true);
    expect(events.data).toEqual(fileEventsJson);
  });

  it('其余读函数返回各自夹具与 CLI 参数数组', async () => {
    expect((await api.getRoles()).data).toEqual(rolesJson);
    expect((await api.getRoles()).command).toEqual(['config', 'role', 'show']);
    expect((await api.getProfiles()).data).toEqual(profilesJson);
    expect((await api.getPresets()).data).toEqual(presetsJson);
    expect((await api.diffPresets('default', 'economy')).data).toEqual(presetDiffJson);
    expect((await api.diffPresets('default', 'economy')).command).toEqual(['config', 'preset', 'diff', 'default', 'economy']);
    expect((await api.getRuntimes()).data).toEqual(runtimesJson);
    expect((await api.getPlugins()).data).toEqual(pluginsJson);
    expect((await api.getPlugins()).command).toEqual(['plugins', 'list']);
    expect((await api.getHistory()).data).toEqual(historyJson);
    expect((await api.getUsage()).data).toEqual(usageJson);
    expect((await api.listSecrets()).data).toEqual(secretsJson);
  });

  it('夹具外参数返回 ok:false、exit_code 2、data null、一条 ERROR', async () => {
    const a = await api.getAttempt('other', 'attempt-009');
    expect(a.ok).toBe(false);
    expect(a.exit_code).toBe(2);
    expect(a.data).toBeNull();
    expect(a.messages).toHaveLength(1);
    expect(a.messages[0]).toContain('夹具里没有这份数据');
    const b = await api.readFile('logs-cat', 'attempt-002', 'nope.md');
    expect(b.ok).toBe(false);
    const c = await api.readFile('logs-cat', 'attempt-002', 'executor-report.md', 'cur');
    expect(c.ok).toBe(false);
    const d = await api.diffPresets('default', 'other');
    expect(d.ok).toBe(false);
  });

  it('每次返回新深拷贝：改动不影响下一次', async () => {
    const first = await api.getStatus();
    (first.data as typeof statusJson).push({ attempt: 'x' } as never);
    (first.data as typeof statusJson)[0].state = 'MUTATED';
    const second = await api.getStatus();
    expect(second.data).toEqual(statusJson);
  });
});

describe('数据层：?mock= 开关', () => {
  it('loading：getStatus 永不兑现；getMeta 不受影响', async () => {
    setMock('loading');
    let resolved = false;
    api.getStatus().then(() => { resolved = true; });
    await Promise.resolve();
    await Promise.resolve();
    expect(resolved).toBe(false);
    const meta = await api.getMeta();
    expect(meta.data).toEqual(metaJson);
  });

  it('error：ok 假、exit_code 2、内核报错原文', async () => {
    setMock('error');
    const env = await api.getStatus();
    expect(env.ok).toBe(false);
    expect(env.exit_code).toBe(2);
    expect(env.data).toBeNull();
    expect(env.command).toEqual(['status']);
    expect(env.messages).toEqual([ERROR_MESSAGE]);
  });

  it('empty：五个列表资源返回空形状，其余照常', async () => {
    setMock('empty');
    expect((await api.getStatus()).data).toEqual([]);
    expect((await api.getRuntimes()).data).toEqual({ runtimes: [] });
    expect((await api.listSecrets()).data).toEqual({ secrets: [] });
    expect((await api.getPlugins()).data).toEqual({ plugins_root_link: false, plugins: [], not_installed: [], problems: [] });
    expect((await api.getHistory()).data).toEqual({ entries: [], broken_lines: [], external_before_first: 0 });
    // 不在五资源里的照常
    expect((await api.getRoles()).data).toEqual(rolesJson);
    expect((await api.getUsage()).data).toEqual(usageJson);
    // getMeta 不受影响
    expect((await api.getMeta()).data).toEqual(metaJson);
  });

  it('offline 与 data 对数据函数等效（只改连接状态）', async () => {
    setMock('offline');
    expect((await api.getStatus()).data).toEqual(statusJson);
  });
});
