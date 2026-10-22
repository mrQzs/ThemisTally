// 补丁页签（合同第 4 节）：candidate.patch 各页的 text 依次接起来交给 DiffView；没读完时能继续加载。
import { useCallback } from 'react';
import { DiffView } from '../../components';
import { FileReadNote, useFilePages } from './common-FileReader';
import { readAttemptFile } from './tasks-data';
import './tasks-tabs.css';

export interface TabPatchProps {
  task: string;
  attempt: string;
}

export function TabPatch({ task, attempt }: TabPatchProps) {
  const read = useCallback(
    (cursor?: string) => readAttemptFile(task, attempt, 'candidate.patch', cursor),
    [task, attempt],
  );
  const file = useFilePages(read);
  if (file.status === 'error') return <FileReadNote path="candidate.patch" read={file} />;
  const patch = file.pages.map((page) => (page.mode === 'text' ? page.text : '')).join('');
  return (
    <div className="tasks-tab">
      <DiffView
        patch={patch}
        title="candidate.patch"
        truncated={file.hasMore}
        onLoadMore={file.hasMore ? file.loadMore : undefined}
        loadingMore={file.loadingMore}
      />
    </div>
  );
}
