// 日志与用量页自测（合同 D02、D03）：检索表单与校验、提交与只认最后一次、结果区与高亮；用量三块与两张表。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LogsView } from '../src/pages/readonly2/logs-LogsView';
import type { UsageData } from '../src/api';
import type { SearchData } from '../src/mock/readonly2-search';

afterEach(cleanup);

const USAGE = {
  executor: {
    attempts: [
      { task: 't-one', attempt: 'attempt-001', requested_model: 'm/one', status: 'known', usage: { input: 1234567, output: 7, cacheRead: 1000, cacheWrite: 0, totalTokens: 1235574 } },
      { task: 't-two', attempt: 'attempt-002', requested_model: 'm/two', status: 'partial', usage: { input: 5, output: 6 } },
      { task: 't-one', attempt: 'attempt-003', requested_model: 'm/two', status: 'unknown', usage: null },
      { task: 't-three', attempt: 'attempt-004', requested_model: 'm/zero', status: 'mystery', usage: null },
    ],
    counts: { known: 2, partial: 1, unknown: 3 },
    skipped_links: 2,
    totals: { input: 7654321, output: 123456, cacheRead: 9876, cacheWrite: 543, totalTokens: 1000000 },
    by_model: [
      { requested_model: 'm/one', known: 1, partial: 0, unknown: 0, usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 250000 } },
      { requested_model: 'm/two', known: 0, partial: 1, unknown: 2, usage: { input: 2, output: 2, cacheRead: 0, cacheWrite: 0, totalTokens: 333333 } },
      { requested_model: 'm/zero', known: 0, partial: 0, unknown: 1, usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0 } },
    ],
  },
  planner: null,
} as unknown as UsageData;

const RESULT: SearchData = {
  matches: [
    { task: 'ta', attempt: 'attempt-001', path: 'a/x.md', line: 3, text: 'first logs_cat here' },
    { task: 'tb', attempt: 'attempt-009', path: 'b.log', line: 10, text: 'logs cat second' },
    { task: 'ta', attempt: 'attempt-001', path: 'c.txt', line: 4, text: 'third logs_cat and logs cat' },
    { task: 'ta', attempt: 'attempt-002', path: 'd.json', line: 1, text: 'fourth' },
  ],
  truncated: true,
  skipped_links: 2,
  skipped_large: 3,
};

const ok = (data: unknown, command: string[] = ['demo']) => ({
  ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0,
});
const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const panel = () => document.querySelector('[role="tabpanel"]') as HTMLElement;
const form = () => (panel().querySelector('form') as HTMLFormElement);
const qBox = () => form().querySelector('input:not([type="number"])') as HTMLInputElement;
const maxBox = () => form().querySelector('input[type="number"]') as HTMLInputElement;
const taskBox = () => form().querySelector('select') as HTMLSelectElement;
const submitBtn = () => form().querySelector('button[type="submit"]') as HTMLButtonElement;
const setValue = (el: Element, v: string) => fireEvent.change(el, { target: { value: v } });
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function submit() {
  fireEvent.submit(form());
  await settle();
}
async function mountLogs(usage: UsageData = USAGE, reader: (...a: unknown[]) => Promise<unknown> = vi.fn()) {
  const out = render(<LogsView data={usage} searchLogs={reader as never} />);
  await settle();
  return { ...out, reader };
}
async function openUsage(usage: UsageData = USAGE) {
  await mountLogs(usage);
  const tab = Array.from(document.querySelectorAll('[role="tab"]')).find((t) => text(t) === '用量') as HTMLElement;
  fireEvent.click(tab);
  await settle();
  return panel();
}
function tableByHeaders(root: ParentNode, headers: string[]) {
  return Array.from(root.querySelectorAll('table')).find(
    (t) => JSON.stringify(Array.from(t.querySelectorAll('thead th')).map((th) => text(th))) === JSON.stringify(headers),
  ) as HTMLTableElement;
}
const cells = (row: Element) => Array.from(row.querySelectorAll('td'));
const rows = (table: Element) => Array.from(table.querySelectorAll('tbody tr'));

describe('日志与用量：页签', () => {
  it('Tabs 两个页签，检索缺省选中；切换后互不出现', async () => {
    await mountLogs();
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    expect(tabs.map((t) => text(t))).toEqual(['检索', '用量']);
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['true', 'false']);
    expect(panel().querySelector('form button[type="submit"]')).not.toBeNull();
    fireEvent.click(tabs[1]);
    await settle();
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['false', 'true']);
    expect(panel().querySelector('form button[type="submit"]')).toBeNull();
    expect(text(panel())).toContain('合计是下界');
    fireEvent.click(tabs[0]);
    await settle();
    expect(panel().querySelector('form button[type="submit"]')).not.toBeNull();
  });
});

