// 回合（迁移第 ⑤d 片，kit_hub.py 的 TurnRunner）：起一个工人回合——会话代数、命令行（claude 与 pi）、环境、起之前的核对、
// launcher（缺省经 base 的 runSupervised，Job Object 监督）、审计、接口报错、限流退避、交差输出、花费、会话记录、result.json、turn.finished。
// run() 是 async（launcher 与 pi 的 --help 探测都是异步），一个 runner 内严格串行 await。不确定的几样（回合号用的时刻与两个随机字节、
// claude 的会话号、限流退避用的当前秒数）由构造参数注入，缺省取真的；契约两边注入同一组值，路径与会话号逐字节可比。
import { createHash, randomBytes, randomUUID } from "node:crypto";
import { closeSync, copyFileSync, existsSync, mkdirSync, openSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { utcCompact, utcNow } from "@themis/base/clock";
import { readText } from "@themis/base/fsutil";
import { jsonlLines } from "@themis/base/jsonl";
import { PyCrash, pyGet, pyIntOf, pyItem, pyLenValue, pyRepr, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, dumps } from "@themis/base/pyjson";
import { purePathName, purePathStr } from "@themis/base/pypath";
import { pyLen } from "@themis/base/pyre";
import { FLAG_IGNORECASE, compilePy } from "@themis/base/pyregex";
import { pyWhich } from "@themis/base/pyshutil";
import { pyWinErrorMessage, runSupervised } from "@themis/base/supervise";
import { pyEq } from "@themis/base/pyvalue";
import { resolvePiCommand } from "@themis/dispatcher/executor";
import { writeJson } from "@themis/dispatcher/evidence";
import { configWithBytes } from "@themis/dispatcher/kernel-config";
import { RESOURCE_FLAGS } from "@themis/dispatcher/pi-cli";
import { Repo } from "@themis/dispatcher/repo";
import { globPaths } from "@themis/dispatcher/instruction";
import {
  auditClaudeStream, auditPiStream, claudePathRule, claudeSessionEffort, guardConfig, piFlagsProblem, sessionCutShort, turnCostUsd,
} from "./audit.ts";
import {
  CLAUDE_SETTINGS, CLAUDE_WORKER_ENV, DELIVER_TOOL, DEPENDENCY_DIRS, INPUTS_INDEX, MAX_INLINE_PROMPT, ROSTER, type RosterSpec, STRUCTURED_TOOL,
  QUIZS_LIVE_FILES, QUIZS_STATE_DIR, QUIZS_TURN_BUDGETS, THROTTLE_BACKOFF_MAX, THROTTLE_BACKOFF_SECONDS, THROTTLE_MAX_HOLDS, THROTTLE_RESET_HORIZON, THROTTLE_RESET_MARGIN, THROTTLE_RESET_OFFSET,
} from "./constants.ts";
import { DELIVERY_SHA256, deliveredOutput, deliveryProblem, interfaceProblem, roleSchema, workerEnv, workerFileProblem } from "./delivery.ts";
import { DELIVER_EXTENSION, GUARD_EXTENSION, HUB_SHA256, SCHEMA_DIR, hubImpl } from "./kernel.ts";
import type { Hub } from "./mailbox.ts";
import { auditQuizsStream, effectiveSpec, quizsSnapshot, resolveQuizsCommand } from "./quizs.ts";

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);
/** 第 38 轮：pi 的模型接口限流（429、throttling、rate limit……）。 */
const THROTTLE = compilePy(`${BS}b429${BS}b|throttl|rate[ _-]?limit|too many requests|quota`, FLAG_IGNORECASE);
const THROTTLE_RESET = /([0-9]{4})-([0-9]{2})-([0-9]{2})[ T]([0-9]{2}):([0-9]{2}):([0-9]{2})/u;

/**
 * 限流报错里的重置时刻（北京时间，见 THROTTLE_RESET_OFFSET）加上余量，换成秒；没写、不是真日期、已经过去或在 24 小时以外时为 null。
 * 不是真日期（2 月 30 日、25 点）照 Python 的 datetime 报 ValueError 那样不认，不让 Date.UTC 进位成别的日子。
 */
