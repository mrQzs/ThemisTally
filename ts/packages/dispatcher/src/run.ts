// run（迁移第 ④b7c2 片）：核对 attempt 与 worktree（G0），解析执行模型与 pi 的命令，预检与上下文取证；在任务锁里重新核算
// 预算、预留本轮时限并领取；写执行说明与运行前的证据，在 worktree 里运行 Pi（runSupervised），最后 collect。
//   - 能失败又不需要领取的准备都放在领取之前，避免留下“已领取却无法运行”的 attempt。
//   - 合同与执行说明从中性的临时目录（pi-attach-*）附上：附件名会原样出现在发给执行器的消息里，放在运行目录下会暴露主仓库
//     的绝对路径（KitExperiment 实机，2.3.0）。两份副本与运行目录里的文件逐字节相同，跑完删掉。
//   - 领取之后、启动之前出错：补一份 run.json（spawn_error），状态记 INFRA_FAILURE，错误照样抛出去。
import { rmSync, statSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyFixed, pyFloatOf, pyGet, pyItem, pyJoinStrings, pyPercentD, pyTruthy } from "@themis/base/pyfmt";
import { PyOSError, pyOSErrorType, pyReadBytes } from "@themis/base/pyio";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { isFileExists, pathMkdir } from "@themis/base/pyos";
import { pyExists, purePathParent, purePathStr } from "@themis/base/pypath";
import { pyGettempdir, pyMkdtemp } from "@themis/base/pytempfile";
import { runSupervised } from "@themis/base/supervise";
import { ensureArgvSafe } from "./argv.ts";
import { copyfile } from "./check-commands.ts";
import { attemptProtectedPaths, collect } from "./collect.ts";
import { supervisedRecord } from "./command-runner.ts";
import { verifyPlannerPublication } from "./contract-plan.ts";
import { loadAttempt, logEvent, setState, sha256File, writeJson, writeText } from "./evidence.ts";
import { resolvePiCommand } from "./executor.ts";
import { resolveBoundExecutor, resolveExecutor, withTaskLock } from "./executor-resolve.ts";
import { verifyInputs } from "./gates.ts";
import { ignoredInventory, mainRepoFingerprint } from "./gitops.ts";
import { measuredCheckSeconds, renderInstruction } from "./instruction.ts";
import { repoConfig } from "./kernel-config.ts";
import { frozenExecutorClass } from "./metrics.ts";
import { RESOURCE_FLAGS, childEnv, expectsSettled } from "./pi-cli.ts";
import { contextEvidence, piPreflight } from "./preflight.ts";
import { budgetUsage } from "./prepare.ts";
import { DispatchError, EXIT_FAIL, EXIT_OK, Repo, gitChecked, gitText, readJsonOr } from "./repo.ts";
import type { SessionFactory } from "./run-health.ts";
import { getState, resolveRunDir } from "./status.ts";
import type { SummaryContext } from "./summary.ts";

const LF = String.fromCharCode(10);
/** bytes.strip() 去掉的 ASCII 空白。 */
const ASCII_SPACE = new Set([9, 10, 11, 12, 13, 32]);

export interface RunArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly timeout: number | null;
}

export interface RunContext {
  /** kit_roles.local_command：本机文件里 runtime 的命令（提示行由它打到标准错误），没有或不可用时为 null。 */
  readonly localCommand: (repo: Repo, config: PyDict, runtime: PyValue) => string[] | null;
}

