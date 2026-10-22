// 摘要页签（合同第 4 节）：文件行、安全 Markdown 内容、截断提示与 [查看全文]、外部链接的第二阶段接入提示。
import { useCallback, useState } from 'react';
import { Banner, Button, SafeMarkdown, TextViewer } from '../../components';
import type { AttemptData, Envelope } from '../../api';
import { FileReadNote, toViewerPage, useFilePages } from './common-FileReader';
import { readAttemptFile } from './tasks-data';
import { formatBytes, kilobytesOf } from './tasks-format';
import { FileTextIcon } from '../../icons';
import './tasks-tabs.css';

export interface TabSummaryProps {
  task: string;
  attempt: string;
  attemptEnv: Envelope<AttemptData> | null;
}

export function TabSummary({ task, attempt, attemptEnv }: TabSummaryProps) {
  const read = useCallback(
    (cursor?: string) => readAttemptFile(task, attempt, 'summary.md', cursor),
    [task, attempt],
  );
  const file = useFilePages(read);
  const [openLink, setOpenLink] = useState<string | null>(null);
  const [full, setFull] = useState(false);

  const summary = attemptEnv != null && attemptEnv.ok && attemptEnv.data != null ? attemptEnv.data.summary : null;
  if (file.status === 'error') return <FileReadNote path="summary.md" read={file} />;
  if (summary == null) {
    return <p className="tasks-tab__empty">还没有摘要：attempt 结束后才有 summary.md</p>;
  }
  const pages = file.pages.length > 0 ? file.pages : [{ mode: 'text' as const, text: summary.text }];
  return (
    <div className="tasks-tab">
      <div className="tasks-tab__file-row">
        <FileTextIcon width={14} height={14} />
        <span className="tasks-tab__file-name">summary.md</span>
        <span className="tasks-tab__file-size tt-num">{formatBytes(summary.bytes)}</span>
        <span className="tasks-tab__file-note">安全 Markdown：原始 HTML 当文字显示</span>
      </div>
      {summary.truncated && (
        <Banner
          tone="info"
          action={
            <Button variant="secondary" size="sm" onClick={() => setFull(true)}>
              查看全文
            </Button>
          }
        >
          {`摘要较长，只显示前 ${kilobytesOf(summary.bytes)} KB`}
        </Banner>
      )}
      {full ? (
        <TextViewer
          title="summary.md"
          pages={pages}
          hasMore={file.hasMore}
          onLoadMore={file.loadMore}
          loadingMore={file.loadingMore}
          onCopy={() => undefined}
        />
      ) : (
        <div className="tasks-tab__summary">
          <SafeMarkdown source={summary.text} onOpenLink={setOpenLink} />
        </div>
      )}
      {openLink != null && <p className="tasks-tab__note">打开外部链接在第二阶段接入：{openLink}</p>}
    </div>
  );
}
