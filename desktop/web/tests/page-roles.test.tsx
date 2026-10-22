// 角色与模型测试（合同第 9 节，注入数据）：RoleCard 四模式、PresetBar、ProfilesTable、PresetsTable 与 PresetDiff 三态/收起/过期丢弃。
import { afterEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { RoleCard } from '../src/pages/readonly1/roles-RoleCard';
import { PresetBar } from '../src/pages/readonly1/roles-PresetBar';
import { ProfilesTable } from '../src/pages/readonly1/roles-ProfilesTable';
import { PresetsTable } from '../src/pages/readonly1/roles-PresetsTable';
import { normalizeRole } from '../src/pages/readonly1/roles-logic';

afterEach(cleanup);

const text = (el: any) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string) => Array.from(root.querySelectorAll(sel));
const btn = (root: any, label: string) => qa(root, 'button').find((b: any) => text(b) === label);
function kv(card: any): Record<string, any> {
  const out: Record<string, any> = {};
  qa(card, 'dt').forEach((dt: any) => {
    out[text(dt)] = dt.nextElementSibling;
  });
  return out;
}
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}

const ROLES = [
  normalizeRole({ role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false } as any),
  normalizeRole({ role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: true } as any),
  normalizeRole({ role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'low' } as any),
  normalizeRole({ role: 'scheduler_agent', explicit: false, binding: { mode: 'disabled' }, differs_from_preset: false } as any),
];

describe('RoleCard 四模式', () => {
  it('交互式宿主', () => {
    const { container } = render(<RoleCard role={ROLES[0]} activePreset="default" />);
    const c = container.querySelector('article[data-role="planning_review"]') as any;
    expect(text(c.querySelector('h3'))).toBe('规划审核端');
    expect(qa(c, '.tt-tag').some((t: any) => text(t) === '交互式宿主')).toBe(true);
    expect(qa(c, '.tt-tag').some((t: any) => text(t) === '已接通')).toBe(false);
    expect(text(kv(c)['宿主'])).toBe('claude-code');
    expect(kv(c)['思考档位'].querySelector('.tt-effort')?.getAttribute('data-state')).toBe('none');
    expect(text(c)).toContain('模型由宿主决定，Themis 不切换。');
    expect(btn(c, '更改…')?.disabled).toBe(true);
  });

  it('手工：默认、与方案不一致、说明', () => {
    const { container } = render(<RoleCard role={ROLES[1]} activePreset="default" />);
    const c = container.querySelector('article[data-role="contract"]') as any;
    const differs = qa(c, '.tt-tag').find((t: any) => text(t) === '与方案 default 不一致');
    expect(differs?.getAttribute('data-tone')).toBe('attention');
    expect(qa(c, '.tt-tag').some((t: any) => text(t) === '默认')).toBe(true);
    expect(Object.keys(kv(c))).toEqual(['思考档位']);
    expect(text(c)).toContain('规划端亲自写合同');
  });

  it('无头：键值四项、已接通、思考档位不同', () => {
    const { container } = render(<RoleCard role={ROLES[2]} activePreset="default" />);
    const c = container.querySelector('article[data-role="execution"]') as any;
    expect(Object.keys(kv(c))).toEqual(['profile', 'runtime', '模型', '思考档位']);
    expect(text(kv(c)['runtime'])).toBe('pi（pi）');
    expect(text(kv(c)['模型'])).toBe('bb/step-5-preview');
    const ok = qa(c, '.tt-tag').find((t: any) => text(t) === '已接通');
    expect(ok?.getAttribute('data-tone')).toBe('success');
    expect(kv(c)['思考档位'].querySelector('.tt-effort')?.getAttribute('data-state')).toBe('differs');
  });

  it('关闭：说明、默认', () => {
    const { container } = render(<RoleCard role={ROLES[3]} activePreset="default" />);
    const c = container.querySelector('article[data-role="scheduler_agent"]') as any;
    expect(qa(c, '.tt-tag').some((t: any) => text(t) === '关闭')).toBe(true);
    expect(text(c)).toContain('本轮没有实现');
  });
});

