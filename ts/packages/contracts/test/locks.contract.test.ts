// 目录锁、pid_alive 与文本读写的契约：照现行三份锁（kit_hub.DirLock、pi_dispatch.TaskLock、kit_config.ConfigLock）、
// pi_dispatch.pid_alive、kit_hub.read_text / write_text_atomic 的行为。每套实现逐条通过，Python 实现先过。
// 对照部分：两套实现抢同一把锁，必须互斥；同一把锁写出的 owner.json 格式相同。
// 报错文字只比较类型（迁移计划 §3.4 的第二类）：三把锁等满之后的报错只进 stderr 与命令的退出信息，
// 不进证据。Python 的 DirLock 写 owner 字典的 repr（单引号），TS 用 JSON，契约这里只比较“busy”。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, utimesSync, writeFileSync } from "node:fs";
import { hostname } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { IMPLS, type Impl, type ProbeResult, PYTHON, TS_NODE, removeDir, runProbe, scratchDir, startProbe } from "./harness.ts";

const UTC = "\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z";
const EOL_CONFIG = process.platform === "win32" ? "\\r\\n" : "\\n";

/** 一个确定已经退出的进程编号。 */
function deadPid(): number {
  const done = spawnSync(process.execPath, ["-e", ""]);
  return done.pid ?? 999_999;
}

function owner(result: ProbeResult): string {
  return Buffer.from(String(result["owner_b64"] ?? ""), "base64").toString("utf8");
}

/** 测试自己摆一把已被占用的锁（owner.json 用现行的格式）。 */
function occupy(lockDir: string, fields: string): void {
  mkdirSync(lockDir, { recursive: true });
  writeFileSync(join(lockDir, "owner.json"), fields + "\n");
}

