// 空状态（组件板 :465–470、UI 文档 7.23）：纵向居中、文字居中；图标缺省 ListChecksIcon；标题、说明、操作区（没有就不渲染）。
import type { ReactNode } from 'react';
import { ListChecksIcon } from '../icons';
import './EmptyState.css';

export interface EmptyStateProps {
  /** 图标，缺省 ListChecksIcon。 */
  icon?: ReactNode;
  title: string;
  description?: string;
  /** 操作区；没有就不渲染。 */
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="tt-empty">
      <span className="tt-empty__icon">{icon ?? <ListChecksIcon />}</span>
      <p className="tt-empty__title">{title}</p>
      {description && <p className="tt-empty__desc">{description}</p>}
      {action && <div className="tt-empty__action">{action}</div>}
    </div>
  );
}
