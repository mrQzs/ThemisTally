// doctor 与 smoke（迁移第 ④b7d 片）。每个场景三份实现各跑一次（Python 走真实的命令行，TS 走启动器交来的规整参数），比退出码、
// 标准输出与标准错误，以及 --out 写出的文件；smoke 另比临时目录里留下的东西。
//   - doctor：PATH 只留假的 pi、claude、codex 与 git、node、python（fake-cli.ts），pi 的回答按场景改 fake-pi.json。凭据库关掉
//     （CODEKIT_SECRET_STORE=off），官方端点的环境变量删掉；--probe-decisions 只对本机另起进程的假端点。doctor 不改被检查的目录
//     （--out 除外），一个场景的三次运行共用一份。
//   - kit 的布局、安装记录、决策模块缺失、问题清单经过链接：拷一份 kit（scripts 与 plugins），Python 直接跑拷贝里的
//     pi_dispatch.py（KIT_ROOT 才是拷贝），TS 的 context.kit_root 给同一个目录。
//   - smoke：pi 是本文件写的 smoke_pi.py（PI_DISPATCH_PI_CMD），按 SMOKE_SCENARIO 演各种失败；临时目录指向各自的空目录。
//   - 路径、时间、用时、mkdtemp 的随机后缀与探测的延迟换成占位符；崩溃只比退出码。不写转义序列。
import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { cpSync, existsSync, readFileSync, readdirSync, realpathSync, renameSync, rmSync, symlinkSync } from "node:fs";
import { basename, delimiter, join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { PYTHON, TS_CONTEXT, json, sha } from "./attempt-fixtures.ts";
import { fileSecretStore } from "./endpoint-fixtures.ts";
import { dirOf, installFakeCli } from "./fake-cli.ts";
import { type CliRun, REPO as KIT, runDispatcherLauncherCli, runPythonCli, runTsCli } from "./harness.ts";
import { LF, RUNNERS, type Runner, git, newRepo, normalize, put, removeCreated, snapshotDir, tempDir } from "./repo-fixtures.ts";

const children: ChildProcess[] = [];
afterAll(() => {
  for (const child of children) child.kill();
  removeCreated();
});

/** 本机的 platform.python_version() 与 platform.machine()：启动器交给 TS 的 context 里就是它们（迁移计划 D1）。 */
const [PY_VERSION = "", MACHINE = ""] = spawnSync(PYTHON, ["-c", "import platform; print(platform.python_version()); print(platform.machine())"], {
  encoding: "utf8",
}).stdout.split(LF).map((line) => line.trim());
const CONTEXT = { ...TS_CONTEXT, python: PY_VERSION, machine: MACHINE };
const KEY = "sk-THEMISCONTRACTabcdefghijklmnop";
const DECISIONS_KEY = "THEMIS_CONTRACT_DECISIONS_KEY";

function withEnv<T>(env: Record<string, string | undefined>, body: () => T): T {
  const saved = Object.fromEntries(Object.keys(env).map((key) => [key, process.env[key]]));
  const apply = (values: Record<string, string | undefined>): void => {
    for (const [key, value] of Object.entries(values)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  apply(env);
  try {
    return body();
  } finally {
    apply(saved);
  }
}

const crashed = (stderr: string): boolean => stderr.includes("Traceback (most recent call last)") || stderr.includes("崩溃（Python 在这里会打印堆栈）");

const scrub = (text: string): string =>
  text
    .replace(/"latency_ms": [0-9]+/gu, '"latency_ms": <MS>')
    .replace(/"wall_seconds": [0-9.e-]+/gu, '"wall_seconds": <S>')
    .replace(/pi-smoke-[a-z0-9_]{8}/gu, "pi-smoke-<R>");

const readOrNull = (file: string): string | null => (existsSync(file) ? readFileSync(file, "utf8") : null);

/** Path.write_text 写出的样子：文本模式，Windows 上换行是 CRLF（与 Python 的标准输出相同）。 */
const CRLF = String.fromCharCode(13, 10);
const textMode = (text: string): string => (process.platform === "win32" ? text.replaceAll(CRLF, LF).replaceAll(LF, CRLF) : text);

// --- doctor ------------------------------------------------------------------------------------------

const BIN = realpathSync.native(tempDir("doc-bin"));
const FAKE_PATH = installFakeCli(BIN);
/** 没有假的 pi、claude、codex 的 PATH。 */
const BARE_PATH = FAKE_PATH.split(delimiter).filter((dir) => dir !== BIN).join(delimiter);
const GIT_DIR = dirOf("git");
const NO_GIT_PATH = FAKE_PATH.split(delimiter).filter((dir) => dir !== GIT_DIR).join(delimiter);
const AGENT = realpathSync.native(tempDir("doc-agent"));
/** ~/.pi/agent 里有 Pi 下载的 rg、fd，全局 AGENTS.md 与 SYSTEM.md（后者让上下文取证带一条 warning）。 */
const AGENT_TOOLS = realpathSync.native(tempDir("doc-agent-tools"));
put(AGENT_TOOLS, "bin/rg.exe", "x");
put(AGENT_TOOLS, "bin/fd.exe", "x");
put(AGENT_TOOLS, "AGENTS.md", "全局规则" + LF);
put(AGENT_TOOLS, "SYSTEM.md", "系统提示词" + LF);
const EMPTY_GITCONFIG = join(realpathSync.native(tempDir("doc-gitconfig")), "empty.gitconfig");
put(join(EMPTY_GITCONFIG, ".."), "empty.gitconfig", "");
const OUTSIDE = realpathSync.native(tempDir("doc-outside"));
put(OUTSIDE, "AGENTS.md", "仓库之外的规则" + LF);

/** 文件凭据库里的假值（切换 c3b；test_dispatch 2846）：环境变量里没有，doctor 从文件凭据库读。 */
const STORED_VALUE = "THEMIS_CONTRACT_stored_value_0123456789";
const STORE_ENV = fileSecretStore(DECISIONS_KEY, STORED_VALUE);

const DOCTOR_ENV: Record<string, string | undefined> = {
  PATH: FAKE_PATH,
  PI_DISPATCH_PI_CMD: undefined,
  PI_CODING_AGENT_DIR: AGENT,
  CODEKIT_SECRET_STORE: "off",
  TYPESAFE_API_KEY: undefined,
  [DECISIONS_KEY]: undefined,
  PYTHONDONTWRITEBYTECODE: "1",
};

interface Reply {
  readonly out?: string;
  readonly err?: string;
  readonly code?: number;
}
type Spec = Record<string, Reply>;

const RESOURCE = ["--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-mcp"];
const helpText = (drop: readonly string[] = []): string =>
  [
    "Usage: pi [options] [prompt]",
    "",
    "Options:",
    "  --provider <name>        Provider",
    "  --model <id>             Model ID",
    "  --thinking <level>       Thinking level: off, minimal, low, medium, high, xhigh",
    "  --mode <mode>            Output mode",
    "  --no-session             Do not save the session",
    "  --tools <list>           Allowed tools",
    ...RESOURCE.map((flag) => `  ${flag}`),
    "  --no-context-files       Skip AGENTS.md",
    "  --list-models [search]   List models",
    "",
    "Built-in Tool Names:",
    "  read     - Read file contents",
    "  write    - Write files",
    "",
  ]
    .filter((line) => !drop.some((flag) => line.trim().startsWith(flag)))
    .join(LF);
const TABLE = ["provider   model            context", "step       step-5           256K", "step       step-5-preview   256K", ""].join(LF);
const GOOD: Spec = {
  version: { out: "pi 0.87.0" + LF },
  help: { out: helpText() },
  list: { out: TABLE },
  auth: { out: '{"ok": true}' + LF },
};

interface DoctorOptions {
  readonly provider?: string;
  readonly model?: string;
  readonly thinking?: string;
  readonly out?: string;
  readonly probe?: boolean;
}

const doctorArgv = (o: DoctorOptions): string[] => [
  ...(o.provider === undefined ? [] : ["--provider", o.provider]),
  ...(o.model === undefined ? [] : ["--model", o.model]),
  ...(o.thinking === undefined ? [] : ["--thinking", o.thinking]),
  ...(o.out === undefined ? [] : ["--out", o.out]),
  ...(o.probe ? ["--probe-decisions"] : []),
];

/** 被检查的目录：repo 是 --repo（也是当前目录）；kit 在时从这份拷贝运行。 */
interface Place {
  readonly repo: string;
  readonly kit?: string;
}

function runDoctor(runner: Runner, place: Place, o: DoctorOptions): CliRun {
  const argv = ["--repo", place.repo, "doctor", ...doctorArgv(o)];
  if (runner === "python") {
    if (place.kit === undefined) return runPythonCli(argv, place.repo);
    const done = spawnSync(PYTHON, [join(place.kit, "scripts", "pi_dispatch.py"), ...argv], { cwd: place.repo });
    return { status: done.status ?? -1, stdout: done.stdout, stderr: done.stderr };
  }
  if (runner === "launcher") return runDispatcherLauncherCli(argv, place.repo, false, place.kit);
  const pyargs = {
    command: ["doctor"], repo: place.repo, provider: o.provider ?? null, model: o.model ?? null, thinking: o.thinking ?? null,
    out: o.out ?? null, probe_decisions: o.probe ?? false, context: { ...CONTEXT, kit_root: place.kit ?? KIT },
  };
  return runTsCli(runner, pyargs, place.repo);
}

interface DoctorCase {
  readonly label: string;
  readonly status: number;
  readonly options?: DoctorOptions;
  readonly spec?: Spec;
  readonly env?: Record<string, string | undefined>;
  /** 建被检查的目录（缺省是一份干净的仓库）。 */
  readonly setup?: () => Place;
  readonly text?: string | readonly string[];
  readonly absent?: readonly string[];
  /** --out 写出的文件（相对 --repo）。 */
  readonly outFile?: string;
}

/** 一份仓库（newRepo：AGENTS.md 与忽略 .agent/runs/ 的 .gitignore 已提交），files 一起提交，edit 在提交之后动手。 */
const plain = (files: Record<string, string> = {}, edit?: (repo: string) => void) => (): Place => {
  const { repo } = newRepo("doc", files);
  edit?.(repo);
  return { repo };
};
const withConfig = (config: unknown, edit?: (repo: string) => void): (() => Place) =>
  plain({}, (repo) => {
    put(repo, ".agent/dispatch.config.json", typeof config === "string" ? config : json(config));
    edit?.(repo);
  });

const SKILLS = ["check-pi-env", "plan-task", "dispatch-pi", "review-pi"];
function skillFiles(sources: readonly string[], copies: Record<string, string>): Record<string, string> {
  const files: Record<string, string> = {};
  for (const name of sources) files[`.agents/skills/${name}/SKILL.md`] = `# ${name}` + LF;
  for (const [name, text] of Object.entries(copies)) files[`.claude/skills/${name}/SKILL.md`] = text;
  return files;
}
const SAME_COPIES = Object.fromEntries(SKILLS.map((name) => [name, `# ${name}` + LF]));

/** 一份 kit 的拷贝（scripts 与 plugins，不带 __pycache__），自己也是 Git 仓库：doctor 就在它里面跑。不带选择文件
 * （它不随 kit 安装）：python 那一边直接起拷贝里的 pi_dispatch.py，带上它就会去找拷贝里没有的 TS（切换 d 之后）。 */
const kitPlace = (edit: (kit: string) => void = () => undefined) => (): Place => {
  const kit = realpathSync.native(tempDir("doc-kit"));
  cpSync(join(KIT, "scripts"), join(kit, "scripts"), {
    recursive: true, filter: (src) => !src.includes("__pycache__") && basename(src) !== "kernel-impl.json",
  });
  cpSync(join(KIT, "plugins"), join(kit, "plugins"), { recursive: true });
  put(kit, ".gitignore", ".agent/runs/" + LF);
  put(kit, "AGENTS.md", "# AGENTS" + LF);
  git(kit, "init", "-q");
  git(kit, "config", "core.autocrlf", "false");
  git(kit, "add", "-A");
  git(kit, "commit", "-q", "-m", "kit");
  edit(kit);
  return { repo: kit, kit };
};

/** 本机另起进程的假端点：不管问什么都回同一个状态码与正文。 */
const ENDPOINT = join(realpathSync.native(tempDir("doc-endpoint")), "endpoint.mjs");
put(join(ENDPOINT, ".."), "endpoint.mjs", [
  'import { createServer } from "node:http";',
  "const status = Number(process.argv[2]);",
  "const body = process.argv[3];",
  "const server = createServer((request, response) => {",
  "  request.resume();",
  '  request.on("end", () => {',
  '    response.writeHead(status, { "Content-Type": "application/json", Connection: "close" });',
  "    response.end(body);",
  "  });",
  "});",
  'server.listen(0, "127.0.0.1", () => process.stdout.write(String(server.address().port) + String.fromCharCode(10)));',
  "",
].join(LF));

async function startEndpoint(status: number, body: string): Promise<number> {
  const child = spawn(process.execPath, [ENDPOINT, String(status), body], { stdio: ["ignore", "pipe", "inherit"] });
  children.push(child);
  return new Promise<number>((resolve, reject) => {
    child.stdout?.once("data", (chunk: Buffer) => resolve(Number(chunk.toString("utf8").trim())));
    child.once("exit", () => reject(new Error("假端点没起来")));
  });
}

const ports = { ok: 0, fail: 0 };
beforeAll(async () => {
  ports.ok = await startEndpoint(200, JSON.stringify({ answers: { ok: { type: "noul", noul: 0.97 } }, usage: { input_tokens: 31 }, model: "m" }));
  ports.fail = await startEndpoint(500, '{"error": "boom"}');
});
const probeConfig = (port: () => number) => (): Place =>
  withConfig({ decisions: { mode: "shadow", base_url: `http://127.0.0.1:${port()}`, api_key_env: DECISIONS_KEY } })();

const DOCTOR: DoctorCase[] = [
  // --- pi 与规划端 ---
  { label: "干净的仓库，不带执行模型：只有提示", status: 0,
    text: ["未检查执行模型与凭据", "没有找到 Code-Kit 技能", "未找到 rg", "未找到 fd", '"layout": "external"', '"claude_code": "claude 9.9.9 (fake)"', '"codex": ""'] },
  { label: "PATH 上没有 git：问题，仓库那一节读不出", status: 1, env: { PATH: NO_GIT_PATH },
    text: ["git 不可用", "未在 Git 仓库中运行：未找到 git", '"layout": "unknown"'] },
  { label: "只带 --provider：不核对模型", status: 0, options: { provider: "step" }, text: "未检查执行模型与凭据", absent: ['"executor_model_list"'] },
  { label: "带执行模型：模型列表、凭据与思考级别都就绪", status: 0, options: { provider: "step", model: "step-5", thinking: "high" },
    text: ['"executor_model_listed": true', '"executor_auth_check": {'] },
  { label: "模型不在列表、凭据没就绪、思考级别不支持", status: 1, options: { provider: "step", model: "step-9", thinking: "ultra" },
    spec: { ...GOOD, auth: { out: `{"ok": false, "detail": "${KEY}"}`, code: 1 } }, absent: [KEY],
    text: ["执行模型 step/step-9 不在可用模型列表中", "执行模型凭据未就绪（pi auth check --no-refresh 退出码 1）", "思考级别 ultra 不受本机 pi 支持"] },
  // 覆盖审计的缺口（切换 c3a；test_dispatch 766、772）：pi 0.87 没有可用或匹配的模型时只输出一句说明，不输出表格
  { label: "pi 一个模型都没有", status: 1, options: { provider: "step", model: "step-5", thinking: "high" },
    spec: { ...GOOD, list: { out: `No models available. Use /login to log into a provider via OAuth or API key. See:${LF}  /pi/docs/providers.md${LF}` } },
    text: ['"empty_reason": "no_models"', "pi 没有任何可用模型"] },
  { label: "没有与执行模型匹配的", status: 1, options: { provider: "step", model: "step-5", thinking: "high" },
    spec: { ...GOOD, list: { out: `No models matching "step-5"${LF}` } },
    text: ['"empty_reason": "no_match"', "没有与 step-5 匹配的"] },
  { label: "--list-models 失败：错误里的凭据遮掉", status: 1, options: { provider: "step", model: "step-5" },
    // 先脱敏再截：stderr_tail 取最后 300 个字符，问题里取前 200 个
    spec: { ...GOOD, list: { err: `${"前".repeat(150)} models.json 解析失败：apiKey ${KEY} ${"后".repeat(280)}`, code: 2 } }, absent: [KEY],
    text: "pi --list-models 执行失败（退出码 2）" },
  { label: "pi 的版本只在 stderr、低于 0.80.4：提示升级", status: 0, spec: { ...GOOD, version: { err: "0.80.3" + LF } }, text: "pi 版本低于 0.80.4，建议升级" },
  { label: "pi 的版本读不出：问题", status: 1, spec: { ...GOOD, version: { out: "dev build" + LF, err: "warn" } }, text: "无法读取 pi 版本" },
  { label: "pi --help 的一部分在 stderr：两路接起来解析", status: 0, spec: { ...GOOD, help: { out: helpText(["--no-mcp"]), err: "  --no-mcp" + LF } },
    absent: ["pi 缺少参数"] },
  { label: "pi 缺参数：--no-mcp 与 --no-context-files", status: 1, spec: { ...GOOD, help: { out: helpText(["--no-mcp", "--no-context-files"]) } },
    text: "pi 缺少参数：--no-mcp, --no-context-files" },
  { label: "PATH 上没有 pi、claude、codex", status: 1, env: { PATH: BARE_PATH }, text: ["PATH 中找不到 pi", "PATH 中没有 claude 或 codex"] },
  { label: "PI_DISPATCH_PI_CMD 指向不存在的程序：版本读不出、参数全缺", status: 1,
    env: { PI_DISPATCH_PI_CMD: JSON.stringify([join(BIN, "no-such-pi.exe")]) }, text: ["无法读取 pi 版本", "pi 缺少参数：--provider"] },
  { label: "PI_DISPATCH_PI_CMD 写错：记成问题", status: 1, env: { PI_DISPATCH_PI_CMD: JSON.stringify(["", 1]) },
    text: "PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组或单个可执行文件路径" },
  { label: "~/.pi/agent/bin 里有 rg 与 fd、全局有 AGENTS.md 与 SYSTEM.md", status: 0, env: { PI_CODING_AGENT_DIR: AGENT_TOOLS },
    absent: ["未找到 rg", "未找到 fd"], text: ['"pi_context_from_repo_root": {', "全局 SYSTEM.md 会改变执行器系统提示词"] },
  // --- --out ---
  { label: "--out 写到 _env：文件与标准输出相同（文本模式写）", status: 0, options: { out: ".agent/runs/_env/doctor.json" }, outFile: ".agent/runs/_env/doctor.json" },
  { label: "--out 写到别处：用法错误", status: 2, options: { out: ".agent/plans/doctor.json" }, text: "--out 只能指向 .agent/runs/_env/ 或 .agent/runs/_reports/ 下的文件" },
  // --- 仓库 ---
  { label: "--repo 不是 Git 仓库：记一条提示，kit 布局 unknown", status: 0, setup: () => ({ repo: realpathSync.native(tempDir("doc-plain")) }),
    text: ["未在 Git 仓库中运行：当前目录不在 Git 仓库中：", '"layout": "unknown"'] },
  { label: "仓库还没有提交：HEAD 读不出，记一条提示", status: 0,
    setup: () => {
      const repo = realpathSync.native(tempDir("doc-empty"));
      git(repo, "init", "-q");
      return { repo };
    },
    text: "未在 Git 仓库中运行：git rev-parse HEAD 失败：" },
  { label: "AGENTS.md 没提交、CLAUDE.md 没有 @AGENTS.md、.agent/runs/ 没被忽略、有改动", status: 1,
    setup: plain({ ".gitignore": "node_modules/" + LF }, (repo) => {
      git(repo, "rm", "-q", "--cached", "AGENTS.md");
      git(repo, "commit", "-q", "-m", "drop");
      put(repo, "CLAUDE.md", "# CLAUDE" + LF);
      put(repo, "src/a.ts", "export const a = 2;" + LF);
    }),
    text: ["AGENTS.md 尚未提交", "CLAUDE.md 尚未提交", "仓库有 CLAUDE.md，但其中没有 @AGENTS.md", ".agent/runs/ 未被 .gitignore 忽略", '"dirty_entries": 3'] },
  { label: "仓库根目录没有 AGENTS.md", status: 0, setup: plain({}, (repo) => rmSync(join(repo, "AGENTS.md"))), text: "仓库根目录没有 AGENTS.md" },
  { label: "暂存的改名：porcelain -z 里算两条", status: 0, setup: plain({}, (repo) => git(repo, "mv", "src/a.ts", "src/b.ts")), text: '"dirty_entries": 2' },
  { label: "AGENTS.md 超过 Codex 的读取上限；CLAUDE.md 带 @AGENTS.md", status: 0,
    setup: plain({ "AGENTS.md": "a".repeat(40000), "CLAUDE.md": "见 @AGENTS.md" + LF }), absent: ["其中没有 @AGENTS.md"],
    text: ["AGENTS.md 有 40000 字节，超过 Codex 默认读取上限 32768 字节", '"agents_md_bytes": 40000'] },
  { label: "CLAUDE.md 是指向 AGENTS.md 的链接：不提示", status: 0, absent: ["其中没有 @AGENTS.md", "指向仓库之外"],
    setup: plain({}, (repo) => symlinkSync(join(repo, "AGENTS.md"), join(repo, "CLAUDE.md"), "file")) },
  { label: "AGENTS.md、CLAUDE.md 链接到仓库之外", status: 0,
    setup: plain({}, (repo) => {
      rmSync(join(repo, "AGENTS.md"));
      symlinkSync(join(OUTSIDE, "AGENTS.md"), join(repo, "AGENTS.md"), "file");
      symlinkSync(join(OUTSIDE, "AGENTS.md"), join(repo, "CLAUDE.md"), "file");
    }),
    text: ["AGENTS.md 是指向仓库之外的链接", "CLAUDE.md 是指向仓库之外的链接"] },
  { label: "技能：四个都在，Claude Code 副本有一处不一致", status: 0,
    setup: plain(skillFiles(SKILLS, { ...SAME_COPIES, "plan-task": "# 改过" + LF })), text: ["不一致 1 处", '"installed": true'] },
  { label: "技能：只在 .claude/skills（1.x 布局）", status: 0, setup: plain(skillFiles([], SAME_COPIES)), text: "技能仍只在 .claude/skills（1.x 布局）" },
  { label: "技能：.agents/skills 缺两个，没有副本", status: 0, setup: plain(skillFiles(["check-pi-env", "plan-task"], {})),
    text: [".agents/skills 中缺少技能：dispatch-pi, review-pi", '"installed": false'] },
  { label: "技能：.claude 是 junction，不读副本", status: 0,
    setup: plain(skillFiles(SKILLS, {}), (repo) => {
      const elsewhere = realpathSync.native(tempDir("doc-claude"));
      put(elsewhere, "skills/plan-task/SKILL.md", "# plan-task" + LF);
      symlinkSync(elsewhere, join(repo, ".claude"), "junction");
    }),
    text: ["是符号链接或 junction", '"claude_skill_adapters": {'] },
  { label: "没有 Git 作者身份：提示", status: 0,
    env: { GIT_CONFIG_GLOBAL: EMPTY_GITCONFIG, GIT_CONFIG_NOSYSTEM: "1", GIT_AUTHOR_NAME: undefined, GIT_AUTHOR_EMAIL: undefined,
      GIT_COMMITTER_NAME: undefined, GIT_COMMITTER_EMAIL: undefined, EMAIL: undefined },
    setup: plain({}, (repo) => git(repo, "config", "user.useConfigOnly", "true")),
    text: ["没有可用的 Git 作者身份（GIT_AUTHOR_IDENT）", '"git_identity": false'] },
  // --- kit ---
  { label: "kit 就是本仓库（source）：缺两个文件", status: 0,
    setup: kitPlace((kit) => ["kit_logs.py", "kit_plugins.py"].forEach((name) => rmSync(join(kit, "scripts", name)))),
    text: ['"layout": "source"', "下缺少 scripts/kit_logs.py、scripts/kit_plugins.py）"] },
  { label: "kit 装在本仓库里（installed），没有安装记录", status: 0, setup: kitPlace((kit) => rmSync(join(kit, "scripts", "kit_install.py"))),
    text: ['"layout": "installed"', "没有安装记录 .agent/kit-install.json"] },
  { label: "installed：安装记录里有改过、缺掉与原样的文件", status: 0,
    setup: kitPlace((kit) => {
      rmSync(join(kit, "scripts", "kit_install.py"));
      put(kit, ".agent/kit-install.json", json({
        kit_version: "2.12.0",
        files: {
          "scripts/kit_logs.py": "0".repeat(64),
          "scripts/gone.py": "abc",
          "scripts/kit_config.py": sha(readFileSync(join(kit, "scripts", "kit_config.py"))),
          "plugins/decisions/manifest.json": 5,
        },
      }));
    }),
    text: ["kit 文件在安装之后有变化：改过 2 个、缺 1 个", '"kit_commit": null'] },
  { label: "决策模块不在 kit 旁边：decisions 记 module_missing", status: 0,
    setup: kitPlace((kit) => rmSync(join(kit, "scripts", "codekit", "decisions.py"))),
    text: ['"reason": "module_missing"', "决策模块不可用"] },
  { label: "问题清单经过 junction：不读，battery_lock 记 link", status: 1,
    setup: kitPlace((kit) => {
      const elsewhere = join(realpathSync.native(tempDir("doc-questions")), "questions");
      renameSync(join(kit, "plugins", "decisions", "questions"), elsewhere);
      symlinkSync(elsewhere, join(kit, "plugins", "decisions", "questions"), "junction");
    }),
    text: ['"battery_lock": "link"', "决策插件的问题清单无效：问题清单经过链接，不读取："] },
  // --- 决策 ---
  { label: "决策配置写错：config_invalid", status: 1, setup: withConfig({ decisions: { mode: "maybe" } }),
    text: ['"reason": "config_invalid"', "dispatch.config.json 的 decisions 无效："] },
  { label: "配置里有疑似凭据：照实报告，不当作没有配置", status: 1, setup: withConfig({ note: KEY }), absent: [KEY],
    text: ['"reason": "config_invalid"', "里有疑似凭据"] },
  { label: "配置不是 JSON：决策按没有配置算", status: 0, setup: withConfig("{"), text: '"reason": "not_configured"' },
  { label: "shadow、自定义端点、凭据不在：两条提示", status: 0,
    setup: withConfig({ decisions: { mode: "shadow", base_url: "http://127.0.0.1:9", api_key_env: DECISIONS_KEY } }),
    text: ["自定义端点将不带凭据头调用", "决策功能生效（shadow）", '"probe": null'] },
  { label: "on、官方端点、凭据不在，--probe-decisions：不探测，记问题", status: 1, options: { probe: true },
    setup: withConfig({ decisions: { mode: "on", api_key_env: DECISIONS_KEY } }),
    text: ["每次调用都会记为无意见（no_key）", `--probe-decisions：凭据 ${DECISIONS_KEY} 既不在环境变量也不在凭据库里，无法探测`] },
  // 覆盖审计的缺口（切换 c3b；test_dispatch 2846）：凭据不在环境变量里、在文件凭据库里：报来源，不报值
  { label: "凭据在文件凭据库里：报 secret_source file，不出现值", status: 0, env: STORE_ENV,
    setup: withConfig({ decisions: { mode: "shadow", base_url: "http://127.0.0.1:9", api_key_env: DECISIONS_KEY } }),
    text: ['"secret_source": "file"', '"secret_store_mode": "file"'], absent: [STORED_VALUE] },
  { label: "DECISIONS_OFF 标记：配置 shadow，实际 off", status: 0,
    setup: withConfig({ decisions: { mode: "shadow", base_url: "http://127.0.0.1:9", api_key_env: DECISIONS_KEY } }, (repo) => put(repo, ".agent/DECISIONS_OFF", "")),
    text: "决策配置为 shadow，实际生效 off：marker" },
  { label: "--probe-decisions 对假端点：探测成功", status: 0, options: { probe: true }, env: { [DECISIONS_KEY]: "THEMIS_CONTRACT_fake_value" },
    setup: probeConfig(() => ports.ok), text: ['"probe": {', '"served_model": "m"'] },
  { label: "--probe-decisions 对回 500 的假端点：探测失败记问题", status: 1, options: { probe: true }, env: { [DECISIONS_KEY]: "THEMIS_CONTRACT_fake_value" },
    setup: probeConfig(() => ports.fail), text: "决策探测失败：" },
];

function doctorCase(item: DoctorCase): void {
  put(BIN, "fake-pi.json", JSON.stringify(item.spec ?? GOOD));
  const place = (item.setup ?? plain())();
  const paths = { "<REPO>": place.repo, "<KIT>": place.kit ?? KIT, "<BIN>": BIN, "<AGENT>": AGENT, "<AGENT_TOOLS>": AGENT_TOOLS, "<OUTSIDE>": OUTSIDE };
  const show = (text: string): string => scrub(normalize(text, paths));
  const results = RUNNERS.map((runner) => {
    const result = withEnv({ ...DOCTOR_ENV, ...item.env }, () => runDoctor(runner, place, item.options ?? {}));
    const out = item.outFile === undefined ? null : readOrNull(join(place.repo, ...item.outFile.split("/")));
    return { status: result.status, stdout: show(result.stdout.toString("utf8")), stderr: show(result.stderr.toString("utf8")), out: out === null ? null : show(out) };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, first.stdout + first.stderr).toBe(item.status);
  for (const wanted of typeof item.text === "string" ? [item.text] : item.text ?? []) expect(first.stdout + first.stderr).toContain(wanted);
  for (const unwanted of item.absent ?? []) expect(first.stdout + first.stderr).not.toContain(unwanted);
  if (item.outFile !== undefined) expect(first.out).toBe(textMode(first.stdout));
}

describe("doctor", () => {
  for (const item of DOCTOR) it(item.label, () => doctorCase(item), 240_000);
});

// --- smoke -------------------------------------------------------------------------------------------

const SMOKE_PI = join(realpathSync.native(tempDir("smoke-pi")), "smoke_pi.py");
put(join(SMOKE_PI, ".."), "smoke_pi.py", [
  "import json",
  "import os",
  "import sys",
  "import time",
  "from pathlib import Path",
  "",
  "args = sys.argv[1:]",
  'scenario = os.environ.get("SMOKE_SCENARIO", "ok")',
  "NL = chr(10)",
  "",
  "",
  "def opt(name):",
  "    return args[args.index(name) + 1] if name in args else None",
  "",
  "",
  "def emit(obj):",
  "    sys.stdout.buffer.write((json.dumps(obj, ensure_ascii=False) + NL).encode(" + '"utf-8"' + "))",
  "    sys.stdout.buffer.flush()",
  "",
  "",
  "def tool(call_id, name, error=False):",
  '    emit({"type": "tool_execution_start", "toolCallId": call_id, "toolName": name, "args": {"path": "smoke.txt"}})',
  '    emit({"type": "tool_execution_end", "toolCallId": call_id, "toolName": name, "result": {}, "isError": error})',
  "",
  "",
  'if "--version" in args:',
  '    print(os.environ.get("SMOKE_VERSION", "0.87.0"))',
  "    sys.exit(0)",
  "# 收到的参数记进工作目录：留下的临时目录三边逐字比较",
  'with open("argv.jsonl", "a", encoding="utf-8") as log:',
  "    log.write(json.dumps(args, ensure_ascii=False) + NL)",
  'if scenario == "hang":',
  "    time.sleep(60)",
  'if scenario == "nostart":',
  '    sys.stderr.write("Error: No API key found for provider step" + NL)',
  "    sys.exit(1)",
  'emit({"type": "agent_start"})',
  'if "smoke.txt" in args[-1]:',
  '    if scenario != "nowrite":',
  '        bad = bytes([255, 254])',
  '        Path("smoke.txt").write_bytes({"wrongtext": b"PI_TOOL_NO", "badutf8": bad, "badutf8exit": bad}.get(scenario, b"PI_TOOL_OK"))',
  '        if scenario != "nowritecall":',
  '            tool("w", "write", scenario == "toolerror")',
  '    if scenario != "noread":',
  '        tool("r", "read")',
  '    reply = "DONE"',
  "else:",
  '    reply = os.environ.get("SMOKE_REPLY", "PI_SMOKE_OK")',
  'usage = {"input": 10, "output": 2, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 12, "cost": {"total": 0.00001}}',
  'model = "other-model" if scenario == "othermodel" else opt("--model")',
  'message = {"role": "assistant", "content": [{"type": "text", "text": reply}], "provider": opt("--provider"), "model": model,',
  '           "stopReason": "stop", "usage": usage}',
  'emit({"type": "message_end", "message": message})',
  'emit({"type": "agent_end", "messages": [], "willRetry": False})',
  'if scenario != "nosettle":',
  '    emit({"type": "agent_settled"})',
  "# badutf8exit：只有第二步（写 smoke.txt 的那步）退出码不是 0",
  'if scenario == "badutf8exit" and "smoke.txt" in args[-1]:',
  "    sys.exit(3)",
  'sys.exit(int(os.environ.get("SMOKE_EXIT", "0")))',
  "",
].join(LF));

interface SmokeCase {
  readonly label: string;
  readonly status: number;
  readonly scenario?: string;
  readonly env?: Record<string, string | undefined>;
  readonly provider?: string;
  readonly model?: string;
  readonly thinking?: string;
  readonly timeout?: number;
  readonly out?: string;
  readonly keep?: boolean;
  /** 留在临时目录里的 pi-smoke-* 有几个。 */
  readonly left: number;
  readonly text?: string | readonly string[];
  readonly absent?: readonly string[];
  readonly crash?: boolean;
}

// 凭据写成裸的 sk- 令牌：就地换成占位，后面的字符留着。先脱敏再截与先截再脱敏，截出来的 500 个码点不同
// （写成 token=… 时脱敏会吃掉后面整段，截多少都一样）
const LONG_REPLY = `PI_SMOKE_OK ${KEY} ${String.fromCodePoint(0x1f600).repeat(600)}`;

const SMOKE: SmokeCase[] = [
  { label: "两步都通过：临时目录删掉", status: 0, left: 0, text: ['"name": "no_tools"', '"name": "tools"', '"final_text": "PI_SMOKE_OK"'] },
  { label: "--keep：临时目录留着", status: 0, keep: true, left: 1 },
  { label: "--out 写到 _env", status: 0, out: ".agent/runs/_env/smoke.json", left: 0 },
  { label: "--out 写到别处：用法错误", status: 2, out: ".agent/plans/smoke.json", left: 0, text: "--out 只能指向" },
  { label: "回复里没有 PI_SMOKE_OK：第一步失败就停", status: 1, env: { SMOKE_REPLY: "hello" }, left: 1, absent: ['"name": "tools"'] },
  { label: "回复很长、带凭据：final_text 遮掉凭据、截到 500 个码点", status: 0, env: { SMOKE_REPLY: LONG_REPLY }, left: 0, absent: [KEY] },
  { label: "smoke.txt 内容不对：第二步失败", status: 1, scenario: "wrongtext", left: 1 },
  { label: "没有读回：第二步失败", status: 1, scenario: "noread", left: 1 },
  { label: "没有写：smoke.txt 不在，第二步失败", status: 1, scenario: "nowrite", left: 1 },
  { label: "写工具报错：第二步失败", status: 1, scenario: "toolerror", left: 1 },
  { label: "smoke.txt 对了却没调用写工具：第二步失败", status: 1, scenario: "nowritecall", left: 1 },
  { label: "smoke.txt 不是 UTF-8：照 Python 崩", status: 1, scenario: "badutf8", left: 1, crash: true },
  // Python 先读 smoke.txt 再看退出码与事件流：退出码不是 0 也照样读，照样崩
  { label: "smoke.txt 不是 UTF-8、第二步退出码也不是 0：照样先读，照 Python 崩", status: 1, scenario: "badutf8exit", left: 1, crash: true },
  { label: "模型从未回复：第一步失败", status: 1, scenario: "nostart", left: 1 },
  { label: "实际模型不同：第一步失败", status: 1, scenario: "othermodel", left: 1, text: "other-model" },
  { label: "退出码不是 0：第一步失败", status: 1, env: { SMOKE_EXIT: "3" }, left: 1 },
  { label: "没有 agent_settled：0.87 的 pi 判失败", status: 1, scenario: "nosettle", left: 1 },
  { label: "没有 agent_settled：0.80.3 的 pi 不要求", status: 0, scenario: "nosettle", env: { SMOKE_VERSION: "0.80.3" }, left: 0 },
  { label: "版本读不出：照样跑", status: 0, env: { SMOKE_VERSION: "dev" }, left: 0, text: '"pi_version": "dev"' },
  { label: "挂住：--timeout 1 超时", status: 1, scenario: "hang", timeout: 1, left: 1, text: '"timed_out": true' },
  { label: "provider 与 model 都不合法：先报 provider", status: 2, provider: "a b", model: "c d", left: 0, text: "无效的 provider：a b" },
  { label: "model 不合法：用法错误", status: 2, model: "c d", thinking: "ultra", left: 0, text: "无效的 model：c d" },
  { label: "--out 与 PI_DISPATCH_PI_CMD 都写错：先报 --out", status: 2, out: ".agent/plans/smoke.json", left: 0,
    env: { PI_DISPATCH_PI_CMD: JSON.stringify(["", 1]) }, text: "--out 只能指向" },
  { label: "思考级别不合法：用法错误", status: 2, thinking: "ultra", left: 0, text: "无效的思考级别：ultra" },
  { label: "PI_DISPATCH_PI_CMD 写错：用法错误", status: 2, env: { PI_DISPATCH_PI_CMD: JSON.stringify(["", 1]) }, left: 0 },
];

function runSmoke(runner: Runner, repo: string, item: SmokeCase): CliRun {
  const provider = item.provider ?? "step";
  const model = item.model ?? "step-5";
  const thinking = item.thinking ?? "high";
  const timeout = item.timeout ?? 300;
  const argv = ["--repo", repo, "smoke", "--provider", provider, "--model", model, "--thinking", thinking, "--timeout", String(timeout),
    ...(item.out === undefined ? [] : ["--out", item.out]), ...(item.keep ? ["--keep"] : [])];
  if (runner === "python") return runPythonCli(argv, repo);
  if (runner === "launcher") return runDispatcherLauncherCli(argv, repo);
  const pyargs = { command: ["smoke"], repo, provider, model, thinking, timeout, out: item.out ?? null, keep: item.keep ?? false };
  return runTsCli(runner, pyargs, repo);
}

/** 临时目录里留下的 pi-smoke-*：文件名与内容（随机后缀换成占位符）。 */
function leftovers(tmp: string, paths: Record<string, string>): Record<string, string>[] {
  return readdirSync(tmp).filter((name) => name.startsWith("pi-smoke-")).map((name) => {
    const files = snapshotDir(join(tmp, name), paths);
    return Object.fromEntries(Object.entries(files).map(([rel, text]) => [rel, scrub(text)]));
  });
}

function smokeCase(item: SmokeCase): void {
  const results = RUNNERS.map((runner) => {
    const { repo } = newRepo(`smoke-${runner}`);
    const tmp = realpathSync.native(tempDir(`smoke-tmp-${runner}`));
    const paths = { "<REPO>": repo, "<TMP>": tmp };
    const env = {
      PI_DISPATCH_PI_CMD: JSON.stringify([PYTHON, SMOKE_PI]), SMOKE_SCENARIO: item.scenario ?? "ok", PYTHONDONTWRITEBYTECODE: "1",
      TMPDIR: tmp, TEMP: tmp, TMP: tmp, SMOKE_REPLY: undefined, SMOKE_VERSION: undefined, SMOKE_EXIT: undefined, ...item.env,
    };
    const result = withEnv(env, () => runSmoke(runner, repo, item));
    const stderr = result.stderr.toString("utf8");
    const out = item.out === undefined ? null : readOrNull(join(repo, ...item.out.split("/")));
    return {
      status: result.status,
      stdout: item.crash ? "" : scrub(normalize(result.stdout.toString("utf8"), paths)),
      stderr: item.crash ? "" : scrub(normalize(stderr, paths)),
      crashed: item.crash ? crashed(stderr) : null,
      out: out === null ? null : scrub(normalize(out, paths)),
      left: leftovers(tmp, paths),
    };
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, first.stdout + first.stderr).toBe(item.status);
  expect(first.left.length, "留下的临时目录").toBe(item.left);
  if (item.crash) expect(first.crashed, "崩溃场景两边都要真崩").toBe(true);
  for (const wanted of typeof item.text === "string" ? [item.text] : item.text ?? []) expect(first.stdout + first.stderr).toContain(wanted);
  for (const unwanted of item.absent ?? []) expect(first.stdout + first.stderr).not.toContain(unwanted);
  if (item.out !== undefined && item.status === 0) expect(first.out).toBe(textMode(first.stdout));
}

describe("smoke", () => {
  for (const item of SMOKE) it(item.label, () => smokeCase(item), 240_000);
});
