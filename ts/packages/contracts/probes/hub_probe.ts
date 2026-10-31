// hub.call（第 ⑤a 片）：按函数名调 @themis/hub 的纯函数，参数与结果照 python_probe.py 的 op_hub_call。
// 结果里的整数照 Python 写成 int（bigint）；HubError 交回文字与退出码，Python 语义的异常只比类型。
import { PyCrash, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, PyJsonError, type PyValue } from "@themis/base/pyjson";
import { PyOverflowError, PyReError, PyValueError } from "@themis/base/pyregex";
import { accessSync, appendFileSync, chmodSync, constants as fsConstants, cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { basename, dirname, join, relative, sep } from "node:path";
import { readText, sleepSync } from "@themis/base/fsutil";
import { withFileLock } from "@themis/base/native";
import { PyOSError } from "@themis/base/pyio";
import { jsonlLines } from "@themis/base/jsonl";
import { cmpCodePoints } from "@themis/base/pyre";
import {
  auditClaudeStream, auditPiStream, claudePathRule, claudeSessionEffort, guardConfig, pathForms, piFlagsProblem, piReachProblem, sessionCutShort, streamEvents,
  turnCostUsd,
} from "@themis/hub/audit";
import * as constants from "@themis/hub/constants";
import { DELIVERY_SHA256, deliveredOutput, deliveryProblem, interfaceProblem, roleSchema, workerEnv, workerFileProblem } from "@themis/hub/delivery";
import { HubError } from "@themis/hub/errors";
import { removeInputs, stageInputs } from "@themis/hub/inputs";
import { INPUTS_INDEX } from "@themis/hub/constants";
import { type Launcher, REAL_SOURCES, TurnRunner, type TurnSources } from "@themis/hub/turn";
import { globPaths } from "@themis/dispatcher/instruction";
import { KERNEL_ROOT, TEMPLATE_DIR } from "@themis/hub/kernel";
import { DirLock, Hub, HubState, holdLetters, keepPrevious, ledgerEvents, letterMain, releaseHeld } from "@themis/hub/mailbox";
import { letterErrors, parseLetter, renderLetter, stageOf } from "@themis/hub/letters";
import {
  budgetUsage, engineeringRules, externalFactsSection, inputPath, letterFromOutput, nextContractVersion, regressionGates, renderTemplate, rolePrompt,
  transitionalSection, turnPrompt,
} from "@themis/hub/prompt";
import { schemaErrors, schemaProblems } from "@themis/hub/schema";
import {
  allowedMoves, dependents, gateFile, gatePattern, guard, hotfixReason, invalidateAfter, moveBase, newTaskState, renderRoutineBrief,
  returnStages, routineMoves, stageBusy, stageStatusTable, upstreamNotes,
} from "@themis/hub/taskstate";

type Result = Record<string, unknown>;

/** 信头：键与值都照字符串（Python 那边是 dict[str, str]）。 */
const metaOf = (value: PyValue | undefined): Map<string, string> =>
  new Map([...(value as PyDict)].map(([key, item]) => [String(key), pyStrValue(item)]));
const dictOf = (value: PyValue | undefined): PyDict => value as PyDict;
const fieldsOf = (value: PyValue | undefined): Map<string, PyValue> => new Map([...(value as PyDict)].map(([key, item]) => [String(key), item]));
const textOf = (value: PyValue | undefined): string => value as string;
const optionalText = (value: PyValue | undefined): string | null => (value === null || value === undefined ? null : (value as string));

function call(fn: string, args: PyValue[], repo: string): PyValue | undefined {
  const [a, b, c, d, e, f] = args;
  switch (fn) {
    case "stage_of":
      return stageOf(optionalText(a));
    case "render_letter":
      return renderLetter(metaOf(a), fieldsOf(b));
    case "parse_letter": {
      const [meta, fields, lines] = parseLetter(textOf(a));
      return [meta as PyDict, fields as PyDict, BigInt(lines)];
    }
    case "letter_errors":
      return letterErrors(metaOf(a), fieldsOf(b), Number(c));
    case "schema_problems":
      return schemaProblems(a as PyValue);
    case "schema_errors":
      return schemaErrors(dictOf(a), b as PyValue);
    case "new_task_state":
      return newTaskState(textOf(a), textOf(b), textOf(c), textOf(d), e === true, textOf(f));
    case "dependents":
      return dependents(textOf(a));
    case "return_stages":
      return returnStages(a);
    case "stage_busy":
      return stageBusy(a as PyValue);
    case "gate_pattern":
      return gatePattern(dictOf(a));
    case "gate_file":
      return gateFile(dictOf(a), textOf(b));
    case "invalidate_after":
      invalidateAfter(dictOf(a), textOf(b));
      return a;
    case "move_base":
      return [moveBase(dictOf(a), textOf(b)), a as PyValue];
    case "hotfix_reason":
      return hotfixReason(dictOf(a));
    case "guard":
      return guard(a === null ? null : dictOf(a), metaOf(b));
    case "allowed_moves":
      return allowedMoves(dictOf(a));
    case "routine_moves": {
      const [moves, reason] = routineMoves((a as PyValue[]).map(textOf));
      return [moves, reason];
    }
    case "render_routine_brief":
      return renderRoutineBrief(repo, dictOf(a), dictOf(b));
    case "stage_status_table":
      return stageStatusTable(dictOf(a));
    case "upstream_notes":
      return upstreamNotes(dictOf(a), optionalText(b));
    default:
      return undefined;
  }
}

export function hubCall(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Result {
  const args = (request["args"] as never[]).map(fromTagged);
  try {
    const value = call(String(request["fn"]), args, String(request["repo"] ?? "."));
    return value === undefined ? { ok: false, error: "UNKNOWN_FN" } : { ok: true, value: toTagged(value) };
  } catch (error) {
    if (error instanceof HubError) return { ok: false, error: "HubError", message: error.message, code: error.code };
    if (error instanceof PyCrash) return { ok: false, error: error.kind };
    if (error instanceof PyReError) return { ok: false, error: "error" };
    if (error instanceof PyValueError) return { ok: false, error: "ValueError" };
    if (error instanceof PyOverflowError) return { ok: false, error: "OverflowError" };
    return { ok: false, error: `JS:${(error as Error).name}:${(error as Error).message}` };
  }
}

/** 影子的一项：交回带标签的值，崩了只交回类型（与 python_probe.py 的 _shadow_one 一致）。 */
function shadowOne(fn: () => PyValue, toTagged: (value: PyValue) => unknown): Result {
  try {
    return { ok: true, value: toTagged(fn()) };
  } catch (error) {
    return { ok: false, error: crashKind(error) };
  }
}

function crashKind(error: unknown): string {
  if (error instanceof HubError) return "HubError";
  if (error instanceof PyCrash) return error.kind;
  if (error instanceof PyJsonError) return error.kind;
  if (error instanceof Error && error.name === "UnicodeDecodeError") return "UnicodeDecodeError";
  return `JS:${(error as Error).name}:${(error as Error).message}`;
}

/** 影子传来的原始字节：写进临时文件，用 base 的 readText 读出来（与 _shadow_text 一致，这一步本身也在比）。 */
function shadowText(b64: string): string {
  const dir = mkdtempSync(join(tmpdir(), "themis-shadow-"));
  try {
    writeFileSync(join(dir, "x"), Buffer.from(b64, "base64"));
    return readText(join(dir, "x"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/** hub.shadow_task（⑤-影子）：一个主任务的只读结论，与 python_probe.py 的 op_hub_shadow_task 一一对应。 */
export function hubShadowTask(request: Record<string, unknown>, toTagged: (value: PyValue) => unknown): Result {
  const hub = new Hub(String(request["repo"]));
  let ts: PyDict | null;
  try {
    ts = (hub.loadState().tasks().get(String(request["task"])) as PyDict | undefined) ?? null;
  } catch (error) {
    return { ok: true, items: [["load_state", { ok: false, error: crashKind(error) }]] };
  }
  const one = (fn: () => PyValue): Result => shadowOne(fn, toTagged);
  const items: [string, Result][] = [];
  if (ts !== null) {
    const task = ts;
    items.push(
      ["allowed_moves", one(() => allowedMoves(task))], ["stage_status_table", one(() => stageStatusTable(task))],
      ["hotfix_reason", one(() => hotfixReason(task))], ["gate_pattern", one(() => gatePattern(task))],
      ...["baseline", "whitebox"].map((kind): [string, Result] => [`gate_file ${kind}`, one(() => gateFile(task, kind))]),
      ...[null, ...constants.STAGE_ORDER].map((suffix): [string, Result] => [`upstream_notes ${suffix ?? "None"}`, one(() => upstreamNotes(task, suffix))]),
    );
  }
  for (const meta of request["metas"] as Record<string, string>[]) items.push(["guard", one(() => guard(ts, new Map(Object.entries(meta))))]);
  return { ok: true, items };
}

/** hub.shadow_letter（⑤-影子）：一封信的读出、解析、往返、形状校验与所属主任务，与 op_hub_shadow_letter 一一对应。 */
export function hubShadowLetter(request: Record<string, unknown>, toTagged: (value: PyValue) => unknown): Result {
  let text: string;
  try {
    text = shadowText(String(request["b64"]));
  } catch (error) {
    return { ok: true, items: [["read_text", { ok: false, error: crashKind(error) }]] };
  }
  const one = (fn: () => PyValue): Result => shadowOne(fn, toTagged);
  const items: [string, Result][] = [["read_text", one(() => text)]];
  let parsed: ReturnType<typeof parseLetter>;
  try {
    parsed = parseLetter(text);
  } catch (error) {
    return { ok: true, items: [...items, ["parse_letter", { ok: false, error: crashKind(error) }]] };
  }
  const [meta, fields, lines] = parsed;
  const reparse = (): PyValue => {
    const [again, againFields, againLines] = parseLetter(renderLetter(meta, fields));
    return [again as PyDict, againFields as PyDict, BigInt(againLines)];
  };
  items.push(
    ["parse_letter", one(() => [meta as PyDict, fields as PyDict, BigInt(lines)])], ["render_letter", one(() => renderLetter(meta, fields))],
    ["reparse", one(reparse)], ["letter_errors", one(() => letterErrors(meta, fields, lines))],
    ["stage_of", one(() => stageOf(meta.get("task-id") ?? null))],
  );
  return { ok: true, items };
}

/** hub.shadow_routine（⑤-影子）：一封写给协调人的信单独成批时的内核代办与任务书，与 op_hub_shadow_routine 一一对应。 */
export function hubShadowRoutine(request: Record<string, unknown>, toTagged: (value: PyValue) => unknown): Result {
  const repo = String(request["repo"]);
  let text: string;
  let routed: ReturnType<typeof routineMoves>;
  try {
    text = shadowText(String(request["b64"]));
    routed = routineMoves([text]);
  } catch (error) {
    return { ok: true, items: [["routine_moves", { ok: false, error: crashKind(error) }]] };
  }
  const [moves, reason] = routed;
  const one = (fn: () => PyValue): Result => shadowOne(fn, toTagged);
  const items: [string, Result][] = [["routine_moves", one(() => [moves, reason])]];
  if (!moves.length) return { ok: true, items };
  let ts: PyDict | undefined;
  try {
    const main = stageOf(parseLetter(text)[0].get("task-id") ?? "")[0];
    ts = new Hub(repo).loadState().tasks().get(typeof main === "string" ? main : "") as PyDict | undefined;
  } catch (error) {
    return { ok: true, items: [...items, ["ts", { ok: false, error: crashKind(error) }]] };
  }
  const task = ts;
  if (task !== undefined) for (const move of moves) items.push(["brief", one(() => renderRoutineBrief(repo, task, move as PyDict))]);
  return { ok: true, items };
}

/** hub.shadow_route（⑤-影子）：账本里一次 route.kernel 的那批信，重算 routine_moves，与 op_hub_shadow_route 一一对应。 */
export function hubShadowRoute(request: Record<string, unknown>, toTagged: (value: PyValue) => unknown): Result {
  try {
    const [moves, reason] = routineMoves((request["b64s"] as string[]).map(shadowText));
    return { ok: true, value: toTagged([moves, reason]) };
  } catch (error) {
    return { ok: false, error: crashKind(error) };
  }
}

/** hub.audit（第 ⑤c 片）：按函数名调 @themis/hub/audit，与 python_probe.py 的 op_hub_audit 一一对应。 */
export async function hubAudit(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  const args = (request["args"] as never[]).map(fromTagged);
  if (typeof request["home"] === "string") process.env["USERPROFILE"] = process.env["HOME"] = request["home"];
  const text = (value: PyValue | undefined): string => value as string;
  const optional = (value: PyValue | undefined): string | null => (value === null || value === undefined ? null : (value as string));
  const lines = (value: PyValue | undefined): string[] => value as string[];
  try {
    let value: PyValue;
    switch (String(request["fn"])) {
      case "turn_cost_usd":
        value = turnCostUsd(text(args[0]), args[1] as PyValue, args[2] as PyValue);
        break;
      case "stream_events": {
        const [events, unreadable] = streamEvents(lines(args[0]));
        value = [events, BigInt(unreadable)];
        break;
      }
      case "session_cut_short":
        value = sessionCutShort(new Hub(text(args[0])).root, text(args[1]), text(args[2]), text(args[3]));
        break;
      case "claude_path_rule":
        value = claudePathRule(text(args[0]));
        break;
      case "path_forms":
        value = pathForms(text(args[0]));
        break;
      case "audit_claude_stream":
        value = auditClaudeStream(lines(args[0]), args[1] as PyValue, optional(args[2]), optional(args[3]));
        break;
      case "audit_pi_stream":
        value = auditPiStream(lines(args[0]), args[1] as PyValue, optional(args[2]), optional(args[3]));
        break;
      case "pi_reach_problem":
        value = piReachProblem(text(args[0]), args[1] as PyValue, text(args[2]), optional(args[3]));
        break;
      case "guard_config":
        value = guardConfig(text(args[0]), text(args[1]));
        break;
      case "jsonl_lines":
        value = jsonlLines(text(args[0]));
        break;
      case "claude_session_effort":
        value = claudeSessionEffort(text(args[0]));
        break;
      case "pi_flags_problem": {
        const env = new Map(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
        value = await piFlagsProblem(lines(args[0]), lines(args[1]), env);
        break;
      }
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
    return { ok: true, value: toTagged(value) };
  } catch (error) {
    return errorResult(error);
  }
}

/** hub.prompt（第 ⑤d 片）：回合输入与交差核对，与 python_probe.py 的 op_hub_prompt 一一对应。template_dir、kernel_root 照参数传给
 * 读模板目录、内核仓库的两个函数；worker_env 只交回排好序的变量名（不比值）。 */
export function hubPrompt(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Result {
  const args = (request["args"] as never[]).map(fromTagged);
  const templateDir = typeof request["template_dir"] === "string" ? request["template_dir"] : TEMPLATE_DIR;
  const kernelRoot = typeof request["kernel_root"] === "string" ? request["kernel_root"] : KERNEL_ROOT;
  const [a, b, c, d, e, f, g, h, i, j] = args;
  if (typeof request["started"] === "string") writeFileSync(request["started"], ""); // 契约用：调用之前写一个标记，另一个进程据此掐时机
  try {
    let value: PyValue;
    switch (String(request["fn"])) {
      case "render_template":
        value = renderTemplate(textOf(a), [...dictOf(b)].map(([key, item]) => [String(key), item as string] as const), optionalText(c), templateDir);
        break;
      case "role_prompt":
        value = rolePrompt(textOf(a), templateDir, kernelRoot);
        break;
      case "engineering_rules":
        value = engineeringRules(kernelRoot);
        break;
      case "delivery_problem":
        value = deliveryProblem(textOf(a));
        break;
      case "role_schema":
        value = roleSchema(textOf(a));
        break;
      case "external_facts_section":
        value = externalFactsSection(dictOf(a));
        break;
      case "interface_problem":
        value = interfaceProblem(a as PyValue, b as PyValue, c as PyValue);
        break;
      case "transitional_section":
        value = transitionalSection(textOf(a));
        break;
      case "worker_file_problem":
        value = workerFileProblem(textOf(a));
        break;
      case "letter_from_output":
        value = letterFromOutput(textOf(a), textOf(b), c as PyValue);
        break;
      case "delivered_output":
        value = deliveredOutput(textOf(a), b as PyValue);
        break;
      case "next_contract_version":
        value = nextContractVersion(dictOf(a));
        break;
      case "input_path":
        value = inputPath(new Hub(textOf(a)), optionalText(b), c as PyValue);
        break;
      case "turn_prompt":
        value = turnPrompt(new Hub(textOf(a)), dictOf(b), textOf(c), textOf(d), e as PyValue[], textOf(f), g as PyValue, optionalText(h), i as PyValue, j as PyValue);
        break;
      case "regression_gates":
        value = regressionGates(new Hub(textOf(a)), dictOf(b));
        break;
      case "budget_usage": {
        const used = budgetUsage(new Hub(textOf(a)), dictOf(b));
        value = new Map<string, PyValue>([["attempts_started", BigInt(used.attempts_started)], ["wall_seconds_used", used.wall_seconds_used]]);
        break;
      }
      case "worker_env":
        value = [...workerEnv(a === null || a === undefined ? null : dictOf(a)).keys()].sort(cmpCodePoints);
        break;
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
    return { ok: true, value: toTagged(value) };
  } catch (error) {
    return errorResult(error);
  }
}

/** 一个目录下的文件（相对路径用正斜杠、排好序）：字节数、可不可写、sha256；与 python_probe.py 的 _tree_listing 对应。 */
function treeListing(root: string): PyValue[] {
  const rows: [string, PyValue][] = [];
  const walk = (dir: string): void => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else {
        let writable = true;
        try {
          accessSync(path, fsConstants.W_OK);
        } catch {
          writable = false;
        }
        const rel = relative(root, path).split(sep).join("/");
        rows.push([rel, [rel, BigInt(statSync(path).size), writable, createHash("sha256").update(readFileSync(path)).digest("hex")]]);
      }
    }
  };
  walk(root);
  return rows.sort(([a], [b]) => cmpCodePoints(a, b)).map(([, row]) => row);
}

/** hub.inputs（第 ⑤d 片）：stage_inputs 与 remove_inputs，与 python_probe.py 的 op_hub_inputs 一一对应。 */
export function hubInputs(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Result {
  const hub = new Hub(String(request["repo"]));
  const restore = request["restore"] as Restore | undefined;
  if (restore !== undefined) restoreTree(restore);
  try {
    if (typeof request["remove"] === "string") {
      removeInputs(request["remove"]);
      return { ok: true, value: toTagged(existsSync(request["remove"])) };
    }
    // 采样的重放（⑤d2）：对应 inputs_fixture 换掉的 worktree_root 与 INPUT_FILE_LIMIT
    const root = request["worktree_root"];
    const limit = request["input_file_limit"];
    const [target, info] = stageInputs(hub, fromTagged(request["ts"] as never) as PyDict, String(request["key"]),
      { ...(typeof root === "string" ? { root } : {}), ...(typeof limit === "number" ? { limit } : {}) });
    const raw = (name: string): PyValue => (existsSync(join(target, name)) && statSync(join(target, name)).isFile() ? readFileSync(join(target, name)).toString("base64") : null);
    return { ok: true, value: toTagged(new Map<string, PyValue>([["dir", target], ["info", info], ["files", treeListing(target)], ["index", raw(INPUTS_INDEX)], ["skipped", raw("SKIPPED.md")],
      ["siblings", readdirSync(dirname(target)).sort(cmpCodePoints)]])) };
  } catch (error) {
    return errorResult(error);
  }
}

/** 回合里内核自己定下的环境变量：比值（别的只比名字）。 */
const KERNEL_SET_ENV = ["THEMIS_DELIVER_SCHEMA", "THEMIS_GUARD", "CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR"];
/** 采样重放的快照：from 原样放回 to，links（[相对路径, 指向, 种类]）照记下的重建（快照里没有它们，见 python_probe.py 的 _snapshot_tree）。 */
interface Restore {
  readonly from: string;
  readonly to: string;
  readonly links?: readonly (readonly [string, string, string])[];
}
/** 把快照原样放回原来的位置（采样的重放：两边先后在调用当时的那个目录里跑）；只读的文件先改回可写再删，链接与联接照记下的重建。 */
function restoreTree({ from: source, to: target, links = [] }: Restore): void {
  const writable = (dir: string): void => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      const info = lstatSync(path);
      if (info.isDirectory()) writable(path);
      else if (!info.isSymbolicLink()) chmodSync(path, 0o666);
    }
  };
  if (existsSync(target)) {
    writable(target);
    rmSync(target, { recursive: true, force: true });
  }
  cpSync(source, target, { recursive: true, verbatimSymlinks: true });
  for (const [rel, pointed, kind] of links) symlinkSync(pointed, join(target, ...rel.split("/")), kind as "dir" | "file" | "junction");
}

/** hub.turn（第 ⑤d 片）：TurnRunner.run 配回放的 launcher，与 python_probe.py 的 op_hub_turn 一一对应。 */
export async function hubTurn(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  const hub = new Hub(String(request["repo"]));
  const script: PyDict = request["script"] === undefined || request["script"] === null ? new Map() : (fromTagged(request["script"] as never) as PyDict);
  const restore = request["restore"] as Restore | undefined;
  if (restore !== undefined) restoreTree(restore);
  const calls: PyValue[] = [];
  const launcher: Launcher = async (cmd, cwd, env, out, err, timeout) => {
    calls.push(new Map<string, PyValue>([["cmd", [...cmd]], ["cwd", cwd], ["env", [...env.keys()].sort(cmpCodePoints)],
      ["kernel_env", new Map<string, PyValue>(KERNEL_SET_ENV.map((name) => [name, env.get(name) ?? null]))], ["timeout", BigInt(timeout)]]));
    appendFileSync(out, Buffer.from(String(script.get("stdout") ?? ""), "base64"));
    appendFileSync(err, Buffer.from(String(script.get("stderr") ?? ""), "base64"));
    return new Map<string, PyValue>([["exit_code", script.has("exit_code") ? (script.get("exit_code") as PyValue) : 0n], ["timed_out", pyTruthy(script.get("timed_out"))],
      ["wall_seconds", script.has("wall_seconds") ? (script.get("wall_seconds") as PyValue) : 1.5]]);
  };
  const given = request["sources"] as Record<string, unknown> | undefined; // 不给时用真的来源：形状核对用
  const sources: TurnSources = given === undefined ? REAL_SOURCES
    : { compact: () => String(given["compact"]), random2: () => String(given["random2"]), uuid4: () => String(given["uuid4"]), seconds: () => Number(given["seconds"]) };
  if (typeof request["home"] === "string") process.env["USERPROFILE"] = process.env["HOME"] = request["home"];
  const ledger = hub.ledger();
  const offset = existsSync(ledger) ? statSync(ledger).size : 0;
  const [agent, key, workspace, role, prompt, retryOf, fresh, inputs, sessionId] = (request["args"] as never[]).map(fromTagged);
  // 名册与交差文件的哈希：调用期间换成给定的值（只在探针里改，调用完还原；与 Python 那边的 monkeypatch 一样）
  const roster = constants.ROSTER as Record<string, constants.RosterSpec>;
  const shas = DELIVERY_SHA256 as Map<string, string | null>;
  const givenRoster = (request["roster"] ?? {}) as Record<string, constants.RosterSpec>;
  const givenShas = (request["delivery_sha256"] ?? {}) as Record<string, string>;
  const savedRoster = Object.keys(givenRoster).map((name) => [name, Object.hasOwn(roster, name) ? roster[name] : undefined] as const);
  const savedShas = Object.keys(givenShas).map((name) => [name, shas.has(name) ? shas.get(name) : undefined] as const);
  Object.assign(roster, givenRoster);
  for (const [name, value] of Object.entries(givenShas)) shas.set(name, value);
  const givenEnv = (request["env"] ?? {}) as Record<string, string>;
  const savedEnv = Object.keys(givenEnv).map((name) => [name, process.env[name]] as const);
  Object.assign(process.env, givenEnv);
  let summary: PyDict;
  try {
    summary = await new TurnRunner(hub, launcher, sources).run(textOf(agent), textOf(key), textOf(workspace), textOf(role), textOf(prompt), optionalText(retryOf),
      Boolean(fresh), optionalText(inputs), optionalText(sessionId));
  } catch (error) {
    return errorResult(error);
  } finally {
    for (const [name, value] of savedRoster) {
      if (value === undefined) delete roster[name];
      else roster[name] = value;
    }
    for (const [name, value] of savedShas) {
      if (value === undefined) shas.delete(name);
      else shas.set(name, value);
    }
    for (const [name, value] of savedEnv) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
  const turnDir = String(summary.get("turn_dir"));
  const b64 = (path: string): string => readFileSync(path).toString("base64");
  const files = new Map<string, PyValue>(readdirSync(turnDir).sort(cmpCodePoints).map((name) => [name, b64(join(turnDir, name))]));
  const longPrompts = new Map<string, PyValue>(inputs === null ? [] : globPaths(textOf(inputs), ["prompt-*.md"]).sort().map((path) => [basename(path), b64(path)]));
  const record = hub.agentPath(textOf(agent));
  const tail = existsSync(ledger) ? readFileSync(ledger).subarray(offset) : Buffer.alloc(0);
  return { ok: true, value: toTagged(new Map<string, PyValue>([["summary", summary], ["calls", calls], ["files", files], ["long_prompts", longPrompts],
    ["agent", existsSync(record) ? b64(record) : null], ["ledger", tail.toString("base64")]])) };
}

/** hub.constants（第 132 轮）：按名字取 @themis/hub/constants 的常量，转成 JSON 交回；与 python_probe.py 的 op_hub_constants 对应。 */
export function hubConstants(request: Record<string, unknown>): Result {
  const table = constants as Record<string, unknown>;
  return { ok: true, json: JSON.stringify(Object.fromEntries((request["names"] as string[]).map((name) => [name, table[name]]))) };
}

/** hub.box（第 ⑤b 片）：在 repo 的信箱上按 steps 依次执行，交回每一步的结果；与 python_probe.py 的 op_hub_box 一一对应。 */
export async function hubBox(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  const hub = new Hub(String(request["repo"]));
  const states = new Map<string, HubState>();
  const results: Result[] = [];
  const tasksOf = (name: string): PyDict => (states.get(name) as HubState).tasks();
  const optional = (value: PyValue | undefined): string | null => (value === null || value === undefined ? null : String(value));
  const hold = async (task: PyValue | undefined, agent: PyValue | undefined, names: PyValue | undefined, until: number, rest: PyValue[]): Promise<PyValue> => {
    const state = hub.loadState();
    const [suffix, turn, reason] = rest;
    const held = await holdLetters(hub, state.tasks().get(String(task)) as PyDict, String(agent), (names as PyValue[]).map(String), until, optional(suffix),
      String(turn), optional(reason));
    await hub.saveState(state);
    return held;
  };
  for (const step of request["steps"] as unknown[][]) {
    const name = String(step[0]);
    const args = step.slice(1).map((item) => fromTagged(item as never));
    try {
      let value: PyValue = null;
      switch (name) {
        case "ensure":
          hub.ensure();
          break;
        case "save_dict":
          await hub.saveState(args[0] as PyDict);
          break;
        case "load":
          states.set(String(args[0]), hub.loadState());
          break;
        case "set":
          (tasksOf(String(args[0])).get(String(args[1])) as PyDict).set(String(args[2]), args[3] as PyValue);
          break;
        case "del": {
          const ts = tasksOf(String(args[0])).get(String(args[1])) as PyDict;
          if (!ts.has(String(args[2]))) throw new PyCrash("KeyError", String(args[2]));
          ts.delete(String(args[2]));
          break;
        }
        case "new_task":
          tasksOf(String(args[0])).set(String(args[1]), args[2] as PyValue);
          break;
        case "save":
          await hub.saveState(states.get(String(args[0])) as HubState);
          break;
        case "signal":
          process.stderr.write("ready" + String.fromCharCode(10));
          break;
        case "wait":
          while (!existsSync(String(args[0]))) sleepSync(5);
          break;
        case "read_state":
          value = hub.readState();
          break;
        case "deliver":
          value = await hub.deliver(metaOf(args[0]), fieldsOf(args[1]));
          break;
        case "unread":
          value = hub.unread(String(args[0])).map((path) => path.slice(path.lastIndexOf(SEP) + 1));
          break;
        case "take_first": {
          const first = hub.unread(String(args[0]))[0];
          if (first === undefined) throw new PyCrash("IndexError", "list index out of range");
          value = relative(hub.root, await hub.take(first)).split(SEP).join("/");
          break;
        }
        case "save_agent_record":
          hub.saveAgentRecord(String(args[0]), args[1] as PyDict);
          break;
        case "save_agent_session":
          await hub.saveAgentSession(String(args[0]), String(args[1]), args[2] as PyValue);
          break;
        case "agent_record":
          value = hub.agentRecord(String(args[0]));
          break;
        case "hold": {
          const [task, agent, names, until, ...rest] = args;
          value = await hold(task, agent, names, Number(until), rest);
          break;
        }
        case "hold_until_now": {
          // 到点的边界：等到新的一秒开头再扣，until 就是这一秒；紧接着的 release 落在同一秒里
          sleepSync(1000 - (Date.now() % 1000));
          const [task, agent, names, ...rest] = args;
          value = await hold(task, agent, names, Math.floor(Date.now() / 1000), rest);
          break;
        }
        case "hold_file_lock":
          await withFileLock(join(hub.repo, String(args[0])), () => {
            process.stderr.write("ready" + String.fromCharCode(10));
            sleepSync(Number(args[1]));
            writeFileSync(join(hub.repo, String(args[2])), "");
          });
          break;
        case "exists":
          value = existsSync(join(hub.repo, String(args[0])));
          break;
        case "release":
          value = await releaseHeld(hub);
          break;
        case "ledger_events":
          value = ledgerEvents(hub);
          break;
        case "write_file": {
          const target = join(hub.repo, String(args[0]));
          mkdirSync(dirname(target), { recursive: true });
          writeFileSync(target, String(args[1]), "utf8");
          break;
        }
        case "keep_previous":
          keepPrevious(join(hub.repo, String(args[0])));
          break;
        case "letter_main":
          value = letterMain(join(hub.repo, String(args[0])));
          break;
        case "dirlock": {
          const lock = new DirLock(join(hub.repo, String(args[0])), Number(args[1])).acquire();
          try {
            sleepSync(Number(args[2]));
          } finally {
            lock.release();
          }
          break;
        }
        default:
          value = new Map([["unknown_step", name]]);
      }
      results.push({ ok: true, value: toTagged(value) });
    } catch (error) {
      results.push(errorResult(error));
    }
  }
  return { ok: true, results };
}

const SEP = process.platform === "win32" ? String.fromCharCode(92) : "/";

/** OSError(errno, ...) 在 Python 里按 errno 成了哪个子类。 */
const OS_ERRORS: Readonly<Record<number, string>> = { 2: "FileNotFoundError", 13: "PermissionError", 17: "FileExistsError", 20: "NotADirectoryError", 21: "IsADirectoryError" };

function errorResult(error: unknown): Result {
  if (error instanceof HubError) return { ok: false, error: "HubError", message: error.message, code: error.code };
  if (error instanceof PyCrash) return { ok: false, error: error.kind };
  if (error instanceof PyJsonError) return { ok: false, error: error.kind };
  if (error instanceof PyOSError) return { ok: false, error: OS_ERRORS[error.errno] ?? "OSError" }; // Python 按 errno 选的子类
  const code = (error as NodeJS.ErrnoException).code;
  if (code === "ENOENT") return { ok: false, error: "FileNotFoundError" };
  if (code === "EEXIST") return { ok: false, error: "FileExistsError" };
  if (code === "EPERM" || code === "EACCES" || code === "EBUSY") return { ok: false, error: "PermissionError" };
  return { ok: false, error: `JS:${(error as Error).name}:${(error as Error).message}` };
}
