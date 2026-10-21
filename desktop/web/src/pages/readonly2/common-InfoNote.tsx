// 说明条（合同「公共件」）：info 色调的一行说明，带 info 图标；不设 role、没有关闭钮，不用 Banner。
import type { ReactNode } from 'react';
import { InfoIcon } from '../../icons';
import './common-styles.css';

export interface InfoNoteProps {
  children: ReactNode;
}

export function InfoNote({ children }: InfoNoteProps) {
  return (
    <div className="r2-note">
      <InfoIcon width={16} height={16} className="r2-note__icon" />
      <span className="r2-note__text">{children}</span>
    </div>
  );
}
