// 服务起的每一个内核子进程的环境（桌面端设计第 7 版 §5.2、D04、T5/T20）：从 process.env 原样复制（按名字排序，
// 次序稳定），只做四件事——去掉名字大写后等于 TYPESAFE_API_KEY 的变量（照 T5 的 kernel_env，一律去掉，不给任何
// 路由开例外：桌面应用从开始菜单或资源管理器起，它的环境里即使有这把 key 也与用户终端里的是两回事，服务索性不把
// 它传给内核）、设 CODEKIT_ACTOR=user-ui、保留 NoDefaultCurrentDirectoryInExePath（Windows 上没有就补成 1）、
// 其余原样。核实结论：内核的四个 main 都把 stdout 重配成 UTF-8，所以不加 PYTHONUTF8=1（不偏离 kernel_env）；
// 若执行端核实出 stdout 不是 UTF-8，加上它并在 README 注明它偏离 kernel_env。
/** 决策 API 的 key：名字大写后等于这个的一律去掉（与路由无关）。 */
export const DECISION_API_KEY = "TYPESAFE_API_KEY";
/** 服务起的子进程自报的身份（内核的 actor）。 */
export const KERNEL_ACTOR = "user-ui";
/** Windows 上 PATH 查找不碰当前目录（内核的 kernel_env 也保留它）。 */
export const NO_CWD_IN_PATH = "NoDefaultCurrentDirectoryInExePath";

/** 一份环境（按插入次序的条目表）：排序、去 key、补三项之后的成品。 */
export type EnvEntries = readonly (readonly [string, string])[];

/** 按名字排序（码点次序，稳定）：环境块的次序由它定，同名不同大小写的变量谁留由 base 的 environmentBlock 收拢。 */
export function sortEnv(entries: EnvEntries): EnvEntries {
  return [...entries].sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0));
}

/** 设置或替换一个变量（保持其余条目的相对次序）。 */
function withVar(entries: EnvEntries, name: string, value: string): EnvEntries {
  const out = entries.filter(([key]) => key !== name);
  out.push([name, value]);
  return sortEnv(out);
}

/** 有没有这个变量（按名字完全相等）。 */
function hasVar(entries: EnvEntries, name: string): boolean {
  return entries.some(([key]) => key === name);
}

/**
 * 内核子进程的环境：从 source（缺省 process.env）复制全部变量，去掉决策 API 的 key，再设 CODEKIT_ACTOR 与
 * NoDefaultCurrentDirectoryInExePath。返回按名字排序的条目表（runSupervised 的 env 就收这个）。
 */
export function kernelEnv(source: NodeJS.ProcessEnv = process.env): EnvEntries {
  const kept: (readonly [string, string])[] = [];
  for (const [name, value] of Object.entries(source)) {
    if (value === undefined) continue;
    if (name.toUpperCase() === DECISION_API_KEY) continue; // 大小写不同的写法也去掉（M18）
    kept.push([name, value]);
  }
  let entries = sortEnv(kept);
  entries = withVar(entries, "CODEKIT_ACTOR", KERNEL_ACTOR);
  if (!hasVar(entries, NO_CWD_IN_PATH)) entries = withVar(entries, NO_CWD_IN_PATH, "1");
  return entries;
}
