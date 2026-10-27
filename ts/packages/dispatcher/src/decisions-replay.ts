// pi_dispatch.cmd_decisions（迁移第 ④b4b 片）：decisions replay，把 shadow / on 的记录与后来的事实并排——report-screen 对
// verdict，mutation-equivalence 按变异列出，run-health 按 tick 统计。只读决策记录，不调用决策模型。
import { readdirSync, statSync, writeFileSync } from "node:fs";
import { utcNow } from "@themis/base/clock";
import { type PyOut, pyFixed, pyFloatOf, pyGet, pyRound, pyStrValue, pySum, pyTruthy } from "@themis/base/pyfmt";
import { type PyDict, type PyValue, dumps, encodeUtf8 } from "@themis/base/pyjson";
import { displayPath } from "@themis/base/pypath";
import { cmpCodePoints } from "@themis/base/pyre";
import { latestByPoint, usageTotals } from "./decision-records.ts";
import { PASSING_VERDICTS } from "./evidence.ts";
import { safeOutputPath } from "./metrics.ts";
import { DispatchError, EXIT_OK, EXIT_USAGE, Repo } from "./repo.ts";
import { decisionsRecordsOf } from "./run-health.ts";
import { latestVerdict, taskAttempts } from "./status.ts";

export interface DecisionsArgs {
  readonly repo: string | null;
  readonly decisions_cmd: string | null;
  readonly task_id?: string | null;
  readonly json?: boolean;
  readonly out?: string | null;
}

const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);
const QUESTIONS = ["claims_unsupported", "chose_interpretation", "scope_creep", "weakened_tests", "severity"];
const dict = (entries: readonly (readonly [string, PyValue])[]): PyDict => new Map(entries);
const get = (value: PyValue | undefined, key: string, fallback: PyValue = null): PyValue => pyGet(value ?? null, key, fallback);
/** x or {}：假值换成空字典。 */
const orEmpty = (value: PyValue | undefined): PyValue => (pyTruthy(value ?? null) ? (value as PyValue) : new Map());

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

/** round(float(x), 2)。 */
const round2 = (value: PyValue): PyValue => pyRound(pyFloatOf(value), 2);

/** decisions replay：输出 Markdown 表（或 --json），写到 --out 时只能在 .agent/runs/_env/ 或 _reports/ 下。 */
export function cmdDecisions(args: DecisionsArgs, out: PyOut): number {
  if (args.decisions_cmd !== "replay") throw new DispatchError("decisions 需要子命令 replay", EXIT_USAGE);
  const outPath = safeOutputPath(args.out ?? null, args.repo);
  const repo = Repo.discover(args.repo);
  const tasks = args.task_id
    ? [args.task_id]
    : isDir(repo.runsDir)
      ? readdirSync(repo.runsDir).filter((name) => isDir(`${repo.runsDir}/${name}`)).sort(cmpCodePoints)
      : [];
  const screenRows: PyDict[] = [];
  const mutationRows: PyDict[] = [];
  const healthRows: PyDict[] = [];
  const allRecords: PyDict[] = [];
  for (const task of tasks) {
    for (const attempt of taskAttempts(repo, task)) {
      const records = decisionsRecordsOf(attempt);
      if (!records.length) continue;
      allRecords.push(...records);
      const name = displayPath(attempt, repo.runsDir);
      const verdict = get(latestVerdict(attempt), "verdict");
      const screen = latestByPoint(records).get("report-screen");
      if (screen && screen.get("status") === "answered") {
        const row = dict([["attempt", name], ["verdict", verdict], ["mode", screen.get("mode") ?? null]]);
        for (const [question, answer] of screen.get("answers") as PyDict) {
          const kind = get(answer, "type");
          row.set(question, kind === "noul" ? round2(get(answer, "noul")) : kind === "score" ? round2(get(answer, "score")) : get(answer, "choice"));
        }
        screenRows.push(row);
      }
      for (const record of records) {
        if (record.get("point") === "mutation-equivalence" && record.get("status") === "answered") {
          const context = orEmpty(record.get("context"));
          const answers = record.get("answers") as PyDict;
          mutationRows.push(dict([
            ["attempt", name], ["mutation", get(context, "mutation")], ["name", get(context, "name")],
            ["equivalent", round2(get(answers.get("equivalent") as PyValue, "noul"))], ["untested", round2(get(answers.get("untested") as PyValue, "noul"))],
          ]));
        }
      }
      const ticks = records.filter((record) => record.get("point") === "run-health");
      if (ticks.length) {
        const actions = new Map<string, PyValue>();
        for (const record of ticks) {
          const choice = record.get("status") === "answered" ? get(get(orEmpty(record.get("answers")), "action", new Map()), "choice") : "无意见";
          const key = pyStrValue(choice);
          actions.set(key, ((actions.get(key) as bigint | undefined) ?? 0n) + 1n);
        }
        healthRows.push(dict([["attempt", name], ["ticks", BigInt(ticks.length)], ["actions", actions]]));
      }
    }
  }
  const totals = usageTotals(allRecords);
  const text = args.json ? jsonText(totals, screenRows, mutationRows, healthRows) : markdownText(totals, screenRows, mutationRows, healthRows);
  if (outPath !== null) {
    // write_text 是文本模式：Windows 上换行写成 CRLF
    writeFileSync(outPath, encodeUtf8(process.platform === "win32" ? text.split(LF).join(CR + LF) : text));
    out.print(`已写入 ${outPath}`);
  } else {
    out.print(text);
  }
  return EXIT_OK;
}

