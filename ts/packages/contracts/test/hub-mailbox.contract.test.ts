// 第 ⑤b 片的契约（迁移计划第 ⑤ 步）：信箱、账本与状态。同一份步骤脚本交给 Python、Node、Bun，各在一个新信箱上跑，
// 比每一步的结果与信箱里落盘的文件（账本的 at、last_turn_at、内核信件的随机编号换成占位符）。场景照搬
// tests/test_kit_hub.py：投递不覆盖与收信、三方合并、工人的会话记录、扣信与放回、留档与信的归属、目录锁。
// 混跑：一套实现读完状态停住，另一套在中间读、改、存（不同键合并、同一键记冲突）；两套同时投递同一个编号、同时写会话。
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { COORDINATOR, KERNEL, OWNER } from "@themis/hub/constants";
import { newTaskState } from "@themis/hub/taskstate";
import { describe, expect, it } from "vitest";
import { toTagged } from "../src/tagged.ts";
import { IMPLS, type Impl, type ProbeResult, removeDir, runProbe, scratchDir, startProbe, withBackupPrivilege } from "./harness.ts";

const LF = String.fromCharCode(10);
const SEP = process.platform === "win32" ? String.fromCharCode(92) : "/";
const BASE = "a".repeat(40);
const PYTHON = IMPLS[0] as Impl;
const dict = (...entries: [string, PyValue][]): PyDict => new Map(entries);
const ts = (task: string, slug = "doc", jev = true): PyDict => newTaskState(task, slug, "标题", BASE, jev, "2026-10-29T00:00:00Z");
const fields = (extra: Record<string, string> = {}): PyDict =>
  new Map<string, PyValue>([["摘要", "做完了"], ["提交", "无"], ["验证", "无"], ["偏离", "无"], ["需协调人决定", "无"], ["证据", "无"], ...Object.entries(extra)]);
const head = (msgId: string | null, from: string, to: string, task: string, type: string): PyDict =>
  new Map<string, PyValue>([...(msgId === null ? [] : [["msg-id", msgId] as [string, PyValue]]), ["from", from], ["to", to], ["task-id", task], ["in-reply-to", "none"], ["type", type]]);
type Step = [string, ...PyValue[]];
const steps = (list: Step[]): unknown[][] => list.map(([name, ...args]) => [name, ...args.map((item) => toTagged(item))]);

/** 随机的信件编号（<时间>-<别名>-<6 位十六进制>）换成占位符。 */
const ID_RE = /[0-9]{8}T[0-9]{12}Z-[a-z0-9-]+?-[0-9a-f]{6}/g;
// 运行时现取的时间（今天与明天的 UTC 日期，跨零点也认）换成占位符；用例自己给的固定时间照样逐字比
const DAYS = [0, 1].map((offset) => new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10));
const NOW_RE = new RegExp(`(${DAYS.join("|")})T[0-9]{2}:[0-9]{2}:[0-9]{2}Z`, "g");
// 内核自己编号的信，编号是随机的，内容的 sha256 跟着不同；信的内容另在落盘文件里逐字比过
const SHA_RE = /[0-9a-f]{64}/g;
const normalize = (text: string): string => text.replace(ID_RE, "<ID>").replace(NOW_RE, "<AT>").replace(SHA_RE, "<SHA>");

/** 结果里的临时仓库路径换成 <REPO>（照 JSON 里转义过的写法找），随机编号与时间换成占位符。 */
const scrub = (value: unknown, repo: string): unknown => JSON.parse(normalize(JSON.stringify(value).split(JSON.stringify(repo).slice(1, -1)).join("<REPO>")));

/** 信箱里落盘的文件（锁文件除外），路径与内容里的随机编号与时间都换成占位符。 */
function snapshot(repo: string): string[] {
  const root = join(repo, ".agent", "mailbox");
  const out: string[] = [];
  const walk = (dir: string): void => {
    if (!existsSync(dir)) return;
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (!name.endsWith(".lock")) out.push(`${normalize(relative(root, path).split(SEP).join("/"))}${LF}${normalize(readFileSync(path, "utf8"))}`);
    }
  };
  walk(root);
  return out.sort();
}

