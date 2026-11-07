// quizs 载体（第 137 轮，P1：名册没换，协调人照旧走 pi；换载体要站主同意）：kit_hub.py 的 resolve_quizs_command、fenced_json、
// quizs_snapshot、audit_quizs_stream。交付是最后回答里的一个 json 代码块（Quizs 的 v1 交付：result 的 final_text 就是这段回答），
// 内核再按岗位 schema 核验；输入目录交 quizs snapshot capture 冻成只读快照，建 git 树的事在 Quizs 里做一次。
import { pyGet, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyJsonError, type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { jsonlLines } from "@themis/base/jsonl";
import { pyStrip } from "@themis/base/pyre";
import { pyWhich } from "@themis/base/pyshutil";
import { runCapture } from "@themis/dispatcher/pi-cli";
import { EXIT_BLOCKED, QUIZS_FENCE_CLOSE, QUIZS_FENCE_OPEN, QUIZS_PERMIT_HELD, THROTTLE_RESET_MARGIN } from "./constants.ts";
import { HubError } from "./errors.ts";

const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);

/** quizs 的命令：QUIZS_CMD 是 JSON 的字符串列表（测试与开发时指向源码入口），缺省是 PATH 里的 quizs。 */
export function resolveQuizsCommand(): string[] {
  const raw = process.env["QUIZS_CMD"];
  if (!raw) return [pyWhich("quizs") ?? "quizs"];
  const value = loads(raw);
  if (!Array.isArray(value) || value.length === 0 || !value.every((item) => typeof item === "string" && item !== "")) {
    throw new HubError("QUIZS_CMD 要是非空的字符串列表（JSON）", EXIT_BLOCKED);
  }
  return value as string[];
}

/** quizs 回合的交付：最后的回答里恰好一个 json 代码块，内容是 JSON 对象；别的一律 null。 */
export function fencedJson(text: string): PyDict | null {
  const blocks: string[] = [];
  let current: string[] | null = null;
  for (const line of text.split(CR + LF).join(LF).split(LF)) {
    if (current === null) {
      if (pyStrip(line) === QUIZS_FENCE_OPEN) current = [];
    } else if (pyStrip(line) === QUIZS_FENCE_CLOSE) {
      blocks.push(current.join(LF));
      current = null;
    } else {
      current.push(line);
    }
  }
  if (blocks.length !== 1 || current !== null) return null;
  let value: PyValue;
  try {
    value = loads(blocks[0] as string);
  } catch (error) {
    if (error instanceof PyJsonError) return null;
    throw error;
  }
  return value instanceof Map ? value : null;
}

/** 这一回合的输入目录交给 quizs snapshot capture 冻成只读快照：交回（manifest_ref, 问题）。 */
export async function quizsSnapshot(quizsCmd: readonly string[], sessionsDir: string, inputs: string, env: Map<string, string>): Promise<[string | null, string | null]> {
  const gitExe = pyWhich("git");
  if (gitExe === null) return [null, "找不到 git，quizs 冻结不了这一回合的输入，没有起这一回合"];
  const [code, out] = await runCapture([...quizsCmd, "snapshot", "capture", "--session-dir", sessionsDir, "--dir", inputs, "--git-executable", gitExe],
    { env, timeout: 180 });
  const lines = jsonlLines(out).filter((line) => pyStrip(line) !== ""); // 输出以换行结尾：最后一个是空串
  let last: PyValue = null;
  try {
    last = lines.length > 0 ? loads(lines[lines.length - 1] as string) : null;
  } catch (error) {
    if (!(error instanceof PyJsonError)) throw error;
  }
  if (code !== 0 || !(last instanceof Map) || typeof last.get("manifest_ref") !== "string") {
    const reason = last instanceof Map ? pyGet(last, "error_class") : null;
    return [null, `quizs 冻结不了这一回合的输入（snapshot capture 退出码 ${code}，${pyTruthy(reason) ? pyStrValue(reason) : "读不出结果"}），没有起这一回合`];
  }
  return [last.get("manifest_ref") as string, null];
}

