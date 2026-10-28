// doctor（迁移第 ④b7d 片）：环境事实。不调用模型，不修改仓库；--out 只能写到 .agent/runs/_env/ 或 _reports/。
//   - 本机的 platform.platform()、platform.machine() 与 Python 版本由启动器放进 context（迁移计划 D1），TS 原样用。
//   - decisions 块（_doctor_decisions）在 @themis/config 的 doctor-decisions，由 cli 交进来：本包不依赖 config。
import { statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { type PyOut, pyGet } from "@themis/base/pyfmt";
import { pyReadTextReplace } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps } from "@themis/base/pyjson";
import { isWithin, normCase, normcase, purePathStr, pyExists, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, pyStrip } from "@themis/base/pyre";
import { redactObj } from "@themis/base/secrets";
import { pyWhich } from "@themis/base/pyshutil";
import { KIT_SKILLS, SKILL_SOURCE_DIR, adapterDrift, claudeSkillTarget } from "./adapters.ts";
import { sha256File } from "./evidence.ts";
import { resolvePiCommand } from "./executor.ts";
import { effectiveAutocrlf } from "./gitops.ts";
import { safeOutputPath } from "./metrics.ts";
import { KIT_LOADED_FILES } from "./patterns.ts";
import { MIN_PI_VERSION, REQUIRED_PI_FLAGS, RESOURCE_FLAGS, compareVersion, parseHelp, parseVersion, piModelReadiness, runCapture } from "./pi-cli.ts";
import { contextEvidence, piAgentDir } from "./preflight.ts";
import { TOOL_VERSION } from "./prepare.ts";
import { DispatchError, EXIT_FAIL, EXIT_OK, Repo, git, gitChecked, gitText, readJsonOr } from "./repo.ts";

const WIN = process.platform === "win32";
const LF = String.fromCharCode(10);
const CRLF = String.fromCharCode(13, 10);
const BT = String.fromCharCode(96);
const code = (text: string): string => BT + text + BT;

/** Codex 读取 AGENTS.md 的缺省上限（project_doc_max_bytes）。 */
const CODEX_PROJECT_DOC_MAX_BYTES = 32768;
/** kit_install.py 在目标仓库里写的安装记录（2.9.0）。 */
const KIT_INSTALL_RECORD = ".agent/kit-install.json";

export interface DoctorArgs {
  readonly repo: string | null;
  readonly provider: string | null;
  readonly model: string | null;
  readonly thinking: string | null;
  readonly out: string | null;
  readonly probe_decisions: boolean;
}

/** 启动器交来的本机事实（迁移计划 D1）与 kit 的位置（pi_dispatch.KIT_ROOT）。 */
export interface DoctorContext {
  readonly kitRoot: string;
  readonly platform: string;
  readonly machine: string;
  readonly python: string;
  /** _doctor_decisions：往 facts 里放 decisions，问题与提示各自追加。 */
  readonly decisions: (facts: PyDict, problems: string[], notes: string[]) => Promise<void>;
}

/** cmd_doctor：有 problems 时退出码 1。 */
export async function cmdDoctor(args: DoctorArgs, out: PyOut, context: DoctorContext): Promise<number> {
  const outPath = safeOutputPath(args.out, args.repo);
  const facts: PyDict = new Map<string, PyValue>([
    ["generated_at", utcNow()], ["tool_version", TOOL_VERSION], ["platform", context.platform], ["machine", context.machine], ["python", context.python],
  ]);
  const problems: string[] = [];
  const notes: string[] = [];
  const [gitCode, gitOut, gitErr] = await runCapture(["git", "--version"]);
  facts.set("git", pyStrip(gitOut) || pyStrip(gitErr));
  if (gitCode !== 0) problems.push("git 不可用");
  await plannerVersions(facts, notes);
  searchToolNotes(notes);
  await piFacts(args, facts, problems, notes);
  repositoryFacts(args.repo, facts, problems, notes);
  doctorKit(discoverOrNull(args.repo), context.kitRoot, facts, notes);
  await context.decisions(facts, problems, notes);
  facts.set("problems", problems);
  facts.set("notes", notes);
  facts.set("ok", !problems.length);
  const text = dumps(redactObj(facts), { ensureAscii: false, indent: 2 });
  if (outPath !== null) writeTextMode(outPath, text + LF);
  out.print(text);
  return problems.length ? EXIT_FAIL : EXIT_OK;
}

