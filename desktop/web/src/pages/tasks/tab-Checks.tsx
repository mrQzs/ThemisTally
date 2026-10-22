// 检查页签（合同第 4 节）：汇总行取自 status 行，证据清单里形如 checks/<NN>/<ID>.log 的文件列成表，
// 点一行或按 Enter 在表下用文本查看器打开；每条检查的结果要等 logs show 给出。
import { useCallback, useState } from 'react';
import { Table, TextViewer, type TableColumn } from '../../components';
import type { StatusRow } from '../../api';
import { FileReadNote, ReadErrorNote, useFilePages, type ReadFailure } from './common-FileReader';
import { readAttemptFile } from './tasks-data';
import { checksSummary, taskRow } from './tasks-model';
import { formatBytes } from './tasks-format';
import './tasks-tabs.css';

/** 检查日志表的一行。 */
interface CheckRow {
  path: string;
  id: string;
  size: string;
}

const COLUMNS: readonly TableColumn<CheckRow>[] = [
  { key: 'path', header: '文件', mono: true },
  { key: 'id', header: '检查 ID', mono: true },
  { key: 'size', header: '大小', numeric: true },
];

const CHECK_LOG_RE = /^checks\/\d+\/[^/]+\.log$/;

function checkIdOf(path: string): string {
  const name = path.slice(path.lastIndexOf('/') + 1);
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(0, dot) : name;
}

export interface TabChecksProps {
  task: string;
  attempt: string;
  row: StatusRow | null;
  /** logs show 的证据清单。 */
  evidence: readonly { path: string; bytes: number }[];
  /** logs show 读不到时的行内出错（合同 §3：页头照常，三个页签显示行内出错块）。 */
  attemptFailure: ReadFailure | null;
}

export function TabChecks({ task, attempt, row, evidence, attemptFailure }: TabChecksProps) {
  const [open, setOpen] = useState<string | null>(null);
  const read = useCallback(
    (cursor?: string) => readAttemptFile(task, attempt, open ?? '', cursor),
    [task, attempt, open],
  );
  const file = useFilePages(read);
  const logs = evidence.filter((e) => CHECK_LOG_RE.test(e.path));
  const summary = checksSummary(row == null ? null : taskRow(row));
  // logs show 读不到：这一页没有证据清单可列，只显示行内出错块。
  if (attemptFailure != null) {
    return (
      <div className="tasks-tab">
        <ReadErrorNote path={`${task}/${attempt}`} failure={attemptFailure} />
      </div>
    );
  }

  return (
    <div className="tasks-tab">
      <p className="tasks-tab__sum">{summary === '—' ? '还没有检查结果' : `检查 ${summary}`}</p>
      {logs.length === 0 ? (
        <p className="tasks-tab__empty">这个 attempt 没有检查日志</p>
      ) : (
        <div className="tasks-tab__table">
          <Table<CheckRow>
            className="tasks-tab__table-wrap"
            aria-label="检查日志"
            columns={COLUMNS}
            rows={logs.map((e) => ({ path: e.path, id: checkIdOf(e.path), size: formatBytes(e.bytes) }))}
            rowKey={(r) => r.path}
            rowHeight={40}
            onRowOpen={(path) => setOpen(path)}
          />
        </div>
      )}
      <p className="tasks-tab__note">每条检查的结果要等 logs show 给出</p>
      {open != null && (
        <>
          {file.status === 'error' ? (
            <FileReadNote path={open} read={file} />
          ) : (
            <TextViewer
              title={open}
              pages={file.pages}
              hasMore={file.hasMore}
              onLoadMore={file.loadMore}
              loadingMore={file.loadingMore}
              onCopy={() => undefined}
            />
          )}
        </>
      )}
    </div>
  );
}
