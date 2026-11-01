// 两套实现并存（迁移计划第 ② 步、第 5 节）：选择文件，与 hub 账本里 dispatcher.called 记的是哪一套实现。pi_dispatch.py 的
// read_kernel_impl、argv_impl、config_argv_path 与几张转交名单的键（迁移第 ⑤e1b 片）。TS 调度器拿的是启动器交来的 kernelImpl，
// 不读选择文件；TS 的 hub 没有启动器在前面，要自己读，所以路径由调用方给。报错文字照 Python。
import { readFileSync } from "node:fs";
import { pyItem, pyRepr, pyReprValue } from "@themis/base/pyfmt";
import { type JsonBuilder, PY_BUILDER, PyJsonError, type PyDict, type PyValue, loadsWith } from "@themis/base/pyjson";
import { PyUnicodeDecodeError, pyDecodeUtf8, pyOSErrorOf } from "@themis/base/pyio";
import { purePathStr } from "@themis/base/pypath";
import { cmpCodePoints } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { DispatchError, EXIT_USAGE } from "./repo.ts";

export const KERNEL_IMPL_COMPONENTS = ["readonly", "config", "dispatcher", "hub"] as const;
export const KERNEL_IMPLS = ["python", "ts"] as const;

const key = (words: readonly string[]): string => JSON.stringify(words);
const table = (rows: readonly (readonly string[])[]): ReadonlySet<string> => new Set(rows.map(key));

/** 名单在 TS 这边只用到键（哪些命令由哪一套回答）；值是 Python 交给 TS 的参数键，用不上。契约逐张对照 Python 的键。 */
export const TS_READONLY_COMMANDS = table([["status"], ["logs", "list"], ["logs", "show"], ["logs", "cat"], ["logs", "search"], ["logs", "usage"]]);
export const TS_ONLY_COMMANDS = table([["ui"]]);
export const TS_CONFIG_COMMANDS = table([
  ["config", "show"], ["config", "validate"], ["config", "set"], ["config", "unset"], ["config", "history"], ["config", "rollback"], ["config", "init"],
  ["config", "decisions"], ["config", "secret"], ["config", "runtime", "list"], ["config", "runtime", "scan"], ["config", "runtime", "add"],
  ["config", "runtime", "remove"], ["config", "runtime", "probe"], ["config", "models"], ["config", "profile", "show"], ["config", "profile", "add"],
  ["config", "profile", "edit"], ["config", "profile", "remove"], ["config", "role", "show"], ["config", "role", "set"], ["config", "preset", "list"],
  ["config", "preset", "show"], ["config", "preset", "save"], ["config", "preset", "use"], ["config", "preset", "diff"], ["config", "preset", "remove"],
  ["config", "doctor"], ["plugins", "list"], ["plugins", "show"], ["plugins", "verify"], ["plugins", "enable"], ["plugins", "disable"],
]);
/** 配置中心命令的路径后两段由哪个 dest 给出（CONFIG_ACTION_DESTS 的前一半）。 */
export const CONFIG_ACTION_FAMILIES: ReadonlySet<string> = new Set(["runtime", "profile", "role", "preset"]);
export const TS_DISPATCHER_COMMANDS = table([
  ["doctor"], ["smoke"], ["validate"], ["derive-json"], ["baseline"], ["prepare"], ["run"], ["collect"], ["check"], ["mutate"], ["wait"],
  ["sync-adapters"], ["verdict"], ["status"], ["decisions"], ["decisions", "replay"], ["release-check"], ["metrics"], ["branch"], ["review-draft"],
  ["integrate"], ["mark"], ["cleanup"],
]);

/** object_pairs_hook：键重复就报 ValueError（json.loads 原样抛出，不包成 JSONDecodeError）。 */
const UNIQUE_KEYS: JsonBuilder<PyValue> = {
  ...PY_BUILDER,
  object(pairs) {
    const seen = new Set<string>();
    for (const [name] of pairs) {
      if (seen.has(name)) throw new PyJsonError("ValueError", `键 ${pyRepr(name)} 重复`);
      seen.add(name);
    }
    return PY_BUILDER.object(pairs);
  },
};

/**
 * 读选择文件。不存在等于全部 python；存在就严格解析：读不了、不是 JSON、键重复、多键少键、取值不是 python 或 ts、schema_version
 * 不是整数 1，都报错拒绝运行，不悄悄退回 python（否则运行中的内核与提交的选择对不上）。
 */
