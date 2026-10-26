// kit_roles.py 的本机文件与 runtime 命令的解析（迁移第 ③c 片，D3）。本机文件 .agent/dispatch.local.json 只放命令路径：
// 从仓库根到它的每一级都不能是链接，不能被 Git 跟踪，必须被忽略；有疑似凭据或形状不对时整份不用。只读，不运行任何命令。
// 混合期 pi_dispatch 在进程内调用 local_command，两边对同一份本机文件要得出同样的命令与报错（本机文件契约）。
import { lstatSync } from "node:fs";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyOSErrorType, pyReadBytes } from "@themis/base/pyio";
import { firstLinkComponent } from "@themis/base/pypath";
import { pyLstatStrerror } from "@themis/base/pyos";
import { pyWhich } from "@themis/base/pyshutil";
import { redactSecrets, secretLikePaths } from "@themis/base/secrets";
import { resolvePiCommand } from "@themis/dispatcher/executor";
import { DispatchError, git } from "@themis/dispatcher/repo";
import { joinPath } from "./decisions.ts";
import { ADAPTERS, adapterOf, entries, extraKeys, idOk, shownValue } from "./roles-check.ts";

export const LOCAL_NAME = "dispatch.local.json";
export const LOCAL_REL = `.agent/${LOCAL_NAME}`;
const LOCAL_SHAPE = '只接受 {"runtimes": {"<id>": {"command": ["<程序>", "<参数>", …]}}}';

