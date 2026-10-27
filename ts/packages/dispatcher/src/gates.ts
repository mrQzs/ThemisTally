// pi_dispatch 的门禁（迁移第 ④b3 片）：verdict 前的 G0–G6 判定与它用到的输入核对。④b7 run/collect、④b8 branch、
// integrate、review-draft 也用。各门禁的 problems、notes 的文字与次序照 Python；证据文件里的字段缺失或类型不对时照 Python
// 抛同类异常。本机的 platform.platform() 由启动器放进 context（迁移计划 D1），这里作参数传入。
import { statSync } from "node:fs";
import path from "node:path";
import { PyCrash, pyGet, pyItem, pyIter, pyJoin, pyPercentD, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyOSError, pyReadBytes } from "@themis/base/pyio";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { normCase, purePathStr, pyExists } from "@themis/base/pypath";
import { TASK_ID_RE } from "@themis/base/secrets";
import { pyEq } from "@themis/base/pyvalue";
import { resolveCommit, verifyPlannerPublication } from "./contract-plan.ts";
import { candidatePatchOk, sha256File } from "./evidence.ts";
import { BindingRecordError, bindingRecordRel, executorClass, loadBindingRecord } from "./executor.ts";
import { effectiveAutocrlf, lineEndingsOnly, snapshotTree, treeDrift } from "./gitops.ts";
import { DispatchError, type Repo, readJsonOr } from "./repo.ts";
import { getState, latestNumbered } from "./status.ts";

export const FAILURE_CLASSES = [
  "PLAN_ERROR", "EXECUTION_ERROR", "INFRA_FAILURE", "SCOPE_VIOLATION", "REQUIREMENT_BLOCKED", "TIMEOUT", "BUDGET_EXCEEDED", "CANCELLED",
] as const;
export const GATES = ["G0", "G1", "G2", "G3", "G4", "G5", "G6"] as const;

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const get = (value: PyValue, key: string, fallback: PyValue = null): PyValue => pyGet(value, key, fallback);
const s = (value: PyValue): string => pyStrValue(value);
/** x or fallback。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);

function isDir(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

/** key in value（dict 看键，list 看元素，str 看子串）。 */
function contains(value: PyValue, key: string): boolean {
  if (isDict(value)) return value.has(key);
  if (Array.isArray(value)) return value.some((item) => pyEq(item, key));
  if (typeof value === "string") return value.includes(key);
  throw new PyCrash("TypeError", `argument of type '${pyTypeName(value)}' is not iterable`);
}

/** value[:count]（列表）。 */
const head = (value: PyValue, count: number): PyValue[] => pyIter(value).slice(0, count);

/** binding_record_problems：按角色写的合同必须带版本记录的副本，且与记录逐项相同、合同哈希一致（3.0 第二轮 D5）。 */
export function bindingRecordProblems(repo: Repo, runDir: string, meta: PyValue): string[] {
  const loaded = readJsonOr(path.join(runDir, "contract.json"), new Map());
  const raw: PyDict = isDict(loaded) ? loaded : new Map();
  if (executorClass(raw.get("executor") ?? null) !== "role") {
    return contains(meta, "executor_binding") ? ["不是按角色写的合同，meta.json 却有 executor_binding"] : [];
  }
  const binding = get(meta, "executor_binding");
  if (!isDict(binding)) return ["按角色写的合同缺少 meta.json 的 executor_binding"];
  const taskId = get(meta, "task_id");
  const version = get(meta, "plan_version");
  if (!(typeof taskId === "string" && TASK_ID_RE.test(taskId)) || typeof version !== "bigint"
    || !pyEq(taskId, raw.get("task_id") ?? null) || !pyEq(version, raw.get("plan_version") ?? null)) {
    return ["meta.json 的 task_id、plan_version 与冻结的合同不一致，推不出版本记录的路径"];
  }
  const rel = bindingRecordRel(taskId, version);
  let record: PyDict | null;
  try {
    record = loadBindingRecord(repo.root, taskId, version);
  } catch (error) {
    if (error instanceof BindingRecordError) return [error.message];
    throw error;
  }
  if (record === null) return [`版本记录不存在：${rel}`];
  const copy: PyDict = new Map([...binding].filter(([key]) => key !== "record_path"));
  if (!pyEq(copy, record)) return [`版本记录与 meta.json 里的副本不一致：${rel}`];
  if (!pyEq(record.get("contract_json_sha256") ?? null, get(meta, "contract_json_sha256"))) return [`版本记录对应的合同哈希与这次 attempt 不同：${rel}`];
  return [];
}

