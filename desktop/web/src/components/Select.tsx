// 下拉（组件板 :360、UI 文档 7.3）：原生 select、appearance: none，右侧留出箭头位；label/帮助/出错接线同输入框。
import type { SelectHTMLAttributes } from 'react';
import { ChevronDownIcon } from '../icons';
import { useFieldA11y } from './field/useFieldA11y';
import './TextField.css';
import './Select.css';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  /** 可见标签，用 htmlFor 关联控件。 */
  label: string;
  /** 选项。 */
  options: SelectOption[];
  /** 帮助文字。 */
  help?: string;
  /** 出错文字；给出错时 aria-invalid=true。 */
  error?: string;
}

export function Select({ label, options, help, error, className, ...rest }: SelectProps) {
  const a11y = useFieldA11y(help, error);
  const classes = ['tt-field__input', 'tt-field__input--select'];
  if (className) classes.push(className);
  return (
    <div className="tt-field">
      <label className="tt-field__label" htmlFor={a11y.controlId}>{label}</label>
      <div className="tt-field__select">
        <select
          {...rest}
          id={a11y.controlId}
          className={classes.join(' ')}
          aria-describedby={a11y.describedBy}
          aria-invalid={a11y.invalid || undefined}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <ChevronDownIcon className="tt-field__arrow" width={16} height={16} />
      </div>
      {error && <p className="tt-field__error" id={a11y.errorId}>{error}</p>}
      {help && <p className="tt-field__help" id={a11y.helpId}>{help}</p>}
    </div>
  );
}
