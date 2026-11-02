// 第 ⑤d2 片的契约（迁移计划第 ⑤ 步）：输入目录与 TurnRunner。kit_hub.py 的 stage_inputs、remove_inputs、TurnRunner.run 交给
// Python、Node、Bun，逐字比（崩溃比类型，HubError 比文字与退出码）。TurnRunner 配回放的 launcher（把给定的字节原样写进标准输出与
// 标准错误，交回给定的退出码、是否超时与用时），不确定的几样两边注入同一组值；只有“到秒、带 Z”的 ISO 时间换成占位（设计稿 8.5）。
// 两边先后在同一个目录里重放：每一边之前照场景重新搭一遍，路径不用占位，产物整份逐字节比。环境只比名字，内核自己定下的几个比值。
import { chmodSync, existsSync, mkdirSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { COORDINATOR, ROSTER } from "@themis/hub/constants";
import { afterAll, describe, expect, it } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON as PYTHON_IMPL, type ProbeRequest, type ProbeResult, REPLAY_TIMEOUT, removeDir, runBatch, scratchDir } from "./harness.ts";

const C = (...codes: number[]): string => String.fromCodePoint(...codes);
const BS = C(92);
const LF = C(10);
const FACE = C(0x1f600);
const ROOT = scratchDir("turn");
const LONG = realpathSync.native(ROOT);
afterAll(() => removeDir(ROOT));

const SOURCES = { compact: "20261031T120000123456Z", random2: "beef", uuid4: "12345678-1234-4abc-9def-123456789abc", seconds: 1_800_000_000 };
const ISO = new RegExp(`${BS}d{4}-${BS}d{2}-${BS}d{2}T${BS}d{2}:${BS}d{2}:${BS}d{2}Z`, "gu");
const line = (value: unknown): string => JSON.stringify(value);
const b64 = (text: string): string => Buffer.from(text, "utf8").toString("base64");
const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";

/** 假 pi：--help 列出 TurnRunner 给 pi 的参数；第一个参数是 fail 时以 1 退出，是 missing 时少列一个 --session-dir。 */
function fakePi(): string {
  const path = join(LONG, "fake_pi.py");
  const flags = ["--provider", "--model", "--thinking", "--mode", "--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-mcp",
    "--extension", "--no-context-files", "--tools", "--append-system-prompt", "--session-dir", "--session-id"];
  writeFileSync(path, [
    "import sys",
    "mode = sys.argv[1]",
    "if mode == 'fail':",
    "    sys.exit(1)",
    `flags = ${JSON.stringify(flags)}`,
    "if mode == 'missing':",
    "    flags.remove('--session-dir')",
    "print('Usage: pi [options]')",
    "for flag in flags:",
    "    print('  ' + flag + ' <x>   y')",
    "",
  ].join(LF));
  return path;
}
const FAKE_PI = fakePi();
const piCmd = (mode: string): Record<string, string> => ({ PI_DISPATCH_PI_CMD: JSON.stringify([PYTHON, FAKE_PI, mode]) });

/** 名册里这个工人的模型说完了话（pi 的 message_end）：审计照它认模型。 */
const piDone = (agent: string): unknown => ({ type: "message_end", message: { role: "assistant", provider: ROSTER[agent]?.provider, model: ROSTER[agent]?.model, stopReason: "toolUse", content: [] } });
/** deliver 的调用：每次是（参数，是否被拒）；不被拒的那次 details 就是参数（pi 1.4.0 的形状）。 */
function delivers(...attempts: [unknown, boolean][]): unknown[] {
  return attempts.flatMap(([args, refused], index) => [
    { type: "tool_execution_start", toolCallId: `d${index}`, toolName: "deliver", args },
    { type: "tool_execution_end", toolCallId: `d${index}`, toolName: "deliver", isError: refused, result: { content: [{ type: "text", text: "x" }], details: refused ? {} : args } },
  ]);
}
const stream = (...events: unknown[]): string => `${events.map(line).join(LF)}${LF}`;

const LETTER = { type: "交付", in_reply_to: "m1", 摘要: "规划", 提交: "无", 验证: "无", 偏离: "无", 需协调人决定: "无", 下游须知: "无", 证据: "无" };

