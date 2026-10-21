// 页内读取函数（读法 A）自测：命令数组、信封七个字段、五个 ?mock= 开关、夹具之外的参数、
// 检索按 max 截断与按 task 过滤、深拷贝（合同 Steps 3；接本机服务那一片推翻）。
import { describe, expect, it } from 'vitest';
import { getHistoryEntry, getPlugin, searchLogs } from '../src/pages/readonly2/common-readers';
import { SEARCH_PATTERN } from '../src/mock/readonly2-search';

const KEYS = ['command', 'data', 'elapsed_ms', 'exit_code', 'messages', 'ok', 'output'];

function setMock(v: string | null) {
  window.location.hash = v ? `#/logs?mock=${v}` : '#/logs';
}

describe('页内读取函数：信封与命令数组', () => {
  it('data：信封七个字段；command 数组依次是 logs search q [--task t] --max N、config history show n、plugins show id', async () => {
    setMock('data');
    const a = await searchLogs(SEARCH_PATTERN, null, 50);
    expect(Object.keys(a).sort()).toEqual(KEYS);
    expect(a.ok).toBe(true);
    expect(a.exit_code).toBe(0);
    expect(a.command).toEqual(['logs', 'search', SEARCH_PATTERN, '--max', '50']);
    expect((await searchLogs(SEARCH_PATTERN, 'logs-cat', 7)).command)
      .toEqual(['logs', 'search', SEARCH_PATTERN, '--task', 'logs-cat', '--max', '7']);
    expect((await getHistoryEntry(42)).command).toEqual(['config', 'history', 'show', '42']);
    expect((await getPlugin('docs-checks')).command).toEqual(['plugins', 'show', 'docs-checks']);
  });

  it('loading：三个函数都返回永不兑现的 Promise（先于参数校验）', async () => {
    setMock('loading');
    const pending = (p: Promise<unknown>) =>
      Promise.race([p.then(() => 'done', () => 'done'), Promise.resolve('tick')]);
    for (const p of [
      searchLogs(SEARCH_PATTERN, null, 50),
      searchLogs('zzz-not-in-fixture', null, 50),
      getHistoryEntry(42),
      getHistoryEntry(7),
      getPlugin('docs-checks'),
      getPlugin('nope'),
    ]) {
      expect(await pending(p)).toBe('tick');
    }
  });

  it('error：ok false、exit_code 2、data null、messages 是报错原文（先于参数校验）', async () => {
    setMock('error');
    for (const r of [
      await searchLogs(SEARCH_PATTERN, null, 50),
      await searchLogs('zzz', null, 50),
      await getHistoryEntry(42),
      await getHistoryEntry(7),
      await getPlugin('docs-checks'),
      await getPlugin('nope'),
    ]) {
      expect(r.ok).toBe(false);
      expect(r.exit_code).toBe(2);
      expect(r.data).toBeNull();
      expect(r.messages).toEqual(['ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied']);
    }
  });

  it('empty：检索返回空 matches（truncated 假、两个计数 0）；另两个照常', async () => {
    setMock('empty');
    const r = await searchLogs(SEARCH_PATTERN, null, 50);
    expect(r.ok).toBe(true);
    expect(r.data?.matches).toEqual([]);
    expect(r.data?.truncated).toBe(false);
    expect(r.data?.skipped_links).toBe(0);
    expect(r.data?.skipped_large).toBe(0);
    expect((await getHistoryEntry(42)).ok).toBe(true);
    expect((await getPlugin('docs-checks')).ok).toBe(true);
  });

  it('offline 与 data 一样返回夹具；认不出的取值按 data', async () => {
    setMock('data');
    const a = await searchLogs(SEARCH_PATTERN, null, 50);
    setMock('offline');
    expect(await searchLogs(SEARCH_PATTERN, null, 50)).toEqual(a);
    setMock(null);
    expect((await searchLogs(SEARCH_PATTERN, null, 50)).ok).toBe(true);
    window.location.hash = '#/logs?mock=bogus';
    expect((await getPlugin('docs-checks')).ok).toBe(true);
  });

  it('夹具之外的参数：ok false、exit_code 2、messages 以「ERROR 夹具里没有这份数据：」开头', async () => {
    setMock('data');
    for (const r of [
      await searchLogs('zzz-not-in-fixture', null, 50),
      await getHistoryEntry(7),
      await getHistoryEntry(0),
      await getPlugin('nope'),
    ]) {
      expect(r.ok).toBe(false);
      expect(r.exit_code).toBe(2);
      expect(r.data).toBeNull();
      expect(r.messages[0].startsWith('ERROR 夹具里没有这份数据：')).toBe(true);
    }
  });
});

