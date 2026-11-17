// T046 profile 表单接 quizs 运行时的自测（合同第 10 步；D01、D04–D09）。
// 写法照 tests/writes-profile-form.test.tsx：vi.mock('../src/api') 的替身默认转调真实现，
// 用 ?quizs= 选档案情景、?write=ok 选预览；不 mock 被测组件。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

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

// 档案 ok 情景的两行（src/mock/quizs.ts）：stepfun 三档、deepseek 两档。
const SIX = ['off', 'low', 'medium', 'high', 'xhigh', 'max'];
// 编辑用的 quizs profile：stepfun/step-4 在档案外，凭据变量带一个（quizs 分支不显示）。
const QUIZS_PROFILE = { id: 'step-old', runtime: 'quizs-cli', provider: 'stepfun', model: 'step-4', options: { thinking: 'high' }, credential_env: ['OLD_KEY'] };
const INSIDE_PROFILE = { ...QUIZS_PROFILE, model: 'step-5-preview' };

// 运行时两行：第二行的 adapter 是 quizs（id 与 adapter 不同名，认 quizs 不能看 id）。
function runtimesEnv(): Promise<unknown> {
  return Promise.resolve({
    ok: true, exit_code: 0,
    data: {
      runtimes: [
        { id: 'pi', adapter: 'pi', source: 'env', command: ['pi'], notes: '' },
        { id: 'quizs-cli', adapter: 'quizs', source: 'env', command: ['quizs'], notes: '' },
      ],
    },
    output: [], messages: [], command: ['config', 'runtime', 'list'], elapsed_ms: 0,
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
  Object.values(hoisted.spies).forEach((s) => s.mockClear());
  set('getRuntimes', runtimesEnv);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.location.hash = '';
  setLiveClientForTests(undefined);
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
const segTexts = (g: HTMLElement) => Array.from(g.querySelectorAll('[role="radio"]')).map((b) => text(b as HTMLElement));
const checkedSeg = (g: HTMLElement) =>
  text(Array.from(g.querySelectorAll('[role="radio"]')).find((b) => b.getAttribute('aria-checked') === 'true') as HTMLElement);
const segByText = (g: HTMLElement, label: string) =>
  Array.from(g.querySelectorAll('[role="radio"]')).find((b) => text(b as HTMLElement) === label) as HTMLElement;
const modelOptions = (d: HTMLElement) =>
  Array.from((controlByLabel(d, '模型') as HTMLSelectElement).querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
const envLabels = (d: HTMLElement) => Array.from(d.querySelectorAll('label')).filter((l) => text(l) === '凭据变量');
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
async function openNew() {
  render(<NewProfileAction />);
  fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
  await settle();
  return needFormDialog();
}
async function openQuizsNew(id: string) {
  const d = await openNew();
  fireEvent.change(controlByLabel(d, 'ID'), { target: { value: id } });
  fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
  await settle();
  return d;
}
async function openEdit(profile: typeof QUIZS_PROFILE) {
  render(<EditProfileAction profile={profile} />);
  fireEvent.click(buttonByText(document.body, '编辑') as HTMLButtonElement);
  await settle();
  return needFormDialog();
}

describe('T046 quizs：档案读到时的模型与档位（D03、D08）', () => {
  it('新建：模型是档案 Select 两项自动选第一项；档位按档案给；无手填提示；凭据换成说明；命令带 provider/model', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openQuizsNew('gate-x');
    expect(Array.from((controlByLabel(d, 'runtime') as HTMLSelectElement).querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value))
      .toEqual(['pi', 'quizs-cli']);
    const model = controlByLabel(d, '模型') as HTMLSelectElement;
    expect(model.tagName, '有档案时模型是 Select').toBe('SELECT');
    expect(modelOptions(d)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(model.value, '新建自动选档案第一项').toBe('stepfun/step-5-preview');
    expect(segTexts(thinkingGroup(d)), '档位按档案给').toEqual(['low', 'medium', 'high']);
    expect(checkedSeg(thinkingGroup(d))).toBe('high');
    expect(text(d), '有档案可选时不显示手填提示').not.toContain('手填的模型没有核实');
    expect(envLabels(d).length, 'quizs 不显示凭据输入框').toBe(0);
    expect(buttonByText(d, '添加'), 'quizs 不显示 [添加]').toBeUndefined();
    const group = d.querySelector('[role="group"][aria-label="凭据变量"]') as HTMLElement | null;
    expect(group, '凭据说明外层是 role=group 且保留无障碍名称').toBeTruthy();
    expect(text(group)).toContain('凭据由 Quizs 保管');
    expect(d.querySelectorAll('.tt-tag').length, 'quizs 不显示已加的凭据 Tag').toBe(0);
    expect(spyCalls('getQuizsProviders'), '选了 quizs 运行时读一次档案').toBe(1);
    await advance(350);
    expect(text(d), '命令带 --runtime=quizs-cli --model=<provider>/<model>').toContain('--runtime=quizs-cli --model=stepfun/step-5-preview');
    expect(text(d), 'quizs 不交 credential_env').not.toContain('--credential-env');
    fireEvent.click(buttonByText(d, '取消') as HTMLButtonElement);
    await settle();
    fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
    await settle();
    expect(spyCalls('getQuizsProviders'), '重新打开对话框会重读').toBe(2);
  });

  it('新建：先在 pi 下加过凭据再切到 quizs，命令里没有 --credential-env', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openNew();
    fireEvent.change(controlByLabel(d, 'ID'), { target: { value: 'gate-x' } });
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
    const idEl = controlByLabel(d, 'ID');
    const modelEl = controlByLabel(d, '模型');
    const env = (Array.from(d.querySelectorAll('input')) as HTMLInputElement[])
      .find((i) => i !== idEl && i !== modelEl && i.type !== 'hidden');
    expect(env, 'pi 下凭据输入在').toBeTruthy();
    fireEvent.change(env as HTMLInputElement, { target: { value: 'OK_KEY' } });
    fireEvent.click(buttonByText(d, '添加') as HTMLButtonElement);
    await settle();
    expect(Array.from(d.querySelectorAll('.tt-tag')).map(text), '夹具自证：凭据加成了 Tag').toEqual(['OK_KEY']);
    await advance(350);
    expect(text(d), '夹具自证：pi 的命令带 credential-env').toContain('--runtime=pi --model=bb/m1');
    expect(text(d)).toContain('--credential-env=OK_KEY');
    fireEvent.change(modelEl, { target: { value: '' } });
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
    await settle();
    expect((controlByLabel(d, '模型') as HTMLSelectElement).value, '切到 quizs 后自动选档案第一项').toBe('stepfun/step-5-preview');
    expect(d.querySelectorAll('.tt-tag').length, 'quizs 不显示已加的凭据 Tag').toBe(0);
    await advance(350);
    expect(text(d)).toContain('--runtime=quizs-cli --model=stepfun/step-5-preview');
    expect(text(d), '之前在 pi 下加的凭据不许悄悄交上去').not.toContain('--credential-env');
  });

  it('新建：用户点过档位（点的就是初值 high）之后命令里出现 --thinking=high', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openQuizsNew('gate-x');
    fireEvent.click(segByText(thinkingGroup(d), 'high'));
    await advance(350);
    expect(text(d), '点过即算改动，照传 --thinking=').toContain('--thinking=high');
  });

  it('换档案：新档案不含当前档位 → 一个段都不选、有提示、不调预览、不可点；点允许的档位后恢复', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openQuizsNew('gate-x');
    fireEvent.click(segByText(thinkingGroup(d), 'medium'));
    await settle();
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'deepseek/deepseek-chat' } });
    await settle();
    const g = thinkingGroup(d);
    expect(checkedSeg(g), 'medium 不在 deepseek 档案允许的档位里，一个段都不选').toBe('');
    expect(text(d)).toContain('medium 不在这个档案允许的档位里');
    const before = spyCalls('preview');
    await advance(1000);
    expect(spyCalls('preview'), '档位不在范围内不调预览').toBe(before);
    expect(formConfirm(d).disabled, '[确认…] 不可点').toBe(true);
    fireEvent.click(segByText(g, 'high'));
    await advance(350);
    expect(text(d), '点允许的档位之后恢复，点过即算改动照传 --thinking=').toContain('--thinking=high');
    expect(formConfirm(d).disabled).toBe(false);
  });

  it('换回非 quizs 运行时：模型值留在文本框里照旧校验，档位回到七段，凭据输入回来', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openQuizsNew('gate-x');
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
    await settle();
    const model = controlByLabel(d, '模型');
    expect(model.tagName, '非 quizs 又是手填文本框').toBe('INPUT');
    expect((model as HTMLInputElement).value, '模型值留在文本框里').toBe('stepfun/step-5-preview');
    expect(text(d), '非 quizs 常显手填提示').toContain('手填的模型没有核实');
    expect(segTexts(thinkingGroup(d)), '非 quizs 七段照旧').toEqual(['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
    expect(envLabels(d).length, '非 quizs 凭据输入仍恰一个').toBe(1);
    expect(spyCalls('getQuizsProviders'), '换回非 quizs 不再读档案').toBe(1);
    await advance(350);
    expect(text(d)).toContain('--runtime=pi --model=stepfun/step-5-preview');
  });
});

