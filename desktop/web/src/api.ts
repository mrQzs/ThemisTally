// 只读数据层：第 9 节有示例的 13 个读函数，返回 Promise<信封>。夹具来自 src/mock/*.json，
// 行为由 ?mock= 开关决定（src/mock/scenario.ts）。开发服务器与测试环境只走夹具（liveClient() 为 null）；
// 生产构建里同源请求本机服务 /api/v1/…（src/live/ 下的传输层），?mock= 一律不生效。
// 写操作（预览、执行、查终态）在真实模式下走服务的写路由，夹具模式下由 mock/writes.ts 按 ?write= 情景生成。
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
  mockAddProfile,
  mockAddRuntime,
  mockEditProfile,
  mockGetOperation,
  mockPreview,
  mockRemovePreset,
  mockRemoveProfile,
  mockRemoveRuntime,
  mockRollback,
  mockSetHubRole,
  mockSetPluginEnabled,
  mockUnsetHubRole,
  mockUsePreset,
} from './mock/writes';
import { liveClient } from './live/mode';
import { isEnvelope } from './live/transport';
import { HISTORY_ENTRIES, type HistoryEntryData } from './mock/readonly2-history-entries';
import { PLUGIN_SHOWS, type PluginShowData } from './mock/readonly2-plugin-show';
import { HUB_ROLES_POSTS } from './mock/hub-roles';
import { quizsLiveEnvelope, quizsProvidersEnvelope } from './mock/quizs';

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

// 写动作：A 片三个（切换方案、启停插件）、B 片四个（删除方案/profile/运行时、回滚）加本片两个（新建/编辑 profile）、
// 七端岗位两个（hub.set、hub.unset）与本片一个（runtime.add，登记运行时）。
export type WriteAction =
  | 'preset.use'
  | 'plugin.enable'
  | 'plugin.disable'
  | 'preset.remove'
  | 'profile.remove'
  | 'runtime.remove'
  | 'config.rollback'
  | 'profile.add'
  | 'profile.edit'
  | 'hub.set'
  | 'hub.unset'
  | 'runtime.add';

// 写操作的参数：值是字符串或字符串数组（T024 新增；数组按顺序原样传给服务，不拼成字符串）。
export type WriteArgs = Record<string, string | string[]>;

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

// 预览里七端岗位一侧的替补（照 scripts/kit_roles.py 的 hub_side：同六个字段，没有替补时 null）。
export interface HubChangeFallback {
  profile: string | null;
  runtime: string | null;
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
}

// 预览里七端岗位生效绑定的一侧（hub_side）：source 加同六个字段与替补。
export interface HubChangeSide {
  source: 'default' | 'config' | null;
  profile: string | null;
  runtime: string | null;
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  fallback: HubChangeFallback | null;
}

