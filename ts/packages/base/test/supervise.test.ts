// supervise 的白盒测试：用一套假的 Win32 调用走契约够不到的分支（建不了 Job、加入 Job 失败、恢复失败、残留进程
// 查不到、句柄都关掉）。真实行为由 packages/contracts 的 supervise 契约覆盖（三套实现、真进程）。
import { describe, expect, it } from "vitest";
import { type WinProcessApi, Win32Error } from "../src/native.ts";
import { type SuperviseOptions, environmentBlock, list2cmdline, superviseWith, windowsErrorText } from "../src/supervise.ts";

interface Script {
  job?: () => bigint;
  assign?: boolean;
  resume?: boolean;
  /** exited 第几次调用开始返回 true（缺省第一次就结束）；Infinity 表示一直不结束，直到 terminateJob。 */
  exitAfter?: number;
  ctrlBreak?: number | null;
  active?: number;
  exitCode?: number;
}

function fakeApi(script: Script = {}) {
  const calls: string[] = [];
  const opened: bigint[] = [];
  const closed: bigint[] = [];
  let next = 100n;
  let polls = 0;
  let killed = false;
  const api: WinProcessApi = {
    createKillOnCloseJob: () => {
      calls.push("job");
      return script.job ? script.job() : 1n;
    },
    openInheritable: () => {
      next += 1n;
      opened.push(next);
      return next;
    },
    spawnSuspended: () => {
      calls.push("spawn");
      return { process: 10n, thread: 11n, pid: 4242 };
    },
    assign: () => {
      calls.push("assign");
      return script.assign ?? true;
    },
    resume: () => {
      calls.push("resume");
      return script.resume ?? true;
    },
    terminateProcess: () => void calls.push("terminateProcess"),
    exited: () => {
      polls += 1;
      return killed || polls >= (script.exitAfter ?? 1);
    },
    exitCode: () => script.exitCode ?? 0,
    ctrlBreak: () => {
      calls.push("ctrlBreak");
      return script.ctrlBreak === undefined ? null : script.ctrlBreak;
    },
    attachConsole: () => true,
    terminateJob: () => {
      calls.push("terminateJob");
      killed = true;
    },
    activeProcesses: () => script.active ?? 0,
    close: (handle) => void closed.push(handle),
    compareIgnoreCase: (a, b) => {
      const x = a.toUpperCase();
      const y = b.toUpperCase();
      return x < y ? -1 : x > y ? 1 : 0;
    },
    message: () => "The system cannot find the file specified.\r\n",
  };
  return { api, calls, opened, closed };
}

const OPTIONS: SuperviseOptions = {
  cwd: "C:\\work", env: [["A", "1"]], timeout: null, grace: 15,
  stdout: { path: "out", how: "create-new" }, stderr: { path: "err", how: "create-new" },
};

describe("supervise 的分支（假的 Win32 调用）", () => {
  it("建不了 Job：拒绝运行，文字与 Python 的 OSError(错误码, …) 相同，什么都没起", async () => {
    for (const [call, code] of [["CreateJobObjectW", 5], ["SetInformationJobObject", 87]] as const) {
      const fake = fakeApi({ job: () => { throw new Win32Error(call, code); } });
      const result = await superviseWith(fake.api, ["x.exe"], OPTIONS);
      expect(result.spawn_error).toBe(`无法创建 Windows Job Object，拒绝在没有进程树监督的情况下运行：[Errno ${code}] ${call} failed`);
      expect(result.kill_method).toBeNull();
      expect(fake.calls).toEqual(["job"]);
    }
  });

  it.each([["加入 Job 失败", { assign: false }], ["恢复失败", { resume: false }]] as const)(
    "%s：终止子进程、拒绝运行，不调 onSpawn，句柄都关掉",
    async (_name, script) => {
      const fake = fakeApi(script);
      const spawned: number[] = [];
      const result = await superviseWith(fake.api, ["x.exe"], { ...OPTIONS, onSpawn: (pid) => void spawned.push(pid) });
      expect(result.spawn_error).toBe("进程未能加入 Job Object，已在启动前终止");
      expect(result.pid).toBe(4242);
      expect(fake.calls).toContain("terminateProcess");
      expect(spawned).toEqual([]);
      expect(fake.closed).toEqual(expect.arrayContaining([...fake.opened, 10n, 11n, 1n]));
    },
  );

  it("超时、CTRL_BREAK 发不出去：记 failed 与错误码，不等宽限就结束 Job", async () => {
    const fake = fakeApi({ exitAfter: Infinity, ctrlBreak: 6, exitCode: 1 });
    const started = performance.now();
    const result = await superviseWith(fake.api, ["x.exe"], { ...OPTIONS, timeout: 0.2, grace: 15 });
    expect(result).toMatchObject({ timed_out: true, ctrl_break: "failed", ctrl_break_winerror: 6, exit_code: 1 });
    expect(performance.now() - started).toBeLessThan(3000);
    expect(fake.calls.filter((call) => call === "ctrlBreak")).toHaveLength(1);
  });

  it("超时、CTRL_BREAK 发出去了但子进程不理会：等满宽限再结束 Job", async () => {
    const fake = fakeApi({ exitAfter: Infinity, exitCode: 1 });
    const started = performance.now();
    const result = await superviseWith(fake.api, ["x.exe"], { ...OPTIONS, timeout: 0.1, grace: 0.5 });
    expect(result).toMatchObject({ timed_out: true, ctrl_break: "sent", ctrl_break_winerror: null });
    expect(performance.now() - started).toBeGreaterThanOrEqual(550);
  });

  it("残留进程：还有就结束并记 true，查不到记 null", async () => {
    const stray = fakeApi({ active: 2 });
    expect((await superviseWith(stray.api, ["x.exe"], OPTIONS)).stray_processes).toBe(true);
    expect(stray.calls).toContain("terminateJob");
    expect((await superviseWith(fakeApi({ active: -1 }).api, ["x.exe"], OPTIONS)).stray_processes).toBeNull();
    expect((await superviseWith(fakeApi({ active: 0 }).api, ["x.exe"], OPTIONS)).stray_processes).toBe(false);
  });

  it("启动失败的报错照 CPython：类名按错误码，文字去掉末尾的换行与句点", () => {
    expect(windowsErrorText(2, "The system cannot find the file specified.\r\n")).toBe(
      "FileNotFoundError: [WinError 2] The system cannot find the file specified");
    expect(windowsErrorText(267, "The directory name is invalid.\r\n")).toBe("NotADirectoryError: [WinError 267] The directory name is invalid");
    expect(windowsErrorText(193, "%1 is not a valid Win32 application.\r\n")).toBe("OSError: [WinError 193] %1 is not a valid Win32 application");
    expect(windowsErrorText(5, "拒绝访问。\r\n")).toBe("PermissionError: [WinError 5] 拒绝访问。");
  });

  it("list2cmdline 与环境块的几个边角", () => {
    expect(list2cmdline(["a", "", "b c", 'd"e', "f\\", "g h\\"])).toBe('a "" "b c" d\\"e f\\ "g h\\\\"');
    const compare = (a: string, b: string): number => (a.toUpperCase() < b.toUpperCase() ? -1 : a.toUpperCase() > b.toUpperCase() ? 1 : 0);
    // Python 的 dict：完全同名的键留第一次的位置、最后一次的值；大小写不同的同名变量留最后插入的那一个
    const block = environmentBlock([["path", "1"], ["PATH", "2"], ["path", "3"]], compare).toString("utf16le");
    expect(block).toBe("PATH=2\0\0");
    expect(environmentBlock([], compare).toString("utf16le")).toBe("\0\0");
  });
});