export function throttleReset(error: string, now: number): number | null {
  const match = THROTTLE_RESET.exec(error);
  if (match === null) return null;
  const [year, month, day, hour, minute, second] = match.slice(1).map(Number) as [number, number, number, number, number, number];
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day || hour > 23 || minute > 59 || second > 59) return null;
  const reset = date.getTime() / 1000 - THROTTLE_RESET_OFFSET;
  return now < reset && reset <= now + THROTTLE_RESET_HORIZON ? reset + THROTTLE_RESET_MARGIN : null;
}

/**
 * 起一个工人进程：照 pd.run_supervised 的形状，(命令, 工作目录, 环境, 标准输出的文件, 标准错误的文件, 时限秒) → 结果（exit_code、timed_out、
 * wall_seconds……）。两个文件 TurnRunner 已经以 wx 建好（Python 的 xb），launcher 往里追加。
 */
export type Launcher = (cmd: readonly string[], cwd: string, env: ReadonlyMap<string, string>, out: string, err: string, timeout: number) => Promise<PyDict>;

/** 缺省的 launcher：base 的 runSupervised（Job Object 监督），结果照 Python 的 dict（整数是 int）。 */
export const superviseLauncher: Launcher = async (cmd, cwd, env, out, err, timeout) => {
  const result = await runSupervised(cmd, { cwd, env: [...env], stdout: { path: out, how: "append" }, stderr: { path: err, how: "append" }, timeout });
  return new Map(Object.entries(result).map(([key, value]): [string, PyValue] => [key, typeof value === "number" && key !== "wall_seconds" ? BigInt(value) : value]));
};

/** 回合里不确定的几样；契约注入同一组值。 */
export interface TurnSources {
  /** utc_compact()：回合号的前一半。 */
  readonly compact: () => string;
  /** os.urandom(2).hex()：回合号的后一半。 */
  readonly random2: () => string;
  /** str(uuid.uuid4())：claude 的新会话号。 */
  readonly uuid4: () => string;
  /** int(time.time())：限流退避的起点。 */
  readonly seconds: () => number;
}

export const REAL_SOURCES: TurnSources = {
  compact: () => utcCompact(),
  random2: () => randomBytes(2).toString("hex"),
  uuid4: () => randomUUID(),
  seconds: () => Math.floor(Date.now() / 1000),
};

/** RosterSpec 照 Python 的 dict（整数是 int），键序照名册。 */
function specDict(spec: RosterSpec, tools?: readonly string[]): PyDict {
  return new Map(Object.entries({ ...spec, ...(tools ? { tools } : {}) }).map(([key, value]): [string, PyValue] => [key, pyValueOf(value)]));
}

function pyValueOf(value: unknown): PyValue {
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(pyValueOf);
  return value as PyValue;
}

/** 启动一个工人回合：一个后台进程，Job Object 监督，事件流由内核截下。 */
export class TurnRunner {
  readonly hub: Hub;
  readonly launcher: Launcher;
  readonly sources: TurnSources;

  constructor(hub: Hub, launcher: Launcher = superviseLauncher, sources: TurnSources = REAL_SOURCES) {
    this.hub = hub;
    this.launcher = launcher;
    this.sources = sources;
  }

