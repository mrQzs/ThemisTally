// review-draft（迁移第 ④b8a 片）：按证据生成复审记录骨架与独立复审简报（2.8.0）。能从证据取的都填好（基线、候选、模型、用时、
// token、门禁的机械部分、DoD 的检查结果与目的、各轮变异、执行报告的自述、摘要的关注项），判断留【待填】；verdict 拒收仍有
// 【待填】的记录。简报写到 <run-dir>/review-brief.md，交给 pi-reviewer 或另一家厂商的只读 CLI。
//   - 证据文件是 JSON，取值照 Python 的 dict.get、or、in 与 % 格式化（类型不对时照 Python 抛异常）。
//   - 本机的 platform.platform() 由启动器放进 context（迁移计划 D1），evaluate_gates 用。
import { statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyGet, pyItem, pyIter, pyJoinStrings, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyReadText } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps, encodeUtf8 } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { displayPath, purePathStr, pyExists, pyResolve } from "@themis/base/pypath";
import { S, codePoints, pyLower, pyRegex, pyRstrip, pySplitlines, pyStrip } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import { loadAttempt, logEvent } from "./evidence.ts";
import { evaluateGates } from "./gates.ts";
import { globPaths } from "./instruction.ts";
import { attemptExecutor } from "./metrics.ts";
import { TOOL_VERSION } from "./prepare.ts";
import { DispatchError, EXIT_OK, EXIT_USAGE, Repo, readJsonOr } from "./repo.ts";
import { getState, latestNumbered, resolveRunDir } from "./status.ts";

const LF = String.fromCharCode(10);
const BT = String.fromCharCode(96);
const code = (text: string): string => BT + text + BT;

/** 给复审判断留的占位；verdict 拒收仍含它的复审记录（PLACEHOLDER_RE）。 */
const REVIEW_TODO = "【待填】";
const GATE_LABELS = [["G0", "输入一致"], ["G1", "执行完整"], ["G2", "范围合规"], ["G3", "行为正确"], ["G4", "回归检查"], ["G5", "质量复审"], ["G6", "可集成"]];
/** 复审骨架与简报照录的执行报告字段（2.10.0 加了 interpretations）。 */
const REPORT_STATEMENTS = [["contract_conflicts", "合同矛盾"], ["interpretations", "自定解读"], ["limitations", "限制与取舍"], ["unresolved_questions", "未决问题"]];
/** 复审骨架列出的解读线索条数上限。 */
const REVIEW_CLUE_LIMIT = 10;
const SPACES_RE = pyRegex(`${S}+`, true);

export interface ReviewDraftArgs {
  readonly repo: string | null;
  readonly run_dir: string;
  readonly out: string | null;
  readonly force: boolean;
}

