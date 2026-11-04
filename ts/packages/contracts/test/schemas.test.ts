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

describe("pyargs-v1 与第 ④ 步的切换", () => {
  // 每条调度器命令一条最简的、一条选项给全的；Python 的 dispatcher_handoff 照真实的 argparse 生成参数（context 是本机的），
  // 交回的命令路径要盖满 TS_DISPATCHER_COMMANDS，每一份都过 Schema
  const SAMPLES = [
    ["doctor"], ["doctor", "--provider", "p", "--model", "m", "--thinking", "high", "--out", "o.json", "--probe-decisions"],
    ["smoke", "--provider", "p", "--model", "m"], ["smoke", "--provider", "p", "--model", "m", "--thinking", "low", "--timeout", "9", "--out", "o", "--keep"],
    ["validate", "t.v1"], ["derive-json", "t.v1"], ["derive-json", "t.v1", "--title", "T", "--force", "--print"],
    ["baseline", "t.v1"], ["baseline", "t.v1", "--only", "V01", "--keep-workspace"], ["prepare", "t.v1"],
    ["run", "t"], ["run", "t", "--timeout", "5"], ["collect", "t"], ["collect", "t", "--recover"],
    ["check", "t"], ["check", "t", "--only", "V01", "--fresh", "--keep-workspace"],
    ["mutate", "--spec", "s.json"], ["mutate", "t", "--spec", "s.json", "--keep-workspace", "--tree", "x", "--out", "o", "--check-anchors"],
    ["wait", "t"], ["wait", "t", "--timeout", "5", "--interval", "1.5", "--assess", "--assess-interval", "2"],
    ["sync-adapters"], ["sync-adapters", "--check"],
    ["verdict", "t", "--verdict", "PASS", "--review", "r.md"],
    ["verdict", "t", "--verdict", "REVISE", "--review", "r.md", "--class", "EXECUTION_ERROR", "--waive", "G2=x", "--waive", "G3=y",
      "--decided-by", "me", "--human-minutes", "1.5", "--note", "n"],
    ["status", "--assess"], ["status", "t1", "--json", "--assess"], ["decisions"], ["decisions", "replay"], ["decisions", "replay", "t1", "--json", "--out", "o"],
    ["release-check"], ["release-check", "--allow", "a", "--allow", "b", "--denylist", "d.txt"], ["metrics"], ["metrics", "--out", "o.json"],
    ["branch", "t"], ["branch", "t", "--name", "n", "--rework", "--trailer", "K: v", "--no-config-trailers"],
    ["review-draft", "t"], ["review-draft", "t", "--out", "r.md", "--force"],
    ["integrate", "t"], ["integrate", "t", "--dry-run", "--skip", "V01", "--reason", "r", "--recheck", "--name", "n", "--trailer", "K: v",
      "--no-config-trailers", "--keep-worktree", "--keep-workspace", "--while-running"],
    ["mark", "t", "ABANDONED"], ["mark", "t", "INTEGRATED", "--ref", "abc", "--reason", "r", "--force"], ["cleanup", "t"], ["cleanup", "t", "--force"],
  ];

  it("启动器为每条命令生成的参数都过 Schema，命令路径盖满转交名单", () => {
    const program = [
      "import json, sys",
      `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`,
      "import pi_dispatch as pd",
      "impl = {'readonly': 'ts', 'config': 'ts', 'dispatcher': 'ts', 'hub': 'python'}",
      "out = [pd.dispatcher_handoff(pd.build_parser().parse_args(['--repo', 'C:/r'] + argv), impl) for argv in json.loads(sys.argv[1])]",
      "print(json.dumps({'pyargs': out, 'table': sorted(list(path) for path in pd.TS_DISPATCHER_COMMANDS)}))",
    ].join(String.fromCharCode(10));
    const done = spawnSync(process.env["THEMIS_PYTHON"] ?? "python", ["-c", program, JSON.stringify(SAMPLES)], { encoding: "utf8" });
    expect(done.status, done.stderr).toBe(0);
    const { pyargs, table } = JSON.parse(done.stdout) as { pyargs: (Record<string, unknown> | null)[]; table: string[][] };
    const paths = pyargs.map((item) => (item === null ? null : (item["command"] as string[]).join(" ")));
    expect(paths.filter((item) => item === null), "每条样例都应转交").toEqual([]);
    expect([...new Set(paths)].sort()).toEqual(table.map((path) => path.join(" ")).sort());
    for (const [index, item] of pyargs.entries()) expect(schemaErrors("pyargs-v1", item), SAMPLES[index]?.join(" ")).toEqual([]);
    // 少 context、context 少一项、多一个键都不过
    const first = pyargs[0] as Record<string, unknown>;
    const { context, ...bare } = first;
    expect(schemaErrors("pyargs-v1", bare)).not.toEqual([]);
    const { machine: _machine, ...partial } = context as Record<string, unknown>;
    expect(schemaErrors("pyargs-v1", { ...first, context: partial })).not.toEqual([]);
    expect(schemaErrors("pyargs-v1", { ...first, extra: 1 })).not.toEqual([]);
  });
});

