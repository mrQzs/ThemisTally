// 内核子进程的环境（桌面端 T5/T20、D04）：服务起的每一个内核子进程都拿不到决策 API 的 key（名字大写后相等就去掉，
// 大小写不同的写法也算），CODEKIT_ACTOR 是 user-ui，NoDefaultCurrentDirectoryInExePath 在；不设 PYTHONUTF8=1
// （核实结论：内核的四个 main 都把 stdout 重配成 UTF-8）。替身只报告「有没有这个 key」「CODEKIT_ACTOR 的值」
// 「有没有 NoDefaultCurrentDirectoryInExePath」，不输出任何变量的值。
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { readReport, startApp, type StartedApp } from "./support.ts";

let started: StartedApp | null = null;
let lowered = false;

beforeEach(() => {
  // 大小写不同的写法也要去掉（M18）：钉住服务起的每一个内核子进程
  process.env["typesafe_api_key"] = "not-a-real-key";
  lowered = true;
});

afterEach(async () => {
  if (lowered) delete process.env["typesafe_api_key"];
  await started?.dispose();
  started = null;
});

describe("内核子进程的环境", () => {
  it("每一条路由起的子进程都没有 TYPESAFE_API_KEY、CODEKIT_ACTOR 是 user-ui、NoDefaultCurrentDirectoryInExePath 在", async () => {
    started = await startApp();
    for (const target of ["/api/v1/meta", "/api/v1/status", "/api/v1/attempts", "/api/v1/config", "/api/v1/profiles", "/api/v1/secrets"]) {
      const response = await started.get(target);
      expect(response.status, target).toBe(200);
    }
    const lines = readReport(started.report).filter((line) => line.event === "begin");
    // meta、status、attempts、config、profiles 各一次，合成的 /secrets 四次（config show、profile show、两条 secret check）
    expect(lines.length).toBeGreaterThanOrEqual(9);
    for (const line of lines) {
      expect(line.has_typesafe_api_key, `argv ${line.argv.join(" ")}`).toBe(false);
      expect(line.codekit_actor).toBe("user-ui");
      expect(line.has_no_cwd_in_path).toBe(true);
    }
    // /secrets 是编排：config show、config profile show 与逐条 config secret check 都起了子进程
    const secretsArgvs = readReport(started.report)
      .filter((line) => line.event === "begin")
      .map((line) => line.argv.join(" "));
    // /profiles 与合成的 /secrets 都跑 config profile show：两处都拿不到这把 key
    expect(secretsArgvs.filter((item) => item === "config profile show --json").length).toBeGreaterThanOrEqual(1);
    expect(secretsArgvs.filter((item) => item.startsWith("config secret check ")).length).toBe(2);
    // /api/v1/config 与合成的 /secrets 都跑 config show：两处都拿不到这把 key
  });
});