const s = pyStrValue;
const get = (value: PyValue, key: string, fallback: PyValue = null): PyValue => pyGet(value, key, fallback);
/** x or fallback。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);

/** cmd_review_draft：运行结束、证据收集完之后才生成；已有骨架或复审记录时要 --force。 */
export function cmdReviewDraft(args: ReviewDraftArgs, out: PyOut, here: string): number {
  const repo = Repo.discover(args.repo);
  const runDir = resolveRunDir(repo, args.run_dir);
  const [meta, contract] = loadAttempt(runDir);
  const state = getState(runDir);
  if (["PREPARING", "PREPARED", "RUNNING", "COLLECTING"].includes(state)) {
    throw new DispatchError(`attempt 处于 ${state}：运行结束、证据收集完之后再生成复审骨架`, EXIT_USAGE);
  }
  const outPath = args.out
    ? pyResolve(path.resolve(process.cwd(), args.out))
    : path.join(repo.agentDir, "reviews", pyItem(meta, "task_id") as string, `${path.basename(runDir)}.md`);
  if (pyExists(outPath) && !args.force) {
    throw new DispatchError(`${displayPath(outPath, repo.root)} 已存在：确认要覆盖（例如重新生成骨架）时加 --force`, EXIT_USAGE);
  }
  const executor = attemptExecutor(runDir, new Map());
  const events = readJsonOr(path.join(runDir, "events-summary.json"), new Map());
  const run = readJsonOr(path.join(runDir, "run.json"), new Map());
  const candidate = readJsonOr(path.join(runDir, "candidate.json"), new Map());
  const scope = or(readJsonOr(path.join(runDir, "scope.json"), new Map()), new Map());
  const rawReport = readJsonOr(path.join(runDir, "executor-report.json"), new Map());
  const report: PyDict = rawReport instanceof Map ? rawReport : new Map();
  const reportStatus = get(readJsonOr(path.join(runDir, "report-status.json"), new Map()), "status");
  const summaryText = readTextOr(path.join(runDir, "summary.md"));
  const usage = or(get(events, "usage"), new Map());
  const cost = or(get(events, "cost"), new Map());
  const budget = or(get(contract, "budget"), new Map());
  const statLines = pySplitlines(pyStrip(readTextOr(path.join(runDir, "candidate.stat.txt"))));
  const latest = latestNumbered(path.join(runDir, "checks"));
  const checks = latest ? readJsonOr(path.join(latest, "checks.json"), new Map()) : new Map();
  const aborted = pyTruthy(get(checks, "aborted"));
  const checkResults = new Map<PyValue, PyValue>();
  if (!aborted) for (const record of pyIter(get(checks, "results", []))) checkResults.set(pyItem(record, "id"), record);
  const ran = [...checkResults.values()];
  const checksLine = latest && !aborted
    ? `checks/${path.basename(latest)}（${s(get(checks, "mode"))}，${ran.filter((record) => pyTruthy(get(record, "passed"))).length}/${ran.length} 通过）`
    : "没有有效的检查记录";
  const gates = evaluateGates(repo, runDir, meta, contract, here).get("gates") as PyDict;
  const actual = pyIter(or(get(events, "actual_models"), [])).map((model) => `${s(get(model, "provider"))}/${s(get(model, "model"))}`).join("、") || "未知";
  const levels = pyIter(or(get(events, "provider_thinking_levels"), [])).map(s).join("、") || "未回报";
  const ending = pyTruthy(get(run, "timed_out")) ? "超时" : pyTruthy(get(run, "interrupted")) ? "取消" : "正常结束";
  const costText = get(cost, "total") !== null ? `${s(get(cost, "total"))}（${s(get(cost, "status"))}）` : `unknown（${s(get(cost, "status", "无记录"))}）`;
  const lines = [
    `# REVIEW：${s(pyItem(meta, "task_id"))} v${s(pyItem(meta, "plan_version"))} · ${path.basename(runDir)}`, "",
    `Verdict: ${REVIEW_TODO}（PASS / ACCEPTED_WITH_EXCEPTION / REVISE / BLOCKED / ESCALATE 中的一个）`, "",
    // 说明里不能出现占位记号本身：verdict 按行拒收含它的记录，填完判断也交不上（2.9.0，kit-install 实机）
    `<!-- review-draft 生成（${utcNow()}，调度工具 ${TOOL_VERSION}）：事实取自 ${displayPath(runDir, repo.root)}；标着“待填”的地方是复审判断，全部填完 verdict 才收。`,
    "     Verdict 行只能写一个结论，并与 verdict 命令的 --verdict 一致。 -->", "",
    "## 基本信息",
    `- 基线：${code(s(pyItem(meta, "base_sha")))}`,
    `- 候选树：${code(s(get(candidate, "tree")))}（补丁往返校验${pyTruthy(get(candidate, "patch_roundtrip_verified")) ? "通过" : "未通过"}；` +
      `${statLines.length ? pyStrip(statLines[statLines.length - 1] as string) : "无改动"}）`,
    `- 要求的执行模型：${s(get(executor, "provider"))}/${s(get(executor, "model"))} · thinking ${s(get(executor, "thinking"))}`,
    `- 实际模型：${actual}；providerThinkingLevel：${levels}`,
    `- 运行：退出码 ${s(get(run, "exit_code"))} · 用时 ${s(get(run, "wall_seconds"))} s / 上限 ${s(get(budget, "max_wall_seconds_per_attempt"))} s · ${ending} · ` +
      `工具错误 ${s(get(events, "tool_errors"))}`,
    `- token：输入 ${s(get(usage, "input"))} · 输出 ${s(get(usage, "output"))} · 缓存读 ${s(get(usage, "cacheRead"))} · 缓存写 ${s(get(usage, "cacheWrite"))}；` +
      `费用 ${costText}`,
    `- 复审者：${REVIEW_TODO}（规划/验收会话；中高风险写明独立复审者的工具与模型，换一家审查时写厂商）`, "",
    "## 门禁", "", "| 门禁 | 结果 | 说明 |", "|---|---|---|",
  ];
  for (const [gate, label] of GATE_LABELS as [string, string][]) {
    const info = gates.get(gate) as PyDict;
    const passed = pyTruthy(pyItem(info, "passed"));
    const mechanical = `工具：${passed ? "通过" : "不通过"}`;
    let detail = pyJoinStrings("；", [...(pyItem(info, "problems") as PyValue[]), ...(pyItem(info, "notes") as PyValue[])]);
    if (gate === "G4") detail = `检查记录：${checksLine}${detail ? "；" + detail : ""}`;
    const result = gate === "G3" || gate === "G5" ? REVIEW_TODO : passed ? "passed" : "failed";
    lines.push(`| ${gate} ${label} | ${result} | ${cell(mechanical + (detail ? "；" + detail : ""))} |`);
  }
  lines.push("", "## DoD 映射", "", "| DoD | 结果 | 证据 | 说明 |", "|---|---|---|---|");
  const violations = get(scope, "violations", []);
  const dod = pyIter(get(contract, "definition_of_done", []));
  for (const item of dod) {
    const evidence = pyIter(get(item, "evidence", [])).map((ref) => {
      if (ref === "scope") return `scope（越界 ${lenOf(violations)}）`;
      if (ref === "review") return "复审";
      const record = checkResults.get(ref);
      return `${s(ref)} ${pyTruthy(record) ? s(get(record as PyValue, "status")) : "未运行"}`;
    });
    const note = s(or(get(item, "text"), "")) + (pyTruthy(get(item, "intent")) ? `；目的：${s(pyItem(item, "intent"))}` : "");
    lines.push(`| ${s(get(item, "id"))} | ${REVIEW_TODO} | ${cell(evidence.join("、"))} | ${cell(note)} |`);
  }
  const [mutationLines, surprising] = mutationReviewLines(runDir);
  const shownViolations = pyTruthy(violations)
    ? "：" + pyIter(violations).slice(0, 10).map((v) => `${s(get(v, "kind"))} ${s(get(v, "path"))}`).join("；")
    : "";
  lines.push("", "## 范围与质量",
    `- 越界与警告：越界 ${lenOf(violations)}、警告 ${lenOf(get(scope, "warnings", []))}${shownViolations}`,
    `- 测试可信度：${REVIEW_TODO}（用例数量、能否在旧实现上失败、有无 skip 或弱化）`);
  if (mutationLines.length) lines.push("- 变异检查：", ...mutationLines.map((line) => "  " + line));
  else lines.push("- 变异检查：没有记录（中高风险任务要做一轮，见 review-pi/mutation-check.md）");
  lines.push(`- 兼容性与残余风险：${REVIEW_TODO}`, `- 执行器自述与证据是否一致：${REVIEW_TODO}`,
    `  - 执行报告：${s(reportStatus)}（executor_status ${s(get(report, "executor_status"))}）`);
  for (const [key, label] of REPORT_STATEMENTS as [string, string][]) {
    const values = or(get(report, key), []);
    if (key === "interpretations" && reportStatus === "json_ok" && !Array.isArray(get(report, key))) {
      lines.push(`  - ${label}：报告没有这个列表（2.10.0 起报告格式里有）`);
      continue;
    }
    if (!pyTruthy(values)) {
      lines.push(`  - ${label}：无`);
      continue;
    }
    lines.push(`  - ${label}（${lenOf(values)}，原文）：`);
    for (const value of pyIter(values)) lines.push(`    - ${cell(statementText(value), 1200)}`);
  }
  const clues = interpretationClueLines(events);
  lines.push(clues.length ? "  - 事件流里的解读线索（逐条核对是否都在上面的自定解读、合同矛盾或未决问题里）：" : "  - 事件流里的解读线索：无",
    ...clues.map((line) => "  " + line));
  const attention = summarySection(summaryText, "复审需要关注");
  lines.push("- 摘要里的“复审需要关注”（原文）：", ...(attention.length ? attention.map((line) => "  " + line) : ["  - 无"]));
  const integration = or(get(or(get(contract, "authorization"), new Map()), "integration"), []);
  const shownRun = displayPath(runDir, repo.root);
  const action = pyIn("local_branch", integration) && pyIn("merge", integration)
    ? `local_branch、merge：${code(`bash scripts/dispatch-pi.sh integrate ${shownRun}`)}（当前末端上验证后落地）`
    : pyIn("local_branch", integration)
      ? `local_branch：${code(`integrate ${shownRun}`)} 只验证并打印落地命令（合同没有 merge），或 ${code(`branch ${shownRun}`)}`
      : "合同没有授权集成动作：交付候选，等待决定";
  lines.push("", "## 结论理由", REVIEW_TODO, "",
    "## 后续动作",
    `- 需要修正的具体差异（REVISE）：${REVIEW_TODO}（没有写“无”）`,
    `- 待决的业务或环境问题（BLOCKED / ESCALATE）：${REVIEW_TODO}（没有写“无”）`,
    `- 已授权且可以继续的集成动作：${action}`,
    `- 人工介入：${REVIEW_TODO}（分钟数与原因，用于 --human-minutes）`, "");
  pathMkdir(path.dirname(outPath), true, true);
  writeFileSync(outPath, encodeUtf8(lines.join(LF)));
  const brief = reviewBrief(runDir, meta, dod, checksLine, attention, surprising, report, clues);
  writeFileSync(path.join(runDir, "review-brief.md"), encodeUtf8(brief.join(LF)));
  logEvent(runDir, "review_draft", [["path", outPath]]);
  const todo = lines.filter((line) => line.includes(REVIEW_TODO)).length;
  out.print(`已写复审记录骨架：${displayPath(outPath, repo.root)}（${todo} 处${REVIEW_TODO}）`);
  out.print(`独立复审简报：${displayPath(path.join(runDir, "review-brief.md"), repo.root)}（交给 pi-reviewer，或另一家厂商的只读 CLI）`);
  return EXIT_OK;
}

