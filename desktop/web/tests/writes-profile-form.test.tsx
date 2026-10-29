// T024 profile 表单对话框的自测（合同第三、四、五节；D04–D06、D08–D10）：
// 字段与控件、逐字校验提示且不合法不调 preview、300ms 防抖、底部实时预览（命令/警告/报错原文）、
// [确认…] 门控、迟到回应按序号丢弃、编辑只传改动字段（ID 只读、thinking 缺省未动不传、还没有改动、清空凭据变量）、
// runtime 读失败「先登记 runtime」、对话框关着时页里不渲染按钮，以及走 A 片确认框的完整流程与 W3。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

const { NewProfileAction, EditProfileAction } = await import('../src/writes/ProfileForm');

const ID_ERR = '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
const MODEL_ERR = '模型要写成 provider/model，两段都只能用字母、数字与 . _ : / @ + -';
const ENV_ERR = '变量名只能用字母、数字与下划线，不能以数字开头，最长 128 个字符';

const STEP_HIGH = { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] };
const STEP_LOW = { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] };

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
const hasIdLabel = (d: Element) => Array.from(d.querySelectorAll('label')).some((l) => text(l) === 'ID');
const formDialog = () => modalDialogs().find(hasIdLabel) ?? null;
const needFormDialog = () => {
  const d = formDialog();
  expect(d, '表单对话框应开着').not.toBeNull();
  return d as HTMLElement;
};
const confirmDialog = () => modalDialogs().find((d) => !hasIdLabel(d)) ?? null;
const needConfirmDialog = () => {
  const d = confirmDialog();
  expect(d, 'A 片确认框应开着').not.toBeNull();
  return d as HTMLElement;
};
const buttonByText = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;
function controlByLabel(d: HTMLElement, labelText: string): HTMLInputElement | HTMLSelectElement {
  const label = Array.from(d.querySelectorAll('label')).find((l) => text(l) === labelText) as HTMLElement | undefined;
  expect(label, `应有 label「${labelText}」`).toBeTruthy();
  const forId = label!.getAttribute('for');
  const hit = Array.from(d.querySelectorAll('input, select')).find((el) => el.id === forId) as HTMLInputElement | HTMLSelectElement;
  expect(hit, `label 关联的控件「${labelText}」应在`).toBeTruthy();
  return hit;
}
const thinkingGroup = (d: HTMLElement) => d.querySelector('[role="radiogroup"][aria-label="thinking"]') as HTMLElement;
const checkedSeg = (g: HTMLElement) =>
  text(Array.from(g.querySelectorAll('[role="radio"]')).find((b) => b.getAttribute('aria-checked') === 'true') as HTMLElement);
const envInput = (d: HTMLElement) => {
  const idEl = controlByLabel(d, 'ID');
  const modelEl = controlByLabel(d, '模型');
  return (Array.from(d.querySelectorAll('input')) as HTMLInputElement[]).find((i) => i !== idEl && i !== modelEl && i.type !== 'hidden') as HTMLInputElement;
};
const addTagBtn = (d: HTMLElement) => buttonByText(d, '添加') as HTMLButtonElement;
const tagRemoveBtn = (d: HTMLElement, name: string) => {
  const tag = Array.from(d.querySelectorAll('.tt-tag')).find((t) => text(t) === name) as HTMLElement;
  expect(tag, `应有 Tag「${name}」`).toBeTruthy();
  return (tag.querySelector('button') ?? Array.from(d.querySelectorAll('button')).find((b) => (b.getAttribute('aria-label') || '').includes(name))) as HTMLButtonElement;
};
const formConfirm = (d: HTMLElement) => buttonByText(d, '确认…') as HTMLButtonElement;
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
function fillNew(d: HTMLElement, opts: { id?: string; model?: string } = {}) {
  fireEvent.change(controlByLabel(d, 'ID'), { target: { value: opts.id ?? 'gate-x' } });
  fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
  fireEvent.change(controlByLabel(d, '模型'), { target: { value: opts.model ?? 'bb/m1' } });
}

