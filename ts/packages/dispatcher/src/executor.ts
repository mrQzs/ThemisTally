// pi_dispatch 的执行模型判定（迁移第 ③c 片，配置中心用到的部分）：executor_class、allowed_executor_check、按合同版本的
// 执行模型记录（load_binding_record）、resolve_pi_command（不带 runtime 的那一种；带 runtime 时读本机文件，第 ④ 步再接）。
import { lstatSync, statSync } from "node:fs";
import { join } from "node:path";
import { pyTruthy } from "@themis/base/pyfmt";
import { PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes, pyOSErrorType, PyOSError } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { firstLinkComponent, purePathParent, purePathStr } from "@themis/base/pypath";
import { pyLstatStrerror } from "@themis/base/pyos";
import { pyLower } from "@themis/base/pyre";
import { pyWhich } from "@themis/base/pyshutil";
import { pyEq } from "@themis/base/pyvalue";
import { secretLikePaths } from "@themis/base/secrets";
import { DispatchError, EXIT_USAGE } from "./repo.ts";

export const EXIT_DRIFT = 4;
export const DEFAULT_THINKING = "high";

/** 版本记录在冻结合同之后出的错（退出码 EXIT_DRIFT）。 */
export class BindingRecordError extends DispatchError {}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

/** role：写了 role；written：provider 与 model 都为真值；legacy：其余。 */
export function executorClass(raw: PyValue | undefined): "role" | "written" | "legacy" {
  if (!isDict(raw)) return "legacy";
  if (raw.has("role")) return "role";
  return pyTruthy(raw.get("provider") ?? null) && pyTruthy(raw.get("model") ?? null) ? "written" : "legacy";
}

/**
 * allowed_executors 的判定：列表为空或通过时 null；不在列表里 ["missing", null]；第一条匹配项固定的 thinking 与之不同
 * ["thinking", 固定的级别]。调用方先整份校验过配置，allowed_executors 是对象的列表。
 */
export function allowedExecutorCheck(config: PyDict, provider: PyValue, model: PyValue, thinking: PyValue): [string, PyValue] | null {
  const allowlist = config.get("allowed_executors") ?? null;
  if (!pyTruthy(allowlist)) return null;
  const hits = (Array.isArray(allowlist) ? allowlist : []).filter(
    (item): item is PyDict => isDict(item) && pyEq(item.get("provider") ?? null, provider) && pyEq(item.get("model") ?? null, model),
  );
  if (!hits.length) return ["missing", null];
  const pinned = (hits[0] as PyDict).get("thinking") ?? null;
  return pyTruthy(pinned) && !pyEq(pinned, thinking) ? ["thinking", pinned] : null;
}

export function bindingRecordRel(taskId: string, version: bigint): string {
  return `.agent/runs/${taskId}/binding-v${version}.json`;
}

/** 版本记录的必填字段（都是字符串）；active_preset、config_sha256 必须在，可以是 null。 */
const RECORD_FIELDS = ["role", "profile", "runtime", "adapter", "provider", "model", "thinking", "contract_json_sha256", "created_at", "created_by_attempt"];
const NULLABLE_FIELDS = ["active_preset", "config_sha256"];

/** 一个合同版本的执行模型记录：不存在是 null；经过链接、看不了、读不出、字段不全或有疑似凭据都抛 BindingRecordError。 */
export function loadBindingRecord(root: string, taskId: string, version: bigint): PyDict | null {
  const rel = bindingRecordRel(taskId, version);
  const link = firstLinkComponent(root, rel);
  if (link !== null) throw new BindingRecordError(`版本记录经过链接或 junction，不读取：${link}`, EXIT_DRIFT);
  const path = join(root, rel);
  try {
    lstatSync(path);
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT" || code === "ENOTDIR") return null;
    throw new BindingRecordError(`版本记录看不了（${rel}：${pyLstatStrerror(error)}）；不能当作没有记录`, EXIT_DRIFT);
  }
  let data: PyValue;
  try {
    data = loads(pyDecodeUtf8(pyReadBytes(path)));
  } catch (error) {
    const name = error instanceof PyOSError ? pyOSErrorType(error) : error instanceof PyUnicodeDecodeError ? error.name : error instanceof PyJsonError && error.kind !== "RecursionError" ? error.kind : null;
    if (name === null) throw error;
    throw new BindingRecordError(`版本记录无效（${rel}）：${name}；确认后删除它，或出新版本合同`, EXIT_DRIFT);
  }
  if (!isDict(data) || RECORD_FIELDS.some((key) => typeof data.get(key) !== "string") || !NULLABLE_FIELDS.every((key) => data.has(key) && (data.get(key) === null || typeof data.get(key) === "string"))) {
    throw new BindingRecordError(`版本记录无效（${rel}）：字段不全或类型不对；确认后删除它，或出新版本合同`, EXIT_DRIFT);
  }
  const secret = secretLikePaths(data);
  if (secret.length) throw new BindingRecordError(`版本记录无效（${rel}）：有疑似凭据（${secret.slice(0, 5).join("、")}）；确认后删除它，或出新版本合同`, EXIT_DRIFT);
  return data;
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

const BS = String.fromCharCode(92);
/** npm 的 .cmd 包装里入口脚本的写法："%dp0%\…\cli.js"（re.I：i 加 u 才与 Python 一样让 s 也配 ſ）。 */
const SHIM_SCRIPT = new RegExp(`"%dp0%${BS}${BS}([^"]+?${BS}.(?:c|m)?js)"`, "iu");

/** CPython 的 errors="replace" 与 TextDecoder 一样按最大子部分换成 U+FFFD；读文本再做通用换行。 */
function readShim(path: string): string {
  try {
    return new TextDecoder("utf-8", { ignoreBOM: true }).decode(pyReadBytes(path)).replace(/\r\n?/gu, "\n");
  } catch (error) {
    if (error instanceof PyOSError) return "";
    throw error;
  }
}

/**
 * pi_dispatch.resolve_pi_command()（不带 runtime）：PI_DISPATCH_PI_CMD；否则 PATH 上的 pi，Windows 上是 npm 的 .cmd 包装时
 * 绕过它，直接用 node 运行入口脚本（包装旁边的 node.exe 优先）。
 */
export function resolvePiCommand(): string[] {
  const override = process.env["PI_DISPATCH_PI_CMD"];
  if (override) {
    let value: PyValue;
    try {
      value = loads(override);
    } catch (error) {
      if (!(error instanceof PyJsonError) || error.kind === "RecursionError") throw error;
      value = [override];
    }
    if (!(Array.isArray(value) && value.length && value.every((part) => typeof part === "string" && part))) {
      throw new DispatchError("PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组或单个可执行文件路径", EXIT_USAGE);
    }
    return value as string[];
  }
  const exe = pyWhich("pi");
  if (!exe) throw new DispatchError("PATH 中找不到 pi；请安装 @earendil-works/pi-coding-agent 或设置 PI_DISPATCH_PI_CMD");
  const lower = pyLower(exe);
  if (process.platform === "win32" && (lower.endsWith(".cmd") || lower.endsWith(".bat"))) {
    const match = SHIM_SCRIPT.exec(readShim(exe));
    if (match) {
      const parent = purePathParent(exe);
      const script = purePathStr(parent, match[1] as string);
      const localNode = purePathStr(parent, "node.exe");
      const node = isFile(localNode) ? localNode : pyWhich("node");
      if (isFile(script) && node) return [node, script];
    }
  }
  return [exe];
}
