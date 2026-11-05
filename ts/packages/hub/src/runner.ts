// 进程模型（迁移第 ⑤j2 片）：kit_hub.py 的 kernel_files、code_fingerprint、kernel_dirty、kernel_changes、refuse_dirty_kernel、kernel_settled、
// spawn_runner、pause_requested、cmd_run、spawn_task_runner、owner_sweep_tick、cmd_owner_sweep、supervise_tick、supervise、cmd_exclusive，
// 以及 EXIT_RESTART、TASK_RUNNER_IDLE_SECONDS、RUNNER_CRASH_LIMIT。
// deps 只给契约用：用例换掉的内层函数（起子进程、内核文件的几样、tasks_with_work、sleep、Engine.step 一类）照记录注入；生产调用方不传。
// 子进程照 Python 的 Popen：不等它、不转交它的退出码，本进程退出时子进程照常跑（Windows 上不经 child_process，见 popenWindows）。起出来的
// 对象只用 pid、poll（与 poll 之后的 returncode），同 python_probe.py 的 _ProcReplay：以后要调 kill、wait 先在两边一起加。
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { closeSync, mkdirSync, openSync, readFileSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { createHash } from "node:crypto";
import { readText, writeTextAtomic } from "@themis/base/fsutil";
import { PyCrash, PyOut, pyGet, pyIntOf, pyRepr, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, loads } from "@themis/base/pyjson";
import { purePathStr } from "@themis/base/pypath";
import { cmpCodePoints, pySplitlines, pyStrip } from "@themis/base/pyre";
import { type Spawned, Win32Error, winProcessApi } from "@themis/base/native";
import { list2cmdline, pyWinErrorMessage, windowsOSError } from "@themis/base/supervise";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { readKernelImpl } from "@themis/dispatcher/kernel-impl";
import { DispatchError } from "@themis/dispatcher/repo";
import { type CommandArgs, type CommandOut, configuredParallel, findRepo, lockAlive, pauseMarker } from "./commands.ts";
import { EXIT_BLOCKED, EXIT_OK, EXIT_USAGE, KERNEL, OWNER } from "./constants.ts";
import { deliveryFiles } from "./delivery.ts";
import { Engine, type EngineDeps, REAL_ENGINE_DEPS, land, pyErrorNames } from "./engine.ts";
import { HubError } from "./errors.ts";
import { HUB_SHA256, KERNEL_ROOT, SCRIPTS_DIR, TEMPLATE_DIR, git, hubImpl } from "./kernel.ts";
import { landingBlockers } from "./land.ts";
import { parseLetter, stageOf } from "./letters.ts";
import { DirLock, Hub, letterMain } from "./mailbox.ts";
import { requeueInterrupted, runnerLock, runnerMayIdleExit, supervisorBusy, tasksWithWork } from "./requeue.ts";
import { KERNEL_IMPL_PATH, kernelPython } from "./runpd.ts";
import { markOwnerMoved, ownerSweep, readOwnerSweep } from "./sweep.ts";

const LF = String.fromCharCode(10);
const NUL = String.fromCharCode(0);

/** 主任务 runner 因内核代码变了而退出：由 supervisor 用新代码再起。 */
export const EXIT_RESTART = 75;
/** 主任务 runner 没事可做多久就退出（supervisor 看到新信再起）。 */
export const TASK_RUNNER_IDLE_SECONDS = 60.0;
/** 主任务 runner 接连异常退出几次就不再起，写信请站主看。 */
export const RUNNER_CRASH_LIMIT = 3;

/** 起出来的子进程：只用 pid 与 poll（poll 不是 null 之后 returncode 是退出码）。 */
export interface ChildLike {
  readonly pid: number | null;
  poll(): number | null;
  readonly returncode?: number | null;
}

/** 子进程输出接到的日志：打开的文件描述符与路径（契约比文件名）。 */
export interface ChildLog {
  readonly fd: number;
  readonly path: string;
}

/** 用例当时换掉、契约照记录注入的；缺省是真的。 */
export interface RunnerDeps extends EngineDeps {
  readonly spawnTaskRunner: (hub: Hub, task: string, args: CommandArgs | null, deps: RunnerDeps) => Promise<ChildLike>;
  readonly spawnRunner: (hub: Hub, argv: readonly string[], deps: RunnerDeps) => Promise<number>;
  readonly kernelDirty: (files?: readonly string[] | null) => boolean;
  readonly kernelSettled: (wait: number, poll: number, deps: RunnerDeps) => Promise<boolean>;
  readonly codeFingerprint: (files?: readonly string[] | null) => string;
  readonly kernelChanges: (files?: readonly string[] | null) => string[];
  readonly tasksWithWork: (hub: Hub) => string[];
  readonly requeueInterrupted: (hub: Hub, skip: readonly string[], deps: RunnerDeps) => Promise<string[]>;
  readonly ownerSweepTick: (hub: Hub, holder: Map<string, ChildLike | null>, deps: RunnerDeps) => Promise<boolean>;
  /** subprocess.Popen([...], cwd=…, stdin=DEVNULL, stdout=日志, stderr=STDOUT)；log 是 null 时 stdout、stderr 照继承。 */
  readonly popen: (argv: readonly string[], cwd: string | null, log: ChildLog | null) => Promise<ChildLike>;
  readonly sleep: (seconds: number) => Promise<void>;
  readonly monotonic: () => number;
  /** cmd_run 里的 Engine.step（run_with_kernel_change 换掉它）。 */
  readonly engineStep: (engine: Engine) => Promise<boolean>;
  /** exclusive 跑的那条命令的标准输出与错误：生产上照继承（站主要看）；契约的探针给 ignore（探针的 stdout 是交回结果的通道）。 */
  readonly commandStdio: "inherit" | "ignore";
  /** 这个进程自己的 pid（runner.started 一类记它）。 */
  readonly selfPid: number;
}

export const REAL_RUNNER_DEPS: RunnerDeps = {
  ...REAL_ENGINE_DEPS,
  spawnTaskRunner: (hub, task, args, deps) => spawnTaskRunner(hub, task, args, deps),
  spawnRunner: (hub, argv, deps) => spawnRunner(hub, argv, deps),
  kernelDirty: (files) => kernelDirty(files),
  kernelSettled: (wait, poll, deps) => kernelSettled(wait, poll, deps),
  codeFingerprint: (files) => codeFingerprint(files),
  kernelChanges: (files) => kernelChanges(files),
  tasksWithWork: (hub) => tasksWithWork(hub),
  requeueInterrupted: (hub, skip, deps) => requeueInterrupted(hub, skip, deps),
  ownerSweepTick: (hub, holder, deps) => ownerSweepTick(hub, holder, deps),
  popen: (argv, cwd, log) => popen(argv, cwd, log),
  sleep: (seconds) => new Promise((done) => setTimeout(done, seconds * 1000)),
  monotonic: () => performance.now() / 1000,
  engineStep: (engine) => engine.step(),
  commandStdio: "inherit",
  selfPid: process.pid,
};

/** Path 的排序（sorted(glob)）：同一个目录下照名字比，Windows 上先转小写。 */
const fold = (name: string): string => (process.platform === "win32" ? name.toLowerCase() : name);

/**
 * 内核文件：代码、调度器、提示词模板与选择文件，加交差工具的文件（同 kit_hub.py）。选择文件的 hub 是 ts 时另加 TS 的源码与依赖清单（E3）：
 * 那时跑的是这些代码，它们变了，runner 也要在两步之间换新代码。code_fingerprint、kernel_dirty、kernel_changes 没给 files 时都用这一份。
 */
export function kernelFiles(impl: PyDict | null = null): string[] {
  // glob("*.md")：Windows 上不分大小写，目录也算（同 Python）
  const templates = listDir(TEMPLATE_DIR).filter((name) => fold(name).endsWith(".md")).sort((a, b) => cmpCodePoints(fold(a), fold(b)));
  const files = [join(SCRIPTS_DIR, "kit_hub.py"), join(SCRIPTS_DIR, "pi_dispatch.py"), ...templates.map((name) => join(TEMPLATE_DIR, name)),
    join(SCRIPTS_DIR, "kernel-impl.json"), ...deliveryFiles()];
  return pyGet(impl ?? kernelSelection(), "hub") === "ts" ? [...files, ...tsKernelFiles()] : files;
}

/**
 * 选择文件；读不了、不合法时交回 {}，当 hub 是 python。runner 每一轮都算指纹，选择文件坏了不能让 supervisor 崩：它本身就是内核文件，内容
 * 一变指纹就变，runner 照常在两步之间退出，重起的进程读到坏文件会拒绝运行。path 只给契约换。
 */
export function kernelSelection(path: string = KERNEL_IMPL_PATH): PyDict {
  try {
    return readKernelImpl(path);
  } catch (error) {
    if (error instanceof DispatchError) return new Map();
    throw error;
  }
}

/** E3 加的那几个包：src 下的全部文件都是 hub 进程的代码（contracts 是测试，ui 不在 hub 进程里）。 */
const TS_KERNEL_PACKAGES = ["base", "config", "dispatcher", "hub", "cli"];

/**
 * E3（⑤j 设计稿第 6 节）：TS_KERNEL_PACKAGES 的 src 下的全部文件（按相对路径的码点排），ts 下的 package.json、bun.lock、bunfig.toml，
 * 各包的 package.json（exports 决定模块怎么解析；按包名排），tsconfig.json。
 */
function tsKernelFiles(): string[] {
  const root = join(KERNEL_ROOT, "ts");
  const sources: string[] = [];
  const walk = (dir: string, rel: string): void => {
    for (const name of listDir(dir)) {
      if (isDirectory(join(dir, name))) walk(join(dir, name), `${rel}/${name}`);
      else sources.push(`${rel}/${name}`);
    }
  };
  for (const name of TS_KERNEL_PACKAGES) walk(join(root, "packages", name, "src"), `packages/${name}/src`);
  const manifests = listDir(join(root, "packages")).filter((name) => isFile(join(root, "packages", name, "package.json")))
    .map((name) => `packages/${name}/package.json`);
  return [...sources.sort(cmpCodePoints), "package.json", "bun.lock", "bunfig.toml", ...manifests.sort(cmpCodePoints), "tsconfig.json"]
    .map((rel) => join(root, ...rel.split("/")));
}

/** 内核文件的指纹：文件名、0 字节、内容、0 字节；读不到的当成变了（写 0 字节加 unreadable）。 */
export function codeFingerprint(files: readonly string[] | null = null): string {
  const digest = createHash("sha256");
  for (const path of files ?? kernelFiles()) {
    let data: Buffer;
    try {
      data = readFileSync(path);
    } catch {
      data = Buffer.from(`${NUL}unreadable`, "utf8");
    }
    digest.update(Buffer.concat([Buffer.from(basename(path), "utf8"), Buffer.from(NUL), data, Buffer.from(NUL)]));
  }
  return digest.digest("hex");
}

/** git status --porcelain -- <路径…>，在第一个路径所在的目录跑：交回 [起不来时的 Python 文字 | null, 退出码, stdout]。 */
function gitStatus(paths: readonly string[]): [string | null, number, Buffer] {
  if (paths.length === 0) throw new PyCrash("IndexError", "list index out of range");
  const cwd = dirname(paths[0] as string);
  const done = spawnSync("git", ["status", "--porcelain", "--", ...paths], { cwd, stdio: ["ignore", "pipe", "ignore"], windowsHide: true, maxBuffer: 1024 * 1024 * 1024 });
  if (done.error) {
    // Windows 上 cwd 不存在时 Python 报 NotADirectoryError（WinError 267），找不到 git 报 WinError 2；都不带路径（同 kernel.ts 的 git）
    return [pyWinErrorMessage(isDirectory(cwd) ? 2 : 267), -1, Buffer.alloc(0)];
  }
  return [null, done.status ?? 1, done.stdout];
}

/** 内核文件有没有未提交的改动：git 起不来、出错都按“有”算。 */
export function kernelDirty(files: readonly string[] | null = null): boolean {
  const [failed, code, stdout] = gitStatus(files ?? kernelFiles());
  return failed !== null || code !== 0 || stdout.some((byte) => !ASCII_SPACE.has(byte)); // bytes.strip() 只去 ASCII 空白
}

/** bytes.strip() 去掉的字节：空格、制表、换行、回车、竖制表、换页。 */
const ASCII_SPACE: ReadonlySet<number> = new Set([32, 9, 10, 13, 11, 12]);

/** 内核文件里没提交的改动（git status --porcelain 的行；git 出错时给一句说明）。 */
export function kernelChanges(files: readonly string[] | null = null): string[] {
  const [failed, code, stdout] = gitStatus(files ?? kernelFiles());
  if (failed !== null) return [`git 起不来：${failed}`];
  if (code !== 0) return [`git status 退出码 ${code}（不在 Git 仓库里？）`];
  return pySplitlines(pyDecodeUtf8Replace(stdout)).filter((line) => pyStrip(line) !== "");
}

/** 起 hub 之前，内核文件必须与 HEAD 一致；站主显式加 --allow-dirty-kernel 才放行。 */
export async function refuseDirtyKernel(hub: Hub, args: CommandArgs | null, task: string | null, deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<void> {
  const changes = deps.kernelChanges(null);
  if (changes.length === 0) return;
  if (pyTruthy((args ?? {})["allow_dirty_kernel"] ?? false)) {
    await hub.appendEvent("runner.dirty_kernel_allowed", [["pid", BigInt(deps.selfPid)], ["task", task], ["changes", changes.slice(0, 20)]]);
    return;
  }
  await hub.appendEvent("runner.refused", [["pid", BigInt(deps.selfPid)], ["task", task], ["reason", "kernel_dirty"], ["changes", changes.slice(0, 20)]]);
  throw new HubError(`内核文件与 HEAD 不一致，hub 不起：${changes.slice(0, 10).join("；")}。正常的内核轮次都经 exclusive 提交合入；真要用这份未提交的`
    + "内核跑，站主显式加 --allow-dirty-kernel", EXIT_BLOCKED);
}

/** 等内核文件落定（没有未提交的改动），最多等 wait 秒。 */
export async function kernelSettled(wait: number, poll: number, deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<boolean> {
  const deadline = deps.monotonic() + wait;
  while (deps.kernelDirty(null)) {
    if (deps.monotonic() >= deadline) return false;
    await deps.sleep(Math.max(poll, 0.1));
  }
  return true;
}

/** 用新代码起一个 hub 后立即交回 EXIT_OK，不等它结束；子进程号记进账本（runner.respawned）。 */
export async function spawnRunner(hub: Hub, argv: readonly string[], deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<number> {
  const child = await deps.popen(argv, null, null);
  await hub.appendEvent("runner.respawned", [["pid", BigInt(deps.selfPid)], ["child", child.pid === null ? null : BigInt(child.pid)]]);
  return EXIT_OK;
}

/** 站主的命令在等这个主任务的 runner 让出锁；命令的进程已经不在时，标记作废并删掉。 */
export function pauseRequested(hub: Hub, task: string, deps: RunnerDeps = REAL_RUNNER_DEPS): boolean {
  const marker = pauseMarker(hub, task);
  if (!isFile(marker)) return false;
  const data = loads(readText(marker) || "{}");
  if (!(data instanceof Map)) throw new PyCrash("AttributeError", `'${pyTypeName(data)}' object has no attribute 'get'`);
  const pid = pyGet(data, "pid");
  if (pyTruthy(pid) && deps.pidAlive(Number(pyIntOf(pid))) === false) {
    try {
      unlinkSync(marker);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
    return false;
  }
  return true;
}

/** Python 的 str(float)：argparse 的 type=float 参数原样写回命令行。 */
const num = (value: PyValue | undefined): string => pyStrValue(value ?? null);
let kitHubPath = join(SCRIPTS_DIR, "kit_hub.py");

/** 换代、主任务 runner、owner-sweep 起的 kit_hub.py：经启动器转交时用启动器给的路径（Python 的 str(Path(__file__))，不 resolve）。 */
export function setKitHub(path: string): void {
  kitHubPath = path;
}

const hubArgv = (hub: Hub): string[] => [kernelPython(), kitHubPath, "--repo", hub.repo];

/** 调度循环（串行，或 --task 时只办这个主任务的信）；并行时转给 supervise。 */
export async function cmdRun(args: CommandArgs, out: CommandOut = new PyOut(), deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<number> {
  const hub = new Hub(findRepo(args["repo"] === null || args["repo"] === undefined ? null : pyStrValue(args["repo"])));
  hub.ensure();
  const task = args["task"] === null || args["task"] === undefined ? null : pyStrValue(args["task"]);
  await refuseDirtyKernel(hub, args, task, deps);
  if (task === null && configuredParallel(hub, args) > 1) return supervise(hub, args, configuredParallel(hub, args), out, deps);
  if (task === null) {
    const runners = purePathStr(hub.root, ".runners");
    const busy = isDirectory(runners) ? listDir(runners).filter((name) => lockAlive(purePathStr(runners, name), deps)).sort(cmpCodePoints) : [];
    if (busy.length > 0) throw new HubError(`这些主任务各有 runner 在跑（并行模式）：${busy.join("、")}。串行的 hub 不能同时跑`, EXIT_BLOCKED);
  }
  const engine = new Engine(hub, null, task, deps);
  const maxSteps = Number(pyIntOf(args["max_steps"] ?? null));
  const idleExit = Number(args["idle_exit"]);
  const poll = Number(args["poll"]);
  let turns = 0;
  let restart = false;
  let deferred: string | null = null;
  const fingerprint = deps.codeFingerprint(null);
  const lock = new DirLock(runnerLock(hub, task), 1.0).acquire();
  try {
    await hub.appendEvent("runner.started", [["pid", BigInt(deps.selfPid)], ["hub_sha256", HUB_SHA256], ["task", task], ["hub_impl", hubImpl()]]);
    if (task === null) await deps.requeueInterrupted(hub, [], deps); // 串行的 hub 起步时没有别人在办（并行时由 supervisor 放回）
    let idleSince = deps.monotonic();
    while (turns < maxSteps) {
      if (deps.codeFingerprint(null) !== fingerprint) {
        restart = !pyTruthy(args["no_restart"] ?? false) && await deps.kernelSettled(Number(args["settle"]), poll, deps);
        await hub.appendEvent("runner.code_changed", [["pid", BigInt(deps.selfPid)], ["steps", BigInt(turns)], ["restart", restart], ["task", task]]);
        out.print(`内核代码或提示词模板变了：${restart ? "已提交，hub 在两步之间用新代码重启"
          : `hub 在两步之间退出（${pyTruthy(args["no_restart"] ?? false) ? "--no-restart" : "还有未提交的改动"}），请用新代码重启`}`);
        break;
      }
      if (task !== null && pauseRequested(hub, task, deps)) { // 站主的命令在等锁
        await hub.appendEvent("runner.paused", [["pid", BigInt(deps.selfPid)], ["steps", BigInt(turns)], ["task", task]]);
        out.print(`站主的命令在等 ${task} 的锁：让出`);
        break;
      }
      const passes = hub.unread("exec-step").filter((path) => parseLetter(readText(path))[0].get("type") === "通过"
        && (task === null || letterMain(path) === task));
      if (passes.length > 0) { // 结项信由内核办，不唤醒任何进程
        const meta = parseLetter(readText(passes[0] as string))[0];
        const blockers = await land(hub, engine, passes[0] as string, meta, deps);
        if (blockers.length > 0) { // 别的主任务的执行端还在跑：落地会改主工作区，等它跑完
          if (!meta.has("msg-id")) throw new PyCrash("KeyError", "'msg-id'"); // meta["msg-id"]
          if (deferred !== meta.get("msg-id")) {
            deferred = meta.get("msg-id") as string;
            await hub.appendEvent("finalize.deferred", [["task", stageOf(meta.get("task-id"))[0]], ["blockers", blockers]]);
            out.print(`结项等别的执行端跑完再落地：${blockers.map(pyStrValue).join("、")}`);
          }
          idleSince = deps.monotonic();
          await deps.sleep(poll);
          continue;
        }
        deferred = null;
        turns += 1;
        continue;
      }
      if (await deps.engineStep(engine)) {
        turns += 1;
        idleSince = deps.monotonic();
        continue;
      }
      if (deps.monotonic() - idleSince >= idleExit && runnerMayIdleExit(hub, task)) break;
      await deps.sleep(poll);
    }
    await hub.appendEvent("runner.stopped", [["pid", BigInt(deps.selfPid)], ["steps", BigInt(turns)], ["task", task]]);
  } finally {
    lock.release();
  }
  if (restart && task !== null) return EXIT_RESTART; // 主任务 runner 不自己重启：supervisor 看到它退出、还有信，就用新代码再起
  if (restart) { // 运行锁已经交出：子进程要拿到它。退出码是 EXIT_OK，不是新 hub 的
    return deps.spawnRunner(hub, [...hubArgv(hub), "run", "--max-steps", String(maxSteps - turns), "--idle-exit", num(args["idle_exit"]),
      "--poll", num(args["poll"]), "--settle", num(args["settle"])], deps);
  }
  out.print(`hub 退出：处理了 ${turns} 件事；站主未读 ${hub.unread(OWNER).length} 封`);
  return EXIT_OK;
}

/** 起一个只办 task 的 runner 子进程，输出追加进信箱下的 runners/<task>.log。 */
export function spawnTaskRunner(hub: Hub, task: string, args: CommandArgs | null, deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<ChildLike> {
  const logs = purePathStr(hub.root, "runners");
  mkdirSync(logs, { recursive: true });
  return withLog(purePathStr(logs, `${task}.log`), (log) => {
    if (args === null) throw new PyCrash("AttributeError", "'NoneType' object has no attribute 'max_steps'"); // 日志已经建了，同 Python
    return deps.popen([...hubArgv(hub), "run", "--task", task, "--max-steps", num(args["max_steps"]), "--idle-exit", num(TASK_RUNNER_IDLE_SECONDS),
      "--poll", num(args["poll"]), "--settle", num(args["settle"]), ...(pyTruthy(args["allow_dirty_kernel"] ?? false) ? ["--allow-dirty-kernel"] : [])],
    hub.repo, log);
  });
}

/** with open(path, "ab") as log：子进程的输出接到这个文件，起完就关（子进程有自己的一份）。 */
async function withLog<T>(path: string, body: (log: ChildLog) => Promise<T>): Promise<T> {
  const fd = openSync(path, "a");
  try {
    return await body({ fd, path });
  } finally {
    closeSync(fd);
  }
}

/**
 * supervisor 的一轮里顺带：站主经 exclusive 动过 HEAD、还没跑门禁回归时，起一个 owner-sweep 子进程。同时只跑一个；内核有未提交的改动时
 * 等落定。交回这轮有没有起。
 */
export async function ownerSweepTick(hub: Hub, holder: Map<string, ChildLike | null>, deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<boolean> {
  const proc = holder.get("proc") ?? null;
  if (proc !== null && proc.poll() === null) return false;
  if (proc !== null) {
    await hub.appendEvent("owner_sweep.exited", [["code", returncodeOf(proc)]]);
    holder.set("proc", null);
  }
  if (!pyTruthy(pyGet(readOwnerSweep(hub), "pending")) || lockAlive(purePathStr(hub.root, ".owner-sweep"), deps) || deps.kernelDirty(null)) return false;
  const logs = purePathStr(hub.root, "runners");
  mkdirSync(logs, { recursive: true });
  const started = await withLog(purePathStr(logs, "owner-sweep.log"), (log) => deps.popen([...hubArgv(hub), "owner-sweep"], hub.repo, log));
  holder.set("proc", started);
  await hub.appendEvent("owner_sweep.started", [["pid", started.pid === null ? null : BigInt(started.pid)]]);
  return true;
}

/** owner-sweep 子命令：拿着 .owner-sweep 跑一次；已经有一个在跑就说一句、照常退出。 */
export async function cmdOwnerSweep(args: CommandArgs, out: CommandOut = new PyOut(), deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<number> {
  const hub = new Hub(findRepo(args["repo"] === null || args["repo"] === undefined ? null : pyStrValue(args["repo"])));
  hub.ensure();
  let result: [boolean, string] | null;
  try {
    const lock = new DirLock(purePathStr(hub.root, ".owner-sweep"), 1.0).acquire();
    try {
      result = await ownerSweep(hub, deps);
    } finally {
      lock.release();
    }
  } catch (error) {
    if (error instanceof HubError && error.code === EXIT_BLOCKED) {
      out.print(`已经有一个在跑：${error.message}`);
      return EXIT_OK;
    }
    throw error;
  }
  out.print(result === null ? "没有待跑的" : result[1]);
  return EXIT_OK;
}

/** supervisor 的一轮：收拾退出的子进程，按名额起新的。交回（有信的主任务，在跑的 runner 数，这轮起了几个）。 */
export async function superviseTick(hub: Hub, args: CommandArgs | null, parallel: number, children: Map<string, ChildLike>, failures: Map<string, bigint>,
  out: CommandOut = new PyOut(), deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<[string[], number, number]> {
  for (const [task, proc] of [...children]) {
    const code = proc.poll();
    if (code === null) continue;
    children.delete(task);
    await hub.appendEvent("runner.child_exited", [["task", task], ["code", BigInt(code)]]);
    out.print(`${task} 的 runner 退出（${code}）`);
    failures.set(task, code === EXIT_OK || code === EXIT_RESTART ? 0n : (failures.get(task) ?? 0n) + 1n);
    if (failures.get(task) === BigInt(RUNNER_CRASH_LIMIT)) { // 接连崩的 runner 一直重起，只会把同一个错误刷满日志
      await hub.deliver(new Map([["from", KERNEL], ["to", OWNER], ["task-id", task], ["in-reply-to", "none"], ["type", "阻塞"]]), new Map<string, PyValue>([
        ["摘要", `${task} 的 runner 接连 ${RUNNER_CRASH_LIMIT} 次异常退出，supervisor 不再起它`], ["提交", "无"], ["验证", `最后一次退出码 ${code}`],
        ["偏离", "无"], ["需协调人决定", "请站主看日志、修好之后重启 hub（kit_hub.py run）"], ["证据", `.agent/mailbox/runners/${task}.log`],
      ]));
    }
  }
  await deps.releaseHeld(hub); // 到点的扣信放回信箱，下面就会给那个主任务起 runner
  const runners = purePathStr(hub.root, ".runners");
  // 上一代 supervisor 起的、还在跑的主任务 runner（重启之后接着算数，不重复起）
  const adopted = isDirectory(runners)
    ? listDir(runners).sort((a, b) => cmpCodePoints(fold(a), fold(b))).filter((name) => !children.has(name) && lockAlive(purePathStr(runners, name), deps))
    : [];
  const paused = [...hub.loadState().tasks().keys()].map(String).filter((name) => pauseRequested(hub, name, deps));
  await deps.requeueInterrupted(hub, [...new Set([...children.keys(), ...paused])], deps); // Python 是 set 的并
  const pending = deps.tasksWithWork(hub);
  let live = children.size + adopted.length;
  let spawned = 0;
  for (const task of pending) {
    if (children.has(task) || adopted.includes(task) || (failures.get(task) ?? 0n) >= BigInt(RUNNER_CRASH_LIMIT)) continue;
    if (pauseRequested(hub, task, deps)) continue; // 站主的命令在等它的锁
    if (live >= parallel || deps.kernelDirty(null)) break; // 满了；或内核有未提交的改动，等落定
    const child = await deps.spawnTaskRunner(hub, task, args, deps);
    children.set(task, child);
    live += 1;
    spawned += 1;
    await hub.appendEvent("runner.child_started", [["task", task], ["pid", child.pid === null ? null : BigInt(child.pid)]]);
    out.print(`起 ${task} 的 runner（pid ${child.pid}）`);
  }
  return [pending.filter((task) => (failures.get(task) ?? 0n) < BigInt(RUNNER_CRASH_LIMIT)), live, spawned];
}

/** 并行调度：每个有信的主任务起一个 run --task 子进程，同时最多 parallel 个；内核代码变了就照第 13 轮重启。 */
export async function supervise(hub: Hub, args: CommandArgs, parallel: number, out: CommandOut = new PyOut(), deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<number> {
  const children = new Map<string, ChildLike>();
  const failures = new Map<string, bigint>();
  const sweeper = new Map<string, ChildLike | null>([["proc", null]]);
  const poll = Number(args["poll"]);
  let current = parallel;
  let started = 0;
  let restart = false;
  const fingerprint = deps.codeFingerprint(null);
  const lock = new DirLock(runnerLock(hub, null), 1.0).acquire();
  try {
    writeMode(hub);
    await hub.appendEvent("runner.started", [["pid", BigInt(deps.selfPid)], ["hub_sha256", HUB_SHA256], ["parallel", BigInt(current)], ["hub_impl", hubImpl()]]);
    out.print(`hub 并行调度：最多 ${current} 个主任务同时跑`);
    let idleSince = deps.monotonic();
    for (;;) {
      current = configuredParallel(hub, args); // 站主改 runner.json 马上生效（--parallel 优先）
      if (deps.codeFingerprint(null) !== fingerprint) {
        restart = !pyTruthy(args["no_restart"] ?? false) && await deps.kernelSettled(Number(args["settle"]), poll, deps);
        await hub.appendEvent("runner.code_changed", [["pid", BigInt(deps.selfPid)], ["steps", BigInt(started)], ["restart", restart]]);
        out.print(`内核代码或提示词模板变了：${restart ? "已提交，supervisor 用新代码重启" : "supervisor 退出，请用新代码重启"}`);
        break;
      }
      let pending: string[];
      let live: number;
      let spawned: number;
      try {
        [pending, live, spawned] = await superviseTick(hub, args, current, children, failures, out, deps);
        await deps.ownerSweepTick(hub, sweeper, deps);
      } catch (error) { // 一次意外不能让所有主任务都停下
        const text = `${pyErrorNames(error)[0]}: ${error instanceof Error ? error.message : String(error)}`;
        await hub.appendEvent("supervisor.error", [["error", text]]);
        out.print(`supervisor 这一轮出错，稍后再试：${text}`);
        [pending, live, spawned] = [[], 1, 0];
        await deps.sleep(Math.max(poll, 5.0));
      }
      started += spawned;
      if (supervisorBusy(hub, pending, BigInt(live))) idleSince = deps.monotonic(); // 扣着的信到点要有人放回
      else if (deps.monotonic() - idleSince >= Number(args["idle_exit"])) break;
      await deps.sleep(poll);
    }
    await hub.appendEvent("runner.stopped", [["pid", BigInt(deps.selfPid)], ["steps", BigInt(started)]]);
  } finally {
    lock.release();
  }
  if (restart) { // 退出码是 EXIT_OK，不是新 supervisor 的；跑着的主任务 runner 照旧归新的管
    const flag = args["parallel"] === null || args["parallel"] === undefined ? [] : ["--parallel", String(current)];
    return deps.spawnRunner(hub, [...hubArgv(hub), "run", ...flag, "--max-steps", num(args["max_steps"]), "--idle-exit", num(args["idle_exit"]),
      "--poll", num(args["poll"]), "--settle", num(args["settle"])], deps);
  }
  out.print(`hub 退出：起过 ${started} 个主任务 runner；站主未读 ${hub.unread(OWNER).length} 封`);
  return EXIT_OK;
}

/**
 * 等所有执行端跑完、拿着落地锁跑一条命令（站主在并行期间提交、合入内核用）。命令的输出照继承给站主看；动了 HEAD 就记下，supervisor 在后台
 * 跑门禁回归与落地预演。
 */
export async function cmdExclusive(args: CommandArgs, out: CommandOut = new PyOut(), deps: RunnerDeps = REAL_RUNNER_DEPS): Promise<number> {
  const hub = new Hub(findRepo(args["repo"] === null || args["repo"] === undefined ? null : pyStrValue(args["repo"])));
  hub.ensure();
  let command = ((args["command"] ?? []) as PyValue[]).map(pyStrValue);
  if (command[0] === "--") command = command.slice(1);
  if (command.length === 0) throw new HubError("要跑的命令写在 -- 之后，例如 kit_hub.py exclusive -- git merge --ff-only <提交>", EXIT_USAGE);
  const wait = Number(args["wait"]);
  const deadline = deps.monotonic() + wait;
  let before: string;
  let after: string;
  let code: number;
  const lock = new DirLock(purePathStr(hub.root, ".land"), wait).acquire();
  try {
    let announced = false;
    for (;;) { // 后台的门禁回归不挡站主的命令（它跑的是固定的末端，下一轮再跑新的）
      const blockers = landingBlockers(hub, new Map<string, PyValue>([["task", null], ["contract_task", NUL]]), false, deps).map(pyStrValue);
      if (blockers.length === 0) break;
      if (deps.monotonic() >= deadline) throw new HubError(`等了 ${Math.trunc(wait)} 秒，执行端还没跑完：${blockers.join("、")}`, EXIT_BLOCKED);
      if (!announced) {
        out.print(`等这些跑完：${blockers.join("、")}（新的执行端在此期间不会开始）`);
        announced = true;
      }
      await deps.sleep(5);
    }
    await hub.appendEvent("exclusive.run", [["command", command.slice(0, 6)], ["hub_impl", hubImpl()]]);
    before = pyStrip(git(["rev-parse", "HEAD"], hub.repo, false));
    code = runCommand(command, hub.repo, deps.commandStdio);
    after = pyStrip(git(["rev-parse", "HEAD"], hub.repo, false));
  } finally {
    lock.release();
  }
  if (before && after && after !== before) await markOwnerMoved(hub, before, after, command); // supervisor 在后台跑门禁回归与落地预演
  return code;
}

/** subprocess.run(command, cwd=…, stdin=DEVNULL).returncode（同 commands.ts 的 runCode）：起不来照 Python 抛 FileNotFoundError。 */
function runCommand(command: readonly string[], cwd: string, stdio: "inherit" | "ignore"): number {
  const done = spawnSync(command[0] as string, command.slice(1), { cwd, stdio: ["ignore", stdio, stdio], windowsHide: true });
  if (done.error) throw new PyCrash("FileNotFoundError", pyWinErrorMessage(2));
  return done.status ?? 1;
}

/** 真的 Popen：不等它，本进程退出时子进程照常跑。win32 走 Win32 的 CreateProcessW，POSIX 照 child_process。 */
async function popen(argv: readonly string[], cwd: string | null, log: ChildLog | null): Promise<ChildLike> {
  if (process.platform === "win32") return popenWindows(argv, cwd, log);
  const child: ChildProcess = spawn(argv[0] as string, argv.slice(1), {
    cwd: cwd ?? undefined, stdio: log === null ? ["ignore", "inherit", "inherit"] : ["ignore", log.fd, log.fd],
  });
  child.on("error", () => undefined); // 起不来时 error 事件没人接会让本进程崩掉；照 Python 在这里抛
  if (child.pid === undefined) throw new PyCrash("FileNotFoundError", `[Errno 2] No such file or directory: ${pyRepr(argv[0] as string)}`);
  child.unref(); // POSIX 上 libuv 没有 Job：子进程本来就不随父进程死，unref 只是不让本进程等它
  return {
    pid: child.pid,
    poll: () => child.exitCode ?? (child.signalCode === null ? null : 1),
    get returncode() {
      return child.exitCode;
    },
  };
}

const IS_BUN = typeof (globalThis as { Bun?: unknown }).Bun !== "undefined";
const CREATE_BREAKAWAY_FROM_JOB = 0x01000000;

/**
 * Windows：不经 child_process。libuv 把不带 detached 的子进程放进它自己的 Job（KILL_ON_JOB_CLOSE），本进程一退出子进程就被杀；带 detached
 * 又多了 DETACHED_PROCESS 与 CREATE_NEW_PROCESS_GROUP。这里照 Python 的 Popen：不挂起、不另起进程组、共用控制台、不加 CREATE_NO_WINDOW。
 * 只多一位 CREATE_BREAKAWAY_FROM_JOB：本进程是启动器转交来的，在启动器的 Job 里（KILL_ON_JOB_CLOSE），换代、主任务 runner、owner-sweep
 * 要比启动器活得久，同 Python 直接跑时一样；启动器的 Job 许脱离（BREAKAWAY_OK），本进程不在 Job 里时这一位不起作用。回合、门禁、执行端
 * 不经这里，照旧留在 Job 里。只继承三个标准句柄；stdin 接 NUL，stdout、stderr 接日志（追加），没有日志时接本进程的标准句柄（本进程没有时接 NUL；Python 是一根读端
 * 关掉的管道，计划第 10 节记了这条）。线程句柄起完就关；进程句柄留到 poll 第一次拿到退出码再关，留着时 pid 也不会被复用。
 */
async function popenWindows(argv: readonly string[], cwd: string | null, log: ChildLog | null): Promise<ChildLike> {
  if (!IS_BUN) throw new Error("hub 在 Windows 上只跑在 Bun 下：起子进程要用 Win32 的 CreateProcessW（bun:ffi）");
  const api = await winProcessApi();
  const opened: bigint[] = [];
  const take = (handle: bigint | null): bigint => {
    const usable = handle ?? api.openInheritable("NUL", "append");
    opened.push(usable);
    return usable;
  };
  let spawned: Spawned;
  try {
    const stdin = take(api.openInheritable("NUL", "read"));
    const stdout = take(log === null ? api.inheritableStd("stdout") : api.openInheritable(log.path, "append"));
    const stderr = log === null ? take(api.inheritableStd("stderr")) : stdout; // stderr=STDOUT
    spawned = api.spawn(list2cmdline(argv), null, cwd, { stdin, stdout, stderr }, CREATE_BREAKAWAY_FROM_JOB);
  } catch (error) {
    if (!(error instanceof Win32Error)) throw error;
    const { name } = windowsOSError(error.winerror, api.message(error.winerror));
    throw new PyCrash(name, pyWinErrorMessage(error.winerror)); // 同 Python 的 Popen 起不来时抛的 OSError
  } finally {
    for (const handle of opened) api.close(handle); // 子进程已经继承了自己的那份
  }
  api.close(spawned.thread);
  let code: number | null = null;
  return {
    pid: spawned.pid,
    poll() {
      if (code === null && api.exited(spawned.process, 0)) {
        code = api.exitCode(spawned.process);
        api.close(spawned.process);
      }
      return code;
    },
    get returncode() {
      return code;
    },
  };
}

function returncodeOf(proc: ChildLike): PyValue {
  const code = proc.returncode ?? null;
  return code === null ? null : BigInt(code);
}

/** supervise 写进总锁目录的 mode（站主的命令据此只等主任务的锁）。 */
function writeMode(hub: Hub): void {
  writeTextAtomic(purePathStr(runnerLock(hub, null), "mode"), `supervisor${LF}`);
}

function listDir(path: string): string[] {
  return isDirectory(path) ? readdirSync(path) : [];
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}
