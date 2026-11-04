// 第 ⑤j1 片的手写对照（采样那份在 hub-commands.contract.test.ts）：临时仓库上摆好信箱与 state.json，三边各自先原地放回再跑站主命令，交回值、
// 文件、账本、git 状态与 stdout、stderr 逐字比（⑤j 设计稿第 4 节）。只补采样走不到的：
//   - 整份测试里没有用例调的 cmd_init、cmd_take、cmd_exec_recheck；
//   - 采样跳过的那一次：status 时 T002 的 runner 锁被另一个进程（真的 Python 子进程，kit_hub.DirLock）拿着；lock_alive 的几种 owner.json；
//     runner.json 的几种写法；
//   - task_quiet：主任务的 runner 锁有活的持有者时先打印“等 … 办完手上这一步”再等；supervisor 拿着总锁时只等主任务的锁。
// 不写转义序列。
import { type ChildProcess, spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { COORDINATOR, OWNER } from "@themis/hub/constants";
import { Hub, canonicalState } from "@themis/hub/mailbox";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { toTagged } from "../src/tagged.ts";
import { REPO, REPLAY_TIMEOUT } from "./harness.ts";
import { AT, BT, LF, type Scene, agreeFlow, flow, kernelPython, pd, py, returned, scene, written } from "./flow-fixtures.ts";
import { put, removeCreated, tempDir } from "./repo-fixtures.ts";
import { BASE_FILES, BOX, failure, letter, lettersTo, setStage, stateAfter } from "./engine-fixtures.ts";
import { holdLock } from "./runner-fixtures.ts";

afterAll(removeCreated);

/** 状态里的 T001（照 test_kit_hub 的 make_ts），edit 再改它。 */
function stateScene(edit: (ts: PyDict, repo: string) => void = () => undefined, more: (repo: string) => void = () => undefined, files = BASE_FILES): Scene {
  return scene(files, (repo, _wt, head) => {
    new Hub(repo).ensure();
    const ts = newTaskState("T001", "doc", "改桌面端文档", head, true, AT);
    edit(ts, repo);
    put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map<string, PyValue>([["tasks", new Map([["T001", ts]])]])));
    more(repo);
  }, false);
}

const stdoutOf = (state: Record<string, unknown> | undefined): string => state?.["stdout"] as string;
const command = (repo: string, name: string, more: Record<string, unknown> = {}): Record<string, unknown> => ({ repo, command: name, ...more });
const task = (repo: string, name: string, more: Record<string, unknown>): Record<string, unknown> => ({ repo, command: "task", task_command: name, ...more });

