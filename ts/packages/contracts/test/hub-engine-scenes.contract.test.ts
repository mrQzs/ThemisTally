// 第 ⑤i1 片的手写对照（采样那份在 hub-engine.contract.test.ts）：临时仓库上摆好信箱与 state.json，三边各自先原地放回再跑 Engine 的方法，
// 交回值、调用之后的参数、文件、账本、git 状态与剧本里每次调用的参数逐字比（⑤i 设计稿第 6 节）。照剧本交回的（request 的 scripted：
// 不核对参数，记下每次调用，参数不对照样比得出来）只有 Python 用例里也换掉的那几个，其余真跑：
//   - runner：Python 用例一律用 FakeRunner，真回合要起 claude 或 pi；
//   - ensure_worktree、worktree_root：Python 用例的 engine_env 也换掉了；这里看的不是工作目录，真 git 上的 ensure_worktree 由采样覆盖
//     （real-repo 用例里 stage_workspace 的几次，mkdtemp 照记录注入）；
//   - finalize、tidy_finished：要真的 attempt 与调度器的 verdict、integrate，它们自己由 ⑤h1 的契约覆盖；这里看的是结项通过之后的放行。
// 执行端等落地锁那一场的 run_exec 真跑（另一个进程真拿着 .land）。
//   - 当场重交：核验没过、同一会话里重交一次后通过；重交的回合撞上限流（不扣信、阶段 failed、信里带第一次核验）；
//   - 扣信：限流的工人回合扣信、阶段 paused；执行端等不到落地锁（另一个进程真拿着 .land，5360 的形状），扣信 120 秒、不建返工版本；
//   - 结项：通过之后放行依赖它的主任务（真 git 取末端）；
//   - 只测 TS：land 等落地锁用 landLockWaitSeconds，不用执行端的 landWaitSeconds（照 ⑤h2 的 Y02，用错时等满 30 秒）。
// 文件末尾一组是变异第二段补的（themistally-04 复核）：采样重放与上面几场都分不出来的变异，每条造一个让 Python 与变异体走出不同结果的输入，
// 结果靠三边对照；断言只确认场景确实走到了那一支（截断的场景里原文都比上限长）。最后一组是 themistally-04 在导出副本上抽查变异之后补的。
// 不写转义序列。
import { type ChildProcess, spawn } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { COORDINATOR, OWNER } from "@themis/hub/constants";
import { REAL_ENGINE_DEPS, land } from "@themis/hub/engine";
import { HubError } from "@themis/hub/errors";
import { renderLetter } from "@themis/hub/letters";
import { Hub, canonicalState } from "@themis/hub/mailbox";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { REPO } from "./harness.ts";
import { AT, LF, type Scene, agreeFlow, flow, kernelPython, py, returned, scene, text, tsAfter, written } from "./flow-fixtures.ts";
import { put, removeCreated, tempDir } from "./repo-fixtures.ts";
import {
  BASE_FILES, BOX, GATE, SECONDS, events, failure, fields, letter, lettersScene, lettersTo, lines, mailboxScene, planJob, planned, planned1, ran,
  runnerCalls, setStage, stageOf, stagesAfter, stateAfter, stateScene, taskState, turn, value,
} from "./engine-fixtures.ts";

afterAll(removeCreated);

