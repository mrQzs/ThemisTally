// 只读页面共用的地址拼接与点击处理（合同第 7 条）：进地址的部分经 encodeURIComponent；
// 无修饰键左键先 preventDefault 再用 navigate 同步换路由，带修饰键或非左键走默认行为。
import type { MouseEvent } from 'react';

/** attempt 字段最后一个斜杠之后的部分（attempt-002）。 */
export function attemptSeg(attempt: string): string {
  const i = attempt.lastIndexOf('/');
  return i >= 0 ? attempt.slice(i + 1) : attempt;
}

/** attempt 详情路径（[查看证据]）。 */
export function evidencePath(taskId: string, attempt: string): string {
  return `/tasks/${encodeURIComponent(taskId)}/${encodeURIComponent(attemptSeg(attempt))}`;
}

/** attempt 详情路径并打开事件页（[跟随事件]）。 */
export function eventsPath(taskId: string, attempt: string): string {
  return `/tasks/${encodeURIComponent(taskId)}/${encodeURIComponent(attemptSeg(attempt))}?tab=events`;
}

/** 任务页按分组过滤的路径（指标卡）。 */
export function groupPath(group: string): string {
  return `/tasks?group=${encodeURIComponent(group)}`;
}

/** 历史页路径（查看全部历史）。 */
export const HISTORY_PATH = '/history';

/** 链接点击处理：无修饰键左键 preventDefault 并导航，其余走默认行为。 */
export function navHandler(navigate: (path: string) => void, path: string) {
  return (e: MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    navigate(path);
  };
}
