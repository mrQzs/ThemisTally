// 浮层内部模块：可聚焦元素查询。按选择器与 disabled/hidden 属性筛，不按布局（offsetParent、getClientRects）筛——
// jsdom 里布局全为 0，按布局筛会把所有元素筛掉。选择器与门禁探针一致，保证对话框焦点陷阱的首末元素对齐。

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/** 返回 root 内可按 Tab 顺序聚焦的元素，保持源码顺序。 */
export function getFocusable(root: ParentNode): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) => !el.hasAttribute('hidden') && !el.hasAttribute('disabled'),
  );
}
