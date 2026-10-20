// 分段选择（组件板 :369、UI 文档 7.4）：role=radiogroup，段是 button role=radio；roving tabindex（只选中段可 Tab 到）。
// 左右方向键选中上一段/下一段并移焦点，到头循环（同原生单选组）；只处理左右；点击选中。受控：value + onChange(value)。
import { useRef, type KeyboardEvent } from 'react';
import './SegmentedControl.css';

export interface SegmentedOption {
  value: string;
  label: string;
}

export interface SegmentedControlProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  'aria-label': string;
}

export function SegmentedControl({ options, value, onChange, ...rest }: SegmentedControlProps) {
  const groupRef = useRef<HTMLDivElement>(null);
  const found = options.findIndex((o) => o.value === value);
  // value 不在选项里时第一项可 Tab 到（T005 终审 S5）；aria-checked 仍只看 value。
  const active = found >= 0 ? found : 0;

  const focusIndex = (i: number) => {
    const segs = groupRef.current?.querySelectorAll<HTMLElement>('[role="radio"]');
    segs?.[i]?.focus();
  };
  const step = (dir: 1 | -1) => {
    const n = options.length;
    if (n === 0) return;
    const next = (active + dir + n) % n;
    onChange(options[next].value);
    focusIndex(next);
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      step(1);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      step(-1);
    }
  };

  return (
    <div ref={groupRef} className="tt-seg" role="radiogroup" onKeyDown={onKeyDown} {...rest}>
      {options.map((opt, i) => {
        const checked = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={i === active ? 0 : -1}
            className="tt-seg__item"
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
