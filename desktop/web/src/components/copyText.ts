// 复制到剪贴板（共用件）：T013 把只读页一、二的两份 copyText 并成这一份，复制结果文字也只在这里定义。
// clipboard 缺省时才读 globalThis.navigator?.clipboard（点击时才读，不在渲染期读）；
// 没有 writeText 返回 unavailable；成功 copied；抛错或被拒返回 failed。

export type CopyResult = 'copied' | 'unavailable' | 'failed';

/** 复制结果对应的文字。 */
export const COPY_RESULT_TEXT: Record<CopyResult, string> = {
  unavailable: '这个环境没有剪贴板接口',
  copied: '已复制',
  failed: '复制失败',
};

interface ClipboardLike {
  writeText?: (text: string) => Promise<void>;
}

export async function copyText(text: string, clipboard?: ClipboardLike | null): Promise<CopyResult> {
  const nav = globalThis.navigator as { clipboard?: ClipboardLike | null } | undefined;
  const clip = clipboard === undefined ? nav?.clipboard ?? null : clipboard;
  if (!clip || typeof clip.writeText !== 'function') return 'unavailable';
  try {
    await clip.writeText(text);
    return 'copied';
  } catch {
    return 'failed';
  }
}
