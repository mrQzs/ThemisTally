// 写操作的演示数据（A 片）：不联网，全部由 location.hash 里的 ?write= 情景决定（独立于 ?mock=，缺省或认不出按 ok）。
// 四个函数的信封与状态码照 ts/packages/ui 的写路由语义给出（第二节那张表逐行实现）；所有 Promise 都已兑现，
// 不用计时器（drop-* 的连接中断靠流程自己的轮询计时器推进）。
import type { Envelope, HttpReply, OperationView, PreviewData, WriteAction, WriteArgs } from '../api';

export type WriteScenario =
  | 'ok'
  | 'warn'
  | 'exit1'
  | 'exit2'
  | 'exit3'
  | 'stale'
  | 'expired'
  | 'busy'
  | 'closing'
  | 'spawn'
  | 'toolarge'
  | 'timeout'
  | 'drop-done'
  | 'drop-lost'
  | 'drop-hang'
  | 'preview-fail'
  | 'preview-busy'
  | 'reread-fail'
  | 'reread-fail-exit1'
  | 'in-use'
  | 'preview-warn'
  | 'preview-invalid';

const SCENARIOS: readonly WriteScenario[] = [
  'ok', 'warn', 'exit1', 'exit2', 'exit3', 'stale', 'expired', 'busy', 'closing', 'spawn', 'toolarge', 'timeout',
  'drop-done', 'drop-lost', 'drop-hang', 'preview-fail', 'preview-busy', 'reread-fail', 'reread-fail-exit1', 'in-use',
  'preview-warn', 'preview-invalid',
];

export function writeScenario(): WriteScenario {
  const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
  const q = hash.indexOf('?');
  if (q < 0) return 'ok';
  const query = hash.slice(q + 1);
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    if (part.slice(0, eq) !== 'write') continue;
    const value = part.slice(eq + 1) as WriteScenario;
    if (SCENARIOS.includes(value)) return value;
  }
  return 'ok';
}