describe.each(IMPLS)("目录锁契约 impl=$name", (impl) => {
  let dir = "";
  beforeEach(() => {
    dir = scratchDir(`lock-${impl.name}`);
  });
  afterEach(() => removeDir(dir));
  const run = (request: Record<string, unknown>): ProbeResult => runProbe(impl, { op: "lock.run", ...request });

  it("DL1 DirLock 空闲时拿到；owner.json 是 {\"pid\": …, \"token\": 16 位十六进制, \"at\": …} 加换行；释放后目录删掉", () => {
    const result = run({ kind: "dir", path: join(dir, ".land") });
    expect(result).toMatchObject({ ok: true, left: false });
    expect(owner(result)).toMatch(new RegExp(`^\\{"pid": \\d+, "token": "[0-9a-f]{16}", "at": "${UTC}"\\}\\n$`));
  });

  it("DL2 DirLock 被活着的进程占着：等满报忙，锁原样不动", () => {
    const fields = `{"pid": ${process.pid}, "token": "live-holder", "at": "2026-10-22T00:00:00Z"}`;
    occupy(join(dir, ".land"), fields);
    expect(run({ kind: "dir", path: join(dir, ".land"), wait: 1 })).toEqual({ ok: false, error: "busy" });
    expect(readFileSync(join(dir, ".land", "owner.json"), "utf8")).toBe(fields + "\n");
  });

  it("DL3 DirLock 的持有者已经不在：接管", () => {
    occupy(join(dir, ".land"), `{"pid": ${deadPid()}, "token": "dead-holder", "at": "2026-10-22T00:00:00Z"}`);
    expect(run({ kind: "dir", path: join(dir, ".land"), wait: 5 })).toMatchObject({ ok: true, left: false });
  });

  it("DL4 DirLock 释放前锁已被别人重建（令牌不同）：不删", () => {
    expect(run({ kind: "dir", path: join(dir, ".land"), tamper: true })).toMatchObject({ ok: true, left: true });
  });

  it("TL1 TaskLock 在 <runs>/<task>/.task.lock；owner.json 是 {\"pid\": …, \"at\": …} 加换行", () => {
    const result = run({ kind: "task", root: dir, task: "t001-doc" });
    expect(result).toMatchObject({ ok: true, left: false });
    expect(owner(result)).toMatch(new RegExp(`^\\{"pid": \\d+, "at": "${UTC}"\\}\\n$`));
  });

  it("TL2 TaskLock 被占、目录还新：等满报忙", () => {
    occupy(join(dir, "t001-doc", ".task.lock"), `{"pid": ${process.pid}, "at": "2026-10-22T00:00:00Z"}`);
    expect(run({ kind: "task", root: dir, task: "t001-doc", wait: 1 })).toEqual({ ok: false, error: "busy" });
  });

  it("TL3 TaskLock 被占但目录的修改时间超过 stale 秒：接管（不看持有者在不在）", () => {
    const lockDir = join(dir, "t001-doc", ".task.lock");
    occupy(lockDir, `{"pid": ${process.pid}, "at": "2026-10-22T00:00:00Z"}`);
    const old = new Date(Date.now() - 600_000);
    utimesSync(lockDir, old, old);
    expect(run({ kind: "task", root: dir, task: "t001-doc", wait: 5, stale: 300 })).toMatchObject({ ok: true, left: false });
  });

  it("TL4 TaskLock 释放时不核对持有者：照删", () => {
    expect(run({ kind: "task", root: dir, task: "t001-doc", tamper: true })).toMatchObject({ ok: true, left: false });
  });

  it("CL1 ConfigLock 在 <.agent>/.config.lock；owner.json 记 pid、主机、32 位十六进制令牌与创建时间，Windows 上换行是 \\r\\n", () => {
    const result = run({ kind: "config", root: dir });
    expect(result).toMatchObject({ ok: true, left: false });
    expect(owner(result)).toMatch(
      new RegExp(`^\\{"pid": \\d+, "host": "[^"]+", "token": "[0-9a-f]{32}", "created_at": "${UTC}"\\}${EOL_CONFIG}$`),
    );
  });

  it("CL2 ConfigLock 从不接管：持有者已经不在也等满报忙", () => {
    occupy(join(dir, ".config.lock"), `{"pid": ${deadPid()}, "host": "x", "token": "dead", "created_at": "2026-10-22T00:00:00Z"}`);
    expect(run({ kind: "config", root: dir, wait: 1 })).toEqual({ ok: false, error: "busy" });
    expect(existsSync(join(dir, ".config.lock", "owner.json"))).toBe(true);
  });

  it("CL3 ConfigLock 释放前令牌被改：不删", () => {
    expect(run({ kind: "config", root: dir, tamper: true })).toMatchObject({ ok: true, left: true });
  });
});

