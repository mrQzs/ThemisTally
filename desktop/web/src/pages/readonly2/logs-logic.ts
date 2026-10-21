// 日志与用量页的纯函数（合同 D02、D03）：任务下拉选项、占比文字、检索分组、摘录高亮、状态色调。
import type { TagTone } from '../../components';
import { formatThousands } from './common-format';
import type { SearchMatch } from '../../mock/readonly2-search';

export interface UsageAttempt {
  task?: unknown;
  attempt?: unknown;
  requested_model?: unknown;
  status?: unknown;
  usage?: Record<string, unknown> | null;
}

export interface UsageModelRow {
  requested_model?: unknown;
  known?: unknown;
  partial?: unknown;
  unknown?: unknown;
  usage?: Record<string, unknown> | null;
}

export interface UsageLike {
  executor?: {
    attempts?: UsageAttempt[];
    by_model?: UsageModelRow[];
    totals?: Record<string, unknown>;
    counts?: Record<string, unknown>;
    skipped_links?: unknown;
  };
  planner?: unknown;
}

/** 数字文字：千分位；缺失显示「未知」。 */
export function numberText(value: unknown): string {
  return formatThousands(value);
}

/** 任务下拉：首项「全部任务」值为空串，其余按首次出现排序去重。 */
export function taskOptions(usage: UsageLike): { value: string; label: string }[] {
  const out: { value: string; label: string }[] = [{ value: '', label: '全部任务' }];
  const seen = new Set<string>();
  for (const a of usage.executor?.attempts ?? []) {
    const task = typeof a.task === 'string' ? a.task : '';
    if (!task || seen.has(task)) continue;
    seen.add(task);
    out.push({ value: task, label: task });
  }
  return out;
}

/** 占比：一位小数加 %；分母为 0 或缺失显示「—」。 */
export function shareText(part: unknown, total: unknown): string {
  const pct = sharePercent(part, total);
  return pct === null ? '—' : `${pct.toFixed(1)}%`;
}

/** 占比的数值（百分比）；分母为 0 或缺失时返回 null。 */
export function sharePercent(part: unknown, total: unknown): number | null {
  const p = typeof part === 'number' ? part : Number.NaN;
  const t = typeof total === 'number' ? total : Number.NaN;
  if (!Number.isFinite(p) || !Number.isFinite(t) || t <= 0) return null;
  return (p / t) * 100;
}

/** 回报情况的三种色调与中文 title；其他值 neutral、不带 title。 */
export function usageStatusTone(status: unknown): { tone: TagTone; title: string | null } {
  if (status === 'known') return { tone: 'success', title: '已回报' };
  if (status === 'partial') return { tone: 'warning', title: '部分回报' };
  if (status === 'unknown') return { tone: 'neutral', title: '未回报' };
  return { tone: 'neutral', title: null };
}

export interface MatchGroup {
  task: string;
  attempt: string;
  items: SearchMatch[];
}

/** 检索结果按 (task, attempt) 首次出现的顺序分组。 */
export function groupMatches(matches: readonly SearchMatch[]): MatchGroup[] {
  const out: MatchGroup[] = [];
  const index = new Map<string, MatchGroup>();
  for (const m of matches) {
    const key = `${m.task}/${m.attempt}`;
    let group = index.get(key);
    if (!group) {
      group = { task: m.task, attempt: m.attempt, items: [] };
      index.set(key, group);
      out.push(group);
    }
    group.items.push(m);
  }
  return out;
}

/**
 * 这一行能不能高亮：JS 编译失败（Python 独有的语法）或检索词含带量词的分组（右括号后紧跟 *、+、?、{）时不高亮。
 */
export function canHighlight(q: string): boolean {
  for (let i = 0; i < q.length; i += 1) {
    if (q[i] === ')' && i + 1 < q.length && '*+?{'.indexOf(q[i + 1]) >= 0) return false;
  }
  try {
    new RegExp(q, 'g');
    return true;
  } catch {
    return false;
  }
}

export interface ExcerptSegment {
  text: string;
  hit: boolean;
}

/** 摘录按段切开，命中段交给调用方包在 mark 里；空匹配跳过，不生成 mark。 */
export function excerptSegments(text: string, q: string): ExcerptSegment[] {
  if (!canHighlight(q)) return [{ text, hit: false }];
  const re = new RegExp(q, 'g');
  const out: ExcerptSegment[] = [];
  let last = 0;
  let m = re.exec(text);
  while (m !== null) {
    if (m[0].length === 0) {
      re.lastIndex += 1;
      m = re.exec(text);
      continue;
    }
    if (m.index > last) out.push({ text: text.slice(last, m.index), hit: false });
    out.push({ text: m[0], hit: true });
    last = m.index + m[0].length;
    m = re.exec(text);
  }
  if (last < text.length) out.push({ text: text.slice(last), hit: false });
  return out.length > 0 ? out : [{ text, hit: false }];
}