describe('T024 表单：字段与控件', () => {
  it('新建：ID/runtime/模型/thinking/凭据变量齐全，thinking 七段缺省 high，「手填的模型没有核实」常显', async () => {
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    expect((controlByLabel(d, 'ID') as HTMLInputElement).value).toBe('');
    expect((controlByLabel(d, 'ID') as HTMLInputElement).readOnly, '新建时 ID 可编辑').toBe(false);
    const opts = Array.from((controlByLabel(d, 'runtime') as HTMLSelectElement).querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
    expect(opts).toEqual(['pi', 'claude-code', 'opencode']);
    const g = thinkingGroup(d);
    expect(Array.from(g.querySelectorAll('[role="radio"]')).map((b) => text(b as HTMLElement))).toEqual(['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
    expect(checkedSeg(g), '新建缺省 high').toBe('high');
    expect(text(d), '「手填的模型没有核实」应常显').toContain('手填的模型没有核实');
    expect(text(d)).toContain('值在‘凭据’页录入');
  });

  it('校验：ID、模型、凭据变量名的逐字提示；不合法的取值不调 preview（调用次数 0）', async () => {
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    fireEvent.change(controlByLabel(d, 'ID'), { target: { value: '-abc' } });
    expect(text(d)).toContain(ID_ERR);
    fireEvent.change(controlByLabel(d, 'ID'), { target: { value: 'a'.repeat(65) } });
    expect(text(d)).toContain(ID_ERR);
    await advance(1000);
    expect(spyCalls('preview'), 'ID 不合法不调 preview').toBe(0);
    fireEvent.change(controlByLabel(d, 'ID'), { target: { value: 'gate-x' } });
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'no-slash' } });
    expect(text(d), '模型没有 / 报错').toContain(MODEL_ERR);
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/bad!' } });
    expect(text(d), '模型段含非法字符报错').toContain(MODEL_ERR);
    await advance(1000);
    expect(spyCalls('preview'), '模型不合法不调 preview').toBe(0);
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
    const inp = envInput(d);
    fireEvent.change(inp, { target: { value: '1ABC' } });
    fireEvent.click(addTagBtn(d));
    await settle();
    expect(text(d), '变量名以数字开头报错').toContain(ENV_ERR);
    fireEvent.change(inp, { target: { value: 'A'.repeat(129) } });
    fireEvent.click(addTagBtn(d));
    await settle();
    expect(text(d), '129 个字符的变量名也报错').toContain(ENV_ERR);
    expect(d.querySelectorAll('.tt-tag').length, '不合法的变量名不加成 Tag').toBe(0);
    fireEvent.change(inp, { target: { value: 'OK_KEY' } });
    fireEvent.click(addTagBtn(d));
    await settle();
    expect(Array.from(d.querySelectorAll('.tt-tag')).map(text)).toEqual(['OK_KEY']);
    await advance(1000);
    expect(spyCalls('preview'), '整个表单合法之后才调 preview').toBeGreaterThanOrEqual(1);
  });
});

describe('T024 表单：实时预览与 [确认…] 门控（D06）', () => {
  it('300ms 防抖：299ms 内不调，300ms 到才调一次', async () => {
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    fillNew(d);
    await advance(299);
    expect(spyCalls('preview'), '299ms 内不调').toBe(0);
    await advance(1);
    expect(spyCalls('preview'), '300ms 防抖后调一次').toBe(1);
  });

  it('底部命令去掉 --dry-run/--json；ok 情景预览过后 [确认…] 可点', async () => {
    window.location.hash = '#/roles?write=ok';
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    fillNew(d);
    await advance(350);
    expect(text(d)).toContain('config profile add gate-x --runtime=pi --model=bb/m1');
    expect(text(d)).not.toContain('--dry-run');
    expect(text(d)).not.toContain('--json');
    expect(formConfirm(d).disabled, 'ok 预览过后可点').toBe(false);
  });

  it('preview-warn：底部显示 WARN 原文且可点；preview-invalid：底部显示 ERROR 原文且不可点', async () => {
    window.location.hash = '#/roles?write=preview-warn';
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    let d = needFormDialog();
    fillNew(d, { model: 'bb/m9' });
    await advance(350);
    expect(text(d), '底部显示预览的 WARN 原文').toContain('WARN: 模型 bb/m9 不在 pi --list-models 的列表里');
    expect(formConfirm(d).disabled, '200 且 ok 可点').toBe(false);
    cleanup();
    window.location.hash = '#/roles?write=preview-invalid';
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    d = needFormDialog();
    fillNew(d, { model: 'bb/bad' });
    await advance(350);
    expect(text(d), '底部显示内核报错原文').toContain('ERROR: model 不合法');
    expect(formConfirm(d).disabled, '预览 400 不可点').toBe(true);
  });

  it('迟到的回应按序号丢弃：后发的先回、先发的后回，底部只认最新的那份', async () => {
    window.location.hash = '#/roles?write=ok';
    const gates = [deferred(), deferred()];
    let n = 0;
    set('preview', () => {
      const g = gates[n];
      n += 1;
      return g.promise;
    });
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    fillNew(d);
    await advance(350);
    expect(n, '第一次预览已发出').toBe(1);
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m2' } });
    await advance(350);
    expect(n, '第二次预览已发出').toBe(2);
    gates[1].resolve({ status: 200, body: pvEnv(['config', 'profile', 'add', 'gate-x', '--runtime=pi', '--model=bb/m2', '--dry-run', '--json']) });
    await settle();
    await advance(20);
    expect(text(d)).toContain('--model=bb/m2');
    gates[0].resolve({ status: 200, body: pvEnv(['config', 'profile', 'add', 'gate-x', '--runtime=pi', '--model=bb/m1', '--dry-run', '--json']) });
    await settle();
    await advance(20);
    expect(text(d), '迟到的旧回应应被丢弃').toContain('--model=bb/m2');
    expect(text(d)).not.toContain('--model=bb/m1');
    expect(formConfirm(d).disabled).toBe(false);
  });
});

