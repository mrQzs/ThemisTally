// T020 的真内核端到端（桌面端 §5.3、D01/D14、U6b/U7/U22）：起真的服务（Bun）与真内核（scripts/pi_dispatch.py），在 git 夹具
// 仓库上经界面跑 profile add|edit 与 runtime add|remove。夹具仓库用 .gitignore 忽略 .agent/，先经 CLI 登记一个 runtime。
// 客户端在 Node 一侧发原始 HTTP；收进程靠关 stdin 与 kill，不发控制台信号。
import { spawnSync, type SpawnSyncReturns } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { type RunningService, REPO_ROOT, header, request, startService } from "./harness.ts";

const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const KERNEL = join(REPO_ROOT, "scripts", "pi_dispatch.py");

let dir = "";
let repo = "";
let assets = "";
let service: RunningService | null = null;
let cookie = "";

/** 经 CLI 直接跑内核（夹具仓库的预备与审计读取用）。 */
function cli(...args: string[]): SpawnSyncReturns<string> {
  return spawnSync(PYTHON, [KERNEL, "--repo", repo, ...args], { encoding: "utf8", timeout: 120_000 });
}

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-write-real-cfg-"));
  repo = join(dir, "repo");
  assets = join(dir, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>real-cfg</title>\n");
  for (const args of [["init", "-q", repo], ["-C", repo, "config", "user.email", "ui@example.invalid"], ["-C", repo, "config", "user.name", "ui"]]) {
    const done = spawnSync("git", args, { encoding: "utf8" });
    if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  }
  writeFileSync(join(repo, "README.md"), "# 夹具仓库\n");
  writeFileSync(join(repo, ".gitignore"), ".agent/\n");
  spawnSync("git", ["-C", repo, "add", "-A"], { encoding: "utf8" });
  spawnSync("git", ["-C", repo, "commit", "-q", "-m", "init"], { encoding: "utf8" });
  // 预备：登记一个 runtime（profile add/edit 引用它）；不带 command，只写配置
  const runtime = cli("config", "runtime", "add", "demo-runtime", "--adapter", "pi");
  if (runtime.status !== 0) throw new Error(`runtime add 失败：${runtime.stderr}`);
});

afterEach(() => {
  service?.kill();
  service = null;
  if (dir !== "") rmSync(dir, { recursive: true, force: true });
  dir = "";
});

async function open(): Promise<void> {
  service = await startService({ repo, assets, python: PYTHON, kernel: KERNEL, entry: "overrides", overrides: {} });
  const nonce = service.handshake.bootstrap.split("/").pop() ?? "";
  const booted = await request(service.port, "GET", `/bootstrap/${nonce}`);
  expect(booted.status).toBe(302);
  cookie = (header(booted, "set-cookie") ?? "").split(";")[0] ?? "";
}

function postHeaders(): [string, string][] {
  const port = (service as RunningService).port;
  return [["Cookie", cookie], ["Origin", `http://127.0.0.1:${port}`], ["X-Themis-UI", "1"], ["Content-Type", "application/json"]];
}

async function preview(action: string, args: Record<string, unknown>): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await request((service as RunningService).port, "POST", "/api/v1/preview", postHeaders(), Buffer.from(JSON.stringify({ action, args })));
  return { status: res.status, body: JSON.parse(res.body.toString("utf8")) as Record<string, unknown> };
}

async function execute(path: string, body: Record<string, unknown>): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await request((service as RunningService).port, "POST", path, postHeaders(), Buffer.from(JSON.stringify(body)));
  return { status: res.status, body: JSON.parse(res.body.toString("utf8")) as Record<string, unknown> };
}

async function getJson(path: string): Promise<Record<string, unknown>> {
  const res = await request((service as RunningService).port, "GET", path, [["Cookie", cookie]]);
  expect(res.status).toBe(200);
  return JSON.parse(res.body.toString("utf8")) as Record<string, unknown>;
}

function lastAudit(): Record<string, unknown> {
  const history = cli("config", "history", "--json");
  expect(history.status).toBe(0);
  const entries = (JSON.parse(history.stdout) as Record<string, unknown>)["entries"] as unknown[];
  return entries[entries.length - 1] as Record<string, unknown>;
}

/** .agent/ 之下的全部文件快照（相对路径 → base64 字节），供逐字节比对。 */
function snapshotAgent(): Record<string, string> {
  const out: Record<string, string> = {};
  const root = join(repo, ".agent");
  const walk = (rel: string): void => {
    for (const name of readdirSync(join(root, rel))) {
      const childRel = rel === "" ? name : `${rel}/${name}`;
      const childAbs = join(root, childRel);
      if (statSync(childAbs).isDirectory()) walk(childRel);
      else out[childRel] = readFileSync(childAbs).toString("base64");
    }
  };
  if (existsSync(root)) walk("");
  return out;
}

const data = (body: Record<string, unknown>): Record<string, unknown> => body["data"] as Record<string, unknown>;

describe("C1（a）：profile add 经界面预览加执行，审计 actor 是 user-ui", () => {
  it("profile add 成功，审计 actor 是 user-ui", async () => {
    await open();
    const previewed = await preview("profile.add", { profile: "ui-profile", runtime: "demo-runtime", model: "anthropic/claude-x" });
    expect(previewed.status).toBe(200);
    const confirmation = data(previewed.body)["confirmation"] as string;
    const executed = await execute("/api/v1/profiles/ui-profile/add", { runtime: "demo-runtime", model: "anthropic/claude-x", confirmation });
    expect(executed.status).toBe(200);
    expect(executed.body["ok"]).toBe(true);
    expect(lastAudit()["actor"], "经本机服务起的写命令审计 actor 是 user-ui").toBe("user-ui");
    const shown = cli("config", "profile", "show", "ui-profile", "--json");
    expect(shown.status).toBe(0);
    const rows = (JSON.parse(shown.stdout) as Record<string, unknown>)["profiles"] as { id: string }[];
    expect(rows.some((row) => row.id === "ui-profile")).toBe(true);
  });
});