function run(impl: Impl, list: Step[], setup: (repo: string) => void = () => undefined): { results: unknown; files: string[] } {
  const repo = scratchDir(`hubbox-${impl.name}`);
  try {
    setup(repo);
    const result = runProbe(impl, { op: "hub.box", repo, steps: steps(list) });
    expect(result.ok, JSON.stringify(result)).toBe(true);
    return { results: scrub(result["results"], repo), files: snapshot(repo) };
  } finally {
    removeDir(repo);
  }
}

/** 三套实现跑同一份脚本，结果与文件都与 Python 相同；另外交回 Python 的结果给用例断言要点。 */
function same(list: Step[], setup?: (repo: string) => void): { results: ProbeResult[]; files: string[] } {
  const [python, ...others] = IMPLS.map((impl) => run(impl, list, setup));
  for (const [index, other] of others.entries()) {
    const name = IMPLS[index + 1]?.name;
    // 先逐步比，报出第一处不同的步骤（整体比较的差异在长输出里会被折叠）
    const theirs = (other as { results: unknown[] }).results;
    const ours = (python as { results: unknown[] }).results;
    const at = ours.findIndex((item, step) => JSON.stringify(item) !== JSON.stringify(theirs[step]));
    expect(at < 0 ? null : { step: at, name: list[at]?.[0], python: ours[at], other: theirs[at] }, `${name} 与 Python 的第一处不同`).toBeNull();
    expect(other, `${name} 与 Python 不同`).toEqual(python);
  }
  return python as { results: ProbeResult[]; files: string[] };
}

