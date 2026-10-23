// 经启动器的端到端（桌面端 T6、D14、D15）：`python scripts/pi_dispatch.py ui --desktop --assets …` 起服务，stdout 仍
// 只有握手一行；关掉 stdin 之后启动器退出 0 且锁目录被清除。临时仓库用 git init 建（Repo.discover 拒绝 worktree），
// 锁目录落在临时仓库里。
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { REPO_ROOT, startServiceProcess } from "./harness.ts";

let dir = "";
let assets = "";
let repo = "";

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "themis-ui-e2e-"));
  assets = join(dir, "assets");
  mkdirSync(join(assets, "assets"), { recursive: true });
  writeFileSync(join(assets, "index.html"), "<!doctype html><title>e2e</title>\n");
  writeFileSync(join(assets, "assets", "app.js"), "// e2e\n");
  repo = join(dir, "repo");
  mkdirSync(repo, { recursive: true });
  const init = spawnSync("git", ["init", "-q", repo], { encoding: "utf8", timeout: 120_000 });
  if (init.status !== 0) throw new Error(`git init 失败：${init.stderr}`);
});

afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

describe("经启动器的端到端", () => {
  it("握手一行、关 stdin 退出 0、锁目录被清除", async () => {
    const launcher = process.env["THEMIS_PYTHON"] ?? "python";
    const service = await startServiceProcess(
      [launcher, join(REPO_ROOT, "scripts", "pi_dispatch.py"), "--repo", repo, "ui", "--desktop", "--assets", assets],
      REPO_ROOT,
      60_000,
    );
    try {
      expect(Object.keys(service.handshake)).toEqual(["themis_ui", "bootstrap", "origin", "control", "pid"]);
      const lines = service.stdout().split("\n").filter((line) => line.trim() !== "");
      expect(lines).toHaveLength(1);
      service.child.stdin?.end();
      const code = await new Promise<number | null>((done) => {
        const timer = setTimeout(() => done(null), 30_000);
        service.child.once("exit", (value) => {
          clearTimeout(timer);
          done(value);
        });
      });
      expect(code).toBe(0);
      expect(existsSync(join(repo, ".agent", ".ui.lock"))).toBe(false);
    } finally {
      service.child.kill();
    }
  }, 90_000);
});

import { existsSync } from "node:fs";
