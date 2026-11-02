// hub.call（第 ⑤a 片）：按函数名调 @themis/hub 的纯函数，参数与结果照 python_probe.py 的 op_hub_call。
// 结果里的整数照 Python 写成 int（bigint）；HubError 交回文字与退出码，Python 语义的异常交回类型与文字（⑤f 起文字也比）。
import { PyCrash, pyGet, pyItem, pyReprValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { PyOverflowError, PyReError, PyValueError } from "@themis/base/pyregex";
import { accessSync, appendFileSync, chmodSync, constants as fsConstants, cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { basename, dirname, join, relative, sep } from "node:path";
import { readText, sleepSync } from "@themis/base/fsutil";
import { withFileLock } from "@themis/base/native";
import { PyOSError } from "@themis/base/pyio";
import { PyWinError } from "@themis/base/pyos";
import { jsonlLines } from "@themis/base/jsonl";
import { cmpCodePoints, pySplitlines, pyStrip } from "@themis/base/pyre";
import { withPinnedClock } from "@themis/base/clock";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { spawnSync } from "node:child_process";
import { type ContractDeps, REAL_DEPS, acceptContract, acceptGatePre, bumpContractVersion, revalidateContract, setContractBase, syncExecutorLine } from "@themis/hub/accept";
import {
  type GatePostDeps, REAL_GATE_POST_DEPS, acceptGatePost, applyCandidate, attemptBase, candidateDefects, defectMatchProblems, defectMatches, ensureWorktree,
  expectedMissedEverywhere, gateSpec, mutantTimeout, mutationProblems, runMutations, seedWhitebox, unchangedMismatches, unmutatedProblems,
} from "@themis/hub/gatepost";
import {
  EXEC_LAND_WAIT_SECONDS, type ExecDeps, REAL_EXEC_DEPS, askSession, dispatchAttempt, ensureReworkScope, finalAuditTurn, finishExec, rebaseCandidate,
  reworkAddedFiles, runExec, runJev, startRework, startRetry, writeReview,
} from "@themis/hub/runexec";
import { DEFAULT_BASE_URL, type Settings } from "@themis/config/decisions";
import { ENDPOINT_PATH, httpTransport } from "@themis/config/decisions-client";
import { normcase } from "@themis/base/pypath";
import type { SuperviseOptions } from "@themis/base/supervise";
import {
  auditClaudeStream, auditPiStream, claudePathRule, claudeSessionEffort, guardConfig, pathForms, piFlagsProblem, piReachProblem, sessionCutShort, streamEvents,
  turnCostUsd,
} from "@themis/hub/audit";
import * as constants from "@themis/hub/constants";
import {
  answersQuestion, budgetProblems, contractDigest, contractPaths, contractRequirements, decisionsSection, dodCoverageProblems, externalFactProblems,
  hollowBaselineProblems, normalizeIdentity, normalizeMarkup, pytestOutcomes, scopeMissingPrefix, stripDecisions, tail, tailFile, unparsedCheckIds, unverifiedFacts,
} from "@themis/hub/contract";
import {
  CONFIG_ACTION_FAMILIES, TS_CONFIG_COMMANDS, TS_DISPATCHER_COMMANDS, TS_ONLY_COMMANDS, TS_READONLY_COMMANDS, argvImpl, readKernelImpl,
} from "@themis/dispatcher/kernel-impl";
import { DispatchError } from "@themis/dispatcher/repo";
import { DELIVERY_SHA256, deliveredOutput, deliveryProblem, interfaceProblem, roleSchema, workerEnv, workerFileProblem } from "@themis/hub/delivery";
import { HubError } from "@themis/hub/errors";
import { removeInputs, stageInputs } from "@themis/hub/inputs";
import { INPUTS_INDEX } from "@themis/hub/constants";
import { type Launcher, REAL_SOURCES, TurnRunner, type TurnSources } from "@themis/hub/turn";
import { globPaths } from "@themis/dispatcher/instruction";
import { KERNEL_ROOT, TEMPLATE_DIR, workspaceStatus } from "@themis/hub/kernel";
import { kernelEnv, kernelPytest, kernelPytestEnv, runPd, setKernelPython } from "@themis/hub/runpd";
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
import {
  addModifiedFiles, attemptsLeft, carryBack, carrySource, carryable, checksPassed, cutOff, emptyCommit, failedAttempt, failedChecksBrief, failureLines, gateClaims,
  interruptedAttempt, jevFlag, latestChecks, reportLeftovers, retrySection, reworkCommits, reworkSection, reworkSource, returnedBlockers, unfinishedWhy,
  unreportedGateClaims,
} from "@themis/hub/exec";
import { PySet } from "@themis/base/pyset";
import { copyTreeTimes } from "../src/tree-times.ts";

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
    if (error instanceof PyCrash) return { ok: false, error: error.kind, message: error.message };
    if (error instanceof PyReError) return { ok: false, error: "error", message: error.message };
    if (error instanceof PyValueError) return { ok: false, error: "ValueError", message: error.message };
    if (error instanceof PyOverflowError) return { ok: false, error: "OverflowError", message: error.message };
    return { ok: false, error: `JS:${(error as Error).name}:${(error as Error).message}` };
  }
}

