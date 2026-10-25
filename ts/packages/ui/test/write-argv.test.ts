// 写 argv 的登记、校验与内核解析器（桌面端 §5.3、D01/D02）：W1 七条基础 argv 加 --dry-run --json / --expect-state= /
// --yes（plugins 不加）都过内核真正的解析器；W2 内核里带 --dry-run 的写命令集合恰好等于本片 7 条加 T020 的 5 条；
// W3 基础 argv 不含那四个开关；W4 validateWriteArgs 的每一类不合格（含 T020 的五个 action 名）回固定 400、不回显值。
import { spawnSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import { buildWriteArgv, T020_WRITE_COMMANDS, validateWriteArgs, WRITE_ACTIONS, WRITE_ARGV } from "../src/writeroutes.ts";
import { REPO_ROOT } from "./harness.ts";

const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const SCRIPTS = REPO_ROOT.replace(/\\/gu, "/") + "/scripts";
const STATE = `v1;config=${"0".repeat(64)}`;

/** 用内核真正的解析器解析一条 argv，返回 dry_run/json/expect_state/yes（config/plugins 剥掉组名）。 */
function parse(argv: readonly string[]): { dry_run: boolean; json: boolean; expect_state: string | null; yes: boolean } {
  const program = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(SCRIPTS)})`,
    "import kit_config, kit_plugins",
    "argv = json.loads(sys.argv[1])",
    "if argv[:1] == ['config']:",
    "    args = kit_config.build_parser().parse_args(argv[1:])",
    "elif argv[:1] == ['plugins']:",
    "    args = kit_plugins.build_parser().parse_args(argv[1:])",
    "else:",
    "    raise SystemExit('没有匹配的解析器：%r' % (argv[:1],))",
    "sys.stdout.write(json.dumps({'dry_run': bool(getattr(args, 'dry_run', False)),"
    + " 'json': bool(getattr(args, 'json', False)), 'expect_state': getattr(args, 'expect_state', None),"
    + " 'yes': bool(getattr(args, 'yes', False))}))",
  ].join("\n");
  const done = spawnSync(PYTHON, ["-c", program, JSON.stringify([...argv])], { encoding: "utf8", timeout: 120_000 });
  expect(done.status, `解析失败：${argv.join(" ")}：${(done.stderr ?? "").slice(0, 400)}`).toBe(0);
  return JSON.parse(done.stdout) as { dry_run: boolean; json: boolean; expect_state: string | null; yes: boolean };
}

/** 内核里所有带 --dry-run 的写命令路径（config/plugins 组名保留）。 */
function dryRunCommands(): string[][] {
  const program = [
    "import argparse, json, sys",
    `sys.path.insert(0, ${JSON.stringify(SCRIPTS)})`,
    "import kit_config, kit_plugins",
    "def walk(parser, prefix):",
    "    out = []",
    "    for action in parser._actions:",
    "        if isinstance(action, argparse._SubParsersAction):",
    "            for name, sub in action.choices.items():",
    "                has = any(getattr(a, 'option_strings', None) and '--dry-run' in a.option_strings for a in sub._actions)",
    "                path = prefix + [name]",
    "                if has: out.append(path)",
    "                out.extend(walk(sub, path))",
    "    return out",
    "result = [['config'] + p for p in walk(kit_config.build_parser(), [])]"
    + " + [['plugins'] + p for p in walk(kit_plugins.build_parser(), [])]",
    "sys.stdout.write(json.dumps(sorted(result)))",
  ].join("\n");
  const done = spawnSync(PYTHON, ["-c", program], { encoding: "utf8", timeout: 120_000 });
  expect(done.status, `枚举 --dry-run 子命令失败：${(done.stderr ?? "").slice(0, 400)}`).toBe(0);
  return JSON.parse(done.stdout) as string[][];
}

describe("W1：七条基础 argv 过内核真正的解析器（dry_run/json/expect_state/yes）", () => {
  it("每条加 --dry-run --json 解析出 dry_run 与 json 为真", () => {
    for (const [name, base] of Object.entries(WRITE_ARGV)) {
      const parsed = parse([...base, "--dry-run", "--json"]);
      expect(parsed.dry_run, `${name} 应解析出 dry_run`).toBe(true);
      expect(parsed.json, `${name} 应解析出 json`).toBe(true);
    }
  });

  it("每条加 --expect-state=<64 个 0> 解析出 expect_state 逐字相同", () => {
    for (const [name, base] of Object.entries(WRITE_ARGV)) {
      const parsed = parse([...base, `--expect-state=${STATE}`]);
      expect(parsed.expect_state, `${name} 的 expect_state`).toBe(STATE);
    }
  });

  it("config 组加 --yes 解析出 yes 为真；plugins 组没有 --yes", () => {
    for (const [name, base] of Object.entries(WRITE_ARGV)) {
      if (base[0] === "plugins") {
        expect(() => parse([...base, "--yes"]), `${name}（plugins）不该接受 --yes`).toThrow();
      } else {
        expect(parse([...base, "--yes"]).yes, `${name} 应解析出 yes`).toBe(true);
      }
    }
  });
});

describe("W2：内核带 --dry-run 的写命令集合 = 本片 7 条 + T020 的 5 条", () => {
  it("恰好 12 条，且等于七条命令路径加 T020_WRITE_COMMANDS", () => {
    const slice = [
      ["config", "role", "set"],
      ["config", "preset", "save"],
      ["config", "preset", "use"],
      ["config", "preset", "remove"],
      ["config", "rollback"],
      ["plugins", "enable"],
      ["plugins", "disable"],
    ];
    const expected = [...slice, ...T020_WRITE_COMMANDS.map((path) => [...path])].map((path) => path.join(" ")).sort();
    const seen = dryRunCommands().map((path) => path.join(" ")).sort();
    expect(seen).toEqual(expected);
    expect(seen).toHaveLength(12);
  });
});

describe("W3：七条基础 argv 不含 --dry-run/--json/--expect-state/--yes", () => {
  it("WRITE_ARGV 与 buildWriteArgv 拼出的基础 argv 都不含那四个开关", () => {
    const forbidden = ["--dry-run", "--json", "--expect-state", "--yes"];
    for (const [name, base] of Object.entries(WRITE_ARGV)) {
      for (const flag of forbidden) {
        expect(base.some((part) => part === flag || part.startsWith(`${flag}=`)), `${name} 不该含 ${flag}`).toBe(false);
      }
    }
    const examples: Record<string, Record<string, unknown>> = {
      "role.set": { role: "execution", target: "manual" },
      "preset.use": { name: "demo-preset" },
      "preset.save": { name: "demo-preset" },
      "preset.remove": { name: "demo-preset" },
      "config.rollback": { number: 1 },
      "plugin.enable": { id: "example-plugin" },
      "plugin.disable": { id: "example-plugin" },
    };
    for (const [action, args] of Object.entries(examples)) {
      const argv = buildWriteArgv(action, args);
      for (const flag of forbidden) {
        expect(argv.some((part) => part === flag || part.startsWith(`${flag}=`)), `${action} 的基础 argv 不该含 ${flag}`).toBe(false);
      }
    }
  });
});

describe("W4：validateWriteArgs 的每一类不合格（先合法基线，再只改受测条件）", () => {
  const ok = (action: string, args: unknown): void => {
    const verdict = validateWriteArgs(action, args);
    expect(verdict.ok, `${action} ${JSON.stringify(args)} 应合法：${verdict.ok ? "" : verdict.message}`).toBe(true);
  };
  const bad = (action: string, args: unknown, message: string): void => {
    const verdict = validateWriteArgs(action, args);
    expect(verdict.ok, `${action} ${JSON.stringify(args)} 应不合法`).toBe(false);
    if (!verdict.ok) expect(verdict.message).toBe(message);
  };

  it("正文不是对象 → 「请求体必须是 JSON 对象」", () => {
    ok("role.set", { role: "execution", target: "manual" });
    bad("role.set", "x", "请求体必须是 JSON 对象");
    bad("role.set", [1], "请求体必须是 JSON 对象");
    bad("role.set", null, "请求体必须是 JSON 对象");
  });

  it("action 不合法（含 T020 的五个 action 名）", () => {
    for (const t020 of ["profile.add", "profile.edit", "profile.remove", "runtime.add", "runtime.remove", "nope", ""]) {
      bad(t020, {}, "action 不合法");
    }
    expect(Object.keys(WRITE_ACTIONS).sort()).toEqual(
      ["config.rollback", "plugin.disable", "plugin.enable", "preset.remove", "preset.save", "preset.use", "role.set"],
    );
  });

  it("未知键、缺必填键", () => {
    bad("role.set", { role: "execution", target: "manual", extra: 1 }, "参数含有未知键");
    bad("role.set", { target: "manual" }, "参数缺少必填键");
    bad("preset.use", {}, "参数缺少必填键");
    bad("plugin.disable", {}, "参数缺少必填键");
  });

  it("role/target/host/cadence_seconds 的取值", () => {
    bad("role.set", { role: "nope", target: "manual" }, "role 不合法");
    bad("role.set", { role: "execution", target: "Bad_Profile" }, "target 不合法");
    ok("role.set", { role: "execution", target: "demo-profile" });
    ok("role.set", { role: "scheduler_agent", target: "interactive_host", host: "codex", cadence_seconds: 3600 });
    bad("role.set", { role: "execution", target: "manual", host: "vim" }, "host 不合法");
    bad("role.set", { role: "execution", target: "manual", cadence_seconds: 30 }, "cadence_seconds 不合法");
    bad("role.set", { role: "execution", target: "manual", cadence_seconds: 86401 }, "cadence_seconds 不合法");
    bad("role.set", { role: "execution", target: "manual", cadence_seconds: 1.5 }, "cadence_seconds 不合法");
    bad("role.set", { role: "execution", target: "manual", cadence_seconds: true }, "cadence_seconds 不合法");
    bad("role.set", { role: "execution", target: "manual", cadence_seconds: "60" }, "cadence_seconds 不合法");
  });

  it("preset.save 的 description/roles/force", () => {
    ok("preset.save", { name: "demo-preset", description: "demo", roles: ["contract", "execution"], force: true });
    bad("preset.save", { name: "demo-preset", description: "" }, "description 不合法");
    bad("preset.save", { name: "demo-preset", description: "x".repeat(201) }, "description 不合法");
    bad("preset.save", { name: "demo-preset", description: 5 }, "description 不合法");
    bad("preset.save", { name: "demo-preset", description: "a\u0001b" }, "description 不合法");
    bad("preset.save", { name: "demo-preset", roles: [] }, "roles 不合法");
    bad("preset.save", { name: "demo-preset", roles: ["nope"] }, "roles 不合法");
    bad("preset.save", { name: "demo-preset", roles: ["execution", "execution"] }, "roles 不合法");
    bad("preset.save", { name: "demo-preset", roles: "execution" }, "roles 不合法");
    bad("preset.save", { name: "demo-preset", force: false }, "force 不合法");
    bad("preset.save", { name: "demo-preset", force: "true" }, "force 不合法");
  });

  it("name/number/id/allow_permission 的取值", () => {
    bad("preset.use", { name: "Bad_Name" }, "name 不合法");
    bad("config.rollback", { number: 0 }, "number 不合法");
    bad("config.rollback", { number: 1000000000 }, "number 不合法");
    bad("config.rollback", { number: 1.5 }, "number 不合法");
    bad("config.rollback", { number: "1" }, "number 不合法");
    ok("config.rollback", { number: 999999999 });
    bad("plugin.enable", { id: "Bad_Plugin" }, "id 不合法");
    bad("plugin.disable", { id: "-x" }, "id 不合法");
    ok("plugin.enable", { id: "example-plugin", allow_permission: ["a", "b"] });
    ok("plugin.enable", { id: "example-plugin", allow_permission: [] });
    bad("plugin.enable", { id: "example-plugin", allow_permission: "a" }, "allow_permission 不合法");
    bad("plugin.enable", { id: "example-plugin", allow_permission: ["a", "a"] }, "allow_permission 不合法");
    bad("plugin.enable", { id: "example-plugin", allow_permission: [""] }, "allow_permission 不合法");
    bad("plugin.enable", { id: "example-plugin", allow_permission: ["x".repeat(257)] }, "allow_permission 不合法");
    bad("plugin.enable", { id: "example-plugin", allow_permission: [5] }, "allow_permission 不合法");
  });

  it("buildWriteArgv 拼出的基础 argv 与登记表逐条一致", () => {
    expect(buildWriteArgv("role.set", { role: "execution", target: "manual" })).toEqual(["config", "role", "set", "execution", "manual"]);
    expect(buildWriteArgv("role.set", { role: "scheduler_agent", target: "manual", host: "codex", cadence_seconds: 3600 })).toEqual([
      "config", "role", "set", "scheduler_agent", "manual", "--host=codex", "--cadence-seconds=3600",
    ]);
    expect(buildWriteArgv("preset.save", { name: "demo-preset", description: "d", roles: ["contract", "execution"], force: true })).toEqual([
      "config", "preset", "save", "demo-preset", "--description=d", "--roles=contract,execution", "--force",
    ]);
    expect(buildWriteArgv("config.rollback", { number: 1 })).toEqual(["config", "rollback", "1"]);
    expect(buildWriteArgv("plugin.enable", { id: "example-plugin", allow_permission: ["a", "b"] })).toEqual([
      "plugins", "enable", "example-plugin", "--allow-permission=a", "--allow-permission=b",
    ]);
  });
});
