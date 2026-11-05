// 第 ⑤h2 片的手写对照（采样那份在 hub-sweep.contract.test.ts）：临时仓库上搭好场景，三边各自先原地放回再跑，交回值、ts、文件、账本、
// git 状态逐字比。样本没走到的语句、各处的常数（tail 的行数、截断的字数、git log 的条数、时限）与两边互认，在这里：
//   - sweep_gates、gate_baselines：真跑两份小门禁（一份过、一份不过，pytest 的用时换成占位；仓库的 pytest.ini 写了 addopts = -rN，命令行的
//     -rfE 照样盖过它）、没有门禁基准；只测 TS 的时限（门禁里起一个睡着的孙进程：按时交回，孙进程跟着整棵树结束，临时目录删掉）；
//   - 后台回归的标记与 .sweep 锁两边互认：TS 挂着窗口时 Python 的 landing_blockers 认它，Python 挂着时 TS 的认它、TS 等 .sweep 锁超时原样抛出；
//   - regression_sweep：没有门禁基准、没过（输出长过 15 行、行很长）、过了；
//   - owner_sweep：没有待跑的；没过（输出长、期间的提交多过 10 个且主题很长、跑的期间站主又动了 HEAD，pending 留着）；过了；
//   - ts_install_if_stale：没有 ts/package.json、选择文件全是 python、戳记对得上、戳记不是 JSON 又找不到 Bun、装好了（输出长过 10 行、带非 UTF-8
//     的字节）、装完戳记还对不上、超时（摘要长过 1500 字）；
//   - mark_owner_moved、read_owner_sweep、rehearsal_letter、rehearse_landing 的边界与截断。
// 不写转义序列。
import { spawn } from "node:child_process";
import { existsSync, readdirSync, writeFileSync } from "node:fs";
import { basename, join, sep } from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { HubError } from "@themis/hub/errors";
import { landingBlockers } from "@themis/hub/land";
import { Hub, canonicalState } from "@themis/hub/mailbox";
import { setKernelPython } from "@themis/hub/runpd";
import { REAL_SWEEP_DEPS, type SweepDeps, sweepGates, tsInstallIfStale, withSweepWindow } from "@themis/hub/sweep";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { depsDigest } from "../../../tools/stamp-install.mjs";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, REPO, runBatch } from "./harness.ts";
import { AT, LF, PIN, type Scene, agreeFlow, flow, kernelPython, py, returned, scene, scrub, tsAfter, written } from "./flow-fixtures.ts";
import { git, put, removeCreated, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const lines = (...items: string[]): string => [...items, ""].join(LF);
const NOTHING = { write: {}, delete: [] };
const GATE_OK = "tests/test_gate_a_baseline.py";
const GATE_BAD = "tests/test_gate_B_baseline.py";
const BASE = { "src/doc.py": lines("def title():", "    return 'old'") };
const OWNER = ".agent/mailbox/ledger/owner-sweep.json";
const LONG = "长".repeat(80);
/** 注入的多行输出：“前缀 1 长……”到“前缀 n 长……”（行很长，截断的字数才起作用）。 */
const many = (prefix: string, count: number, tail = LONG): string => Array.from({ length: count }, (_, at) => `${prefix} ${at + 1} ${tail}`).join(LF);
const b64 = (data: string | Uint8Array): string => Buffer.from(data).toString("base64");

const errorOf = (state: Record<string, unknown> | undefined): unknown => (state?.["result"] as Record<string, unknown>)["error"] ?? null;
function injectedCleanly(states: readonly Record<string, unknown>[]): void {
  expect(states.map(errorOf).filter((error) => String(error).startsWith("INJECTION_")), "注入的记录与调用对不上").toEqual([]);
}
/** 新写进信箱的信：文件名（相对 inbox）与内容。 */
const letters = (state: Record<string, unknown> | undefined): string[] =>
  Object.entries(written(state)).filter(([key]) => key.includes("/inbox/")).map(([, data]) => Buffer.from(data, "base64").toString("utf8"));

function sweepTs(sc: Scene, extra: Record<string, unknown> = {}): PyDict {
  const ts = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
  for (const [key, value] of Object.entries(extra)) ts.set(key, value instanceof Map ? (value as PyDict) : py(value));
  return ts;
}

/** scratch_worktree 的 worktree_root 与 mkdtemp 照手写的记录注入：建在固定的名字上；sweep_gates 交回给定的结果。 */
function scratch(sc: Scene, label: string, code: number, out: string, tests: string[], gateFiles: object = NOTHING): { inner: unknown[]; made: string } {
  const root = tempDir("sweep-wtroot");
  const prefix = `${basename(sc.repo).slice(0, 16)}-hub-${label}-`;
  const made = join(root, `${prefix}fixed`);
  return {
    made, inner: [
      { fn: "worktree_root", repo: sc.repo, value: toTagged(root), files: NOTHING }, { fn: "mkdtemp", prefix, dir: root, value: toTagged(made), files: NOTHING },
      { fn: "sweep_gates", path: made, value: toTagged([BigInt(code), out, tests]), files: gateFiles },
    ],
  };
}
const scratchExtra = (s: { inner: unknown[]; made: string }): { inner: unknown[]; replaced: string[]; fresh: string[] } =>
  ({ inner: s.inner, replaced: ["worktree_root", "mkdtemp", "sweep_gates"], fresh: [s.made] });

/** 不经 hub.contract_flow 的（只读）：三边各跑一次，normalize 之后逐个比，交回 Python 的结果。 */
function agreeCalls(requests: readonly ProbeRequest[], normalize: (value: unknown) => unknown = (value) => value): ProbeResult[] {
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests, 300_000));
  for (const [index, other] of others.entries()) {
    expect(JSON.stringify(normalize(other)), `${IMPLS[index + 1]?.name} 与 Python 不同`).toBe(JSON.stringify(normalize(python)));
  }
  return python as ProbeResult[];
}
const valueOf = (result: ProbeResult | undefined): PyValue => (result?.["ok"] ? fromTagged(result["value"] as Tagged) : (result?.["error"] as string));