describe('T046 quizs：编辑模式（D05）', () => {
  it('档案内的 profile 全都没改写「还没有改动」', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openEdit(INSIDE_PROFILE);
    expect((controlByLabel(d, '模型') as HTMLSelectElement).value, '档案内初值照旧选中').toBe('stepfun/step-5-preview');
    expect(segTexts(thinkingGroup(d))).toEqual(['low', 'medium', 'high']);
    expect(text(d), '全都没改写「还没有改动」').toContain('还没有改动');
    expect(d.querySelectorAll('.tt-tag').length, 'quizs 不显示凭据 Tag').toBe(0);
  });

  it('档案外的模型原值照样选中、标「不在 Quizs 已批准的档案里」、不调预览；选回档案项后命令只含 --model', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openEdit(QUIZS_PROFILE);
    const model = controlByLabel(d, '模型') as HTMLSelectElement;
    expect(modelOptions(d), '档案外原值作额外第一项').toEqual(['stepfun/step-4', 'stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(model.value, '原值照样选中').toBe('stepfun/step-4');
    expect(model.getAttribute('aria-invalid'), '标「不在档案里」带 aria-invalid').toBe('true');
    expect(text(d)).toContain('不在 Quizs 已批准的档案里');
    expect(segTexts(thinkingGroup(d)), '档案不明时档位给六值').toEqual(SIX);
    expect(checkedSeg(thinkingGroup(d))).toBe('high');
    await advance(1000);
    expect(spyCalls('preview'), '档案外模型不调预览').toBe(0);
    fireEvent.change(model, { target: { value: 'deepseek/deepseek-chat' } });
    await settle();
    expect(model.getAttribute('aria-invalid'), '从档案里选一项之后 error 消失').toBe(null);
    await advance(350);
    expect(text(d), '从档案里选一项之后命令只含 --model').toContain('config profile edit step-old --model=deepseek/deepseek-chat');
    expect(text(d), '没点过档位就不传 thinking').not.toContain('--thinking=');
    expect(text(d), 'quizs 一律不交 credential_env').not.toContain('--credential-env');
  });
});

