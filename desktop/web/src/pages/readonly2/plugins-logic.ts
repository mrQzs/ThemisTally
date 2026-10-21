// 插件页的纯函数（合同 D04、D05）：启用、锁与资源、状态、操作入口的取值与色调。
import type { TagTone } from '../../components';

export interface PluginRow {
  id: string;
  version: string;
  enabled: string;
  lock: string;
  resource: string;
  missing: string[];
  status: string;
  reason: string;
}

export type LockIconKind = 'ok' | 'warn' | 'bad' | null;

export interface LockView {
  text: string;
  tone: TagTone;
  icon: LockIconKind;
  title: string | null;
}

/** 启用列：启用/是 → brand；停用/否 → neutral；不限制 → 不套标签；其他值原样 neutral。 */
export function enabledView(enabled: string): { text: string; tone: TagTone | null } {
  if (enabled === '启用' || enabled === '是') return { text: enabled, tone: 'brand' };
  if (enabled === '停用' || enabled === '否') return { text: enabled, tone: 'neutral' };
  if (enabled === '不限制') return { text: enabled, tone: null };
  return { text: enabled, tone: 'neutral' };
}

/** 锁与资源列：一致 success；漂移/不一致 warning；以「无效」开头 danger；「-」显示「—」；其他 warning。 */
export function lockView(value: string, reason: string): LockView {
  if (value === '一致') return { text: value, tone: 'success', icon: 'ok', title: null };
  if (value === '漂移' || value === '不一致') {
    return { text: value, tone: 'warning', icon: 'warn', title: reason || null };
  }
  if (value.slice(0, 2) === '无效') return { text: value, tone: 'danger', icon: 'bad', title: reason || null };
  if (value === '-') return { text: '—', tone: 'neutral', icon: null, title: null };
  return { text: value, tone: 'warning', icon: null, title: reason || null };
}

/** 状态列色调：READY success、DRIFT warning、BLOCKED danger、其他 neutral。 */
export function statusTone(status: string): TagTone {
  if (status === 'READY') return 'success';
  if (status === 'DRIFT') return 'warning';
  if (status === 'BLOCKED') return 'danger';
  return 'neutral';
}

export type PluginAction =
  | { kind: 'disable'; label: string }
  | { kind: 'enable'; label: string }
  | { kind: 'detail' };

/** 操作列：启用/是 → [停用…]；停用/否 → [启用…]；其余（含不限制）只显示文字「详情」。 */
export function pluginAction(enabled: string): PluginAction {
  if (enabled === '启用' || enabled === '是') return { kind: 'disable', label: '停用…' };
  if (enabled === '停用' || enabled === '否') return { kind: 'enable', label: '启用…' };
  return { kind: 'detail' };
}

/** 抽屉里的提示条：reason 非空写「reason。」，缺的权限非空再接「缺的权限：a、b。」，两者都空写状态码。 */
export function drawerWarning(status: string, reason: string, missing: readonly string[]): string {
  const parts: string[] = [];
  if (reason) parts.push(`${reason}。`);
  if (missing.length > 0) parts.push(`缺的权限：${missing.join('、')}。`);
  return parts.length > 0 ? parts.join('') : status;
}

/** 列表项用「、」连接；为空写「（无）」。 */
export function joinList(values: readonly string[] | null | undefined): string {
  return values && values.length > 0 ? values.join('、') : '（无）';
}
