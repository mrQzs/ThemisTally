// 只读页面共用的区块（合同公共约定）：section + aria-labelledby 指 h2，卡片式外观；标题、可选说明、h2 后元素与右侧链接。
import { useId, type ReactNode } from 'react';
import './common-section.css';

export interface SectionProps {
  title: string;
  description?: string;
  /** h2 之后的元素（如计数胶囊）。 */
  afterTitle?: ReactNode;
  /** 头部右侧元素（如「查看全部历史」链接），靠右对齐。 */
  action?: ReactNode;
  /** 额外类名（如需要你判断的左边框）。 */
  className?: string;
  children: ReactNode;
}

export function Section({ title, description, afterTitle, action, className, children }: SectionProps) {
  const id = useId();
  const cls = className ? `common-section ${className}` : 'common-section';
  return (
    <section className={cls} aria-labelledby={id}>
      <div className="common-section__head">
        <div className="common-section__head-row">
          <h2 className="common-section__title" id={id}>
            {title}
          </h2>
          {afterTitle}
          {action}
        </div>
        {description && <p className="common-section__desc">{description}</p>}
      </div>
      {children}
    </section>
  );
}
