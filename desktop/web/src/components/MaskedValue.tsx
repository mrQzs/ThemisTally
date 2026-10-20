// 遮蔽值（UI 文档 7.13）：后端给出的占位原样显示，前面加 lock 图标 14，工具提示「内核已遮蔽」。
// 占位逐字比较（括号是全角）；字体先写简写再写字形（简写会重置字形）。
import { LockIcon } from '../icons';
import './MaskedValue.css';

/** 内核遮蔽时给出的四种占位，逐字相等才算（UI 文档 7.13）。 */
const PLACEHOLDERS = ['（含疑似凭据，不显示）', '（值不显示）', '<redacted>', '（疑似凭据的键名）'];

/** 值是不是内核的遮蔽占位。 */
export function isMaskedPlaceholder(value: string): boolean {
  return PLACEHOLDERS.indexOf(value) >= 0;
}

export interface MaskedValueProps {
  /** 后端给的占位，原样显示。 */
  children: string;
}

export function MaskedValue({ children }: MaskedValueProps) {
  return (
    <span className="tt-masked" title="内核已遮蔽">
      <LockIcon width={14} height={14} />
      {children}
    </span>
  );
}
