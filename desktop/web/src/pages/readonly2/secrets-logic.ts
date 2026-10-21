// 凭据页的纯函数（合同 D01）：用在哪里按出现顺序合并相邻 profile；来源取值映射到文字、色调与图标。
import type { TagTone } from '../../components';

export interface UsedByItem {
  kind: string;
  id?: string;
}

export interface UsedSegment {
  /** profiles：相邻的 profile 合成一段；decisions：决策模型；other：未知 kind 原样。 */
  kind: 'profiles' | 'decisions' | 'other';
  label: string;
  ids: string[];
}

/** 相邻的 profile 合并成「profile a、b」；决策模型；未知 kind 原样带 id。 */
export function usedBySegments(used: readonly UsedByItem[] | null | undefined): UsedSegment[] {
  const out: UsedSegment[] = [];
  for (const item of used ?? []) {
    if (item.kind === 'profile') {
      const last = out[out.length - 1];
      if (last && last.kind === 'profiles') last.ids.push(item.id ?? '');
      else out.push({ kind: 'profiles', label: 'profile', ids: [item.id ?? ''] });
    } else if (item.kind === 'decisions') {
      out.push({ kind: 'decisions', label: '决策模型', ids: [] });
    } else {
      out.push({ kind: 'other', label: item.kind, ids: item.id ? [item.id] : [] });
    }
  }
  return out;
}

export type SourceIcon = 'store' | 'missing' | null;

export interface SourceTag {
  label: string;
  tone: TagTone;
  icon: SourceIcon;
}

/** 来源取值（画布 Secrets :117–120 的「“来源”标签」小节）。 */
const SOURCE_TAGS: Record<string, SourceTag> = {
  env: { label: '环境变量', tone: 'success', icon: null },
  credential_store: { label: '系统凭据库', tone: 'success', icon: 'store' },
  file: { label: '0600 文件', tone: 'success', icon: null },
  none: { label: '没有', tone: 'danger', icon: 'missing' },
};

/** 来源 → 文字、色调、图标；未知取值原样、neutral、不带图标。 */
export function sourceTag(source: string): SourceTag {
  return SOURCE_TAGS[source] ?? { label: source, tone: 'neutral', icon: null };
}

/** 「“来源”标签」小节列出的四种取值，顺序照画布。 */
export const SOURCE_LEGEND: readonly { tag: SourceTag; note: string }[] = [
  { tag: SOURCE_TAGS.env, note: '当前进程的环境里有' },
  { tag: SOURCE_TAGS.credential_store, note: '存在操作系统的凭据库' },
  { tag: SOURCE_TAGS.file, note: '只有本人可读的本机文件' },
  { tag: SOURCE_TAGS.none, note: '哪一层都没找到' },
];