/** PATH 上的 claude、codex 的版本（起不来时是空串）。 */
async function plannerVersions(facts: PyDict, notes: string[]): Promise<void> {
  let found = false;
  for (const [tool, key] of [["claude", "claude_code"], ["codex", "codex"]] as const) {
    const toolPath = pyWhich(tool);
    if (!toolPath) continue;
    facts.set(key, pyStrip((await runCapture([toolPath, "--version"], { timeout: 30 }))[1]));
    found = true;
  }
  if (!found) notes.push("PATH 中没有 claude 或 codex（在规划端会话内运行时可忽略）");
}

function searchToolNotes(notes: string[]): void {
  const piBin = purePathStr(piAgentDir(), "bin");
  for (const tool of ["rg", "fd"]) {
    if (!pyWhich(tool) && ![tool, tool + ".exe"].some((name) => isFile(purePathStr(piBin, name)))) {
      notes.push(`未找到 ${tool}：Pi 的 grep/find 工具首次使用时会从 GitHub 下载到 ~/.pi/agent/bin`);
    }
  }
}

/** pi 的命令、版本、--help 里的参数与思考级别；带了 --provider 与 --model 时再核对模型列表、凭据与思考级别。 */
async function piFacts(args: DoctorArgs, facts: PyDict, problems: string[], notes: string[]): Promise<void> {
  try {
    const piCmd = resolvePiCommand();
    facts.set("pi_command", piCmd);
    const [, versionOut, versionErr] = await runCapture([...piCmd, "--version"], { timeout: 60 });
    const versionText = pyStrip(versionOut || versionErr);
    facts.set("pi_version", versionText);
    const version = parseVersion(versionText);
    if (!version) problems.push("无法读取 pi 版本");
    else if (compareVersion(version, MIN_PI_VERSION) < 0) notes.push(`pi 版本低于 ${MIN_PI_VERSION.join(".")}，建议升级`);
    const [, helpOut, helpErr] = await runCapture([...piCmd, ...RESOURCE_FLAGS, "--help"], { timeout: 90 });
    const info = parseHelp(helpOut + helpErr);
    const missing = [...REQUIRED_PI_FLAGS, "--no-context-files"].filter((flag) => !info.flags.includes(flag));
    facts.set("pi_help", new Map<string, PyValue>([
      ["thinking_levels", info.thinking_levels], ["builtin_tools", info.builtin_tools], ["required_flags_missing", missing],
    ]));
    if (missing.length) problems.push(`pi 缺少参数：${missing.join(", ")}`);
    if (args.provider && args.model) {
      const [readiness, found] = await piModelReadiness(piCmd, args.provider, args.model, args.thinking, info.thinking_levels, null);
      for (const [key, value] of readiness) facts.set(key, value);
      problems.push(...found);
    } else {
      // 2.5.0：技能写了要带参数，但容易漏；没有 executor_* 三个键的输出要自己说明。
      notes.push("未检查执行模型与凭据：带 --provider 与 --model（可加 --thinking）再运行 doctor，才会核对 pi 的模型列表、auth check 与思考级别");
    }
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    problems.push(error.message);
  }
}

/** 仓库的事实；不在 Git 仓库里（或 HEAD 读不出）只记一条 note。repository 先放进 facts，后面的检查往里补。 */
function repositoryFacts(repoArg: string | null, facts: PyDict, problems: string[], notes: string[]): void {
  try {
    const root = Repo.discover(repoArg).root;
    const head = gitText(["rev-parse", "HEAD"], root);
    const status = gitChecked(["status", "--porcelain=v1", "-z"], root).stdout.toString("latin1");
    const repository: PyDict = new Map<string, PyValue>([
      ["root", root],
      ["head", head],
      ["dirty_entries", BigInt(status.split(String.fromCharCode(0)).filter(Boolean).length)],
      ["runs_ignored", git(["check-ignore", "-q", ".agent/runs/probe"], root).status === 0],
      ["git_autocrlf", effectiveAutocrlf(root)],
    ]);
    facts.set("repository", repository);
    for (const name of ["AGENTS.md", "CLAUDE.md"]) {
      const inHead = git(["cat-file", "-e", `HEAD:${name}`], root).status === 0;
      const inTree = isFile(path.join(root, name));
      repository.set(name, new Map<string, PyValue>([["working_tree", inTree], ["committed_at_head", inHead]]));
      if (inTree && !inHead) notes.push(`${name} 尚未提交：worktree 基于提交创建，执行器看不到未提交的规则`);
    }
    if (!repository.get("runs_ignored")) problems.push(".agent/runs/ 未被 .gitignore 忽略");
    notes.push(...plannerFileNotes(root, repository));
    const identity = gitIdentityProblem(root);
    repository.set("git_identity", identity === null);
    if (identity) notes.push(identity);
    const context = contextEvidence(root, "project");
    facts.set("pi_context_from_repo_root", context);
    notes.push(...(context.get("warnings") as string[]));
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    notes.push(`未在 Git 仓库中运行：${error.message}`);
  }
}