interface Setup {
  readonly agent: string;
  readonly key?: string;
  readonly prompt?: string;
  readonly fresh?: boolean;
  readonly sessionId?: string;
  readonly inputs?: boolean;
  readonly mode?: string;
  readonly script?: Record<string, unknown>;
  /** 名册里换掉的岗位、交差文件换掉的哈希：调用期间两边设同一个值（对应用例里的 monkeypatch.setitem）。 */
  readonly roster?: Record<string, unknown>;
  readonly shas?: Record<string, string>;
  /** 在信箱里先放好的东西（会话记录、会话文件、claude 的会话文件……）：(hub 仓库, 工作目录, 临时 home)。 */
  readonly prepare?: (repo: string, workspace: string, home: string) => void;
}

/** 回放脚本照 Python 的值：退出码是 int，用时是 float。 */
function pyScript(script: Record<string, unknown>): PyDict {
  return new Map(Object.entries(script).map(([key, value]): [string, PyValue] => [key, key === "exit_code" && typeof value === "number" ? BigInt(value) : (value as PyValue)]));
}

/** 一个场景的目录：照 Setup 重新搭一遍（每一边重放之前都搭）；交回请求。 */
function build(name: string, setup: Setup): ProbeRequest {
  const dir = join(LONG, "cases", name);
  rmSync(dir, { recursive: true, force: true });
  const repo = join(dir, "repo");
  const workspace = join(dir, "ws");
  const home = join(dir, "home");
  for (const sub of ["agents", "ledger", "sessions", "turns", "tasks"]) mkdirSync(join(repo, ".agent", "mailbox", sub), { recursive: true });
  mkdirSync(workspace, { recursive: true });
  mkdirSync(home, { recursive: true });
  let inputs: string | null = null;
  if (setup.inputs) {
    inputs = join(dir, "inputs", "T001-x");
    mkdirSync(inputs, { recursive: true });
    writeFileSync(join(inputs, "INPUTS.json"), `{${LF} "files": []${LF}}${LF}`);
  }
  setup.prepare?.(repo, workspace, home);
  const args: PyValue[] = [setup.agent, setup.key ?? "T001", workspace, "角色", setup.prompt ?? "输入", null, setup.fresh ?? false, inputs, setup.sessionId ?? null];
  return { op: "hub.turn", repo, args: args.map((arg) => toTagged(arg)), script: toTagged(pyScript(setup.script ?? {})), sources: SOURCES, home, env: piCmd(setup.mode ?? "ok"),
    roster: setup.roster ?? {}, delivery_sha256: setup.shas ?? {} };
}

/** 带标签的值写成文字：int 写成带 n 的数，dict 写成键值对的数组（保留次序）。 */
const serial = (value: unknown): string => JSON.stringify(value, (_key: string, item: unknown) => (typeof item === "bigint" ? `${item}n` : item instanceof Map ? ["<dict>", ...item] : item));

/** 交回值里的 base64 解开、ISO 时间换成占位：比的是这一份。 */
function shown(result: ProbeResult): unknown {
  if (!result.ok) return result;
  const value = fromTagged(result["value"] as Tagged) as PyDict;
  const text = (item: PyValue | undefined): string | null => (typeof item === "string" ? Buffer.from(item, "base64").toString("utf8").replace(ISO, "<AT>") : null);
  const files = value.get("files") as PyDict;
  const summary = value.get("summary") as PyDict;
  return {
    summary: serial(new Map([...summary].map(([key, item]) => [key, typeof item === "string" ? item.replace(ISO, "<AT>") : item]))), calls: serial(value.get("calls")),
    files: Object.fromEntries([...files].map(([name, item]) => [name, text(item)])),
    long: Object.fromEntries([...(value.get("long_prompts") as PyDict)].map(([name, item]) => [name, text(item)])),
    agent: text(value.get("agent")), ledger: text(value.get("ledger")),
  };
}

/** 三边先后重放：每一边之前照 Setup 重新搭一遍同一组目录。交回 Python 那边的结果。 */
function replay(cases: Record<string, Setup>): Record<string, unknown> {
  const names = Object.keys(cases);
  const results = IMPLS.map((impl) => {
    const requests = names.map((name) => build(name, cases[name] as Setup));
    return runBatch(impl, requests, REPLAY_TIMEOUT).map(shown);
  });
  const [python, ...others] = results;
  for (const [index, other] of others.entries()) {
    names.forEach((name, at) => expect(other[at], `${IMPLS[index + 1]?.name} 与 Python 在「${name}」不同`).toEqual(python?.[at]));
  }
  const crashed = names.filter((_, at) => (python?.[at] as { ok?: boolean }).ok === false);
  expect(crashed, "这些场景两边都没跑完（别让一样地崩掉也算一致）").toEqual([]);
  return Object.fromEntries(names.map((name, at) => [name, python?.[at]]));
}

