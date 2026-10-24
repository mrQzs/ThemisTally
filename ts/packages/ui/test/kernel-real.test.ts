// 真内核的端到端（桌面端 §5.3、D09/D15、U9）：起真的服务（Bun）与真内核（scripts/pi_dispatch.py），在 git 夹具仓库上
// 比对 status 与 file 的 data 与 CLI stdout 逐字节一致；file 路由超时时整棵树（含孙进程）被结束，期间 ping 与
// /control/bootstrap 照常响应。客户端在 Node 一侧发原始 HTTP；收进程靠关 stdin 与 kill，不发控制台信号。
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, beforeEach, describe, expect, it } from "vitest";
import { dumps, loads } from "@themis/base/pyjson";
import { pidAlive } from "@themis/base/process";
import { type RunningService, REPO_ROOT, header, request, startService } from "./harness.ts";

const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const KERNEL = join(REPO_ROOT, "scripts", "pi_dispatch.py");

let dir = "";
let repo = "";
let assets = "";
let service: RunningService | null = null;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-real-"));
  repo = join(dir, "repo");
  assets = join(dir, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>real</title>\n");
  for (const args of [["init", "-q", repo], ["-C", repo, "config", "user.email", "ui@example.invalid"], ["-C", repo, "config", "user.name", "ui"]]) {
    const done = spawnSync("git", args, { encoding: "utf8" });
    if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  }
  writeFileSync(join(repo, "README.md"), "# 夹具仓库\n");
  const added = spawnSync("git", ["-C", repo, "add", "-A"], { encoding: "utf8" });
  if (added.status !== 0) throw new Error(`git add 失败：${added.stderr}`);
  const committed = spawnSync("git", ["-C", repo, "commit", "-q", "-m", "init"], { encoding: "utf8" });
  if (committed.status !== 0) throw new Error(`git commit 失败：${committed.stderr}`);
  const attempt = join(repo, ".agent", "runs", "demo-task", "attempt-001");
  mkdirSync(attempt, { recursive: true });
  writeFileSync(join(attempt, "notes.txt"), "第一行：夹具证据\n第二行：还是夹具\n", "utf8");
});

afterEach(() => {
  service?.kill();
  service = null;
});

afterAll(() => {
  rmSync(dir, { recursive: true, force: true });
});

/** 起真的服务（python 与 kernel 都可指向真内核或夹具内核）。 */
async function open(options: { kernel?: string; timeouts?: Record<string, number> } = {}): Promise<RunningService> {
  service = await startService({
    repo,
    assets,
    python: PYTHON,
    kernel: options.kernel ?? KERNEL,
    entry: "overrides",
    overrides: { ...(options.timeouts === undefined ? {} : { timeouts: options.timeouts }) },
  });
  return service;
}

const sessionOf = async (running: RunningService): Promise<string> => {
  const nonce = running.handshake.bootstrap.split("/").pop() ?? "";
  const booted = await request(running.port, "GET", `/bootstrap/${nonce}`);
  expect(booted.status).toBe(302);
  return (header(booted, "set-cookie") ?? "").split(";")[0] ?? "";
};

const envelopeOf = (body: Buffer): Record<string, unknown> => JSON.parse(body.toString("utf8")) as Record<string, unknown>;

/**
 * 服务给的 data 用 pyjson 的 dumps(ensureAscii:false, indent:2) 拼出来（与内核的 stdout 同一写法）。内核在 Windows 上
 * 把换行写成 CRLF，服务解析之后用 LF 重新写出，所以比对前把 CLI stdout 的 CRLF 归一成 LF——除换行之外逐字节相同。
 */
const rendered = (data: unknown): string => dumps(loads(JSON.stringify(data)) as never, { ensureAscii: false, indent: 2 });
const cliText = (stdout: string): string => {
  const lf = String.fromCharCode(10);
  const crlf = String.fromCharCode(13) + lf;
  const text = stdout.split(crlf).join(lf);
  return text.endsWith(lf) ? text.slice(0, -1) : text;
};

").join("
").replace(/
$/u, "");

/gu, "
").replace(/
$/u, "");