/** planner_file_notes：规划端读取的规则文件与技能副本的检查。 */
function plannerFileNotes(root: string, facts: PyDict): string[] {
  const notes: string[] = [];
  const base = pyResolve(root);
  const agentsMd = path.join(root, "AGENTS.md");
  if (isFile(agentsMd)) {
    if (!isWithin(pyResolve(agentsMd), base)) {
      notes.push(`AGENTS.md 是指向仓库之外的链接（${pyResolve(agentsMd)}）：规划端与执行器读到的是仓库之外的内容，而且 worktree 中不一定有同样的文件`);
    }
    const size = statSync(agentsMd).size;
    facts.set("agents_md_bytes", BigInt(size));
    if (size > CODEX_PROJECT_DOC_MAX_BYTES) {
      notes.push(`AGENTS.md 有 ${size} 字节，超过 Codex 默认读取上限 ${CODEX_PROJECT_DOC_MAX_BYTES} 字节（project_doc_max_bytes）：超出部分不会被 Codex 读取`);
    }
  } else {
    notes.push("仓库根目录没有 AGENTS.md：规划端与执行器都读不到协作规则");
  }
  const claudeMd = path.join(root, "CLAUDE.md");
  if (isFile(claudeMd)) {
    const target = pyResolve(claudeMd);
    if (!isWithin(target, base)) {
      // 不读取仓库之外的内容，只提示。
      notes.push(`CLAUDE.md 是指向仓库之外的链接（${target}）：Claude Code 会读取该文件，而不是本仓库的 AGENTS.md`);
    } else if (normcase(target) === normcase(path.join(base, "AGENTS.md"))) {
      // CLAUDE.md 链接到 AGENTS.md：Claude Code 文档给出的合法做法，读到的就是 AGENTS.md
    } else if (!pyReadTextReplace(claudeMd).includes("@AGENTS.md")) {
      notes.push("仓库有 CLAUDE.md，但其中没有 @AGENTS.md：有 CLAUDE.md 时 Claude Code 只读 CLAUDE.md，读不到 AGENTS.md 中的协作规则。在 CLAUDE.md 中加一行 @AGENTS.md，或删去 CLAUDE.md");
    }
  }
  let missing: string[];
  let drift: string[];
  try {
    [missing, drift] = adapterDrift(root);
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    facts.set("claude_skill_adapters", new Map([["error", error.message]]));
    notes.push(error.message);
    return notes;
  }
  const installed = KIT_SKILLS.some((name) => pyExists(claudeSkillTarget(root, name)));
  // 只用 Codex 时可以不装 Claude Code 副本：没有任何副本时不算不一致。
  facts.set("claude_skill_adapters", new Map<string, PyValue>([
    ["installed", installed], ["missing_sources", missing], ["drift", installed ? drift.slice(0, 50) : []],
  ]));
  if (missing.length === KIT_SKILLS.length) {
    const legacy = KIT_SKILLS.filter((name) => isFile(path.join(claudeSkillTarget(root, name), "SKILL.md")));
    if (legacy.length) {
      notes.push("技能仍只在 .claude/skills（1.x 布局）：Codex 读不到。按 README 的升级说明移到 .agents/skills，再运行 sync-adapters");
    } else {
      notes.push(`没有找到 Code-Kit 技能（${SKILL_SOURCE_DIR}/${KIT_SKILLS[0] as string} 等）`);
    }
  } else if (missing.length) {
    notes.push(`.agents/skills 中缺少技能：${missing.join(", ")}`);
  }
  if (drift.length && installed) {
    notes.push(`Claude Code 的技能副本（.claude/skills）与 .agents/skills 不一致 ${drift.length} 处：运行 bash scripts/dispatch-pi.sh sync-adapters`);
  }
  return notes;
}