const PI_SESSION = (stopReason: string): string => `${line({ type: "message", message: { role: "assistant", stopReason } })}${LF}`;
const record = (sessions: Record<string, unknown>): string => `${JSON.stringify({ name: "x", sessions })}${LF}`;

describe("第 ⑤d2 片：TurnRunner 的手写场景", () => {
  it("pi：交差成功、复核不过、没交、读不到参数、非零退出、超时、限流的退避、被拦（参数不认、--help 读不出）", () => {
    const shownCases = replay({
      "pi-ok": { agent: COORDINATOR, script: { stdout: b64(stream(...delivers([{ letters: [], state: "一" }, false]), piDone(COORDINATOR))) } },
      "pi-invalid": { agent: "gate-sonnet", key: "T001-3-gate-pre", script: { stdout: b64(stream(...delivers([{ letter: "x" }, true], [{ letter: {} }, false]), piDone("gate-sonnet"))) } },
      "pi-none": { agent: "audit-sonnet", key: "T001-4-audit-pre", script: { stdout: b64(stream(piDone("audit-sonnet"))), stderr: b64("警告一行") } },
      "pi-unreadable": {
        agent: COORDINATOR,
        script: { stdout: b64(stream({ type: "tool_execution_start", toolCallId: "d0", toolName: "deliver", args: {} },
          { type: "tool_execution_end", toolCallId: "d0", toolName: "deliver", isError: false, result: { content: [] } }, piDone(COORDINATOR))) },
      },
      "pi-exit": { agent: COORDINATOR, script: { stdout: "", exit_code: 1 } },
      "pi-timeout": { agent: COORDINATOR, script: { stdout: b64(stream(piDone(COORDINATOR))), exit_code: null, timed_out: true, wall_seconds: 1200.25 } },
      "pi-throttle": {
        agent: COORDINATOR,
        script: { stdout: b64(stream({ type: "message_end", message: { role: "assistant", provider: ROSTER[COORDINATOR]?.provider, model: ROSTER[COORDINATOR]?.model, stopReason: "error", errorMessage: "429 Too Many Requests" } })) },
        prepare: (repo, workspace) => writeFileSync(join(repo, ".agent", "mailbox", "agents", `${COORDINATOR}.json`), record({ T001: { id: "T001-g0", cwd: workspace, turns: 2, generation: 0, throttles: 2 } })),
      },
      // 会话里记着限流的次数，这一回合没被限流：次数清掉
      "pi-throttle-cleared": {
        agent: COORDINATOR, script: { stdout: b64(stream(...delivers([{ letters: [], state: "三" }, false]), piDone(COORDINATOR))) },
        prepare: (repo, workspace) => writeFileSync(join(repo, ".agent", "mailbox", "agents", `${COORDINATOR}.json`), record({ T001: { id: "T001-g0", cwd: workspace, turns: 2, generation: 0, throttles: 2 } })),
      },
      "pi-blocked-missing": { agent: COORDINATOR, mode: "missing", script: { stdout: b64(stream(piDone(COORDINATOR))) } },
      "pi-blocked-fail": { agent: COORDINATOR, mode: "fail" },
    });
    const of = (name: string): { summary: string; calls: string; ledger: string | null } => shownCases[name] as { summary: string; calls: string; ledger: string | null };
    expect(of("pi-ok").summary).toContain('["output_error",null]');
    expect((shownCases["pi-throttle-cleared"] as { agent: string }).agent).not.toContain("throttles");
    expect(of("pi-invalid").summary).toContain("deliver 交上来的参数内核复核不过");
    expect(of("pi-unreadable").summary).toContain("交差工具报了成功，内核读不到参数");
    expect(of("pi-exit").summary).toContain("pi 一条回复都没有就以退出码 1 结束");
    expect(of("pi-throttle").summary).toContain('["rate_limited_until","1800001200n"]');
    for (const name of ["pi-blocked-missing", "pi-blocked-fail"]) expect(of(name).calls, name).toBe("[]");
    expect(of("pi-blocked-missing").summary).toContain("本机 pi 不认识 hub 传给工人的参数：--session-dir");
  }, 300_000);

  it("pi 的会话：续接、fresh、工作目录变了、停在半截换新会话、跳过已有会话文件的代、给定会话号", () => {
    const resumed = (stop = "stop") => (repo: string, workspace: string): void => {
      writeFileSync(join(repo, ".agent", "mailbox", "agents", `${COORDINATOR}.json`), record({ T001: { id: "T001-g0", cwd: workspace, turns: 3, generation: 0, cost_usd_total: 0.5 } }));
      mkdirSync(join(repo, ".agent", "mailbox", "sessions", COORDINATOR), { recursive: true });
      writeFileSync(join(repo, ".agent", "mailbox", "sessions", COORDINATOR, `20261031_T001-g0.jsonl`), PI_SESSION(stop));
    };
    const script = { stdout: b64(stream(...delivers([{ letters: [], state: "二" }, false]), piDone(COORDINATOR))) };
    const sessions = replay({
      "session-resume": { agent: COORDINATOR, script, prepare: resumed() },
      "session-fresh": { agent: COORDINATOR, script, fresh: true, prepare: resumed() },
      "session-moved": { agent: COORDINATOR, script, prepare: (repo, workspace) => resumed()(repo, join(workspace, "elsewhere")) },
      "session-cut": { agent: COORDINATOR, script, prepare: resumed("toolUse") },
      "session-skip": {
        agent: COORDINATOR, script,
        prepare: (repo) => {
          mkdirSync(join(repo, ".agent", "mailbox", "sessions", COORDINATOR), { recursive: true });
          for (const generation of [0, 1]) writeFileSync(join(repo, ".agent", "mailbox", "sessions", COORDINATOR, `x_T001-g${generation}.jsonl`), PI_SESSION("stop"));
        },
      },
      "session-given": { agent: COORDINATOR, script, sessionId: "T001-g7", prepare: resumed() },
    });
    const id = (name: string): string => (sessions[name] as { summary: string }).summary;
    expect([id("session-resume"), id("session-fresh"), id("session-cut"), id("session-skip"), id("session-given")].map((text) => text.match(/T001-g[0-9]+/u)?.[0]))
      .toEqual(["T001-g0", "T001-g1", "T001-g1", "T001-g2", "T001-g7"]);
    expect((sessions["session-cut"] as { ledger: string }).ledger).toContain("session.cut_short");
  }, 300_000);

  it("claude：新会话、续接、生效档位取会话文件、只读输入目录与长输入、主工作区里装好的依赖", () => {
    const spec = ROSTER["planner-opus"];
    const init = { type: "system", subtype: "init", tools: [...(spec?.tools ?? []), "StructuredOutput"], mcp_servers: [], model: spec?.model, session_id: "s1" };
    const good = { letter: LETTER, report: "出处", state: "", external_facts: [] };
    const use = { type: "assistant", message: { model: spec?.model, content: [{ type: "tool_use", id: "u1", name: "StructuredOutput", input: good }] } };
    const result = { type: "result", result: "", structured_output: good, total_cost_usd: 2.5, usage: { output_tokens_details: { thinking_tokens: 28501 } } };
    const script = { stdout: b64(stream(init, use, result)) };
    const effort = (id: string) => (_repo: string, _workspace: string, home: string): void => {
      mkdirSync(join(home, ".claude", "projects", "C--x"), { recursive: true });
      writeFileSync(join(home, ".claude", "projects", "C--x", `${id}.jsonl`), `${line({ type: "assistant", effort: "max" })}${LF}`);
    };
    const claude = replay({
      "claude-first": { agent: "planner-opus", key: "T001-1-plan", script, prepare: effort(SOURCES.uuid4) },
      "claude-resume": {
        agent: "planner-opus", key: "T001-1-plan", script,
        prepare: (repo, workspace, home) => {
          writeFileSync(join(repo, ".agent", "mailbox", "agents", "planner-opus.json"), record({ "T001-1-plan": { id: "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa", cwd: workspace, turns: 1, generation: 0, cost_usd_total: 1.25 } }));
          effort("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa")(repo, workspace, home);
        },
      },
      "claude-inputs": {
        agent: "planner-opus", key: "T001-1-plan", inputs: true, prompt: "长".repeat(20001), script,
        prepare: (repo) => mkdirSync(join(repo, "ts", "node_modules"), { recursive: true }),
      },
      "pi-inputs": { agent: "gate-sonnet", key: "T001-3-gate-pre", inputs: true, prompt: "x".repeat(20001), script: { stdout: b64(stream(piDone("gate-sonnet"))) } },
    });
    const at = (name: string): { summary: string; calls: string; long: Record<string, string> } => claude[name] as { summary: string; calls: string; long: Record<string, string> };
    expect(at("claude-first").calls).toContain(`"--session-id","${SOURCES.uuid4}"`);
    expect(at("claude-first").summary).toContain('["effort_effective","max"]');
    expect(at("claude-resume").calls).toContain('"--resume","aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"');
    expect(Object.keys(at("claude-inputs").long)).toEqual([`prompt-${SOURCES.compact}-${SOURCES.random2}.md`]);
    expect(at("claude-inputs").calls).toContain("--add-dir");
  }, 300_000);
});

