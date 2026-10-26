// 只读数据层：第 9 节有示例的 13 个读函数，返回 Promise<信封>。夹具来自 src/mock/*.json，
// 行为由 ?mock= 开关决定（src/mock/scenario.ts）。本片不接本机服务：运行时不发任何网络请求
// （见 tests/shell-no-network.test.ts）。第 9 节没有示例的读函数、写函数、作业与 SSE 由后面的片按需补。
import metaJson from './mock/meta.json';
import statusJson from './mock/status.json';
import attemptJson from './mock/attempt.json';
import fileReportJson from './mock/file-executor-report.json';
import fileEventsJson from './mock/file-events.json';
import rolesJson from './mock/roles.json';
import profilesJson from './mock/profiles.json';
import presetsJson from './mock/presets.json';
import presetDiffJson from './mock/preset-diff.json';
import runtimesJson from './mock/runtimes.json';
import pluginsJson from './mock/plugins.json';
import historyJson from './mock/history.json';
import usageJson from './mock/usage.json';
import secretsJson from './mock/secrets.json';
import { currentMock, type MockMode } from './mock/scenario';
import {
  EMPTY_STATUS,
  EMPTY_RUNTIMES,
  EMPTY_SECRETS,
  EMPTY_PLUGINS,
  EMPTY_HISTORY,
} from './mock/empty';
import {
  mockGetOperation,
  mockPreview,
  mockSetPluginEnabled,
  mockUsePreset,
} from './mock/writes';

// 信封（UI 文档 8.9 :1093–1095）：ok、exit_code、data、output、messages、command、elapsed_ms。
// exit_code 放宽成 number | null：超时（504）等信封的退出码是 null（照 ts/packages/ui 的 timeoutEnvelope）。
export interface Envelope<T> {
  ok: boolean;
  exit_code: number | null;
  data: T | null;
  output: string[];
  messages: string[];
  command: string[];
  elapsed_ms: number;
}

// A 片三个写动作（B 片的删除、回滚不在此列）。
export type WriteAction = 'preset.use' | 'plugin.enable' | 'plugin.disable';

// 一次 HTTP 式响应：状态码加七字段信封（写路由不回 data，data 恒 null；预览回 PreviewData）。
export interface HttpReply<T> {
  status: number;
  body: Envelope<T>;
}

// 预览里的一条角色绑定变化（演示用的简化形状，照 UI 文档 7.11 的变化行）。
export interface BindingChange {
  role: string;
  from: string;
  to: string;
}

// 预览数据（POST /api/v1/preview 的 data）：command 是 README :83–95 的预览写法（带 --dry-run --json）。
export interface PreviewData {
  binding_changes: BindingChange[];
  resources: string[];
  notes: string[];
  warnings: string[];
  running_attempts: string[];
  needs_yes: boolean;
  command: string[];
  confirmation: string;
}

// 操作记录暴露给界面的八键投影（照 ts/packages/ui/src/operations.ts 的 operationView，八键一个不能少）。
export interface OperationView {
  id: string;
  action: string;
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'stale' | 'timed_out';
  reason: string | null;
  created_ms: number;
  started_ms: number | null;
  finished_ms: number | null;
  envelope: Envelope<null> | null;
}

export type MetaData = typeof metaJson;
export type StatusRow = (typeof statusJson)[number];
export type StatusData = StatusRow[];
export type AttemptData = typeof attemptJson;
export type FileData = typeof fileReportJson | typeof fileEventsJson;
export type RolesData = typeof rolesJson;
export type ProfilesData = typeof profilesJson;
export type PresetsData = typeof presetsJson;
export type PresetDiffData = typeof presetDiffJson;
export type RuntimesData = typeof runtimesJson;
export type PluginsData = typeof pluginsJson;
export type HistoryData = typeof historyJson;
export type UsageData = typeof usageJson;
export type SecretsData = typeof secretsJson;

// error 开关的报错原文（Main 画布 :237–238）。
const ERROR_MESSAGE = 'ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied';

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function okEnvelope<T>(command: string[], data: T): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

function missingEnvelope(command: string[], detail: string): Envelope<never> {
  return {
    ok: false,
    exit_code: 2,
    data: null,
    output: [],
    messages: [`ERROR 夹具里没有这份数据：${detail}`],
    command,
    elapsed_ms: 0,
  };
}

function errorEnvelope<T>(command: string[]): Envelope<T> {
  return { ok: false, exit_code: 2, data: null, output: [], messages: [ERROR_MESSAGE], command, elapsed_ms: 0 };
}

// loading：永不兑现的 Promise，不用计时器（假计时器下也拿不到结果）。
function pending<T>(): Promise<Envelope<T>> {
  return new Promise<Envelope<T>>(() => {});
}

// loading / error 两个开关先于参数校验：整次请求挂起或内核报错，与参数是否在夹具里无关。
// 返回 data 模式（含 offline、empty）下 produce 给出的信封；已兑现的 Promise，不用计时器。
function read<T>(command: string[], produce: (mode: MockMode) => Envelope<T>): Promise<Envelope<T>> {
  const mode = currentMock();
  if (mode === 'loading') return pending();
  if (mode === 'error') return Promise.resolve(errorEnvelope<T>(command));
  return Promise.resolve(produce(mode));
}