/**
 * quizs 回合的审计：逐行读 Quizs 的 JSONL。init 与 tool_call 里名册之外的工具算越权；result 给出退出码、模型、思考档位、用量与
 * 最后的回答（交付是其中一个 json 代码块）。退出码 3 带 retry_at 时直接扣到那时，不带时照第 38 轮的限流退避。
 */
export function auditQuizsStream(lines: readonly string[], spec: PyValue): PyDict {
  const allowed = new Set((pyGet(spec, "tools") as PyValue[]).map((tool) => pyStrValue(tool)));
  const violations: string[] = [];
  const warnings: string[] = [];
  const toolCalls: PyDict = new Map();
  const audit: PyDict = new Map<string, PyValue>([["violations", violations], ["tool_calls", toolCalls], ["models", []], ["effective_levels", []],
    ["usage", null], ["cost_usd", null], ["delivered", null], ["delivery_error", null], ["api_error", null], ["terminal", false], ["warnings", warnings],
    ["deliver_refusals", []], ["thinking_chars", null], ["thinking_tokens", null], ["rate_limited_until", null]]);
  let result: PyDict | null = null;
  for (const line of lines) {
    let event: PyValue;
    try {
      event = loads(line);
    } catch (error) {
      if (!(error instanceof PyJsonError)) throw error;
      warnings.push("quizs 的事件流里有读不出的行");
      continue;
    }
    if (!(event instanceof Map)) continue;
    const kind = event.get("type");
    if (kind === "init") {
      const tools = pyGet(event, "tools");
      for (const tool of pyTruthy(tools) ? (tools as PyValue[]) : []) {
        const name = tool instanceof Map ? pyGet(tool, "name") : null;
        if (!allowed.has(name as string)) violations.push(`quizs 给模型的工具里有名册之外的 ${pyStrValue(name)}`);
      }
    } else if (kind === "tool_call") {
      const name = pyGet(event, "name");
      toolCalls.set(name as string, ((toolCalls.get(name as string) as bigint | undefined) ?? 0n) + 1n);
      if (!allowed.has(name as string)) violations.push(`调了名册之外的工具 ${pyStrValue(name)}`);
    } else if (kind === "result") {
      result = event;
    }
  }
  if (result === null) {
    audit.set("api_error", "quizs 没有交回 result 事件（看这一回合的 stderr.log）");
    return audit;
  }
  audit.set("terminal", true);
  if (pyTruthy(pyGet(result, "actual_model"))) audit.set("models", [pyGet(result, "actual_model")]);
  const thinking = pyGet(result, "thinking");
  const effective = thinking instanceof Map ? pyGet(thinking, "effective") : null;
  if (pyTruthy(effective)) audit.set("effective_levels", [effective]);
  const usage = pyGet(result, "usage");
  if (usage instanceof Map && pyGet(usage, "total_input") !== null) {
    const count = (key: string): bigint => (pyTruthy(pyGet(usage, key)) ? (pyGet(usage, key) as bigint) : 0n);
    audit.set("usage", new Map<string, PyValue>([["input", (pyGet(usage, "total_input") as bigint) - count("cache_read") - count("cache_write")],
      ["cacheRead", count("cache_read")], ["cacheWrite", count("cache_write")], ["output", count("output")]]));
  }
  const code = pyGet(result, "exit_code");
  if (code !== 0n) {
    const errorClass = pyStrValue(pyGet(result, "error_class"));
    audit.set("api_error", errorClass === "QUEUE_TIMEOUT" ? QUIZS_PERMIT_HELD : `quizs 退出码 ${pyStrValue(code)}（${errorClass}）`);
    const retryAt = pyGet(result, "retry_at");
    if (code === 3n && typeof retryAt === "string") audit.set("rate_limited_until", BigInt(Math.floor(Date.parse(retryAt) / 1000) + THROTTLE_RESET_MARGIN));
    return audit;
  }
  const text = pyGet(result, "final_text");
  audit.set("delivered", fencedJson(pyTruthy(text) ? pyStrValue(text) : ""));
  if (audit.get("delivered") === null) audit.set("delivery_error", "最后的回答里没有恰好一个能解析成 JSON 对象的 json 代码块（quizs 用代码块交差）");
  return audit;
}
