// pi_dispatch 的 mutate（迁移第 ④b5a、④b5b 片）：变异清单的读取与校验、只插入代码的提示、--check-anchors 的锚点核对与提示；
// 变异轮次（基线、逐条套用、判定、恢复）、结果行与计数、决策点 mutation-equivalence，attempt 的干净副本与 --tree 的原地两种入口。
// hub 解析 --check-anchors 的 OK、MISMATCH、MISSING 行，并把提示原样转进信里，所以提示里的“最相近的行”、百分比与第一处不同都照
// difflib 逐字。记录字段的次序照 Python 的字典；整数一律是 bigint。
import { readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyFixed, pyFloatOf, pyGet, pyItem, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyDecodeUtf8, pyReadBytes, pyReadText, pyReadTextReplace } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, encodeUtf8, loads } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { displayPath, isWithin, ntIsabs, purePathStr, pyResolve } from "@themis/base/pypath";
import { compilePy } from "@themis/base/pyregex";
import { PY_END, cmpCodePoints, codePoints, pySplitlines, pyStrCount, pyStrFind, pyStrReplace, pyStrip } from "@themis/base/pyre";
import { SequenceMatcher } from "@themis/base/pydifflib";
import { pyGettempdir, pyMkdtemp } from "@themis/base/pytempfile";
import { REVIEWABLE_STATES, copyfile, freshFailure, graceOf } from "./check-commands.ts";
import { nextNumber, prepareFreshWorkspace, runCommandItem } from "./command-runner.ts";
import { DECISIONS_RECORD, usageTotals } from "./decision-records.ts";
import { candidatePatchOk, loadAttempt, logEvent, removeWorktree, sha256File, strArg, writeJson } from "./evidence.ts";
import { plannerAttemptPublicationErrors } from "./gates.ts";
import { snapshotTree, treeDrift } from "./gitops.ts";
import { repoConfig } from "./kernel-config.ts";
import { childEnv } from "./pi-cli.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_FAIL, EXIT_OK, EXIT_USAGE, Repo, readJsonOr } from "./repo.ts";
import type { AssessBattery, DecisionSession, SessionFactory } from "./run-health.ts";
import { getState, resolveRunDir } from "./status.ts";

export const MUTATION_DEFAULT_TIMEOUT = 600n;
const MUTATION_MAX_COMMANDS = 8;
const MUTATION_COMMAND_ID_PATTERN = "^[A-Za-z][A-Za-z0-9_-]{0,31}$";
const MUTATION_COMMAND_ID_RE = new RegExp(`^[A-Za-z][A-Za-z0-9_-]{0,31}${PY_END}`, "u");
/** --check-anchors 的“最相近”提示：相似度不到这个值的行不列出。 */
const ANCHOR_HINT_MIN_RATIO = 0.6;
/** 字符级提示里，不同之处两边各带多少个字符的上下文。 */
const ANCHOR_DIFF_CONTEXT = 12;
const LF = String.fromCharCode(10);
const CRLF = String.fromCharCode(13, 10);
const SEP = process.platform === "win32" ? String.fromCharCode(92) : "/";

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const isStr = (value: PyValue | undefined): value is string => typeof value === "string";
/** isinstance(value, int) and not isinstance(value, bool) and value > 0。 */
const positiveInt = (value: PyValue | undefined): boolean => typeof value === "bigint" && value > 0n;

/** 清单校验通过后的一条命令（_commands 的一项）。 */
export interface MutationCommand {
  readonly id: string;
  readonly argv: string[];
  readonly cwd: string;
  readonly timeout_seconds: bigint;
}

export interface MutationSpec {
  readonly raw: PyDict;
  readonly commands: MutationCommand[];
  readonly mutations: PyDict[];
}

/** relative_ok：非空字符串，不是绝对路径，各段里没有 ".."。 */
function relativeOk(value: PyValue | undefined): boolean {
  if (!isStr(value) || !value) return false;
  if (process.platform === "win32" ? ntIsabs(value) : value.startsWith("/")) return false;
  return !purePathStr(value).split(SEP).includes("..");
}

const argvOk = (value: PyValue | undefined): boolean => Array.isArray(value) && value.length > 0 && value.every((item) => isStr(item) && item.length > 0);

/**
 * _load_mutation_spec：读取并校验变异清单，交回（清单, 问题列表）；问题的文字与次序照 Python。shown 是 Python 那边
 * str(Path(spec)) 的写法，只用在“读不了”的报错里。
 */