// credential_env 之类的数组参数：缺省（没传这个键）算空数组；按顺序原样展开，不拼成字符串。
function asStringArray(value: string | string[] | undefined): string[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

// 基础写 argv（不含 --expect-state、--yes、--dry-run、--json）：照 README :83–95 的写路由与服务侧 buildWriteArgv。
function baseArgv(action: WriteAction, args: WriteArgs): string[] {
  const s = args as Record<string, string>;
  if (action === 'preset.use') return ['config', 'preset', 'use', s.name];
  if (action === 'preset.remove') return ['config', 'preset', 'remove', s.name];
  if (action === 'profile.remove') return ['config', 'profile', 'remove', s.profile];
  if (action === 'runtime.remove') return ['config', 'runtime', 'remove', s.runtime];
  if (action === 'config.rollback') return ['config', 'rollback', s.number];
  if (action === 'plugin.enable') return ['plugins', 'enable', s.id];
  if (action === 'plugin.disable') return ['plugins', 'disable', s.id];
  if (action === 'profile.add') {
    const out = ['config', 'profile', 'add', s.profile, '--runtime=' + s.runtime, '--model=' + s.model];
    if (s.thinking) out.push('--thinking=' + s.thinking);
    for (const name of asStringArray(args.credential_env)) out.push('--credential-env=' + name);
    return out;
  }
  // profile.edit：runtime/model/thinking 传了才加对应的 --opt=值；--credential-env 一项一个，按数组顺序。
  const out = ['config', 'profile', 'edit', s.profile];
  if (s.runtime) out.push('--runtime=' + s.runtime);
  if (s.model) out.push('--model=' + s.model);
  if (s.thinking) out.push('--thinking=' + s.thinking);
  for (const name of asStringArray(args.credential_env)) out.push('--credential-env=' + name);
  return out;
}

// 执行时起的命令行：基础 argv 加 --expect-state=<state>（演示里 needs_yes 恒假，不加 --yes，不带 --json）。
function writeArgv(action: WriteAction, args: WriteArgs): string[] {
  return [...baseArgv(action, args), '--expect-state=<state>'];
}

function env<T>(over: Partial<Envelope<T>>): Envelope<T> {
  return { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0, ...over } as Envelope<T>;
}

// 每个预览签发一个不重复的确认号（43 位量级；流程把它当操作号用，drop-* 的轮询按它记次数）。
// opActions 记全部 action（A 片 getOperation 按它反推 args 用）；opArgs 只记 B 片四个新 action 的 (action, args)，
// 供 B 片写函数核对确认号与参数（第二节）。
let opSeq = 0;
const opActions = new Map<string, string>();
const opArgs = new Map<string, { action: string; args: WriteArgs }>();
const opPolls = new Map<string, number>();

// B 片四个删除/回滚加本片两个 profile 写动作：opArgs 记下它们的 (action, args)，供写函数核对确认号与参数（第二节）。
const NEW_ACTIONS = new Set<string>(['preset.remove', 'profile.remove', 'runtime.remove', 'config.rollback', 'profile.add', 'profile.edit']);

function newOpId(action: string, args: WriteArgs): string {
  opSeq += 1;
  const id = `op${opSeq}${'y'.repeat(40)}`.slice(0, 43);
  opActions.set(id, action);
  if (NEW_ACTIONS.has(action)) opArgs.set(id, { action, args });
  return id;
}

function previewData(action: WriteAction, args: WriteArgs, confirmation: string): PreviewData {
  // 预览命令照 README :83–95：基础 argv 加 --dry-run --json（对话框的「将运行的命令」另去掉这两个开关）。
  const command = [...baseArgv(action, args), '--dry-run', '--json'];
  if (action === 'preset.use') {
    return {
      binding_changes: [{ role: 'execution', from: 'step-high', to: 'step-low' }],
      resources: ['roles'],
      notes: [],
      warnings: [],
      running_attempts: [],
      needs_yes: false,
      command,
      confirmation,
    };
  }
  if (action === 'config.rollback') {
    // 夹具里最新一条（#42）时绑定不变（空）；其余编号给一条演示变化。
    return {
      binding_changes: args.number === '42' ? [] : [{ role: 'execution', from: 'step-low', to: 'step-high' }],
      resources: ['config'],
      notes: [],
      warnings: [],
      running_attempts: [],
      needs_yes: false,
      command,
      confirmation,
    };
  }
  if (action === 'profile.add' || action === 'profile.edit') {
    // 两个 profile 写动作：binding_changes 恒空（改动靠变化区摘要说明）；WARN 由 preview-warn 情景注入。
    return {
      binding_changes: [],
      resources: ['profiles'],
      notes: [],
      warnings: [],
      running_attempts: [],
      needs_yes: false,
      command,
      confirmation,
    };
  }
  // 三个删除与插件启停：binding_changes 恒空（删除靠变化区摘要说明）。
  return {
    binding_changes: [],
    resources: ['plugins'],
    notes: [],
    warnings: [],
    running_attempts: [],
    needs_yes: false,
    command,
    confirmation,
  };
}

export function mockPreview(action: WriteAction, args: WriteArgs): Promise<HttpReply<PreviewData>> {
  const scenario = writeScenario();
  const command = [...baseArgv(action, args), '--dry-run', '--json'];
  if (scenario === 'preview-busy') {
    return Promise.resolve({
      status: 503,
      body: env({ ok: false, exit_code: null, messages: ['ERROR 服务繁忙，请稍后重试'], command }),
    });
  }
  if (scenario === 'preview-fail') {
    return Promise.resolve({
      status: 200,
      body: env({ ok: false, exit_code: 2, messages: ['ERROR 预览不合格：参数不符合组合规则'], command }),
    });
  }
  if (scenario === 'preview-invalid') {
    // 预览就不合法：400、ok:false、退出码 null、无 data、一行内核原文（界面在表单底部显示这行并禁用 [确认…]）。
    return Promise.resolve({
      status: 400,
      body: env<PreviewData>({ ok: false, exit_code: null, data: null, messages: ['ERROR: model 不合法'], command }),
    });
  }
  const id = newOpId(action, args);
  const data = previewData(action, args, id);
  if (scenario === 'preview-warn') {
    // 预览带一行 WARN：有 model 时点名叫模型，没有 model 时写「模型不在」；执行与终态照 ok（成功）。
    const model = typeof args.model === 'string' && args.model ? args.model : null;
    data.warnings = [model ? `WARN: 模型 ${model} 不在 pi --list-models 的列表里` : 'WARN: 模型不在 pi --list-models 的列表里'];
  }
  return Promise.resolve({
    status: 200,
    body: { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 },
  });
}

// in-use 的内核原文（合同第五节）：三个删除各有原文；config.rollback 与 A 片 action 照 exit1 的报错行。
function inUseMessage(action: WriteAction, args: WriteArgs): string {
  const s = args as Record<string, string>;
  if (action === 'preset.remove') {
    return `ERROR: 方案 ${s.name} 正在用：先 preset use 别的方案，或 config unset active_preset`;
  }
  if (action === 'profile.remove') {
    return `ERROR: profile ${s.profile} 被 roles.execution 引用：先改这些绑定或方案`;
  }
  if (action === 'runtime.remove') {
    return `ERROR: runtime ${s.runtime} 被 profile step-high、step-low 引用：先改或删这些 profile`;
  }
  return 'ERROR 内核拒绝：profile step-low 不存在';
}

// 执行响应：第二节「执行」列。drop-* 由写函数直接抛错，不在这里。
function executeEnvelope(scenario: WriteScenario, action: WriteAction, args: WriteArgs): Envelope<null> {
  const command = writeArgv(action, args);
  switch (scenario) {
    case 'in-use':
      return env({ ok: false, exit_code: 1, messages: [inUseMessage(action, args)], command });
    case 'warn':
      return env({
        output: ['WARN 执行端已固定，切换不影响正在运行的 attempt'],
        messages: ['WARN 有一个 attempt 在运行：ui-readonly-api/attempt-001'],
        command,
      });
    case 'exit1':
      return env({ ok: false, exit_code: 1, messages: ['ERROR 内核拒绝：profile step-low 不存在'], command });
    case 'exit2':
      return env({ ok: false, exit_code: 2, messages: ['ERROR 用法错误：preset use 需要一个方案名'], command });
    case 'exit3':
      return env({ ok: false, exit_code: 3, messages: ['ERROR 内核拒绝：写不进去配置文件'], command });
    case 'reread-fail-exit1':
      // 与 exit1 同一份执行响应（200 ok:false 退出 1），区别在重读：本情景让重读失败。
      return env({ ok: false, exit_code: 1, messages: ['ERROR 内核拒绝：profile step-low 不存在'], command });
    case 'stale':
      return env({ ok: false, exit_code: 4, messages: ['ERROR 在预览之后配置被改动了，请重新预览'], command });
    case 'expired':
      return env({ ok: false, exit_code: null, messages: ['ERROR 确认号无效、已过期或已用过：请重新预览'], command });
    case 'busy':
      return env({ ok: false, exit_code: null, messages: ['ERROR 服务繁忙，请稍后重试'], command });
    case 'closing':
      return env({ ok: false, exit_code: null, messages: ['ERROR 服务正在关闭'], command });
    case 'spawn':
      return env({ ok: false, exit_code: null, messages: ['ERROR 起不了内核子进程'], command });
    case 'toolarge':
      return env({ ok: false, exit_code: null, messages: ['ERROR 内核输出超过上限'], command });
    case 'timeout':
      return env({ ok: false, exit_code: null, messages: ['ERROR: 命令超时（90 秒），子进程已结束；请改用 CLI 查看'], command });
    default:
      return env({ command });
  }
}

function executeStatus(scenario: WriteScenario): number {
  switch (scenario) {
    case 'stale':
    case 'expired':
      return 409;
    case 'busy':
    case 'closing':
      return 503;
    case 'spawn':
    case 'toolarge':
      return 500;
    case 'timeout':
      return 504;
    default:
      return 200;
  }
}

function executeReply(scenario: WriteScenario, action: WriteAction, args: WriteArgs): HttpReply<null> {
  return { status: executeStatus(scenario), body: executeEnvelope(scenario, action, args) };
}

function writeCall(scenario: WriteScenario, action: WriteAction, args: WriteArgs): Promise<HttpReply<null>> {
  if (scenario === 'drop-done' || scenario === 'drop-lost' || scenario === 'drop-hang') {
    return Promise.reject(new Error('连接中断'));
  }
  return Promise.resolve(executeReply(scenario, action, args));
}

export function mockUsePreset(name: string, _confirmation: string): Promise<HttpReply<null>> {
  return writeCall(writeScenario(), 'preset.use', { name });
}

export function mockSetPluginEnabled(id: string, enabled: boolean, _confirmation: string): Promise<HttpReply<null>> {
  return writeCall(writeScenario(), enabled ? 'plugin.enable' : 'plugin.disable', { id });
}

// 确认号与参数核对（第二节）：两个对象的键数相同、逐键相等；值是数组时长度相同且按顺序逐项相等（不把数组拼成字符串再比）。
function sameValue(a: string | string[], b: string | string[]): boolean {
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((v, i) => v === b[i]);
  }
  return a === b;
}