// 预览里一个岗位的前后对比（hub_changes）：前后不同的岗位各一项；一侧为 null 表示内核那一侧读不出来。
export interface HubChange {
  post: string;
  before: HubChangeSide | null;
  after: HubChangeSide | null;
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
  hub_changes: HubChange[];
  running_turns: string[];
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

// 七端岗位（GET /api/v1/hub/roles → config hub show --json）的 data：六行名册。
// 替补的 profile 与 runtime 是可选键：内核缺省行的替补只有 adapter/provider/model/thinking 四个键
// （scripts/kit_roles.py 的 HUB_DEFAULTS），写成必填会让四键字面量过不了 tsc --noEmit；服务缺这些键时按 null 处理。
export interface HubPostFallback {
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  profile?: string | null;
  runtime?: string | null;
}
export interface HubPostRow {
  post: string;
  source: 'default' | 'config';
  allowed_adapters: string[];
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  profile: string | null;
  runtime: string | null;
  fallback: HubPostFallback | null;
}
export interface HubRolesData {
  posts: HubPostRow[];
}

// Quizs 提供方档案一行（GET /api/v1/quizs/providers 的 data.providers[]）：字段只用 T042 白名单登记的
// （provider、model、thinking[*]、billing）；id、build_id 一类键服务不登记，前端拿不到也就不显示。
// 枚举值越界时服务遮成 <redacted>，所以按普通字符串收，不用字面量联合把它挡在类型外。
export interface QuizsProviderRow {
  provider: string | null;
  model: string | null;
  thinking: string[];
  billing: string;
}
export interface QuizsProvidersData {
  providers: QuizsProviderRow[];
}

// Quizs live 一套的状态（data.live[].status）：null 表示这一套读不出状态（不解析 problem 的文字来判定）。
// live_dir、plan.*、issued_at_ms、capabilities 服务未登记，这里一个都不写。
export interface QuizsLiveStatus {
  state: string;
  problem: string | null;
  missing: string[];
  certificate: { expires_at_ms: number | null } | null;
  profile: { valid_until: string | null } | null;
}
export interface QuizsLiveRow {
  source: 'mailbox' | 'env';
  provider: string | null;
  problem: string | null;
  status: QuizsLiveStatus | null;
}
export interface QuizsLiveData {
  live: QuizsLiveRow[];
}

// meta 路由给的是 {version, repo_name}，页面读的是 kit_version（归一化见 toMetaData）。
// version 缺失或不是字符串时按「对不上格式」处理：kit_version 给空串（未知），不猜、也不回夹具。
type MetaServiceData = { version?: string | null; repo_name: string };

// error 开关的报错原文（Main 画布 :237–238）。
const ERROR_MESSAGE = 'ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied';

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function okEnvelope<T>(command: string[], data: T | null): Envelope<T> {
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

// 服务端时限（ts/packages/ui/src/writeroutes.ts：PREVIEW_TIMEOUT = 30、WRITE_TIMEOUT = 90；操作查询照预览的 30 秒）。
const PREVIEW_TIMEOUT_SECONDS = 30;
const OPERATION_TIMEOUT_SECONDS = 30;
const WRITE_TIMEOUT_SECONDS = 90;

// 绑定没有可取的值时显示的占位符。
const DASH = '—';

function textOf(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function asNumber(value: string): string | number {
  const n = Number(value);
  return Number.isFinite(n) ? n : value;
}

// 预览与执行共用的参数整理：值是空串或空数组不传这个键（服务侧都不合法）；number 键转成 JSON 数字
// （转不成原样传，服务回 400）；其余键值原样传，数组按顺序原样传、不拼成字符串。
// 预览与执行必须用同一份规则，否则服务按确认号记的 argv 与这次的 argv 对不上，回 409「参数不符」。
function writeArgs(args: WriteArgs): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(args)) {
    if (Array.isArray(value)) {
      if (value.length > 0) out[key] = value;
      continue;
    }
    if (value === '') continue;
    out[key] = key === 'number' ? asNumber(value) : value;
  }
  return out;
}

function stringsOf(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

// 一条绑定的显示值：profile 非空 → profile；provider 与 model 都非空 → provider/model；只有一个非空 → 那一个；
// 都没有 → mode；再没有 → 占位符。null（绑定原来就没有）同样给占位符。
function displayValue(value: unknown): string {
  if (typeof value !== 'object' || value === null) return DASH;
  const binding = value as Record<string, unknown>;
  const profile = textOf(binding.profile);
  const provider = textOf(binding.provider);
  const model = textOf(binding.model);
  const mode = textOf(binding.mode);
  if (profile !== '') return profile;
  if (provider !== '' && model !== '') return `${provider}/${model}`;
  if (provider !== '') return provider;
  if (model !== '') return model;
  return mode === '' ? DASH : mode;
}

// 替补的六个字段：缺键或类型不对归 null（服务没登记这个键时同样按没有处理）。
function hubFallbackOf(value: unknown): HubChangeFallback | null {
  if (typeof value !== 'object' || value === null) return null;
  const row = value as Record<string, unknown>;
  return {
    profile: textOrNull(row.profile),
    runtime: textOrNull(row.runtime),
    adapter: textOrNull(row.adapter),
    provider: textOrNull(row.provider),
    model: textOrNull(row.model),
    thinking: textOrNull(row.thinking),
  };
}

// 岗位一侧：整侧不是对象 → null；source 不是 default/config → null；六个字段不是字符串 → null。
function hubSideOf(value: unknown): HubChangeSide | null {
  if (typeof value !== 'object' || value === null) return null;
  const row = value as Record<string, unknown>;
  return {
    source: row.source === 'default' || row.source === 'config' ? row.source : null,
    profile: textOrNull(row.profile),
    runtime: textOrNull(row.runtime),
    adapter: textOrNull(row.adapter),
    provider: textOrNull(row.provider),
    model: textOrNull(row.model),
    thinking: textOrNull(row.thinking),
    fallback: hubFallbackOf(row.fallback),
  };
}

// 岗位前后对比一项：post 不是字符串 → 整项跳过（不显示半条）；两侧按 hubSideOf 收。
function hubChangeOf(value: unknown): HubChange | null {
  if (typeof value !== 'object' || value === null) return null;
  const row = value as Record<string, unknown>;
  if (typeof row.post !== 'string') return null;
  return { post: row.post, before: hubSideOf(row.before), after: hubSideOf(row.after) };
}

// 服务的预览 JSON → 前端的 PreviewData：binding_changes 的 {role, before, after} 映射成 {role, from, to}；
// resources 取每项的 resource（按服务给的次序，不去重）；unreadable 并进 notes（前端形状里没有单独的键）；
// hub_changes 逐项映射（post 不是字符串的跳过该项，侧与字段缺键或类型不对归 null）；running_turns 只留字符串项；
// command 取信封顶层（带 --dry-run --json），不取预览 JSON 里的东西。
function toPreviewData(preview: Record<string, unknown>, command: string[], confirmation: string): PreviewData {
  const binding_changes: BindingChange[] = [];
  if (Array.isArray(preview.binding_changes)) {
    for (const item of preview.binding_changes) {
      if (typeof item !== 'object' || item === null) continue;
      const row = item as Record<string, unknown>;
      if (typeof row.role !== 'string') continue;
      binding_changes.push({ role: row.role, from: displayValue(row.before), to: displayValue(row.after) });
    }
  }
  const resources: string[] = [];
  if (Array.isArray(preview.resources)) {
    for (const item of preview.resources) {
      if (typeof item !== 'object' || item === null) continue;
      const resource = textOf((item as Record<string, unknown>).resource);
      if (resource !== '') resources.push(resource);
    }
  }
  const hub_changes: HubChange[] = [];
  if (Array.isArray(preview.hub_changes)) {
    for (const item of preview.hub_changes) {
      const change = hubChangeOf(item);
      if (change !== null) hub_changes.push(change);
    }
  }
  return {
    binding_changes,
    resources,
    notes: [...stringsOf(preview.notes), ...stringsOf(preview.unreadable)],
    warnings: stringsOf(preview.warnings),
    running_attempts: stringsOf(preview.running_attempts),
    needs_yes: preview.needs_yes === true,
    command,
    confirmation,
    hub_changes,
    running_turns: stringsOf(preview.running_turns),
  };
}

// 预览成功（200、ok、data 带 preview 与 confirmation）时映射成 PreviewData，信封其余字段原样保留；
// 缺任何一样（含 data 缺 preview）就原样透传：不签发确认号，状态码与信封都不改。
function mappedPreview(reply: HttpReply<PreviewData>): HttpReply<PreviewData> {
  const data: unknown = reply.body.data;
  if (reply.status !== 200 || !reply.body.ok || typeof data !== 'object' || data === null) return reply;
  const record = data as Record<string, unknown>;
  const preview = record.preview;
  if (typeof record.confirmation !== 'string' || typeof preview !== 'object' || preview === null) return reply;
  return {
    status: reply.status,
    body: {
      ...reply.body,
      data: toPreviewData(preview as Record<string, unknown>, reply.body.command, record.confirmation),
    },
  };
}

// 操作终态的八键投影：envelope 不是合法七字段信封就取 null；正文不是对象或缺 state 时整个视图取 null。
function toOperationView(body: unknown): OperationView | null {
  if (typeof body !== 'object' || body === null) return null;
  const row = body as Record<string, unknown>;
  if (typeof row.state !== 'string') return null;
  return {
    id: textOf(row.id),
    action: textOf(row.action),
    state: row.state as OperationView['state'],
    reason: textOf(row.reason) === '' ? null : textOf(row.reason),
    created_ms: typeof row.created_ms === 'number' ? row.created_ms : 0,
    started_ms: typeof row.started_ms === 'number' ? row.started_ms : null,
    finished_ms: typeof row.finished_ms === 'number' ? row.finished_ms : null,
    envelope: isEnvelope(row.envelope) ? (row.envelope as Envelope<null>) : null,
  };
}

// profile.add / profile.edit 的执行正文：除路径参数 profile 以外的键，过同一份整理规则，再加确认号。
function profileBody(
  args: { runtime?: string; model?: string; thinking?: string; credential_env?: string[] },
  confirmation: string,
): Record<string, unknown> {
  const w: WriteArgs = {};
  if (args.runtime !== undefined) w.runtime = args.runtime;
  if (args.model !== undefined) w.model = args.model;
  if (args.thinking !== undefined) w.thinking = args.thinking;
  if (args.credential_env !== undefined) w.credential_env = args.credential_env;
  return { ...writeArgs(w), confirmation };
}

// meta：version 是内核 --version 的输出（pi_dispatch 2.12.0），去掉前缀才是 kit 版本；对不上格式就原样。
function toMetaData(data: MetaServiceData): MetaData {
  const prefix = 'pi_dispatch ';
  const version = typeof data.version === 'string' ? data.version : null;
  const kit_version = version !== null && version.startsWith(prefix) ? version.slice(prefix.length) : version;
  return { kit_version: kit_version ?? '', repo_name: data.repo_name };
}

// 配置历史一条：配置条目没有 resource（补 'config'）与 diff（补 null），本机文件条目两个都有。
function toHistoryEntryData(data: HistoryEntryData): HistoryEntryData {
  return { ...data, resource: data.resource ?? 'config', diff: data.diff ?? null };
}

// 插件详情：配置里没有 allowed 权限时服务给 null，前端按空列表渲染。
function toPluginShowData(data: PluginShowData): PluginShowData {
  if (data.config == null || data.config.allowed_permissions != null) return data;
  return { ...data, config: { ...data.config, allowed_permissions: [] } };
}

// 真实分支的归一化：读成功了才改形状，服务自己的报错信封原样透传。
function mapped<T, R>(env: Envelope<T>, map: (data: T) => R): Envelope<R> {
  return env.ok && env.data != null ? { ...env, data: map(env.data) } : (env as unknown as Envelope<R>);
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
  const client = liveClient();
  if (client) {
    return client.get<MetaServiceData>('/api/v1/meta', undefined, 15).then((env) => mapped(env, toMetaData));
  }
  // getMeta 不受开关影响：任何 ?mock= 下都返回 meta 夹具。
  return Promise.resolve(okEnvelope(['--version'], getMetaNow()));
}

// getMeta 的同步版本：meta 不受开关影响、恒为夹具，外壳常驻件（仓库名、kit 版本）首屏就要用到，
// 不希望等一个微任务。设置页仍走异步的 getMeta（走 PageFrame 的五态）。
export function getMetaNow(): MetaData {
  return clone(metaJson);
}

export function getStatus(): Promise<Envelope<StatusData>> {
  const client = liveClient();
  if (client) return client.get<StatusData>('/api/v1/status', undefined, 30);
  return read(['status'], (mode) =>
    okEnvelope(['status'], mode === 'empty' ? clone(EMPTY_STATUS) : clone(statusJson)),
  );
}

export function getAttempt(task: string, attempt: string): Promise<Envelope<AttemptData>> {
  const client = liveClient();
  if (client) {
    const path = `/api/v1/attempts/${encodeURIComponent(task)}/${encodeURIComponent(attempt)}`;
    return client.get<AttemptData>(path, undefined, 30);
  }
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
  const client = liveClient();
  if (client) {
    const url = `/api/v1/attempts/${encodeURIComponent(task)}/${encodeURIComponent(attempt)}/file`;
    const query: Record<string, string | undefined> = { path };
    if (cursor != null) query.cursor = cursor;
    return client.get<FileData>(url, query, 60);
  }
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
  const client = liveClient();
  if (client) return client.get<RolesData>('/api/v1/roles', undefined, 30);
  return read(['config', 'role', 'show'], () => okEnvelope(['config', 'role', 'show'], clone(rolesJson)));
}

export function getProfiles(): Promise<Envelope<ProfilesData>> {
  const client = liveClient();
  if (client) return client.get<ProfilesData>('/api/v1/profiles', undefined, 30);
  return read(['config', 'profile', 'show'], () =>
    okEnvelope(['config', 'profile', 'show'], clone(profilesJson)),
  );
}

export function getPresets(): Promise<Envelope<PresetsData>> {
  const client = liveClient();
  if (client) return client.get<PresetsData>('/api/v1/presets', undefined, 30);
  return read(['config', 'preset', 'list'], () =>
    okEnvelope(['config', 'preset', 'list'], clone(presetsJson)),
  );
}

export function getHubRoles(): Promise<Envelope<HubRolesData>> {
  const client = liveClient();
  if (client) return client.get<HubRolesData>('/api/v1/hub/roles', undefined, 30);
  return read(['config', 'hub', 'show', '--json'], () =>
    okEnvelope(['config', 'hub', 'show', '--json'], clone(HUB_ROLES_POSTS)),
  );
}

export function diffPresets(a: string, b: string): Promise<Envelope<PresetDiffData>> {
  const client = liveClient();
  if (client) {
    const path = `/api/v1/presets/${encodeURIComponent(a)}/diff/${encodeURIComponent(b)}`;
    return client.get<PresetDiffData>(path, undefined, 30);
  }
  const command = ['config', 'preset', 'diff', a, b];
  return read(command, () =>
    a === 'default' && b === 'economy'
      ? okEnvelope(command, clone(presetDiffJson))
      : missingEnvelope(command, `${a} → ${b}`),
  );
}

export function getRuntimes(): Promise<Envelope<RuntimesData>> {
  const client = liveClient();
  if (client) return client.get<RuntimesData>('/api/v1/runtimes', undefined, 30);
  return read(['config', 'runtime', 'list'], (mode) =>
    okEnvelope(['config', 'runtime', 'list'], mode === 'empty' ? clone(EMPTY_RUNTIMES) : clone(runtimesJson)),
  );
}

// Quizs 两个读函数：真实模式分别 GET /api/v1/quizs/providers（60 秒）与 /api/v1/quizs/live（150 秒），
// 服务的信封原样透传、失败不回落桩；桩模式走 read()（?mock= 的 loading/error 先于情景），情景由 mock/quizs.ts
// 按 ?quizs= 给出（broken 时 providers 是 ok:false、退出码 1 的错误信封）。
export function getQuizsProviders(): Promise<Envelope<QuizsProvidersData>> {
  const client = liveClient();
  if (client) return client.get<QuizsProvidersData>('/api/v1/quizs/providers', undefined, 60);
  return read(['config', 'quizs', 'providers', '--json'], () => quizsProvidersEnvelope());
}

export function getQuizsLive(): Promise<Envelope<QuizsLiveData>> {
  const client = liveClient();
  if (client) return client.get<QuizsLiveData>('/api/v1/quizs/live', undefined, 150);
  return read(['config', 'quizs', 'live', '--json'], () => quizsLiveEnvelope());
}

export function getPlugins(): Promise<Envelope<PluginsData>> {
  const client = liveClient();
  if (client) return client.get<PluginsData>('/api/v1/plugins', undefined, 30);
  return read(['plugins', 'list'], (mode) =>
    okEnvelope(['plugins', 'list'], mode === 'empty' ? clone(EMPTY_PLUGINS) : clone(pluginsJson)),
  );
}

export function getHistory(): Promise<Envelope<HistoryData>> {
  const client = liveClient();
  if (client) return client.get<HistoryData>('/api/v1/config/history', undefined, 30);
  return read(['config', 'history'], (mode) =>
    okEnvelope(['config', 'history'], mode === 'empty' ? clone(EMPTY_HISTORY) : clone(historyJson)),
  );
}

export function getUsage(): Promise<Envelope<UsageData>> {
  const client = liveClient();
  if (client) return client.get<UsageData>('/api/v1/usage', undefined, 120);
  return read(['logs', 'usage'], () => okEnvelope(['logs', 'usage'], clone(usageJson)));
}

export function listSecrets(): Promise<Envelope<SecretsData>> {
  const client = liveClient();
  if (client) return client.get<SecretsData>('/api/v1/secrets', undefined, 120);
  return read(['config', 'show'], (mode) =>
    okEnvelope(['config', 'show'], mode === 'empty' ? clone(EMPTY_SECRETS) : clone(secretsJson)),
  );
}

// 只读数据页二的两个读函数（原在 pages/readonly2/common-readers.ts，页面仍从那里引入）：
// 真实分支读服务并归一化形状，夹具分支逐字保留原来的 command、报缺原文与深拷贝。
export function getHistoryEntry(n: number): Promise<Envelope<HistoryEntryData>> {
  const client = liveClient();
  if (client) {
    return client.get<HistoryEntryData>(`/api/v1/config/history/${n}`, undefined, 30).then((env) =>
      mapped(env, toHistoryEntryData),
    );
  }
  const command = ['config', 'history', 'show', String(n)];
  return read(command, () =>
    Object.prototype.hasOwnProperty.call(HISTORY_ENTRIES, n)
      ? okEnvelope(command, clone(HISTORY_ENTRIES[n]))
      : missingEnvelope(command, String(n)),
  );
}

export function getPlugin(id: string): Promise<Envelope<PluginShowData>> {
  const client = liveClient();
  if (client) {
    return client.get<PluginShowData>(`/api/v1/plugins/${encodeURIComponent(id)}`, undefined, 30).then((env) =>
      mapped(env, toPluginShowData),
    );
  }
  const command = ['plugins', 'show', id];
  return read(command, () =>
    Object.prototype.hasOwnProperty.call(PLUGIN_SHOWS, id)
      ? okEnvelope(command, clone(PLUGIN_SHOWS[id]))
      : missingEnvelope(command, id),
  );
}

// 写函数：预览、查操作，加 A 片四个、B 片四个、七端岗位两个与本片一个（登记运行时）。演示数据由 mock/writes.ts 按 ?write= 情景生成，不联网。
// preview 的参数放宽成 WriteArgs：旧调用点传 Record<string,string> 仍然合法，行为不变。
// 真实模式（liveClient() 非 null）下走服务的写路由：预览 POST /api/v1/preview、执行各走自己的写路由
// （服务端时限 90 秒）、断线时查 GET /api/v1/operations/<确认号>；拿不到回应时 reject（同桩的 drop-*）。
export function preview(action: WriteAction, args: WriteArgs): Promise<HttpReply<PreviewData>> {
  const client = liveClient();
  if (client) {
    return client
      .post<PreviewData>('/api/v1/preview', { action, args: writeArgs(args) }, PREVIEW_TIMEOUT_SECONDS)
      .then(mappedPreview);
  }
  return mockPreview(action, args);
}

export function getOperation(id: string): Promise<HttpReply<OperationView>> {
  const client = liveClient();
  if (client) {
    return client
      .getRaw<unknown>(`/api/v1/operations/${encodeURIComponent(id)}`, undefined, OPERATION_TIMEOUT_SECONDS)
      .then((reply) =>
        reply.status === 200
          ? { status: 200, body: okEnvelope<OperationView>([], toOperationView(reply.body)) }
          : { status: reply.status, body: reply.body as Envelope<OperationView> },
      );
  }
  return mockGetOperation(id);
}

export function usePreset(name: string, confirmation: string): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/presets/${encodeURIComponent(name)}/use`,
      { confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockUsePreset(name, confirmation);
}

export function setPluginEnabled(id: string, enabled: boolean, confirmation: string): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    const path = enabled
      ? `/api/v1/plugins/${encodeURIComponent(id)}/enable`
      : `/api/v1/plugins/${encodeURIComponent(id)}/disable`;
    return client.post<null>(path, { confirmation }, WRITE_TIMEOUT_SECONDS);
  }
  return mockSetPluginEnabled(id, enabled, confirmation);
}

// B 片四个写函数：删除方案/profile/运行时与回滚；确认号与参数核对在 mock 侧（第二节）。
export function removePreset(name: string, confirmation: string): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/presets/${encodeURIComponent(name)}/remove`,
      { confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockRemovePreset(name, confirmation);
}

export function removeProfile(profile: string, confirmation: string): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/profiles/${encodeURIComponent(profile)}/remove`,
      { confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockRemoveProfile(profile, confirmation);
}

export function removeRuntime(runtime: string, confirmation: string): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/runtimes/${encodeURIComponent(runtime)}/remove`,
      { confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockRemoveRuntime(runtime, confirmation);
}

// config.rollback 的编号走路径段（十进制写法），正文只有确认号；服务从路径取这个 JSON 数字。
export function rollback(number: number, confirmation: string): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/config/rollback/${encodeURIComponent(String(number))}`,
      { confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockRollback(number, confirmation);
}

// 本片两个写函数：新建与编辑 profile。参数键名与服务侧 WRITE_ACTIONS 一一对应（profile/runtime/model/thinking/credential_env）；
// profile 是路径参数，不重复传进正文；credential_env 为空数组时不传这个键（服务侧空数组不合法）；
// 数组按顺序原样传给服务，不拼成字符串。确认号与参数核对在 mock 侧。
export function addProfile(
  args: {
    profile: string;
    runtime: string;
    model: string;
    thinking?: string;
    credential_env?: string[];
  },
  confirmation: string
): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/profiles/${encodeURIComponent(args.profile)}/add`,
      profileBody(args, confirmation),
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockAddProfile(args, confirmation);
}

export function editProfile(
  args: {
    profile: string;
    runtime?: string;
    model?: string;
    thinking?: string;
    credential_env?: string[];
  },
  confirmation: string
): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/profiles/${encodeURIComponent(args.profile)}/edit`,
      profileBody(args, confirmation),
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockEditProfile(args, confirmation);
}

// 七端岗位两个写函数：hub.set 的正文带 profile 与可选的 fallback（post 是路径参数，不重复传）；
// hub.unset 只有确认号。确认号与参数核对在 mock 侧。
export function setHubRole(
  args: { post: string; profile: string; fallback?: string },
  confirmation: string
): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    const w: WriteArgs = { profile: args.profile };
    if (args.fallback !== undefined) w.fallback = args.fallback;
    return client.post<null>(
      `/api/v1/hub/roles/${encodeURIComponent(args.post)}`,
      { ...writeArgs(w), confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockSetHubRole(args, confirmation);
}

export function unsetHubRole(post: string, confirmation: string): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    return client.post<null>(
      `/api/v1/hub/roles/${encodeURIComponent(post)}/unset`,
      { confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockUnsetHubRole(post, confirmation);
}

// 本片一个写函数：登记运行时。runtime 是路径参数，不重复传进正文；command 为空数组时不传这个键
// （服务侧空数组不合法，等于「命令留空不传」）；界面不传 force——同一个 id 已登记为别的适配器时由内核拒绝。
// 确认号与参数核对在 mock 侧。
export function addRuntime(
  args: { runtime: string; adapter: string; command?: string[] },
  confirmation: string
): Promise<HttpReply<null>> {
  const client = liveClient();
  if (client) {
    const w: WriteArgs = { adapter: args.adapter };
    if (args.command !== undefined) w.command = args.command;
    return client.post<null>(
      `/api/v1/runtimes/${encodeURIComponent(args.runtime)}/add`,
      { ...writeArgs(w), confirmation },
      WRITE_TIMEOUT_SECONDS,
    );
  }
  return mockAddRuntime(args, confirmation);
}
