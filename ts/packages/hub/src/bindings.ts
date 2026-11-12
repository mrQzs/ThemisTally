// 第 154 轮：配置中心里七端各岗位的绑定（kit_hub.py 的 hub_bindings、bound_spec、executor_line）。
// 岗位的工具、时限、工作目录、流转方式是安全边界，留在名册里；配置只决定载体、提供方、模型、档位与替补。
import { pyStrValue } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { HUB_POSTS, configErrors, hubBinding } from "@themis/config/roles-check";
import { configWithBytes } from "@themis/dispatcher/kernel-config";
import { DispatchError, Repo } from "@themis/dispatcher/repo";
import { EXECUTOR, ROSTER, type RosterSpec } from "./constants.ts";

/** {岗位: kit_roles.hub_binding 的结果}，没配的岗位不在里面。 */
export type HubBindings = ReadonlyMap<string, PyDict>;

/**
 * kit_hub.hub_bindings：配置读不了、没有 hub_roles 这一段、整份校验不过，都当作没配：照名册的缺省跑，
 * 不让一份坏配置把枢纽停下。
 */
export function hubBindings(repo: string): HubBindings {
  let config: PyDict;
  try {
    config = configWithBytes(new Repo(repo))[0];
  } catch (error) {
    if (error instanceof DispatchError) return new Map();
    throw error;
  }
  if (!(config.get("hub_roles") instanceof Map)) return new Map();
  if (configErrors(config).length) return new Map();
  const found = new Map<string, PyDict>();
  for (const post of HUB_POSTS) {
    const binding = hubBinding(config, post);
    if (binding !== null) found.set(post, binding);
  }
  return found;
}

/**
 * kit_hub.bound_spec：名册里这个岗位的配置，叠上配置中心的绑定。键的先后照 Python 的 dict：改已有的键位置不变，
 * 新加的键排在末尾。执行端的载体永远是调度器，绑定只决定合同里的执行模型。
 */
export function boundSpec(agent: string, binding: PyDict | null | undefined): RosterSpec {
  const spec: Record<string, unknown> = { ...(ROSTER[agent] as RosterSpec) };
  if (binding == null || binding.size === 0) return spec as unknown as RosterSpec;
  const carrier = binding.get("adapter") ?? null;
  const adapter = carrier === "claude-code" ? "claude" : carrier;
  if (spec["adapter"] !== "dispatcher") spec["adapter"] = adapter;
  spec["model"] = binding.get("model") ?? null;
  if (adapter === "claude") {
    delete spec["provider"];
    delete spec["thinking"];
    spec["effort"] = binding.get("thinking") ?? null;
  } else {
    delete spec["effort"];
    spec["provider"] = binding.get("provider") ?? null;
    spec["thinking"] = binding.get("thinking") ?? null;
  }
  delete spec["fallback"];
  const substitute = binding.get("fallback");
  if (adapter === "quizs" && substitute instanceof Map && substitute.size > 0) {
    spec["fallback"] = {
      adapter: "pi",
      provider: substitute.get("provider") ?? null,
      model: substitute.get("model") ?? null,
      thinking: substitute.get("thinking") ?? null,
    };
  }
  spec["binding_profile"] = binding.get("profile") ?? null;
  return spec as unknown as RosterSpec;
}

/** kit_hub.executor_line：合同里执行模型的三元组与那一行的写法：执行端绑了 profile 就照它，没绑照名册。 */
export function executorLine(bindings: HubBindings | null = null): [readonly [PyValue, PyValue, PyValue], string] {
  const binding = bindings?.get("exec");
  const triple: readonly [PyValue, PyValue, PyValue] = binding
    ? [binding.get("provider") ?? null, binding.get("model") ?? null, binding.get("thinking") ?? null]
    : EXECUTOR;
  return [triple, `- executor: ${pyStrValue(triple[0])}/${pyStrValue(triple[1])} · thinking ${pyStrValue(triple[2])}`];
}