function sameArgs(a: WriteArgs, b: WriteArgs): boolean {
  const ka = Object.keys(a);
  if (ka.length !== Object.keys(b).length) return false;
  return ka.every((k) => sameValue(a[k], b[k]));
}

function confirmWrite(action: WriteAction, args: WriteArgs, confirmation: string): Promise<HttpReply<null>> {
  const stored = opArgs.get(confirmation);
  if (!stored || stored.action !== action || !sameArgs(stored.args, args)) {
    return Promise.resolve({
      status: 409,
      body: env({
        ok: false,
        exit_code: null,
        messages: ['ERROR 确认号无效、已过期或已用过：请重新预览'],
        command: writeArgv(action, args),
      }),
    });
  }
  return writeCall(writeScenario(), action, args);
}

export function mockRemovePreset(name: string, confirmation: string): Promise<HttpReply<null>> {
  return confirmWrite('preset.remove', { name }, confirmation);
}

export function mockRemoveProfile(profile: string, confirmation: string): Promise<HttpReply<null>> {
  return confirmWrite('profile.remove', { profile }, confirmation);
}

export function mockRemoveRuntime(runtime: string, confirmation: string): Promise<HttpReply<null>> {
  return confirmWrite('runtime.remove', { runtime }, confirmation);
}

export function mockRollback(number: number, confirmation: string): Promise<HttpReply<null>> {
  return confirmWrite('config.rollback', { number: String(number) }, confirmation);
}

