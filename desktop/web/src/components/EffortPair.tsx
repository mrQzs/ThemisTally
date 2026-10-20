// 思考档位（UI 文档 7.24、架构文档 D11）：要求与生效并列显示，规则如下。
//   一致：两个值，不加标记；不同：加 warning 标签「与要求不同」；生效未知：「生效 未知」；没有要求：「—」。
// 逐字相同才算一致；生效有多个时原样列出，任一不同即不一致；不用金色。
import { Tag } from './Tag';
import './EffortPair.css';

export interface EffortPairProps {
  /** 合同里记下的要求档位。 */
  requested?: string | null;
  /** 内核记下的生效档位：一个或多个；缺失算未知。 */
  effective?: string | readonly string[] | null;
}

function effectiveList(effective: EffortPairProps['effective']): string[] {
  if (effective == null) return [];
  const items = typeof effective === 'string' ? [effective] : Array.from(effective);
  return items.filter((v) => v !== '');
}

export function EffortPair({ requested, effective }: EffortPairProps) {
  const hasRequest = requested != null && requested !== '';
  const list = effectiveList(effective);
  if (!hasRequest) {
    return (
      <span className="tt-effort" data-state="none">
        <span className="tt-effort__label">—</span>
      </span>
    );
  }
  const state = list.length === 0 ? 'unknown' : list.every((v) => v === requested) ? 'same' : 'differs';
  return (
    <span className="tt-effort" data-state={state}>
      <span className="tt-effort__label">要求</span>{' '}
      <span className="tt-effort__level">{requested}</span>{' · '}
      <span className="tt-effort__label">生效</span>{' '}
      {list.length === 0 ? (
        <span className="tt-effort__label">未知</span>
      ) : (
        list.map((v, i) => (
          <span className="tt-effort__level" key={`${v}-${i}`}>
            {i > 0 ? '、' : ''}
            {v}
          </span>
        ))
      )}
      {state === 'differs' && (
        <>
          {' '}
          <Tag tone="warning" title="内核记下的生效档位与要求不同">
            与要求不同
          </Tag>
        </>
      )}
    </span>
  );
}