/** git_identity_problem：branch 用 git commit-tree 创建候选提交，需要作者与提交者身份（git var 与 commit-tree 同一套判定）。 */
function gitIdentityProblem(root: string): string | null {
  for (const name of ["GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"]) {
    if (git(["var", name], root).status !== 0) {
      return `没有可用的 Git 作者身份（${name}）：branch 生成候选提交时会失败。配置 user.name 与 user.email，或在运行 branch 时提供 GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL / GIT_COMMITTER_NAME / GIT_COMMITTER_EMAIL 环境变量`;
    }
  }
  return null;
}

/**
 * kit_layout：source 是本仓库就是 kit（有 scripts/kit_install.py）；installed 是 kit 装在本仓库的 scripts/ 里；
 * external 是调度器从仓库之外的 kit 目录运行；unknown 是不在仓库里。
 */
function kitLayout(kitRoot: string, repoRoot: string | null): string {
  if (repoRoot === null) return "unknown";
  if (normCase(kitRoot) !== normCase(pyResolve(repoRoot))) return "external";
  return isFile(purePathStr(kitRoot, "scripts", "kit_install.py")) ? "source" : "installed";
}

/**
 * _doctor_kit：kit 是否齐全、是哪种布局、装进来的文件在安装之后有没有变化（2.9.0）。只作提示：缺文件时调度照常，
 * 只是决策、配置管理器等功能不可用；本地改过的文件 update 时列为 KEEP，不会被覆盖。
 */
function doctorKit(repo: Repo | null, kitRoot: string, facts: PyDict, notes: string[]): void {
  const needed = ["scripts/pi_dispatch.py", "scripts/dispatch-pi.sh", ...KIT_LOADED_FILES];
  const missing = needed.filter((rel) => !(rel.endsWith("/**") ? isDir(purePathStr(kitRoot, rel.slice(0, -3))) : isFile(purePathStr(kitRoot, rel))));
  const layout = kitLayout(kitRoot, repo === null ? null : repo.root);
  const kit: PyDict = new Map<string, PyValue>([["root", kitRoot], ["layout", layout], ["missing", missing]]);
  if (missing.length) {
    notes.push(`kit 不完整（${kitRoot} 下缺少 ${missing.slice(0, 8).join("、")}）：决策与配置管理器等功能不可用。从 kit 目录运行 ` +
      `${code("python <kit>/scripts/kit_install.py update <本仓库>")} 补齐（2.9.0）`);
  }
  if (layout === "installed" && repo !== null) installRecordFacts(repo.root, kit, notes);
  facts.set("kit", kit);
}

function installRecordFacts(root: string, kit: PyDict, notes: string[]): void {
  const record = readJsonOr(path.join(root, KIT_INSTALL_RECORD), null);
  const files = record instanceof Map ? record.get("files") : undefined;
  if (!(record instanceof Map) || !(files instanceof Map)) {
    notes.push(`kit 装在本仓库里，但没有安装记录 ${KIT_INSTALL_RECORD}：多半是手工复制的。用 kit 目录的 kit_install.py install 登记` +
      "（已有的文件会列为 CONFLICT，核对后加 --force）");
    return;
  }
  const changed: string[] = [];
  const gone: string[] = [];
  const entries = [...files].map(([key, digest]) => [key as string, digest] as const); // JSON 对象的键都是字符串
  for (const [rel, digest] of entries.sort(([a], [b]) => cmpCodePoints(a, b))) {
    const file = purePathStr(root, rel);
    if (!isFile(file)) gone.push(rel);
    else if (sha256File(file) !== digest) changed.push(rel);
  }
  kit.set("record", new Map<string, PyValue>([
    ["kit_version", pyGet(record, "kit_version")], ["kit_commit", pyGet(record, "kit_commit")], ["changed", changed.slice(0, 50)], ["missing", gone.slice(0, 50)],
  ]));
  if (changed.length || gone.length) {
    notes.push(`kit 文件在安装之后有变化：改过 ${changed.length} 个、缺 ${gone.length} 个（${[...changed, ...gone].slice(0, 6).join("、")}）。` +
      "update 时改过的列为 KEEP，不会被覆盖；缺的会补回");
  }
}

function discoverOrNull(repoArg: string | null): Repo | null {
  try {
    return Repo.discover(repoArg);
  } catch (error) {
    if (!(error instanceof DispatchError)) throw error;
    return null;
  }
}

/** Path.write_text(text, encoding="utf-8")：文本模式，Windows 上换行写成 CRLF。 */
function writeTextMode(file: string, text: string): void {
  writeFileSync(file, Buffer.from(WIN ? text.replaceAll(LF, CRLF) : text, "utf8"));
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}