describe("第 ⑤h2 片：sweep_gates 与 gate_baselines（手写，真跑门禁基准）", () => {
  it("两份小门禁一过一不过：退出码、跑了哪几份、输出三边相同（pytest 的用时换成占位）；没有门禁基准时不跑；只认 tests/test_gate_*_baseline.py", () => {
    const sc = scene({
      [GATE_OK]: lines("def test_ok():", "    assert True"), [GATE_BAD]: lines("def test_bad():", "    assert 1 == 2"),
      "tests/test_other.py": lines("def test_x():", "    assert False"), "tests/test_gate_helper.py": lines("def test_h():", "    assert False"),
      "tests/TEST_GATE_C_BASELINE.txt": "不是 .py", "pytest.ini": lines("[pytest]", "addopts = -rN"), // 被管的仓库可以有自己的 -r
    }, () => undefined, false);
    const empty = scene(BASE, () => undefined, false);
    const request = (fn: string, dir: string): ProbeRequest => ({ op: "hub.contract", fn, args: [toTagged(dir)], restores: [], python: kernelPython() });
    const results = agreeCalls([request("sweep_gates", sc.repo), request("sweep_gates", empty.repo), request("gate_baselines", sc.repo)], scrub);
    const [code, out, tests] = valueOf(results[0]) as [bigint, string, string[]];
    expect([code, tests, out.includes("1 failed, 1 passed")]).toEqual([1n, [GATE_BAD, GATE_OK], true]);
    expect(out.includes(`FAILED ${GATE_BAD}::test_bad`), "命令行的 -rfE 盖过仓库配置的 -rN").toBe(true);
    expect(valueOf(results[1])).toEqual([0n, "没有门禁基准可跑", []]);
    expect(valueOf(results[2])).toEqual([GATE_BAD, GATE_OK]);
  }, 600_000);

  it("只测 TS：时限到了，门禁里起的孙进程连同整棵树一起结束，按时交回 (-1, 那句话)，临时目录也删掉了", async () => {
    const dir = tempDir("sweep-slow");
    const marker = [...dir.split(sep), "alive"].join("/"); // 孙进程睡 8 秒后写它：整棵树结束了就不会有
    const code = `import time, pathlib; time.sleep(8); pathlib.Path('${marker}').write_text('x')`;
    put(dir, "tests/test_gate_slow_baseline.py", lines(
      "import subprocess", "import sys", "import time", "", `CODE = ${JSON.stringify(code)}`, "", "", "def test_slow():",
      "    subprocess.Popen([sys.executable, '-c', CODE])", "    time.sleep(120)",
    ));
    setKernelPython(kernelPython());
    const temp = tempDir("sweep-tmp");
    const saved = [process.env["TEMP"], process.env["TMP"]];
    process.env["TEMP"] = temp;
    process.env["TMP"] = temp;
    const started = Date.now();
    let result: unknown;
    try {
      result = await sweepGates(dir, 3);
    } finally {
      process.env["TEMP"] = saved[0];
      process.env["TMP"] = saved[1];
    }
    expect(result).toEqual([-1, "超过 3 秒没有跑完", ["tests/test_gate_slow_baseline.py"]]);
    expect(Date.now() - started, "按时交回").toBeLessThan(30_000);
    expect(readdirSync(temp), "临时目录删掉了").toEqual([]);
    await new Promise((resolve) => setTimeout(resolve, 12_000));
    expect(existsSync(marker), "孙进程跟着整棵树结束了，没写出标记").toBe(false);
  }, 120_000);
});

