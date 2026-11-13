// T031 的真内核端到端（桌面端 §5.3、D08/D09、U6b/U7/U9）：起真的服务（Bun）与真内核（scripts/pi_dispatch.py），在 git 夹具
// 仓库上经界面读岗位绑定（U9 逐字段一致）、经预览加确认号执行一次 hub set（U7 审计 actor 是 user-ui）、预览之后配置被别的
// 进程改过再执行回 409/stale（U6b）、以及内核整份校验拒掉不许的绑定。夹具仓库用 .gitignore 忽略 .agent/，先经 CLI 登记一个
// pi 的 runtime 与 profile。客户端在 Node 一侧发原始 HTTP；收进程靠关 stdin 与 kill，不发控制台信号。
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
  dir = mkdtempSync(join(tmpdir(), "themis-ui-hub-real-"));
  repo = join(dir, "repo");
  assets = join(dir, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>hub-real</title>\n");
  for (const args of [["init", "-q", repo], ["-C", repo, "config", "user.email", "ui@example.invalid"], ["-C", repo, "config", "user.name", "ui"]]) {
    const done = spawnSync("git", args, { encoding: "utf8" });
    if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  }
  writeFileSync(join(repo, "README.md"), "# 夹具仓库\n");
  writeFileSync(join(repo, ".gitignore"), ".agent/\n");
  spawnSync("git", ["-C", repo, "add", "-A"], { encoding: "utf8" });
  spawnSync("git", ["-C", repo, "commit", "-q", "-m", "init"], { encoding: "utf8" });
  // 预备：登记一个 pi 的 runtime 与 profile（hub set 引用它；pi 允许用在 contract/gate/audit/exec/coordinator）
  const runtime = cli("config", "runtime", "add", "demo-runtime", "--adapter", "pi");
  if (runtime.status !== 0) throw new Error(`runtime add 失败：${runtime.stderr}`);
  const profile = cli("config", "profile", "add", "ui-profile", "--runtime", "demo-runtime", "--model", "anthropic/claude-x");
  if (profile.status !== 0) throw new Error(`profile add 失败：${profile.stderr}`);
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

describe("U9：GET /api/v1/hub/roles 与 config hub show --json 逐字段相等", () => {
  it("六个岗位逐行比：缺省行与配置行的十个字段加 fallback 子字段都一致", async () => {
    await open();
    // 经 CLI 给 exec 配一个绑定：读路由同时覆盖配置行（exec）与缺省行（其余五个）
    const set = cli("config", "hub", "set", "exec", "ui-profile");
    expect(set.status, set.stderr).toBe(0);
    const shown = await getJson("/api/v1/hub/roles");
    const posts = data(shown)["posts"] as Record<string, unknown>[];
    const direct = cli("config", "hub", "show", "--json");
    expect(direct.status, direct.stderr).toBe(0);
    const directPosts = (JSON.parse(direct.stdout) as Record<string, unknown>)["posts"] as Record<string, unknown>[];
    // 逐字段相等（整份 data 与内核输出一致，白名单对合法值不作改动）
    expect(data(shown)).toEqual(JSON.parse(direct.stdout) as Record<string, unknown>);
    expect(posts).toHaveLength(6);
    // 配置行 exec：source=config、profile 是新值、adapter 由 runtime 解析出 pi
    const exec = posts.find((row) => row["post"] === "exec");
    expect(exec?.["source"]).toBe("config");
    expect(exec?.["profile"]).toBe("ui-profile");
    expect(exec?.["runtime"]).toBe("demo-runtime");
    expect(exec?.["adapter"]).toBe("pi");
    expect(exec?.["provider"]).toBe("anthropic");
    expect(exec?.["model"]).toBe("claude-x");
    // 缺省行 coordinator：profile/runtime 为 null、provider 非空、fallback 是四键对象；planner 的 provider 是 null
    const coordinator = posts.find((row) => row["post"] === "coordinator");
    expect(coordinator?.["source"]).toBe("default");
    expect(coordinator?.["profile"]).toBeNull();
    expect(coordinator?.["runtime"]).toBeNull();
    expect(coordinator?.["provider"]).toBe("deepseek");
    expect((coordinator?.["fallback"] as Record<string, unknown>)["model"]).toBe("deepseek-flash");
    const planner = posts.find((row) => row["post"] === "planner");
    expect(planner?.["provider"]).toBeNull();
    expect(planner?.["fallback"]).toBeNull();
    expect(directPosts).toHaveLength(6);
  });
});

describe("U7：经本机服务执行 hub set，审计 actor 是 user-ui，再读能看到 source=config", () => {
  it("预览加确认号执行 hub set 回 200，审计 actor 是 user-ui，岗位绑定生效", async () => {
    await open();
    const previewed = await preview("hub.set", { post: "contract", profile: "ui-profile" });
    expect(previewed.status).toBe(200);
    const confirmation = data(previewed.body)["confirmation"] as string;
    const executed = await execute("/api/v1/hub/roles/contract", { profile: "ui-profile", confirmation });
    expect(executed.status).toBe(200);
    expect(executed.body["ok"]).toBe(true);
    expect(lastAudit()["actor"], "经本机服务起的写命令审计 actor 是 user-ui").toBe("user-ui");
    const shown = await getJson("/api/v1/hub/roles");
    const contract = (data(shown)["posts"] as Record<string, unknown>[]).find((row) => row["post"] === "contract");
    expect(contract?.["source"], "执行之后 source 变成 config").toBe("config");
    expect(contract?.["profile"]).toBe("ui-profile");
  });
});

describe("U6b：预览之后配置被别的进程改过 → 执行 409、exit_code 4、操作 stale、配置与审计逐字节不变", () => {
  it("预览后用 CLI 改配置 → 执行 409、exit_code 4、snapshot 不变、操作 stale", async () => {
    await open();
    const previewed = await preview("hub.set", { post: "exec", profile: "ui-profile" });
    expect(previewed.status).toBe(200);
    const confirmation = data(previewed.body)["confirmation"] as string;
    // 用 CLI 改配置（写另一个岗位）：state 令牌随之失效
    const other = cli("config", "hub", "set", "gate", "ui-profile");
    expect(other.status, other.stderr).toBe(0);
    const before = snapshotAgent();
    const executed = await execute("/api/v1/hub/roles/exec", { profile: "ui-profile", confirmation });
    expect(executed.status, "退出 4 转 409").toBe(409);
    expect(executed.body["exit_code"]).toBe(4);
    expect(executed.body["ok"]).toBe(false);
    expect(snapshotAgent(), "配置与审计逐字节不变（409 什么也没写）").toEqual(before);
    const op = await getJson(`/api/v1/operations/${confirmation}`);
    expect(op["state"]).toBe("stale");
  });
});

describe("不许的绑定：内核整份校验拒掉，信封 ok=false、配置不变", () => {
  it("适配器不能用在这个岗位（planner 只许 claude-code，绑 pi）→ 预览 ok=false、messages 是内核原文、配置不变", async () => {
    await open();
    const before = snapshotAgent();
    const previewed = await preview("hub.set", { post: "planner", profile: "ui-profile" });
    expect(previewed.status, "内核退出非 0 也回 200").toBe(200);
    expect(previewed.body["ok"]).toBe(false);
    const messages = (previewed.body["messages"] as unknown[]) ?? [];
    expect(messages.some((line) => String(line).includes("不能用在") && String(line).includes("planner")), `messages 应含内核原文：${JSON.stringify(messages)}`).toBe(true);
    expect(data(previewed.body)?.["confirmation"], "不许的绑定不发确认号").toBeUndefined();
    expect(snapshotAgent(), "预览不写配置与审计").toEqual(before);
  });

  it("绑一个没登记的 profile → 预览 ok=false、messages 含「没有登记」、配置不变", async () => {
    await open();
    const before = snapshotAgent();
    const previewed = await preview("hub.set", { post: "exec", profile: "no-such-profile" });
    expect(previewed.status).toBe(200);
    expect(previewed.body["ok"]).toBe(false);
    const messages = (previewed.body["messages"] as unknown[]) ?? [];
    expect(messages.some((line) => String(line).includes("没有登记")), `messages 应含「没有登记」：${JSON.stringify(messages)}`).toBe(true);
    expect(snapshotAgent(), "预览不写配置与审计").toEqual(before);
  });
});