function jsonText(totals: PyDict, screen: PyDict[], mutations: PyDict[], health: PyDict[]): string {
  const payload = dict([["generated_at", utcNow()], ["totals", totals], ["report_screen", screen], ["mutation_equivalence", mutations], ["run_health", health]]);
  return `${dumps(payload, { ensureAscii: false, indent: 2 })}${LF}`;
}

const sortedCounts = (counts: PyDict): string =>
  ([...counts] as [string, PyValue][]).sort(([left], [right]) => cmpCodePoints(left, right)).map(([key, value]) => `${key} ${pyStrValue(value)}`).join("，");

function markdownText(totals: PyDict, screen: PyDict[], mutations: PyDict[], health: PyDict[]): string {
  const lines = [
    "# 决策回放", "",
    `生成时间：${utcNow()} · 记录 ${pyStrValue(totals.get("calls") as PyValue)} 条，有答案 ${pyStrValue(totals.get("answered") as PyValue)} · ` +
      `输入 token ${pyStrValue(totals.get("input_tokens") as PyValue)} · 估算费用 ${pyFixed(totals.get("estimated_cost_usd") as number, 4)} 美元`,
    "",
  ];
  const reasons = totals.get("no_opinion_reasons") as PyDict;
  if (reasons.size) lines.push(`无意见的原因：${sortedCounts(reasons)}`, "");
  lines.push("## report-screen（对照 verdict）", "");
  if (screen.length) {
    lines.push(`| attempt | verdict | 模式 | ${QUESTIONS.join(" | ")} |`, `|---|---|---|${"---|".repeat(QUESTIONS.length)}`);
    for (const row of screen) {
      const verdict = row.get("verdict") ?? null;
      lines.push(`| ${pyStrValue(row.get("attempt") as PyValue)} | ${pyTruthy(verdict) ? pyStrValue(verdict) : "-"} | ${pyStrValue(row.get("mode") ?? null)} | ` +
        `${QUESTIONS.map((question) => pyStrValue(row.has(question) ? (row.get(question) as PyValue) : "-")).join(" | ")} |`);
    }
    const passing = screen.filter((row) => PASSING_VERDICTS.includes(row.get("verdict") as string));
    const failing = screen.filter((row) => pyTruthy(row.get("verdict") ?? null) && !PASSING_VERDICTS.includes(row.get("verdict") as string));
    // sum(float(r.get(q, 0) or 0) for r in rows) / len(rows)：补偿求和（themistally-15 复核 b29ab6c）
    const mean = (rows: PyDict[], question: string): string =>
      rows.length ? pyFixed((pySum(rows.map((row) => pyFloatOf(orZero(row.has(question) ? (row.get(question) as PyValue) : 0n)))) as number) / rows.length, 2) : "-";
    lines.push("", `| 问题 | 通过类 attempt 均值（${passing.length}） | 未通过类均值（${failing.length}） |`, "|---|---|---|");
    for (const question of QUESTIONS) lines.push(`| ${question} | ${mean(passing, question)} | ${mean(failing, question)} |`);
    lines.push("", "通过类与未通过类的均值分不开的问题，在这个仓库上还不能开 on；分得开的，阈值放在两者之间。");
  } else {
    lines.push("没有有答案的 report-screen 记录。");
  }
  lines.push("", "## mutation-equivalence（对照复审记录里的人工判定）", "");
  if (mutations.length) {
    lines.push("| attempt | 变异 | 名称 | 等价 p | 缺口 p |", "|---|---|---|---|---|");
    for (const row of mutations) {
      lines.push(`| ${["attempt", "mutation", "name", "equivalent", "untested"].map((key) => pyStrValue(row.get(key) as PyValue)).join(" | ")} |`);
    }
  } else {
    lines.push("没有有答案的 mutation-equivalence 记录。");
  }
  lines.push("", "## run-health", "");
  if (health.length) {
    lines.push("| attempt | tick 数 | 建议分布 |", "|---|---|---|");
    for (const row of health) {
      lines.push(`| ${pyStrValue(row.get("attempt") as PyValue)} | ${pyStrValue(row.get("ticks") as PyValue)} | ${sortedCounts(row.get("actions") as PyDict)} |`);
    }
  } else {
    lines.push("没有 run-health 记录。");
  }
  return `${lines.join(LF)}${LF}`;
}

/** x or 0。 */
const orZero = (value: PyValue): PyValue => (pyTruthy(value) ? value : 0n);