/** 影子的一项：交回带标签的值，崩了交回类型与文字（与 python_probe.py 的 _shadow_one 一致）。 */
function shadowOne(fn: () => PyValue, toTagged: (value: PyValue) => unknown): Result {
  try {
    return { ok: true, value: toTagged(fn()) };
  } catch (error) {
    return { ok: false, error: crashKind(error), message: (error as Error).message };
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
    return { ok: true, items: [["load_state", { ok: false, error: crashKind(error), message: (error as Error).message }]] };
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
    return { ok: true, items: [["read_text", { ok: false, error: crashKind(error), message: (error as Error).message }]] };
  }
  const one = (fn: () => PyValue): Result => shadowOne(fn, toTagged);
  const items: [string, Result][] = [["read_text", one(() => text)]];
  let parsed: ReturnType<typeof parseLetter>;
  try {
    parsed = parseLetter(text);
  } catch (error) {
    return { ok: true, items: [...items, ["parse_letter", { ok: false, error: crashKind(error), message: (error as Error).message }]] };
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
    return { ok: true, items: [["routine_moves", { ok: false, error: crashKind(error), message: (error as Error).message }]] };
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
    return { ok: true, items: [...items, ["ts", { ok: false, error: crashKind(error), message: (error as Error).message }]] };
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
    return { ok: false, error: crashKind(error), message: (error as Error).message };
  }
}

/** hub.audit（第 ⑤c 片）：按函数名调 @themis/hub/audit，与 python_probe.py 的 op_hub_audit 一一对应。home 只在调用期间设（⑤e1b，照 hub.turn）。 */
export async function hubAudit(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  const home = typeof request["home"] === "string" ? request["home"] : null;
  const saved = [process.env["USERPROFILE"], process.env["HOME"]] as const;
  if (home !== null) process.env["USERPROFILE"] = process.env["HOME"] = home;
  try {
    return await auditCall(request, fromTagged, toTagged);
  } finally {
    if (home !== null) {
      for (const [name, before] of [["USERPROFILE", saved[0]], ["HOME", saved[1]]] as const) {
        if (before === undefined) delete process.env[name];
        else process.env[name] = before;
      }
    }
  }
}

