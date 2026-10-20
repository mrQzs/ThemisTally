// 禁用的写操作入口（合同第 10 条）：用 Tooltip 包一个 disabled 的 Button；Button 带设 pointer-events:none 的类，
// 让悬停落到 Tooltip 的包裹 span 上（禁用的 button 不派发鼠标事件，交给外层 span 才能弹出提示）。
import type { ReactNode } from 'react';
import { Button, Tooltip, type ButtonVariant, type ButtonSize } from '../components';
import './DisabledAction.css';

export interface DisabledActionProps {
  label: string;
  /** 提示文字，缺省「第二阶段接入」。 */
  reason?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
}

export function DisabledAction({
  label,
  reason = '第二阶段接入',
  variant = 'secondary',
  size = 'md',
  icon,
}: DisabledActionProps) {
  return (
    <Tooltip content={reason}>
      <Button variant={variant} size={size} disabled className="tt-disabled-action">
        {icon}
        {label}
      </Button>
    </Tooltip>
  );
}