describe("第 ⑤j1 片：整份测试里没有用例调的命令（手写）", () => {
  it("init：信箱被 .gitignore 忽略时只报信箱路径，没忽略时多一行 WARN", () => {
    const ignored = scene({ ...BASE_FILES, ".gitignore": `.agent/mailbox/${LF}` }, () => undefined, false);
    const plain = scene(BASE_FILES, () => undefined, false);
    const [first, second] = agreeFlow([flow("cmd_init", ignored, [command(ignored.repo, "init")]), flow("cmd_init", plain, [command(plain.repo, "init")])]);
    expect([returned(first), returned(second)]).toEqual([0n, 0n]);
    expect(stdoutOf(first).includes("WARN")).toBe(false);
    expect(stdoutOf(second).split(LF)[1]).toBe("WARN  .agent/mailbox/ 没有被 .gitignore 忽略");
  }, 600_000);

  it("take：逐封打印站主的未读信，--peek 只看不挪；没有未读信时说一句", () => {
    const two = (): Scene => stateScene(() => undefined, (repo) => {
      letter(repo, OWNER, "20261101T000001000000Z-kernel-000000", "kernel", "T001", "阻塞");
      letter(repo, OWNER, "20261101T000002000000Z-kernel-000000", "kernel", "T001", "汇报");
    });
    const peek = two();
    const take = two();
    const empty = stateScene();
    const [first, second, third] = agreeFlow([
      flow("cmd_take", peek, [command(peek.repo, "take", { peek: true })]), flow("cmd_take", take, [command(take.repo, "take", { peek: false })]),
      flow("cmd_take", empty, [command(empty.repo, "take", { peek: false })]),
    ]);
    const moved = (state: Record<string, unknown> | undefined): string[] => Object.keys(written(state)).filter((key) => key.includes(`/inbox/${OWNER}/cur/`));
    expect([Object.keys(written(first)), moved(second).length]).toEqual([[], 2]);
    expect(stdoutOf(first).split("msg-id: ").length - 1).toBe(2);
    expect(stdoutOf(third)).toBe(`（站主没有未读信）${LF}`);
  }, 600_000);

  it("exec-recheck：执行阶段没判失败时报错；判失败、attempt 目录还在时重新核验并打印结果，退出码看 check_ok", () => {
    const locked = (ts: PyDict): void => {
      (ts.get("contract") as PyDict).set("validated", true).set("sha256", "c1").set("key", "t001-doc.v1").set("version", 1n);
      (ts.get("oracle") as PyDict).set("sha", "o".repeat(40)).set("locked", true);
      for (const suffix of ["1-plan", "2-contract", "3-gate-pre"]) ((ts.get("stages") as PyDict).get(suffix) as PyDict).set("status", "delivered");
    };
    const runDir = (repo: string): string => join(repo, ".agent", "runs", "t001-doc", "attempt-002");
    const attempt = (repo: string): void => {
      put(runDir(repo), "state.json", JSON.stringify({ state: "NEEDS_REVIEW" }));
      put(runDir(repo), "scope.json", JSON.stringify({ violations: [], files: [] }));
      put(runDir(repo), "executor-report.json", JSON.stringify({ executor_status: "completed", dod: [] }));
    };
    const at = (failed: boolean) => stateScene((ts, repo) => {
      locked(ts);
      ts.set("exec", py({ run_dir: runDir(repo), run_exit: 0, check_ok: false, status: null }));
      if (failed) setStage(ts, "5-exec", py({ status: "failed", assigned_at: AT, kind: "开工" }));
    }, attempt);
    const idle = at(false);
    const failed = at(true);
    const [first, second] = agreeFlow([
      flow("cmd_exec_recheck", idle, [command(idle.repo, "exec-recheck", { task: "T001" })]),
      flow("cmd_exec_recheck", failed, [command(failed.repo, "exec-recheck", { task: "T001" })], { inner: [pd(["check", runDir(failed.repo), "--fresh"], 0, "ok", 3600)] }),
    ]);
    expect(failure(first)[0]).toBe("HubError");
    expect([returned(second), stdoutOf(second)]).toEqual([0n, `T001 执行阶段重新核验：通过（attempt 状态 NEEDS_REVIEW，check --fresh 退出码 0，范围违规 0）${LF}`]);
    expect(lettersTo(second, COORDINATOR)).toHaveLength(1);
  }, 600_000);
});