async function auditCall(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  const args = (request["args"] as never[]).map(fromTagged);
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

/** sorted(元组)：逐项按码点比，短的是前缀时排前面。 */
function compareWords(left: string[], right: string[]): number {
  for (let at = 0; at < Math.min(left.length, right.length); at += 1) {
    const order = cmpCodePoints(left[at] as string, right[at] as string);
    if (order !== 0) return order;
  }
  return left.length - right.length;
}

/** hub.contract（第 ⑤e 片）：合同与战前门禁，与 python_probe.py 的 op_hub_contract 一一对应。参数照原值交给函数，类型不对时由它照 Python 抛。 */
export async function hubContract(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  const args = (request["args"] as never[]).map(fromTagged);
  const [a, b] = args as [PyValue, PyValue];
  for (const item of (request["restores"] as Restore[] | undefined) ?? []) restoreTree(item); // ⑤e2a：调用当时的快照（带 .git）
  if (typeof request["python"] === "string") setKernelPython(request["python"]);
  const givenEnv = Object.entries((request["env"] as Record<string, string> | undefined) ?? {});
  const savedEnv = givenEnv.map(([name]) => [name, process.env[name]] as const);
  for (const [name, value] of givenEnv) process.env[name] = value;
  try {
    let value: PyValue;
    switch (String(request["fn"])) {
      case "tail":
        value = args.length > 1 ? tail(a, b) : tail(a);
        break;
      case "tail_file":
        // 显式给的 null 照传（Python 遇到 None 报 TypeError），没给的才用缺省值
        value = tailFile(textOf(a), args.length > 1 ? (args[1] as PyValue) : 30n, (args.length > 2 ? args[2] : 65536n) as number | bigint);
        break;
      case "normalize_identity":
        value = normalizeIdentity(a, b);
        break;
      case "normalize_markup":
        value = normalizeMarkup(a);
        break;
      case "strip_decisions":
        value = stripDecisions(a);
        break;
      case "decisions_section":
        value = decisionsSection(a);
        break;
      case "unparsed_check_ids":
        value = unparsedCheckIds(a);
        break;
      case "external_fact_problems":
        value = externalFactProblems(a);
        break;
      case "unverified_facts":
        value = unverifiedFacts(a);
        break;
      case "pytest_outcomes":
        value = pytestOutcomes(textOf(a));
        break;
      case "contract_paths":
        value = contractPaths(new Hub(textOf(a)), b);
        break;
      case "scope_missing_prefix":
        value = scopeMissingPrefix(new Hub(textOf(a)), b);
        break;
      case "contract_requirements":
        value = contractRequirements(new Hub(textOf(a)), b as PyDict);
        break;
      case "dod_coverage_problems":
        value = dodCoverageProblems(new Hub(textOf(a)), b as PyDict, args[2] as PyValue);
        break;
      case "budget_problems":
        value = budgetProblems(new Hub(textOf(a)), b as PyDict);
        break;
      case "answers_question":
        value = answersQuestion(new Hub(textOf(a)), b);
        break;
      case "read_kernel_impl":
        value = readKernelImpl(textOf(a));
        break;
      case "argv_impl":
        value = argvImpl(a as string[], b, textOf(args[2] as PyValue));
        break;
      case "workspace_status":
        value = workspaceStatus(textOf(a));
        break;
      case "contract_digest":
        value = contractDigest(new Hub(textOf(a)), b);
        break;
      case "hollow_baseline_problems":
        value = hollowBaselineProblems(new Hub(textOf(a)), b, args[2] as PyValue);
        break;
      case "run_pd": {
        // 交回结果与账本新增的行（不带 at），同 python_probe.py
        const hub = new Hub(textOf(a));
        const before = existsSync(hub.ledger()) ? statSync(hub.ledger()).size : 0;
        // 没给 impl_path 时走 runPd 自己的缺省（内核目录下的选择文件，待办第 26 项）
        const implPath = request["impl_path"];
        const [code, out] = typeof implPath === "string" ? await runPd(hub, b as string[], Number(args[2]), implPath) : await runPd(hub, b as string[], Number(args[2]));
        const added = existsSync(hub.ledger()) ? pySplitlines(readFileSync(hub.ledger()).subarray(before).toString("utf8")) : [];
        const events = added.map((line) => new Map([...(loads(line) as PyDict)].filter(([key]) => key !== "at")));
        value = new Map<string, PyValue>([["result", [BigInt(code), out]], ["events", events]]);
        break;
      }
      case "kernel_env":
      case "kernel_pytest_env": {
        // 原样的名字（排好序）；值只交 PYTHONDONTWRITEBYTECODE 一个（不是凭据），同 python_probe.py
        const env = request["fn"] === "kernel_env" ? kernelEnv() : kernelPytestEnv();
        value = [[...env.keys()].sort(cmpCodePoints), env.get("PYTHONDONTWRITEBYTECODE") ?? null];
        break;
      }
      case "kernel_pytest":
        value = kernelPytest();
        break;
      case "mutant_timeout": // ⑤f 的纯函数与只读文件的几个
        value = mutantTimeout(a, b);
        break;
      case "expected_missed_everywhere":
        value = expectedMissedEverywhere(a);
        break;
      case "defect_matches":
        value = defectMatches(textOf(a), textOf(b));
        break;
      case "defect_match_problems":
        value = defectMatchProblems(a as PyDict[], b as string[]);
        break;
      case "mutation_problems":
        value = mutationProblems(a, b, args[2] as PyValue);
        break;
      case "unchanged_mismatches":
        value = unchangedMismatches(dictOf(a), b);
        break;
      case "candidate_defects":
        value = candidateDefects(a);
        break;
      case "gate_spec":
        value = gateSpec(textOf(a), b);
        break;
      case "attempt_base":
        value = attemptBase(dictOf(a), textOf(b));
        break;
      case "unmutated_problems": // 连同改过的 ts["gate_post"]["unmutated"]，同 python_probe.py
        value = [unmutatedProblems(dictOf(a), b, args[2] as PyValue), pyGet(pyItem(a, "gate_post"), "unmutated")];
        break;
      case "latest_checks": // ⑤g1：参数是 attempt 目录
        value = latestChecks(textOf(a));
        break;
      case "cut_off":
        value = cutOff(textOf(a));
        break;
      case "checks_passed":
        value = checksPassed(textOf(a));
        break;
      case "unfinished_why":
        value = unfinishedWhy(textOf(a));
        break;
      case "failed_checks_brief":
        value = failedChecksBrief(textOf(a));
        break;
      case "failure_lines":
        value = failureLines(textOf(a));
        break;
      case "report_leftovers":
        value = reportLeftovers(textOf(a));
        break;
      case "unreported_gate_claims":
        value = unreportedGateClaims(textOf(a));
        break;
      case "interrupted_attempt": // 交回 Path 或（Path, 原因），同 python_probe.py
        value = interruptedAttempt(new Hub(textOf(a)), dictOf(b));
        break;
      case "carry_back":
        value = carryBack(new Hub(textOf(a)), dictOf(b), args[2] as PyValue);
        break;
      case "carry_source":
        value = carrySource(new Hub(textOf(a)), dictOf(b));
        break;
      case "rework_source":
        value = reworkSource(dictOf(a));
        break;
      case "failed_attempt":
        value = failedAttempt(dictOf(a));
        break;
      case "attempts_left":
        value = attemptsLeft(new Hub(textOf(a)), dictOf(b));
        break;
      case "empty_commit":
        value = emptyCommit(new Hub(textOf(a)), textOf(b));
        break;
      case "rework_commits": // 集合交回按 repr 排好的列表
        value = reworkCommits(dictOf(a)).values().sort((x, y) => cmpCodePoints(pyReprValue(x), pyReprValue(y)));
        break;
      case "carryable": // carried 给的是列表，照调用方换成集合
        value = args.length > 1 ? carryable(textOf(a), new PySet(b as PyValue[])) : carryable(textOf(a));
        break;
      case "returned_blockers":
        value = returnedBlockers(dictOf(a), textOf(b));
        break;
      case "retry_section":
        value = retrySection(textOf(a), dictOf(b), args[2] as PyValue);
        break;
      case "rework_section":
        value = reworkSection(textOf(a), b, args[2] as PyValue, args[3] as PyValue, ...(args.slice(4) as PyValue[]));
        break;
      case "add_modified_files":
        value = addModifiedFiles(textOf(a), b as string[]);
        break;
      case "gate_claims":
        value = gateClaims(a);
        break;
      case "jev_flag":
        value = jevFlag(a, b, args[2] as PyValue);
        break;
      case "kernel_impl_tables": {
        const keys = (rows: ReadonlySet<string>): PyValue[] => [...rows].map((row) => JSON.parse(row) as string[]).sort(compareWords);
        value = new Map<string, PyValue>([
          ["TS_READONLY_COMMANDS", keys(TS_READONLY_COMMANDS)], ["TS_ONLY_COMMANDS", keys(TS_ONLY_COMMANDS)],
          ["TS_CONFIG_COMMANDS", keys(TS_CONFIG_COMMANDS)], ["TS_DISPATCHER_COMMANDS", keys(TS_DISPATCHER_COMMANDS)],
          ["CONFIG_ACTION_FAMILIES", [...CONFIG_ACTION_FAMILIES].sort(cmpCodePoints)],
        ]);
        break;
      }
      default:
        return { ok: false, error: "UNKNOWN_FN" };
    }
    return { ok: true, value: toTagged(value) };
  } catch (error) {
    return errorResult(error);
  } finally {
    for (const [name, before] of savedEnv) {
      if (before === undefined) delete process.env[name];
      else process.env[name] = before;
    }
  }
}

// --- ⑤e2b：合同与战前门禁里改状态的六个函数，照调用当时重放（与 python_probe.py 的 op_hub_contract_flow 一一对应） -----------

/** 最外层调用期间的提交作者与日期，同 python_probe.py 的 FLOW_GIT_ENV。 */
const FLOW_GIT_ENV: Record<string, string> = {
  GIT_AUTHOR_NAME: "themis-contract", GIT_AUTHOR_EMAIL: "contract@example.invalid", GIT_COMMITTER_NAME: "themis-contract",
  GIT_COMMITTER_EMAIL: "contract@example.invalid", GIT_AUTHOR_DATE: "2026-01-01T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-01T00:00:00+00:00",
};

/** 记录里的一次内层调用（python_probe.py 的 _flow_recorder 记下的）。 */
interface InnerEntry {
  readonly fn: string;
  readonly [key: string]: unknown;
}

class InjectionMismatch extends Error {}

/** 几棵树里的文件：{“树的序号/相对路径（正斜杠）”: sha256}。.git 不进，链接与联接不跟（lstat 把联接也当链接）。 */
function flowListing(roots: readonly string[]): Map<string, string> {
  const listing = new Map<string, string>();
  roots.forEach((root, index) => {
    if (!existsSync(root)) return; // ⑤f：mkdtemp 建的 worktree 调用之前还不在
    const walk = (dir: string, rel: string[]): void => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        const info = lstatSync(path);
        if (name === ".git" || info.isSymbolicLink()) continue;
        if (info.isDirectory()) walk(path, [...rel, name]);
        // 空文件不读：别的进程按字节区间锁着的锁文件读不出来（⑤f 的 add_worktree 等锁场景）
        else listing.set(`${index}/${[...rel, name].join("/")}`, createHash("sha256").update(info.size ? readFileSync(path) : Buffer.alloc(0)).digest("hex"));
      }
    };
    walk(root, []);
  });
  return listing;
}

