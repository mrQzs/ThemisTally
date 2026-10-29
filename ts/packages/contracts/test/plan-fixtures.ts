// 合同对的模板（迁移第 ④b1 片的两份契约共用）：一份能通过 validate 的最小合同，Markdown 与 JSON 一致；用例在它上面改。
const LF = String.fromCharCode(10);
const BT = "`";

export interface MdOptions {
  readonly executor?: string;
  readonly facts?: readonly string[];
  readonly modified?: string;
  readonly newFiles?: string;
  readonly cwd?: string;
  readonly goal?: string;
  readonly family?: string;
  /** integration_actions（缺省 none），JSON 的 authorization.integration 要另外改成一样的。 */
  readonly integration?: string;
}

export function mdOf(task: string, base: string, o: MdOptions = {}): string {
  return [
    `# TASK: ${task}`, "",
    "## Identity", "- plan_version: 1", `- base_sha: ${base}`, "- risk_level: low", "- authorized_actions: local_edit, local_test",
    `- integration_actions: ${o.integration ?? "none"}`, `- executor: ${o.executor ?? "step/step-5-preview · thinking high"}`,
    ...(o.family ? [`- contract_family: ${o.family}`] : []), "",
    "## Goal", o.goal ?? "改一个文件。", "",
    "## Non-goals", "无", "",
    "## Repository facts", ...(o.facts ?? [`- ${BT}src/a.ts${BT} 已有`]), "",
    "## Scope", `- allowed_modified_files: ${o.modified ?? "src/a.ts"}`, `- allowed_new_files: ${o.newFiles ?? "无"}`,
    "- allowed_deleted_files: 无", "- forbidden_paths: 无", "- dependency_changes: forbidden", "",
    "## Behavior contract", "照旧。", "",
    "## Steps", "1. 改。", "",
    "## Validation commands", `- V01（必要，基线应失败）：${BT}python -m pytest tests -q${BT} · cwd：${o.cwd ?? "仓库根"} · 超时：300s`, "",
    "## Definition of done", "- D01: 行为正确；证据：V01", "",
    "## Stop conditions", "无", "",
    "## Budget", "- max_attempts_total: 2", "- max_wall_seconds_per_attempt: 1200", "- max_wall_seconds_total: 2400", "",
    "## Report back", "照常。", "",
    "## Forbidden", "无", "",
  ].join(LF);
}

export type Json = Record<string, unknown>;

export function jsonOf(task: string, base: string): Json {
  return {
    schema_version: 1, task_id: task, plan_version: 1, title: "改一个文件。", repository: null, base_sha: base, risk_level: "low",
    authorization: { executor: ["local_edit", "local_test"], integration: [] },
    executor: { provider: "step", model: "step-5-preview", thinking: "high", tools: ["read", "grep", "find", "ls", "edit", "write", "bash"], context_files: "project" },
    scope: { allowed_modified_files: ["src/a.ts"], allowed_new_files: [], allowed_deleted_files: [], forbidden_paths: [], dependency_changes: "forbidden" },
    setup: [],
    checks: [{ id: "V01", argv: ["python", "-m", "pytest", "tests", "-q"], cwd: ".", timeout_seconds: 300, required: true, expected_exit_code: 0, expect_on_base: "fail" }],
    definition_of_done: [{ id: "D01", text: "行为正确", evidence: ["V01"] }],
    budget: { max_attempts_total: 2, max_wall_seconds_per_attempt: 1200, max_wall_seconds_total: 2400, cost_budget: null },
  };
}

export const text = (data: Json): string => `${JSON.stringify(data, null, 2)}${LF}`;
