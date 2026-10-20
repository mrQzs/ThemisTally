// 「下一步」提示（UI 文档 7.21）：info 色调的卡片，说明文字后面接一条可复制的命令（7.16 的小号样式）。
// 用于第一阶段界面上不能做、要回到规划端会话做的事；不是提示条，不设 role。
import type { ReactNode } from 'react';
import { InfoIcon } from '../icons';
import { CommandLine } from './CommandLine';
import './NextStep.css';

type NextStepPlain = {
  children: ReactNode;
  title?: string;
  command?: undefined;
  onCopy?: undefined;
};
type NextStepWithCommand = {
  children: ReactNode;
  title?: string;
  /** 可复制的命令；给了就必须同时给 onCopy。 */
  command: string;
  onCopy: (text: string) => void;
};

export type NextStepProps = NextStepPlain | NextStepWithCommand;

export function NextStep({ children, title, command, onCopy }: NextStepProps) {
  return (
    <div className="tt-next">
      <InfoIcon width={16} height={16} />
      {title != null && <strong>{title}</strong>}
      <span className="tt-next__text">{children}</span>
      {command != null && onCopy != null && <CommandLine size="sm" command={command} onCopy={onCopy} />}
    </div>
  );
}
