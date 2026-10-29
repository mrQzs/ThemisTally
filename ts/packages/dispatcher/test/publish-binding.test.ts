// K4②、K4b（r2 文档 9.4 节，themistally-15 复核切换 c1 时指出命令行契约够不着）：首次发布版本记录时，另一个进程在“看过没有
// 记录”之后、发布之前抢先发布了。Python 的用例靠替身让进程停在发布前一刻；TS 没有这样的口子，这里直接调 publishBindingRecord，
// 在 roles.resolveRoleExecutor 里写入抢先的那份记录（它正好夹在两步之间）：publishNew 返回 false，沿用别人的记录、字节不动；
// 采用的记录与 PI_EXEC_MODEL 冲突退出 2，不在 allowed_executors 里退出 3，合同哈希不同退出 4。
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { BindingRecordError, bindingRecordRel } from "../src/executor.ts";
import { type BindingRoles, publishBindingRecord } from "../src/executor-resolve.ts";
import { Repo } from "../src/repo.ts";

const FROZEN = new TextEncoder().encode(JSON.stringify({ task_id: "t1", plan_version: 1 }));
const SHA = createHash("sha256").update(FROZEN).digest("hex");
const CONTRACT: PyDict = new Map<string, PyValue>([
  ["executor", new Map<string, PyValue>([["role", "execution"], ["tools", ["read", "edit", "bash"]], ["context_files", "project"]])],
]);
const binding = (model: string): PyDict => new Map<string, PyValue>([
  ["role", "execution"], ["profile", "exec"], ["runtime", "pi"], ["adapter", "pi"], ["active_preset", null],
  ["provider", "step"], ["model", model], ["thinking", "high"],
]);

let root = "";
let saved: string | undefined;
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "themis-publish-binding-"));
  mkdirSync(join(root, ".agent", "runs", "t1"), { recursive: true });
  saved = process.env["PI_EXEC_MODEL"];
  delete process.env["PI_EXEC_MODEL"];
});
afterEach(() => {
  if (saved === undefined) delete process.env["PI_EXEC_MODEL"];
  else process.env["PI_EXEC_MODEL"] = saved;
  rmSync(root, { recursive: true, force: true });
});

/** 别人抢先发布的那份记录（与 publishBindingRecord 写的字段相同）。 */
function competitor(model: string, contractSha = SHA): Uint8Array {
  const record = Object.fromEntries([...binding(model)].map(([key, value]) => [key, value]));
  const text = JSON.stringify({ ...record, contract_json_sha256: contractSha, created_at: "2026-01-01T00:00:00Z", created_by_attempt: "attempt-009", config_sha256: null }, null, 2);
  return new TextEncoder().encode(`${text}${String.fromCharCode(10)}`);
}

/** 解析出 mine 的 roles；race 给出时，在交回之前把它写成已发布的记录（模拟另一个进程抢先）。 */
function roles(mine: string, race: Uint8Array | null): BindingRoles {
  return {
    resolveRoleExecutor: () => {
      if (race !== null) writeFileSync(join(root, bindingRecordRel("t1", 1n)), race, { flag: "wx" });
      return [binding(mine), null];
    },
    configErrors: () => [],
    bindingTuple: () => null,
  };
}

const publish = (config: PyDict, r: BindingRoles): PyDict =>
  publishBindingRecord(new Repo(root), "execution", FROZEN, CONTRACT, config, null, "t1", 1n, 1n, r);

function refusal(body: () => unknown): BindingRecordError {
  try {
    body();
  } catch (error) {
    if (error instanceof BindingRecordError) return error;
    throw error;
  }
  throw new Error("应当拒绝");
}

describe("publishBindingRecord：发布前一刻被别人抢先", () => {
  it("没人抢：发布自己的", () => {
    expect(publish(new Map(), roles("step-5", null)).get("model")).toBe("step-5");
    expect(existsSync(join(root, bindingRecordRel("t1", 1n)))).toBe(true);
  });

  it("被抢先：沿用别人的记录，字节不动，不留临时文件", () => {
    const theirs = competitor("step-4");
    expect(publish(new Map(), roles("step-5", theirs)).get("model")).toBe("step-4");
    expect([...readFileSync(join(root, bindingRecordRel("t1", 1n)))]).toEqual([...theirs]);
    expect(readdirSync(join(root, ".agent", "runs", "t1"))).toEqual(["binding-v1.json"]);
  });

  it("采用的记录与 PI_EXEC_MODEL 冲突：退出 2", () => {
    process.env["PI_EXEC_MODEL"] = "step-5";
    const error = refusal(() => publish(new Map(), roles("step-5", competitor("step-4"))));
    expect([error.code, error.message.includes("PI_EXEC_MODEL=step-5")]).toEqual([2, true]);
  });

  it("采用的记录不在 allowed_executors 里：退出 3", () => {
    const config: PyDict = new Map<string, PyValue>([["allowed_executors", [new Map<string, PyValue>([["provider", "step"], ["model", "step-5"]])]]]);
    const error = refusal(() => publish(config, roles("step-5", competitor("step-4"))));
    expect([error.code, error.message.includes("allowed_executors")]).toEqual([3, true]);
  });

  it("采用的记录是另一份合同的：退出 4", () => {
    const error = refusal(() => publish(new Map(), roles("step-5", competitor("step-4", "0".repeat(64)))));
    expect([error.code, error.message.includes("已派遣的版本不能改")]).toEqual([4, true]);
  });
});