describe("第 ⑤h2 片：后台回归的标记与 .sweep 锁两边互认（手写）", () => {
  const marked = (repo: string): string => join(repo, ".agent", "mailbox", "ledger", "exec-active", "owner-sweep.json");

  it("TS 挂着窗口时，Python 的 landing_blockers 认它的标记（sweeps 为假时不算）；窗口收掉之后标记也删了", async () => {
    const sc = scene(BASE, () => undefined, false);
    const ts = sweepTs(sc);
    const blockers = (sweeps: boolean): ProbeRequest => ({
      op: "hub.contract_flow", fn: "landing_blockers", args: [sc.repo, ts, sweeps].map((arg) => toTagged(py(arg))), restores: [], roots: [sc.repo], fresh: [],
      pin: PIN, replaced: [], inner: [], python: kernelPython(), env: {},
    });
    let seen: PyValue[] = [];
    await withSweepWindow(new Hub(sc.repo), "owner-sweep", "站主提交之后的门禁回归", async () => {
      seen = runBatch(PYTHON, [blockers(true), blockers(false)]).map((result) => returned(result["value"] as Record<string, unknown>));
    }, { ...REAL_SWEEP_DEPS, sweepWaitSeconds: 5, landLockWaitSeconds: 5 });
    expect(seen).toEqual([["站主提交之后的门禁回归"], []]);
    expect(existsSync(marked(sc.repo)), "窗口收掉之后标记删了").toBe(false);
  }, 300_000);

  it("Python 挂着窗口时，TS 的 landing_blockers 认它的标记（sweeps 为假时不算）；TS 等 .sweep 锁超时，HubError 原样抛出", async () => {
    const sc = scene(BASE, () => undefined, false);
    const flag = tempDir("sweep-flag");
    const script = join(flag, "hold.py");
    writeFileSync(script, lines(
      "import sys", "import time", "from pathlib import Path", `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`, "import kit_hub as kh",
      `hub = kh.Hub(Path(${JSON.stringify(sc.repo)}))`,
      "with kh.sweep_window(hub, 'owner-sweep', '站主提交之后的门禁回归'):",
      `    Path(${JSON.stringify(join(flag, "ready"))}).write_text('ok')`,
      `    while not Path(${JSON.stringify(join(flag, "go"))}).exists():`, "        time.sleep(0.05)",
    ));
    const child = spawn(kernelPython(), [script], { stdio: "ignore", env: { ...process.env, PYTHONUTF8: "1" } });
    const exited = new Promise((resolve) => child.on("exit", resolve));
    for (let waited = 0; !existsSync(join(flag, "ready")) && waited < 600; waited += 1) sleepSync(50);
    const hub = new Hub(sc.repo);
    const ts = sweepTs(sc);
    const seen = [landingBlockers(hub, ts, true), landingBlockers(hub, ts, false)];
    let error: unknown = null;
    try {
      await withSweepWindow(hub, "regression-T001", "T001 合入后的门禁回归", async () => undefined, { ...REAL_SWEEP_DEPS, sweepWaitSeconds: 0.3 });
    } catch (caught) {
      error = caught;
    }
    writeFileSync(join(flag, "go"), "go");
    await exited;
    expect(seen).toEqual([["站主提交之后的门禁回归"], []]);
    expect([error instanceof HubError, String((error as Error | null)?.message).startsWith("锁被占用：")]).toEqual([true, true]);
    expect(existsSync(marked(sc.repo)), "Python 的窗口收掉之后标记删了").toBe(false);
  }, 300_000);
});

