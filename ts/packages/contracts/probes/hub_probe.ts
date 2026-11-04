// hub.call（第 ⑤a 片）：按函数名调 @themis/hub 的纯函数，参数与结果照 python_probe.py 的 op_hub_call。
// 结果里的整数照 Python 写成 int（bigint）；HubError 交回文字与退出码，Python 语义的异常交回类型与文字（⑤f 起文字也比）。
import { PyCrash, pyGet, pyItem, pyReprValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, PyJsonError, type PyValue, loads } from "@themis/base/pyjson";
import { PyOverflowError, PyReError, PyValueError } from "@themis/base/pyregex";
import { accessSync, appendFileSync, chmodSync, closeSync, constants as fsConstants, cpSync, openSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { devNull, tmpdir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { readText, sleepSync } from "@themis/base/fsutil";
import { winProcessApi, withFileLock } from "@themis/base/native";
import { PyOSError } from "@themis/base/pyio";
import { PyWinError } from "@themis/base/pyos";
import { jsonlLines } from "@themis/base/jsonl";
import { cmpCodePoints, pySplitlines, pyStrip } from "@themis/base/pyre";
import { advancePinnedClock, nowMicros, withPinnedClock } from "@themis/base/clock";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { spawn, spawnSync } from "node:child_process";
import { type ContractDeps, REAL_DEPS, acceptContract, acceptGatePre, bumpContractVersion, revalidateContract, setContractBase, syncExecutorLine } from "@themis/hub/accept";
import {
  type GatePostDeps, REAL_GATE_POST_DEPS, acceptGatePost, applyCandidate, attemptBase, candidateDefects, defectMatchProblems, defectMatches, ensureWorktree,
  expectedMissedEverywhere, gateSpec, mutantTimeout, mutationProblems, runMutations, seedWhitebox, unchangedMismatches, unmutatedProblems,
} from "@themis/hub/gatepost";
import {
  EXEC_LAND_WAIT_SECONDS, type ExecDeps, LandBusy, REAL_EXEC_DEPS, askSession, dispatchAttempt, ensureReworkScope, finalAuditTurn, finishExec, rebaseCandidate,
  reworkAddedFiles, runExec, runJev, startRework, startRetry, writeReview,
} from "@themis/hub/runexec";
import {
  type LandDeps, REAL_LAND_DEPS, commitRecords, finalize, landOracle, landReworkChain, landedMeanwhile, landingBlockers, landingChain, landingRecords, onBranch,
  recordPass, removeWorkspaces, retireAttempts, tidyFinished, undoLanding,
} from "@themis/hub/land";
import {
  LAND_WAIT_SECONDS, REAL_SWEEP_DEPS, SWEEP_SECONDS, SWEEP_WAIT_SECONDS, type SweepDeps, gateBaselines, markOwnerMoved, ownerSweep, readOwnerSweep, regressionSweep,
  rehearsalLetter, rehearseLanding, sweepGates, tsInstallIfStale,
} from "@themis/hub/sweep";
import { Engine, type EngineDeps, type StateLike, land, releaseDependents, resumedSession } from "@themis/hub/engine";
import {
  type CommandArgs, type CommandOut, cmdExecRecheck, cmdInit, cmdMetrics, cmdSend, cmdStatus, cmdTake, cmdTaskAfter, cmdTaskBudget, cmdTaskCleanup,
  cmdTaskClose, cmdTaskNew, cmdTaskRebase, cmdTaskUnstick, configuredParallel, execMetrics, recordedSum, turnMetrics, uncommittedReferences,
} from "@themis/hub/commands";
import {
  type ChildLike, type ChildLog, REAL_RUNNER_DEPS, type RunnerDeps, cmdExclusive, cmdOwnerSweep, cmdRun, codeFingerprint, kernelChanges, kernelDirty, kernelFiles, kernelSelection,
  ownerSweepTick, pauseRequested, refuseDirtyKernel, setKitHub, spawnRunner, spawnTaskRunner, superviseTick,
} from "@themis/hub/runner";
import { type HubContext, useLauncherContext } from "@themis/hub/cli";
import {
  finishedTurn, interruptedLetters, lettersHeld, reportStrandedExec, requeueInterrupted, requeueLetters, requeueTask, runnerLock, runnerMayIdleExit,
  strandedStages, supervisorBusy, tasksWithWork,
} from "@themis/hub/requeue";
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
import { DispatchError, type Repo } from "@themis/dispatcher/repo";
import { DELIVERY_SHA256, deliveredOutput, deliveryProblem, interfaceProblem, roleSchema, workerEnv, workerFileProblem } from "@themis/hub/delivery";
import { HubError } from "@themis/hub/errors";
import { removeInputs, stageInputs } from "@themis/hub/inputs";
import { INPUTS_INDEX } from "@themis/hub/constants";
import { type Launcher, REAL_SOURCES, TurnRunner, type TurnSources } from "@themis/hub/turn";
import { globPaths } from "@themis/dispatcher/instruction";
import { KERNEL_ROOT, SCRIPTS_DIR, TEMPLATE_DIR, workspaceStatus } from "@themis/hub/kernel";
import { kernelEnv, kernelPytest, kernelPytestEnv, kernelPython, runPd, setKernelPython } from "@themis/hub/runpd";
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
      case "resumed_session": // ⑤i1：交回会话号或 None
        value = resumedSession(new Hub(textOf(a)), textOf(b), args[2] as PyValue, textOf(args[3]));
        break;
      case "Engine.output_problem": // ⑤i1：参数前两个是仓库与 only_task
        value = new Engine(new Hub(textOf(a)), null, optionalText(b)).outputProblem(textOf(args[2]), textOf(args[3]), args[4] as PyDict);
        break;
      case "Engine.next_job": // ⑤i2：（agent, 信的路径）
        value = new Engine(new Hub(textOf(a)), null, optionalText(b)).nextJob();
        break;
      case "finished_turn": // ⑤i2：只看传进来的事件
        value = finishedTurn(args[0] as PyValue[], textOf(b), textOf(args[2]), textOf(args[3]));
        break;
      case "interrupted_letters":
        value = interruptedLetters(new Hub(textOf(a)), b as PyValue[], textOf(args[2]), textOf(args[3]), textOf(args[4]), (args[5] ?? []) as PyValue[]);
        break;
      case "stranded_stages":
        value = strandedStages(new Hub(textOf(a)), b as PyDict);
        break;
      case "letters_held":
        value = lettersHeld(new Hub(textOf(a)));
        break;
      case "supervisor_busy":
        value = supervisorBusy(new Hub(textOf(a)), b as PyValue[], args[2] as PyValue);
        break;
      case "runner_may_idle_exit":
        value = runnerMayIdleExit(new Hub(textOf(a)), optionalText(b));
        break;
      case "tasks_with_work":
        value = tasksWithWork(new Hub(textOf(a)));
        break;
      case "runner_lock": // 纯算路径
        value = runnerLock(new Hub(textOf(a)), optionalText(b));
        break;
      case "turn_metrics": // ⑤j1：只读，参数是仓库
        value = turnMetrics(new Hub(textOf(a)));
        break;
      case "exec_metrics":
        value = execMetrics(new Hub(textOf(a)));
        break;
      case "uncommitted_references":
        value = uncommittedReferences(textOf(a), textOf(b));
        break;
      case "recorded_sum":
        value = recordedSum(a as PyDict[], textOf(b));
        break;
      case "configured_parallel": // 第二个参数记成 Namespace 的各键
        value = BigInt(configuredParallel(new Hub(textOf(a)), commandArgs(b)));
        break;
      case "kernel_files": // ⑤j2：内核文件清单（路径交回字符串）。TS 另认一个参数：选择文件的内容（E3 的场景用；Python 的不带参数）
        value = kernelFiles(args.length > 0 ? (a as PyDict) : null);
        break;
      case "kernel_selection": // ⑤j2，只有 TS：读给定的选择文件，坏了交回 {}
        value = kernelSelection(textOf(a));
        break;
      case "code_fingerprint": // ⑤j2：给了 files 照真的算；没给就是内核文件
        value = codeFingerprint(kernelPaths(args));
        break;
      case "kernel_dirty":
        value = kernelDirty(kernelPaths(args));
        break;
      case "kernel_changes":
        value = kernelChanges(kernelPaths(args));
        break;
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
      case "sweep_gates": { // ⑤h2：真跑门禁基准；退出码照 Python 记成 int
        const [code, out, tests] = await sweepGates(textOf(a));
        value = [BigInt(code), out, tests];
        break;
      }
      case "gate_baselines":
        value = gateBaselines(textOf(a));
        break;
      case "read_owner_sweep": // ⑤h2
        value = readOwnerSweep(new Hub(textOf(a)));
        break;
      case "landing_records": // ⑤h1
        value = landingRecords(dictOf(a));
        break;
      case "landed_meanwhile":
        value = landedMeanwhile(new Hub(textOf(a)), dictOf(b), textOf(args[2]));
        break;
      case "landing_chain": // 第三个参数是 Path 或 None
        value = landingChain(new Hub(textOf(a)), dictOf(b), args[2] === null ? null : textOf(args[2]));
        break;
      case "on_branch":
        value = onBranch(new Hub(textOf(a)), b, args[2] === null ? null : textOf(args[2]));
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
function envCheck(env: readonly (readonly [string, string])[], expected: ReadonlyMap<string, string> = kernelPytestEnv()): true | string[] {
  const given = new Map(env);
  const names = [...new Set([...given.keys(), ...expected.keys()])].filter((name) => given.get(name) !== expected.get(name)).sort(cmpCodePoints);
  return names.length ? names : true;
}

/**
 * 内层调用要核对的参数：run_pd 比 argv 与 timeout（没给是 null）；⑤f 的 worktree_root 比仓库路径，mkdtemp 比 prefix 与 dir，
 * run_supervised 比命令、目录、环境、输出去向、时限、grace 与中断处理；另外三个比仓库路径与调用那一刻的整份 ts。
 */
function innerCall(name: string, args: readonly unknown[], toTagged: (value: PyValue) => unknown): Record<string, unknown> {
  if (name === "runner") { // ⑤i1：Engine 的回合；输入目录记调用当时的文件
    const [agent, sessionKey, workspace, role, prompt, retryOf, fresh, inputs, sessionId] = args;
    return {
      fn: name, agent, session_key: sessionKey, workspace, role_prompt: role, prompt, retry_of: retryOf ?? null, fresh: Boolean(fresh), inputs: inputs ?? null,
      session_id: sessionId ?? null, inputs_files: inputsFiles(inputs),
    };
  }
  if (name === "role_prompt") return { fn: name, agent: args[0] };
  if (name === "Engine.verify_delivery" || name === "Engine.auto_jev") return { fn: name, args: toTagged(args.map((item) => stateData(item)) as PyValue) };
  if (name === "engine.handle_pass") return { fn: name, state: toTagged(stateData(args[0])), meta: toTagged(args[1] as PyValue) }; // 4001 的假 Engine
  if (name === "engine.after_land") return { fn: name, main: args[0] };
  if (name === "release_held") return { fn: name, repo: (args[0] as Hub).repo }; // ⑤i2：只有 hub 一个参数
  // ⑤j2：进程模型换掉的内层函数（同 python_probe.py）；最后的 deps 不算
  if (name === "spawn_task_runner") return { fn: name, repo: (args[0] as Hub).repo, task: args[1], args: toTagged(namespaceShown(args[2] as CommandArgs | null)) };
  if (name === "spawn_runner") return { fn: name, repo: (args[0] as Hub).repo, argv: argvShown(args[1] as string[]) };
  if (name === "kernel_dirty" || name === "code_fingerprint" || name === "kernel_changes") return { fn: name, paths: args[0] ?? null }; // 没给 files 记 null
  if (name === "kernel_settled") return { fn: name, wait: args[0], poll: args[1] };
  if (name === "tasks_with_work") return { fn: name, repo: (args[0] as Hub).repo };
  if (name === "requeue_interrupted") return { fn: name, repo: (args[0] as Hub).repo, skip: [...((args[1] as string[] | undefined) ?? [])].sort(cmpCodePoints) };
  if (name === "owner_sweep_tick") return { fn: name, repo: (args[0] as Hub).repo, holder: toTagged(procShown(args[1])) };
  if (name === "Popen") { // 比命令行、当前目录与输出写进哪个日志（文件名）
    const log = args[2] as ChildLog | null;
    return { fn: name, argv: argvShown(args[0] as string[]), cwd: args[1] ?? null, log: log === null ? null : basename(log.path) };
  }
  if (name === "sleep") return { fn: name, seconds: args[0] };
  if (name === "Engine.step") return { fn: name, repo: (args[0] as Engine).hub.repo, only_task: (args[0] as Engine).onlyTask }; // 第一个参数是 Engine 本身
  if (Object.hasOwn(REST_ARITY, name)) { // ⑤i1：hub、ts 之外的参数也比（最后的 deps 不算）
    return { fn: name, repo: (args[0] as Hub).repo, ts: toTagged(args[1] as PyDict), rest: toTagged(args.slice(2, 2 + (REST_ARITY[name] as number)) as PyValue) };
  }
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
  if (name === "_running_attempts") return { fn: name, repo: (args[0] as Repo).root }; // ⑤h1
  if (name === "pid_alive") return { fn: name, pid: args[0] };
  if (name === "sweep_gates") return { fn: name, path: args[0] }; // ⑤h2
  if (name === "find_bun") return { fn: name, env: envCheck([...(args[0] as Map<string, string>)], kernelEnv()) };
  if (name === "read_kernel_impl") return { fn: name, args: 0 };
  if (name === "ts_install_if_stale") return { fn: name, repo: (args[0] as Hub).repo };
  if (name === "ts_runner") { // ts_install_if_stale 的 runner：输出写在 themis-ts-install- 临时目录下的 output，两路是同一个文件
    const options = args[1] as SuperviseOptions;
    const temporary = basename(options.stdout.path) === "output" && basename(dirname(options.stdout.path)).startsWith("themis-ts-install-");
    return {
      fn: name, argv: (args[0] as string[]).map(String), cwd: options.cwd, env: envCheck(options.env, kernelEnv()),
      stdout: temporary ? "<temporary>" : options.stdout.path, stderr: options.stderr === "stdout" ? "same" : "other", timeout: options.timeout,
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

/**
 * 重放：照记录注入内层调用。参数逐次核对，对不上或多调抛 InjectionMismatch；照记录写文件、删文件、原地改 ts，再交回或抛出。
 * ⑤h1：被调用的一方是同步的（_running_attempts、pid_alive）就直接用这个；异步的经 injector 包一层。
 */
function injectorSync(name: string, queue: InnerEntry[], roots: readonly string[], fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown) {
  return (...args: unknown[]): never => {
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
    applyFiles(expected, roots);
    if ("output" in expected) appendFileSync((args[1] as SuperviseOptions).stdout.path, Buffer.from(expected["output"] as string, "base64")); // ⑤h2：ts_runner
    if ("ts_after" in expected) {
      const ts = (name.startsWith("Engine.") ? stateData(args[0]) : args[1]) as PyDict; // ⑤i1：Engine 的两个方法没有 self，ts 或 state 在第一个
      ts.clear();
      for (const [key, value] of fromTagged(expected["ts_after"] as never) as PyDict) ts.set(key, value);
    }
    if ("raise" in expected) {
      const [kind, message, code] = expected["raise"] as [string, string, number?];
      if (code !== undefined) throw kind === "LandBusy" ? new LandBusy(message, code) : new HubError(message, code); // ⑤i1：HubError 一族带退出码
      if (kind === "DispatchError") throw new DispatchError(message); // ⑤h1：同 python_probe.py，被调用的一方认得出
      throw new PyCrash(kind, message);
    }
    const value = fromTagged(expected["value"] as never);
    if (name === "spawn_task_runner" || name === "Popen") return procsOf(value, queue, roots, fromTagged) as never; // ⑤j2：记下的进程换成假进程
    if (name === "spawn_runner") return Number(value) as never; // ⑤j2：退出码是 number
    if (name === "run_supervised" || name === "ts_runner") return superviseResult(value as PyDict) as never;
    if (name === "sweep_gates") return [Number((value as PyValue[])[0]), (value as PyValue[])[1], (value as PyValue[])[2]] as never; // ⑤h2：退出码是 number
    return (name === "run_pd" ? [Number((value as PyValue[])[0]), (value as PyValue[])[1]] : value) as never;
  };
}

/** 照记录写文件、删文件（内层调用与 ⑤j2 假进程的 poll 共用，同 python_probe.py 的 _flow_apply_files）。 */
function applyFiles(expected: InnerEntry, roots: readonly string[]): void {
  const files = expected["files"] as { write: Record<string, string>; delete: string[] };
  for (const [key, data] of Object.entries(files.write)) {
    mkdirSync(dirname(flowPath(roots, key)), { recursive: true });
    writeFileSync(flowPath(roots, key), Buffer.from(data, "base64"));
  }
  for (const key of files.delete) rmSync(flowPath(roots, key));
}

/**
 * ⑤j2：重放时的假进程（同 python_probe.py 的 _ProcReplay）。pid 照记录；poll 逐次核对记下的 proc.poll（编号相同），写回文件改动，交回记下的值；
 * returncode 是最后一次 poll 的值。runner.ts 只经 ChildLike 用 pid、poll、returncode 三样：以后要调别的，先在两边的假进程一起加。
 */
class ProcReplay implements ChildLike {
  returncode: number | null = null;
  readonly ident: number;
  readonly pid: number | null;
  private readonly queue: InnerEntry[];
  private readonly roots: readonly string[];
  private readonly fromTagged: (tagged: never) => PyValue;

  constructor(ident: number, pid: number | null, queue: InnerEntry[], roots: readonly string[], fromTagged: (tagged: never) => PyValue) {
    this.ident = ident;
    this.pid = pid;
    this.queue = queue;
    this.roots = roots;
    this.fromTagged = fromTagged;
  }

  poll(): number | null {
    const expected = this.queue.shift();
    if (expected === undefined || expected.fn !== "proc.poll" || expected["proc"] !== this.ident) {
      const shown = expected === undefined ? null : { fn: expected.fn, proc: expected["proc"] ?? null };
      throw new InjectionMismatch(JSON.stringify({ got: { fn: "proc.poll", proc: this.ident }, expected: shown }));
    }
    applyFiles(expected, this.roots);
    const value = this.fromTagged(expected["value"] as never);
    this.returncode = value === null ? null : Number(value);
    return this.returncode;
  }
}

/** ⑤j2：这一次重放的假进程，编号照样本（同 python_probe.py 的 _PROC["replay"]）。 */
const PROCS = new Map<number, ProcReplay>();

/** 参数与注入的交回值里记成 {"__proc__", "pid"} 的换回假进程，同一个编号是同一个对象（同 python_probe.py 的 _procs_of）。 */
function procsOf(value: unknown, queue: InnerEntry[], roots: readonly string[], fromTagged: (tagged: never) => PyValue): unknown {
  if (value instanceof Map && value.size === 2 && value.has("__proc__") && value.has("pid")) {
    const ident = Number(value.get("__proc__"));
    const pid = value.get("pid");
    if (!PROCS.has(ident)) PROCS.set(ident, new ProcReplay(ident, pid === null ? null : Number(pid), queue, roots, fromTagged));
    return PROCS.get(ident);
  }
  if (value instanceof Map) return new Map([...value].map(([key, item]) => [key, procsOf(item, queue, roots, fromTagged)]));
  if (Array.isArray(value)) return value.map((item) => procsOf(item, queue, roots, fromTagged));
  return value;
}

/** 假进程记成编号与 pid（同 python_probe.py 的 _proc_shown）；字典与列表逐项，别的原样。 */
function procShown(value: unknown): PyValue {
  if (value instanceof ProcReplay) return new Map<string, PyValue>([["__proc__", BigInt(value.ident)], ["pid", value.pid === null ? null : BigInt(value.pid)]]);
  if (value instanceof Map) return new Map([...value].map(([key, item]) => [key, procShown(item)]));
  if (Array.isArray(value)) return value.map(procShown);
  return value as PyValue;
}

let rawArgv = false;

/** 起子进程的命令行：Python 与 kit_hub.py 的路径换成占位（同 python_probe.py 的 _argv_shown；TS 起的是同一个启动器，路径各自取）。 */
function argvShown(argv: readonly string[]): string[] {
  if (rawArgv) return [...argv];
  const real = (path: string): string => {
    try {
      return normcase(realpathSync.native(path));
    } catch {
      return normcase(resolve(path));
    }
  };
  const hubFile = real(join(SCRIPTS_DIR, "kit_hub.py"));
  return argv.map((text) => (text === kernelPython() ? "<python>" : text.endsWith(".py") && real(text) === hubFile ? "<kit_hub>" : text));
}

/** ⑤j2：Namespace 记成各键（去掉 func，同 python_probe.py 的 _plain）；None 照旧。 */
function namespaceShown(args: CommandArgs | null): PyValue {
  return args === null ? null : new Map(Object.entries(args).filter(([key]) => key !== "func") as [string, PyValue][]);
}

/** 异步的被调用方（run_pd 等）：同 injectorSync，交回 Promise。 */
function injector(name: string, queue: InnerEntry[], roots: readonly string[], fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown) {
  const sync = injectorSync(name, queue, roots, fromTagged, toTagged);
  return async (...args: unknown[]): Promise<never> => sync(...args);
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

// --- ⑤i1：Engine 的方法、land、release_dependents（python_probe.py 的 _flow_call 与 FLOW_INNER_I 一带） -------------------------------------

/** 用例换掉之后照记录注入、hub 与 ts 之外还有参数的那几个：参数个数（最后的 deps 不算），同 python_probe.py 记的 rest。 */
const REST_ARITY: Readonly<Record<string, number>> = {
  ensure_worktree: 2, apply_candidate: 0, seed_whitebox: 1, run_exec: 0, run_jev: 1, finalize: 0, tidy_finished: 1, regression_sweep: 0,
};

/** Engine 的方法、land、release_dependents 的参数名（不含 self、hub、engine），照 kit_hub.py 的签名次序；args_after 照这个次序列出。 */
const ENGINE_PARAMS: Readonly<Record<string, readonly string[]>> = {
  "Engine.escalate": ["ts", "text"], "Engine.worker_job": ["state", "agent", "paths"], "Engine.auto_jev": ["state", "ts", "suffix"],
  "Engine.stage_workspace": ["ts", "agent", "suffix"], "Engine.verify_delivery": ["ts", "agent", "suffix", "output", "fields"],
  "Engine.after_delivery": ["ts", "suffix", "fields", "output"], "Engine.finish_kernel_stage": ["state", "ts", "agent", "suffix", "fields", "ok"],
  "Engine.recheck_exec": ["main"], "Engine.worker_turns": ["agent", "task_id", "ts", "texts", "workspace", "kinds", "inputs", "resume"],
  "Engine.redeliver": ["state", "ts", "agent", "task_id", "suffix", "texts", "workspace", "problems", "turn"], "Engine.handle_pass": ["state", "meta"],
  "Engine.after_land": ["main"], "Engine.after_land_run": ["main"], land: ["letter", "meta"], release_dependents: ["state", "done"],
  // ⑤i2（report_step_error 的 exc 记不下来，它只在 step 里被调到）
  "Engine.step": [], "Engine.fail_stage": ["agent", "paths", "note"], "Engine.coordinator_turn": ["state", "paths"],
  "Engine.route": ["state", "ts", "paths", "texts"], "Engine.deliver_coordinator_letter": ["state", "item", "sender"], "Engine.write_brief": ["task_id", "brief"],
  requeue_interrupted: ["skip"], requeue_task: ["task"], requeue_letters: ["ts", "events", "agent", "key", "names", "turn", "label"],
  report_stranded_exec: ["ts", "stage", "names"],
};

/**
 * ⑤j2：跑到静止换成真的 cmd_run（⑤j 设计稿第 5 节，同 python_probe.py 的 _sleep_clock，request.clock 是 "sleep"）：sleep 把钉住的时钟往后挪、
 * 不真睡，第 400 次抛错；monotonic 跟着钉住的时钟走；指纹交回常数、kernel_changes 交回 []。TS 只换 cmdRun 的 deps，Python 换的是整个 time
 * 模块（DirLock 的等待也算在内）；跑到静止时锁都没人抢，次数一样，有分歧三边对照会抓到。
 */
function sleepClockDeps(deps: RunnerDeps): RunnerDeps {
  let calls = 0;
  return {
    ...deps,
    codeFingerprint: () => "quiesce",
    kernelChanges: () => [],
    sleep: async (seconds) => {
      calls += 1;
      if (calls >= 400) throw new PyCrash("RuntimeError", "跑到静止：sleep 调到第 400 次");
      advancePinnedClock(Math.round(seconds * 1_000_000));
    },
    monotonic: () => nowMicros() / 1_000_000,
  };
}

/**
 * ⑤j2：cmd_run 自己建 Engine（runner 是 TurnRunner），剧本给的回合与 Engine 的两个方法换在原型上，调用完还原；同 Python 换在类上
 * （TurnRunner.run、Engine.verify_delivery、Engine.auto_jev）。
 */
async function withEnginePatches<T>(pick: Pick, runner: boolean, body: () => Promise<T>): Promise<T> {
  const turn = TurnRunner.prototype as unknown as Record<string, unknown>;
  const engine = Engine.prototype as unknown as Record<string, unknown>;
  const saved: [Record<string, unknown>, string, unknown][] = [];
  const swap = (owner: Record<string, unknown>, name: string, fn: (...args: unknown[]) => Promise<never>): void => {
    saved.push([owner, name, owner[name]]);
    owner[name] = function patched(...args: unknown[]): Promise<never> {
      return fn(...args);
    };
  };
  if (runner) swap(turn, "run", pick.inject("runner"));
  if (pick.has("Engine.verify_delivery")) swap(engine, "verifyDelivery", pick.inject("Engine.verify_delivery"));
  if (pick.has("Engine.auto_jev")) swap(engine, "autoJev", pick.inject("Engine.auto_jev"));
  try {
    return await body();
  } finally {
    for (const [owner, name, value] of saved.reverse()) owner[name] = value;
  }
}

/** 模块函数（没有 Engine，参数第一个是仓库）：同 python_probe.py 的 FLOW_I_FUNCTIONS 去掉 land。 */
const FLOW_I_MODULE = ["release_dependents", "requeue_interrupted", "requeue_task", "requeue_letters", "report_stranded_exec"];
/** ⑤j1：站主命令（同 python_probe.py 的 FLOW_J1）：参数是仓库与 Namespace 的各键，另比 stdout、stderr。 */
const FLOW_J1 = [
  "cmd_init", "cmd_task_new", "cmd_task_close", "cmd_task_rebase", "cmd_task_after", "cmd_task_unstick", "cmd_task_budget", "cmd_task_cleanup",
  "cmd_send", "cmd_exec_recheck", "cmd_take", "cmd_status", "cmd_metrics",
];

/** ⑤j2：进程模型（同 python_probe.py 的 FLOW_J2_COMMANDS、FLOW_J2）：前三个同站主命令记；其余第一个参数是 hub。都另比 stdout、stderr。 */
const FLOW_J2_COMMANDS = ["cmd_run", "cmd_owner_sweep", "cmd_exclusive"];
const FLOW_J2 = [...FLOW_J2_COMMANDS, "supervise_tick", "owner_sweep_tick", "spawn_runner", "spawn_task_runner", "refuse_dirty_kernel", "pause_requested"];

const LF = String.fromCharCode(10);

/** ⑤j2：kernel_files 一族的 files 参数：没给或 None 是 null。 */
function kernelPaths(args: readonly PyValue[]): string[] | null {
  const files = args[0];
  return files === undefined || files === null ? null : (files as PyValue[]).map(textOf);
}

/** ⑤j2：进程模型的 deps：Engine 的 deps 加上用例换掉的内层函数（照记录注入）。探针的 stdout 是交回结果的通道，exclusive 跑的命令的输出不接过来。 */
function runnerDepsOf(engineDeps: EngineDeps, pick: Pick): RunnerDeps {
  const real = REAL_RUNNER_DEPS;
  const sync = <T>(name: string, fallback: T): T => (pick.has(name) ? pick.injectSync(name) as T : fallback);
  const async = <T>(name: string, fallback: T): T => (pick.has(name) ? pick.inject(name) as T : fallback);
  return {
    ...engineDeps,
    spawnTaskRunner: async("spawn_task_runner", real.spawnTaskRunner),
    spawnRunner: async("spawn_runner", real.spawnRunner),
    kernelDirty: sync("kernel_dirty", real.kernelDirty),
    kernelSettled: async("kernel_settled", real.kernelSettled),
    codeFingerprint: sync("code_fingerprint", real.codeFingerprint),
    kernelChanges: sync("kernel_changes", real.kernelChanges),
    tasksWithWork: sync("tasks_with_work", real.tasksWithWork),
    requeueInterrupted: async("requeue_interrupted", real.requeueInterrupted),
    ownerSweepTick: async("owner_sweep_tick", real.ownerSweepTick),
    popen: async("Popen", contractPopen),
    sleep: async("sleep", real.sleep),
    monotonic: real.monotonic,
    engineStep: async("Engine.step", real.engineStep),
    commandStdio: "ignore",
    selfPid: process.pid,
  };
}

/**
 * ⑤j2：契约里真起子进程（Popen 没换掉时）。没给日志时接空设备，同 python_probe.py 重放时把 fd 1、2 接到空设备：继承了探针的 stdout，
 * 调用方要等它退出才读得完结果。只给契约用的后备：Node 调不了 Win32（生产上 hub 在 Windows 只跑在 Bun 下），Windows 的 Node 改用
 * child_process 加 detached（不进 libuv 的 Job，代价是另起进程组、没有控制台），别处照 runner.ts 的真 popen。
 */
async function contractPopen(argv: readonly string[], cwd: string | null, log: ChildLog | null): Promise<ChildLike> {
  const fd = log === null ? openSync(devNull, "a") : null;
  const given = log ?? { fd: fd as number, path: devNull };
  try {
    if (process.platform !== "win32" || typeof (globalThis as { Bun?: unknown }).Bun !== "undefined") return await REAL_RUNNER_DEPS.popen(argv, cwd, given);
    const child = spawn(argv[0] as string, argv.slice(1), { cwd: cwd ?? undefined, stdio: ["ignore", given.fd, given.fd], detached: true, windowsHide: true });
    child.on("error", () => undefined);
    child.unref();
    return {
      pid: child.pid ?? null,
      poll: () => child.exitCode,
      get returncode() {
        return child.exitCode;
      },
    };
  } finally {
    if (fd !== null) closeSync(fd);
  }
}

/**
 * ⑤j2：第一个参数是 hub 的进程模型函数（同 python_probe.py 的 _flow_call 的 FLOW_J2 一支）：参数名是 args 的照建回 Namespace（不进 args_after），
 * 记下的进程已换成假进程；args_after 照签名次序列出字典与列表参数，假进程记成编号与 pid。
 */
function runnerFlow(fn: string, hub: Hub, given: readonly unknown[], out: CommandOut, deps: RunnerDeps): EngineFlow {
  const params = RUNNER_PARAMS[fn];
  if (params === undefined) throw new Error(`UNKNOWN_FN ${fn}`);
  const namespace = (value: unknown): CommandArgs | null => (value instanceof Map ? commandArgs(value as PyValue) : null);
  const g = (index: number): never => given[index] as never;
  const calls: Record<string, () => Promise<PyValue>> = {
    supervise_tick: async () => {
      const [pending, live, spawned] = await superviseTick(hub, namespace(g(0)), Number(g(1)), g(2), g(3), out, deps);
      return [pending, BigInt(live), BigInt(spawned)];
    },
    owner_sweep_tick: () => ownerSweepTick(hub, g(0), deps),
    spawn_runner: async () => BigInt(await spawnRunner(hub, (g(0) as PyValue[]).map(textOf), deps)),
    spawn_task_runner: async () => spawnTaskRunner(hub, textOf(g(0)), namespace(g(1)), deps) as unknown as PyValue,
    refuse_dirty_kernel: async () => {
      await refuseDirtyKernel(hub, namespace(g(0)), optionalText(g(1)), deps);
      return null;
    },
    pause_requested: async () => pauseRequested(hub, textOf(g(0)), deps),
  };
  return {
    run: calls[fn] as () => Promise<PyValue>,
    ts: () => null,
    after: (tag) => Object.fromEntries(params.map((name, index) => [name, given[index]] as const)
      .filter(([name, value]) => name !== "args" && (value instanceof Map || Array.isArray(value)))
      .map(([name, value]) => [name, tag(procShown(value))])),
  };
}

/** ⑤j2：runnerFlow 各函数 hub 之后的参数名，照 kit_hub.py 的签名次序。 */
const RUNNER_PARAMS: Readonly<Record<string, readonly string[]>> = {
  supervise_tick: ["args", "parallel", "children", "failures"], owner_sweep_tick: ["holder"], spawn_runner: ["argv"], spawn_task_runner: ["task", "args"],
  refuse_dirty_kernel: ["args", "task"], pause_requested: ["task"],
};

/** ⑤j1：Namespace 记下的各键（pyjson 的 dict）换成命令的参数。 */
function commandArgs(value: PyValue): CommandArgs {
  if (!(value instanceof Map)) throw new Error("站主命令的参数要是 Namespace 的各键");
  return Object.fromEntries([...value].map(([key, item]) => [String(key), item]));
}

/** ⑤j1：站主命令照名字调，输出截进 out，标准输入是采样时读到的文字。交回 Python 的 int（退出码）。 */
async function commandCall(fn: string, args: CommandArgs, out: CommandOut, stdin: string, deps: RunnerDeps): Promise<PyValue> {
  const calls: Record<string, () => number | Promise<number>> = {
    cmd_init: () => cmdInit(args, out),
    cmd_task_new: () => cmdTaskNew(args, out),
    cmd_task_close: () => cmdTaskClose(args, out, deps),
    cmd_task_rebase: () => cmdTaskRebase(args, out, deps),
    cmd_task_after: () => cmdTaskAfter(args, out, deps),
    cmd_task_unstick: () => cmdTaskUnstick(args, out, deps),
    cmd_task_budget: () => cmdTaskBudget(args, out, deps),
    cmd_task_cleanup: () => cmdTaskCleanup(args, out, deps),
    cmd_send: () => cmdSend(args, out, () => stdin),
    cmd_exec_recheck: () => cmdExecRecheck(args, out, deps),
    cmd_take: () => cmdTake(args, out),
    cmd_status: () => cmdStatus(args, out, deps),
    cmd_metrics: () => cmdMetrics(args, out),
    cmd_run: () => cmdRun(args, out, deps), // ⑤j2
    cmd_owner_sweep: () => cmdOwnerSweep(args, out, deps),
    cmd_exclusive: () => cmdExclusive(args, out, deps),
  };
  return BigInt(await (calls[fn] as () => number | Promise<number>)());
}

/**
 * ⑤j1：重放站主命令之前，--file、--brief 照调用当时的字节写回；调用当时不在的仓库外目录删掉，只删用例临时目录（仓库的上一层）下的
 * （同 python_probe.py，报错文字也同）。
 */
function prepareCommand(request: Record<string, unknown>, repo: string): void {
  for (const [path, data] of Object.entries((request["inputs"] as Record<string, string> | null | undefined) ?? {})) {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, Buffer.from(data, "base64"));
  }
  const parent = normcase(dirname(resolve(repo)));
  for (const path of (request["absent"] as string[] | null | undefined) ?? []) {
    const rel = relative(parent, normcase(resolve(path)));
    if (rel.startsWith("..") || isAbsolute(rel)) throw new Error(`调用当时不在的目录不在用例的临时目录下：${path}`);
    if (existsSync(path)) rmSync(path, { recursive: true, force: true });
  }
}

/** 用例改过的 kit_hub 常量对应到 EngineDeps 的哪一项；不在这里的直接报错（themistally-04 定的：TS 只认支持的常量）。 */
const CONSTANT_DEPS: Readonly<Record<string, string>> = {
  INPUT_FILE_LIMIT: "inputFileLimit", EXEC_LAND_WAIT_SECONDS: "landWaitSeconds", LAND_WAIT_SECONDS: "landLockWaitSeconds", SWEEP_WAIT_SECONDS: "sweepWaitSeconds",
  SWEEP_SECONDS: "sweepSeconds",
};

const stateData = (value: unknown): PyValue => (value instanceof HubState ? value.data : value as PyValue);
const tasksOfState = (value: unknown): PyDict => (value instanceof HubState ? value.tasks() : pyItem(value as PyDict, "tasks") as PyDict);

/** 回合的输入目录在调用当时的文件：{相对路径（正斜杠）: sha256}，按码点排；不是目录时记 null。同 python_probe.py 的 _inputs_files。 */
function inputsFiles(inputs: unknown): Record<string, string> | null {
  if (typeof inputs !== "string" || !existsSync(inputs) || !statSync(inputs).isDirectory()) return null;
  const found: [string, string][] = [];
  const walk = (dir: string, rel: string[]): void => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (lstatSync(path).isDirectory()) walk(path, [...rel, name]);
      else if (statSync(path).isFile()) found.push([[...rel, name].join("/"), createHash("sha256").update(readFileSync(path)).digest("hex")]);
    }
  };
  walk(inputs, []);
  return Object.fromEntries(found.sort((left, right) => cmpCodePoints(left[0], right[0])));
}

/** ⑤i1 手写场景的剧本一项（同 python_probe.py 的 _flow_scripted）：value（带标签）或 raise（[类名, 文字, 退出码]）；files 照注入的写法写进几棵树。 */
interface ScriptItem {
  readonly value?: unknown;
  readonly raise?: [string, string, number];
  readonly files?: { readonly write?: Record<string, string> };
  readonly listing?: string;
  readonly peek?: string;
  readonly ts_set?: readonly (readonly [readonly string[], unknown])[];
}

/** ⑤i2：调用当时某个文件的内容（不是文件记 null）：剧本一项的 peek（C06），与投信那一刻的 peek_deliver（T06）。同 python_probe.py 的 _flow_peek。 */
function flowPeek(roots: readonly string[], rel: string): string | null {
  const file = flowPath(roots, rel);
  return existsSync(file) && statSync(file).isFile() ? readFileSync(file, "utf8") : null;
}

/** 照剧本按次交回、不核对参数，每次调用的参数照 innerCall 记进 calls，随结果交回、三边互相比。 */
function scriptedInjector(name: string, items: readonly ScriptItem[], calls: unknown[], roots: readonly string[], fromTagged: (tagged: never) => PyValue,
  toTagged: (value: PyValue) => unknown) {
  const queue = [...items];
  return (...args: unknown[]): never => {
    calls.push(innerCall(name, args, toTagged));
    const item = queue.shift();
    if (item === undefined) throw new PyCrash("RuntimeError", `剧本用完了：${name}`);
    for (const [key, data] of Object.entries(item.files?.write ?? {})) {
      mkdirSync(dirname(flowPath(roots, key)), { recursive: true });
      writeFileSync(flowPath(roots, key), Buffer.from(data, "base64"));
    }
    if (item.listing !== undefined) { // 调用当时某个目录下的文件名（按码点排；不是目录记 null），记进这次调用
      const folder = flowPath(roots, item.listing);
      (calls[calls.length - 1] as Record<string, unknown>)["listing"] = existsSync(folder) && statSync(folder).isDirectory() ? readdirSync(folder).sort(cmpCodePoints) : null;
    }
    if (item.peek !== undefined) (calls[calls.length - 1] as Record<string, unknown>)["peek"] = flowPeek(roots, item.peek); // ⑤i2 C06：协调人回合进行中的在办标记
    for (const [path, data] of item.ts_set ?? []) { // ⑤i2 跑到静止：照剧本改 ts（键的路径加新值），同 python_probe.py
      let target = args[name.startsWith("Engine.") ? 0 : 1] as PyDict; // TS 的 Engine 方法剧本没有 self，ts 在第一个
      for (const key of path.slice(0, -1)) target = pyItem(target, key) as PyDict;
      target.set(path[path.length - 1] as string, fromTagged(data as never));
    }
    if (item.raise !== undefined) {
      const [kind, message, code] = item.raise;
      throw kind === "LandBusy" ? new LandBusy(message, code) : new HubError(message, code);
    }
    return fromTagged(item.value as never) as never;
  };
}

/** 内层函数从哪来：手写场景的剧本、采样的照记录注入，都不是就用真的。 */
interface Pick {
  readonly has: (name: string) => boolean;
  readonly inject: (name: string) => (...args: unknown[]) => Promise<never>;
  readonly injectSync: (name: string) => (...args: unknown[]) => never;
}

interface EngineFlow {
  readonly run: () => Promise<PyValue>;
  /** 交回值之外要比的 ts（签名里有 ts 才有）。 */
  readonly ts: () => PyValue;
  /** 调用之后的字典与列表参数，照签名次序。 */
  readonly after: (toTagged: (value: PyValue) => unknown) => Record<string, unknown>;
}

/**
 * python_probe.py 的 _flow_call：参数前两个是仓库与 only_task（release_dependents 没有 Engine，只有仓库）；state 当时是 load_state 读出来的
 * （state_seen）照样建 HubState；ts 当时是 state 里的一项（ts_alias）接回同一个对象；land 收到假 Engine（fake_engine）时它的两个方法照记录注入。
 */
function engineFlow(fn: string, hub: Hub, args: readonly PyValue[], request: Record<string, unknown>, deps: EngineDeps, pick: Pick): EngineFlow {
  const names = ENGINE_PARAMS[fn];
  if (names === undefined) throw new Error(`UNKNOWN_FN ${fn}`);
  const given: unknown[] = FLOW_I_MODULE.includes(fn) ? args.slice(1) : args.slice(2);
  const at = (name: string): number => names.indexOf(name);
  const seen = request["state_seen"] as Record<string, Record<string, string>> | null | undefined;
  if (seen !== null && seen !== undefined) {
    const state = new HubState(given[at("state")] as PyDict);
    state.seen.clear();
    for (const [task, keys] of Object.entries(seen)) state.seen.set(task, new Map(Object.entries(keys)));
    given[at("state")] = state;
  }
  if (typeof request["ts_alias"] === "string") given[at("ts")] = pyItem(tasksOfState(given[at("state")]), request["ts_alias"]);
  const engine = (): Engine => {
    const made = new Engine(hub, { run: pick.inject("runner") }, optionalText(args[1]), deps);
    if (pick.has("Engine.verify_delivery")) made.verifyDelivery = pick.inject("Engine.verify_delivery");
    if (pick.has("Engine.auto_jev")) made.autoJev = pick.inject("Engine.auto_jev");
    return made;
  };
  const g = (index: number): never => given[index] as never;
  const none = async (done: Promise<void>): Promise<PyValue> => {
    await done;
    return null;
  };
  const calls: Record<string, () => Promise<PyValue>> = {
    release_dependents: () => releaseDependents(hub, g(0) as StateLike, textOf(g(1))),
    land: () => land(hub, request["fake_engine"] ? { handlePass: pick.inject("engine.handle_pass"), afterLand: pick.inject("engine.after_land") } : engine(),
      textOf(g(0)), g(1) as Map<string, string>, deps),
    "Engine.escalate": () => none(engine().escalate(g(0), textOf(g(1)))),
    "Engine.worker_job": () => none(engine().workerJob(g(0), textOf(g(1)), g(2))),
    "Engine.auto_jev": () => none(engine().autoJev(g(0), g(1), textOf(g(2)))),
    "Engine.stage_workspace": () => engine().stageWorkspace(g(0), textOf(g(1)), textOf(g(2))),
    "Engine.verify_delivery": () => engine().verifyDelivery(g(0), textOf(g(1)), textOf(g(2)), g(3), g(4)),
    "Engine.after_delivery": () => none(engine().afterDelivery(g(0), textOf(g(1)), g(2), g(3))),
    "Engine.finish_kernel_stage": () => none(engine().finishKernelStage(g(0), g(1), textOf(g(2)), textOf(g(3)), g(4), g(5))),
    "Engine.recheck_exec": () => engine().recheckExec(textOf(g(0))),
    "Engine.worker_turns": async () => {
      const [turn, error, timeouts] = await engine().workerTurns(textOf(g(0)), textOf(g(1)), g(2), g(3), textOf(g(4)), g(5), optionalText(g(6)), g(7));
      return [turn, error, BigInt(timeouts)]; // Python 的 int
    },
    "Engine.redeliver": () => engine().redeliver(g(0), g(1), textOf(g(2)), textOf(g(3)), textOf(g(4)), g(5), textOf(g(6)), g(7), g(8)),
    "Engine.handle_pass": () => none(engine().handlePass(g(0), g(1))),
    "Engine.after_land": () => none(engine().afterLand(textOf(g(0)))),
    "Engine.after_land_run": () => none(engine().afterLandRun(textOf(g(0)))),
    "Engine.step": () => engine().step(),
    "Engine.fail_stage": () => engine().failStage(textOf(g(0)), g(1), textOf(g(2))),
    "Engine.coordinator_turn": () => none(engine().coordinatorTurn(g(0), g(1))),
    "Engine.route": () => engine().route(g(0), g(1), g(2), g(3)),
    "Engine.deliver_coordinator_letter": () => engine().deliverCoordinatorLetter(g(0), g(1), textOf(g(2))),
    "Engine.write_brief": async () => {
      engine().writeBrief(textOf(g(0)), textOf(g(1)));
      return null;
    },
    requeue_interrupted: () => requeueInterrupted(hub, g(0), deps),
    requeue_task: () => requeueTask(hub, textOf(g(0)), deps),
    requeue_letters: () => requeueLetters(hub, g(0), g(1), textOf(g(2)), textOf(g(3)), g(4), g(5), textOf(g(6))),
    report_stranded_exec: () => reportStrandedExec(hub, g(0), g(1), g(2), deps),
  };
  return {
    run: calls[fn] as () => Promise<PyValue>,
    ts: () => (names.includes("ts") ? stateData(given[at("ts")]) : null),
    after: (tag) => Object.fromEntries(names.map((name, index) => [name, given[index]] as const)
      .filter(([, value]) => value instanceof Map || Array.isArray(value) || value instanceof HubState)
      .map(([name, value]) => [name, tag(stateData(value))])),
  };
}

/** ⑤i1：Engine 的 deps：各片 deps 的并集，剧本或记录里有的照它交回，用例改过的常量照设。 */
function engineDepsOf(gateDeps: GatePostDeps, landDeps: LandDeps, sweepDeps: SweepDeps, request: Record<string, unknown>, pick: Pick): EngineDeps {
  const constantsGiven: Record<string, number> = {};
  for (const [name, value] of Object.entries((request["constants"] as Record<string, unknown> | null | undefined) ?? {})) {
    const key = CONSTANT_DEPS[name];
    if (key === undefined) throw new Error(`UNSUPPORTED_CONSTANT ${name}`);
    constantsGiven[key] = Number(value);
  }
  const deps: EngineDeps = {
    ...gateDeps,
    ...landDeps,
    ...sweepDeps,
    runSupervised: gateDeps.runSupervised, // 白盒测试那一次（sweepDeps 的是 ts 重装的 runner，Engine 走不到）
    worktreeRoot: pick.has("worktree_root") ? pick.inject("worktree_root") : gateDeps.worktreeRoot,
    ensureWorktree: pick.has("ensure_worktree") ? pick.inject("ensure_worktree") : (h, t, kind, commit, d) => ensureWorktree(h, t, kind, commit, d),
    applyCandidate: pick.has("apply_candidate") ? pick.inject("apply_candidate") : (h, t, d) => applyCandidate(h, t, d),
    seedWhitebox: pick.has("seed_whitebox") ? pick.inject("seed_whitebox") : (h, t, w) => seedWhitebox(h, t, w),
    rolePrompt: pick.has("role_prompt") ? pick.injectSync("role_prompt") : (agent) => rolePrompt(agent),
    runExec: pick.has("run_exec") ? pick.inject("run_exec") : (h, t, d) => runExec(h, t, d),
    runJev: pick.has("run_jev") ? pick.inject("run_jev") : (h, t, suffix, d) => runJev(h, t, suffix, d),
    finalize: pick.has("finalize") ? pick.inject("finalize") : (h, t, d) => finalize(h, t, d),
    tidyFinished: pick.has("tidy_finished") ? pick.inject("tidy_finished") : (h, t, reason, d) => tidyFinished(h, t, reason, d),
    regressionSweep: pick.has("regression_sweep") ? pick.inject("regression_sweep") : (h, t, d) => regressionSweep(h, t, d),
    rehearseLanding: pick.has("rehearse_landing") ? pick.inject("rehearse_landing") : (h, t) => rehearseLanding(h, t, deps),
    releaseHeld: pick.has("release_held") ? pick.inject("release_held") : (h) => releaseHeld(h), // ⑤i2
    inputFileLimit: constants.INPUT_FILE_LIMIT,
    ...constantsGiven,
  };
  return deps;
}

/** 第 ⑤e2b 片：python_probe.py 的 op_hub_contract_flow。 */
export async function hubContractFlow(request: Record<string, unknown>, fromTagged: (tagged: never) => PyValue, toTagged: (value: PyValue) => unknown): Promise<Result> {
  for (const item of (request["restores"] as Restore[] | undefined) ?? []) restoreTree(item);
  if (typeof request["python"] === "string") setKernelPython(request["python"]);
  // ⑤j3：只有 TS 一边的场景给 context（启动器转交时 runHub 设的两项），这时起子进程的命令行照原样记；没给时还原，批量重放里不串到下一条
  const launcher = request["context"] as HubContext | undefined;
  if (launcher === undefined) setKitHub(join(SCRIPTS_DIR, "kit_hub.py"));
  else useLauncherContext(launcher);
  rawArgv = launcher !== undefined;
  const fn = String(request["fn"]);
  const args = (request["args"] as never[]).map(fromTagged);
  const hub = (args[0] === null ? null : new Hub(textOf(args[0]))) as Hub; // ⑤f：hub 可以是 None（用不到它就交回的调用）
  const command = FLOW_J1.includes(fn) || FLOW_J2_COMMANDS.includes(fn); // ⑤j1：站主命令；⑤j2 的 run、owner-sweep、exclusive 同
  const runnerFn = FLOW_J2.includes(fn) && !command; // ⑤j2：第一个参数是 hub 的进程模型函数
  const streamed = FLOW_J1.includes(fn) || FLOW_J2.includes(fn); // 另比 stdout、stderr
  PROCS.clear(); // ⑤j2：这一次重放的假进程
  if (command) prepareCommand(request, textOf(args[0]));
  const captured = { out: [] as string[], err: [] as string[] };
  const commandOut: CommandOut = {
    print: (text = "") => void captured.out.push(`${text}${LF}`),
    printErr: (text = "") => void captured.err.push(`${text}${LF}`),
  };
  // ⑤i1：ts 从参数绑定里取；⑤j1：站主命令没有 ts
  const flowI = fn.startsWith("Engine.") || fn === "land" || FLOW_I_MODULE.includes(fn) || command || runnerFn;
  const ts = (["owner_sweep", "mark_owner_moved", "ts_install_if_stale"].includes(fn) || flowI ? null : args[1]) as PyDict; // ⑤h2：没有 ts 参数的记成 None
  const roots = request["roots"] as string[];
  removeFresh((request["fresh"] as string[] | undefined) ?? [], (request["inner"] as InnerEntry[] | undefined) ?? []);
  const before = flowListing(roots);
  const ledger = hub === null ? null : hub.ledger();
  const offset = ledger !== null && existsSync(ledger) ? statSync(ledger).size : 0;
  const queue = [...((request["inner"] as InnerEntry[] | undefined) ?? [])];
  const replaced = new Set((request["replaced"] as string[] | undefined) ?? []);
  const inject = (name: string) => injector(name, queue, roots, fromTagged, toTagged);
  const injectSync = (name: string) => injectorSync(name, queue, roots, fromTagged, toTagged);
  // ⑤i1 手写场景：剧本里的内层函数照剧本交回（每个名字一份剧本，记下的调用随结果交回）；别的照记录注入或用真的
  const scripted = (request["scripted"] ?? {}) as Record<string, ScriptItem[]>;
  const scriptCalls: unknown[] = [];
  const scriptedOnce = new Map<string, (...args: unknown[]) => never>();
  const scriptedFor = (name: string): ((...args: unknown[]) => never) => {
    if (!scriptedOnce.has(name)) scriptedOnce.set(name, scriptedInjector(name, scripted[name] ?? [], scriptCalls, roots, fromTagged, toTagged));
    return scriptedOnce.get(name) as (...args: unknown[]) => never;
  };
  // ⑤i2 跑到静止：回合剧本按 agent 分开（"runner:<agent>"），各自照次交回，记下的调用同 runner（python_probe.py 的 _flow_runner_by_agent）
  const byAgent = Object.keys(scripted).some((name) => name.startsWith("runner:"));
  const peeks: (string | null)[] = []; // ⑤i2 T06：每次投信那一刻 peek_deliver 那个文件的内容，随结果交回（同 python_probe.py）
  if (typeof request["peek_deliver"] === "string") {
    const realDeliver = hub.deliver.bind(hub);
    hub.deliver = async (...more) => (peeks.push(flowPeek(roots, request["peek_deliver"] as string)), realDeliver(...more));
  }
  const agentRunner = (...args: unknown[]): never => {
    const key = `runner:${String(args[0])}`;
    if (!Object.hasOwn(scripted, key)) throw new PyCrash("RuntimeError", `剧本里没有 ${String(args[0])} 的回合`);
    if (!scriptedOnce.has(key)) scriptedOnce.set(key, scriptedInjector("runner", scripted[key] ?? [], scriptCalls, roots, fromTagged, toTagged));
    return (scriptedOnce.get(key) as (...rest: unknown[]) => never)(...args);
  };
  const pick: Pick = {
    has: (name) => Object.hasOwn(scripted, name) || replaced.has(name),
    injectSync: (name) => (Object.hasOwn(scripted, name) ? scriptedFor(name) : injectSync(name)),
    inject: (name) => {
      if (name === "runner" && byAgent && !Object.hasOwn(scripted, "runner")) return async (...args: unknown[]): Promise<never> => agentRunner(...args);
      if (!Object.hasOwn(scripted, name)) return inject(name);
      const sync = scriptedFor(name);
      return async (...args: unknown[]): Promise<never> => sync(...args);
    },
  };
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
    // ⑤j3 覆盖审计：worktree add 重试之间的 sleep 照剧本换（Python 那边换的是 kit_hub.time.sleep）
    ...(pick.has("sleep") ? { sleep: pick.inject("sleep") } : {}),
  };
  const execDeps: ExecDeps = { // ⑤g2：Python 那边 decisions.Session 换掉时，它的 ask 记成一次内层调用
    ...deps, worktreeRoot: gateDeps.worktreeRoot, mkdtemp: gateDeps.mkdtemp,
    reworkAddedFiles: replaced.has("rework_added_files") ? inject("rework_added_files") : REAL_EXEC_DEPS.reworkAddedFiles,
    loadLockedBatteries: replaced.has("load_locked_batteries") ? inject("load_locked_batteries") : REAL_EXEC_DEPS.loadLockedBatteries,
    ask: replaced.has("Session") ? inject("ask") : jevAsk(request["jev"] as { endpoint: string; key: string } | undefined),
    landWaitSeconds: typeof request["land_wait"] === "number" ? request["land_wait"] : EXEC_LAND_WAIT_SECONDS,
  };
  const landDeps: LandDeps = { // ⑤h1：调度器的 _running_attempts 换掉时照记录注入
    ...deps, runningAttempts: replaced.has("_running_attempts") ? injectSync("_running_attempts") : REAL_LAND_DEPS.runningAttempts,
    pidAlive: replaced.has("pid_alive") ? injectSync("pid_alive") : REAL_LAND_DEPS.pidAlive,
  };
  const sweepDeps: SweepDeps = { // ⑤h2：嵌在 owner_sweep 里的 rehearse_landing 没换掉时，照样用这一份 deps
    ...execDeps, // land_wait 照 ⑤g2 只管 EXEC_LAND_WAIT_SECONDS；后台回归的三个时限各有各的键，同 python_probe.py
    landLockWaitSeconds: typeof request["land_lock_wait"] === "number" ? request["land_lock_wait"] : LAND_WAIT_SECONDS,
    sweepGates: replaced.has("sweep_gates") ? inject("sweep_gates") : REAL_SWEEP_DEPS.sweepGates,
    rehearseLanding: replaced.has("rehearse_landing") ? inject("rehearse_landing") : (h, t) => rehearseLanding(h, t, sweepDeps),
    findBun: replaced.has("find_bun") ? injectSync("find_bun") : REAL_SWEEP_DEPS.findBun,
    readKernelImpl: replaced.has("read_kernel_impl") ? injectSync("read_kernel_impl") : REAL_SWEEP_DEPS.readKernelImpl,
    runSupervised: replaced.has("ts_runner") ? inject("ts_runner") : REAL_SWEEP_DEPS.runSupervised,
    tsInstallIfStale: replaced.has("ts_install_if_stale") ? inject("ts_install_if_stale") : (h) => tsInstallIfStale(h, sweepDeps),
    sweepSeconds: typeof request["sweep_seconds"] === "number" ? request["sweep_seconds"] : SWEEP_SECONDS,
    sweepWaitSeconds: typeof request["sweep_wait"] === "number" ? request["sweep_wait"] : SWEEP_WAIT_SECONDS,
  };
  const givenEnv = Object.entries({ ...FLOW_GIT_ENV, ...((request["env"] as Record<string, string> | undefined) ?? {}) });
  const savedEnv = givenEnv.map(([name]) => [name, process.env[name]] as const);
  for (const [name, value] of givenEnv) process.env[name] = value;
  // ⑤i1：名册与交差文件的哈希照采样当时的改动设上，调用完还原（同 hubTurn）
  const roster = constants.ROSTER as Record<string, constants.RosterSpec>;
  const shas = DELIVERY_SHA256 as Map<string, string | null>;
  const givenRoster = (request["roster"] ?? {}) as Record<string, constants.RosterSpec>;
  const givenShas = (request["delivery_sha256"] ?? {}) as Record<string, string>;
  const savedRoster = Object.keys(givenRoster).map((name) => [name, Object.hasOwn(roster, name) ? roster[name] : undefined] as const);
  const savedShas = Object.keys(givenShas).map((name) => [name, shas.has(name) ? shas.get(name) : undefined] as const);
  Object.assign(roster, givenRoster);
  for (const [name, value] of Object.entries(givenShas)) shas.set(name, value);
  const holder: { flow: EngineFlow | null } = { flow: null };
  let result: Result;
  try {
    const value = await withPinnedClock(Number(request["pin"]), async (): Promise<PyValue> => {
      if (command) {
        const stdin = typeof request["stdin"] === "string" ? request["stdin"] : "";
        const deps = runnerDepsOf(engineDepsOf(gateDeps, landDeps, sweepDeps, request, pick), pick);
        const clock = request["clock"] === "sleep";
        // 回合只在跑到静止时照剧本换（同 _sleep_clock：剧本里有 runner 才换）；Engine 的两个方法照 Python，换掉了就换
        return withEnginePatches(pick, clock && (Object.hasOwn(scripted, "runner") || byAgent), () =>
          commandCall(fn, commandArgs(args[1] as PyValue), commandOut, stdin, clock ? sleepClockDeps(deps) : deps));
      }
      if (runnerFn) { // ⑤j2：记下的进程换成假进程（同一个编号同一个对象）
        const given = args.slice(1).map((item) => procsOf(item, queue, roots, fromTagged));
        holder.flow = runnerFlow(fn, hub, given, commandOut, runnerDepsOf(engineDepsOf(gateDeps, landDeps, sweepDeps, request, pick), pick));
        return holder.flow.run();
      }
      if (flowI) { // ⑤i1：钉住的时刻也管 int(time.time())（nowMicros）
        holder.flow = engineFlow(fn, hub, args, request, engineDepsOf(gateDeps, landDeps, sweepDeps, request, pick), pick);
        return holder.flow.run();
      }
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
        case "finalize": // ⑤h1
          return finalize(hub, ts, landDeps);
        case "landing_blockers":
          return landingBlockers(hub, ts, args[2] as PyValue, landDeps);
        case "retire_attempts":
          return retireAttempts(hub, ts, textOf(args[2]), landDeps);
        case "tidy_finished":
          return tidyFinished(hub, ts, textOf(args[2]), landDeps);
        case "remove_workspaces":
          return removeWorkspaces(hub, ts);
        case "commit_records":
          return commitRecords(hub, ts);
        case "land_oracle":
          return landOracle(hub, ts);
        case "land_rework_chain":
          return landReworkChain(hub, ts);
        case "undo_landing":
          return undoLanding(hub, ts, textOf(args[2]), args[3] as PyDict[]);
        case "record_pass":
          return recordPass(hub, ts, textOf(args[2]), landDeps);
        case "regression_sweep": // ⑤h2
          return regressionSweep(hub, ts, sweepDeps);
        case "rehearse_landing":
          return rehearseLanding(hub, ts, sweepDeps);
        case "rehearsal_letter":
          return rehearsalLetter(hub, ts, textOf(args[2]), textOf(args[3])).then(() => null);
        case "mark_owner_moved":
          return markOwnerMoved(hub, textOf(args[1]), textOf(args[2]), args[3] as string[]).then(() => null);
        case "owner_sweep":
          return ownerSweep(hub, sweepDeps);
        case "ts_install_if_stale":
          return tsInstallIfStale(hub, sweepDeps);
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
  for (const [name, value] of savedRoster) {
    if (value === undefined) delete roster[name];
    else roster[name] = value;
  }
  for (const [name, value] of savedShas) {
    if (value === undefined) shas.delete(name);
    else shas.set(name, value);
  }
  const tail = ledger !== null && existsSync(ledger) ? readFileSync(ledger).subarray(offset) : Buffer.alloc(0);
  const flow = holder.flow;
  const shown = flow === null ? ts : flow.ts();
  return {
    ok: true, value: {
      result, ts: toTagged(shown), files: flowChanges(roots, before), ledger: tail.toString("base64"), git: flowGit(roots),
      ...(flow === null ? {} : { args_after: flow.after(toTagged) }),
      ...(streamed ? { stdout: captured.out.join(""), stderr: captured.err.join("") } : {}), // ⑤j1；⑤j2 同
      ...(FLOW_J2.includes(fn) ? { self_pid: process.pid } : {}), // ⑤j2：探针自己的 pid，契约归一化时只换等于它的
      ...(Object.keys(scripted).length > 0 ? { scripted_calls: scriptCalls } : {}),
      ...(peeks.length > 0 ? { deliver_peeks: peeks } : {}),
    },
  };
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

/**
 * ⑤j2：python_probe.py 的 op_hub_popen。runner.ts 的真 popen（Windows 上是 CreateProcessW，只在 Bun 下有；Node 下照实交回它的报错），
 * 给了 log 就照 spawnTaskRunner 先 open("a") 再起；每 50 毫秒 poll 一次到子进程退出（最多 timeout 秒）。ctrl_c_default 同 Python：起之前
 * 恢复缺省的 Ctrl+C 处理、起完恢复成忽略（只在 Bun 下，经 bun:ffi），子进程读 PEB 的 ConsoleFlags 分得出有没有另起进程组。inherit 同 Python：
 * 起之前本进程另开这个文件的一个可继承句柄（只在 Bun 下），命令行里的 <handle> 换成它的数值，起完关掉；子进程只该继承三个标准句柄。
 */
export async function hubPopen(request: Record<string, unknown>): Promise<Result> {
  const path = (request["log"] as string | null | undefined) ?? null;
  const fd = path === null ? null : openSync(path, "a");
  const ctrlC = request["ctrl_c_default"] === true ? await consoleCtrlHandler() : null;
  const api = typeof request["inherit"] === "string" ? await winProcessApi() : null;
  const extra = api === null ? null : api.openInheritable(request["inherit"] as string, "append");
  const argv = (request["argv"] as string[]).map((item) => (item === "<handle>" && extra !== null ? String(extra) : item));
  let child: ChildLike;
  ctrlC?.(0);
  try {
    child = await REAL_RUNNER_DEPS.popen(argv, (request["cwd"] as string | null | undefined) ?? null, fd === null ? null : { fd, path: path as string });
  } catch (error) {
    return errorResult(error);
  } finally {
    ctrlC?.(1);
    if (fd !== null) closeSync(fd);
    if (extra !== null) api?.close(extra);
  }
  const deadline = Date.now() + Number(request["timeout"] ?? 30) * 1000;
  let code = child.poll();
  while (code === null && Date.now() < deadline) {
    await new Promise((done) => setTimeout(done, 50));
    code = child.poll();
  }
  return {
    ok: true,
    value: { code, returncode: code === null ? null : child.returncode ?? null, pid: (child.pid ?? 0) > 0, log: path === null ? null : readFileSync(path).toString("base64") },
  };
}

/** SetConsoleCtrlHandler(NULL, ignore)（只给 hubPopen 的 ctrl_c_default 用，只在 Bun 下）。 */
async function consoleCtrlHandler(): Promise<(ignore: number) => void> {
  const ffi = await import("bun:ffi");
  const kernel32 = ffi.dlopen("kernel32.dll", { SetConsoleCtrlHandler: { args: [ffi.FFIType.ptr, ffi.FFIType.i32], returns: ffi.FFIType.i32 } });
  const symbols = kernel32.symbols as unknown as { SetConsoleCtrlHandler(handler: null, ignore: number): number };
  return (ignore) => void symbols.SetConsoleCtrlHandler(null, ignore);
}

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