describe("第 ⑤j1 片：锁与并行的设置（手写）", () => {
  it("status：另一个进程拿着 T002 的 runner 锁时列出它；owner.json 读不出当成刚建（算活着），持有者已经退出的不算；runner.json 的几种写法", () => {
    const held: ChildProcess[] = [];
    try {
      const busy = stateScene(() => undefined, (repo) => {
        const runners = join(repo, ...`${BOX}/.runners`.split("/"));
        holdLock(join(runners, "T002"), held);
        put(join(runners, "T003"), "owner.json", "{");
        put(join(runners, "T004"), "owner.json", JSON.stringify({ pid: 4242 }));
        put(join(runners, "T005"), "owner.json", new Uint8Array([0xff, 0xfe, 0x41])); // 不是 UTF-8：Python 的 except ValueError 接住，算活着
        put(repo, `${BOX}/runner.json`, JSON.stringify({ parallel: "3" }));
      });
      const broken = stateScene(() => undefined, (repo) => put(repo, `${BOX}/runner.json`, "{"));
      const word = stateScene(() => undefined, (repo) => put(repo, `${BOX}/runner.json`, JSON.stringify({ parallel: "x" })));
      // PowerShell 5.1 的 Out-File 与 > 缺省写 UTF-16（带 BOM）：读不出，当成没写（themistally-04 在 Python 上实测）
      const utf16 = stateScene(() => undefined, (repo) => put(repo, `${BOX}/runner.json`,
        Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(JSON.stringify({ parallel: 3 }), "utf16le")])));
      // 持有者的死活照记录注入（runner 目录照码点次序问：T002 是拿着锁的子进程，T004 记的 pid 当它已经退出）：起一个进程等它退出、拿它的 pid
      // 当“已退出”，整套并行时 pid 会被别的进程复用（全量跑撞过一次，同 locks 的 CL4）
      const owners = [alive(held[0]?.pid as number, true), alive(4242, false)];
      const states = agreeFlow([
        flow("cmd_status", busy, [command(busy.repo, "status", { json: false })], { inner: owners, replaced: ["pid_alive"] }),
        flow("cmd_status", busy, [command(busy.repo, "status", { json: true })]),
        flow("cmd_status", broken, [command(broken.repo, "status", { json: false })]), flow("cmd_status", word, [command(word.repo, "status", { json: false })]),
        flow("cmd_status", utf16, [command(utf16.repo, "status", { json: false })]),
      ], undefined, REPLAY_TIMEOUT);
      const last = (state: Record<string, unknown> | undefined): string => stdoutOf(state).trimEnd().split(LF).at(-1) as string;
      expect(last(states[0])).toBe("并行：最多 3 个主任务；在跑的主任务 runner：T002、T003、T005；在跑的执行端：无");
      expect((JSON.parse(stdoutOf(states[1])) as { unread: Record<string, number> }).unread[OWNER]).toBe(0);
      expect([last(states[2]), last(states[3]), last(states[4])].map((line) => line.split("；")[0]))
        .toEqual(["并行：最多 1 个主任务", "并行：最多 1 个主任务", "并行：最多 1 个主任务"]);
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);

  it("task_quiet：主任务的 runner 锁有活的持有者、没有 supervisor 时先打印要等，等 1 秒拿不到报 BLOCKED；supervisor 拿着总锁时只等主任务的锁", () => {
    const held: ChildProcess[] = [];
    try {
      const stuck = (ts: PyDict): void => setStage(ts, "1-plan", py({ status: "assigned", assigned_at: AT, kind: "开工" }));
      const busy = stateScene(stuck, (repo) => holdLock(join(repo, ...`${BOX}/.runners/T001`.split("/")), held));
      const supervised = stateScene(stuck, (repo) => holdLock(join(repo, ...`${BOX}/.runner`.split("/")), held, "supervisor"));
      const args = (sc: Scene) => [task(sc.repo, "unstick", { task: "T001", stage: "1-plan", reason: "回合被收掉" })];
      const [first, second] = agreeFlow([flow("cmd_task_unstick", busy, args(busy)), flow("cmd_task_unstick", supervised, args(supervised))],
        undefined, REPLAY_TIMEOUT);
      expect([failure(first)[0], stdoutOf(first)]).toEqual(["HubError", `等 T001 的 runner 办完手上这一步（最长 1 秒）……${LF}`]);
      expect([returned(second), stdoutOf(second)]).toEqual([0n, `T001-1-plan 已标成 failed${LF}`]);
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);
});

const NOTHING = { write: {}, delete: [] };
/** 注入一次 pid_alive（采样的写法：问的 pid、交回值）。 */
const alive = (pid: number, answer: boolean | null): unknown => ({ fn: "pid_alive", pid, value: toTagged(answer), files: NOTHING });

/** 状态里有几个主任务（各照 make_ts 建，edit 再改）。 */
function tasksScene(edits: Record<string, (ts: PyDict) => void>): Scene {
  return scene(BASE_FILES, (repo, _wt, head) => {
    new Hub(repo).ensure();
    const tasks = new Map<string, PyValue>();
    for (const [name, edit] of Object.entries(edits)) {
      const ts = newTaskState(name, name.toLowerCase(), `主任务 ${name}`, head, true, AT);
      edit(ts);
      tasks.set(name, ts);
    }
    put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map<string, PyValue>([["tasks", tasks]])));
  }, false);
}

