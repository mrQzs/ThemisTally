// 真内核上的跟随（桌面端 §5.3、D13，T018 第 4 片）：起真的服务（Bun）与真内核（scripts/pi_dispatch.py），
// 在真实增长的 events.jsonl 上核对「只给已经写完的行」：半行不给（内核的 --complete-lines），补上换行之后给且
// 只给一次，追加接着给，截短回 409 且句柄被丢掉；每一步的 data 都带 poll_after_ms（2000）。一行超过一页时按
// part/parts 分片接着给。另起一条 describe 用内核自己的 kit_logs.build_parser() 解析 FOLLOW_ARGV 的两条
// （不并进 argv-templates.test.ts 那个既有文件）。客户端在 Node 一侧发原始 HTTP；收进程靠关 stdin 与 kill。
import { spawnSync } from "node:child_process";
import { appendFileSync, mkdirSync, mkdtempSync, rmSync, truncateSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, beforeEach, describe, expect, it } from "vitest";
import { FOLLOW_ARGV } from "../src/readroutes.ts";
import { type RunningService, REPO_ROOT, header, request, startService } from "./harness.ts";

const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const KERNEL = join(REPO_ROOT, "scripts", "pi_dispatch.py");
const SCRIPTS = join(REPO_ROOT, "scripts");

let dir = "";
let repo = "";
let assets = "";
let service: RunningService | null = null;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-follow-real-"));
  repo = join(dir, "repo");
  assets = join(dir, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>follow real</title>\n");
  for (const args of [["init", "-q", repo], ["-C", repo, "config", "user.email", "ui@example.invalid"], ["-C", repo, "config", "user.name", "ui"]]) {
    const done = spawnSync("git", args, { encoding: "utf8" });
    if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  }
  writeFileSync(join(repo, "README.md"), "# 夹具仓库\n");
  const added = spawnSync("git", ["-C", repo, "add", "-A"], { encoding: "utf8" });
  if (added.status !== 0) throw new Error(`git add 失败：${added.stderr}`);
  const committed = spawnSync("git", ["-C", repo, "commit", "-q", "-m", "init"], { encoding: "utf8" });
  if (committed.status !== 0) throw new Error(`git commit 失败：${committed.stderr}`);
  mkdirSync(join(repo, ".agent", "runs", "demo-task", "attempt-001"), { recursive: true });
});

afterEach(() => {
  service?.kill();
  service = null;
});

afterAll(() => {
  rmSync(dir, { recursive: true, force: true });
});

/** 起真的服务（真内核 scripts/pi_dispatch.py）。 */
async function open(): Promise<RunningService> {
  service = await startService({ repo, assets, python: PYTHON, kernel: KERNEL, entry: "overrides", overrides: {} });
  return service;
}

const sessionOf = async (running: RunningService): Promise<string> => {
  const nonce = running.handshake.bootstrap.split("/").pop() ?? "";
  const booted = await request(running.port, "GET", `/bootstrap/${nonce}`);
  expect(booted.status).toBe(302);
  return (header(booted, "set-cookie") ?? "").split(";")[0] ?? "";
};

const envelopeOf = (body: Buffer): Record<string, unknown> => JSON.parse(body.toString("utf8")) as Record<string, unknown>;

/** 证据文件（只靠文件大小与内容判定，不靠修改时间）。 */
const evidence = (): string => join(repo, ".agent", "runs", "demo-task", "attempt-001", "events.jsonl");

/** 一次跟随请求（不带游标或带上一步发回来的句柄）。 */
const follow = async (running: RunningService, cookie: string, cursor?: string): Promise<Record<string, unknown>> => {
  const target = `/api/v1/attempts/demo-task/attempt-001/file?path=events.jsonl&follow=1${cursor === undefined ? "" : `&cursor=${cursor}`}`;
  const response = await request(running.port, "GET", target, [["Cookie", cookie]]);
  return { status: response.status, envelope: envelopeOf(response.body) };
};

const page = (result: Record<string, unknown>): Record<string, unknown> => (result["envelope"] as Record<string, unknown>)["data"] as Record<string, unknown>;