describe("第 ⑤i1 片：当场重交（手写）", () => {
  it("核验没过，同一会话重交一次后通过：返工次数不加，信里注明，账本记 delivery.retried；重交的回合续接上一回合、带核验原话", () => {
    const passed = mailboxScene("planner-opus", "T001-1-plan", (head) => new Map([["T001", taskState(head, "1-plan")]]));
    const limited = mailboxScene("planner-opus", "T001-1-plan", (head) => new Map([["T001", taskState(head, "1-plan")]]));
    const roots = tempDir("engine-inputs");
    const states = agreeFlow([
      {
        ...flow("Engine.worker_job", passed.sc, [null, passed.state, "planner-opus", [passed.path]]),
        scripted: { runner: [turn("t1", planned(" ")), turn("t2", planned("# 概要步骤"))], ensure_worktree: [value(passed.sc.wt)], worktree_root: [value(roots), value(roots)] },
      },
      {
        ...flow("Engine.worker_job", limited.sc, [null, limited.state, "planner-opus", [limited.path]]),
        scripted: {
          runner: [turn("t1", planned(" ")), turn("t2", null, { api_error: "rate_limit", rate_limited_until: SECONDS + 600 })],
          ensure_worktree: [value(limited.sc.wt)], worktree_root: [value(roots), value(roots)],
        },
      },
    ]);
    expect(states.map((state) => returned(state))).toEqual([null, null]);
    const stage = stateAfter(states[0])["T001"]?.["stages"] as Record<string, Record<string, unknown>>;
    expect([stage["1-plan"]?.["status"], "reworks" in (stateAfter(states[0])["T001"] ?? {})], "通过了，返工次数也没加").toEqual(["delivered", false]);
    expect(lettersTo(states[0], COORDINATOR).join(LF)).toContain("验证: （第一次交付内核核验没过：规划端的 report 为空；同一会话里当场重交了一次）读了文档");
    expect(events(states[0]).filter((event) => event["event"] === "delivery.retried").map((event) => [event["first"], event["ok"]]))
      .toEqual([["规划端的 report 为空", true]]);
    const calls = runnerCalls(states[0]);
    expect([calls.length, calls[1]?.["retry_of"], String(calls[1]?.["prompt"]).includes("内核核验没过（交付已收到，同一会话里当场重交一次）")]).toEqual([2, "t1", true]);
    // 重交的回合撞上限流：不扣信，阶段标 failed，写给协调人的阻塞信里带第一次核验
    const failed = stateAfter(states[1])["T001"] as Record<string, unknown>;
    expect([(failed["stages"] as Record<string, Record<string, unknown>>)["1-plan"]?.["status"], failed["held"] ?? null]).toEqual(["failed", null]);
    expect(lettersTo(states[1], COORDINATOR).join(LF)).toContain("（这是核验没过之后的当场重交；第一次核验：规划端的 report 为空）");
  }, 600_000);
});

describe("第 ⑤i1 片：扣信（手写）", () => {
  it("限流的工人回合：扣信、阶段 paused、写信告诉站主几点接着做；不当场重交", () => {
    const sc = mailboxScene("planner-opus", "T001-1-plan", (head) => new Map([["T001", taskState(head, "1-plan")]]));
    const roots = tempDir("engine-inputs");
    const [state] = agreeFlow([{
      ...flow("Engine.worker_job", sc.sc, [null, sc.state, "planner-opus", [sc.path]]),
      scripted: {
        runner: [turn("t1", null, { api_error: "rate_limit", rate_limited_until: SECONDS + 600 })], ensure_worktree: [value(sc.sc.wt)], worktree_root: [value(roots)],
      },
    }]);
    const ts = stateAfter(state)["T001"] as Record<string, unknown>;
    expect([(ts["stages"] as Record<string, Record<string, unknown>>)["1-plan"]?.["status"], (ts["held"] as unknown[]).length]).toEqual(["paused", 1]);
    expect(lettersTo(state, OWNER).join(LF)).toContain("planner-opus 撞上模型接口的额度限制：2026-11-01T00:10:00Z 之后内核自动接着做，不用回信");
    expect(runnerCalls(state).length).toBe(1);
  }, 600_000);

  it("执行端等不到落地锁（另一个进程真拿着 .land，5360 的形状）：扣信 120 秒、阶段 paused、只记账本不写信，拿到锁之前不建返工版本", () => {
    const LAND = `${BOX}/.land`;
    const holderScript = [
      "import sys, time", "sys.path.insert(0, sys.argv[1])", "import kit_hub", "from pathlib import Path",
      "kit_hub.DirLock(Path(sys.argv[2])).__enter__()", "print('held', flush=True)", "time.sleep(600)",
    ].join(LF);
    const held: { child: ChildProcess | null } = { child: null };
    try {
      const sc = mailboxScene("exec-step", "T001-5-exec", (head) => new Map([["T001", taskState(head, "5-exec", {
        contract: { version: 1, key: "t001-doc.v1", md: ".agent/plans/t001-doc.v1.md", json: ".agent/plans/t001-doc.v1.json", written_version: 1 },
        oracle: { sha: head, files: [GATE] },
      })]]), (repo) => {
        held.child = spawn(kernelPython(), ["-c", holderScript, join(REPO, "scripts"), join(repo, ...LAND.split("/"))], { stdio: "ignore" });
        for (let waited = 0; !existsSync(join(repo, ...LAND.split("/"), "owner.json")) && waited < 200; waited += 1) sleepSync(100);
      });
      const [state] = agreeFlow([{ ...flow("Engine.worker_job", sc.sc, [null, sc.state, "exec-step", [sc.path]]), constants: { EXEC_LAND_WAIT_SECONDS: 0.6 } }]);
      const ts = stateAfter(state)["T001"] as Record<string, unknown>;
      const hold = (ts["held"] as Record<string, unknown>[])[0];
      expect([(ts["stages"] as Record<string, Record<string, unknown>>)["5-exec"]?.["status"], hold?.["until"], hold?.["suffix"]])
        .toEqual(["paused", "2026-11-01T00:02:00Z", "5-exec"]);
      expect(events(state).filter((event) => event["event"] === "letters.held").map((event) => String(event["reason"]).startsWith("落地锁被占（锁被占用：")))
        .toEqual([true]);
      expect(lettersTo(state, OWNER), "带 reason 的扣信不写信").toEqual([]);
      expect(Object.keys(written(state)).filter((key) => key.includes(".agent/plans/")), "拿到锁之前不建返工版本").toEqual([]);
    } finally {
      held.child?.kill();
    }
  }, 600_000);
});