describe("第 ⑤b 片：信箱、账本与状态（三套实现跑同一份脚本）", () => {
  it("B1 投递不覆盖：同一个编号第二次报 HubError；new 里按编号排序；收信移到 cur（test_delivery_never_overwrites_and_take_moves_to_cur）", () => {
    const first = "20260101T000000000000Z-owner-aaaaaa";
    const { results } = same([
      ["ensure"],
      ["deliver", head(first, OWNER, COORDINATOR, "T001", "任务"), fields()],
      ["deliver", head(first, OWNER, COORDINATOR, "T001", "任务"), fields({ 摘要: "别的内容" })],
      ["deliver", head("20250101T000000000000Z-owner-bbbbbb", OWNER, COORDINATOR, "T001", "任务"), fields()],
      ["unread", COORDINATOR], ["take_first", COORDINATOR], ["unread", COORDINATOR], ["take_first", "nobody"],
      ["deliver", head(null, KERNEL, OWNER, "T001", "核验"), fields()], ["ledger_events"],
    ]);
    expect(results[2]).toMatchObject({ ok: false, error: "HubError", code: 1, message: "信件编号冲突：<ID>" }); // 编号在比较前换成了占位符
  });

  it("B2 三方合并：按主任务、按键只写改过的；同一键以后存的为准并记 state.conflict；新主任务整个写；手搭的整份写（test_state_saves_merge_by_task_and_key）", () => {
    const { results } = same([
      ["ensure"], ["save_dict", dict(["tasks", dict(["T001", ts("T001")], ["T002", ts("T002", "x")])])],
      ["load", "mine"], ["load", "theirs"],
      ["set", "mine", "T001", "notes", ["T001 的 runner 写的"]], ["set", "theirs", "T002", "notes", ["T002 的 runner 写的"]],
      ["set", "theirs", "T001", "owner_rework", dict(["suffix", "2-contract"])],
      ["save", "theirs"], ["save", "mine"], ["read_state"],
      ["set", "mine", "T001", "status", "done"], ["save", "mine"], ["read_state"],
      ["load", "first"], ["load", "second"], ["set", "first", "T001", "notes", ["先"]], ["set", "second", "T001", "notes", ["后"]],
      ["del", "second", "T001", "owner_rework"], ["save", "first"], ["save", "second"], ["read_state"], ["ledger_events"],
      ["load", "later"], ["new_task", "later", "T003", ts("T003", "y", false)], ["save", "later"], ["read_state"],
      ["save_dict", dict(["tasks", dict(["T009", ts("T009")])])], ["read_state"],
    ]);
    expect(JSON.stringify(results[21])).toContain("state.conflict");
  });

  it("B3 回合结束只写本回合的会话，别的主任务写的会话留着（test_turn_end_keeps_the_sessions_other_tasks_wrote）", () => {
    same([
      ["ensure"], ["save_agent_record", "gate-sonnet", dict(["name", "gate-sonnet"], ["sessions", dict(["T001", dict(["id", "a"], ["turns", 3n])])])],
      ["save_agent_session", "gate-sonnet", "T002", dict(["id", "b"], ["turns", 1n])], ["save_agent_session", "gate-sonnet", "T001", dict(["id", "a"], ["turns", 4n])],
      ["agent_record", "gate-sonnet"], ["agent_record", "nobody"], ["agent_record", OWNER],
    ]);
  });

  it("B4 扣信与放回：额度限制写信给站主、内核自己等不写；到点放回 cur→new、阶段回到 assigned；阶段已经变了就丢掉、记 letters.dropped", () => {
    const state = ts("T001");
    ((state.get("stages") as PyDict).get("3-gate-pre") as PyDict).set("status", "assigned");
    ((state.get("stages") as PyDict).get("4-audit-pre") as PyDict).set("status", "assigned");
    const letter = (id: string, task: string): Step => ["deliver", head(id, COORDINATOR, "gate-sonnet", task, "开工"), fields()];
    same([
      ["ensure"], ["save_dict", dict(["tasks", dict(["T001", state])])],
      letter("20260101T000000000001Z-womovie-c8-000001", "T001-3-gate-pre"), letter("20260101T000000000002Z-womovie-c8-000002", "T001-3-gate-pre"),
      ["take_first", "gate-sonnet"], ["take_first", "gate-sonnet"],
      ["hold", "T001", "gate-sonnet", ["20260101T000000000001Z-womovie-c8-000001.md", "20260101T000000000002Z-womovie-c8-000002.md"], 1000000000n, "3-gate-pre", "turn-1", null],
      ["hold", "T001", "audit-sonnet", ["x.md"], 4102444800n, "4-audit-pre", "turn-2", "落地锁被占"],
      ["read_state"], ["unread", "gate-sonnet"], ["release"], ["unread", "gate-sonnet"], ["read_state"],
      ["hold", "T001", "gate-sonnet", ["gone.md"], 1000000000n, "3-gate-pre", "turn-3", "等一会儿"],
      ["load", "s"], ["set", "s", "T001", "stages", (() => {
        const stages = new Map(state.get("stages") as PyDict);
        stages.set("3-gate-pre", dict(["status", "delivered"]));
        return stages;
      })()], ["save", "s"], ["release"], ["read_state"], ["ledger_events"],
    ]);
  });

  it("B5 留档改名照序号往后排；信属于哪个主任务；账本坏行跳过", () => {
    same([
      ["ensure"], ["keep_previous", ".agent/mailbox/tasks/T001/brief.md"], ["keep_previous", ".agent/mailbox/tasks/T001/report.md"],
      ["deliver", head("20260101T000000000003Z-owner-000003", OWNER, COORDINATOR, "T001-2-contract", "回复"), fields()],
      ["letter_main", ".agent/mailbox/inbox/womovie-c8/new/20260101T000000000003Z-owner-000003.md"], ["letter_main", "nope.md"], ["ledger_events"],
    ], (repo) => {
      const dir = join(repo, ".agent", "mailbox", "tasks", "T001");
      mkdirSync(dir, { recursive: true });
      for (const name of ["brief.md", "brief.1.md", "brief.x.md", "BRIEF.2.MD", "report.txt"]) writeFileSync(join(dir, name), name);
      const ledger = join(repo, ".agent", "mailbox", "ledger");
      mkdirSync(ledger, { recursive: true });
      writeFileSync(join(ledger, "events.jsonl"), `{"event": "a"}${LF}坏行${LF}{"event": "b"}${LF}`);
    });
  });

  it("B8 重写报告之前先留档：三轮之后是 report.1.md、report.2.md 与最新的一份（test_rewritten_reports_and_briefs_keep_their_previous_versions）", () => {
    const report = ".agent/mailbox/tasks/T001/report.md";
    const { files } = same(["第一轮", "第二轮", "第三轮"].flatMap((text): Step[] => [["keep_previous", report], ["write_file", report, text]]));
    expect(files.filter((file) => file.startsWith("tasks/T001/"))).toEqual([
      `tasks/T001/report.1.md${LF}第一轮`, `tasks/T001/report.2.md${LF}第二轮`, `tasks/T001/report.md${LF}第三轮`,
    ]);
  });

  it("B6 目录锁：持有者已死就接管；持有者还活着就等到期限报 HubError（持有者照 dict 的 repr）", () => {
    const lockDir = (repo: string, pid: number): void => {
      const dir = join(repo, ".agent", "mailbox", "locks", "landing");
      mkdirSync(dir, { recursive: true });
      writeFileSync(join(dir, "owner.json"), `{"pid": ${pid}, "token": "tok", "at": "2026-10-29T00:00:00Z"}${LF}`);
    };
    const taken = same([["dirlock", ".agent/mailbox/locks/landing", 5n, 0n]], (repo) => lockDir(repo, 2147483000));
    expect(taken.results[0]).toMatchObject({ ok: true });
    const busy = same([["dirlock", ".agent/mailbox/locks/landing", 1n, 0n]], (repo) => lockDir(repo, process.pid));
    expect(busy.results[0]).toMatchObject({ ok: false, error: "HubError", code: 3 });
    expect(String((busy.results[0] as { message?: string }).message)).toContain("（持有者 {'pid': ");
  });

  it("B7 读状态：没有文件是空的主任务表；不是对象照 Python 崩溃；只有空白的文件算读不出", () => {
    same([["read_state"]]);
    same([["read_state"]], (repo) => {
      mkdirSync(join(repo, ".agent", "mailbox", "ledger"), { recursive: true });
      writeFileSync(join(repo, ".agent", "mailbox", "ledger", "state.json"), "[1, 2]");
    });
    // 只有空白的文件：照 Python 算“读不出”（strip 之后是空的、文件却不是空的），不当成没有主任务
    for (const text of [`  ${LF}`, String.fromCharCode(0x3000)]) {
      const { results } = same([["read_state"]], (repo) => {
        mkdirSync(join(repo, ".agent", "mailbox", "ledger"), { recursive: true });
        writeFileSync(join(repo, ".agent", "mailbox", "ledger", "state.json"), text);
      });
      expect(results[0]).toMatchObject({ ok: false, error: "HubError", code: 3 });
    }
  });

  it("B9 new 里的信照 Python 的路径次序排（小写比较），不照目录列出来的次序；扩展名大写的也算", () => {
    const box = `.agent/mailbox/inbox/${COORDINATOR}/new`;
    const { results } = same([
      ["ensure"], ["write_file", `${box}/a.md`, "x"], ["write_file", `${box}/B.MD`, "x"], ["write_file", `${box}/_x.md`, "x"], ["write_file", `${box}/c.txt`, "x"],
      ["unread", COORDINATOR],
    ]);
    // NTFS 按大写比较列目录（a、B、_x），Python 按小写比较排序（_x、a、B）
    expect(results[5]).toEqual({ ok: true, value: toTagged(["_x.md", "a.md", "B.MD"]) });
  });

  it("B10 存过之后，读出来时的样子跟着更新：别人后来改的键，再存时不拿自己先前存过的值盖回去，也不记冲突", () => {
    const { results } = same([
      ["ensure"], ["save_dict", dict(["tasks", dict(["T001", ts("T001")])])],
      ["load", "a"], ["set", "a", "T001", "notes", ["a 存的"]], ["save", "a"],
      ["load", "b"], ["set", "b", "T001", "notes", ["b 后改的"]], ["save", "b"],
      ["set", "a", "T001", "status", "done"], ["save", "a"], ["read_state"], ["ledger_events"],
    ]);
    expect(JSON.stringify(results[10])).toContain("b 后改的");
    expect(JSON.stringify(results[11])).not.toContain("state.conflict");
  });

  it("B11 到点的边界：until 恰好是当前这一秒也放回（照 Python 用 <=）", () => {
    const state = ts("T001");
    ((state.get("stages") as PyDict).get("3-gate-pre") as PyDict).set("status", "assigned");
    const id = "20260101T000000000001Z-womovie-c8-000001";
    const { results } = same([
      ["ensure"], ["save_dict", dict(["tasks", dict(["T001", state])])],
      ["deliver", head(id, COORDINATOR, "gate-sonnet", "T001-3-gate-pre", "开工"), fields()], ["take_first", "gate-sonnet"],
      ["hold_until_now", "T001", "gate-sonnet", [`${id}.md`], "3-gate-pre", "turn-1", "等一会儿"],
      ["release"], ["unread", "gate-sonnet"],
    ]);
    expect(results[6]).toEqual({ ok: true, value: toTagged(["<ID>.md"]) }); // 编号在比较前换成了占位符
  });
});

