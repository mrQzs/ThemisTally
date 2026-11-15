// T041 api 与 mock 的自测（合同第 10 节；D01、D02、D04）：addRuntime 真实模式的路径/正文/时限
// （命令留空与空数组都不带 command 键）、桩模式预览命令与服务 buildWriteArgv 逐字一致（带 --dry-run --json）、
// resources 两态、执行命令带 --expect-state、确认号或参数不符回 409、preview-registered 情景的原文与退出码。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import * as api from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import type { Envelope } from '../src/api';

type PostCall = { path: string; body: unknown; timeoutSeconds: number | undefined };
const posts: PostCall[] = [];

const fakeClient: LiveClient = {
  get<T>(): Promise<Envelope<T>> {
    return Promise.resolve({
      ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0,
    }) as Promise<Envelope<T>>;
  },
  post<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body, timeoutSeconds });
    return Promise.resolve({
      status: 200,
      body: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 },
    }) as { status: number; body: Envelope<T> };
  },
  getRaw<T>(): Promise<{ status: number; body: T }> {
    return Promise.resolve({ status: 404, body: null as T });
  },
};

beforeEach(() => {
  posts.length = 0;
  window.location.hash = '';
  setLiveClientForTests(undefined);
});
afterEach(() => {
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('T041 api：addRuntime 真实模式（D01）', () => {
  beforeEach(() => {
    setLiveClientForTests(fakeClient);
  });

  it('POST /api/v1/runtimes/<id>/add，正文带 adapter 与 confirmation，时限 90 秒', async () => {
    await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs' }, 'c-1');
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/runtimes/demo-run/add');
    expect(posts[0].body).toEqual({ adapter: 'quizs', confirmation: 'c-1' });
    expect(posts[0].timeoutSeconds).toBe(90);
  });

  it('命令按字符串数组原样传；留空与空数组都不带 command 键（路径段照旧编码）', async () => {
    await api.addRuntime({ runtime: 'demo-run', adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'] }, 'c-2');
    await api.addRuntime({ runtime: 'demo-run', adapter: 'pi', command: [] }, 'c-3');
    await api.addRuntime({ runtime: 'a b/c', adapter: 'pi' }, 'c-4');
    expect(posts.length).toBe(3);
    expect(posts[0].body).toEqual({ adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'], confirmation: 'c-2' });
    expect(posts[1].body, '空数组的 command 会被去掉（writeArgs 的规则）').toEqual({ adapter: 'pi', confirmation: 'c-3' });
    expect(posts[2].path).toBe('/api/v1/runtimes/a%20b%2Fc/add');
    expect(posts[2].body).toEqual({ adapter: 'pi', confirmation: 'c-4' });
  });
});

describe('T041 桩模式：命令行与服务 buildWriteArgv 逐字一致（D01、D02）', () => {
  it('预览命令带 --dry-run --json；--command=JSON.stringify 无空格；resources 不带命令 [config]、带命令 [config,local]', async () => {
    window.location.hash = '#/runtimes?write=ok';
    const r = await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'quizs' });
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(r.body.data!.command).toEqual(['config', 'runtime', 'add', 'demo-run', '--adapter=quizs', '--dry-run', '--json']);
    expect(r.body.data!.resources).toEqual(['config']);
    expect(r.body.data!.binding_changes).toEqual([]);
    expect((r.body.data!.confirmation as string).length).toBe(43);
    const withCmd = await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'] });
    expect(withCmd.body.data!.command).toEqual([
      'config', 'runtime', 'add', 'demo-run', '--adapter=pi', '--command=["C:/tools/pi.exe","--flag"]', '--dry-run', '--json',
    ]);
    expect(withCmd.body.data!.resources).toEqual(['config', 'local']);
  });

  it('执行命令带 --expect-state=<state>；号或参数不符回 409；空数组命令与「预览没带」等价', async () => {
    window.location.hash = '#/runtimes?write=ok';
    const conf = (await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'quizs' })).body.data!.confirmation;
    const run = await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs' }, conf);
    expect(run.status).toBe(200);
    expect(run.body.ok).toBe(true);
    expect(run.body.command).toEqual(['config', 'runtime', 'add', 'demo-run', '--adapter=quizs', '--expect-state=<state>']);
    const same = await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs', command: [] }, conf);
    expect(same.status, '空数组命令整理后与「没带」等价，确认号应匹配').toBe(200);
    const badConf = await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs' }, 'x'.repeat(43));
    expect(badConf.status).toBe(409);
    expect(badConf.body.exit_code).toBe(null);
    expect(badConf.body.messages).toEqual(['ERROR 确认号无效、已过期或已用过：请重新预览']);
    const badArgs = await api.addRuntime({ runtime: 'demo-run', adapter: 'codex' }, conf);
    expect(badArgs.status, '参数不符也回 409').toBe(409);
  });
});

describe('T041 preview-registered 情景：同一个 id 已登记为别的适配器（D03）', () => {
  it('预览 200、ok 假、退出码 1、data null、一行内核原文，不发确认号；执行一律 409', async () => {
    window.location.hash = '#/runtimes?write=preview-registered';
    const r = await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'pi' });
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(false);
    expect(r.body.exit_code).toBe(1);
    expect(r.body.data).toBe(null);
    expect(r.body.messages.length).toBe(1);
    expect(r.body.messages[0]).toMatch(/^ERROR: runtime demo-run 已登记为 [a-z-]+；改 adapter 要加 --force$/);
    const run = await api.addRuntime({ runtime: 'demo-run', adapter: 'pi' }, 'y'.repeat(43));
    expect(run.status, '没有签发确认号，执行一律 409').toBe(409);
  });
});
