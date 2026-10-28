// mutate 的整轮运行（迁移第 ④b5b 片）：--tree 原地与 attempt 的干净副本两种入口；变异轮次、判定、结果行与计数、决策点
// mutation-equivalence、命令的进程组收到 CTRL_BREAK。每个场景按三份实现各建一份相同的树（或仓库与 attempt），跑同一份清单，
// 比退出码、标准输出与标准错误、记录目录（mutations.json、各条日志、决策记录）、发给决策端点的请求与跑完之后树里的文件。
// 测试命令是真的子进程，一律 python -B：不写 .pyc（变异前后文件大小相同、修改时间落在同一秒时，旧的 .pyc 会被当成新的）。
// wall_seconds、pid、时间、延迟与路径换成占位符；崩溃只比退出码与树。不写转义序列。
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { BREAK_INNER, BREAK_OUTER, PYTHON, TS_CONTEXT, fullAttempt, state, type AttemptOptions } from "./attempt-fixtures.ts";
import { KEY_NAME, type Reply, startEndpoint } from "./endpoint-fixtures.ts";
import { pythonCliCommand, tsCliCommand } from "./harness.ts";
import { DIRECT_RUNNERS, LF, RUNNERS, type Runner, git, newRepo, normalize, put, removeCreated, runCommand, snapshotDir, tempDir } from "./repo-fixtures.ts";

const CR = String.fromCharCode(13);
const SEP = String.fromCharCode(92);
const savedKey = process.env[KEY_NAME];

beforeAll(() => {
  process.env[KEY_NAME] = "fake-key-for-contract";
});

afterAll(() => {
  if (savedKey === undefined) delete process.env[KEY_NAME];
  else process.env[KEY_NAME] = savedKey;
  removeCreated();
});

// ---------------------------------------------------------------------------
// 被变异的代码与测试
// ---------------------------------------------------------------------------

const LIB = [
  "def add(a, b):", "    return a + b", "", "",
  "def sign(x):", "    if x > 0:", "        return 1", "    if x < 0:", "        return -1", "    return 0", "", "",
  "def nothing():", "    return None  # twin", "", "",
  "def other():", "    return None  # twin", "", "",
  `# ${String.fromCodePoint(0x1f600)}`,
  "LIMIT = 10", "ABORT = False", "BANNER = False", "EXIT2 = False", "SLEEP = False", "REMOVE = False", "",
].join(LF);
// 横幅照 _session_aborted 的正则取最短的写法（三个叹号）；只有横幅、退出码不是 2 的不算会话中断
const CHECK = [
  "import shutil, sys, time",
  "import crlfmod, lib",
  "if lib.SLEEP:", "    time.sleep(30)",
  "if lib.ABORT:", "    print('!!! KeyboardInterrupt !!!')", "    sys.exit(2)",
  "if lib.BANNER:", "    print('!!! KeyboardInterrupt !!!')", "    sys.exit(1)",
  "if lib.EXIT2:", "    sys.exit(2)",
  "if lib.REMOVE:", "    shutil.rmtree('sub')",
  "assert lib.add(2, 3) == 5", "assert lib.sign(5) == 1", "assert lib.sign(-5) == -1", "assert lib.nothing() is None", "assert crlfmod.VALUE == 3",
  "print('ok', lib.LIMIT)", "",
].join(LF);
const CHECK_B = ["import lib", "assert lib.sign(0) == 0", "assert lib.add(1, 1) == 2", "print('b ok')", ""].join(LF);
const CRLF_MOD = ["A = 1", "VALUE = A + 2", ""].join(CR + LF);

function buildTree(): string {
  const tree = tempDir("mtree");
  put(tree, "lib.py", LIB);
  put(tree, "check.py", CHECK);
  put(tree, "check_b.py", CHECK_B);
  put(tree, "crlfmod.py", CRLF_MOD);
  put(tree, "bin.dat", new Uint8Array([0xff, 0xfe, 0x00, 0x41]));
  put(tree, "sub/keep.txt", "x");
  return tree;
}

/** 树里的全部文件：相对路径 → base64。 */
function treeFiles(root: string): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (dir: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const full = join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else out[relative(root, full).split(SEP).join("/")] = readFileSync(full).toString("base64");
    }
  };
  walk(root);
  return out;
}

