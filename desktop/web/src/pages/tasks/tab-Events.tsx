// 事件页签（合同第 4 节）：LogFollow 带过滤框与跟随开关；已结束时跟随禁用，运行中时由 tasks-live 模拟追加。
import { useCallback, useEffect, useRef, useState } from 'react';
import { LogFollow } from '../../components';
import type { ViewerPage } from '../../components/evidence/viewerLines';
import { FileReadNote, useFilePages } from './common-FileReader';
import { readAttemptFile } from './tasks-data';
import { subscribeMockEvents } from '../../mock/tasks-live';
import { groupOfState } from '../../shell/attemptGroups';
import './tasks-tabs.css';

/** 跟随禁用的原因：attempt 已结束，没有新事件。 */
const ENDED_REASON = 'attempt 已结束，没有新事件';

export interface TabEventsProps {
  task: string;
  attempt: string;
  /** attempt 的状态（status 行优先，取不到用 logs show 的）。 */
  state: string;
}

export function TabEvents({ task, attempt, state }: TabEventsProps) {
  const read = useCallback(
    (cursor?: string) => readAttemptFile(task, attempt, 'events.jsonl', cursor),
    [task, attempt],
  );
  const file = useFilePages(read);
  const running = groupOfState(state) === 'running';
  const pagesRef = useRef<readonly ViewerPage[]>(file.pages);
  pagesRef.current = file.pages;
  const appendRef = useRef(file.append);
  appendRef.current = file.append;
  const nextNRef = useRef(0);

  // 运行中的 attempt：由 tasks-live 按 1000ms 的节奏往后追加；切走页签或卸载时取消，不留下挂起的计时器。
  // 行号在本回调里自己往下数（不依赖渲染时的 pages）：一次 advance 里可能连 ticks 好几次，
  // 渲染还没发生，靠 pagesRef 会算出重复的行号、行数不涨。
  useEffect(() => {
    if (!running) return undefined;
    return subscribeMockEvents(task, attempt, (lines) => {
      if (nextNRef.current === 0) {
        let max = 0;
        for (const page of pagesRef.current) {
          if (page.mode !== 'jsonl') continue;
          for (const line of page.lines) if (line.n > max) max = line.n;
        }
        nextNRef.current = max + 1;
      }
      const start = nextNRef.current;
      nextNRef.current = start + lines.length;
      appendRef.current({ mode: 'jsonl', lines: lines.map((line, i) => ({ n: start + i, text: line.text })) });
    });
  }, [task, attempt, running]);

  if (file.status === 'error') return <FileReadNote path="events.jsonl" read={file} />;
  return (
    <div className="tasks-tab">
      <LogFollow
        title="events.jsonl"
        pages={file.pages}
        hasMore={file.hasMore}
        onLoadMore={file.loadMore}
        loadingMore={file.loadingMore}
        onCopy={() => undefined}
        followDisabledReason={running ? undefined : ENDED_REASON}
      />
    </div>
  );
}