// 名册与交差文件换过的手写场景，两边设同一个覆盖值（pytest 里改过这两样的用例，采样时另照调用当时记下的覆盖值重放，见最后一节）
const CLAUDE_GATE = { role: "gate", adapter: "claude", model: "claude-sonnet-5-5", effort: "high", tools: ["Read", "Grep", "Glob", "Edit", "Write", "Bash"],
  allowed_rules: ["Bash(python -m pytest:*)"], timeout: 2400, workspace: "stage" };
const CLAUDE_AUDIT = { role: "audit", adapter: "claude", model: "claude-sonnet-5-5", effort: "max", tools: ["Read", "Grep", "Glob"], timeout: 2400, workspace: "stage" };
const CHANGED = "0".repeat(64);

describe("第 ⑤d2 片：名册与交差文件换过的场景（对应改过全局的用例）", () => {
  it("交差文件被改过（schema、守卫扩展）就不起；claude 工人带写工具时只许写工作目录、shell 回到工作目录；U+2028 藏起来的调用照样作废", () => {
    const init = (tools: string[]) => ({ type: "system", subtype: "init", tools: [...tools, "StructuredOutput"], mcp_servers: [], model: "claude-sonnet-5-5", session_id: "s1" });
    const hidden = { type: "assistant", message: { model: "claude-sonnet-5-5", content: [{ type: "tool_use", id: "w1", name: "Write", input: { file_path: `x${C(0x2028)}y` } }] } };
    const cases = replay({
      "changed-coordinator-schema": { agent: COORDINATOR, shas: { "coordinator.json": CHANGED } },
      "changed-planner-schema": { agent: "planner-opus", key: "T001-1-plan", shas: { "planner.json": CHANGED } },
      "changed-guard": { agent: COORDINATOR, shas: { "guard.ts": CHANGED } },
      "claude-gate-writes": { agent: "gate-sonnet", key: "T001-3-gate-pre", roster: { "gate-sonnet": CLAUDE_GATE }, inputs: true, script: { stdout: b64(stream(init(CLAUDE_GATE.tools))) } },
      "claude-audit-u2028": { agent: "audit-sonnet", key: "T001-4-audit-pre", roster: { "audit-sonnet": CLAUDE_AUDIT }, script: { stdout: b64(stream(init(CLAUDE_AUDIT.tools), hidden)) } },
    });
    const of = (name: string): { summary: string; calls: string } => cases[name] as { summary: string; calls: string };
    for (const name of ["changed-coordinator-schema", "changed-planner-schema", "changed-guard"]) {
      expect(of(name).summary, name).toContain("交差工具的文件被改过");
      expect(of(name).calls, name).toBe("[]");
    }
    expect(of("claude-gate-writes").calls).toContain("acceptEdits");
    expect(of("claude-gate-writes").calls).toContain("CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR");
    expect(of("claude-audit-u2028").summary).toContain("白名单之外的工具");
  }, 300_000);
});