/** 独立复审简报的各行（写到 <run-dir>/review-brief.md）。 */
function reviewBrief(runDir: string, meta: PyValue, dod: PyValue[], checksLine: string, attention: string[], surprising: string[],
  report: PyDict, clues: string[]): string[] {
  const worktree = purePathStr(pyItem(meta, "worktree") as string);
  const cleaned = isDirectory(worktree) ? "" : `（已清理：用 git show ${codePoints(pyItem(meta, "base_sha") as string).slice(0, 12).join("")}:<路径> 对照补丁）`;
  const brief = [`# 独立复审简报：${s(pyItem(meta, "task_id"))} v${s(pyItem(meta, "plan_version"))} · ${path.basename(runDir)}`, "",
    `按 ${code(".agents/skills/review-pi/independent-review.md")} 复审：只读，不修改任何文件，只输出结论与发现。`, "",
    `- RUN：${code(runDir)}`,
    `- 合同：RUN/plan.md；候选：RUN/candidate.patch；检查：${checksLine}`,
    `- worktree：${code(worktree)}${cleaned}`, "",
    "## 重点", "", "- 每条 DoD 的目的（检查通过而目的没有保住，就是不满足）："];
  for (const item of dod) brief.push(`  - ${s(get(item, "id"))}：${cell(or(or(get(item, "intent"), get(item, "text")), ""), 600)}`);
  brief.push("- 摘要里的“复审需要关注”：", ...(attention.length ? attention.map((line) => "  " + line) : ["  - 无"]));
  brief.push("- 意外漏掉的变异（测试可能有缺口，或是等价改写）：", ...(surprising.length ? surprising.map((item) => `  - ${item}`) : ["  - 无"]));
  const stated = (REPORT_STATEMENTS as [string, string][]).flatMap(([key, label]) => {
    const values = get(report, key);
    return Array.isArray(values) ? values.map((value) => `  - ${label}：${cell(statementText(value), 600)}`) : [];
  });
  brief.push("- 执行器自述的取舍（核对是否越出合同字面）：", ...(stated.length ? stated : ["  - 无"]));
  brief.push("- 事件流里的解读线索（核对是否都已写进报告；没写的就是没有报告的自定解读）：", ...(clues.length ? clues : ["  - 无"]));
  brief.push("- 规划端补充的风险：（交给复审者前在这里补充）", "", "## 输出", "",
    "按 independent-review.md 的“输出”一节：建议结论、按严重度排序的发现（文件:行、问题、证据、建议的修正）、无法判断的项以及需要主会话补跑的检查。", "");
  return brief;
}

