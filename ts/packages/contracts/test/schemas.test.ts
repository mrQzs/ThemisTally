// Schema 本身：contracts/schemas/ 下的每一份、以及仓库根 schemas/ 的 plugin-lock-v1、plugin-manifest-v1，
// 都要在 Ajv2020 的 strict 下能编译（迁移计划第 3.2 节：第一次引入 Ajv 时加这一条）。
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CONTRACT_SCHEMAS, REPO_SCHEMAS, newAjv, schemaErrors } from "./schemas.ts";

describe("契约 Schema 在 strict 下能编译", () => {
  const own = readdirSync(CONTRACT_SCHEMAS).filter((name) => name.endsWith(".schema.json"));

  it("contracts/schemas/ 的每一份", () => {
    expect(own.length).toBeGreaterThanOrEqual(4);
    for (const name of own) {
      const ajv = newAjv();
      expect(() => ajv.compile(JSON.parse(readFileSync(join(CONTRACT_SCHEMAS, name), "utf8")) as object), name).not.toThrow();
    }
  });

  it("仓库根的 plugin-lock-v1、plugin-manifest-v1", () => {
    for (const name of ["plugin-lock-v1.schema.json", "plugin-manifest-v1.schema.json"]) {
      const ajv = newAjv();
      expect(() => ajv.compile(JSON.parse(readFileSync(join(REPO_SCHEMAS, name), "utf8")) as object), name).not.toThrow();
    }
  });

  it("启动器参数：合法的过、多键少键与类型不对的不过", () => {
    expect(schemaErrors("pyargs-v1", { command: ["status"], repo: null, task_id: null, json: true })).toEqual([]);
    expect(schemaErrors("pyargs-v1", { command: ["logs", "show"], repo: "C:/r", target: "a", json: false })).toEqual([]);
    expect(schemaErrors("pyargs-v1", { command: ["status"], repo: null, task_id: null, json: true, assess: true })).not.toEqual([]);
    expect(schemaErrors("pyargs-v1", { command: ["logs", "show"], repo: null, json: false })).not.toEqual([]);
    expect(schemaErrors("pyargs-v1", { command: ["logs", "cat"], repo: null, json: false })).not.toEqual([]);
  });
});