describe("第 ⑤d2 片：真的来源与 claude 的路径", () => {
  it("不注入时用真的来源：回合号是“8 位日期 T 12 位时刻 Z-4 位十六进制”，claude 的新会话号是 uuid4 的形状", () => {
    const turnId = new RegExp(`^${BS}d{8}T${BS}d{12}Z-[0-9a-f]{4}$`, "u");
    const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
    for (const impl of IMPLS) {
      const requests = [build(`real-pi-${impl.name}`, { agent: COORDINATOR }), build(`real-claude-${impl.name}`, { agent: "planner-opus", key: "T001-1-plan" })]
        .map(({ sources: _sources, ...rest }) => rest as ProbeRequest);
      const [pi, claude] = runBatch(impl, requests).map((result) => fromTagged(result["value"] as Tagged) as PyDict);
      const summary = (value: PyDict | undefined): PyDict => value?.get("summary") as PyDict;
      expect(String(summary(pi).get("turn_id")), impl.name).toMatch(turnId);
      expect(String(summary(claude).get("turn_id")), impl.name).toMatch(turnId);
      expect(String(summary(claude).get("session_id")), impl.name).toMatch(uuid4);
    }
  }, 300_000);

  it("claude 的路径：同一目录里同时有 claude.cmd、claude.exe、没扩展名的 claude，两边挑中同一个、扩展名的写法也相同", () => {
    const bin = join(LONG, "bin");
    mkdirSync(bin, { recursive: true });
    for (const name of ["claude.cmd", "claude.exe", "claude"]) writeFileSync(join(bin, name), "");
    const env = { PATH: bin, PATHEXT: ".COM;.EXE;.BAT;.CMD" };
    const shownPath = IMPLS.map((impl) => {
      const request = { ...build("claude-which-path", { agent: "planner-opus", key: "T001-1-plan" }), env };
      const value = fromTagged(runBatch(impl, [request])[0]?.["value"] as Tagged) as PyDict;
      return ((value.get("calls") as PyDict[])[0]?.get("cmd") as string[])[0];
    });
    expect(new Set(shownPath).size, JSON.stringify(shownPath)).toBe(1);
    expect(String(shownPath[0]).startsWith(bin)).toBe(true);
  }, 300_000);
});
// --- 输入目录 -----------------------------------------------------------------------------------------------

