// 写链路的真内核端到端（桌面端 §5.3、D14/D15、U6b/U7/U8/U20/U15）：起真的服务（Bun）与真内核（scripts/pi_dispatch.py），
// 在 git 夹具仓库上跑预览与执行。夹具仓库用 .gitignore 忽略 .agent/，先经 CLI 登记一个 runtime 与一个 profile，再经界面
// 预览/执行 role.set。客户端在 Node 一侧发原始 HTTP；收进程靠关 stdin 与 kill，不发控制台信号。
import { spawnSync, type SpawnSyncReturns } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
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
  dir = mkdtempSync(join(tmpdir(), "themis-ui-write-real-"));
  repo = join(dir, "repo");
  assets = join(dir, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>real</title>\n");
  for (const args of [["init", "-q", repo], ["-C", repo, "config", "user.email", "ui@example.invalid"], ["-C", repo, "config", "user.name", "ui"]]) {
    const done = spawnSync("git", args, { encoding: "utf8" });
    if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  }
  writeFileSync(join(repo, "README.md"), "# 夹具仓库\n");
  writeFileSync(join(repo, ".gitignore"), ".agent/\n"); // 忽略 .agent/：本机文件与审计才写得进去
  spawnSync("git", ["-C", repo, "add", "-A"], { encoding: "utf8" });
  spawnSync("git", ["-C", repo, "commit", "-q", "-m", "init"], { encoding: "utf8" });
  // 预备：登记一个 runtime 与一个 profile（claude-code 本轮不接通 execution，R4 的 WARN 靠它）
  const runtime = cli("config", "runtime", "add", "demo-runtime", "--adapter", "claude-code", "--command", '["claude"]');
  if (runtime.status !== 0) throw new Error(`runtime add 失败：${runtime.stderr}`);
  const profile = cli("config", "profile", "add", "demo-profile", "--runtime", "demo-runtime", "--model", "anthropic/claude-x");
  if (profile.status !== 0) throw new Error(`profile add 失败：${profile.stderr}`);
});

afterEach(() => {
  service?.kill();
  service = null;
  if (dir !== "") rmSync(dir, { recursive: true, force: true });
  dir = "";
});

/** 起真的服务并经引导地址拿会话 cookie。 */
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

async function preview(role: string, target: string): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await request(
    (service as RunningService).port,
    "POST",
    "/api/v1/preview",
    postHeaders(),
    Buffer.from(JSON.stringify({ action: "role.set", args: { role, target } })),
  );
  return { status: res.status, body: JSON.parse(res.body.toString("utf8")) as Record<string, unknown> };
}

async function execute(role: string, target: string, confirmation: string): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await request(
    (service as RunningService).port,
    "POST",
    `/api/v1/roles/${role}`,
    postHeaders(),
    Buffer.from(JSON.stringify({ target, confirmation })),
  );
  return { status: res.status, body: JSON.parse(res.body.toString("utf8")) as Record<string, unknown> };
}

async function getOperation(id: string): Promise<Record<string, unknown>> {
  const res = await request((service as RunningService).port, "GET", `/api/v1/operations/${id}`, [["Cookie", cookie]]);
  expect(res.status).toBe(200);
  return JSON.parse(res.body.toString("utf8")) as Record<string, unknown>;
}

/** 审计的最后一条（config history --json）。 */
function lastAudit(): Record<string, unknown> {
  const history = cli("config", "history", "--json");
  expect(history.status).toBe(0);
  const entries = (JSON.parse(history.stdout) as Record<string, unknown>)["entries"] as unknown[];
  return entries[entries.length - 1] as Record<string, unknown>;
}

/** 建一个 RUNNING 的 attempt（A4：只需目录与 state.json）。 */
function makeRunningAttempt(): void {
  const attempt = join(repo, ".agent", "runs", "demo-task", "attempt-001");
  mkdirSync(attempt, { recursive: true });
  writeFileSync(join(attempt, "state.json"), JSON.stringify({ state: "RUNNING" }) + "\n");
}

/** .agent/ 之下的全部文件快照（相对路径 → base64 字节），供 R1/R5 的逐字节比对。 */
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