describe("第 ⑤b 片：混跑（两套实现同时写一个信箱）", () => {
  const pairs = [[IMPLS[0], IMPLS[2]], [IMPLS[2], IMPLS[0]], [IMPLS[1], IMPLS[0]]] as [Impl, Impl][];

  it.each(pairs.map(([a, b]) => [a.name, b.name, a, b] as const))("C1 %s 读完停住、%s 在中间存：不同键合并、同一键以后存的为准并记冲突", async (_a, _b, first, second) => {
    for (const sameKey of [false, true]) {
      const repo = scratchDir("hubmix");
      const go = join(repo, "go");
      try {
        runProbe(PYTHON, { op: "hub.box", repo, steps: steps([["ensure"], ["save_dict", dict(["tasks", dict(["T001", ts("T001")], ["T002", ts("T002", "x")])])]]) });
        const waiting = startProbe(first, { op: "hub.box", repo, steps: steps([["load", "s"], ["signal"], ["wait", go], ["set", "s", "T001", "notes", ["先读、后存"]], ["save", "s"]]) });
        try {
          await waiting.ready;
          const middle = runProbe(second, { op: "hub.box", repo, steps: steps([["load", "s"], ["set", "s", sameKey ? "T001" : "T002", "notes", ["中间存的"]], ["save", "s"]]) });
          expect(middle.ok).toBe(true);
          writeFileSync(go, "");
          expect((await waiting.result).ok).toBe(true);
        } finally {
          waiting.stop();
        }
        const state = JSON.parse(readFileSync(join(repo, ".agent", "mailbox", "ledger", "state.json"), "utf8")) as { tasks: Record<string, { notes: string[] }> };
        const ledgerPath = join(repo, ".agent", "mailbox", "ledger", "events.jsonl");
        const ledger = existsSync(ledgerPath) ? readFileSync(ledgerPath, "utf8") : "";
        expect(state.tasks["T001"]?.notes).toEqual(["先读、后存"]);
        expect(state.tasks["T002"]?.notes).toEqual(sameKey ? [] : ["中间存的"]);
        expect(ledger.includes('"key": "notes"')).toBe(sameKey);
      } finally {
        removeDir(repo);
      }
    }
  });

  // 第 37 轮：别的进程正开着 state.json，读与替换都短暂重试（40 次 × 50 毫秒）；过了期限读算“读不出”（不当成没有主任务），
  // 写报 PermissionError、不留临时文件。持有者是 Python 用 GENERIC_READ、dwShareMode=0 打开它（不许任何共享）。
  // libuv 打开文件总带 FILE_FLAG_BACKUP_SEMANTICS：令牌的备份特权启用时，Node 与 Bun 读得穿这种占用；停用时与 Python 一样撞上
  // 共享冲突（libuv 报 EBUSY）。Git Bash 起的进程树里是启用的，PowerShell 起的（supervisor 就是）是停用的，所以两种状态都跑：
  // 停用时三边逐字相同；启用时 TS 读到真实内容（已知差异，迁移计划第 10 节），写与短暂的占用照样相同
  const STATE_TEXT = `{"tasks": {"T001": {"status": "已有的主任务"}}}${LF}`;
  const SHARE_CASES: [number, string, Step[]][] = [
    [600, "读", [["read_state"]]],
    [600, "写", [["save_dict", dict(["tasks", dict(["T001", ts("T001")])])]]],
    [4000, "读", [["read_state"]]],
    [4000, "写", [["save_dict", dict(["tasks", dict(["T001", ts("T001")])])]]],
  ];
  type Shared = { outcome: unknown; leftovers: string[] };

  async function underShare(impl: Impl, holdMs: number, list: Step[]): Promise<Shared> {
    const repo = scratchDir("hubmix-share");
    try {
      const ledger = join(repo, ".agent", "mailbox", "ledger");
      mkdirSync(ledger, { recursive: true });
      const path = join(ledger, "state.json");
      writeFileSync(path, STATE_TEXT);
      // 被测进程先起来、停在起跑线上，持有者开好之后才放行：都是一开始就撞上占用，不受各自启动快慢的影响
      const go = join(repo, "go");
      const tested = startProbe(impl, { op: "hub.box", repo, steps: steps([["signal"], ["wait", go], ...list]) });
      let result: ProbeResult;
      try {
        // 启动器设不了特权（不是管理员）时直接交回结果、不报就绪
        const early = await Promise.race([tested.ready.then(() => null), tested.result]);
        expect(early, `${impl.name} 没有报就绪`).toBeNull();
        const holder = startProbe(PYTHON, { op: "fs.hold_exclusive", path, hold_ms: holdMs });
        try {
          await holder.ready;
          writeFileSync(go, "");
          result = await tested.result;
          expect((await holder.result).ok).toBe(true);
        } finally {
          holder.stop();
        }
      } finally {
        tested.stop();
      }
      expect(result.ok, JSON.stringify(result)).toBe(true);
      return { outcome: scrub((result["results"] as unknown[]).at(-1), repo), leftovers: readdirSync(ledger).filter((name) => name.endsWith(".tmp")) };
    } finally {
      removeDir(repo);
    }
  }

  it.each([false, true].flatMap((enabled) => SHARE_CASES.map(([holdMs, label, list]) => [enabled ? "启用" : "停用", holdMs, label, enabled, list] as const)))(
    "C4 备份特权%s、别的进程独占 state.json %i 毫秒时%s：短的等过去；长的读报“读不出”、写报 PermissionError，不留临时文件（test_state_writes_and_reads_wait_out_a_sharing_violation）",
    async (_state, holdMs, label, enabled, list) => {
      const runs: Shared[] = [];
      for (const impl of IMPLS) runs.push(await underShare(withBackupPrivilege(impl, enabled), holdMs, list));
      const [python, ...others] = runs as [Shared, ...Shared[]];
      expect(python.leftovers).toEqual([]);
      if (holdMs < 1000) expect(python.outcome).toMatchObject({ ok: true });
      else if (label === "读") {
        const message = `读不出 ${["<REPO>", ".agent", "mailbox", "ledger", "state.json"].join(SEP)}（文件在，内容读不到）`;
        expect(python.outcome).toEqual({ ok: false, error: "HubError", code: 3, message });
      } else expect(python.outcome).toEqual({ ok: false, error: "PermissionError" });
      for (const [index, other] of others.entries()) {
        const name = IMPLS[index + 1]?.name;
        if (enabled && holdMs > 1000 && label === "读") {
          // 已知差异：读得穿独占的打开，读到的是真实内容，不会把有内容的状态当成空的
          const value = toTagged(dict(["tasks", dict(["T001", dict(["status", "已有的主任务"])])]));
          expect(other, name).toEqual({ outcome: { ok: true, value }, leftovers: [] });
        } else {
          expect(other, `${name} 与 Python 不同`).toEqual(python);
        }
      }
    },
    120_000,
  );

  // 写状态与写工人的会话都在文件锁里读、改、写：Python 拿着锁时，各套实现的写都要等它放开。持有者放开之前先留一个记号，
  // 写完之后记号已经在，说明是等过的
  it.each([
    ["state.json", ".agent/mailbox/ledger/.state.lock", ["save_dict", dict(["tasks", dict(["T001", ts("T001")])])]],
    ["工人会话", ".agent/mailbox/agents/.agents.lock", ["save_agent_session", "gate-sonnet", "T001", dict(["id", "s"])]],
  ] as [string, string, Step][])("C5 Python 拿着%s的文件锁时，各套实现的写都等它放开", async (_label, lock, save) => {
    for (const impl of IMPLS) {
      const repo = scratchDir("hubmix-lock");
      const go = join(repo, "go");
      try {
        runProbe(PYTHON, { op: "hub.box", repo, steps: steps([["ensure"]]) });
        const tested = startProbe(impl, { op: "hub.box", repo, steps: steps([["signal"], ["wait", go], save, ["exists", "released"]]) });
        try {
          await tested.ready;
          const holder = startProbe(PYTHON, { op: "hub.box", repo, steps: steps([["hold_file_lock", lock, 800n, "released"]]) });
          try {
            await holder.ready;
            writeFileSync(go, "");
            const result = await tested.result;
            expect((result["results"] as unknown[]).slice(2), impl.name).toEqual([{ ok: true, value: toTagged(null) }, { ok: true, value: toTagged(true) }]);
            expect((await holder.result).ok).toBe(true);
          } finally {
            holder.stop();
          }
        } finally {
          tested.stop();
        }
      } finally {
        removeDir(repo);
      }
    }
  }, 60_000);

  it("C2 两套实现同时投递同一个编号：恰好一封发出去，另一边报编号冲突", async () => {
    for (let round = 0; round < 5; round += 1) {
      const repo = scratchDir("hubmix-deliver");
      const barrier = join(repo, "start");
      try {
        const id = "20260101T000000000009Z-owner-000009";
        const racers = [IMPLS[0], IMPLS[2]].map((impl, index) =>
          startProbe(impl as Impl, { op: "hub.box", repo, barrier, steps: steps([["deliver", head(id, OWNER, COORDINATOR, "T001", "任务"), fields({ 摘要: `第 ${index} 个` })]]) }));
        try {
          await Promise.all(racers.map((racer) => racer.ready));
          writeFileSync(barrier, "");
          const outcomes = await Promise.all(racers.map((racer) => racer.result));
          const oks = outcomes.map((outcome) => (outcome["results"] as { ok: boolean }[])[0]?.ok);
          expect(oks.filter(Boolean)).toHaveLength(1);
          const winner = oks.indexOf(true);
          expect(readFileSync(join(repo, ".agent", "mailbox", "inbox", COORDINATOR, "new", `${id}.md`), "utf8")).toContain(`第 ${winner} 个`);
        } finally {
          racers.forEach((racer) => racer.stop());
        }
      } finally {
        removeDir(repo);
      }
    }
  });

  it("C3 两套实现同时写同一个工人的会话：两条都在", async () => {
    for (let round = 0; round < 5; round += 1) {
      const repo = scratchDir("hubmix-agent");
      const barrier = join(repo, "start");
      try {
        const racers = [IMPLS[0], IMPLS[2]].map((impl, index) =>
          startProbe(impl as Impl, { op: "hub.box", repo, barrier, steps: steps([["save_agent_session", "gate-sonnet", `T00${index + 1}`, dict(["id", `s${index}`])]]) }));
        try {
          await Promise.all(racers.map((racer) => racer.ready));
          writeFileSync(barrier, "");
          await Promise.all(racers.map((racer) => racer.result));
        } finally {
          racers.forEach((racer) => racer.stop());
        }
        const record = JSON.parse(readFileSync(join(repo, ".agent", "mailbox", "agents", "gate-sonnet.json"), "utf8")) as { sessions: Record<string, unknown> };
        expect(Object.keys(record.sessions).sort()).toEqual(["T001", "T002"]);
      } finally {
        removeDir(repo);
      }
    }
  });
});