export interface LocalRepo {
  readonly root: string;
  readonly agentDir: string;
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

/** os.lstat：不存在（ENOENT、ENOTDIR）时 false，其余错误照抛。 */
export function lexists(path: string): boolean {
  try {
    lstatSync(path);
    return true;
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT" || code === "ENOTDIR") return false;
    throw error;
  }
}

/** 本机文件能不能用：从仓库根到它的每一级都不是链接、不被 Git 跟踪、已被忽略。返回问题，空表示可用。 */
export function checkLocal(repo: LocalRepo): string[] {
  try {
    const link = firstLinkComponent(repo.root, LOCAL_REL);
    if (link !== null) return [`${LOCAL_REL} 经过链接或 junction（${link}），不使用`];
    const problems: string[] = [];
    if (git(["ls-files", "--error-unmatch", "--", LOCAL_REL], repo.root).status === 0) {
      problems.push(`${LOCAL_REL} 被 Git 跟踪，不使用：本机文件不进提交（git rm --cached ${LOCAL_REL}）`);
    }
    if (git(["check-ignore", "-q", "--", LOCAL_REL], repo.root).status !== 0) {
      problems.push(`${LOCAL_REL} 没有被 .gitignore 忽略，不使用：运行 kit_install update 补上 kit 的忽略规则`);
    }
    return problems;
  } catch (error) {
    if (error instanceof DispatchError) return [`${LOCAL_REL} 无法核对（${error.message}），不使用`];
    throw error;
  }
}

/** 本机文件内容的问题：疑似凭据（只报位置）与形状；空表示可用。读与写（runtime add --command）共用。 */
export function localErrors(data: PyValue): string[] {
  const secret = secretLikePaths(data);
  if (secret.length) return [`${LOCAL_REL} 里有疑似凭据（${secret.slice(0, 5).join("、")}），不使用`];
  const runtimes = isDict(data) ? (data.has("runtimes") ? data.get("runtimes") : new Map()) : null;
  if (!isDict(data) || extraKeys(data, ["runtimes"]).length || !isDict(runtimes)) return [`${LOCAL_REL} ${LOCAL_SHAPE}，不使用`];
  const errors: string[] = [];
  for (const [runtimeId, spec] of entries(runtimes)) {
    const command = isDict(spec) ? spec.get("command") : undefined;
    const valid =
      idOk(runtimeId) &&
      isDict(spec) &&
      !extraKeys(spec, ["command"]).length &&
      Array.isArray(command) &&
      command.length > 0 &&
      command.every((part) => typeof part === "string" && part !== "");
    if (!valid) errors.push(`${LOCAL_REL} 的 runtimes.${shownValue(runtimeId)} 不合法（${LOCAL_SHAPE}）`);
  }
  return errors;
}

export interface LocalRead {
  /** {runtime ID: 命令}；有错误时为 null，整份不使用。 */
  readonly commands: Map<string, string[]> | null;
  readonly errors: string[];
  readonly warnings: string[];
}

/** 读本机文件。不存在时命令表为空；疑似凭据同样是错误；提交的配置里没有登记的 runtime ID 是警告。 */
export function readLocal(repo: LocalRepo, config: PyDict): LocalRead {
  const path = joinPath(repo.agentDir, LOCAL_NAME);
  try {
    if (!lexists(path)) return { commands: new Map(), errors: [], warnings: [] };
  } catch (error) {
    return { commands: null, errors: [`${LOCAL_REL} 看不了（${pyLstatStrerror(error)}），不使用`], warnings: [] };
  }
  const problems = checkLocal(repo);
  if (problems.length) return { commands: null, errors: problems, warnings: [] };
  let data: PyValue;
  try {
    data = loads(pyDecodeUtf8(pyReadBytes(path)));
  } catch (error) {
    const name = error instanceof PyOSError ? pyOSErrorType(error) : error instanceof PyUnicodeDecodeError || error instanceof PyJsonError ? error.name : null;
    if (name === null) throw error;
    return { commands: null, errors: [`${LOCAL_REL} 读不出来（${name}），不使用`], warnings: [] };
  }
  const errors = localErrors(data);
  if (errors.length) return { commands: null, errors, warnings: [] };
  const runtimes = (data as PyDict).get("runtimes");
  const commands = new Map<string, string[]>(
    entries(isDict(runtimes) ? runtimes : new Map()).map(([runtimeId, spec]) => [runtimeId, [...((spec as PyDict).get("command") as string[])]]),
  );
  const registered = isDict(config.get("runtimes")) ? (config.get("runtimes") as PyDict) : new Map();
  const warnings = [...commands.keys()].filter((runtimeId) => !registered.has(runtimeId)).map((runtimeId) => `${LOCAL_REL} 的 runtime ${shownValue(runtimeId)} 没有在配置的 runtimes 里登记`);
  return { commands, errors: [], warnings };
}

/** runtime 在本机文件里的命令与要打印的提示行（“ERROR …”“WARN  …”）；没有这一项、或本机文件不可用时命令为 null。 */
export function localCommand(repo: LocalRepo, config: PyDict, runtime: string): { command: string[] | null; lines: string[] } {
  const { commands, errors, warnings } = readLocal(repo, config);
  const lines = [...errors.map((message) => `ERROR ${message}`), ...warnings.map((message) => `WARN  ${message}`)];
  return { command: commands?.get(runtime) ?? null, lines };
}

export interface RuntimeCommand {
  readonly command: string[] | null;
  /** env、local、path 或 missing。 */
  readonly source: string;
  readonly lines: string[];
}

/**
 * runtime 的命令、来源与提示行，按 D3 的解析顺序：PI_DISPATCH_PI_CMD（只对 pi 适配器）→ 本机文件 → PATH。只读，不运行命令。
 * adapter 给出时按它解析、不要求 runtime 仍在配置里登记（config doctor --record，第 ③d 片）。
 */
export function runtimeCommand(repo: LocalRepo, config: PyDict, runtimeId: PyValue, adapter: string | null = null): RuntimeCommand {
  const resolved = adapter !== null && Object.hasOwn(ADAPTERS, adapter) ? adapter : adapterOf(config, runtimeId);
  if (resolved === null) return { command: null, source: "missing", lines: [`ERROR runtime ${shownValue(runtimeId)} 没有登记（或它的 adapter 无效）`] };
  let lines: string[] = [];
  try {
    if (resolved === "pi" && process.env["PI_DISPATCH_PI_CMD"]) return { command: resolvePiCommand(), source: "env", lines };
    const local = localCommand(repo, config, String(runtimeId));
    lines = local.lines;
    if (local.command !== null) return { command: local.command, source: "local", lines };
    if (resolved === "pi") return { command: resolvePiCommand(), source: "path", lines };
  } catch (error) {
    if (error instanceof DispatchError) return { command: null, source: "missing", lines: [...lines, `ERROR ${error.message}`] };
    throw error;
  }
  const found = pyWhich((ADAPTERS[resolved] as { program: string }).program);
  return { command: found ? [found] : null, source: found ? "path" : "missing", lines };
}

/** 显示用的命令：每一段照 redact_secrets 脱敏；没有命令时 null。 */
export function shownCommand(command: string[] | null): string[] | null {
  return command && command.length ? command.map((part) => redactSecrets(part)) : null;
}