export function loadMutationSpec(file: string): [MutationSpec | null, string[]] {
  let raw: PyValue;
  try {
    raw = loads(pyReadText(file, purePathStr(file)));
  } catch (error) {
    const reason = readFailure(error);
    if (reason === null) throw error;
    return [null, [`变异清单无法读取或不是合法 JSON：${reason}`]];
  }
  if (!isDict(raw)) return [null, ["变异清单必须是 JSON 对象"]];
  const spec = raw;
  const problems: string[] = [];
  const get = (key: string, fallback: PyValue): PyValue => (spec.has(key) ? (spec.get(key) as PyValue) : fallback);
  if (!relativeOk(get("cwd", "."))) problems.push("cwd 必须是工作副本内的相对路径");
  const timeout = get("timeout_seconds", MUTATION_DEFAULT_TIMEOUT);
  if (!positiveInt(timeout)) problems.push("timeout_seconds 必须是正整数");
  const commands: { id: PyValue; argv: PyValue; cwd: PyValue; timeout_seconds: PyValue }[] = [];
  if (spec.has("commands") && spec.has("command")) {
    problems.push("command 与 commands 只能写一个（commands 是 2.8.0 的多条命令）");
  } else if (spec.has("commands")) {
    let rawCommands = spec.get("commands") as PyValue;
    if (!(Array.isArray(rawCommands) && rawCommands.length >= 1 && rawCommands.length <= MUTATION_MAX_COMMANDS)) {
      problems.push(`commands 必须是 1 到 ${MUTATION_MAX_COMMANDS} 个对象的数组`);
      rawCommands = [];
    }
    (rawCommands as PyValue[]).forEach((entry, index) => {
      const label = `commands[${index + 1}]`;
      if (!isDict(entry) || [...entry.keys()].some((key) => !["id", "argv", "cwd", "timeout_seconds"].includes(key as string))) {
        problems.push(`${label} 必须是只含 id、argv、cwd、timeout_seconds 的对象`);
        return;
      }
      const cid = entry.get("id") ?? null;
      if (!isStr(cid) || !MUTATION_COMMAND_ID_RE.test(cid)) {
        problems.push(`${label}.id 必须匹配 ${MUTATION_COMMAND_ID_PATTERN}（会写进日志文件名）`);
      } else if (commands.some((command) => command.id === cid)) {
        problems.push(`${label}.id 重复：${cid}`);
      }
      if (!argvOk(entry.get("argv"))) problems.push(`${label}.argv 必须是非空的字符串数组（argv，不经过 shell）`);
      const cwd = entry.has("cwd") ? (entry.get("cwd") as PyValue) : get("cwd", ".");
      if (!relativeOk(cwd)) problems.push(`${label}.cwd 必须是工作副本内的相对路径`);
      const own = entry.has("timeout_seconds") ? (entry.get("timeout_seconds") as PyValue) : timeout;
      if (!positiveInt(own)) problems.push(`${label}.timeout_seconds 必须是正整数`);
      commands.push({ id: cid, argv: entry.get("argv") ?? null, cwd, timeout_seconds: own });
    });
  } else if (!argvOk(spec.get("command"))) {
    problems.push("command 必须是非空的字符串数组（argv，不经过 shell）；多条命令写 commands（2.8.0）");
  } else {
    commands.push({ id: "main", argv: spec.get("command") as PyValue, cwd: get("cwd", "."), timeout_seconds: timeout });
  }
  // {c["id"] for c in commands}：id 是列表或字典时 Python 在这里就崩（不可哈希）
  const unhashable = commands.find((command) => Array.isArray(command.id) || isDict(command.id));
  if (unhashable) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(unhashable.id)}'`);
  const knownIds = new Set(commands.map((command) => command.id));
  let mutations = spec.get("mutations");
  if (!(Array.isArray(mutations) && mutations.length)) {
    problems.push("mutations 必须是非空数组");
    mutations = [];
  }
  const names = new Set<string>();
  (mutations as PyValue[]).forEach((item, index) => {
    const label = `mutations[${index + 1}]`;
    if (!isDict(item)) {
      problems.push(`${label} 必须是对象`);
      return;
    }
    const name = item.get("name");
    if (!isStr(name) || !pyStrip(name)) problems.push(`${label}.name 必须是非空字符串`);
    else if (names.has(name)) problems.push(`${label}.name 重复：${name}`);
    else names.add(name);
    if (!relativeOk(item.get("file"))) problems.push(`${label}.file 必须是工作副本内的相对路径`);
    const [old, replacement] = [item.get("old"), item.get("new")];
    if (!isStr(old) || !old) problems.push(`${label}.old 必须是非空字符串`);
    if (!isStr(replacement)) problems.push(`${label}.new 必须是字符串`);
    else if (replacement === old) problems.push(`${label}.new 与 old 相同，不构成变异`);
    if (!positiveInt(item.has("count") ? (item.get("count") as PyValue) : 1n)) problems.push(`${label}.count 必须是正整数`);
    const expectMissed = item.get("expect_missed") ?? null;
    if (expectMissed !== null) {
      if (!(Array.isArray(expectMissed) && expectMissed.length && expectMissed.every(isStr) && new Set(expectMissed).size === expectMissed.length)) {
        problems.push(`${label}.expect_missed 必须是不重复的命令 id 数组`);
      } else {
        const unknown = [...new Set(expectMissed as string[])].filter((id) => !knownIds.has(id)).sort(cmpCodePoints);
        if (unknown.length) problems.push(`${label}.expect_missed 里有清单没有的命令：${unknown.join(", ")}`);
      }
    }
    const equivalent = item.get("equivalent") ?? null;
    if (equivalent !== null) {
      if (!isStr(equivalent) || !pyStrip(equivalent)) problems.push(`${label}.equivalent 必须是写明等价理由的非空字符串`);
      else if (expectMissed !== null) problems.push(`${label} 同时写了 equivalent 与 expect_missed：等价已表示每条命令都预期漏掉`);
    }
  });
  if (problems.length) return [null, problems];
  return [{ raw: spec, commands: commands as unknown as MutationCommand[], mutations: mutations as PyDict[] }, problems];
}

/** except (OSError, ValueError) as exc：读不出、不是 UTF-8、不是合法 JSON；RecursionError 不在其中，照抛。 */
function readFailure(error: unknown): string | null {
  if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError) return error.message;
  if (error instanceof PyJsonError && error.kind !== "RecursionError") return error.message;
  return null;
}

/** _insertion_only：new 包含完整的 old，原代码仍在，只插入了新代码。 */
export function insertionOnly(item: PyDict): boolean {
  const [old, replacement] = [item.get("old"), item.get("new")];
  return isStr(old) && isStr(replacement) && old.length > 0 && replacement.includes(old);
}

/** _mutation_spec_warnings：不阻止运行的清单提示。 */
export function mutationSpecWarnings(spec: MutationSpec): string[] {
  return spec.mutations.flatMap((item, index) =>
    insertionOnly(item)
      ? [`M${String(index + 1).padStart(2, "0")} ${pyStrValue(item.get("name") ?? null)}：new 包含完整的 old，原代码仍在，只插入了新代码。` +
          "插入的代码不改变被测行为时，漏掉不说明缺少测试；确认它确实改变了行为（例如提前返回、改写结果）"]
      : []);
}

// --- 锚点 ---------------------------------------------------------------------

const cpSlice = (text: string, start: number, end?: number): string => codePoints(text).slice(start, end).join("");

/** 文件按 UTF-8 读、CRLF 先换成 LF；不是 UTF-8 时抛 PyUnicodeDecodeError。 */
const lfText = (file: string): string => pyDecodeUtf8(pyReadBytes(file)).replaceAll(CRLF, LF);

/** _anchor_count：old 在文件里的出现次数，按 _apply_mutation 的口径（文件与 old 的 CRLF 都先按 LF 比对）。 */
export function anchorCount(file: string, old: string): number {
  return pyStrCount(lfText(file), old.replaceAll(CRLF, LF));
}