/** cmd_run：只运行未领取的 PREPARED attempt。最终状态是 NEEDS_REVIEW 且事件流正常时退出码 0，否则 1。 */
export async function cmdRun(args: RunArgs, out: PyOut, context: RunContext, sessions: SessionFactory, summary: SummaryContext): Promise<number> {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const state = getState(runDir);
  if (state !== "PREPARED" || pyExists(path.join(runDir, "claim"))) {
    const claimed = pyExists(path.join(runDir, "claim")) ? "（已领取）" : "";
    throw new DispatchError(`attempt 状态为 ${state}${claimed}，只能运行未领取的 PREPARED attempt；返工请重新 prepare。`);
  }
  const workDir = refuseInconsistentInputs(repo, runDir, meta);
  const config = repoConfig(repo);
  // 按冻结合同的类别决定（闸二第 3 片 B1）：按角色写时模型取自版本记录，verify_inputs 已核对它与记录逐项相同
  const bindingValue = frozenExecutorClass(runDir) === "role" ? pyGet(meta, "executor_binding") : null;
  const binding = bindingValue instanceof Map ? bindingValue : null;
  const executor =
    binding !== null
      ? resolveBoundExecutor(contract, binding, config)
      : resolveExecutor(new Map([...contract, ["_raw_executor", loadRawExecutor(runDir)]]), config);
  const taskId = pyItem(meta, "task_id") as string;
  const budget = pyItem(contract, "budget");
  checkAttempts(repo, taskId, runDir, budget);
  const [env, removed] = childEnv(config);
  const piCmd = piCommand(repo, config, binding === null ? null : pyGet(binding, "runtime"), context);
  ensureArgvSafe(piCmd); // 本机文件给出的命令在预检运行它之前就要过这一关（3.0 第二轮 D3）
  const preflight = await piPreflight(piCmd, workDir, executor, path.join(runDir, "preflight"), env);
  const evidence = contextEvidence(workDir, pyItem(executor, "context_files") as string);
  writeJson(path.join(runDir, "preflight", "context-files.json"), evidence);
  if (!pyTruthy(pyItem(preflight, "ok"))) {
    logEvent(runDir, "preflight_failed", [["problems", pyItem(preflight, "problems")]]);
    for (const problem of pyItem(preflight, "problems") as string[]) out.print(`PREFLIGHT ${problem}`);
    throw new DispatchError("预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。");
  }
  for (const note of [...(pyItem(preflight, "notes") as string[]), ...(pyItem(evidence, "warnings") as string[])]) out.print(`NOTE  ${note}`);
  const settled = expectsSettled(pyGet(preflight, "pi_version", "") as string);
  const cmd = [...piCmd, "--provider", pyItem(executor, "provider"), "--model", pyItem(executor, "model"), "--thinking", pyItem(executor, "thinking"), "--no-session", ...RESOURCE_FLAGS] as string[];
  if (pyItem(executor, "context_files") === "none") cmd.push("--no-context-files");
  const attachDir = purePathStr(pyMkdtemp("pi-attach-", pyGettempdir()));
  copyfile(path.join(runDir, "plan.md"), path.join(attachDir, "plan.md"));
  cmd.push("--tools", pyJoinStrings(",", pyItem(executor, "tools") as PyValue[]), "--mode", "json", `@${purePathStr(attachDir, "plan.md")}`, `@${purePathStr(attachDir, "instruction.md")}`);
  ensureArgvSafe(cmd);
  const ignoredBefore = ignoredInventory(workDir);
  const mainBefore = mainRepoFingerprint(repo.root, runDir);
  const timeout = withTaskLock(repo, taskId, () => claim(repo, taskId, runDir, budget, args.timeout));
  const runInfo: PyDict = new Map<string, PyValue>([
    ["command", cmd],
    ["cwd", workDir],
    ["timeout_seconds", timeout],
    ["env_removed", removed],
    ["started_at", utcNow()],
    ["main_repo_before", mainBefore],
    ["expects_agent_settled", settled],
    ["attachments_dir", attachDir],
  ]);
  try {
    writeJson(path.join(runDir, "executor.json"), executor, true);
    const setup = readJsonOr(path.join(runDir, "setup.json"), []);
    const instruction = renderInstruction(meta, contract, executor, timeout, attemptProtectedPaths(config, meta), setup, measuredCheckSeconds(purePathParent(runDir), pyItem(contract, "checks")));
    writeText(path.join(runDir, "instruction.md"), instruction);
    copyfile(path.join(runDir, "instruction.md"), path.join(attachDir, "instruction.md"));
    const attachments = ["plan.md", "instruction.md"].map(
      (name): PyDict => new Map<string, PyValue>([["name", name], ["path", purePathStr(attachDir, name)], ["sha256", sha256File(path.join(attachDir, name))]]),
    );
    runInfo.set("attachments", attachments);
    writeJson(path.join(runDir, "ignored-before.json"), ignoredBefore, true);
    writeJson(path.join(runDir, "run-started.json"), runInfo, true);
    setState(runDir, "RUNNING");
  } catch (error) {
    const spawnError = `领取后、启动前失败：${exceptionName(error)}: ${(error as Error).message}`;
    runInfo.set("spawn_error", spawnError).set("exit_code", null).set("wall_seconds", 0).set("ended_at", utcNow());
    writeJson(path.join(runDir, "run.json"), runInfo);
    setState(runDir, "INFRA_FAILURE", [["reason", spawnError]]);
    throw error;
  }
  const attemptId = pyItem(meta, "attempt_id") as string;
  out.print(`RUNNING ${attemptId}（时限 ${timeout}s）`, { flush: true });
  const grace = pyFloatOf(pyGet(config, "kill_grace_seconds", 15n));
  let result;
  try {
    // 照 Python 的 open(…, "xb")：先依次独占建出两份输出，已存在就报 FileExistsError（状态停在 RUNNING，没有 run.json）
    for (const name of ["events.jsonl", "stderr.log"]) writeText(path.join(runDir, name), "");
    result = await runSupervised(cmd, {
      cwd: workDir,
      env: [...env],
      stdout: { path: path.join(runDir, "events.jsonl"), how: "truncate" },
      stderr: { path: path.join(runDir, "stderr.log"), how: "truncate" },
      timeout: Number(timeout),
      grace,
      onSpawn: (pid) => writeText(path.join(runDir, "pid.txt"), `${pid}${LF}`),
    });
  } finally {
    removeQuietly(attachDir);
  }
  for (const [key, value] of supervisedRecord(result)) runInfo.set(key, value);
  runInfo.set("ended_at", utcNow());
  writeJson(path.join(runDir, "run.json"), runInfo, true);
  setState(runDir, "COLLECTING");
  const finalState = await collect(repo, runDir, meta, contract, executor, runInfo, sessions, summary);
  out.print(`${finalState} ${attemptId}`);
  out.print(`Summary: ${path.join(runDir, "summary.md")}`);
  const events = readJsonOr(path.join(runDir, "events-summary.json"), new Map());
  return finalState === "NEEDS_REVIEW" && pyTruthy(pyGet(events, "ok")) ? EXIT_OK : EXIT_FAIL;
}