describe("第 ⑤h2 片：另一个进程拿着落地锁（手写）", () => {
  /** 另一个进程（Python 的 DirLock）拿着 repo 信箱下的 lock（缺省 .land），直到 flag 下出现 go；交回它退出的 Promise。 */
  function holdLand(flag: string, repo: string, name: string, lock = ".land"): Promise<unknown> {
    const script = join(flag, `${name}.py`);
    writeFileSync(script, lines(
      "import sys", "import time", "from pathlib import Path", `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`, "import kit_hub as kh",
      `with kh.DirLock(Path(${JSON.stringify(join(repo, ".agent", "mailbox", lock))}), wait_seconds=5):`,
      `    Path(${JSON.stringify(join(flag, `${name}-ready`))}).write_text("ok")`,
      `    while not Path(${JSON.stringify(join(flag, "go"))}).exists():`, "        time.sleep(0.05)",
    ));
    const child = spawn(kernelPython(), [script], { stdio: "ignore", env: { ...process.env, PYTHONUTF8: "1" } });
    const exited = new Promise((resolve) => child.on("exit", resolve));
    for (let waited = 0; !existsSync(join(flag, `${name}-ready`)) && waited < 600; waited += 1) sleepSync(50);
    return exited;
  }

  it("owner_sweep 拿到 .sweep 之后挂标记时等 .land 超时（仓库没有 ts/package.json，挡住它的只有这一下），HubError 原样抛出、.sweep 放掉；ts 重装等 .land 超时同样抛出", async () => {
    const flag = tempDir("sweep-land");
    const exits: Promise<unknown>[] = [];
    // 搭场景时就拿着：快照里带着这把锁，每次放回之后照样是它拿着
    const held = (repo: string, name: string): void => {
      exits.push(holdLand(flag, repo, name));
    };
    const owned = scene(BASE, (repo, _wt, head) => {
      put(repo, OWNER, JSON.stringify({ pending: true, head, since: head, command: ["git"], at: AT }));
      held(repo, "owner");
    }, false);
    const sc = scene({ ...BASE, "ts/package.json": lines("{", "}") }, (repo) => held(repo, "ts"), false);
    const ON_TS = { readonly: "ts", config: "python", dispatcher: "python", hub: "python" };
    const tsInner = [{ fn: "read_kernel_impl", args: 0, value: toTagged(py(ON_TS)), files: NOTHING }, { fn: "find_bun", env: true, value: toTagged("C:/bun/bun.exe"), files: NOTHING }];
    let states: Record<string, unknown>[] = [];
    try {
      states = agreeFlow([
        { ...flow("owner_sweep", owned, []), land_lock_wait: 0.2 },
        { ...flow("ts_install_if_stale", sc, [null], { inner: tsInner, replaced: ["read_kernel_impl", "find_bun"] }), land_lock_wait: 0.2 },
      ]);
    } finally {
      writeFileSync(join(flag, "go"), "go");
      await Promise.all(exits);
    }
    injectedCleanly(states);
    for (const [index, state] of states.entries()) {
      const result = state["result"] as Record<string, unknown>;
      const land = join([owned, sc][index]?.repo as string, ".agent", "mailbox", ".land");
      expect([result["error"], String(result["message"]).startsWith(`锁被占用：${land}`)]).toEqual(["HubError", true]);
    }
    expect(written(states[0])["0/.agent/mailbox/.sweep/owner.json"], ".sweep 放掉了").toBe(undefined);
  }, 300_000);

  it("后台回归之间排队：另一份拿着 .sweep 时，owner_sweep 等 SWEEP_WAIT_SECONDS 超时原样抛出，自己的标记没挂、.land 没碰（7055，⑤j3 覆盖审计补）", async () => {
    const flag = tempDir("sweep-queue");
    const exits: Promise<unknown>[] = [];
    // 搭场景时就拿着（快照里带着这把锁）：拿着它的是正在跑的那一份后台回归
    const queued = scene(BASE, (repo, _wt, head) => {
      put(repo, OWNER, JSON.stringify({ pending: true, head, since: head, command: ["git"], at: AT }));
      exits.push(holdLand(flag, repo, "sweep", ".sweep"));
    }, false);
    // 前一份跑完：另一个进程拿过 .sweep、又放掉（DirLock 退出时删掉整个目录），快照里没有这把锁；后一份照常拿到、跑完
    const releaseFlag = tempDir("sweep-released");
    const released = scene({ ...BASE, [GATE_OK]: lines("def test_ok():", "    assert True") }, (repo, _wt, head) => {
      put(repo, OWNER, JSON.stringify({ pending: true, head, since: head, command: ["git"], at: AT }));
      exits.push(holdLand(releaseFlag, repo, "sweep", ".sweep"));
      writeFileSync(join(releaseFlag, "go"), "go");
      for (let waited = 0; existsSync(join(repo, ".agent", "mailbox", ".sweep")) && waited < 600; waited += 1) sleepSync(50);
    }, false);
    const run = scratch(released, "owner-sweep", 0, lines("1 passed in 0.01s"), [GATE_OK]);
    let states: Record<string, unknown>[] = [];
    try {
      states = agreeFlow([{ ...flow("owner_sweep", queued, []), sweep_wait: 0.6 }, { ...flow("owner_sweep", released, [], scratchExtra(run)), sweep_wait: 0.6 }]);
    } finally {
      writeFileSync(join(flag, "go"), "go");
      await Promise.all(exits);
    }
    injectedCleanly(states);
    const result = states[0]?.["result"] as Record<string, unknown>;
    const sweep = join(queued.repo, ".agent", "mailbox", ".sweep");
    expect([result["error"], String(result["message"]).startsWith(`锁被占用：${sweep}`)]).toEqual(["HubError", true]);
    // 排队的那一份没挂标记，也没碰落地锁：挡着落地的只有正在跑的那一份
    expect(Object.keys(written(states[0])).filter((key) => key.includes("exec-active") || key.includes("/.land/"))).toEqual([]);
    expect((returned(states[1]) as PyValue[])[0]).toBe(true);
  }, 300_000);

  it("只测 TS：挂标记与 ts 重装等 .land 用的是 landLockWaitSeconds（LAND_WAIT_SECONDS），不是执行端的 landWaitSeconds", async () => {
    const flag = tempDir("sweep-land-ts");
    const sc = scene({ ...BASE, "ts/package.json": lines("{", "}") }, () => undefined, false);
    const exited = holdLand(flag, sc.repo, "direct");
    // 执行端的时限给 30 秒：用错了字段会等满 30 秒才抛，下面“10 秒内就抛”那一项对不上（不靠撞上测试的时限）
    const deps: SweepDeps = {
      ...REAL_SWEEP_DEPS, sweepWaitSeconds: 5, landLockWaitSeconds: 0.3, landWaitSeconds: 30,
      readKernelImpl: () => py({ readonly: "ts" }) as PyDict, findBun: () => "C:/bun/bun.exe",
    };
    const timed = async (fn: () => Promise<unknown>): Promise<boolean[]> => {
      const started = Date.now();
      try {
        await fn();
        return [false, false, false];
      } catch (error) {
        return [error instanceof HubError, String((error as Error).message).startsWith("锁被占用："), Date.now() - started < 10_000];
      }
    };
    const seen: boolean[][] = [];
    try {
      const hub = new Hub(sc.repo);
      seen.push(await timed(() => withSweepWindow(hub, "owner-sweep", "站主提交之后的门禁回归", async () => undefined, deps)));
      seen.push(await timed(() => tsInstallIfStale(hub, deps)));
    } finally {
      writeFileSync(join(flag, "go"), "go");
      await exited;
    }
    expect(seen, "每次三项：HubError、锁被占用、10 秒内就抛").toEqual([[true, true, true], [true, true, true]]);
  }, 180_000);
});

