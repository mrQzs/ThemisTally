// 七端的守卫（第 106 轮）：pi 工人用 `--extension <这个文件>` 加载。碰主工作区、写到工作目录之外的工具调用，
// 在执行之前就拦下（pi 1.4.0 的 tool_call 事件返回 block），模型当场收到报错、在同一回合里改正；以前要等回合结束，
// 内核事后审计判违规、整回合作废（门禁端因此作废过 13 个回合，合计约 338 分钟）。
// 判定照搬 kit_hub.py 的 pi_reach_problem 判“违规”的三条，不多不少；路径的各种写法与规范化后的根目录由内核用
// path_forms、normcase 算好，经环境变量 THEMIS_GUARD 传进来，这里只做比较。两边由对照用例逐条核对。
// 拦下的调用 pi 照样记 tool_execution_start；内核认“isError、details 为空对象、正文以 GUARD_PREFIX 开头、以
// GUARD_SUFFIX 结尾”的结果为已拦下，只记警告。这个文件在内核目录里，算内核文件：起 pi 之前核对哈希。
import { resolve, sep } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export const GUARD_PREFIX = "内核拦下：";
/** 拦下原因的固定结尾。内核认“已拦下”时连结尾一起核：bash 超时的报错也是 isError、details 为空对象，正文却是命令自己的输出。 */
export const GUARD_SUFFIX = "。这一步没有执行：在工作目录里写，读只读输入目录或工作目录里的那一份，接着干；不要换写法绕过去";

export interface GuardConfig {
  /** 工作目录与主工作区，已按 os.path.normcase(os.path.abspath(...)) 规范化。 */
  readonly workspace: string;
  readonly main: string;
  /** 主工作区里许读的依赖目录（DEPENDENCY_DIRS），同样规范化；depNames 是它们相对仓库的原名，写进说明。 */
  readonly deps: readonly string[];
  readonly depNames: readonly string[];
  /** path_forms：命令里可能的写法，小写，长的在前。 */
  readonly workspaceForms: readonly string[];
  readonly mainForms: readonly string[];
  /** 按路径读与搜索的工具（READ_TOOLS）。 */
  readonly readTools: readonly string[];
}

/** os.path.normcase(os.path.abspath(...))：Windows 上不分大小写、分隔符换成反斜杠（resolve 已经换好）。 */
function normcase(path: string): string {
  return process.platform === "win32" ? path.toLowerCase() : path;
}

function within(target: string, root: string): boolean {
  return target === root || target.startsWith(root.replace(/[\\/]+$/u, "") + sep);
}

function argStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(argStrings);
  if (value !== null && typeof value === "object") return Object.values(value).flatMap(argStrings);
  return [];
}

/** 这次调用碰没碰不该碰的地方：违规时返回说明（与 pi_reach_problem 的说明逐字相同），否则 null。 */
export function reachProblem(name: string, args: Record<string, unknown>, config: GuardConfig): string | null {
  if (name === "write" || name === "edit") {
    const raw = String(args["path"] ?? "");
    if (!within(normcase(resolve(config.workspace, raw)), config.workspace)) {
      return `${name} 写到了工作目录之外：${raw}`;
    }
  }
  if (config.readTools.includes(name) && args["path"] !== undefined && args["path"] !== null) {
    const raw = String(args["path"]);
    const target = normcase(resolve(config.workspace, raw));
    if (!within(target, config.workspace) && within(target, config.main)) {
      if (config.deps.some((dep) => within(target, dep))) return null;
      return `${name} 读了主工作区：${raw}。合同、信箱与执行证据在只读输入目录里，主工作区只许读已经装好的依赖`
        + `（${config.depNames.join("、")}）`;
    }
  }
  let text = argStrings(args).join(" ").toLowerCase();
  for (const form of config.workspaceForms) text = text.split(form).join("{工作目录}");
  if (config.mainForms.some((form) => text.includes(form))) {
    return `${name} 的参数提到了主工作区（材料在只读输入目录里，主工作区不许碰）：${argStrings(args).join(" ").slice(0, 200)}`;
  }
  return null;
}

/** tool_call 的处理：拦下时给 pi 的结果，放行时 undefined。 */
export function guardDecision(name: string, args: Record<string, unknown>,
  config: GuardConfig): { block: true; reason: string } | undefined {
  if (name === "deliver") return undefined; // 交的是内容、不碰文件：report 里引用主工作区的路径不算（第 100 轮）
  const problem = reachProblem(name, args, config);
  if (problem === null) return undefined;
  return { block: true, reason: `${GUARD_PREFIX}${problem}${GUARD_SUFFIX}` };
}

export default function (pi: ExtensionAPI): void {
  const raw = process.env["THEMIS_GUARD"];
  if (!raw) throw new Error("THEMIS_GUARD 没有设：内核起工人时会给");
  const config = JSON.parse(raw) as GuardConfig;
  pi.on("tool_call", async (event) => guardDecision(event.toolName, event.input as Record<string, unknown>, config));
}
