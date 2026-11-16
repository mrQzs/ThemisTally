// 七端岗位前后对比的纯逻辑（确认框「变化」一节按岗位渲染，B 片的表单底部也用同一份文字）：
// 只 import type，不碰 DOM、不取时钟，不引 ts/packages/ui。
import type { HubChange, HubChangeSide } from '../api';

// 岗位中文名在本文件里另维护一份：hubPostName 在 src/pages/readonly1/roles-logic.ts（T038 钉住了那里的三个导出
// 与「只 import type」），而 src/writes 不跨层引 src/pages（本仓库现在没有这种依赖，B 片的表单仍用 hubPostName），
// 所以这里放一份同样的六个名字；两处不要各改一份。
const HUB_POST_LABELS: Record<string, string> = {
  coordinator: '协调人（coordinator）',
  planner: '规划端（planner）',
  contract: '合同端（contract）',
  gate: '门禁端（gate）',
  audit: '审核端（audit）',
  exec: '执行端（exec）',
};

// 取不到值时的占位符（与 api.ts 的 DASH 同一个字符）。
const DASH = '—';

/** 岗位小标题：六个岗位给「中文名（岗位码）」，未知岗位码原样返回。 */
export function hubPostLabel(post: string): string {
  return HUB_POST_LABELS[post] ?? post;
}

function orDash(value: string | null | undefined): string {
  return value ?? DASH;
}

// 「默认」标记按侧生效：该侧 source 是 default 时，四行的值末尾各加一个（替补行也算；没有替补时是 —（默认））。
function mark(side: HubChangeSide | null, value: string): string {
  return side !== null && side.source === 'default' ? `${value}（默认）` : value;
}

// 替补文字：替补为 null → 占位符；替补的 profile 非空 → 那个 profile id；否则按 runtime · provider/model 拼。
function fallbackText(side: HubChangeSide | null): string {
  const fallback = side?.fallback ?? null;
  if (fallback === null) return DASH;
  if (fallback.profile) return fallback.profile;
  return `${orDash(fallback.runtime)} · ${orDash(fallback.provider)}/${orDash(fallback.model)}`;
}

/** 一个岗位的前后对比：恰好四行，次序固定（运行时、模型、思考档位、替补）；一侧为 null 时该侧全是占位符。 */
export function hubChangeLines(change: HubChange): string[] {
  const before = change.before;
  const after = change.after;
  return [
    `运行时：${mark(before, `${orDash(before?.runtime)} · ${orDash(before?.adapter)}`)} → ${mark(after, `${orDash(after?.runtime)} · ${orDash(after?.adapter)}`)}`,
    `模型：${mark(before, `${orDash(before?.provider)}/${orDash(before?.model)}`)} → ${mark(after, `${orDash(after?.provider)}/${orDash(after?.model)}`)}`,
    `思考档位：${mark(before, orDash(before?.thinking))} → ${mark(after, orDash(after?.thinking))}`,
    `替补：${mark(before, fallbackText(before))} → ${mark(after, fallbackText(after))}`,
  ];
}
