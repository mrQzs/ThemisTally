// pi_dispatch 的 metrics（迁移第 ④b2 片）：按任务汇总试运行指标，费用另按配置的单价估算，决策调用按记录统计。
// 数字照 Python 的动态类型算：int 与 bool 相加仍是 int、有 float 就是 float，round 对 int 仍是 int，"%.Nf" 恰在中点时
// 取偶，%s 打印 float 用 repr；证据里的值类型不对时 Python 抛异常、命令崩溃，这里照样抛。
import { readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyFixed, pyRound, pyStrValue, pySum, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyOSError, pyReadText } from "@themis/base/pyio";
import { type PyDict, type PyValue, PyJsonError, encodeUtf8, loads } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { isWithin, normCase, pyResolve } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyLower } from "@themis/base/pyre";
import { redactObj } from "@themis/base/secrets";
import { pyEq } from "@themis/base/pyvalue";
import { normalizeContract } from "./contract.ts";
import { executorClass } from "./executor.ts";
import { pricingTable, repoConfig } from "./kernel-config.ts";
import { DispatchError, EXIT_OK, EXIT_USAGE, Repo, readJsonOr } from "./repo.ts";
import { attemptRow, taskAttempts } from "./status.ts";

const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);
const BT = "`";
const DECISIONS_RECORD = "decisions.jsonl";
const PRICE_USD_PER_MILLION_INPUT = 0.042;
const USAGE_PRICE_FIELDS = [["input", "input"], ["output", "output"], ["cacheRead", "cache_read"], ["cacheWrite", "cache_write"]];
const FINAL_OUTCOMES: [string, string][] = [["integrated", "直接集成"], ["superseded", "补完后集成"], ["abandoned", "放弃"], ["pending", "未定"]];

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;

/** dict.get：不是字典时照 Python 抛 AttributeError。 */
function dictGet(value: PyValue, key: string, fallback: PyValue = null): PyValue {
  if (!isDict(value)) throw new PyCrash("AttributeError", `'${pyTypeName(value)}' object has no attribute 'get'`);
  return value.has(key) ? (value.get(key) as PyValue) : fallback;
}

const orZero = (value: PyValue): PyValue => (pyTruthy(value) ? value : 0n);

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

/** safe_output_path：--out 只能写到 .agent/runs/_env/ 或 .agent/runs/_reports/ 下，不能覆盖仓库文件或 attempt 证据。 */
export function safeOutputPath(out: string | null, repoArg: string | null): string | null {
  if (!out) return null;
  const repo = Repo.discover(repoArg);
  const target = pyResolve(path.resolve(process.cwd(), out));
  const allowed = [pyResolve(path.join(repo.runsDir, "_env")), pyResolve(path.join(repo.runsDir, "_reports"))];
  if (!allowed.some((root) => isWithin(target, root) && normCase(target) !== normCase(root))) {
    throw new DispatchError(`--out 只能指向 .agent/runs/_env/ 或 .agent/runs/_reports/ 下的文件：${target}`, EXIT_USAGE);
  }
  pathMkdir(path.dirname(target), true, true);
  return target;
}

/** _final_outcome：有 INTEGRATED 是直接集成；没有而有带 ref 的 SUPERSEDED 是补完后集成；最后一个是 ABANDONED 是放弃；其余未定。 */
function finalOutcome(attempts: readonly string[]): [string, PyValue] {
  const states = attempts.map((attempt) => readJsonOr(path.join(attempt, "state.json"), new Map()));
  const stateOf = (record: PyValue): PyValue => dictGet(record, "state");
  const integrated = states.filter((record) => pyEq(stateOf(record), "INTEGRATED"));
  if (integrated.length) return ["integrated", dictGet(integrated[integrated.length - 1] as PyValue, "ref")];
  const superseded = states.filter((record) => pyEq(stateOf(record), "SUPERSEDED") && pyTruthy(dictGet(record, "ref")));
  if (superseded.length) return ["superseded", dictGet(superseded[superseded.length - 1] as PyValue, "ref")];
  if (states.length && pyEq(stateOf(states[states.length - 1] as PyValue), "ABANDONED")) return ["abandoned", null];
  return ["pending", null];
}