describe("第 ⑤i1 片：不唤醒工人的信（手写）", () => {
  it("主任务没登记、这批信里有一封缺 type：类型排不了序，照 Python 抛 TypeError（信已读进 cur）；报错文字里两个类型名的先后不固定，只比类型", () => {
    const box: { paths: string[]; state: PyValue } = { paths: [], state: null };
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      const state = new Map<string, PyValue>([["tasks", new Map([["T001", taskState(head, "1-plan")]])]]);
      put(repo, `${BOX}/ledger/state.json`, canonicalState(state));
      const typed = letter(repo, "planner-opus", "20261101T000000000000Z-coordinator-000000", COORDINATOR, "T009-1-plan", "开工");
      const untyped = letter(repo, "planner-opus", "20261101T000000000000Z-coordinator-000001", COORDINATOR, "T009-1-plan", "开工");
      const rel = `${BOX}/inbox/planner-opus/new/20261101T000000000000Z-coordinator-000001.md`;
      const original = renderLetter(new Map([["msg-id", "20261101T000000000000Z-coordinator-000001"], ["from", COORDINATOR], ["to", "planner-opus"],
        ["task-id", "T009-1-plan"], ["in-reply-to", "none"], ["type", "开工"]]), fields());
      expect(original.split(LF).filter((line) => line === "type: 开工").length).toBe(1);
      put(repo, rel, original.split(LF).filter((line) => line !== "type: 开工").join(LF)); // 整行删掉：空值是 ""，不是 None
      box.paths = [typed, untyped];
      box.state = state;
    });
    const sameMessage = (state: Record<string, unknown>): unknown => {
      const result = state["result"] as Record<string, unknown>;
      return { ...state, result: { ...result, message: String(result["message"]).startsWith("'<' not supported between instances of '") ? "<两个类型名>" : result["message"] } };
    };
    const [state] = agreeFlow([flow("Engine.worker_job", sc, [null, box.state, "planner-opus", box.paths])], sameMessage);
    expect([(state?.["result"] as Record<string, unknown>)["error"], (state?.["files"] as { delete: string[] }).delete.length]).toEqual(["TypeError", 2]);
  }, 600_000);
});

describe("第 ⑤i1 片：结项放行依赖（手写）", () => {
  it("handle_pass 结项通过：放行依赖它的主任务，基线挪到当前末端，写信叫协调人开工合同端；写给站主的核验信", () => {
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      const t001 = newTaskState("T001", "doc", "改文档", head, true, AT);
      t001.set("exec", py({ run_dir: ".agent/runs/t001-doc/attempt-001" }));
      const t002 = newTaskState("T002", "next", "下一片", "f".repeat(40), true, AT);
      t002.set("after", ["T001"]);
      put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map([["tasks", new Map([["T001", t001], ["T002", t002]])]])));
    });
    const loaded = new Hub(sc.repo).loadState().data;
    const meta = { "msg-id": "m", from: COORDINATOR, to: "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none", type: "通过" };
    const [result] = agreeFlow([{
      ...flow("Engine.handle_pass", sc, [null, loaded, meta]),
      scripted: { finalize: [value([true, lines("verdict PASS", "integrate ok")])], tidy_finished: [value([])] },
    }]);
    const tasks = stateAfter(result);
    expect([tasks["T001"]?.["status"], tasks["T002"]?.["base_head"] === sc.head, (tasks["T002"]?.["after_released"] as Record<string, unknown>)["head"]])
      .toEqual(["done", true, sc.head]);
    expect(lettersTo(result, COORDINATOR).join(LF)).toContain("依赖 T001 都已结项：基线从 ffffffffff 挪到");
    expect(lettersTo(result, OWNER).join(LF)).toContain("摘要: T001 结项：verdict PASS，已 integrate");
    expect(events(result).filter((event) => event["event"] === "dependency.released").map((event) => event["task"])).toEqual(["T002"]);
  }, 600_000);
});