/** verify_inputs：冻结合同的两份字节与 prepare 时的哈希一致，再加版本记录的核对。 */
export function verifyInputs(runDir: string, meta: PyValue, repo: Repo): string[] {
  const problems: string[] = [];
  for (const [name, key] of [["plan.md", "plan_md_sha256"], ["contract.json", "contract_json_sha256"]] as const) {
    const file = path.join(runDir, name);
    if (!pyExists(file) || !pyEq(sha256File(file), get(meta, key))) problems.push(`${name} 的哈希与 prepare 时记录的不一致`);
  }
  problems.push(...bindingRecordProblems(repo, runDir, meta));
  return problems;
}

/** _platform_family：platform.platform() 的系统名（版本号会随升级变，只比系统名）。 */
const platformFamily = (text: PyValue): string => (pyTruthy(text) ? s(text) : "").split("-")[0]?.toLowerCase() ?? "";

/** attempt_origin_notes：attempt 在另一台机器或另一处仓库上派遣时的提示（2.4.0）。here 是本机的 platform.platform()。 */
export function attemptOriginNotes(repo: Repo, meta: PyValue, here: string): string[] {
  const recordedPlatform = get(meta, "platform");
  const recordedRepo = get(meta, "repository");
  const otherMachine = pyTruthy(recordedPlatform) && platformFamily(recordedPlatform) !== platformFamily(here);
  const otherRepo = pyTruthy(recordedRepo) && normCase(s(recordedRepo)) !== normCase(repo.root);
  if (!(otherMachine || otherRepo)) return [];
  return [
    `attempt 在${otherMachine ? "另一台机器上" : "另一处仓库"}派遣（prepare 时 ${s(recordedPlatform)}，仓库 ${s(recordedRepo)}；本机 ${here}，仓库 ${repo.root}）：` +
      "执行 worktree 只在派遣的位置，验收检查用 check --fresh；verdict 不重新快照 worktree，G6 只凭候选补丁的往返校验",
  ];
}

/** planner_attempt_publication_errors：planner-v2 的合同在每个消费点都要过发布门禁。键照 Python 用 run_dir 的名字拼。 */
export function plannerAttemptPublicationErrors(repo: Repo, runDir: string, contract: PyValue): string[] {
  if (!isDict(contract) || contract.get("contract_family") !== "planner-v2") return [];
  let md: Buffer;
  let machine: Buffer;
  try {
    md = pyReadBytes(path.join(runDir, "plan.md"));
    machine = pyReadBytes(path.join(runDir, "contract.json"));
  } catch (error) {
    if (error instanceof PyOSError) return [`planner-v2 固定合同字节读取失败：${error.message}`];
    throw error;
  }
  const taskId = path.basename(runDir).split(".v")[0] as string;
  return verifyPlannerPublication(repo, `${taskId}.v${s(contract.get("plan_version") ?? null)}`, md, machine);
}

interface Gate {
  passed: boolean;
  readonly problems: PyValue[];
  readonly notes: PyValue[];
}