/** 合同已写好、没派遣的 T001（budget 的场景用）：plans 下的 md 与 json 照 test_owner_raises_the_attempt_budget 的写法。 */
function budgetScene(edit: (ts: PyDict) => void, md: string): Scene {
  return stateScene((ts) => {
    (ts.get("contract") as PyDict).set("validated", true).set("key", "t001-doc.v3").set("version", 3n).set("dispatched", false).set("md", ".agent/plans/t001-doc.v3.md");
    ts.set("exec", py({ run_dir: "r", check_ok: false, attempts_left: 0 }));
    setStage(ts, "5-exec", py({ status: "failed", assigned_at: AT, kind: "开工" }));
    edit(ts);
  }, (repo) => {
    put(repo, ".agent/plans/t001-doc.v3.md", md);
    put(repo, ".agent/plans/t001-doc.v3.json", JSON.stringify({ budget: { max_attempts_total: 2, max_wall_seconds_per_attempt: 100, max_wall_seconds_total: 99999 } }));
  });
}
const BUDGET_MD = [
  "# TASK: t001-doc", "- plan_version: 3", `- base_sha: ${"o".repeat(40)}`, "", "## Budget", "- max_attempts_total: 2",
  "- max_wall_seconds_per_attempt: 100", "- max_wall_seconds_total: 99999", "",
].join(LF);