const RUN = ["python", "-B", "check.py"];
const m = (name: string, file: string, old: string, replacement: string, extra: Record<string, unknown> = {}): Record<string, unknown> =>
  ({ name, file, old, new: replacement, ...extra });
const ADD = (name: string, extra: Record<string, unknown> = {}): Record<string, unknown> => m(name, "lib.py", "return a + b", "return a - b", extra);
const ZERO = (name: string, extra: Record<string, unknown> = {}): Record<string, unknown> => m(name, "lib.py", "    return 0", "    return 2", extra);
const LOW = String.fromCharCode(0xde00);
const HIGH = String.fromCharCode(0xd83d);

/** 单条命令、没有预期标注：各种结果都有一条。 */
const MIX = {
  command: RUN, timeout_seconds: 3,
  mutations: [
    ADD("M01 加法改减法"),
    ZERO("M02 零的符号"),
    m("M03 锚点对不上", "lib.py", "return a * b", "return a"),
    m("M04 文件不在", "nope.py", "x", "y"),
    m("M05 不是 UTF-8", "bin.dat", "A", "B"),
    m("M06 只插入代码", "lib.py", "LIMIT = 10", `LIMIT = 10${LF}UNUSED = 1`),
    m("M07 CRLF 的文件、LF 的 old", "crlfmod.py", `A = 1${LF}VALUE`, `A = 5${LF}VALUE`),
    m("M08 两处一起改", "lib.py", "return None  # twin", "return 1  # twin", { count: 2 }),
    m("M09 测试会话被中断", "lib.py", "ABORT = False", "ABORT = True"),
    m("M10 退出码 2、没有横幅", "lib.py", "EXIT2 = False", "EXIT2 = True"),
    m("M11 超时", "lib.py", "SLEEP = False", "SLEEP = True"),
    m("M12 old 与 new 里带 CRLF", "crlfmod.py", `A = 1${CR}${LF}VALUE`, `A = 6${CR}${LF}VALUE`),
    // 孤立的代理项只对得上补充平面字符的半边：按码点数是 0 次
    m("M13 孤立的低位代理", "lib.py", LOW, "x"),
    m("M14 孤立的高位代理", "lib.py", HIGH, "x"),
    m("M15 出现两次、期望一次", "lib.py", "return None  # twin", "return 2  # twin"),
    m("M16 有横幅、退出码 1", "lib.py", "BANNER = False", "BANNER = True"),
  ],
};

/** 单条命令，带预期标注：预期内、意外漏掉、标了预期漏掉却被抓住。 */
const LABELLED = {
  command: RUN,
  mutations: [
    m("E01 等价", "lib.py", "    return 0", "    return -0", { equivalent: "负零就是零" }),
    m("E02 预期漏掉", "lib.py", "LIMIT = 10", "LIMIT = 11", { expect_missed: ["main"] }),
    ADD("E03 标了等价却被抓住", { equivalent: "其实不等价" }),
    m("E04 意外漏掉", "lib.py", "    return 0", "    return 3"),
    m("E05 文件不在", "nope.py", "x", "y"),
  ],
};

/** 三条命令：c 在 sub 里跑，X04 让 a 删掉 sub，c 被拦下记出错。X01 在 a 上意外漏掉、在 c 上预期漏掉：决策的后缀只跟在 a 那行。 */
const MULTI = {
  commands: [
    { id: "a", argv: RUN },
    { id: "b", argv: ["python", "-B", "check_b.py"] },
    { id: "c", argv: ["python", "-B", "-c", "print('c ok')"], cwd: "sub" },
  ],
  mutations: [
    ZERO("X01 零的符号", { expect_missed: ["c"] }),
    ADD("X02 加法改减法"),
    m("X03 文件不在", "nope.py", "x", "y"),
    m("X04 删掉 sub", "lib.py", "REMOVE = False", "REMOVE = True", { expect_missed: ["a", "b"] }),
  ],
};

