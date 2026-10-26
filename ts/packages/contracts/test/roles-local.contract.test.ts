// kit_roles 不起 CLI 的部分的契约（迁移第 ③c 片）：shutil.which、resolve_pi_command、本机文件（read_local）、runtime_command、
// resolve_role_executor、allowed_executor_check、load_binding_record。混合期 pi_dispatch 在进程内调用这几个名字，两边对同一份
// 输入要得出同样的结果。每条先断言 Python 的结果，再要求 TS 两种运行方式逐字一致。
// 假的 pi、node、claude 都是临时目录里的空文件或批处理文本，只解析、不运行；PATH、PATHEXT 与当前目录每条请求自己给。
import { spawnSync } from "node:child_process";
import { mkdirSync, realpathSync, symlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { type Tagged, fromTagged } from "../src/tagged.ts";
import { type ProbeRequest, type ProbeResult, removeDir, runAgreeing, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("roles"));
afterAll(() => removeDir(ROOT));
const BS = String.fromCharCode(92);
const CRLF = String.fromCharCode(13, 10);
const TOKEN = `sk-${"b2".repeat(12)}`;

function put(path: string, content: string | Buffer = ""): string {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content);
  return path;
}

/** npm 生成的 .cmd 包装（只有入口脚本那一行要紧）。 */
const shim = (script: string): string => `@ECHO off${CRLF}"%dp0%${BS}node.exe" "%dp0%${BS}${script}" %*${CRLF}`;

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  readonly check: (result: ProbeResult) => string | null;
}

const valueOf = (result: ProbeResult): PyValue => fromTagged(result["value"] as Tagged);
const field = (value: PyValue, key: string): PyValue => (value instanceof Map ? ((value as PyDict).get(key) ?? null) : null);

/** Python 的结果是 ok，取值满足 predicate。 */
const gives = (name: string, request: ProbeRequest, predicate: (value: PyValue) => boolean): Case => ({
  name,
  request,
  check: (result) => (result.ok && predicate(valueOf(result)) ? null : JSON.stringify(result)),
});
/** Python 抛 DispatchError（含 BindingRecordError），消息含 fragment、退出码是 code。 */
const fails = (name: string, request: ProbeRequest, fragment: string, code: number): Case => ({
  name,
  request,
  check: (result) => (result["error"] === "DispatchError" && String(result["message"]).includes(fragment) && result["code"] === code ? null : JSON.stringify(result)),
});

function verifyAll(cases: readonly Case[]): void {
  const { python, mismatches } = runAgreeing(cases.map((item) => item.request));
  const wrong = cases.flatMap((item, index) => {
    const problem = item.check(python[index] as ProbeResult);
    return problem === null ? [] : [{ name: item.name, python: problem }];
  });
  expect(wrong, "Python 的结果不符合契约").toEqual([]);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
}

const call = (fn: string, fields: Record<string, unknown>): ProbeRequest => ({ op: "roles.call", fn, cwd: ROOT, ...fields });

// --- PATH 上的假程序 -------------------------------------------------------------------------------
const PI_SCRIPT = ["node_modules", "@earendil-works", "pi", "dist", "cli.js"].join(BS);
const B1 = join(ROOT, "bin1"); // .cmd 包装，旁边有 node.exe 与入口脚本
put(join(B1, "pi.cmd"), shim(PI_SCRIPT));
put(join(B1, "node.exe"));
put(join(B1, ...PI_SCRIPT.split(BS)));
const B2 = join(ROOT, "bin2"); // pi.exe
put(join(B2, "pi.exe"));
const B3 = join(ROOT, "bin3"); // 名叫 pi.EXE 的目录（不算）
mkdirSync(join(B3, "pi.EXE"), { recursive: true });
const B4 = join(ROOT, "bin4"); // claude.cmd 与 node.exe
put(join(B4, "claude.cmd"), "@echo off");
put(join(B4, "node.exe"));
const B5 = join(ROOT, "bin5"); // .bat 包装，入口脚本不在
put(join(B5, "pi.bat"), shim(PI_SCRIPT));
const B6 = join(ROOT, "bin6"); // .cmd 包装，旁边没有 node.exe（从 PATH 找）
put(join(B6, "pi.cmd"), shim(PI_SCRIPT.replace("cli.js", "cli.mjs")));
put(join(B6, ...PI_SCRIPT.replace("cli.js", "cli.mjs").split(BS)));
const B7 = join(ROOT, "bin7"); // 没有后缀的 pi
put(join(B7, "pi"));
const B8 = join(ROOT, "bin8"); // 包装里没有 %dp0% 的入口脚本
put(join(B8, "pi.cmd"), `@echo off${CRLF}node cli.js %*${CRLF}`);
const EMPTY = join(ROOT, "empty");
mkdirSync(EMPTY, { recursive: true });
const CWD = join(ROOT, "cwd"); // 当前目录里有 pi.bat
put(join(CWD, "pi.bat"), "@echo off");

