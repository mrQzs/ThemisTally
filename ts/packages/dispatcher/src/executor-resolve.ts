// pi_dispatch 的执行模型解析（迁移第 ④b7a 片）：resolve_executor、resolve_bound_executor，按角色写的合同在 prepare 时的
// 版本记录（_role_binding_candidate、_binding_drift_note、_publish_binding_record），写死模型的合同与当前绑定不同时的提示
// （_written_binding_note）。run（④b7b）复用 resolveExecutor。kit_roles 由调用方经 BindingRoles 交进来（Python 是惰性导入）。
// 单独成一个模块：contract.ts 引用 executor.ts，这里又要用 contract.ts 的正则，放进 executor.ts 会成环。
import { createHash } from "node:crypto";
import { join } from "node:path";
import { utcNow } from "@themis/base/clock";
import { LockBusyError, TaskLock } from "@themis/base/locks";
import { type PyOut, pyReprValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps } from "@themis/base/pyjson";
import { PyWinError, pyPublishNew } from "@themis/base/pyos";
import { pyEq } from "@themis/base/pyvalue";
import type { KitRoles } from "./contract-plan.ts";
import { MODEL_TOKEN_RE, PLACEHOLDER_RE } from "./contract.ts";
import { BindingRecordError, EXIT_DRIFT, allowedExecutorCheck, bindingRecordRel, loadBindingRecord } from "./executor.ts";
import { FALLBACK_THINKING_LEVELS } from "./pi-cli.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_USAGE, type Repo } from "./repo.ts";

/** prepare 还要用到的两个 kit_roles 函数（@themis/config 的 configErrors、bindingTuple）。 */
export interface BindingRoles extends KitRoles {
  configErrors(config: PyDict): string[];
  bindingTuple(config: PyDict, role: string): (string | null)[] | null;
}

/** 配置 v3 的五个键。 */
const V3_CONFIG_KEYS = ["runtimes", "profiles", "roles", "presets", "active_preset"];
const NO_KIT_ROLES = "合同按角色写 executor，但 scripts/kit_roles.py 不在本工具旁边";
const EXEC_ENV: readonly [string, string][] = [["provider", "PI_EXEC_PROVIDER"], ["model", "PI_EXEC_MODEL"], ["thinking", "PI_EXEC_THINKING"]];

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const s = (value: PyValue | undefined): string => pyStrValue(value ?? null);
const sha256 = (raw: Uint8Array): string => createHash("sha256").update(raw).digest("hex");

/**
 * resolve_executor：合同（_raw_executor 是显式写出的值）为准，PI_EXEC_* 只补缺、冲突报错，再过 allowed_executors。
 * source 给定时（按角色写的合同），显式值来自版本记录，错误里的“合同”换成它。
 */
export function resolveExecutor(contract: PyDict, config: PyDict, source: string | null = null): PyDict {
  const executor = new Map(contract.get("executor") as PyDict);
  const raw = contract.get("_raw_executor");
  for (const [field, envName] of EXEC_ENV) {
    const envValue = process.env[envName];
    if (!envValue) continue;
    const explicit = isDict(raw) ? (raw.get(field) ?? null) : null;
    if (pyTruthy(explicit) && !pyEq(explicit, envValue)) {
      if (source !== null) throw new DispatchError(`${envName}=${envValue} 与${source}的 ${field}=${s(explicit)} 冲突；以它为准，请移除环境变量`, EXIT_USAGE);
      throw new DispatchError(`${envName}=${envValue} 与合同 executor.${field}=${s(explicit)} 冲突；以审阅过的合同为准，请移除环境变量`, EXIT_USAGE);
    }
    if (!pyTruthy(explicit)) executor.set(field, envValue);
  }
  for (const field of ["provider", "model"]) {
    const value = executor.get(field) ?? null;
    if (!pyTruthy(value) || !MODEL_TOKEN_RE.test(s(value)) || PLACEHOLDER_RE.test(s(value))) {
      throw new DispatchError(`缺少或无效的执行模型 ${field}：在合同 executor 中填写，或设置 PI_EXEC_${field.toUpperCase()}`, EXIT_USAGE);
    }
  }
  const thinking = executor.get("thinking") ?? null;
  if (!(typeof thinking === "string" && FALLBACK_THINKING_LEVELS.includes(thinking))) throw new DispatchError(`无效的思考级别：${pyReprValue(thinking)}`, EXIT_USAGE);
  const problem = allowedExecutorCheck(config, executor.get("provider") ?? null, executor.get("model") ?? null, thinking);
  if (problem !== null && problem[0] === "missing") {
    throw new DispatchError(`执行模型 ${s(executor.get("provider"))}/${s(executor.get("model"))} 不在 .agent/dispatch.config.json 的 allowed_executors 中`, EXIT_BLOCKED);
  }
  if (problem !== null) throw new DispatchError(`该执行模型的思考级别固定为 ${s(problem[1])}，${source ?? "合同"}为 ${thinking}`, EXIT_BLOCKED);
  return executor;
}

