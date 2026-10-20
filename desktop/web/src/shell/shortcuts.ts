// 快捷键（合同第 5 条）：在 window 上监听 keydown。同时满足 ctrlKey 真、alt/shift/meta 都假、
// isComposing 假、未被 preventDefault 才处理；key 为 1–8 依次切前 8 个 Tab，逗号切设置；处理了就 preventDefault。
// 文档里有 role=dialog 且 aria-modal=true 的元素时不处理；Esc 不处理，各浮层自己关。
import { TABS } from './routes';

export function shortcutTabId(key: string): string | null {
  const tab = TABS.find((t) => t.shortcut === key);
  return tab ? tab.id : null;
}

export function installShortcuts(onActivate: (tabId: string) => void): () => void {
  const onKeyDown = (e: KeyboardEvent) => {
    if (!e.ctrlKey || e.altKey || e.shiftKey || e.metaKey || e.isComposing || e.defaultPrevented) return;
    if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
    const tabId = shortcutTabId(e.key);
    if (!tabId) return;
    e.preventDefault();
    onActivate(tabId);
  };
  window.addEventListener('keydown', onKeyDown);
  return () => window.removeEventListener('keydown', onKeyDown);
}