describe("第 ⑤h2 片：regression_sweep 与 owner_sweep（手写）", () => {
  const gated = (prepare: (repo: string, head: string) => void = () => undefined): Scene =>
    scene({ ...BASE, [GATE_OK]: lines("def test_ok():", "    assert True") }, (repo, _wt, head) => prepare(repo, head), false);

  it("regression_sweep：没有门禁基准直接算过；没过（输出长过 15 行）记 regression 与全文；过了只给最后一行", () => {
    const none = scene(BASE, () => undefined, false);
    const red = gated();
    const green = gated();
    const redRun = scratch(red, "sweep", 1, many("FAILED 第", 20), [GATE_OK]);
    const greenRun = scratch(green, "sweep", 0, lines("....", "1 passed in 0.01s"), [GATE_OK]);
    const states = agreeFlow([
      flow("regression_sweep", none, [sweepTs(none)]),
      flow("regression_sweep", red, [sweepTs(red)], scratchExtra(redRun)), flow("regression_sweep", green, [sweepTs(green)], scratchExtra(greenRun)),
    ]);
    injectedCleanly(states);
    expect(returned(states[0])).toEqual([true, "合入后没有门禁基准可跑"]);
    const [ok, summary] = returned(states[1]) as [boolean, string];
    expect([ok, summary.split(LF).length]).toEqual([false, 16]);
    expect((tsAfter(states[1]).get("regression") as PyDict).get("exit")).toBe(1n);
    expect(returned(states[2])).toEqual([true, `合入后的门禁回归（1 份，末端 ${green.head.slice(0, 12)}）：1 passed in 0.01s`]);
  }, 600_000);

  it("owner_sweep：没有待跑的交回 None；没过写信（验证截 1500 字、期间的提交只列 10 个且截 600 字），跑的期间站主又动了 HEAD 就留着待跑；过了清掉待跑", () => {
    let since = "";
    const subjects = Array.from({ length: 12 }, (_, at) => `站主的第 ${at + 1} 轮提交 ${"主题很长".repeat(12)}`);
    const short = Array.from({ length: 12 }, (_, at) => `短提交 ${at + 1}`); // 不撞上截 600 字，git log 的条数才看得出来
    const pendingOf = (list: string[]) => (repo: string, head: string): void => {
      since = head;
      let tip = head;
      for (const [at, subject] of list.entries()) {
        put(repo, `src/owner${at}.py`, `x = ${at}${LF}`);
        git(repo, "add", "-A");
        git(repo, "commit", "-q", "-m", subject);
        tip = git(repo, "rev-parse", "HEAD");
      }
      put(repo, OWNER, JSON.stringify({ pending: true, head: tip, since: head, command: ["git", "merge"], at: AT }));
    };
    const pending = pendingOf(subjects);
    const idle = gated();
    const red = gated(pending);
    const redSince = since;
    const green = gated(pending);
    const redShort = gated(pendingOf(short));
    const moved = { [`0/${OWNER}`]: b64(JSON.stringify({ pending: true, head: "f".repeat(40), since: redSince, command: ["git", "merge"], at: AT })) };
    const redRun = scratch(red, "owner-sweep", 1, many("FAILED 第", 20), [GATE_OK], { write: moved, delete: [] });
    // 跑的期间执行标记被外面删了：收尾删不到照样吞掉
    const redShortRun = scratch(redShort, "owner-sweep", 1, many("FAILED 第", 3), [GATE_OK]);
    const greenRun = scratch(green, "owner-sweep", 0, lines("1 passed in 0.01s"), [GATE_OK], { write: {}, delete: [".agent/mailbox/ledger/exec-active/owner-sweep.json"].map((rel) => `0/${rel}`) });
    // owner_sweep_run 先查 ts/ 的依赖：绿的那条照记录注入一次，不调就是 INJECTION_LEFTOVER
    const withTsInstall = (sc: Scene, extra: ReturnType<typeof scratchExtra>): ReturnType<typeof scratchExtra> => ({
      ...extra, inner: [{ fn: "ts_install_if_stale", repo: sc.repo, value: toTagged(null), files: NOTHING }, ...extra.inner],
      replaced: [...extra.replaced, "ts_install_if_stale"],
    });
    const states = agreeFlow([
      flow("owner_sweep", idle, []), flow("owner_sweep", red, [], scratchExtra(redRun)), flow("owner_sweep", green, [], withTsInstall(green, scratchExtra(greenRun))),
      flow("owner_sweep", redShort, [], scratchExtra(redShortRun)),
    ]);
    injectedCleanly(states);
    expect(returned(states[0])).toBe(null);
    expect((returned(states[1]) as PyValue[])[0]).toBe(false);
    const owner = (state: Record<string, unknown> | undefined): Record<string, unknown> =>
      JSON.parse(Buffer.from(written(state)[`0/${OWNER}`] as string, "base64").toString("utf8")) as Record<string, unknown>;
    expect([owner(states[1])["pending"], owner(states[2])["pending"]], "跑的期间动了 HEAD 就留着待跑").toEqual([true, false]);
    const letter = letters(states[1])[0] ?? "";
    expect([letters(states[1]).length, letter.includes(`${subjects[11]}`), letter.includes(`${subjects[1]}`)], "期间的提交只列最近 10 个").toEqual([1, true, false]);
    expect(letters(states[2]).length).toBe(0);
    const shortLetter = letters(states[3])[0] ?? "";
    expect([shortLetter.includes("短提交 3"), shortLetter.includes("短提交 2")], "主题短的也只列最近 10 个").toEqual([true, false]);
    const last = owner(states[2])["last"] as Record<string, unknown>;
    expect([last["exit"], last["tests"]], "过了的那次记在 last 里").toEqual([0, [GATE_OK]]);
  }, 600_000);

  it("owner_sweep 之后的预演只做 active 的：收了尾的任务条件齐全也不预演", () => {
    const RUN = ".agent/runs/t001-doc/attempt-001";
    const closed = gated((repo, head) => {
      put(repo, "src/m.py", lines("m = 1"));
      git(repo, "add", "-A");
      git(repo, "commit", "-q", "-m", "并行主任务先落地");
      const tip = git(repo, "rev-parse", "HEAD");
      put(repo, `${RUN}/meta.json`, JSON.stringify({ base_sha: head }));
      put(repo, `${RUN}/candidate.patch`, "");
      const ts = newTaskState("T001", "doc", "改文档", head, true, AT);
      ts.set("status", "closed");
      ts.set("exec", py({ run_dir: join(repo, ...RUN.split("/")), check_ok: true }));
      ts.set("oracle", py({ sha: head, files: [GATE_OK] }));
      put(repo, ".agent/mailbox/ledger/state.json", canonicalState(new Map([["tasks", new Map([["T001", ts]])]])));
      put(repo, OWNER, JSON.stringify({ pending: true, head: tip, since: head, command: ["git", "merge"], at: AT }));
    });
    const run = scratch(closed, "owner-sweep", 0, lines("1 passed in 0.01s"), [GATE_OK]);
    const states = agreeFlow([flow("owner_sweep", closed, [], scratchExtra(run))]);
    injectedCleanly(states);
    expect((returned(states[0]) as PyValue[])[0]).toBe(true);
  }, 600_000);

  it("第 ⑤ 步切换（一）：owner.swept 记的 hub_impl 是各边自己的值（请求带 hub_impl: default，各开一个探针进程；三边逐字比的那几条照 Python 钉成 python）", () => {
    const pending = gated((repo, head) => put(repo, OWNER, JSON.stringify({ pending: true, head, since: head, command: ["git", "merge"], at: AT })));
    const run = scratch(pending, "owner-sweep", 0, lines("1 passed in 0.01s"), [GATE_OK]);
    const request = { ...flow("owner_sweep", pending, [], scratchExtra(run)), hub_impl: "default" };
    const swept = IMPLS.map((impl) => {
      const state = runBatch(impl, [request], REPLAY_TIMEOUT)[0]?.["value"] as Record<string, unknown> | undefined;
      const ledger = Buffer.from((state?.["ledger"] as string | undefined) ?? "", "base64").toString("utf8");
      return ledger.split(LF).filter(Boolean).map((row) => JSON.parse(row) as Record<string, unknown>)
        .filter((event) => event["event"] === "owner.swept").map((event) => event["hub_impl"]);
    });
    expect(swept).toEqual([["python"], ["ts"], ["ts"]]);
  }, 600_000);
});

