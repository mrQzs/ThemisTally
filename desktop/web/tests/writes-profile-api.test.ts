// T024 api 与 mock 的自测（合同第一、二、七节；D01–D03、D07、D11）：
// 两个新写函数 addProfile/editProfile、profile.add/profile.edit 的命令 argv（数组按顺序逐项，不拼成字符串）、
// 确认号与参数核对（号不存在 / action 不符 / 数组顺序错 / 丢项 / 多了项都 409 且 exit_code 为 null）、
// preview-warn 与 preview-invalid 两个新 ?write= 情景的实测响应、profileSnapshot 投影只比约定字段。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import * as api from '../src/api';
import { profileSnapshot, sameSnapshot } from '../src/writes/snapshots';

beforeEach(() => {
  window.location.hash = '';
});
afterEach(() => {
  window.location.hash = '';
});

const ADD_FULL = { profile: 'gate-new', runtime: 'pi', model: 'bb/m1', thinking: 'high', credential_env: ['AAA_KEY', 'BBB_KEY'] };
const ADD_MIN = { profile: 'x1', runtime: 'pi', model: 'bb/m' };

describe('T024 api：两个新写函数与命令 argv（D01）', () => {
  it('导出 addProfile/editProfile；profile.add 预览命令照服务侧 buildWriteArgv（数组按顺序逐项）', async () => {
    window.location.hash = '#/roles?write=ok';
    expect(typeof (api as unknown as { addProfile: unknown }).addProfile).toBe('function');
    expect(typeof (api as unknown as { editProfile: unknown }).editProfile).toBe('function');
    const r = await api.preview('profile.add', ADD_FULL);
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(r.body.data!.command).toEqual([
      'config', 'profile', 'add', 'gate-new', '--runtime=pi', '--model=bb/m1',
      '--thinking=high', '--credential-env=AAA_KEY', '--credential-env=BBB_KEY', '--dry-run', '--json',
    ]);
    expect(r.body.data!.binding_changes, 'profile.add 的 binding_changes 恒为空数组').toEqual([]);
  });

  it('profile.add 不传 thinking/credential_env 就没有对应开关；profile.edit 只传了的字段才有 --opt', async () => {
    window.location.hash = '#/roles?write=ok';
    const add = await api.preview('profile.add', ADD_MIN);
    expect(add.body.data!.command).toEqual(['config', 'profile', 'add', 'x1', '--runtime=pi', '--model=bb/m', '--dry-run', '--json']);
    const edit = await api.preview('profile.edit', { profile: 'step-high', model: 'bb/m2' });
    expect(edit.body.data!.command).toEqual(['config', 'profile', 'edit', 'step-high', '--model=bb/m2', '--dry-run', '--json']);
    const editFull = await api.preview('profile.edit', { profile: 'step-high', runtime: 'claude-code', model: 'bb/m2', thinking: 'low', credential_env: ['A_KEY'] });
    expect(editFull.body.data!.command).toEqual([
      'config', 'profile', 'edit', 'step-high', '--runtime=claude-code', '--model=bb/m2', '--thinking=low', '--credential-env=A_KEY', '--dry-run', '--json',
    ]);
  });

  it('执行命令带 --expect-state=<state>；号与参数都对才 200', async () => {
    window.location.hash = '#/roles?write=ok';
    const conf = (await api.preview('profile.add', ADD_FULL)).body.data!.confirmation;
    const run = await api.addProfile(ADD_FULL, conf);
    expect(run.status).toBe(200);
    expect(run.body.ok).toBe(true);
    expect(run.body.exit_code).toBe(0);
    expect(run.body.command).toEqual([
      'config', 'profile', 'add', 'gate-new', '--runtime=pi', '--model=bb/m1',
      '--thinking=high', '--credential-env=AAA_KEY', '--credential-env=BBB_KEY', '--expect-state=<state>',
    ]);
    const confEdit = (await api.preview('profile.edit', { profile: 'step-high', model: 'bb/m2' })).body.data!.confirmation;
    const edit = await api.editProfile({ profile: 'step-high', model: 'bb/m2' }, confEdit);
    expect(edit.status).toBe(200);
    expect(edit.body.command).toEqual(['config', 'profile', 'edit', 'step-high', '--model=bb/m2', '--expect-state=<state>']);
  });
});