describe("真内核逐字节一致（U9）", () => {
  it("status 与 file 的 data 与 CLI stdout 逐字节相同", async () => {
    const running = await open();
    const cookie = await sessionOf(running);

    const status = await request(running.port, "GET", "/api/v1/status", [["Cookie", cookie]]);
    expect(status.status).toBe(200);
    const statusEnvelope = envelopeOf(status.body);
    expect(statusEnvelope["ok"]).toBe(true);
    expect(statusEnvelope["command"]).toEqual(["status", "--json"]);
    const cliStatus = spawnSync(PYTHON, [KERNEL, "--repo", repo, "status", "--json"], { encoding: "utf8", timeout: 120_000 });
    expect(cliStatus.status).toBe(0);
    expect(rendered(statusEnvelope["data"])).toBe(cliStatus.stdout.replace(/\n$/u, ""));

    const first = await request(running.port, "GET", "/api/v1/attempts/demo-task/attempt-001/file?path=notes.txt", [["Cookie", cookie]]);
    expect(first.status).toBe(200);
    const page = envelopeOf(first.body)["data"] as Record<string, unknown>;
    const handle = page["next_cursor"] as string;
    expect(handle).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    const cliPage = spawnSync(PYTHON, [KERNEL, "--repo", repo, "logs", "cat", "demo-task/attempt-001", "notes.txt", "--json"], {
      encoding: "utf8",
      timeout: 120_000,
    });
    expect(cliPage.status).toBe(0);
    const cliPageData = JSON.parse(cliPage.stdout) as Record<string, unknown>;
    const mine = JSON.parse(JSON.stringify(page)) as Record<string, unknown>;
    mine["next_cursor"] = cliPageData["next_cursor"]; // 句柄换回 CLI 的 next_cursor
    expect(rendered(mine)).toBe(cliPage.stdout.replace(/\n$/u, ""));

    // 第二页：把上一页的句柄交回去，内核认得真游标（done 为真、没有下一页）
    const second = await request(running.port, "GET", `/api/v1/attempts/demo-task/attempt-001/file?path=notes.txt&cursor=${handle}`, [
      ["Cookie", cookie],
    ]);
    expect(second.status).toBe(200);
    const secondPage = envelopeOf(second.body)["data"] as Record<string, unknown>;
    expect(secondPage["done"]).toBe(true);
    expect(secondPage["next_cursor"]).toBe(null);
  });
});

describe("超时结束整棵树（D09）", () => {
  it("file 路由超时：504，孙进程也不在了，ping 与控制接口照常响应", async () => {
    const pidfile = join(dir, "grandchild.pid");
    process.env["TREE_KERNEL_PIDFILE"] = pidfile;
    // 夹具内核：起一个孙进程之后睡（真内核的 logs cat 不起孙进程，这一条钉的是执行器结束整棵树）
    const treeKernel = join(dir, "tree-kernel.py");
    writeFileSync(
      treeKernel,
      [
        "import os, subprocess, sys, time",
        "pidfile = os.environ.get('TREE_KERNEL_PIDFILE')",
        "if pidfile:",
        "    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])",
        "    with open(pidfile, 'w', encoding='utf-8') as handle:",
        "        handle.write(str(child.pid))",
        "time.sleep(120)",
      ].join("\n"),
      "utf8",
    );
    let running: RunningService | null = null;
    try {
      running = await open({ kernel: treeKernel, timeouts: { "api.attempts.file": 1 } });
      const cookie = await sessionOf(running);
      const timedOut = await request(running.port, "GET", "/api/v1/attempts/demo-task/attempt-001/file?path=notes.txt", [["Cookie", cookie]]);
      expect(timedOut.status).toBe(504);
      const body = envelopeOf(timedOut.body);
      expect(body["ok"]).toBe(false);
      expect(body["exit_code"]).toBe(null);
      expect(body["messages"]).toEqual(["ERROR: 命令超时（1 秒），子进程已结束；请改用 CLI 查看"]);
      expect(body["command"]).toEqual(["logs", "cat", "demo-task/attempt-001", "notes.txt", "--json"]);

      // 孙进程（夹具内核起的那个）也不在了
      const grandchild = Number(readFileSync(pidfile, "utf8").trim());
      expect(grandchild).toBeGreaterThan(0);
      const deadline = Date.now() + 10_000;
      while (Date.now() < deadline && pidAlive(grandchild) !== false) await new Promise((done) => setTimeout(done, 200));
      expect(pidAlive(grandchild), `孙进程 ${grandchild} 应该已经不在了`).toBe(false);

      // 期间别的接口照常响应
      const ping = await request(running.port, "GET", "/api/v1/ping", [["Cookie", cookie]]);
      expect(ping.status).toBe(200);
      const control = await request(running.port, "POST", "/control/bootstrap", [["X-Themis-Control", running.handshake.control]]);
      expect(control.status).toBe(200);
    } finally {
      delete process.env["TREE_KERNEL_PIDFILE"];
    }
  });
});