const ANSWER = (equivalent: number, untested: number): Reply => ({
  status: 200,
  body: JSON.stringify({
    answers: { equivalent: { type: "noul", noul: equivalent }, untested: { type: "noul", noul: untested } },
    usage: { input_tokens: 210, output_tokens: 7 }, model: "jev-test",
  }),
});
const FAILING: Reply = { status: 500, body: "{}" };
// D03 在 CRLF 的文件上、跨两行：决策的上下文要先把文件的 CRLF 换成 LF 才找得到 old
const DECIDE = { command: RUN, mutations: [ADD("D01 加法改减法"), ZERO("D02 零的符号"), m("D03 换个写法", "crlfmod.py", `A = 1${LF}VALUE = A + 2`, `A = 1${LF}VALUE = 2 + A`)] };

// ---------------------------------------------------------------------------
// 比较口径
// ---------------------------------------------------------------------------

function scrub(text: string): string {
  return text
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/"pid": [0-9]+/gu, '"pid": <PID>')
    .replace(/"latency_ms": [0-9]+/gu, '"latency_ms": <MS>')
    .replace(/-verify-[a-z0-9_]{8}/gu, "-verify-<RND>")
    .replace(/pi-mutate-tree-[a-z0-9_]{8}/gu, "pi-mutate-tree-<RND>");
}

const scrubAll = (record: Record<string, string>): Record<string, string> =>
  Object.fromEntries(Object.entries(record).map(([key, value]) => [scrub(key), scrub(value)]));

/** 崩溃时两边都要真崩：Python 打堆栈，TS 写“崩溃”那一行。 */
const crashed = (stderr: string): boolean => stderr.includes("Traceback (most recent call last)") || stderr.includes("崩溃（Python 在这里会打印堆栈）");

// ---------------------------------------------------------------------------
// --tree
// ---------------------------------------------------------------------------

interface TreeCase {
  readonly label: string;
  readonly spec: unknown;
  readonly status: number;
  readonly text?: string;
  /** given：--out 给一个新目录；inside：在树里；full：已有内容；file：是个文件；none：不给。 */
  readonly out?: "given" | "inside" | "full" | "file" | "none";
  /** dispatch.config.json：字符串原样写；缺省 kill_grace_seconds 为 1。 */
  readonly config?: unknown;
  /** 有就起假端点，配置里补 decisions（缺省 on 模式、只启用 mutation-equivalence）。 */
  readonly replies?: readonly Reply[];
  readonly decisions?: Record<string, unknown>;
  readonly crash?: boolean;
  readonly merged?: boolean;
  /** 跑完之后树与开始时逐字节相同（缺省要求相同）。 */
  readonly treeChanges?: boolean;
}

function outFor(kind: NonNullable<TreeCase["out"]>, tree: string): string | null {
  if (kind === "none") return null;
  if (kind === "inside") return join(tree, "rec");
  const dir = join(tempDir("mout"), "deep", "rec");
  if (kind === "full") put(dir, "old.txt", "x");
  if (kind === "file") put(dirname(dir), "rec", "x");
  return dir;
}

/** 不给 --out 时记录在系统临时目录下：从计数那一行（“ · ”之后）取出记录文件的路径。 */
function printedOut(stdout: string): string | null {
  const line = stdout.split(LF).find((text) => text.includes("pi-mutate-tree-") && text.includes(" · "));
  return line === undefined ? null : dirname(line.slice(line.lastIndexOf(" · ") + 3).trim());
}