const flowPath = (roots: readonly string[], key: string): string => {
  const [index, ...rel] = key.split("/");
  return join(roots[Number(index)] as string, ...rel);
};

/** 与 before 比：新建与改动的文件（原始字节，base64），删掉的文件。键按码点排序。 */
function flowChanges(roots: readonly string[], before: ReadonlyMap<string, string>): { write: Record<string, string>; delete: string[] } {
  const after = flowListing(roots);
  const write: Record<string, string> = {};
  for (const key of [...after.keys()].sort(cmpCodePoints)) {
    if (before.get(key) !== after.get(key)) write[key] = readFileSync(flowPath(roots, key)).toString("base64");
  }
  return { write, delete: [...before.keys()].filter((key) => !after.has(key)).sort(cmpCodePoints) };
}

/** 用命令读出的 git 状态：每棵树的 HEAD 与 status -z 的原文，第一棵树里的全部引用；不是仓库的记 null。 */
function flowGit(roots: readonly string[]): Record<string, unknown> {
  const run = (args: string[], cwd: string): string | null => {
    const done = spawnSync("git", args, { cwd, stdio: ["ignore", "pipe", "ignore"], maxBuffer: 1024 * 1024 * 1024, windowsHide: true });
    return done.status === 0 ? pyDecodeUtf8Replace(done.stdout) : null;
  };
  const trees = roots.map((root) => {
    const head = run(["rev-parse", "HEAD"], root);
    return { head: head === null ? null : pyStrip(head), status: run(["status", "--porcelain=v1", "--untracked-files=all", "-z"], root) };
  });
  return { trees, refs: run(["for-each-ref", "--format=%(refname) %(objectname)"], roots[0] as string) };
}

