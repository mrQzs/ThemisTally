// Schema 本身：contracts/schemas/ 下的每一份、以及仓库根 schemas/ 的 plugin-lock-v1、plugin-manifest-v1，
// 都要在 Ajv2020 的 strict 下能编译（迁移计划第 3.2 节：第一次引入 Ajv 时加这一条）。
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CONTRACT_SCHEMAS, REPO_SCHEMAS, newAjv, schemaErrors } from "./schemas.ts";
import { spawnSync } from "node:child_process";
import { REPO } from "./harness.ts";

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
    const ui = { command: ["ui"], repo: "C:/r", desktop: true, assets: null, transcript: [], idle_timeout: null, python: "py", kernel: "pd.py" };
    expect(schemaErrors("pyargs-v1", ui)).toEqual([]);
    expect(schemaErrors("pyargs-v1", { ...ui, repo: null })).not.toEqual([]); // 调度器总给仓库根目录
    expect(schemaErrors("pyargs-v1", { ...ui, idle_timeout: 1.5 })).not.toEqual([]);
    expect(schemaErrors("pyargs-v1", { ...ui, json: true })).not.toEqual([]);
    const { kernel: _kernel, ...withoutKernel } = ui;
    expect(schemaErrors("pyargs-v1", withoutKernel)).not.toEqual([]);
  });
});

describe("pyargs-v1 与第 ③ 步的切换", () => {
  // 每条转交给 TS 的配置中心命令各一条 argv；Python 的 config_handoff 照真实的 argparse 生成参数，交回的命令路径要盖满
  // TS_CONFIG_COMMANDS，每一份都要过 Schema（Schema 里 config、plugins 的条目由 argparse 生成，缺键、多键都不过）
  const SAMPLES = [
    ["config", "show"], ["config", "validate", "--json"], ["config", "set", "k", "v"], ["config", "unset", "k", "--yes"],
    ["config", "history", "show", "3", "--json"], ["config", "rollback", "2", "--dry-run", "--json"], ["config", "init"],
    ["config", "decisions", "marker", "on"], ["config", "secret", "check", "SOME_NAME"], ["config", "runtime", "list"],
    ["config", "runtime", "scan", "--add"], ["config", "runtime", "add", "pi", "--adapter", "pi", "--command", '["C:/pi.exe"]'],
    ["config", "runtime", "remove", "pi", "--yes"], ["config", "runtime", "probe", "pi", "--json"], ["config", "models", "pi"],
    ["config", "profile", "show"], ["config", "profile", "add", "p", "--runtime", "pi", "--model", "a/b", "--thinking", "high", "--credential-env", "K"],
    ["config", "profile", "edit", "p", "--model", "a/c"], ["config", "profile", "remove", "p"], ["config", "role", "show", "--json"],
    ["config", "role", "set", "scheduler_agent", "p", "--cadence-seconds", "60"], ["config", "preset", "list"], ["config", "preset", "show", "day"],
    ["config", "preset", "save", "day", "--description", "d", "--roles", "execution"], ["config", "preset", "use", "day", "--expect-state=v1;config=x"],
    ["config", "preset", "diff", "a", "b"], ["config", "preset", "remove", "day", "--dry-run", "--json"], ["config", "doctor", "--record", "t.v1"],
    ["plugins", "list", "--json"], ["plugins", "show", "x"], ["plugins", "verify"], ["plugins", "enable", "x", "--allow-permission", "a"],
    ["plugins", "disable", "x"],
  ];

  it("启动器为每条命令生成的参数都过 Schema，命令路径盖满转交名单", () => {
    const program = [
      "import json, sys",
      `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`,
      "import pi_dispatch as pd",
      "out = []",
      "for argv in json.loads(sys.argv[1]):",
      "    argv = ['--repo', 'C:/r'] + argv",
      "    args = pd.forwarded_command(argv) or pd.build_parser().parse_args(argv)",
      "    out.append(pd.config_handoff(args))",
      "print(json.dumps({'pyargs': out, 'table': sorted(list(path) for path in pd.TS_CONFIG_COMMANDS)}))",
    ].join(String.fromCharCode(10));
    const done = spawnSync(process.env["THEMIS_PYTHON"] ?? "python", ["-c", program, JSON.stringify(SAMPLES)], { encoding: "utf8" });
    expect(done.status, done.stderr).toBe(0);
    const { pyargs, table } = JSON.parse(done.stdout) as { pyargs: (Record<string, unknown> | null)[]; table: string[][] };
    const paths = pyargs.map((item) => (item === null ? null : (item["command"] as string[]).join(" ")));
    expect(paths.filter((item) => item === null), "每条样例都应转交").toEqual([]);
    expect([...new Set(paths)].sort()).toEqual(table.map((path) => path.join(" ")).sort());
    for (const [index, item] of pyargs.entries()) expect(schemaErrors("pyargs-v1", item), SAMPLES[index]?.join(" ")).toEqual([]);
    // 少一个键、多一个键都不过
    const first = pyargs[0] as Record<string, unknown>;
    const { json: _json, ...missing } = first;
    expect(schemaErrors("pyargs-v1", missing)).not.toEqual([]);
    expect(schemaErrors("pyargs-v1", { ...first, extra: 1 })).not.toEqual([]);
  });
});