/** resolve_bound_executor：provider、model、thinking 取自版本记录，其余取自合同；再过与写死合同相同的两项检查。 */
export function resolveBoundExecutor(contract: PyDict, record: PyDict, config: PyDict): PyDict {
  const fields = new Map<string, PyValue>(["provider", "model", "thinking"].map((key) => [key, record.get(key) ?? null]));
  const executor = new Map([...(contract.get("executor") as PyDict)].filter(([key]) => key !== "role"));
  for (const [key, value] of fields) executor.set(key, value);
  const bound = new Map(contract).set("executor", executor).set("_raw_executor", fields);
  return resolveExecutor(bound, config, `${s(record.get("role"))} 角色绑定的版本记录`);
}

/** _role_binding_candidate：prepare 预检时的执行模型（候选, 是否已有记录）。已有有效记录就以它为准；没有时当前绑定必须有效。 */
export function roleBindingCandidate(repo: Repo, role: string, config: PyDict, taskId: string, version: bigint, roles: BindingRoles | null): [PyDict, boolean] {
  const existing = loadBindingRecord(repo.root, taskId, version);
  if (existing !== null) return [existing, true];
  if (roles === null) throw new DispatchError(NO_KIT_ROLES, EXIT_USAGE);
  const [value, error] = roles.resolveRoleExecutor(config, role);
  if (error !== null) throw new DispatchError(error.message, error.code);
  return [value as PyDict, false];
}

/** _binding_drift_note：已有版本记录、当前绑定却与它不同时的提示；只读配置。 */
export function bindingDriftNote(config: PyDict, role: string, record: PyDict, roles: BindingRoles | null): string | null {
  if (roles === null) return null;
  const [value] = roles.resolveRoleExecutor(config, role);
  const keep = `${s(record.get("provider"))}/${s(record.get("model"))} · thinking ${s(record.get("thinking"))}`;
  if (value === null) return `当前没有可用的 ${role} 绑定；本版本沿用版本记录（${keep}）`;
  if (["provider", "model", "thinking"].some((key) => !pyEq(value.get(key) ?? null, record.get(key) ?? null))) {
    return `${role} 绑定已改为 ${s(value.get("provider"))}/${s(value.get("model"))} · thinking ${s(value.get("thinking"))}（profile ${s(value.get("profile"))}）；本版本沿用 ${keep}；要用新绑定，出新版本合同`;
  }
  return null;
}

/**
 * _written_binding_note：写死模型的合同，配置了 execution 的 headless 绑定、而它与合同解析出的执行模型有任何一项不同时，
 * 打 NOTE 并返回 meta 的 executor_binding_note。没有 v3 键、v3 键校验不过时不比较；从不阻塞。
 */
