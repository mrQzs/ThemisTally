// 进程监督（pi_dispatch.run_supervised 与 @themis/base/supervise）的契约与 ④a 的验证用例（迁移计划第 8.2 节）。
// 三套实现跑同一组场景：Python、TS 在 Bun 下（进程内 FFI）、TS 在 Node 下（经 Bun 辅助进程）。结果逐字段比较，
// 只有 pid（各次不同）与 wall_seconds（量出来的时间）按范围比。子进程一律是 Python 小程序，分小段睡：Windows 上
// Python 的 time.sleep 只被 SIGINT 提前唤醒，SIGBREAK 的处理器要等它醒来才运行。
//   S1 退出码、stdout 与 stderr 逐字节；S2 参数的引号（list2cmdline）；S3 环境块（排序、大小写不同的同名变量、
//   =C: 这类隐藏变量、各种非法键与值）；S4 启动失败的报错文字；S5 超时：调用方没有控制台时 CTRL_BREAK 发不出去、
//   不等宽限，有控制台（不显示窗口）时子进程真的收到、没等满宽限就退出，子进程不理会时等满宽限；S6 子进程退出后
//   留下的孙进程算残留并被结束；S7 .cmd 照样能跑（npm 这种经 which 解析出的 .CMD 实跑一次）；S8 杀掉调用方，整棵树
//   跟着结束。POSIX 的进程组没有实机验证，这些用例只在 Windows 上跑。
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { pidAlive } from "@themis/base/process";
import { secretKey } from "@themis/base/secrets";
import { IMPLS, type Impl, type ProbeRequest, type ProbeResult, removeDir, runBatch, runProbe, scratchDir } from "./harness.ts";

const PY = process.env["THEMIS_PYTHON"] ?? "python";
const PYTHON_IMPL = IMPLS[0] as Impl;
const DETACHED_PROCESS = 0x00000008;
const CREATE_NO_WINDOW = 0x08000000;
const onWindows = process.platform === "win32";

// 键名像凭据的变量（api key、token、secret、password，决策 key TYPESAFE_API_KEY 也在内）不交给子进程：用例用不到。
// 请求一律经 stdin 交，不进任何进程的命令行（同用户的进程都读得到命令行；S10 以前把整份请求连环境放在 argv 里）
const BASE_ENV = Object.entries(process.env).filter(
  (pair): pair is [string, string] => typeof pair[1] === "string" && !secretKey(pair[0]),
);

interface Supervised {
  exit_code: number | null;
  timed_out: boolean;
  interrupted: boolean;
  spawn_error: string | null;
  wall_seconds: number;
  stray_processes: boolean | null;
  kill_method: string | null;
  pid: number | null;
  ctrl_break: string | null;
  ctrl_break_winerror: number | null;
}

function request(dir: string, tag: string, cmd: string[], extra: Record<string, unknown> = {}): ProbeRequest {
  return {
    op: "supervise.run", cmd, cwd: dir, env: BASE_ENV, timeout: 30, grace: 15,
    stdout: { path: join(dir, `${tag}.out`), how: "create-new" }, stderr: { path: join(dir, `${tag}.err`), how: "create-new" },
    ...extra,
  };
}

/** 探针经一个 Python 包装器以指定的创建标志起（控制调用方有没有控制台）。 */
function runProbeWithFlags(impl: Impl, req: ProbeRequest, flags: number): ProbeResult {
  const wrapper = [
    "import json, subprocess, sys",
    "argv = json.loads(sys.argv[1])",
    "done = subprocess.run(argv, input=sys.stdin.buffer.read(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=int(sys.argv[2]))",
    "sys.stdout.buffer.write(done.stdout)",
    "sys.exit(done.returncode)",
  ].join("\n");
  const done = spawnSync(PY, ["-c", wrapper, JSON.stringify(impl.argv), String(flags)], {
    input: JSON.stringify(req), encoding: "utf8", timeout: 120_000,
  });
  if (done.status !== 0) throw new Error(`${impl.name} 探针（标志 ${flags}）退出码 ${done.status}：${done.stderr}`);
  return JSON.parse(done.stdout) as ProbeResult;
}

function supervised(result: ProbeResult): Supervised {
  expect(result.ok, JSON.stringify(result)).toBe(true);
  return result["result"] as Supervised;
}