describe('日志与用量：检索表单与校验', () => {
  it('默认值与提交前的说明', async () => {
    await mountLogs();
    expect(qBox().value).toBe('');
    expect(maxBox().value).toBe('50');
    expect(maxBox().getAttribute('min')).toBe('1');
    expect(Array.from(taskBox().options).map((o) => o.textContent)).toEqual(['全部任务', 't-one', 't-two', 't-three']);
    expect(taskBox().value).toBe('');
    expect(text(panel())).toContain('输入 Python 正则表达式后检索');
  });

  it('空检索词：不调读取函数，检索框下显示「先输入要检索的内容」', async () => {
    const { reader } = await mountLogs();
    for (const v of ['', '   ']) {
      setValue(qBox(), v);
      await submit();
      expect(reader).not.toHaveBeenCalled();
      expect(text(form().querySelector('.tt-field__error'))).toBe('先输入要检索的内容');
      expect(qBox().getAttribute('aria-invalid')).toBe('true');
    }
  });

  it('非法最多条数：不调读取函数，显示「最多条数必须是不小于 1 的整数」；改对后恰好调用一次', async () => {
    const { reader } = await mountLogs();
    setValue(qBox(), 'logs[_ ]cat');
    for (const v of ['0', '-3', '2.5', '']) {
      setValue(maxBox(), v);
      await submit();
      expect(reader).not.toHaveBeenCalled();
      const errs = Array.from(form().querySelectorAll('.tt-field__error')).map((e) => text(e));
      expect(errs).toContain('最多条数必须是不小于 1 的整数');
    }
    (reader as unknown as { mockResolvedValue: (v: unknown) => void }).mockResolvedValue(ok(RESULT));
    setValue(maxBox(), '5');
    await submit();
    expect(reader).toHaveBeenCalledTimes(1);
  });

  it('提交：参数是（检索词、任务或 null、数字上限）', async () => {
    const { reader } = await mountLogs(USAGE, vi.fn().mockResolvedValue(ok(RESULT)));
    setValue(qBox(), 'logs[_ ]cat');
    await submit();
    expect(reader).toHaveBeenCalledTimes(1);
    expect((reader as unknown as { mock: { calls: unknown[][] } }).mock.calls[0]).toEqual(['logs[_ ]cat', null, 50]);
    setValue(taskBox(), 't-two');
    setValue(maxBox(), '7');
    await submit();
    expect((reader as unknown as { mock: { calls: unknown[][] } }).mock.calls[1]).toEqual(['logs[_ ]cat', 't-two', 7]);
  });

  it('读取中 [检索] 转圈，回应到了恢复', async () => {
    let resolve!: (v: unknown) => void;
    const reader = vi.fn(() => new Promise((r) => { resolve = r; }));
    await mountLogs(USAGE, reader);
    setValue(qBox(), 'q1');
    await submit();
    const btn = submitBtn();
    expect(btn.getAttribute('aria-busy')).toBe('true');
    expect(btn.disabled).toBe(true);
    expect(text(btn)).toBe('正在检索…');
    expect(btn.querySelector('svg.tt-spin')).not.toBeNull();
    await act(async () => { resolve(ok(RESULT)); });
    expect(submitBtn().getAttribute('aria-busy')).toBeNull();
    expect(submitBtn().disabled).toBe(false);
    expect(text(submitBtn())).toBe('检索');
  });

  it('只认最后一次请求：旧回应后到不覆盖新结果', async () => {
    const first = new Promise<unknown>(() => {});
    let second!: (v: unknown) => void;
    const pending2 = new Promise<unknown>((r) => { second = r; });
    let n = 0;
    const reader = vi.fn(() => (++n === 1 ? first : pending2));
    await mountLogs(USAGE, reader);
    setValue(qBox(), 'first');
    await submit();
    setValue(qBox(), 'second');
    await submit();
    await act(async () => { second(ok({ matches: [{ task: 'tb', attempt: 'attempt-002', path: 'b.md', line: 2, text: 'BBB-NEW' }], truncated: false, skipped_links: 0, skipped_large: 0 })); });
    await act(async () => { (first as Promise<unknown>); });
    expect(text(panel())).toContain('BBB-NEW');
  });
});

