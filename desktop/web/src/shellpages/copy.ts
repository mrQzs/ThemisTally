// 复制到剪贴板（src/shellpages/copy.ts）：copyText(text, clipboard?) 返回 copied / failed / unavailable。
// clipboard 缺省取 globalThis.navigator?.clipboard；没有 writeText 返回 unavailable，写入成功 copied，抛错或被拒 failed。
// 点击时才读 navigator.clipboard；结果文字由调用方显示在原处一行，不弹轻提示、不设 role。

export type CopyResult = 'copied' | 'failed' | 'unavailable';

interface ClipboardLike {
  writeText?: (text: string) => Promise<void>;
}

export async function copyText(text: string, clipboard?: ClipboardLike): Promise<CopyResult> {
  const clip = clipboard ?? ((globalThis.navigator as { clipboard?: ClipboardLike } | undefined)?.clipboard);
  if (!clip || typeof clip.writeText !== 'function') return 'unavailable';
  try {
    await clip.writeText(text);
    return 'copied';
  } catch {
    return 'failed';
  }
}

/** 复制结果的显示文字（依次对应 unavailable / copied / failed）。 */
export const COPY_RESULT_TEXT: Record<CopyResult, string> = {
  copied: '已复制',
  failed: '复制失败',
  unavailable: '这个环境没有剪贴板接口',
};