describe("pyargs-v1 与 hub 的转交（⑤j3）", () => {
  // 样例不手写：照 kit_hub.build_parser 的每个叶子机械生成两条（只给必填的；选项全给，互斥的只取第一个），经真的 parse_args 与
  // kit_hub.hub_handoff 生成参数。交回的命令路径要盖满 kit_hub.HUB_COMMANDS，也要与 TS 的 HUB_COMMANDS 一致；每一份都过 Schema。
  // Schema 里 hub 的条目照 HUB_COMMANDS 生成之后按手写文件维护，分支数要正好等于路径数，不留没人用的旧分支
  const PROGRAM = [
    "import argparse, json, sys",
    `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`,
    "import kit_hub",
    "impl = {'readonly': 'ts', 'config': 'ts', 'dispatcher': 'ts', 'hub': 'ts'}",
    "def leaves(parser, path):",
    "    subs = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]",
    "    if not subs:",
    "        yield path, parser",
    "    for sub in subs:",
    "        for name, child in sub.choices.items():",
    "            yield from leaves(child, path + [name])",
    "def argv_for(path, parser, full):",
    "    skipped = {id(action) for group in parser._mutually_exclusive_groups for action in group._group_actions[1:]}",
    "    options, positionals = [], []",
    "    for action in parser._actions:",
    "        if isinstance(action, argparse._HelpAction) or id(action) in skipped:",
    "            continue",
    "        if not action.option_strings:",
    "            positionals += ['--', 'git', 'status'] if action.nargs == argparse.REMAINDER else ['x']",
    "        elif action.required or full:",
    "            options.append(action.option_strings[0])",
    "            if not isinstance(action, argparse._StoreTrueAction):",
    "                options.append(str(list(action.choices)[0]) if action.choices else '1' if action.type in (int, float) else 'x')",
    "    return path + options + positionals",
    "out = []",
    "for path, parser in leaves(kit_hub.build_parser(), []):",
    "    for full in (False, True):",
    "        argv = argv_for(path, parser, full)",
    "        out.append({'argv': argv, 'pyargs': kit_hub.hub_handoff(kit_hub.build_parser().parse_args(['--repo', 'C:/r'] + argv), impl)})",
    "print(json.dumps({'samples': out, 'table': sorted(list(path) for path, _keys in kit_hub.HUB_COMMANDS.values())}))",
  ].join(String.fromCharCode(10));

  it("启动器为每条命令生成的参数都过 Schema，命令路径盖满两边的转交名单，Schema 的 hub 分支正好这么多", async () => {
    const done = spawnSync(process.env["THEMIS_PYTHON"] ?? "python", ["-c", PROGRAM], { encoding: "utf8" });
    expect(done.status, done.stderr).toBe(0);
    const { samples, table } = JSON.parse(done.stdout) as { samples: { argv: string[]; pyargs: Record<string, unknown> }[]; table: string[][] };
    const { HUB_COMMANDS } = await import("@themis/hub/cli");
    const paths = samples.map((item) => (item.pyargs["command"] as string[]).join(" "));
    expect([...new Set(paths)].sort()).toEqual(table.map((path) => ["hub", ...path].join(" ")).sort());
    expect([...HUB_COMMANDS.keys()].sort()).toEqual(table.map((path) => path.join(" ")).sort());
    for (const item of samples) expect(schemaErrors("pyargs-v1", item.pyargs), item.argv.join(" ")).toEqual([]);
    const schema = JSON.parse(readFileSync(join(CONTRACT_SCHEMAS, "pyargs-v1.schema.json"), "utf8")) as { oneOf: { properties: { command: { const?: string[] } } }[] };
    expect(schema.oneOf.filter((branch) => branch.properties.command.const?.[0] === "hub").length).toBe(table.length);
    // namespace 少一个键、多一个键，context 少 executable 或 kit_hub，命令不带 hub 前缀，都不过
    const first = samples.find((item) => item.argv.slice(0, 2).join(" ") === "task new")?.pyargs as {
      command: string[]; namespace: Record<string, unknown>; context: Record<string, unknown> };
    const { slug: _slug, ...missing } = first.namespace;
    expect(schemaErrors("pyargs-v1", { ...first, namespace: missing })).not.toEqual([]);
    expect(schemaErrors("pyargs-v1", { ...first, namespace: { ...first.namespace, extra: 1 } })).not.toEqual([]);
    for (const key of ["executable", "kit_hub"]) {
      const { [key]: _dropped, ...partial } = first.context;
      expect(schemaErrors("pyargs-v1", { ...first, context: partial }), key).not.toEqual([]);
    }
    expect(schemaErrors("pyargs-v1", { ...first, command: first.command.slice(1) })).not.toEqual([]);
  });
});
