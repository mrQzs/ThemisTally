// 复制结果一行（合同第 6 节）：显示 copyText 的三态文字，不设 role、不弹轻提示。
import { COPY_RESULT_TEXT, type CopyResult } from '../../components';

export interface CopyNoteProps {
  result: CopyResult | null;
}

export function CopyNote({ result }: CopyNoteProps) {
  if (!result) return null;
  return <p className="common-copy-note">{COPY_RESULT_TEXT[result]}</p>;
}