/** 比较用：pid 只看有没有，wall_seconds 去掉（各自按范围断言）。 */
function comparable(result: Supervised): Record<string, unknown> {
  const { pid, wall_seconds: _wall, ...rest } = result;
  return { ...rest, pid: pid === null ? null : "<pid>" };
}

/** 等进程消失：消失了返回 true，等满 30 秒还在返回诊断（断言失败时打印出来）。
 *  第 109 轮：S5a 在 V10（全量连跑三遍）里两次等不到孙进程消失（26 次里红 2 次），T017 的结项因此撤回一次。以前每轮
 *  起一个 python 睡 0.1 秒、数满 100 轮：机器忙时又慢、又让进程号周转更快；pidAlive 为 null（tasklist 没跑出结果）
 *  也算“还在”。现在按墙钟算，同步睡不起进程，null 当“不知道”接着等。还等不到，就查清这个进程号此刻是谁：
 *  命令行是孙进程那段 range(1200)，就是真没被结束（supervise 的缺陷）；是别的进程，就是进程号被复用了。 */
function waitGone(pid: number): true | string {
  const deadline = Date.now() + 30_000;
  const nap = new Int32Array(new SharedArrayBuffer(4));
  let last: boolean | null = null;
  while (Date.now() < deadline) {
    last = pidAlive(pid);
    if (last === false) return true;
    Atomics.wait(nap, 0, 0, 100);
  }
  return goneDiagnosis(pid, last);
}

