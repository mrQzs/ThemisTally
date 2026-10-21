// CLI 运行时纯函数（合同第 6 节）：能担任、命令来源标签与色调、命令截断、操作出现规则。
import type { RuntimesData } from '../../api';

/** 能担任：按 runtime id 对应。 */
export function canServe(id: string): string {
  if (id === 'pi') return '执行端、合同端';
  if (id === 'claude-code' || id === 'codex') return '交互式宿主';
  if (id === 'opencode') return '未接通';
  return '—';
}

/** opencode 未接通用 --tt-text-3 淡显。 */
export function isUnconnected(id: string): boolean {
  return id === 'opencode';
}

const SOURCE_LABELS: Record<string, string> = {
  env: '环境变量',
  local: '本机文件',
  path: 'PATH',
  missing: '找不到',
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

export function sourceTone(source: string): 'neutral' | 'danger' {
  return source === 'missing' ? 'danger' : 'neutral';
}

/** 命令按码点截断：超 40 个码点显示前 22、「 … 」、后 15，否则原样。 */
export function shortCommand(full: string): string {
  const cps = Array.from(full);
  return cps.length > 40 ? cps.slice(0, 22).join('') + ' … ' + cps.slice(-15).join('') : full;
}

/** 命令单元格文字：null 显示「—」，否则空格连后截断；title 用全文。 */
export function commandText(command: string[] | null): string {
  if (!command) return '—';
  return shortCommand(command.join(' '));
}

export function commandFull(command: string[] | null): string | null {
  return command ? command.join(' ') : null;
}

/** [探测]：来源不是 missing 才有。 */
export function canProbe(source: string): boolean {
  return source !== 'missing';
}

/** [模型]：adapter 是 pi 且来源不是 missing 才有。 */
export function canModels(adapter: string, source: string): boolean {
  return adapter === 'pi' && source !== 'missing';
}

export type RuntimeRow = RuntimesData['runtimes'][number];
