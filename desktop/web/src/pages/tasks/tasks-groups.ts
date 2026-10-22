// 任务页的分组（合同第 1、2 节）：五个分组 ID、顺序与状态到分组的映射都来自 T009 的 shell/attemptGroups，
// 本文件只加五组的中文标签，不另写映射（合同 D01：分组表与 UI 文档 3.4 :171–177 一致）。
import { ATTEMPT_GROUPS, groupOfState } from '../../shell/attemptGroups';
import type { AttemptGroup } from '../../shell/attemptGroups';

/** 五个分组的中文标签（UI 文档 3.4 :173–177）。 */
export const GROUP_LABELS: Record<AttemptGroup, string> = {
  running: '运行中',
  review: '待验收',
  decide: '要你决定',
  integrate: '待集成',
  ended: '已结束',
};

export { ATTEMPT_GROUPS, groupOfState };
export type { AttemptGroup };
