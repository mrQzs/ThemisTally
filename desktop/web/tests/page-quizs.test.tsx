// Quizs 一块（合同第 9 节）：桩模式下经 ?quizs= 挂载运行时页，逐字核对两张表、五个情景与区块规矩；
// providers / live / runtimes 三种失败用替身 client 注入——Quizs 读失败只影响这一块，runtimes 失败整页出错。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import App from '../src/App';
import { setLiveClientForTests } from '../src/live/mode';
import { formatLocalUtc } from '../src/components/RelativeTime';

beforeEach(() => {
  location.hash = '';
});
afterEach(() => {
  cleanup();
  location.hash = '';
  setLiveClientForTests(undefined);
});

const text = (el: any) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string) => Array.from(root.querySelectorAll(sel));
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mount(hash: string) {
  location.hash = hash;
  const r = render(<App />);
  await flush();
  return r;
}
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function pageRoot(): any {
  return document.querySelector('[data-page="runtimes"]');
}
function sectionNamed(root: any, title: string): any {
  return qa(root, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === title : false;
  }) || null;
}
function quizsSection(): any {
  const sec = sectionNamed(pageRoot(), 'Quizs');
  expect(sec, '应有「Quizs」区块').toBeTruthy();
  return sec;
}
function tableOf(root: any, label: string): any {
  const t = root.querySelector(`table[aria-label="${label}"]`);
  expect(t, `应有表 aria-label=${label}`).toBeTruthy();
  return t;
}
function headsOf(table: any): string[] {
  return qa(table, 'thead th').map(text);
}
function rowsOf(table: any): Array<Record<string, any>> {
  const heads = qa(table, 'thead th').map(text);
  return qa(table, 'tbody tr').map((tr: any) => {
    const o: Record<string, any> = {};
    qa(tr, 'td').forEach((td: any, i: number) => { o[heads[i]] = td; });
    return o;
  });
}
function rowByColumn(table: any, column: string, value: string): Record<string, any> {
  const hit = rowsOf(table).find((r) => text(r[column]) === value);
  expect(hit, `应有一行 ${column}=${value}`).toBeTruthy();
  return hit as Record<string, any>;
}
function toneOf(cell: any): string | null {
  const tag = cell.querySelector('[data-tone]');
  return tag ? tag.getAttribute('data-tone') : null;
}

