// attempt 状态分组计数（UI 文档 3.4 :169–177）：运行中（PREPARING/RUNNING/COLLECTING）、
// 待验收（NEEDS_REVIEW/TIMEOUT/CANCELLED/INFRA_FAILURE）与要你决定（ESCALATE/BLOCKED）。
// 任务 Tab 的计数胶囊与状态段的两个计数都用这里的 needJudge；运行中用 running。
import type { StatusRow } from '../api';

const RUNNING = ['PREPARING', 'RUNNING', 'COLLECTING'];
const NEED_JUDGE = ['NEEDS_REVIEW', 'TIMEOUT', 'CANCELLED', 'INFRA_FAILURE', 'ESCALATE', 'BLOCKED'];

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