export function getMeta(): Promise<Envelope<MetaData>> {
  // getMeta 不受开关影响：任何 ?mock= 下都返回 meta 夹具。
  return Promise.resolve(okEnvelope(['--version'], getMetaNow()));
}

// getMeta 的同步版本：meta 不受开关影响、恒为夹具，外壳常驻件（仓库名、kit 版本）首屏就要用到，
// 不希望等一个微任务。设置页仍走异步的 getMeta（走 PageFrame 的五态）。
export function getMetaNow(): MetaData {
  return clone(metaJson);
}

export function getStatus(): Promise<Envelope<StatusData>> {
  return read(['status'], (mode) =>
    okEnvelope(['status'], mode === 'empty' ? clone(EMPTY_STATUS) : clone(statusJson)),
  );
}

export function getAttempt(task: string, attempt: string): Promise<Envelope<AttemptData>> {
  const command = ['logs', 'show', `${task}/${attempt}`];
  return read(command, () =>
    task === 'logs-cat' && attempt === 'attempt-002'
      ? okEnvelope(command, clone(attemptJson))
      : missingEnvelope(command, `${task}/${attempt}`),
  );
}

export function readFile(
  task: string,
  attempt: string,
  path: string,
  cursor?: string,
): Promise<Envelope<FileData>> {
  const command = ['logs', 'cat', `${task}/${attempt}`, path];
  return read<FileData>(command, () => {
    if (cursor != null) return missingEnvelope(command, `${task}/${attempt}/${path}（带 cursor）`);
    if (task !== 'logs-cat' || attempt !== 'attempt-002') {
      return missingEnvelope(command, `${task}/${attempt}/${path}`);
    }
    if (path === 'executor-report.md') return okEnvelope(command, clone(fileReportJson));
    if (path === 'events.jsonl') return okEnvelope(command, clone(fileEventsJson));
    return missingEnvelope(command, `${task}/${attempt}/${path}`);
  });
}

export function getRoles(): Promise<Envelope<RolesData>> {
  return read(['config', 'role', 'show'], () => okEnvelope(['config', 'role', 'show'], clone(rolesJson)));
}

export function getProfiles(): Promise<Envelope<ProfilesData>> {
  return read(['config', 'profile', 'show'], () =>
    okEnvelope(['config', 'profile', 'show'], clone(profilesJson)),
  );
}

export function getPresets(): Promise<Envelope<PresetsData>> {
  return read(['config', 'preset', 'list'], () =>
    okEnvelope(['config', 'preset', 'list'], clone(presetsJson)),
  );
}

export function diffPresets(a: string, b: string): Promise<Envelope<PresetDiffData>> {
  const command = ['config', 'preset', 'diff', a, b];
  return read(command, () =>
    a === 'default' && b === 'economy'
      ? okEnvelope(command, clone(presetDiffJson))
      : missingEnvelope(command, `${a} → ${b}`),
  );
}

export function getRuntimes(): Promise<Envelope<RuntimesData>> {
  return read(['config', 'runtime', 'list'], (mode) =>
    okEnvelope(['config', 'runtime', 'list'], mode === 'empty' ? clone(EMPTY_RUNTIMES) : clone(runtimesJson)),
  );
}

export function getPlugins(): Promise<Envelope<PluginsData>> {
  return read(['plugins', 'list'], (mode) =>
    okEnvelope(['plugins', 'list'], mode === 'empty' ? clone(EMPTY_PLUGINS) : clone(pluginsJson)),
  );
}

export function getHistory(): Promise<Envelope<HistoryData>> {
  return read(['config', 'history'], (mode) =>
    okEnvelope(['config', 'history'], mode === 'empty' ? clone(EMPTY_HISTORY) : clone(historyJson)),
  );
}

export function getUsage(): Promise<Envelope<UsageData>> {
  return read(['logs', 'usage'], () => okEnvelope(['logs', 'usage'], clone(usageJson)));
}

export function listSecrets(): Promise<Envelope<SecretsData>> {
  return read(['config', 'show'], (mode) =>
    okEnvelope(['config', 'show'], mode === 'empty' ? clone(EMPTY_SECRETS) : clone(secretsJson)),
  );
}

// A 片四个写函数：预览、查操作、用方案、启停插件。演示数据由 mock/writes.ts 按 ?write= 情景生成，不联网。
// B 片的 removePreset/removeProfile/removeRuntime/rollback 不在此列（不放桩、不接界面）。
export function preview(action: WriteAction, args: Record<string, string>): Promise<HttpReply<PreviewData>> {
  return mockPreview(action, args);
}

export function getOperation(id: string): Promise<HttpReply<OperationView>> {
  return mockGetOperation(id);
}

export function usePreset(name: string, confirmation: string): Promise<HttpReply<null>> {
  return mockUsePreset(name, confirmation);
}

export function setPluginEnabled(id: string, enabled: boolean, confirmation: string): Promise<HttpReply<null>> {
  return mockSetPluginEnabled(id, enabled, confirmation);
}