// ok 情景的取值照 src/mock/quizs.ts：两个提供方、两套 live（一封信箱、一套环境变量）。
const PROVIDERS = {
  providers: [
    { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
    { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
  ],
};
const LIVE = {
  live: [
    {
      source: 'mailbox', provider: 'deepseek', problem: null,
      status: {
        state: 'ready', problem: null, missing: [],
        certificate: { expires_at_ms: 1790000000000 }, profile: { valid_until: '2026-11-20T08:00:00.000Z' },
      },
    },
    {
      source: 'env', provider: 'deepseek', problem: null,
      status: {
        state: 'ready', problem: null, missing: [],
        certificate: { expires_at_ms: 1790000000000 }, profile: { valid_until: '2026-11-20T08:00:00.000Z' },
      },
    },
  ],
};
const RUNTIMES = { runtimes: [{ id: 'pi', adapter: 'pi', source: 'env', command: ['pi'], notes: [] }] };

function envelope(data: unknown, command: string[], ok = true, exitCode: number | null = 0, messages: string[] = []): any {
  return { ok, exit_code: exitCode, data, output: [], messages, command, elapsed_ms: 0 };
}

// 替身 client：按路径给信封，over 里的路径换成失败信封（真实模式下 ?quizs= 与 ?mock= 都不生效）。
function clientWith(over: Record<string, () => Promise<any>>): string[] {
  const paths: string[] = [];
  const client = {
    get(path: string) {
      paths.push(path);
      const bad = over[path];
      if (bad) return bad();
      if (path === '/api/v1/runtimes') return Promise.resolve(envelope(RUNTIMES, ['config', 'runtime', 'list']));
      if (path === '/api/v1/quizs/providers') return Promise.resolve(envelope(PROVIDERS, ['config', 'quizs', 'providers', '--json']));
      if (path === '/api/v1/quizs/live') return Promise.resolve(envelope(LIVE, ['config', 'quizs', 'live', '--json']));
      return Promise.resolve(envelope(null, []));
    },
    post() { return Promise.resolve({ status: 200, body: envelope(null, []) }); },
    getRaw() { return Promise.resolve({ status: 200, body: null }); },
  };
  setLiveClientForTests(client as any);
  return paths;
}

describe('Quizs 一块：ok 情景', () => {
  it('Quizs 在「就绪检查」之后；提供方档案表四列两行逐字；live 表六列两套就绪；容器类不用 rt-table', async () => {
    await mount('#/runtimes');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    const titles = qa(pageRoot(), 'section').map((s: any) => {
      const id = s.getAttribute('aria-labelledby');
      return text(id ? document.getElementById(id) : null);
    });
    expect(titles.slice(0, 2)).toEqual(['已登记', '就绪检查']);
    expect(titles.indexOf('Quizs')).toBeGreaterThan(titles.indexOf('就绪检查'));
    const pt = tableOf(quizsSection(), 'Quizs 提供方档案');
    expect(headsOf(pt)).toEqual(['提供方', '模型', '思考档位', '计费']);
    const stepfun = rowByColumn(pt, '提供方', 'stepfun');
    expect(text(stepfun['模型'])).toBe('step-5-preview');
    expect(text(stepfun['思考档位'])).toBe('low、medium、high');
    expect(text(stepfun['计费'])).toBe('套餐额度');
    const deepseek = rowByColumn(pt, '提供方', 'deepseek');
    expect(text(deepseek['模型'])).toBe('deepseek-chat');
    expect(text(deepseek['思考档位'])).toBe('low、high');
    expect(text(deepseek['计费'])).toBe('预付余额');
    expect(rowsOf(pt).length).toBe(2);
    const lt = tableOf(quizsSection(), 'Quizs live 套');
    expect(headsOf(lt)).toEqual(['提供方', '来源', '状态', '证书到期', '档案有效期', '下一步']);
    const mailbox = rowByColumn(lt, '来源', '信箱');
    const fromEnv = rowByColumn(lt, '来源', '环境变量');
    for (const row of [mailbox, fromEnv]) {
      expect(text(row['提供方'])).toBe('deepseek');
      expect(text(row['状态'])).toBe('就绪');
      expect(toneOf(row['状态']), '只有「就绪」不醒目').toBe('success');
      expect(text(row['下一步'])).toBe('不用动');
    }
    // 时刻只比 formatLocalUtc 的输出（本地时间随机器时区变，不写死）。
    expect(text(mailbox['证书到期'])).toBe(formatLocalUtc(new Date(1790000000000).toISOString()));
    expect(text(mailbox['档案有效期'])).toBe(formatLocalUtc('2026-11-20T08:00:00.000Z'));
    expect(text(fromEnv['证书到期'])).not.toBe('—');
    expect(text(fromEnv['档案有效期'])).not.toBe('—');
    for (const t of [pt, lt]) {
      const wrap = t.closest('.tt-table-wrap');
      expect(wrap.className).toContain('rt-quizs-table');
      expect(wrap.className, 'Quizs 的表不加 rt-table').not.toContain('rt-table');
    }
  });

  it('区块里没有按钮、没有 role=status、没有内联 style；每个 section 都带 h2', async () => {
    for (const hash of ['#/runtimes', '#/runtimes?quizs=broken']) {
      await mount(hash);
      const sec = quizsSection();
      expect(qa(sec, 'button'), `区块里不放任何按钮（${hash}）`).toEqual([]);
      expect(qa(sec, '[role="status"]')).toEqual([]);
      expect(qa(sec, '[style]')).toEqual([]);
      qa(sec, 'section').forEach((s: any) => {
        const id = s.getAttribute('aria-labelledby');
        const head = id ? document.getElementById(id) : null;
        expect(head && head.tagName).toBe('H2');
      });
      cleanup();
    }
  });

  it('?mock=loading 挂起（三个读一起等）、?mock=empty 空态下视图根照常渲染且 Quizs 一块在视图根里', async () => {
    await mount('#/runtimes?mock=loading');
    expect(frame().getAttribute('data-page-state')).toBe('loading');
    expect(pageRoot()).toBeNull();
    cleanup();
    await mount('#/runtimes?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(pageRoot(), '空态下视图根照常渲染（页面状态仍是 empty）').not.toBeNull();
    const sec = sectionNamed(frame(), 'Quizs');
    expect(sec, '空态下 Quizs 一块照常摆在视图根里').toBeTruthy();
    expect(sec.closest('[data-page="runtimes"]'), 'Quizs 一块在视图根里').toBe(pageRoot());
  });
});

describe('Quizs 一块：expired / missing / empty 情景', () => {
  it('expired：信箱那套「已过期」（danger）、「续期后再看」；环境变量那套仍就绪', async () => {
    await mount('#/runtimes?quizs=expired');
    const lt = tableOf(quizsSection(), 'Quizs live 套');
    const mailbox = rowByColumn(lt, '来源', '信箱');
    expect(text(mailbox['状态'])).toBe('已过期');
    expect(toneOf(mailbox['状态'])).toBe('danger');
    expect(text(mailbox['下一步'])).toBe('续期后再看');
    expect(text(mailbox['证书到期'])).toBe(formatLocalUtc(new Date(1700000000000).toISOString()));
    const fromEnv = rowByColumn(lt, '来源', '环境变量');
    expect(text(fromEnv['状态'])).toBe('就绪');
    expect(text(fromEnv['下一步'])).toBe('不用动');
    expect(rowsOf(tableOf(quizsSection(), 'Quizs 提供方档案')).length, '提供方档案照常').toBe(2);
  });

  it('missing：信箱那套「缺文件」（warning），下一步含「补齐缺的文件」与「缺 qualification.json」', async () => {
    await mount('#/runtimes?quizs=missing');
    const lt = tableOf(quizsSection(), 'Quizs live 套');
    const mailbox = rowByColumn(lt, '来源', '信箱');
    expect(text(mailbox['状态'])).toBe('缺文件');
    expect(toneOf(mailbox['状态'])).toBe('warning');
    expect(text(mailbox['下一步'])).toContain('补齐缺的文件');
    expect(text(mailbox['下一步'])).toContain('缺 qualification.json');
    const fromEnv = rowByColumn(lt, '来源', '环境变量');
    expect(text(fromEnv['下一步']), '其它状态不显示 missing 列表').not.toContain('缺 ');
  });

  it('empty：两张空态文案', async () => {
    await mount('#/runtimes?quizs=empty');
    const t = text(quizsSection());
    expect(t).toContain('还没有 Quizs 提供方档案');
    expect(t).toContain('还没有 Quizs live 套');
  });
});

describe('Quizs 一块：broken 情景与注入的失败', () => {
  it('broken：区块写「Quizs 跑不起来」与退出码 1；live 两套「读不出」，各自写出 problem；其余两节照常', async () => {
    await mount('#/runtimes?quizs=broken');
    const sec = quizsSection();
    const t = text(sec);
    expect(t).toContain('Quizs 跑不起来');
    expect(t).toContain('命令 config quizs providers --json 返回退出码 1');
    const lt = tableOf(sec, 'Quizs live 套');
    const lrows = rowsOf(lt);
    expect(lrows.length).toBe(2);
    lrows.forEach((row) => {
      expect(text(row['状态'])).toBe('读不出');
      expect(toneOf(row['状态'])).toBe('danger');
      expect(text(row['下一步'])).toContain('看这一套自己的问题；quizs live status 失败（退出码 127）：');
    });
    expect(text(lt).match(/quizs live status 失败（退出码 127）/g)?.length, '每一套都写自己的 problem').toBe(2);
    expect(sectionNamed(pageRoot(), '已登记')).toBeTruthy();
    expect(sectionNamed(pageRoot(), '就绪检查')).toBeTruthy();
    expect(rowsOf(tableOf(sectionNamed(pageRoot(), '已登记'), '已登记的 runtime')).length).toBeGreaterThan(0);
    expect(frame().getAttribute('data-page-state'), 'Quizs 坏不影响整页').toBe('data');
  });

  it('注入 providers 失败（退出码 3、两行 messages）：只有 Quizs 一块显示失败，live 表照自己的信封', async () => {
    clientWith({
      '/api/v1/quizs/providers': () =>
        Promise.resolve(envelope(null, ['config', 'quizs', 'providers', '--json'], false, 3, ['E-ONE', 'E-TWO'])),
    });
    await mount('#/runtimes');
    const t = text(quizsSection());
    expect(t).toContain('Quizs 跑不起来');
    expect(t).toContain('命令 config quizs providers --json 返回退出码 3');
    expect(t).toContain('E-ONE');
    expect(t).toContain('E-TWO');
    const lrows = rowsOf(tableOf(quizsSection(), 'Quizs live 套'));
    expect(lrows.map((r) => text(r['状态'])), 'live 表照它自己的信封显示').toEqual(['就绪', '就绪']);
    expect(sectionNamed(pageRoot(), '已登记')).toBeTruthy();
    expect(sectionNamed(pageRoot(), '就绪检查')).toBeTruthy();
    expect(frame().getAttribute('data-page-state')).toBe('data');
  });

  it('注入 providers 失败且退出码 null：「没有返回退出码」的写法', async () => {
    clientWith({
      '/api/v1/quizs/providers': () =>
        Promise.resolve(envelope(null, ['config', 'quizs', 'providers', '--json'], false, null, ['E-NULL'])),
    });
    await mount('#/runtimes');
    const t = text(quizsSection());
    expect(t).toContain('命令 config quizs providers --json 没有返回退出码');
    expect(t).toContain('E-NULL');
  });

  it('注入 live 失败（退出码 4）：只在 live 表位置写读失败；提供方档案照常', async () => {
    clientWith({
      '/api/v1/quizs/live': () =>
        Promise.resolve(envelope(null, ['config', 'quizs', 'live', '--json'], false, 4, ['E-LIVE'])),
    });
    await mount('#/runtimes');
    const t = text(quizsSection());
    expect(t).toContain('没能读到 Quizs 的 live 套');
    expect(t).toContain('命令 config quizs live --json 返回退出码 4');
    expect(t).toContain('E-LIVE');
    expect(t, 'providers 没坏就不写「Quizs 跑不起来」').not.toContain('Quizs 跑不起来');
    expect(rowsOf(tableOf(quizsSection(), 'Quizs 提供方档案')).length, '提供方档案表照常').toBe(2);
    expect(frame().getAttribute('data-page-state')).toBe('data');
  });

  // getRuntimes 走真实分支时注入失败信封：整页出错（页面级错误块写命令与退出码），视图不渲染。
  it('注入 runtimes 失败：整页出错，Quizs 一块看不到', async () => {
    clientWith({
      '/api/v1/runtimes': () => Promise.resolve(envelope(null, ['config', 'runtime', 'list'], false, 6)),
    });
    await mount('#/runtimes');
    expect(frame().getAttribute('data-page-state')).toBe('error');
    expect(text(frame())).toContain('命令（config runtime list）返回退出码 6');
    expect(pageRoot()).toBeNull();
  });
});