/** 传给 run_supervised 的环境变量与当场的 kernelPytestEnv() 整份比：相同记 true，不同只记对不上的名字（值不进记录）。 */
function envCheck(env: readonly (readonly [string, string])[]): true | string[] {
  const given = new Map(env);
  const expected = kernelPytestEnv();
  const names = [...new Set([...given.keys(), ...expected.keys()])].filter((name) => given.get(name) !== expected.get(name)).sort(cmpCodePoints);
  return names.length ? names : true;
}

/**
 * 内层调用要核对的参数：run_pd 比 argv 与 timeout（没给是 null）；⑤f 的 worktree_root 比仓库路径，mkdtemp 比 prefix 与 dir，
 * run_supervised 比命令、目录、环境、输出去向、时限、grace 与中断处理；另外三个比仓库路径与调用那一刻的整份 ts。
 */
function innerCall(name: string, args: readonly unknown[], toTagged: (value: PyValue) => unknown): Record<string, unknown> {
  if (name === "run_pd") return { fn: name, argv: (args[1] as string[]).map(String), timeout: args[2] ?? null };
  if (name === "worktree_root") return { fn: name, repo: args[0] };
  if (name === "mkdtemp") return { fn: name, prefix: args[0], dir: args[1] };
  if (name === "load_locked_batteries") return { fn: name, path: args[0] }; // ⑤g2
  if (name === "ask") { // ⑤g2：设置比 run_jev 改过的四样，账本比整个路径
    const settings = args[0] as Settings;
    return {
      fn: name, settings: { mode: settings.mode, configured_mode: settings.configured_mode, reason: settings.reason, points: settings.points }, ledger: args[1],
      battery: toTagged(args[2] as PyValue), state: toTagged(args[3] as PyValue), context: toTagged(args[4] as PyValue),
    };
  }
  if (name === "run_supervised") {
    const options = args[1] as SuperviseOptions;
    return {
      fn: name, argv: (args[0] as string[]).map(String), cwd: options.cwd, env: envCheck(options.env), stdout: [options.stdout.path, options.stdout.how],
      stderr: options.stderr === "stdout" ? "stdout" : "other", timeout: options.timeout, grace: options.grace ?? 15, handle_signals: options.handleSignals ?? true,
      on_spawn: options.onSpawn !== undefined,
    };
  }
  return { fn: name, repo: (args[0] as Hub).repo, ts: toTagged(args[1] as PyDict) };
}