describe('PresetBar', () => {
  const presets = [
    { name: 'default', description: 'x', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
    { name: 'economy', description: 'y', roles: ['execution'], active: false },
  ] as any;

  it('选项与初值、两种说明、[切换…] 禁用', () => {
    const { container } = render(<PresetBar presets={presets} active="default" />);
    const radios = qa(container, '[role="radio"]');
    expect(radios.map((r: any) => text(r))).toEqual(['default', 'economy']);
    expect(text(container)).toContain('当前：default · 4 个角色');
    expect(btn(container, '切换…')?.disabled).toBe(true);
    fireEvent.click(radios[1]);
    expect(text(container)).toContain('已选 economy · 切换在第二阶段接入');
  });

  it('无方案时只写提示', () => {
    const { container } = render(<PresetBar presets={[]} active="default" />);
    expect(text(container)).toContain('还没有方案');
    expect(container.querySelector('[role="radiogroup"]')).toBeNull();
    expect(btn(container, '切换…')).toBeUndefined();
  });
});

describe('ProfilesTable', () => {
  it('各列、thinking 缺省、凭据、被引用、操作禁用', () => {
    const profiles = [
      { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY', 'OTHER_KEY'] },
      { id: 'bare', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: {}, credential_env: [] },
    ] as any;
    const { container } = render(<ProfilesTable profiles={profiles} roles={ROLES} />);
    const table = container.querySelector('table[aria-label="profile"]') as any;
    expect(qa(table, 'thead th').map(text)).toEqual(['ID', 'runtime', '模型', 'thinking', '凭据变量', '被引用', '操作']);
    const trs = qa(table, 'tbody tr');
    expect(trs.length).toBe(2);
    const creds = qa(trs[0].children[4], '.tt-tag').map(text);
    expect(creds).toEqual(['STEP_API_KEY', 'OTHER_KEY']);
    expect(text(trs[0].children[6])).toContain('编辑');
    expect(btn(trs[0].children[6], '编辑')?.disabled).toBe(true);
    expect(text(trs[1].children[3])).toBe('缺省');
  });
});

describe('PresetsTable 与差异面板', () => {
  const presets = [
    { name: 'default', description: 'x', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
    { name: 'economy', description: 'y', roles: ['execution'], active: false },
  ] as any;
  const diffEnv = (a: string, b: string, roles: any[]): any => ({ ok: true, exit_code: 0, data: { a, b, roles }, output: [], messages: [], command: ['config', 'preset', 'diff', a, b], elapsed_ms: 0 });

  it('当前行不能删，其余行按钮与 [查看差异]；展开读一次、显示差异、可收起', async () => {
    const calls: any[] = [];
    const onDiff = (a: string, b: string) => {
      calls.push([a, b]);
      return Promise.resolve(diffEnv(a, b, [{ role: 'execution', a: { mode: 'headless', profile: 'step-high' }, b: { mode: 'headless', profile: 'step-low' }, same: false }]));
    };
    const { container } = render(<PresetsTable presets={presets} active="default" totalRoles={4} onDiff={onDiff} />);
    const trs = qa(container, 'tbody tr');
    expect(text(trs[0].children[4])).toContain('当前方案不能删');
    expect(btn(trs[0].children[4], '使用')).toBeUndefined();
    const diff = btn(trs[1].children[4], '查看差异');
    expect(diff?.disabled).toBe(false);
    expect(diff!.getAttribute('aria-controls')).toBeNull();
    fireEvent.click(diff!);
    await flush();
    expect(calls).toEqual([['default', 'economy']]);
    const controls = diff!.getAttribute('aria-controls') as string;
    expect(controls, '展开后 aria-controls 应指向存在的面板').toBeTruthy();
    expect(controls).not.toMatch(/\s/);
    const panel = document.getElementById(controls) as any;
    expect(text(panel)).toContain('default 与 economy 的差异');
    expect(panel.textContent.replace(/\s+/g, '')).toContain('其余3个角色相同');
    fireEvent.click(diff!);
    await flush();
    expect(diff!.getAttribute('aria-controls')).toBeNull();
    expect(document.getElementById(controls)).toBeNull();
  });

  it('出错显示命令与退出码加 messages', async () => {
    const onDiff = () => Promise.resolve({ ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR 坏'], command: ['config', 'preset', 'diff', 'default', 'economy'], elapsed_ms: 0 } as any);
    const { container } = render(<PresetsTable presets={presets} active="default" totalRoles={4} onDiff={onDiff} />);
    const diff = btn(qa(container, 'tbody tr')[1].children[4], '查看差异');
    fireEvent.click(diff!);
    await flush();
    const panel = document.getElementById(diff!.getAttribute('aria-controls') as string) as any;
    expect(text(panel)).toContain('没能读到差异：命令 config preset diff default economy 返回退出码 2。');
    expect(panel.querySelector('pre')?.textContent).toBe('ERROR 坏');
  });
});
