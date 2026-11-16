// quizs 运行时的提供方档案转表单选项（合同第 2 步）：纯函数，不碰 DOM、不引计时器、不读 window。
// 只从 ../api 取档案行的类型；档案信封本身由 ProfileForm 调 getQuizsProviders 拿，不走 src/mock。
import type { QuizsProviderRow } from '../api';
import { validModel } from './profileRules';

// 服务侧放行的思考档位（ts/packages/ui/src/redaction.ts 的 QUIZS_THINKING_ENUM 六值）：没有 minimal。
export const QUIZS_LEVELS = ['off', 'low', 'medium', 'high', 'xhigh', 'max'] as const;

export interface QuizsProviderOption {
  value: string;
  label: string;
  thinking: readonly string[];
}

// 服务把枚举外的值遮成 <redacted>（api.ts 的口径：按普通字符串收，这里当成不可用）。
const REDACTED = '<redacted>';

/** 档案行里能当一段模型名用的值：非字符串、空串与 <redacted> 都不算。 */
function usableSegment(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  if (value === '' || value === REDACTED) return null;
  return value;
}

/** 认 quizs 看适配器不看 id：按所选 id 找那一行，adapter 等于 quizs 才算；列表里找不到按非 quizs 走。 */
export function isQuizsRuntime(runtimeId: string, runtimes: readonly { id: string; adapter: string }[]): boolean {
  const row = runtimes.find((r) => r.id === runtimeId);
  return row !== undefined && row.adapter === 'quizs';
}

/** 档位：按原顺序取属于六值的元素并去重；thinking 不是数组（或元素不是字符串）时为空。 */
function archiveThinking(thinking: unknown): string[] {
  if (!Array.isArray(thinking)) return [];
  const levels = QUIZS_LEVELS as readonly string[];
  const out: string[] = [];
  for (const level of thinking) {
    if (typeof level !== 'string') continue;
    if (!levels.includes(level)) continue;
    if (out.includes(level)) continue;
    out.push(level);
  }
  return out;
}

/** 档案转模型选项：value 与 label 都是 provider/model 一段；同 value 只留第一项。 */
export function quizsProviderOptions(providers: readonly QuizsProviderRow[]): QuizsProviderOption[] {
  const out: QuizsProviderOption[] = [];
  for (const row of providers) {
    const provider = usableSegment(row.provider);
    const model = usableSegment(row.model);
    if (provider === null || model === null) continue;
    const value = `${provider}/${model}`;
    // 过不了 validModel 的值不进选项（服务只放行两段都合规的模型）。
    if (!validModel(value)) continue;
    if (out.some((o) => o.value === value)) continue;
    out.push({ value, label: value, thinking: archiveThinking(row.thinking) });
  }
  return out;
}

/** 档位可选项：有档案项给它的档位；没有（模型不在档案里或档案不明）给六值。 */
export function thinkingLevelsFor(option: QuizsProviderOption | null): readonly string[] {
  return option === null ? QUIZS_LEVELS : option.thinking;
}

export function thinkingAllowed(value: string, levels: readonly string[]): boolean {
  return levels.includes(value);
}

export function modelInArchive(value: string, options: readonly QuizsProviderOption[]): boolean {
  return options.some((o) => o.value === value);
}