const which = (name: string, env: Record<string, string | null>, cwd = ROOT): ProbeRequest => call("which", { name, env: { PATHEXT: null, NoDefaultCurrentDirectoryInExePath: null, ...env }, cwd });
const piCommand = (env: Record<string, string | null>): ProbeRequest => call("resolve_pi_command", { env: { PATHEXT: null, NoDefaultCurrentDirectoryInExePath: null, PI_DISPATCH_PI_CMD: null, ...env } });
const is = (expected: PyValue) => (value: PyValue): boolean => JSON.stringify(value) === JSON.stringify(expected);

describe("shutil.which 与 resolve_pi_command", () => {
  it("契约", () => {
    verifyAll([
      gives("PATH 上的 pi.exe：后缀照 PATHEXT 的写法", which("pi", { PATH: B2 }), is(join(B2, "pi.EXE"))),
      gives("名叫 pi.EXE 的目录不算", which("pi", { PATH: `${B3};${B2}` }), is(join(B2, "pi.EXE"))),
      gives("PATH 是空串：找不到", which("pi", { PATH: "" }), is(null)),
      gives("没有 PATH：取 os.defpath，当前目录先查", which("pi", { PATH: null }, CWD), is(`.${BS}pi.BAT`)),
      gives("当前目录排在 PATH 前面", which("pi", { PATH: B2 }, CWD), is(`.${BS}pi.BAT`)),
      gives("设了 NoDefaultCurrentDirectoryInExePath 就不查当前目录", which("pi", { PATH: B2, NoDefaultCurrentDirectoryInExePath: "1" }, CWD), is(join(B2, "pi.EXE"))),
      gives("PATHEXT 的次序", which("pi", { PATH: `${CWD};${B2}`, PATHEXT: ".EXE;.BAT", NoDefaultCurrentDirectoryInExePath: "1" }), is(join(CWD, "pi.BAT"))),
      gives("名字已带 PATHEXT 里的后缀：先试名字本身", which("pi.exe", { PATH: B2 }), is(join(B2, "pi.exe"))),
      gives("PATH 里重复的目录（大小写不同）", which("claude", { PATH: `${B2};${B2.toUpperCase()};${B4}` }), is(join(B4, "claude.CMD"))),
      gives("名字带目录：只查那个目录", which(join(B2, "pi"), { PATH: B4 }), is(join(B2, "pi.EXE"))),
      gives("PATH 里的空项按当前目录拼", which("pi", { PATH: `;;${B2};`, NoDefaultCurrentDirectoryInExePath: "1" }), is(join(B2, "pi.EXE"))),
      gives("PATHEXT 里只有点的一项：名字本身也试", which("pi", { PATH: B7, PATHEXT: ".;.EXE" }), is(join(B7, "pi"))),
      gives("找不到", which("nonexistent-program", { PATH: `${B2};${B4}` }), is(null)),
      gives("PI_DISPATCH_PI_CMD 是 JSON 数组", piCommand({ PI_DISPATCH_PI_CMD: '["C:/x/pi.exe", "--flag"]' }), is(["C:/x/pi.exe", "--flag"])),
      gives("PI_DISPATCH_PI_CMD 不是 JSON：整串当路径", piCommand({ PI_DISPATCH_PI_CMD: "C:/x/pi" }), is(["C:/x/pi"])),
      fails("PI_DISPATCH_PI_CMD 是空数组", piCommand({ PI_DISPATCH_PI_CMD: "[]" }), "PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组", 2),
      fails("PI_DISPATCH_PI_CMD 里有非字符串", piCommand({ PI_DISPATCH_PI_CMD: "[1]" }), "PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组", 2),
      fails("PI_DISPATCH_PI_CMD 是 JSON 字符串", piCommand({ PI_DISPATCH_PI_CMD: '"x"' }), "PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组", 2),
      fails("PI_DISPATCH_PI_CMD 里有空串", piCommand({ PI_DISPATCH_PI_CMD: '[""]' }), "PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组", 2),
      gives("npm 的 .cmd 包装：绕过它，用旁边的 node.exe 跑入口脚本", piCommand({ PATH: B1 }), is([join(B1, "node.exe"), join(B1, PI_SCRIPT)])),
      gives(".bat 包装、入口脚本不在：照旧用包装", piCommand({ PATH: B5 }), is([join(B5, "pi.BAT")])),
      gives("包装旁边没有 node.exe：从 PATH 找 node", piCommand({ PATH: `${B6};${B4}` }), is([join(B4, "node.EXE"), join(B6, PI_SCRIPT.replace("cli.js", "cli.mjs"))])),
      gives("包装里没有 %dp0% 的入口脚本", piCommand({ PATH: B8 }), is([join(B8, "pi.CMD")])),
      gives("不是包装的 pi.exe", piCommand({ PATH: B2 }), is([join(B2, "pi.EXE")])),
      fails("PATH 上没有 pi", piCommand({ PATH: EMPTY }), "PATH 中找不到 pi", 3),
    ]);
  });
});