describe("第 ⑤j1 片：变异补的场景（手写，各条 it 的标题里写了对着哪条变异）", () => {
  it("task new：主任务号、slug 不合格与已登记过的都拒（J13、J14、J16）；--no-jev 记进状态（J20）；任务书里不带斜杠的路径不查（J23），几处没提交的照路径排（J26）", () => {
    const dir = tempDir("brief");
    put(dir, "plain.md", `# 任务书${LF}先看 ${BT}notes.md${BT}${LF}`);
    put(dir, "two.md", `# 任务书${LF}${BT}docs/b.md${BT} 与 ${BT}docs/a.md${BT}${LF}`);
    const fresh = (): Scene => stateScene(() => undefined, (repo) => {
      put(repo, "notes.md", "草稿");
      put(repo, "docs/a.md", "a");
      put(repo, "docs/b.md", "b");
    });
    const scenes = [fresh(), fresh(), fresh(), fresh(), fresh()];
    const args = (at: number, more: Record<string, unknown>) => [task((scenes[at] as Scene).repo, "new", {
      task: "T002", slug: "next", title: "下一片", brief: join(dir, "plain.md"), no_jev: false, after: null, ...more,
    })];
    const states = agreeFlow([
      flow("cmd_task_new", scenes[0] as Scene, args(0, { task: "X1" })), flow("cmd_task_new", scenes[1] as Scene, args(1, { slug: "Bad_Slug" })),
      flow("cmd_task_new", scenes[2] as Scene, args(2, { task: "T001" })), flow("cmd_task_new", scenes[3] as Scene, args(3, { no_jev: true })),
      flow("cmd_task_new", scenes[4] as Scene, args(4, { brief: join(dir, "two.md") })),
    ]);
    expect(states.slice(0, 3).map((state) => failure(state)[1])).toEqual(["主任务号要像 T001", "--slug 只能是小写字母、数字与连字符", "主任务 T001 已存在"]);
    expect([returned(states[3]), stateAfter(states[3])["T002"]?.["jev_enabled"]]).toEqual([0n, false]);
    expect(failure(states[4])[1]).toContain("docs/a.md 没有提交；docs/b.md 没有提交");
  }, 600_000);

  it("task close：结项收尾没做完的逐条打印（J32）", () => {
    const stray = join(tempDir("stray"), "not-a-worktree");
    put(stray, "x.txt", "不是 worktree");
    const dir = tempDir("note");
    put(dir, "note.md", "站主在分支上补完了");
    const sc = stateScene((ts) => void (ts.get("workspaces") as PyDict).set("base", py({ path: stray, commit: ts.get("base_head") })));
    const [state] = agreeFlow([flow("cmd_task_close", sc, [task(sc.repo, "close", { task: "T001", ref: "HEAD", file: join(dir, "note.md") })])]);
    expect(returned(state)).toBe(0n);
    expect(stdoutOf(state).split(LF)[1]).toMatch(new RegExp("^结项收尾没做完："));
  }, 600_000);

  it("task after：几项依赖照主任务号排（J41）", () => {
    const sc = tasksScene({ T001: () => undefined, T002: () => undefined, T003: () => undefined });
    const [state] = agreeFlow([flow("cmd_task_after", sc, [task(sc.repo, "after", { task: "T001", on: "T003,T002", reason: "要用它们新加的接口" })])]);
    expect([returned(state), stateAfter(state)["T001"]?.["after"]]).toEqual([0n, ["T002", "T003"]]);
  }, 600_000);

  it("task budget：墙钟取原有与补足后的较大值（J52）；Budget 行不唯一时不改（J54）；执行端在办（J56）、主任务停了（J58）都不追加", () => {
    // revalidate_contract 照真的跑，只换掉 run_pd（derive-json、validate 各一次）；最小合同过不了 contract_requirements，报“没有追加成”，
    // 合同文件已经改写，比的就是改写成什么
    const inner = [pd(["derive-json", "t001-doc.v3", "--force", "--title", "改桌面端文档"], 0, "ok"), pd(["validate", "t001-doc.v3"], 0, "ok")];
    const raise = budgetScene(() => undefined, BUDGET_MD);
    const twice = budgetScene(() => undefined, `${BUDGET_MD}- max_attempts_total: 2${LF}`);
    const busy = budgetScene((ts) => setStage(ts, "5-exec", py({ status: "assigned", assigned_at: AT, kind: "返工" })), BUDGET_MD);
    const stopped = budgetScene((ts) => void ts.set("status", "stopped"), BUDGET_MD);
    const args = (sc: Scene) => [task(sc.repo, "budget", { task: "T001", attempts: 3, reason: "内核用掉了一次" })];
    const states = agreeFlow([
      flow("cmd_task_budget", raise, args(raise), { inner, replaced: ["run_pd"] }), flow("cmd_task_budget", twice, args(twice)),
      flow("cmd_task_budget", busy, args(busy)), flow("cmd_task_budget", stopped, args(stopped)),
    ]);
    const md = Buffer.from(written(states[0])["0/.agent/plans/t001-doc.v3.md"] as string, "base64").toString("utf8");
    expect(md).toContain("- max_wall_seconds_total: 99999");
    expect(states.slice(1).map((state) => failure(state).map(String)))
      .toEqual([["HubError", "预算没有追加成：合同 Budget 里找不到唯一的“- max_attempts_total:”行"], ["HubError", "T001 的执行端正在办：等它交付再追加"],
        ["HubError", "T001 是 stopped、合同 t001-doc.v3：没有可追加预算的执行阶段"]]);
  }, 600_000);

  it("send：回信让 blocked 的主任务恢复成 active、拒收计数清零（J67）；停止把主任务标 stopped（J73）；摘要 35 行能投、36 行拒收（J71）", () => {
    const blocked = stateScene((ts) => void ts.set("status", "blocked").set("coordinator_rejections", 2n));
    const plain = (): Scene => stateScene();
    const [stop, short, long] = [plain(), plain(), plain()];
    const send = (sc: Scene, kind: string, text: string) => ({
      ...flow("cmd_send", sc, [{ repo: sc.repo, command: "send", task: "T001", type: kind, file: "-", reply_to: null, rework: null, facts_checked: false,
        decision: false, no_decision: false }]),
      stdin: text,
    });
    const lines = (count: number): string => Array.from({ length: count }, (_, at) => `第 ${at + 1} 行`).join(LF);
    const states = agreeFlow([
      send(blocked, "回复", "环境修好了"), send(stop, "停止", "这一片不做了"), send(short, "回复", lines(35)), send(long, "回复", lines(36)),
    ]);
    const ts = (at: number): Record<string, unknown> | undefined => stateAfter(states[at])["T001"];
    expect([ts(0)?.["status"], ts(0)?.["coordinator_rejections"], ts(1)?.["status"]]).toEqual(["active", 0, "stopped"]);
    expect([returned(states[2]), failure(states[3])[0]]).toEqual([0n, "HubError"]);
  }, 600_000);

  it("exec-recheck：check --fresh 没过时打印未通过、退出码 1（J74）", () => {
    const runDir = (repo: string): string => join(repo, ".agent", "runs", "t001-doc", "attempt-002");
    const sc = stateScene((ts, repo) => {
      (ts.get("contract") as PyDict).set("validated", true).set("sha256", "c1").set("key", "t001-doc.v1").set("version", 1n);
      (ts.get("oracle") as PyDict).set("sha", "o".repeat(40)).set("locked", true);
      for (const suffix of ["1-plan", "2-contract", "3-gate-pre"]) ((ts.get("stages") as PyDict).get(suffix) as PyDict).set("status", "delivered");
      setStage(ts, "5-exec", py({ status: "failed", assigned_at: AT, kind: "开工" }));
      ts.set("exec", py({ run_dir: runDir(repo), run_exit: 0, check_ok: false, status: null }));
    }, (repo) => {
      put(runDir(repo), "state.json", JSON.stringify({ state: "NEEDS_REVIEW" }));
      put(runDir(repo), "scope.json", JSON.stringify({ violations: [], files: [] }));
      put(runDir(repo), "executor-report.json", JSON.stringify({ executor_status: "completed", dod: [] }));
    });
    const [state] = agreeFlow([flow("cmd_exec_recheck", sc, [command(sc.repo, "exec-recheck", { task: "T001" })],
      { inner: [pd(["check", runDir(sc.repo), "--fresh"], 1, "V01 没过", 3600)] })]);
    expect([returned(state), stdoutOf(state).startsWith("T001 执行阶段重新核验：未通过")]).toEqual([1n, true]);
  }, 600_000);

  // parallel 写 0 时 Python 的 value or 1 先变成 1，走不到 max(1, …)；写负数才看得出保底（第一次写 0，J06 漏过）
  it("锁：pid 问不出死活的持有者算活着（J02）；runner 目录照码点排（J77）；runner.json 的 parallel 是负数时最多 1（J06）", () => {
    const sc = stateScene(() => undefined, (repo) => {
      const runners = join(repo, ...`${BOX}/.runners`.split("/"));
      put(join(runners, "T006"), "owner.json", JSON.stringify({ pid: 4242 }));
      put(join(runners, "b-x"), "owner.json", "{");
      put(join(runners, "T003"), "owner.json", "{");
      put(repo, `${BOX}/runner.json`, JSON.stringify({ parallel: -2 }));
    });
    const [state] = agreeFlow([flow("cmd_status", sc, [command(sc.repo, "status", { json: false })], { inner: [alive(4242, null)], replaced: ["pid_alive"] })]);
    expect(stdoutOf(state).trimEnd().split(LF).at(-1)).toBe("并行：最多 1 个主任务；在跑的主任务 runner：T003、T006、b-x；在跑的执行端：无");
  }, 600_000);

  it("task_quiet：.runner 有人拿着、却不是 supervisor 时照样要拿总锁（J03）；暂停标记里的 pid 是命令自己的进程，别的进程问得到它活着（J11）", () => {
    const held: ChildProcess[] = [];
    const log = join(tempDir("spy"), "seen.jsonl");
    try {
      const stuck = (ts: PyDict): void => setStage(ts, "1-plan", py({ status: "assigned", assigned_at: AT, kind: "开工" }));
      const serial = stateScene(stuck, (repo) => holdLock(join(repo, ...`${BOX}/.runner`.split("/")), held));
      const watched = stateScene(stuck, (repo) => {
        holdLock(join(repo, ...`${BOX}/.runners/T001`.split("/")), held);
        // 盯着暂停标记的进程：每看到一份新的标记就记下里面的 pid 还活不活着（命令要等 1 秒拿 runner 锁，标记这段时间都在）
        const spy = [
          "import json, sys, time", "sys.path.insert(0, sys.argv[1])", "import kit_hub", "seen = set()", "while True:",
          "    try:", "        text = open(sys.argv[2], encoding='utf-8').read()", "    except OSError:", "        text = ''",
          "    if text and text not in seen:", "        seen.add(text)", "        data = json.loads(text)",
          "        alive = kit_hub.pd.pid_alive(int(data['pid'])) if data.get('pid') else None",
          "        open(sys.argv[3], 'a', encoding='utf-8').write(json.dumps({'alive': alive, 'at': data.get('at')}) + chr(10))",
          "    time.sleep(0.02)",
        ].join(LF);
        held.push(spawn(kernelPython(), ["-c", spy, join(REPO, "scripts"), join(repo, ...`${BOX}/.pause/T001`.split("/")), log], { stdio: "ignore" }));
      });
      const args = (sc: Scene) => [task(sc.repo, "unstick", { task: "T001", stage: "1-plan", reason: "回合被收掉" })];
      const [first, second] = agreeFlow([flow("cmd_task_unstick", serial, args(serial)), flow("cmd_task_unstick", watched, args(watched))],
        undefined, REPLAY_TIMEOUT);
      expect([failure(first)[0], failure(second)[0]]).toEqual(["HubError", "HubError"]);
      const seen = readFileSync(log, "utf8").split(LF).filter(Boolean).map((line) => JSON.parse(line) as { alive: unknown; at: unknown });
      expect(seen).toEqual([1, 2, 3].map(() => ({ alive: true, at: AT })));
    } finally {
      for (const child of held) child.kill();
    }
  }, 1_800_000);
});

