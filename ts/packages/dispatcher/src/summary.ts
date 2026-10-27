// pi_dispatch.write_summary（迁移第 ④b6 片）：attempt 的 summary.md。各节标题是内部格式契约：review-draft 按“复审需要关注”
// 一节解析（④b8）。取值照 Python 的 %s、%d 写法；证据文件里的字段缺失或类型不对时照 Python 抛同类异常，求值次序也照 Python，
// 先出错的先报。
import path from "node:path";
import { writeText } from "@themis/base/fsutil";
import {
  PyCrash,
  pyFixed,
  pyFloatOf,
  pyGet,
  pyItem,
  pyIter,
  pyJoin,
  pyJoinStrings,
  pyLenValue,
  pyPercentD,
  pyPlus,
  pyStrValue,
  pyTruthy,
  pyTypeName,
} from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { displayPath } from "@themis/base/pypath";
import { cmpCodePoints, codePoints } from "@themis/base/pyre";
import { redactSecrets } from "@themis/base/secrets";
import { pyEq } from "@themis/base/pyvalue";
import { DECISIONS_RECORD, answerValue, latestByPoint } from "./decision-records.ts";
import { attemptExecutor, frozenExecutorClass, readRecords } from "./metrics.ts";
import { type Repo, readJsonOr } from "./repo.ts";
import { getState } from "./status.ts";

const NL = String.fromCharCode(10);
const BACKTICK = "`";

/** 问题清单里 summary 用到的两项：给人看的 label 与提示的阈值。 */
export interface BatteryView {
  readonly labels: PyDict;
  readonly thresholds: PyDict;
}

export interface SummaryContext {
  /**
   * kit 的 plugins/decisions/questions 里 report-screen 那一份；清单读不了（DecisionError）或没有这一份时为 null。
   * 由命令层接上配置中心的 loadBatteries（@themis/config 依赖本包，这里不能反过来 import 它）。
   */
  readonly reportScreen: () => BatteryView | null;
}

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const get = (value: PyValue, key: string, fallback: PyValue = null): PyValue => pyGet(value, key, fallback);
const s = (value: PyValue): string => pyStrValue(value);
const yesNo = (value: PyValue): string => (pyTruthy(value) ? "是" : "否");
const code = (text: string): string => BACKTICK + text + BACKTICK;
/** x or fallback。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);

/** value.replace("`", "'")：不是字符串时照 Python 抛 AttributeError。 */
function tick(value: PyValue): string {
  if (typeof value !== "string") throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'replace'`);
  return value.split(BACKTICK).join("'");
}

/** value[:count]。 */
function prefix(value: PyValue, count: number): PyValue {
  if (typeof value === "string") return codePoints(value).slice(0, count).join("");
  if (Array.isArray(value)) return value.slice(0, count);
  if (isDict(value)) throw new PyCrash("KeyError", `slice(None, ${count}, None)`);
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not subscriptable`);
}

/** value[0]：调用方都先判过真值（空串、空列表走不到这里）。 */
function first(value: PyValue): PyValue {
  if (typeof value === "string") return codePoints(value)[0] as string;
  if (Array.isArray(value)) return value[0] as PyValue;
  if (isDict(value)) throw new PyCrash("KeyError", "0");
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not subscriptable`);
}

/** dict.items()：不是字典时照 Python 抛 AttributeError。 */
function items(value: PyValue): [PyValue, PyValue][] {
  if (!isDict(value)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'items'`);
  return [...value] as [PyValue, PyValue][];
}

/** value > count（count 是 int）：不是数字时照 Python 抛 TypeError。 */
function greater(value: PyValue, count: number): boolean {
  if (typeof value === "bigint") return value > BigInt(count);
  if (typeof value === "number") return value > count;
  if (typeof value === "boolean") return Number(value) > count;
  throw new PyCrash("TypeError", `'>' not supported between instances of '${pyTypeName(value)}' and 'int'`);
}

/** value - count：调用前已经过了 %d，只会是数字。 */
function minus(value: PyValue, count: number): PyValue {
  if (typeof value === "number") return value - count;
  if (typeof value === "bigint") return value - BigInt(count);
  return BigInt(value === true ? 1 : 0) - BigInt(count);
}

const numeric = (value: PyValue): value is bigint | number | boolean =>
  typeof value === "bigint" || typeof value === "number" || typeof value === "boolean";

