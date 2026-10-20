// 输入框（组件板 :356–360、UI 文档 7.3）：label 关联、出错与帮助文字、等宽可选，其余透传给原生 input。
import type { InputHTMLAttributes } from 'react';
import { useFieldA11y } from './field/useFieldA11y';
import './TextField.css';

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  /** 可见标签，用 htmlFor 关联控件。 */
  label: string;
  /** 帮助文字（控件下方）。 */
  help?: string;
  /** 出错文字；给出错时 aria-invalid=true、边框与文字走危险色。 */
  error?: string;
  /** 值用等宽字体。 */
  mono?: boolean;
}

export function TextField({ label, help, error, mono, className, ...rest }: TextFieldProps) {
  const a11y = useFieldA11y(help, error);
  const classes = ['tt-field__input'];
  if (mono) classes.push('tt-field__input--mono');
  if (className) classes.push(className);
  return (
    <div className="tt-field">
      <label className="tt-field__label" htmlFor={a11y.controlId}>{label}</label>
      <input
        {...rest}
        id={a11y.controlId}
        className={classes.join(' ')}
        aria-describedby={a11y.describedBy}
        aria-invalid={a11y.invalid || undefined}
      />
      {error && <p className="tt-field__error" id={a11y.errorId}>{error}</p>}
      {help && <p className="tt-field__help" id={a11y.helpId}>{help}</p>}
    </div>
  );
}