describe("R1（U6b）：预览后用 CLI 改配置再执行 → 409、exit_code 4、配置与审计逐字节不变、操作 stale", () => {
  it("同一个确认号在配置被改过之后执行 → 409 stale", async () => {
    await open();
    const previewed = await preview("execution", "demo-profile");
    expect(previewed.status).toBe(200);
    const confirmation = data(previewed.body)["confirmation"] as string;
    // 用 CLI 写一次配置：state 令牌随之失效
    const set = cli("config", "set", "kill_grace_seconds", "20");
    expect(set.status, set.stderr).toBe(0);
    const before = snapshotAgent();
    const executed = await execute("execution", "demo-profile", confirmation);
    expect(executed.status, "退出 4 转 409").toBe(409);
    expect(executed.body["exit_code"]).toBe(4);
    expect(executed.body["ok"]).toBe(false);
    expect(snapshotAgent(), "配置与审计逐字节不变（409 什么也没写）").toEqual(before);
    const op = await getOperation(confirmation);
    expect(op["state"]).toBe("stale");
  });
});

describe("R2（U7）：经界面执行的审计 actor 是 user-ui、confirmation 是 none；改 execution 绑定且 attempt 在跑 → needs_yes、带 --yes、confirmation 是 flag", () => {
  it("audit 记 user-ui/none；attempt 在跑时改 contract 绑定 → needs_yes 为真、执行带 --yes、confirmation 是 flag", async () => {
    await open();
    const p1 = await preview("execution", "demo-profile");
    const c1 = data(p1.body)["confirmation"] as string;
    expect((await execute("execution", "demo-profile", c1)).status).toBe(200);
    const entry1 = lastAudit();
    expect(entry1["actor"], "经本机服务起的写命令审计 actor 是 user-ui").toBe("user-ui");
    expect(entry1["confirmation"], "没有 attempt 在跑：confirmation 是 none").toBe("none");

    makeRunningAttempt(); // 建 RUNNING 的 attempt
    const p2 = await preview("contract", "demo-profile"); // 改 contract 的绑定（manual → headless）
    expect((data(p2.body)["preview"] as Record<string, unknown>)["needs_yes"], "attempt 在跑且改绑定：needs_yes 为真").toBe(true);
    const c2 = data(p2.body)["confirmation"] as string;
    expect((await execute("contract", "demo-profile", c2)).status).toBe(200);
    expect(lastAudit()["confirmation"], "带了 --yes：confirmation 是 flag").toBe("flag");
  });
});

describe("R3（U8）：先预览再建 RUNNING 的 attempt 再执行 → 内核退出 1、提示里有 --yes、配置不变、操作 failed/exit", () => {
  it("预览时没有 attempt（needs_yes 假）→ 建 attempt 后执行 → 内核要求 --yes、退出 1", async () => {
    await open();
    const previewed = await preview("execution", "demo-profile");
    expect((data(previewed.body)["preview"] as Record<string, unknown>)["needs_yes"]).toBe(false);
    const confirmation = data(previewed.body)["confirmation"] as string;
    const configPath = join(repo, ".agent", "dispatch.config.json");
    const before = readFileSync(configPath);
    makeRunningAttempt();
    const executed = await execute("execution", "demo-profile", confirmation);
    expect(executed.status, "退出 1 仍回 200").toBe(200);
    expect(executed.body["ok"]).toBe(false);
    expect(JSON.stringify(executed.body["messages"]), "提示里有 --yes").toContain("--yes");
    expect(readFileSync(configPath), "没写进任何东西").toEqual(before);
    const op = await getOperation(confirmation);
    expect(op["state"]).toBe("failed");
    expect(op["reason"]).toBe("exit");
  });
});

describe("R4（U20）：绑到没接通这个角色的适配器 → output 里有那条 WARN、ok 为真", () => {
  it("execution 绑到 claude-code（本轮不接通 execution）→ WARN 进 output、退出 0", async () => {
    await open();
    const previewed = await preview("execution", "demo-profile");
    const confirmation = data(previewed.body)["confirmation"] as string;
    const executed = await execute("execution", "demo-profile", confirmation);
    expect(executed.status).toBe(200);
    expect(executed.body["ok"], "只是 WARN，退出 0").toBe(true);
    const output = executed.body["output"] as string[];
    expect(output.some((line) => line.startsWith("WARN") && line.includes("claude-code")), "output 里有那条 WARN").toBe(true);
  });
});

describe("R5（U15）：预览前后 .agent/ 逐字节不变（预览不写任何文件）", () => {
  it("预览之后 .agent/ 一个字节都没动", async () => {
    await open();
    const before = snapshotAgent();
    const previewed = await preview("execution", "demo-profile");
    expect(previewed.status).toBe(200);
    expect(data(previewed.body)["confirmation"], "预览成功签发了确认号").toMatch(/^[A-Za-z0-9_-]{43}$/u);
    expect(snapshotAgent(), "预览前后 .agent/ 逐字节不变").toEqual(before);
  });
});
