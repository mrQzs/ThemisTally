// config 只读命令的命令行对照（迁移第 ③a2 片）：validate、show、history [show N]、secret check|remove。Python 走真实的
// `pi_dispatch.py --repo <仓库> config …`（钉成 Python 实现），TS 走规整参数（--pyargs-b64，带 context 的 kit_root）；
// stdout 逐字节、stderr 逐字节、退出码都比较（两路分开比，见迁移计划第 ③ 步）。
// 凭据库一律设成 off 或临时目录下的 file 模式，测试进程里去掉官方凭据的环境变量：只比来源，不读任何真实凭据。
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { type CliRun, REPO, removeDir, runPythonCli, runConfigLauncherCli, runTsCli, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("config-ro"));
const SAVED: Record<string, string | undefined> = {};
const ENV: Record<string, string | undefined> = {
  CODEKIT_SECRET_STORE: "off",
  TYPESAFE_API_KEY: undefined,
  PI_DISPATCH_WORKTREE_ROOT: undefined,
  CODEKIT_ACTOR: undefined,
};

beforeAll(() => {
  for (const [name, value] of Object.entries(ENV)) {
    SAVED[name] = process.env[name];
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
});
afterAll(() => {
  for (const [name, value] of Object.entries(SAVED)) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
  removeDir(ROOT);
});

function gitRepo(name: string): string {
  const repo = join(ROOT, name);
  mkdirSync(join(repo, ".agent"), { recursive: true });
  const done = spawnSync("git", ["init", "-q", repo], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`git init 失败：${done.stderr}`);
  return repo;
}

/** argparse 解析之后交给 TS 的参数（迁移计划第 ③ 步：context 带 kit_root 与 lock_wait_seconds）。 */
function pyargs(repo: string, command: string[], fields: Record<string, unknown>): Record<string, unknown> {
  return { command, repo, ...fields, context: { kit_root: REPO, lock_wait_seconds: 30.0 } };
}

interface Run {
  readonly name: string;
  readonly argv: string[];
  readonly args: Record<string, unknown>;
}

const shown = (run: CliRun): Record<string, unknown> => ({ status: run.status, stdout: run.stdout.toString("utf8"), stderr: run.stderr.toString("utf8") });

function compare(repo: string, runs: readonly Run[]): void {
  const problems: unknown[] = [];
  for (const run of runs) {
    const python = runPythonCli(["--repo", repo, "config", ...run.argv], repo);
    for (const runtime of ["node", "bun", "launcher"] as const) {
      const other = runtime === "launcher" ? runConfigLauncherCli(["--repo", repo, "config", ...run.argv], repo) : runTsCli(runtime, run.args, repo);
      if (other.status !== python.status || !other.stdout.equals(python.stdout) || !other.stderr.equals(python.stderr)) {
        problems.push({ name: run.name, runtime, python: shown(python), other: shown(other) });
      }
    }
  }
  expect(problems.slice(0, 2), `共 ${problems.length} 条不一致`).toEqual([]);
}

const validate = (repo: string, json: boolean): Run => ({
  name: `validate${json ? " --json" : ""}`,
  argv: ["validate", ...(json ? ["--json"] : [])],
  args: pyargs(repo, ["config", "validate"], { json }),
});
const show = (repo: string, json: boolean): Run => ({
  name: `show${json ? " --json" : ""}`,
  argv: ["show", ...(json ? ["--json"] : [])],
  args: pyargs(repo, ["config", "show"], { json }),
});

describe("config validate 与 show", () => {
  it("没有配置文件、合法的配置、无效的配置、解析不了的配置", () => {
    const empty = gitRepo("empty");
    const good = gitRepo("good");
    writeFileSync(
      join(good, ".agent", "dispatch.config.json"),
      JSON.stringify({ kill_grace_seconds: 20, check_artifact_patterns: ["dist/**"], decisions: { mode: "on", api_key_env: "THEMIS_CONTRACT_KEY" }, _note: "说明" }, null, 2),
    );
    const bad = gitRepo("bad");
    writeFileSync(
      join(bad, ".agent", "dispatch.config.json"),
      JSON.stringify({ zz: 1, plugins: { enabled: 1 }, roles: { execution: { mode: "x" } }, pricing: { "s/m": { input: 1 } }, decisions: { mode: "x" } }),
    );
    const broken = gitRepo("broken");
    writeFileSync(join(broken, ".agent", "dispatch.config.json"), "{\n  \"a\": \n}");
    const secret = gitRepo("secret");
    writeFileSync(join(secret, ".agent", "dispatch.config.json"), JSON.stringify({ decisions: { mode: "off", base_url: `https://x.example/${"sk-" + "q1".repeat(12)}` } }));
    for (const repo of [empty, good, bad, broken, secret]) compare(repo, [validate(repo, false), validate(repo, true), show(repo, false), show(repo, true)]);
  });

  it("不在 Git 仓库里", () => {
    const plain = join(ROOT, "plain");
    mkdirSync(plain);
    compare(plain, [validate(plain, true), show(plain, false)]);
  });
});

/** 审计里的一行（sort_keys、ensure_ascii=False，照 _append_audit 的写法）。 */
function auditLine(record: Record<string, unknown>): string {
  const sorted = (value: unknown): unknown =>
    value !== null && typeof value === "object" && !Array.isArray(value)
      ? Object.fromEntries(Object.keys(value as object).sort().map((key) => [key, sorted((value as Record<string, unknown>)[key])]))
      : value;
  return JSON.stringify(sorted({ record_type: "management-audit", schema_version: 1, ...record }))
    .replaceAll('":', '": ')
    .replaceAll(',"', ', "');
}

function snapshot(repo: string, content: string): { kind: string; sha256: string; stored: boolean } {
  const sha = createHash("sha256").update(content).digest("hex");
  mkdirSync(join(repo, ".agent", "config-history"), { recursive: true });
  writeFileSync(join(repo, ".agent", "config-history", `${sha}.json`), content);
  return { kind: "config-snapshot", sha256: sha, stored: true };
}

function historyRun(repo: string, name: string, argv: string[], fields: Record<string, unknown>): Run {
  return { name, argv: ["history", ...argv], args: pyargs(repo, ["config", "history"], { show: null, number: null, json: false, ...fields }) };
}

describe("config history", () => {
  it("空白行不算损坏、同一事务先到的终结记录为准、空对象是叶子、快照被改过、审计读不出来", () => {
    const repo = gitRepo("history-edge");
    const emptyPlugins = snapshot(repo, '{"plugins": {}, "kill_grace_seconds": 20}\n');
    const filled = snapshot(repo, '{"plugins": {"enabled": []}, "kill_grace_seconds": 20}\n');
    const tampered = snapshot(repo, '{"plugins": {"enabled": []}, "kill_grace_seconds": 25}\n');
    writeFileSync(join(repo, ".agent", "config-history", `${tampered.sha256}.json`), '{"plugins": {"enabled": []}, "kill_grace_seconds": 26}\n');
    const lines = [
      auditLine({ phase: "intent", resource: "config", txn: "t1", action: "config.set", target: "plugins", actor: "user", confirmation: "none", at: "2026-10-26T02:00:00Z", audit_id: "aud-1", before_ref: emptyPlugins, after_ref: filled }),
      String.fromCharCode(32, 9, 11, 12, 32),
      auditLine({ phase: "commit", resource: "config", txn: "t1", result: "published", at: "2026-10-26T02:00:01Z", audit_id: "aud-2" }),
      auditLine({ phase: "resolve", resource: "config", txn: "t1", result: "aborted", at: "2026-10-26T02:00:02Z", audit_id: "aud-3" }),
      auditLine({ phase: "intent", resource: "config", txn: "t2", action: "config.set", target: "kill_grace_seconds", actor: "user", confirmation: "none", at: "2026-10-26T02:01:00Z", audit_id: "aud-4", before_ref: filled, after_ref: tampered }),
      auditLine({ phase: "commit", resource: "config", txn: "t2", result: "published", at: "2026-10-26T02:01:01Z", audit_id: "aud-5" }),
    ];
    mkdirSync(join(repo, ".agent", "audit"), { recursive: true });
    writeFileSync(join(repo, ".agent", "audit", "management.jsonl"), lines.join("\n") + "\n");
    compare(repo, [
      historyRun(repo, "列表", [], {}),
      historyRun(repo, "空对象变成非空", ["show", "1", "--json"], { show: "show", number: 1n, json: true }),
      historyRun(repo, "快照的哈希对不上", ["show", "2"], { show: "show", number: 2n }),
    ]);
    // 审计路径是目录：读不出来要报错，不能当作还没有写入记录
    const unreadable = gitRepo("history-unreadable");
    mkdirSync(join(unreadable, ".agent", "audit", "management.jsonl"), { recursive: true });
    compare(unreadable, [historyRun(unreadable, "审计读不出来", [], {})]);
  });

  it("编号、终结状态、逐键差异、本机配置、外部改动与损坏的行", () => {
    const repo = gitRepo("history");
    const first = snapshot(repo, '{\n  "kill_grace_seconds": 20,\n  "decisions": {"mode": "off", "points": [1, 2]}\n}\n');
    const second = snapshot(repo, '{\n  "kill_grace_seconds": 20.0,\n  "decisions": {"mode": "on", "points": [1, 2]},\n  "env_keep": ["A"]\n}\n');
    const secretSnap = snapshot(repo, `{"env_keep": ["${"sk-" + "z9".repeat(12)}"]}`);
    const withNull = snapshot(repo, `{"worktree_root": null, "kill_grace_seconds": 30}${String.fromCharCode(10)}`);
    const withoutNull = snapshot(repo, `{"kill_grace_seconds": 30}${String.fromCharCode(10)}`);
    const lines = [
      auditLine({ phase: "observed", resource: "config", action: "external", at: "2026-10-26T01:00:00Z", audit_id: "aud-0", after_ref: first }),
      auditLine({ phase: "intent", resource: "config", txn: "t1", action: "config.set", target: "kill_grace_seconds", actor: "user", confirmation: "none", at: "2026-10-26T01:01:00Z", audit_id: "aud-1", before_ref: first, after_ref: second, invalidated_approvals: [], note: "P3 之前没有批准记录" }),
      auditLine({ phase: "commit", resource: "config", txn: "t1", result: "published", at: "2026-10-26T01:01:01Z", audit_id: "aud-2" }),
      "{not json",
      auditLine({ phase: "intent", resource: "local", txn: "t2", action: "runtime.add", target: "pi", actor: "user-ui", confirmation: "flag", at: "2026-10-26T01:02:00Z", audit_id: "aud-3", before_ref: null, after_ref: { kind: "local-file", sha256: "a".repeat(64), stored: false } }),
      auditLine({ phase: "observed", resource: "config", action: "external", at: "2026-10-26T01:03:00Z", audit_id: "aud-4", after_ref: second }),
      auditLine({ phase: "intent", resource: "config", txn: "t3", action: "config.set", target: `sk-${"w8".repeat(12)}`, actor: "undeclared", confirmation: "none", at: "2026-10-26T01:04:00Z", audit_id: "aud-5", before_ref: second, after_ref: secretSnap }),
      auditLine({ phase: "resolve", resource: "config", txn: "t3", result: "unknown", at: "2026-10-26T01:05:00Z", audit_id: "aud-6" }),
      auditLine({ phase: "intent", resource: "config", txn: "t5", action: "config.unset", target: "worktree_root", actor: "user", confirmation: "none", at: "2026-10-26T01:05:30Z", audit_id: "aud-8", before_ref: withNull, after_ref: withoutNull }),
      auditLine({ phase: "commit", resource: "config", txn: "t5", result: "published", at: "2026-10-26T01:05:31Z", audit_id: "aud-9" }),
      auditLine({ phase: "intent", resource: "config", txn: "t4", action: "config.unset", target: "", actor: "agent:planner", confirmation: "none", at: "2026-10-26T01:06:00Z", audit_id: "aud-7", before_ref: null, after_ref: { kind: "config-snapshot", sha256: "b".repeat(64), stored: true } }),
      auditLine({ phase: "intent", resource: "config", txn: 5, action: "x" }),
      "",
      '{"half": ',
    ];
    mkdirSync(join(repo, ".agent", "audit"), { recursive: true });
    writeFileSync(join(repo, ".agent", "audit", "management.jsonl"), lines.join("\n"));
    const history = (name: string, argv: string[], fields: Record<string, unknown>): Run => historyRun(repo, name, argv, fields);
    const empty = gitRepo("history-empty");
    compare(repo, [
      history("列表", [], {}),
      history("列表 --json", ["--json"], { json: true }),
      history("第 1 条", ["show", "1"], { show: "show", number: 1n }),
      history("第 1 条 --json", ["show", "1", "--json"], { show: "show", number: 1n, json: true }),
      history("本机配置那一条", ["show", "2"], { show: "show", number: 2n }),
      history("本机配置那一条 --json", ["show", "2", "--json"], { show: "show", number: 2n, json: true }),
      history("快照里有疑似凭据", ["show", "3", "--json"], { show: "show", number: 3n, json: true }),
      history("键从 null 变成缺省也算改动", ["show", "4", "--json"], { show: "show", number: 4n, json: true }),
      history("快照缺失", ["show", "5"], { show: "show", number: 5n }),
      history("没有这一条", ["show", "99"], { show: "show", number: 99n }),
    ]);
    compare(empty, [
      { name: "还没有写入记录", argv: ["history"], args: pyargs(empty, ["config", "history"], { show: null, number: null, json: false }) },
    ]);
  });
});

describe("config secret check 与 remove", () => {
  it("off 模式、file 模式、名字不合法", () => {
    const repo = gitRepo("secret-cmd");
    const home = join(ROOT, "xdg");
    mkdirSync(join(home, "code-kit", "secrets"), { recursive: true });
    const secret = (action: string, name: string): Run => ({
      name: `secret ${action} ${name}`,
      argv: ["secret", action, name],
      args: pyargs(repo, ["config", "secret"], { action, name, tty: false, no_browser: false, timeout: 600.0, verify: false }),
    });
    compare(repo, [secret("check", "THEMIS_CONTRACT_A"), secret("remove", "THEMIS_CONTRACT_A"), secret("check", "1BAD")]);
    process.env["CODEKIT_SECRET_STORE"] = "file";
    process.env["XDG_CONFIG_HOME"] = home;
    try {
      writeFileSync(join(home, "code-kit", "secrets", "THEMIS_CONTRACT_B"), "0123456789abcdef\n");
      compare(repo, [secret("check", "THEMIS_CONTRACT_B")]);
    } finally {
      process.env["CODEKIT_SECRET_STORE"] = "off";
      delete process.env["XDG_CONFIG_HOME"];
    }
  });
});