// 本片两个写函数：把带类型的参数整理成 WriteArgs（credential_env 为空数组时不传这个键），再走同一套确认号与参数核对。
function profileArgs(args: {
  profile: string;
  runtime?: string;
  model?: string;
  thinking?: string;
  credential_env?: string[];
}): WriteArgs {
  const w: WriteArgs = { profile: args.profile };
  if (args.runtime !== undefined) w.runtime = args.runtime;
  if (args.model !== undefined) w.model = args.model;
  if (args.thinking !== undefined) w.thinking = args.thinking;
  if (args.credential_env && args.credential_env.length > 0) w.credential_env = args.credential_env;
  return w;
}

export function mockAddProfile(
  args: { profile: string; runtime: string; model: string; thinking?: string; credential_env?: string[] },
  confirmation: string,
): Promise<HttpReply<null>> {
  return confirmWrite('profile.add', profileArgs(args), confirmation);
}

export function mockEditProfile(
  args: { profile: string; runtime?: string; model?: string; thinking?: string; credential_env?: string[] },
  confirmation: string,
): Promise<HttpReply<null>> {
  return confirmWrite('profile.edit', profileArgs(args), confirmation);
}

// 操作终态的信封：连接中断后由 getOperation 查到，照当时会跑完的信封给出（WARN/ERROR 照常显示）。
function terminalEnvelope(scenario: WriteScenario, action: WriteAction, args: WriteArgs): Envelope<null> | null {
  switch (scenario) {
    case 'ok':
    case 'preview-warn':
    case 'preview-invalid':
      return env({ command: writeArgv(action, args) });
    case 'warn':
      return env({
        output: ['WARN 执行端已固定，切换不影响正在运行的 attempt'],
        messages: ['WARN 有一个 attempt 在运行：ui-readonly-api/attempt-001'],
        command: writeArgv(action, args),
      });
    case 'exit1':
    case 'exit2':
    case 'exit3':
    case 'in-use':
      return executeEnvelope(scenario, action, args);
    case 'stale':
      return executeEnvelope('stale', action, args);
    case 'timeout':
      return executeEnvelope('timeout', action, args);
    case 'closing':
      return executeEnvelope('closing', action, args);
    case 'spawn':
      return executeEnvelope('spawn', action, args);
    case 'toolarge':
      return executeEnvelope('toolarge', action, args);
    default:
      return null;
  }
}