describe("第 ⑤j1 片：themistally-04 抽查补的场景（手写，标题里写了对着哪条抽查）", () => {
  it("send：没登记的主任务带 --decision 回复，先报没有登记，信不投（S05）", () => {
    const sc = stateScene();
    const [state] = agreeFlow([{
      ...flow("cmd_send", sc, [{ repo: sc.repo, command: "send", task: "T009", type: "回复", file: "-", reply_to: null, rework: null, facts_checked: false,
        decision: true, no_decision: false }]),
      stdin: "照这个改",
    }]);
    expect([failure(state)[1], lettersTo(state, COORDINATOR)]).toEqual(["没有登记主任务 T009", []]);
  }, 600_000);

  it("status：.runner 的 owner.json 带结尾换行时照去空白（S08）；锁目录里还没有 owner.json、或是空文件，都算活着（S11）", () => {
    // DirLock 先建目录、再写带换行的 owner.json（kit_hub.py:897–899）：中间那一刻目录在、文件还没有
    const sc = stateScene(() => undefined, (repo) => {
      put(repo, `${BOX}/.runner/owner.json`, `${JSON.stringify({ pid: 4242, token: "t", at: AT })}${LF}`);
      put(repo, `${BOX}/.runners/T008/owner.json`, "");
      put(join(repo, ...`${BOX}/.runners/T007`.split("/")), ".keep", "");
    });
    const [state] = agreeFlow([flow("cmd_status", sc, [command(sc.repo, "status", { json: false })])]);
    const lines = stdoutOf(state).trimEnd().split(LF);
    expect(lines.slice(-2)).toEqual([
      `运行中的 hub：${JSON.stringify({ pid: 4242, token: "t", at: AT })}`, "并行：最多 1 个主任务；在跑的主任务 runner：T007、T008；在跑的执行端：无",
    ]);
  }, 600_000);

  it("metrics：回合记录没有 session_key 时主任务写问号（S09）；同一个 run_dir 的第二条 exec.finished 不再算一次（S10）", () => {
    const turns = stateScene(() => undefined, (repo) => put(repo, `${BOX}/turns/planner-opus/t1/result.json`, JSON.stringify({
      turn_id: "20261101T000000000000Z-ab", agent: "planner-opus", wall_seconds: 60, cost_usd: 0.5, session_cost_usd: 0.5,
    })));
    const event = (kind: string, at: string): string => JSON.stringify({ at, event: kind, task: "T001", run_dir: "r1" });
    const ledger = stateScene(() => undefined, (repo) => put(repo, `${BOX}/ledger/events.jsonl`, [
      event("exec.started", AT), event("exec.finished", "2026-11-01T00:10:00Z"), event("exec.finished", "2026-11-01T00:20:00Z"), "",
    ].join(LF)));
    const states = agreeFlow([
      flow("cmd_metrics", turns, [command(turns.repo, "metrics", { json: true })]), flow("cmd_metrics", turns, [command(turns.repo, "metrics", { json: false })]),
      flow("cmd_metrics", ledger, [command(ledger.repo, "metrics", { json: true })]),
    ]);
    const parsed = (at: number) => JSON.parse(stdoutOf(states[at])) as { turns: { task: string }[]; exec: Record<string, { attempts: number }> };
    expect([parsed(0).turns.map((row) => row.task), stdoutOf(states[1]).split(LF)[0], parsed(2).exec["T001"]?.attempts]).toEqual([["?"], "## ?", 1]);
  }, 600_000);
});