/** sorted({...})：集合去重（1、1.0 与 True 相等），字符串按码点、数字按大小排；不可哈希或比不了时照 Python 抛 TypeError。 */
function sortedUnique(values: readonly PyValue[]): PyValue[] {
  for (const value of values) {
    if (Array.isArray(value) || isDict(value)) throw new PyCrash("TypeError", `unhashable type: '${pyTypeName(value)}'`);
  }
  const unique: PyValue[] = [];
  for (const value of values) if (!unique.some((seen) => pyEq(seen, value))) unique.push(value);
  if (unique.length < 2) return unique; // 一项不比较，什么类型都照常（themistally-15 复核 ④b6 查出）
  if (unique.every((value) => typeof value === "string")) return (unique as string[]).sort(cmpCodePoints);
  if (unique.every(numeric)) return unique.sort((a, b) => Number(a) - Number(b));
  const [left, right] = [unique[0] as PyValue, unique.find((value) => pyTypeName(value) !== pyTypeName(unique[0] as PyValue)) as PyValue];
  throw new PyCrash("TypeError", `'<' not supported between instances of '${pyTypeName(right)}' and '${pyTypeName(left)}'`);
}

/** "`a`、`b`" 这种列举：每项照 %s。 */
const listed = (values: readonly PyValue[]): string => values.map((value) => code(s(value))).join("、");

/**
 * executor_source_text：摘要的“执行模型来源”一行；按现在的规则脱敏，旧规则下留下的副本也一样。
 * meta 不是字典时照 Python 抛 AttributeError（在读合同的类别之后）。
 */
export function executorSourceText(runDir: string, meta: PyValue): string {
  return redactSecrets(sourceText(runDir, meta));
}

function sourceText(runDir: string, meta: PyValue): string {
  const kind = frozenExecutorClass(runDir);
  const binding = get(meta, "executor_binding");
  if (kind === "role") {
    if (!isDict(binding)) return "按角色写，但 meta.json 缺少 executor_binding";
    const field = (key: string): string => s(get(binding, key));
    const sha = codePoints(s(or(get(binding, "config_sha256"), "无"))).slice(0, 12).join("");
    return `角色绑定 ${field("role")}（profile ${field("profile")}，runtime ${field("runtime")}，方案 ${s(or(get(binding, "active_preset"), "无"))}，配置 sha256 ${sha}，记录 ${field("record_path")}）`;
  }
  if (kind === "written") {
    const note = get(meta, "executor_binding_note");
    if (isDict(note) && isDict(get(note, "binding"))) {
      const other = get(note, "binding");
      return `合同写死；与当时的 ${s(get(note, "role"))} 绑定不同（profile ${s(get(note, "profile"))}：${s(get(other, "provider"))}/${s(get(other, "model"))} · thinking ${s(get(other, "thinking"))}）`;
    }
    return "合同写死";
  }
  return "合同，缺的项由环境变量 PI_EXEC_* 补上";
}

/** _decisions_summary：“决策”一节与（on 模式下）要进“复审需要关注”的行；没有 report-screen 的记录时都为空。 */
function decisionsSummary(runDir: string, context: SummaryContext): [string[], string[]] {
  const record = latestByPoint(readRecords(path.join(runDir, DECISIONS_RECORD))).get("report-screen");
  if (record === undefined) return [[], []];
  const battery =
    get(record, "reason") === "battery_drift"
      ? "与内容锁不符，本次没有问"
      : `${s(get(record, "battery_version"))}（${s(prefix(or(get(record, "battery_sha256"), ""), 12))}）`;
  const lines = [
    `模式 ${s(get(record, "mode"))} · 模型 ${s(get(record, "model"))} · 清单 report-screen ${battery}`,
    "",
    "决策模型的答案只是提示，门禁不读它；中文输入上的准确率先用 shadow 记录对照（`decisions replay`）再决定开 on。",
    "",
  ];
  const attention: string[] = [];
  if (get(record, "status") !== "answered") {
    const detail = pyTruthy(get(record, "detail")) ? `（${s(pyItem(record, "detail"))}）` : "";
    lines.push(`- 无意见：${s(get(record, "reason"))}${detail}`);
    return [lines, attention];
  }
  const view = context.reportScreen();
  const labels: PyDict = view ? view.labels : new Map();
  const thresholds: PyDict = view ? view.thresholds : new Map();
  const action = Number(get(thresholds, "action", 0.7));
  const severityAction = Number(get(thresholds, "severity_action", 2.0));
  for (const [name, answer] of items(get(record, "answers", new Map()))) {
    const [shown, confidence] = answerValue(answer);
    const label = get(labels, name as string, name);
    lines.push(`- ${s(label)}（${s(name)}）：${shown} · 置信度 ${pyFixed(confidence, 2)}`);
    if (get(record, "mode") !== "on") continue;
    if (get(answer, "type") === "noul" && pyFloatOf(get(answer, "noul", 0)) >= action) {
      attention.push(`决策模型提示（report-screen/${s(name)} p=${pyFixed(pyFloatOf(pyItem(answer, "noul")), 2)}）：${s(label)}；按证据核实，这不是裁定`);
    } else if (get(answer, "type") === "score" && pyFloatOf(get(answer, "score", 0)) >= severityAction) {
      attention.push(`决策模型提示（report-screen/severity ${pyFixed(pyFloatOf(pyItem(answer, "score")), 2)}）：报告可能误导不核对证据的复审者`);
    }
  }
  lines.push(`- 用时 ${s(get(record, "latency_ms"))} ms · 输入 token ${s(get(or(get(record, "usage"), new Map()), "input_tokens"))}`);
  return [lines, attention];
}