export function readKernelImpl(path: string): PyDict {
  const shown = purePathStr(path);
  let raw: Buffer;
  try {
    raw = readFileSync(path);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return new Map(KERNEL_IMPL_COMPONENTS.map((name) => [name, "python"]));
    const failure = pyOSErrorOf(error, shown);
    if (failure === null) throw error;
    throw new DispatchError(`选择文件读不了：${shown}（${failure.message}）；拒绝运行`, EXIT_USAGE);
  }
  let data: PyValue;
  try {
    data = loadsWith(pyDecodeUtf8(raw), UNIQUE_KEYS);
  } catch (error) {
    const readable = error instanceof PyUnicodeDecodeError || (error instanceof PyJsonError && error.kind !== "RecursionError");
    if (!readable) throw error;
    throw new DispatchError(`选择文件不是合法的 JSON：${shown}（${(error as Error).message}）；拒绝运行`, EXIT_USAGE);
  }
  const problem = kernelImplProblem(data);
  if (problem !== null) throw new DispatchError(`选择文件无效：${shown}：${problem}；拒绝运行（不退回 python）`, EXIT_USAGE);
  const valid = data as PyDict;
  return new Map(KERNEL_IMPL_COMPONENTS.map((name) => [name, valid.get(name) as PyValue]));
}

function kernelImplProblem(data: PyValue): string | null {
  const expected = ["schema_version", ...KERNEL_IMPL_COMPONENTS];
  if (!(data instanceof Map)) return "顶层不是对象";
  if (data.size !== expected.length || !expected.every((name) => data.has(name))) {
    return `键应当正好是 ${expected.join(", ")}，实际是 ${[...data.keys()].map(String).sort(cmpCodePoints).join(", ")}`;
  }
  const version = data.get("schema_version");
  if (typeof version !== "bigint" || version !== 1n) return `schema_version 应当是 1，实际是 ${pyReprValue(version as PyValue)}`;
  const bad = KERNEL_IMPL_COMPONENTS.filter((name) => !KERNEL_IMPLS.some((impl) => pyEq(data.get(name) as PyValue, impl)))
    .map((name) => `${name}=${pyReprValue(data.get(name) as PyValue)}`);
  return bad.length ? `取值只能是 python 或 ts：${bad.join("，")}` : null;
}

/** argv_impl 用：hub 写法的 config、plugins 命令在 TS_CONFIG_COMMANDS 里的路径（不解析选项）。 */
export function configArgvPath(words: readonly string[]): string[] {
  if (words.length < 2) return [];
  if (words[0] === "plugins") return ["plugins", words[1] as string];
  if (CONFIG_ACTION_FAMILIES.has(words[1] as string) && words.length >= 3) return ["config", words[1] as string, words[2] as string];
  return ["config", words[1] as string];
}

/**
 * 这条调度器命令由哪一套实现回答，hub 账本的 dispatcher.called 记它。只认 hub 的写法（可选的全局 --repo，之后是完整拼写的子命令），
 * 带 -h 的按 python 算；只有 TS 实现的命令总是 ts。impl 是 null 时读 implPath 的选择文件，次序照 Python：在 -h 与只有 TS 实现的命令
 * 判定之后才读，选择文件坏了时这两种照样交回、不报错。
 */
export function argvImpl(argv: readonly string[], impl: PyValue, implPath: string): string {
  let words = [...argv];
  while (words.length && (words[0] === "--repo" || (words[0] as string).startsWith("--repo="))) words = words[0] === "--repo" ? words.slice(2) : words.slice(1);
  if (words.includes("-h") || words.includes("--help")) return "python";
  if (TS_ONLY_COMMANDS.has(key(words.slice(0, 1)))) return "ts";
  const read = impl === null ? readKernelImpl(implPath) : impl;
  const chosen = (name: string): boolean => pyEq(pyItem(read, name), "ts");
  if (words[0] === "config" || words[0] === "plugins") {
    const listed = TS_CONFIG_COMMANDS.has(key(configArgvPath(words))) && !(words.length >= 3 && words[1] === "secret" && words[2] === "set");
    return chosen("config") && listed ? "ts" : "python";
  }
  const assess = words[0] === "status" && words.includes("--assess");
  if (assess || (words[0] !== "status" && TS_DISPATCHER_COMMANDS.has(key(words.slice(0, 1))))) return chosen("dispatcher") ? "ts" : "python";
  if (!chosen("readonly")) return "python";
  if (words[0] === "status") return words.includes("--assess") ? "python" : "ts";
  return words.length >= 2 && words[0] === "logs" && TS_READONLY_COMMANDS.has(key(["logs", words[1] as string])) ? "ts" : "python";
}