/** _cell：表格单元，单行、不含竖线、截断到 limit 个码点。 */
function cell(value: PyValue, limit = 400): string {
  const text = pyStrip(s(value).replace(SPACES_RE, " ").replaceAll("|", "/"));
  const points = codePoints(text);
  return points.length <= limit ? text : points.slice(0, limit - 1).join("") + "…";
}

/** 执行报告里的一条自述：字符串原样，其余照 json.dumps(ensure_ascii=False)。 */
const statementText = (value: PyValue): string => (typeof value === "string" ? value : dumps(value, { ensureAscii: false }));

/** _summary_section：summary.md 里某一节的非空行（到下一个二级标题为止），去掉行尾空白。 */
function summarySection(summaryText: string, heading: string): string[] {
  const lines = pySplitlines(summaryText);
  const start = lines.indexOf(`## ${heading}`);
  if (start < 0) return [];
  const found: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith("## ")) break;
    if (pyStrip(line)) found.push(pyRstrip(line));
  }
  return found;
}

/**
 * _mutation_review_lines：复审记录的变异一节与简报里的意外漏掉（2.8.0）。每轮每条命令一行计数；意外漏掉的逐条写成复审模板
 * 的固定格式，归因与处理留【待填】；标了等价的预填“等价变异”；列进 expect_missed 的合并成一行“预期内”。
 */
