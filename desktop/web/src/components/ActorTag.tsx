// 执行者标签（合同第 3 节）：把 actor 原文显示成一个等宽 Tag，按 actor 取色调。
// user-ui=brand、user=neutral、agent:<角色>=info、undeclared=warning、其他=neutral。
import { Tag, type TagTone } from './Tag';

export interface ActorTagProps {
  /** 要显示的 actor 原文。 */
  actor: string;
  className?: string;
}

/** 执行者色调：user-ui brand、user neutral、agent: 开头 info、undeclared warning、其他 neutral。 */
export function actorTone(actor: string): TagTone {
  if (actor === 'user-ui') return 'brand';
  if (actor === 'undeclared') return 'warning';
  if (actor.startsWith('agent:')) return 'info';
  return 'neutral';
}

export function ActorTag({ actor, className }: ActorTagProps) {
  return (
    <Tag tone={actorTone(actor)} mono className={className}>
      {actor}
    </Tag>
  );
}