describe('日志与用量：结果区', () => {
  it('出错块：命令、退出码、messages 在 pre 里按纯文本；不显示固定说明', async () => {
    await mountLogs(USAGE, vi.fn().mockResolvedValue({
      ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR 坏 <b>x</b>', '第二行'],
      command: ['logs', 'search', 'q1'], elapsed_ms: 0,
    }));
    setValue(qBox(), 'q1');
    await submit();
    expect(text(panel())).toContain('没能检索：命令（logs search q1）返回退出码 2。');
    const pre = panel().querySelector('pre') as HTMLElement;
    expect(pre).not.toBeNull();
    expect(pre.textContent).toContain('ERROR 坏 <b>x</b>');
    expect(pre.querySelector('b')).toBeNull();
    expect(text(panel())).not.toContain('摘录取自脱敏之后的文本');
  });

  it('头部「N 条 · 上限 M」与说明行顺序', async () => {
    await mountLogs(USAGE, vi.fn().mockResolvedValue(ok(RESULT)));
    setValue(qBox(), 'logs[_ ]cat');
    setValue(maxBox(), '7');
    await submit();
    const t = text(panel());
    expect(t).toContain('结果');
    expect(t).toContain('4 条 · 上限 7');
    const order = ['只显示前 7 条匹配', '有 3 个文件太大或读不出来，没有搜；请用 CLI 查看', '跳过的链接：2', '摘录取自脱敏之后的文本']
      .map((s) => t.indexOf(s));
    for (const i of order) expect(i).toBeGreaterThanOrEqual(0);
    expect(order[0]).toBeLessThan(order[1]);
    expect(order[1]).toBeLessThan(order[2]);
    expect(order[2]).toBeLessThan(order[3]);
    expect(t).not.toContain('只显示前 4 条匹配');
  });

  it('没有截断与跳过时不显示三条提示；空 matches 写「没有匹配的行」', async () => {
    const reader = vi.fn();
    await mountLogs(USAGE, reader);
    (reader as unknown as { mockResolvedValue: (v: unknown) => void })
      .mockResolvedValue(ok({ ...RESULT, truncated: false, skipped_links: 0, skipped_large: 0 }));
    setValue(qBox(), 'logs[_ ]cat');
    await submit();
    let t = text(panel());
    expect(t).not.toContain('只显示前');
    expect(t).not.toContain('太大或读不出来');
    expect(t).not.toContain('跳过的链接');
    expect(t).toContain('摘录取自脱敏之后的文本');
    (reader as unknown as { mockResolvedValue: (v: unknown) => void })
      .mockResolvedValue(ok({ matches: [], truncated: false, skipped_links: 0, skipped_large: 1 }));
    await submit();
    t = text(panel());
    expect(t).toContain('没有匹配的行');
    expect(t).toContain('有 1 个文件太大或读不出来');
  });

  it('分组顺序、N 处、path:line；结果条目不可点', async () => {
    await mountLogs(USAGE, vi.fn().mockResolvedValue(ok(RESULT)));
    setValue(qBox(), 'logs[_ ]cat');
    await submit();
    const t = text(panel());
    expect(t).toContain('ta · attempt-001 2 处');
    expect(t).toContain('tb · attempt-009 1 处');
    expect(t).toContain('ta · attempt-002 1 处');
    const items = ['a/x.md:3', 'c.txt:4', 'b.log:10', 'd.json:1'].map((s) => t.indexOf(s));
    for (const i of items) expect(i).toBeGreaterThanOrEqual(0);
    for (let k = 1; k < items.length; k += 1) expect(items[k - 1]).toBeLessThan(items[k]);
    expect(panel().querySelectorAll('a, [role="button"], [tabindex]').length).toBe(0);
    expect(panel().querySelectorAll('button').length).toBe(1);
  });

  it('高亮：命中段包在 mark 里；编译失败与带量词的分组不高亮；空匹配跳过', async () => {
    const reader = vi.fn().mockResolvedValue(ok(RESULT));
    await mountLogs(USAGE, reader);
    setValue(qBox(), 'logs[_ ]cat');
    await submit();
    expect(Array.from(panel().querySelectorAll('mark')).map((m) => text(m))).toEqual(['logs_cat', 'logs_cat', 'logs cat', 'logs cat']);
    for (const m of Array.from(panel().querySelectorAll('mark'))) expect(m.children.length).toBe(0);
    cleanup();
    for (const q of ['(?P<n>logs)', '(logs)+', '(l|x)+', 'z*']) {
      await mountLogs(USAGE, vi.fn().mockResolvedValue(ok(RESULT)));
      setValue(qBox(), q);
      await submit();
      expect(panel().querySelectorAll('mark').length, q).toBe(0);
      expect(text(panel())).toContain('first logs_cat here');
      cleanup();
    }
    await mountLogs(USAGE, vi.fn().mockResolvedValue(ok(RESULT)));
    setValue(qBox(), 'logs[_ ]cat+');
    await submit();
    expect(panel().querySelectorAll('mark').length).toBeGreaterThan(0);
  });

  it('摘录里的 <img src=x onerror=…> 与 <script> 只是文字', async () => {
    await mountLogs(USAGE, vi.fn().mockResolvedValue(ok({
      matches: [{ task: 'ta', attempt: 'attempt-001', path: 'x.md', line: 1, text: '<img src=x onerror=alert(1)> logs_cat <script>window.__x=1</script>' }],
      truncated: false, skipped_links: 0, skipped_large: 0,
    })));
    setValue(qBox(), 'logs[_ ]cat');
    await submit();
    expect(panel().querySelector('img, script, [onerror]')).toBeNull();
    expect((window as unknown as { __x?: unknown }).__x).toBeUndefined();
    expect(text(panel())).toContain('<img src=x onerror=alert(1)>');
    expect(text(panel())).toContain('<script>window.__x=1</script>');
  });
});

