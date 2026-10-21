// 历史与审计页的纯函数（合同 D06、D07）：倒序、资源与状态文字、动作的中文说明、执行者色调、键级差异的情形判断。
import { isMaskedPlaceholder, type TagTone } from '../../components';
import { formatLocalUtc, relativeFrom } from './common-format';

export interface HistoryKeyDiff {
  key: string;
  old: unknown;
  new: unknown;
}

export interface HistoryEntry {
  number: number;
  resource: string;
  at: string;
  action: string;
  target: string;
  actor: string;
  confirmation: string;
  state: string | null;
  resolved?: boolean;
  changed_keys: string[] | null;
  note: string | null;
  external_changes?: number;
}

export interface HistoryDetail {
  number?: number;
  resource?: string;
  state?: string | null;
  note?: string | null;
  diff?: HistoryKeyDiff[] | null;
}

export interface HistoryDataLike {
  entries: HistoryEntry[];
  broken_lines: string[];
  external_before_first?: number;
}

/** 动作的中文说明（UI 文档 10.4）；表外动作不带 title。 */
const ACTION_TITLES: Record<string, string> = {
  'config.set': '设置配置键',
  'config.unset': '删除配置键',
  'config.rollback': '回滚配置',
  'preset.use': '切换方案',
  'preset.save': '保存方案',
  'preset.remove': '删除方案',
  'role.set': '修改角色绑定',
  'profile.add': '新建 profile',
  'profile.edit': '修改 profile',
  'profile.remove': '删除 profile',
  'runtime.add': '登记 runtime',
  'runtime.remove': '删除 runtime',
  external: '检测到界面与命令之外的改动',
};

export function actionTitle(action: string): string | null {
  return Object.prototype.hasOwnProperty.call(ACTION_TITLES, action) ? ACTION_TITLES[action] : null;
}

/** 资源：config 配置、local 本机文件、其他原样。 */
export function resourceLabel(resource: string): string {
  if (resource === 'config') return '配置';
  if (resource === 'local') return '本机文件';
  return resource;
}

/** 状态：published 已发布、aborted 已中止、unknown 未知、null 进行中或已中断；resolved 后接（补判）。 */
export function stateText(entry: { state: string | null; resolved?: boolean }): string {
  let text: string;
  if (entry.state === 'published') text = '已发布';
  else if (entry.state === 'aborted') text = '已中止';
  else if (entry.state === 'unknown') text = '未知';
  else text = '进行中或已中断';
  return entry.resolved ? `${text}（补判）` : text;
}

/** 执行者色调：user-ui brand、user neutral、agent: 开头 info、undeclared warning、其他 neutral。 */
export function actorTone(actor: string): TagTone {
  if (actor === 'user-ui') return 'brand';
  if (actor === 'user') return 'neutral';
  if (actor.indexOf('agent:') === 0) return 'info';
  if (actor === 'undeclared') return 'warning';
  return 'neutral';
}

/** 行按编号倒序。 */
export function sortedEntries(entries: readonly HistoryEntry[]): HistoryEntry[] {
  return [...entries].sort((a, b) => b.number - a.number);
}

/** 时间格：相对时间；title 是本地加 UTC 的写法，解析不了原样显示、不带 title。 */
export function timeCell(iso: string, now: number): { text: string; title: string | null } {
  const rel = relativeFrom(iso, now);
  if (rel === null) return { text: iso, title: null };
  return { text: rel, title: formatLocalUtc(iso) };
}

export type DiffKind =
  | { kind: 'local' }
  | { kind: 'keys'; diff: HistoryKeyDiff[] }
  | { kind: 'empty' }
  | { kind: 'masked-keys'; placeholder: string; keys: string[] }
  | { kind: 'masked-note'; note: string }
  | { kind: 'note'; note: string | null };

const hasCredential = (note: string | null | undefined) =>
  typeof note === 'string' && note.indexOf('疑似凭据') >= 0;

/** 键级差异小节：按顺序取第一条成立的情形（合同 D07）。 */
export function diffKind(entry: HistoryEntry, detail: HistoryDetail): DiffKind {
  if (entry.resource === 'local') return { kind: 'local' };
  const diff = detail.diff;
  if (Array.isArray(diff)) {
    return diff.length > 0 ? { kind: 'keys', diff } : { kind: 'empty' };
  }
  const notePlaceholder = isMaskedPlaceholder(entry.note ?? '') ? (entry.note as string) : null;
  const detailPlaceholder = isMaskedPlaceholder(detail.note ?? '') ? (detail.note as string) : null;
  const placeholder = notePlaceholder ?? detailPlaceholder;
  if (diff === null && (placeholder !== null || hasCredential(entry.note) || hasCredential(detail.note))) {
    const keys = entry.changed_keys ?? [];
    if (keys.length > 0 && placeholder !== null) return { kind: 'masked-keys', placeholder, keys };
    return { kind: 'masked-note', note: detail.note ?? entry.note ?? '' };
  }
  return { kind: 'note', note: detail.note ?? null };
}

/** 抽屉底栏说明：最新一条、本机文件；其余不写。 */
export function rollbackNote(entry: HistoryEntry, newestNumber: number): string {
  if (entry.number === newestNumber) return '这是最新的一条，回滚后没有变化';
  if (entry.resource === 'local') return '本机文件不存快照，不能回滚';
  return '';
}

/** 抽屉标题：「#n · action target」。 */
export function drawerTitle(entry: HistoryEntry): string {
  return `#${entry.number} · ${entry.action}${entry.target ? ` ${entry.target}` : ''}`;
}