/** 重放：照记录注入内层调用。参数逐次核对，对不上或多调抛 InjectionMismatch；照记录写文件、删文件、原地改 ts，再交回或抛出。 */
function injector(name: string, queue: InnerEntry[], roots: readonly string[], fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown) {
  return async (...args: unknown[]): Promise<never> => {
    const got = innerCall(name, args, toTagged);
    const expected = queue.shift();
    if (expected === undefined || Object.entries(got).some(([key, value]) => JSON.stringify(expected[key] ?? null) !== JSON.stringify(value))) {
      throw new InjectionMismatch(JSON.stringify({ got, expected: expected && Object.fromEntries(Object.keys(got).map((key) => [key, expected[key]])) }));
    }
    if (name === "mkdtemp") {
      const made = fromTagged(expected["value"] as never) as string;
      if (normcase(dirname(made)) !== normcase(String(args[1]))) throw new InjectionMismatch(`mkdtemp 记下的目录不在 dir 下：${made}`);
      mkdirSync(made);
    }
    const files = expected["files"] as { write: Record<string, string>; delete: string[] };
    for (const [key, data] of Object.entries(files.write)) {
      mkdirSync(dirname(flowPath(roots, key)), { recursive: true });
      writeFileSync(flowPath(roots, key), Buffer.from(data, "base64"));
    }
    for (const key of files.delete) rmSync(flowPath(roots, key));
    if ("ts_after" in expected) {
      const ts = args[1] as PyDict;
      ts.clear();
      for (const [key, value] of fromTagged(expected["ts_after"] as never) as PyDict) ts.set(key, value);
    }
    if ("raise" in expected) {
      const [kind, message] = expected["raise"] as [string, string];
      throw new PyCrash(kind, message);
    }
    const value = fromTagged(expected["value"] as never);
    if (name === "run_supervised") return superviseResult(value as PyDict) as never;
    return (name === "run_pd" ? [Number((value as PyValue[])[0]), (value as PyValue[])[1]] : value) as never;
  };
}

/** 记下的 run_supervised 结果（Python 的字典）换回 SuperviseResult：整数成 number。 */
function superviseResult(value: PyDict): Record<string, unknown> {
  return Object.fromEntries([...value].map(([key, item]) => [key, typeof item === "bigint" ? Number(item) : item]));
}

/** ⑤f：调用当时还不在的树（mkdtemp 建的 worktree），重放前先删掉；只删记下的 mkdtemp 的 dir 下的目录。 */
function removeFresh(fresh: readonly string[], inner: readonly InnerEntry[]): void {
  const dirs = new Set(inner.filter((entry) => entry.fn === "mkdtemp").map((entry) => normcase(String(entry["dir"]))));
  for (const root of fresh) {
    if (!dirs.has(normcase(dirname(root)))) throw new Error(`新建的树不在 mkdtemp 的 dir 下：${root}`);
    if (existsSync(root)) rmSync(root, { recursive: true, force: true });
  }
}

/**
 * ⑤g2 手写场景的真会话（同 python_probe.py 的 _jev_session）：传输层核对恰好是官方地址之后，一律改发本机的假端点，官方地址不交给真的
 * 传输层；环境只给假 key。
 */
function jevAsk(jev: { endpoint: string; key: string } | undefined): ExecDeps["ask"] {
  if (jev === undefined) return REAL_EXEC_DEPS.ask;
  if (!jev.endpoint.startsWith("http://127.0.0.1:")) throw new Error("假端点只能在本机");
  return (settings, ledger, battery, state, context) => askSession(settings, ledger, battery, state, context, {
    transport: (body, headers, timeout, url) => {
      if (url !== DEFAULT_BASE_URL + ENDPOINT_PATH) throw new Error("决策请求没有发往官方端点");
      return httpTransport(body, headers, timeout, jev.endpoint + ENDPOINT_PATH);
    },
    environ: { [settings.api_key_env]: jev.key },
  });
}