describe.each(IMPLS)("pid_alive 与文本读写契约 impl=$name", (impl) => {
  let dir = "";
  beforeEach(() => {
    dir = scratchDir(`fs-${impl.name}`);
  });
  afterEach(() => removeDir(dir));

  it("PA1 活着的进程为 true，已退出的为 false，0 为 null", () => {
    expect(runProbe(impl, { op: "pid_alive", pid: process.pid })).toEqual({ ok: true, alive: true });
    expect(runProbe(impl, { op: "pid_alive", pid: deadPid() })).toEqual({ ok: true, alive: false });
    expect(runProbe(impl, { op: "pid_alive", pid: 0 })).toEqual({ ok: true, alive: null });
  });

  it("FS1 read_text：\\r\\n 与单独的 \\r 换成 \\n，BOM 保留；不存在或是目录读成空串；不是 UTF-8 报 UnicodeDecodeError", () => {
    writeFileSync(join(dir, "a.txt"), Buffer.from([0xef, 0xbb, 0xbf, 0x61, 0x0d, 0x0a, 0x62, 0x0d, 0x63, 0xe4, 0xb8, 0xad]));
    writeFileSync(join(dir, "bad.txt"), Buffer.from([0x61, 0xff, 0x62]));
    mkdirSync(join(dir, "sub"));
    expect(runProbe(impl, { op: "fs.read_text", path: join(dir, "a.txt") })).toEqual({ ok: true, text: "\ufeffa\nb\nc中" });
    expect(runProbe(impl, { op: "fs.read_text", path: join(dir, "missing.txt") })).toEqual({ ok: true, text: "" });
    expect(runProbe(impl, { op: "fs.read_text", path: join(dir, "sub") })).toEqual({ ok: true, text: "" });
    expect(runProbe(impl, { op: "fs.read_text", path: join(dir, "bad.txt") })).toEqual({ ok: false, error: "UnicodeDecodeError" });
  });

  it("FS2 write_text_atomic：整份替换已有的文件，换行原样，不留临时文件", () => {
    writeFileSync(join(dir, "state.json"), "旧的");
    expect(runProbe(impl, { op: "fs.write_text_atomic", path: join(dir, "state.json"), text: "{\n  \"a\": 1\r\n}\n中" })).toEqual({ ok: true });
    expect(readFileSync(join(dir, "state.json"), "utf8")).toBe("{\n  \"a\": 1\r\n}\n中");
    expect(readdirSync(dir)).toEqual(["state.json"]);
  });

  it("FS3 write_text_atomic 遇到孤立代理项报 UnicodeEncodeError，原文件不动（与 Python 一样留下临时文件）", () => {
    writeFileSync(join(dir, "state.json"), "旧的");
    expect(runProbe(impl, { op: "fs.write_text_atomic", path: join(dir, "state.json"), text: "a\ud800b" })).toEqual({
      ok: false,
      error: "UnicodeEncodeError",
    });
    expect(readFileSync(join(dir, "state.json"), "utf8")).toBe("旧的");
    expect(readdirSync(dir).filter((name) => name.endsWith(".tmp"))).toHaveLength(1);
  });
});

describe("目录锁对照：两套实现抢同一把锁", () => {
  const pairs: readonly (readonly [Impl, Impl])[] = [
    [PYTHON, TS_NODE],
    [TS_NODE, PYTHON],
  ];
  it.each(
    (["dir", "task", "config"] as const).flatMap((kind) => pairs.map(([holder, waiter]) => [kind, holder.name, waiter.name, holder, waiter] as const)),
  )("%s 锁：%s 持有期间 %s 拿不到，放了才拿到", async (kind, _holderName, _waiterName, holder, waiter) => {
    const dir = scratchDir(`race-${kind}`);
    try {
      const where = kind === "dir" ? { path: join(dir, ".land") } : kind === "task" ? { root: dir, task: "t001-doc" } : { root: dir };
      const lockDir = kind === "dir" ? join(dir, ".land") : kind === "task" ? join(dir, "t001-doc", ".task.lock") : join(dir, ".config.lock");
      const held = startProbe(holder, { op: "lock.run", kind, ...where, hold_ms: 1500 });
      const until = Date.now() + 10_000;
      while (!existsSync(join(lockDir, "owner.json")) && Date.now() < until) await new Promise((r) => setTimeout(r, 20));
      const waited = runProbe(waiter, { op: "lock.run", kind, ...where, wait: 10 });
      const first = await held.result;
      expect(first).toMatchObject({ ok: true });
      expect(waited).toMatchObject({ ok: true, left: false });
      expect(Number(waited["acquired_ms"])).toBeGreaterThanOrEqual(Number(first["released_ms"]) - 50);
    } finally {
      removeDir(dir);
    }
  });

  it("两套实现写的 ConfigLock owner.json 只差 pid、令牌与时间；主机名相同", () => {
    const hosts = IMPLS.map((impl) => {
      const dir = scratchDir(`host-${impl.name}`);
      try {
        const text = owner(runProbe(impl, { op: "lock.run", kind: "config", root: dir }));
        return /"host": "([^"]+)"/.exec(text)?.[1];
      } finally {
        removeDir(dir);
      }
    });
    expect(new Set(hosts)).toEqual(new Set([hosts[0]]));
    expect(hosts[0]?.toLowerCase()).toBe(hostname().toLowerCase());
  });
});