describe("第 ⑤i1 片：land 等落地锁的时限（只测 TS）", () => {
  it("另一个进程拿着 .land：land 照 landLockWaitSeconds（0.3 秒）报“锁被占用：”，不等执行端的 landWaitSeconds（30 秒）", async () => {
    const flag = tempDir("engine-land");
    const repo = tempDir("engine-land-repo");
    new Hub(repo).ensure();
    const script = join(flag, "hold.py");
    writeFileSync(script, lines(
      "import sys", "import time", "from pathlib import Path", `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`, "import kit_hub as kh",
      `with kh.DirLock(Path(${JSON.stringify(join(repo, ".agent", "mailbox", ".land"))}), wait_seconds=5):`,
      `    Path(${JSON.stringify(join(flag, "ready"))}).write_text("ok")`,
      `    while not Path(${JSON.stringify(join(flag, "go"))}).exists():`, "        time.sleep(0.05)",
    ));
    const child = spawn(kernelPython(), [script], { stdio: "ignore", env: { ...process.env, PYTHONUTF8: "1" } });
    const exited = new Promise((resolve) => child.on("exit", resolve));
    try {
      for (let waited = 0; !existsSync(join(flag, "ready")) && waited < 600; waited += 1) sleepSync(50);
      const landing = { handlePass: async () => undefined, afterLand: async () => undefined };
      const started = Date.now();
      const meta = new Map([["task-id", "T001-5-exec"]]);
      const failure = await land(new Hub(repo), landing, join(repo, "letter.md"), meta, { ...REAL_ENGINE_DEPS, landLockWaitSeconds: 0.3, landWaitSeconds: 30 })
        .then(() => null, (error: unknown) => error);
      expect([failure instanceof HubError, String((failure as Error | null)?.message).startsWith("锁被占用：")]).toEqual([true, true]);
      expect(Date.now() - started, "等的是 landLockWaitSeconds").toBeLessThan(10_000);
    } finally {
      writeFileSync(join(flag, "go"), "go");
      await exited;
    }
  }, 120_000);
});

// --- 变异第二段补的场景 -----------------------------------------------------------------------------------------------------------------