/** G0：输入与 prepare 时一致，planner-v2 的固定合同字节对得上，worktree 还在基线上且没有未忽略的变更。交回 worktree 的路径。 */
function refuseInconsistentInputs(repo: Repo, runDir: string, meta: PyValue): string {
  const problems = verifyInputs(runDir, meta, repo);
  const attemptContract = readJsonOr(path.join(runDir, "contract.json"), new Map());
  if (attemptContract instanceof Map && attemptContract.get("contract_family") === "planner-v2") {
    try {
      const planKey = pyItem(meta, "plan_key") as string;
      problems.push(...verifyPlannerPublication(repo, planKey, pyReadBytes(path.join(runDir, "plan.md")), pyReadBytes(path.join(runDir, "contract.json"))));
    } catch (error) {
      if (!(error instanceof PyOSError)) throw error;
      problems.push(`planner-v2 固定合同字节读取失败：${error.message}`);
    }
  }
  const workDir = purePathStr(pyItem(meta, "worktree") as string);
  if (!isDir(workDir)) {
    problems.push(`worktree 不存在：${workDir}`);
  } else {
    if (gitText(["rev-parse", "HEAD"], workDir) !== pyItem(meta, "base_sha")) problems.push("worktree HEAD 已不是基线提交");
    if ([...gitChecked(["status", "--porcelain=v1"], workDir).stdout].some((byte) => !ASCII_SPACE.has(byte))) problems.push("worktree 在运行前已有未忽略的变更");
  }
  if (problems.length) {
    logEvent(runDir, "run_refused", [["problems", problems]]);
    throw new DispatchError(`输入不一致（G0）：${problems.join("；")}`);
  }
  return workDir;
}

