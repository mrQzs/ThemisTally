// 浮层内部模块：打开时记下焦点、同步聚焦到框内第一个可聚焦元素，关闭或卸载时把焦点还给打开前的元素。
// 记与还都幂等：StrictMode 下 effect 跑两遍，opener 只在第一次记下，还不覆盖；同步聚焦不用 rAF/setTimeout，避免和 fake timers 搅在一起。
import { useEffect, useRef, type RefObject } from 'react';
import { getFocusable } from './focusable';

export function useOverlayFocus(open: boolean, rootRef: RefObject<HTMLElement | null>): void {
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    // 记打开前的焦点：只在 openerRef 为空时记，StrictMode 二次运行不覆盖。
    if (openerRef.current === null) {
      openerRef.current = document.activeElement as HTMLElement | null;
    }
    // 同步聚焦到框内第一个可聚焦元素，没有则落到根（根带 tabIndex=-1）。
    const root = rootRef.current;
    if (root) {
      const list = getFocusable(root);
      (list[0] ?? root).focus();
    }
    return () => {
      const opener = openerRef.current;
      if (opener && document.contains(opener)) {
        opener.focus();
      }
      openerRef.current = null;
    };
  }, [open, rootRef]);
}