/** frozen_executor_class：attempt 冻结合同（contract.json）的 executor 类别。 */
export function frozenExecutorClass(runDir: string): string {
  const raw = readJsonOr(path.join(runDir, "contract.json"), new Map());
  return executorClass(isDict(raw) ? (raw.get("executor") ?? null) : null);
}

/** attempt_executor：executor.json；没有时用 meta 里版本记录的副本补 provider、model、thinking，其余取自合同；再没有用后备值。 */
export function attemptExecutor(runDir: string, fallback: PyValue): PyValue {
  const executor = readJsonOr(path.join(runDir, "executor.json"), null);
  if (isDict(executor)) return redactObj(executor);
  const meta = readJsonOr(path.join(runDir, "meta.json"), new Map());
  const binding = isDict(meta) ? (meta.get("executor_binding") ?? null) : null;
  if (!isDict(binding) || frozenExecutorClass(runDir) !== "role") return redactObj(fallback);
  const raw = readJsonOr(path.join(runDir, "contract.json"), new Map());
  const contractExecutor = isDict(raw) ? (normalizeContract(raw).get("executor") ?? null) : null;
  const merged: PyDict = isDict(contractExecutor) ? new Map([...contractExecutor].filter(([key]) => key !== "role")) : new Map();
  for (const key of ["provider", "model", "thinking"]) merged.set(key, binding.get(key) ?? null);
  return redactObj(merged);
}

/** estimate_cost：按单价估算一轮的费用；某类 token 用到了却没有单价、或 usage 不完整时为 null。 */
export function estimateCost(usage: PyValue, price: PyDict): number | null {
  if (!isDict(usage)) return null;
  let total = 0;
  for (const [usageKey, priceKey] of USAGE_PRICE_FIELDS as [string, string][]) {
    const tokens = orZero(usage.get(usageKey) ?? null);
    if (typeof tokens !== "bigint" && typeof tokens !== "number") return null;
    if (!pyTruthy(tokens)) continue;
    const unit = price.get(priceKey) ?? null;
    if (unit === null) return null;
    total += (Number(tokens) * Number(unit)) / Number(price.get("per_tokens") as bigint);
  }
  return pyRound(total, 6) as number;
}

/** _priced_attempt：（币种, 按配置价格估算的费用）；这一轮的执行模型没有价格或 token 不全时费用为 null。 */
function pricedAttempt(runDir: string, pricing: PyDict): [string | null, number | null] {
  const executor = attemptExecutor(runDir, new Map());
  const price = pricing.get(`${pyStrValue(dictGet(executor, "provider"))}/${pyStrValue(dictGet(executor, "model"))}`) ?? null;
  if (!pyTruthy(price)) return [null, null];
  const summary = readJsonOr(path.join(runDir, "events-summary.json"), new Map());
  const usage = dictGet(pyTruthy(summary) ? summary : new Map(), "usage");
  return [(price as PyDict).get("currency") as string, estimateCost(usage, price as PyDict)];
}

/** codekit.decisions.read_records：只按换行切（字符串里的 U+2028 之类不算行界），坏行跳过；读不了为空。 */
export function readRecords(file: string): PyDict[] {
  let text: string;
  try {
    text = pyReadText(file);
  } catch (error) {
    if (error instanceof PyOSError) return [];
    throw error;
  }
  const records: PyDict[] = [];
  for (const line of text.split(LF)) {
    let item: PyValue;
    try {
      item = loads(line);
    } catch (error) {
      if (error instanceof PyJsonError && error.kind !== "RecursionError") continue;
      throw error;
    }
    if (isDict(item)) records.push(item);
  }
  return records;
}