describe("第 ⑤h2 片：ts_install_if_stale（手写）", () => {
  const BUN = "C:/bun/bun.exe";
  const ON_TS = { readonly: "ts", config: "python", dispatcher: "python", hub: "python" };
  const withTs = (stamp: string | null): Scene => scene(BASE, (repo) => {
    put(repo, "ts/package.json", lines("{", '  "name": "x",', '  "private": true', "}"));
    if (stamp !== null) put(repo, "ts/node_modules/.themis-installed", stamp);
  }, false);
  const digestOf = (sc: Scene): string => depsDigest(join(sc.repo, "ts"));
  const kernelImpl = (value: Record<string, string>): unknown => ({ fn: "read_kernel_impl", args: 0, value: toTagged(py(value)), files: NOTHING });
  const findBun = (value: string | null): unknown => ({ fn: "find_bun", env: true, value: toTagged(value), files: NOTHING });
  const runner = (sc: Scene, result: Record<string, unknown>, output: Uint8Array, stamp: string | null): unknown => ({
    fn: "ts_runner", argv: [BUN, "install", "--frozen-lockfile"], cwd: join(sc.repo, "ts"), env: true, stdout: "<temporary>", stderr: "same", timeout: 900,
    value: toTagged(py(result)), output: b64(output),
    files: { write: stamp === null ? {} : { "0/ts/node_modules/.themis-installed": b64(stamp) }, delete: [] },
  });
  const install = (sc: Scene, inner: unknown[]): ProbeRequest =>
    flow("ts_install_if_stale", sc, [null], { inner, replaced: ["read_kernel_impl", "find_bun", "ts_runner"].filter((name) => inner.some((entry) => (entry as { fn: string }).fn === name)) });
  /** 十二行输出，中间夹着不是 UTF-8 的字节。 */
  const output = (prefix: string): Uint8Array => Buffer.concat([Buffer.from(`${many(prefix, 6)}${LF}`), Buffer.from([0xff, 0xfe, 0x0a]), Buffer.from(many(`${prefix}后`, 5))]);

  it("不装的三种：没有 ts/package.json、选择文件全是 python、戳记对得上", () => {
    const bare = scene(BASE, () => undefined, false);
    const python = withTs(null);
    const fresh = withTs(null);
    put(fresh.repo, "ts/node_modules/.themis-installed", JSON.stringify({ deps_sha256: digestOf(fresh) }));
    const stamped = scene(BASE, (repo) => {
      put(repo, "ts/package.json", lines("{", '  "name": "x",', '  "private": true', "}"));
      put(repo, "ts/node_modules/.themis-installed", JSON.stringify({ deps_sha256: depsDigest(join(repo, "ts")) }));
    }, false);
    const states = agreeFlow([
      install(bare, []), install(python, [kernelImpl({ ...ON_TS, readonly: "python" })]), install(stamped, [kernelImpl(ON_TS)]),
    ]);
    injectedCleanly(states);
    expect(states.map(returned)).toEqual([null, null, null]);
  }, 600_000);

  it("要装的：戳记不是 JSON 又找不到 Bun（写信）；装好了（输出长过 10 行、带非 UTF-8 的字节）；装完戳记对不上（写信）；超时（摘要长过 1500 字，写信）", () => {
    const broken = withTs("{坏");
    const good = withTs(null);
    const stale = withTs(null);
    const slow = withTs(null);
    const wrong = withTs(JSON.stringify({ deps_sha256: "0".repeat(64) }));
    const late = withTs(null);
    const listed = withTs("[1, 2]"); // 合法 JSON，不是对象：当成没对上
    const stamp = (sc: Scene): string => JSON.stringify({ deps_sha256: digestOf(sc) });
    const states = agreeFlow([
      install(broken, [kernelImpl(ON_TS), findBun(null)]),
      install(good, [kernelImpl(ON_TS), findBun(BUN), runner(good, { exit_code: 0, timed_out: false }, output("装"), stamp(good))]),
      install(stale, [kernelImpl(ON_TS), findBun(BUN), runner(stale, { exit_code: 0, timed_out: false }, output("装"), null)]),
      install(slow, [kernelImpl(ON_TS), findBun(BUN), runner(slow, { exit_code: null, timed_out: true }, Buffer.from(many("还在装", 30, "长".repeat(200))), null)]),
      install(wrong, [kernelImpl(ON_TS), findBun(null)]),
      install(late, [kernelImpl(ON_TS), findBun(BUN), runner(late, { exit_code: 0, timed_out: true }, output("装"), stamp(late))]),
      install(listed, [kernelImpl(ON_TS), findBun(null)]),
    ]);
    injectedCleanly(states);
    const [brokenOk, brokenSummary] = returned(states[0]) as [boolean, string];
    expect([brokenOk, brokenSummary]).toEqual([false, "找不到 Bun：PATH 上既没有 bun.exe，也没有 npm 的 bun.cmd 垫片"]);
    const [goodOk, goodSummary] = returned(states[1]) as [boolean, string];
    expect([goodOk, goodSummary.split(LF).length, goodSummary.split(LF)[0]]).toEqual([true, 11, "主工作区 ts/ 重装依赖（bun install --frozen-lockfile）：装好了"]);
    expect((returned(states[2]) as [boolean, string])[1].split(LF)[0]).toBe("主工作区 ts/ 重装依赖（bun install --frozen-lockfile）：没装好（退出码 0）");
    expect((returned(states[3]) as [boolean, string])[1].length, "摘要长过 1500 字，信里的验证才截得到").toBeGreaterThan(1500);
    expect((returned(states[3]) as [boolean, string])[1].split(LF)[0]).toBe("主工作区 ts/ 重装依赖（bun install --frozen-lockfile）：没装好（退出码 None，超时）");
    expect((returned(states[4]) as [boolean, string])[0], "戳记在但哈希不对：照样要装").toBe(false);
    expect((returned(states[5]) as [boolean, string])[1].split(LF)[0]).toBe("主工作区 ts/ 重装依赖（bun install --frozen-lockfile）：没装好（退出码 0，超时）");
    expect(returned(states[6]), "戳记是数组：照样要装").toEqual([false, "找不到 Bun：PATH 上既没有 bun.exe，也没有 npm 的 bun.cmd 垫片"]);
    expect(states.map((state) => letters(state).length)).toEqual([1, 0, 1, 1, 1, 1, 1]);
  }, 600_000);
});

