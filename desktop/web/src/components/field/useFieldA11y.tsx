import { useId } from 'react';

// 输入框（TextField）与下拉（Select）共用的无障碍接线：label 的 htmlFor 指向控件，
// 出错与帮助文字各有 id，aria-describedby 依次放出错、帮助的 id（只放渲染了的），有 error 时 aria-invalid=true。
export interface FieldA11y {
  /** 控件 id；label 用 htmlFor 指向它。 */
  controlId: string;
  /** 出错文字元素的 id（渲染了才有）。 */
  errorId: string | undefined;
  /** 帮助文字元素的 id（渲染了才有）。 */
  helpId: string | undefined;
  /** aria-describedby：依次出错、帮助，只放渲染了的；都没有则为 undefined。 */
  describedBy: string | undefined;
  /** 有 error 时为 true。 */
  invalid: boolean;
}

export function useFieldA11y(help: string | undefined, error: string | undefined): FieldA11y {
  const base = useId();
  const errorId = error ? `${base}-error` : undefined;
  const helpId = help ? `${base}-help` : undefined;
  const ids = [errorId, helpId].filter((v): v is string => Boolean(v));
  return {
    controlId: base,
    errorId,
    helpId,
    describedBy: ids.length > 0 ? ids.join(' ') : undefined,
    invalid: Boolean(error),
  };
}
