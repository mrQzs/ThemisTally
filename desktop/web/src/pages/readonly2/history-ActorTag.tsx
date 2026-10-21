// 执行者标签（合同 D06）：等宽 Tag，色调按取值分五类。
import { Tag } from '../../components';
import { actorTone } from './history-logic';

export function ActorTag({ actor }: { actor: string }) {
  return (
    <Tag tone={actorTone(actor)} mono>
      {actor}
    </Tag>
  );
}
