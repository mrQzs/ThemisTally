// 凭据录入的真内核端到端（桌面端 §5.3、U18、D12）：起真的服务（Bun）与真内核（scripts/pi_dispatch.py），
// CODEKIT_SECRET_STORE=file 与临时 XDG_CONFIG_HOME 只经 harness 的 startService({ env }) 合进服务子进程（不改 vitest
// 进程的 process.env，也绝不写进本机真正的凭据库）。录入之前先经同一个服务核对 store_mode 与 system_backend，不符就
// 失败、不录入；录入时测试自己当浏览器，把假值 POST 到内核给的那一个一次性页面。客户端在 Node 一侧发原始 HTTP。
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { type RunningService, REPO_ROOT, header, request, startService } from "./harness.ts";

const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const KERNEL = join(REPO_ROOT, "scripts", "pi_dispatch.py");
const TERMINAL = new Set(["succeeded", "failed", "cancelled", "timed_out"]);

let dir = "";
let repo = "";
let assets = "";
let xdg = "";
let name = "";
let service: RunningService | null = null;
let cookie = "";

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-secret-real-"));
  repo = join(dir, "repo");
  assets = join(dir, "assets");
  xdg = join(dir, "xdg");
  mkdirSync(assets, { recursive: true });
  mkdirSync(xdg, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>secret-real</title>\n");
  for (const args of [["init", "-q", repo], ["-C", repo, "config", "user.email", "ui@example.invalid"], ["-C", repo, "config", "user.name", "ui"]]) {
    const done = spawnSync("git", args, { encoding: "utf8" });
    if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  }
  writeFileSync(join(repo, "README.md"), "# 夹具仓库\n");
  spawnSync("git", ["-C", repo, "add", "-A"], { encoding: "utf8" });
  spawnSync("git", ["-C", repo, "commit", "-q", "-m", "init"], { encoding: "utf8" });
  name = `THEMIS_UI_TEST_${createHash("sha256").update(String(Date.now())).digest("hex").slice(0, 12).toUpperCase()}`;
});

afterEach(() => {
  service?.kill();
  service = null;
  rmSync(dir, { recursive: true, force: true });
});

/** 起真的服务：环境变量只经 env 合进服务子进程（内核子进程从服务进程继承）。 */
async function open(): Promise<RunningService> {
  service = await startService({
    repo,
    assets,
    python: PYTHON,
    kernel: KERNEL,
    entry: "overrides",
    overrides: {},
    env: { CODEKIT_SECRET_STORE: "file", XDG_CONFIG_HOME: xdg },
  });
  const nonce = service.handshake.bootstrap.split("/").pop() ?? "";
  const booted = await request(service.port, "GET", `/bootstrap/${nonce}`);
  expect(booted.status).toBe(302);
  cookie = (header(booted, "set-cookie") ?? "").split(";")[0] ?? "";
  return service;
}

const postHeaders = (): [string, string][] => [
  ["Cookie", cookie],
  ["Origin", `http://127.0.0.1:${(service as RunningService).port}`],
  ["X-Themis-UI", "1"],
  ["Content-Type", "application/json"],
];

describe("真内核的凭据录入（D12）", () => {
  it("录入前核对 store_mode 与 system_backend，录入之后 succeeded、check.source 是 file、临时目录下有文件", async () => {
    const running = await open();

    // 录入之前：先经同一个服务核对 store_mode 与 system_backend，不符就失败、不录入
    const before = await request(running.port, "GET", `/api/v1/secrets/${name}`, [["Cookie", cookie]]);
    expect(before.status).toBe(200);
    const beforeData = (JSON.parse(before.body.toString("utf8")) as Record<string, unknown>)["data"] as Record<string, unknown>;
    expect(beforeData["store_mode"], "file 后端才往下录入").toBe("file");
    expect(beforeData["system_backend"], "file 后端不碰系统凭据库").toBeNull();

    // 录入：起作业、拿到一次性页面地址
    const entry = await request(running.port, "POST", `/api/v1/secrets/${name}/entry`, postHeaders(), Buffer.from("{}"));
    expect(entry.status).toBe(201);
    const entryBody = JSON.parse(entry.body.toString("utf8")) as Record<string, unknown>;
    const job = entryBody["job"] as Record<string, unknown>;
    const url = String(entryBody["url"]);
    expect(url).toMatch(/^http:\/\/127\.0\.0\.1:\d{1,5}\/[A-Za-z0-9_-]{32}$/u);
    expect(job["state"]).toBe("running");
    expect(job["kind"]).toBe("secret-entry");

    // 测试自己当浏览器：把假值 POST 到那一个一次性页面（只能用一次）
    const page = new URL(url);
    const saved = await request(Number(page.port), "POST", page.pathname, [["Content-Type", "application/x-www-form-urlencoded"]], Buffer.from("value=fake-ui-secret-value-1234"));
    expect(saved.status).toBe(200);

    // 作业落到终态：succeeded，set.backend 是 file，重查的 source 是 file
    const deadline = Date.now() + 60_000;
    let terminal: Record<string, unknown> = job;
    for (;;) {
      const polled = await request(running.port, "GET", `/api/v1/jobs/${String(job["id"])}`, [["Cookie", cookie]]);
      expect(polled.status).toBe(200);
      terminal = JSON.parse(polled.body.toString("utf8")) as Record<string, unknown>;
      if (TERMINAL.has(String(terminal["state"]))) break;
      if (Date.now() > deadline) throw new Error(`作业没到终态：${JSON.stringify(terminal)}`);
      await new Promise((done) => setTimeout(done, 100));
    }
    expect(terminal["state"]).toBe("succeeded");
    const envelope = terminal["envelope"] as Record<string, unknown>;
    expect(envelope["ok"]).toBe(true);
    const data = envelope["data"] as Record<string, unknown>;
    const set = data["set"] as Record<string, unknown>;
    expect(set["stored"]).toBe(true);
    expect(set["backend"]).toBe("file");
    expect(set["name"]).toBe(name);
    const check = data["check"] as Record<string, unknown>;
    expect(check["source"]).toBe("file");
    expect(check["store_mode"]).toBe("file");
    expect(check["system_backend"]).toBeNull();
    expect(Object.keys(check).sort()).toEqual(["name", "source", "store_mode", "system_backend"]);

    // 值落在临时 XDG 目录下的文件里，本机真正的凭据库没有多出东西（store_mode 是 file，系统后端不参与）
    const stored = join(xdg, "code-kit", "secrets", name);
    expect(existsSync(stored), `临时凭据库应有 ${stored}`).toBe(true);
    expect(readFileSync(stored, "utf8").trim()).toBe("fake-ui-secret-value-1234");
  });
});
