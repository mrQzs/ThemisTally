// 执行说明 instruction.md 的生成（迁移第 ④b7c1 片）：INSTRUCTION_TEMPLATE、render_instruction、setup_facts_text、
// self_check_command、machine_summary 与 measured_check_seconds。run 领取之后写 instruction.md，与 plan.md 一起附给执行器。
//   - 模板照 Python 的 str.format：占位符一次替换完，填进去的值里再出现花括号也不再替换。
//   - 命令行在 Windows 上照 subprocess.list2cmdline 拼，其余平台照 shlex.quote。
import { readdirSync, statSync } from "node:fs";
import path from "node:path";
import { PyCrash, pyFloatOf, pyGet, pyItem, pyIter, pyJoinStrings, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { ci, cmpCodePoints } from "@themis/base/pyre";
import { shlexQuote } from "@themis/base/pyshlex";
import { pyEq } from "@themis/base/pyvalue";
import { list2cmdline } from "@themis/base/supervise";
import { readJsonOr } from "./repo.ts";

const WIN = process.platform === "win32";
const LF = String.fromCharCode(10);
const BT = "`";
const code = (text: string): string => BT + text + BT;

/** 自检照抄的写法保留的输出行数（2.10.0）。 */
export const SELF_CHECK_TAIL_LINES = 40;

const TEMPLATE = [
  "# 执行说明（调度器生成）",
  "",
  "你是本任务的 Pi 执行器。前面附带的 plan.md 是已经审阅的任务合同，本说明只补充运行事实与报告格式；二者冲突时停止并报告。",
  "",
  "## 运行事实",
  "- 任务：{task_id} · 合同版本 v{version} · {attempt_id}",
  "- 工作目录：{work_dir}（独立 worktree，基线 {base}）",
  "- 可用工具：{tools}",
  "- 单轮时限：{timeout} 秒，到时会被强制终止，未完成的自检与报告都会丢失。你看不到已用时间：开始时用 shell 记下时间（例如 `date +%s`）；之后每次开跑一条合同检查之前、每次动手修一个新发现的问题之前，都先用 `date +%s` 算出已用时间。用时过半前应开始修改文件，不要在动手前长时间推演；剩余不到五分之一时停止扩展，转入收尾：不再开新的修改，来不及修的问题，相关 DoD 标 not_done、在 note 里写明，executor_status 写 partial；最后一次改动之后已经通过的检查不要重跑，与改动无关的检查也不必为求稳再跑（attempt 结束后调度器会在固定候选上重跑合同的全部检查）；一条检查跑多久以这一轮实测的用时为准；这一轮还没跑过的，看机器合同摘要里的实测用时；剩下的时间跑不完就不开跑、在报告里写明，不要用比实测用时短的 `timeout` 截着跑；结束时留出写执行报告的几分钟。",
  "",
  "## 必须遵守",
  "1. 只修改合同 Scope 允许的文件；需要越界、需要新增依赖或需要远程写入时，停止并在报告中说明。",
  "2. 不修改合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/ 与 scripts/pi_dispatch.py、scripts/dispatch-pi.sh。",
  "3. 不删除、跳过或弱化测试与断言来获得通过。",
  "4. {commit_rule}不要用 git stash、git checkout -- 或 git reset 临时撤掉自己的改动来对比基线行为：恢复一旦失败，改动就会丢失。确实需要对比时，在报告中说明，由验收端在基线副本上运行。",
  '5. 不访问工作目录之外的路径，包括主仓库、其他 worktree、家目录与系统目录（例如不要用 `ls /usr/bin/python3*` 查找解释器，直接用 PATH 上的命令）。唯一的例外是临时文件，只用来存放测试或命令的中间产物：测试框架管理的临时目录（例如 pytest 的 tmp_path）可以使用；确需在命令里新建临时目录时，只能写成 `T=$(mktemp -d)`，并以 `rm -rf "$T"` 作为这条命令的最后一步，删除之后不再接任何命令（`date`、`git status` 这类只读命令也不要接，需要时另起一条命令）；不要切换到其中运行命令，也不要读写其他工作目录之外的路径。需要截短输出时，照抄“机器合同摘要”里每条检查的“自检照抄”写法：bash 的写法以 `set -o pipefail;` 开头，管道的退出码就是被测程序自己的退出码；自己临时写的测试命令要接 `| tail` 之类的管道时，开头同样加 `set -o pipefail;`。不要把输出写到 `/tmp/v01.txt` 这类固定路径。不读取、打印或写入任何凭据。读写工作目录中的文件一律使用相对路径（工具的当前目录就是工作目录），不要手写绝对路径——手写的长路径容易拼错而落到工作目录之外；`"$T"` 这样运行时生成的临时路径不受此限。plan.md 与本说明已随消息附上，不需要再去读取它们的原始文件。',
  "6. 遇到未定义行为、需求冲突、基线不符或环境缺失：停止并报告，不要猜测。合同内部前后矛盾（例如行为说明、步骤、DoD 或测试要求对同一行为说法不同）也属于需求冲突，不要自行选定一种解释当作完成。其余部分能独立完成时可以继续，但要把两处原文、你暂时采用的做法和理由写进报告的 `contract_conflicts`，并把相关 DoD 标为 blocked。合同没有写死、需要你自己定的地方（某个边界算不算、出错时走哪条路、两种读法都说得通时选哪一种）不算矛盾：按最合理的读法继续，并写进报告的 `interpretations`。",
  "{self_check_rule}",
  "8. 验收端会在固定候选上做变异检查（mutate），你不需要自己做突变反测；确要临时改坏文件验证测试时，备份放在工作目录内（例如 `x.ts.orig`），同一条命令里改回并删除备份，不要用系统临时目录。",
  "9. 合同要求编写测试时，每个拒绝反例先验证合法基线，再只改受测条件并断言具体错误；避免另一条规则提前拒绝而掩盖缺口。比较摘要时固定其余字段，分别验证每个语义字段；非空、partial 等有不同分支的形态按合同分别覆盖。只从非法输入得到异常、或测试数量增加，不代表目标规则已被保护。",
  "{setup_facts}",
  "## 机器合同摘要（调度器据此判定范围与验收）",
  "以下内容由调度器从机器合同（JSON）自动生成。它与 plan.md 有任何不一致时，停止并在报告中指出，不要自行选择其一。",
  "",
  "{machine_summary}",
  "",
  "## 最后一条消息必须是执行报告",
  "只输出一份报告：先用中文逐项说明 DoD（{dod_ids}）的完成情况、运行过的自检命令与结果、合同中的矛盾与你的处理、遗留问题与阻塞原因；",
  "然后给出一个 JSON 代码块，字段如下（自检结果属于自述，最终验收由验收端独立完成）。",
  '`contract_conflicts` 的每一项写成 `{"quotes": ["合同原文 1", "合同原文 2"], "adopted": "暂时采用的做法", "reason": "理由"}`；没有矛盾时保留空列表。',
  '`interpretations` 列出合同没有写死、由你自己定下的做法，每一项写成 `{"quote": "合同原文或条目号", "adopted": "你采用的做法", "reason": "理由"}`；命名、函数拆分这类实现细节不算，没有就保留空列表。验收端会把它和你在推理里说过的取舍逐条对照：',
  "",
  "```json",
  "{",
  '  "task_id": "{task_id}",',
  '  "plan_version": {version},',
  '  "attempt_id": "{attempt_id}",',
  '  "executor_status": "completed | blocked | partial",',
  '  "changed_files": ["相对路径"],',
  '  "self_checks": [{"id": "V01", "command": "实际命令", "reported_exit_code": 0, "summary": "关键输出"}],',
  '  "dod": [{"id": "D01", "status": "done | not_done | blocked", "note": "说明"}],',
  '  "contract_conflicts": [],',
  '  "interpretations": [],',
  '  "unresolved_questions": [],',
  '  "limitations": []',
  "}",
  "```",
  "",
].join(LF);

const FIELD_RE = /[{](task_id|version|attempt_id|work_dir|base|tools|timeout|commit_rule|self_check_rule|dod_ids|setup_facts|machine_summary)[}]/gu;

const COMMIT_ALLOWED = "可以在 worktree 中创建本地提交，但不得推送、合并或部署。";
const COMMIT_FORBIDDEN = "不提交、推送、合并或部署；保持 HEAD 为基线提交。";
const SELF_CHECK_RULE =
  "7. 完成后运行合同 Validation commands 中与改动相关的检查（{ids}），如实记录结果；不需要每改一行都跑全量测试。必要检查通过且没有新增修改或未解决问题后，转入执行报告；" +
  "不要自行扩大到无关全仓测试。变异检查（故意改坏实现来检验测试）默认由验收端执行；" +
  "只有合同明确列出变异命令和目标范围时才能运行，local_test 本身不授权额外变异，" +
  "临时修改后恢复也不能突破 Scope。时间不足时报告未运行项与剩余工作，不得声称通过。";
const NO_SELF_CHECK_RULE = "7. 你没有可用的 shell 工具或未获自检授权：不要声称运行过测试，检查由验收端执行。";

/**
 * 合同 Markdown 写“基线应失败 / 基线应通过”，那是给验收端的说明；执行器按字面读容易误解成“这条检查应该失败”，
 * 摘要里写成完成后的要求。
 */
const BASE_NOTES = new Map([
  ["fail", "；基线上预期失败（用来证明修复），你完成后它必须通过"],
  ["pass", "；基线上已通过（回归保护），完成后仍须通过"],
]);

const strings = (value: PyValue): string[] => pyIter(value).map(pyStrValue);
const commandLine = (argv: readonly string[]): string => (WIN ? list2cmdline(argv) : argv.map(shlexQuote).join(" "));

/** 交给 list2cmdline 的 argv：它先对每一项 os.fsdecode，不是字符串时照 Python 抛 TypeError。 */
function argvOf(value: PyValue): string[] {
  return pyIter(value).map((item) => {
    if (typeof item !== "string") throw new PyCrash("TypeError", `expected str, bytes or os.PathLike object, not ${pyTypeName(item)}`);
    return item;
  });
}

/** render_instruction：执行说明的全文。 */
export function renderInstruction(
  meta: PyValue,
  contract: PyValue,
  executor: PyValue,
  timeout: PyValue,
  extraProtected: readonly string[] = [],
  setupResults: PyValue = [],
  measured: ReadonlyMap<string, bigint> | null = null,
): string {
  const rawTools = pyIter(pyItem(executor, "tools"));
  const tools = rawTools.map(pyStrValue);
  const hasShell = tools.includes("bash") || tools.includes("powershell");
  const actions = strings(pyItem(pyItem(contract, "authorization"), "executor"));
  const selfCheck = hasShell && actions.includes("local_test");
  let selfCheckRule = NO_SELF_CHECK_RULE;
  if (selfCheck) {
    const ids = pyJoinStrings(", ", pyIter(pyItem(contract, "checks")).map((check) => pyItem(check, "id"))) || "（合同未列出）";
    selfCheckRule = SELF_CHECK_RULE.replace("{ids}", () => ids);
  }
  const dodIds = pyJoinStrings(", ", pyIter(pyItem(contract, "definition_of_done")).map((item) => pyGet(item, "id", "?")));
  const fields = new Map<string, string>([
    ["task_id", pyStrValue(pyItem(meta, "task_id"))],
    ["version", pyStrValue(pyItem(meta, "plan_version"))],
    ["attempt_id", pyStrValue(pyItem(meta, "attempt_id"))],
    ["work_dir", pyStrValue(pyItem(meta, "worktree"))],
    ["base", pyStrValue(pyItem(meta, "base_sha"))],
    ["tools", pyJoinStrings(",", rawTools)],
    ["timeout", pyStrValue(timeout)],
    ["commit_rule", actions.includes("local_commit") ? COMMIT_ALLOWED : COMMIT_FORBIDDEN],
    ["self_check_rule", selfCheckRule],
    ["dod_ids", dodIds],
    ["setup_facts", setupFactsText(setupResults)],
    ["machine_summary", machineSummary(contract, extraProtected, selfCheck ? tools : [], measured)],
  ]);
  return TEMPLATE.replace(FIELD_RE, (_, name: string) => fields.get(name) as string);
}

/** setup_facts_text：prepare 阶段 setup 的结果。执行器看不到 prepare 的日志，否则只能猜依赖有没有装好。 */
export function setupFactsText(setupResults: PyValue): string {
  if (!pyTruthy(setupResults)) return "";
  const lines = ["", "## 准备阶段已经做过的事（prepare）"];
  for (const item of pyIter(setupResults)) {
    const argv = pyGet(item, "argv");
    const command = commandLine(pyTruthy(argv) ? argvOf(argv) : []);
    const passed = pyTruthy(pyGet(item, "passed")) ? "已通过" : "失败";
    lines.push(`- ${pyStrValue(pyGet(item, "id"))} ${code(command)}（cwd ${pyStrValue(pyGet(item, "cwd", "."))}）：${passed}，退出码 ${pyStrValue(pyGet(item, "exit_code"))}。不必重跑。`);
  }
  return lines.join(LF) + LF;
}

/**
 * self_check_command：执行器自检照抄的写法（2.10.0），截短输出，退出码仍是被检查程序自己的。bash 开 pipefail；只有
 * PowerShell 时打印 $LASTEXITCODE；没有 shell 时没有写法。
 */
export function selfCheckCommand(check: PyValue, tools: readonly string[]): string | null {
  const argv = strings(pyItem(check, "argv"));
  const envValue = pyGet(check, "env");
  const env = [...(pyTruthy(envValue) ? (envValue as PyDict) : new Map<string, PyValue>())].sort(([a], [b]) => cmpCodePoints(a as string, b as string));
  const cwd = pyStrValue(pyGet(check, "cwd", "."));
  const here = cwd === "" || cwd === "." || cwd === "./";
  if (tools.includes("bash")) {
    const assign = env.map(([key, value]) => `${key}=${shlexQuote(pyStrValue(value))} `).join("");
    return `set -o pipefail; ${here ? "" : `cd ${shlexQuote(cwd)} && `}${assign}${argv.map(shlexQuote).join(" ")} 2>&1 | tail -n ${SELF_CHECK_TAIL_LINES}`;
  }
  if (tools.includes("powershell")) {
    const quote = (value: string): string => `'${value.replaceAll("'", "''")}'`;
    const assign = env.map(([key, value]) => `$env:${key} = ${quote(pyStrValue(value))}; `).join("");
    return `${here ? "" : `Set-Location ${quote(cwd)}; `}${assign}& ${argv.map(quote).join(" ")} 2>&1 | Select-Object -Last ${SELF_CHECK_TAIL_LINES}; "exit=$LASTEXITCODE"`;
  }
  return null;
}

/** machine_summary：执行说明里的机器合同摘要（范围、授权与每条验收检查）。 */
export function machineSummary(contract: PyValue, extraProtected: readonly string[] = [], tools: readonly string[] = [], measured: ReadonlyMap<string, bigint> | null = null): string {
  const scope = pyItem(contract, "scope");
  const listing = (values: PyValue): string => (pyTruthy(values) ? pyIter(values).map((value) => code(pyStrValue(value))).join("、") : "无");
  const lines = [
    `- 允许修改：${listing(pyItem(scope, "allowed_modified_files"))}`,
    `- 允许新增：${listing(pyItem(scope, "allowed_new_files"))}`,
    `- 允许删除：${listing(pyItem(scope, "allowed_deleted_files"))}`,
    `- 额外禁止：${listing(pyItem(scope, "forbidden_paths"))}；另外始终禁止合同、代理规则、.agent/、.agents/、.claude/、.codex/、.pi/ 与调度脚本`,
    `- 本仓库只读的路径：${listing([...extraProtected])}`,
    `- 依赖变更：${pyStrValue(pyItem(scope, "dependency_changes"))}`,
    `- 执行器授权：${pyJoinStrings(", ", pyIter(pyItem(pyItem(contract, "authorization"), "executor")))}`,
    "- 验收检查（由验收端在固定候选上独立运行）：",
  ];
  for (const check of pyIter(pyItem(contract, "checks"))) {
    const expected = pyGet(check, "expected_exit_code", 0n);
    const id = pyItem(check, "id");
    const seconds = typeof id === "string" ? measured?.get(id) : undefined;
    const required = pyTruthy(pyGet(check, "required", true)) ? "（必要）" : "";
    const facts = [
      seconds === undefined ? "" : `，实测最长 ${seconds} 秒`,
      pyEq(expected, 0n) ? "" : `，期望退出码 ${pyStrValue(expected)}`,
      BASE_NOTES.get(pyStrValue(pyGet(check, "expect_on_base", "any"))) ?? "",
    ].join("");
    lines.push(`  - ${pyStrValue(id)}${required}：${code(commandLine(argvOf(pyItem(check, "argv"))))}（cwd ${pyStrValue(pyGet(check, "cwd", "."))}，超时 ${pyStrValue(pyItem(check, "timeout_seconds"))}s${facts}）`);
    const form = selfCheckCommand(check, tools);
    // 2.10.0：执行器照抄合同的检查命令再接管道，退出码就成了 tail 的；给出现成的截短写法
    if (form) lines.push(`    自检照抄：${code(form)}`);
  }
  return lines.join(LF);
}

/**
 * measured_check_seconds（第 120 轮）：每条检查跑完的实测用时里最长的一次。本任务 baseline 与各 attempt 的 checks.json 里，
 * 同 id、同 argv、同 cwd、没超时、退出码等于期望的才算；基线上预期失败的检查很快就失败，那次的用时不算。取最长而不取最近：
 * 估长了最多少跑一条能跑完的检查，估短了开跑之后被时限掐断。
 */
export function measuredCheckSeconds(runs: string, checks: PyValue): Map<string, bigint> {
  const wanted = new Map<string, [PyValue, PyValue]>();
  for (const check of pyIter(checks)) wanted.set(pyItem(check, "id") as string, [pyItem(check, "argv"), pyGet(check, "cwd", ".")]);
  const longest = new Map<string, number>();
  const files = [...globPaths(runs, ["baseline", "*", "checks.json"]), ...globPaths(runs, ["attempt-*", "checks", "*", "checks.json"])];
  for (const file of files) {
    const results = pyGet(readJsonOr(file, new Map()), "results");
    for (const item of pyTruthy(results) ? pyIter(results) : []) {
      const id = pyGet(item, "id");
      if (Array.isArray(id) || id instanceof Map) throw new PyCrash("TypeError", `unhashable type: '${Array.isArray(id) ? "list" : "dict"}'`);
      const target = typeof id === "string" ? wanted.get(id) : undefined;
      if (
        target === undefined ||
        !pyEq(target[0], pyGet(item, "argv")) ||
        !pyEq(target[1], pyGet(item, "cwd", ".")) ||
        pyTruthy(pyGet(item, "timed_out")) ||
        !pyEq(pyGet(item, "exit_code"), pyGet(item, "expected_exit_code")) ||
        pyGet(item, "wall_seconds") === null
      ) {
        continue;
      }
      const key = id as string;
      const seconds = pyFloatOf(pyItem(item, "wall_seconds"));
      const known = longest.get(key) ?? 0;
      // max(已知, 本次)：并列或本次是 NaN 时留已知的
      longest.set(key, seconds > known ? seconds : known);
    }
  }
  return new Map([...longest].map(([key, seconds]) => [key, roundToInt(seconds)]));
}

/** int(round(x))：四舍六入五成双。NaN 到不了这里（max 遇到 NaN 留已知的）。 */
function roundToInt(value: number): bigint {
  if (!Number.isFinite(value)) throw new PyCrash("OverflowError", "cannot convert float infinity to integer");
  const floor = Math.floor(value);
  const rest = value - floor;
  const up = rest > 0.5 || (rest === 0.5 && floor % 2 !== 0);
  return BigInt(up ? floor + 1 : floor);
}

/**
 * Path(root).glob(pattern)（Python 3.12）：每一级都按 fnmatch 匹配目录里的名字（Windows 上不分大小写，re.I 下 s 也配 ſ），
 * 不是最后一级时只要目录；列不出的目录跳过。顺序是操作系统列目录的顺序。
 */
function globPaths(root: string, parts: readonly string[]): string[] {
  const [part, ...rest] = parts;
  if (part === undefined) return [root];
  if (!isDir(root)) return [];
  let names: string[];
  try {
    names = readdirSync(root);
  } catch {
    return [];
  }
  const pattern = new RegExp(`^${part.split("*").map((piece) => (WIN ? ci(piece) : [...piece].map((char) => `[${char}]`).join(""))).join("[^]*")}$`, "u");
  const found: string[] = [];
  for (const name of names) {
    const child = path.join(root, name);
    if (rest.length && !isDir(child)) continue;
    if (pattern.test(name)) found.push(...(rest.length ? globPaths(child, rest) : [child]));
  }
  return found;
}

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}
