// 执行报告页签（合同第 4 节）：warning 提示条加文本查看器；内容是执行器的自述，不是证据。
import { useCallback, useState } from 'react';
import { Banner, TextViewer } from '../../components';
import { CopyNote } from './common-CopyNote';
import { FileReadNote, useFilePages } from './common-FileReader';
import { readAttemptFile } from './tasks-data';
import { copyText, type CopyResult } from './tasks-copy';
import './tasks-tabs.css';

export interface TabReportProps {
  task: string;
  attempt: string;
}

export function TabReport({ task, attempt }: TabReportProps) {
  const read = useCallback(
    (cursor?: string) => readAttemptFile(task, attempt, 'executor-report.md', cursor),
    [task, attempt],
  );
  const file = useFilePages(read);
  const [copy, setCopy] = useState<CopyResult | null>(null);
  if (file.status === 'error') return <FileReadNote path="executor-report.md" read={file} />;
  return (
    <div className="tasks-tab">
      <Banner tone="warning">以下是执行器的自述，不是证据。</Banner>
      <TextViewer
        title="executor-report.md"
        pages={file.pages}
        hasMore={file.hasMore}
        onLoadMore={file.loadMore}
        loadingMore={file.loadingMore}
        onCopy={(text) => {
          void copyText(text).then(setCopy);
        }}
      />
      <CopyNote result={copy} />
    </div>
  );
}
