// 「保存当前为方案」表单与写流程的组件测试（合同第 7 步）：直接渲染 PresetSaveAction（不挂整页 App、不 mock 被测组件），
// 用 setLiveClientForTests 注入假服务记录预览与写请求，看真实正文（force 'true' 经 writeArgs 转成布尔 true）。
// 覆盖：只列 explicit 角色且缺省全选、预览 args 的 roles 恰是读到的两个；不合法名当场错误句且不发预览；
// 重名显示「会覆盖方案 default」、不勾覆盖不可确认、勾了正文带布尔 force、改名复位覆盖勾选；
// 确认先关表单再开确认框、POST /api/v1/presets/<name>/save、写完 reload；一个显式绑定都没有给原因句；
// 取消再开/外部改数据再开都按当时数据预填。等防抖用真实计时器 sleep(450)（不用假计时器）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { PresetSaveAction } from '../src/writes/PresetSaveForm';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const ENTRY = '保存当前为方案…';
const NO_EXPLICIT = '还没有写出绑定的角色：先在角色卡上用 [更改…] 写出绑定';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function inputByLabel(d: HTMLElement, labelText: string): HTMLInputElement {
  const label = qa(d, 'label').find((l: any) => text(l) === labelText);
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const hit = qa(d, 'input').find((el: any) => el.id === (label as any).getAttribute('for'));
  expect(hit, 'label 关联的 input 应在表单里').toBeTruthy();
  return hit as HTMLInputElement;
}
function checkboxByLabel(d: HTMLElement, label: string): HTMLElement {
  const hit = qa(d, '[role="checkbox"]').find((b: any) => text(b) === label);
  expect(hit, '应有勾选项「' + label + '」').toBeTruthy();
  return hit as HTMLElement;
}
function boxesOf(d: HTMLElement): any[] {
  return qa(d, '[role="checkbox"]').filter((b: any) => text(b).indexOf('角色-') === 0);
}

function okEnv<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function badEnv(): any {
  return { ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 读不出'], command: [], elapsed_ms: 0 };
}

let posts: Array<{ path: string; body: any }> = [];

// 可变数据：换内容模拟「外部改了数据后再开」与读失败；roles 的四行 explicit 可调。
function rolesEnvelope(explicit: Record<string, boolean>): any {
  return {
    roles: ['planning_review', 'contract', 'execution', 'scheduler_agent'].map((role) => ({
      role,
      explicit: explicit[role] === true,
      binding: { mode: 'manual' },
    })),
  };
}
const DEFAULT_ROLES = rolesEnvelope({ planning_review: true, execution: true });
const PRESETS_DATA = {
  active_preset: 'default',
  presets: [
    { name: 'default', description: '日常', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
    { name: 'economy', description: '省钱', roles: ['execution'], active: false },
  ],
};
let rolesData: any = DEFAULT_ROLES;
let rolesFail = false;

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/roles') return Promise.resolve(rolesFail ? badEnv() : okEnv(rolesData));
    if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS_DATA));
    return Promise.resolve(okEnv(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const a: any = (body as any).args;
      const command = ['config', 'preset', 'save', a.name, '--roles=' + (a.roles || []).join(',')];
      if (a.description) command.push('--description=' + a.description);
      if (a.force === true) command.push('--force');
      command.push('--dry-run', '--json');
      const preview = {
        binding_changes: [], resources: [{ resource: 'presets' }], notes: [], warnings: [],
        running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [],
      };
      return Promise.resolve({ status: 200, body: okEnv({ preview, confirmation: 'c-real-1' }, command) });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'preset', 'save']) });
  },
  getRaw(): Promise<any> {
    return Promise.resolve({ status: 404, body: null });
  },
};

function props(over: Record<string, unknown> = {}): any {
  return { reload: vi.fn(() => Promise.resolve()), roleLabel: (c: string) => '角色-' + c, ...over };
}
function previews(): any[] {
  return posts.filter((x) => x.path === '/api/v1/preview');
}
function saveWrites(): any[] {
  return posts.filter((x) => x.path.indexOf('/api/v1/presets/') === 0 && x.path.endsWith('/save'));
}