/** _first_difference：第一处不同在第几个字符、两边各是什么；old 可以只是这一行的一段，行首行尾多出来的不算不同。 */
function firstDifference(wanted: string, actual: string, where = "old 首行"): string[] {
  const wantedLength = codePoints(wanted).length;
  for (const [tag, i1, i2, j1, j2] of new SequenceMatcher(wanted, actual, false).getOpcodes()) {
    if (tag === "equal" || (tag === "insert" && (i1 === 0 || i1 === wantedLength))) continue;
    const what = tag === "insert" ? `文件里多了「${cpSlice(cpSlice(actual, j1, j2), 0, 40)}」`
      : tag === "delete" ? `old 里多了「${cpSlice(cpSlice(wanted, i1, i2), 0, 40)}」`
        : `old 是「${cpSlice(cpSlice(wanted, i1, i2), 0, 40)}」，文件是「${cpSlice(cpSlice(actual, j1, j2), 0, 40)}」`;
    return [`  第一处不同在 ${where}（去掉首尾空白）第 ${i1 + 1} 个字符：${what}；old …${cpSlice(wanted, Math.max(0, i1 - ANCHOR_DIFF_CONTEXT), i2 + ANCHOR_DIFF_CONTEXT)}…，` +
      `文件 …${cpSlice(actual, Math.max(0, j1 - ANCHOR_DIFF_CONTEXT), j2 + ANCHOR_DIFF_CONTEXT)}…`];
  }
  return [];
}

/** _later_difference：首行在文件第 number 行对上了，逐行比 old 的后续行与文件里接着的行。 */
function laterDifference(old: string, lines: string[], number: number): string[] {
  let rest = old.split(LF);
  while (rest.length && !pyStrip(rest[0] as string)) rest.shift();
  rest = rest.slice(1);
  while (rest.length && !pyStrip(rest[rest.length - 1] as string)) rest.pop();
  const end = lines.length && lines[lines.length - 1] === "" ? lines.length - 1 : lines.length;
  for (const [index0, wanted] of rest.entries()) {
    const offset = index0 + 1;
    const index = number - 1 + offset;
    if (index >= end) return [`  首行对上了；文件在 L${end} 就结束了，old 还多 ${rest.length - offset + 1} 行`];
    const [want, have] = [pyStrip(wanted), pyStrip(lines[index] as string)];
    if (want === have || (offset === rest.length && have.startsWith(want))) continue;
    return [`  首行对上了，old 第 ${offset + 1} 行与文件 L${index + 1} 不同`, ...firstDifference(want, have, `old 第 ${offset + 1} 行`)];
  }
  return ["  逐行去掉首尾空白之后都对上了：差在缩进、行尾空白或换行"];
}