describe("第 ⑤i1 片：变异第二段补的场景（手写）", () => {
  it("escalate：note 截 2000 字，摘要取首行前 200 字（E01、E03）", () => {
    const sc = stateScene(planned1);
    const ts = taskState(sc.head, "1-plan");
    const said = ["甲".repeat(250), "乙".repeat(1900)].join(LF);
    const [state] = agreeFlow([flow("Engine.escalate", sc, [null, ts, said])]);
    const notes = tsAfter(state).get("notes") as PyDict[];
    expect([said.length, String(notes[0]?.get("text")).length]).toEqual([2151, 2000]);
    expect(lettersTo(state, OWNER).join(LF)).toContain(`摘要: ${"甲".repeat(200)}${LF}`);
  }, 600_000);

  it("worker_job 的几封信：开工加告知类照样唤醒、拿掉 stranded_notice（W01、W04）；全是告知类不唤醒，类型照码点排（K02）", () => {
    const roots = tempDir("engine-inputs");
    const woken = lettersScene("planner-opus", "T001-1-plan", ["开工", "等待"], (head) => {
      const ts = taskState(head, "1-plan");
      stageOf(ts, "1-plan").set("stranded_notice", ["20261031T000000000000Z-coordinator-000009.md"]);
      return ts;
    });
    const quiet = lettersScene("planner-opus", "T001-1-plan", ["通过", "等待"], planned1); // 插入次序与码点次序相反
    const states = agreeFlow([planJob(woken, [turn("t1", planned("# 概要步骤"))], roots), flow("Engine.worker_job", quiet.sc, [null, quiet.state, "planner-opus", quiet.paths])]);
    const stage = stagesAfter(states[0])["1-plan"] ?? {};
    expect([stage["status"], "stranded_notice" in stage, runnerCalls(states[0]).length]).toEqual(["delivered", false, 1]);
    expect(events(states[1]).filter((event) => event["event"] === "worker.not_woken").map((event) => event["kinds"])).toEqual([["等待", "通过"]]);
  }, 600_000);

  it("执行端交付：没有 check_ok 当没过，落地预演没过截 600 字；没过的 note 截 300 字、下游作废、内核核验写明短路（W09、W11、F02–F04）", () => {
    const sc = lettersScene("exec-step", "T001-5-exec", ["开工"], (head) => {
      const ts = taskState(head, "5-exec");
      setStage(ts, "6-gate-post", py({ status: "delivered", delivered_at: AT }));
      return ts;
    });
    const [state] = agreeFlow([{
      ...flow("Engine.worker_job", sc.sc, [null, sc.state, "exec-step", sc.paths]),
      scripted: { run_exec: [value(ran("庚".repeat(400)))], rehearse_landing: [value([false, "辛".repeat(700)])] },
    }]);
    const stages = stagesAfter(state);
    expect([stages["5-exec"]?.["status"], String(stages["5-exec"]?.["note"]).length, stages["6-gate-post"]]).toEqual(["failed", 300, { status: "idle" }]);
    const sent = lettersTo(state, COORDINATOR).join(LF);
    expect(sent).toContain(`落地预演: 没过，已写信给站主，站主处理之前别结项：${"辛".repeat(600)}${LF}`);
    expect(sent).toContain(`内核核验: 未通过（短路：只能返工给执行端）${LF}`);
  }, 600_000);

  it("当场重交：第一次核验截 300 字、验证的前缀截 200 字、通过后下游作废（W24、W26、W33）；两次都没过时 note 截 600 字、内核核验截 1200 字（W29、W31）", () => {
    const roots = tempDir("engine-inputs");
    const once = lettersScene("planner-opus", "T001-1-plan", ["开工"], (head) => {
      const ts = taskState(head, "1-plan");
      setStage(ts, "2-contract", py({ status: "delivered", delivered_at: AT }));
      return ts;
    });
    const twice = lettersScene("planner-opus", "T001-1-plan", ["开工"], planned1);
    const first = ["壬".repeat(350)];
    const both = ["癸".repeat(700), "子".repeat(700)];
    const job = (sc: ReturnType<typeof lettersScene>, verdicts: unknown[][]) => {
      const made = planJob(sc, [turn("t1", planned("# 第一版")), turn("t2", planned("# 第二版"))], roots, 2);
      return { ...made, scripted: { ...made.scripted, "Engine.verify_delivery": verdicts.map((item) => value(item)) } };
    };
    const states = agreeFlow([job(once, [first, []]), job(twice, [both, both])]);
    expect([stagesAfter(states[0])["1-plan"]?.["status"], stagesAfter(states[0])["2-contract"]]).toEqual(["delivered", { status: "idle" }]);
    expect(events(states[0]).filter((event) => event["event"] === "delivery.retried").map((event) => String(event["first"]).length)).toEqual([300]);
    expect(lettersTo(states[0], COORDINATOR).join(LF)).toContain(`验证: （第一次交付内核核验没过：${"壬".repeat(200)}；同一会话里当场重交了一次）读了文档`);
    const failed = stagesAfter(states[1])["1-plan"] ?? {};
    expect([failed["status"], String(failed["note"]).length, failed["redelivered"]]).toEqual(["failed", 600, true]);
    expect(lettersTo(states[1], COORDINATOR).join(LF)).toContain(`内核核验: 未通过（同一会话里已经当场重交过一次）：${both.join("；").slice(0, 1200)}${LF}`);
  }, 600_000);

  it("回合的几种形状：违规用分号连、偏离截 1500 字（V01、V11）；重交的回合限流（V03）；没有输出（O01）；信缺两栏又超长（O02、O03）", () => {
    const roots = tempDir("engine-inputs");
    const plan = () => lettersScene("planner-opus", "T001-1-plan", ["开工"], planned1);
    const reasons = ["丑".repeat(800), "寅".repeat(800)];
    const verified = Array.from({ length: 45 }, (_, index) => `第 ${index + 1} 行`).join(LF);
    const bad = {
      letter: { type: "交付", in_reply_to: "m", 摘要: "拆成 3 步", 验证: verified, 需协调人决定: "无", 证据: "report.md" }, report: "# 概要", state: "交付", external_facts: [],
    };
    const states = agreeFlow([
      planJob(plan(), [turn("t1", planned("# 概要"), { violations: reasons })], roots),
      planJob(plan(), [turn("t1", planned(" ")), turn("t2", planned("# 概要"), { rate_limited_until: SECONDS + 600 })], roots, 2),
      planJob(plan(), [turn("t1", null, { output_error: null }), turn("t2", null, { output_error: null })], roots),
      planJob(plan(), [turn("t1", bad), turn("t2", bad)], roots),
    ]);
    expect(stagesAfter(states[0])["1-plan"]?.["note"]).toBe(`回合作废：${reasons.join("；")}`);
    expect(lettersTo(states[0], COORDINATOR).join(LF)).toContain(`偏离: ${reasons.join("；").slice(0, 1500)}${LF}`);
    expect(lettersTo(states[1], COORDINATOR).join(LF)).toContain(`偏离: 接口限流（到 ${SECONDS + 600}）（这是核验没过之后的当场重交；第一次核验：规划端的 report 为空）`);
    expect([lettersTo(states[2], COORDINATOR).join(LF).includes(`偏离: 没有输出${LF}`), runnerCalls(states[2]).length]).toEqual([true, 2]);
    expect(lettersTo(states[3], COORDINATOR).join(LF))
      .toContain("偏离: 正文缺“提交”（没有就写“无”）；正文缺“偏离”（没有就写“无”）；正文 50 行，超过 40 行：细节放进 report.md");
  }, 600_000);

  it("续接哪个会话：result.json 带 output_error、带 violations、不是 JSON 都开新会话（Q02、Q03、Q04）；第一条是对照（工作目录对得上、会话续上）", () => {
    const roots = tempDir("engine-inputs");
    const resumed = (record: (wt: string) => string) => lettersScene("planner-opus", "T001-1-plan", ["开工"], (head) => {
      const ts = taskState(head, "1-plan");
      stageOf(ts, "1-plan").set("resume", py({ turn: "t0" }));
      return ts;
    }, (repo, wt) => put(repo, `${BOX}/turns/planner-opus/t0/result.json`, record(wt)));
    const cases = [
      resumed((wt) => JSON.stringify({ workspace: wt, session_id: "s-1" })),
      resumed((wt) => JSON.stringify({ workspace: wt, session_id: "s-1", output_error: "没有代码块" })),
      resumed((wt) => JSON.stringify({ workspace: wt, session_id: "s-1", violations: ["改了工作目录外的文件"] })),
      resumed(() => "{不是 JSON"),
    ];
    const states = agreeFlow(cases.map((sc) => planJob(sc, [turn("t1", planned("# 概要"))], roots)));
    expect(states.map((state) => [runnerCalls(state)[0]?.["session_id"], runnerCalls(state)[0]?.["fresh"]]))
      .toEqual([["s-1", false], [null, true], [null, true], [null, true]]);
  }, 600_000);

  it("stage_workspace 与 verify_delivery 只在用到的分支里读：没有 base_head 的战后门禁（G08）；战后门禁的 worktree 键（D05）；结论缺失（D06）；不是通过时不读 gate_post（D09）", () => {
    const sc = stateScene(planned1);
    const made = (suffix: string, edit: (ts: PyDict) => void): PyDict => {
      const ts = taskState(sc.head, suffix);
      edit(ts);
      return ts;
    };
    const post = made("6-gate-post", (ts) => {
      ts.set("exec", py({ run_dir: join(sc.repo, ".agent", "runs", "t001-doc", "attempt-001") }));
      ts.set("workspaces", py({ "post-attempt-001": { path: sc.wt, baseline_status: [] } }));
    });
    const states = agreeFlow([
      {
        ...flow("Engine.stage_workspace", sc, [null, made("6-gate-post", (ts) => ts.delete("base_head")), "gate-sonnet", "6-gate-post"]),
        scripted: { apply_candidate: [value(sc.wt)], seed_whitebox: [value(null)] },
      },
      flow("Engine.verify_delivery", sc, [null, post, "gate-sonnet", "6-gate-post", {}, {}]),
      flow("Engine.verify_delivery", sc, [null, made("7-audit-post", () => undefined), "audit-sonnet", "7-audit-post", {}, { 结论: "存疑" }]),
      flow("Engine.verify_delivery", sc, [null, made("7-audit-post", (ts) => ts.delete("gate_post")), "audit-sonnet", "7-audit-post", {}, { 结论: "返工" }]),
    ]);
    expect(states.map((state) => returned(state))).toEqual([sc.wt, ["没有新增 tests/test_gate_t001_whitebox.py"], ["审核结论缺失"], []]);
  }, 600_000);

  it("after_delivery：事实去两端空白、一条没核实也写信、出处没写写“未写”（A01、A03、A04）；事实清单截 1500 字（A05）；一审返工加 fails（A10）", () => {
    const sc = stateScene(planned1);
    const plan = (): PyDict => taskState(sc.head, "1-plan");
    const trimmed = { external_facts: [{ fact: "  上游 1.3.0 的许可证是 MIT  ", source: "", verified: "未核实" }] };
    const lengthy = { external_facts: [{ fact: "卯".repeat(1600), source: "npm", verified: "没核实" }] };
    const states = agreeFlow([
      flow("Engine.after_delivery", sc, [null, plan(), "1-plan", {}, trimmed]),
      flow("Engine.after_delivery", sc, [null, plan(), "1-plan", {}, lengthy]),
      flow("Engine.after_delivery", sc, [null, taskState(sc.head, "4-audit-pre"), "4-audit-pre", { 结论: "返工", 退回: "合同端" }, {}]),
    ]);
    const items = (tsAfter(states[0]).get("external_facts") as PyDict).get("items") as PyDict[];
    expect(items[0]?.get("fact")).toBe("上游 1.3.0 的许可证是 MIT");
    expect(lettersTo(states[0], OWNER).join(LF)).toContain(`偏离: - 上游 1.3.0 的许可证是 MIT（出处：未写）${LF}`);
    expect(lettersTo(states[1], OWNER).join(LF)).toContain(`偏离: - ${"卯".repeat(1498)}${LF}`);
    expect((tsAfter(states[2]).get("audit_pre") as PyDict).get("fails")).toBe(1n);
  }, 600_000);

  it("finish_kernel_stage：通过与没过都让下游作废、没过的写法（F01–F04）；阶段是列表、是 None 时照 Python 报 TypeError（Y01、Y03）；worker_job 的阶段是列表（Y04）", () => {
    const sc = stateScene(planned1);
    const kernel = (edit: (ts: PyDict) => void, fields: Record<string, string>, ok: boolean) => {
      const ts = taskState(sc.head, "5-exec");
      setStage(ts, "6-gate-post", py({ status: "delivered", delivered_at: AT }));
      edit(ts);
      const state = new Map<string, PyValue>([["tasks", new Map([["T001", ts]])]]);
      return { ...flow("Engine.finish_kernel_stage", sc, [null, state, ts, "exec-step", "5-exec", fields, ok]), ts_alias: "T001" };
    };
    const listed = lettersScene("planner-opus", "T001-1-plan", ["开工"], (head) => {
      const ts = taskState(head, "1-plan");
      setStage(ts, "1-plan", []);
      return ts;
    });
    const states = agreeFlow([
      kernel(() => undefined, ran("通过"), true),
      kernel(() => undefined, ran("辰".repeat(400)), false),
      kernel((ts) => setStage(ts, "5-exec", []), ran("通过"), true),
      kernel((ts) => setStage(ts, "5-exec", null), ran("通过"), true),
      flow("Engine.worker_job", listed.sc, [null, listed.state, "planner-opus", listed.paths]),
    ]);
    expect([stagesAfter(states[0])["5-exec"]?.["status"], stagesAfter(states[0])["6-gate-post"]]).toEqual(["delivered", { status: "idle" }]);
    const failed = stagesAfter(states[1]);
    expect([failed["5-exec"]?.["status"], String(failed["5-exec"]?.["note"]).length, failed["6-gate-post"]]).toEqual(["failed", 300, { status: "idle" }]);
    expect(lettersTo(states[1], COORDINATOR).join(LF)).toContain(`内核核验: 未通过（短路：只能返工给执行端）${LF}`);
    expect(states.slice(2).map(failure)).toEqual([
      ["TypeError", "list indices must be integers or slices, not str"], ["TypeError", "'NoneType' object does not support item assignment"],
      ["TypeError", "pop expected at most 1 argument, got 2"],
    ]);
  }, 600_000);

  it("recheck_exec：阶段 failed、attempt 目录不在时报错，不重新核验（R05）", () => {
    const sc = stateScene((head, repo) => {
      const ts = taskState(head, "5-exec");
      stageOf(ts, "5-exec").set("status", "failed");
      ts.set("exec", py({ run_dir: join(repo, ".agent", "runs", "t001-doc", "attempt-009"), run_exit: 1 }));
      return ts;
    });
    const [state] = agreeFlow([flow("Engine.recheck_exec", sc, [null, "T001"])]);
    const [error, message] = failure(state);
    expect([error, String(message).startsWith("只有执行阶段判为失败、attempt 目录还在时")]).toEqual(["HubError", true]);
  }, 600_000);

  it("handle_pass：提交一栏取末行前 200 字、收尾没做完截 1500 字（H04、H06）；结项失败的偏离写原因（H07）", () => {
    const meta = { "msg-id": "m", from: COORDINATOR, to: "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none", type: "通过" };
    const pass = (finalized: unknown, tidied: unknown[]) => {
      const sc = stateScene((head) => {
        const ts = taskState(head, "5-exec");
        ts.set("exec", py({ run_dir: ".agent/runs/t001-doc/attempt-001" }));
        return ts;
      });
      return { ...flow("Engine.handle_pass", sc, [null, new Hub(sc.repo).loadState().data, meta]), scripted: { finalize: [value(finalized)], tidy_finished: tidied } };
    };
    const leftover = ["午".repeat(800), "未".repeat(800)];
    const why = lines("integrate 失败", "申".repeat(1600));
    const states = agreeFlow([pass([true, lines("verdict PASS", "巳".repeat(300))], [value(leftover)]), pass([false, why], [])]);
    const done = lettersTo(states[0], OWNER).join(LF);
    expect(done).toContain(`提交: ${"巳".repeat(200)}${LF}`);
    expect(done).toContain(`偏离: ${`结项收尾没做完：${leftover.join("；")}`.slice(0, 1500)}${LF}`);
    const kept = 1500 - "integrate 失败".length - 1;
    expect(lettersTo(states[1], OWNER).join(LF)).toContain(`偏离: integrate 失败${LF}  ${"申".repeat(kept)}${LF}`);
  }, 600_000);

  it("after_land：回归期间 exec-active 下挂着 <主任务>-after-land.json（L01）；回归没过的验证截 1500 字（L03）", () => {
    const pending = (): Scene => stateScene((head) => {
      const ts = taskState(head, "5-exec");
      ts.set("regression", py({ pending: true }));
      return ts;
    });
    const states = agreeFlow([
      { ...flow("Engine.after_land", pending(), [null, "T001"]), scripted: { regression_sweep: [{ ...value([true, "门禁基准都过了"]) as object, listing: `0/${BOX}/ledger/exec-active` }] } },
      { ...flow("Engine.after_land_run", pending(), [null, "T001"]), scripted: { regression_sweep: [value([false, "酉".repeat(1600)])] } },
    ]);
    expect((states[0]?.["scripted_calls"] as Record<string, unknown>[]).map((call) => call["listing"])).toEqual([["T001-after-land.json"]]);
    expect(lettersTo(states[1], OWNER).join(LF)).toContain(`验证: ${"酉".repeat(1500)}${LF}`);
  }, 600_000);

  it("land：后台回归的窗口标记挡着落地，信留在 new（N05）", () => {
    const box = { path: "" };
    const sc = scene(BASE_FILES, (repo, _wt, head) => {
      put(repo, `${BOX}/ledger/state.json`, canonicalState(new Map([["tasks", new Map([["T001", taskState(head, "5-exec")]])]])));
      const mark = { task: "T009-after-land", label: "T009 合入后的门禁回归与落地预演", sweep: true };
      put(repo, `${BOX}/ledger/exec-active/T009-after-land.json`, `${JSON.stringify(mark)}${LF}`);
      box.path = letter(repo, "exec-step", "20261101T000000000000Z-coordinator-000000", COORDINATOR, "T001-5-exec", "通过");
    });
    const meta = { "msg-id": "20261101T000000000000Z-coordinator-000000", from: COORDINATOR, to: "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none", type: "通过" };
    const [state] = agreeFlow([flow("land", sc, [null, box.path, meta])]);
    expect(returned(state)).toEqual(["T009 合入后的门禁回归与落地预演"]);
  }, 600_000);
});

describe("第 ⑤i1 片：themistally-04 抽查之后补的场景（手写）", () => {
  it("verify_delivery 的规划：report 为空与缺 external_facts 同时出现，先报 report（Z05）", () => {
    const sc = stateScene(planned1);
    const [state] = agreeFlow([flow("Engine.verify_delivery", sc, [null, taskState(sc.head, "1-plan"), "planner-opus", "1-plan", { report: "  " }, {}])]);
    const problems = returned(state) as string[];
    expect([problems.length, problems[0], problems[1]?.startsWith("输出里没有 external_facts")]).toEqual([2, "规划端的 report 为空", true]);
  }, 600_000);
});
