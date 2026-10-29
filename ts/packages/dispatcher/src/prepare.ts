// pi_dispatch prepare（迁移第 ④b7a 片）：budget_usage、allocate_attempt、pending_attempt_notes 与 cmd_prepare。
// 合同校验通过之后冻结合同对的字节、按合同版本发布执行模型记录、建 worktree、跑 setup；任何一步出错都把 attempt 标成
// PREPARE_FAILED。run（④b7b）复用 budgetUsage 与 allocateAttempt。
import { readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyFixed, pyFloatOf, pyGet, pyItem, pyRound, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, pyDecodeUtf8, pyDecodeUtf8Replace, pyOSErrorType, pyReadBytes } from "@themis/base/pyio";
import { type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { PyWinError, isFileExists, pathMkdir } from "@themis/base/pyos";
import { displayPath, normCase, purePathStr, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyIntParse, pyStrip } from "@themis/base/pyre";
import { strictJsonLoads } from "@themis/base/protocols";
import { pyMkdtemp } from "@themis/base/pytempfile";
import { pyEq } from "@themis/base/pyvalue";
import { runSetup, worktreeRoot } from "./command-runner.ts";
import { type PlanContext, jsonParseError, planKeyFromArg, printMessages, validatePlan, verifyPlannerPublication } from "./contract-plan.ts";
import { validateContract } from "./contract.ts";
import { readJson, setState, sha256File, writeJson } from "./evidence.ts";
import { BindingRecordError, EXIT_DRIFT, bindingRecordRel, executorClass } from "./executor.ts";
import {
  type BindingRoles, bindingDriftNote, publishBindingRecord, resolveBoundExecutor, resolveExecutor, roleBindingCandidate, writtenBindingNote,
} from "./executor-resolve.ts";
import { effectiveAutocrlf } from "./gitops.ts";
import { configWithBytes, extraProtectedPaths, kernelProtectedPaths, repoConfig } from "./kernel-config.ts";
import { DispatchError, EXIT_BLOCKED, EXIT_FAIL, EXIT_OK, EXIT_USAGE, Repo, git, gitChecked, readJsonOr } from "./repo.ts";
import { ATTEMPT_DIR_RE, getState, taskAttempts } from "./status.ts";

/** pi_dispatch.TOOL_VERSION：写进 meta.json；切换那一轮再与常量表逐项对照。 */
export const TOOL_VERSION = "2.12.0";

export const PENDING_INTEGRATION_STATES = ["PREPARING", "PREPARED", "RUNNING", "COLLECTING", "NEEDS_REVIEW", "PASS", "ACCEPTED_WITH_EXCEPTION", "REVISE"];
const EXECUTOR_STYLE: Readonly<Record<string, string>> = { role: "按角色", written: "写死", legacy: "旧" };

export interface PrepareArgs {
  readonly repo: string | null;
  readonly plan_key: string;
}

/** prepare 的 context：PlanContext 的 kit_roles 多用两个函数，另有本机的 platform.platform() 与 Python 版本（迁移计划 D1）。 */
export interface PrepareContext extends PlanContext {
  readonly roles: BindingRoles | null;
  readonly platform: string;
  readonly python: string;
}

/** decisions_session(config, agent_dir, None, strict=True)：配置写错或问题清单与内容锁不符时抛 DispatchError，结果不用。 */
export type StrictDecisionsCheck = (config: PyDict, agentDir: string) => void;

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

/** budget_usage：领取过的 attempt 数与累计用时；还没有 run.json（仍在运行或调度器中途退出）的按预留的时限计入。 */
export function budgetUsage(repo: Repo, taskId: string, exclude: string | null = null): { attempts_started: number; wall_seconds_used: number } {
  let started = 0;
  let wall = 0;
  for (const attempt of taskAttempts(repo, taskId)) {
    if (exclude !== null && normCase(attempt) === normCase(exclude)) continue;
    if (!isDir(path.join(attempt, "claim"))) continue;
    started += 1;
    const run = readJsonOr(path.join(attempt, "run.json"), null);
    if (run !== null && pyGet(run, "wall_seconds") !== null) {
      wall += pyFloatOf(pyItem(run, "wall_seconds"));
    } else {
      const reserved = pyGet(readJsonOr(path.join(attempt, "claim", "reservation.json"), new Map()), "timeout_seconds");
      wall += pyFloatOf(pyTruthy(reserved) ? reserved : 0n);
    }
  }
  return { attempts_started: started, wall_seconds_used: pyRound(wall, 3) as number };
}

/** allocate_attempt：编号是已有 attempt-NNN 里最大的加一；目录被别人抢先建了就往后挪。 */
export function allocateAttempt(repo: Repo, taskId: string): [string, bigint] {
  const base = path.join(repo.runsDir, taskId);
  pathMkdir(base, true, true);
  let number = 0n;
  for (const name of readdirSync(base)) {
    const match = ATTEMPT_DIR_RE.exec(name);
    if (match === null || !isDir(path.join(base, name))) continue;
    const value = pyIntParse(match.groups?.["n"] ?? "") as bigint;
    if (value > number) number = value;
  }
  number += 1n;
  for (let tries = 0; tries < 1000; tries += 1) {
    const candidate = path.join(base, `attempt-${String(number).padStart(3, "0")}`);
    try {
      pathMkdir(candidate, false, false);
      return [candidate, number];
    } catch (error) {
      if (!isFileExists(error)) throw error;
      number += 1n;
    }
  }
  throw new DispatchError("无法分配 attempt 目录");
}

/** _scope_files：合同 scope 里三张清单的全部路径。 */
function scopeFiles(contract: PyValue): Set<string> {
  const scope = isDict(contract) && isDict(contract.get("scope")) ? (contract.get("scope") as PyDict) : new Map<string, PyValue>();
  const files = new Set<string>();
  for (const key of ["allowed_modified_files", "allowed_new_files", "allowed_deleted_files"]) {
    const values = scope.get(key) ?? [];
    if (Array.isArray(values)) for (const value of values) if (typeof value === "string") files.add(value);
  }
  return files;
}

/**
 * pending_attempt_notes：并行派遣的提示，返回（警告, 提示）。警告：其他任务最新的 attempt 尚未集成、改动范围又与本合同重叠；
 * 提示：正在运行的 attempt。
 */
export function pendingAttemptNotes(repo: Repo, contract: PyDict): [string[], string[]] {
  const mine = scopeFiles(contract);
  const warnings: string[] = [];
  const running: string[] = [];
  const tasks = isDir(repo.runsDir) ? readdirSync(repo.runsDir).filter((name) => isDir(path.join(repo.runsDir, name))).sort(cmpCodePoints) : [];
  for (const task of tasks) {
    const attempts = taskAttempts(repo, task);
    for (const attempt of attempts) if (getState(attempt) === "RUNNING") running.push(displayPath(attempt, repo.runsDir));
    if (pyEq(task, contract.get("task_id") ?? null) || !attempts.length) continue;
    const latest = attempts[attempts.length - 1] as string;
    const state = getState(latest);
    if (!PENDING_INTEGRATION_STATES.includes(state)) continue;
    const others = scopeFiles(readJsonOr(path.join(latest, "contract.json"), new Map()));
    const overlap = [...mine].filter((file) => others.has(file)).sort(cmpCodePoints);
    if (overlap.length) {
      warnings.push(`与未集成的 ${displayPath(latest, repo.runsDir)}（${state}）改动范围重叠：${overlap.slice(0, 10).join("、")}；并行派遣时后集成的一方需要合并或返工`);
    }
  }
  const notes: string[] = [];
  if (running.length) notes.push(`有 ${running.length} 个 attempt 正在运行（${running.slice(0, 5).join("、")}）：它们结束前不要合并、提交或改动规划路径之外的主工作区文件`);
  return [warnings, notes];
}

/** type(exc).__name__。 */
function exceptionName(error: unknown): string {
  if (error instanceof BindingRecordError) return "BindingRecordError";
  if (error instanceof DispatchError) return "DispatchError";
  if (error instanceof PyOSError) return pyOSErrorType(error);
  if (error instanceof PyCrash) return error.kind;
  return (error as Error).name;
}

/** 固定合同字节的 JSON：planner-v2 的合同再用严格解码器解同一份字节。 */
function frozenRawOf(frozenJson: Buffer): PyValue {
  try {
    const raw = loads(pyDecodeUtf8(frozenJson));
    return isDict(raw) && pyEq(raw.get("contract_family") ?? null, "planner-v2") ? strictJsonLoads(frozenJson) : raw;
  } catch (error) {
    if (jsonParseError(error)) throw new DispatchError(`固定合同字节无法解析：${(error as Error).message}`, EXIT_USAGE);
    throw error;
  }
}

/** freezeAndSetUp 的结果：worktree、失败的 setup 项（失败就停，最多一项）与 setup 之后 worktree 的未提交改动。 */
interface Prepared {
  readonly worktree: string;
  readonly failed: PyDict[];
  readonly dirty: string;
}

export async function cmdPrepare(args: PrepareArgs, out: PyOut, ctx: PrepareContext, checkDecisions: StrictDecisionsCheck): Promise<number> {
  const repo = Repo.discover(args.repo);
  const planKey = planKeyFromArg(repo, args.plan_key);
  const [contract, errors, validated] = validatePlan(repo, planKey, ctx);
  let warnings = validated;
  if (contract !== null) {
    const [overlapWarnings, runningNotes] = pendingAttemptNotes(repo, contract);
    warnings = [...warnings, ...overlapWarnings];
    for (const note of runningNotes) out.print(`NOTE  ${note}`);
  }
  printMessages(out, errors, warnings);
  if (errors.length || contract === null) throw new DispatchError("合同校验失败，未创建 attempt。", EXIT_USAGE);
  if (git(["check-ignore", "-q", ".agent/runs/probe"], repo.root).status !== 0) {
    throw new DispatchError("请先把 .agent/runs/ 加入 .gitignore：运行证据含源码与日志，不应进入提交。", EXIT_BLOCKED);
  }
  // 只读一次配置字节：按角色写的合同用同一份字节解析绑定、记哈希
  const [config, configBytes] = configWithBytes(repo);
  checkDecisions(config, repo.agentDir);
  const mdPath = path.join(repo.plansDir, `${planKey}.md`);
  const jsonPath = path.join(repo.plansDir, `${planKey}.json`);
  const rawExecutor = pyGet(readJson(jsonPath), "executor", new Map());
  const taskId = contract.get("task_id") as string;
  const version = contract.get("plan_version") as bigint;
  const base = contract.get("base_sha") as string;
  const preClass = executorClass(rawExecutor);
  let bindingNote: PyDict | null = null;
  if (preClass === "written") {
    bindingNote = writtenBindingNote(config, resolveExecutor(new Map(contract).set("_raw_executor", rawExecutor), config), ctx.roles, out);
  } else if (preClass === "role") { // 分配 attempt 之前预检，失败不留 attempt
    const role = (rawExecutor as PyDict).get("role") as string;
    const [candidate, existed] = roleBindingCandidate(repo, role, config, taskId, version, ctx.roles);
    resolveBoundExecutor(contract, candidate, config);
    const drift = existed ? bindingDriftNote(config, role, candidate, ctx.roles) : null;
    if (drift) out.print(`NOTE  ${drift}`);
  }
  checkBudget(repo, taskId, contract.get("budget") as PyDict);
  const root = worktreeRoot(repo, config);
  pathMkdir(root, true, true);
  const [runDir, number] = allocateAttempt(repo, taskId);
  const attemptId = `${taskId}.v${version}.a${String(number).padStart(3, "0")}`;
  let prepared: Prepared;
  try {
    prepared = await freezeAndSetUp(repo, planKey, contract, config, configBytes, ctx, {
      mdPath, jsonPath, runDir, root, number, attemptId, preClass, bindingNote,
    });
  } catch (error) {
    setState(runDir, "PREPARE_FAILED", [["reason", `${exceptionName(error)}: ${(error as Error).message}`]]);
    if (error instanceof BindingRecordError) throw new BindingRecordError(`prepare 失败（${attemptId} 已标记 PREPARE_FAILED）：${error.message}`, error.code);
    if (error instanceof DispatchError || error instanceof PyOSError || error instanceof PyWinError) {
      throw new DispatchError(`prepare 失败（${attemptId} 已标记 PREPARE_FAILED）：${error.message}`);
    }
    throw error;
  }
  const { worktree, failed, dirty } = prepared;
  const first = failed[0];
  if (first !== undefined) {
    setState(runDir, "PREPARE_FAILED", [["reason", `setup ${pyStrValue(first.get("id") ?? null)} 失败：${pyStrValue(first.get("reason") ?? null)}`]]);
    out.print(`setup 失败：${pyStrValue(first.get("id") ?? null)}（日志 ${displayPath(path.join(runDir, first.get("log") as string), repo.root)}）。修正后重新 prepare；本 attempt 未领取，不计入尝试次数。`);
    return EXIT_FAIL;
  }
  if (dirty) {
    setState(runDir, "PREPARE_FAILED", [["reason", "setup 后 worktree 有未忽略的变更"]]);
    out.print(`setup 修改了受版本管理的文件或产生了未忽略的新文件：${String.fromCharCode(10)}${codePoints(dirty).slice(0, 2000).join("")}`);
    return EXIT_FAIL;
  }
  setState(runDir, "PREPARED");
  out.print(`PREPARED ${attemptId}`);
  out.print(`Run directory: ${runDir}`);
  out.print(`Worktree: ${worktree}`);
  if (!(contract.get("setup") as PyValue[]).length) {
    out.print("合同没有 setup。测试需要额外依赖时，按 dispatch-pi 技能出新版本合同补上 setup，再重新 prepare；不要在 worktree 里手工准备，否则 check --fresh 无法复现。");
  }
  out.print(`下一步（在后台运行）：bash scripts/dispatch-pi.sh run ${displayPath(runDir, repo.root)}`);
  return EXIT_OK;
}

function checkBudget(repo: Repo, taskId: string, budget: PyDict): void {
  const usage = budgetUsage(repo, taskId);
  const maxAttempts = budget.get("max_attempts_total") as bigint;
  const maxWall = budget.get("max_wall_seconds_total") as bigint;
  if (BigInt(usage.attempts_started) >= maxAttempts) {
    throw new DispatchError(`BUDGET_EXCEEDED：任务 ${taskId} 已运行 ${usage.attempts_started} 次，达到 max_attempts_total=${maxAttempts}。`);
  }
  if (usage.wall_seconds_used >= maxWall) {
    throw new DispatchError(`BUDGET_EXCEEDED：累计运行 ${pyFixed(usage.wall_seconds_used, 0)}s，达到 max_wall_seconds_total=${maxWall}。`);
  }
}

interface FreezeInputs {
  readonly mdPath: string;
  readonly jsonPath: string;
  readonly runDir: string;
  readonly root: string;
  readonly number: bigint;
  readonly attemptId: string;
  readonly preClass: string;
  readonly bindingNote: PyDict | null;
}

/**
 * 冻结校验过的合同对：只从同一次读到的字节写证据、算哈希，读了两次就可能把没一起审过的两份字节配成一对。内核的 TS 禁区
 * 每个 attempt 冻结一次，记进 meta.json。之后发布版本记录、建 worktree、跑 setup。
 */
async function freezeAndSetUp(
  repo: Repo, planKey: string, contract: PyDict, config: PyDict, configBytes: Buffer | null, ctx: PrepareContext, at: FreezeInputs,
): Promise<Prepared> {
  const { runDir, number } = at;
  const taskId = contract.get("task_id") as string;
  const version = contract.get("plan_version") as bigint;
  const frozenMd = pyReadBytes(at.mdPath);
  const frozenJson = pyReadBytes(at.jsonPath);
  const frozenRaw = frozenRawOf(frozenJson);
  const kernelProtected = kernelProtectedPaths(repo.root, ctx.kitRoot, ctx.kernelImpl);
  const [frozenContract, frozenErrors] = validateContract(pyDecodeUtf8(frozenMd), frozenRaw, planKey, [...extraProtectedPaths(repoConfig(repo)), ...kernelProtected]);
  if (frozenErrors.length || frozenContract === null) throw new DispatchError(`验证后的合同字节在冻结时发生变化：${frozenErrors.join("；")}`, EXIT_DRIFT);
  if (isDict(frozenRaw) && pyEq(frozenRaw.get("contract_family") ?? null, "planner-v2")) {
    const publicationErrors = verifyPlannerPublication(repo, planKey, frozenMd, frozenJson);
    if (publicationErrors.length) throw new DispatchError(`固定合同字节未通过 planner-v2 发布门禁：${publicationErrors.join("；")}`, EXIT_BLOCKED);
  }
  writeFileSync(path.join(runDir, "plan.md"), frozenMd);
  writeFileSync(path.join(runDir, "contract.json"), frozenJson);
  const frozenExecutor = isDict(frozenRaw) ? (frozenRaw.get("executor") ?? null) : null;
  const frozenClass = executorClass(frozenExecutor);
  if (frozenClass !== at.preClass && (frozenClass === "role" || at.preClass === "role")) {
    throw new BindingRecordError(`合同在校验之后被改过：executor 从${EXECUTOR_STYLE[at.preClass]}写法变成了${EXECUTOR_STYLE[frozenClass]}写法`, EXIT_DRIFT);
  }
  const bindingRecord = frozenClass === "role"
    ? publishBindingRecord(repo, (frozenExecutor as PyDict).get("role") as string, frozenJson, frozenContract, config, configBytes, taskId, version, number, ctx.roles)
    : null;
  // 唯一的空目录：不复用、不删除来历不明的旧目录（git 允许在空目录上建立 worktree）
  const prefix = `${codePoints(path.basename(repo.root)).slice(0, 16).join("")}-${taskId.slice(0, 24)}-a${String(number).padStart(3, "0")}-`;
  const worktree = pyResolve(purePathStr(pyMkdtemp(prefix, at.root)));
  const sourceStatus = gitChecked(["status", "--porcelain=v1", "-z"], repo.root).stdout;
  writeFileSync(path.join(runDir, "source-status.z"), sourceStatus);
  const meta = new Map<string, PyValue>([
    ["tool_version", TOOL_VERSION], ["impl", "ts"], ["task_id", taskId], ["plan_version", version], ["plan_key", planKey],
    ["kernel_protected", kernelProtected], ["attempt_no", number], ["attempt_id", at.attemptId], ["repository", repo.root], ["base_sha", contract.get("base_sha") as string],
    ["worktree", worktree], ["plan_md_sha256", sha256File(path.join(runDir, "plan.md"))], ["contract_json_sha256", sha256File(path.join(runDir, "contract.json"))],
    ["risk_level", contract.get("risk_level") as PyValue], ["source_worktree_dirty", sourceStatus.length > 0], ["created_at", utcNow()],
    ["platform", ctx.platform], ["python", ctx.python],
    // 行尾归一化配置：之后所有快照与补丁重建都沿用它，不受运行期间全局配置变化影响
    ["git_autocrlf", effectiveAutocrlf(repo.root)],
  ]);
  if (bindingRecord !== null) meta.set("executor_binding", new Map(bindingRecord).set("record_path", bindingRecordRel(taskId, version)));
  if (at.bindingNote !== null) meta.set("executor_binding_note", at.bindingNote);
  writeJson(path.join(runDir, "meta.json"), meta, true);
  setState(runDir, "PREPARING");
  gitChecked(["worktree", "add", "--detach", worktree, contract.get("base_sha") as string], repo.root);
  const setup = await runSetup(runDir, worktree, contract, config);
  if (setup.length) writeJson(path.join(runDir, "setup.json"), setup, true);
  const failed = setup.filter((item) => !pyTruthy(item.get("passed") ?? null));
  const dirty = failed.length ? "" : pyStrip(pyDecodeUtf8Replace(gitChecked(["status", "--porcelain=v1"], worktree).stdout));
  return { worktree, failed, dirty };
}
