// 任务页的地址（合同第 1 节）：视图解析、受管参数的读写与跨视图跳转目标。
// 页内变化（页签、分组胶囊、选中任务）用 history.replaceState 只改受管的那一项、不加历史项（E5）；
// 跨视图跳转用 useAppNavigate（shell/router :94-97），目标路径把本片受管的参数写成缺省值盖掉残留（K16）。
import { parseHash } from '../../shell/router';
import { ATTEMPT_GROUPS, type AttemptGroup } from '../../shell/attemptGroups';

export type TaskTabId = 'summary' | 'patch' | 'checks' | 'report' | 'events' | 'files';

/** 六个页签的取值与顺序（E4）。 */
export const TASK_TABS: readonly TaskTabId[] = ['summary', 'patch', 'checks', 'report', 'events', 'files'];

/** 页签的缺省值：缺省或认不出时是摘要。 */
export const DEFAULT_TAB: TaskTabId = 'summary';

export interface TasksView {
  /** 列表或详情。 */
  kind: 'list' | 'detail';
  /** 列表：地址第一段（选中的任务，可为空）；详情：task 段。 */
  task: string | null;
  /** 详情：attempt 段；列表为 null。 */
  attempt: string | null;
  /** 按下的分组（E2：多值取并集，按 ATTEMPT_GROUPS 的顺序，认不出的 ID 忽略）。 */
  groups: AttemptGroup[];
  /** 当前页签（E4）。 */
  tab: TaskTabId;
  /** 当前 ?mock= 值（没有为空串）。 */
  mock: string;
  /** 原始查询串（? 之后，不含 ?）。 */
  query: string;
}

function queryOf(hash: string): string {
  return parseHash(hash).query;
}

/** tab 的解析：六个取值各自生效，缺省或认不出时是摘要。 */
export function tabOfQuery(query: string): TaskTabId {
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq < 0 || part.slice(0, eq) !== 'tab') continue;
    const value = decodeSafe(part.slice(eq + 1));
    if ((TASK_TABS as readonly string[]).includes(value)) return value as TaskTabId;
  }
  return DEFAULT_TAB;
}

/** group 的解析：逗号分隔可多值，也认重复的 group 参数，取并集；认不出的 ID 忽略。 */
export function groupsOfQuery(query: string): AttemptGroup[] {
  const found = new Set<string>();
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq < 0 || part.slice(0, eq) !== 'group') continue;
    for (const piece of decodeSafe(part.slice(eq + 1)).split(',')) {
      const id = piece.trim();
      if ((ATTEMPT_GROUPS as readonly string[]).includes(id)) found.add(id);
    }
  }
  return ATTEMPT_GROUPS.filter((g) => found.has(g));
}

/** ?mock= 的值；没有为空串。 */
export function mockOfQuery(query: string): string {
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq >= 0 && part.slice(0, eq) === 'mock') return decodeSafe(part.slice(eq + 1));
  }
  return '';
}

function decodeSafe(value: string): string {
  try {
    return decodeURIComponent(value.replace(/\+/g, ' '));
  } catch {
    return value;
  }
}

/** 从地址读出视图（合同 §1）：路径段 0 或 1 个是列表，2 个及以上是详情（多出的段忽略，K15）。 */
export function tasksViewFromHash(hash: string): TasksView {
  const route = parseHash(hash);
  // 路径段进地址时经 encodeURIComponent，读的时候解回来（任务名可以带空格与尖括号）。
  const segments = route.segments.map((s) => decodeSafe(s));
  if (segments.length >= 2) {
    return {
      kind: 'detail',
      task: segments[0],
      attempt: segments[1],
      groups: groupsOfQuery(route.query),
      tab: tabOfQuery(route.query),
      mock: mockOfQuery(route.query),
      query: route.query,
    };
  }
  return {
    kind: 'list',
    task: segments.length === 1 ? segments[0] : null,
    attempt: null,
    groups: groupsOfQuery(route.query),
    tab: tabOfQuery(route.query),
    mock: mockOfQuery(route.query),
    query: route.query,
  };
}

function queryPairs(query: string): string[] {
  return query.split('&').filter((pair) => pair !== '');
}

function hasParam(query: string, key: string): boolean {
  return queryPairs(query).some((pair) => pair.split('=')[0] === key);
}

function liveQuery(): string {
  return queryOf(window.location.hash);
}

/**
 * 页内改地址（E5）：只改受管的那一个参数，其余查询参数（含 mock）原样保留；
 * 值是缺省值时删掉这个参数；用 replaceState，不加历史项、不派发 hashchange（Q2）。
 */
export function replaceInPage(
  path: string,
  patch: { groups?: readonly AttemptGroup[]; tab?: TaskTabId },
): void {
  const kept = queryPairs(liveQuery()).filter((pair) => {
    const key = pair.split('=')[0];
    if (patch.groups !== undefined && key === 'group') return false;
    if (patch.tab !== undefined && key === 'tab') return false;
    return true;
  });
  if (patch.groups !== undefined) {
    // 分组 ID 来自 ATTEMPT_GROUPS（封闭集合，只含小写字母），逐个编码后用逗号连接。
    const value = patch.groups.map((g) => encodeURIComponent(g)).join(',');
    if (value !== '') kept.push(`group=${value}`);
  }
  if (patch.tab !== undefined && patch.tab !== DEFAULT_TAB) kept.push(`tab=${patch.tab}`);
  const qs = kept.join('&');
  const next = `#${path}${qs === '' ? '' : `?${qs}`}`;
  if (next !== window.location.hash) window.history.replaceState(null, '', next);
}

/**
 * 跨视图的目标路径（K16）：把本片受管的参数写成缺省值，盖掉当前地址里的残留；
 * 只在当前地址真有这个参数时才写（否则会在地址里留下空参数）。
 */
export function crossViewPath(path: string): string {
  const query = liveQuery();
  const clear: string[] = [];
  if (hasParam(query, 'group')) clear.push('group=');
  if (hasParam(query, 'tab')) clear.push('tab=');
  if (clear.length === 0) return path;
  const sep = path.includes('?') ? '&' : '?';
  return `${path}${sep}${clear.join('&')}`;
}

/** 任务列表路径（选中任务可缺省）。 */
export function listPath(task?: string | null): string {
  return crossViewPath(task == null || task === '' ? '/tasks' : `/tasks/${encodeURIComponent(task)}`);
}

/** attempt 详情路径（进详情写 ?tab=summary）。 */
export function detailPath(task: string, attempt: string): string {
  return crossViewPath(`/tasks/${encodeURIComponent(task)}/${encodeURIComponent(attempt)}?tab=${DEFAULT_TAB}`);
}

/** 站内地址（面包屑 href）：只带 mock，不带 group、tab。 */
export function hrefWithMock(path: string, mock: string): string {
  return mock === '' ? `#${path}` : `#${path}?mock=${encodeURIComponent(mock)}`;
}

/** 面包屑链接点击：无修饰键左键先 preventDefault 再同步换路由，带修饰键或非左键走默认行为。 */
export function crumbHandler(navigate: (path: string) => void) {
  return (event: { target: unknown; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean; button: number; preventDefault: () => void }) => {
    const el = event.target as { closest?: (sel: string) => (HTMLElement | null) } | null;
    const link = el != null && typeof el.closest === 'function' ? el.closest('a') : null;
    if (link == null) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    const href = link.getAttribute('href') ?? '';
    const target = href.startsWith('#') ? href.slice(1) : href;
    // 受管的参数写成缺省值，盖掉当前地址里的残留（K16）。
    navigate(crossViewPath(target));
  };
}
