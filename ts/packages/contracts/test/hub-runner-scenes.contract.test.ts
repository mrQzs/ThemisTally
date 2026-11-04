// 第 ⑤j2 片的手写对照（采样那份在 hub-runner.contract.test.ts）：临时仓库上摆好信箱，三边各自先原地放回再跑，交回值、文件、账本、git 状态、
// 调用之后的参数与 stdout、stderr 逐字比；账本里进程自己的 pid 照 pidNormalized 换成占位。只补采样走不到的：
//   - 采样跳过的：spawn_runner 真起子进程（1097）；锁被另一个进程（真的 Python 子进程，kit_hub.DirLock）拿着时的 cmd_run、owner_sweep_tick、
//     supervise_tick（4106、4578、4652、4727）；
//   - 用例经 REAL_KERNEL_CHANGES 调、采样器包不到的 kernel_changes（7873、7893），与同样几种情形的 kernel_dirty；
//   - E3：选择文件的 hub 是 ts 时内核文件多出 TS 的源码与依赖清单（只有 TS 有）；
//   - 变异检验补的：采样、跑到静止都走不到的分支（剧本交回内层函数，记下的调用三边比），每条 it 的标题后写了对着哪几条变异。
// 不写转义序列。
import type { ChildProcess } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import { cmpCodePoints } from "@themis/base/pyre";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { KERNEL } from "@themis/hub/constants";
import { Hub, canonicalState } from "@themis/hub/mailbox";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, REPLAY_TIMEOUT, TS_BUN, TS_NODE, runBatch } from "./harness.ts";
import { AT, CR, LF, agreeFlow, flow, kernelPython, py, returned, scene, written } from "./flow-fixtures.ts";
import { git, newRepo, put, removeCreated, tempDir } from "./repo-fixtures.ts";
import { BASE_FILES, BOX, failure, letter, value } from "./engine-fixtures.ts";
import { holdLock, pidNormalized } from "./runner-fixtures.ts";

afterAll(removeCreated);

const NOTHING = { write: {}, delete: [] };
/** 手写的一次内层调用（采样的写法）：要核对的参数、交回值；调用期间没有文件改动。 */
const inner = (fn: string, fields: Record<string, unknown>, value: unknown): unknown => ({ fn, ...fields, value: toTagged(py(value)), files: NOTHING });
const alive = (pid: number, answer: boolean): unknown => inner("pid_alive", { pid }, answer);
/** 账本里进程自己的 pid 换成占位：各边只换自己交回的 self_pid。 */
const ownPid = (state: Record<string, unknown>): unknown => pidNormalized(state, new Set([Number(state["self_pid"])]));
const stdoutOf = (state: Record<string, unknown> | undefined): string => state?.["stdout"] as string;
const events = (state: Record<string, unknown> | undefined): Record<string, unknown>[] =>
  Buffer.from(state?.["ledger"] as string, "base64").toString("utf8").split(LF).filter(Boolean).map((line) => JSON.parse(line) as Record<string, unknown>);
const hubScene = (more: (repo: string) => void = () => undefined) => scene(BASE_FILES, (repo) => {
  new Hub(repo).ensure();
  more(repo);
}, false);
const boxPath = (repo: string, rel: string): string => join(repo, ...`${BOX}/${rel}`.split("/"));

/** 状态里有这几个主任务（各照 make_ts 建）。 */
function tasksIn(repo: string, names: readonly string[], head: string): void {
  const tasks = new Map<string, PyValue>(names.map((name) => [name, newTaskState(name, name.toLowerCase(), `主任务 ${name}`, head, true, AT)]));
  put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map<string, PyValue>([["tasks", tasks]])));
}

/**
 * 子进程读自己 PEB 里 RTL_USER_PROCESS_PARAMETERS.ConsoleFlags 并打印（x64：PEB+0x20 是 ProcessParameters，其中 +0x18 是 ConsoleFlags；
 * 1 是忽略 Ctrl+C，CREATE_NEW_PROCESS_GROUP 会替新进程设上）。
 */
const CONSOLE_FLAGS = "import ctypes; info = (ctypes.c_void_p * 6)(); ctypes.WinDLL('ntdll').NtQueryInformationProcess(ctypes.c_void_p(-1), 0, info, 48, None); "
  + "params = ctypes.c_void_p.from_address(info[1] + 32).value; print(ctypes.c_uint32.from_address(params + 24).value)";

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

