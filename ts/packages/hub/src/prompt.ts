// 回合的输入（迁移第 ⑤d 片）：kit_hub.py 的 render_template、role_prompt、engineering_rules、transitional_section、external_facts_section、
// input_path、turn_prompt、letter_from_output，加上 turn_prompt 合同端那一段用到的 regression_gates、next_contract_version、budget_usage
// （⑤e 复用）。文字逐字节照 Python；parts 照 Python 收原值，最后的 join 对不是字符串的照样报 TypeError。
// 读模板目录、内核仓库的两处带一个缺省取内核目录的参数：契约两边设同一个值来比（Python 那边在探针里改模块的全局）。
import { type Stats, lstatSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { readText, sleepSync } from "@themis/base/fsutil";
import { PyCrash, pyGet, pyIntOf, pyItem, pyIter, pyJoin, pyJoinStrings, pyLenValue, pyPercentD, pyPlus, pyRepr, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, type PyValue } from "@themis/base/pyjson";
import { abspath, purePathName, purePathRelativePosix, purePathStr, relpath } from "@themis/base/pypath";
import { cmpCodePoints, pySplitlines, pyStrip } from "@themis/base/pyre";
import { FLAG_MULTILINE, compilePy } from "@themis/base/pyregex";
import { pyEq } from "@themis/base/pyvalue";
import { budgetUsage as dispatcherBudgetUsage } from "@themis/dispatcher/prepare";
import { Repo } from "@themis/dispatcher/repo";
import { globPaths } from "@themis/dispatcher/instruction";
import { comparePaths, stripChars } from "./audit.ts";
import {
  CONTRACT_EXECUTOR_LINE, COORDINATOR, DEPENDENCY_DIRS, ENGINEERING_HEADING, ENGINEERING_ROLES, EXIT_BLOCKED, FIELDS, GATE_PITFALLS, HANDOFF_FIELD,
  MIN_ATTEMPTS_LEFT, OUTPUT_SPECS, ROLE_EXTRA_OUTPUT, ROSTER, type RosterSpec, TEMPLATE_READ_TRIES, VERDICT_FIELDS,
} from "./constants.ts";
import { HubError } from "./errors.ts";
import { KERNEL_ROOT, TEMPLATE_DIR, git } from "./kernel.ts";
import { stageOf } from "./letters.ts";
import type { Hub } from "./mailbox.ts";
import { gateFile, gatePattern, stageStatusTable, upstreamNotes } from "./taskstate.ts";

const BS = String.fromCharCode(92);
const TAB = String.fromCharCode(9);
const LF = String.fromCharCode(10);
const DQ = String.fromCharCode(34);
const BT = String.fromCharCode(96);
const or = (value: PyValue | undefined, fallback: PyValue): PyValue => (pyTruthy(value) ? (value as PyValue) : fallback);

/** ROSTER[agent]：没有这个工人照 Python 报 KeyError。 */
function rosterSpec(agent: string): RosterSpec {
  if (!Object.hasOwn(ROSTER, agent)) throw new PyCrash("KeyError", pyRepr(agent));
  return ROSTER[agent] as RosterSpec;
}

// --- 模板与角色提示词 ----------------------------------------------------------------------------------------------

const ROLE_BLOCK = new RegExp(`<!-- 角色:([a-z]+) -->${LF}(.*?)<!-- /角色 -->${LF}?`, "gsu");

/** 代入占位符；给了 role 时只保留这个角色的职责段（<!-- 角色:x -->…<!-- /角色 -->）。模板读到空文件时隔 0.2 秒重读，最多 TEMPLATE_READ_TRIES 次（第 26 轮）。 */
export function renderTemplate(name: string, values: readonly (readonly [string, string])[], role: string | null = null, templateDir = TEMPLATE_DIR): string {
  const path = purePathStr(templateDir, name);
  let text = readText(path);
  for (let attempt = 0; attempt < TEMPLATE_READ_TRIES; attempt += 1) {
    if (text) break;
    sleepSync(200);
    text = readText(path);
  }
  if (!text) throw new HubError(`找不到提示词模板：${path}`);
  if (role !== null) text = text.replace(ROLE_BLOCK, (_whole, who: string, body: string) => (who === role ? body : ""));
  for (const [key, value] of values) text = text.split(`{{${key}}}`).join(value);
  return text;
}

export function rolePrompt(agent: string, templateDir = TEMPLATE_DIR, kernelRoot = KERNEL_ROOT): string {
  const spec = rosterSpec(agent);
  const values: [string, string][] = [["名字", agent], ["角色", spec.label], ["协调人", COORDINATOR], ["仓库", "ThemisTally"]];
  if (agent === COORDINATOR) return renderTemplate("coordinator.md", values, null, templateDir);
  const prompt = renderTemplate("worker.md", values, spec.role, templateDir);
  return ENGINEERING_ROLES.includes(spec.role) ? `${prompt}${LF}${engineeringRules(kernelRoot)}${LF}` : prompt;
}

/** AGENTS.md 里“通用工程要求”一节，取内核仓库已提交的版本；切不出来（标题改了名）就报错交给站主，不悄悄少一节规则。 */
export function engineeringRules(kernelRoot = KERNEL_ROOT): string {
  const text = git(["show", "HEAD:AGENTS.md"], kernelRoot, false);
  const start = text.indexOf(`${ENGINEERING_HEADING}${LF}`);
  if (start < 0) {
    throw new HubError(`已提交的 AGENTS.md 里找不到“${ENGINEERING_HEADING.slice(3)}”一节，合同端、门禁端、审核端的提示词要拼它：标题改了名就同步改`
      + " kit_hub.ENGINEERING_HEADING", EXIT_BLOCKED);
  }
  const end = text.indexOf(`${LF}## `, start + 1);
  return pyStrip(text.slice(start, end >= 0 ? end : text.length));
}

// --- 规划端看的过渡断言 ----------------------------------------------------------------------------------------------

/** 门禁测试里的过渡断言（TRANSITIONAL_RE）：pyregex 不记组，用例名与说明行从整段匹配里取（transitionalParts）。 */
const TRANSITIONAL = compilePy(
  `^[ ${BS}t]*def (test_transitional_${BS}w+)${BS}([^)]*${BS})[^:${BS}n]*:[ ${BS}t]*(?:${BS}n[ ${BS}t]*[rRuU]?(?:${DQ.repeat(3)}|''')([^${BS}n]*))?`,
  FLAG_MULTILINE,
);

/**
 * 前端测试里的过渡用例（FRONTEND_TRANSITIONAL_RE，迁移计划 E6）：原式的反向引用按三种引号展开成三支，分支里的“不是开引号的字符”
 * 写成“不是这个引号、也不是换行”（原式的点号不跨行）。前缀里没有引号，整段匹配里的第一个引号就是开引号，标题是它之后到末尾闭引号之前。
 */
const FRONTEND_TRANSITIONAL = compilePy(
  `^[ ${BS}t]*(?:describe|it|test)(?:${BS}.${BS}w+)*${BS}(${BS}s*(?:${[DQ, "'", BT].map((quote) => `${quote}[^${quote}${BS}n]*（过渡）[^${quote}${BS}n]*${quote}`).join("|")})`,
  FLAG_MULTILINE,
);

/** 一处 TRANSITIONAL 匹配的（用例名，说明行）：参数表里没有右括号，冒号在它之后的同一行；说明行可有可无。 */
function transitionalParts(whole: string): [string, string | null] {
  const name = whole.slice(whole.indexOf("def ") + 4, whole.indexOf("("));
  const close = whole.indexOf(")");
  const rest = skipBlanks(whole.slice(whole.indexOf(":", close) + 1));
  if (!rest.startsWith(LF)) return [name, null];
  const line = skipBlanks(rest.slice(1));
  const quoted = "rRuU".includes(line[0] as string) && (line[1] === DQ || line[1] === "'") ? line.slice(1) : line;
  return [name, quoted.slice(3)];
}

/** 规划端要看到仓库里现有的过渡断言（第 8 轮）与前端测试里标题带“（过渡）”的用例（第 121 轮）。 */
export function transitionalSection(workspace: string): string[] {
  const gate: string[] = [];
  for (const path of globPaths(purePathStr(workspace, "tests"), ["test_gate_*.py"]).sort(comparePaths)) {
    for (const match of TRANSITIONAL.finditer(readText(path))) {
      const [name, doc] = transitionalParts(match.group);
      const note = pyStrip(stripChars(pyStrip(doc ?? ""), `${DQ}'`)) || "（没有说明）";
      gate.push("- " + BT + `${purePathRelativePosix(path, workspace)}::${name}` + BT + `：${note}`);
    }
  }
  const frontend: string[] = [];
  const tests = purePathStr(workspace, "desktop", "web", "tests");
  for (const path of rglob(tests, "*.test.ts*")) {
    const text = readText(path);
    const points = Array.from(text);
    for (const match of FRONTEND_TRANSITIONAL.finditer(text)) {
      const line = points.slice(0, match.start).filter((char) => char === LF).length + 1;
      const title = match.group.slice(firstQuote(match.group) + 1, -1);
      frontend.push("- " + BT + `${purePathRelativePosix(path, workspace)}:${line}` + BT + `：${title}`);
    }
  }
  const lines: string[] = [];
  if (gate.length) {
    lines.push("", "## 仓库里现有的过渡断言（门禁测试里只在当时那一片成立的断言）", "", ...gate,
      "- 本任务会推翻其中哪几条，写进 report，并在信的“需协调人决定”里列出：站主在开工合同端之前退役它们。");
  }
  if (frontend.length) {
    lines.push("", "## 前端测试里的过渡用例（describe、it 的标题带“（过渡）”）", "", ...frontend,
      "- 本任务会推翻其中哪几条，写进 report：那几个测试文件要写进合同的允许修改范围，由执行端照新行为改。");
  }
  return lines;
}

/** 去掉开头的空格与制表符（TRANSITIONAL_RE 里“零个或多个空格、制表符”那一段）。 */
function skipBlanks(text: string): string {
  let index = 0;
  while (text[index] === " " || text[index] === TAB) index += 1;
  return text.slice(index);
}

function firstQuote(text: string): number {
  const found = [DQ, "'", BT].map((quote) => text.indexOf(quote)).filter((index) => index >= 0);
  return Math.min(...found);
}

/**
 * root.is_dir() 时的 sorted(root.rglob(pattern))（Python 3.12）：每一层目录都按 pattern 匹配名字；往下走照 Path.walk(follow_symlinks=False)，
 * 不进符号链接（联接 Python 当目录走、lstat 当链接，测试目录里不会有）。
 */
function rglob(root: string, pattern: string): string[] {
  const found: string[] = [];
  const walk = (dir: string): void => {
    found.push(...globPaths(dir, [pattern]));
    let names: string[] = [];
    try {
      names = readdirSync(dir);
    } catch {
      return;
    }
    for (const name of names) {
      const child = join(dir, name);
      if (lstatOrNull(child)?.isDirectory()) walk(child);
    }
  };
  if (statOrNull(root)?.isDirectory()) walk(root);
  return found.sort(comparePaths);
}

function lstatOrNull(path: string): Stats | null {
  try {
    return lstatSync(path);
  } catch {
    return null;
  }
}

function statOrNull(path: string): Stats | null {
  try {
    return statSync(path);
  } catch {
    return null;
  }
}

// --- 回合输入的各节 ----------------------------------------------------------------------------------------------

export function externalFactsSection(ts: PyDict): string[] {
  const record = pyGet(ts, "external_facts");
  if (!pyTruthy(record)) return [];
  const lines = ["", "## 规划依赖的仓库外事实（内核记录）", ""];
  for (const item of pyIter(or(pyGet(record, "items"), []))) {
    lines.push(`- ${pyStrValue(pyGet(item, "fact"))}（出处：${pyStrValue(or(pyGet(item, "source"), "未写"))}）—— ${pyStrValue(pyGet(item, "verified"))}`);
  }
  if (!pyTruthy(pyGet(record, "items"))) lines.push("- 规划端声明没有仓库外事实");
  if (pyTruthy(pyGet(record, "checked_at"))) {
    lines.push(`- 其中没核实的 ${pyLenValue(or(pyGet(record, "checked"), []))} 条，站主已在 ${pyStrValue(pyGet(record, "checked_msg"))} 的回复里核实：以那封回复为准`);
  }
  lines.push("- 合同只能把核实过的当事实写；合同依赖、却不在这张表里的仓库外事实，一审退回规划端。");
  return lines;
}

/** 主工作区里的一个路径，在输入目录里对应的那一份（第 88 轮）；没有输入目录、不在仓库里或不在同一个盘时原样。 */
export function inputPath(hub: Hub, inputs: string | null, path: PyValue): string {
  const text = pyStrValue(path);
  if (inputs === null || !text) return text;
  let rel: string;
  try {
    rel = relpath(abspath(text), abspath(hub.repo));
  } catch {
    return text;
  }
  return rel === ".." || rel.startsWith(`..${BS}`) ? text : purePathStr(inputs, rel);
}

/** 任务基线上先前各片留下的门禁基准测试（第 14 轮）。 */
const GATE_BASELINE = compilePy(`^tests/test_gate_t${BS}d+_baseline${BS}.py$`);

export function regressionGates(hub: Hub, ts: PyDict): string[] {
  const listing = git(["ls-tree", "-r", "--name-only", pyStrValue(pyItem(ts, "base_head")), "--", "tests"], hub.repo, false);
  const own = gateFile(ts, "baseline");
  return pySplitlines(listing).filter((path) => GATE_BASELINE.match(path) !== null && path !== own).sort(cmpCodePoints);
}

/** 合同端下一份合同的版本号，以及是不是原号重写（第 17 轮）：没派遣、也没通过核验的草稿原号重写。 */
export function nextContractVersion(ts: PyDict): [bigint, boolean] {
  const current = pyItem(ts, "contract");
  if (pyTruthy(pyGet(current, "version")) && !pyTruthy(pyGet(current, "dispatched")) && !pyTruthy(pyGet(current, "validated"))) {
    return [pyIntOf(pyItem(current, "version")), true];
  }
  return [pyIntOf(pyGet(current, "version", 0n)) + 1n, false];
}

/** 调度器按 task_id 累计各合同版本已领取的 attempt 与墙钟（只看 runs/<任务号>）。 */
export function budgetUsage(hub: Hub, ts: PyDict): { attempts_started: number; wall_seconds_used: number } {
  return dispatcherBudgetUsage(new Repo(hub.repo), pyStrValue(pyItem(ts, "contract_task")));
}

// --- 本回合输入 ------------------------------------------------------------------------------------------------

export function turnPrompt(
  hub: Hub, ts: PyDict, agent: string, taskId: string, letters: readonly PyValue[], workspace: string,
  error: PyValue = null, inputs: string | null = null, resume: PyValue = null, routingNote: PyValue = null,
): string {
  const shown = (path: PyValue): string => inputPath(hub, inputs, path); // 主工作区的路径一律换成输入目录里的
  const spec = rosterSpec(agent);
  const role = spec.role;
  const taskDir = hub.taskDir(taskId);
  const parts: PyValue[] = ["# 本回合输入（内核）", "",
    `- 你：${agent}（${spec.label}）`,
    `- 主任务：${pyStrValue(pyItem(ts, "task"))} ${pyStrValue(pyItem(ts, "title"))}`,
    `- 本回合的任务：${taskId}`,
    `- 工作目录：${workspace}`,
    inputs !== null
      ? `- 只读输入目录：${inputs}（内核这一回合复制的信箱、合同与执行证据，照相对仓库的原样摆放：信里写的 ` + BT + ".agent/…" + BT
        + ` 路径在这里找；主工作区一律不碰，只许按路径读已经装好的依赖 ${DEPENDENCY_DIRS.map((dep) => purePathStr(hub.repo, dep)).join("、")}）`
      : `- 仓库主工作区（只读参考）：${hub.repo}`,
    `- 你的 state.md：${shown(purePathStr(taskDir, "state.md"))}`,
    `- 你的 report.md：${shown(purePathStr(taskDir, "report.md"))}（内核按你的输出写）`];
  if (spec.timeout) {
    // 第 53 轮：T011 的门禁端把 40 分钟都花在调查上，只改了一处就超时
    parts.push(`- 本回合时限：${Math.floor(spec.timeout / 60)} 分钟。到点整个回合作废、什么也交不出：先把能确定的做完并交付，没做完的写进交付信，不要把时间耗在调查上`);
  }
  const suffix = stageOf(taskId)[1];
  const stages = pyGet(ts, "stages", new Map());
  const hasStage = suffix !== null && stages instanceof Map && stages.has(suffix);
  const stage = (): PyValue => pyItem(pyItem(ts, "stages"), suffix as string);
  if (hasStage && pyTruthy(pyGet(stage(), "timed_out"))) {
    parts.push("", "## 上一回合超时作废", "", "- 上一回合跑满时限，什么也没交出。" + (spec.workspace === "stage"
      ? "工作目录里它留下的改动还在：先 " + BT + "git status" + BT + "、" + BT + "git diff" + BT + " 看清楚，在上面接着做，不要从头调查。"
      : "这一回合先把确定的部分交出来，不要从头调查。"));
  }
  const owner = hasStage ? pyGet(stage(), "owner_text") : null;
  if (pyTruthy(owner)) {
    // 第 54 轮：站主指定的返工，门禁端要看到站主的原话
    parts.push("", "## 站主的原话（站主指定的返工，内核原样转交；与任务书不一致时以这里为准）", "",
      `站主来信 ${pyStrValue(pyItem(owner, "msg"))}：`, "", pyStrValue(pyItem(owner, "text")));
  }
  if (pyTruthy(error)) parts.push("", "## 上一次输出没有通过内核校验，请改正后重新交出", "", error);
  if (pyTruthy(resume) && pyTruthy(pyGet(resume, "routing")) && role === "coordinator") {
    // 第 112 轮：被收掉的是内核代办，不是你的回合
    parts.push("", "## 这一批信接着办（内核）", "",
      "- 上一次是内核在代办这批信，做到一半 hub 被收掉了：已经投出去的看下面的主任务状态表，重发的开工、返工内核不收，也不算你出错。");
  } else if (pyTruthy(resume) && pyTruthy(pyGet(resume, "session")) && role === "coordinator") {
    parts.push("", "## 这一回合接着做（内核）", "",
      `- 你上一回合（${pyStrValue(pyItem(resume, "turn"))}）的输出内核收到了，投递做到一半 hub 被系统收掉了。`,
      "- 照原样再交一次。已经投递的信看下面的主任务状态表，不要重发（重发的开工、返工内核不收，也不算你出错）。");
  } else if (pyTruthy(resume) && pyTruthy(pyGet(resume, "session"))) {
    parts.push("", "## 这一回合接着做（内核）", "",
      `- 你上一回合（${pyStrValue(pyItem(resume, "turn"))}）的交付内核收到了，核验做到一半 hub 被系统收掉了，交付没有记下来。`,
      "- 会话与工作目录里的文件都在：照原样再交一次，不用重做检查。");
  } else if (pyTruthy(resume)) {
    parts.push("", "## 这一回合接着做（内核）", "",
      "- 上一回合办到一半，hub 被系统收掉了。这是新会话：工作目录里留着上一回合的改动，先看一遍，接着做，做完再交。");
  }
  parts.push("", "## 新信", "", ...(letters.length ? letters : ["（没有新信）"]));
  if (role === "coordinator") coordinatorParts(hub, ts, letters, routingNote, parts, shown);
  else workerParts(hub, ts, agent, taskId, workspace, parts, shown);
  if (spec.adapter !== "claude") {
    // 第 90 轮：用 deliver 工具交差，格式由工具的 schema 卡住
    parts.push("", "## 交差（用 deliver 工具）", "",
      "- 这一回合做完，调用一次 " + BT + "deliver" + BT + " 工具交差；参数的格式在工具的说明里（内核给的 schema），大致如下。调用成功，这一回合就结束。",
      "- 参数不合格式时，工具当场退回并写明哪里不对：照着改了再调一次。",
      "- 不要再在消息里写 " + BT.repeat(3) + "json 代码块：内核不读它。", "",
      BT.repeat(3), OUTPUT_SPECS[role === "coordinator" ? "coordinator" : "worker"] as string, BT.repeat(3));
  } else {
    // 第 101 轮：claude 用 --json-schema 交差，CLI 给的工具叫 StructuredOutput
    parts.push("", "## 交差（交结构化结果）", "",
      "- 这一回合做完，用 " + BT + "StructuredOutput" + BT + " 工具交出结构化结果；格式是内核给的 JSON Schema，大致如下。交上了，这一回合就结束。",
      "- 不合格式时会退回并写明哪里不对：照着改了再交。",
      "- 不要再在消息里写 " + BT.repeat(3) + "json 代码块：内核不读它。", "",
      BT.repeat(3), OUTPUT_SPECS["worker"] as string, BT.repeat(3));
  }
  if (Object.hasOwn(ROLE_EXTRA_OUTPUT, role)) parts.push(ROLE_EXTRA_OUTPUT[role] as string);
  return `${pyJoinStrings(LF, parts)}${LF}`;
}

function coordinatorParts(hub: Hub, ts: PyDict, letters: readonly PyValue[], routingNote: PyValue, parts: PyValue[], shown: (path: PyValue) => string): void {
  parts.push("", "## 主任务状态（内核）", "", stageStatusTable(ts));
  if (pyTruthy(pyGet(ts, "routed"))) {
    // 第 112 轮：你上一回合之后内核代办的例行流转
    parts.push("", "## 内核代办记录（你上一回合之后）", "", ...pyIter(pyItem(ts, "routed")).map((entry) =>
      `- ${pyStrValue(pyItem(entry, "at"))}：${pyJoin("；", pyItem(entry, "moves"))}（处理了 ${pyJoin("、", pyItem(entry, "letters"))}）`));
  }
  if (pyTruthy(routingNote)) parts.push("", "## 内核没有代办这一批信", "", routingNote);
  const briefPath = purePathStr(hub.taskDir(pyStrValue(pyItem(ts, "task"))), "brief.md");
  const ownerBrief = readText(briefPath);
  if (ownerBrief && letters.some((letter) => pyStrValue(letter).includes(`${LF}type: 任务${LF}`))) {
    parts.push("", `## 站主的任务书（${shown(briefPath)}）`, "", ownerBrief);
  }
}

function workerParts(hub: Hub, ts: PyDict, agent: string, taskId: string, workspace: string, parts: PyValue[], shown: (path: PyValue) => string): void {
  const role = rosterSpec(agent).role;
  const taskDir = hub.taskDir(taskId);
  const brief = readText(purePathStr(taskDir, "brief.md"));
  parts.push("", `## 任务书（${shown(purePathStr(taskDir, "brief.md"))}）`, "", brief || "（没有任务书）");
  const notes = upstreamNotes(ts, stageOf(taskId)[1]);
  if (notes.length) parts.push("", "## 上游各阶段的下游须知（内核原样附上）", "", ...notes); // 第 111 轮：由内核附上，不靠协调人转抄
  const state = readText(purePathStr(taskDir, "state.md"));
  if (state) parts.push("", "## 你上次留下的 state.md", "", state);
  if (role === "audit") auditParts(hub, ts, taskId, parts, shown);
  if (role === "contract" || taskId.endsWith("-4-audit-pre")) parts.push(...externalFactsSection(ts));
  if (role === "contract" && pyTruthy(pyGet(ts, "decisions"))) {
    parts.push("", "## 站主的决定（规划阶段对提问的答复原文）", "",
      "- 执行端只看合同、看不到这些信：合同正文要把决定写成具体做法（图标名、令牌、文案这类细节照原文写进 Steps 与 DoD），不要只写“按 Q1”。"
        + "内核会另把原文附在合同末尾，附录不用你抄。");
    for (const item of pyIter(pyItem(ts, "decisions"))) parts.push("", `站主来信 ${pyStrValue(pyItem(item, "msg"))}：`, "", pyStrValue(pyItem(item, "text")));
  }
  if (role === "contract") contractParts(hub, ts, parts);
  if (role === "planner") parts.push(...transitionalSection(workspace));
  if (role === "gate") gateParts(ts, taskId, parts, shown);
}

function auditParts(hub: Hub, ts: PyDict, taskId: string, parts: PyValue[], shown: (path: PyValue) => string): void {
  const stage = stageOf(taskId)[1];
  const history = pyIter(or(pyGet(ts, "audit_history"), [])).filter((item) => pyEq(pyGet(item, "stage"), stage));
  const last = history.at(-1);
  if (last !== undefined && pyEq(pyGet(last, "verdict"), "返工")) {
    parts.push("", "## 上一轮你列的阻塞项（复审封板）", "", or(pyGet(last, "blockers"), "（空）"), "",
      "- 先逐条复核这些阻塞项是否已经解决，在报告里逐条写结论。",
      "- 新的打回理由只能来自本轮新改动的内容，或者会导致错误结果的严重问题；上一轮没提的建议类意见不能在这一轮升级成阻塞项。");
  }
  const post = stage === "7-audit-post";
  const gatePost = (): PyValue => pyItem(ts, "gate_post");
  const inRepo = (value: PyValue): string => shown(purePathStr(hub.repo, pyStrValue(value)));
  const archive: string[] = []; // 第 113 轮：单起一节，不然这几行落在前一节（下游须知）底下，像是上游写的
  if (post && pyTruthy(pyGet(gatePost(), "whitebox_file"))) archive.push(`- 白盒测试文件（就是跑出下面结果的那一份）：${inRepo(pyItem(gatePost(), "whitebox_file"))}`);
  if (post && pyTruthy(pyGet(gatePost(), "mutate_record"))) {
    archive.push(`- 内核的变异记录（逐条结果）：${inRepo(pyItem(gatePost(), "mutate_record"))}`,
      `- 白盒测试的输出：${inRepo(or(pyGet(gatePost(), "whitebox_log"), ""))}`);
  }
  if (archive.length) parts.push("", "## 战后门禁的存档（内核）", "", ...archive);
  if (post && pyTruthy(pyGet(gatePost(), "defects"))) {
    parts.push("", "## 门禁端举证的候选缺陷（逐条裁定：成立的写进阻塞项、退回执行端；不成立的——白盒测试误读了合同——退回战后门禁；有缺陷时不能判通过）", "",
      `- 白盒测试的输出：${inRepo(or(pyGet(gatePost(), "whitebox_log"), ""))}`,
      ...pyIter(pyItem(gatePost(), "defects")).map((item) =>
        "- " + BT + pyStrValue(pyItem(item, "test")) + BT + `：${pyStrValue(pyItem(item, "where"))} —— 合同：${pyStrValue(pyItem(item, "contract"))}`));
  }
  const listed = (key: string, heading: string): void => {
    if (post && pyTruthy(pyGet(gatePost(), key))) parts.push("", heading, "", ...pyIter(pyItem(gatePost(), key)).map((item) => pyPlus("- ", item)));
  };
  listed("equivalent", "## 门禁端声明的等价变异（逐条复核：改了真的测不出来吗）");
  listed("expect_missed", "## 门禁端标了“这条命令预期抓不住”的变异（逐条复核：那条命令真的测不到吗）");
  listed("unmutated", "## 门禁端说没法变异的改动文件（逐条复核：这些改动真的不用测吗）");
}

function contractParts(hub: Hub, ts: PyDict, parts: PyValue[]): void {
  const used = budgetUsage(hub, ts);
  const code = (text: string): string => BT + text + BT;
  const task = pyStrValue(pyItem(ts, "contract_task"));
  parts.push("", "## 合同要求（内核会逐项核对）", "",
    "- 第一行：" + code(`# TASK: ${task}`) + `；Identity 的 plan_version 写 ${nextContractVersion(ts)[0]}、base_sha 写 ${pyStrValue(pyItem(ts, "base_head"))}。`
      + "这两项由内核决定，写错了内核会改正；门禁提交后内核再把 base_sha 改成基准测试的提交。版本号与当前 HEAD 不用你操心，validate 的“base_sha 不是当前 HEAD”只是提示。",
    "- executor 行照抄：" + code(CONTRACT_EXECUTOR_LINE) + "；integration_actions 写 " + code("local_branch, merge") + "。",
    "- Scope 的 forbidden_paths 包含 " + code(gatePattern(ts)) + "（门禁测试，执行端不能碰）。",
    "- Validation commands 要有一条门禁检查，照这个格式写（ID 可以换，但要是一个大写字母加两位数字，调度器只认这种编号）："
      + code("- G01（必要，基线应失败）：" + code(`python -m pytest ${gateFile(ts, "baseline")} -q`) + " · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：" + code(`${BS}d+ passed`))
      + "。门禁测试由门禁端稍后写好、内核做成基线提交，你只写这一行。");
  const regression = regressionGates(hub, ts);
  if (regression.length) {
    parts.push("- 先前各片的门禁基准测试是回归测试，Validation commands 要有一条回归检查，照这个格式写："
      + code("- R01（必要，基线应通过）：" + code(`python -m pytest ${regression.join(" ")} -q`) + " · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：" + code(`${BS}d+ passed`))
      + "。");
  }
  parts.push("- Budget 的 max_attempts_total 与 max_wall_seconds_total 是 " + code(task) + " 各版本的累计上限（调度器跨版本累计）："
    + `已用掉 ${pyPercentD(used.attempts_started)} 次、${pyPercentD(used.wall_seconds_used)} 秒。总数要把它们算进去，给这一版至少留 ${MIN_ATTEMPTS_LEFT} 次 attempt 与 ${MIN_ATTEMPTS_LEFT} 倍单次时限。`,
  "- 格式照 .agents/skills/plan-task/contract-template.md 与 contract-guide.md（在工作目录里，先读）。");
}

function gateParts(ts: PyDict, taskId: string, parts: PyValue[], shown: (path: PyValue) => string): void {
  const stage = stageOf(taskId)[1];
  const pre = stage === "3-gate-pre";
  const target = gateFile(ts, pre ? "baseline" : "whitebox");
  parts.push("", "## 门禁要求（内核会核对）", "",
    "- 只新增 " + BT + target + BT + " 这一个文件，不改动任何已有文件；在工作目录里写。",
    "- 用 " + BT + `python -m pytest ${target} -q` + BT + " 自己跑一遍：" + (pre ? "战前的基准测试应当在当前基线上失败（目标功能还没实现）"
      : "战后的白盒测试在候选上应当全部通过；候选不满足合同写明的行为时让它红着，红的用例逐条写进 candidate_defects。不许用 xfail、skip 标掉") + "。");
  parts.push("", "## 门禁测试撞过的坑（T010–T012 实测，任何实现都过不了的写法；交付前逐条自查）", "", ...GATE_PITFALLS.map((item) => `- ${item}`));
  const claims = pre ? pyGet(or(pyGet(ts, "hotfix"), new Map()), "claims") : null;
  if (pyTruthy(claims)) {
    const runDir = shown(or(pyGet(pyItem(ts, "hotfix"), "run_dir"), ""));
    parts.push("", "## 热修补：执行端说门禁测试有错（原话，内核转交）", "",
      "- 逐条核实：说对了的改测试（断言的意图不变），说错了的不改，并在交付信里逐条写结论与依据（合同出处、库的版本与源码位置、候选里的代码）。",
      `- 候选与检查日志（只读）：${runDir}/candidate.patch、${runDir}/checks/、${runDir}/executor-report.md`, "", ...pyIter(claims).map((claim) => pyPlus("- ", claim)));
  }
  if (stage === "6-gate-post" && pyTruthy(pyGet(pyItem(ts, "gate_post"), "mutate_spec"))) {
    parts.push(`- 你上一次交的变异清单，内核存了档（可读）：${shown(pyItem(pyItem(ts, "gate_post"), "mutate_spec"))}。返工时在它上面改，不必整份重写。`);
  }
  const seeded = stage === "6-gate-post"
    ? pyGet(or(pyGet(pyItem(ts, "workspaces"), `post-${purePathName(pyStrValue(or(pyGet(pyItem(ts, "exec"), "run_dir"), ".")))}`), new Map()), "whitebox_seeded")
    : null;
  if (pyTruthy(seeded)) {
    parts.push(`- 这是新的 attempt：内核已把上一轮的白盒测试（${pyStrValue(seeded)}）放进工作目录的 ` + BT + target + BT + "。在它上面改，对照这一轮的候选核对每条断言，不必整份重写。");
  }
}

/** 工人交上来的输出折成写给协调人的信：（信头，字段）。 */
export function letterFromOutput(agent: string, taskId: string, data: PyValue): [Map<string, string>, Map<string, string>] {
  const letter = pyGet(data, "letter");
  const raw: PyValue = letter instanceof Map ? letter : new Map();
  const meta = new Map([["from", agent], ["to", COORDINATOR], ["task-id", taskId],
    ["in-reply-to", pyStrValue(or(pyGet(raw, "in_reply_to"), "none"))], ["type", pyStrValue(or(pyGet(raw, "type"), ""))]]);
  const fields = new Map<string, string>(FIELDS.map((key) => [key, pyStrip(pyStrValue(pyGet(raw, key, "")))]));
  for (const key of [...VERDICT_FIELDS, HANDOFF_FIELD]) if (pyTruthy(pyGet(raw, key))) fields.set(key, pyStrip(pyStrValue(pyItem(raw, key))));
  return [meta, fields];
}