  /**
   * fresh：不续接旧会话，开一个干净的新会话（返工时用）。inputs：这一回合的只读输入目录（第 88 轮）。
   * sessionId：续接这一个会话（第 93 轮：被打断的回合的会话，取自它的 result.json），不看记录里的是哪个。
   */
  async run(agent: string, sessionKey: string, workspace: string, rolePrompt: string, prompt: string,
    retryOf: string | null = null, fresh = false, inputs: string | null = null, sessionId: string | null = null): Promise<PyDict> {
    if (!Object.hasOwn(ROSTER, agent)) throw new PyCrash("KeyError", pyRepr(agent));
    // 第 143 轮：quizs 岗位起不了（证书过期、文件没设）就这一回合改用名册写的替补（pi），开新会话
    const [spec, fallback] = effectiveSpec(agent, this.sources.seconds());
    const claude = spec.adapter === "claude";
    const quizs = spec.adapter === "quizs";
    // 第 90 轮：用工具交差：pi 用 deliver 扩展；claude 用 --json-schema，CLI 自己加上 StructuredOutput 工具；quizs 用代码块（第 137 轮）
    const tools = [...(spec.tools ?? []), ...(quizs ? [] : [claude ? STRUCTURED_TOOL : DELIVER_TOOL])];
    const turnId = `${this.sources.compact()}-${this.sources.random2()}`;
    const turnDir = join(this.hub.root, "turns", agent, turnId);
    if (existsSync(turnDir)) throw new PyCrash("FileExistsError", pyWinErrorMessage(183, turnDir)); // Path.mkdir 走 os.mkdir，带路径
    mkdirSync(turnDir, { recursive: true });
    const rolePath = join(turnDir, "role.md");
    writeFileSync(rolePath, rolePrompt);
    writeFileSync(join(turnDir, "prompt.md"), prompt);
    const where = purePathStr(workspace);
    const record = this.hub.agentRecord(agent);
    let session: PyDict | null = (pyGet(pyItem(record, "sessions"), sessionKey) as PyDict | null) ?? null;
    let generation = pyIntOf(pyGet(session ?? new Map(), "generation", 0n));
    if (sessionId !== null) {
      if (!pyEq(pyGet(session ?? new Map(), "id"), sessionId)) {
        session = new Map<string, PyValue>([["id", sessionId], ["cwd", where], ["turns", 1n], ["created_at", utcNow()], ["generation", generation]]);
      }
    } else if (pyTruthy(session) && (fresh || !pyEq(pyGet(session, "cwd"), where))) {
      [session, generation] = [null, generation + 1n]; // 返工重开，或工作目录变了（claude 按目录找会话）
    }
    // 第 145 轮：开新会话也带上连着被限流的次数（退避照样加倍，太多次照样交给站主）
    const throttles = quizs || fallback !== null ? pyGet(session ?? new Map(), "throttles") : null;
    if (quizs || fallback !== null) session = null; // 第 137 轮：quizs 每回合一个新会话，不续接（Quizs 的最终回答策略只认新会话）；替补也一样
    const cut = session !== null && sessionCutShort(this.hub.root, agent, spec.adapter, pyStrValue(pyItem(session, "id"))) ? pyStrValue(pyItem(session, "id")) : null;
    if (cut !== null) {
      // 第 94 轮：要续接的会话停在半截：换新的一代，附上“接着做”的说明
      session = null;
      prompt = `## 换了新会话（内核）${LF}${LF}- 上一个会话（${cut}）停在半截：回合中途被打断，最后是还没有结果的工具调用。`
        + `工作目录里留着之前的改动，先看一遍，接着做，做完再交。${LF}${LF}${prompt}`;
      writeFileSync(join(turnDir, "prompt.md"), prompt);
      await this.hub.appendEvent("session.cut_short", [["agent", agent], ["session_key", sessionKey], ["session", cut]]);
    }
    const first = session === null;
    if (first && spec.adapter === "pi") {
      // 第 93 轮：pi 的会话号按代数定，新会话跳过已有会话文件的代（回合中途被收掉时那一代的会话文件已经留下了）
      const sessions = join(this.hub.root, "sessions", agent);
      while (globPaths(sessions, [`*_${sessionKey}-g${generation}.jsonl`]).length) generation += 1n;
    }
    if (first) {
      session = new Map<string, PyValue>([["id", claude ? this.sources.uuid4() : quizs ? `${sessionKey}-${turnId}` : `${sessionKey}-g${generation}`], ["cwd", where], ["turns", 0n],
        ["created_at", utcNow()], ["generation", generation]]);
      if (pyTruthy(throttles)) session.set("throttles", throttles as PyValue);
    }
    const current = session as PyDict;
    const id = pyStrValue(pyItem(current, "id"));
    let longPrompt = join(turnDir, "prompt.md");
    if (inputs !== null && pyLen(prompt) > MAX_INLINE_PROMPT) {
      longPrompt = purePathStr(inputs, `prompt-${turnId}.md`); // 第 88 轮：回合目录在主工作区里，工人读不到
      writeFileSync(longPrompt, prompt);
    }
    if (inputs !== null && statOrNull(join(inputs, INPUTS_INDEX))?.isFile()) copyFileSync(join(inputs, INPUTS_INDEX), join(turnDir, "inputs.json"));
    const inline = pyLen(prompt) <= MAX_INLINE_PROMPT ? prompt : `本回合的输入很长，已写在文件里，先完整读它再开始：${longPrompt}`;
    const [cmd, piCmd, quizsCmd, sessionsDir] = claude ? [this.claudeCommand(spec, rolePath, inputs, first, id, inline), null, [], ""]
      : quizs ? this.quizsCommand(spec, agent, tools, rolePath, turnDir, id, inputs, where)
      : [...this.piCommand(spec, agent, tools, rolePath, turnDir, id), [], ""];
    const started = utcNow();
    const env = workerEnv(this.config());
    if (claude) for (const [name, value] of Object.entries(CLAUDE_WORKER_ENV)) env.set(name, value);
    else if (!quizs) {
      env.set("THEMIS_DELIVER_SCHEMA", purePathStr(SCHEMA_DIR, `${spec.role}.json`));
      env.set("THEMIS_GUARD", guardConfig(where, this.hub.repo));
    }
    let blocked: string | null;
    if (quizs) {
      const [ref, problem] = inputs === null ? [null, null] : await quizsSnapshot(quizsCmd, sessionsDir, inputs, env);
      blocked = deliveryProblem(spec.role) || problem;
      if (ref !== null) cmd.push("--read-snapshot", ref);
    } else {
      blocked = claude ? deliveryProblem(spec.role)
        : (await piFlagsProblem(piCmd as string[], cmd.slice((piCmd as string[]).length), env)) || workerFileProblem(GUARD_EXTENSION) || deliveryProblem(spec.role);
    }
    const out = join(turnDir, "stream.jsonl");
    const err = join(turnDir, "stderr.log");
    for (const path of [out, err]) closeSync(openSync(path, "wx"));
    const result: PyDict = blocked
      ? new Map<string, PyValue>([["exit_code", null], ["timed_out", false], ["wall_seconds", 0]])
      : await this.launcher(cmd, where, env, out, err, spec.timeout ?? 1800);
    const lines = jsonlLines(readText(out));
    const audit = claude ? auditClaudeStream(lines, specDict(spec, tools), where, this.hub.repo)
      : quizs ? auditQuizsStream(lines, specDict(spec, tools)) : auditPiStream(lines, specDict(spec, tools), where, this.hub.repo);
    if (blocked) audit.set("api_error", blocked); // 按接口报错走：不重试，阶段标为 failed，直接交给站主
    else if (!pyTruthy(pyGet(audit, "api_error"))) audit.set("api_error", interfaceProblem(specDict(spec), audit, result));
    if (claude) {
      audit.set("effort_requested", spec.effort ?? null);
      audit.set("effort_effective", claudeSessionEffort(id));
    } else {
      audit.set("effort_requested", spec.thinking ?? null);
      const levels = pyGet(audit, "effective_levels");
      audit.set("effort_effective", (Array.isArray(levels) ? levels : []).map((level) => level as string).join(",") || null);
    }
    let output: PyValue = null;
    let outputError: string | null = null;
    const apiError = pyGet(audit, "api_error");
    // quizs 退出码 3 带了 retry_at 的，审计已经给出解除时刻（第 137 轮），不再走限流正则
    const throttled = !claude && pyGet(audit, "rate_limited_until") === null && THROTTLE.search(pyTruthy(apiError) ? pyStrValue(apiError) : "") !== null;
    if (throttled) {
      // 第 38 轮：同一会话连着被限流就加倍退避，扣信到点再办；连着限流太多次照旧按接口报错交给站主。报错写了重置时刻就扣到那时
      const throttles = pyIntOf(pyGet(current, "throttles", 0n)) + 1n;
      current.set("throttles", throttles);
      if (throttles <= BigInt(THROTTLE_MAX_HOLDS)) {
        const now = this.sources.seconds();
        const reset = throttleReset(pyStrValue(apiError), now);
        audit.set("rate_limited_until", BigInt(reset ?? now + Math.min(THROTTLE_BACKOFF_SECONDS * 2 ** Number(throttles - 1n), THROTTLE_BACKOFF_MAX)));
      }
    } else {
      current.delete("throttles");
    }
    if (pyTruthy(pyGet(audit, "api_error"))) outputError = `模型接口报错（环境问题，不是工人的输出问题）：${pyStrValue(pyItem(audit, "api_error"))}`;
    else if (!pyTruthy(pyItem(audit, "violations"))) {
      [output, outputError] = pyTruthy(pyGet(audit, "delivery_error")) ? [null, pyStrValue(pyGet(audit, "delivery_error"))]
        : deliveredOutput(spec.role, pyGet(audit, "delivered"));
    }
    const [turnCost, sessionCost] = turnCostUsd(spec.adapter, current, pyGet(audit, "cost_usd"));
    current.set("turns", pyIntOf(pyGet(current, "turns", 0n)) + 1n);
    current.set("last_turn", turnId);
    if (sessionCost !== null) current.set("cost_usd_total", sessionCost);
    await this.hub.saveAgentSession(agent, sessionKey, current);
    const refusals = pyGet(audit, "deliver_refusals");
    const refused = Array.isArray(refusals) ? refusals : [];
    const summary = new Map<string, PyValue>([
      ["turn_id", turnId], ["agent", agent], ["session_key", sessionKey], ["session_id", id],
      ["first_turn", first], ["retry_of", retryOf], ["started_at", started], ["finished_at", utcNow()],
      ["exit_code", pyGet(result, "exit_code")], ["timed_out", pyTruthy(pyGet(result, "timed_out"))],
      ["wall_seconds", pyGet(result, "wall_seconds")], ["workspace", where],
      ["model_requested", spec.model ?? null], ["models", pyGet(audit, "models")],
      ["effort_requested", pyItem(audit, "effort_requested")], ["effort_effective", pyItem(audit, "effort_effective")],
      ["tool_calls", pyItem(audit, "tool_calls")], ["violations", pyItem(audit, "violations")], ["cost_usd", turnCost],
      ["session_cost_usd", sessionCost], ["usage", pyGet(audit, "usage")], ["terminal", pyGet(audit, "terminal")], ["output_error", outputError],
      ["api_error", pyGet(audit, "api_error")], ["warnings", pyTruthy(pyGet(audit, "warnings")) ? pyItem(audit, "warnings") : []],
      ["role_prompt_sha256", createHash("sha256").update(rolePrompt, "utf8").digest("hex")], ["hub_sha256", HUB_SHA256], ["hub_impl", hubImpl()],
      // 第 90 轮：怎么交差的，记下这个岗位的 schema（pi 还有扩展）的哈希；第 110 轮起一律是 "tool"
      ["delivery", quizs ? "final_json" : "tool"],
      ["delivery_sha256", new Map((claude || quizs ? [] : [purePathName(DELIVER_EXTENSION), purePathName(GUARD_EXTENSION)]).concat(`${spec.role}.json`).map((name) => [name, DELIVERY_SHA256.get(name) ?? null]))],
      // 第 102 轮：交差被工具退回几次、报错多长；思考的证据（第 103 轮分开记）
      ["deliver_refusals", BigInt(pyLenValue(refused))], ["deliver_refusal_chars", refused.reduce<bigint>((sum, chars) => sum + pyIntOf(chars), 0n)],
      ["thinking_chars", pyGet(audit, "thinking_chars")], ["thinking_tokens", pyGet(audit, "thinking_tokens")],
    ]);
    if (fallback !== null) summary.set("quizs_fallback", fallback);
    writeJson(join(turnDir, "result.json"), summary, true);
    await this.hub.appendEvent("turn.finished", [["turn_id", turnId], ["agent", agent], ["session_key", sessionKey],
      ["exit_code", pyItem(summary, "exit_code")], ["timed_out", pyItem(summary, "timed_out")], ["violations", BigInt(pyLenValue(pyItem(audit, "violations")))],
      ["output_ok", output !== null], ["effort_requested", pyItem(summary, "effort_requested")], ["effort_effective", pyItem(summary, "effort_effective")],
      ["cost_usd", turnCost], ["wall_seconds", pyItem(summary, "wall_seconds")], ["hub_impl", hubImpl()]]);
    summary.set("output", output);
    summary.set("turn_dir", turnDir);
    summary.set("rate_limited_until", pyGet(audit, "rate_limited_until"));
    return summary;
  }