/** stage_inputs 的现场：本主任务的各阶段目录（另有两个只是前缀相同的）、合同的各版本（另有一个名字相近的）、runs 证据（一个超过 4 MB、
 * 一个联接、一个符号链接），worktree 根目录下这个主任务留下的旧目录与别的主任务的目录。交回（仓库，worktree 根目录）。 */
function inputsRepo(): { repo: string; worktrees: string } {
  const dir = join(LONG, "inputs-case");
  rmSync(dir, { recursive: true, force: true });
  const repo = join(dir, "repo");
  const worktrees = join(dir, "worktrees");
  const put = (rel: string, content: string | Buffer): void => {
    mkdirSync(join(repo, ...rel.split("/"), ".."), { recursive: true });
    writeFileSync(join(repo, ...rel.split("/")), content);
  };
  put(".agent/dispatch.config.json", JSON.stringify({ worktree_root: worktrees }));
  for (const task of ["T001", "T001-1-plan", "T001-2-contract", "T0010", "T001x"]) {
    put(`.agent/mailbox/tasks/${task}/brief.md`, `# ${task}${LF}`);
    put(`.agent/mailbox/tasks/${task}/state.md`, `断点 ${FACE}${LF}`);
  }
  put(".agent/mailbox/tasks/T001-2-contract/evidence/sub/x.log", "日志");
  for (const name of ["t001-doc.v1.md", "t001-doc.v2.md", "t001-doc.v1.json", "t001-docx.v1.md"]) put(`.agent/plans/${name}`, name);
  put(".agent/runs/t001-doc/attempt-001/run.json", "{}");
  put(".agent/runs/t001-doc/attempt-001/events.jsonl", Buffer.alloc(4 * 1024 * 1024 + 1, 120));
  put(".agent/runs/t001-doc/attempt-001/candidate.patch", "diff");
  put("outside/secret.txt", "不该被复制");
  symlinkSync(join(repo, "outside"), join(repo, ".agent", "runs", "t001-doc", "junction"), "junction");
  symlinkSync(join(repo, "outside", "secret.txt"), join(repo, ".agent", "runs", "t001-doc", "attempt-001", "link.txt"), "file");
  const parent = join(worktrees, "repo-hub-inputs");
  for (const old of ["T001-old", "T002-other"]) {
    mkdirSync(join(parent, old), { recursive: true });
    writeFileSync(join(parent, old, "x.md"), "旧");
    chmodSync(join(parent, old, "x.md"), 0o444);
  }
  return { repo, worktrees };
}

