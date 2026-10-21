// 复制结果一行（合同第 6 节）：显示 copyText 的三态文字，不设 role、不弹轻提示。
import type { CopyResult } from './common-copyText';

const TEXT: Record<CopyResult, string> = {
  copied: '已复制',
  failed: '复制失败',
  unavailable: '这个环境没有剪贴板接口',
};

export interface CopyNoteProps {
  result: CopyResult | null;
}

export function CopyNote({ result }: CopyNoteProps) {
  if (!result) return null;
  return <p className="common-copy-note">{TEXT[result]}</p>;
}