// --- 本机文件 ---------------------------------------------------------------------------------------

function gitRepo(name: string, ignoreLocal = true): string {
  const repo = join(ROOT, "repos", name);
  mkdirSync(join(repo, ".agent"), { recursive: true });
  const done = spawnSync("git", ["init", "-q", repo], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`git init 失败：${done.stderr}`);
  if (ignoreLocal) writeFileSync(join(repo, ".gitignore"), ".agent/dispatch.local.json\n.agent/runs/\n");
  return repo;
}

function localRepo(name: string, content: string | Buffer | null, ignoreLocal = true): string {
  const repo = gitRepo(name, ignoreLocal);
  if (content !== null) writeFileSync(join(repo, ".agent", "dispatch.local.json"), content);
  return repo;
}

const CONFIG = JSON.stringify({ runtimes: { pi: { adapter: "pi" }, cc: { adapter: "claude-code" }, oc: { adapter: "opencode" }, _note: "x" } });
const local = (repo: string, config = CONFIG): ProbeRequest => call("read_local", { repo, config });
const errorsHave = (fragment: string) => (value: PyValue): boolean => field(value, "commands") === null && JSON.stringify(field(value, "errors")).includes(fragment);

describe("本机文件（read_local）", () => {
  it("不存在、合法、各种坏法、没被忽略、被跟踪、经过链接、读不出来", () => {
    const tracked = localRepo("tracked", '{"runtimes": {}}');
    spawnSync("git", ["-C", tracked, "add", "-f", ".agent/dispatch.local.json"], { encoding: "utf8" });
    const linked = gitRepo("linked");
    removeDir(join(linked, ".agent"));
    const elsewhere = join(ROOT, "elsewhere-agent");
    put(join(elsewhere, "dispatch.local.json"), '{"runtimes": {}}');
    symlinkSync(elsewhere, join(linked, ".agent"), "junction");
    const directory = gitRepo("directory");
    mkdirSync(join(directory, ".agent", "dispatch.local.json"));
    verifyAll([
      gives("不存在：空命令表", local(gitRepo("absent")), (value) => JSON.stringify(field(value, "errors")) === "[]" && field(value, "commands") instanceof Map),
      gives(
        "合法：说明键不算条目",
        local(localRepo("valid", JSON.stringify({ runtimes: { pi: { command: ["C:/x/pi.exe", "--a"] }, _note: { any: 1 } } }))),
        (value) => JSON.stringify([...((field(value, "commands") as PyDict) ?? new Map())]) === JSON.stringify([["pi", ["C:/x/pi.exe", "--a"]]]),
      ),
      gives("配置里没有登记的 runtime：警告", local(localRepo("unregistered", JSON.stringify({ runtimes: { other: { command: ["x"] } } }))), (value) => JSON.stringify(field(value, "warnings")).includes("'other' 没有在配置的 runtimes 里登记")),
      gives("解析不了", local(localRepo("broken", "{not json")), errorsHave("读不出来（JSONDecodeError）")),
      gives("不是 UTF-8", local(localRepo("latin", Buffer.from([0x7b, 0xff, 0x7d]))), errorsHave("读不出来（UnicodeDecodeError）")),
      gives("嵌套太深", local(localRepo("deep", `${"[".repeat(100000)}${"]".repeat(100000)}`)), errorsHave("读不出来（RecursionError）")),
      gives("有疑似凭据：只报位置", local(localRepo("secret", JSON.stringify({ runtimes: { pi: { command: [TOKEN] } } }))), errorsHave("里有疑似凭据（runtimes.pi.command.0）")),
      gives("顶层多了键", local(localRepo("extra", JSON.stringify({ runtimes: {}, x: 1 }))), errorsHave("只接受")),
      gives("runtimes 不是对象", local(localRepo("list", JSON.stringify({ runtimes: [] }))), errorsHave("只接受")),
      gives("runtimes 是 null", local(localRepo("null", JSON.stringify({ runtimes: null }))), errorsHave("只接受")),
      gives("顶层是数组", local(localRepo("array", "[]")), errorsHave("只接受")),
      gives(
        "条目不合法：ID、命令为空、命令里有非字符串、多了键",
        local(localRepo("entries", JSON.stringify({ runtimes: { Bad: { command: ["x"] }, a: { command: [] }, b: { command: ["x", 1] }, c: { command: ["x"], y: 1 }, d: "x" } }))),
        (value) => (field(value, "errors") as string[]).length === 5,
      ),
      gives("没被 .gitignore 忽略", local(localRepo("not-ignored", '{"runtimes": {}}', false)), errorsHave("没有被 .gitignore 忽略")),
      gives("被 Git 跟踪", local(tracked), errorsHave("被 Git 跟踪")),
      gives("经过 junction", local(linked), errorsHave("经过链接或 junction（.agent）")),
      gives("是目录", local(directory), errorsHave("读不出来（PermissionError）")),
    ]);
  });
});