/** load_raw_executor：冻结合同里原样的 executor 字段。 */
function loadRawExecutor(runDir: string): PyValue {
  const raw = readJsonOr(path.join(runDir, "contract.json"), new Map());
  return raw instanceof Map ? (raw.get("executor") ?? new Map()) : new Map();
}

function checkAttempts(repo: Repo, taskId: string, runDir: string, budget: PyValue): number {
  const usage = budgetUsage(repo, taskId, runDir);
  const limit = pyItem(budget, "max_attempts_total");
  if (BigInt(usage.attempts_started) >= (limit as bigint)) throw new DispatchError(`BUDGET_EXCEEDED：已达到 max_attempts_total=${pyPercentD(limit)}。`);
  return usage.wall_seconds_used;
}

/**
 * resolve_pi_command(repo, runtime, config)：PI_DISPATCH_PI_CMD；按角色写的合同再看本机文件里 runtime 的命令；最后 PATH 上的 pi。
 * 写死的合同与旧合同不传 runtime，不读本机文件。
 */
function piCommand(repo: Repo, config: PyDict, runtime: PyValue, context: RunContext): string[] {
  if (!process.env["PI_DISPATCH_PI_CMD"] && runtime !== null) {
    const local = context.localCommand(repo, config, runtime);
    if (local !== null) return local;
  }
  return resolvePiCommand();
}

/** 临界区（任务锁里）：重新核算预算，预留本轮时限，建 claim/ 领取。交回本轮时限（秒）。 */
function claim(repo: Repo, taskId: string, runDir: string, budget: PyValue, requested: number | null): bigint {
  const used = checkAttempts(repo, taskId, runDir, budget);
  const remaining = pyFloatOf(pyItem(budget, "max_wall_seconds_total")) - used;
  if (remaining < 60) throw new DispatchError(`BUDGET_EXCEEDED：剩余墙钟预算 ${pyFixed(remaining, 0)}s，不足 60s。`);
  const perAttempt = pyItem(budget, "max_wall_seconds_per_attempt") as bigint;
  // int(min(每轮上限, 剩余))：剩余更小时截掉小数
  let timeout = remaining < Number(perAttempt) ? BigInt(Math.trunc(remaining)) : perAttempt;
  if (requested) {
    const cap = BigInt(requested);
    timeout = cap < timeout ? cap : timeout;
    if (timeout < 1n) timeout = 1n;
  }
  try {
    pathMkdir(path.join(runDir, "claim"), false, false);
  } catch (error) {
    if (isFileExists(error)) throw new DispatchError("该 attempt 已被领取，不能重复运行。");
    throw error;
  }
  writeJson(path.join(runDir, "claim", "reservation.json"), new Map<string, PyValue>([["timeout_seconds", timeout], ["pid", BigInt(process.pid)], ["at", utcNow()]]), true);
  return timeout;
}

/** type(exc).__name__ 的对应。 */
function exceptionName(error: unknown): string {
  if (error instanceof PyOSError) return pyOSErrorType(error);
  if (error instanceof PyCrash) return error.kind;
  if (error instanceof DispatchError) return "DispatchError";
  return error instanceof Error ? error.name : "Exception";
}

/** shutil.rmtree(ignore_errors=True)。 */
function removeQuietly(dir: string): void {
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch {
    // 照 ignore_errors：删不掉就留着
  }
}

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}
