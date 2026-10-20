// 面包屑（组件板 :449）：nav aria-label「面包屑」里一个 ol；前项有 href 渲染 a、否则 button type=button（样式像链接）；
// 末项是带 aria-current=page 的 span（既不是链接也不是按钮）；项之间是 ChevronRightIcon 14、aria-hidden。
import { Fragment } from 'react';
import { ChevronRightIcon } from '../icons';
import './Breadcrumb.css';

export interface BreadcrumbItem {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav className="tt-crumb" aria-label="面包屑">
      <ol className="tt-crumb__list">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <Fragment key={`${item.label}-${i}`}>
              <li className="tt-crumb__item">
                {isLast ? (
                  <span className="tt-crumb__current" aria-current="page">{item.label}</span>
                ) : item.href ? (
                  <a className="tt-crumb__link" href={item.href}>{item.label}</a>
                ) : (
                  <button type="button" className="tt-crumb__link" onClick={item.onClick}>{item.label}</button>
                )}
              </li>
              {!isLast && (
                <li className="tt-crumb__sep" aria-hidden="true">
                  <ChevronRightIcon width={14} height={14} />
                </li>
              )}
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
