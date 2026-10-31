// hub.call（第 ⑤a 片）：按函数名调 @themis/hub 的纯函数，参数与结果照 python_probe.py 的 op_hub_call。
// 结果里的整数照 Python 写成 int（bigint）；HubError 交回文字与退出码，Python 语义的异常只比类型。
import { PyCrash, pyStrValue } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { PyOverflowError, PyReError, PyValueError } from "@themis/base/pyregex";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import { withFileLock } from "@themis/base/native";
import * as constants from "@themis/hub/constants";
import { HubError } from "@themis/hub/errors";
import { DirLock, Hub, HubState, holdLetters, keepPrevious, ledgerEvents, letterMain, releaseHeld } from "@themis/hub/mailbox";
import { letterErrors, parseLetter, renderLetter, stageOf } from "@themis/hub/letters";
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

function errorResult(error: unknown): Result {
  if (error instanceof HubError) return { ok: false, error: "HubError", message: error.message, code: error.code };
  if (error instanceof PyCrash) return { ok: false, error: error.kind };
  const code = (error as NodeJS.ErrnoException).code;
  if (code === "ENOENT") return { ok: false, error: "FileNotFoundError" };
  if (code === "EEXIST") return { ok: false, error: "FileExistsError" };
  if (code === "EPERM" || code === "EACCES" || code === "EBUSY") return { ok: false, error: "PermissionError" };
  return { ok: false, error: `JS:${(error as Error).name}:${(error as Error).message}` };
}
