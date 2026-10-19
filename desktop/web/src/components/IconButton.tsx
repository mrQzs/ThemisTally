// 图标按钮：只用图标的按钮，永远包一层 Tooltip 并带 aria-label（UI 文档 7.2：只用图标的按钮必须有工具提示与 aria-label）。
// label 必填由类型保证：漏写 label，npm run build 的 tsc --noEmit 过不了。tooltip 与名称不同时用 tooltip 作提示文字。
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Tooltip } from './Tooltip';
import './IconButton.css';

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** 无障碍名称，必填；缺省提示文字。 */
  label: string;
  /** 图标（ReactNode，通常是某个 Icon 组件）。 */
  icon: ReactNode;
  /** 边长：sm 28 / md 32，缺省 md。 */
  size?: 'sm' | 'md';
  /** 提示文字与名称不同时用；缺省用 label。 */
  tooltip?: ReactNode;
}

export function IconButton({ label, icon, size = 'md', tooltip, className, ...rest }: IconButtonProps) {
  const classes = ['tt-icon-btn', `tt-icon-btn--${size}`];
  if (className) classes.push(className);
  return (
    <Tooltip content={tooltip ?? label}>
      <button type="button" className={classes.join(' ')} aria-label={label} {...rest}>
        {icon}
      </button>
    </Tooltip>
  );
}