  /** pd.Repo(hub.repo).config()；读不出（DispatchError）时是空的。 */
  private config(): PyDict {
    try {
      return configWithBytes(new Repo(this.hub.repo))[0];
    } catch (error) {
      if ((error as Error).name === "DispatchError") return new Map();
      throw error;
    }
  }

  private claudeCommand(spec: RosterSpec, rolePath: string, inputs: string | null, first: boolean, id: string, inline: string): string[] {
    const cmd = ["claude", "-p", "--model", spec.model ?? "", "--effort", spec.effort ?? "", "--output-format", "stream-json", "--verbose",
      "--setting-sources", "project", "--settings", dumps(new Map<string, PyValue>(Object.entries(CLAUDE_SETTINGS))),
      "--strict-mcp-config", "--disable-slash-commands", "--tools", (spec.tools ?? []).join(",")];
    if (spec.allowed_rules?.length) cmd.push("--allowedTools", ...spec.allowed_rules);
    // 第 88 轮：不再 --add-dir 主工作区；合同、信箱、长输入与执行证据由内核复制进只读输入目录，主工作区里只给已经装好的依赖
    const extras = [...(inputs !== null ? [inputs] : []), ...DEPENDENCY_DIRS.map((dep) => purePathStr(this.hub.repo, dep)).filter((path) => statOrNull(path)?.isDirectory())];
    for (const extra of extras) cmd.push("--add-dir", purePathStr(extra));
    const writes = ["Edit", "Write"].filter((tool) => (spec.tools ?? []).includes(tool));
    if (writes.length) {
      // 没有人能答权限提示：工作目录里的写入自动放行，主工作区与输入目录的写入一律拒绝（拒绝规则优先）
      cmd.push("--permission-mode", "acceptEdits", "--disallowedTools",
        ...writes.flatMap((tool) => [this.hub.repo, ...(inputs !== null ? [inputs] : [])].map((root) => `${tool}(${claudePathRule(root)})`)));
    }
    cmd.push("--permission-prompts", "none", "--append-system-prompt-file", rolePath);
    cmd.push("--json-schema", dumps(roleSchema(spec.role), { ensureAscii: false, separators: [",", ":"] }));
    cmd.push(...(first ? ["--session-id", id] : ["--resume", id]), inline);
    cmd[0] = pyWhich("claude") ?? "claude";
    return cmd;
  }