async function runTreeCase(item: TreeCase): Promise<void> {
  const results = [];
  for (const runner of RUNNERS as readonly Runner[]) {
    const endpoint = item.replies ? await startEndpoint(item.replies) : null;
    let createdOut: string | null = null;
    try {
      const { repo } = newRepo(`mrun-${runner}`);
      const decisions = endpoint
        ? { decisions: { mode: "on", base_url: `http://127.0.0.1:${endpoint.port}`, api_key_env: KEY_NAME, points: ["mutation-equivalence"], ...item.decisions } }
        : {};
      const config = item.config ?? { kill_grace_seconds: 1, ...decisions };
      put(repo, ".agent/dispatch.config.json", typeof config === "string" ? config : JSON.stringify(config));
      const tree = buildTree();
      const initial = treeFiles(tree);
      const specDir = tempDir("mspec");
      const spec = join(specDir, "spec.json");
      put(specDir, "spec.json", JSON.stringify(item.spec, null, 2));
      const out = outFor(item.out ?? "given", tree);
      const argv = ["mutate", "--tree", tree, "--spec", spec, ...(out === null ? [] : ["--out", out])];
      const args = { command: ["mutate"], run_dir: null, spec, keep_workspace: false, tree, out, check_anchors: false, context: TS_CONTEXT };
      const result = runCommand(runner, repo, argv, args, repo, item.merged === true);
      const stdoutRaw = result.stdout.toString("utf8");
      const stderrRaw = result.stderr.toString("utf8");
      createdOut = out === null ? printedOut(stdoutRaw) : null;
      const recordDir = out ?? createdOut;
      const paths: Record<string, string> = { "<TREE>": tree, "<SPEC>": specDir, "<REPO>": repo, ...(recordDir ? { "<OUT>": recordDir } : {}) };
      const after = treeFiles(tree);
      const record = recordDir !== null && existsSync(recordDir) && statSync(recordDir).isDirectory() && !item.crash ? scrubAll(snapshotDir(recordDir, paths)) : {};
      results.push({
        status: result.status,
        stdout: item.crash ? "" : scrub(normalize(stdoutRaw, paths)),
        stderr: item.crash ? "" : scrub(normalize(stderrRaw, paths)),
        crashed: item.crash ? crashed(stderrRaw) : null,
        record,
        requests: endpoint ? scrub(JSON.stringify(endpoint.requests())) : "",
        tree: after,
        treeSame: JSON.stringify(after) === JSON.stringify(initial),
      });
    } finally {
      endpoint?.stop();
      if (createdOut !== null) rmSync(createdOut, { recursive: true, force: true });
    }
  }
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify({ ...first, tree: undefined })).toBe(item.status);
  if (item.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  expect(first.treeSame, "跑完之后树与开始时逐字节相同").toBe(!item.treeChanges);
  if (item.text) expect(first.stdout + first.stderr).toContain(item.text);
}

