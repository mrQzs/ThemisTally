// Quizs 纯函数（合同第 6、7 节）：计费、状态、来源、下一步文本与「下一步」列的拼接，以及两个时刻的显示。
// 文案是合同逐字表，测试照它断言；纯函数不碰 DOM、不引计时器，时刻一律经 components/RelativeTime 的
// formatLocalUtc（本地加 UTC 的那串拼写只许出现在那一份文件里，本文件不自己拼）。
import type { TagTone } from '../../components';
import type { Envelope, QuizsLiveData, QuizsProvidersData } from '../../api';
import { formatLocalUtc } from '../../components/RelativeTime';

/** 兜底占位符：字段为 null、缺键或不是预期形状时显示它。 */
const DASH = '—';

const BILLING_LABELS: Record<string, string> = {
  none_test_only: '仅测试',
  step_plan_credits: '套餐额度',
  deepseek_prepaid_balance: '预付余额',
};

/** 计费：三个枚举值各有中文名，认不出的（含 <redacted>）原样显示原值。 */
export function billingLabel(billing: string): string {
  return BILLING_LABELS[billing] ?? billing;
}

const STATE_LABELS: Record<string, { label: string; tone: TagTone }> = {
  ready: { label: '就绪', tone: 'success' },
  expired: { label: '已过期', tone: 'danger' },
  build_mismatch: { label: '构建不一致', tone: 'warning' },
  invalid: { label: '无效', tone: 'danger' },
  missing: { label: '缺文件', tone: 'warning' },
};

/** 状态：五个枚举各有标签与色调（只有「就绪」不醒目）；status 为 null 是「读不出」，认不出是「未知」。 */
export function liveStateLabel(state: string | null): { label: string; tone: TagTone } {
  if (state === null) return { label: '读不出', tone: 'danger' };
  return STATE_LABELS[state] ?? { label: '未知', tone: 'neutral' };
}

const SOURCE_LABELS: Record<string, string> = {
  mailbox: '信箱',
  env: '环境变量',
};

/** 来源：信箱 / 环境变量；认不出原样返回。 */
export function liveSourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

const NEXT_STEPS: Record<string, string> = {
  ready: '不用动',
  expired: '续期后再看',
  build_mismatch: '重新构建这一套',
  invalid: '换一套能用的',
  missing: '补齐缺的文件',
};

/** 下一步文本：七个取值照逐字表；状态是 missing 时在后面追加「缺 <文件名>」（多个用「、」连接）。 */
export function liveNextStep(state: string | null, missing: readonly string[]): string {
  if (state === null) return '看这一套自己的问题';
  const step = NEXT_STEPS[state];
  if (step === undefined) return '按这一套的说明处理';
  if (state !== 'missing' || missing.length === 0) return step;
  return `${step}：缺 ${missing.join('、')}`;
}

/** 「下一步」列：下一步文本在前、问题文字在后，中间「；」；问题文字内部 problem 与 status.problem 也用「；」。 */
export function nextStepCell(nextStep: string, problem: string | null, statusProblem: string | null): string {
  const problems = [problem, statusProblem].filter((p): p is string => typeof p === 'string' && p !== '');
  const text = problems.join('；');
  if (nextStep === '') return text === '' ? DASH : text;
  return text === '' ? nextStep : `${nextStep}；${text}`;
}

/** 证书到期：毫秒整数先转 ISO 字符串再经 formatLocalUtc；null、不是数或解析不了显示「—」。 */
export function formatMsUtc(ms: number | null | undefined): string {
  if (typeof ms !== 'number' || !Number.isFinite(ms)) return DASH;
  const at = new Date(ms);
  if (Number.isNaN(at.getTime())) return DASH;
  return formatLocalUtc(at.toISOString()) ?? DASH;
}

/** 档案有效期：ISO 字符串经 formatLocalUtc；null 或解析不了显示「—」。 */
export function formatIsoUtc(iso: string | null | undefined): string {
  if (typeof iso !== 'string') return DASH;
  return formatLocalUtc(iso) ?? DASH;
}

/** 提供方档案读失败（退出码非 0 或没有 data）：整块按失败显示，live 表照它自己的信封。 */
export function providersUnavailable(env: Envelope<QuizsProvidersData>): boolean {
  return !env.ok || env.data == null;
}

/** live 读失败：只在 live 套表的位置写读失败，提供方档案照常。 */
export function liveUnavailable(env: Envelope<QuizsLiveData>): boolean {
  return !env.ok || env.data == null;
}
