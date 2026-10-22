// 全部文件页签（合同第 4 节）：证据清单三列，点一行或按 Enter 按段打开；每行一个禁用的「在资源管理器中显示」。
import { useCallback, useState, type ReactNode } from 'react';
import { Table, TextViewer, type TableColumn } from '../../components';
import { FolderOpenIcon } from '../../icons/frame';
import { DisabledAction } from '../../shell/DisabledAction';
import { FileReadNote, ReadErrorNote, useFilePages, type ReadFailure } from './common-FileReader';
import { readAttemptFile } from './tasks-data';
import { formatBytes } from './tasks-format';
import './tasks-tabs.css';

/** 证据文件表的一行。 */
interface FileRow {
  path: string;
  size: string;
  action: ReactNode;
}

const COLUMNS: readonly TableColumn<FileRow>[] = [
  { key: 'path', header: '路径', mono: true },
  { key: 'size', header: '大小', numeric: true },
  { key: 'action', header: '操作' },
];

/** 本片唯一的禁用写入口（第二阶段接入）。 */
const REVEAL_LABEL = '在资源管理器中显示';

export interface TabFilesProps {
  task: string;
  attempt: string;
  /** logs show 的证据清单。 */
  evidence: readonly { path: string; bytes: number }[];
  /** logs show 记下的跳过链接数。 */
  skippedLinks: number;
  /** logs show 读不到时的行内出错（合同 §3：页头照常，三个页签显示行内出错块）。 */
  attemptFailure: ReadFailure | null;
}

export function TabFiles({ task, attempt, evidence, skippedLinks, attemptFailure }: TabFilesProps) {
  const [open, setOpen] = useState<string | null>(null);
  const read = useCallback(
    (cursor?: string) => readAttemptFile(task, attempt, open ?? '', cursor),
    [task, attempt, open],
  );
  const file = useFilePages(read);
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
      <div className="tasks-tab__table">
        <Table<FileRow>
          className="tasks-tab__table-wrap"
          aria-label="证据文件"
          columns={COLUMNS}
          rows={evidence.map((e) => ({
            path: e.path,
            size: formatBytes(e.bytes),
            action: (
              <DisabledAction
                label={REVEAL_LABEL}
                reason="第二阶段接入"
                variant="ghost"
                size="sm"
                icon={<FolderOpenIcon width={16} height={16} />}
              />
            ),
          }))}
          rowKey={(r) => r.path}
          rowHeight={40}
          onRowOpen={(path) => setOpen(path)}
        />
      </div>
      <p className="tasks-tab__note">{`点一行按段打开 · 来自 logs show · 跳过的链接 ${skippedLinks} 个`}</p>
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
