// 复制（合同「公共件」）：只有复制钮用，结果文字显示在钮旁，不弹轻提示。
// clipboard 缺省时才读 globalThis.navigator.clipboard（点击时才读，不在渲染期读）。
export type CopyResult = 'unavailable' | 'copied' | 'failed';

/** 复制结果对应的文字。 */
export const COPY_RESULT_TEXT: Record<CopyResult, string> = {
  unavailable: '这个环境没有剪贴板接口',
  copied: '已复制',
  failed: '复制失败',
};

export async function copyText(
  text: string,
  clipboard?: { writeText?: (value: string) => Promise<void> } | null,
): Promise<CopyResult> {
  const clip = clipboard === undefined ? globalThis.navigator?.clipboard : clipboard;
  if (!clip || typeof clip.writeText !== 'function') return 'unavailable';
  try {
    await clip.writeText(text);
    return 'copied';
  } catch {
    return 'failed';
  }
}