describe('页内读取函数：检索夹具', () => {
  it('固定模式：两个 attempt 各至少一组，skipped_large ≥ 1，摘录 ≤ 200 字且命中模式，路径只用允许的后缀', async () => {
    setMock('data');
    const r = await searchLogs(SEARCH_PATTERN, null, 500);
    const d = r.data!;
    expect(r.ok).toBe(true);
    expect(d.truncated).toBe(false);
    expect(d.skipped_large).toBeGreaterThanOrEqual(1);
    expect(new Set(d.matches.map((m) => `${m.task}/${m.attempt}`)).size).toBeGreaterThanOrEqual(2);
    for (const m of d.matches) {
      expect(/\.(md|txt|log|json|jsonl)$/.test(m.path)).toBe(true);
      expect(m.line >= 1).toBe(true);
      expect(m.text.length).toBeLessThanOrEqual(200);
      expect(new RegExp(SEARCH_PATTERN).test(m.text)).toBe(true);
    }
  });

  it('按 max 截成前 max 条并置 truncated；恰好等于总数时不截断', async () => {
    setMock('data');
    const full = (await searchLogs(SEARCH_PATTERN, null, 500)).data!;
    const total = full.matches.length;
    expect(total).toBeGreaterThanOrEqual(2);
    const one = (await searchLogs(SEARCH_PATTERN, null, 1)).data!;
    expect(one.matches).toEqual(full.matches.slice(0, 1));
    expect(one.truncated).toBe(true);
    const exact = (await searchLogs(SEARCH_PATTERN, null, total)).data!;
    expect(exact.matches).toHaveLength(total);
    expect(exact.truncated).toBe(false);
    const less = (await searchLogs(SEARCH_PATTERN, null, total - 1)).data!;
    expect(less.matches).toEqual(full.matches.slice(0, total - 1));
    expect(less.truncated).toBe(true);
  });

  it('按 task 过滤：只留该任务的命中、保持顺序；过滤后多于 max 才截断', async () => {
    setMock('data');
    const full = (await searchLogs(SEARCH_PATTERN, null, 500)).data!;
    for (const task of Array.from(new Set(full.matches.map((m) => m.task)))) {
      const want = full.matches.filter((m) => m.task === task);
      const got = (await searchLogs(SEARCH_PATTERN, task, 500)).data!;
      expect(got.matches).toEqual(want);
      expect(got.truncated).toBe(false);
      if (want.length >= 2) {
        const cut = (await searchLogs(SEARCH_PATTERN, task, 1)).data!;
        expect(cut.matches).toEqual(want.slice(0, 1));
        expect(cut.truncated).toBe(true);
      }
    }
  });
});

describe('页内读取函数：夹具形状与深拷贝', () => {
  it('历史 42 两键差异；41 本机文件两个 64 位 sha256；40 diff 为 null 且 note 疑似凭据', async () => {
    setMock('data');
    const e42 = (await getHistoryEntry(42)).data!;
    expect(e42.number).toBe(42);
    expect(e42.diff?.map((k) => k.key)).toEqual(['active_preset', 'roles.execution.profile']);
    const e41 = (await getHistoryEntry(41)).data!;
    expect(e41.resource).toBe('local');
    expect(/^[0-9a-f]{64}$/.test(e41.before_sha256!)).toBe(true);
    expect(/^[0-9a-f]{64}$/.test(e41.after_sha256!)).toBe(true);
    const e40 = (await getHistoryEntry(40)).data!;
    expect(e40.diff).toBeNull();
    expect(String(e40.note)).toContain('疑似凭据');
  });

  it('插件详情：三个插件与 plugins.json 一致；docs-checks 缺 fs.write、资源两行一致、锁有 generation 与 64 位 sha256', async () => {
    setMock('data');
    for (const id of ['decisions', 'code-change', 'docs-checks']) {
      const r = await getPlugin(id);
      expect(r.ok, id).toBe(true);
      expect(r.data?.plugin_id).toBe(id);
    }
    const d = (await getPlugin('docs-checks')).data!;
    expect(d.permissions).toContain('fs.read');
    expect(d.permissions).toContain('fs.write');
    expect(d.config.missing_permissions).toEqual(['fs.write']);
    expect(d.resources).toHaveLength(2);
    for (const r of d.resources) expect(r.status).toBe('一致');
    expect(d.lock.generation).toBeDefined();
    expect(/^[0-9a-f]{64}$/.test(d.lock.lock_sha256)).toBe(true);
  });

  it('改返回值不影响下一次读取', async () => {
    setMock('data');
    const a = await searchLogs(SEARCH_PATTERN, null, 50);
    const keep = JSON.parse(JSON.stringify(a.data));
    a.data!.matches.length = 0;
    a.data!.truncated = !a.data!.truncated;
    expect((await searchLogs(SEARCH_PATTERN, null, 50)).data).toEqual(keep);
    const p = await getPlugin('docs-checks');
    const keepP = JSON.parse(JSON.stringify(p.data));
    p.data!.permissions.push('x');
    expect((await getPlugin('docs-checks')).data).toEqual(keepP);
    const h = await getHistoryEntry(42);
    const keepH = JSON.parse(JSON.stringify(h.data));
    h.data!.diff!.length = 0;
    expect((await getHistoryEntry(42)).data).toEqual(keepH);
    window.location.hash = '';
  });
});
