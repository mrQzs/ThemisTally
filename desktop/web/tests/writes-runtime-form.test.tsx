// T041 登记运行时表单的自测（合同第 10 节；D01、D03、D04）：页头入口（离线也可点）、字段与逐字校验
// （不合法不调 preview）、300ms 防抖、底部实时预览（将运行的命令不含 --dry-run/--json、内核报错原文）、
// [确认…] 门控、走写确认框的完整流程与成功轻提示、成功后表单清空、界面任何位置没有 force。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

const hoisted = vi.hoisted(() => ({
  spies: {} as Record<string, { mock: { calls: unknown[] }; mockClear: () => void }>,
  overrides: {} as Record<string, (...args: unknown[]) => Promise<unknown>>,
}));
vi.mock('../src/api', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const out: Record<string, unknown> = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      const spy = vi.fn((...args: unknown[]) =>
        hoisted.overrides[name] ? hoisted.overrides[name](...args) : (fn as (...a: unknown[]) => unknown)(...args),
      );
      hoisted.spies[name] = spy;
      out[name] = spy;
    }
  }
  return out;
});

const { AddRuntimeAction } = await import('../src/writes/RuntimeForm');

const ID_ERR = '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
const CMD_ERR = '命令要写成 JSON 字符串数组，例如 ["C:/tools/pi.exe"]；每项非空、不超过 1024 个字符、不含控制字符';
const CMD_HELP = 'JSON 字符串数组，第一项写命令的绝对路径';

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
  Object.values(hoisted.spies).forEach((s) => s.mockClear());
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.location.hash = '';
});

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const modalDialogs = () => Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')) as HTMLElement[];
// 表单对话框：里面有适配器下拉（选项值里有 quizs）；写确认框（WriteConfirmDialog）没有下拉。
const hasAdapterSelect = (d: Element) =>
  Array.from(d.querySelectorAll('option')).some((o) => (o as HTMLOptionElement).value === 'quizs');
const formDialog = () => modalDialogs().find(hasAdapterSelect) ?? null;
const needFormDialog = () => {
  const d = formDialog();
  expect(d, '登记运行时的表单对话框应开着').not.toBeNull();
  return d as HTMLElement;
};
const confirmDialog = () => modalDialogs().find((d) => !hasAdapterSelect(d)) ?? null;
const buttonByText = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;
const entryButton = () => buttonByText(document.body, '手动登记…') as HTMLButtonElement;
const formConfirm = (d: HTMLElement) => buttonByText(d, '确认…') as HTMLButtonElement;
function controlByLabel(d: HTMLElement, labelText: string): HTMLInputElement | HTMLSelectElement {
  const label = Array.from(d.querySelectorAll('label')).find((l) => text(l) === labelText) as HTMLElement | undefined;
  expect(label, `应有 label「${labelText}」`).toBeTruthy();
  const forId = label!.getAttribute('for');
  const hit = Array.from(d.querySelectorAll('input, select')).find((el) => el.id === forId) as HTMLInputElement | HTMLSelectElement;
  expect(hit, `label 关联的控件「${labelText}」应在`).toBeTruthy();
  return hit;
}
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
function set(name: string, value: (...args: unknown[]) => Promise<unknown>) {
  hoisted.overrides[name] = value;
}
const spyCalls = (name: string) => hoisted.spies[name]?.mock.calls.length ?? 0;
const previewCalls = () => hoisted.spies.preview?.mock.calls ?? [];
const addRuntimeCalls = () => hoisted.spies.addRuntime?.mock.calls ?? [];
async function openForm(): Promise<HTMLElement> {
  render(<AddRuntimeAction />);
  fireEvent.click(entryButton());
  await settle();
  return needFormDialog();
}
const fillId = (d: HTMLElement, value: string) => fireEvent.change(controlByLabel(d, 'ID'), { target: { value } });
const fillCommand = (d: HTMLElement, value: string) => fireEvent.change(controlByLabel(d, '命令'), { target: { value } });