describe("第 ⑤h2 片：mark_owner_moved、read_owner_sweep、rehearsal_letter（手写）", () => {
  it("mark_owner_moved：没有待跑时 since 记动之前的末端；已有待跑时 since 留着第一次之前的，命令只记前 6 个；read_owner_sweep 读不出、坏 JSON、不是对象都是 {}", () => {
    const first = scene(BASE, () => undefined, false);
    const again = scene(BASE, (repo) => put(repo, OWNER, JSON.stringify({ pending: true, head: "b".repeat(40), since: "a".repeat(40), command: ["git"], at: AT })), false);
    const states = agreeFlow([
      flow("mark_owner_moved", first, ["1".repeat(40), "2".repeat(40), ["git", "commit", "-q", "-m", "一轮"]]),
      flow("mark_owner_moved", again, ["3".repeat(40), "4".repeat(40), ["git", "merge", "--ff-only", "x", "y", "z", "w", "v"]]),
    ]);
    const owner = (state: Record<string, unknown> | undefined): Record<string, unknown> =>
      JSON.parse(Buffer.from(written(state)[`0/${OWNER}`] as string, "base64").toString("utf8")) as Record<string, unknown>;
    expect([owner(states[0])["since"], owner(states[1])["since"], (owner(states[1])["command"] as string[]).length]).toEqual(["1".repeat(40), "a".repeat(40), 6]);
    const shaped = (body: string | null): Scene => scene(BASE, (repo) => {
      if (body !== null) put(repo, OWNER, body);
    }, false);
    const reads = [shaped(null), shaped("{坏"), shaped("[1, 2]"), shaped(JSON.stringify({ pending: false }))];
    const results = agreeCalls(reads.map((sc) => ({ op: "hub.contract", fn: "read_owner_sweep", args: [toTagged(sc.repo)], restores: sc.restores })));
    expect(results.map(valueOf)).toEqual([new Map(), new Map(), new Map(), new Map([["pending", false]])]);
  }, 600_000);

  it("rehearsal_letter：验证截 1500 字", () => {
    const sc = scene(BASE, () => undefined, false);
    const states = agreeFlow([flow("rehearsal_letter", sc, [sweepTs(sc), many("预演没过", 40), "站主的提交之后"])]);
    const letter = letters(states[0])[0] ?? "";
    expect([letters(states[0]).length, letter.includes("预演没过 40"), letter.includes("预演没过 1 ")]).toEqual([1, false, true]);
  }, 600_000);
});