describe('T024 表单：编辑模式（D05）', () => {
  it('初值带全、ID 只读；全都没改写「还没有改动」（不写「没有变化」）且不可点；只改模型时命令只含 --model', async () => {
    window.location.hash = '#/roles?write=ok';
    render(<EditProfileAction profile={STEP_HIGH} />);
    fireEvent.click(buttonByText(document.body, '编辑') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    const idEl = controlByLabel(d, 'ID') as HTMLInputElement;
    expect(idEl.value).toBe('step-high');
    expect(idEl.readOnly, '编辑时 ID 只读').toBe(true);
    expect((controlByLabel(d, 'runtime') as HTMLSelectElement).value).toBe('pi');
    expect((controlByLabel(d, '模型') as HTMLInputElement).value).toBe('bb/step-5-preview');
    expect(checkedSeg(thinkingGroup(d))).toBe('high');
    expect(Array.from(d.querySelectorAll('.tt-tag')).map(text)).toEqual(['STEP_API_KEY']);
    expect(text(d), '全都没改写「还没有改动」').toContain('还没有改动');
    expect(text(d), 'W3b：表单对话框也不写「没有变化」').not.toContain('没有变化');
    expect(formConfirm(d).disabled, '全都没改不可点').toBe(true);
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m2' } });
    await advance(350);
    expect(text(d)).toContain('config profile edit step-high --model=bb/m2');
    expect(text(d), '没改的 runtime 不传').not.toContain('--runtime=');
    expect(text(d), '没改的 thinking 不传').not.toContain('--thinking=');
    expect(text(d), '没改的凭据变量不传').not.toContain('--credential-env=');
  });

  it('thinking 原来缺省（界面显示 high）但没动过 → 不传；清空凭据变量 → 「内核没有清空凭据变量的写法」且不可点', async () => {
    window.location.hash = '#/roles?write=ok';
    const noThinking = { ...STEP_HIGH, options: {} };
    render(<EditProfileAction profile={noThinking} />);
    fireEvent.click(buttonByText(document.body, '编辑') as HTMLButtonElement);
    await settle();
    let d = needFormDialog();
    expect(checkedSeg(thinkingGroup(d)), 'thinking 缺省时界面显示 high').toBe('high');
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m2' } });
    await advance(350);
    expect(text(d), 'thinking 缺省而未动过就不传').not.toContain('--thinking=');
    cleanup();
    render(<EditProfileAction profile={STEP_LOW} />);
    fireEvent.click(buttonByText(document.body, '编辑') as HTMLButtonElement);
    await settle();
    d = needFormDialog();
    fireEvent.click(tagRemoveBtn(d, 'STEP_API_KEY'));
    await advance(350);
    expect(text(d)).toContain('内核没有清空凭据变量的写法');
    expect(formConfirm(d).disabled, '清空凭据变量不可点').toBe(true);
  });
});

describe('T024 表单：runtime 与对话框关着（D04、M9）', () => {
  it('没有已登记的 runtime：提示「先登记 runtime」且不可点', async () => {
    window.location.hash = '#/roles?write=ok';
    set('getRuntimes', () => Promise.resolve({ ok: true, exit_code: 0, data: { runtimes: [] }, output: [], messages: [], command: ['config', 'runtime', 'list'], elapsed_ms: 0 } as never));
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    expect(text(d)).toContain('先登记 runtime');
    expect(formConfirm(d).disabled).toBe(true);
  });

  it('对话框关着时页里不渲染任何按钮（连禁用的 [确认…] 也没有）', async () => {
    render(<NewProfileAction />);
    const before = pageButtons();
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    needFormDialog();
    fireEvent.click(buttonByText(needFormDialog(), '取消') as HTMLButtonElement);
    await settle();
    expect(formDialog(), '取消后表单对话框应关上').toBeNull();
    expect(pageButtons(), '关着时页里的按钮集合与打开前一致').toEqual(before);
  });
});

describe('T024 表单：走 A 片确认框的完整流程（D09、D10、W3）', () => {
  it('新建：表单 [确认…] 关上表单、A 片接手（标题/摘要/primary）；成功后弹轻提示并调一次 reload', async () => {
    window.location.hash = '#/roles?write=ok';
    const reload = vi.fn(() => Promise.resolve());
    render(<NewProfileAction reload={reload} />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    fillNew(d, { id: 'gate-new' });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    expect(formDialog(), '点 [确认…] 之后表单对话框应关上').toBeNull();
    const cd = needConfirmDialog();
    const t = text(cd);
    expect(t).toContain('新建 profile gate-new？');
    expect(t).toContain('profile 表里加上 gate-new');
    expect(t).toContain('config profile add gate-new --runtime=pi --model=bb/m1');
    expect((Array.from(cd.querySelectorAll('button')).find((b) => b.getAttribute('data-variant') === 'primary') as HTMLButtonElement), 'profile.add 确认钮是 primary').toBeTruthy();
    expect(t, 'W3b：确认框不写「没有变化」').not.toContain('没有变化');
    fireEvent.click(buttonByText(cd, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(text(document.querySelector('.tt-toast'))).toContain('已新建 profile gate-new');
    expect(confirmDialog(), '成功后确认框关上').toBeNull();
    expect(reload, '成功之后调一次 reload').toHaveBeenCalledTimes(1);
  });

  it('W3：重读兑现之前整页没有「已新建 profile」、Toast 空；兑现之后才弹轻提示', async () => {
    window.location.hash = '#/roles?write=ok';
    let hang = false;
    const gate = deferred();
    set('getProfiles', () => (hang ? gate.promise : Promise.resolve(profilesEnv())));
    render(<NewProfileAction />);
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    const d = needFormDialog();
    fillNew(d, { id: 'gate-w3' });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    hang = true;
    fireEvent.click(buttonByText(needConfirmDialog(), '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(confirmDialog(), '重读中确认框还开着').not.toBeNull();
    expect(document.querySelector('.tt-toast'), '重读兑现之前 Toast 是空的（W3）').toBeNull();
    expect(text(document.body), '重读兑现之前整页没有「已新建」').not.toContain('已新建');
    gate.resolve(profilesEnv());
    await settle();
    await advance(20);
    expect(text(document.body), '重读兑现之后才说成功').toContain('已新建 profile gate-w3');
    expect(confirmDialog()).toBeNull();
  });
});

// 小工具：可控的延迟 Promise 与一份 PreviewData 信封（门控与迟到回应用）。
function deferred(): { promise: Promise<unknown>; resolve: (v: unknown) => void } {
  let resolve: (v: unknown) => void = () => {};
  const promise = new Promise<unknown>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
function pvEnv(command: string[]): unknown {
  return {
    ok: true,
    exit_code: 0,
    data: { binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [], needs_yes: false, command, confirmation: 'c' },
    output: [],
    messages: [],
    command,
    elapsed_ms: 0,
  };
}
function profilesEnv(): Promise<unknown> {
  return Promise.resolve({ ok: true, exit_code: 0, data: { profiles: [STEP_HIGH, STEP_LOW] }, output: [], messages: [], command: ['config', 'profile', 'show'], elapsed_ms: 0 });
}
function pageButtons(): string[] {
  return (Array.from(document.body.querySelectorAll('button')) as HTMLButtonElement[])
    .filter((b) => !b.closest('[role="dialog"]'))
    .map((b) => text(b))
    .sort();
}