/** 第 ⑤e2b 片：python_probe.py 的 op_hub_contract_flow。 */
export async function hubContractFlow(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  for (const item of (request["restores"] as Restore[] | undefined) ?? []) restoreTree(item);
  if (typeof request["python"] === "string") setKernelPython(request["python"]);
  const fn = String(request["fn"]);
  const args = (request["args"] as never[]).map(fromTagged);
  const hub = (args[0] === null ? null : new Hub(textOf(args[0]))) as Hub; // ⑤f：hub 可以是 None（用不到它就交回的调用）
  const ts = args[1] as PyDict;
  const roots = request["roots"] as string[];
  removeFresh((request["fresh"] as string[] | undefined) ?? [], (request["inner"] as InnerEntry[] | undefined) ?? []);
  const before = flowListing(roots);
  const ledger = hub === null ? null : hub.ledger();
  const offset = ledger !== null && existsSync(ledger) ? statSync(ledger).size : 0;
  const queue = [...((request["inner"] as InnerEntry[] | undefined) ?? [])];
  const replaced = new Set((request["replaced"] as string[] | undefined) ?? []);
  const inject = (name: string) => injector(name, queue, roots, fromTagged, toTagged);
  const deps: ContractDeps = {
    runPd: replaced.has("run_pd") ? inject("run_pd") : REAL_DEPS.runPd,
    contractRequirements: replaced.has("contract_requirements") ? inject("contract_requirements") : REAL_DEPS.contractRequirements,
    budgetProblems: replaced.has("budget_problems") ? inject("budget_problems") : REAL_DEPS.budgetProblems,
    revalidateContract: replaced.has("revalidate_contract") ? inject("revalidate_contract") : REAL_DEPS.revalidateContract,
  };
  const gateDeps: GatePostDeps = {
    runPd: deps.runPd,
    worktreeRoot: replaced.has("worktree_root") ? inject("worktree_root") : REAL_GATE_POST_DEPS.worktreeRoot,
    runSupervised: replaced.has("run_supervised") ? inject("run_supervised") : REAL_GATE_POST_DEPS.runSupervised,
    mkdtemp: replaced.has("mkdtemp") ? inject("mkdtemp") : REAL_GATE_POST_DEPS.mkdtemp,
  };
  const execDeps: ExecDeps = { // ⑤g2：Python 那边 decisions.Session 换掉时，它的 ask 记成一次内层调用
    ...deps, worktreeRoot: gateDeps.worktreeRoot, mkdtemp: gateDeps.mkdtemp,
    reworkAddedFiles: replaced.has("rework_added_files") ? inject("rework_added_files") : REAL_EXEC_DEPS.reworkAddedFiles,
    loadLockedBatteries: replaced.has("load_locked_batteries") ? inject("load_locked_batteries") : REAL_EXEC_DEPS.loadLockedBatteries,
    ask: replaced.has("Session") ? inject("ask") : jevAsk(request["jev"] as { endpoint: string; key: string } | undefined),
    landWaitSeconds: typeof request["land_wait"] === "number" ? request["land_wait"] : EXEC_LAND_WAIT_SECONDS,
  };
  const givenEnv = Object.entries({ ...FLOW_GIT_ENV, ...((request["env"] as Record<string, string> | undefined) ?? {}) });
  const savedEnv = givenEnv.map(([name]) => [name, process.env[name]] as const);
  for (const [name, value] of givenEnv) process.env[name] = value;
  let result: Result;
  try {
    const value = await withPinnedClock(Number(request["pin"]), async (): Promise<PyValue> => {
      switch (fn) {
        case "accept_contract":
          return acceptContract(hub, ts, args[2] as PyValue, deps);
        case "revalidate_contract":
          return revalidateContract(hub, ts, deps);
        case "bump_contract_version":
          return bumpContractVersion(hub, ts);
        case "set_contract_base":
          return setContractBase(hub, ts, textOf(args[2]), deps);
        case "accept_gate_pre":
          return acceptGatePre(hub, ts, textOf(args[2]), deps);
        case "sync_executor_line":
          return syncExecutorLine(hub, ts);
        case "apply_candidate": // ⑤f
          return applyCandidate(hub, ts, gateDeps);
        case "ensure_worktree":
          return ensureWorktree(hub, ts, textOf(args[2]), args[3] as PyValue, gateDeps);
        case "seed_whitebox":
          return seedWhitebox(hub, ts, textOf(args[2]));
        case "accept_gate_post":
          return acceptGatePost(hub, ts, textOf(args[2]), args[3] as PyValue, gateDeps);
        case "run_mutations":
          return runMutations(hub, ts, textOf(args[2]), textOf(args[3]), args[4] as PyValue, gateDeps);
        case "run_exec": // ⑤g2
          return runExec(hub, ts, execDeps);
        case "finish_exec":
          return finishExec(hub, ts, textOf(args[2]), args[3] as bigint | null, execDeps);
        case "write_review":
          return writeReview(hub, ts, textOf(args[2]), textOf(args[3]));
        case "run_jev":
          return runJev(hub, ts, textOf(args[2]), execDeps);
        case "ensure_rework_scope":
          return ensureReworkScope(hub, ts, execDeps);
        case "dispatch_attempt": // 以下只进手写场景
          return dispatchAttempt(hub, ts, execDeps);
        case "start_rework":
          return startRework(hub, ts, textOf(args[2]), args[3] as PyValue, execDeps);
        case "rebase_candidate":
          return rebaseCandidate(hub, ts, textOf(args[2]), textOf(args[3]), execDeps);
        case "start_retry":
          return startRetry(hub, ts, textOf(args[2]), execDeps);
        case "final_audit_turn":
          return finalAuditTurn(hub, ts, textOf(args[2]));
        case "rework_added_files":
          return reworkAddedFiles(hub, ts);
        default:
          throw new Error(`UNKNOWN_FN ${fn}`);
      }
    });
    result = queue.length ? { ok: false, error: "INJECTION_LEFTOVER", left: queue.map((entry) => entry.fn) } : { ok: true, value: toTagged(value) };
  } catch (error) {
    result = error instanceof InjectionMismatch ? { ok: false, error: "INJECTION_MISMATCH", detail: error.message } : errorResult(error);
  } finally {
    for (const [name, before] of savedEnv) {
      if (before === undefined) delete process.env[name];
      else process.env[name] = before;
    }
  }
  const tail = ledger !== null && existsSync(ledger) ? readFileSync(ledger).subarray(offset) : Buffer.alloc(0);
  return { ok: true, value: { result, ts: toTagged(ts), files: flowChanges(roots, before), ledger: tail.toString("base64"), git: flowGit(roots) } };
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
  cpSync(source, target, { recursive: true, verbatimSymlinks: true, preserveTimestamps: true });
  for (const [rel, pointed, kind] of links) symlinkSync(pointed, join(target, ...rel.split("/")), kind as "dir" | "file" | "junction");
  copyTreeTimes(source, target); // ⑤g：文件与目录的修改时刻照快照，同 python_probe.py 的 _copy_dir_times
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
  // home 也在调用期间设、调用完还原：同一批里下一个没带 home 的请求不沿用
  const home = typeof request["home"] === "string" ? { USERPROFILE: request["home"], HOME: request["home"] } : {};
  const givenEnv = { ...((request["env"] ?? {}) as Record<string, string>), ...home };
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

/** ⑤f 起报错文字也比（str(exc)）：report_step_error 把它写进账本与给站主的信。Node 自己抛的错没有照 Python 的文字，露出原文，契约对不上时就知道漏了 pyOSErrorOf。 */
function errorResult(error: unknown): Result {
  // ⑤g2：子类（LandBusy）记自己的类名，同 python_probe.py 的 _recorded_error
  if (error instanceof HubError) return { ok: false, error: error.constructor.name, message: error.message, code: error.code };
  if (error instanceof DispatchError) return { ok: false, error: "DispatchError", message: error.message, code: error.code };
  if ((error as Error | null)?.name === "UnicodeDecodeError") return { ok: false, error: "UnicodeDecodeError", message: (error as Error).message }; // base 的 fsutil 与 pyio 各有一个
  if (error instanceof PyCrash) return { ok: false, error: error.kind, message: error.message };
  if (error instanceof PyJsonError) return { ok: false, error: error.kind, message: error.message };
  if (error instanceof PyOSError) return { ok: false, error: OS_ERRORS[error.errno] ?? "OSError", message: error.message }; // Python 按 errno 选的子类
  if (error instanceof PyWinError) return { ok: false, error: error.name, message: error.message }; // Windows 错误码照 CPython 归的子类
  const code = (error as NodeJS.ErrnoException).code;
  const raw = `JS:${(error as Error).message}`;
  if (code === "ENOENT") return { ok: false, error: "FileNotFoundError", message: raw };
  if (code === "EEXIST") return { ok: false, error: "FileExistsError", message: raw };
  if (code === "EPERM" || code === "EACCES" || code === "EBUSY") return { ok: false, error: "PermissionError", message: raw };
  return { ok: false, error: `JS:${(error as Error).name}:${(error as Error).message}` };
}