// --- runtime_command ------------------------------------------------------------------------------

/** check_local 要运行 git：PATH 后面接上 git 所在的目录（那里没有 pi、claude、opencode）。 */
const GIT_DIR = dirname((spawnSync("where", ["git"], { encoding: "utf8" }).stdout.split(String.fromCharCode(10))[0] ?? "").trim());
const runtime = (repo: string, name: string, env: Record<string, string>, adapter: string | null = null, config = CONFIG): ProbeRequest =>
  call("runtime_command", { repo, config, runtime: name, adapter, env: { PATHEXT: null, NoDefaultCurrentDirectoryInExePath: null, PI_DISPATCH_PI_CMD: null, ...env, PATH: `${env["PATH"] ?? ""};${GIT_DIR}` } });
const resolved = (source: string, command: PyValue, lines: (text: string) => boolean = (text) => text === "[]") => (value: PyValue): boolean =>
  field(value, "source") === source && JSON.stringify(field(value, "command")) === JSON.stringify(command) && lines(JSON.stringify(field(value, "lines")));

describe("runtime_command", () => {
  it("环境变量、本机文件、PATH、找不到、没登记", () => {
    const plain = gitRepo("plain");
    const withLocal = localRepo("with-local", JSON.stringify({ runtimes: { pi: { command: ["C:/local/pi.exe"] }, oc: { command: ["C:/local/oc.exe"] } } }));
    const badLocal = localRepo("bad-local", "{not json");
    verifyAll([
      gives("pi：PI_DISPATCH_PI_CMD 优先，不读本机文件", runtime(withLocal, "pi", { PI_DISPATCH_PI_CMD: '["C:/env/pi"]', PATH: B2 }), resolved("env", ["C:/env/pi"])),
      gives("pi：本机文件", runtime(withLocal, "pi", { PATH: B2 }), resolved("local", ["C:/local/pi.exe"])),
      gives("opencode：本机文件", runtime(withLocal, "oc", { PATH: B2 }), resolved("local", ["C:/local/oc.exe"])),
      gives("pi：PATH", runtime(plain, "pi", { PATH: B2 }), resolved("path", [join(B2, "pi.EXE")])),
      gives("pi：PATH 上没有", runtime(plain, "pi", { PATH: EMPTY }), resolved("missing", null, (text) => text.includes("ERROR PATH 中找不到 pi"))),
      gives("claude-code：按程序名 claude 找", runtime(plain, "cc", { PATH: B4 }), resolved("path", [join(B4, "claude.CMD")])),
      gives("opencode：找不到", runtime(plain, "oc", { PATH: B4 }), resolved("missing", null)),
      gives("没有登记", runtime(plain, "ghost", { PATH: B2 }), resolved("missing", null, (text) => text.includes("ERROR runtime 'ghost' 没有登记"))),
      gives("像令牌的 runtime ID 不显示", runtime(plain, TOKEN, { PATH: B2 }), resolved("missing", null, (text) => text.includes("（值不显示）"))),
      gives("给了 adapter：没登记也照它解析", runtime(plain, "ghost", { PATH: B2 }, "pi"), resolved("path", [join(B2, "pi.EXE")])),
      gives("本机文件坏了：报 ERROR，再按 PATH 找", runtime(badLocal, "pi", { PATH: B2 }), resolved("path", [join(B2, "pi.EXE")], (text) => text.includes("ERROR .agent/dispatch.local.json 读不出来"))),
    ]);
  });
});