describe('日志与用量：用量', () => {
  it('固定说明、合计与四项、三个计数标签、跳过的链接', async () => {
    const p = await openUsage();
    const t = text(p);
    expect(t).toContain('合计是下界：没有回报的记为未知，不计为 0。');
    expect(t).toContain('1,000,000');
    expect(t).toContain('token（下界）');
    expect(Array.from(p.querySelectorAll('.tt-num')).some((e) => text(e).includes('1,000,000'))).toBe(true);
    for (const [k, v] of [['input', '7,654,321'], ['output', '123,456'], ['cacheRead', '9,876'], ['cacheWrite', '543']]) {
      expect(new RegExp(`(${k}\\s*${v}|${v}\\s*${k})`).test(t), `${k} ${v}`).toBe(true);
    }
    for (const [label, tone, title] of [['known 2', 'success', '已回报'], ['partial 1', 'warning', '部分回报'], ['unknown 3', 'neutral', '未回报']]) {
      const tag = Array.from(p.querySelectorAll('[data-tone]')).find((x) => text(x) === label) as HTMLElement;
      expect(tag, label).not.toBeNull();
      expect(tag.getAttribute('data-tone')).toBe(tone);
      expect(tag.getAttribute('title')).toBe(title);
    }
    expect(t).toContain('跳过的链接：2');
  });

  it('skipped_links 为 0 时不显示「跳过的链接」', async () => {
    const usage = JSON.parse(JSON.stringify(USAGE)) as typeof USAGE;
    usage.executor.skipped_links = 0;
    const p = await openUsage(usage);
    expect(text(p)).not.toContain('跳过的链接');
  });

  it('规划端空状态与 [去设置] href；planner 非空只写一行', async () => {
    window.location.hash = '#/logs?mock=data';
    let p = await openUsage();
    expect(p.querySelector('.tt-empty')).not.toBeNull();
    expect(text(p)).toContain('在设置里指定会话记录目录后统计');
    let link = Array.from(p.querySelectorAll('a')).find((a) => text(a) === '去设置') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('#/settings?mock=data');
    cleanup();
    const usage = JSON.parse(JSON.stringify(USAGE)) as typeof USAGE;
    (usage as unknown as { planner: unknown }).planner = { sessions: 3 };
    p = await openUsage(usage);
    expect(text(p)).toContain('规划端用量的显示在后续片接入');
    expect(p.querySelector('.tt-empty')).toBeNull();
    expect(Array.from(p.querySelectorAll('a')).some((a) => text(a) === '去设置')).toBe(false);
    window.location.hash = '';
  });

  it('按 attempt 表：列、状态 Tag、缺键与 null 显示「未知」', async () => {
    const p = await openUsage();
    const table = tableByHeaders(p, ['任务', 'attempt', '模型', '状态', 'input', 'output', 'cacheRead', 'cacheWrite', '合计']);
    expect(table.getAttribute('data-row-height')).toBe('40');
    const rs = rows(table);
    expect(rs).toHaveLength(4);
    const texts = (r: Element) => cells(r).map((c) => text(c));
    expect(texts(rs[0]).filter((_t, i) => i !== 3)).toEqual(['t-one', 'attempt-001', 'm/one', '1,234,567', '7', '1,000', '0', '1,235,574']);
    expect(texts(rs[1]).filter((_t, i) => i !== 3)).toEqual(['t-two', 'attempt-002', 'm/two', '5', '6', '未知', '未知', '未知']);
    expect(texts(rs[2]).filter((_t, i) => i !== 3)).toEqual(['t-one', 'attempt-003', 'm/two', '未知', '未知', '未知', '未知', '未知']);
    const status = (r: Element) => cells(r)[3].querySelector('[data-tone]') as HTMLElement;
    expect([text(status(rs[0])), text(status(rs[1])), text(status(rs[2])), text(status(rs[3]))])
      .toEqual(['known', 'partial', 'unknown', 'mystery']);
    expect(status(rs[0]).getAttribute('data-tone')).toBe('success');
    expect(status(rs[0]).getAttribute('title')).toBe('已回报');
    expect(status(rs[1]).getAttribute('data-tone')).toBe('warning');
    expect(status(rs[2]).getAttribute('data-tone')).toBe('neutral');
    expect(status(rs[3]).getAttribute('data-tone')).toBe('neutral');
    expect(status(rs[3]).getAttribute('title') || '').toBe('');
    for (const r of rs) for (const i of [4, 5, 6, 7, 8]) expect(cells(r)[i].classList.contains('tt-num')).toBe(true);
  });

  it('attempts 为空写「还没有执行端的用量记录」', async () => {
    const usage = JSON.parse(JSON.stringify(USAGE)) as typeof USAGE;
    usage.executor.attempts = [];
    const p = await openUsage(usage);
    expect(text(p)).toContain('还没有执行端的用量记录');
  });

  it('按模型表：回报情况、占比与条宽、合计', async () => {
    const p = await openUsage();
    const table = tableByHeaders(p, ['模型', '回报情况', '占比', 'input', 'output', '合计']);
    expect(table.getAttribute('data-row-height')).toBe('40');
    const rs = rows(table);
    expect(rs).toHaveLength(3);
    const want: [string, string, string, number, string][] = [
      ['m/one', 'known 1 · partial 0 · unknown 0', '25.0%', 25, '250,000'],
      ['m/two', 'known 0 · partial 1 · unknown 2', '33.3%', 33.3, '333,333'],
      ['m/zero', 'known 0 · partial 0 · unknown 1', '0.0%', 0, '0'],
    ];
    rs.forEach((r, i) => {
      const c = cells(r);
      expect(text(c[0])).toBe(want[i][0]);
      expect(text(c[1])).toBe(want[i][1]);
      expect(text(c[2])).toContain(want[i][2]);
      const bars = Array.from(r.querySelectorAll('[style]')) as HTMLElement[];
      expect(bars.length).toBeLessThanOrEqual(1);
      if (want[i][3] > 0) {
        expect(bars).toHaveLength(1);
        expect(bars[0].style.length).toBe(1);
        expect(bars[0].style.width.endsWith('%')).toBe(true);
        expect(Math.abs(parseFloat(bars[0].style.width) - want[i][3])).toBeLessThan(0.2);
      }
      expect(text(c[5])).toBe(want[i][4]);
    });
    expect(cells(rs[0])[2].classList.contains('tt-num')).toBe(true);
  });

  it('分母为 0 时占比显示「—」；内联 style 只在占比条上', async () => {
    const usage = JSON.parse(JSON.stringify(USAGE)) as typeof USAGE;
    usage.executor.totals.totalTokens = 0;
    const p = await openUsage(usage);
    const table = tableByHeaders(p, ['模型', '回报情况', '占比', 'input', 'output', '合计']);
    for (const r of rows(table)) {
      const t = text(cells(r)[2]);
      expect(t).toContain('—');
      expect(t).not.toContain('%');
    }
    const root = document.querySelector('[data-page="logs"]') as HTMLElement;
    for (const el of Array.from(root.querySelectorAll('[style]'))) expect(table.contains(el)).toBe(true);
  });

  it('by_model 为空写「还没有按模型的统计」', async () => {
    const usage = JSON.parse(JSON.stringify(USAGE)) as typeof USAGE;
    usage.executor.by_model = [];
    const p = await openUsage(usage);
    expect(text(p)).toContain('还没有按模型的统计');
  });
});
