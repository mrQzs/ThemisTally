// 二道脱敏在路由上的落地（桌面端 §5.3、D07、U5）：/config 与 /profiles 的白名单、messages 只留 ERROR/WARN 开头的
// 行且逐行过 redactSecrets、command 里的游标与 transcript 显示成占位符、file 路由（证据）不登记白名单但照样过
// redactJson。
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { envelopeOf, startApp, type StartedApp } from "./support.ts";

const TOKEN = "sk-abcdefghijklmnopqrstuvwxyz0123456789";

let started: StartedApp | null = null;
const setJson = (payload: unknown): void => {
  process.env["FAKE_KERNEL_JSON"] = JSON.stringify(payload);
};

beforeEach(() => {
  delete process.env["FAKE_KERNEL_JSON"];
  delete process.env["FAKE_KERNEL_STDERR"];
});

afterEach(async () => {
  delete process.env["FAKE_KERNEL_JSON"];
  delete process.env["FAKE_KERNEL_STDERR"];
  await started?.dispose();
  started = null;
});

describe("白名单在路由上的落地", () => {
  it("/config：环境变量名与枚举原样，令牌形状遮掉，file_dir 不出现", async () => {
    started = await startApp();
    setJson({
      decisions: {
        env_var_name: "TYPESAFE_API_KEY",
        secret: { name: "TYPESAFE_API_KEY", source: "env", store_mode: "system", system_backend: "windows-credential-manager", file_dir: "C:/secret/dir" },
      },
      keys: [{ key: "env_remove", value: ["KEEP_ONE", TOKEN] }],
    });
    const response = await started.get("/api/v1/config");
    expect(response.status).toBe(200);
    const body = await envelopeOf(response);
    expect(body["ok"]).toBe(true);
    const data = body["data"] as Record<string, unknown>;
    const decisions = data["decisions"] as Record<string, unknown>;
    const keys = data["keys"] as Record<string, unknown>[];
    expect(decisions["env_var_name"]).toBe("TYPESAFE_API_KEY");
    expect(decisions["secret"]).toMatchObject({ name: "TYPESAFE_API_KEY", source: "env", store_mode: "system" });
    expect(keys[0]?.["value"]).toEqual(["KEEP_ONE", "<redacted>"]);
    const raw = JSON.stringify(body);
    expect(raw).not.toContain("C:/secret/dir");
    expect(raw).not.toContain(TOKEN);
  });

  it("/profiles：credential_env 里的名字原样，令牌形状遮掉", async () => {
    started = await startApp();
    setJson({ profiles: [{ id: "execution", credential_env: ["TYPESAFE_API_KEY", TOKEN] }] });
    const response = await started.get("/api/v1/profiles");
    const data = (await envelopeOf(response))["data"] as Record<string, unknown>;
    const rows = data["profiles"] as Record<string, unknown>[];
    expect(rows[0]?.["credential_env"]).toEqual(["TYPESAFE_API_KEY", "<redacted>"]);
  });
});

describe("messages 与 command", () => {
  it("messages 只留 ERROR/WARN 开头的行，逐行过 redactSecrets", async () => {
    started = await startApp();
    process.env["FAKE_KERNEL_STDERR"] = [
      `ERROR: 起不来 api_key=${TOKEN}`,
      "WARN: 这把 key 不在环境变量里",
      "这一行不是 ERROR 也不是 WARN",
      "（未完：--cursor fake-cursor-0001）",
    ].join("\n");
    const response = await started.get("/api/v1/status");
    const body = await envelopeOf(response);
    const messages = body["messages"] as string[];
    expect(messages).toHaveLength(2);
    expect(messages[0]?.startsWith("ERROR: ")).toBe(true);
    expect(messages[0]).toContain("<redacted>");
    expect(messages[0]).not.toContain(TOKEN);
    expect(messages[1]).toBe("WARN: 这把 key 不在环境变量里");
  });

  it("command：transcript 与游标显示成占位符，不含仓库路径", async () => {
    started = await startApp({ transcript: ["C:/users/me/transcript.jsonl"] });
    const usage = await started.get("/api/v1/usage");
    expect((await envelopeOf(usage))["command"]).toEqual(["logs", "usage", "--json", "--transcript=<transcript>"]);
    const first = await started.get("/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt");
    const page = (await envelopeOf(first))["data"] as Record<string, unknown>;
    const handle = page["next_cursor"] as string;
    expect(handle).toMatch(/^[A-Za-z0-9_-]{43}$/u);
    const second = await started.get(`/api/v1/attempts/demo-task/attempt-001/file?path=a/b.txt&cursor=${handle}`);
    const command = (await envelopeOf(second))["command"] as string[];
    expect(command).toEqual(["logs", "cat", "demo-task/attempt-001", "a/b.txt", "--json", "--cursor=<cursor>"]);
    expect(command.join(" ")).not.toContain("fake-cursor-0001");
  });
});

describe("证据（file 路由）不登记白名单", () => {
  it("data 原样过 redactJson：令牌形状被遮，其余字段不受约束", async () => {
    started = await startApp();
    setJson({
      path: "weird path/带空格.txt",
      mode: "text",
      text: `第一页 token=${TOKEN} 结束`,
      next_cursor: "fake-cursor-0001",
      done: false,
    });
    const response = await started.get("/api/v1/attempts/demo-task/attempt-001/file?path=weird%20path%2F%E5%B8%A6%E7%A9%BA%E6%A0%BC.txt");
    expect(response.status).toBe(200);
    const data = (await envelopeOf(response))["data"] as Record<string, unknown>;
    expect(data["path"]).toBe("weird path/带空格.txt"); // 没有白名单约束它
    expect(data["text"]).toContain("<redacted>"); // redactJson 照样跑
    expect(data["text"]).not.toContain(TOKEN);
    expect(data["done"]).toBe(false);
    expect(data["next_cursor"]).toMatch(/^[A-Za-z0-9_-]{43}$/u);
  });
});
