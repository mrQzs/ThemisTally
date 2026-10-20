// 复选框（组件板 :378–379、handoff :146）：ARIA 自绘 role=checkbox 的 span，aria-checked；键盘、鼠标、禁用同开关，只认空格。
// 选 ARIA 自绘而非原生 input：jsdom 只在 click 上跑激活行为，原生复选框的空格在门禁里测不到；本片筛选都是受控状态。
import { CheckIcon } from '../icons';
import { useToggle } from './field/useToggle';
import './Checkbox.css';

export interface CheckboxProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** 可见文字，也是无障碍名称。 */
  label: string;
  disabled?: boolean;
}

export function Checkbox({ checked, onChange, label, disabled }: CheckboxProps) {
  const handlers = useToggle(checked, disabled, onChange);
  return (
    <span className="tt-check" role="checkbox" aria-checked={checked} {...handlers}>
      <span className="tt-check__box" aria-hidden="true">
        {checked && <CheckIcon className="tt-check__mark" width={12} height={12} strokeWidth={3} />}
      </span>
      <span className="tt-check__label">{label}</span>
    </span>
  );
}
