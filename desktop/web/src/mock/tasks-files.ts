// 本片夹具（示意，非真实数据）：logs-cat/attempt-002 与 ui-readonly-api/attempt-001 的证据文件。
// 键是「<task>/<attempt>/<path>」，带游标时再加「@<cursor>」；内容守 UI 文档 8.9 的信封形状。
import type { FileData } from '../api';

interface FileEntry {
  path: string;
  mode: 'text' | 'jsonl';
  done: boolean;
  next_cursor: string | null;
  text?: string;
  lines?: readonly unknown[];
}

// logs-cat/attempt-002 的 candidate.patch（示意）：一个改动文件带两个片段、一个新文件、一个二进制新文件；
// 第一个文件的第一行放探针文字，页面必须原样显示成文字。
const PATCH = [
  'diff --git a/src/pages/tasks/tasks-route.ts b/src/pages/tasks/tasks-route.ts',
  '--- a/src/pages/tasks/tasks-route.ts',
  '+++ b/src/pages/tasks/tasks-route.ts',
  '@@ -1,4 +1,5 @@',
  ' // 任务页的地址（合同第 1 节）：视图解析与受管参数的读写。',
  '-// 旧说明：页内变化用 pushState。',
  '+// 新说明：页内变化用 history.replaceState，不加历史项。',
  '+// 探针：<script>alert(1)</script> 与 \u001b[31mRED\u001b[0m 都必须原样显示成文字。',
  ' import { parseHash } from \'../../shell/router\';',
  '@@ -20,3 +21,4 @@ export interface TasksView {',
  '   kind: \'list\' | \'detail\';',
  '   task: string | null;',
  '+  /** 当前页签（E4）。 */',
  '   attempt: string | null;',
  ' }',
  'diff --git a/src/pages/tasks/tasks-groups.ts b/src/pages/tasks/tasks-groups.ts',
  'new file mode 100644',
  '--- /dev/null',
  '+++ b/src/pages/tasks/tasks-groups.ts',
  '@@ -0,0 +1,3 @@',
  '+// 任务页的分组（合同第 1、2 节）。',
  '+import { ATTEMPT_GROUPS, groupOfState } from \'../../shell/attemptGroups\';',
  '+export const GROUP_LABELS = { running: \'运行中\' };',
  'diff --git a/assets/logo.bin b/assets/logo.bin',
  'new file mode 100644',
  'index 0000000..1111111',
  'Binary files /dev/null and b/assets/logo.bin differ',
  '',
].join('\n');

const V01_LOG = [
  'V01 attempt 状态表（示意）',
  'domain/attemptStates.ts 与 UI 文档 3.4 :171–177 逐个相同：17 个状态、五组。',
  'PREPARED 不在任何组；groupOfState 对它返回 null。',
  '结果：通过',
  '',
].join('\n');

const SUMMARY = [
  '# logs-cat.v2 / attempt-002',
  '',
  '- 基线：9461d31',
  '- 模型：bb/step-5-preview · thinking high',
  '- 用时：28 分 39 秒；token 4,210,385；费用未知',
  '- 检查：8/8（fresh）',
  '- 越界：0',
  '',
  '## 复审需要关注',
  '',
  '- 无',
  '',
].join('\n');

const EVENTS_PAGE2 = [
  { n: 7, text: '{"type":"tool_execution_end","toolName":"read","isError":false}' },
  { n: 8, text: '{"type":"message_update","api_key":"<redacted>"}' },
  { n: 9, hidden: 'not_json' },
  { n: 10, text: '{"type":"agent_end","exitCode":0}' },
];

// 运行中 attempt 的事件第 1 页（示意）：由 tasks-live.ts 按 1000ms 的节奏往后追加。
const LIVE_EVENTS_PAGE1 = [
  { n: 1, text: '{"type":"agent_start","task":"ui-readonly-api"}' },
  { n: 2, text: '{"type":"tool_execution_end","toolName":"bash","isError":false}' },
  { n: 3, text: '{"type":"tool_execution_end","toolName":"read","isError":false}' },
];

const FILES: Record<string, FileEntry> = {
  'logs-cat/attempt-002/candidate.patch': {
    path: 'candidate.patch', mode: 'text', done: true, next_cursor: null, text: PATCH,
  },
  'logs-cat/attempt-002/checks/01/V01.log': {
    path: 'checks/01/V01.log', mode: 'text', done: true, next_cursor: null, text: V01_LOG,
  },
  'logs-cat/attempt-002/summary.md': {
    path: 'summary.md', mode: 'text', done: true, next_cursor: null, text: SUMMARY,
  },
  'logs-cat/attempt-002/events.jsonl@c1-0001a2f3': {
    path: 'events.jsonl', mode: 'jsonl', done: true, next_cursor: null, lines: EVENTS_PAGE2,
  },
  'ui-readonly-api/attempt-001/events.jsonl': {
    path: 'events.jsonl', mode: 'jsonl', done: false, next_cursor: 'live-0001', lines: LIVE_EVENTS_PAGE1,
  },
};

/** 读文件夹具的键：<task>/<attempt>/<path>，带游标时再加 @<cursor>。 */
export function fileKey(task: string, attempt: string, path: string, cursor?: string | null): string {
  const base = `${task}/${attempt}/${path}`;
  return cursor == null || cursor === '' ? base : `${base}@${cursor}`;
}

/** 夹具里有没有这一页；有就返回一份可安全改写的副本（调用方还会再深拷贝）。 */
export function findFileFixture(task: string, attempt: string, path: string, cursor?: string | null): FileEntry | null {
  const entry = FILES[fileKey(task, attempt, path, cursor)];
  return entry == null ? null : { ...entry };
}

/** 交给 api.ts 信封的 data（深拷贝由 tasks-data.ts 做）。 */
export function fileFixtureData(entry: FileEntry): FileData {
  if (entry.mode === 'jsonl') {
    return { path: entry.path, mode: 'jsonl', done: entry.done, next_cursor: entry.next_cursor, lines: entry.lines ?? [] } as unknown as FileData;
  }
  return { path: entry.path, mode: 'text', done: entry.done, next_cursor: entry.next_cursor, text: entry.text ?? '' } as unknown as FileData;
}