function goneDiagnosis(pid: number, last: boolean | null): string {
  const tasklist = spawnSync(join(process.env["SystemRoot"] ?? "C:/Windows", "System32", "tasklist.exe"),
    ["/FI", `PID eq ${pid}`, "/NH"], { encoding: "utf8", timeout: 20_000 });
  const query = `Get-CimInstance Win32_Process -Filter "ProcessId=${pid}" | Format-List Name,ProcessId,ParentProcessId,`
    + "CreationDate,CommandLine | Out-String -Width 400";
  // 按绝对路径起（第 77 轮的规矩：当前目录里的同名程序顶替不了）
  const powershell = join(process.env["SystemRoot"] ?? "C:/Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
  const cim = spawnSync(powershell, ["-NoProfile", "-NonInteractive", "-Command", query], { encoding: "utf8", timeout: 60_000 });
  return `进程 ${pid} 30 秒内没有消失。最后一次 pidAlive：${String(last)}；tasklist：${(tasklist.stdout ?? "").trim()}；`
    + `Get-CimInstance：${(cim.stdout ?? "").trim() || `（没查到；${String(cim.error ?? cim.stderr)}）`}`;
}

/** 每套实现在自己的临时目录里跑同一个场景，返回各自的结果与目录。 */
function acrossImpls<T>(name: string, body: (impl: Impl, dir: string) => T): { impl: Impl; dir: string; value: T }[] {
  return IMPLS.map((impl) => {
    const dir = scratchDir(`sup-${name}-${impl.name}`);
    return { impl, dir, value: body(impl, dir) };
  });
}

/** 收拾现场：删不掉只记一笔，不往外抛。清理不是断言（第 109 轮，themistally-15 指出）：孙进程真没被结束时，
 *  它的当前目录就是 run.dir，Windows 删不掉，finally 里抛出的 EBUSY 会顶掉断言里 waitGone 的诊断。 */
function tidy(path: string): void {
  try {
    removeDir(path);
  } catch (error) {
    console.warn(`清理 ${path} 没成功：${String(error)}`);
  }
}

function cleanup(runs: readonly { dir: string }[]): void {
  for (const run of runs) tidy(run.dir);
}

const SLEEP = "import time\nfor _ in range(1200): time.sleep(0.1)";

describe.skipIf(!onWindows)("进程监督契约", () => {
  it("S1 退出码、stdout 与 stderr 逐字节", () => {
    const child = "import sys\nsys.stdout.buffer.write(b'out\\r\\nline\\n\\xff')\nsys.stderr.buffer.write(b'err\\x00\\n')\nsys.exit(7)";
    const runs = acrossImpls("s1", (impl, dir) => supervised(runProbe(impl, request(dir, "s1", [PY, "-c", child]))));
    try {
      for (const run of runs) {
        expect(comparable(run.value), run.impl.name).toEqual(comparable((runs[0] as typeof run).value));
        expect(run.value.exit_code).toBe(7);
        expect(run.value.stray_processes).toBe(false);
        expect(readFileSync(join(run.dir, "s1.out"))).toEqual(Buffer.from("out\r\nline\n\xff", "latin1"));
        expect(readFileSync(join(run.dir, "s1.err"))).toEqual(Buffer.from("err\0\n", "latin1"));
      }
    } finally {
      cleanup(runs);
    }
  });

  it("S2 参数的引号照 list2cmdline，子进程看到的 argv 一样", () => {
    const args = ["a b", 'q"x', "c:\\d\\", "", "tab\there", 'back\\\\"quote', "中文 文字", "\\\\server\\share\\", "trail\\"];
    const child = "import json, sys\nsys.stdout.write(json.dumps(sys.argv[1:]))";
    const runs = acrossImpls("s2", (impl, dir) => supervised(runProbe(impl, request(dir, "s2", [PY, "-c", child, ...args]))));
    try {
      for (const run of runs) {
        expect(run.value.exit_code, run.impl.name).toBe(0);
        expect(JSON.parse(readFileSync(join(run.dir, "s2.out"), "utf8")), run.impl.name).toEqual(args);
      }
    } finally {
      cleanup(runs);
    }
  });

  it("S3 环境块：排序、大小写不同的同名变量、=C:、空值、Unicode 与 Python 一样", () => {
    // 子进程打印 GetEnvironmentStringsW 原样的环境块（顺序与大小写都看得见）
    const child = [
      "import ctypes, json",
      "k = ctypes.windll.kernel32",
      "k.GetEnvironmentStringsW.restype = ctypes.c_void_p",
      "p = k.GetEnvironmentStringsW()",
      "out, offset = [], 0",
      "while True:",
      "    s = ctypes.wstring_at(p + offset * 2)",
      "    if not s: break",
      "    out.append(s)",
      "    offset += len(s) + 1",
      "print(json.dumps(out))", // 只给了几个变量时 stdout 退回 cp1252，非 ASCII 要转义
    ].join("\n");
    const env: [string, string][] = [
      ["SYSTEMROOT", process.env["SYSTEMROOT"] ?? "C:\\Windows"], ["b", "2"], ["A", "1"], ["a_", "3"], ["Z", "4"], ["_x", "5"],
      ["path", "lower"], ["PATH", "upper"], ["Path", "middle"], ["=C:", "C:\\x"], ["EMPTY", ""], ["é", "x"], ["中", "文"],
      ["dup", "first"], ["DUP", "second"], ["dup", "third"],
    ];
    const runs = acrossImpls("s3", (impl, dir) => supervised(runProbe(impl, request(dir, "s3", [PY, "-c", child], { env }))));
    try {
      const python = readFileSync(join((runs[0] as (typeof runs)[number]).dir, "s3.out"), "utf8");
      expect(JSON.parse(python)).toContain("Path=middle"); // 大小写不同的同名变量留最后插入的那一个
      for (const run of runs) expect(readFileSync(join(run.dir, "s3.out"), "utf8"), run.impl.name).toBe(python);
    } finally {
      cleanup(runs);
    }
  });

  it.each([
    ["键里含 NUL", [["A\0B", "1"]]],
    ["值里含 NUL", [["AB", "1\0"]]],
    ["键里（第 1 个字符之后）含 =", [["A=B", "1"]]],
    ["被去掉的同名变量里含 NUL 不报错", [["PATH", "x\0"], ["path", "y"]]],
    ["留下的同名变量里含 NUL 报错", [["path", "y"], ["PATH", "x\0"]]],
    ["两个错误时报排在前面的那个", [["B", "\0"], ["A=", "1"]]],
  ] as const)("S3b 环境块的报错：%s", (_name, extra) => {
    const runs = acrossImpls("s3b", (impl, dir) =>
      runProbe(impl, request(dir, "s3b", [PY, "-c", "pass"], { env: [...BASE_ENV, ...extra] })));
    try {
      const python = (runs[0] as (typeof runs)[number]).value;
      for (const run of runs) {
        if (python.ok) expect(comparable(supervised(run.value)), run.impl.name).toEqual(comparable(supervised(python)));
        else expect(run.value, run.impl.name).toEqual(python);
      }
    } finally {
      cleanup(runs);
    }
  });

  it.each([
    ["找不到程序", ["no-such-program-xyz.exe"], {}],
    ["工作目录不存在", [PY, "-c", "pass"], { cwd: "C:\\no\\such\\dir\\for\\themis" }],
    ["不是可执行文件", [join(process.env["SYSTEMROOT"] ?? "C:\\Windows", "win.ini")], {}],
    ["环境变量的键是空串", [PY, "-c", "pass"], { env: [...BASE_ENV, ["", "1"]] }],
  ] as const)("S4 启动失败：%s，报错文字与 Python 一样", (_name, cmd, extra) => {
    const runs = acrossImpls("s4", (impl, dir) => supervised(runProbe(impl, request(dir, "s4", [...cmd], extra))));
    try {
      const python = (runs[0] as (typeof runs)[number]).value;
      expect(python.spawn_error).toMatch(/^\w+Error: \[WinError \d+\] /u);
      for (const run of runs) expect(comparable(run.value), run.impl.name).toEqual(comparable(python));
    } finally {
      cleanup(runs);
    }
  });

  it("S5a 调用方没有控制台：CTRL_BREAK 发不出去（错误码 6），不等宽限，整棵树都结束", () => {
    const child = [
      "import pathlib, subprocess, sys, time",
      "g = subprocess.Popen([sys.executable, '-c', 'import time\\nfor _ in range(1200): time.sleep(0.1)'], creationflags=0x8,",
      "                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
      "pathlib.Path('grandchild.pid').write_text(str(g.pid))",
      // 第 128 轮：监督进程没有控制台时，子进程的控制台开在后台（没有窗口），不在桌面上弹报错窗口
      "import ctypes; pathlib.Path('console.txt').write_text(str(ctypes.windll.kernel32.GetConsoleWindow() or 0))",
      "for _ in range(1200): time.sleep(0.1)",
    ].join("\n");
    const runs = acrossImpls("s5a", (impl, dir) =>
      supervised(runProbeWithFlags(impl, request(dir, "s5a", [PY, "-c", child], { timeout: 1, grace: 15 }), DETACHED_PROCESS)));
    try {
      for (const run of runs) {
        expect(comparable(run.value), run.impl.name).toEqual(comparable((runs[0] as typeof run).value));
        expect(run.value).toMatchObject({ timed_out: true, kill_method: "job-object", ctrl_break: "failed", ctrl_break_winerror: 6 });
        expect(run.value.wall_seconds, run.impl.name).toBeLessThan(8); // 以前送不到也照样白等 15 秒
        expect(waitGone(run.value.pid as number)).toBe(true);
        expect(waitGone(Number(readFileSync(join(run.dir, "grandchild.pid"), "utf8")))).toBe(true);
        expect(readFileSync(join(run.dir, "console.txt"), "utf8"), run.impl.name).toBe("0");
      }
    } finally {
      cleanup(runs);
    }
  });

  it("S5b 调用方有控制台（不显示窗口）：子进程真的收到 CTRL_BREAK，没等满宽限就退出", () => {
    const child = [
      "import pathlib, signal, sys, time",
      "def on_break(signum, frame):",
      "    pathlib.Path('marker').write_text('got')",
      "    sys.exit(3)",
      "signal.signal(signal.SIGBREAK, on_break)",
      "for _ in range(1200): time.sleep(0.1)",
    ].join("\n");
    const runs = acrossImpls("s5b", (impl, dir) =>
      supervised(runProbeWithFlags(impl, request(dir, "s5b", [PY, "-c", child], { timeout: 1, grace: 15 }), CREATE_NO_WINDOW)));
    try {
      for (const run of runs) {
        expect(comparable(run.value), run.impl.name).toEqual(comparable((runs[0] as typeof run).value));
        expect(run.value).toMatchObject({ timed_out: true, ctrl_break: "sent", ctrl_break_winerror: null, exit_code: 3 });
        expect(readFileSync(join(run.dir, "marker"), "utf8"), run.impl.name).toBe("got");
        expect(run.value.wall_seconds, run.impl.name).toBeLessThan(8);
      }
    } finally {
      cleanup(runs);
    }
  });

  it("S5c 子进程不理会 CTRL_BREAK：等满宽限再结束 Job", () => {
    const child = "import signal, time\nsignal.signal(signal.SIGBREAK, signal.SIG_IGN)\nfor _ in range(1200): time.sleep(0.1)";
    const runs = acrossImpls("s5c", (impl, dir) =>
      supervised(runProbeWithFlags(impl, request(dir, "s5c", [PY, "-c", child], { timeout: 1, grace: 2 }), CREATE_NO_WINDOW)));
    try {
      for (const run of runs) {
        expect(comparable(run.value), run.impl.name).toEqual(comparable((runs[0] as typeof run).value));
        expect(run.value).toMatchObject({ timed_out: true, ctrl_break: "sent", exit_code: 1 });
        expect(run.value.wall_seconds, run.impl.name).toBeGreaterThanOrEqual(2.9);
        expect(run.value.wall_seconds, run.impl.name).toBeLessThan(10);
      }
    } finally {
      cleanup(runs);
    }
  });

  it("S6 子进程退出后留下的孙进程算残留，被结束", () => {
    const child = [
      "import pathlib, subprocess, sys",
      "g = subprocess.Popen([sys.executable, '-c', 'import time\\nfor _ in range(1200): time.sleep(0.1)'], creationflags=0x8,",
      "                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
      "pathlib.Path('grandchild.pid').write_text(str(g.pid))",
    ].join("\n");
    const runs = acrossImpls("s6", (impl, dir) => supervised(runProbe(impl, request(dir, "s6", [PY, "-c", child]))));
    try {
      for (const run of runs) {
        expect(comparable(run.value), run.impl.name).toEqual(comparable((runs[0] as typeof run).value));
        expect(run.value).toMatchObject({ exit_code: 0, stray_processes: true, timed_out: false });
        expect(waitGone(Number(readFileSync(join(run.dir, "grandchild.pid"), "utf8")))).toBe(true);
      }
    } finally {
      cleanup(runs);
    }
  });

  it("S7 .cmd 照样能跑（lpApplicationName 传 NULL），npm 经 which 解析出的 .CMD 实跑一次", () => {
    const runs = acrossImpls("s7", (impl, dir) => {
      const script = join(dir, "fake.cmd");
      writeFileSync(script, "@echo off\r\necho args=%*\r\nexit /b 5\r\n");
      return supervised(runProbe(impl, request(dir, "s7", [script, "a", "b c"])));
    });
    const npm = spawnSync(PY, ["-c", "import shutil; print(shutil.which('npm'))"], { encoding: "utf8" }).stdout.trim();
    const npmRuns = acrossImpls("s7npm", (impl, dir) => supervised(runProbe(impl, request(dir, "npm", [npm, "--version"]))));
    try {
      expect(npm.toLowerCase()).toMatch(/\.cmd$/u);
      for (const run of runs) {
        expect(run.value.exit_code, run.impl.name).toBe(5);
        expect(readFileSync(join(run.dir, "s7.out"), "utf8"), run.impl.name).toBe('args=a "b c"\r\n');
      }
      const version = readFileSync(join((npmRuns[0] as (typeof npmRuns)[number]).dir, "npm.out"), "utf8");
      expect(version).toMatch(/^\d+\.\d+\.\d+/u);
      for (const run of npmRuns) {
        expect(run.value.exit_code, run.impl.name).toBe(0);
        expect(readFileSync(join(run.dir, "npm.out"), "utf8"), run.impl.name).toBe(version);
      }
    } finally {
      cleanup([...runs, ...npmRuns]);
    }
  });

  it("S9 ensure_argv_safe：一组含特殊字符的语料，判定与报错和 Python 逐个一致", () => {
    // 末尾带点与空格的几种写法（第 71 轮）：Windows 去掉它们之后照样是批处理；制表符、:: 之类不去，也起不来
    const programs = ["x.cmd", "X.CMD", "npm.Cmd", "a.bat", "A.BAT", "x.cmd.", "x.cmd ", "x.bat. .", "X.BAT..", "x.cmd  ",
      "x.bat.\t", "x.bat::$DATA", "x.exe", "x.exe.", "x.bat.exe", "x.cmdx", "cmd", ".", " ",
      "ｘ.ＣＭＤ", "x.cmİ", "ẞ.cmd", "\u212Aey.CMD", "x.c\u0307md", "x.\u0130", "C:\\Program Files\\nodejs\\npm.cmd"];
    const args = ["a&b", "a|b", "a<b", "a>b", "a^b", "a%b", "a!b", 'a"b', "a\rb", "a\nb", "a b", "a-b", "中文", "", "a'b"];
    const items = programs.flatMap((program) => args.map((arg) => ({ op: "argv.ensure_safe", cmd: [program, "ok", arg] })));
    const python = runBatch(PYTHON_IMPL, items);
    expect(python.filter((result) => !result.ok).length).toBeGreaterThan(20); // 语料里确实有被拒的
    const refused = (program: string): boolean => !(python[programs.indexOf(program) * args.length] as ProbeResult).ok; // 参数 a&b
    for (const program of ["x.cmd.", "x.cmd ", "x.bat. .", "X.BAT..", "x.cmd  "]) expect(refused(program), program).toBe(true);
    for (const program of ["x.bat.\t", "x.bat::$DATA", "x.exe.", "x.bat.exe", ".", " "]) expect(refused(program), program).toBe(false);
    for (const impl of IMPLS.slice(1)) expect(runBatch(impl, items), impl.name).toEqual(python);
  });

  it("S9b 文件名末尾带点的 .bat（第 71 轮，CVE-2024-43402）：照样经 cmd.exe 执行，注入真的生效；ensure_argv_safe 三套实现都拦下", () => {
    // 进程监督本身不拒绝批处理（迁移计划第 8.2 节第 3 条），先证明绕过是真的：直接起 t.bat.，参数里的 echo 被 cmd.exe
    // 执行了。再证明调用方该过的那一关把同一个 argv 拦下
    const injection = 'x" & echo INJECTED & rem "';
    const runs = acrossImpls("s9b", (impl, dir) => {
      writeFileSync(join(dir, "t.bat"), "@echo ARG1=%1\r\n", "ascii");
      const cmd = [`${join(dir, "t.bat")}.`, injection];
      return { run: supervised(runProbe(impl, request(dir, "s9b", cmd))), check: runProbe(impl, { op: "argv.ensure_safe", cmd }) };
    });
    try {
      for (const run of runs) {
        expect(run.value.run.exit_code, run.impl.name).toBe(0);
        expect(readFileSync(join(run.dir, "s9b.out"), "utf8"), run.impl.name).toContain("INJECTED");
        expect(run.value.check.ok, run.impl.name).toBe(false);
        expect(String(run.value.check["message"]), run.impl.name).toContain("含批处理特殊字符");
      }
      // 报错文字里有临时目录，各不相同：换成同一个占位再比
      const masked = runs.map((run) => JSON.stringify(run.value.check).split(JSON.stringify(run.dir).slice(1, -1)).join("<dir>"));
      for (const text of masked) expect(text).toBe(masked[0]);
    } finally {
      cleanup(runs);
    }
  });

  it("S10 中断：调用方的进程组收到 CTRL_BREAK，三套实现都照中断处理，子进程也收到", () => {
    // 外层以 CREATE_NO_WINDOW 起一个不显示窗口的控制台，探针另起进程组、共用这个控制台；探针报 spawned 之后外层给
    // 探针的进程组发 CTRL_BREAK（只到探针，被监督的子进程在自己的进程组里，由探针去结束）。请求经两层的 stdin 交给探针。
    // 内层等 spawned 时读到 EOF 或过了 60 秒就结束探针退出（以前读到 EOF 会空转）；外层等内层 90 秒，超时用 taskkill /T
    // 结束整棵树（内层还活着，/T 才找得到它的子孙），不留孤儿
    const inner = [
      "import json, signal, subprocess, sys, time",
      "p = subprocess.Popen(json.loads(sys.argv[1]), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x200)",
      "p.stdin.write(sys.stdin.buffer.read()); p.stdin.close()",
      "deadline = time.monotonic() + 60",
      "line = p.stderr.readline()",
      "while b'spawned' not in line:",
      "    if not line or time.monotonic() > deadline:",
      "        p.kill(); sys.exit('探针没报 spawned：stderr 关了或等满 60 秒')",
      "    line = p.stderr.readline()",
      "time.sleep(1)",
      "p.send_signal(signal.CTRL_BREAK_EVENT)",
      "out = p.stdout.read(); p.wait()",
      "sys.stdout.buffer.write(out)",
    ].join("\n");
    const outer = [
      "import os, subprocess, sys",
      "p = subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, creationflags=0x08000000)",
      "try:",
      "    out, _ = p.communicate(sys.stdin.buffer.read(), timeout=90)",
      "except subprocess.TimeoutExpired:",
      "    taskkill = os.path.join(os.environ['SystemRoot'], 'System32', 'taskkill.exe')",
      "    subprocess.run([taskkill, '/T', '/F', '/PID', str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
      "    p.communicate()",
      "    sys.exit('内层 90 秒没结束，已结束整棵树')",
      "sys.stdout.buffer.write(out)",
    ].join("\n");
    const runs = acrossImpls("s10", (impl, dir) => {
      const req = request(dir, "s10", [PY, "-c", SLEEP], { timeout: 120, grace: 15 });
      const done = spawnSync(PY, ["-c", outer, inner, JSON.stringify(impl.argv)], {
        input: JSON.stringify(req), encoding: "utf8", timeout: 150_000,
      });
      if (done.status !== 0) throw new Error(`${impl.name} 中断用例的包装进程退出码 ${String(done.status)}：${done.stderr}`);
      return supervised(JSON.parse(done.stdout) as ProbeResult);
    });
    try {
      for (const run of runs) {
        expect(comparable(run.value), run.impl.name).toEqual(comparable((runs[0] as typeof run).value));
        expect(run.value).toMatchObject({ interrupted: true, timed_out: false, ctrl_break: "sent", kill_method: "job-object" });
        expect(run.value.wall_seconds, run.impl.name).toBeLessThan(10);
      }
    } finally {
      cleanup(runs);
    }
  });

  it("S11 挂起创建之后、恢复之前，子进程一条指令也不执行（Bun，真的 Win32 调用）", () => {
    const bun = IMPLS.find((impl) => impl.name === "ts-bun") as Impl;
    const dir = scratchDir("sup-s11");
    try {
      const marker = join(dir, "marker");
      const result = runProbe(bun, {
        ...request(dir, "s11", [PY, "-c", `open(${JSON.stringify(marker)}, 'w').write('1')`]),
        op: "supervise.suspended_check", marker,
      });
      expect(result).toMatchObject({ ok: true, before_resume: false, after: true });
      expect((result["result"] as Supervised).exit_code).toBe(0);
    } finally {
      removeDir(dir);
    }
  });

  it.each(IMPLS)("S8 杀掉调用方（$name），整棵树跟着结束", async (impl) => {
    const dir = scratchDir(`sup-s8-${impl.name}`);
    const child = [
      "import pathlib, subprocess, sys, time",
      "g = subprocess.Popen([sys.executable, '-c', 'import time\\nfor _ in range(1200): time.sleep(0.1)'], creationflags=0x8,",
      "                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
      "pathlib.Path('grandchild.pid').write_text(str(g.pid))",
      "for _ in range(1200): time.sleep(0.1)",
    ].join("\n");
    const [command, ...args] = impl.argv;
    const probe = spawn(command ?? "", args, { stdio: ["pipe", "pipe", "pipe"] });
    probe.stdin.end(JSON.stringify(request(dir, "s8", [PY, "-c", child], { timeout: 300 })));
    try {
      const pid = await new Promise<number>((done, fail) => {
        let stderr = "";
        probe.stderr.setEncoding("utf8").on("data", (chunk: string) => {
          stderr += chunk;
          const match = /spawned (\d+)/u.exec(stderr);
          if (match) done(Number(match[1]));
        });
        probe.on("exit", () => fail(new Error(`探针先退出了：${stderr}`)));
      });
      for (let i = 0; i < 100 && !existsSync(join(dir, "grandchild.pid")); i += 1) await new Promise((r) => setTimeout(r, 100));
      const grandchild = Number(readFileSync(join(dir, "grandchild.pid"), "utf8"));
      expect(pidAlive(pid)).toBe(true);
      probe.kill(); // TerminateProcess：调用方意外死掉
      expect(waitGone(pid), "子进程").toBe(true);
      expect(waitGone(grandchild), "孙进程").toBe(true);
    } finally {
      probe.kill();
      tidy(dir);
    }
  });
});
