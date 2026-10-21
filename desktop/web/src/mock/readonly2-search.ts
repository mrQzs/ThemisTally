// 检索夹具（示意）：固定模式 logs[_ ]cat 的命中，两个 attempt 各至少一组；路径只用 .md/.txt/.log/.json/.jsonl；
// skipped_large ≥ 1；摘录 ≤ 200 字。接本机服务后由 searchLogs 直接读服务，本文件作废。
export const SEARCH_PATTERN = 'logs[_ ]cat';

export interface SearchMatch {
  task: string;
  attempt: string;
  path: string;
  line: number;
  text: string;
}

export interface SearchData {
  matches: SearchMatch[];
  truncated: boolean;
  skipped_links: number;
  skipped_large: number;
}

export const SEARCH_FIXTURE: SearchData = {
  matches: [
    {
      task: 'logs-cat',
      attempt: 'attempt-002',
      path: 'exec-summary.md',
      line: 3,
      text: '改动范围：src/themis/cli/logs.py（+13 −2），新增 src/themis/logs/cat.py 与 tests/test_logs_cat.py。',
    },
    {
      task: 'logs-cat',
      attempt: 'attempt-002',
      path: 'events.jsonl',
      line: 5,
      text: '{"ts": "2026-10-17T05:56:37Z", "type": "tool_call", "tool": "bash", "cmd": "python -m pytest bench/ tests/test_logs_cat.py -q"}',
    },
    {
      task: 'logs-cat',
      attempt: 'attempt-002',
      path: 'run.log',
      line: 12,
      text: 'python -m themis logs cat logs-cat attempt-002 summary.md --json',
    },
    {
      task: 'ui-readonly-api',
      attempt: 'attempt-001',
      path: 'notes.txt',
      line: 2,
      text: '检索用 logs_cat 与 logs cat 两种写法都要能命中，摘录里保留原文不改写。',
    },
    {
      task: 'ui-readonly-api',
      attempt: 'attempt-001',
      path: 'summary.md',
      line: 7,
      text: '门禁端要求：logs cat 子命令在空目录下也要给出可读的报错，退出码 2。',
    },
  ],
  truncated: false,
  skipped_links: 1,
  skipped_large: 2,
};