describe('T046 quizs：档案读不出时表单不卡死（D06）', () => {
  it('信封失败：写明原因（messages 第一行）、退回手填、常显手填提示、档位六段无 minimal、手填后照常预览', async () => {
    window.location.hash = '#/roles?write=ok&quizs=broken';
    const d = await openQuizsNew('gate-x');
    expect(text(d), '信封失败写明原因').toContain('读不出 Quizs 的提供方档案：ERROR: 没有设置 QUIZS_CMD，读不到 Quizs 提供方档案');
    expect(controlByLabel(d, '模型').tagName, '读不出档案退回手填文本框').toBe('INPUT');
    expect(text(d), '照旧提示手填').toContain('手填的模型没有核实');
    expect(segTexts(thinkingGroup(d)), '档位给六值（无 minimal）').toEqual(SIX);
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
    await advance(350);
    expect(text(d), '读不出档案预览照常可用').toContain('--runtime=quizs-cli --model=bb/m1');
  });

  it('信封失败（编辑）：模型退回手填并留住原值，改过之后照常预览', async () => {
    window.location.hash = '#/roles?write=ok&quizs=broken';
    const d = await openEdit(QUIZS_PROFILE);
    expect(text(d)).toContain('读不出 Quizs 的提供方档案：ERROR: 没有设置 QUIZS_CMD，读不到 Quizs 提供方档案');
    expect((controlByLabel(d, '模型') as HTMLInputElement).value, '原值留在手填框里').toBe('stepfun/step-4');
    expect(segTexts(thinkingGroup(d))).toEqual(SIX);
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
    await advance(350);
    expect(text(d)).toContain('config profile edit step-old --model=bb/m1');
    expect(text(d), 'quizs 一律不交 credential_env').not.toContain('--credential-env');
  });

  it('Promise reject：只写「读不出 Quizs 的提供方档案」，模型退回手填', async () => {
    set('getQuizsProviders', () => Promise.reject(new Error('boom')));
    const d = await openQuizsNew('gate-x');
    expect(text(d), 'reject 也写明原因').toContain('读不出 Quizs 的提供方档案');
    expect(text(d), 'reject 不带 messages 那一行').not.toContain('读不出 Quizs 的提供方档案：');
    expect(controlByLabel(d, '模型').tagName).toBe('INPUT');
    expect(segTexts(thinkingGroup(d))).toEqual(SIX);
  });

  it('无可选项：写「Quizs 没有列出可用的提供方档案」，模型退回手填、档位六值', async () => {
    window.location.hash = '#/roles?write=ok&quizs=empty';
    const d = await openQuizsNew('gate-x');
    expect(text(d)).toContain('Quizs 没有列出可用的提供方档案');
    expect(controlByLabel(d, '模型').tagName, '没有可用项退回手填').toBe('INPUT');
    expect(segTexts(thinkingGroup(d))).toEqual(SIX);
    expect(text(d)).toContain('手填的模型没有核实');
  });

  it('读取中：写「正在读 Quizs 的提供方档案…」，不调预览', async () => {
    set('getQuizsProviders', () => new Promise(() => {}));
    const d = await openQuizsNew('gate-x');
    expect(text(d)).toContain('正在读 Quizs 的提供方档案…');
    expect(controlByLabel(d, '模型').tagName, '读取中与非 quizs 同形态手填').toBe('INPUT');
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
    await advance(1000);
    expect(spyCalls('preview'), '档案不在读取中才许调预览').toBe(0);
  });
});