describe("第 ⑤d2 片：只读输入目录", () => {
  it("复制的范围、超过 4 MB 的跳过、链接与联接不跟、只读位、INPUTS.json（CRLF）与 SKIPPED.md、旧目录清掉而别的主任务的不动、删得干净", () => {
    const ts = toTagged(new Map<string, PyValue>([["task", "T001"], ["contract_task", "t001-doc"]]));
    const results = IMPLS.map((impl) => {
      const { repo, worktrees } = inputsRepo();
      const [staged] = runBatch(impl, [{ op: "hub.inputs", repo, ts, key: "T001-1-plan-20261031T120000123456Z-beef" }]);
      const parent = join(worktrees, "repo-hub-inputs");
      const left = ["T001-old", "T002-other"].map((name) => existsSync(join(parent, name)));
      const value = fromTagged(staged?.["value"] as Tagged) as PyDict;
      const [removed] = runBatch(impl, [{ op: "hub.inputs", repo, remove: String(value.get("dir")) }]);
      return { staged: serial(value), left, removed: serial(fromTagged(removed?.["value"] as Tagged)) };
    });
    for (const [index, other] of results.slice(1).entries()) expect(other, IMPLS[index + 1]?.name).toEqual(results[0]);
    expect(results[0]?.left).toEqual([false, true]);
    expect(results[0]?.removed).toBe("false");
    const staged = results[0]?.staged ?? "";
    expect(staged).toContain("events.jsonl");
    expect(staged).not.toContain("secret");
    expect(staged).not.toContain("T0010");
  }, 300_000);
});
// --- pytest 的场景 ------------------------------------------------------------------------------------------

const TURN_TESTS = [
  "test_a_session_cut_short_mid_tool_call_is_not_continued",
  "test_turn_runner_reports_when_the_rate_limit_lifts",
  "test_session_ids_change_on_a_fresh_restart",
  "test_turn_cost_is_this_turn_not_the_session_total",
  "test_claude_resumes_the_named_session_of_an_interrupted_turn",
  "test_claude_workers_read_the_inputs_and_write_only_their_worktree",
  "test_planner_may_only_run_npm_view",
  "test_turn_with_api_error_says_so",
  "test_claude_workers_return_to_the_workspace_after_each_command",
  "test_pi_workers_run_their_rostered_model_and_tools",
  "test_pi_workers_may_not_write_outside_their_worktree",
  "test_pi_workers_load_the_guard_with_the_kernel_roots",
  "test_a_throttled_pi_turn_is_held_with_a_growing_backoff",
  "test_a_turn_whose_stream_hides_a_call_behind_u2028_is_voided",
  "test_stage_inputs_copies_this_tasks_mailbox_contracts_and_evidence_read_only",
  "test_the_runner_keeps_the_listing_and_writes_long_prompts_into_the_inputs",
  "test_stage_inputs_does_not_follow_directory_links_or_junctions",
  "test_stage_inputs_clears_this_tasks_leftover_directories",
  "test_a_coordinator_turn_hands_in_through_deliver",
  "test_an_audit_turn_hands_in_through_deliver",
  "test_a_gate_turn_hands_in_through_deliver",
  "test_a_contract_turn_hands_in_through_deliver",
  "test_a_changed_planner_schema_stops_the_claude_turn",
  "test_the_planner_hands_in_through_claude_json_schema",
  "test_no_deliver_or_a_bad_one_is_an_invalid_output",
  "test_a_delivery_the_kernel_cannot_read_is_an_interface_error",
  "test_a_changed_delivery_file_stops_the_turn",
];

/** 调 stage_inputs 的用例：只调它的三条，与 TurnRunner 用例里先调它的那一条。 */
const STAGE_TESTS = [
  "test_stage_inputs_clears_this_tasks_leftover_directories",
  "test_stage_inputs_copies_this_tasks_mailbox_contracts_and_evidence_read_only",
  "test_stage_inputs_does_not_follow_directory_links_or_junctions",
  "test_the_runner_keeps_the_listing_and_writes_long_prompts_into_the_inputs",
];

/**
 * 记下的一次调用照当时的样子交给探针：快照放回原位置（链接与联接照记下的重建）。TurnRunner 照记下的回放脚本、来源、home，以及调用当时
 * 名册与交差文件哈希的覆盖值（用例里 monkeypatch.setitem 改过的）；stage_inputs 照记下的 worktree 根目录与 INPUT_FILE_LIMIT（inputs_fixture 换过的）。
 */
function sampled(item: PyDict): ProbeRequest {
  const repo = String(item.get("repo"));
  const restore = { from: String(item.get("snapshot")), to: repo, links: item.get("links") };
  if (item.get("fn") === "stage_inputs") {
    return { op: "hub.inputs", repo, restore, ts: toTagged(item.get("ts") as PyValue), key: String(item.get("key")),
      worktree_root: String(item.get("worktree_root")), input_file_limit: Number(item.get("input_file_limit")) };
  }
  const sources = item.get("sources") as PyDict;
  const overrides = JSON.parse(String(item.get("overrides"))) as { roster: Record<string, unknown>; delivery_sha256: Record<string, string> };
  return {
    op: "hub.turn", repo, restore, args: (item.get("args") as PyValue[]).map((arg) => toTagged(arg)), script: toTagged(item.get("script") as PyValue),
    home: String(item.get("home")), env: piCmd("ok"), roster: overrides.roster, delivery_sha256: overrides.delivery_sha256,
    sources: { compact: String(sources.get("compact")), random2: String(sources.get("random2")), uuid4: String(sources.get("uuid4")), seconds: Number(sources.get("seconds")) },
  };
}

