// 第 ⑤c 片（迁移计划第 ⑤ 步）：回合审计。kit_hub.py 的 turn_cost_usd、jsonl_lines、stream_events、session_cut_short、
// claude_session_effort、claude_path_rule、audit_claude_stream、path_forms、pi_reach_problem、guard_config、audit_pi_stream、
// pi_supported_flags、pi_flags_problem。事件是 json.loads 读出来的任意值：取键、遍历、放进集合、排序都照 Python 的语义
// （不是字典时 .get 抛 AttributeError，放进集合的值不可散列时抛 TypeError），崩溃与 Python 同型；交回的字典键序与 Python 相同。
import { readText } from "@themis/base/fsutil";
import { jsonlLines } from "@themis/base/jsonl";
import { PyCrash, pyAdd, pyFloatOf, pyGet, pyItem, pyIter, pyReprValue, pyRound, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { type PyDict, type PyKey, PyJsonError, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { abspath, expanduser, normcase, ntIsabs, osPathJoin, purePathStr, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyLower, pyStrip } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { globPaths } from "@themis/dispatcher/instruction";
import { RESOURCE_FLAGS, parseHelp, runCapture } from "@themis/dispatcher/pi-cli";
import {
  CLAUDE_REACH_NAMES, DELIVER_TOOL, DEPENDENCY_DIRS, GUARD_PREFIX, GUARD_SUFFIX, READ_TOOLS, STRUCTURED_TOOL, UNREADABLE_STREAM,
} from "./constants.ts";

const BS = String.fromCharCode(92);
const WIN = process.platform === "win32";
const SEP = WIN ? BS : "/";
/** json.loads 抛的这几种，stream_events 当成读不出来的行；别的照样抛出。 */
const UNREADABLE_KINDS = new Set(["ValueError", "JSONDecodeError", "RecursionError"]);

/** （这一回合的花费，会话累计的花费）。claude 的 total_cost_usd 是会话累计值，减去上一回合记下的（第 16 轮）。 */
export function turnCostUsd(adapter: string, session: PyValue, reported: PyValue): [number | null, number | null] {
  if (reported === null) return [null, null];
  const total = pyFloatOf(reported);
  if (adapter !== "claude") return [total, null];
  const previous = pyGet(session, "cost_usd_total");
  if (previous === null || total < pyFloatOf(previous)) return [total, total];
  return [pyRound(total - pyFloatOf(previous), 6) as number, total];
}

/**
 * 逐行解析事件流，边读边交出；读不出来的非空行（不是 JSON、不是对象、嵌套太深）记进 counter。审计与会话的四处只走一遍，
 * 不留整个事件数组：30 MB 的事件流解析成 Map 留着要近 1 GB，逐条丢掉只要两百来 MB（⑤-影子量的）。
 */
export function* eachEvent(lines: readonly string[], counter: { unreadable: number }): Generator<PyDict> {
  for (const raw of lines) {
    const line = pyStrip(raw);
    if (!line) continue;
    let event: PyValue | undefined;
    try {
      event = loads(line);
    } catch (error) {
      if (!(error instanceof PyJsonError && UNREADABLE_KINDS.has(error.kind))) throw error;
    }
    if (event instanceof Map) yield event;
    else counter.unreadable += 1;
  }
}

/** kit_hub 的 stream_events：(事件, 读不出来的非空行数)。 */
export function streamEvents(lines: readonly string[]): [PyDict[], number] {
  const counter = { unreadable: 0 };
  return [[...eachEvent(lines, counter)], counter.unreadable];
}

/** 会话停在半截（第 94 轮）：最后一条消息是模型发出、还没有结果的工具调用。会话文件找不到不算。 */
export function sessionCutShort(hubRoot: string, agent: string, adapter: string, sessionId: string): boolean {
  const paths = adapter === "claude"
    ? globPaths(claudeProjects(), ["*", `${sessionId}.jsonl`])
    : globPaths(purePathStr(hubRoot, "sessions", agent), [`*_${sessionId}.jsonl`]);
  const last = paths.sort(comparePaths).at(-1);
  if (last === undefined) return false;
  const lines = jsonlLines(readText(last)).filter((line) => pyStrip(line));
  if (lines.length && !streamEvents(lines.slice(-1))[0].length) return true; // 最后一行没写完、读不出来：算半截
  const kinds = adapter === "claude" ? ["assistant", "user"] : ["message"];
  let entry: PyDict | undefined;
  for (const event of eachEvent(lines, { unreadable: 0 })) if (kinds.some((kind) => pyEq(pyGet(event, "type"), kind))) entry = event;
  if (entry === undefined) return false;
  const message = or(pyGet(entry, "message"), new Map());
  if (adapter === "claude") {
    const content = pyGet(message, "content");
    const blocks = Array.isArray(content) ? content : [];
    return pyEq(pyGet(entry, "type"), "assistant") && (pyEq(pyGet(message, "stop_reason"), "tool_use")
      || blocks.some((block) => block instanceof Map && pyEq(pyGet(block, "type"), "tool_use")));
  }
  return pyEq(pyGet(message, "role"), "assistant") && pyEq(pyGet(message, "stopReason"), "toolUse");
}

/** claude 的会话文件里每条 assistant 记录带 effort：读出实际生效的档位（设计 §6.1）。只看 glob 到的第一个文件。 */
export function claudeSessionEffort(sessionId: string): string | null {
  for (const path of globPaths(claudeProjects(), ["*", `${sessionId}.jsonl`])) {
    let effort: string | null = null;
    for (const entry of eachEvent(jsonlLines(readText(path)), { unreadable: 0 })) {
      if (pyEq(pyGet(entry, "type"), "assistant") && pyTruthy(pyGet(entry, "effort"))) effort = pyStrValue(pyItem(entry, "effort"));
    }
    return effort;
  }
  return null;
}

/** claude 权限规则里绝对路径的写法：`//c/Code/Repo/**`（盘符小写、正斜杠）。 */
export function claudePathRule(path: string): string {
  let text = pyResolve(purePathStr(path));
  if (WIN) text = text.split(BS).join("/");
  const chars = codePoints(text);
  if (chars.length > 1 && chars[1] === ":") text = pyLower(chars[0] as string) + chars.slice(2).join("");
  return `//${stripChars(text, "/")}/**`;
}

/** 读内核截下的 claude 事件流：白名单之外的工具、init 的工具与 MCP、模型，以及模型接口的报错。 */
export function auditClaudeStream(lines: readonly string[], spec: PyValue, workspace: string | null = null, repo: string | null = null): PyDict {
  const allowed = new PySet(pyIter(pyItem(spec, "tools")));
  const violations: string[] = [];
  const toolCalls: PyDict = new Map();
  let init: PyDict = new Map();
  let result: PyDict = new Map();
  const models = new PySet();
  let apiError: string | null = null;
  let rejectedUntil: PyValue = null; // 额度限制（rate_limit_event 的 rejected）解除的时刻
  const outside = new Map<string, string>(); // 白名单之外的 tool_use：id → 工具名
  const refused = new PySet();
  const structured = new PySet(); // StructuredOutput 的 tool_use id
  let accepted = 0n; // 其中被 CLI 收下的次数
  const refusals: PyValue[] = [];
  const counter = { unreadable: 0 };
  for (const event of eachEvent(lines, counter)) {
    const kind = pyGet(event, "type");
    if (pyEq(kind, "system") && pyEq(pyGet(event, "subtype"), "init")) {
      init = event;
    } else if (pyEq(kind, "assistant")) {
      const message = or(pyGet(event, "message"), new Map());
      if (pyTruthy(pyGet(message, "model"))) models.add(pyItem(message, "model"));
      if (pyTruthy(pyGet(event, "error")) || pyTruthy(pyGet(event, "is_api_error_message"))) {
        const text = joinStrings(blockTexts(pyGet(message, "content"), "text"));
        const status = or(pyGet(event, "api_error_status"), "");
        const code = or(or(pyGet(event, "api_error_code"), pyGet(event, "error")), "");
        apiError = `${pyStrValue(status)} ${pyStrValue(code)}：${firstCodePoints(pyStrip(text), 300)}`;
      } else if (!pyEq(pyGet(message, "model"), "<synthetic>")) {
        apiError = null; // 报错之后模型又正常回复了：以最后的为准
      }
      for (const block of pyIter(or(pyGet(message, "content"), []))) {
        if (!(block instanceof Map)) continue;
        const type = pyGet(block, "type");
        if (!(pyEq(type, "tool_use") || pyEq(type, "server_tool_use"))) continue;
        const name = pyStrValue(pyGet(block, "name"));
        count(toolCalls, name);
        if (name === STRUCTURED_TOOL) structured.add(pyGet(block, "id"));
        if (pyEq(type, "server_tool_use")) {
          violations.push(`调用了白名单之外的工具：${name}（${pyStrValue(type)}）`);
        } else if (!allowed.has(name)) {
          outside.set(pyStrValue(pyGet(block, "id")), name);
        } else if (workspace !== null && name !== STRUCTURED_TOOL) {
          const args = pyDictOf(or(pyGet(block, "input"), new Map()));
          if (args.has("file_path")) {
            const value = args.get("file_path") as PyValue;
            args.delete("file_path");
            args.set("path", value);
          }
          const [level, note] = piReachProblem(Object.hasOwn(CLAUDE_REACH_NAMES, name) ? (CLAUDE_REACH_NAMES[name] as string) : name, args.toDict(), workspace, repo);
          if (level === "violation") violations.push(note);
        }
      }
    } else if (pyEq(kind, "user")) {
      const content = pyGet(or(pyGet(event, "message"), new Map()), "content");
      for (const block of Array.isArray(content) ? content : []) {
        if (!(block instanceof Map && pyEq(pyGet(block, "type"), "tool_result"))) continue;
        const useId = pyGet(block, "tool_use_id");
        if (!pyTruthy(pyGet(block, "is_error"))) {
          if (structured.has(useId)) accepted += 1n; // CLI 收下了交差（第 110 轮）
          continue;
        }
        if (inKeys(outside, useId) && pyStrValue(pyGet(block, "content")).includes("No such tool available")) {
          refused.add(pyItem(block, "tool_use_id"));
        } else if (structured.has(useId)) {
          refusals.push(BigInt(codePoints(pyStrValue(or(pyGet(block, "content"), ""))).length));
        }
      }
    } else if (pyEq(kind, "rate_limit_event")) {
      const info = or(pyGet(event, "rate_limit_info"), new Map());
      rejectedUntil = pyEq(pyGet(info, "status"), "rejected") ? pyGet(info, "resetsAt") : null;
    } else if (pyEq(kind, "result")) {
      result = event;
    }
  }
  // 读完才知道读不出几行：放在最前面，与 Python 先数再审的次序一样（循环里只往后加）
  if (counter.unreadable) violations.unshift(UNREADABLE_STREAM.replace("%d", String(counter.unreadable)));
  if (!init.size) {
    violations.push("事件流里没有 init");
  } else {
    const tools = or(pyGet(init, "tools"), []);
    if (!new PySet(pyIter(tools)).equals(allowed)) {
      violations.push(`init 的工具 ${pyReprValue(pySorted(pyIter(tools)))} 与白名单 ${pyReprValue(pySorted(allowed.values()))} 不一致`);
    }
    if (pyTruthy(pyGet(init, "mcp_servers"))) {
      const names = pyIter(pyItem(init, "mcp_servers")).filter((server) => server instanceof Map).map((server) => pyGet(server, "name"));
      violations.push(`加载了 MCP 服务器：${pyReprValue(names)}`);
    }
    if (pyTruthy(pyGet(init, "memory_paths"))) violations.push(`自动记忆没有关掉：${pyStrValue(pyItem(init, "memory_paths"))}`);
    if (pyTruthy(pyGet(init, "model")) && !pyEq(pyItem(init, "model"), pyItem(spec, "model"))) {
      violations.push(`init 的模型 ${pyStrValue(pyItem(init, "model"))} 不是 ${pyStrValue(pyItem(spec, "model"))}`);
    }
  }
  models.discard("<synthetic>"); // claude 自己合成的消息（例如接口报错时）没有真实模型
  const required = pyItem(spec, "model");
  if (models.minus(new PySet([required])).size) {
    violations.push(`实际模型 ${pyReprValue(pySorted(models.values()))} 与要求 ${pyStrValue(required)} 不一致`);
  }
  if (apiError === null && pyEq(pyGet(result, "terminal_reason"), "api_error")) {
    apiError = `terminal_reason=api_error：${firstCodePoints(pyStrValue(or(pyGet(result, "result"), "")), 300)}`;
  }
  // 白名单之外的客户端调用：被 CLI 当场拒绝的只记警告，看不到拒绝结果的照旧作废
  const warnings = [...outside].filter(([id]) => refused.has(id)).map(([, name]) => `试图调用白名单之外的工具 ${name}，被 CLI 拒绝`);
  violations.push(...[...outside].filter(([id]) => !refused.has(id)).map(([, name]) => `调用了白名单之外的工具：${name}（tool_use）`));
  const output = pyGet(result, "structured_output");
  const delivered = output instanceof Map ? output : null;
  const thinking = pyGet(or(pyGet(or(pyGet(result, "usage"), new Map()), "output_tokens_details"), new Map()), "thinking_tokens");
  const deliveredUnreadable = accepted && delivered === null ? `StructuredOutput 被收下 ${accepted} 次，result 里却没有 structured_output` : null;
  return new Map<PyKey, PyValue>([
    ["violations", violations], ["warnings", warnings], ["tool_calls", toolCalls], ["delivered", delivered],
    ["delivered_unreadable", deliveredUnreadable], ["deliver_refusals", refusals], ["thinking_chars", null], ["thinking_tokens", thinking],
    ["init_session", pyGet(init, "session_id")], ["final_text", pyStrValue(or(pyGet(result, "result"), ""))],
    ["is_error", pyTruthy(pyGet(result, "is_error"))], ["cost_usd", pyGet(result, "total_cost_usd")], ["usage", or(pyGet(result, "usage"), new Map())],
    ["models", pySorted(models.values())], ["terminal", result.size > 0], ["api_error", apiError],
    ["rate_limited_until", apiError !== null && isPyInt(rejectedUntil) ? rejectedUntil : null],
  ]);
}

/** 一个绝对路径在命令里可能的写法（小写）：原样（反斜杠）、正斜杠、Git Bash 的 /c/…；长的在前，等长的按字面（第 133 轮）。 */
export function pathForms(path: string): string[] {
  const text = pyResolve(purePathStr(path));
  const forms = new Set([pyLower(text), pyLower(text.split(BS).join("/"))]);
  const chars = codePoints(text);
  if (chars.length > 2 && chars[1] === ":") forms.add(pyLower(`/${chars[0]}${chars.slice(2).join("").split(BS).join("/")}`));
  return [...forms].sort((a, b) => codePoints(b).length - codePoints(a).length || cmpCodePoints(a, b));
}

/** target 是不是 root 本身或它下面的路径（两个都已 normcase、abspath）。 */
function within(target: string, root: string): boolean {
  return target === root || target.startsWith(stripRight(root, `${BS}/`) + SEP);
}

/** 参数里的全部字符串（嵌套的列表与字典也取）：主工作区的路径写在哪个键里都算。 */
function argStrings(value: PyValue): string[] {
  if (typeof value === "string") return [value];
  if (value instanceof Map) return [...value.values()].flatMap(argStrings);
  if (Array.isArray(value)) return value.flatMap(argStrings);
  return [];
}

/** 工具调用碰没碰不该碰的地方：（"violation" 或 ""，说明）。写只能写工作目录；主工作区只许读文件的工具读已经装好的依赖。 */
export function piReachProblem(name: string, args: PyValue, workspace: string, repo: string | null): [string, string] {
  const space = purePathStr(workspace);
  const root = normcase(abspath(space));
  if (name === "write" || name === "edit") {
    const raw = pyStrValue(or(pyGet(args, "path"), ""));
    if (!within(normcase(abspath(isabs(raw) ? raw : osPathJoin(space, raw))), root)) return ["violation", `${name} 写到了工作目录之外：${raw}`];
  }
  if (repo === null) return ["", ""];
  const main = normcase(abspath(purePathStr(repo)));
  if (READ_TOOLS.includes(name) && pyGet(args, "path") !== null) {
    const raw = pyStrValue(pyGet(args, "path"));
    const target = normcase(abspath(isabs(raw) ? raw : osPathJoin(space, raw)));
    if (!within(target, root) && within(target, main)) { // 测试里工作目录可以在仓库里面
      if (DEPENDENCY_DIRS.some((dep) => within(target, normcase(osPathJoin(main, ...dep.split("/")))))) return ["", ""];
      return ["violation", `${name} 读了主工作区：${raw}。合同、信箱与执行证据在只读输入目录里，主工作区只许读已经装好的依赖（${DEPENDENCY_DIRS.join("、")}）`];
    }
  }
  let text = pyLower(argStrings(args).join(" "));
  for (const form of pathForms(space)) text = text.split(form).join("{工作目录}");
  if (pathForms(repo).some((form) => text.includes(form))) {
    return ["violation", `${name} 的参数提到了主工作区（材料在只读输入目录里，主工作区不许碰）：${firstCodePoints(argStrings(args).join(" "), 200)}`];
  }
  return ["", ""];
}

/** 守卫扩展（guard.ts，第 106 轮）的配置，经环境变量 THEMIS_GUARD 传给 pi：根目录与路径写法在这里算好，扩展只做比较。 */
export function guardConfig(workspace: string, repo: string): string {
  const main = normcase(abspath(purePathStr(repo)));
  return dumps(new Map<PyKey, PyValue>([
    ["workspace", normcase(abspath(purePathStr(workspace)))], ["main", main],
    ["deps", DEPENDENCY_DIRS.map((dep) => normcase(osPathJoin(main, ...dep.split("/"))))],
    ["depNames", [...DEPENDENCY_DIRS]], ["workspaceForms", pathForms(workspace)], ["mainForms", pathForms(repo)],
    ["readTools", [...READ_TOOLS]],
  ]));
}

/** 读内核截下的 pi 事件流：白名单之外的工具、碰了不该碰的地方（守卫当场拦下的只记警告）、模型、交差、思考的字数。 */
export function auditPiStream(lines: readonly string[], spec: PyValue, workspace: string | null = null, repo: string | null = null): PyDict {
  const allowed = new PySet(pyIter(pyItem(spec, "tools")));
  const violations: string[] = [];
  const reachWarnings: string[] = [];
  const toolCalls: PyDict = new Map();
  let finalText = "";
  const levels = new PySet();
  const models = new PySet();
  let stop: PyValue = null;
  let apiError: string | null = null;
  const usage: PyDict = new Map();
  let terminal = false;
  const outside = new Map<string, string>(); // 白名单之外的调用：toolCallId → 工具名
  const refused = new PySet();
  const reach = new Map<string, string>(); // 碰了不该碰的地方的调用：toolCallId → 说明
  let delivered: PyValue = null; // 最后一次成功的 deliver 交上来的参数
  const refusals: PyValue[] = []; // deliver 每次被退回时报错的长度
  let unreadDetails = 0; // deliver 报了成功、result.details 却不是对象的次数
  let thinking = 0n; // thinking 块的字数
  const counter = { unreadable: 0 };
  for (const event of eachEvent(lines, counter)) {
    const kind = pyGet(event, "type");
    if (pyEq(kind, "tool_execution_start")) {
      const name = pyStrValue(pyGet(event, "toolName"));
      count(toolCalls, name);
      if (!allowed.has(name)) {
        outside.set(pyStrValue(pyGet(event, "toolCallId")), name);
      } else if (workspace !== null && name !== DELIVER_TOOL) {
        const [level, note] = piReachProblem(name, or(pyGet(event, "args"), new Map()), workspace, repo);
        if (level === "violation") reach.set(pyStrValue(pyGet(event, "toolCallId")), note);
        else if (level) reachWarnings.push(note);
      }
    } else if (pyEq(kind, "tool_execution_end")) {
      const callId = pyStrValue(pyGet(event, "toolCallId"));
      const text = joinStrings(pyIter(or(pyGet(or(pyGet(event, "result"), new Map()), "content"), []))
        .filter((block) => block instanceof Map).map((block) => pyGet(block, "text", "")));
      const failed = pyTruthy(pyGet(event, "isError"));
      if (outside.has(callId) && failed && pyStrip(text) === `Tool ${outside.get(callId)} not found`) refused.add(callId);
      // 守卫拦下的调用没有执行：isError、details 是空对象、正文以 GUARD_PREFIX 开头、以 GUARD_SUFFIX 结尾
      if (reach.has(callId) && failed && isEmptyDict(pyGet(or(pyGet(event, "result"), new Map()), "details"))
        && text.startsWith(GUARD_PREFIX) && text.endsWith(GUARD_SUFFIX)) {
        reachWarnings.push(`守卫当场拦下，没有执行：${reach.get(callId)}`);
        reach.delete(callId);
      }
      const details = pyGet(or(pyGet(event, "result"), new Map()), "details");
      const deliver = pyEq(pyGet(event, "toolName"), DELIVER_TOOL) && allowed.has(DELIVER_TOOL);
      if (deliver && failed) refusals.push(BigInt(codePoints(text).length));
      else if (deliver && details instanceof Map) delivered = details;
      else if (deliver) unreadDetails += 1;
    } else if (pyEq(kind, "message_end") && pyEq(pyGet(or(pyGet(event, "message"), new Map()), "role"), "assistant")) {
      const message = pyItem(event, "message");
      for (const block of blocksOf(pyGet(message, "content"), "thinking")) {
        thinking += BigInt(codePoints(pyStrValue(or(pyGet(block, "thinking"), ""))).length);
      }
      models.add(`${pyStrValue(pyGet(message, "provider"))}/${pyStrValue(pyGet(message, "model"))}`);
      if (pyTruthy(pyGet(message, "thinkingLevel"))) levels.add(pyStrValue(pyItem(message, "thinkingLevel")));
      const text = joinStrings(blockTexts(pyGet(message, "content"), "text"));
      if (pyStrip(text)) finalText = text;
      stop = pyGet(message, "stopReason");
      // 只认最后一条：pi 自己重试成功时，前面那条出错的消息不算
      apiError = pyEq(stop, "error") ? firstCodePoints(pyStrValue(or(pyGet(message, "errorMessage"), "stopReason=error")), 300) : null;
      for (const [key, value] of dictItems(or(pyGet(message, "usage"), new Map()))) {
        if (typeof value === "bigint" || typeof value === "number") usage.set(key, pyAdd(usage.get(key) ?? 0n, value));
      }
    } else if (pyEq(kind, "agent_settled") || pyEq(kind, "agent_end")) {
      terminal = true;
    }
  }
  if (counter.unreadable) violations.unshift(UNREADABLE_STREAM.replace("%d", String(counter.unreadable)));
  const expected =`${pyStrValue(pyItem(spec, "provider"))}/${pyStrValue(pyItem(spec, "model"))}`;
  if (models.minus(new PySet([expected])).size) violations.push(`实际模型 ${pyReprValue(pySorted(models.values()))} 与要求 ${expected} 不一致`);
  // 与 claude 一样：pi 当场拒绝（“Tool bash not found”）的调用只记警告，看不到拒绝结果的照旧作废
  const warnings = [...outside].filter(([id]) => refused.has(id)).map(([, name]) => `试图调用白名单之外的工具 ${name}，被 pi 拒绝`);
  warnings.push(...reachWarnings);
  violations.push(...reach.values()); // 没看到守卫拦下的结果（执行了，或流被截断）
  violations.push(...[...outside].filter(([id]) => !refused.has(id)).map(([, name]) => `调用了白名单之外的工具：${name}`));
  return new Map<PyKey, PyValue>([
    ["violations", violations], ["warnings", warnings], ["tool_calls", toolCalls], ["final_text", finalText],
    ["effective_levels", pySorted(levels.values())], ["stop_reason", stop], ["usage", usage], ["models", pySorted(models.values())],
    ["terminal", terminal], ["is_error", !(stop === null || pyEq(stop, "stop"))], ["api_error", apiError], ["delivered", delivered],
    ["delivered_unreadable", unreadDetails ? `deliver 报了成功 ${unreadDetails} 次，result.details 却不是对象` : null],
    ["deliver_refusals", refusals], ["thinking_chars", thinking], ["thinking_tokens", usage.has("reasoning") ? (usage.get("reasoning") as PyValue) : null],
  ]);
}

// pi 命令 → 它的 --help 列出的参数；读不出时是 null（第 83 轮：一个进程只探一次）
const PI_FLAGS = new Map<string, Set<string> | null>();

/** 本机 pi 的 --help 里列出的参数，按 pi 命令缓存（与调度器预检同一个解析）。 */
export async function piSupportedFlags(piCmd: readonly string[], env: ReadonlyMap<string, string>): Promise<Set<string> | null> {
  const key = JSON.stringify(piCmd);
  if (!PI_FLAGS.has(key)) {
    const [code, out, err] = await runCapture([...piCmd, ...RESOURCE_FLAGS, "--help"], { env, timeout: 90 });
    PI_FLAGS.set(key, code === 0 ? new Set(parseHelp(out + err).flags) : null);
  }
  return PI_FLAGS.get(key) ?? null;
}

/** 第 83 轮：pi 对不认识的参数静默忽略。起 pi 工人之前，命令里每个 -- 开头的参数都要在本机 pi 的 --help 里。 */
export async function piFlagsProblem(piCmd: readonly string[], args: readonly string[], env: ReadonlyMap<string, string>): Promise<string | null> {
  const supported = await piSupportedFlags(piCmd, env);
  if (supported === null) return `读不出本机 pi 的 --help，核对不了参数，没有起这一回合（pi 命令：${piCmd.join(" ")}）`;
  const missing = [...new Set(args.filter((arg) => arg.startsWith("--") && !supported.has(arg)))].sort(cmpCodePoints);
  if (missing.length) {
    return `本机 pi 不认识 hub 传给工人的参数：${missing.join(", ")}。pi 对不认识的参数静默忽略，照样起会让这些限制失效，没有起这一回合（升级 pi 或改名册）`;
  }
  return null;
}

// --- Python 语义的小工具 ----------------------------------------------------------------------------------------

/** Path.home() / ".claude" / "projects"。 */
function claudeProjects(): string {
  return purePathStr(expanduser("~"), ".claude", "projects");
}

/** sorted() 一组 Path：Windows 上按小写之后的各段逐段比（PureWindowsPath 不分大小写），POSIX 上按各段比。 */
function comparePaths(a: string, b: string): number {
  const parts = (path: string): string[] => (WIN ? pyLower(path) : path).split(SEP);
  const left = parts(a);
  const right = parts(b);
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    const order = cmpCodePoints(left[index] as string, right[index] as string);
    if (order) return order;
  }
  return left.length - right.length;
}

/** x or y。 */
function or(value: PyValue, fallback: PyValue): PyValue {
  return pyTruthy(value) ? value : fallback;
}

function count(counts: PyDict, name: string): void {
  counts.set(name, ((counts.get(name) as bigint | undefined) ?? 0n) + 1n);
}

/** `for block in content or []`（字符串逐字、字典取键、别的抛 TypeError）里类型为 type 的字典块。 */
function blocksOf(content: PyValue, type: string): PyDict[] {
  return pyIter(or(content, [])).filter((block): block is PyDict => block instanceof Map && pyEq(pyGet(block, "type"), type));
}

/** 类型为 type 的块的 block.get("text", "")。 */
function blockTexts(content: PyValue, type: string): PyValue[] {
  return blocksOf(content, type).map((block) => pyGet(block, "text", ""));
}

/** "".join(items)：不是字符串照 Python 抛 TypeError。 */
function joinStrings(items: readonly PyValue[]): string {
  items.forEach((item, index) => {
    if (typeof item !== "string") throw new PyCrash("TypeError", `sequence item ${index}: expected str instance, ${pyTypeName(item)} found`);
  });
  return items.join("");
}

/** dict.items()：不是字典照 Python 抛 AttributeError。 */
function dictItems(value: PyValue): [PyKey, PyValue][] {
  if (!(value instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'items'`);
  return [...value];
}

function isEmptyDict(value: PyValue): boolean {
  return value instanceof Map && value.size === 0;
}

/** isinstance(value, int)：布尔也算。 */
function isPyInt(value: PyValue): boolean {
  return typeof value === "bigint" || typeof value === "boolean";
}

/** value in {str 键的字典}：不可散列的照 Python 抛 TypeError；只有相等的字符串在里面。 */
function inKeys(keys: ReadonlyMap<string, unknown>, value: PyValue): boolean {
  hashKey(value);
  return typeof value === "string" && keys.has(value);
}

function firstCodePoints(text: string, count: number): string {
  return codePoints(text).slice(0, count).join("");
}

function stripChars(text: string, chars: string): string {
  return stripRight(stripLeft(text, chars), chars);
}

function stripLeft(text: string, chars: string): string {
  let start = 0;
  while (start < text.length && chars.includes(text[start] as string)) start += 1;
  return text.slice(start);
}

function stripRight(text: string, chars: string): string {
  let end = text.length;
  while (end > 0 && chars.includes(text[end - 1] as string)) end -= 1;
  return text.slice(0, end);
}

/** os.path.isabs。 */
function isabs(path: string): boolean {
  return WIN ? ntIsabs(path) : path.startsWith("/");
}

/** 可散列的 JSON 值在 Python 里的相等类：1、1.0、True 是同一个；json.loads 出来的 NaN 都是同一个对象。 */
function hashKey(value: PyValue): string {
  if (Array.isArray(value)) throw new PyCrash("TypeError", "unhashable type: 'list'");
  if (value instanceof Map) throw new PyCrash("TypeError", "unhashable type: 'dict'");
  if (value === null) return "N";
  if (typeof value === "string") return `S${value}`;
  if (typeof value === "boolean") return value ? "I1" : "I0";
  if (typeof value === "bigint") return `I${value}`;
  if (Number.isNaN(value)) return "NaN";
  if (Number.isInteger(value)) return `I${BigInt(value)}`;
  return `F${value}`;
}

/** Python 的集合（元素是可散列的 JSON 值）。 */
class PySet {
  private readonly items = new Map<string, PyValue>();

  constructor(values: Iterable<PyValue> = []) {
    for (const value of values) this.add(value);
  }

  get size(): number {
    return this.items.size;
  }

  add(value: PyValue): void {
    const key = hashKey(value);
    if (!this.items.has(key)) this.items.set(key, value);
  }

  has(value: PyValue): boolean {
    return this.items.has(hashKey(value));
  }

  discard(value: PyValue): void {
    this.items.delete(hashKey(value));
  }

  values(): PyValue[] {
    return [...this.items.values()];
  }

  minus(other: PySet): PySet {
    return new PySet(this.values().filter((value) => !other.has(value)));
  }

  equals(other: PySet): boolean {
    return this.size === other.size && this.values().every((value) => other.has(value));
  }
}

/** Python 的字典（键是可散列的值，按 Python 的相等合并，保留先插入的那个键）。 */
class PyKeyedDict {
  private readonly keys = new Map<string, PyKey>();
  private readonly values = new Map<string, PyValue>();

  has(key: PyKey): boolean {
    return this.keys.has(hashKey(key));
  }

  get(key: PyKey): PyValue | undefined {
    return this.values.get(hashKey(key));
  }

  set(key: PyKey, value: PyValue): void {
    const hash = hashKey(key);
    if (!this.keys.has(hash)) this.keys.set(hash, key);
    this.values.set(hash, value);
  }

  delete(key: PyKey): void {
    const hash = hashKey(key);
    this.keys.delete(hash);
    this.values.delete(hash);
  }

  toDict(): PyDict {
    return new Map([...this.keys].map(([hash, key]) => [key, this.values.get(hash) as PyValue]));
  }
}

/** dict(value)：字典照抄；别的当成成对的序列（长度为 2 的字符串也是一对），不成对照 Python 报错。 */
function pyDictOf(value: PyValue): PyKeyedDict {
  const out = new PyKeyedDict();
  if (value instanceof Map) {
    for (const [key, item] of value) out.set(key, item);
    return out;
  }
  pyIter(value).forEach((item, index) => {
    let pair: PyValue[];
    if (Array.isArray(item)) pair = item;
    else if (typeof item === "string") pair = codePoints(item);
    else if (item instanceof Map) pair = [...item.keys()] as PyValue[];
    else throw new PyCrash("TypeError", `cannot convert dictionary update sequence element #${index} to a sequence`);
    if (pair.length !== 2) throw new PyCrash("ValueError", `dictionary update sequence element #${index} has length ${pair.length}; 2 is required`);
    const [key, item2] = pair as [PyValue, PyValue];
    if (Array.isArray(key) || key instanceof Map) hashKey(key);
    out.set(key as PyKey, item2);
  });
  return out;
}

/** Python 的 a < b（可散列的 JSON 值）：数与数、字符串与字符串可比，别的照 Python 抛 TypeError。 */
function pyLess(a: PyValue, b: PyValue): boolean {
  const numeric = (value: PyValue): value is bigint | number | boolean => typeof value === "bigint" || typeof value === "number" || typeof value === "boolean";
  if (numeric(a) && numeric(b)) return compareNumbers(a, b) < 0;
  if (typeof a === "string" && typeof b === "string") return cmpCodePoints(a, b) < 0;
  throw new PyCrash("TypeError", `'<' not supported between instances of '${pyTypeName(a)}' and '${pyTypeName(b)}'`);
}

/** 两个数的大小，Python 的整数与浮点精确比较；有 NaN 时交回 NaN（比较都为假）。 */
function compareNumbers(a: bigint | number | boolean, b: bigint | number | boolean): number {
  const int = (value: bigint | number | boolean): bigint | number => (typeof value === "boolean" ? (value ? 1n : 0n) : value);
  const left = int(a);
  const right = int(b);
  if (typeof left === "bigint" && typeof right === "bigint") return left < right ? -1 : left > right ? 1 : 0;
  if (typeof left === "number" && typeof right === "number") return Number.isNaN(left) || Number.isNaN(right) ? Number.NaN : left - right;
  return typeof left === "bigint" ? intFloat(left, right as number) : -intFloat(right as bigint, left as number);
}

function intFloat(int: bigint, float: number): number {
  if (Number.isNaN(float)) return Number.NaN;
  if (float === Number.POSITIVE_INFINITY) return -1;
  if (float === Number.NEGATIVE_INFINITY) return 1;
  const floor = Math.floor(float);
  const whole = BigInt(floor);
  if (int !== whole) return int < whole ? -1 : 1;
  return floor === float ? 0 : -1;
}

/**
 * sorted(values)：照 CPython 3.12 的 list.sort，64 个以内先 count_run、再二分插入，比较的先后与 Python 相同，
 * 混了不能比的值时在同一处抛 TypeError，有 NaN 时排出来的次序也相同。更长的退回稳定的归并排序（全序时结果相同）。
 */
function pySorted(values: readonly PyValue[]): PyValue[] {
  const items = [...values];
  const n = items.length;
  if (n < 2) return items;
  if (n >= 64) return mergeSort(items);
  let run = 2;
  if (pyLess(items[1] as PyValue, items[0] as PyValue)) {
    while (run < n && pyLess(items[run] as PyValue, items[run - 1] as PyValue)) run += 1;
    items.splice(0, run, ...items.slice(0, run).reverse());
  } else {
    while (run < n && !pyLess(items[run] as PyValue, items[run - 1] as PyValue)) run += 1;
  }
  for (let start = run; start < n; start += 1) {
    const pivot = items[start] as PyValue;
    let low = 0;
    let high = start;
    while (low < high) {
      const middle = low + ((high - low) >> 1);
      if (pyLess(pivot, items[middle] as PyValue)) high = middle;
      else low = middle + 1;
    }
    items.splice(start, 1);
    items.splice(low, 0, pivot);
  }
  return items;
}

function mergeSort(items: PyValue[]): PyValue[] {
  if (items.length < 2) return items;
  const middle = items.length >> 1;
  const left = mergeSort(items.slice(0, middle));
  const right = mergeSort(items.slice(middle));
  const out: PyValue[] = [];
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) out.push(pyLess(right[j] as PyValue, left[i] as PyValue) ? (right[j++] as PyValue) : (left[i++] as PyValue));
  return [...out, ...left.slice(i), ...right.slice(j)];
}