beforeEach(() => {
  posts = [];
  rolesData = DEFAULT_ROLES;
  rolesFail = false;
  setLiveClientForTests(fake);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('PresetSaveAction：入口与角色清单（真实模式）', () => {
  it('(a) 入口 secondary/md 一直可点；只列 explicit 角色且缺省全选；预览 args 恰是 name+roles', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    const entry = btnIn(r.container, ENTRY);
    expect(entry.disabled, '入口一直可点').toBe(false);
    expect(entry.getAttribute('data-variant')).toBe('secondary');
    expect(entry.getAttribute('data-size')).toBe('md');
    fireEvent.click(entry);
    await flush();
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('保存当前为方案');
    const boxes = boxesOf(d);
    expect(boxes.map((b: any) => text(b)), '只列 explicit 的两个，次序照读到的').toEqual(['角色-planning_review', '角色-execution']);
    expect(boxes.every((b: any) => b.getAttribute('aria-checked') === 'true'), '缺省全选').toBe(true);
    const name = inputByLabel(d, '方案名');
    expect(name.className, '方案名等宽字体').toContain('mono');
    expect(text(d), '名字空 → 错误句').toContain('方案名要填');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(name, { target: { value: 'demo-save' } });
    await sleep(450);
    await flush();
    const prev = previews().pop();
    expect(prev, '应发过预览').toBeTruthy();
    expect((prev!.body as any).args, 'roles 一律显式带，说明空不带 description').toEqual({ name: 'demo-save', roles: ['planning_review', 'execution'] });
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    expect(text(needDlg()), '底部预览命令').toContain('config preset save demo-save --roles=planning_review,execution');
  });
});

describe('PresetSaveAction：校验与勾选（真实模式）', () => {
  it('(b) 不合法名/超长说明当场错误句且不发预览；一个都没勾原因句；勾回一个预览更新', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'Bad Name' } });
    await flush();
    let d = needDlg();
    expect(text(d), '不合法名 → 错误句').toContain('方案名不合法：小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(inputByLabel(d, '说明'), { target: { value: '字'.repeat(201) } });
    await sleep(450);
    await flush();
    d = needDlg();
    expect(text(d), '说明超 200 码点 → 错误句').toContain('说明最多 200 个字，不能有控制字符');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    expect(previews().length, '不合法时不调预览').toBe(0);
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'good-name' } });
    fireEvent.change(inputByLabel(needDlg(), '说明'), { target: { value: '' } });
    await sleep(450);
    await flush();
    expect(previews().length, '改合法后预览发出').toBe(1);
    fireEvent.click(checkboxByLabel(needDlg(), '角色-planning_review'));
    await sleep(450);
    await flush();
    const half = previews().pop();
    expect((half!.body as any).args.roles, '只勾 execution').toEqual(['execution']);
    const before = previews().length;
    fireEvent.click(checkboxByLabel(needDlg(), '角色-execution'));
    await sleep(450);
    await flush();
    d = needDlg();
    expect(text(d), '一个都没勾 → 原因句').toContain('还没有勾要存的角色');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    expect(previews().length, '一个都没勾时不调预览').toBe(before);
  });
});

describe('PresetSaveAction：重名与覆盖（真实模式）', () => {
  it('(c) 重名显示会覆盖；不勾覆盖不发预览；勾了正文带布尔 force；改名复位覆盖勾选', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'default' } });
    await sleep(450);
    await flush();
    let d = needDlg();
    expect(text(d), '重名提示').toContain('会覆盖方案 default');
    const over = checkboxByLabel(d, '覆盖方案 default');
    expect(over.getAttribute('aria-checked'), '覆盖勾选缺省不勾').toBe('false');
    expect(btnIn(d, '确认…').disabled, '不勾覆盖不可确认').toBe(true);
    expect(previews().length, '不勾覆盖不发预览').toBe(0);
    fireEvent.click(over);
    await sleep(450);
    await flush();
    const prev = previews().pop();
    expect(prev, '勾了覆盖才预览').toBeTruthy();
    expect((prev!.body as any).args.force, 'writeArgs 把 force 转成布尔 true').toBe(true);
    expect(text(needDlg()), '命令带 --force').toContain('--force');
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'economy' } });
    await flush();
    d = needDlg();
    expect(checkboxByLabel(d, '覆盖方案 economy').getAttribute('aria-checked'), '改名后覆盖勾选复位').toBe('false');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(inputByLabel(d, '方案名'), { target: { value: 'fresh-preset' } });
    await sleep(450);
    await flush();
    d = needDlg();
    expect(text(d), '不重名 → 没有覆盖提示').not.toContain('会覆盖方案');
    expect(qa(d, '[role="checkbox"]').some((b: any) => text(b).indexOf('覆盖方案') === 0), '没有覆盖勾选项').toBe(false);
    const prev2 = previews().pop();
    expect((prev2!.body as any).args.force, '不重名不带 force').toBeUndefined();
    expect(btnIn(d, '确认…').disabled).toBe(false);
  });
});