describe("第 ⑤h2 片：rehearse_landing（手写）", () => {
  const RUN = ".agent/runs/t001-doc/attempt-001";
  /** B0（场景的 head）上，主分支前进了一个“并行主任务”的提交；oracle 是给定的提交，attempt 的基线是 B0。 */
  function rehearsal(oracleFiles: Record<string, string> | null, patch: string, meanwhile: Record<string, string> = { "src/m.py": lines("m = 1") }):
    { sc: Scene; oracle: string } {
    let oracle = "";
    const sc = scene({ ...BASE, [GATE_OK]: lines("def test_ok():", "    assert True") }, (repo, _wt, head) => {
      oracle = head;
      if (oracleFiles !== null) {
        for (const [rel, content] of Object.entries(oracleFiles)) put(repo, rel, content);
        git(repo, "add", "-A");
        git(repo, "commit", "-q", "--allow-empty", "-m", "门禁基准测试"); // 不给文件时是空提交
        oracle = git(repo, "rev-parse", "HEAD");
        git(repo, "reset", "-q", "--hard", head);
      }
      for (const [rel, content] of Object.entries(meanwhile)) put(repo, rel, content);
      git(repo, "add", "-A");
      git(repo, "commit", "-q", "-m", "并行主任务先落地");
      put(repo, `${RUN}/meta.json`, JSON.stringify({ base_sha: head }));
      put(repo, `${RUN}/candidate.patch`, patch);
    }, false);
    return { sc, oracle };
  }
  const tsOf = (item: { sc: Scene; oracle: string }): PyDict =>
    sweepTs(item.sc, { exec: { run_dir: join(item.sc.repo, ...RUN.split("/")), check_ok: true }, oracle: { sha: item.oracle, files: [GATE_OK] } });
  const worktreeOnly = (sc: Scene): { inner: unknown[]; replaced: string[]; fresh: string[] } => {
    const s = scratch(sc, "rehearse", 0, "", []);
    return { inner: s.inner.slice(0, 2), replaced: ["worktree_root", "mkdtemp"], fresh: [s.made] };
  };
  /** 十个打不上的改动：git apply 的报错多过 8 行。 */
  const badPatch = Array.from({ length: 10 }, (_, at) =>
    lines(`diff --git a/src/zz${at}.py b/src/zz${at}.py`, `--- a/src/zz${at}.py`, `+++ b/src/zz${at}.py`, "@@ -1 +1 @@", "-old", "+new")).join("");

  it("门禁没过（输出长过 15 行）、基准测试挑不上（git 的输出多过 8 行）、候选补丁打不上（多过 8 行）；末端就是 base_head 时也先算 attempt_base，ts 没有 oracle 照样崩", () => {
    const red = rehearsal(null, "");
    const clash = rehearsal({ "src/doc.py": lines("def title():", "    return 'oracle'") }, "", { "src/doc.py": lines("def title():", "    return 'meanwhile'") });
    const broken = rehearsal(null, badPatch);
    const same = scene(BASE, (repo) => put(repo, `${RUN}/candidate.patch`, ""), false);
    const sameTs = sweepTs(same, { exec: { run_dir: join(same.repo, ...RUN.split("/")), check_ok: true } });
    sameTs.delete("oracle");
    const redRun = scratch(red.sc, "rehearse", 1, many("FAILED 第", 20), [GATE_OK]);
    const states = agreeFlow([
      flow("rehearse_landing", red.sc, [tsOf(red)], scratchExtra(redRun)), flow("rehearse_landing", clash.sc, [tsOf(clash)], worktreeOnly(clash.sc)),
      flow("rehearse_landing", broken.sc, [tsOf(broken)], worktreeOnly(broken.sc)), flow("rehearse_landing", same, [sameTs]),
    ]);
    injectedCleanly(states);
    const [ok, problem] = returned(states[0]) as [boolean, string];
    expect([ok, problem.includes("FAILED 第 20"), problem.includes("FAILED 第 5 "), problem.includes("并行主任务先落地")]).toEqual([false, true, false, true]);
    expect(String((returned(states[1]) as PyValue[])[1])).toContain(`提交 ${clash.oracle.slice(0, 12)} 挑不到末端`);
    expect(String((returned(states[2]) as PyValue[])[1])).toContain("候选补丁（attempt-001）打不到末端");
    expect((states[3]?.["result"] as Record<string, unknown>)["error"]).toBe("KeyError");
  }, 600_000);

  it("早退：末端就是 base_head（attempt 的基线不同）、这个候选在这个末端上预演过、check 没过；oracle 是空提交时不挑，照样跑门禁", () => {
    const tipOf = (sc: Scene): string => git(sc.repo, "rev-parse", "HEAD");
    const runDir = (sc: Scene): string => join(sc.repo, ...RUN.split("/"));
    const atBase = rehearsal(null, "");
    const seen = rehearsal(null, "");
    const unchecked = rehearsal(null, "");
    const empty = rehearsal({}, "");
    const atBaseTs = tsOf(atBase);
    atBaseTs.set("base_head", tipOf(atBase.sc));
    const seenTs = tsOf(seen);
    seenTs.set("rehearsal", py({ head: tipOf(seen.sc), run_dir: runDir(seen.sc), ok: true, at: AT }));
    const uncheckedTs = sweepTs(unchecked.sc, { exec: { run_dir: runDir(unchecked.sc), check_ok: false }, oracle: { sha: unchecked.oracle, files: [GATE_OK] } });
    const emptyRun = scratch(empty.sc, "rehearse", 0, lines("1 passed in 0.01s"), [GATE_OK]);
    const states = agreeFlow([
      flow("rehearse_landing", atBase.sc, [atBaseTs]), flow("rehearse_landing", seen.sc, [seenTs]), flow("rehearse_landing", unchecked.sc, [uncheckedTs]),
      flow("rehearse_landing", empty.sc, [tsOf(empty)], scratchExtra(emptyRun)),
    ]);
    injectedCleanly(states);
    expect(states.slice(0, 3).map(returned)).toEqual([null, null, null]);
    expect(returned(states[3])).toEqual([true, `末端 ${tipOf(empty.sc).slice(0, 12)} 加上 attempt-001 的候选，全部门禁基准（1 份）：1 passed in 0.01s`]);
  }, 600_000);
});