  /** 第 137 轮：quizs 回合的命令（不含 --read-snapshot：快照冻好了才知道），交回（命令, quizs 命令, 会话目录）。 */
  private quizsCommand(spec: RosterSpec, agent: string, tools: readonly string[], rolePath: string, turnDir: string, id: string,
    inputs: string | null, where: string): [string[], null, string[], string] {
    const sessionsDir = join(this.hub.root, "sessions", agent);
    const stateDir = join(this.hub.root, QUIZS_STATE_DIR);
    for (const folder of [sessionsDir, stateDir]) mkdirSync(folder, { recursive: true });
    const quizsCmd = resolveQuizsCommand();
    const deadlineMs = (this.sources.seconds() + (spec.timeout ?? 1800)) * 1000; // 取到秒：与 Python 的 int(time.time()) 一致
    const cmd = [...quizsCmd, "worker", "turn", "--provider", spec.provider ?? "", "--model", spec.model ?? "", "--thinking", spec.thinking ?? "",
      "--tools", inputs !== null ? tools.join(",") : "none",
      // Quizs 的 worker turn 要 --cwd 与 --readonly-root（已有的目录，记进会话的固定前缀；只读快照照样要）
      "--cwd", where, "--readonly-root", inputs ?? where,
      "--system-append", rolePath, "--prompt", `@${join(turnDir, "prompt.md")}`,
      "--session-dir", sessionsDir, "--session-id", id, "--deadline", String(deadlineMs), "--provider-state-dir", stateDir,
      ...QUIZS_TURN_BUDGETS.flat()];
    for (const [flag, name] of QUIZS_LIVE_FILES) {
      const value = process.env[name];
      if (value) cmd.push(flag, value);
    }
    return [cmd, null, quizsCmd, sessionsDir];
  }

  private piCommand(spec: RosterSpec, agent: string, tools: readonly string[], rolePath: string, turnDir: string, id: string): [string[], string[]] {
    const sessionsDir = join(this.hub.root, "sessions", agent);
    mkdirSync(sessionsDir, { recursive: true });
    // pi 的输入一律用 @文件 附上，命令行只放一句话；交差扩展与守卫扩展显式加载（--no-extensions 只关掉自动发现）
    const piCmd = resolvePiCommand();
    const cmd = [...piCmd, "--provider", spec.provider ?? "", "--model", spec.model ?? "", "--thinking", spec.thinking ?? "", "--mode", "json",
      ...RESOURCE_FLAGS, "--extension", DELIVER_EXTENSION, "--extension", GUARD_EXTENSION,
      "--no-context-files", "--tools", tools.join(","), "--append-system-prompt", rolePath, "--session-dir", sessionsDir,
      "--session-id", id, `@${join(turnDir, "prompt.md")}`, "按附件里的本回合输入办事。"];
    return [cmd, piCmd];
  }
}


function statOrNull(path: string): ReturnType<typeof statSync> | null {
  try {
    return statSync(path);
  } catch {
    return null;
  }
}
