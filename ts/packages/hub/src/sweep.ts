// 后台回归与落地预演（迁移第 ⑤h2 片）：kit_hub.py 的 LAND_WAIT_SECONDS、sweep_window、SWEEP_SECONDS、SWEEP_WAIT_SECONDS、gate_baselines、
// sweep_gates、keep_sweep_output、regression_sweep、rehearse_landing、rehearsal_letter、owner_sweep_path、read_owner_sweep、mark_owner_moved、
// owner_sweep、TS_INSTALL_TIMEOUT、ts_install_if_stale、owner_sweep_run。结项与落地在 land.ts（⑤h1）。
// deps 只给契约用：用例当时换掉的 sweep_gates、rehearse_landing、调度器的 find_bun 与 read_kernel_impl、ts_install_if_stale 的 runner，以及
// 几个时限照记录注入；生产调用方不传。门禁基准在临时 worktree 里真跑：Python 是 subprocess.run 加 timeout（超时只杀 pytest 本身），这里照
// accept.ts 的先例经 runSupervised，超时整棵树一起结束（计划第 10 节）。
import { mkdtempSync, readFileSync, statSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { utcNow } from "@themis/base/clock";
import { readText, removeTempDir, writeTextAtomic } from "@themis/base/fsutil";
import { findBunOnPath, withFileLock } from "@themis/base/native";
import { pyCaught } from "@themis/base/pyexc";
import { PyCrash, pyGet, pyItem, pyPercentD, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { purePathName, purePathParent, purePathStr } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyStrip } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { type SuperviseOptions, type SuperviseResult, runSupervised } from "@themis/base/supervise";
import { pathArg } from "@themis/dispatcher/evidence";
import { globPaths } from "@themis/dispatcher/instruction";
import { TS_STAMP, readKernelImpl } from "@themis/dispatcher/kernel-impl";
import { depsDigest } from "../../../tools/stamp-install.mjs";
import { KERNEL, OWNER } from "./constants.ts";
import { tail } from "./contract.ts";
import { emptyCommit, pySliceHead } from "./exec.ts";
import { attemptBase } from "./gatepost.ts";
import { git } from "./kernel.ts";
import { landedMeanwhile, landingChain, onBranch } from "./land.ts";
import { DirLock, type Hub } from "./mailbox.ts";
import { KERNEL_IMPL_PATH, kernelEnv, kernelPytest, kernelPytestEnv } from "./runpd.ts";
import { type ExecDeps, REAL_EXEC_DEPS, execMarks, runMerged, scratchWorktree } from "./runexec.ts";

const LF = String.fromCharCode(10);

/** 落地等别的主任务执行端跑完的上限；后台回归挂标记、ts/ 重装也过这把锁。 */
export const LAND_WAIT_SECONDS = 3600.0;
/** 合入后门禁回归的时限：每份门禁各跑一遍 npm ci、build 与探针。 */
export const SWEEP_SECONDS = 2400;
/** 后台回归排队等前一份跑完的上限（第 68 轮）：一份最长 SWEEP_SECONDS，再留出它附带的落地预演。 */
export const SWEEP_WAIT_SECONDS = 2 * SWEEP_SECONDS;
/** 主工作区 ts/ 重装依赖的时限（第 64 轮）。 */
export const TS_INSTALL_TIMEOUT = 900;

/** 跑全部门禁基准的结果：（退出码, 输出, 跑了哪几份）。 */
export type SweepResult = [number, string, string[]];

/** 用例当时换掉、契约照记录注入的内层调用与时限；缺省是真的。 */
export interface SweepDeps extends ExecDeps {
  readonly sweepGates: (path: string, seconds: number) => SweepResult | Promise<SweepResult>;
  readonly rehearseLanding: (hub: Hub, ts: PyDict) => [boolean, string] | null | Promise<[boolean, string] | null>;
  /** pd.find_bun(kernel_env())。 */
  readonly findBun: (env: Map<string, string>) => string | null;
  /** pd.read_kernel_impl()（内核目录下的选择文件）。 */
  readonly readKernelImpl: () => PyDict;
  /** ts_install_if_stale 的 runner：签名同 pd.run_supervised。 */
  readonly runSupervised: (cmd: readonly string[], options: SuperviseOptions) => Promise<SuperviseResult>;
  /** owner_sweep_run 先调的 ts_install_if_stale。 */
  readonly tsInstallIfStale: (hub: Hub) => Promise<[boolean, string] | null>;
  /** LAND_WAIT_SECONDS：后台回归挂标记、ts/ 重装过落地锁等多久（与执行端的 landWaitSeconds 不是一回事）。 */
  readonly landLockWaitSeconds: number;
  readonly sweepSeconds: number;
  readonly sweepWaitSeconds: number;
}

export const REAL_SWEEP_DEPS: SweepDeps = {
  ...REAL_EXEC_DEPS,
  sweepGates: (path, seconds) => sweepGates(path, seconds),
  rehearseLanding: (hub, ts) => rehearseLanding(hub, ts),
  findBun: (env) => findBunOnPath(Object.fromEntries(env)),
  readKernelImpl: () => readKernelImpl(KERNEL_IMPL_PATH),
  runSupervised,
  tsInstallIfStale: (hub) => tsInstallIfStale(hub),
  landLockWaitSeconds: LAND_WAIT_SECONDS,
  sweepSeconds: SWEEP_SECONDS,
  sweepWaitSeconds: SWEEP_WAIT_SECONDS,
};

/** x or y。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);
/** value[:12]。 */
const short = (value: PyValue): string => pyStrValue(pySliceHead(value, 12));
/** text[:limit]（按码点）。 */
const head = (text: string, limit: number): string => codePoints(text).slice(0, limit).join("");

function isKind(path: string, kind: "file" | "dir"): boolean {
  try {
    const info = statSync(path);
    return kind === "file" ? info.isFile() : info.isDirectory();
  } catch {
    return false;
  }
}

/**
 * 跑全部门禁基准的后台活（站主提交之后的回归、合入后回归，连同它们附带的落地预演）也挂一份标记（第 62 轮）：落地等它跑完，它也先过
 * 落地锁、等正在落地的落完再开始。站主的 exclusive 不等这类标记（landing_blockers 的 sweeps=False）。第 68 轮：后台回归之间也排队，整段
 * 持有 .sweep 锁（持有者进程不在了就接管），再照旧短暂过落地锁挂标记。等锁超时的 HubError 原样往外抛（不像 exec_window 换成 LandBusy）。
 */
export async function withSweepWindow<T>(hub: Hub, name: string, label: string, fn: () => Promise<T>, deps: SweepDeps = REAL_SWEEP_DEPS): Promise<T> {
  const marks = execMarks(hub);
  pathMkdir(marks, true, true);
  const path = purePathStr(marks, `${name}.json`);
  const sweep = new DirLock(purePathStr(hub.root, ".sweep"), deps.sweepWaitSeconds).acquire();
  try {
    const land = new DirLock(purePathStr(hub.root, ".land"), deps.landLockWaitSeconds).acquire();
    try {
      const mark = new Map<string, PyValue>([["pid", BigInt(process.pid)], ["task", name], ["label", label], ["sweep", true], ["at", utcNow()]]);
      writeTextAtomic(path, `${dumps(mark)}${LF}`);
    } finally {
      land.release();
    }
    try {
      return await fn();
    } finally {
      try {
        unlinkSync(path);
      } catch (error) {
        if (!pyCaught(error, ["OSError"])) throw error;
      }
    }
  } finally {
    sweep.release();
  }
}

/** 仓库里的门禁基准测试（tests/test_gate_*_baseline.py），相对路径用正斜杠、按码点排序。 */
export function gateBaselines(root: string): string[] {
  return globPaths(purePathStr(root, "tests"), ["test_gate_*_baseline.py"]).map((path) => `tests/${purePathName(path)}`).sort(cmpCodePoints);
}

/** 在 path 里跑全部门禁基准（白盒不算）；返回（退出码, 输出, 跑了哪几份）。 */
export async function sweepGates(path: string, seconds = SWEEP_SECONDS): Promise<SweepResult> {
  const tests = gateBaselines(path);
  if (!tests.length) return [0, "没有门禁基准可跑", tests];
  const dir = mkdtempSync(join(tmpdir(), "themis-sweep-"));
  try {
    const out = join(dir, "output");
    const result = await runSupervised([...kernelPytest(), "-q", "-rfE", ...tests], {
      cwd: path, env: [...kernelPytestEnv()], stdout: { path: out, how: "create-new" }, stderr: "stdout", timeout: seconds, grace: 0, handleSignals: false,
    });
    if (result.timed_out) return [-1, `超过 ${pyPercentD(seconds)} 秒没有跑完`, tests];
    if (result.spawn_error !== null) throw new PyCrash("OSError", result.spawn_error);
    return [result.exit_code as number, pyDecodeUtf8Replace(readFileSync(out)), tests];
  } finally {
    await removeTempDir(dir);
  }
}

/**
 * 门禁基准的全文每次覆盖写一份（第 133 轮）。记录与信只留最后 15 行：站主扫描在临时 worktree 里红过两次，git 自己的报错都在被截掉的
 * 那段里。上级目录由 writeTextAtomic 建。
 */
export function keepSweepOutput(path: string, out: string): void {
  writeTextAtomic(path, out);
}

/**
 * 在合入后的末端上跑全部门禁基准（第 20 轮）。并行的两个主任务各自只验过自己合同的检查，合在一起可能互相打破。在临时 worktree 里跑，
 * 不碰主工作区。
 */
export async function regressionSweep(hub: Hub, ts: PyDict, deps: SweepDeps = REAL_SWEEP_DEPS): Promise<[boolean, string]> {
  if (!gateBaselines(hub.repo).length) return [true, "合入后没有门禁基准可跑"];
  const tip = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  const [code, out, tests] = await scratchWorktree(hub, "sweep", tip, (path) => deps.sweepGates(path, deps.sweepSeconds), deps);
  keepSweepOutput(purePathStr(hub.taskDir(pyStrValue(pyItem(ts, "task"))), "regression-sweep.log"), out);
  ts.set("regression", new Map<string, PyValue>([["head", tip], ["exit", BigInt(code)], ["tests", [...tests]], ["tail", tail(out, 15n)], ["at", utcNow()]]));
  await hub.appendEvent("regression.swept", [["task", pyItem(ts, "task")], ["head", tip], ["exit", BigInt(code)]]);
  const summary = `合入后的门禁回归（${tests.length} 份，末端 ${short(tip)}）：${pyStrip(tail(out, 1n)) || "没有输出"}`;
  return [code === 0, code === 0 ? summary : `${summary}${LF}${tail(out, 15n)}`];
}

/**
 * 落地预演（第 30 轮）：在临时 worktree 里照结项的做法拼出“当前末端 + 基准测试 + 返工链 + 候选”，跑全部门禁基准。分支在任务期间没动、
 * 或者这个候选在这个末端上预演过，就不预演（交回 None）；否则交回（通过与否, 摘要），结果记在 ts["rehearsal"]。
 */
export async function rehearseLanding(hub: Hub, ts: PyDict, deps: SweepDeps = REAL_SWEEP_DEPS): Promise<[boolean, string] | null> {
  const given = pyGet(pyItem(ts, "exec"), "run_dir");
  if (!pyTruthy(given) || !pyTruthy(pyGet(pyItem(ts, "exec"), "check_ok")) || !isKind(pathArg(given), "dir")) return null;
  const runDir = pathArg(given);
  const tip = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  // 末端就是候选 check --fresh 时的那个：没有新东西要合。照 Python 的元组先把两项都算出来（attempt_base 总会被调到）
  const [baseHead, attempted] = [pyItem(ts, "base_head"), attemptBase(ts, runDir)];
  if (pyEq(tip, baseHead) || pyEq(tip, attempted)) return null;
  const seen = or(pyGet(ts, "rehearsal"), new Map());
  if (pyEq(pyGet(seen, "head"), tip) && pyEq(pyGet(seen, "run_dir"), runDir)) return null;
  const commits = [pyGet(pyItem(ts, "oracle"), "sha"), ...landingChain(hub, ts, runDir).map((link) => pyItem(link, "commit"))].filter(pyTruthy);
  let problem: string | null = null;
  let summary = "";
  await scratchWorktree(hub, "rehearse", tip, async (path) => {
    for (const sha of commits) {
      if (onBranch(hub, sha, path) || emptyCommit(hub, sha as string)) continue;
      const [code, out] = runMerged(["git", "cherry-pick", "-x", sha as string], path);
      if (code !== 0) {
        problem = `提交 ${short(sha)} 挑不到末端 ${short(tip)} 上：${LF}${tail(pyDecodeUtf8Replace(out), 8n)}`;
        break;
      }
    }
    // 第 44 轮：接着返工提交改、一行没动的 attempt，补丁是空的；git apply 空补丁报“No valid patches in input”。活都在返工链里，上面已经挑过了
    const patch = purePathStr(runDir, "candidate.patch");
    if (problem === null && pyStrip(readText(patch))) {
      const [code, out] = runMerged(["git", "apply", "--3way", "--whitespace=nowarn", patch], path);
      if (code !== 0) problem = `候选补丁（${purePathName(runDir)}）打不到末端 ${short(tip)} 上：${LF}${tail(pyDecodeUtf8Replace(out), 8n)}`;
    }
    if (problem === null) {
      const [code, out, tests] = await deps.sweepGates(path, deps.sweepSeconds);
      summary = `末端 ${short(tip)} 加上 ${purePathName(runDir)} 的候选，全部门禁基准（${tests.length} 份）：${pyStrip(tail(out, 1n)) || "没有输出"}`;
      if (code !== 0) problem = `${summary}${LF}${tail(out, 15n)}`;
    }
  }, deps);
  const ok = problem === null;
  ts.set("rehearsal", new Map<string, PyValue>([["head", tip], ["run_dir", runDir], ["ok", ok], ["at", utcNow()]]));
  await hub.appendEvent("landing.rehearsed", [["task", pyItem(ts, "task")], ["head", tip], ["run_dir", runDir], ["ok", ok]]);
  return ok ? [true, summary] : [false, `${problem as string | null}${landedMeanwhile(hub, ts, tip)}`];
}

/** 落地预演没过：写信给站主。不是执行端的错（候选在自己的基线上过了），要站主协调：收窄写得太宽的门禁断言，或者让后落地的一片返工。 */
export async function rehearsalLetter(hub: Hub, ts: PyDict, summary: string, why: string): Promise<void> {
  const task = pyStrValue(pyItem(ts, "task"));
  await hub.deliver(new Map([["from", KERNEL], ["to", OWNER], ["task-id", task], ["in-reply-to", "none"], ["type", "阻塞"]]), new Map<string, PyValue>([
    ["摘要", `${task} 的候选落地预演没过（${why}）：现在结项，integrate 会在末端上红`], ["提交", "无"], ["验证", head(summary, 1500)], ["偏离", "无"],
    ["需协调人决定", "请站主处理：收窄写得太宽的门禁断言，或者协调哪一片返工；处理完之前别结项"], ["证据", `.agent/mailbox/ledger/state.json（${task} 的 rehearsal）`],
  ]));
}

export const ownerSweepPath = (hub: Hub): string => purePathStr(hub.root, "ledger", "owner-sweep.json");

/** owner-sweep.json：读不出、不是合法 JSON 或不是对象时都是 {}。 */
export function readOwnerSweep(hub: Hub): PyDict {
  let data: PyValue;
  try {
    data = loads(readText(ownerSweepPath(hub)) || "{}");
  } catch (error) {
    if (!pyCaught(error, ["ValueError"])) throw error;
    return new Map();
  }
  return data instanceof Map ? data : new Map();
}

const writeOwnerSweep = (hub: Hub, data: PyDict): void =>
  writeTextAtomic(ownerSweepPath(hub), `${dumps(data, { ensureAscii: false, indent: 2, sortKeys: true })}${LF}`);
const ownerSweepLock = (hub: Hub): string => purePathStr(purePathParent(ownerSweepPath(hub)), ".owner-sweep.lock");

/**
 * 站主经 exclusive 动了 HEAD（第 61 轮）：记下要在新末端上跑的门禁回归与落地预演，由 supervisor 起子进程在后台跑（owner_sweep）。连着
 * 动了几次只跑最新的末端，since 留着第一次之前的末端，信里列出这期间的提交。
 */
export async function markOwnerMoved(hub: Hub, before: string, after: string, command: readonly string[]): Promise<void> {
  pathMkdir(purePathParent(ownerSweepPath(hub)), true, true);
  await withFileLock(ownerSweepLock(hub), () => {
    const data = readOwnerSweep(hub);
    const since = pyTruthy(pyGet(data, "pending")) ? pyGet(data, "since") : before;
    const updates: [string, PyValue][] = [["pending", true], ["head", after], ["since", since], ["command", command.slice(0, 6)], ["at", utcNow()]];
    for (const [key, value] of updates) data.set(key, value);
    writeOwnerSweep(hub, data);
  });
  await hub.appendEvent("owner.moved", [["before", before], ["after", after]]);
}

/**
 * 站主的提交之后的门禁回归与落地预演（第 61 轮）：在临时 worktree 里跑全部门禁基准，再给手上有过了检查的候选的主任务各做一次落地预演；
 * 红了写信给站主。没有待跑的交回 None，否则交回（门禁回归通过与否, 摘要）。
 */
export async function ownerSweep(hub: Hub, deps: SweepDeps = REAL_SWEEP_DEPS): Promise<[boolean, string] | null> {
  const marker = readOwnerSweep(hub);
  if (!pyTruthy(pyGet(marker, "pending"))) return null;
  return withSweepWindow(hub, "owner-sweep", "站主提交之后的门禁回归", () => ownerSweepRun(hub, marker, deps), deps); // 第 62 轮：与结项互斥
}

/**
 * 主工作区 ts/ 的依赖跟上末端（第 64 轮）：选择文件至少有一项是 ts，而依赖清单的合并哈希与装好戳记对不上，就在落地锁里跑一次
 * bun install --frozen-lockfile，postinstall 写新的戳记；失败写阻塞信。不需要装时交回 None，否则交回（装好与否, 摘要）。
 */
export async function tsInstallIfStale(hub: Hub, deps: SweepDeps = REAL_SWEEP_DEPS): Promise<[boolean, string] | null> {
  const root = purePathStr(hub.repo, "ts");
  if (!isKind(purePathStr(root, "package.json"), "file") || ![...deps.readKernelImpl().values()].includes("ts")) return null;
  const stampPath = purePathStr(root, TS_STAMP);
  const stamped = (): boolean => {
    let stamp: PyValue;
    try {
      stamp = loads(readText(stampPath) || "{}");
    } catch (error) {
      if (!pyCaught(error, ["ValueError"])) throw error;
      return false;
    }
    return stamp instanceof Map && pyGet(stamp, "deps_sha256") === depsDigest(root);
  };
  if (stamped()) return null;
  const bun = deps.findBun(kernelEnv());
  let ok: boolean;
  let summary: string;
  if (bun === null) {
    [ok, summary] = [false, "找不到 Bun：PATH 上既没有 bun.exe，也没有 npm 的 bun.cmd 垫片"];
  } else {
    const land = new DirLock(purePathStr(hub.root, ".land"), deps.landLockWaitSeconds).acquire();
    let result: SuperviseResult;
    let text: string;
    try {
      const dir = mkdtempSync(join(tmpdir(), "themis-ts-install-"));
      try {
        const out = join(dir, "output");
        result = await deps.runSupervised([bun, "install", "--frozen-lockfile"], {
          cwd: root, env: [...kernelEnv()], stdout: { path: out, how: "create-new" }, stderr: "stdout", timeout: TS_INSTALL_TIMEOUT,
        });
        text = isKind(out, "file") ? pyDecodeUtf8Replace(readFileSync(out)) : "";
      } finally {
        await removeTempDir(dir);
      }
    } finally {
      land.release();
    }
    ok = result.exit_code === 0 && !result.timed_out && stamped();
    const how = ok ? "装好了" : `没装好（退出码 ${result.exit_code === null ? "None" : result.exit_code}${result.timed_out ? "，超时" : ""}）`;
    summary = `主工作区 ts/ 重装依赖（bun install --frozen-lockfile）：${how}${LF}${tail(text, 10n)}`;
  }
  await hub.appendEvent("ts.installed", [["ok", ok]]);
  if (!ok) {
    await hub.deliver(new Map([["from", KERNEL], ["to", OWNER], ["task-id", "none"], ["in-reply-to", "none"], ["type", "阻塞"]]), new Map<string, PyValue>([
      ["摘要", "主工作区 ts/ 的依赖跟不上末端：转交给 TS 的命令（status、logs）会报依赖不一致"], ["提交", "无"], ["验证", head(summary, 1500)], ["偏离", "无"],
      ["需协调人决定", "请站主在 ts/ 下运行 bun install --frozen-lockfile，看报错处理"], ["证据", stampPath],
    ]));
  }
  return [ok, summary];
}

/** owner_sweep 的本体：先让主工作区 ts/ 的依赖跟上末端（第 64 轮），再在当前末端上跑全部门禁基准，再给过了检查的候选各做一次落地预演。 */
export async function ownerSweepRun(hub: Hub, marker: PyDict, deps: SweepDeps = REAL_SWEEP_DEPS): Promise<[boolean, string]> {
  await deps.tsInstallIfStale(hub);
  const tip = pyStrip(git(["rev-parse", "HEAD"], hub.repo));
  const [code, out, tests] = await scratchWorktree(hub, "owner-sweep", tip, (path) => deps.sweepGates(path, deps.sweepSeconds), deps);
  // 不叫 owner-sweep.log：runners/ 下有同名的、子进程自己的输出，看的人容易拿错
  keepSweepOutput(purePathStr(purePathParent(ownerSweepPath(hub)), "owner-sweep-pytest.log"), out);
  await withFileLock(ownerSweepLock(hub), () => {
    const data = readOwnerSweep(hub);
    data.set("last", new Map<string, PyValue>([["head", tip], ["exit", BigInt(code)], ["tests", [...tests]], ["tail", tail(out, 15n)], ["at", utcNow()]]));
    if (pyEq(pyGet(data, "head"), tip)) data.set("pending", false); // 跑的期间站主又动了 HEAD：留着待跑，下一轮跑新的末端
    writeOwnerSweep(hub, data);
  });
  await hub.appendEvent("owner.swept", [["head", tip], ["exit", BigInt(code)]]);
  const summary = `站主的提交之后，末端 ${short(tip)} 上的全部门禁基准（${tests.length} 份）：${pyStrip(tail(out, 1n)) || "没有输出"}`;
  if (code !== 0) {
    const since = pyGet(marker, "since");
    const commits = pyTruthy(since) ? pyStrip(git(["log", "--oneline", "-n", "10", `${pyStrValue(since)}..${tip}`], hub.repo, false)) : "";
    await hub.deliver(new Map([["from", KERNEL], ["to", OWNER], ["task-id", "none"], ["in-reply-to", "none"], ["type", "阻塞"]]), new Map<string, PyValue>([
      ["摘要", `站主的提交之后，门禁回归在末端 ${short(tip)} 上没过：主任务落地之前就会在这里红`], ["提交", "无"], ["验证", head(`${summary}${LF}${tail(out, 15n)}`, 1500)],
      ["偏离", commits ? head(`这期间站主合入的提交：${LF}${commits}`, 600) : "无"], ["需协调人决定", "请站主处理：收窄写得太宽的门禁断言，或者改回刚才的提交"],
      ["证据", ".agent/mailbox/ledger/owner-sweep.json；全文在 .agent/mailbox/ledger/owner-sweep-pytest.log"],
    ]));
  }
  for (const task of [...hub.loadState().tasks().keys()].map(String).sort(cmpCodePoints)) {
    const state = hub.loadState(); // 每次现读：预演一次要几分钟，runner 这期间照常写
    const ts = pyItem(state.tasks(), task) as PyDict;
    if (pyGet(ts, "status") !== "active") continue;
    const rehearsed = await deps.rehearseLanding(hub, ts);
    if (rehearsed === null) continue;
    await hub.saveState(state);
    if (!rehearsed[0]) await rehearsalLetter(hub, ts, rehearsed[1], "站主的提交之后");
  }
  return [code === 0, summary];
}