describe("C2（b）：runtime add --command 的 U6b——改本机文件后执行回 409、操作 stale、文件逐字节不变", () => {
  it("预览后用 CLI 改 .agent/dispatch.local.json → 执行 409、exit_code 4、snapshot 不变、操作 stale", async () => {
    await open();
    const previewed = await preview("runtime.add", { runtime: "cmd-runtime", adapter: "pi", command: ["C:/tools/pi.exe"] });
    expect(previewed.status).toBe(200);
    const confirmation = data(previewed.body)["confirmation"] as string;
    // 用 CLI 改 .agent/dispatch.local.json（连带改配置）：state 令牌随之失效
    const other = cli("config", "runtime", "add", "other-rt", "--adapter", "pi", "--command", '["C:/other.exe"]');
    expect(other.status, other.stderr).toBe(0);
    const before = snapshotAgent();
    const executed = await execute("/api/v1/runtimes/cmd-runtime/add", { adapter: "pi", command: ["C:/tools/pi.exe"], confirmation });
    expect(executed.status, "退出 4 转 409").toBe(409);
    expect(executed.body["exit_code"]).toBe(4);
    expect(executed.body["ok"]).toBe(false);
    expect(snapshotAgent(), "两个文件与审计逐字节不变（409 什么也没写）").toEqual(before);
    const op = await getJson(`/api/v1/operations/${confirmation}`);
    expect(op["state"]).toBe("stale");
  });
});

describe("C3（c）：runtime add --command 成功，本机文件里的 command 与请求逐项相同（路径含反斜杠与空格）", () => {
  it("执行成功，dispatch.local.json 里 cmd-rt.command 逐项等于请求（MSVCRT 引号 round-trip）", async () => {
    await open();
    const command = ["C:\\a b\\pi.exe"];
    const previewed = await preview("runtime.add", { runtime: "cmd-rt", adapter: "pi", command });
    expect(previewed.status).toBe(200);
    const confirmation = data(previewed.body)["confirmation"] as string;
    const executed = await execute("/api/v1/runtimes/cmd-rt/add", { adapter: "pi", command, confirmation });
    expect(executed.status).toBe(200);
    expect(executed.body["ok"]).toBe(true);
    const local = JSON.parse(readFileSync(join(repo, ".agent", "dispatch.local.json"), "utf8")) as {
      runtimes: Record<string, { command?: string[] }>;
    };
    expect(local.runtimes["cmd-rt"]?.command, "本机文件里的 command 与请求逐项相同（含反斜杠与空格）").toEqual(command);
  });
});

describe("C4（d）：U22——读到的 credential_env 原样回填进 profile.edit，预览加执行都过", () => {
  it("GET /api/v1/profiles 读到的 credential_env 回填 profile.edit，配置里的值与提交的相同", async () => {
    await open();
    const seed = cli("config", "profile", "add", "seed-profile", "--runtime", "demo-runtime", "--model", "prov/mod", "--credential-env", "DEMO_KEY", "--credential-env", "OTHER_KEY");
    expect(seed.status, seed.stderr).toBe(0);
    const profiles = await getJson("/api/v1/profiles");
    const rows = data(profiles)["profiles"] as { id: string; credential_env: string[] }[];
    const row = rows.find((item) => item.id === "seed-profile");
    expect(row, "GET /api/v1/profiles 应读到 seed-profile").toBeDefined();
    const credentialEnv = row?.credential_env ?? [];
    expect(credentialEnv).toEqual(["DEMO_KEY", "OTHER_KEY"]);
    const previewed = await preview("profile.edit", { profile: "seed-profile", credential_env: credentialEnv });
    expect(previewed.status).toBe(200);
    const confirmation = data(previewed.body)["confirmation"] as string;
    const executed = await execute("/api/v1/profiles/seed-profile/edit", { credential_env: credentialEnv, confirmation });
    expect(executed.status).toBe(200);
    const shown = cli("config", "profile", "show", "seed-profile", "--json");
    expect(shown.status).toBe(0);
    const after = (JSON.parse(shown.stdout) as Record<string, unknown>)["profiles"] as { id: string; credential_env: string[] }[];
    expect(after.find((item) => item.id === "seed-profile")?.credential_env, "配置里的值与提交的相同").toEqual(credentialEnv);
  });
});

describe("C5：profile.edit 一个可选项都不给——服务照形状放行，组合规则交给内核", () => {
  it("预览回 200、ok 假、exit_code 2、提示「至少给一项」，不发确认号", async () => {
    await open();
    const seed = cli("config", "profile", "add", "seed-profile", "--runtime", "demo-runtime", "--model", "prov/mod");
    expect(seed.status, seed.stderr).toBe(0);
    // profile 是路径参数（算给过了），正文一个可选项都没有：服务照形状放行，由内核判定「至少给一项」
    const previewed = await preview("profile.edit", { profile: "seed-profile" });
    expect(previewed.status, "内核退出非 0 也回 200").toBe(200);
    expect(previewed.body["ok"]).toBe(false);
    expect(previewed.body["exit_code"]).toBe(2);
    const body = previewed.body["data"] as Record<string, unknown> | null;
    expect(body === null || body["confirmation"] === undefined, "不发确认号").toBe(true);
    const messages = (previewed.body["messages"] as unknown[]) ?? [];
    expect(messages.some((line) => String(line).includes("至少给一项")), `提示应含「至少给一项」：${JSON.stringify(messages)}`).toBe(true);
  });
});