/** _anchor_hints：出现 0 次时列出最相近的至多 3 行与第一处不同；出现多次时列出每一处的行号与锚点之后的下一行。 */
export function anchorHints(file: string, oldRaw: string, found: number): string[] {
  const lines = lfText(file).split(LF);
  const old = oldRaw.replaceAll(CRLF, LF);
  if (found === 0) {
    const first = old.split(LF).map(pyStrip).find((line) => line) ?? "";
    if (!first) return [];
    const scored = lines
      .map((line, index) => [new SequenceMatcher(first, pyStrip(line)).ratio(), index + 1, line] as const)
      .filter(([, , line]) => pyStrip(line))
      .sort((x, y) => y[0] - x[0] || x[1] - y[1]);
    const near = scored.slice(0, 3).filter(([ratio]) => ratio >= ANCHOR_HINT_MIN_RATIO)
      .map(([ratio, number, line]) => `最相近 L${number}（${pyFixed(ratio * 100, 0)}%）：${cpSlice(pyStrip(line), 0, 160)}`);
    if (!near.length) return ["文件里没有相近的行"];
    const best = scored[0] as (typeof scored)[number];
    const difference = firstDifference(first, pyStrip(best[2]));
    return [...near.slice(0, 1), ...(difference.length ? difference : laterDifference(old, lines, best[1])), ...near.slice(1)];
  }
  const text = lines.join(LF);
  const hints: string[] = [];
  for (let start = pyStrFind(text, old); start !== -1 && hints.length < 5; start = pyStrFind(text, old, start + 1)) {
    const lineNo = text.slice(0, start).split(LF).length;
    const endLine = text.slice(0, start + old.length).split(LF).length;
    const following = endLine < lines.length ? (lines[endLine] as string) : "";
    hints.push(`出现在 L${lineNo}；锚点之后的下一行：${cpSlice(pyStrip(following), 0, 160) || "（空行）"}`);
  }
  return hints;
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

/** _check_anchors：只核对每条 old 的出现次数，不运行命令，不写任何文件。 */
export function checkAnchors(tree: string, spec: MutationSpec, out: PyOut): number {
  let mismatched = 0;
  spec.mutations.forEach((item, index) => {
    const mid = `M${String(index + 1).padStart(2, "0")}`;
    const count = Number(item.has("count") ? (item.get("count") as bigint) : 1n);
    const file = purePathStr(tree, item.get("file") as string);
    let status: string;
    let detail: string;
    let hints: string[] = [];
    if (!isFile(file) || !isWithin(pyResolve(file), tree)) {
      [status, detail] = ["MISSING", "文件不存在或位于树之外"];
    } else {
      let found: number | null = null;
      try {
        found = anchorCount(file, item.get("old") as string);
      } catch (error) {
        if (!(error instanceof PyUnicodeDecodeError)) throw error;
      }
      if (found === null) {
        [status, detail] = ["MISSING", "文件不是 UTF-8 文本"];
      } else {
        status = found === count ? "OK" : "MISMATCH";
        detail = found === count ? `出现 ${found} 次` : `出现 ${found} 次，期望 ${count} 次`;
        if (found !== count) hints = anchorHints(file, item.get("old") as string, found);
      }
    }
    if (status !== "OK") mismatched += 1;
    out.print(`${status.padEnd(8)} ${mid} ${pyStrValue(item.get("name") ?? null)}  ${detail}`, { flush: true });
    for (const hint of hints) out.print(`         ${hint}`, { flush: true });
  });
  out.print(`锚点核对：${spec.mutations.length} 条，${mismatched} 条不符`);
  return mismatched ? EXIT_FAIL : EXIT_OK;
}

export interface MutateArgs {
  readonly repo: string | null;
  readonly run_dir: string | null;
  readonly spec: string;
  readonly keep_workspace: boolean;
  readonly tree: string | null;
  readonly out: string | null;
  readonly check_anchors: boolean;
}

/**
 * cmd_mutate：在干净副本（基线 + 候选补丁 + setup）上逐个套用最小变异，看测试能否抓住。先不做变异把命令跑一遍，必须通过；
 * 之后每条变异单独跑，命令失败（退出码非 0 或超时）记“抓住”，通过记“漏掉”，old 的出现次数与 count 不符记“跳过”。
 * 记录写到 <run-dir>/mutations/NN/。--tree 对任意一棵树原地做同样的事（_mutate_tree）。
 */
export async function cmdMutate(args: MutateArgs, out: PyOut, sessions: SessionFactory): Promise<number> {
  if (args.tree) return mutateTree(args, args.tree, out, sessions);
  if (!args.run_dir) throw new DispatchError("缺少 run_dir：对 attempt 给 run_dir，对草稿树用 --tree <路径>", EXIT_USAGE);
  if (args.out || args.check_anchors) throw new DispatchError("--out 与 --check-anchors 只在 --tree 模式下有效", EXIT_USAGE);
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const publicationErrors = plannerAttemptPublicationErrors(repo, runDir, contract);
  if (publicationErrors.length) throw new DispatchError(`planner-v2 发布门禁拒绝变异检查：${publicationErrors.join("；")}`, EXIT_BLOCKED);
  const state = getState(runDir);
  if (!REVIEWABLE_STATES.includes(state) && state !== "INTEGRATED") throw new DispatchError(`状态 ${state} 不能做变异检查`);
  const candidate = readJsonOr(path.join(runDir, "candidate.json"), new Map());
  if (!pyTruthy(pyGet(candidate, "tree")) || !candidatePatchOk(runDir, candidate)) {
    throw new DispatchError("候选补丁缺失、被改动或未通过往返校验，不能建立干净副本");
  }
  const spec = loadValidSpec(args.spec, out);
  const warnings = printWarnings(spec, out);
  const config = repoConfig(repo);
  const [env] = childEnv(config);
  const grace = graceOf(config);
  const root = path.join(runDir, "mutations");
  pathMkdir(root, false, true);
  const number = nextNumber(root);
  const outDir = path.join(root, String(number).padStart(2, "0"));
  pathMkdir(outDir, false, false);
  copyfile(args.spec, path.join(outDir, "spec.json"));
  const session = sessions(config, repo.agentDir, path.join(outDir, DECISIONS_RECORD), "mutation-equivalence");
  let workspace: string;
  try {
    workspace = await prepareFreshWorkspace(repo, runDir, meta as PyDict, contract, candidate as PyDict, config, outDir, env, grace);
  } catch (error) {
    const message = freshFailure(error);
    if (message === null) throw error;
    writeJson(path.join(outDir, "mutations.json"), new Map<string, PyValue>([["aborted", "fresh_workspace_failed"], ["error", message], ["at", utcNow()]]), true);
    throw new DispatchError(`无法建立干净副本：${message}`);
  }
  const started = utcNow();
  let baseline: PyDict;
  let results: PyDict[];
  let drifted: string[];
  try {
    [baseline, results] = await runMutationRounds(spec, workspace, outDir, env, grace, "mutations/", session, out);
    if (!pyTruthy(baseline.get("passed") ?? null)) {
      writeJson(path.join(outDir, "mutations.json"), new Map<string, PyValue>([["aborted", "baseline_failed"], ["baseline", baseline], ["at", utcNow()]]), true);
      throw new DispatchError(`不做变异时 command 没有通过（${reasonOf(baseline)}），变异结果没有意义；先让它在候选上通过`);
    }
    const treeAfter = snapshotTree(workspace, strArg(pyItem(meta, "base_sha")), outDir, "after", pyGet(meta, "git_autocrlf"));
    drifted = treeDrift(workspace, strArg(pyItem(candidate, "tree")), treeAfter).modified;
  } finally {
    if (!args.keep_workspace) removeWorktree(repo, workspace);
  }
  const counts = mutationCounts(results, firstIdIfMulti(spec));
  const recordPath = path.join(outDir, "mutations.json");
  const first = spec.commands[0] as MutationCommand;
  const payload = new Map<string, PyValue>([
    ["run", number], ["started_at", started], ["ended_at", utcNow()], ["candidate_tree", pyItem(candidate, "tree")],
    ["spec_sha256", sha256File(path.join(outDir, "spec.json"))], ["command", first.argv], ["cwd", first.cwd], ["commands", commandsValue(spec)],
    ["workspace", workspace], ["workspace_kept", Boolean(args.keep_workspace)], ["candidate_files_left_modified", drifted],
    ["baseline", baseline], ["counts", counts], ["counts_by_command", mutationCountsByCommand(results, spec)],
    ["not_run", mutationsNotRun(spec, results)], ["warnings", warnings], ["results", results], ["decisions", decisionsPayload(session)],
  ]);
  writeJson(recordPath, payload, true);
  logEvent(runDir, "mutations", [["run", number], ["commands", spec.commands.map((command) => command.id)], ...counts]);
  printMutationTotals(results, spec, displayPath(recordPath, repo.root), out);
  printMutationDecisions(session, path.join(outDir, DECISIONS_RECORD), out);
  if (drifted.length) {
    out.print(`WARN  变异后候选文件没有恢复原样：${drifted.slice(0, 10).join(", ")}（记录仍有效，干净副本${args.keep_workspace ? "已保留" : "已移除"}）`);
  }
  return (payload.get("not_run") as string[]).length ? EXIT_FAIL : EXIT_OK;
}

/**
 * _mutate_tree：对任意一棵树（规划端的草稿 worktree）原地做变异，不要求 attempt。判定与 attempt 模式是同一段代码；记录不写进
 * 被变异的树（缺省是系统临时目录下新建的目录，结束时打印），每条变异之后恢复原文件，结束时再核对清单里的每个文件与开始时逐字节相同。
 */
async function mutateTree(args: MutateArgs, treeArg: string, out: PyOut, sessions: SessionFactory): Promise<number> {
  if (args.run_dir) throw new DispatchError("--tree 与 run_dir 二选一：对 attempt 用 run_dir，对草稿树用 --tree", EXIT_USAGE);
  const tree = pyResolve(purePathStr(treeArg));
  if (!isDirectory(tree)) throw new DispatchError(`--tree 不是目录：${tree}`, EXIT_USAGE);
  const spec = loadValidSpec(args.spec, out);
  if (args.check_anchors) return checkAnchors(tree, spec, out);
  const warnings = printWarnings(spec, out);
  // 找不到仓库或配置写错都按没有配置跑（Repo.discover 成功、config() 报错时，决策会话照样用这个仓库的 .agent）
  let repoOfTree: Repo | null = null;
  let config: PyDict;
  try {
    repoOfTree = Repo.discover(args.repo);
    config = repoConfig(repoOfTree);
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    config = new Map();
  }
  const [env] = childEnv(config);
  const grace = graceOf(config);
  const outDir = treeOutDir(args.out, tree);
  copyfile(args.spec, path.join(outDir, "spec.json"));
  const before = new Map<string, Buffer>();
  for (const item of spec.mutations) {
    const name = item.get("file") as string;
    const file = purePathStr(tree, name);
    if (!before.has(name) && isFile(file) && isWithin(pyResolve(file), tree)) before.set(name, pyReadBytes(file));
  }
  const started = utcNow();
  const session = sessions(config, repoOfTree === null ? null : repoOfTree.agentDir, path.join(outDir, DECISIONS_RECORD), "mutation-equivalence");
  const [baseline, results] = await runMutationRounds(spec, tree, outDir, env, grace, "", session, out);
  const left = [...before].filter(([name, data]) => !pyReadBytes(purePathStr(tree, name)).equals(data)).map(([name]) => name);
  const recordPath = path.join(outDir, "mutations.json");
  if (!pyTruthy(baseline.get("passed") ?? null)) {
    writeJson(recordPath, new Map<string, PyValue>([["aborted", "baseline_failed"], ["baseline", baseline], ["tree", tree], ["at", utcNow()]]), true);
    throw new DispatchError(`不做变异时 command 没有通过（${reasonOf(baseline)}），变异结果没有意义；先让它在这棵树上通过 · 记录 ${recordPath}`);
  }
  for (const record of results) {
    const runs = record.get("commands");
    for (const run of [record, ...(runs instanceof Map ? [...runs.values()] : [])] as PyDict[]) {
      const log = run.get("log") ?? null;
      if (pyTruthy(log)) run.set("log", (log as string).split("/").pop() as string);
    }
  }
  const first = spec.commands[0] as MutationCommand;
  const payload = new Map<string, PyValue>([
    ["tree", tree], ["started_at", started], ["ended_at", utcNow()], ["spec_sha256", sha256File(path.join(outDir, "spec.json"))],
    ["command", first.argv], ["cwd", first.cwd], ["commands", commandsValue(spec)], ["files_left_modified", left],
    ["baseline", baseline], ["counts", mutationCounts(results, firstIdIfMulti(spec))], ["counts_by_command", mutationCountsByCommand(results, spec)],
    ["not_run", mutationsNotRun(spec, results)], ["warnings", warnings], ["results", results], ["decisions", decisionsPayload(session)],
  ]);
  writeJson(recordPath, payload, true);
  printMutationTotals(results, spec, recordPath, out);
  printMutationDecisions(session, path.join(outDir, DECISIONS_RECORD), out);
  if (left.length) out.print(`WARN  变异后文件没有恢复原样：${left.slice(0, 10).join(", ")}`);
  return (payload.get("not_run") as string[]).length ? EXIT_FAIL : EXIT_OK;
}

/** --out 给了就用它（不能在树里、不能已有内容）；没给就在系统临时目录下新建 pi-mutate-tree-XXXXXXXX。 */
function treeOutDir(outArg: string | null, tree: string): string {
  if (!outArg) return pyResolve(pyMkdtemp("pi-mutate-tree-", pyGettempdir()));
  const outDir = pyResolve(purePathStr(outArg));
  if (isWithin(outDir, tree)) throw new DispatchError(`--out 不能在被变异的树里面：${outDir}`, EXIT_USAGE);
  // 是文件时 iterdir 照 Python 报错（NotADirectoryError）
  if (exists(outDir) && readdirSync(outDir).length) throw new DispatchError(`--out 目录已有内容：${outDir}`, EXIT_USAGE);
  pathMkdir(outDir, true, true);
  return outDir;
}

function loadValidSpec(file: string, out: PyOut): MutationSpec {
  const [spec, problems] = loadMutationSpec(file);
  if (spec === null) {
    for (const problem of problems) out.print(`ERROR ${problem}`);
    throw new DispatchError(`变异清单无效：${problems.length} 个问题`, EXIT_USAGE);
  }
  return spec;
}

function printWarnings(spec: MutationSpec, out: PyOut): string[] {
  const warnings = mutationSpecWarnings(spec);
  for (const warning of warnings) out.print(`WARN  ${warning}`);
  return warnings;
}

/** baseline.get("reason") or baseline.get("status")。 */
const reasonOf = (record: PyDict): string => pyStrValue((pyTruthy(record.get("reason") ?? null) ? record.get("reason") : record.get("status")) ?? null);
const firstIdIfMulti = (spec: MutationSpec): string | null => (spec.commands.length > 1 ? (spec.commands[0] as MutationCommand).id : null);
const commandsValue = (spec: MutationSpec): PyDict[] => spec.commands.map((command) => new Map<string, PyValue>([
  ["id", command.id], ["argv", command.argv], ["cwd", command.cwd], ["timeout_seconds", command.timeout_seconds],
]));

function exists(file: string): boolean {
  try {
    statSync(file);
    return true;
  } catch {
    return false;
  }
}

// --- 变异轮次 -------------------------------------------------------------------

const BS = String.fromCharCode(92);
/** pytest 被 KeyboardInterrupt 打断整个会话时日志里的横幅。 */
const SESSION_ABORTED_RE = compilePy(`!{3,}${BS}s*KeyboardInterrupt${BS}s*!{3,}`);
const STATUSES = ["caught", "missed", "skipped", "error"] as const;

/** _mutation_expected：标了等价或列进 expect_missed 的预期漏掉，其余预期抓住。 */
function mutationExpected(item: PyDict, commandId: string): string {
  const expectMissed = item.get("expect_missed") ?? null;
  return pyTruthy(item.get("equivalent") ?? null) || (Array.isArray(expectMissed) && expectMissed.includes(commandId)) ? "missed" : "caught";
}

const specHasExpectations = (spec: MutationSpec): boolean =>
  spec.mutations.some((item) => pyTruthy(item.get("equivalent") ?? null) || pyTruthy(item.get("expect_missed") ?? null));

/**
 * _apply_mutation：old 恰好出现 count 次时把它全部换成 new 写回，交回（原始字节, 实际出现次数），调用方用原始字节恢复。
 * 文件是 CRLF 时先按 LF 比对、写回时换回 CRLF；old、new 里的 CRLF 也先换成 LF。文件不是 UTF-8 时抛 PyUnicodeDecodeError。
 * 与 Python 一样先编码再写：new 里有孤立代理项时报 UnicodeEncodeError，文件不动。
 */
function applyMutation(file: string, old: string, replacement: string, count: bigint): [Buffer, number] {
  const original = pyReadBytes(file);
  const text = pyDecodeUtf8(original);
  const usesCrlf = text.includes(CRLF);
  const normalized = usesCrlf ? text.replaceAll(CRLF, LF) : text;
  const [from, to] = [old.replaceAll(CRLF, LF), replacement.replaceAll(CRLF, LF)];
  const found = pyStrCount(normalized, from);
  if (BigInt(found) === count) {
    const mutated = pyStrReplace(normalized, from, to);
    writeFileSync(file, encodeUtf8(usesCrlf ? mutated.replaceAll(LF, CRLF) : mutated));
  }
  return [original, found];
}

/** _session_aborted：pytest 被 KeyboardInterrupt 打断整个会话，退出码 2，日志里有横幅。 */
function sessionAborted(logPath: string, run: PyDict): boolean {
  if (run.get("exit_code") !== 2n) return false;
  let text: string;
  try {
    text = pyReadTextReplace(logPath);
  } catch (error) {
    if (error instanceof PyOSError) return false;
    throw error;
  }
  return SESSION_ABORTED_RE.search(text) !== null;
}

/**
 * _run_mutation_rounds：先不做变异把每条命令各跑一次，再逐个套用变异、依次跑每条命令、恢复；交回（基线记录, 结果列表）。
 * 基线没有通过时结果列表为空，调用方决定怎么报告。多条命令时日志名带命令 id，第一条命令的结果同时留在记录顶层；
 * 意外漏掉的变异问一次决策模型（session 不为 null 时），判定与计数与它无关。
 */
async function runMutationRounds(
  spec: MutationSpec, workspace: string, outDir: string, env: ReadonlyMap<string, string>, grace: number, logPrefix: string,
  session: DecisionSession | null, out: PyOut,
): Promise<[PyDict, PyDict[]]> {
  const commands = spec.commands;
  const multi = commands.length > 1;
  const labelled = multi || specHasExpectations(spec);
  const runId = (base: string, command: MutationCommand): string => (multi ? `${base}-${command.id}` : base);
  const itemFor = (command: MutationCommand, rid: string): PyDict => new Map<string, PyValue>([
    ["id", rid], ["argv", command.argv], ["cwd", command.cwd], ["timeout_seconds", command.timeout_seconds], ["expected_exit_code", 0n],
  ]);
  const results: PyDict[] = [];
  out.print("MUTATE baseline ...", { flush: true });
  const baselineRuns = new Map<string, PyDict>();
  for (const command of commands) {
    const run = await runCommandItem(itemFor(command, runId("baseline", command)), workspace, env, outDir, grace);
    baselineRuns.set(command.id, run);
    if (!pyTruthy(run.get("passed") ?? null)) break;
  }
  const failed = [...baselineRuns].find(([, run]) => !pyTruthy(run.get("passed") ?? null))?.[0] ?? null;
  const baseline: PyDict = new Map(baselineRuns.get(failed ?? (commands[commands.length - 1] as MutationCommand).id));
  if (multi) {
    baseline.set("commands", baselineRuns);
    if (failed !== null) baseline.set("failed_command", failed).set("reason", `命令 ${failed}：${reasonOf(baseline)}`);
  }
  if (failed !== null) return [baseline, results];
  for (const [index0, item] of spec.mutations.entries()) {
    const mid = `M${String(index0 + 1).padStart(2, "0")}`;
    const count = item.has("count") ? (item.get("count") as bigint) : 1n;
    const record: PyDict = new Map<string, PyValue>([
      ["id", mid], ["name", item.get("name") as PyValue], ["file", item.get("file") as PyValue], ["count_expected", count], ["insertion_only", insertionOnly(item)],
    ]);
    for (const key of ["equivalent", "expect_missed"]) if (pyTruthy(item.get(key) ?? null)) record.set(key, item.get(key) as PyValue);
    const runs = new Map<string, PyDict>();
    let original: Buffer = Buffer.alloc(0);
    const file = purePathStr(workspace, item.get("file") as string);
    if (!isFile(file) || !isWithin(pyResolve(file), workspace)) {
      record.set("status", "skipped").set("reason", "文件不存在或位于工作副本之外");
    } else {
      let found: number | null = null;
      try {
        [original, found] = applyMutation(file, item.get("old") as string, item.get("new") as string, count);
      } catch (error) {
        if (!(error instanceof PyUnicodeDecodeError)) throw error;
        record.set("status", "skipped").set("reason", "文件不是 UTF-8 文本");
      }
      if (found !== null) {
        record.set("count_found", BigInt(found));
        if (BigInt(found) !== count) {
          record.set("status", "skipped").set("reason", `old 出现 ${found} 次，期望 ${count} 次`);
        } else {
          try {
            for (const command of commands) {
              const rid = runId(mid, command);
              const run = await runCommandItem(itemFor(command, rid), workspace, env, outDir, grace);
              const outcome = mutationOutcome(run, path.join(outDir, `${rid}.log`));
              runs.set(command.id, outcome);
              if (outcome.get("interrupted") === true) break;
            }
          } finally {
            writeFileSync(file, original);
          }
        }
      }
    }
    if (runs.size) {
      const firstRun = runs.get((commands[0] as MutationCommand).id) as PyDict;
      for (const key of ["status", "exit_code", "timed_out", "log", "reason"]) record.set(key, firstRun.get(key) as PyValue);
      if (multi) record.set("commands", runs);
    }
    const statuses = runs.size
      ? new Map([...runs].map(([cid, run]) => [cid, run.get("status") as string]))
      : new Map(commands.map((command) => [command.id, record.get("status") as string]));
    const unexpected = [...statuses].filter(([cid, status]) => (status === "caught" || status === "missed") && status !== mutationExpected(item, cid)).map(([cid]) => cid);
    record.set("unexpected", unexpected);
    if (session !== null && unexpected.some((cid) => statuses.get(cid) === "missed")) record.set("decision", await decideMutation(session, item, original, spec, mid));
    results.push(record);
    printMutationRecord(record, item, spec, runs, multi, labelled, logPrefix, session, out);
    if ([...runs.values()].some((run) => run.get("interrupted") === true)) {
      // 文件已在上面恢复；没跑的变异由调用方记进 not_run
      out.print(`MUTATE 被中断：后面 ${spec.mutations.length - index0 - 1} 条变异没有运行`, { flush: true });
      break;
    }
  }
  return [baseline, results];
}

/** _mutations_not_run：运行被中断时清单里没有轮到的变异（名称）；跑完时为空。 */
const mutationsNotRun = (spec: MutationSpec, results: readonly PyDict[]): string[] =>
  spec.mutations.slice(results.length).map((item) => item.get("name") as string);

/** _mutation_outcome：只有退出码非 0 或超时算抓住；被拦下的命令、被中断的运行与中断的测试会话是出错。 */
function mutationOutcome(run: PyDict, logPath: string): PyDict {
  let status: string;
  let source = run;
  if (run.get("status") === "blocked") {
    status = "error";
  } else if (pyTruthy(run.get("interrupted") ?? null)) {
    // 收到了 Ctrl+C、关闭控制台或控制台的 CTRL_BREAK：测试没有跑完，退出码不说明任何事
    status = "error";
    source = new Map(run).set("reason", "命令被中断（Ctrl+C、关闭控制台或控制台的 CTRL_BREAK），测试没有跑完，不算抓住；后面的变异不再运行");
  } else if (!pyTruthy(run.get("passed") ?? null) && sessionAborted(logPath, run)) {
    status = "error";
    source = new Map(run).set("reason", "测试会话被 KeyboardInterrupt 中断（退出码 2），后面的用例没有运行，不算抓住；让测试拦住冒出的中断后重跑");
  } else {
    status = pyTruthy(run.get("passed") ?? null) ? "missed" : "caught";
  }
  return new Map<string, PyValue>([
    ["status", status], ["exit_code", source.get("exit_code") ?? null], ["timed_out", pyTruthy(source.get("timed_out") ?? null)],
    ["interrupted", pyTruthy(source.get("interrupted") ?? null)], ["log", source.get("log") ?? null],
    ["reason", pyTruthy(source.get("reason") ?? null) ? (source.get("reason") as PyValue) : ""],
  ]);
}

/**
 * _print_mutation_record：单命令、没有预期标注的清单一条一行；否则每条命令一行，带 [命令] 与预期。日志按清单位置编号（M01…）；
 * --tree 模式（log_prefix 为空）只写日志文件名，attempt 模式写 mutations/NN/Mxx.log。
 */
function printMutationRecord(
  record: PyDict, item: PyDict, spec: MutationSpec, runs: ReadonlyMap<string, PyDict>, multi: boolean, labelled: boolean, logPrefix: string,
  session: DecisionSession | null, out: PyOut,
): void {
  const shownLog = (log: PyValue): string => {
    if (!pyTruthy(log)) return "";
    const text = log as string;
    return `日志 ${logPrefix ? logPrefix + text : (text.split("/").pop() as string)}`;
  };
  const note = decisionNote((record.get("decision") ?? null) as PyDict | null, session);
  const unexpected = record.get("unexpected") as string[];
  const ordered = spec.commands.filter((command) => runs.has(command.id)).map((command) => [command.id, runs.get(command.id) as PyDict] as const);
  const rows: (readonly [string | null, PyDict])[] = ordered.length ? ordered : [[null, record]];
  for (const [cid, run] of rows) {
    const status = run.get("status") as string;
    let expectation = "";
    if (labelled && cid !== null && (status === "caught" || status === "missed")) {
      const expected = mutationExpected(item, cid);
      if (status === "missed" && expected === "missed") {
        expectation = pyTruthy(item.get("equivalent") ?? null) ? `预期内：等价（${pyStrValue(item.get("equivalent") as PyValue)}）` : "预期内（expect_missed）";
      } else if (status === "missed") {
        expectation = "意外漏掉";
      } else if (expected === "missed") {
        expectation = "意外：标了预期漏掉，却被抓住";
      }
    }
    const detail = [
      pyTruthy(run.get("reason") ?? null) ? pyStrValue(run.get("reason") as PyValue) : "",
      expectation,
      record.get("insertion_only") === true ? "只插入代码" : "",
      shownLog(run.get("log") ?? null),
      status === "missed" && (cid === null || unexpected.includes(cid)) ? note : "",
    ].filter((part) => part);
    const tag = multi && cid !== null ? ` [${cid}]` : "";
    out.print(`${status.toUpperCase().padEnd(7)} ${record.get("id") as string} ${pyStrValue(item.get("name") as PyValue)}${tag}${detail.map((part) => `  ${part}`).join("")}`, { flush: true });
  }
}

/** _mutation_counts：给了 command_id 时按那条命令的结果计（多命令清单），跳过的变异对每条命令都算跳过。 */
function mutationCounts(results: readonly PyDict[], commandId: string | null): Map<string, bigint> {
  const statusOf = (record: PyDict): PyValue => {
    const runs = record.get("commands");
    if (commandId !== null && runs instanceof Map && runs.has(commandId)) return pyItem(runs.get(commandId) as PyValue, "status");
    return record.get("status") as PyValue;
  };
  return new Map(STATUSES.map((status) => [status, BigInt(results.filter((record) => statusOf(record) === status).length)]));
}

/** _mutation_counts_by_command：每条命令的计数，加上预期内与意外的条目。 */
function mutationCountsByCommand(results: readonly PyDict[], spec: MutationSpec): Map<string, PyDict> {
  const byCommand = new Map<string, PyDict>();
  const multi = spec.commands.length > 1;
  for (const { id: cid } of spec.commands) {
    const counts: PyDict = new Map<string, PyValue>(mutationCounts(results, multi ? cid : null));
    const runOf = (record: PyDict): PyDict => {
      const runs = record.get("commands");
      return (runs instanceof Map && runs.has(cid) ? runs.get(cid) : record) as PyDict;
    };
    const flagged = (status: string): string[] => results
      .filter((record) => (record.get("unexpected") as string[]).includes(cid) && runOf(record).get("status") === status)
      .map((record) => record.get("id") as string);
    const unexpectedMissed = flagged("missed");
    counts.set("unexpected_missed", unexpectedMissed).set("unexpected_caught", flagged("caught"))
      .set("expected_missed", (counts.get("missed") as bigint) - BigInt(unexpectedMissed.length));
    byCommand.set(cid, counts);
  }
  return byCommand;
}

const MISSED_ADVICE = "漏掉的变异说明没有测试覆盖对应规则：合同测试清单遗漏的，由规划端补测试并单独提交；执行器少写的，记入复审（必要时 REVISE）。";

/** _print_mutation_totals：没有标注的单命令清单一行计数；否则每条命令一行，带预期内与意外的条目。 */
function printMutationTotals(results: readonly PyDict[], spec: MutationSpec, recordPath: string, out: PyOut): void {
  const notRun = mutationsNotRun(spec, results);
  if (notRun.length) out.print(`变异清单 ${spec.mutations.length} 条，运行被中断，只跑了 ${results.length} 条，下面的计数不完整；没有运行：${notRun.join("、")}`);
  const byCommand = mutationCountsByCommand(results, spec);
  const multi = spec.commands.length > 1;
  const n = (counts: PyDict, key: string): string => String(counts.get(key) as bigint);
  if (!multi && !specHasExpectations(spec)) {
    const counts = byCommand.get((spec.commands[0] as MutationCommand).id) as PyDict;
    out.print(`变异 ${results.length} 个：抓住 ${n(counts, "caught")}，漏掉 ${n(counts, "missed")}，跳过 ${n(counts, "skipped")}，出错 ${n(counts, "error")} · ${recordPath}`);
    if (counts.get("missed") !== 0n) out.print(MISSED_ADVICE);
    return;
  }
  for (const [cid, counts] of byCommand) {
    const unexpected = counts.get("unexpected_missed") as string[];
    const surprise = counts.get("unexpected_caught") as string[];
    out.print(`变异 ${results.length} 个${multi ? ` · ${cid}` : ""}：抓住 ${n(counts, "caught")}，漏掉 ${n(counts, "missed")}（预期 ${n(counts, "expected_missed")}，` +
      `意外 ${unexpected.length}${unexpected.length ? `：${unexpected.join(" ")}` : ""}），跳过 ${n(counts, "skipped")}，出错 ${n(counts, "error")}` +
      `${surprise.length ? `；标了预期漏掉却被抓住 ${surprise.length}：${surprise.join(" ")}` : ""}`);
  }
  out.print(`记录：${recordPath}`);
  if ([...byCommand.values()].some((counts) => (counts.get("unexpected_missed") as string[]).length)) out.print(`意外${MISSED_ADVICE}预期内的不用再判。`);
  if ([...byCommand.values()].some((counts) => (counts.get("unexpected_caught") as string[]).length)) {
    out.print("标了预期漏掉却被抓住：等价判断或“留给 oracle”的划分不对，复审记录里更正。");
  }
}

// --- 决策点 mutation-equivalence -----------------------------------------------

/** _decide_mutation：一条意外漏掉的变异，问“等价改写还是测试缺口”。state 是文件相对路径、old/new 与前后各 8 行。 */
async function decideMutation(session: DecisionSession, item: PyDict, original: Buffer, spec: MutationSpec, mid: string): Promise<PyDict> {
  let source = "";
  try {
    source = pyDecodeUtf8(original).replaceAll(CRLF, LF);
  } catch (error) {
    if (!(error instanceof PyUnicodeDecodeError)) throw error;
  }
  // 这里照 Python 用原样的 old：old 里带 CRLF 时找不到，上下文是空的
  const old = item.get("old") as string;
  const index = pyStrFind(source, old);
  let context = "";
  if (index >= 0) {
    const before = pySplitlines(source.slice(0, index)).slice(-8);
    const after = pySplitlines(source.slice(index + old.length)).slice(0, 8);
    context = `${before.join(LF)}${LF}[[MUTATION HERE]]${LF}${after.join(LF)}`;
  }
  const state = new Map<string, PyValue>([
    ["file", item.get("file") as PyValue],
    ["mutation", new Map<string, PyValue>([["name", item.get("name") as PyValue], ["old", old], ["new", item.get("new") as PyValue]])],
    ["context", cpSlice(context, 0, 4000)],
    ["test_command", spec.commands.map((command) => command.argv.map((part) => pyStrValue(part)).join(" ")).join(" ; ")],
  ]);
  return session.ask(equivalenceBattery(session), state, new Map<string, PyValue>([["mutation", mid], ["name", item.get("name") as PyValue]]));
}

function equivalenceBattery(session: DecisionSession): AssessBattery {
  const battery = session.batteries.get("mutation-equivalence");
  if (battery === undefined) throw new PyCrash("KeyError", "'mutation-equivalence'");
  return battery;
}

/** _mutation_decision_note：on 模式下结果行的后缀；shadow 只记录不显示。 */
function decisionNote(decision: PyDict | null, session: DecisionSession | null): string {
  if (decision === null || session === null || session.mode !== "on" || decision.get("status") !== "answered") return "";
  const hint = pyFloatOf(equivalenceBattery(session).thresholds.get("hint") ?? 0.7);
  const answers = pyItem(decision, "answers");
  const equivalent = pyFloatOf(pyItem(pyItem(answers, "equivalent"), "noul"));
  const untested = pyFloatOf(pyItem(pyItem(answers, "untested"), "noul"));
  if (equivalent >= hint) return `决策：可能等价 p=${pyFixed(equivalent, 2)}`;
  if (untested >= hint) return `决策：可能是测试缺口 p=${pyFixed(untested, 2)}`;
  return `决策：等价 p=${pyFixed(equivalent, 2)} · 缺口 p=${pyFixed(untested, 2)}`;
}

/** _mutation_decisions_payload：模式、模型与调用汇总；没有会话时为 null。 */
function decisionsPayload(session: DecisionSession | null): PyValue {
  if (session === null) return null;
  const payload: PyDict = new Map<string, PyValue>([["mode", session.mode], ["model", session.settings.model]]);
  for (const [key, value] of usageTotals(session.records)) payload.set(key, value);
  return payload;
}

function printMutationDecisions(session: DecisionSession | null, recordPath: string, out: PyOut): void {
  if (session === null) return;
  const totals = decisionsPayload(session) as PyDict;
  out.print(`决策（mutation-equivalence, ${session.mode}）：${pyStrValue(totals.get("calls") ?? 0n)} 次调用，${pyStrValue(totals.get("answered") ?? 0n)} 次有答案 · 记录 ${recordPath}`);
}

function isDirectory(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}