// --- resolve_role_executor 与 allowed_executor_check ----------------------------------------------

const RUNTIMES = { pi: { adapter: "pi" }, cc: { adapter: "claude-code" } };
const PROFILES = {
  exec: { runtime: "pi", model: { provider: "step", id: "step-5" }, options: { thinking: "medium" } },
  plain: { runtime: "pi", model: { provider: "step", id: "step-4" } },
  host: { runtime: "cc", model: { provider: "anthropic", id: "claude-x" } },
};
const roleOf = (role: unknown, config: Record<string, unknown>): ProbeRequest => call("resolve_role_executor", { role, config: JSON.stringify(config) });
const roleError = (fragment: string, code: number) => (value: PyValue): boolean =>
  field(value, "value") === null && String(field(field(value, "error"), "message")).includes(fragment) && field(field(value, "error"), "code") === BigInt(code);
const allowed = (allowlist: unknown, args: unknown[]): ProbeRequest => call("allowed_executor_check", { config: JSON.stringify({ allowed_executors: allowlist }), args: JSON.stringify(args) });

describe("resolve_role_executor 与 allowed_executor_check", () => {
  it("契约", () => {
    const base = { runtimes: RUNTIMES, profiles: PROFILES };
    verifyAll([
      gives("角色不对", roleOf("planner", base), roleError("executor.role 只能是 execution 或 contract：'planner'", 2)),
      gives("角色像令牌：不显示", roleOf(TOKEN, base), roleError("（值不显示）", 2)),
      gives("角色不是字符串", roleOf(3, base), roleError("（值不显示）", 2)),
      gives("配置无效：只报前三条", roleOf("execution", { ...base, roles: { execution: { mode: "x" } }, active_preset: 1 }), roleError("角色绑定的配置无效", 2)),
      gives("execution 没写", roleOf("execution", base), roleError("按角色写的合同需要 execution 角色的 headless 绑定", 2)),
      gives("contract 缺省是 manual", roleOf("contract", base), roleError("contract 角色是 manual", 2)),
      gives("适配器没接通这个角色", roleOf("contract", { ...base, roles: { contract: { mode: "headless", profile: "host" } } }), roleError("这个适配器本轮没有接通 contract，不派遣", 3)),
      gives(
        "合法：带当前方案",
        roleOf("execution", { ...base, roles: { execution: { mode: "headless", profile: "exec" } }, presets: { day: { roles: { execution: { mode: "headless", profile: "exec" } } } }, active_preset: "day" }),
        (value) => field(field(value, "value"), "thinking") === "medium" && field(field(value, "value"), "active_preset") === "day" && field(value, "error") === null,
      ),
      gives("合法：thinking 缺省 high", roleOf("contract", { ...base, roles: { contract: { mode: "headless", profile: "plain" } } }), (value) => field(field(value, "value"), "thinking") === "high"),
      gives("允许列表为空", allowed([], ["step", "step-5", "high"]), is(null)),
      gives("不在允许列表", allowed([{ provider: "step", model: "step-4" }], ["step", "step-5", "high"]), is(["missing", null])),
      gives("思考级别被固定成别的", allowed([{ provider: "step", model: "step-5", thinking: "low" }], ["step", "step-5", "high"]), is(["thinking", "low"])),
      gives("固定的级别相同", allowed([{ provider: "step", model: "step-5", thinking: "high" }], ["step", "step-5", "high"]), is(null)),
      gives("只看第一条匹配项", allowed([{ provider: "step", model: "step-5" }, { provider: "step", model: "step-5", thinking: "low" }], ["step", "step-5", "high"]), is(null)),
      gives("provider 为 None 与缺省的项相配", allowed([{ model: "m" }], [null, "m", null]), is(null)),
    ]);
  });
});

