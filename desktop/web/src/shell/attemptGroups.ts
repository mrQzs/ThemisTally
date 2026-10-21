// attempt 状态分组计数（UI 文档 3.4 :169–177）：运行中（PREPARING/RUNNING/COLLECTING）、
// 待验收（NEEDS_REVIEW/TIMEOUT/CANCELLED/INFRA_FAILURE）与要你决定（ESCALATE/BLOCKED）。
// 任务 Tab 的计数胶囊与状态段的两个计数都用这里的 needJudge；运行中用 running。
import type { StatusRow } from '../api';

const RUNNING = ['PREPARING', 'RUNNING', 'COLLECTING'];
const NEED_JUDGE = ['NEEDS_REVIEW', 'TIMEOUT', 'CANCELLED', 'INFRA_FAILURE', 'ESCALATE', 'BLOCKED'];

// T3（合同第 1 条）：五个分组 ID 与状态到分组的映射，供总览指标卡与任务页分组用。
export type AttemptGroup = 'running' | 'review' | 'decide' | 'integrate' | 'ended';

export const ATTEMPT_GROUPS: readonly AttemptGroup[] = ['running', 'review', 'decide', 'integrate', 'ended'];

const GROUP_OF_STATE: Record<AttemptGroup, readonly string[]> = {
  running: ['PREPARING', 'RUNNING', 'COLLECTING'],
  review: ['NEEDS_REVIEW', 'TIMEOUT', 'CANCELLED', 'INFRA_FAILURE'],
  decide: ['ESCALATE', 'BLOCKED'],
  integrate: ['PASS', 'ACCEPTED_WITH_EXCEPTION'],
  ended: ['INTEGRATED', 'REVISE', 'ABANDONED', 'SUPERSEDED', 'PREPARE_FAILED'],
};

export function groupOfState(state: string): AttemptGroup | null {
  for (const group of ATTEMPT_GROUPS) {
    if (GROUP_OF_STATE[group].includes(state)) return group;
  }
  return null;
}

export interface StatusCounts {
  running: number;
  needJudge: number;
}

export function countByGroup(rows: StatusRow[]): StatusCounts {
  let running = 0;
  let needJudge = 0;
  for (const row of rows) {
    if (RUNNING.includes(row.state)) running += 1;
    if (NEED_JUDGE.includes(row.state)) needJudge += 1;
  }
  return { running, needJudge };
}