/** decisions_records_of：attempt 目录的 decisions.jsonl 加每轮 mutations/NN/ 的。 */
function decisionsRecordsOf(runDir: string): PyDict[] {
  const records = readRecords(path.join(runDir, DECISIONS_RECORD));
  const mutations = path.join(runDir, "mutations");
  if (isDir(mutations)) {
    const key = (name: string): string => (process.platform === "win32" ? pyLower(name) : name);
    for (const name of readdirSync(mutations).sort((a, b) => cmpCodePoints(key(a), key(b)))) {
      if (isDir(path.join(mutations, name))) records.push(...readRecords(path.join(mutations, name, DECISIONS_RECORD)));
    }
  }
  return records;
}

/** codekit.decisions.usage_totals 里 metrics 用到的几项。 */
function usageTotals(records: readonly PyDict[]): { calls: number; answered: number; inputTokens: bigint; costUsd: number } {
  const answered = records.filter((record) => pyEq(record.get("status") ?? null, "answered")).length;
  let tokens = 0n;
  for (const record of records) {
    const usage = record.get("usage") ?? null;
    const value = dictGet(pyTruthy(usage) ? usage : new Map(), "input_tokens");
    if (typeof value === "bigint") tokens += value;
    else if (typeof value === "boolean") tokens += value ? 1n : 0n;
  }
  return { calls: records.length, answered, inputTokens: tokens, costUsd: pyRound((Number(tokens) * PRICE_USD_PER_MILLION_INPUT) / 1_000_000, 8) as number };
}

interface TaskMetrics {
  final: string;
  finalRef: PyValue;
  pricedCost: Map<string, number>;
  unpricedAttempts: number;
  taskId: string;
  attempts: number;
  firstAttemptPass: boolean;
  passed: boolean;
  acceptedWithException: boolean;
  violationAny: boolean;
  wallSeconds: bigint | number;
  tokens: bigint | number;
  knownCost: bigint | number | null;
  unknownCostAttempts: number;
  humanMinutes: bigint | number;
  failureClasses: string[];
}

/** (x or 0) > 0：不是数字时 Python 抛 TypeError。 */
function positive(value: PyValue): boolean {
  const number = orZero(value);
  if (typeof number === "bigint") return number > 0n;
  if (typeof number === "number" || typeof number === "boolean") return Number(number) > 0;
  throw new PyCrash("TypeError", `'>' not supported between instances of '${pyTypeName(number)}' and 'int'`);
}

/** sorted({...})：失败分类最后要 ", ".join，不是字符串的 Python 会在排序或拼接时抛 TypeError。 */
function failureClasses(rows: readonly PyDict[]): string[] {
  const values = rows.map((row) => row.get("failure_class") ?? null).filter((value) => pyTruthy(value));
  if (values.some((value) => typeof value !== "string")) throw new PyCrash("TypeError", "sequence item 0: expected str instance");
  return [...new Set(values as string[])].sort(cmpCodePoints);
}

function taskMetrics(repo: Repo, task: string, pricing: PyDict): TaskMetrics | null {
  const attempts = taskAttempts(repo, task);
  const rows = attempts.map((attempt) => attemptRow(repo, attempt));
  const started = rows.filter((row) => pyTruthy(row.get("started") ?? null));
  if (!started.length) return null;
  const verdicts = started.map((row) => row.get("verdict") ?? null);
  const knownCosts = started.map((row) => row.get("cost") ?? null).filter((cost) => cost !== null);
  const [final, finalRef] = finalOutcome(attempts);
  const pricedCost = new Map<string, number>();
  let unpricedAttempts = 0;
  attempts.forEach((attempt, index) => {
    if (!pyTruthy(rows[index]?.get("started") ?? null)) return;
    const [currency, value] = pricedAttempt(attempt, pricing);
    if (value === null) unpricedAttempts += 1;
    else pricedCost.set(currency as string, pyRound((pricedCost.get(currency as string) ?? 0) + value, 6) as number);
  });
  const passed = verdicts.some((verdict) => pyEq(verdict, "PASS"));
  const field = (key: string): PyValue[] => started.map((row) => orZero(row.get(key) ?? null));
  return {
    final, finalRef, pricedCost, unpricedAttempts, taskId: task, attempts: started.length,
    firstAttemptPass: pyEq(verdicts[0] as PyValue, "PASS"),
    passed,
    acceptedWithException: !passed && verdicts.some((verdict) => pyEq(verdict, "ACCEPTED_WITH_EXCEPTION")),
    violationAny: started.some((row) => positive(row.get("violations") ?? null)),
    wallSeconds: pyRound(pySum(field("wall_seconds")), 1),
    tokens: pySum(field("tokens")),
    knownCost: knownCosts.length ? pyRound(pySum(knownCosts), 6) : null,
    unknownCostAttempts: started.filter((row) => (row.get("cost") ?? null) === null || !pyEq(row.get("cost_status") ?? null, "estimated")).length,
    humanMinutes: pySum(field("human_minutes")),
    failureClasses: failureClasses(started),
  };
}