// --- load_binding_record --------------------------------------------------------------------------

const RECORD = {
  role: "execution",
  profile: "exec",
  runtime: "pi",
  adapter: "pi",
  provider: "step",
  model: "step-5",
  thinking: "high",
  contract_json_sha256: "a".repeat(64),
  created_at: "2026-10-26T00:00:00Z",
  created_by_attempt: "attempt-001",
  active_preset: null,
  config_sha256: null,
};
const record = (repo: string, version = 1): ProbeRequest => call("load_binding_record", { repo, task: "t1", version });

function recordRepo(name: string, content: string | Buffer | null): string {
  const repo = gitRepo(name);
  if (content !== null) put(join(repo, ".agent", "runs", "t1", "binding-v1.json"), content);
  return repo;
}

describe("load_binding_record", () => {
  it("不存在、合法、各种坏法、经过链接", () => {
    const { active_preset: _drop, ...withoutPreset } = RECORD;
    const directory = recordRepo("record-dir", null);
    mkdirSync(join(directory, ".agent", "runs", "t1", "binding-v1.json"), { recursive: true });
    const linked = recordRepo("record-link", null);
    const outside = join(ROOT, "outside-runs");
    put(join(outside, "t1", "binding-v1.json"), JSON.stringify(RECORD));
    symlinkSync(outside, join(linked, ".agent", "runs"), "junction");
    const rel = ".agent/runs/t1/binding-v1.json";
    verifyAll([
      gives("不存在", record(recordRepo("record-absent", null)), is(null)),
      gives("合法", record(recordRepo("record-ok", JSON.stringify(RECORD))), (value) => field(value, "model") === "step-5"),
      gives("另一个版本号不存在", record(recordRepo("record-v2", JSON.stringify(RECORD)), 2), is(null)),
      fails("解析不了", record(recordRepo("record-broken", "{")), `版本记录无效（${rel}）：JSONDecodeError`, 4),
      fails("不是 UTF-8", record(recordRepo("record-latin", Buffer.from([0xff]))), `版本记录无效（${rel}）：UnicodeDecodeError`, 4),
      fails("缺字段", record(recordRepo("record-missing", JSON.stringify({ ...RECORD, model: undefined }))), "字段不全或类型不对", 4),
      fails("字段类型不对", record(recordRepo("record-type", JSON.stringify({ ...RECORD, thinking: 1 }))), "字段不全或类型不对", 4),
      fails("active_preset 不能缺", record(recordRepo("record-preset", JSON.stringify(withoutPreset))), "字段不全或类型不对", 4),
      fails("顶层不是对象", record(recordRepo("record-list", "[]")), "字段不全或类型不对", 4),
      fails("有疑似凭据", record(recordRepo("record-secret", JSON.stringify({ ...RECORD, profile: TOKEN }))), "有疑似凭据（profile）", 4),
      fails("是目录", record(directory), `版本记录无效（${rel}）：PermissionError`, 4),
      fails("经过 junction", record(linked), "版本记录经过链接或 junction，不读取：.agent/runs", 4),
    ]);
  });
});
