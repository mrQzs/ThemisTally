// 总览指标卡（合同第 4 节）：整张是一个 a 链接，data-metric 为分组 ID，计数按分组统计；色调条 3px 贴左缘。
// 标签行是图标加标签文字（16px 图标，颜色各取本卡的色调令牌）；数字是整张卡唯一的 tt-num。
import { CircleArrowUpIcon, GitMergeIcon, LoaderCircleIcon, ScaleIcon } from '../../icons';
import { groupPath, navHandler } from './common-links';
import type { CardGroup } from './overview-logic';

export interface MetricCardProps {
  /** 分组 ID（AttemptGroup 名）。 */
  group: CardGroup;
  label: string;
  count: number;
  navigate: (path: string) => void;
}

const CARD_ICON = {
  running: LoaderCircleIcon,
  review: ScaleIcon,
  decide: CircleArrowUpIcon,
  integrate: GitMergeIcon,
} as const;

export function MetricCard({ group, label, count, navigate }: MetricCardProps) {
  const path = groupPath(group);
  const CardIcon = CARD_ICON[group];
  return (
    <a className="ov-metric" data-metric={group} href={`#${path}`} onClick={navHandler(navigate, path)}>
      <span className="ov-metric__bar" aria-hidden="true" />
      <span className="ov-metric__label">
        <CardIcon width={16} height={16} className="ov-metric__icon" aria-hidden="true" />
        {label}
      </span>
      <span className="ov-metric__num tt-num">{count}</span>
    </a>
  );
}