describe('T024 确认号与参数核对：数组按顺序逐项比（D02、D03）', () => {
  it('号不存在、对象错、action 不符、数组顺序错、丢项、多了项都 409 且 exit_code 为 null', async () => {
    window.location.hash = '#/roles?write=ok';
    const conf = (await api.preview('profile.add', ADD_FULL)).body.data!.confirmation;
    const wrongs = [
      ['顺序错', await api.addProfile({ ...ADD_FULL, credential_env: ['BBB_KEY', 'AAA_KEY'] }, conf)],
      ['丢项', await api.addProfile({ ...ADD_FULL, credential_env: ['AAA_KEY'] }, conf)],
      ['多了项', await api.addProfile({ ...ADD_FULL, credential_env: ['AAA_KEY', 'BBB_KEY', 'CCC_KEY'] }, conf)],
      ['对象错', await api.addProfile({ ...ADD_FULL, profile: 'other' }, conf)],
      ['action 不符', await api.editProfile({ profile: 'gate-new' }, conf)],
      ['号不存在', await api.editProfile({ profile: 'gate-new' }, 'x'.repeat(43))],
    ] as const;
    for (const [why, w] of wrongs) {
      expect(w.status, `${why} 应 409`).toBe(409);
      expect(w.body.exit_code, `${why} 的 exit_code 应为 null`).toBe(null);
    }
    expect(wrongs[0][1].body.messages).toEqual(['ERROR 确认号无效、已过期或已用过：请重新预览']);
  });
});

describe('T024 两个新 ?write= 情景（D07）', () => {
  it('preview-warn：预览 200 ok、warnings 一行（有 model 点名称、没有写「模型不在」）；执行与终态照 ok', async () => {
    window.location.hash = '#/roles?write=preview-warn';
    const pv = await api.preview('profile.add', ADD_MIN);
    expect(pv.status).toBe(200);
    expect(pv.body.ok).toBe(true);
    expect(pv.body.data!.warnings).toEqual(['WARN: 模型 bb/m 不在 pi --list-models 的列表里']);
    const pu = await api.preview('preset.use', { name: 'economy' });
    expect(pu.body.data!.warnings).toEqual(['WARN: 模型不在 pi --list-models 的列表里']);
    const run = await api.addProfile(ADD_MIN, pv.body.data!.confirmation);
    expect(run.status).toBe(200);
    expect(run.body.ok).toBe(true);
    expect(run.body.exit_code).toBe(0);
    const op = await api.getOperation(pv.body.data!.confirmation);
    expect(op.status).toBe(200);
    expect(op.body.data!.state).toBe('succeeded');
  });

  it('preview-invalid：预览 400、ok:false、exit_code:null、data:null、messages 一行；执行与终态照 ok', async () => {
    window.location.hash = '#/roles?write=preview-invalid';
    const pv = await api.preview('profile.add', { profile: 'p9', runtime: 'pi', model: 'bad' });
    expect(pv.status).toBe(400);
    expect(pv.body.ok).toBe(false);
    expect(pv.body.exit_code).toBe(null);
    expect(pv.body.data).toBe(null);
    expect(pv.body.messages).toEqual(['ERROR: model 不合法']);
    // 预览 400 不签确认号；「执行与终态照 ok」用 ok 情景预签的号换情景后执行。
    window.location.hash = '#/roles?write=ok';
    const conf = (await api.preview('profile.add', { profile: 'p9', runtime: 'pi', model: 'bad' })).body.data!.confirmation;
    window.location.hash = '#/roles?write=preview-invalid';
    const run = await api.addProfile({ profile: 'p9', runtime: 'pi', model: 'bad' }, conf);
    expect(run.status).toBe(200);
    expect(run.body.ok).toBe(true);
    const op = await api.getOperation(conf);
    expect(op.status).toBe(200);
    expect(op.body.data!.state).toBe('succeeded');
  });
});

describe('T024 profileSnapshot 投影（D11）', () => {
  it('只比 profiles[].{id,runtime,provider,model,options.thinking,credential_env}；adapter 与多余字段变了仍相同', () => {
    const p = (id: string, over: Record<string, unknown> = {}) => ({
      id, runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'm1', options: { thinking: 'high' }, credential_env: ['S'], ...over,
    });
    const a = { profiles: [p('a'), p('b', { model: 'm2', credential_env: [] })] };
    const b = { profiles: [p('b', { model: 'm2', credential_env: [], adapter: 'zz', notes: 'x' }), p('a', { adapter: 'other', extra: 1 })] };
    expect(sameSnapshot(profileSnapshot(a as never), profileSnapshot(b as never)), '排除字段变了、顺序颠倒仍相同').toBe(true);
    expect(sameSnapshot(profileSnapshot(a as never), profileSnapshot({ profiles: [p('a', { model: 'CHANGED' }), p('b', { model: 'm2', credential_env: [] })] } as never)), 'model 变了应不同').toBe(false);
    expect(sameSnapshot(profileSnapshot(a as never), profileSnapshot({ profiles: [p('a', { options: {} }), p('b', { model: 'm2', credential_env: [] })] } as never)), 'thinking 缺省（null）与 high 应不同').toBe(false);
    expect(sameSnapshot(profileSnapshot(a as never), profileSnapshot({ profiles: [p('a', { credential_env: ['S', 'T'] }), p('b', { model: 'm2', credential_env: [] })] } as never)), 'credential_env 变了应不同').toBe(false);
  });
});