/** 内核自己的解析器解析一条跟随的 argv（剥掉组名 logs）。 */
function parseWithKernel(argv: readonly string[]): { status: number; stdout: string; stderr: string } {
  const program = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(SCRIPTS)})`,
    "import kit_logs",
    "argv = json.loads(sys.argv[1])",
    "args = kit_logs.build_parser().parse_args(argv[1:])", // 剥掉组名 logs
    "sys.stdout.write(json.dumps({'json': bool(args.json), 'complete_lines': bool(args.complete_lines), 'cursor': args.cursor}))",
  ].join("\n");
  const done = spawnSync(PYTHON, ["-c", program, JSON.stringify([...argv])], { encoding: "utf8", timeout: 120_000 });
  return { status: done.status ?? -1, stdout: done.stdout ?? "", stderr: done.stderr ?? "" };
}

describe("FOLLOW_ARGV 过内核真正的解析器（R1）", () => {
  it("两条都解析成功，json 与 complete_lines 都为真，--cursor= 排在最后", () => {
    for (const name of ["api.attempts.file.follow", "api.attempts.file.follow.cursor"]) {
      const argv = FOLLOW_ARGV[name];
      expect(argv, name).toBeDefined();
      const done = parseWithKernel(argv as readonly string[]);
      expect(done.status, `${name}（${(argv as readonly string[]).join(" ")}）解析失败：${done.stderr.slice(0, 400)}`).toBe(0);
      const parsed = JSON.parse(done.stdout) as Record<string, unknown>;
      expect(parsed["json"], `${name} 应带 --json`).toBe(true);
      expect(parsed["complete_lines"], `${name} 应带 --complete-lines`).toBe(true);
      const expected = name === "api.attempts.file.follow.cursor" ? "fake-cursor-0001" : null;
      expect(parsed["cursor"], `${name} 的游标`).toBe(expected);
    }
  });
});

describe("真实增长的 events.jsonl（R2）", () => {
  it("半行不给、补上换行只给一次、追加接着给、截短回 409 且句柄被丢", async () => {
    const running = await open();
    const cookie = await sessionOf(running);
    const file = evidence();
    // 第 1 行写完、第 2 行是半行（跟随时内核整行不给）
    writeFileSync(file, '{"a": 1}\n{"b": 2', "utf8");

    const first = await follow(running, cookie);
    expect(first["status"]).toBe(200);
    expect(page(first)["lines"]).toEqual([{ n: 1, text: '{"a": 1}' }]);
    expect(page(first)["done"]).toBe(false);
    expect(page(first)["poll_after_ms"]).toBe(2000);
    const h1 = page(first)["next_cursor"] as string;
    expect(h1).toMatch(/^[A-Za-z0-9_-]{43}$/u);

    // 半行还在写：空页，句柄原样发回来（句柄表项数不变）
    const second = await follow(running, cookie, h1);
    expect(second["status"]).toBe(200);
    expect(page(second)["lines"]).toEqual([]);
    expect(page(second)["next_cursor"]).toBe(h1);
    expect(page(second)["poll_after_ms"]).toBe(2000);

    // 补上换行：第 2 行只给一次，done 为真也发句柄
    appendFileSync(file, "}\n", "utf8");
    const third = await follow(running, cookie, h1);
    expect(third["status"]).toBe(200);
    expect(page(third)["lines"]).toEqual([{ n: 2, text: '{"b": 2}' }]);
    expect(page(third)["done"]).toBe(true);
    expect(page(third)["poll_after_ms"]).toBe(2000);
    const h2 = page(third)["next_cursor"] as string;
    expect(h2).toMatch(/^[A-Za-z0-9_-]{43}$/u);

    // 没有新内容：空页，句柄不变（b 只给一次）
    const fourth = await follow(running, cookie, h2);
    expect(fourth["status"]).toBe(200);
    expect(page(fourth)["lines"]).toEqual([]);
    expect(page(fourth)["next_cursor"]).toBe(h2);
    expect(page(fourth)["poll_after_ms"]).toBe(2000);

    // 再追加一行：接着给
    appendFileSync(file, '{"c": 3}\n', "utf8");
    const fifth = await follow(running, cookie, h2);
    expect(fifth["status"]).toBe(200);
    expect(page(fifth)["lines"]).toEqual([{ n: 3, text: '{"c": 3}' }]);
    expect(page(fifth)["done"]).toBe(true);
    expect(page(fifth)["poll_after_ms"]).toBe(2000);
    const h3 = page(fifth)["next_cursor"] as string;

    // 截短：内核报「游标对应的文件已变化」→ 409 并丢掉这个句柄；再用它还是 409
    truncateSync(file, Buffer.byteLength('{"a": 1}\n', "utf8"));
    const sixth = await follow(running, cookie, h3);
    expect(sixth["status"]).toBe(409);
    expect((sixth["envelope"] as Record<string, unknown>)["messages"]).toEqual(["ERROR: 游标无效或文件已变化，请从头读取"]);
    const seventh = await follow(running, cookie, h3);
    expect(seventh["status"]).toBe(409);

    // 不带游标：从头给
    const eighth = await follow(running, cookie);
    expect(eighth["status"]).toBe(200);
    expect(page(eighth)["lines"]).toEqual([{ n: 1, text: '{"a": 1}' }]);
    expect(page(eighth)["poll_after_ms"]).toBe(2000);
  });
});

describe("一行超过一页（R3）", () => {
  it("第 1 页 part 1/2、第 2 页 part 2/2 且 done 为真、第 3 页空且句柄不变", async () => {
    const running = await open();
    const cookie = await sessionOf(running);
    const big = "x".repeat(300 * 1024); // 大于 SAFE_PAGE_CHARS（256 KiB 个字符）
    const dumped = `{"big": ${JSON.stringify(big)}}`;
    writeFileSync(join(evidence()), `${JSON.stringify({ big })}\n`, "utf8");

    const first = await follow(running, cookie);
    expect(first["status"]).toBe(200);
    const firstLines = page(first)["lines"] as Record<string, unknown>[];
    expect(firstLines).toHaveLength(1);
    expect(firstLines[0]?.["part"]).toBe(1);
    expect(firstLines[0]?.["parts"]).toBe(2);
    expect(firstLines[0]?.["text"]).toBe(dumped.slice(0, 262144));
    expect(page(first)["done"]).toBe(false);
    expect(page(first)["poll_after_ms"]).toBe(2000);
    const h1 = page(first)["next_cursor"] as string;

    const second = await follow(running, cookie, h1);
    expect(second["status"]).toBe(200);
    const secondLines = page(second)["lines"] as Record<string, unknown>[];
    expect(secondLines).toHaveLength(1);
    expect(secondLines[0]?.["part"]).toBe(2);
    expect(secondLines[0]?.["parts"]).toBe(2);
    expect(secondLines[0]?.["text"]).toBe(dumped.slice(262144));
    expect(page(second)["done"]).toBe(true);
    expect(page(second)["poll_after_ms"]).toBe(2000);
    const h2 = page(second)["next_cursor"] as string;

    const third = await follow(running, cookie, h2);
    expect(third["status"]).toBe(200);
    expect(page(third)["lines"]).toEqual([]);
    expect(page(third)["next_cursor"]).toBe(h2);
    expect(page(third)["poll_after_ms"]).toBe(2000);
  });
});