/** write_summary：按 attempt 目录里的证据文件写 summary.md（覆盖）。 */
export function writeSummary(runDir: string, repo: Repo, context: SummaryContext): void {
  const read = (name: string): PyValue => readJsonOr(path.join(runDir, name), new Map());
  const meta = read("meta.json");
  const state = getState(runDir);
  const run = read("run.json");
  const events = read("events-summary.json");
  const report = read("report-status.json");
  const candidate = read("candidate.json");
  const scope = read("scope.json");
  const extra = read("observations.json");
  const executor = attemptExecutor(runDir, new Map());
  const usage = get(events, "usage", new Map());
  const cost = get(events, "cost", new Map());
  const lines = [
    `# Attempt 摘要：${s(get(meta, "task_id"))} v${s(get(meta, "plan_version"))} · ${s(get(meta, "attempt_id"))}`,
    "",
    `- 状态：**${state}**`,
    `- 基线：${code(s(get(meta, "base_sha")))}`,
    // 换一台机器复审时，据此知道 attempt 从哪里来（2.4.0）
    `- 派遣环境：${s(get(meta, "platform"))} · Python ${s(get(meta, "python"))} · 仓库 ${code(s(get(meta, "repository")))}`,
    `- 候选树：${code(s(get(candidate, "tree")))}（补丁往返校验：${yesNo(get(candidate, "patch_roundtrip_verified"))}）`,
    `- 要求的执行模型：${s(get(executor, "provider"))}/${s(get(executor, "model"))} · thinking=${s(get(executor, "thinking"))} · 工具=${pyJoin(",", get(executor, "tools", []))}`,
    `- 执行模型来源：${executorSourceText(runDir, meta)}`,
    `- 实际模型：${pyIter(get(events, "actual_models", [])).map((model) => `${s(get(model, "provider"))}/${s(get(model, "model"))}`).join(", ") || "无"}（一致：${yesNo(get(events, "model_match"))}）· 提供商回报的思考级别：${
      pyJoin(",", get(events, "provider_thinking_levels", [])) || "未回报（只能确认请求的级别；映射方式取决于协议）"
    }`,
    `- Pi 退出码：${s(get(run, "exit_code"))} · 用时 ${s(get(run, "wall_seconds"))}s / 上限 ${s(get(run, "timeout_seconds"))}s · 超时：${yesNo(get(run, "timed_out"))} · 取消：${yesNo(get(run, "interrupted"))} · 残留进程：${s(get(run, "stray_processes"))}`,
    `- 事件流：完整=${yesNo(get(events, "complete"))}（${s(get(events, "terminal_event"))}）· 行数 ${s(get(events, "lines"))} · 最终 stopReason=${s(get(events, "final_stop_reason"))} · 工具错误 ${s(get(events, "tool_errors"))} · 自动重试 ${pyLenValue(get(events, "auto_retries", []))} · 压缩 ${s(get(events, "compactions"))}`,
    `- 用量：input ${s(get(usage, "input"))} / output ${s(get(usage, "output"))} / cacheRead ${s(get(usage, "cacheRead"))} / cacheWrite ${s(get(usage, "cacheWrite"))} · 费用 ${get(cost, "total") === null ? "未知" : s(get(cost, "total"))}（${s(get(cost, "status"))}）`,
    `- 执行报告：${s(get(report, "status"))}（执行器自述状态：${s(get(report, "executor_status"))}）`,
    `- 变更：${items(get(scope, "counts", new Map())).map(([key, value]) => s(key) + s(value)).join(" ")} · 越界 ${pyLenValue(get(scope, "violations", []))} · 警告 ${pyLenValue(get(scope, "warnings", []))}`,
    "",
  ];
  if (pyTruthy(get(events, "problems"))) {
    lines.push("## 执行完整性问题", "", ...pyIter(pyItem(events, "problems")).map((problem) => `- ${s(problem)}`), "");
  }
  if (pyTruthy(get(scope, "files"))) {
    lines.push("## 变更文件", "", "| 状态 | 路径 | 范围 |", "|---|---|---|");
    lines.push(...pyIter(pyItem(scope, "files")).map((file) => `| ${s(pyItem(file, "status"))} | ${code(s(pyItem(file, "path")))} | ${s(pyItem(file, "scope"))} |`));
    lines.push("");
  }
  if (pyTruthy(get(scope, "violations")) || pyTruthy(get(scope, "warnings"))) {
    lines.push("## 越界与警告", "");
    const entry = (word: string) => (item: PyValue): string =>
      `- ${word} ${code(s(pyItem(item, "path")))}：${s(pyItem(item, "kind"))}（${s(pyItem(item, "detail"))}）`;
    lines.push(...pyIter(get(scope, "violations", [])).map(entry("越界")));
    lines.push(...pyIter(get(scope, "warnings", [])).map(entry("警告")));
    lines.push("");
  }
  const attention: string[] = [];
  for (const item of pyIter(get(events, "suspicious_commands", []))) {
    if (pyTruthy(get(item, "match"))) {
      attention.push(
        `可疑命令（${s(pyItem(item, "label"))}）：命令第 ${s(pyItem(item, "match_line"))} / ${s(pyItem(item, "command_lines"))} 行 ${code(tick(pyItem(item, "match")))}（事件流第 ${s(pyItem(item, "event_line"))} 行）`,
      );
    } else {
      attention.push(`可疑命令（${s(pyItem(item, "label"))}）：${code(tick(pyItem(item, "command")))}`);
    }
  }
  const tempUses = get(events, "temp_path_uses", []);
  if (pyTruthy(tempUses)) {
    const shownCount = pyLenValue(tempUses); // dict.get 的缺省值先求值
    const totalTempUses = get(events, "temp_path_use_count", BigInt(shownCount));
    attention.push(
      `系统临时路径线索（${pyPercentD(totalTempUses)} 个命中片段）：逐项按 AGENTS.md 核对写法、用途和工具结果。` +
        "这些是事后扫描线索，不是命令阻断或违规裁定；清理输出或路径当前不存在，不能证明此前未覆盖既有内容",
    );
    for (const item of pyIter(tempUses)) {
      attention.push(`临时路径：事件流第 ${s(pyItem(item, "event_line"))} 行，命令第 ${s(pyItem(item, "match_line"))} 行 ${code(tick(pyItem(item, "match")))}`);
    }
    if (greater(totalTempUses, shownCount)) {
      attention.push(
        `临时路径摘录已截断：另有 ${pyPercentD(minus(totalTempUses, shownCount))} 个命中片段未展示，须继续核对 events.jsonl 原始命令；` +
          `events-summary.json 仅保留前 ${shownCount} 条摘录`,
      );
    }
  }
  const notes: string[] = [];
  const caches = get(events, "cache_dir_cleanups", []);
  if (pyTruthy(caches)) {
    notes.push(
      `执行器删除了工作副本内的缓存目录（__pycache__ 等，${pyLenValue(caches)} 处，例如事件流第 ${s(pyItem(first(caches), "event_line"))} 行 ${code(tick(pyItem(first(caches), "command")))}），` +
        "不列为可疑命令",
    );
  }
  for (const item of pyIter(get(events, "outside_worktree_paths", []))) {
    const detail: PyValue[] = [pyItem(item, "tool")];
    if (pyTruthy(get(item, "main_repo"))) detail.push("位于主仓库，G2 不通过");
    const failed = get(item, "failed");
    if (failed === true) detail.push("调用失败");
    else if (failed === false) detail.push("调用成功");
    if (get(item, "exists") === false) detail.push("路径不存在，可能是手写绝对路径时拼错");
    if (pyTruthy(get(item, "event_line"))) detail.push(`事件流第 ${s(pyItem(item, "event_line"))} 行`);
    if (greater(or(get(item, "occurrences"), 0n), 1)) detail.push(`共 ${pyPercentD(pyItem(item, "occurrences"))} 条命令`);
    attention.push(`工作副本外路径（${pyJoinStrings("，", detail)}）：${code(tick(pyItem(item, "path")))}`);
  }
  const ownReads = sortedUnique(pyIter(get(events, "own_run_paths", [])).map((item) => pyItem(item, "path")));
  if (ownReads.length) notes.push(`执行器访问了本 attempt 运行目录中的文件（合同与执行说明）：${listed(ownReads.slice(0, 5))}`);
  for (const ignored of pyIter(get(extra, "new_ignored_paths", []))) attention.push(`新增被 Git 忽略的路径：${code(s(ignored))}`);
  for (const skipped of pyIter(get(extra, "unindexable_skipped", []))) {
    attention.push(`候选没有收这个文件：${code(s(skipped))}（Windows 的保留设备名，git 打不开；多半是命令把输出写到了 nul、con 这类名字）`);
  }
  const changes = or(get(extra, "main_repo_changes"), new Map());
  if (pyTruthy(get(changes, "head_changed"))) {
    attention.push(
      `运行期间主工作区 HEAD 由 ${code(s(prefix(or(get(changes, "head_before"), "?"), 12)))} 变为 ${code(s(prefix(or(get(changes, "head_after"), "?"), 12)))}：` +
        "可能是规划器在批次运行期间集成了其他候选，也可能是越界提交",
    );
  }
  if (pyTruthy(get(changes, "other_paths"))) {
    attention.push(`运行期间主工作区以下文件发生变化（不在规划路径内，需确认不是执行器写入）：${listed(pyIter(prefix(pyItem(changes, "other_paths"), 10)))}`);
  }
  if (pyTruthy(get(changes, "planner_paths"))) {
    notes.push(`运行期间规划路径有变化（通常是规划器自己编辑合同或复审记录）：${listed(pyIter(prefix(pyItem(changes, "planner_paths"), 10)))}`);
  }
  if (pyTruthy(get(extra, "main_repo_changed")) && (pyTruthy(get(changes, "diff_error")) || !pyTruthy(changes))) {
    attention.push(`运行期间主工作区的 HEAD 或状态发生变化（可能是并发编辑，也可能是越界写入）；${s(or(get(changes, "diff_error"), "未能列出变化的路径"))}`);
  }
  const hints = get(extra, "review_hints", new Map());
  for (const marker of pyIter(get(hints, "skip_markers_added", []))) attention.push(`新增跳过/聚焦标记：${code(tick(marker))}`);
  if (pyTruthy(get(hints, "assertion_lines_removed"))) {
    attention.push(`删除了 ${s(pyItem(hints, "assertion_lines_removed"))} 行含断言的代码（新增 ${s(get(hints, "assertion_lines_added"))} 行）`);
  }
  for (const flag of pyIter(get(events, "stderr_flags", []))) attention.push(`stderr 标记：${s(flag)}`);
  const conflicts = or(get(report, "contract_conflicts"), 0n);
  // 2.10.0：执行器列出的自定解读（interpretations）也算报告过的取舍
  const declared = pyPlus(pyPlus(conflicts, or(get(report, "unresolved_questions"), 0n)), or(get(report, "interpretations"), 0n));
  if (pyTruthy(conflicts)) {
    attention.push(`执行器报告了 ${pyPercentD(conflicts)} 处合同矛盾或含义不明（executor-report.json 的 contract_conflicts）：逐条裁定后再下结论；相关实现是执行器的临时选择`);
  }
  const masked = or(get(events, "masked_exit_commands"), []);
  const maskedChecks = pyIter(masked).filter((item) => pyTruthy(get(item, "check")));
  if (maskedChecks.length) {
    // 2.6.1：测试或检查命令的退出码被管道掩盖，报告里的 reported_exit_code 是推断值，复审要关注；验收证据仍是调度器在固定候选上的 check
    const example = maskedChecks[0] as PyValue;
    attention.push(
      `测试或检查命令的退出码被管道掩盖（${maskedChecks.length} 条，例如事件流第 ${s(pyItem(example, "event_line"))} 行 ${code(tick(pyItem(example, "match")))}；另有 ${pyLenValue(masked) - maskedChecks.length} 条探索命令也如此）：` +
        "执行器没有看到被检查程序的退出码，报告里的 reported_exit_code 是推断值，以 check 的结果为准（2.10.0 起执行说明给了每条检查的自检照抄写法）",
    );
  } else if (pyTruthy(masked)) {
    notes.push(
      `掩盖退出码的写法（${pyLenValue(masked)} 条命令，例如事件流第 ${s(pyItem(first(masked), "event_line"))} 行 ${code(tick(pyItem(first(masked), "match")))}）：管道之后的退出码是最后一个命令的，` +
        `${code("|| true")} 直接抹掉；都不是测试或检查命令`,
    );
  }
  const leaks = or(get(events, "temp_dirs_without_cleanup"), []);
  if (pyTruthy(leaks)) {
    notes.push(`创建了临时目录、同一条命令里没有清理（${pyLenValue(leaks)} 条，例如事件流第 ${s(pyItem(first(leaks), "event_line"))} 行 ${code(tick(pyItem(first(leaks), "match")))}）：核对它之后是否被删除`);
  }
  const excerpt = (mention: PyValue): string => codePoints(tick(s(get(mention, "excerpt", "")))).slice(0, 160).join("");
  const interpretationCount = or(get(events, "interpretation_mention_count"), 0n);
  if (pyTruthy(interpretationCount)) {
    const mention = first(or(get(events, "interpretation_mentions"), [new Map()]));
    const text = `执行器自行宣布了 ${pyPercentD(interpretationCount)} 处解读（例如事件流第 ${s(get(mention, "line"))} 行：“${excerpt(mention)}”）`;
    if (pyTruthy(declared)) notes.push(`${text}；核对它们都在报告的 interpretations / contract_conflicts / unresolved_questions 里`);
    else attention.push(`${text}；报告的 interpretations、contract_conflicts 与 unresolved_questions 都为空：这些解读没有被报告（全部摘录见 events-summary.json 的 interpretation_mentions）`);
  }
  if (pyTruthy(get(report, "interpretations_missing"))) notes.push("执行报告没有 interpretations 列表（2.10.0 起报告格式里有）：执行器自定的解读只能从事件流核对");
  const mentionCount = or(get(events, "ambiguity_mention_count"), 0n);
  if (pyTruthy(mentionCount)) {
    const mention = first(or(get(events, "ambiguity_mentions"), [new Map()]));
    const text = `执行过程中有 ${pyPercentD(mentionCount)} 处提到合同的歧义、矛盾或一致性，可能只是在检查，需要核实（例如事件流第 ${s(get(mention, "line"))} 行：“${excerpt(mention)}”）`;
    if (pyTruthy(declared)) notes.push(`${text}；报告列出了 interpretations / contract_conflicts / unresolved_questions，核对两者是否一致`);
    else attention.push(`${text}；报告的 interpretations、contract_conflicts 与 unresolved_questions 都为空：核对执行器是否自行选定了某种解释（全部摘录见 events-summary.json 的 ambiguity_mentions）`);
  }
  const [decisionLines, decisionAttention] = decisionsSummary(runDir, context);
  attention.push(...decisionAttention);
  if (attention.length) lines.push("## 复审需要关注", "", ...attention.map((line) => `- ${line}`), "");
  if (notes.length) lines.push("## 备注", "", ...notes.map((line) => `- ${line}`), "");
  if (decisionLines.length) lines.push("## 决策", "", ...decisionLines, "");
  const rel = displayPath(runDir, repo.root);
  lines.push(
    "## 下一步",
    "",
    "```bash",
    `bash scripts/dispatch-pi.sh check ${rel}`,
    "```",
    "",
    "证据文件：events.jsonl、stderr.log、run.json、events-summary.json、candidate.patch、scope.json、executor-report.md。",
    "进程退出码为 0 不代表任务通过；结论以独立检查与复审为准。",
    "",
  );
  writeText(path.join(runDir, "summary.md"), lines.join(NL), false);
}
