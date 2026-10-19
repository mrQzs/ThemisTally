// attempt 的 17 个已知状态 + 未知状态兜底。
// 状态码 → { 中文标签, 色调, 图标(Lucide) }；未知状态原样显示状态码、neutral、circle-help。
// 取自画布「3.4 attempt 的 17 个状态 + 兜底」与 UI 文档 §3.4。
import type { ComponentType } from 'react';
import type { IconProps } from '../icons';
import {
  HourglassIcon,
  CircleDashedIcon,
  CircleXIcon,
  LoaderCircleIcon,
  ArchiveIcon,
  ScaleIcon,
  CircleCheckIcon,
  BadgeCheckIcon,
  RotateCcwIcon,
  OctagonXIcon,
  CircleArrowUpIcon,
  ServerIcon,
  TimerOffIcon,
  BanIcon,
  GitMergeIcon,
  ArchiveXIcon,
  LayersIcon,
  CircleHelpIcon,
} from '../icons';

export type Tone =
  | 'neutral'
  | 'info'
  | 'attention'
  | 'success'
  | 'warning'
  | 'danger'
  | 'escalate'
  | 'brand';

export type StateIcon = ComponentType<IconProps>;

export interface AttemptStateInfo {
  /** 中文标签；未知状态为空，由调用方原样显示状态码。 */
  label: string;
  tone: Tone;
  icon: StateIcon;
  /** 是否旋转（运行中的转圈图标）。 */
  spin?: boolean;
}

export const ATTEMPT_STATES: Record<string, AttemptStateInfo> = {
  PREPARING: { label: '准备中', tone: 'info', icon: HourglassIcon },
  PREPARED: { label: '待运行', tone: 'neutral', icon: CircleDashedIcon },
  PREPARE_FAILED: { label: '准备失败', tone: 'danger', icon: CircleXIcon },
  RUNNING: { label: '运行中', tone: 'info', icon: LoaderCircleIcon, spin: true },
  COLLECTING: { label: '收集证据', tone: 'info', icon: ArchiveIcon },
  NEEDS_REVIEW: { label: '待验收', tone: 'attention', icon: ScaleIcon },
  PASS: { label: '通过', tone: 'success', icon: CircleCheckIcon },
  ACCEPTED_WITH_EXCEPTION: { label: '带豁免通过', tone: 'success', icon: BadgeCheckIcon },
  REVISE: { label: '返工', tone: 'warning', icon: RotateCcwIcon },
  BLOCKED: { label: '阻塞', tone: 'danger', icon: OctagonXIcon },
  ESCALATE: { label: '升级', tone: 'escalate', icon: CircleArrowUpIcon },
  INFRA_FAILURE: { label: '基础设施故障', tone: 'danger', icon: ServerIcon },
  TIMEOUT: { label: '超时', tone: 'warning', icon: TimerOffIcon },
  CANCELLED: { label: '已取消', tone: 'neutral', icon: BanIcon },
  INTEGRATED: { label: '已集成', tone: 'brand', icon: GitMergeIcon },
  ABANDONED: { label: '已放弃', tone: 'neutral', icon: ArchiveXIcon },
  SUPERSEDED: { label: '已被取代', tone: 'neutral', icon: LayersIcon },
};

/** 未知状态兜底：原样显示状态码、neutral、circle-help。 */
export const FALLBACK_STATE: AttemptStateInfo = {
  label: '',
  tone: 'neutral',
  icon: CircleHelpIcon,
};

export interface ResolvedAttemptState extends AttemptStateInfo {
  /** 展示文本：已知状态用中文标签，未知状态原样显示状态码。 */
  display: string;
  /** 是否为已知状态。 */
  known: boolean;
}

export function resolveAttemptState(code: string): ResolvedAttemptState {
  const known = ATTEMPT_STATES[code];
  if (known) {
    return { ...known, display: known.label, known: true };
  }
  return { ...FALLBACK_STATE, display: code, known: false };
}
