// kit_roles.py 的生效绑定与运行中切换（迁移第 ③b 片 D8）、resolve_role_executor（第 ③c 片）。
// binding_tuple 是 D8 比较的元组：任何字段类型不对都按“没有这一项”处理，这里不抛异常（写入前的配置可能是手改坏的）。
import { lstatSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { isLinkOrJunction } from "@themis/base/pypath";
import { pyLstatStrerror } from "@themis/base/pyos";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { cmpCodePoints, pyLower } from "@themis/base/pyre";
import { pyStrValue } from "@themis/base/pyfmt";
import { pyEq } from "@themis/base/pyvalue";
import { TASK_ID_RE } from "@themis/base/secrets";
import { EXIT_BLOCKED, EXIT_USAGE } from "@themis/dispatcher/repo";
import { stateInFlight } from "@themis/dispatcher/status";
import { ADAPTERS, HUB_POST_AGENTS, adapterOf, configErrors, shownValue } from "./roles-check.ts";

/** 没写的角色取的默认值；execution 没写时由合同决定。 */
const DEFAULT_ROLES: Readonly<Record<string, PyDict | null>> = {
  planning_review: new Map([["mode", "interactive_host"]]),
  contract: new Map([["mode", "manual"]]),
  execution: null,
  scheduler_agent: new Map([["mode", "disabled"]]),
};
const DEFAULT_THINKING = "high";
/** pi_dispatch.ATTEMPT_DIR_RE（\d 认 Unicode 数字，$ 放过末尾换行）。 */
const ATTEMPT_DIR_RE = /^attempt-\p{Nd}{3,}(?=\n?$)/u;

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const text = (value: PyValue | undefined): string | null => (typeof value === "string" ? value : null);

/** 某个角色的生效绑定；execution 没写时是 null。 */
export function effectiveBinding(config: PyDict, role: string): PyDict | null {
  const roles = isDict(config.get("roles")) ? (config.get("roles") as PyDict) : new Map();
  const binding = roles.has(role) ? roles.get(role) : (DEFAULT_ROLES[role] ?? null);
  return isDict(binding) ? new Map(binding) : null;
}

/** D8 的元组 (mode, profile, runtime, adapter, provider, model, thinking)；没有绑定时 null。 */
export function bindingTuple(config: PyDict, role: string): (string | null)[] | null {
  const binding = effectiveBinding(config, role);
  if (binding === null) return null;
  const profileId = text(binding.get("profile"));
  const profiles = isDict(config.get("profiles")) ? (config.get("profiles") as PyDict) : new Map();
  const found = profileId !== null ? profiles.get(profileId) : undefined;
  const profile: PyDict = isDict(found) ? found : new Map();
  const model = isDict(profile.get("model")) ? (profile.get("model") as PyDict) : new Map();
  const options = isDict(profile.get("options")) ? (profile.get("options") as PyDict) : new Map();
  const runtime = text(profile.get("runtime"));
  const thinking = profile.size ? text(options.has("thinking") ? options.get("thinking") : DEFAULT_THINKING) : null;
  return [text(binding.get("mode")), profileId, runtime, adapterOf(config, runtime), text(model.get("provider")), text(model.get("id")), thinking];
}

/** 两个元组相等（Python 的 ==：None 与字符串逐项比）。 */
export function sameBinding(left: (string | null)[] | null, right: (string | null)[] | null): boolean {
  return pyEq(left, right);
}

interface Lstat {
  readonly isDir: boolean;
}

/** 不跟随链接的 stat；不存在（ENOENT、ENOTDIR）时 null，其余错误照抛。 */
function lstatOrNull(path: string): Lstat | null {
  try {
    return { isDir: lstatSync(path).isDirectory() };
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT" || code === "ENOTDIR") return null;
    throw error;
  }
}

function plainDir(path: string): boolean {
  const status = lstatOrNull(path);
  return status !== null && status.isDir && !isLinkOrJunction(path);
}

/** "<路径>（<strerror>）"：Python 的 exc.strerror。 */
function unreadable(path: string, error: unknown): string {
  return `${path}（${pyLstatStrerror(error)}）`;
}

/** Windows 上 Path 的排序按小写比较。 */
const pathOrder = (left: string, right: string): number =>
  process.platform === "win32" ? cmpCodePoints(pyLower(left), pyLower(right)) : cmpCodePoints(left, right);

/** （是否在运行, 读不出来的说明）：state.json 只读一次；已领取的 PREPARED 才看 claim/。 */
function attemptStatus(runDir: string): [boolean, string | null] {
  const path = join(runDir, "state.json");
  let data: PyValue;
  try {
    if (lstatOrNull(path) === null) return [false, null];
    data = loads(pyDecodeUtf8(pyReadBytes(path)));
  } catch (error) {
    if (error instanceof PyOSError) return [false, `${path}（${error.strerror}）`];
    if (error instanceof PyUnicodeDecodeError) return [false, `${path}（UnicodeDecodeError）`];
    if (error instanceof PyJsonError && error.kind !== "RecursionError") return [false, `${path}（JSONDecodeError）`];
    throw error;
  }
  if (!isDict(data)) return [false, `${path}（不是对象）`];
  const state = pyStrValue(data.has("state") ? (data.get("state") as PyValue) : "UNKNOWN");
  if (state !== "PREPARED") return [stateInFlight(state, false), null];
  const claim = join(runDir, "claim");
  let status: Lstat | null;
  try {
    status = lstatOrNull(claim);
  } catch (error) {
    return [false, unreadable(claim, error)];
  }
  return [stateInFlight(state, status !== null && status.isDir), null];
}

/** 正在运行的 attempt（task/attempt-NNN）与扫描中列不出来的位置；列不出来的不当作“没有在运行”。 */
export function inFlightAttempts(runsDir: string): [string[], string[]] {
  const found: string[] = [];
  const problems: string[] = [];
  let tasks: string[];
  try {
    if (lstatOrNull(runsDir) === null) return [found, problems];
    tasks = readdirSync(runsDir).filter((name) => TASK_ID_RE.test(name)).sort(pathOrder);
  } catch (error) {
    return [found, [unreadable(runsDir, error)]];
  }
  for (const task of tasks) {
    const taskDir = join(runsDir, task);
    let attempts: string[];
    try {
      if (!plainDir(taskDir)) continue;
      attempts = readdirSync(taskDir).filter((name) => ATTEMPT_DIR_RE.test(name)).sort(pathOrder);
    } catch (error) {
      problems.push(unreadable(taskDir, error));
      continue;
    }
    for (const attempt of attempts) {
      const attemptDir = join(taskDir, attempt);
      let plain: boolean;
      try {
        plain = plainDir(attemptDir);
      } catch (error) {
        problems.push(unreadable(attemptDir, error));
        continue;
      }
      if (!plain) continue;
      const [running, why] = attemptStatus(attemptDir);
      if (why !== null) problems.push(why);
      else if (running) found.push(`${task}/${attempt}`);
    }
  }
  return [found, problems];
}

/** D8：这次写入改变了 execution 或 contract 的生效绑定时，返回（在运行的 attempt, 列不出来的位置）。 */
export function bindingSwitchInFlight(runsDir: string, oldConfig: PyDict, newConfig: PyDict): [string[], string[]] {
  if (["execution", "contract"].every((role) => sameBinding(bindingTuple(oldConfig, role), bindingTuple(newConfig, role)))) return [[], []];
  return inFlightAttempts(runsDir);
}

/**
 * kit_roles.hub_running_turns：改到的这些岗位此刻在跑的回合（模型配置 §3.3，r3 第 163 轮），返回（每个有回合在跑的岗位一句,
 * 列不出来的位置）。信箱的回合目录没有 result.json 的就是在跑；执行端不在 HUB_POST_AGENTS 里，不算；列不出来的不当作“没有”。
 */
export function hubRunningTurns(agentDir: string, posts: readonly string[]): [string[], string[]] {
  const found: string[] = [];
  const problems: string[] = [];
  for (const post of posts) {
    const spec = HUB_POST_AGENTS[post];
    if (spec === undefined) continue;
    const [agent, label] = spec;
    const where = join(agentDir, "mailbox", "turns", agent);
    let turns: string[];
    try {
      if (!plainDir(where)) continue;
      turns = readdirSync(where).sort(pathOrder);
    } catch (error) {
      problems.push(unreadable(where, error));
      continue;
    }
    let running = 0;
    for (const name of turns) {
      const turn = join(where, name);
      try {
        if (plainDir(turn) && lstatOrNull(join(turn, "result.json")) === null) running += 1;
      } catch (error) {
        problems.push(unreadable(turn, error));
      }
    }
    if (running > 0) found.push(`${label}（${post}）：${running} 个回合在跑`);
  }
  return [found, problems];
}

/**
 * kit_roles._hub_last_turn：这个岗位最近一个跑完的回合实际拿到了什么（r3 第 168 轮）：回合目录名以开始时刻开头，倒着找第一个有
 * result.json 的。档位照 Quizs 的写法分要求、映射（只有 quizs 回报）、生效三值；第 168 轮之前的记录没有 adapter 与 effort_mapped。
 * 没有信箱、没跑完过、读不出时 null；执行端不看。
 */
export function hubLastTurn(agentDir: string, post: string): PyDict | null {
  const spec = HUB_POST_AGENTS[post];
  if (spec === undefined) return null;
  const where = join(agentDir, "mailbox", "turns", spec[0]);
  let record: PyValue;
  try {
    if (!plainDir(where)) return null;
    const done = readdirSync(where).sort(pathOrder).reverse().map((name) => join(where, name, "result.json")).find((path) => lstatOrNull(path) !== null);
    if (done === undefined) return null;
    record = loads(pyDecodeUtf8(pyReadBytes(done)));
  } catch {
    return null; // OSError、UnicodeDecodeError、JSON 读不出：照 Python 的 (OSError, ValueError)
  }
  if (!isDict(record)) return null;
  const field = (key: string): PyValue => (record as PyDict).get(key) ?? null;
  const adapter = field("adapter");
  return new Map<string, PyValue>([
    ["at", field("finished_at")], ["adapter", adapter === "claude" ? "claude-code" : adapter], ["models", field("models")],
    ["profile", field("binding_profile")],
    ["thinking", new Map<string, PyValue>([["requested", field("effort_requested")], ["mapped", field("effort_mapped")], ["effective", field("effort_effective")]])],
    ["fallback", field("quizs_fallback")],
  ]);
}

export interface RoleExecutorError {
  readonly message: string;
  readonly code: number;
}

/**
 * kit_roles.resolve_role_executor：按角色写的合同第一次建立版本记录时用的执行模型，返回（值, 错误），不抛异常（D4、D5）。
 * 值含 role、profile、runtime、adapter、active_preset、provider、model、thinking。混合期由 Python 的内核在进程内调用，
 * 两边对同一份配置必须逐字段一致（绑定解析契约）。
 */
export function resolveRoleExecutor(config: PyDict, role: PyValue): [PyDict | null, RoleExecutorError | null] {
  if (role !== "execution" && role !== "contract") return [null, { message: `executor.role 只能是 execution 或 contract：${shownValue(role)}`, code: EXIT_USAGE }];
  const errors = configErrors(config);
  if (errors.length) return [null, { message: `角色绑定的配置无效：${errors.slice(0, 3).join("；")}；先修好配置（config validate）`, code: EXIT_USAGE }];
  const binding = effectiveBinding(config, role);
  if (binding === null || binding.get("mode") !== "headless") {
    if (role === "contract" && binding !== null && binding.get("mode") === "manual") {
      return [null, { message: "contract 角色是 manual（规划审核端手写合同），合同却写了 role:contract：改绑定（config role set contract <profile>）或改合同", code: EXIT_USAGE }];
    }
    return [null, { message: `按角色写的合同需要 ${role} 角色的 headless 绑定：config role set ${role} <profile>`, code: EXIT_USAGE }];
  }
  const [, profileId, runtime, adapter, provider, model, thinking] = bindingTuple(config, role) as (string | null)[];
  if (adapter == null || !provider || !model) {
    return [null, { message: `${role} 角色绑定的 profile ${shownValue(profileId ?? null)} 无效：先修好配置（config validate）`, code: EXIT_USAGE }];
  }
  if (!ADAPTERS[adapter]?.headless_roles.includes(role)) {
    return [null, { message: `${role} 角色绑定到 ${adapter}（runtime ${runtime}）：这个适配器本轮没有接通 ${role}，不派遣`, code: EXIT_BLOCKED }];
  }
  const preset = config.get("active_preset");
  return [
    new Map<string, PyValue>([
      ["role", role],
      ["profile", profileId ?? null],
      ["runtime", runtime ?? null],
      ["adapter", adapter],
      ["active_preset", typeof preset === "string" ? preset : null],
      ["provider", provider],
      ["model", model],
      ["thinking", thinking ?? null],
    ]),
    null,
  ];
}