describe('T041 表单：页头入口与字段', () => {
  it('点 [手动登记…] 出标题「登记运行时」的对话框；适配器五值缺省 pi；ID 与命令等宽、命令帮助原文；界面没有 force', async () => {
    const d = await openForm();
    expect(text(d), '对话框标题').toContain('登记运行时');
    const sel = controlByLabel(d, '适配器') as HTMLSelectElement;
    expect(Array.from(sel.querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value))
      .toEqual(['pi', 'claude-code', 'codex', 'opencode', 'quizs']);
    expect(sel.value, '缺省 pi').toBe('pi');
    expect(/mono/.test((controlByLabel(d, 'ID') as HTMLInputElement).className), 'ID 等宽').toBe(true);
    const cmd = controlByLabel(d, '命令') as HTMLInputElement;
    expect(/mono/.test(cmd.className), '命令等宽').toBe(true);
    expect(text(d)).toContain(CMD_HELP);
    const labelled = Array.from(d.querySelectorAll('button')).map((b) => text(b) || b.getAttribute('aria-label') || '');
    expect(labelled.some((t) => /force/i.test(t)), '不应有 force 按钮').toBe(false);
    expect(Array.from(d.querySelectorAll('option')).some((o) => /force/i.test((o as HTMLOptionElement).value)), '不应有 force 选项').toBe(false);
    expect(text(document.body), '整页没有 force').not.toMatch(/force/i);
  });

  it('离线（?mock=offline）时 [手动登记…] 照样可点，点开表单', async () => {
    window.location.hash = '#/runtimes?mock=offline';
    render(<App />);
    await settle();
    const b = entryButton();
    expect(b, '页头应有 [手动登记…]').toBeTruthy();
    expect(b.disabled, '离线时也可点').toBe(false);
    fireEvent.click(b);
    await settle();
    needFormDialog();
  });
});

describe('T041 表单：本地校验（D03、D04）', () => {
  it('ID 不合法（大写、下划线、连字符开头、超 64）：逐字提示、不调 preview、[确认…] 不可点；空 ID 也不调', async () => {
    const d = await openForm();
    for (const v of ['Bad_ID', '-lead', 'a'.repeat(65)]) {
      fillId(d, v);
      await advance(301);
      expect(text(d), `ID 提示逐字（${v.slice(0, 8)}）`).toContain(ID_ERR);
      expect(spyCalls('preview'), 'ID 不合法不调 preview').toBe(0);
      expect(formConfirm(d).disabled).toBe(true);
    }
    fillId(d, '');
    await advance(301);
    expect(spyCalls('preview'), '空 ID 不调 preview').toBe(0);
    expect(formConfirm(d).disabled).toBe(true);
  });

  it('命令不合法（非 JSON、非数组、空数组、空串、超 1024 码点、控制字符）：逐字提示、不调 preview、[确认…] 不可点', async () => {
    const d = await openForm();
    fillId(d, 'gate-x');
    const bad = ['not json', '"pi"', '[]', '[""]', `["${'x'.repeat(1025)}"]`, '["a\u0001b"]'];
    for (const v of bad) {
      fillCommand(d, v);
      await advance(301);
      expect(text(d), `命令提示逐字（${v.slice(0, 10)}）`).toContain(CMD_ERR);
      expect(spyCalls('preview'), '命令不合法不调 preview').toBe(0);
      expect(formConfirm(d).disabled).toBe(true);
    }
    fillCommand(d, '["C:/tools/pi.exe"]');
    await advance(301);
    expect(spyCalls('preview'), '命令合法之后才调 preview').toBe(1);
    expect(formConfirm(d).disabled, '合法且预览 ok 可点').toBe(false);
  });
});