describe("第 ⑤j2 片：采样跳过的（手写）", () => {
  it("spawn_runner：真起子进程，立即交回 0；账本记下自己的 pid 与子进程号，交回时子进程还在跑（1097）", () => {
    const sc = hubScene();
    const request = flow("spawn_runner", sc, [[kernelPython(), "-c", "import time; time.sleep(60)"]]);
    const children: number[] = [];
    try {
      const shown = IMPLS.map((impl) => {
        const began = Date.now();
        const state = runBatch(impl, [request], REPLAY_TIMEOUT)[0]?.["value"] as Record<string, unknown>;
        const elapsed = Date.now() - began;
        const respawned = events(state).filter((event) => event["event"] === "runner.respawned");
        const child = Number(respawned[0]?.["child"]);
        children.push(child);
        expect([impl.name, returned(state), elapsed < 15_000, respawned.length, isAlive(child)]).toEqual([impl.name, 0n, true, 1, true]);
        // 子进程号各边不同：换成占位再比
        const ledger = Buffer.from(Buffer.from(state["ledger"] as string, "base64").toString("utf8").split(`"child": ${child}`).join(`"child": "<child>"`), "utf8");
        return ownPid({ ...state, ledger: ledger.toString("base64"), files: "<files>" });
      });
      expect(shown[1]).toEqual(shown[0]);
      expect(shown[2]).toEqual(shown[0]);
    } finally {
      for (const child of children) {
        if (isAlive(child)) process.kill(child);
      }
    }
  }, 1_800_000);

  it("spawn_runner（bun）：起子进程的那个进程退出之后，子进程照样跑完自己的事（Windows 上不进 libuv 的 Job）", () => {
    const sc = hubScene();
    const marker = join(tempDir("respawn-marker"), "child.txt");
    // 子进程先睡 5 秒再写标记：那时探针早已退出（runBatch 等探针退出才交回）
    const program = "import sys, time; time.sleep(5); open(sys.argv[1], 'w').write('alive'); time.sleep(30)";
    const state = runBatch(TS_BUN, [flow("spawn_runner", sc, [[kernelPython(), "-c", program, marker]])], REPLAY_TIMEOUT)[0]?.["value"] as Record<string, unknown>;
    const child = Number(events(state).find((event) => event["event"] === "runner.respawned")?.["child"]);
    try {
      for (let waited = 0; !existsSync(marker) && waited < 200; waited += 1) sleepSync(100);
      expect([returned(state), existsSync(marker) ? readFileSync(marker, "utf8") : null, isAlive(child)]).toEqual([0n, "alive", true]);
    } finally {
      if (isAlive(child)) process.kill(child);
    }
  }, 600_000);

  it("cmd_run：别的进程拿着主任务的 runner 锁时，串行的 hub 不起（4106）", () => {
    const held: ChildProcess[] = [];
    try {
      const sc = hubScene((repo) => holdLock(boxPath(repo, ".runners/T002"), held));
      const args = { repo: sc.repo, max_steps: 1, idle_exit: 0, poll: 0, settle: 0, no_restart: true, parallel: 1, task: null };
      const [state] = agreeFlow([flow("cmd_run", sc, [args], {
        inner: [inner("kernel_changes", { paths: null }, []), alive(held[0]?.pid as number, true)], replaced: ["kernel_changes", "pid_alive"],
      })], ownPid, REPLAY_TIMEOUT);
      expect(failure(state)).toEqual(["HubError", "这些主任务各有 runner 在跑（并行模式）：T002。串行的 hub 不能同时跑"]);
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);

  it("owner_sweep_tick：命令行手动起的 owner-sweep 拿着锁时不起；上一个子进程退出的那一轮先记 owner_sweep.exited（4578）", () => {
    const held: ChildProcess[] = [];
    try {
      const sc = hubScene((repo) => {
        put(repo, `${BOX}/ledger/owner-sweep.json`, `${JSON.stringify({ pending: true, head: "b".repeat(40), since: "a".repeat(40) })}${LF}`);
        holdLock(boxPath(repo, ".owner-sweep"), held);
      });
      const holder = held[0]?.pid as number;
      const proc = { __proc__: 0, pid: 4242 };
      const [idle, exited] = agreeFlow([
        flow("owner_sweep_tick", sc, [{ proc: null }], { inner: [alive(holder, true)], replaced: ["pid_alive"] }),
        flow("owner_sweep_tick", sc, [{ proc }], { inner: [inner("proc.poll", { proc: 0 }, 0), alive(holder, true)], replaced: ["pid_alive"] }),
      ], ownPid, REPLAY_TIMEOUT);
      expect([returned(idle), events(idle)]).toEqual([false, []]);
      expect([returned(exited), events(exited).map((event) => [event["event"], event["code"]])]).toEqual([false, [["owner_sweep.exited", 0]]]);
      expect(fromTagged((exited?.["args_after"] as Record<string, Tagged>)["holder"] as Tagged)).toEqual(new Map([["proc", null]]));
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);

  it("supervise_tick：上一代起的、还活着的主任务 runner 占一个名额，不重复起它（4652）；没有待办时它在跑也算忙（4727）", () => {
    const held: ChildProcess[] = [];
    try {
      const sc = scene(BASE_FILES, (repo, _wt, head) => {
        new Hub(repo).ensure();
        tasksIn(repo, ["T001", "T002", "T003"], head);
        holdLock(boxPath(repo, ".runners/T001"), held);
      }, false);
      const holder = held[0]?.pid as number;
      const args = { max_steps: 10, poll: 0, settle: 0 };
      const requeue = inner("requeue_interrupted", { repo: new Hub(sc.repo).repo, skip: [] }, []);
      const spawned = inner("spawn_task_runner", { repo: new Hub(sc.repo).repo, task: "T002", args: toTagged(py(args)) }, { __proc__: 0, pid: 4321 });
      const replaced = ["pid_alive", "requeue_interrupted", "tasks_with_work", "kernel_dirty", "spawn_task_runner"];
      const [busy, quiet] = agreeFlow([
        flow("supervise_tick", sc, [args, 2, {}, {}], {
          inner: [alive(holder, true), requeue, inner("tasks_with_work", { repo: new Hub(sc.repo).repo }, ["T001", "T002", "T003"]),
            inner("kernel_dirty", { paths: null }, false), spawned],
          replaced,
        }),
        flow("supervise_tick", sc, [args, 2, {}, {}], {
          inner: [alive(holder, true), requeue, inner("tasks_with_work", { repo: new Hub(sc.repo).repo }, [])], replaced,
        }),
      ], ownPid, REPLAY_TIMEOUT);
      expect(returned(busy)).toEqual([["T001", "T002", "T003"], 2n, 1n]);
      expect(stdoutOf(busy)).toBe(`起 T002 的 runner（pid 4321）${LF}`);
      expect(returned(quiet)).toEqual([[], 1n, 0n]);
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);
});

describe("第 ⑤j2 片：采样没调到的命令与分支（手写）", () => {
  it("owner-sweep：没有待跑的说一句；另一个进程拿着 .owner-sweep 时说已经有一个在跑，都照常退出", () => {
    const held: ChildProcess[] = [];
    try {
      const idle = hubScene();
      const busy = hubScene((repo) => {
        put(repo, `${BOX}/ledger/owner-sweep.json`, `${JSON.stringify({ pending: true, head: "b".repeat(40), since: "a".repeat(40) })}${LF}`);
        holdLock(boxPath(repo, ".owner-sweep"), held);
      });
      const [first, second] = agreeFlow([flow("cmd_owner_sweep", idle, [{ repo: idle.repo }]), flow("cmd_owner_sweep", busy, [{ repo: busy.repo }])],
        ownPid, REPLAY_TIMEOUT);
      expect([returned(first), stdoutOf(first)]).toEqual([0n, `没有待跑的${LF}`]);
      expect([returned(second), stdoutOf(second).startsWith("已经有一个在跑：")]).toEqual([0n, true]);
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);

  it("exclusive：命令的退出码原样交回；命令起不来照 Python 报 FileNotFoundError", () => {
    const exits = hubScene();
    const missing = hubScene();
    const [first, second] = agreeFlow([
      flow("cmd_exclusive", exits, [{ repo: exits.repo, command: ["--", kernelPython(), "-c", "import sys; sys.exit(4)"], wait: 0 }]),
      flow("cmd_exclusive", missing, [{ repo: missing.repo, command: ["--", "no-such-program-themis"], wait: 0 }]),
    ], ownPid, REPLAY_TIMEOUT);
    expect(returned(first)).toBe(4n);
    expect(failure(second)[0]).toBe("FileNotFoundError");
  }, 1_800_000);

  it("选择文件（只有 TS）：坏了交回 {}，内核文件照 hub 是 python 列；合法的照读；不在时各部分都是 python", () => {
    const dir = tempDir("selection");
    put(dir, "broken.json", "{");
    put(dir, "ts.json", JSON.stringify({ schema_version: 1, readonly: "ts", config: "ts", dispatcher: "ts", hub: "ts" }));
    const python = new Map([["hub", "python"]]);
    for (const impl of [TS_NODE, TS_BUN]) {
      const results = runBatch(impl, [
        ...["broken.json", "ts.json", "missing.json"].map((name) => ({ op: "hub.contract", fn: "kernel_selection", args: [toTagged(join(dir, name))] })),
        { op: "hub.contract", fn: "kernel_files", args: [toTagged(new Map() as PyDict)] }, { op: "hub.contract", fn: "kernel_files", args: [toTagged(python)] },
      ]);
      const values = results.map((result) => fromTagged(result["value"] as Tagged) as PyDict);
      expect([values[0], values[1]?.get("hub"), values[2]?.get("hub")], impl.name).toEqual([new Map(), "ts", "python"]);
      expect(values[3], impl.name).toEqual(values[4]);
    }
  }, 600_000);
});

describe("第 ⑤j2 片：变异检验补的（手写，剧本交回内层函数、记下的调用三边比）", () => {
  /** cmd_run 的参数：串行、不重启、一轮睡 0.5 秒；more 覆盖。 */
  const runArgs = (repo: string, more: Record<string, unknown> = {}) =>
    ({ repo, task: null, max_steps: 5, idle_exit: 0, poll: 0.5, settle: 0, no_restart: true, parallel: 1, allow_dirty_kernel: false, ...more });
  /** 内核指纹：起步时取一次，之后每轮比一次；共取 n 次，第 n 次变了。 */
  const fingerprints = (n: number): unknown[] => Array.from({ length: n }, (_, index) => value(index === n - 1 ? "b" : "a"));
  /** 内核指纹一直不变，共取 n 次。 */
  const steady = (n: number): unknown[] => Array.from({ length: n }, () => value("a"));
  /** 内核干净；串行的 hub 起步时没有要放回的。 */
  const quiet = { kernel_changes: [value([])], requeue_interrupted: [value([])] };
  const calls = (state: Record<string, unknown> | undefined, fn: string): Record<string, unknown>[] =>
    (state?.["scripted_calls"] as Record<string, unknown>[]).filter((call) => call["fn"] === fn);
  const kinds = (state: Record<string, unknown> | undefined): unknown[] => events(state).map((event) => event["event"]);
  const seconds = (state: Record<string, unknown> | undefined): unknown[] => calls(state, "sleep").map((call) => call["seconds"]);
  /** 状态里有 T001、T002 两个主任务，再照 more 摆。 */
  const twoTasks = (more: (repo: string) => void) => scene(BASE_FILES, (repo, _wt, head) => {
    new Hub(repo).ensure();
    tasksIn(repo, ["T001", "T002"], head);
    more(repo);
  }, false);
  /** exec-step 里一封执行端跑完的信（结项信是“通过”）；n 区分同一个信箱里的几封（未读照名字排）。 */
  const execLetter = (repo: string, taskId: string, kind: string, n = 0): void =>
    void letter(repo, "exec-step", `20261101T000000000000Z-kernel-00000${n}`, KERNEL, taskId, kind);
  /** 别的主任务的执行标记，持有进程的死活照记录注入。 */
  const BLOCKER = 4242;
  const execMark = (repo: string, task: string): void => put(repo, `${BOX}/ledger/exec-active/${task}.json`, JSON.stringify({ task, pid: BLOCKER }));

  it("cmd_run 的结项信：被挡两轮只记一次、只说一次，每轮睡 poll 秒；落成算一件事；不是“通过”的、--task 时别的主任务的不办（R39–R44）", () => {
    const blocked = twoTasks((repo) => {
      execLetter(repo, "T001-5-exec", "通过");
      execMark(repo, "T002");
    });
    const landed = twoTasks((repo) => execLetter(repo, "T001-5-exec", "通过"));
    const rework = twoTasks((repo) => execLetter(repo, "T001-5-exec", "返工"));
    const other = twoTasks((repo) => execLetter(repo, "T002-5-exec", "通过"));
    const step = { "Engine.step": [value(false)] };
    const [deferred, done, skipped, own] = agreeFlow([
      { ...flow("cmd_run", blocked, [runArgs(blocked.repo)], { inner: [alive(BLOCKER, true), alive(BLOCKER, true)], replaced: ["pid_alive"] }),
        scripted: { ...quiet, code_fingerprint: fingerprints(4), sleep: [value(null), value(null)] } },
      // 落成：finalize 照剧本交回没过，handle_pass 只给站主投一封阻塞信；after_land 见主任务不是 done 就回
      { ...flow("cmd_run", landed, [runArgs(landed.repo)]), scripted: { ...quiet, ...step, code_fingerprint: steady(3), finalize: [value([false, "integrate 被拒"])] } },
      { ...flow("cmd_run", rework, [runArgs(rework.repo)]), scripted: { ...quiet, ...step, code_fingerprint: steady(2) } },
      { ...flow("cmd_run", other, [runArgs(other.repo, { task: "T001" })]), scripted: { ...quiet, ...step, code_fingerprint: steady(2) } },
    ], ownPid, REPLAY_TIMEOUT);
    expect(kinds(deferred)).toEqual(["runner.started", "finalize.deferred", "runner.code_changed", "runner.stopped"]);
    expect(seconds(deferred)).toEqual([0.5, 0.5]);
    expect(stdoutOf(deferred).split(LF).filter((line) => line.startsWith("结项等别的执行端跑完再落地："))).toEqual(["结项等别的执行端跑完再落地：T002 的执行端"]);
    expect([events(done).at(-1)?.["steps"], stdoutOf(done).endsWith(`hub 退出：处理了 1 件事；站主未读 1 封${LF}`)]).toEqual([1, true]);
    for (const state of [skipped, own]) expect([calls(state, "Engine.step").length, events(state).at(-1)?.["steps"]]).toEqual([1, 0]);
  }, 1_800_000);

  it("cmd_run 的等待：没到 idle_exit 不退、照 poll 睡；内核变了等落定时每次至少睡 0.1 秒，落定了另起一个 hub（R25、R47）", () => {
    const idle = hubScene();
    const settle = hubScene();
    const [now, waited, restarted] = agreeFlow([
      // 前提：同一个信箱 idle_exit 是 0 时空闲就退（没有扣着的信，runner_may_idle_exit 是真），下一条才分得出等不等 idle_exit
      { ...flow("cmd_run", idle, [runArgs(idle.repo)]), scripted: { ...quiet, code_fingerprint: steady(2), "Engine.step": [value(false)] } },
      { ...flow("cmd_run", idle, [runArgs(idle.repo, { idle_exit: 3600 })]),
        scripted: { ...quiet, code_fingerprint: fingerprints(3), "Engine.step": [value(false)], sleep: [value(null)] } },
      { ...flow("cmd_run", settle, [runArgs(settle.repo, { no_restart: false, settle: 5, poll: 0.05 })]),
        scripted: { ...quiet, code_fingerprint: fingerprints(2), kernel_dirty: [value(true), value(false)], sleep: [value(null)], spawn_runner: [value(0)] } },
    ], ownPid, REPLAY_TIMEOUT);
    expect(kinds(now)).toEqual(["runner.started", "runner.stopped"]);
    expect([kinds(waited), calls(waited, "Engine.step").length, seconds(waited)]).toEqual([["runner.started", "runner.code_changed", "runner.stopped"], 1, [0.5]]);
    expect([returned(restarted), seconds(restarted), calls(restarted, "spawn_runner").length]).toEqual([0n, [0.1], 1]);
  }, 1_800_000);

  it("⑤j3：经启动器转交时，串行 hub 与 supervisor 换代起的是启动器给的 Python 与 kit_hub.py（只有 TS：context 是转交才有的）", () => {
    // 两个标记路径不存在、也不会被起：spawn_runner 照剧本交回，命令行照原样记下
    const context = { executable: "C:/launcher-mark/python.exe", kit_hub: "C:/launcher-mark/kit_hub.py" };
    const serial = hubScene();
    const parallel = hubScene();
    const requests = [
      { ...flow("cmd_run", serial, [runArgs(serial.repo, { no_restart: false, settle: 5, poll: 0.05 })]), context,
        scripted: { ...quiet, code_fingerprint: fingerprints(2), kernel_dirty: [value(false)], spawn_runner: [value(0)] } },
      { ...flow("cmd_run", parallel, [runArgs(parallel.repo, { parallel: 2, no_restart: false, settle: 5, poll: 0.05, idle_exit: 3600 })]), context,
        scripted: { kernel_changes: [value([])], code_fingerprint: fingerprints(2), kernel_dirty: [value(false)], spawn_runner: [value(0)] } },
    ];
    for (const impl of [TS_NODE, TS_BUN]) {
      const [run, supervisor] = runBatch(impl, requests, REPLAY_TIMEOUT).map((result) => result["value"] as Record<string, unknown>);
      // 第四项是 find_repo 解析出来的仓库路径（长路径），与这里的写法可能不同，不比
      const argv = (state: Record<string, unknown> | undefined): unknown[] => {
        const recorded = calls(state, "spawn_runner")[0]?.["argv"] as string[];
        return [recorded.slice(0, 3), recorded.slice(4)];
      };
      const head = [context.executable, context.kit_hub, "--repo"];
      expect(argv(run), impl.name).toEqual([head, ["run", "--max-steps", "5", "--idle-exit", "0", "--poll", "0.05", "--settle", "5"]]);
      expect(argv(supervisor), impl.name).toEqual([head, ["run", "--parallel", "2", "--max-steps", "5", "--idle-exit", "3600", "--poll", "0.05", "--settle", "5"]]);
    }
  }, 1_800_000);

  it("supervise：拿着总锁的期间锁目录里有 mode；supervise_tick 不放回挂着活暂停标记的主任务（R78、R70）", () => {
    const sc = hubScene();
    const paused = twoTasks((repo) => put(repo, `${BOX}/.pause/T002`, JSON.stringify({ pid: BLOCKER })));
    const repo = new Hub(paused.repo).repo;
    const [running, tick] = agreeFlow([
      // mode 只在拿着锁时在（DirLock 退出时整个目录删掉）：第一轮末尾那次 sleep 当场读它
      { ...flow("cmd_run", sc, [runArgs(sc.repo, { parallel: 2, idle_exit: 3600 })]),
        scripted: { ...quiet, tasks_with_work: [value([])], code_fingerprint: fingerprints(3), sleep: [{ ...(value(null) as object), peek: `0/${BOX}/.runner/mode` }] } },
      flow("supervise_tick", paused, [{ max_steps: 10, poll: 0, settle: 0 }, 2, {}, {}], {
        inner: [alive(BLOCKER, true), inner("requeue_interrupted", { repo, skip: ["T002"] }, []), inner("tasks_with_work", { repo }, [])],
        replaced: ["pid_alive", "requeue_interrupted", "tasks_with_work"],
      }),
    ], ownPid, REPLAY_TIMEOUT);
    expect(calls(running, "sleep").map((call) => [call["seconds"], call["peek"]])).toEqual([[0.5, `supervisor${LF}`]]);
    expect(returned(tick)).toEqual([[], 0n, 0n]);
  }, 1_800_000);

  it("pause_requested：问不出命令进程的死活（None）当它还在，空的标记当 {}；spawn_task_runner 的 args 是 None 时先建好日志再报 AttributeError（R30、R55，抽查 T04）", () => {
    const sc = hubScene((repo) => put(repo, `${BOX}/.pause/T001`, JSON.stringify({ pid: BLOCKER })));
    // read_text 遇到 OSError 也交回 ""：不只手改过的标记才是空的
    const empty = hubScene((repo) => put(repo, `${BOX}/.pause/T001`, ""));
    const [paused, crashed, blank] = agreeFlow([
      flow("pause_requested", sc, ["T001"], { inner: [inner("pid_alive", { pid: BLOCKER }, null)], replaced: ["pid_alive"] }),
      flow("spawn_task_runner", sc, ["T001", null]),
      flow("pause_requested", empty, ["T001"]),
    ], ownPid, REPLAY_TIMEOUT);
    expect([returned(paused), returned(blank)]).toEqual([true, true]);
    expect([failure(crashed), Object.keys(written(crashed)).includes(`0/${BOX}/runners/T001.log`)])
      .toEqual([["AttributeError", "'NoneType' object has no attribute 'max_steps'"], true]);
  }, 1_800_000);

  it("exclusive：执行端跑着时每 5 秒看一次，“等这些跑完”只说一次；跑完了才跑命令，账本只记命令的前 6 项（R91，抽查 T13）", () => {
    const sc = hubScene((repo) => execMark(repo, "T002"));
    const command = [kernelPython(), "-c", "pass", "a", "b", "c", "d"];
    const [state] = agreeFlow([{
      ...flow("cmd_exclusive", sc, [{ repo: sc.repo, command: ["--", ...command], wait: 600 }], {
        inner: [alive(BLOCKER, true), alive(BLOCKER, true), alive(BLOCKER, false)], replaced: ["pid_alive"],
      }),
      scripted: { sleep: [value(null), value(null)] },
    }], ownPid, REPLAY_TIMEOUT);
    expect([returned(state), stdoutOf(state), seconds(state)]).toEqual([0n, `等这些跑完：T002 的执行端（新的执行端在此期间不会开始）${LF}`, [5, 5]]);
    expect(events(state).find((event) => event["event"] === "exclusive.run")?.["command"]).toEqual(command.slice(0, 6));
  }, 1_800_000);

  it("refuse_dirty_kernel：拒绝时账本只记前 20 条改动、报错只列前 10 条；放行时也只记前 20 条（抽查 T01、T02）", () => {
    const sc = hubScene();
    const changes = Array.from({ length: 25 }, (_, index) => ` M scripts/hub/f${String(index).padStart(2, "0")}.py`);
    const [refused, allowed] = agreeFlow([
      { ...flow("refuse_dirty_kernel", sc, [{ allow_dirty_kernel: false }, "T001"]), scripted: { kernel_changes: [value(changes)] } },
      { ...flow("refuse_dirty_kernel", sc, [{ allow_dirty_kernel: true }, null]), scripted: { kernel_changes: [value(changes)] } },
    ], ownPid, REPLAY_TIMEOUT);
    const listed = (state: Record<string, unknown> | undefined): unknown => (events(state)[0]?.["changes"] as unknown[]).length;
    expect([failure(refused)[0], String(failure(refused)[1]).split(" M scripts/hub/f").length - 1, kinds(refused), listed(refused)])
      .toEqual(["HubError", 10, ["runner.refused"], 20]);
    expect([returned(allowed), kinds(allowed), listed(allowed)]).toEqual([null, ["runner.dirty_kernel_allowed"], 20]);
  }, 1_800_000);

  it("cmd_run：exec-step 里同时有两封结项信时照名字的次序先办第一封（抽查 T06）", () => {
    const sc = twoTasks((repo) => {
      execLetter(repo, "T001-5-exec", "通过", 0);
      execLetter(repo, "T002-5-exec", "通过", 1);
    });
    const failed = value([false, "integrate 被拒"]);
    const [state] = agreeFlow([{
      ...flow("cmd_run", sc, [runArgs(sc.repo)]),
      scripted: { ...quiet, "Engine.step": [value(false)], code_fingerprint: steady(4), finalize: [failed, failed] },
    }], ownPid, REPLAY_TIMEOUT);
    const tasks = calls(state, "finalize").map((call) => (fromTagged(call["ts"] as Tagged) as PyDict).get("task"));
    expect([tasks, stdoutOf(state).endsWith(`hub 退出：处理了 2 件事；站主未读 2 封${LF}`)]).toEqual([["T001", "T002"], true]);
  }, 1_800_000);

  it("supervise_tick：自己起的、还在跑的子进程不算上一代的，名额照算（抽查 T09）", () => {
    const held: ChildProcess[] = [];
    try {
      // 在跑的子进程都拿着自己的 .runners/<task>：生产上每一轮都走到这里
      const sc = twoTasks((repo) => holdLock(boxPath(repo, ".runners/T001"), held));
      const repo = new Hub(sc.repo).repo;
      const args = { max_steps: 10, poll: 0, settle: 0 };
      const [state] = agreeFlow([flow("supervise_tick", sc, [args, 2, { T001: { __proc__: 0, pid: 4321 } }, {}], {
        inner: [inner("proc.poll", { proc: 0 }, null), inner("requeue_interrupted", { repo, skip: ["T001"] }, []),
          inner("tasks_with_work", { repo }, ["T001", "T002"]), inner("kernel_dirty", { paths: null }, false),
          inner("spawn_task_runner", { repo, task: "T002", args: toTagged(py(args)) }, { __proc__: 1, pid: 4322 })],
        replaced: ["requeue_interrupted", "tasks_with_work", "kernel_dirty", "spawn_task_runner"],
      })], ownPid, REPLAY_TIMEOUT);
      expect([returned(state), stdoutOf(state)]).toEqual([[["T001", "T002"], 2n, 1n], `起 T002 的 runner（pid 4322）${LF}`]);
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);

  it("owner-sweep：别的 HubError（仓库还没有提交，末端读不出）照抛，不当“已经有一个在跑”（抽查 T14）", () => {
    const sc = hubScene((repo) => {
      put(repo, `${BOX}/ledger/owner-sweep.json`, `${JSON.stringify({ pending: true, head: "b".repeat(40), since: "a".repeat(40) })}${LF}`);
      git(repo, "update-ref", "-d", "HEAD");
    });
    const [state] = agreeFlow([flow("cmd_owner_sweep", sc, [{ repo: sc.repo }])], ownPid, REPLAY_TIMEOUT);
    expect([failure(state)[0], String(failure(state)[1]).startsWith("git rev-parse HEAD 失败：")]).toEqual(["HubError", true]);
  }, 1_800_000);
});

describe("第 ⑤j2 片：起长命子进程（Python 的 Popen 与 bun 的 CreateProcessW 逐字比）", () => {
  it("日志追加、stderr 并进 stdout、工作目录、stdin 是空设备、退出码；不给日志；起不来的报错；Node 下报只跑在 Bun 下", () => {
    const dir = tempDir("popen");
    const work = tempDir("popen-cwd");
    const child = "import os, sys; sys.stdout.write(os.getcwd() + chr(10)); sys.stdout.flush(); sys.stderr.write(repr(sys.stdin.read()) + chr(10)); "
      + "sys.stderr.flush(); sys.exit(3)";
    const requests = (tag: string): ProbeRequest[] => {
      put(dir, `${tag}.log`, `旧的一行${LF}`);
      return [
        { op: "hub.popen", argv: [kernelPython(), "-c", child], cwd: work, log: join(dir, `${tag}.log`), timeout: 30 },
        { op: "hub.popen", argv: [kernelPython(), "-c", "pass"], cwd: null, log: null, timeout: 30 },
        { op: "hub.popen", argv: ["no-such-program-themis"], cwd: null, log: null, timeout: 30 },
        // 子进程读自己 PEB 里的 ConsoleFlags：探针先恢复缺省的 Ctrl+C 处理，没另起进程组的子进程继承“不忽略”，是 0（themistally-04 提的办法）
        { op: "hub.popen", argv: [kernelPython(), "-c", CONSOLE_FLAGS], cwd: null, log: flagsLog(tag), ctrl_c_default: true, timeout: 30 },
      ];
    };
    const flagsLog = (tag: string): string => {
      put(dir, `${tag}-flags.log`, "");
      return join(dir, `${tag}-flags.log`);
    };
    const python = runBatch(PYTHON, requests("python"), REPLAY_TIMEOUT);
    const bun = runBatch(TS_BUN, requests("bun"), REPLAY_TIMEOUT);
    expect(bun).toEqual(python);
    const value = python[0]?.["value"] as Record<string, unknown>;
    const log = Buffer.from(value["log"] as string, "base64").toString("utf8").split(LF);
    // 子进程的 stdout、stderr 是文本模式：换行写成 CRLF；第一行是场景先放进去的
    expect([value["code"], value["returncode"], value["pid"], log[0], log[2], log[3]]).toEqual([3, 3, true, "旧的一行", `''${CR}`, ""]);
    expect([(python[1]?.["value"] as Record<string, unknown>)["code"], python[2]?.["error"]]).toEqual([0, "FileNotFoundError"]);
    expect(Buffer.from((python[3]?.["value"] as Record<string, unknown>)["log"] as string, "base64").toString("utf8")).toBe(`0${CR}${LF}`);
    const [node] = runBatch(TS_NODE, requests("node").slice(1, 2));
    expect([node?.["ok"], String(node?.["error"]).includes("hub 在 Windows 上只跑在 Bun 下")]).toEqual([false, true]);
  }, 600_000);

  it("只继承三个标准句柄：本进程另开的可继承句柄子进程拿不到（N01，themistally-04 提的办法）", () => {
    const dir = tempDir("popen-inherit");
    // 子进程拿命令行给的句柄数值问它对应的文件：路径以那个独有的文件名结尾才算继承到了（数值碰巧撞上子进程自己的句柄也不会误判）
    const program = "import ctypes, sys; k = ctypes.WinDLL('kernel32', use_last_error=True); buf = ctypes.create_unicode_buffer(2048); "
      + "n = k.GetFinalPathNameByHandleW(ctypes.c_void_p(int(sys.argv[1])), buf, 2048, 0); "
      + "print('inherited' if n and buf.value.lower().endswith(sys.argv[2].lower()) else 'not inherited')";
    const request = (tag: string): ProbeRequest => {
      put(dir, `${tag}.log`, "");
      return { op: "hub.popen", argv: [kernelPython(), "-c", program, "<handle>", `${tag}-held.txt`], cwd: null, log: join(dir, `${tag}.log`),
        inherit: join(dir, `${tag}-held.txt`), timeout: 30 };
    };
    const python = runBatch(PYTHON, [request("python")], REPLAY_TIMEOUT);
    const bun = runBatch(TS_BUN, [request("bun")], REPLAY_TIMEOUT);
    expect(bun).toEqual(python);
    const value_ = python[0]?.["value"] as Record<string, unknown>;
    expect([value_["code"], Buffer.from(value_["log"] as string, "base64").toString("utf8")]).toEqual([0, `not inherited${CR}${LF}`]);
  }, 600_000);
});

describe("第 ⑤j2 片：真的 git status（手写，用例经 REAL_KERNEL_CHANGES 调的那两条）", () => {
  it("kernel_changes、kernel_dirty：干净、改过加未跟踪（含中文文件名）、目录不在、git 报错（GIT_DIR 指向不在的目录）、空清单", () => {
    const kernel = { "scripts/kit_hub.py": `# kernel${LF}`, "scripts/hub/deliver.ts": `// deliver${LF}` };
    const clean = newRepo("kernel-clean", kernel).repo;
    const dirty = newRepo("kernel-dirty", kernel).repo;
    put(dirty, "scripts/hub/deliver.ts", `// changed${LF}`);
    put(dirty, "scripts/hub/schemas/gate.json", "{}");
    put(dirty, "scripts/hub/schemas/说明.json", "{}");
    const files = (repo: string, more: string[] = []): string[] => [...Object.keys(kernel), ...more].map((rel) => join(repo, ...rel.split("/")));
    const nowhere = [join(tempDir("kernel-nowhere"), "nowhere", "x.py")];
    const cases: [string[], Record<string, string>][] = [
      [files(clean), {}], [files(dirty, ["scripts/hub/schemas/gate.json", "scripts/hub/schemas/说明.json"]), {}], [nowhere, {}],
      [files(clean), { GIT_DIR: join(tempDir("kernel-gitdir"), "no-such-git-dir") }], [[], {}],
    ];
    const requests: ProbeRequest[] = ["kernel_changes", "kernel_dirty"].flatMap((fn) => cases.map(([paths, env]) => ({
      op: "hub.contract", fn, args: [toTagged(py(paths))], env,
    })));
    const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests, REPLAY_TIMEOUT));
    for (const other of others) expect(other).toEqual(python);
    const values = (python ?? []).map((result) => (result["ok"] ? fromTagged(result["value"] as Tagged) : [result["error"], result["message"]]));
    const changes = values.slice(0, 5) as PyValue[][];
    expect(changes[0]).toEqual([]);
    expect([changes[1]?.length, changes[1]?.[0], changes[1]?.[1]]).toEqual([3, " M scripts/hub/deliver.ts", "?? scripts/hub/schemas/gate.json"]);
    expect([changes[2]?.length, String(changes[2]?.[0]).startsWith("git 起不来：[WinError 267] ")]).toEqual([1, true]);
    expect(changes[3]).toEqual(["git status 退出码 128（不在 Git 仓库里？）"]);
    expect(values[4]).toEqual(["IndexError", "list index out of range"]);
    expect(values.slice(5)).toEqual([false, true, true, true, ["IndexError", "list index out of range"]]);
  }, 1_800_000);
});

describe("第 ⑤j2 片：E3 内核文件（⑤j 设计稿第 6 节）", () => {
  it("选择文件的 hub 是 python 时 TS 与 Python 逐项相同；是 ts 时 TS 正好多出五个包 src 下的全部文件与依赖清单", () => {
    const python = new Map([["hub", "python"]]);
    const listed = IMPLS.map((impl) => runBatch(impl, [{ op: "hub.contract", fn: "kernel_files", args: [toTagged(python)] }])[0]);
    expect(listed[1]).toEqual(listed[0]);
    expect(listed[2]).toEqual(listed[0]);
    const base = fromTagged(listed[0]?.["value"] as Tagged) as string[];
    const root = join(dirname(dirname(base[0] as string)), "ts"); // 第一项是 scripts/kit_hub.py
    const sources: string[] = [];
    const walk = (dir: string, rel: string): void => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (entry.isDirectory()) walk(join(dir, entry.name), `${rel}/${entry.name}`);
        else sources.push(`${rel}/${entry.name}`);
      }
    };
    for (const name of ["base", "config", "dispatcher", "hub", "cli"]) walk(join(root, "packages", name, "src"), `packages/${name}/src`);
    const manifests = readdirSync(join(root, "packages"), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && readdirSync(join(root, "packages", entry.name)).includes("package.json"))
      .map((entry) => `packages/${entry.name}/package.json`);
    const expected = [...sources.sort(cmpCodePoints), "package.json", "bun.lock", "bunfig.toml", ...manifests.sort(cmpCodePoints), "tsconfig.json"];
    expect(sources.some((rel) => rel === "packages/hub/src/runner.ts")).toBe(true);
    for (const impl of [TS_NODE, TS_BUN]) {
      const [result] = runBatch(impl, [{ op: "hub.contract", fn: "kernel_files", args: [toTagged(new Map([["hub", "ts"]]) as PyDict)] }]);
      const files = fromTagged(result?.["value"] as Tagged) as string[];
      expect(files.slice(0, base.length), impl.name).toEqual(base);
      expect(files.slice(base.length).map((path) => relative(root, path).split(String.fromCharCode(92)).join("/")), impl.name).toEqual(expected);
    }
  }, 600_000);
});