describe('T046 quizs：非 quizs 分支与真实模式（D01、D09）', () => {
  it('选 pi：getQuizsProviders 调用次数 0；凭据输入仍恰一个；七段档位与命令照旧', async () => {
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openNew();
    fireEvent.change(controlByLabel(d, 'ID'), { target: { value: 'gate-x' } });
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
    fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
    await settle();
    await advance(350);
    expect(spyCalls('getQuizsProviders'), '非 quizs 一次都不调').toBe(0);
    expect(text(d)).toContain('--runtime=pi --model=bb/m1');
    expect(text(d), '非 quizs 常显手填提示').toContain('手填的模型没有核实');
    expect(envLabels(d).length, '非 quizs 凭据输入仍恰一个').toBe(1);
    expect(segTexts(thinkingGroup(d)), '非 quizs 七段照旧').toEqual(['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
  });

  it('真实模式：注入 live 客户端后读服务回的信封，桩的档案不出现', async () => {
    const fakeClient: LiveClient = {
      get<T>(): Promise<import('../src/api').Envelope<T>> {
        return Promise.resolve({
          ok: true, exit_code: 0,
          data: { providers: [{ provider: 'qwen', model: 'qwen-max', thinking: ['high'], billing: 'qwen_credits' }] } as T,
          output: [], messages: [], command: ['config', 'quizs', 'providers', '--json'], elapsed_ms: 0,
        }) as Promise<import('../src/api').Envelope<T>>;
      },
      post<T>(): Promise<{ status: number; body: import('../src/api').Envelope<T> }> {
        return Promise.resolve({ status: 200, body: { ok: true, exit_code: 0, data: null as T, output: [], messages: [], command: [], elapsed_ms: 0 } });
      },
      getRaw<T>(): Promise<{ status: number; body: T }> {
        return Promise.resolve({ status: 404, body: null as T });
      },
    };
    setLiveClientForTests(fakeClient);
    window.location.hash = '#/roles?write=ok&quizs=ok';
    const d = await openQuizsNew('gate-x');
    expect(controlByLabel(d, '模型').tagName, '读的是服务回的信封').toBe('SELECT');
    expect(modelOptions(d), '服务回的档案').toEqual(['qwen/qwen-max']);
    expect(modelOptions(d).join(' '), '桩的档案不出现').not.toContain('stepfun/step-5-preview');
    expect(segTexts(thinkingGroup(d)), '档位按服务回的档案给').toEqual(['high']);
  });
});

// T050 竞态：读提供方档案的 effect 重跑（合同 t050 行为口径，不钉实现写法）。
// 复现竞态的关键：getRuntimes 与 getQuizsProviders 都换成手动兑现的 promise——两个已兑现 promise 的
// .then 会在同一次 act 里跑完，不手动控制就复现不出「运行时列表换数组作废在途读」。
// 手动兑现：promise 的兑现时机由测试掌握。
function deferred<T = unknown>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

// 档案 ok 信封（照 src/mock/quizs.ts 的 PROVIDER_ROWS 两行；信封形状照 quizsProvidersEnvelope()）。
const PROVIDERS_OK_ENV = {
  ok: true, exit_code: 0,
  data: {
    providers: [
      { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
      { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
    ],
  },
  output: [], messages: [], command: ['config', 'quizs', 'providers', '--json'], elapsed_ms: 0,
};
// 迟到的失败信封：回晚了必须被丢掉，不许盖掉已经读到的档案。
const PROVIDERS_LATE_BROKEN_ENV = {
  ok: false, exit_code: 1, data: null,
  output: [], messages: ['ERROR: 迟到的失败信封'], command: [], elapsed_ms: 0,
};

// 站主登记的顺序：先打开一次让运行时列表就位（beforeEach 的已兑现桩），取消；再换成手动兑现的两个读
// 函数，在同一个已挂载的组件上再打开一次（不重新 render），回到「getRuntimes 还没兑现、运行时列表还是
// 上一次的旧数组」的第二次打开；填 ID、选 quizs 运行时，发出第 1 次档案读（还在路上）。
async function secondOpenWithDeferredReads(id: string) {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const first = await openNew();
  expect((controlByLabel(first, 'runtime') as HTMLSelectElement).value, '夹具自证：第一次打开后 runtime 落在 pi').toBe('pi');
  fireEvent.click(buttonByText(first, '取消') as HTMLButtonElement);
  await settle();
  const rt = deferred<unknown>();
  const reads = [deferred<unknown>(), deferred<unknown>(), deferred<unknown>()];
  let n = 0;
  set('getRuntimes', () => rt.promise);
  set('getQuizsProviders', () => reads[n++]?.promise ?? new Promise(() => {}));
  fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
  await settle();
  const d = needFormDialog();
  fireEvent.change(controlByLabel(d, 'ID'), { target: { value: id } });
  fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
  await settle();
  return { d, rt, reads };
}

describe('T050 竞态：第二次打开与读档案途中 effect 重跑', () => {
  it('第二次打开、getRuntimes 回来之前选 quizs：列表换数组作废在途读，重跑照样再读，档案读到', async () => {
    const { d, rt, reads } = await secondOpenWithDeferredReads('t050-a');
    expect(spyCalls('getQuizsProviders'), '选了 quizs 运行时发出第 1 次读（还在路上）').toBe(1);
    expect(text(d), '夹具自证：界面停在正在读').toContain('正在读 Quizs 的提供方档案…');
    expect(controlByLabel(d, '模型').tagName, '夹具自证：读取中模型是手填').toBe('INPUT');
    rt.resolve(await runtimesEnv());
    await settle();
    expect(spyCalls('getQuizsProviders'), '列表换新数组作废在途读后重跑照样再读（作废一次 + 重读一次）').toBe(2);
    reads[1].resolve(PROVIDERS_OK_ENV);
    await settle();
    const model = controlByLabel(d, '模型') as HTMLSelectElement;
    expect(model.tagName, '档案读到后模型是档案 Select').toBe('SELECT');
    expect(modelOptions(d), '档案两项逐字是 provider/model').toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(model.value, '新建自动选档案第一项').toBe('stepfun/step-5-preview');
    expect(segTexts(thinkingGroup(d)), '档位按档案给').toEqual(['low', 'medium', 'high']);
    expect(text(d), '不再停在「正在读」').not.toContain('正在读 Quizs 的提供方档案…');
    await advance(350);
    expect(text(d), '命令带 --runtime=quizs-cli --model=provider/model').toContain('--runtime=quizs-cli --model=stepfun/step-5-preview');
    expect(formConfirm(d).disabled, '档案读到、预览回话之后 [确认…] 可点').toBe(false);
    reads[0].resolve(PROVIDERS_LATE_BROKEN_ENV);
    await settle();
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '迟到的第 1 次读回来不改界面').toBe('SELECT');
    expect(modelOptions(d), '迟到的结果不许盖掉读到的档案').toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(spyCalls('getQuizsProviders')).toBe(2);
  });

  it('档案读完之后列表换数组或切走再切回：不再读第二次，已读到的档案仍显示', async () => {
    const { d, rt, reads } = await secondOpenWithDeferredReads('t050-b');
    expect(spyCalls('getQuizsProviders'), '选了 quizs 运行时发出第 1 次读（还在路上）').toBe(1);
    reads[0].resolve(PROVIDERS_OK_ENV);
    await settle();
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '夹具自证：档案读到了').toBe('SELECT');
    rt.resolve(await runtimesEnv());
    await settle();
    expect(spyCalls('getQuizsProviders'), '读完之后 effect 再重跑不再读第二次').toBe(1);
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '已读到的档案仍在').toBe('SELECT');
    expect(modelOptions(d), '已读到的档案选项不变').toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
    await settle();
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
    await settle();
    expect(spyCalls('getQuizsProviders'), '读完之后切到非 quizs 再切回不重复读').toBe(1);
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '切回后已读到的档案仍显示').toBe('SELECT');
    expect(modelOptions(d), '切回后档案选项不变').toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
  });

  it('读档案途中切到 pi 再切回 quizs：切回时重新读，档案照样读到', async () => {
    const { d, reads } = await secondOpenWithDeferredReads('t050-c');
    expect(spyCalls('getQuizsProviders'), '选了 quizs 运行时发出第 1 次读（还在路上）').toBe(1);
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
    await settle();
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
    await settle();
    expect(spyCalls('getQuizsProviders'), '结果还在路上时切走作废这次读，切回时重读').toBe(2);
    reads[1].resolve(PROVIDERS_OK_ENV);
    await settle();
    const model = controlByLabel(d, '模型') as HTMLSelectElement;
    expect(model.tagName, '切回后档案照样读到').toBe('SELECT');
    expect(modelOptions(d), '切回后档案两项逐字是 provider/model').toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(model.value, '新建自动选档案第一项').toBe('stepfun/step-5-preview');
    expect(text(d), '不再停在「正在读」').not.toContain('正在读 Quizs 的提供方档案…');
    reads[0].resolve(PROVIDERS_LATE_BROKEN_ENV);
    await settle();
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '迟到的第 1 次读回来不改界面').toBe('SELECT');
    expect(modelOptions(d), '迟到的结果不许盖掉读到的档案').toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(spyCalls('getQuizsProviders')).toBe(2);
  });
});