const TREE_CASES: TreeCase[] = [
  { label: "各种结果各一条：抓住、漏掉、跳过、出错、超时、只插入代码、CRLF、孤立代理项", spec: MIX, status: 0,
    text: "变异 16 个：抓住 7，漏掉 2，跳过 6，出错 1 · <OUT>" },
  { label: "各种结果：合并输出的次序", spec: MIX, status: 0, merged: true, text: "WARN  M06 M06 只插入代码：new 包含完整的 old" },
  { label: "带预期标注：预期内、意外漏掉、标了等价却被抓住", spec: LABELLED, status: 0,
    text: "变异 5 个：抓住 1，漏掉 3（预期 2，意外 1：M04），跳过 1，出错 0；标了预期漏掉却被抓住 1：M03" },
  { label: "三条命令：按命令记结果，删掉 sub 之后第三条被拦下", spec: MULTI, status: 0, treeChanges: true, text: "ERROR   M04 X04 删掉 sub [c]  cwd 不存在或位于工作副本之外" },
  { label: "基线失败", spec: { command: ["python", "-B", "-c", "import sys; print('boom'); sys.exit(1)"], mutations: [ADD("M01")] }, status: 3,
    text: "不做变异时 command 没有通过（退出码 1 ≠ 期望 0），变异结果没有意义；先让它在这棵树上通过 · 记录 <OUT>" },
  { label: "基线失败：合并输出的次序", spec: { command: ["python", "-B", "-c", "import sys; sys.exit(1)"], mutations: [m("M01", "lib.py", "LIMIT = 10", "LIMIT = 10 ")] },
    status: 3, merged: true },
  { label: "多条命令的基线：第二条失败，第三条不跑", spec: {
    commands: [{ id: "a", argv: RUN }, { id: "b", argv: ["python", "-B", "-c", "import sys; sys.exit(4)"] }, { id: "c", argv: RUN }], mutations: [ADD("M01")],
  }, status: 3, text: "不做变异时 command 没有通过（命令 b：退出码 4 ≠ 期望 0）" },
  { label: "命令改了被变异的文件：结束时提示没有恢复原样", spec: {
    commands: [{ id: "a", argv: RUN }, { id: "touch", argv: ["python", "-B", "-c", "open('lib.py', 'ab').write(b'# ran' + bytes([10]))"] }],
    mutations: [ADD("M01")],
  }, status: 0, treeChanges: true, text: "WARN  变异后文件没有恢复原样：lib.py" },
  { label: "new 里有孤立代理项：编码时崩，文件不动", spec: { command: RUN, mutations: [m("M01", "lib.py", "    return 0", `    return 0${HIGH}`)] }, status: 1, crash: true },
  { label: "--out 在树里", spec: MIX, status: 2, out: "inside", text: "--out 不能在被变异的树里面" },
  { label: "--out 已有内容", spec: MIX, status: 2, out: "full", text: "--out 目录已有内容" },
  { label: "--out 是个文件", spec: MIX, status: 1, out: "file", crash: true },
  { label: "不给 --out：记录在系统临时目录下", spec: DECIDE, status: 0, out: "none", text: "变异 3 个：抓住 1，漏掉 2，跳过 0，出错 0 · <OUT>" },
  { label: "配置写错照样跑（按没有配置）", spec: DECIDE, status: 0, config: "{", text: "变异 3 个：抓住 1，漏掉 2" },
  { label: "决策 on：可能等价", spec: DECIDE, status: 0, replies: [ANSWER(0.85, 0.1)], text: "MISSED  M02 D02 零的符号  日志 M02.log  决策：可能等价 p=0.85" },
  { label: "决策 on：可能是测试缺口", spec: DECIDE, status: 0, replies: [ANSWER(0.2, 0.8)], text: "决策：可能是测试缺口 p=0.80" },
  { label: "决策 on：都不到阈值", spec: DECIDE, status: 0, replies: [ANSWER(0.4, 0.5)], text: "决策：等价 p=0.40 · 缺口 p=0.50" },
  { label: "决策 on：恰好到阈值 0.7", spec: DECIDE, status: 0, replies: [ANSWER(0.7, 0.7)], text: "决策：可能等价 p=0.70" },
  { label: "决策 on：缺口恰好到阈值", spec: DECIDE, status: 0, replies: [ANSWER(0.69, 0.7)], text: "决策：可能是测试缺口 p=0.70" },
  { label: "决策 shadow：只记录不显示", spec: DECIDE, status: 0, replies: [ANSWER(0.85, 0.1)], decisions: { mode: "shadow" },
    text: "决策（mutation-equivalence, shadow）：2 次调用，2 次有答案 · 记录 <OUT>" },
  { label: "决策 on：端点回 500，无意见", spec: DECIDE, status: 0, replies: [FAILING], text: "决策（mutation-equivalence, on）：2 次调用，0 次有答案" },
  { label: "决策 on、带预期标注：只问意外漏掉的", spec: LABELLED, status: 0, replies: [ANSWER(0.85, 0.1)], text: "1 次调用，1 次有答案" },
  { label: "决策 on、三条命令：意外漏掉的那条问一次", spec: MULTI, status: 0, treeChanges: true, replies: [ANSWER(0.2, 0.9)], text: "决策：可能是测试缺口 p=0.90" },
  { label: "决策 off：不问也不打印", spec: DECIDE, status: 0, replies: [ANSWER(0.85, 0.1)], decisions: { mode: "off" }, text: "变异 3 个：抓住 1，漏掉 2" },
  { label: "决策配置写错是用法错误", spec: DECIDE, status: 2, replies: [ANSWER(0.85, 0.1)], decisions: { mode: "loud" }, text: "dispatch.config.json 的 decisions 无效" },
];

describe("mutate --tree", () => {
  for (const item of TREE_CASES) it(item.label, () => runTreeCase(item), 180_000);
});

// ---------------------------------------------------------------------------
// D2：变异跑到一半，命令的进程组收到 CTRL_BREAK
// ---------------------------------------------------------------------------

const SLEEPING = m("B02 睡着", "lib.py", "SLEEP = False", "SLEEP = True");