function mutationReviewLines(runDir: string): [string[], string[]] {
  const lines: string[] = [];
  const brief: string[] = [];
  // sorted(Path.glob)：Windows 上 Path 按小写之后的各级名字比较
  const files = globPaths(path.join(runDir, "mutations"), ["*", "mutations.json"]).sort(comparePaths);
  for (const file of files) {
    const data = readJsonOr(file, null);
    const label = `mutations/${path.basename(path.dirname(file))}`;
    if (!(data instanceof Map) || pyTruthy(data.get("aborted") ?? null)) {
      lines.push(`- ${label}：没有结果（${data instanceof Map ? s(data.get("aborted") ?? null) : "记录无法读取"}）`);
      continue;
    }
    const results = pyIter(or(data.get("results") ?? null, [])).filter((record): record is PyDict => record instanceof Map);
    const listed = pyIter(or(data.get("commands") ?? null, [])).filter((item) => item instanceof Map).map((item) => get(item, "id"));
    const commands = listed.length ? listed : ["main"];
    const multi = commands.length > 1;
    const statusUnder = (record: PyDict, cid: PyValue): PyValue => {
      const runs = or(record.get("commands") ?? null, new Map());
      if (!multi) return record.get("status") ?? null;
      return or(get(or(get(runs, cid as string), new Map()), "status"), record.get("status") ?? null);
    };
    const unexpectedMissed = (record: PyDict): PyValue[] =>
      pyIter(record.has("unexpected") ? (record.get("unexpected") as PyValue) : commands).filter((cid) => statusUnder(record, cid) === "missed");
    lines.push(`- ${label}：${results.length} 条${multi ? "，命令 " + pyJoinStrings("、", commands) : ""}`);
    for (const cid of commands) {
      const count = (status: string): number => results.filter((record) => statusUnder(record, cid) === status).length;
      const surprise = results.filter((record) => listIncludes(unexpectedMissed(record), cid)).map((record) => pyItem(record, "id"));
      const caughtAnyway = results
        .filter((record) => pyIn(cid, or(record.get("unexpected") ?? null, [])) && statusUnder(record, cid) === "caught")
        .map((record) => pyItem(record, "id"));
      lines.push(`  - ${multi ? `${s(cid)}：` : ""}抓住 ${count("caught")}，漏掉 ${count("missed")}（意外 ${surprise.length}` +
        `${surprise.length ? "：" + pyJoinStrings(" ", surprise) : ""}），跳过 ${count("skipped")}，出错 ${count("error")}` +
        `${caughtAnyway.length ? "；标了预期漏掉却被抓住：" + pyJoinStrings(" ", caughtAnyway) : ""}`);
    }
    const owned: string[] = [];
    for (const record of results) {
      const name = s(or(record.get("name") ?? null, ""));
      const id = record.get("id") ?? null;
      const shown = name.startsWith(s(id)) ? name : `${s(id)} ${name}`;
      const missedUnexpected = unexpectedMissed(record);
      const missedSomewhere = (): boolean => commands.some((cid) => statusUnder(record, cid) === "missed");
      if (missedUnexpected.length) {
        lines.push(`  - ${code(shown)}${multi ? `（${pyJoinStrings("、", missedUnexpected)} 意外漏掉）` : ""} → 归因：${REVIEW_TODO}` +
          `（合同遗漏 | 执行器少写 | 等价变异 | 输入观察不到） → 处理：${REVIEW_TODO}（规划端补测 <提交> | REVISE | 注明 | 探针实测）`);
        brief.push(`${shown}（${s(record.get("file") ?? null)}，${label}）`);
      } else if (pyTruthy(record.get("equivalent") ?? null) && missedSomewhere()) {
        lines.push(`  - ${code(shown)} → 归因：等价变异（${s(pyItem(record, "equivalent"))}） → 处理：注明`);
      } else if (pyTruthy(record.get("expect_missed") ?? null) && missedSomewhere()) {
        owned.push(s(id));
      }
    }
    if (owned.length) lines.push(`  - 预期内的漏掉（expect_missed：合同交给其他命令覆盖的规则）：${owned.join(" ")} → 处理：注明`);
  }
  return [lines, brief];
}