describe('PresetSaveAction：确认与写流程（真实模式）', () => {
  it('(d) 确认先关表单再开确认框；POST 正文无 name 无 force；成功轻提示与 reload', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<PresetSaveAction {...props({ reload })} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'demo-save' } });
    fireEvent.change(inputByLabel(needDlg(), '说明'), { target: { value: '一句说明' } });
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '写确认框标题（表单已关上）').toContain('保存方案 demo-save？');
    expect(text(cd), '写确认框里没有表单字段').not.toContain('方案名');
    expect(text(cd), '变化区摘要').toContain('方案表里加上 demo-save：存 planning_review、execution');
    expect(text(cd), '将运行的命令').toContain('config preset save demo-save --roles=planning_review,execution --description=一句说明');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = saveWrites();
    expect(writes.length, '只发一次写路由').toBe(1);
    expect(writes[0].path).toBe('/api/v1/presets/demo-save/save');
    const wb = writes[0].body as any;
    expect(wb.roles).toEqual(['planning_review', 'execution']);
    expect(wb.description).toBe('一句说明');
    expect(typeof wb.confirmation).toBe('string');
    expect('name' in wb, 'name 走路径段，不在正文').toBe(false);
    expect('force' in wb, '不覆盖不带 force').toBe(false);
    expect(text(document.body), '成功轻提示').toContain('已保存方案 demo-save');
    expect(reload, '成功后 reload').toHaveBeenCalled();
    // 写完后再开：按当时的数据预填（缺省全选、名字清空）。
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    const d2 = needDlg();
    expect(boxesOf(d2).map((b: any) => text(b)), '写完后再开按当时数据预填').toEqual(['角色-planning_review', '角色-execution']);
    expect(boxesOf(d2).every((b: any) => b.getAttribute('aria-checked') === 'true'), '再开缺省全选').toBe(true);
    expect(inputByLabel(d2, '方案名').value, '再开名字清空').toBe('');
  });

  it('(d2) 覆盖流：摘要「覆盖方案 default：存 …」；正文 force 是布尔 true；成功轻提示与 reload', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<PresetSaveAction {...props({ reload })} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'default' } });
    await sleep(450);
    await flush();
    fireEvent.click(checkboxByLabel(needDlg(), '覆盖方案 default'));
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '覆盖分支的摘要').toContain('覆盖方案 default：存 planning_review、execution');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = saveWrites();
    expect(writes.length).toBe(1);
    expect(writes[0].path).toBe('/api/v1/presets/default/save');
    expect((writes[0].body as any).force, '正文 force 是布尔 true').toBe(true);
    expect(text(document.body), '成功轻提示').toContain('已保存方案 default');
    expect(reload).toHaveBeenCalled();
  });
});

describe('PresetSaveAction：空与读失败（真实模式）', () => {
  it('(e) 一个显式绑定都没有：原因句、确认… 不可点、不发预览；入口仍可点', async () => {
    rolesData = rolesEnvelope({});
    const r = render(<PresetSaveAction {...props()} />);
    const entry = btnIn(r.container, ENTRY);
    expect(entry.disabled, '页头入口不随数据变灰').toBe(false);
    fireEvent.click(entry);
    await flush();
    const d = needDlg();
    expect(text(d), '原因句').toContain(NO_EXPLICIT);
    expect(boxesOf(d).length, '没有角色勾选项').toBe(0);
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(inputByLabel(d, '方案名'), { target: { value: 'demo-save' } });
    await sleep(450);
    await flush();
    expect(previews().length, '没有可存的角色时不调预览').toBe(0);
  });

  it('(f) 读不出（roles 失败）：原因句、确认… 不可点、不发预览', async () => {
    rolesFail = true;
    const r = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    const d = needDlg();
    expect(text(d), '读不出 → 原因句').toContain('读不出当前的角色绑定与方案列表：稍后再试');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    await sleep(450);
    await flush();
    expect(previews().length, '读不出时不调预览').toBe(0);
  });
});

describe('PresetSaveAction：取消再开与外部改动再开（真实模式）', () => {
  it('(g) 取消再开回到缺省全选；外部改了数据再开按新数据预填', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.click(checkboxByLabel(needDlg(), '角色-execution'));
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'draft' } });
    await flush();
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单应关上').toBeNull();
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    let d = needDlg();
    expect(boxesOf(d).every((b: any) => b.getAttribute('aria-checked') === 'true'), '取消后再开回到缺省全选（丢弃未保存取值）').toBe(true);
    expect(inputByLabel(d, '方案名').value, '取消后再开名字清空').toBe('');
    fireEvent.click(btnIn(d, '取消'));
    await flush();
    rolesData = rolesEnvelope({ execution: true });
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    d = needDlg();
    expect(boxesOf(d).map((b: any) => text(b)), '外部改了绑定后再开按新数据预填').toEqual(['角色-execution']);
    expect(boxesOf(d)[0].getAttribute('aria-checked'), '新清单也缺省全选').toBe('true');
  });
});