/** 比的那一份：TurnRunner 照 shown；stage_inputs 的产物整份写成文字（只读位、sha256、INPUTS.json 与 SKIPPED.md 的字节、上一层剩下的目录）。 */
const view = (item: PyDict, result: ProbeResult): unknown =>
  item.get("fn") !== "stage_inputs" ? shown(result) : result.ok ? serial(fromTagged(result["value"] as Tagged)) : result;

describe("第 ⑤d2 片：pytest 的场景（样例只有 tests/test_kit_hub.py 这一个来源）", () => {
  it("记下的 TurnRunner.run 与 stage_inputs 三边在调用当时的目录里重放：先比 Python 重放与当时的结果，再比三边", () => {
    const tmp = join(ROOT, "samples");
    mkdirSync(tmp, { recursive: true });
    // 采样与重放都用假 pi（设计稿第 3 节）：采样时 --help 的探测被 autouse 夹具换成全认，pi 不起；重放时两边去探假 pi 的 --help
    const recorded = runBatch(PYTHON_IMPL, [{ op: "hub.audit_samples", tests: TURN_TESTS, functions: ["TurnRunner.run", "stage_inputs"], tmp, env: piCmd("ok") }])[0];
    expect(recorded?.ok, JSON.stringify(recorded).slice(0, 2000)).toBe(true);
    const value = fromTagged(recorded?.["value"] as Tagged) as PyDict;
    expect(value.get("skipped")).toEqual([]);
    const calls = value.get("calls") as PyDict[];
    const testOf = (item: PyDict): string => String(item.get("test"));
    expect(new Set(calls.filter((item) => item.get("fn") === "TurnRunner.run").map(testOf)).size, "记到 TurnRunner.run 的用例").toBe(24);
    expect([...new Set(calls.filter((item) => item.get("fn") === "stage_inputs").map(testOf))].sort(), "记到 stage_inputs 的用例").toEqual(STAGE_TESTS);
    const replayed = calls.filter((item) => item.get("fn") === "stage_inputs" || item.has("script"));
    // 记下的 pi 命令都以假 pi 开头（采样当时设了 PI_DISPATCH_PI_CMD）：以后改了采样，也不会悄悄又起本机的 pi
    const fake = JSON.parse(piCmd("ok")["PI_DISPATCH_PI_CMD"] as string) as string[];
    const piHeads = replayed.filter((item) => item.get("fn") === "TurnRunner.run").flatMap((item) => {
      const agent = String((item.get("args") as PyValue[])[0]);
      const roster = (JSON.parse(String(item.get("overrides"))) as { roster: Record<string, { adapter?: string }> }).roster;
      const back = JSON.parse(String(item.get("result"))) as ProbeResult;
      if ((roster[agent] ?? ROSTER[agent])?.adapter === "claude" || !back.ok) return [];
      return ((fromTagged(back["value"] as Tagged) as PyDict).get("calls") as PyDict[]).map((call) => JSON.stringify((call.get("cmd") as string[]).slice(0, fake.length)));
    });
    expect(piHeads.length, "记下的 pi 命令").toBe(39);
    expect(piHeads.filter((head) => head !== JSON.stringify(fake)), "不以假 pi 开头的 pi 命令").toEqual([]);
    const label = (item: PyDict, at: number): string => `${testOf(item)}（第 ${at} 条记录，${String(item.get("fn"))}）`;
    const [python, ...others] = IMPLS.map((impl) => runBatch(impl, replayed.map(sampled)).map((result, at) => view(replayed[at] as PyDict, result)));
    const drifted = replayed.flatMap((item, at) =>
      JSON.stringify(view(item, JSON.parse(String(item.get("result"))) as ProbeResult)) === JSON.stringify(python?.[at]) ? [] : [label(item, at)]);
    expect(drifted, "当时的结果与 Python 重放").toEqual([]);
    for (const [index, other] of others.entries()) {
      replayed.forEach((item, at) => expect(other[at], `${IMPLS[index + 1]?.name} 在 ${label(item, at)}`).toEqual(python?.[at]));
    }
  }, 900_000);
});
