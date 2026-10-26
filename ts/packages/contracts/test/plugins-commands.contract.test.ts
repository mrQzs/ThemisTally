// plugins 命令的命令行契约（迁移第 ③e 片）：list、show、verify、enable、disable，覆盖 kit_plugins oracle 的 P1–P17 与
// 之后几轮复审补的场景。每个场景在临时目录里复制一份真实的 plugins/ 再改坏（链接、漂移、坏 JSON、自造的插件），
// Python 走真实的 pi_dispatch.py plugins …（kit 根换成这份副本），TS 走 pyargs（context 的 kit_root 是同一个目录）。
// 每种实现各用一个新仓库跑同一串命令：每一步比较退出码、stdout、stderr，最后比较配置、快照与审计。
import { spawn, spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, realpathSync, renameSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { RUNNERS, type Runner, gitRepo, normalize, state } from "./config-cli.ts";
import { type CliRun, REPO, removeDir, runPythonCliAt, runTsCli, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("plugins-cmd"));
const SAVED: Record<string, string | undefined> = {};
beforeAll(() => {
  for (const [name, value] of Object.entries({ CODEKIT_SECRET_STORE: "off", CODEKIT_ACTOR: "user", TYPESAFE_API_KEY: undefined })) {
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

const CRLF = String.fromCharCode(13, 10);
const LF = String.fromCharCode(10);
const BS = String.fromCharCode(92);

// --- 命令 -------------------------------------------------------------------------------------------

interface Step {
  readonly label: string;
  readonly argv: string[];
  readonly fields: Record<string, unknown>;
  readonly action: string;
}

const WRITE = { allow_permission: [], dry_run: false, json: false, expect_state: null };
const list = (json = false): Step => ({ label: `list${json ? " --json" : ""}`, action: "list", argv: ["list", ...(json ? ["--json"] : [])], fields: { json } });
const show = (id: string, json = false): Step => ({ label: `show ${id}${json ? " --json" : ""}`, action: "show", argv: ["show", id, ...(json ? ["--json"] : [])], fields: { plugin_id: id, json } });
const verify = (id: string | null = null, json = false): Step => ({
  label: `verify ${id ?? ""}${json ? " --json" : ""}`,
  action: "verify",
  argv: ["verify", ...(id === null ? [] : [id]), ...(json ? ["--json"] : [])],
  fields: { plugin_id: id, json },
});
interface MutateOptions {
  readonly permissions?: string[];
  readonly dryRun?: boolean;
  readonly json?: boolean;
  readonly expectState?: string;
}
function mutation(action: "enable" | "disable", id: string, options: MutateOptions = {}): Step {
  const permissions = options.permissions ?? [];
  const argv = [
    action,
    id,
    ...permissions.flatMap((name) => ["--allow-permission", name]),
    ...(options.dryRun ? ["--dry-run"] : []),
    ...(options.json ? ["--json"] : []),
    ...(options.expectState ? [`--expect-state=${options.expectState}`] : []),
  ];
  const fields: Record<string, unknown> = { ...WRITE, plugin_id: id, dry_run: Boolean(options.dryRun), json: Boolean(options.json), expect_state: options.expectState ?? null };
  if (action === "enable") fields["allow_permission"] = permissions;
  else delete fields["allow_permission"];
  return { label: argv.join(" "), action, argv, fields };
}
const enable = (id: string, options: MutateOptions = {}): Step => mutation("enable", id, options);
const disable = (id: string, options: MutateOptions = {}): Step => mutation("disable", id, options);

function runStep(runner: Runner, kit: string, repo: string, cwd: string, step: Step): CliRun {
  if (runner === "python") return runPythonCliAt(kit, ["--repo", repo, "plugins", ...step.argv], cwd);
  return runTsCli(runner, { command: ["plugins", step.action], repo, ...step.fields, context: { kit_root: kit, lock_wait_seconds: 5.0 } }, cwd);
}

// --- 夹具 -------------------------------------------------------------------------------------------

interface Kit {
  readonly root: string;
  readonly plugin: (id: string) => string;
}

function copyKit(name: string): Kit {
  const root = join(ROOT, "kits", name);
  cpSync(join(REPO, "plugins"), join(root, "plugins"), { recursive: true });
  return { root, plugin: (id) => join(root, "plugins", id) };
}

const readJson = (path: string): Record<string, unknown> => JSON.parse(readFileSync(path, "utf8")) as Record<string, unknown>;

/** 插件锁里第一个资源的仓库相对路径。 */
function firstResource(kit: Kit, id: string): string {
  const lock = readJson(join(kit.plugin(id), "lock.json")) as { plugins: { resources: { path: string }[] }[] };
  return (lock.plugins[0] as { resources: { path: string }[] }).resources[0]?.path as string;
}

/** 照 oracle 的 build_consistent，用 codekit 的 build_lock 造一份自洽的 manifest 与锁（夹具，不在比较之列）。 */
function buildPlugin(kit: Kit, id: string, options: { permissions?: string[]; dependsOn?: string[]; resource?: string } = {}): void {
  const resource = options.resource ?? `plugins/${id}/README.md`;
  const program = [
    "import json, sys",
    `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`,
    "from codekit import plugins",
    "spec = json.loads(sys.argv[1])",
    'manifest = {"record_type": "builtin-task-plugin-manifest", "schema_version": 1, "plugin_id": spec["id"], "version": "1.0.0",',
    '            "api_version": "08-plugin-v1", "roles": ["planner"], "capabilities": ["offline-reference"],',
    '            "permissions": spec["permissions"], "platforms": ["windows", "linux", "macos"], "depends_on": [], "conflicts": [],',
    '            "entrypoints": [], "resources": [{"kind": "file", "id": spec["id"] + ".readme", "path": spec["resource"], "sha256": "0" * 64}], "checks": []}',
    'lock = plugins.build_lock([manifest], compiler_sha256="0" * 64)',
    'manifest["depends_on"] = spec["depends_on"]',
    "print(json.dumps({'manifest': manifest, 'lock': lock}, ensure_ascii=False))",
  ].join(LF);
  const spec = JSON.stringify({ id, permissions: options.permissions ?? ["read-candidate"], depends_on: options.dependsOn ?? [], resource });
  const done = spawnSync(process.env["THEMIS_PYTHON"] ?? "python", ["-c", program, spec], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`build_lock 失败：${done.stderr}`);
  const { manifest, lock } = JSON.parse(done.stdout) as { manifest: unknown; lock: unknown };
  mkdirSync(kit.plugin(id), { recursive: true });
  writeFileSync(join(kit.plugin(id), "manifest.json"), JSON.stringify(manifest));
  writeFileSync(join(kit.plugin(id), "lock.json"), JSON.stringify(lock));
}

function junction(link: string, target: string): void {
  symlinkSync(target, link, "junction");
}

/** 文件换成指向副本的文件符号链接（内容不变）。 */
function fileSymlink(kit: Kit, path: string, name: string): void {
  const target = join(kit.root, "elsewhere", name);
  mkdirSync(join(kit.root, "elsewhere"), { recursive: true });
  writeFileSync(target, readFileSync(path));
  rmSync(path);
  symlinkSync(target, path, "file");
}

/** 另一个进程用 msvcrt.locking 锁住文件的第一个字节，直到调用返回的函数（以 Administrator 运行时造不出“拒绝访问”，
 * 读被锁住的字节同样读不出来：Python 报 [Errno 13]，Node 报 EBUSY）。 */
function lockFirstByte(kit: Kit, path: string): () => void {
  const marker = join(kit.root, "elsewhere", "locked.flag");
  mkdirSync(join(kit.root, "elsewhere"), { recursive: true });
  const program = ["import msvcrt, sys", "f = open(sys.argv[1], 'rb')", "msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)", "open(sys.argv[2], 'w').write('locked')", "sys.stdin.read()"].join(LF);
  const child = spawn(process.env["THEMIS_PYTHON"] ?? "python", ["-c", program, path, marker], { stdio: ["pipe", "ignore", "ignore"] });
  const deadline = Date.now() + 10_000;
  while (!existsSync(marker)) {
    if (Date.now() > deadline) throw new Error("锁不住资源文件");
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
  }
  return () => {
    child.stdin.end();
    child.kill();
  };
}

// --- 场景 -------------------------------------------------------------------------------------------

interface Scenario {
  readonly name: string;
  readonly config?: unknown;
  /** 原样写进配置文件的文字（解析不了的配置）。 */
  readonly rawConfig?: string;
  /** 改坏副本；返回函数时在场景跑完之后调用（放开锁之类）。 */
  readonly setup?: (kit: Kit) => void | (() => void);
  readonly steps: readonly Step[];
  /** Python 的输出里必须有的片段：场景确实走到了要测的路径（两边一致不代表两边都走到了）。 */
  readonly expect?: readonly string[];
  /** 在哪个目录运行、--repo 交什么：缺省是新仓库本身；outside 时两者都是不在 Git 仓库里的目录。 */
  readonly outside?: boolean;
}

function runScenario(scenario: Scenario, index: number): void {
  const kit = copyKit(`s${index}`);
  const cleanup = scenario.setup?.(kit);
  let results;
  try {
  results = RUNNERS.map((runner) => {
    const repo = scenario.outside ? join(ROOT, "outside", `s${index}-${runner}`) : gitRepo(join(ROOT, "repos", `s${index}-${runner}`));
    mkdirSync(join(repo, ".agent"), { recursive: true });
    const raw = scenario.rawConfig ?? (scenario.config === undefined ? undefined : JSON.stringify(scenario.config));
    if (raw !== undefined) writeFileSync(join(repo, ".agent", "dispatch.config.json"), raw);
    const scrub = (text: string): string => normalize(text, repo).replaceAll(kit.root.replaceAll(BS, BS + BS), "<KIT>").replaceAll(kit.root, "<KIT>");
    const steps = scenario.steps.map((step) => {
      const result = runStep(runner, kit.root, repo, repo, step);
      return { step: step.label, status: result.status, stdout: scrub(result.stdout.toString("utf8")), stderr: scrub(result.stderr.toString("utf8")) };
    });
    return { steps, state: scenario.outside ? null : state(repo) };
  });
  } finally {
    if (typeof cleanup === "function") cleanup();
  }
  const python = results[0] as (typeof results)[number];
  const output = JSON.stringify(python.steps);
  for (const fragment of scenario.expect ?? []) expect(output, `${scenario.name}：${fragment}`).toContain(fragment);
  for (const [position, other] of results.slice(1).entries()) {
    const differ = other.steps.findIndex((step, at) => JSON.stringify(step) !== JSON.stringify(python.steps[at]));
    expect(differ === -1 ? null : { runner: RUNNERS[position + 1], python: python.steps[differ], other: other.steps[differ] }, scenario.name).toEqual(null);
    expect(other.state, scenario.name).toEqual(python.state);
  }
}

const SCENARIOS: readonly Scenario[] = [
  {
    name: "P1 现有的插件全部一致",
    expect: ["READY", "decisions 一致", "锁 generation"],
    config: {},
    steps: [list(), list(true), verify(), verify(null, true), show("code-change"), show("decisions", true), show("decisions")],
  },
  {
    name: "P2 资源改一个字节、只差 CRLF、多出题库清单",
    expect: ["仅行尾不同（CRLF）", "与锁不一致", "题库与内容锁不一致", "资源不一致", "无法启用 docs-checks"],
    config: {},
    setup: (kit) => {
      const one = join(kit.root, firstResource(kit, "docs-checks"));
      const bytes = readFileSync(one);
      bytes[0] = (bytes[0] as number) ^ 1;
      writeFileSync(one, bytes);
      const crlf = join(kit.root, firstResource(kit, "python-checks"));
      writeFileSync(crlf, readFileSync(crlf, "utf8").replaceAll(CRLF, LF).replaceAll(LF, CRLF));
      writeFileSync(join(kit.plugin("decisions"), "questions", "zz-extra.json"), JSON.stringify({ id: "zz-extra", version: "1.0.0", questions: {} }));
    },
    steps: [list(), verify(null, true), show("docs-checks"), show("python-checks", true), verify("decisions"), enable("docs-checks")],
  },
  {
    name: "P3、P4 lock_sha256 与 manifest 漂移",
    expect: ["漂移", "lock.json：E_PLUGIN_LOCK", "无法启用 code-change"],
    config: {},
    setup: (kit) => {
      const lockPath = join(kit.plugin("code-change"), "lock.json");
      const lock = readJson(lockPath);
      lock["lock_sha256"] = "1".repeat(64);
      writeFileSync(lockPath, JSON.stringify(lock));
      const manifestPath = join(kit.plugin("docs-change"), "manifest.json");
      const manifest = readJson(manifestPath);
      manifest["version"] = "9.9.9";
      writeFileSync(manifestPath, JSON.stringify(manifest));
    },
    steps: [verify("code-change"), verify("docs-change", true), show("docs-change"), list(), enable("code-change")],
  },
  {
    name: "P5 链接：插件目录、manifest、锁、题库目录、资源越界",
    expect: ["无效：链接 plugins/repo-analysis", "manifest.json：无效：链接", "lock.json：无效：链接", "无效：链接 plugins/decisions/questions", "路径越出插件目录"],
    config: {},
    setup: (kit) => {
      const moved = join(kit.root, "elsewhere", "repo-analysis");
      mkdirSync(join(kit.root, "elsewhere"), { recursive: true });
      renameSync(kit.plugin("repo-analysis"), moved);
      junction(kit.plugin("repo-analysis"), moved);
      fileSymlink(kit, join(kit.plugin("mutation-review"), "manifest.json"), "mr-manifest.json");
      fileSymlink(kit, join(kit.plugin("regression-tests"), "lock.json"), "rt-lock.json");
      const questions = join(kit.root, "elsewhere", "questions");
      renameSync(join(kit.plugin("decisions"), "questions"), questions);
      junction(join(kit.plugin("decisions"), "questions"), questions);
      buildPlugin(kit, "oob-x", { resource: "plugins/code-change/manifest.json" });
    },
    steps: [list(), list(true), verify(null, true), show("mutation-review"), show("regression-tests", true), verify("decisions"), show("oob-x"), enable("oob-x"), disable("code-change")],
  },
  {
    name: "P6 目录名与 plugin_id 不符、重复键、坏 JSON、null；坏插件不拖垮 list",
    expect: ["目录名与 plugin_id 不一致", "解析失败：E_JSON_DUPLICATE_KEY", "解析失败：E_JSON_SYNTAX", "不是对象（内容是 null）", "lock.json：不是对象"],
    config: {},
    setup: (kit) => {
      cpSync(kit.plugin("code-change"), kit.plugin("code-change-two"), { recursive: true });
      writeFileSync(join(kit.plugin("docs-checks"), "manifest.json"), '{"plugin_id": "docs-checks", "plugin_id": "docs-checks"}');
      writeFileSync(join(kit.plugin("python-checks"), "manifest.json"), "{ not json");
      writeFileSync(join(kit.plugin("docs-change"), "lock.json"), "null");
      writeFileSync(join(kit.plugin("regression-tests"), "lock.json"), "[]");
    },
    steps: [list(), verify(null, true), show("code-change-two"), show("docs-checks", true), show("docs-change"), show("regression-tests")],
  },
  {
    name: "P7、P8 不限制时 enable 与 disable（坏插件仍进显式列表）",
    expect: ["当前不限制，所有插件都算启用", "从不限制改为显式列表", "没有变化", "plugins 段（dry-run，未写入）", "dry_run", "docs-change"],
    config: {},
    setup: (kit) => writeFileSync(join(kit.plugin("docs-change"), "manifest.json"), "{ not json"),
    steps: [enable("code-change"), enable("code-change", { dryRun: true }), enable("code-change", { dryRun: true, json: true }), disable("code-change", { dryRun: true }), disable("code-change"), list(), disable("code-change")],
  },
  {
    name: "P9 缺权限、授予后列出因此满足的插件",
    expect: ["缺 read-candidate", "一个不多一个不少", "以下插件也将满足权限条件", "已写入"],
    config: { plugins: { allowed_permissions: ["network-decisions"] } },
    setup: (kit) => buildPlugin(kit, "needs-two", { permissions: ["read-candidate", "write-report"] }),
    steps: [list(), enable("python-checks"), enable("python-checks", { permissions: ["read-candidate"], dryRun: true }), enable("python-checks", { permissions: ["read-candidate"] }), list(true), show("needs-two")],
  },
  {
    name: "P10 --allow-permission 多给、少给、不限制时给",
    expect: ["一个不多一个不少", "没有缺失的权限"],
    config: { plugins: { allowed_permissions: ["network-decisions"] } },
    steps: [enable("python-checks", { permissions: ["read-candidate", "network-decisions"] }), enable("python-checks", { permissions: [] }), enable("decisions", { permissions: ["read-candidate"] })],
  },
  {
    name: "P10c 不限制权限时给了 --allow-permission",
    expect: ["当前不限制权限"],
    config: {},
    steps: [enable("python-checks", { permissions: ["read-candidate"] })],
  },
  {
    name: "P11 depends_on 非空：本轮不支持",
    expect: ["本轮不支持", "无法启用 dep-x"],
    config: {},
    setup: (kit) => buildPlugin(kit, "dep-x", { dependsOn: ["code-change"] }),
    steps: [enable("dep-x"), list(), verify("dep-x"), verify("dep-x", true), show("dep-x")],
  },
  {
    name: "P12 坏插件不挡关闭；决策题库坏时的恢复路径",
    expect: ["决策插件生效且问题清单与内容锁不一致", "决策插件会因此变为 off", "已写入"],
    config: { decisions: { mode: "on" }, plugins: { enabled: ["code-change", "docs-change", "decisions"] } },
    setup: (kit) => {
      writeFileSync(join(kit.plugin("docs-change"), "manifest.json"), "{ not json");
      writeFileSync(join(kit.plugin("decisions"), "questions", "zz-extra.json"), JSON.stringify({ id: "zz-extra", version: "1.0.0", questions: {} }));
    },
    steps: [disable("code-change"), disable("decisions"), disable("code-change"), disable("docs-change"), enable("decisions")],
  },
  {
    name: "P13 plugins 段不是列表：拒绝并给修复提示",
    expect: ["修复：config"],
    config: { plugins: { enabled: null, allowed_permissions: 3, _keep: "it's" } },
    steps: [list(), verify(), show("code-change"), enable("code-change"), disable("code-change")],
  },
  {
    name: "P13 plugins 段整个不是对象",
    expect: ["修复：config"],
    config: { plugins: "x", decisions: { mode: "on" } },
    steps: [list(), enable("code-change")],
  },
  {
    name: "P16、P17 关掉 decisions 提示 off、dry-run 不落盘、enabled 拼错",
    expect: ["决策插件会因此变为 off", "doc-change 未安装", "dry_run"],
    config: { plugins: { enabled: ["code-change", "decisions", "doc-change"] } },
    steps: [disable("decisions", { dryRun: true }), disable("decisions", { dryRun: true, json: true }), disable("decisions"), verify(), verify(null, true), list(), disable("doc-change")],
  },
  {
    name: "G2、B3 不存在的插件、ID 不合法、ID 末尾带换行",
    expect: ["插件不存在或未安装：ghost", "插件 ID 不合法"],
    config: {},
    steps: [show("ghost"), verify("ghost"), enable("ghost"), disable("ghost"), show("Bad_ID"), enable(`code-change${LF}`)],
  },
  {
    name: "M3 plugins 根是链接",
    expect: ["无效：链接 plugins"],
    config: { plugins: { enabled: ["code-change"] } },
    setup: (kit) => {
      const moved = join(kit.root, "real-plugins");
      renameSync(join(kit.root, "plugins"), moved);
      junction(join(kit.root, "plugins"), moved);
    },
    steps: [list(), list(true), verify(), verify(null, true), show("code-change")],
  },
  {
    name: "令牌过期、配置解析不了、嵌套很深",
    expect: ["在预览之后被改过", "令牌格式不对", "--json 只与 --dry-run 一起用"],
    config: { plugins: { enabled: ["code-change"] } },
    steps: [enable("docs-change", { expectState: `v1;config=${"0".repeat(64)}` }), enable("docs-change", { expectState: "v1;bogus" }), enable("docs-change", { json: true })],
  },
];

describe("plugins 命令", () => {
  for (const [index, scenario] of SCENARIOS.entries()) {
    it(scenario.name, () => runScenario(scenario, index));
  }

  it.runIf(process.platform === "win32")("资源读不出来（别的进程锁住了字节）：锁列无效、资源不一致", () => {
    runScenario(
      {
        name: "资源读取失败",
        config: {},
        expect: ["资源读取失败：资源", "[Errno 13] Permission denied", "无法启用 python-checks"],
        setup: (kit) => lockFirstByte(kit, join(kit.root, firstResource(kit, "python-checks"))),
        steps: [verify("python-checks"), list(), show("python-checks", true), enable("python-checks")],
      },
      103,
    );
  });

  it("G1 不在 Git 仓库里：每个子命令都退出 2", () => {
    runScenario({ name: "G1", outside: true, expect: ["\"status\":2"], steps: [list(), show("code-change"), verify(), enable("code-change"), disable("code-change")] }, 100);
  });

  it("配置解析不了与嵌套很深的配置", () => {
    runScenario({ name: "坏配置", rawConfig: "{not json", steps: [list(), verify(), enable("code-change")] }, 101);
    const deep = { plugins: { enabled: JSON.parse(`${"[".repeat(3000)}${"]".repeat(3000)}`) as unknown } };
    runScenario({ name: "嵌套很深", config: deep, steps: [list(), enable("code-change")] }, 102);
  });
});
