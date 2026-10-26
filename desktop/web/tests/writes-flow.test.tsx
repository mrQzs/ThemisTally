// 写流程状态机（合同第三、四节）的自测：经真实 ?write= 情景走完「预览 → 确认 → 执行 → 重读 → 结果」。
// 覆盖 D03–D05、D12 与 M1、M4、M5、M6、M7、M9、M10–M13、M17、M18、M19：成功只在重读之后才说（W3），
// 连接中断先轮询 getOperation 再下结论，轮询上限 120 秒。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope, PresetsData } from '../src/api';

const hoisted = vi.hoisted(() => ({ overrides: {} as Record<string, (...args: unknown[]) => Promise<unknown>> }));

// 只替掉个别读函数（用来卡住重读或改重读后的快照），其余照常转调真实现：演示数据仍来自夹具与 ?write=。
vi.mock('../src/api', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const out: Record<string, unknown> = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      out[name] = (...args: unknown[]) =>
        hoisted.overrides[name] ? hoisted.overrides[name](...args) : (fn as (...a: unknown[]) => unknown)(...args);
    }
  }
  return out;
});

const { PresetBar } = await import('../src/pages/readonly1/roles-PresetBar');

const PRESETS = [
  { name: 'default', description: 'x', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
  { name: 'economy', description: 'y', roles: ['execution'], active: false },
] as unknown as PresetsData['presets'];

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.location.hash = '';
});

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = <T extends Element>(sel: string) => Array.from(document.querySelectorAll(sel)) as T[];
const dlg = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const dlgText = () => {
  const d = dlg();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const bodyText = () => text(document.body);
const toastText = () => text(document.querySelector('.tt-toast'));
const btn = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;

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

function presetsEnv(active: string): Envelope<PresetsData> {
  return {
    ok: true,
    exit_code: 0,
    data: { active_preset: active, presets: PRESETS } as PresetsData,
    output: [],
    messages: [],
    command: ['config', 'preset', 'list'],
    elapsed_ms: 0,
  };
}

async function mount(hash: string) {
  window.location.hash = hash;
  const out = render(<PresetBar presets={PRESETS} active="default" />);
  await settle();
  return out;
}
async function openConfirm(hash: string) {
  await mount(hash);
  fireEvent.click(qa<HTMLElement>('[role="radio"]').find((r) => text(r) === 'economy') as HTMLElement);
  await settle();
  fireEvent.click(btn(document.body, '切换…') as HTMLButtonElement);
  await settle();
  dlgText();
}
async function confirmNow() {
  fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
  await settle();
  await advance(20);
}

describe('预览', () => {
  it('预览中：变化区是骨架屏，[确认…] 禁用，可以 [取消]；兑现后出现命令与 [确认…]', async () => {
    let release!: (v: unknown) => void;
    const gate = new Promise<unknown>((r) => {
      release = r;
    });
    set('preview', () => gate as Promise<unknown>);
    await mount('#/roles?write=ok');
    fireEvent.click(qa<HTMLElement>('[role="radio"]').find((r) => text(r) === 'economy') as HTMLElement);
    await settle();
    fireEvent.click(btn(document.body, '切换…') as HTMLButtonElement);
    await settle();
    await advance(300);
    const t = dlgText();
    expect(t).toContain('变化');
    expect(t).not.toContain('将运行的命令');
    expect(dlg()?.querySelector('.tt-skeleton'), '预览中变化区是骨架屏').not.toBeNull();
    expect((btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement).disabled).toBe(true);
    expect((btn(dlg() as HTMLElement, '取消') as HTMLButtonElement).disabled).toBe(false);
    release({
      status: 200,
      body: {
        ok: true,
        exit_code: 0,
        data: {
          binding_changes: [{ role: 'execution', from: 'step-high', to: 'step-low' }],
          resources: ['roles'],
          notes: [],
          warnings: [],
          running_attempts: [],
          needs_yes: false,
          command: ['config', 'preset', 'use', 'economy'],
          confirmation: 'conf-1',
        },
        output: [],
        messages: [],
        command: ['config', 'preset', 'use', 'economy', '--dry-run', '--json'],
        elapsed_ms: 0,
      },
    });
    await settle();
    const after = dlgText();
    expect(after).toContain('将运行的命令');
    expect(after).toContain('config preset use economy');
    expect(after).toContain('execution');
    expect((btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement).disabled).toBe(false);
    expect(dlg()?.querySelector('.tt-skeleton')).toBeNull();
    fireEvent.click(btn(dlg() as HTMLElement, '取消') as HTMLButtonElement);
    await settle();
    expect(dlg()).toBeNull();
  });

  it('预览失败（preview-fail）：[重新预览] [关闭]，不重读', async () => {
    await openConfirm('#/roles?write=preview-fail');
    await advance(20);
    expect(dlgText()).toContain('ERROR');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(btn(dlg() as HTMLElement, '关闭')).toBeTruthy();
    expect(bodyText()).not.toContain('已切换');
  });

  it('预览繁忙（preview-busy）：提示「服务繁忙，请稍后重试」', async () => {
    await openConfirm('#/roles?write=preview-busy');
    await advance(20);
    expect(dlgText()).toContain('服务繁忙，请稍后重试');
  });
});

describe('成功只在重读之后才说（W3）', () => {
  it('ok：确认后重读兑现才关框、弹「已切换到方案 economy」', async () => {
    await openConfirm('#/roles?write=ok');
    await confirmNow();
    expect(dlg(), '完成后关框').toBeNull();
    expect(bodyText()).toContain('已切换到方案 economy');
  });

  it('重读卡住时整页没有「已切换」、Toast 区域空；兑现之后才说成功（M1）', async () => {
    let hang = false;
    let release!: (v: Envelope<PresetsData>) => void;
    const gate = new Promise<Envelope<PresetsData>>((r) => {
      release = r;
    });
    set('getPresets', () => (hang ? gate : Promise.resolve(presetsEnv('default'))));
    await openConfirm('#/roles?write=ok');
    hang = true;
    fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
    await settle();
    await advance(20);
    expect(dlg(), '重读中框还开着').not.toBeNull();
    expect(dlgText()).not.toContain('已切换');
    expect(toastText(), '重读兑现之前 Toast 区域是空的').toBe('');
    expect(bodyText(), '重读兑现之前整页没有「已切换」').not.toContain('已切换');
    release(presetsEnv('economy'));
    await settle();
    await advance(20);
    expect(dlg()).toBeNull();
    expect(bodyText()).toContain('已切换到方案 economy');
  });

  it('warn：不关框，warning 条列出 WARN 行，按钮 [知道了]，不弹轻提示（M17）', async () => {
    await openConfirm('#/roles?write=warn');
    await confirmNow();
    const d = dlg() as HTMLElement;
    expect(d, '有 WARN 时不应直接关框').not.toBeNull();
    expect(d.querySelector('[data-tone="warning"]')).not.toBeNull();
    expect(text(d)).toContain('WARN');
    expect(btn(d, '知道了')).toBeTruthy();
    expect(toastText(), '完成但有警告不弹轻提示').toBe('');
  });

  it('reread-fail：执行成功但重读失败 →「命令已成功，但重新读取失败，请刷新」，不弹轻提示（M9）', async () => {
    await openConfirm('#/roles?write=reread-fail');
    await confirmNow();
    expect(dlgText()).toContain('命令已成功，但重新读取失败，请刷新');
    expect(btn(dlg() as HTMLElement, '关闭')).toBeTruthy();
    expect(toastText()).toBe('');
    expect(bodyText()).not.toContain('已切换');
  });
});

describe('执行失败与 409', () => {
  it('exit3：整页没有「已切换」没有「成功」，框里有「内核拒绝」与 [重新预览] [关闭]（M18）', async () => {
    await openConfirm('#/roles?write=exit3');
    await confirmNow();
    expect(toastText()).toBe('');
    expect(bodyText()).not.toContain('已切换');
    expect(bodyText()).not.toContain('成功');
    expect(dlgText()).toContain('内核拒绝');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(btn(dlg() as HTMLElement, '关闭')).toBeTruthy();
  });

  it('exit2：原因是「用法错误」', async () => {
    await openConfirm('#/roles?write=exit2');
    await confirmNow();
    expect(dlgText()).toContain('用法错误');
    expect(bodyText()).not.toContain('已切换');
  });

  it('exit1 且重读后快照相同 → 失败，原因「内核拒绝」，不弹轻提示（M19）', async () => {
    await openConfirm('#/roles?write=exit1');
    await confirmNow();
    expect(dlgText()).toContain('内核拒绝');
    expect(dlgText()).not.toContain('已部分写入');
    expect(toastText()).toBe('');
    expect(bodyText()).not.toContain('已切换');
  });

  it('exit1 且重读后快照不同 → 「已部分写入，结果待核实」，框里没有「成功」', async () => {
    let flipped = false;
    set('getPresets', () => Promise.resolve(presetsEnv(flipped ? 'economy' : 'default')));
    await openConfirm('#/roles?write=exit1');
    flipped = true;
    await confirmNow();
    expect(dlgText()).toContain('已部分写入，结果待核实');
    expect(dlgText()).not.toContain('成功');
    expect(btn(dlg() as HTMLElement, '查看历史')).toBeTruthy();
    expect(toastText()).toBe('');
  });

  it('stale（409 退出 4）：「配置在你确认之前被改动了，请重新预览」+ [重新预览]', async () => {
    await openConfirm('#/roles?write=stale');
    await confirmNow();
    expect(dlgText()).toContain('配置在你确认之前被改动了，请重新预览');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(toastText()).toBe('');
  });

  it('expired（409、exit_code 为 null）：「确认已失效」，与 stale 文案不同（M4）', async () => {
    await openConfirm('#/roles?write=expired');
    await confirmNow();
    const t = dlgText();
    expect(t).toContain('确认已失效');
    expect(t).toContain('请重新预览');
    expect(t).not.toContain('配置在你确认之前被改动了');
  });

  it('timeout（504）：按超时重读再分，快照相同 → 失败带「超时」', async () => {
    await openConfirm('#/roles?write=timeout');
    await confirmNow();
    expect(dlgText()).toContain('超时');
    expect(bodyText()).not.toContain('已切换');
  });

  it('toolarge（500）：服务出错也重读再分，不重读就判失败是错的（M7）', async () => {
    await openConfirm('#/roles?write=toolarge');
    await confirmNow();
    expect(dlgText()).toContain('服务出错');
    expect(bodyText()).not.toContain('已切换');
  });

  it('spawn（500）：同样是服务出错，重读之后再分', async () => {
    await openConfirm('#/roles?write=spawn');
    await confirmNow();
    expect(dlgText()).toContain('服务出错');
    expect(bodyText()).not.toContain('已切换');
  });

  it('reread-fail-exit1（退出 1 且重读失败）：结果未知，不猜成失败', async () => {
    await openConfirm('#/roles?write=reread-fail-exit1');
    await confirmNow();
    expect(dlgText()).toContain('结果未知，请在历史与审计里核对');
    expect(btn(dlg() as HTMLElement, '打开历史')).toBeTruthy();
    expect(bodyText()).not.toContain('已切换');
    expect(toastText()).toBe('');
  });
});

describe('503 与连接中断', () => {
  it('busy（503 且查不到操作）：回到可确认，提示「服务繁忙，请稍后再确认」（M5/M6）', async () => {
    await openConfirm('#/roles?write=busy');
    await confirmNow();
    expect(dlgText()).toContain('服务繁忙，请稍后再确认');
    expect(btn(dlg() as HTMLElement, '确认…'), '回到可确认应有 [确认…]').toBeTruthy();
    expect(toastText()).toBe('');
  });

  it('closing（503，查到 failed/closing 终态）：按服务出错重读再分，快照相同 → 失败带「服务出错」', async () => {
    await openConfirm('#/roles?write=closing');
    await confirmNow();
    expect(dlgText()).toContain('服务出错');
    expect(btn(dlg() as HTMLElement, '重新预览')).toBeTruthy();
    expect(toastText()).toBe('');
  });

  it('drop-done：执行抛错 →「连接中断，正在确认结果…」，轮询到终态后重读完成、弹轻提示（M12）', async () => {
    await openConfirm('#/roles?write=drop-done');
    await confirmNow();
    expect(dlgText()).toContain('连接中断，正在确认结果…');
    await advance(1000);
    await advance(1000);
    expect(dlg()).toBeNull();
    expect(bodyText(), '轮询到 succeeded 后重读完成').toContain('已切换到方案 economy');
  });

  it('drop-lost：getOperation 404 → 「结果未知，请在历史与审计里核对」+ [打开历史]（M13）', async () => {
    await openConfirm('#/roles?write=drop-lost');
    await confirmNow();
    await advance(1500);
    expect(dlgText()).toContain('结果未知，请在历史与审计里核对');
    expect(btn(dlg() as HTMLElement, '打开历史')).toBeTruthy();
    expect(toastText()).toBe('');
  });

  it('drop-hang：119 秒仍在轮询不下结论，120 秒上限到了进「结果未知」（M10/M11）', async () => {
    await openConfirm('#/roles?write=drop-hang');
    await confirmNow();
    expect(dlgText()).toContain('连接中断');
    await advance(119000);
    expect(dlgText(), '119 秒仍是 running 时不下结论').toContain('连接中断');
    expect(dlgText()).not.toContain('结果未知');
    await advance(2000);
    expect(dlgText(), '120 秒上限到了进「结果未知」，不是失败').toContain('结果未知，请在历史与审计里核对');
    expect(dlgText()).not.toContain('内核拒绝');
    expect(toastText()).toBe('');
  });
});

describe('被拒与其他状态码', () => {
  it('400：显示报错与「请求被拒」，按钮 [关闭]，不重读', async () => {
    set('usePreset', () =>
      Promise.resolve({
        status: 400,
        body: {
          ok: false,
          exit_code: null,
          data: null,
          output: [],
          messages: ['ERROR 请求被拒：confirmation 不匹配'],
          command: ['config', 'preset', 'use', 'economy'],
          elapsed_ms: 0,
        },
      }),
    );
    await openConfirm('#/roles?write=ok');
    await confirmNow();
    expect(dlgText()).toContain('请求被拒');
    expect(dlgText()).toContain('ERROR 请求被拒：confirmation 不匹配');
    expect(btn(dlg() as HTMLElement, '关闭')).toBeTruthy();
    expect(bodyText()).not.toContain('已切换');
  });
});
