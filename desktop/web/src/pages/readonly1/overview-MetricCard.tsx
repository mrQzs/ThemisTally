// 总览指标卡（合同第 4 节）：整张是一个 a 链接，data-metric 为分组 ID，计数按分组统计；色调条 3px。
import { groupPath, navHandler } from './common-links';

export interface MetricCardProps {
  /** 分组 ID（AttemptGroup 名）。 */
  group: string;
  label: string;
  count: number;
  navigate: (path: string) => void;
}

export function MetricCard({ group, label, count, navigate }: MetricCardProps) {
  const path = groupPath(group);
  return (
    <a className="ov-metric" data-metric={group} href={`#${path}`} onClick={navHandler(navigate, path)}>
      <span className="ov-metric__bar" aria-hidden="true" />
      <span className="ov-metric__label">{label}</span>
      <span className="ov-metric__num tt-num">{count}</span>
    </a>
  );
}
