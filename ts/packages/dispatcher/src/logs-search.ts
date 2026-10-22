// kit_logs 的 logs search（迁移第 ②b2 步）：在证据的 .md/.txt/.log/.json/.jsonl 里逐行搜索脱敏之后的文本。
// PATTERN 照 Python re 的语法与语义（@themis/base/pyregex，sre 的移植），先过第 58 轮的三道检查；行号、截断、
// 计数与输出照 kit_logs.cmd_search。后缀按大小写区分（Python 的 str.endswith）。
import { jsonlRecords } from "@themis/base/jsonl";
import type { PyOut } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { codePoints } from "@themis/base/pyre";
import { type SearchPattern, SearchPatternError, compileSearch } from "@themis/base/pyregex";
import { jsonlEntry, redactedText, safeMode } from "./logs-cat.ts";
import {
  LinkTally,
  LogsError,
  LOGS_EXIT_OK,
  LOGS_EXIT_USAGE,
  attemptEntries,
  checkTask,
  emitJson,
  evidence,
  repoOf,
  skippedLinksLine,
  taskEntries,
  under,
} from "./logs.ts";

const MAX_LINE_CHARS = 200;
const SEARCH_SUFFIXES = [".md", ".txt", ".log", ".json", ".jsonl"] as const;

/** kit_logs.safe_lines：脱敏之后的（行号, 文本），隐藏的行不给。text、json 模式整份超过上限或读不出来时抛 LogsError。 */
export function* safeLines(file: string, name: string, rel: string): Generator<[number, string]> {
  const mode = safeMode(rel);
  if (mode === "jsonl") {
    let number = 0;
    for (const [, , raw] of jsonlRecords(file, 0, true)) {
      number += 1;
      if (raw === null) continue;
      const entry = jsonlEntry(raw);
      if ("text" in entry) yield [number, entry.text];
    }
    return;
  }
  const lines = redactedText(file, name, mode).split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index] as string;
    yield [index + 1, line.endsWith("\r") ? line.slice(0, -1) : line];
  }
}

/** kit_logs._compile_search：不合法的 PATTERN 报用法错误（退出码 2）。 */
function compilePattern(text: string): SearchPattern {
  try {
    return compileSearch(text);
  } catch (error) {
    if (error instanceof SearchPatternError) throw new LogsError(error.message, LOGS_EXIT_USAGE);
    throw error;
  }
}

export interface SearchArgs {
  readonly repo: string | null;
  readonly pattern: string;
  readonly task: string | null;
  readonly max: bigint;
  readonly json: boolean;
}

/** kit_logs.cmd_search。 */
export function cmdSearch(args: SearchArgs, out: PyOut): number {
  const repo = repoOf(args.repo);
  const pattern = compilePattern(args.pattern);
  if (args.max < 1n) throw new LogsError(`--max 必须是不小于 1 的整数：${args.max}`, LOGS_EXIT_USAGE);
  const task = checkTask(args.task);
  const links = new LinkTally();
  const matches: PyDict[] = [];
  let truncated = false;
  let skippedLarge = 0;
  search: for (const [name, taskDir] of taskEntries(repo.runsDir, links)) {
    if (task !== null && name !== task) continue;
    for (const [attempt, , attemptDir] of attemptEntries(taskDir, links)) {
      const files = evidence(attemptDir, links);
      if (files === null) continue; // attempt 目录列不出来：跳过该 attempt（B11(a)）
      for (const [rel] of files) {
        if (!SEARCH_SUFFIXES.some((suffix) => rel.endsWith(suffix))) continue;
        const parts = rel.split("/");
        try {
          for (const [number, text] of safeLines(under(attemptDir, parts), parts[parts.length - 1] as string, rel)) {
            if (!pattern.test(text)) continue;
            if (BigInt(matches.length) >= args.max) {
              truncated = true;
              break;
            }
            matches.push(new Map<string, PyValue>([
              ["task", name],
              ["attempt", attempt],
              ["path", rel],
              ["line", BigInt(number)],
              ["text", codePoints(text).slice(0, MAX_LINE_CHARS).join("")],
            ]));
          }
        } catch (error) {
          if (error instanceof LogsError) {
            skippedLarge += 1; // 太大或读不出来：不搜，计数
          } else if (typeof (error as NodeJS.ErrnoException).code !== "string") {
            throw error;
          } // 系统错误（Python 的 OSError）：读不出来的文件没有行
        }
        if (truncated) break search;
      }
    }
  }
  if (args.json) {
    emitJson(out, new Map<string, PyValue>([
      ["matches", matches],
      ["truncated", truncated],
      ["skipped_links", BigInt(links.count)],
      ["skipped_large", BigInt(skippedLarge)],
    ]));
    return LOGS_EXIT_OK;
  }
  for (const match of matches) {
    out.print(`${match.get("task") as string}/${match.get("attempt") as string}/${match.get("path") as string}:${
      String(match.get("line"))}: ${match.get("text") as string}`);
  }
  if (truncated) out.print(`（已截断：只显示前 ${args.max} 条匹配）`);
  if (links.count > 0) out.print(skippedLinksLine(links.count));
  if (skippedLarge > 0) out.print(`跳过的大文件或读不出来的文件：${skippedLarge}`);
  return LOGS_EXIT_OK;
}
