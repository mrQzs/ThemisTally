// 本片夹具（示意，非真实数据）：logs show 形状的 attempt 详情。
// 键是「<task>/<attempt>」；内容守 UI 文档 8.9 的信封形状。
import type { AttemptData } from '../api';

interface AttemptEntry {
  task: string;
  attempt: string;
  state: string;
  state_at: string;
  summary: { bytes: number; truncated: boolean; text: string } | null;
  evidence: { path: string; bytes: number }[];
  skipped_links: number;
}

// ui-readonly-api/attempt-001（示意）：运行中，还没有摘要。
const LIVE_ATTEMPT: AttemptEntry = {
  task: 'ui-readonly-api',
  attempt: 'attempt-001',
  state: 'RUNNING',
  state_at: '2026-10-18T09:41:07Z',
  summary: null,
  evidence: [
    { path: 'events.jsonl', bytes: 18422 },
    { path: 'executor-report.md', bytes: 0 },
  ],
  skipped_links: 0,
};

const ATTEMPTS: Record<string, AttemptEntry> = {
  'ui-readonly-api/attempt-001': LIVE_ATTEMPT,
};

/** 夹具里有没有这个 attempt；有就返回（调用方还会深拷贝）。 */
export function findAttemptFixture(task: string, attempt: string): AttemptEntry | null {
  return ATTEMPTS[`${task}/${attempt}`] ?? null;
}

/** 交给 api.ts 信封的 data。 */
export function attemptFixtureData(entry: AttemptEntry): AttemptData {
  return {
    task: entry.task,
    attempt: entry.attempt,
    state: entry.state,
    state_at: entry.state_at,
    summary: entry.summary,
    evidence: entry.evidence.map((e) => ({ ...e })),
    skipped_links: entry.skipped_links,
  } as unknown as AttemptData;
}
