// 复制结果一行（共用件，T014）：把 copyText 的三态显示成一行小字，不设 role、不弹轻提示。
// 文字只从 components 的 COPY_RESULT_TEXT 取，不另写字面量；result 为 null 时不渲染任何元素。
// 类名 tt-copy-note，样式在同目录的 CopyNote.css（三级文字色、小号字）。
import { COPY_RESULT_TEXT, type CopyResult } from '../components';
import './CopyNote.css';

export interface CopyNoteProps {
  result: CopyResult | null;
}

export function CopyNote({ result }: CopyNoteProps) {
  if (result == null) return null;
  return <p className="tt-copy-note">{COPY_RESULT_TEXT[result]}</p>;
}