function opView(id: string, over: Partial<OperationView>): OperationView {
  return {
    id,
    action: opActions.get(id) ?? 'preset.use',
    state: 'succeeded',
    reason: null,
    created_ms: 0,
    started_ms: 0,
    finished_ms: 0,
    envelope: null,
    ...over,
  };
}

function notFound(id: string): HttpReply<OperationView> {
  return {
    status: 404,
    body: { ok: false, exit_code: null, data: null, output: [], messages: ['ERROR 没有这个操作'], command: ['operations', id], elapsed_ms: 0 },
  };
}

function ok(view: OperationView): HttpReply<OperationView> {
  return { status: 200, body: { ok: true, exit_code: 0, data: view, output: [], messages: [], command: view.envelope?.command ?? [], elapsed_ms: 0 } };
}

export function mockGetOperation(id: string): Promise<HttpReply<OperationView>> {
  const scenario = writeScenario();
  const action = (opActions.get(id) ?? 'preset.use') as WriteAction;
  // B 片四个新 action 的 args 取自 opArgs（预览时记下）；A 片照旧按 action 反推。
  const args: WriteArgs =
    opArgs.get(id)?.args ?? (action === 'preset.use' ? { name: 'economy' } : { id: 'code-change' });
  switch (scenario) {
    case 'ok':
    case 'warn':
    case 'preview-warn':
    case 'preview-invalid':
      return Promise.resolve(ok(opView(id, { state: 'succeeded', finished_ms: 5, envelope: terminalEnvelope(scenario, action, args) })));
    case 'exit1':
    case 'exit2':
    case 'exit3':
    case 'in-use':
      return Promise.resolve(ok(opView(id, { state: 'failed', reason: 'exit', finished_ms: 5, envelope: terminalEnvelope(scenario, action, args) })));
    case 'stale':
      return Promise.resolve(ok(opView(id, { state: 'stale', finished_ms: 5, envelope: terminalEnvelope('stale', action, args) })));
    case 'timeout':
      return Promise.resolve(ok(opView(id, { state: 'timed_out', finished_ms: 5, envelope: terminalEnvelope('timeout', action, args) })));
    case 'closing':
      return Promise.resolve(ok(opView(id, { state: 'failed', reason: 'closing', finished_ms: 5, envelope: terminalEnvelope('closing', action, args) })));
    case 'spawn':
      return Promise.resolve(ok(opView(id, { state: 'failed', reason: 'spawn-error', finished_ms: 5, envelope: terminalEnvelope('spawn', action, args) })));
    case 'toolarge':
      return Promise.resolve(ok(opView(id, { state: 'failed', reason: 'output-too-large', finished_ms: 5, envelope: terminalEnvelope('toolarge', action, args) })));
    case 'expired':
    case 'busy':
    case 'drop-lost':
      return Promise.resolve(notFound(id));
    case 'drop-done': {
      const n = opPolls.get(id) ?? 0;
      opPolls.set(id, n + 1);
      if (n === 0) {
        return Promise.resolve(ok(opView(id, { state: 'running', started_ms: 1, finished_ms: null, envelope: null })));
      }
      return Promise.resolve(ok(opView(id, { state: 'succeeded', started_ms: 1, finished_ms: 5, envelope: terminalEnvelope('ok', action, args) })));
    }
    case 'drop-hang':
      return Promise.resolve(ok(opView(id, { state: 'running', started_ms: 1, finished_ms: null, envelope: null })));
    default:
      return Promise.resolve(notFound(id));
  }
}
