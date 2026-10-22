// 总览纯函数（合同第 4 节）：指标卡分组计数、attempt 行文字、时长格式化、下一步命令、配置变更排序截取。
// 动作的中文说明用共用件 components/actionTitle（T013 合并，本文件不再另存一份表）。
// 分组只来自 attemptGroups（groupOfState），这里不另写 3.4 分组状态码。
import type { StatusRow, HistoryData } from '../../api';
import type { AttemptGroup } from '../../shell/attemptGroups';
import { groupOfState } from '../../shell/attemptGroups';
import { attemptSeg } from './common-links';

export type CardGroup = Exclude<AttemptGroup, 'ended'>;

export const CARD_META: readonly { id: CardGroup; label: string }[] = [
  { id: 'running', label: '运行中' },
  { id: 'review', label: '待验收' },
  { id: 'decide', label: '要你决定' },
  { id: 'integrate', label: '待集成' },
];

export interface CardCounts {
  running: number;
  review: number;
  decide: number;
  integrate: number;
}

type LooseRow = {
  attempt: string;
  task_id: string;
  state: string;
  plan_version?: number | null;
  wall_seconds?: number | null;
  checks?: string | null;
  live?: { tool_calls?: number; elapsed_seconds?: number; deltas_since_last_tool?: number; long_idle?: boolean } | null;
};

function loose(row: StatusRow): LooseRow {
  return row as unknown as LooseRow;
}

/** 四张指标卡的计数：按 groupOfState 逐行统计，ended 与不在映射里的状态不计。 */
export function metricCounts(rows: readonly StatusRow[]): CardCounts {
  const counts: CardCounts = { running: 0, review: 0, decide: 0, integrate: 0 };
  for (const row of rows) {
    const g = groupOfState(row.state);
    if (g === 'running') counts.running += 1;
    else if (g === 'review') counts.review += 1;
    else if (g === 'decide') counts.decide += 1;
    else if (g === 'integrate') counts.integrate += 1;
  }
  return counts;
}

/** 取属于给定分组（可多个）的行，保持 getStatus 顺序。 */
export function rowsInGroups(rows: readonly StatusRow[], groups: readonly AttemptGroup[]): StatusRow[] {
  const set = new Set<string>(groups);
  return rows.filter((r) => {
    const g = groupOfState(r.state);
    return g != null && set.has(g);
  });
}

/** 时长：秒向下取整；<60 秒 N 秒；<1 小时 M 分 S 秒；否则 H 小时 M 分；非数或负数返回 null。 */
export function formatDuration(sec: number | null | undefined): string | null {
  if (typeof sec !== 'number' || !Number.isFinite(sec) || sec < 0) return null;
  const s = Math.floor(sec);
  if (s < 60) return `${s} 秒`;
  if (s < 3600) return `${Math.floor(s / 60)} 分 ${s % 60} 秒`;
  return `${Math.floor(s / 3600)} 小时 ${Math.floor((s % 3600) / 60)} 分`;
}

/** 行名称：<task_id>.v<plan_version> · <attempt段>；plan_version 缺失只写 <task_id> · <attempt段>。 */
export function rowName(row: StatusRow): string {
  const r = loose(row);
  const ver = typeof r.plan_version === 'number' ? `.v${r.plan_version}` : '';
  return `${r.task_id}${ver} · ${attemptSeg(r.attempt)}`;
}

function checksText(row: StatusRow): string | null {
  const c = loose(row).checks;
  return typeof c === 'string' && c.length > 0 && c !== '-' ? c : null;
}

/** 需要你判断与待集成的信息列：用时与「检查 8/8」用 · 连，都没有留空。 */
export function checksInfo(row: StatusRow): string {
  const parts: string[] = [];
  const dur = formatDuration(loose(row).wall_seconds);
  if (dur) parts.push(dur);
  const c = checksText(row);
  if (c) parts.push(`检查 ${c}`);
  return parts.join(' · ');
}

/** 运行中的已用时间（live.elapsed_seconds）。 */
export function liveElapsed(row: StatusRow): string | null {
  const l = loose(row).live;
  return l ? formatDuration(l.elapsed_seconds ?? null) : null;
}

/** 运行中的工具调用次数。 */
export function toolCalls(row: StatusRow): number {
  const l = loose(row).live;
  return l && typeof l.tool_calls === 'number' ? l.tool_calls : 0;
}

export function longIdle(row: StatusRow): boolean {
  const l = loose(row).live;
  return !!(l && l.long_idle);
}

/** long_idle 的增量数；没有返回 null。 */
export function idleDeltas(row: StatusRow): number | null {
  const l = loose(row).live;
  return l && typeof l.deltas_since_last_tool === 'number' ? l.deltas_since_last_tool : null;
}

/** 给定分组里显示顺序第一行的 attempt 原文（下一步命令用）。 */
export function firstAttemptIn(rows: readonly StatusRow[], groups: readonly AttemptGroup[]): string | null {
  const filtered = rowsInGroups(rows, groups);
  return filtered.length > 0 ? filtered[0].attempt : null;
}

/** 下一步的 /review-pi 命令。 */
export function reviewCommand(attempt: string): string {
  return `/review-pi .agent/runs/${attempt}`;
}

export type HistoryEntry = HistoryData['entries'][number];

/** 配置变更：按 number 倒序取前 5。 */
export function topChanges(history: HistoryData): HistoryEntry[] {
  return history.entries.slice().sort((a, b) => b.number - a.number).slice(0, 5);
}
