// 交差核对与工人环境（迁移第 ⑤d 片）：kit_hub.py 的 delivery_files、_file_sha256、DELIVERY_SHA256、role_schema、delivered_output、
// interface_problem、delivery_problem、worker_file_problem 与 worker_env。
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { pyEq } from "@themis/base/pyvalue";
import { pyGet, pyItem, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { pyReadText } from "@themis/base/pyio";
import { type PyDict, type PyKey, type PyValue, loads } from "@themis/base/pyjson";
import { purePathStr } from "@themis/base/pypath";
import { globPaths } from "@themis/dispatcher/instruction";
import { childEnv } from "@themis/dispatcher/pi-cli";
import { comparePaths } from "./audit.ts";
import { LETTER_KEYS, STRUCTURED_TOOL, WORKER_ENV_DROP } from "./constants.ts";
import { DELIVER_EXTENSION, GUARD_EXTENSION, SCHEMA_DIR } from "./kernel.ts";
import { schemaErrors, schemaProblems } from "./schema.ts";

/** 交差工具的文件（第 90 轮）：pi 扩展与各岗位的 schema；守卫扩展（第 106 轮）同样在工人进程里跑，一并算。 */
export function deliveryFiles(): string[] {
  return [DELIVER_EXTENSION, GUARD_EXTENSION, ...globPaths(SCHEMA_DIR, ["*.json"]).sort(comparePaths)];
}

/** 文件内容的 sha256；读不到（OSError）是 null。 */
export function fileSha256(path: string): string | null {
  try {
    return createHash("sha256").update(readFileSync(path)).digest("hex");
  } catch {
    return null;
  }
}

/** 本进程载入时交差工具各文件的哈希（第 90 轮）：起 pi 之前核对，被改过就不起。supervisor 换代重启时跟着换。 */
export const DELIVERY_SHA256: ReadonlyMap<string, string | null> = new Map(deliveryFiles().map((path) => [basename(path), fileSha256(path)]));

/** 一个岗位的交差 schema（schemas/<岗位>.json）。 */
export function roleSchema(role: string): PyDict {
  const path = purePathStr(SCHEMA_DIR, `${role}.json`);
  return loads(pyReadText(path)) as PyDict;
}

/** 给模型看的交差 schema（第 169 轮）：letter 的中文键换成 LETTER_KEYS 的英文名，描述前面加上中文栏目名。协调人的 letters 不换。 */
export function toolSchema(role: string): PyDict {
  const schema = roleSchema(role);
  const letter = pyGet(pyTruthy(pyGet(schema, "properties")) ? pyGet(schema, "properties") : new Map(), "letter");
  if (!(letter instanceof Map)) return schema;
  const english = new Map<PyKey, string>(LETTER_KEYS.map(([name, chinese]) => [chinese, name]));
  const properties: PyDict = new Map();
  const listed = pyGet(letter, "properties");
  for (const [key, sub] of (pyTruthy(listed) ? listed as PyDict : new Map<string, PyValue>()).entries()) {
    let value = sub;
    if (english.has(key)) {
      const description = pyGet(sub, "description");
      value = new Map(sub as PyDict);
      value.set("description", pyTruthy(description) ? `${key}：${pyStrValue(pyItem(sub, "description"))}` : key);
    }
    properties.set(english.get(key) ?? key, value);
  }
  letter.set("properties", properties);
  const required = pyGet(letter, "required");
  letter.set("required", (pyTruthy(required) ? required as PyValue[] : []).map((key) => english.get(key as string) ?? key));
  return schema;
}

/** 交上来的 letter 里认得的英文键换回中文栏目（第 169 轮）。同名的中文键已经在时不换，留给复核报“多了”；中文键照收。 */
export function chineseLetter(delivered: PyDict): PyDict {
  const letter = pyGet(delivered, "letter");
  if (!(letter instanceof Map)) return delivered;
  const chinese = new Map<PyKey, string>(LETTER_KEYS);
  const renamed: PyDict = new Map();
  for (const [key, value] of letter.entries()) {
    const target = chinese.get(key);
    renamed.set(target !== undefined && !letter.has(target) ? target : key, value);
  }
  const out: PyDict = new Map(delivered);
  out.set("letter", renamed);
  return out;
}

/** 没交上（第 169 轮）：退回过就写明几次与最后一次的原因，没退回过按载体说没交哪个工具。 */
export function noDeliveryProblem(adapter: string, audit: PyValue): string {
  const listed = pyGet(audit, "deliver_refusals");
  const refusals = pyTruthy(listed) ? (listed as PyValue[]).length : 0;
  if (refusals) {
    const last = pyGet(audit, "deliver_last_refusal");
    return `这一回合交差被退回 ${refusals} 次，没有交上；最后一次退回的原因：${pyTruthy(last) ? pyStrValue(last) : "（没读到）"}`;
  }
  const how = adapter === "claude" ? `用 ${STRUCTURED_TOOL} 交差` : "调用 deliver 工具交差";
  return `这一回合没有${how}（消息里的 json 代码块内核不读）`;
}

/**
 * 用 deliver 交差的回合的输出（第 90 轮）：最后一次成功的 deliver 的参数，内核再按同一份 schema 复核一遍。
 * 没交或复核不过都按“输出不合格”走。交回（输出，问题）。
 */
export function deliveredOutput(role: string, delivered: PyValue, adapter = "pi", audit: PyValue = null): [PyValue, string | null] {
  if (delivered === null) return [null, noDeliveryProblem(adapter, audit ?? new Map())];
  if (delivered instanceof Map) delivered = chineseLetter(delivered);
  const errors = schemaErrors(roleSchema(role), delivered);
  if (errors.length) return [null, `deliver 交上来的参数内核复核不过：${errors.slice(0, 8).join("；")}`];
  return [delivered, null];
}

/**
 * 不是工人的错、重试与返工都白费的两种“没交上”（第 110 轮），按接口报错直接交给站主：交差工具报了成功、内核却读不到参数；
 * pi 一条回复都没有就以非零码退出。
 */
export function interfaceProblem(spec: PyValue, audit: PyValue, result: PyValue): string | null {
  if (pyGet(audit, "delivered") === null && pyTruthy(pyGet(audit, "delivered_unreadable"))) {
    return `交差工具报了成功，内核读不到参数（${pyStrValue(pyItem(audit, "delivered_unreadable"))}）：pi 或 claude 的接口可能变了，看版本与这一回合的事件流`;
  }
  const code = pyGet(result, "exit_code");
  if (pyEq(pyItem(spec, "adapter"), "pi") && !pyTruthy(pyGet(audit, "models")) && !(code === null || pyEq(code, 0n)) && !pyTruthy(pyGet(result, "timed_out"))) {
    return `pi 一条回复都没有就以退出码 ${pyStrValue(pyItem(result, "exit_code"))} 结束（扩展加载失败、参数不认……看这一回合的 stderr.log）`;
  }
  return null;
}

/** 起 pi 之前核对交差工具（第 90 轮）：扩展与这个岗位的 schema 都在，哈希与本进程载入时一致，schema 只用子集。 */
export function deliveryProblem(role: string): string | null {
  for (const path of [DELIVER_EXTENSION, purePathStr(SCHEMA_DIR, `${role}.json`)]) {
    const problem = workerFileProblem(path);
    if (problem) return problem;
  }
  const problems = schemaProblems(roleSchema(role));
  return problems.length ? `交差 schema 用了内核复核不了的写法：${problems.join("；")}` : null;
}

/** 在工人进程里跑的内核文件（deliveryFiles）不在，或与本进程载入时的哈希不一致。 */
export function workerFileProblem(path: string): string | null {
  const now = fileSha256(path);
  if (now === null) return `交差工具的文件不在：${path}，没有起这一回合`;
  const loaded = DELIVERY_SHA256.get(basename(path)) ?? null;
  if (now !== loaded) {
    return `交差工具的文件被改过：${path}（载入时 ${pyStrValue(loaded).slice(0, 12)}，现在 ${now.slice(0, 12)}），没有起这一回合。内核刚合入新的一轮就等 supervisor `
      + "用新代码重启；不是的话，查是谁改的";
  }
  return null;
}

/** 工人进程的环境：调度器的过滤（推送类凭据、仓库重定向变量、配置的 env_remove）之外，再去掉决策 API 的 key 与宿主会话变量。 */
export function workerEnv(config: PyDict | null = null): Map<string, string> {
  const [env] = childEnv(config ?? new Map());
  for (const name of [...env.keys()]) if (WORKER_ENV_DROP.includes(name.toUpperCase())) env.delete(name);
  return env;
}
