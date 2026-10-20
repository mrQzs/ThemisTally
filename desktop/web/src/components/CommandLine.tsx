// 命令行（UI 文档 7.16）：等宽显示 bash scripts/dispatch-pi.sh 加参数，右侧一个复制钮。
// 参数由后端给出（已脱敏），原样拼接，不加引号不转义。
import { CopyIcon } from '../icons';
import { IconButton } from './IconButton';
import './CommandLine.css';

/** 把调度参数拼成一行命令：bash scripts/dispatch-pi.sh 加空格连接的参数。 */
export function dispatchCommand(args: readonly string[]): string {
  return args.length === 0 ? 'bash scripts/dispatch-pi.sh' : `bash scripts/dispatch-pi.sh ${args.join(' ')}`;
}

export interface CommandLineProps {
  /** 要显示的命令文字。 */
  command: string;
  /** 尺寸：md 整块（缺省）/ sm 行内。 */
  size?: 'md' | 'sm';
  /** 点复制钮时调用，参数是要复制的文字。 */
  onCopy: (text: string) => void;
}

export function CommandLine({ command, size = 'md', onCopy }: CommandLineProps) {
  const classes = size === 'sm' ? 'tt-cmd tt-cmd--sm' : 'tt-cmd';
  return (
    <div className={classes}>
      <code>{command}</code>
      <IconButton
        size="sm"
        label="复制命令"
        tooltip="复制"
        icon={<CopyIcon width={14} height={14} />}
        onClick={() => onCopy(command)}
      />
    </div>
  );
}