describe('T041 表单：实时预览与 [确认…] 门控（D01）', () => {
  it('300ms 防抖：299ms 内不调，300ms 到才调一次；命令留空 → 不传 command 键', async () => {
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(299);
    expect(spyCalls('preview'), '299ms 内不调').toBe(0);
    await advance(1);
    expect(spyCalls('preview'), '300ms 防抖后调一次').toBe(1);
    expect(previewCalls()[0][0]).toBe('runtime.add');
    expect(previewCalls()[0][1]).toEqual({ runtime: 'gate-x', adapter: 'pi' });
  });

  it('底部显示将运行的命令（不含 --dry-run 与 --json），[确认…] 可点', async () => {
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(301);
    expect(text(d)).toContain('config runtime add gate-x --adapter=pi');
    expect(text(d), '界面显示的是「将运行的命令」').not.toContain('--dry-run');
    expect(text(d)).not.toContain('--json');
    expect(formConfirm(d).disabled).toBe(false);
  });

  it('带命令：--command=JSON.stringify（无空格）；选 quizs 不在本地被拦', async () => {
    const d = await openForm();
    fillId(d, 'gate-x');
    fireEvent.change(controlByLabel(d, '适配器'), { target: { value: 'quizs' } });
    fillCommand(d, '["C:/tools/pi.exe","--flag"]');
    await advance(301);
    expect(previewCalls()[0][1]).toEqual({ runtime: 'gate-x', adapter: 'quizs', command: ['C:/tools/pi.exe', '--flag'] });
    expect(text(d)).toContain('config runtime add gate-x --adapter=quizs');
    expect(text(d)).toContain('--command=["C:/tools/pi.exe","--flag"]');
    expect(formConfirm(d).disabled).toBe(false);
  });

  it('服务 400：预览区原样显示该行，[确认…] 不可点', async () => {
    set('preview', () => Promise.resolve({
      status: 400,
      body: { ok: false, exit_code: null, data: null, output: [], messages: ['ERROR: adapter 不合法'], command: [], elapsed_ms: 0 },
    } as never));
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(301);
    expect(text(d)).toContain('ERROR: adapter 不合法');
    expect(formConfirm(d).disabled).toBe(true);
  });

  it('同一个 id 已登记为别的适配器（?write=preview-registered）：内核原文逐字显示、[确认…] 不可点、没有 force 控件', async () => {
    window.location.hash = '#/runtimes?write=preview-registered';
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(301);
    expect(spyCalls('preview')).toBe(1);
    expect(text(d)).toMatch(/ERROR: runtime gate-x 已登记为 [a-z-]+；改 adapter 要加 --force/);
    expect(formConfirm(d).disabled, '内核拒绝时 [确认…] 不可点').toBe(true);
    const labelled = Array.from(d.querySelectorAll('button')).map((b) => text(b) || b.getAttribute('aria-label') || '');
    expect(labelled.some((t) => /force/i.test(t)), '不应有 force 按钮').toBe(false);
    expect(Array.from(d.querySelectorAll('option')).some((o) => /force/i.test((o as HTMLOptionElement).value)), '不应有 force 选项').toBe(false);
  });

  it('取消对话框不写任何东西', async () => {
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(301);
    fireEvent.click(buttonByText(d, '取消') as HTMLButtonElement);
    await settle();
    expect(formDialog(), '取消后表单对话框应关上').toBeNull();
    expect(spyCalls('addRuntime')).toBe(0);
    expect(confirmDialog(), '不进写确认框').toBeNull();
  });
});

describe('T041 表单：走写确认框的完整流程（D01）', () => {
  it('[确认…] 进确认框（标题「登记运行时 X？」、变化区摘要、命令），执行后成功轻提示「已登记运行时 X」并清空表单', async () => {
    const reload = vi.fn(() => Promise.resolve());
    render(<AddRuntimeAction reload={reload} />);
    fireEvent.click(entryButton());
    await settle();
    const d = needFormDialog();
    fillId(d, 'gate-x');
    await advance(301);
    fireEvent.click(formConfirm(d));
    await settle();
    expect(formDialog(), '点 [确认…] 之后表单对话框应关上').toBeNull();
    const cd = confirmDialog();
    expect(cd, '写确认框应开着').not.toBeNull();
    const t = text(cd);
    expect(t).toContain('登记运行时 gate-x？');
    expect(t).toContain('已登记表里加上 gate-x（适配器 pi）');
    expect(t).toContain('config runtime add gate-x --adapter=pi');
    expect(t, '同一个 id 同一个适配器也照常走完流程（不显示「没有变化」）').not.toContain('没有变化');
    fireEvent.click(buttonByText(cd as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(addRuntimeCalls().length, '执行一次 addRuntime').toBe(1);
    expect(addRuntimeCalls()[0][0], '命令留空 → 不传 command 键').toEqual({ runtime: 'gate-x', adapter: 'pi' });
    expect(typeof addRuntimeCalls()[0][1]).toBe('string');
    expect(text(document.querySelector('.tt-toast'))).toContain('已登记运行时 gate-x');
    expect(confirmDialog(), '成功后确认框关上').toBeNull();
    expect(reload, '成功之后调一次 reload').toHaveBeenCalledTimes(1);
    fireEvent.click(entryButton());
    await settle();
    const d2 = needFormDialog();
    expect((controlByLabel(d2, 'ID') as HTMLInputElement).value, '成功后表单清空').toBe('');
    expect((controlByLabel(d2, '适配器') as HTMLSelectElement).value).toBe('pi');
    expect((controlByLabel(d2, '命令') as HTMLInputElement).value).toBe('');
  });

  it('带命令：变化区摘要接「；命令写进本机文件」，addRuntime 带命令数组', async () => {
    const d = await openForm();
    fillId(d, 'gate-x');
    fillCommand(d, '["C:/tools/pi.exe","--flag"]');
    await advance(301);
    fireEvent.click(formConfirm(d));
    await settle();
    const cd = confirmDialog() as HTMLElement;
    expect(text(cd)).toContain('已登记表里加上 gate-x（适配器 pi）；命令写进本机文件');
    fireEvent.click(buttonByText(cd, '确认…') as HTMLButtonElement);
    await settle();
    expect(addRuntimeCalls()[0][0]).toEqual({ runtime: 'gate-x', adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'] });
    expect(text(document.querySelector('.tt-toast'))).toContain('已登记运行时 gate-x');
  });
});
