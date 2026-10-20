import type { KeyboardEvent, MouseEvent } from 'react';

// 开关（Switch）与复选框（Checkbox）共用的交互接线：ARIA 自绘的 span（不是 button，避免浏览器在 keyup 再点一次导致切两次）。
// 空格 keydown 切换一次并 preventDefault，repeat 为真时不切换；点击整个控件切换；禁用时不可聚焦（不带 tabindex）、不切换。
// 复选框只认空格，不认 Enter（WAI-ARIA 复选框模式）——本钩子同样只处理空格。
export interface ToggleHandlers {
  tabIndex: number | undefined;
  'aria-disabled': boolean | undefined;
  onClick: (e: MouseEvent) => void;
  onKeyDown: (e: KeyboardEvent) => void;
}

export function useToggle(
  checked: boolean,
  disabled: boolean | undefined,
  onChange: (next: boolean) => void,
): ToggleHandlers {
  const isDisabled = Boolean(disabled);
  const flip = () => {
    if (!isDisabled) onChange(!checked);
  };
  return {
    tabIndex: isDisabled ? undefined : 0,
    'aria-disabled': isDisabled ? true : undefined,
    onClick: flip,
    onKeyDown: (e) => {
      if (isDisabled) return;
      if (e.key === ' ') {
        e.preventDefault();
        if (!e.repeat) onChange(!checked);
      }
    },
  };
}
