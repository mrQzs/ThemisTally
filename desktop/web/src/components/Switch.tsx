// 开关（组件板 :374–377、UI 文档 7.5）：role=switch 的 span（不是 button），aria-checked；可用时 tabIndex=0，禁用时不可聚焦。
// 空格切换一次、点击整个控件切换；名称来自可见文字。受控：checked + onChange(next)。
import { useToggle } from './field/useToggle';
import './Switch.css';

export interface SwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** 可见文字，也是无障碍名称。 */
  label: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, disabled }: SwitchProps) {
  const handlers = useToggle(checked, disabled, onChange);
  return (
    <span className="tt-switch" role="switch" aria-checked={checked} {...handlers}>
      <span className="tt-switch__track" aria-hidden="true">
        <span className="tt-switch__knob" />
      </span>
      <span className="tt-switch__label">{label}</span>
    </span>
  );
}