/** _interpretation_clue_lines：事件流里执行器自己宣布裁定的句子，按行号与摘录列出（2.10.0）。 */
function interpretationClueLines(events: PyValue): string[] {
  const clues = pyIter(or(get(events, "interpretation_mentions"), [])).filter((item) => item instanceof Map);
  const lines = clues.slice(0, REVIEW_CLUE_LIMIT).map((item) => `  - 第 ${s(get(item, "line"))} 行（${s(get(item, "kind"))}）：${cell(get(item, "excerpt", ""), 300)}`);
  const total = or(get(events, "interpretation_mention_count"), BigInt(clues.length));
  if (typeof total !== "bigint" && typeof total !== "number" && typeof total !== "boolean") {
    throw new PyCrash("TypeError", `'>' not supported between instances of '${pyTypeName(total)}' and 'int'`);
  }
  if (Number(total) > lines.length && lines.length) lines.push(`  - 另有 ${Math.trunc(Number(total)) - lines.length} 处，见 events-summary.json 的 interpretation_mentions`);
  return lines;
}

/** item in container：列表按 ==，字典看键，字符串看子串（左边必须是字符串），其余照 Python 报 TypeError。 */
function pyIn(item: PyValue, container: PyValue): boolean {
  if (Array.isArray(container)) return listIncludes(container, item);
  if (container instanceof Map) {
    if (Array.isArray(item) || item instanceof Map) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(item)}'`);
    return typeof item === "string" && container.has(item);
  }
  if (typeof container === "string") {
    if (typeof item !== "string") throw new PyCrash("TypeError", `'in <string>' requires string as left operand, not ${pyTypeName(item)}`);
    return container.includes(item);
  }
  throw new PyCrash("TypeError", `argument of type '${pyTypeName(container)}' is not iterable`);
}

const listIncludes = (items: readonly PyValue[], item: PyValue): boolean => items.some((value) => pyEq(value, item));

/** len(value)：列表、字典、字符串（码点），其余照 Python 报 TypeError。 */
function lenOf(value: PyValue): number {
  if (Array.isArray(value)) return value.length;
  if (value instanceof Map) return value.size;
  if (typeof value === "string") return codePoints(value).length;
  throw new PyCrash("TypeError", `object of type '${pyTypeName(value)}' has no len()`);
}

/** WindowsPath 的比较：各级名字小写之后逐级比（POSIX 上不改大小写）。 */
function comparePaths(a: string, b: string): number {
  const parts = (value: string): string[] => (process.platform === "win32" ? pyLower(value) : value).split(path.sep);
  const [left, right] = [parts(a), parts(b)];
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    const [x, y] = [left[index] as string, right[index] as string];
    if (x !== y) return x < y ? -1 : 1;
  }
  return left.length - right.length;
}

/** read_text_or：读不了或不是 UTF-8 时返回空串。 */
function readTextOr(file: string): string {
  try {
    return pyReadText(file);
  } catch (error) {
    if (error instanceof PyOSError || error instanceof PyUnicodeDecodeError) return "";
    throw error;
  }
}

function isDirectory(value: string): boolean {
  try {
    return statSync(value).isDirectory();
  } catch {
    return false;
  }
}
