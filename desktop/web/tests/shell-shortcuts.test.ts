// 快捷键（合同第 5 条 / D04）：Ctrl+1…8 与前 8 个 Tab、Ctrl+, 切设置；带 Alt/Shift/Meta 不切；Ctrl+9 不切；
// 模态对话框打开时不切；处理的键被 preventDefault，其余不管。
import { afterEach, describe, expect, it } from 'vitest';
import { installShortcuts, shortcutTabId } from '../src/shell/shortcuts';

function press(key: string, init: KeyboardEventInit = {}) {
  const e = new KeyboardEvent('keydown', { key, cancelable: true, bubbles: true, ...init });
  window.dispatchEvent(e);
  return e;
}

describe('快捷键', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('shortcutTabId 映射 1–8 与逗号，9 为空', () => {
    expect(shortcutTabId('1')).toBe('overview');
    expect(shortcutTabId('8')).toBe('history');
    expect(shortcutTabId(',')).toBe('settings');
    expect(shortcutTabId('9')).toBeNull();
  });

  it('Ctrl+数字/逗号触发且 preventDefault', () => {
    const seen: string[] = [];
    const off = installShortcuts((id) => seen.push(id));
    const e1 = press('3', { ctrlKey: true });
    expect(seen).toEqual(['roles']);
    expect(e1.defaultPrevented).toBe(true);
    const e2 = press(',', { ctrlKey: true });
    expect(seen).toEqual(['roles', 'settings']);
    expect(e2.defaultPrevented).toBe(true);
    off();
  });

  it('带 Alt/Shift/Meta 不触发', () => {
    const seen: string[] = [];
    const off = installShortcuts((id) => seen.push(id));
    press('1', { ctrlKey: true, altKey: true });
    press('1', { ctrlKey: true, shiftKey: true });
    press('1', { ctrlKey: true, metaKey: true });
    press('1', {});
    expect(seen).toEqual([]);
    off();
  });

  it('Ctrl+9 不触发', () => {
    const seen: string[] = [];
    const off = installShortcuts((id) => seen.push(id));
    press('9', { ctrlKey: true });
    expect(seen).toEqual([]);
    off();
  });

  it('模态对话框打开时不触发', () => {
    const seen: string[] = [];
    const off = installShortcuts((id) => seen.push(id));
    const dlg = document.createElement('div');
    dlg.setAttribute('role', 'dialog');
    dlg.setAttribute('aria-modal', 'true');
    document.body.appendChild(dlg);
    press('1', { ctrlKey: true });
    expect(seen).toEqual([]);
    off();
  });
});
