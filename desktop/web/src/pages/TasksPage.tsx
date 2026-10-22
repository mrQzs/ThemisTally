// 任务页（合同第 1、3 节）：按地址分派列表页与 attempt 详情页，两页五态都由 PageFrame 承担。
// 页面组件拿不到路由（App.tsx :63-67），所以挂载时用 parseHash 读 window.location.hash 得出视图，
// 自己再监听 hashchange 作为后退、前进与手改地址的兜底（Q2-A）；页内变化用 history.replaceState。
import { useCallback, useEffect, useRef, useState } from 'react';
import { PageFrame } from '../shell/PageFrame';
import { useAppNavigate } from '../shell/router';
import { getStatus, type Envelope, type StatusData } from '../api';
import { AttemptDetailView } from './tasks/AttemptDetailView';
import { TaskListView } from './tasks/TaskListView';
import { isAttemptMissing, loadAttemptDetail, type AttemptDetailData } from './tasks/tasks-data';
import {
  detailPath,
  replaceInPage,
  tasksViewFromHash,
  type TaskTabId,
  type TasksView,
} from './tasks/tasks-route';
import type { AttemptGroup } from '../shell/attemptGroups';

const loadStatus = (): Promise<Envelope<StatusData>> => getStatus();

const isStatusEmpty = (d: StatusData) => d.length === 0;

const isDetailEmpty = (d: AttemptDetailData) => isAttemptMissing(d);

/** 页内改地址时要写的受管参数。 */
interface InPagePatch {
  groups?: readonly AttemptGroup[];
  tab?: TaskTabId;
}

interface Loaded {
  task: string;
  attempt: string;
}

export default function TasksPage() {
  const navigate = useAppNavigate();
  const [view, setView] = useState<TasksView>(() => tasksViewFromHash(window.location.hash));
  // 详情页的 h1 要用读到的 attempt（Q5-A）；PageFrame 自己持有五态，所以这里只记「读到了没有」。
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    const onHashChange = () => setView(tasksViewFromHash(window.location.hash));
    window.addEventListener('hashchange', onHashChange);
    return () => {
      aliveRef.current = false;
      window.removeEventListener('hashchange', onHashChange);
    };
  }, []);

  // 页内改地址（E5）：先改本地视图，再把地址写延后一个宏任务。
  // jsdom 里挂载时那次 location.hash 赋值排下的 hashchange 会在之后才派发，而且派发时读的是当时的
  // location.hash；同步 replaceState 会让它带着新地址去改外壳的路由，页面跟着重挂载。延后一个宏任务
  // 那次派发就先看到旧地址（外壳路由不变、不重挂载），写完再按地址同步一次视图。
  const patchAddress = useCallback((path: string, patch: InPagePatch, next: Partial<TasksView>) => {
    setView((prev) => ({ ...prev, ...next }));
    setTimeout(() => {
      if (!aliveRef.current) return;
      replaceInPage(path, patch);
      setView(tasksViewFromHash(window.location.hash));
    }, 0);
  }, []);

  const task = view.task ?? '';
  const attempt = view.attempt ?? '';

  const loadDetail = useCallback((): Promise<Envelope<AttemptDetailData>> => {
    const env = loadAttemptDetail(task, attempt);
    void env.then((result) => {
      const usable = result.ok && result.data != null && !isAttemptMissing(result.data);
      setLoaded(usable ? { task, attempt } : null);
    });
    return env;
  }, [task, attempt]);

  if (view.kind === 'detail') {
    const title = loaded != null && loaded.task === task && loaded.attempt === attempt
      ? `${task} · ${attempt}`
      : '任务';
    const detailUrl = `/tasks/${encodeURIComponent(task)}/${encodeURIComponent(attempt)}`;
    return (
      <PageFrame<AttemptDetailData>
        title={title}
        description="attempt 的证据只读；下一步要回规划端会话。"
        load={loadDetail}
        isEmpty={isDetailEmpty}
        empty={{
          title: '找不到这个 attempt',
          description: `${task}/${attempt} 不在 status 里，logs show 也没有读到。回到任务列表重新选一个。`,
        }}
      >
        {(data) => (
          <AttemptDetailView
            task={data.task}
            attempt={data.attempt}
            row={data.row}
            attemptEnv={data.attemptEnv}
            tab={view.tab}
            onTabChange={(tab) => patchAddress(detailUrl, { tab }, { tab })}
            mock={view.mock}
            navigate={navigate}
          />
        )}
      </PageFrame>
    );
  }

  return (
    <PageFrame<StatusData>
      title="任务"
      description="每个任务由多个版本的合同组成，每个版本可以有多个 attempt"
      load={loadStatus}
      isEmpty={isStatusEmpty}
      empty={{ title: '还没有 attempt', description: '在规划端用 /dispatch-pi 派遣第一个任务' }}
    >
      {(rows) => (
        <TaskListView
          rows={rows}
          selectedTask={view.task}
          groups={view.groups}
          onSelectTask={(picked) =>
            patchAddress(`/tasks/${encodeURIComponent(picked)}`, {}, { task: picked })
          }
          onGroupsChange={(groups) =>
            patchAddress(
              view.task == null ? '/tasks' : `/tasks/${encodeURIComponent(view.task)}`,
              { groups },
              { groups },
            )
          }
          onOpenAttempt={(pickedTask, pickedAttempt) => navigate(detailPath(pickedTask, pickedAttempt))}
          mock={view.mock}
          navigate={navigate}
        />
      )}
    </PageFrame>
  );
}