describe("D2：命令的进程组收到 CTRL_BREAK", () => {
  it("这条记出错，后面的不再运行，照常写记录", () => {
    const first = runBreak({ command: RUN, timeout_seconds: 120, mutations: [ADD("B01 加法改减法"), SLEEPING, ZERO("B03 零的符号")] });
    expect(first.stdout).toContain("MUTATE 被中断：后面 1 条变异没有运行");
    expect(first.stdout).toContain("变异清单 3 条，运行被中断，只跑了 2 条，下面的计数不完整；没有运行：B03 零的符号");
  }, 300_000);

  it("多条命令：中断的那条命令之后的命令也不再跑", () => {
    const first = runBreak({
      commands: [{ id: "a", argv: RUN, timeout_seconds: 120 }, { id: "b", argv: ["python", "-B", "check_b.py"] }],
      mutations: [ADD("B01 加法改减法"), SLEEPING, ZERO("B03 零的符号")],
    });
    expect(first.stdout).toContain("ERROR   M02 B02 睡着 [a]  命令被中断");
    expect(first.stdout).not.toContain("M02 B02 睡着 [b]");
  }, 300_000);
});

/** 读到 M01 的结果行、再等一秒，给 mutate 的进程组发 CTRL_BREAK（这时 M02 的命令睡着）。三边一致，交回 Python 的结果。 */
function runBreak(spec: unknown): { status: number; stdout: string } {
  const results = DIRECT_RUNNERS.map((runner) => {
    const { repo } = newRepo(`mbr-${runner}`);
    put(repo, ".agent/dispatch.config.json", JSON.stringify({ kill_grace_seconds: 1 }));
    const tree = buildTree();
    const initial = treeFiles(tree);
    const specDir = tempDir("mspec");
    const specPath = join(specDir, "spec.json");
    put(specDir, "spec.json", JSON.stringify(spec));
    const out = join(tempDir("mout"), "rec");
    const argv = ["mutate", "--tree", tree, "--spec", specPath, "--out", out];
    const args = { command: ["mutate"], run_dir: null, spec: specPath, keep_workspace: false, tree, out, check_anchors: false, context: TS_CONTEXT };
    const command = runner === "python" ? pythonCliCommand(["--repo", repo, ...argv]) : tsCliCommand(runner, { repo, ...args });
    const done = spawnSync(PYTHON, ["-c", BREAK_OUTER, BREAK_INNER, JSON.stringify(command), repo, "CAUGHT  M01"], { encoding: "utf8", timeout: 150_000 });
    if (done.status !== 0) throw new Error(`${runner} 中断用例的包装进程退出码 ${String(done.status)}：${done.stderr}`);
    const run = JSON.parse(done.stdout) as { status: number; stdout: string; stderr: string };
    const paths = { "<TREE>": tree, "<SPEC>": specDir, "<REPO>": repo, "<OUT>": out };
    return {
      status: run.status, stdout: scrub(normalize(run.stdout, paths)), stderr: scrub(normalize(run.stderr, paths)),
      record: scrubAll(snapshotDir(out, paths)), treeSame: JSON.stringify(treeFiles(tree)) === JSON.stringify(initial),
    };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify(first)).toBe(1);
  expect(first.treeSame).toBe(true);
  return first;
}

// ---------------------------------------------------------------------------
// attempt：干净副本
// ---------------------------------------------------------------------------

const ACHECK = ["import lib", "assert lib.add(2, 3) == 5", "print('ok')", ""].join(LF);
const ASPEC = { command: ["python", "-B", "acheck.py"], mutations: [ADD("A01 加法改减法"), ZERO("A02 零的符号")] };
const TOUCH = { id: "touch", argv: ["python", "-B", "-c", "open('src/a.ts', 'ab').write(b'//')"] };

interface AttemptCase {
  readonly label: string;
  readonly spec: unknown;
  readonly status: number;
  readonly text?: string;
  readonly attempt?: AttemptOptions;
  readonly keep?: boolean;
  readonly crash?: boolean;
}

function runAttemptCase(item: AttemptCase): void {
  const results = (RUNNERS as readonly Runner[]).map((runner) => {
    const { repo, head } = newRepo(`mat-${runner}`);
    const paths: Record<string, string> = {
      "<REPO>": repo, ...fullAttempt(repo, head, runner, { ...item.attempt, candidateFiles: { "lib.py": LIB, "acheck.py": ACHECK, ...item.attempt?.candidateFiles } }),
    };
    const specDir = tempDir("mspec");
    const spec = join(specDir, "spec.json");
    put(specDir, "spec.json", JSON.stringify(item.spec, null, 2));
    paths["<SPEC>"] = specDir;
    const argv = ["mutate", "t1", "--spec", spec, ...(item.keep ? ["--keep-workspace"] : [])];
    const args = { command: ["mutate"], run_dir: "t1", spec, keep_workspace: item.keep === true, tree: null, out: null, check_anchors: false, context: TS_CONTEXT };
    const result = runCommand(runner, repo, argv, args);
    const stderr = result.stderr.toString("utf8");
    const worktrees = git(repo, "worktree", "list", "--porcelain").split(LF).filter((line) => line.startsWith("worktree ")).length;
    return {
      status: result.status,
      stdout: item.crash ? "" : scrub(normalize(result.stdout.toString("utf8"), paths)),
      stderr: item.crash ? "" : scrub(normalize(stderr, paths)),
      crashed: item.crash ? crashed(stderr) : null,
      evidence: item.crash ? {} : scrubAll(snapshotDir(join(repo, ".agent", "runs"), paths)),
      worktrees,
    };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify(first)).toBe(item.status);
  if (item.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  if (item.text) expect(first.stdout + first.stderr).toContain(item.text);
}

const ATTEMPT_CASES: AttemptCase[] = [
  { label: "抓住一条、漏掉一条，干净副本用完移除", spec: ASPEC, status: 0, text: "变异 2 个：抓住 1，漏掉 1，跳过 0，出错 0 · .agent/runs/t1/attempt-001/mutations/01/mutations.json" },
  { label: "--keep-workspace 保留干净副本", spec: ASPEC, status: 0, keep: true, text: "MISSED  M02 A02 零的符号  日志 mutations/01/M02.log" },
  { label: "已集成的 attempt 也能做", spec: ASPEC, status: 0, attempt: { files: { "state.json": state("INTEGRATED") } } },
  { label: "状态不能做变异检查", spec: ASPEC, status: 3, attempt: { files: { "state.json": state("RUNNING") } }, text: "状态 RUNNING 不能做变异检查" },
  { label: "没有候选记录", spec: ASPEC, status: 3, attempt: { files: { "candidate.json": null } }, text: "候选补丁缺失、被改动或未通过往返校验，不能建立干净副本" },
  { label: "补丁被改", spec: ASPEC, status: 3, attempt: { after: ({ runDir }) => put(runDir, "candidate.patch", "x") }, text: "不能建立干净副本" },
  { label: "候选记录是列表", spec: ASPEC, status: 1, attempt: { files: { "candidate.json": [] } }, crash: true },
  { label: "planner-v2 的合同没有发布记录", spec: ASPEC, status: 3, attempt: { contract: { contract_family: "planner-v2" } }, text: "planner-v2 发布门禁拒绝变异检查" },
  { label: "清单无效：问题打到标准输出", spec: { command: [], mutations: [] }, status: 2, text: "ERROR command 必须是非空的字符串数组" },
  { label: "干净副本建不出来", spec: ASPEC, status: 3, attempt: { config: { worktree_root: "inside" } }, text: "无法建立干净副本：worktree_root 不能位于仓库内部" },
  { label: "基线失败：记录 aborted，副本照样移除", spec: { command: ["python", "-B", "-c", "import sys; sys.exit(3)"], mutations: [ADD("A01")] }, status: 3,
    text: "不做变异时 command 没有通过（退出码 3 ≠ 期望 0），变异结果没有意义；先让它在候选上通过" },
  { label: "第二次变异检查编号递增", spec: ASPEC, status: 0, attempt: { files: { "mutations/01/spec.json": "{}" } }, text: "mutations/02/mutations.json" },
  { label: "命令改了候选文件", spec: { commands: [{ id: "a", argv: ["python", "-B", "acheck.py"] }, TOUCH], mutations: [ADD("A01")] }, status: 0,
    text: "WARN  变异后候选文件没有恢复原样：src/a.ts（记录仍有效，干净副本已移除）" },
  { label: "命令改了候选文件，保留副本", spec: { commands: [{ id: "a", argv: ["python", "-B", "acheck.py"] }, TOUCH], mutations: [ADD("A01")] }, status: 0, keep: true,
    text: "（记录仍有效，干净副本已保留）" },
];

describe("mutate <run_dir>", () => {
  for (const item of ATTEMPT_CASES) it(item.label, () => runAttemptCase(item), 180_000);
});