export function writtenBindingNote(config: PyDict, resolved: PyDict, roles: BindingRoles | null, out: Pick<PyOut, "print">): PyDict | null {
  if (!V3_CONFIG_KEYS.some((key) => config.has(key))) return null;
  if (roles === null || roles.configErrors(config).length) return null;
  const binding = roles.bindingTuple(config, "execution");
  if (binding === null) return null;
  const [mode, profileId, , , provider, model, thinking] = binding as (string | null)[];
  if (mode !== "headless" || !provider || !model) return null;
  const wanted = [resolved.get("provider") ?? null, resolved.get("model") ?? null, resolved.get("thinking") ?? null];
  if (pyEq([provider, model, thinking ?? null], wanted)) return null;
  out.print(`NOTE  合同写死执行模型 ${s(wanted[0])}/${s(wanted[1])} · thinking ${s(wanted[2])}；execution 绑定是 ${provider}/${model} · thinking ${s(thinking ?? null)}（profile ${s(profileId ?? null)}），本次按合同`);
  return new Map<string, PyValue>([
    ["role", "execution"],
    ["profile", profileId ?? null],
    ["binding", new Map<string, PyValue>([["provider", provider], ["model", model], ["thinking", thinking ?? null]])],
  ]);
}

/** TaskLock 的 with：占用时照 Python 报 DispatchError。 */
export function withTaskLock<T>(repo: Repo, taskId: string, body: () => T): T {
  let lock: TaskLock;
  try {
    lock = new TaskLock(repo.runsDir, taskId).acquire();
  } catch (error) {
    if (error instanceof LockBusyError) throw new DispatchError(error.message);
    throw error;
  }
  try {
    return body();
  } finally {
    lock.release();
  }
}

/**
 * _publish_binding_record：冻结合同之后发布或读取版本记录。已有就校验后采用；没有就用冻结的合同与同一份配置字节构造，
 * 以不覆盖的方式发布，别人抢先就重新读取胜者。最后统一核对合同哈希、环境变量与允许列表。
 */
export function publishBindingRecord(
  repo: Repo, role: string, frozenJson: Uint8Array, frozenContract: PyDict, config: PyDict, configBytes: Uint8Array | null,
  taskId: string, version: bigint, attemptNo: bigint, roles: BindingRoles | null,
): PyDict {
  const rel = bindingRecordRel(taskId, version);
  const contractSha = sha256(frozenJson);
  const record = withTaskLock(repo, taskId, () => {
    const existing = loadBindingRecord(repo.root, taskId, version);
    if (existing !== null) return existing;
    if (roles === null) throw new BindingRecordError(NO_KIT_ROLES, EXIT_USAGE);
    const [value, error] = roles.resolveRoleExecutor(config, role);
    if (error !== null) throw new BindingRecordError(error.message, error.code);
    const candidate = new Map(value as PyDict)
      .set("contract_json_sha256", contractSha)
      .set("created_at", utcNow())
      .set("created_by_attempt", `attempt-${String(attemptNo).padStart(3, "0")}`)
      .set("config_sha256", configBytes !== null ? sha256(configBytes) : null);
    const data = Buffer.from(`${dumps(candidate, { ensureAscii: false, indent: 2, sortKeys: true })}${String.fromCharCode(10)}`, "utf8");
    let published: boolean;
    try {
      published = pyPublishNew(join(repo.root, rel), data);
    } catch (error) {
      if (!(error instanceof PyOSError || error instanceof PyWinError)) throw error;
      throw new BindingRecordError(`版本记录写不进去（${rel}）：${error.message}；.agent/runs 所在的文件系统要支持不覆盖的原子发布`, EXIT_BLOCKED);
    }
    const chosen = published ? candidate : loadBindingRecord(repo.root, taskId, version);
    if (chosen === null) throw new BindingRecordError(`版本记录发布失败、又读不到（${rel}）`, EXIT_DRIFT);
    return chosen;
  });
  if (!pyEq(record.get("contract_json_sha256") ?? null, contractSha)) {
    throw new BindingRecordError(`合同 v${version} 的字节与首次派遣时不同（版本记录 ${rel}）：已派遣的版本不能改，出新版本合同`, EXIT_DRIFT);
  }
  try {
    resolveBoundExecutor(frozenContract, record, config); // 对最终选定的记录重做两项检查
  } catch (error) {
    if (error instanceof BindingRecordError || !(error instanceof DispatchError)) throw error;
    throw new BindingRecordError(error.message, error.code);
  }
  return record;
}
