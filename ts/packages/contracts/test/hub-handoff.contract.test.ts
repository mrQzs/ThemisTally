// 第 ⑤j3 片：经真启动器的场景。启动器是 probes/hub_launcher.py 在独立进程里调的 kit_hub.main，选择文件指到场景自己的临时文件，被测 kit
// 的 kernel-impl.json 不动。hub 选 python 时由 Python 回答（对照）；选 ts 时转交给 TS，走 pi_dispatch.run_handoff，Job 带 BREAKAWAY_OK。
// 长命子进程（主任务 runner、owner-sweep）一律换成 probes/hub_child_stub.py 的副本，不起回合、不花钱；supervisor 带 --max-steps 0，变异体
// 就算起了真的 kit_hub.py，也是 0 步就退。桩只放在场景自己的临时目录里；收尾只结束桩自己记下的进程号，孤儿断言在那之前做。
// 只在 Windows 上跑（Job 与控制台）。被测 kit 的内核文件要已提交：hub 起 supervisor、起子进程之前都核对。不写转义序列。
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { closeSync, copyFileSync, existsSync, openSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { list2cmdline } from "@themis/base/supervise";
import { afterAll, describe, expect, it } from "vitest";
import { REPO } from "./harness.ts";
import { LF, git, newRepo, normalize, removeCreated, snapshotDir, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const PY = process.env["THEMIS_PYTHON"] ?? "python";
const PROBES = resolve(dirname(fileURLToPath(import.meta.url)), "..", "probes");
const LAUNCHER = join(PROBES, "hub_launcher.py");
const CR = String.fromCharCode(13);
const STATUS_CONTROL_C_EXIT = 0xc000013a;
const LAUNCHER_JOB = 0x2000 | 0x800; // pi_dispatch._WinJob(breakaway=True)
const OUTER_JOB = 0x400; // JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION：不许脱离，也不随句柄关闭结束进程
const BOX = [".agent", "mailbox"];
const SCRIPTS = join(REPO, "scripts");

/** GetShortPathNameW 给的 8.3 写法；拿不到（不是 Windows、卷上关了 8.3）时是空串。 */
function shortPath(path: string): string {
  const program = ["import ctypes, sys", "buffer = ctypes.create_unicode_buffer(32768)",
    "size = ctypes.windll.kernel32.GetShortPathNameW(sys.argv[1], buffer, 32768)", "sys.stdout.write(buffer.value if size else '')"].join(LF);
  const done = spawnSync(PY, ["-c", program, path], { encoding: "utf8" });
  return done.status === 0 ? done.stdout : "";
}

const SHORT_SCRIPTS = shortPath(realpathSync.native(SCRIPTS));
/** 信件编号：utc_compact、发信人的简称、六位十六进制。 */
const MSG = /[0-9]{8}T[0-9]{12}Z-[^-]+-[0-9a-f]{6}/gu;

type Impl = "python" | "ts";
const SELECTOR_DIR = tempDir("hub-selector");
const SELECTORS: Record<Impl, string> = { python: join(SELECTOR_DIR, "python.json"), ts: join(SELECTOR_DIR, "ts.json") };
for (const hub of ["python", "ts"] as const) {
  writeFileSync(SELECTORS[hub], JSON.stringify({ schema_version: 1, readonly: "ts", config: "ts", dispatcher: "ts", hub }));
}

/** hub_launcher.py 的配置（见那个文件的头注释）。 */
interface Launch {
  readonly argv: readonly string[];
  readonly scripts?: string;
  readonly context_out?: string;
  readonly popen_out?: string;
  readonly stub?: string;
  readonly outer_job?: number;
  readonly interrupt?: { readonly ready: string; readonly signals: readonly string[] };
  readonly console?: { readonly stdout: string; readonly stderr: string };
}

function configFile(impl: Impl, launch: Launch): string {
  const dir = tempDir("hub-launch");
  const path = join(dir, "config.json");
  writeFileSync(path, JSON.stringify({ scripts: SCRIPTS, selector: SELECTORS[impl], context_out: join(dir, "context.json"), ...launch }));
  return path;
}

interface Done {
  readonly status: number | null;
  readonly stdout: Buffer;
  readonly stderr: Buffer;
}

function launchSync(impl: Impl, launch: Launch, cwd: string, input?: Buffer): Done {
  const done = spawnSync(PY, [LAUNCHER, configFile(impl, launch)], { cwd, input: input ?? Buffer.alloc(0), timeout: 300_000 });
  if (done.error) throw done.error;
  return { status: done.status, stdout: done.stdout, stderr: done.stderr };
}

/** 一直跑的启动器：输出写进文件；detached 时没有控制台（DETACHED_PROCESS）。 */
function launchAsync(impl: Impl, launch: Launch, cwd: string, detached = false): { child: ChildProcess; exited: Promise<number | null> } {
  const dir = tempDir("hub-output");
  const out = openSync(join(dir, "stdout"), "w");
  const err = openSync(join(dir, "stderr"), "w");
  const child = spawn(PY, [LAUNCHER, configFile(impl, launch)], { cwd, stdio: ["ignore", out, err], detached, windowsHide: true });
  closeSync(out);
  closeSync(err);
  const exited = new Promise<number | null>((done) => child.on("exit", (code) => done(code)));
  return { child, exited };
}

/** 一个 hub 仓库：同一份内容、同一个提交号，先经 Python 回答的启动器 init，再依次跑 setup。 */
function hubRepo(prefix: string, setup: readonly (readonly string[])[] = []): string {
  const { repo } = newRepo(prefix, { "brief.md": `# 任务书${LF}`, "close.md": `站主接手：本地验收过${LF}` });
  for (const argv of [["init"], ...setup]) {
    const done = launchSync("python", { argv: ["--repo", repo, ...argv] }, repo);
    expect(done.status, `${argv.join(" ")}：${done.stderr.toString("utf8")}`).toBe(0);
  }
  return repo;
}

/**
 * letter.delivered 记的信件哈希：信里有信件编号与时间，两边各跑一遍本来就不同（信的全文另在信箱里逐字比）。hub_impl 本来就各写各的（第 ⑤ 步
 * 切换），换成占位；各边写的值另在命令表那条里断言。
 */
const shown = (text: string, repo: string): string => normalize(text, { "<REPO>": repo }).replace(MSG, "<MSG>")
  .replace(/"pid": [0-9]+/gu, '"pid": <PID>').replace(/"sha256": "[0-9a-f]{64}"/gu, '"sha256": "<SHA>"')
  .replace(/"hub_impl": "(python|ts)"/gu, '"hub_impl": "<IMPL>"');

/** 信箱里全部文件（文件名与内容里的信件编号、仓库路径、时间、进程号换成占位），按名字排。 */
function box(repo: string): [string, string][] {
  return Object.entries(snapshotDir(join(repo, ...BOX), { "<REPO>": repo }))
    .map(([rel, text]) => [rel.replace(MSG, "<MSG>"), shown(text, repo)] as [string, string])
    .sort(([a, x], [b, y]) => (a === b ? x.localeCompare(y) : a.localeCompare(b)));
}

function events(repo: string): Record<string, unknown>[] {
  const path = join(repo, ...BOX, "ledger", "events.jsonl");
  return existsSync(path) ? readFileSync(path, "utf8").split(LF).filter(Boolean).map((line) => JSON.parse(line) as Record<string, unknown>) : [];
}

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function waitFor(what: string, ready: () => boolean, seconds = 30): Promise<void> {
  const deadline = Date.now() + seconds * 1000;
  while (!ready()) {
    if (Date.now() > deadline) throw new Error(`${seconds} 秒内没等到：${what}`);
    await new Promise((done) => setTimeout(done, 100));
  }
}

/** 等启动器自己退出，最多 seconds 秒（hub 一直不退时照失败报，不挂到用例超时）。 */
async function exitWithin(exited: Promise<number | null>, seconds: number): Promise<number | null | "超时"> {
  let timer: NodeJS.Timeout | undefined;
  const late = new Promise<"超时">((done) => {
    timer = setTimeout(() => done("超时"), seconds * 1000);
  });
  try {
    return await Promise.race([exited, late]);
  } finally {
    clearTimeout(timer);
  }
}

interface StubRecord {
  readonly pid: number;
  readonly cmdline: string;
  readonly executable: string;
  readonly argv: string[];
  readonly job_flags: number;
  readonly window: boolean;
  readonly visible: boolean;
}

/** 场景自己的桩：复制进临时目录，记录与放行文件都在它旁边。 */
function stubDir(): { dir: string; stub: string; record: (role: string) => StubRecord | null; release: () => void } {
  const dir = tempDir("hub-stub");
  const stub = join(dir, "kit_hub_stub.py");
  copyFileSync(join(PROBES, "hub_child_stub.py"), stub);
  const record = (role: string): StubRecord | null => {
    const path = join(dir, `${role}.json`);
    return existsSync(path) ? (JSON.parse(readFileSync(path, "utf8")) as StubRecord) : null;
  };
  return { dir, stub, record, release: () => writeFileSync(join(dir, "release"), "") };
}

/** 收尾：放行，等桩自己退出；还在的只结束桩记下的进程号。 */
async function retire(stubs: ReturnType<typeof stubDir>, roles: readonly string[]): Promise<void> {
  stubs.release();
  const pids = roles.map((role) => stubs.record(role)?.pid).filter((pid): pid is number => pid !== undefined);
  try {
    await waitFor("桩退出", () => pids.every((pid) => !alive(pid)), 15);
  } finally {
    for (const pid of pids.filter(alive)) process.kill(pid);
  }
}

describe.runIf(process.platform === "win32")("第 ⑤j3 片：经真启动器转交（hub 选 python 与 ts 各跑一遍）", () => {
  it("命令表：16 条路径经真启动器各跑一遍，退出码、stdout、stderr 与信箱逐字相同；exclusive 的输出到调用方，孙进程的错误模式带 0x8003；管道送进来的字节照 UTF-8 解码、BOM 留成 U+FEFF（3883）", () => {
    const python = String(PY);
    const calls: { readonly argv: readonly string[]; readonly input?: Buffer }[] = [
      { argv: ["init"] },
      { argv: ["task", "new", "T001", "--slug", "s", "--title", "标题", "--brief", "brief.md", "--no-jev"] },
      { argv: ["task", "new", "T002", "--slug", "t", "--title", "二", "--brief", "brief.md", "--no-jev", "--after", "T001"] },
      { argv: ["status"] }, { argv: ["status", "--json"] }, { argv: ["metrics"] }, { argv: ["metrics", "--json"] },
      { argv: ["take", "--peek"] }, { argv: ["take"] },
      { argv: ["send", "T001", "--type", "回复"], input: Buffer.from(`环境已修好，恢复${CR}${LF}第二行`, "utf8") },
      { argv: ["send", "T009", "--type", "回复"], input: Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from("带 BOM 的回复", "utf8")]) },
      // 2000 字的上限照通用换行之后的字数算：四行各 499 字、CRLF 隔开，换成 LF 恰好 2000 字，照常投出（信里按 splitlines 分行，只有这里看得出 CR）
      { argv: ["send", "T009", "--type", "回复"], input: Buffer.from(Array.from({ length: 4 }, () => "长".repeat(499)).join(CR + LF), "utf8") },
      { argv: ["task", "rebase", "T001", "--reason", "挪基线"] },
      { argv: ["task", "after", "T001", "--on", "T002", "--reason", "依赖"] },
      { argv: ["task", "unstick", "T001", "5-exec", "--reason", "卡住"] },
      { argv: ["task", "budget", "T001", "--attempts", "3", "--reason", "追加"] },
      { argv: ["exec-recheck", "T001"] },
      { argv: ["task", "close", "T001", "--ref", "HEAD", "--file", "close.md"] },
      { argv: ["task", "cleanup", "T001"] },
      { argv: ["run", "--max-steps", "0", "--idle-exit", "0", "--poll", "0"] },
      { argv: ["owner-sweep"] },
      { argv: ["exclusive", "--", python, "-c", "import ctypes; print('x', ctypes.windll.kernel32.GetErrorMode() & 0x8003)"] },
    ];
    const runAll = (impl: Impl) => {
      const { repo } = newRepo(`hub-cmd-${impl}`, { "brief.md": `# 任务书${LF}`, "close.md": `站主接手：本地验收过${LF}` });
      const results = calls.map((call) => {
        const done = launchSync(impl, { argv: ["--repo", repo, ...call.argv] }, repo, call.input);
        return { argv: call.argv.join(" "), status: done.status, stdout: shown(done.stdout.toString("utf8"), repo), stderr: shown(done.stderr.toString("utf8"), repo) };
      });
      const impls = events(repo).filter((event) => ["runner.started", "exclusive.run"].includes(String(event["event"]))).map((event) => [event["event"], event["hub_impl"]]);
      return { results, box: box(repo), impls };
    };
    const reference = runAll("python");
    const handed = runAll("ts");
    for (const [index, result] of handed.results.entries()) expect(result).toEqual(reference.results[index]);
    expect(handed.box).toEqual(reference.box);
    // 第 ⑤ 步切换（一）：经真启动器、不经探针，各边写自己的 hub_impl（run 那一次的 runner.started、exclusive 那一次的 exclusive.run）
    expect([reference.impls, handed.impls]).toEqual([
      [["runner.started", "python"], ["exclusive.run", "python"]], [["runner.started", "ts"], ["exclusive.run", "ts"]],
    ]);
    expect(handed.results.filter((result) => result.argv.startsWith("send ")).map((result) => result.status)).toEqual([0, 0, 0]);
    expect(handed.results.at(-1)?.stdout).toBe(`x 32771${CR}${LF}`); // 孙进程是 Python，文本模式的 print 在 Windows 上写 CRLF
    const texts = handed.box.map(([, text]) => text).join(LF);
    expect(texts).toContain(`摘要: ${String.fromCharCode(0xfeff)}带 BOM 的回复`);
  }, 600_000);

  it("DispatchError 一路抛到 kit_hub.main（find_repo 的三种报错：--repo 是文件、不在 Git 仓库里、是 worktree）：两边都写“ERROR: ”加消息、退出 2（抽查 V10）", () => {
    const { repo } = newRepo("hub-repo-errors");
    const plain = tempDir("hub-not-git");
    const worktree = join(tempDir("hub-worktree-root"), "wt");
    git(repo, "worktree", "add", "-q", "--detach", worktree);
    const file = join(plain, "a.txt");
    writeFileSync(file, "x");
    const paths = { "<REPO>": repo, "<PLAIN>": plain, "<WT>": worktree };
    const run = (impl: Impl) => [file, plain, worktree].map((where) => {
      const done = launchSync(impl, { argv: ["--repo", where, "status"] }, plain);
      return { status: done.status, stdout: normalize(done.stdout.toString("utf8"), paths), stderr: normalize(done.stderr.toString("utf8"), paths) };
    });
    const reference = run("python");
    expect(reference.map((result) => [result.status, result.stdout, result.stderr.startsWith("ERROR: ")])).toEqual([[2, "", true], [2, "", true], [2, "", true]]);
    expect(run("ts")).toEqual(reference);
  }, 300_000);

  const noShortNames = SHORT_SCRIPTS === "" || SHORT_SCRIPTS === realpathSync.native(SCRIPTS);

  it.skipIf(noShortNames)(
    "交给 TS 的 context.kit_hub 照 Python 的写法原样、不 resolve：经 8.3 短写法起启动器（hub 选 ts 的 status，不看内核文件干不干净），逐字是短写法加 kit_hub.py（抽查 V02；卷上关了 8.3 短名时跳过）",
    () => {
      const repo = hubRepo("hub-short-ts");
      const contextOut = join(tempDir("hub-short-out"), "context.json");
      const done = launchSync("ts", { argv: ["--repo", repo, "status"], scripts: SHORT_SCRIPTS, context_out: contextOut }, repo);
      expect(done.status, done.stderr.toString("utf8")).toBe(0);
      expect((JSON.parse(readFileSync(contextOut, "utf8")) as { kit_hub: string }).kit_hub).toBe(join(SHORT_SCRIPTS, "kit_hub.py"));
    }, 300_000);

  it.skipIf(noShortNames)(
    "对照：Python 的 hub 经 8.3 短写法起时，起 owner-sweep 的命令行第二项就是短写法（str(Path(__file__)) 不 resolve；要内核文件干净才起；卷上关了 8.3 短名时跳过）",
    async () => {
      const repo = hubRepo("hub-short-python", [["exclusive", "--", "git", "commit", "-q", "--allow-empty", "-m", "moved"]]);
      const stubs = stubDir();
      const popenOut = join(tempDir("hub-short-out"), "popen.jsonl");
      const { child, exited } = launchAsync("python", {
        argv: ["--repo", repo, "run", "--parallel", "2", "--max-steps", "0", "--poll", "0.2", "--idle-exit", "1"], scripts: SHORT_SCRIPTS, stub: stubs.stub,
        popen_out: popenOut,
      }, repo);
      try {
        expect(await exitWithin(exited, 30)).toBe(0);
        expect(stubs.record("owner-sweep")).not.toBeNull();
        const argv = readFileSync(popenOut, "utf8").split(LF).filter(Boolean).map((line) => JSON.parse(line) as string[]);
        expect(argv.map((item) => item[1])).toEqual([join(SHORT_SCRIPTS, "kit_hub.py")]);
      } finally {
        child.kill();
        await retire(stubs, ["owner-sweep"]);
      }
    }, 300_000);

  it("长命子进程脱离启动器的 Job：杀掉启动器之后 TS 随 Job 结束，主任务 runner 与 owner-sweep 照常活着；两边起它们的整条命令行逐字相同", async () => {
    const shownRecord = (record: StubRecord | null, stub: string, repo: string) => ({
      cmdline: shown(record?.cmdline.replaceAll(stub, "<STUB>") ?? "", repo), executable: record?.executable,
    });
    const run = async (impl: Impl) => {
      // T001 有信（主任务 runner 有事可做）；exclusive 动过 HEAD，owner-sweep 待跑
      const repo = hubRepo(`hub-break-${impl}`, [
        ["task", "new", "T001", "--slug", "s", "--title", "标题", "--brief", "brief.md", "--no-jev"],
        ["exclusive", "--", "git", "commit", "-q", "--allow-empty", "-m", "moved"],
      ]);
      const stubs = stubDir();
      const roles = ["task-T001", "owner-sweep"];
      const { child, exited } = launchAsync(impl, {
        argv: ["--repo", repo, "run", "--parallel", "2", "--max-steps", "0", "--poll", "0.2", "--idle-exit", "1"], stub: stubs.stub,
      }, repo);
      try {
        await waitFor("两个桩都起来", () => roles.every((role) => stubs.record(role) !== null));
        const hubPid = Number(events(repo).filter((event) => event["event"] === "runner.started").at(-1)?.["pid"]);
        child.kill(); // TerminateProcess：启动器的 Job 句柄随之关闭
        await exited;
        await waitFor("hub 进程结束", () => !alive(hubPid), 15);
        const records = roles.map((role) => stubs.record(role) as StubRecord);
        expect(records.map((record) => alive(record.pid)), impl).toEqual([true, true]);
        if (impl === "ts") for (const record of records) expect(record.job_flags, record.argv.join(" ")).not.toBe(LAUNCHER_JOB);
        return roles.map((role) => shownRecord(stubs.record(role), stubs.stub, repo));
      } finally {
        child.kill();
        await retire(stubs, roles);
      }
    };
    const reference = await run("python");
    const handed = await run("ts");
    expect(handed).toEqual(reference);
    // 主任务 runner 的命令行：float 的参数照 Python 的 str(float) 写（TASK_RUNNER_IDLE_SECONDS 是 60.0）
    expect(handed[0]?.cmdline).toBe(list2cmdline([String(reference[0]?.executable), "<STUB>", "--repo", "<REPO>", "run", "--task", "T001", "--max-steps", "0",
      "--idle-exit", "60.0", "--poll", "0.2", "--settle", "120.0"]));
  }, 600_000);

  it("从别的工具不许脱离的 Job 里起 hub（嵌套）：带 CREATE_BREAKAWAY_FROM_JOB 照常起来、不报 5，owner-sweep 留在外层 Job 里；启动器没有控制台时桩没有可见的窗口", async () => {
    for (const [label, launch, detached] of [["嵌套", { outer_job: OUTER_JOB }, false], ["没有控制台", {}, true]] as const) {
      const repo = hubRepo(`hub-outer-${label === "嵌套" ? "nested" : "detached"}`, [["exclusive", "--", "git", "commit", "-q", "--allow-empty", "-m", "moved"]]);
      const stubs = stubDir();
      // 没有主任务：supervisor 起了 owner-sweep，空闲 1 秒就照常退出，启动器跟着退出
      const { child, exited } = launchAsync("ts", {
        argv: ["--repo", repo, "run", "--parallel", "2", "--max-steps", "0", "--poll", "0.2", "--idle-exit", "1"], stub: stubs.stub, ...launch,
      }, repo, detached);
      try {
        expect(await exitWithin(exited, 30), label).toBe(0);
        const record = stubs.record("owner-sweep");
        expect(record === null ? null : [alive(record.pid), record.visible], label).toEqual([true, false]);
        if (label === "嵌套") expect(record?.job_flags).toBe(OUTER_JOB);
      } finally {
        child.kill();
        await retire(stubs, ["owner-sweep"]);
      }
    }
  }, 600_000);

  it("Ctrl+C（启动器在自己的隐藏控制台里收到 SIGINT）：两边都以 KeyboardInterrupt 结束；之后 run 拿得到锁、exclusive 不被挡（恢复）", async () => {
    const run = (impl: Impl) => {
      const repo = hubRepo(`hub-ctrlc-${impl}`);
      const dir = tempDir("hub-ctrlc-out");
      const ready = join(repo, ...BOX, ".runner", "owner.json");
      const done = launchSync(impl, {
        argv: ["--repo", repo, "run", "--max-steps", "5", "--idle-exit", "3600", "--poll", "0.2"],
        interrupt: { ready, signals: ["SIGINT"] }, console: { stdout: join(dir, "stdout"), stderr: join(dir, "stderr") },
      }, repo);
      const stderr = readFileSync(join(dir, "stderr"), "utf8").trimEnd().split(LF);
      const leftover = existsSync(join(repo, ...BOX, ".runner"));
      const status = launchSync(impl, { argv: ["--repo", repo, "status"] }, repo).stdout.toString("utf8").split(LF).map((line) => line.split(CR).join(""))
        .filter((line) => line.startsWith("运行中的 hub") || line.startsWith("并行"));
      const again = launchSync(impl, { argv: ["--repo", repo, "run", "--max-steps", "0", "--idle-exit", "0", "--poll", "0"] }, repo);
      const exclusive = launchSync(impl, { argv: ["--repo", repo, "exclusive", "--wait", "5", "--", "git", "status", "--short"] }, repo);
      return { status: done.status === null ? null : done.status >>> 0, last: stderr.at(-1)?.trim(), leftover, shown: status.map((line) => shown(line, repo)), again: again.status, exclusive: exclusive.status };
    };
    const reference = run("python");
    const handed = run("ts");
    expect(reference).toEqual({ status: STATUS_CONTROL_C_EXIT, last: "KeyboardInterrupt", leftover: false,
      shown: ["运行中的 hub：无", "并行：最多 1 个主任务；在跑的主任务 runner：无；在跑的执行端：无"], again: 0, exclusive: 0 });
    // 不同只在 .runner（计划第 10 节）：Bun 按缺省处理 CTRL_BREAK 时不走 finally，锁目录留下。status 照 Python 的写法原样打出锁目录里的
    // owner.json（持有者已死）；在跑的主任务 runner、执行端照 lock_alive 判断，照样是“无”；下一次 run 照 pid 接管，exclusive 不被挡
    expect([handed.leftover, handed.shown[0]?.startsWith("运行中的 hub：{")]).toEqual([true, true]);
    expect({ ...handed, leftover: false, shown: handed.shown.slice(1) }).toEqual({ ...reference, shown: reference.shown.slice(1) });
  }, 600_000);

  it("Ctrl+C 的连锁（只有 TS）：supervisor 的进程组收到转发的 CTRL_BREAK，同组的主任务 runner 与 owner-sweep 也收到，各自结束，不留孤儿", async () => {
    const repo = hubRepo("hub-cascade", [
      ["task", "new", "T001", "--slug", "s", "--title", "标题", "--brief", "brief.md", "--no-jev"],
      ["exclusive", "--", "git", "commit", "-q", "--allow-empty", "-m", "moved"],
    ]);
    const stubs = stubDir();
    const roles = ["task-T001", "owner-sweep"];
    const dir = tempDir("hub-cascade-out");
    try {
      const done = launchSync("ts", {
        argv: ["--repo", repo, "run", "--parallel", "2", "--max-steps", "0", "--poll", "0.2", "--idle-exit", "3600"], stub: stubs.stub,
        interrupt: { ready: join(stubs.dir, "owner-sweep.json"), signals: ["SIGINT"] }, console: { stdout: join(dir, "stdout"), stderr: join(dir, "stderr") },
      }, repo);
      expect((done.status ?? 0) >>> 0).toBe(STATUS_CONTROL_C_EXIT);
      // 启动器在 TS 结束后马上退出，桩每 0.1 秒才醒一次处理信号：等它们各自写下 .break、退出，不当场看
      await waitFor("两个桩都收到 CTRL_BREAK 并退出", () => roles.every((role) =>
        existsSync(join(stubs.dir, `${role}.break`)) && !alive((stubs.record(role) as StubRecord).pid)), 15);
    } finally {
      await retire(stubs, roles);
    }
  }, 600_000);
});