export interface MetricsArgs {
  readonly repo: string | null;
  readonly out: string | null;
}

const sortedByKey = <T>(entries: Iterable<[string, T]>): [string, T][] => [...entries].sort(([a], [b]) => cmpCodePoints(a, b));
const fixed4 = (value: PyValue): string => pyFixed(value as bigint | number, 4);

export function cmdMetrics(args: MetricsArgs, out: PyOut): number {
  const outPath = safeOutputPath(args.out, args.repo);
  const repo = Repo.discover(args.repo);
  const pricing = pricingTable(repoConfig(repo));
  const tasks = isDir(repo.runsDir) ? readdirSync(repo.runsDir).filter((name) => isDir(path.join(repo.runsDir, name))).sort(cmpCodePoints) : [];
  const perTask = tasks.map((task) => taskMetrics(repo, task, pricing)).filter((item): item is TaskMetrics => item !== null);
  const decisionRecords = tasks.flatMap((task) => taskAttempts(repo, task).flatMap(decisionsRecordsOf));
  const decisionTotals = decisionRecords.length ? usageTotals(decisionRecords) : null;
  const total = perTask.length;
  const count = (test: (task: TaskMetrics) => boolean): number => perTask.filter(test).length;
  const rate = (n: number): string => (total ? `${pyFixed((100 * n) / total, 0)}%` : "-");
  const knownTotal = pySum(perTask.map((task) => (task.knownCost !== null && pyTruthy(task.knownCost) ? task.knownCost : 0n)));
  const unknownAttempts = perTask.reduce((sum, task) => sum + task.unknownCostAttempts, 0);
  const finals = new Map(FINAL_OUTCOMES.map(([key]) => [key, count((task) => task.final === key)]));
  const pricedTotal = new Map<string, number>();
  for (const task of perTask) {
    for (const [currency, value] of task.pricedCost) pricedTotal.set(currency, pyRound((pricedTotal.get(currency) ?? 0) + value, 6) as number);
  }
  const unpricedTotal = perTask.reduce((sum, task) => sum + task.unpricedAttempts, 0);
  let pricedText: string;
  if (pricing.size) {
    const totals = sortedByKey(pricedTotal).map(([currency, value]) => `${fixed4(value)} ${currency}`).join(" + ") || "0";
    const sources = sortedByKey([...pricing].map(([key, value]): [string, PyValue] => [String(key), value])).map(([key, price]) => `${key} ${pyStrValue((price as PyDict).get("source") as PyValue)}（${pyStrValue((price as PyDict).get("as_of") as PyValue)}）`);
    pricedText = `${totals}${unpricedTotal ? `（另有 ${unpricedTotal} 轮没有价格或 token 不全）` : ""}；单价来源：${sources.join("；")}`;
  } else {
    pricedText = "没有配置价格（单价由用户填：config set pricing.<provider>/<model> …）";
  }
  const decisionsText = decisionTotals
    ? `${decisionTotals.calls} 次，有答案 ${decisionTotals.answered} · 输入 token ${decisionTotals.inputTokens} · 估算费用 ${fixed4(decisionTotals.costUsd)} 美元`
    : "无记录";
  const lines = [
    "# Pi 执行试运行指标", "", `生成时间：${utcNow()} · 任务数：${total}`, "",
    "PASS 与 ACCEPTED_WITH_EXCEPTION 分开统计：通过率只计 PASS。", "",
    "| 指标 | 数值 |", "|---|---|",
    `| 首次验收通过率（PASS） | ${rate(count((task) => task.firstAttemptPass))} |`,
    `| 有限重试内通过率（PASS） | ${rate(count((task) => task.passed))} |`,
    `| 豁免接受（ACCEPTED_WITH_EXCEPTION）任务 | ${count((task) => task.acceptedWithException)} |`,
    `| 验收未通过任务（最终去向见下两行） | ${count((task) => !task.passed && !task.acceptedWithException)} |`,
    `| 最终集成率（直接集成 + 补完后集成，2.8.0） | ${rate((finals.get("integrated") ?? 0) + (finals.get("superseded") ?? 0))} |`,
    `| 最终去向 | ${FINAL_OUTCOMES.map(([key, label]) => `${label} ${finals.get(key) ?? 0}`).join(" · ")} |`,
    `| 越界率 | ${rate(count((task) => task.violationAny))} |`,
    `| 执行轮次合计 | ${perTask.reduce((sum, task) => sum + task.attempts, 0)} |`,
    `| 已知执行费用（估算，仅 Pi 执行端） | ${fixed4(knownTotal)}${unknownAttempts ? `（另有 ${unknownAttempts} 轮费用未知或不完整，实际更高）` : ""} |`,
    `| 执行费用（按配置价格估算，2.8.0） | ${pricedText} |`,
    `| 人工介入分钟 | ${pyStrValue(pySum(perTask.map((task) => task.humanMinutes)))} |`,
    `| 决策调用（Jev，2.6.0） | ${decisionsText} |`, "",
    "规划与复审（规划端）费用不在此表，请按同一口径另行记录后再比较（方案第 13 节）。", "",
    "| 任务 | 轮次 | 首轮 PASS | 验收结论 | 最终 | 越界 | 墙钟(s) | tokens | 已知费用 | 价格估算 | 失败分类 |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
  ];
  const labels = new Map(FINAL_OUTCOMES);
  for (const task of perTask) lines.push(taskLine(task, labels));
  const text = `${lines.join(LF)}${LF}`;
  if (outPath !== null) {
    // write_text 是文本模式：Windows 上换行写成 CRLF
    writeFileSync(outPath, encodeUtf8(process.platform === "win32" ? text.split(LF).join(CR + LF) : text));
    out.print(`已写入 ${outPath}`);
  } else {
    out.print(text);
  }
  return EXIT_OK;
}

function taskLine(task: TaskMetrics, labels: Map<string, string>): string {
  const outcome = task.passed ? "PASS" : task.acceptedWithException ? "豁免接受" : "未通过";
  const costText = task.knownCost === null ? "unknown" : `${pyStrValue(task.knownCost)}${task.unknownCostAttempts ? "（不完整）" : ""}`;
  const finalText = `${labels.get(task.final) as string}${pyTruthy(task.finalRef) ? ` ${BT}${codePoints(pyStrValue(task.finalRef)).slice(0, 12).join("")}${BT}` : ""}`;
  const pricedCell = task.pricedCost.size
    ? `${sortedByKey(task.pricedCost).map(([currency, value]) => `${fixed4(value)} ${currency}`).join(" + ")}${task.unpricedAttempts ? `（${task.unpricedAttempts} 轮无价）` : ""}`
    : "-";
  const cells = [
    task.taskId, String(task.attempts), task.firstAttemptPass ? "是" : "否", outcome, finalText, task.violationAny ? "是" : "否",
    pyStrValue(task.wallSeconds), pyStrValue(task.tokens), costText, pricedCell, task.failureClasses.join(", ") || "-",
  ];
  return `| ${cells.join(" | ")} |`;
}
