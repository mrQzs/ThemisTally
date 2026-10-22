// 任务页的行模型（合同第 2 节）：把 getStatus 的行按任务归组、求每个任务的最新 attempt、
// 五组计数、搜索过滤与下一步规则。分组只来自 attemptGroups（groupOfState），这里不另写状态到分组的映射。
import type { StatusRow } from '../../api';
import { groupOfState, type AttemptGroup } from '../../shell/attemptGroups';
import { formatDuration } from './tasks-format';

/** 运行中 attempt 的实时信息（只在部分夹具行里有）。 */
export interface TaskLive {
  tool_calls?: number;
  elapsed_seconds?: number;
  deltas_since_last_tool?: number;
  long_idle?: boolean;
}

/** 本片读到的 status 行字段：StatusRow 由 status.json 推出，这里只收窄到本片用得到的字段。 */
export interface TaskRow {
  attempt: string;
  task_id: string;
  state: string;
  plan_version?: number | null;
  attempt_no?: number | null;
  wall_seconds?: number | null;
  checks?: string | null;
  check_mode?: string | null;
  verdict?: string | null;
  failure_class?: string | null;
  violations?: number | null;
  tokens?: number | null;
  cost?: string | null;
  cost_status?: string | null;
  live?: TaskLive | null;
  effort_requested?: string | null;
  effort_effective?: string | null;
}

/** 收窄：api.ts 的 StatusRow 是本片行模型的超集，读取前先收窄。 */
export function taskRow(row: StatusRow): TaskRow {
  return row as unknown as TaskRow;
}

/** attempt 字段最后一个斜杠之后的部分（attempt-002）。 */
export function attemptSeg(attempt: string): string {
  const i = attempt.lastIndexOf('/');
  return i >= 0 ? attempt.slice(i + 1) : attempt;
}

/** 一个任务：task_id、它在 getStatus 里的行（保持原顺序）与最新 attempt 那一行。 */
export interface TaskEntry {
  task_id: string;
  rows: TaskRow[];
  latest: TaskRow;
}

/** 按 task_id 归组，顺序按在 getStatus 里第一次出现；最新 attempt 指 attempt_no 最大、相同时靠前的那个。 */
export function buildTasks(rows: readonly StatusRow[]): TaskEntry[] {
  const order: string[] = [];
  const byId = new Map<string, TaskRow[]>();
  for (const raw of rows) {
    const row = taskRow(raw);
    if (!byId.has(row.task_id)) {
      byId.set(row.task_id, []);
      order.push(row.task_id);
    }
    byId.get(row.task_id)!.push(row);
  }
  return order.map((task_id) => {
    const list = byId.get(task_id)!;
    let latest = list[0];
    for (const row of list) {
      const a = typeof row.attempt_no === 'number' ? row.attempt_no : 0;
      const b = typeof latest.attempt_no === 'number' ? latest.attempt_no : 0;
      if (a > b) latest = row;
    }
    return { task_id, rows: list, latest };
  });
}

/** 这个任务的最新 attempt 所在的组；PREPARED 与未知状态不在任何组，返回 null。 */
export function groupOfLatest(entry: TaskEntry): AttemptGroup | null {
  return groupOfState(entry.latest.state);
}

/** 五组各有多少个任务：按每个任务的最新 attempt 所在的组计数，不受搜索与选中的影响。 */
export function countTasksByGroup(entries: readonly TaskEntry[]): Record<AttemptGroup, number> {
  const counts: Record<AttemptGroup, number> = { running: 0, review: 0, decide: 0, integrate: 0, ended: 0 };
  for (const entry of entries) {
    const g = groupOfLatest(entry);
    if (g !== null) counts[g] += 1;
  }
  return counts;
}

/** 搜索：按 task_id 做不分大小写的子串过滤，先去掉首尾空白；空串不过滤。 */
export function filterTasks(entries: readonly TaskEntry[], query: string): TaskEntry[] {
  const needle = query.trim().toLowerCase();
  if (needle === '') return entries.slice();
  return entries.filter((entry) => entry.task_id.toLowerCase().includes(needle));
}

/** attempt 表按 attempt_no 倒序；相同时保持 getStatus 里的先后。 */
export function attemptsOf(entry: TaskEntry): TaskRow[] {
  return entry.rows
    .map((row, i) => ({ row, i }))
    .sort((a, b) => {
      const an = typeof a.row.attempt_no === 'number' ? a.row.attempt_no : 0;
      const bn = typeof b.row.attempt_no === 'number' ? b.row.attempt_no : 0;
      if (bn !== an) return bn - an;
      return a.i - b.i;
    })
    .map((x) => x.row);
}

/** 用时列：wall_seconds 格式化；为空且有 live 时写「已用」加 live.elapsed_seconds；都没有「—」。 */
export function durationText(row: TaskRow): string {
  const wall = formatDuration(row.wall_seconds);
  if (wall !== null) return wall;
  const live = row.live;
  if (live != null) {
    const elapsed = formatDuration(live.elapsed_seconds ?? null);
    if (elapsed !== null) return `已用 ${elapsed}`;
  }
  return '—';
}

/** 检查列：「<checks> <check_mode>」；checks 为「-」或为空写「—」。 */
export function checksText(row: TaskRow): string {
  const checks = typeof row.checks === 'string' ? row.checks : '';
  if (checks === '' || checks === '-') return '—';
  const mode = typeof row.check_mode === 'string' ? row.check_mode : '';
  return mode === '' ? checks : `${checks} ${mode}`;
}

/** 页头与检查页签的检查汇总：「8/8（fresh）」；没有写「—」。 */
export function checksSummary(row: TaskRow | null): string {
  if (row == null) return '—';
  const checks = typeof row.checks === 'string' ? row.checks : '';
  if (checks === '' || checks === '-') return '—';
  const mode = typeof row.check_mode === 'string' ? row.check_mode : '';
  return mode === '' ? checks : `${checks}（${mode}）`;
}

/** 下一步：四种规则（合同 §3）。REVISE 只能用状态码区分，不能靠 groupOfState 与 ended 组区分。 */
export interface NextStepInfo {
  text: string;
  command: string | null;
}

export function nextStepOf(state: string, task: string, attempt: string): NextStepInfo | null {
  const group = groupOfState(state);
  if (group === 'review') {
    return { text: '这个 attempt 等你验收。验收在规划端会话里进行。', command: `/review-pi .agent/runs/${task}/${attempt}` };
  }
  if (group === 'integrate') {
    return { text: '已通过，等待集成。集成在规划端会话里进行。', command: `/review-pi .agent/runs/${task}/${attempt}` };
  }
  if (group === 'decide') {
    return { text: '需要你做决定，见摘要里的阻塞点。', command: null };
  }
  if (state === 'REVISE') {
    return { text: '需要出新版本合同返工。', command: `/plan-task ${task}` };
  }
  return null;
}
