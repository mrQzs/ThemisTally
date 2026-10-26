// 写操作的演示数据（A 片）：不联网，全部由 location.hash 里的 ?write= 情景决定（独立于 ?mock=，缺省或认不出按 ok）。
// 四个函数的信封与状态码照 ts/packages/ui 的写路由语义给出（第二节那张表逐行实现）；所有 Promise 都已兑现，
// 不用计时器（drop-* 的连接中断靠流程自己的轮询计时器推进）。
import type { Envelope, HttpReply, OperationView, PreviewData, WriteAction } from '../api';

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
  | 'reread-fail-exit1';

const SCENARIOS: readonly WriteScenario[] = [
  'ok', 'warn', 'exit1', 'exit2', 'exit3', 'stale', 'expired', 'busy', 'closing', 'spawn', 'toolarge', 'timeout',
  'drop-done', 'drop-lost', 'drop-hang', 'preview-fail', 'preview-busy', 'reread-fail', 'reread-fail-exit1',
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

// 基础写 argv（不含 --expect-state、--yes、--dry-run、--json）：照 README :83–95 的 12 条写路由。
function baseArgv(action: WriteAction, args: Record<string, string>): string[] {
  if (action === 'preset.use') return ['config', 'preset', 'use', args.name];
  if (action === 'plugin.enable') return ['plugins', 'enable', args.id];
  return ['plugins', 'disable', args.id];
}

// 执行时起的命令行：基础 argv 加 --expect-state=<state>（演示里 needs_yes 恒假，不加 --yes，不带 --json）。
function writeArgv(action: WriteAction, args: Record<string, string>): string[] {
  return [...baseArgv(action, args), '--expect-state=<state>'];
}

function env<T>(over: Partial<Envelope<T>>): Envelope<T> {
  return { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0, ...over } as Envelope<T>;
}

// 每个预览签发一个不重复的确认号（43 位量级；流程把它当操作号用，drop-* 的轮询按它记次数）。
let opSeq = 0;
const opActions = new Map<string, string>();
const opPolls = new Map<string, number>();

function newOpId(action: string): string {
  opSeq += 1;
  const id = `op${opSeq}${'y'.repeat(40)}`.slice(0, 43);
  opActions.set(id, action);
  return id;
}

function previewData(action: WriteAction, args: Record<string, string>, confirmation: string): PreviewData {
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

export function mockPreview(action: WriteAction, args: Record<string, string>): Promise<HttpReply<PreviewData>> {
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
  const id = newOpId(action);
  return Promise.resolve({
    status: 200,
    body: { ok: true, exit_code: 0, data: previewData(action, args, id), output: [], messages: [], command, elapsed_ms: 0 },
  });
}

// 执行响应：第二节「执行」列。drop-* 由写函数直接抛错，不在这里。
function executeEnvelope(scenario: WriteScenario, action: WriteAction, args: Record<string, string>): Envelope<null> {
  const command = writeArgv(action, args);
  switch (scenario) {
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

function executeReply(scenario: WriteScenario, action: WriteAction, args: Record<string, string>): HttpReply<null> {
  return { status: executeStatus(scenario), body: executeEnvelope(scenario, action, args) };
}

function writeCall(scenario: WriteScenario, action: WriteAction, args: Record<string, string>): Promise<HttpReply<null>> {
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

// 操作终态的信封：连接中断后由 getOperation 查到，照当时会跑完的信封给出（WARN/ERROR 照常显示）。
function terminalEnvelope(scenario: WriteScenario, action: WriteAction, args: Record<string, string>): Envelope<null> | null {
  switch (scenario) {
    case 'ok':
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
  const args: Record<string, string> = action === 'preset.use' ? { name: 'economy' } : { id: 'code-change' };
  switch (scenario) {
    case 'ok':
    case 'warn':
      return Promise.resolve(ok(opView(id, { state: 'succeeded', finished_ms: 5, envelope: terminalEnvelope(scenario, action, args) })));
    case 'exit1':
    case 'exit2':
    case 'exit3':
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