/** evaluate_gates：{state_at_review, gates}，gates 是 G0–G6 各自的 passed、problems、notes。 */
export function evaluateGates(repo: Repo, runDir: string, meta: PyValue, contract: PyDict, here: string): PyDict {
  const gates = new Map<string, Gate>(GATES.map((name) => [name, { passed: true, problems: [], notes: [] }]));
  const gate = (name: string): Gate => gates.get(name) as Gate;
  gate("G5").notes.push("质量复审（测试是否弱化、兼容性、残余风险）由复审报告负责，工具不做机械判断");
  const fail = (name: string, message: PyValue): void => {
    gate(name).passed = false;
    gate(name).problems.push(message);
  };
  for (const problem of plannerAttemptPublicationErrors(repo, runDir, contract)) fail("G0", problem);
  for (const problem of verifyInputs(runDir, meta, repo)) fail("G0", problem);
  const base = pyItem(meta, "base_sha");
  if (resolveCommit(repo.root, s(base)) !== base) fail("G0", "基线提交不可用");
  gate("G0").notes.push(...attemptOriginNotes(repo, meta, here));
  const state = getState(runDir);
  const read = (name: string, fallback: PyValue): PyValue => readJsonOr(path.join(runDir, name), fallback);
  const run = read("run.json", new Map());
  const events = read("events-summary.json", new Map());
  if (!pyTruthy(run)) fail("G1", "缺少 run.json");
  if (pyTruthy(get(run, "timed_out"))) fail("G1", "运行超时");
  if (pyTruthy(get(run, "interrupted"))) fail("G1", "运行被取消或调度器中断");
  if (!pyEq(get(run, "exit_code"), 0n)) fail("G1", `Pi 退出码为 ${s(get(run, "exit_code"))}`);
  for (const problem of pyIter(get(events, "problems", ["缺少事件摘要"]))) fail("G1", problem);
  if (pyTruthy(events) && !pyTruthy(get(events, "provider_thinking_levels"))) {
    gate("G1").notes.push(`提供商未回报思考级别：只能确认请求的级别（${s(get(or(get(events, "requested_model"), new Map()), "thinking"))}）`);
  }
  const report = read("report-status.json", new Map());
  if (get(report, "status") !== "json_ok") gate("G1").notes.push(`执行报告状态：${s(get(report, "status"))}`);
  if (pyTruthy(get(report, "contract_conflicts"))) {
    gate("G3").notes.push(`执行报告列出了 ${pyPercentD(pyItem(report, "contract_conflicts"))} 处合同矛盾：PASS 前在复审中逐条裁定`);
  } else if (pyTruthy(get(events, "ambiguity_mention_count")) && !pyTruthy(get(report, "unresolved_questions")) && !pyTruthy(get(report, "interpretations"))) {
    gate("G3").notes.push("执行过程中提到合同的歧义、矛盾或一致性，报告没有列出：复审时核对（见 summary.md）");
  }
  const scope = read("scope.json", null);
  if (scope === null) fail("G2", "缺少 scope.json");
  else for (const violation of pyIter(get(scope, "violations", []))) fail("G2", `${s(pyItem(violation, "kind"))} ${s(pyItem(violation, "path"))}`);
  const changes = or(get(read("observations.json", new Map()), "main_repo_changes"), new Map());
  if (pyTruthy(get(changes, "head_changed")) || pyTruthy(get(changes, "other_paths"))) {
    gate("G2").notes.push("运行期间主工作区有规划路径之外的变化，复审时确认来源（见 summary.md）");
  }
  for (const item of pyIter(get(events, "outside_worktree_paths", []))) {
    const tool = get(item, "tool");
    const shell = tool === "bash" || tool === "powershell";
    if (pyTruthy(get(item, "main_repo")) && (shell || get(item, "failed") !== true)) {
      // 主仓库是规划端的工作区：执行器读写它，会把未提交的内容带进候选，或改动规划端的状态（2.3.0）
      fail("G2", `执行器访问了主仓库：${s(get(item, "path"))}（${s(tool)}）`);
    } else if (shell) {
      gate("G2").notes.push(`执行器的命令里出现工作副本外路径：${s(get(item, "path"))}（${s(tool)}，事件流第 ${s(get(item, "event_line"))} 行）`);
    } else if (get(item, "failed") !== true) {
      gate("G2").notes.push(`执行器访问了工作副本外路径：${s(get(item, "path"))}（${s(tool)}）`);
    }
  }
  const candidate = read("candidate.json", new Map());
  const latest = latestNumbered(path.join(runDir, "checks"));
  const checks = latest ? readJsonOr(path.join(latest, "checks.json"), null) : null;
  if (!pyTruthy(checks) || pyTruthy(get(checks as PyValue, "aborted"))) {
    fail("G3", "没有有效的独立检查记录");
    fail("G4", "没有有效的独立检查记录");
  } else {
    const results = new Map<PyValue, PyValue>();
    for (const record of pyIter(get(checks, "results", []))) results.set(pyItem(record, "id"), record);
    const resultOf = (id: PyValue): PyValue | undefined => [...results].find(([key]) => pyEq(key, id))?.[1];
    if (!pyEq(get(checks, "candidate_tree"), get(candidate, "tree"))) fail("G4", "最近一次检查不是针对当前候选");
    if (!pyTruthy(get(checks, "covers_all_required"))) fail("G4", "最近一次检查没有覆盖全部必要检查（使用了 --only？）");
    if (pyTruthy(get(checks, "modified_by_checks"))) {
      fail("G4", `检查过程修改了候选文件：${pyJoin(", ", head(get(checks, "candidate_files_modified", []), 10))}`);
    }
    if (pyTruthy(get(checks, "unexpected_files_by_checks"))) {
      fail("G4", `检查产生了候选之外的新文件：${pyJoin(", ", head(pyItem(checks, "unexpected_files_by_checks"), 10))}`);
    }
    if (pyTruthy(get(checks, "artifact_files"))) gate("G4").notes.push(`忽略的缓存文件：${pyJoin(", ", head(pyItem(checks, "artifact_files"), 10))}`);
    if (get(checks, "mode") === "fresh") gate("G4").notes.push("检查在干净副本（基线 + 候选补丁 + setup）上运行");
    else {
      gate("G4").notes.push("检查在执行 worktree 中运行：被 .gitignore 忽略的文件（依赖、构建产物）也可能影响结果；中高风险任务建议 check --fresh");
    }
    for (const check of contract.get("checks") as PyDict[]) {
      if (!pyTruthy(pyGet(check, "required", true))) continue;
      const record = resultOf(check.get("id") ?? null);
      if (!pyTruthy(record ?? null) || !pyTruthy(get(record as PyValue, "passed"))) {
        fail("G4", `必要检查 ${s(check.get("id") ?? null)}：${record !== undefined && pyTruthy(record) ? s(get(record, "status")) : "not_run"}`);
      }
    }
    for (const item of contract.get("definition_of_done") as PyDict[]) {
      for (const ref of pyIter(pyGet(item, "evidence", []))) {
        if (ref === "scope") {
          if (scope === null || pyTruthy(get(scope, "violations"))) fail("G3", `${s(item.get("id") ?? null)} 依赖的范围证据未通过`);
        } else if (ref !== "review") {
          const record = resultOf(ref);
          if (!pyTruthy(record ?? null) || !pyTruthy(get(record as PyValue, "passed"))) fail("G3", `${s(item.get("id") ?? null)} 依赖的 ${s(ref)} 未通过或未运行`);
        }
      }
    }
  }
  const workDir = purePathStr(s(pyItem(meta, "worktree")));
  const tree = get(candidate, "tree");
  if (pyTruthy(tree) && isDir(workDir)) {
    try {
      const now = snapshotTree(workDir, s(base), runDir, "gate", get(meta, "git_autocrlf"));
      const drift = treeDrift(workDir, s(tree), now);
      if (drift.modified.length) {
        if (lineEndingsOnly(workDir, s(tree), now)) {
          fail("G6", `候选文件与记录只差行尾（CRLF / LF）：${drift.modified.length} 个文件。多半是 core.autocrlf 在运行后被改动` +
            `（prepare 时记录 ${s(get(meta, "git_autocrlf", "未记录"))}，现在 ${effectiveAutocrlf(repo.root)}）；先恢复配置再重新 verdict`);
        } else {
          fail("G6", `候选文件在记录后被修改：${drift.modified.slice(0, 10).join(", ")}`);
        }
      }
      if (drift.added.length) gate("G6").notes.push(`工作副本有候选之外的新文件（不会被集成）：${drift.added.slice(0, 10).join(", ")}`);
    } catch (error) {
      if (!(error instanceof DispatchError)) throw error;
      fail("G6", `无法重新快照：${error.message}`);
    }
  } else if (pyTruthy(tree)) {
    // 以前这里静默跳过，复审者看不出 G6 少了一项依据（跨机器复审实机，2.4.0）
    gate("G6").notes.push(`执行 worktree 不存在（已清理，或在派遣 attempt 的另一台机器上）：${workDir}。没有重新快照，G6 只凭候选补丁的往返校验`);
  }
  if (!candidatePatchOk(runDir, candidate)) fail("G6", "候选补丁缺失、被改动或未通过往返校验");
  const shown: PyDict = new Map(
    [...gates].map(([name, info]): [string, PyValue] => [name, new Map<string, PyValue>([["passed", info.passed], ["problems", info.problems], ["notes", info.notes]])]),
  );
  return new Map<string, PyValue>([["state_at_review", state], ["gates", shown]]);
}

/** 便于命令层取用：gates 的 G0–G6 各自是否通过。 */
export function failedGates(evaluation: PyDict): string[] {
  return [...(evaluation.get("gates") as PyDict)].filter(([, info]) => !(info as PyDict).get("passed")).map(([name]) => name as string);
}

