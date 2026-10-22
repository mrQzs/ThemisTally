// 复制到剪贴板（合同第 7 节）：copyText(text, clipboard?) 返回三态。
// clipboard 缺省取 globalThis.navigator?.clipboard；没有 writeText 返回 unavailable；
// 写入成功返回 copied；抛错或拒绝返回 failed。jsdom 没有 navigator.clipboard。

export type CopyResult = 'copied' | 'unavailable' | 'failed';

interface ClipboardLike {
  writeText?: (text: string) => Promise<void>;
}

function resolveClipboard(clipboard?: ClipboardLike | null): ClipboardLike | null {
  if (clipboard !== undefined) return clipboard;
  const nav = globalThis.navigator as { clipboard?: ClipboardLike | null } | undefined;
  return nav?.clipboard ?? null;
}

export async function copyText(text: string, clipboard?: ClipboardLike | null): Promise<CopyResult> {
  const clip = resolveClipboard(clipboard);
  if (clip == null || typeof clip.writeText !== 'function') return 'unavailable';
  try {
    await clip.writeText(text);
    return 'copied';
  } catch {
    return 'failed';
  }
}
