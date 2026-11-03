// 主任务状态与内核校验（迁移第 ⑤a 片，kit_hub.py 923–1306 行，加 stage_status_table 与 upstream_notes）：守卫、
// “内核此刻允许的下一步”、例行流转的推导与任务书。都是纯函数：状态是 json.loads 读出的 PyDict，取值照 Python 的
// [] 与 .get，比较照 ==，截断按码点。拒收原因的文字逐字进信与账本，影子运行逐字对照。
import { PyCrash, pyGet, pyItem, pyJoin, pyLenValue, pyPercentD, pyRepr, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { purePathIsAbsolute, purePathRelativePosix, purePathStr } from "@themis/base/pypath";
import { cmpCodePoints, codePoints, pyLower, pyStrip } from "@themis/base/pyre";
import { pyEq } from "@themis/base/pyvalue";
import {
  BUSY_GUARD, DEPENDS, HANDOFF_FIELD, MAX_STAGE_REWORKS, OWNER, PAUSE_TYPES, RETURN_TARGETS, ROUTINE_NEXT, STAGE_ORDER, STAGE_WORKER, WORKERS,
} from "./constants.ts";
import { type Meta, parseLetter, splitReturnNames, stageOf } from "./letters.ts";

const LF = String.fromCharCode(10);
const BT = String.fromCharCode(96);

const dict = (...entries: [string, PyValue][]): PyDict => new Map(entries);
const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
/** `x or {}`。 */
const orDict = (value: PyValue | undefined): PyValue => (pyTruthy(value) ? (value as PyValue) : new Map());
/** text[:n]，按码点。 */
const head = (text: string, n: number): string => codePoints(text).slice(0, n).join("");
/** text[:n]，text 必须是字符串（Python 对别的类型切片会报错或得到别的东西，这里照崩溃处理）。 */
function strHead(value: PyValue, n: number): string {
  if (typeof value !== "string") throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not subscriptable`);
  return head(value, n);
}
const str = (value: PyValue): string => pyStrValue(value);
const stageIndex = (suffix: string): number => STAGE_ORDER.indexOf(suffix);
/** value in container（dict 看键，list 看元素，str 看子串）。 */
function contains(container: PyValue, value: string): boolean {
  if (isDict(container)) return container.has(value);
  if (Array.isArray(container)) return container.some((item) => pyEq(item, value));
  if (typeof container === "string") return container.includes(value);
  throw new PyCrash("TypeError", `argument of type '${pyTypeName(container)}' is not iterable`);
}
const stagesOf = (ts: PyDict): PyValue => pyItem(ts, "stages");
const stageAt = (ts: PyDict, suffix: string): PyValue => pyItem(stagesOf(ts), suffix);

export function newTaskState(task: string, slug: string, title: string, baseHead: string, jevEnabled: boolean, createdAt: string): PyDict {
  return dict(
    ["task", task], ["slug", slug], ["title", title], ["status", "active"], ["created_at", createdAt], ["base_head", baseHead],
    ["contract_task", `${pyLower(task)}-${slug}`], ["jev_enabled", jevEnabled],
    ["stages", new Map(STAGE_ORDER.map((suffix) => [suffix, dict(["status", "idle"])]))],
    ["contract", dict()], ["oracle", dict()], ["audit_pre", dict(["fails", 0n])], ["exec", dict()], ["gate_post", dict()],
    ["jev", dict()], ["audit_post", dict()], ["workspaces", dict()], ["notes", []], ["coordinator_rejections", 0n],
  );
}

const taskLower = (ts: PyDict): string => {
  const task = pyItem(ts, "task");
  if (typeof task !== "string") throw new PyCrash("AttributeError", `'${pyTypeName(task)}' object has no attribute 'lower'`);
  return pyLower(task);
};
export const gatePattern = (ts: PyDict): string => `tests/test_gate_${taskLower(ts)}_*.py`;
export const gateFile = (ts: PyDict, kind: string): string => `tests/test_gate_${taskLower(ts)}_${kind}.py`;

/** 依赖 suffix 的下游阶段（传递闭包，按流水线顺序）。 */
export function dependents(suffix: string): string[] {
  const found: string[] = [];
  for (const name of STAGE_ORDER) if ((DEPENDS[name] ?? []).some((dep) => dep === suffix || found.includes(dep))) found.push(name);
  return found;
}

/** 上游重新交付后，依赖它的下游结论一律作废：阶段回到 idle，相关记录清空（就地改 ts）。 */
export function invalidateAfter(ts: PyDict, suffix: string): void {
  const later = dependents(suffix);
  const stages = stagesOf(ts);
  for (const name of later) {
    setItem(stages, name, dict(["status", "idle"]));
    const reworks = orDict(pyGet(ts, "reworks"));
    popKey(reworks, name);
  }
  if (later.includes("3-gate-pre")) ts.set("oracle", dict());
  if (later.includes("3j-jev")) popKey(pyItem(ts, "jev"), "3j-jev");
  if (later.includes("4-audit-pre")) ts.set("audit_pre", dict(["fails", pyGet(pyItem(ts, "audit_pre"), "fails", 0n)]));
  if (later.includes("5-exec")) ts.set("exec", dict());
  if (later.includes("6-gate-post")) ts.set("gate_post", dict());
  if (later.includes("6j-jev")) popKey(pyItem(ts, "jev"), "6j-jev");
  if (later.includes("7-audit-post")) ts.set("audit_post", dict());
}

function setItem(container: PyValue, key: string, value: PyValue): void {
  if (!isDict(container)) throw new PyCrash("TypeError", `'${pyTypeName(container)}' object does not support item assignment`);
  container.set(key, value);
}

/** d.pop(key, None)。 */
function popKey(container: PyValue, key: string): void {
  if (!isDict(container)) throw new PyCrash("AttributeError", `'${pyTypeName(container)}' object has no attribute 'pop'`);
  container.delete(key);
}

/** 审核端“退回”写的对象 → 阶段，按流水线顺序；认不出的名字丢掉。 */
export function returnStages(value: PyValue | undefined): string[] {
  const text = pyTruthy(value) ? str(value as PyValue) : "";
  const stages = new Set(splitReturnNames(text).filter((name) => Object.prototype.hasOwnProperty.call(RETURN_TARGETS, name)).map((name) => RETURN_TARGETS[name] as string));
  return [...stages].sort((a, b) => stageIndex(a) - stageIndex(b));
}

/** 工人正在办这个阶段（停下来提问、阻塞的不算）。 */
export function stageBusy(stage: PyValue): boolean {
  const last = pyGet(stage, "last_letter");
  return pyEq(pyItem(stage, "status"), "assigned") && !(typeof last === "string" && (PAUSE_TYPES as readonly string[]).includes(last));
}

export function guardStart(ts: PyDict, suffix: string): string | null {
  if (stageBusy(stageAt(ts, suffix))) return `阶段 ${suffix} ${BUSY_GUARD}`;
  if (suffix === "1-plan") return null;
  if (suffix === "2-contract") {
    if (!pyEq(pyItem(stageAt(ts, "1-plan"), "status"), "delivered")) return "规划端还没交付（1-plan）";
    const pending = pyGet(orDict(pyGet(ts, "external_facts")), "pending");
    if (pyTruthy(pending)) return `规划依赖 ${pyLenValue(pending)} 条未核实的仓库外事实，等站主核实（kit_hub.py send --facts-checked）`;
    return null;
  }
  if (suffix === "3-gate-pre") return pyTruthy(pyGet(pyItem(ts, "contract"), "validated")) ? null : "合同还没写进 .agent/plans/ 并通过 validate";
  if (suffix === "3j-jev") return pyEq(pyItem(stageAt(ts, "2-contract"), "status"), "delivered") ? null : "合同端还没交付（2-contract）";
  if (suffix === "4-audit-pre") {
    if (!pyTruthy(pyGet(pyItem(ts, "oracle"), "locked"))) return "基准测试还没锁定：要有基线提交、在基线上失败、合同的 base_sha 指向它并重新通过 validate";
    if (pyTruthy(pyGet(ts, "jev_enabled")) && !contains(pyItem(ts, "jev"), "3j-jev")) return "JEV 已启用，还没有合同概述的判断（3j-jev）";
    return null;
  }
  if (suffix === "5-exec") {
    const audit = pyItem(ts, "audit_pre");
    if (!pyEq(pyGet(audit, "verdict"), "通过")) return "一审还没有通过";
    if (!pyEq(pyGet(audit, "contract_sha256"), pyGet(pyItem(ts, "contract"), "sha256")) || !pyEq(pyGet(audit, "oracle_sha"), pyGet(pyItem(ts, "oracle"), "sha"))) {
      return "一审之后合同或基线提交变了，要重新一审";
    }
    return null;
  }
  if (suffix === "6-gate-post") return pyTruthy(pyGet(pyItem(ts, "exec"), "check_ok")) ? null : "执行端的检查还没全部通过（check --fresh 与范围门禁）";
  const gatePost = (): PyValue => pyItem(ts, "gate_post");
  const gatePostDone = (): boolean => pyTruthy(pyGet(gatePost(), "ok")) || pyTruthy(pyGet(gatePost(), "defects"));
  if (suffix === "6j-jev") return gatePostDone() ? null : "战后门禁还没全部通过";
  if (suffix === "7-audit-post") {
    if (!gatePostDone()) return "战后门禁还没全部通过";
    if (pyTruthy(pyGet(ts, "jev_enabled")) && !contains(pyItem(ts, "jev"), "6j-jev")) return "JEV 已启用，还没有执行概述的判断（6j-jev）";
    return null;
  }
  return `未知阶段 ${suffix}`;
}

/** 执行之后能不能热修补基准测试：执行端举证，或终审退回门禁端，或站主指定门禁返工。 */
export function hotfixReason(ts: PyDict): string | null {
  const execution = pyItem(ts, "exec");
  if (pyTruthy(pyGet(execution, "conflicts"))) return `执行端报了 ${pyPercentD(pyItem(execution, "conflicts"))} 条合同矛盾`;
  if (pyTruthy(pyGet(execution, "gate_claim"))) return "执行端说门禁测试有错";
  const auditPost = pyItem(ts, "audit_post");
  if (pyEq(pyGet(auditPost, "verdict"), "返工") && returnStages(pyGet(auditPost, "target")).includes("3-gate-pre")) return "终审退回门禁端";
  if (pyEq(pyGet(orDict(pyGet(ts, "owner_rework")), "suffix"), "3-gate-pre") && pyTruthy(pyGet(execution, "run_dir"))) return "站主指定门禁返工";
  return null;
}

function guardRework(ts: PyDict, suffix: string): string | null {
  const stage = stageAt(ts, suffix);
  const status = pyItem(stage, "status");
  if (stageBusy(stage)) return `阶段 ${suffix} 正在进行，不能返工`;
  if (pyEq(pyGet(orDict(pyGet(ts, "owner_rework")), "suffix"), suffix)) return null;
  const execution = pyItem(ts, "exec");
  if (suffix === "5-exec" && pyTruthy(pyGet(execution, "gate_claim"))) {
    return "执行端说门禁测试有错，协调人核实不了：给 gate-sonnet 发返工（热修补，内核会把执行端的原话交给它逐条核实），" +
      "或者给站主发提问；门禁重新交付或站主答复之前不能返工执行端";
  }
  if (suffix === "5-exec" && pyTruthy(pyGet(execution, "collect_failed"))) {
    return "上一轮 attempt 的候选没收上来（调度器收集出错），执行端的改动还在它的工作区里，从头重派会把它们丢掉。" +
      "给站主发提问（站主查明收集为什么失败、能不能把改动收回来）；站主用 send --rework 5-exec 指定之后才放行";
  }
  if (suffix === "5-exec" && pyTruthy(pyGet(execution, "stalled"))) {
    return "上一轮 attempt 跑满时限、候选一处没改：原样再派多半还是这样。给站主发提问（拆小合同、换执行模型，" +
      "或站主接手、查明卡在哪里）；站主用 send --rework 5-exec 指定之后才放行";
  }
  const done = pyGet(orDict(pyGet(ts, "reworks")), suffix, 0n);
  if (suffix !== "5-exec" && atLeast(done, MAX_STAGE_REWORKS)) {
    return `阶段 ${suffix} 已经返工 ${pyPercentD(done)} 次，同一处反复改不好：给站主发提问。站主可以用 send --rework 再指定一次返工，或者接手`;
  }
  if (suffix === "5-exec" && pyEq(pyGet(execution, "attempts_left"), 0n)) {
    return "合同预算的 attempt 已经用完，执行端派不出去：给站主发提问（出新版本合同追加预算，或站主接手）";
  }
  if (pyEq(status, "failed")) return null;
  const auditPre = pyItem(ts, "audit_pre");
  const auditPost = pyItem(ts, "audit_post");
  const returnedBy = (audit: PyValue): boolean => pyEq(pyGet(audit, "verdict"), "返工") && returnStages(pyGet(audit, "target")).includes(suffix);
  for (const audit of [auditPre, auditPost]) {
    const targets = returnStages(pyGet(audit, "target"));
    const upstream = targets.filter((stage) => stageIndex(stage) < stageIndex(suffix));
    if (returnedBy(audit) && upstream.length) {
      return `审核同时退回了 ${targets.join("、")}：先返工最上游的 ${upstream[0]}。它重新交付之后 ${suffix} 回到 idle，再给它发“开工”，brief 照抄审核对它列的阻塞项`;
    }
  }
  if (suffix === "3-gate-pre" && hotfixReason(ts)) return null;
  if (suffix === "2-contract" || suffix === "3-gate-pre") {
    if (returnedBy(auditPre) || (suffix === "2-contract" && returnedBy(auditPost))) return null;
    if (suffix === "2-contract" && pyTruthy(pyGet(execution, "conflicts"))) return null;
    return `没有一审或终审退回 ${suffix} 的记录，也没有内核核验失败，站主也没有指定返工`;
  }
  if (suffix === "6-gate-post") return returnedBy(auditPost) ? null : "没有终审退回战后门禁的记录，也没有内核核验失败";
  if (suffix === "1-plan") {
    if (atLeast(pyGet(auditPre, "fails", 0n), 3) || returnedBy(auditPre) || returnedBy(auditPost)) return null;
    if (pyEq(pyGet(stageAt(ts, "2-contract"), "last_letter"), "阻塞")) return null;
    return "一审连续没过不到 3 次，也没有一审或终审退回规划端，合同端也没有发“阻塞”";
  }
  if (suffix === "5-exec") {
    const gatePost = pyItem(ts, "gate_post");
    if (pyTruthy(pyGet(execution, "run_dir")) && !pyTruthy(pyGet(execution, "check_ok"))) return null;
    if (pyTruthy(pyGet(gatePost, "ran")) && !pyTruthy(pyGet(gatePost, "ok"))) return null;
    if (returnedBy(auditPost)) return null;
    return "没有执行之后的失败记录，也没有终审退回执行端";
  }
  return `阶段 ${suffix} 没有核验失败的记录`;
}

/** value >= limit，照 Python 比较；不能比的照 Python 报 TypeError。 */
function atLeast(value: PyValue, limit: number): boolean {
  if (typeof value === "boolean") return Number(value) >= limit;
  if (typeof value === "bigint") return value >= BigInt(limit);
  if (typeof value === "number") return value >= limit;
  throw new PyCrash("TypeError", `'>=' not supported between instances of '${pyTypeName(value)}' and 'int'`);
}

/** 协调人这封信能不能投递：交回拒收原因，能投递时交回 null。前置条件只看内核写下的状态。 */
export function guard(ts: PyDict | null, meta: Meta): string | null {
  const kind = meta.get("type") ?? "";
  const receiver = meta.get("to") ?? "";
  const taskId = meta.get("task-id") ?? "";
  const [main, suffix] = stageOf(taskId);
  if (ts === null) return `没有登记主任务 ${main || taskId}`;
  if (receiver === OWNER) return kind === "汇报" || kind === "提问" ? null : "给站主只能发 汇报 或 提问";
  if (kind === "汇报" || kind === "提问") return "汇报、提问只发给站主";
  if (!pyEq(pyGet(ts, "status"), "active")) return `主任务 ${str(pyItem(ts, "task"))} 已${pyEq(pyGet(ts, "status"), "done") ? "结项" : "停止"}`;
  if (!WORKERS.includes(receiver)) return `收信人 ${receiver} 不是工人`;
  if (suffix === null) return `发给工人的信要写阶段任务（例如 ${str(pyItem(ts, "task"))}-1-plan）`;
  if (STAGE_WORKER[suffix] !== receiver) return `阶段 ${suffix} 归 ${STAGE_WORKER[suffix]}，不归 ${receiver}`;
  const starting = kind === "开工" || kind === "返工";
  if (starting && suffix !== "1-plan" && pyTruthy(pyGet(ts, "after")) && !pyTruthy(pyGet(ts, "after_released"))) {
    return `登记时写了依赖 ${pyJoin("、", pyGet(ts, "after"))}：规划可以先做，合同端及以后的阶段要等它们都结项。内核到时把基线挪到新末端，写信通知你，再开工合同端`;
  }
  const upstream = pyGet(orDict(pyGet(ts, "owner_rework")), "suffix");
  if (starting && typeof upstream === "string" && STAGE_ORDER.includes(upstream) && stageIndex(upstream) < stageIndex(suffix)) {
    return `站主指定了 ${upstream} 返工，还没发：先给它发返工。它重新交付会把 ${suffix} 作废`;
  }
  if (kind === "开工") return guardStart(ts, suffix);
  if (kind === "返工") return guardRework(ts, suffix);
  if (kind === "通过") {
    if (suffix === "5-exec") {
      if (!pyEq(pyGet(pyItem(ts, "audit_post"), "verdict"), "通过")) return "终审还没有通过，不能结项";
      const rehearsal = orDict(pyGet(ts, "rehearsal"));
      if (pyGet(rehearsal, "ok") === false && pyEq(pyGet(rehearsal, "run_dir"), pyGet(pyItem(ts, "exec"), "run_dir"))) {
        const head12 = head(str(orEmptyString(pyGet(rehearsal, "head"))), 12);
        return `落地预演没过（末端 ${head12}）：等站主处理（收窄门禁断言或协调哪一片返工），末端变了内核会重新预演，通过之后再发`;
      }
      return null;
    }
    return pyEq(pyItem(stageAt(ts, suffix), "status"), "delivered") ? null : `阶段 ${suffix} 还没交付`;
  }
  if (kind === "等待" || kind === "停止") return null;
  return `协调人不能发 ${kind}`;
}

/** `x or ""`。 */
const orEmptyString = (value: PyValue): PyValue => (pyTruthy(value) ? value : "");

/** 把主任务的基线挪到 head：旧基线上的阶段 worktree 改名留着。交回原来的基线（就地改 ts）。 */
export function moveBase(ts: PyDict, headSha: string): PyValue {
  const previous = pyItem(ts, "base_head");
  ts.set("base_head", headSha);
  const workspaces = pyItem(ts, "workspaces");
  if (!isDict(workspaces)) throw new PyCrash("TypeError", `'${pyTypeName(workspaces)}' object is not iterable`);
  for (const kind of [...workspaces.keys()].filter((key) => key === "base" || key === "gate")) {
    const value = workspaces.get(kind) as PyValue;
    workspaces.delete(kind);
    workspaces.set(`${str(kind as PyValue)}@${strHead(previous, 10)}`, value);
  }
  return previous;
}

/** 给协调人看的“内核此刻允许的下一步”（只是提示；投递时照样逐封校验）。 */
export function allowedMoves(ts: PyDict): string[] {
  const task = str(pyItem(ts, "task"));
  const moves: string[] = [];
  for (const suffix of STAGE_ORDER) {
    const worker = STAGE_WORKER[suffix] as string;
    for (const kind of ["开工", "返工"]) {
      const meta = new Map([["type", kind], ["to", worker], ["task-id", `${task}-${suffix}`]]);
      if (guard(ts, meta) === null) moves.push(`${kind} → ${worker}（${task}-${suffix}）`);
    }
  }
  if (guard(ts, new Map([["type", "通过"], ["to", "exec-step"], ["task-id", `${task}-5-exec`]])) === null) {
    moves.push(`通过 → exec-step（${task}-5-exec）：结项，内核随后 verdict PASS 并 integrate`);
  }
  return moves;
}

/**
 * 这批信是不是全是例行信、例行的下一步是什么：交回 [下一步, 不是例行时的原因]。每一步是
 * {reply_to, fields, from_task, type, suffix}（键序照 Python 的 dict(reply, type=…, suffix=…)）。
 */
export function routineMoves(texts: readonly string[]): [PyDict[], string | null] {
  const moves: PyDict[] = [];
  for (const text of texts) {
    const [meta, fields] = parseLetter(text);
    const sender = meta.get("from") ?? "";
    const kind = meta.get("type") ?? "";
    const suffix = stageOf(meta.get("task-id") ?? "")[1];
    const move = (type: string, to: string): PyDict =>
      dict(["reply_to", meta.get("msg-id") || "none"], ["fields", new Map(fields)], ["from_task", meta.get("task-id") ?? ""], ["type", type], ["suffix", to]);
    if (sender === OWNER && kind === "任务") {
      moves.push(move("开工", "1-plan"));
      continue;
    }
    if (sender === "jev-judge") continue;
    if (!WORKERS.includes(sender) || !(kind === "交付" || kind === "返工完成") || suffix === null) return [[], `${sender} 的“${kind}”要协调人看`];
    const decision = pyStrip(fields.get("需协调人决定") || "无");
    if (decision !== "无" && decision !== "无。") return [[], `${sender} 的信里有需协调人决定的事`];
    const check = fields.get("内核核验") ?? "";
    if (suffix === "5-exec" && !check.startsWith("通过")) return [[], "执行端的检查没过：原始失败还没人分诊，交协调人（错一次就是一个 attempt）"];
    if (!check.startsWith("通过")) {
      if (check.includes("审核结论缺失")) return [[], "审核结论缺失，交协调人"];
      moves.push(move("返工", suffix));
    } else if ((suffix === "4-audit-pre" || suffix === "7-audit-post") && fields.get("结论") === "返工") {
      const targets = returnStages(fields.get("退回") ?? null);
      if (!targets.length) return [[], `审核退回的对象认不出：${fields.has("退回") ? (fields.get("退回") as string) : "None"}`];
      moves.push(move("返工", targets[0] as string));
    } else if (suffix === "4-audit-pre" || suffix === "7-audit-post") {
      moves.push(move(suffix === "4-audit-pre" ? "开工" : "通过", "5-exec"));
    } else {
      const next = ROUTINE_NEXT[suffix];
      if (next === undefined) throw new PyCrash("KeyError", `'${suffix}'`);
      moves.push(move("开工", next));
    }
  }
  if (!moves.length) return [[], "这批信推不出下一步"];
  return [moves, null];
}

/** 内核代办时写的任务书：上游产物在只读输入目录里的路径；返工的原因照原话附上。 */
export function renderRoutineBrief(repo: string, ts: PyDict, move: PyDict): string {
  const task = str(pyItem(ts, "task"));
  const suffix = str(pyItem(move, "suffix"));
  const kind = str(pyItem(move, "type"));
  const tasks = ".agent/mailbox/tasks";
  const execution = pyItem(ts, "exec");
  const runDir = pyGet(execution, "run_dir");
  const run = pyTruthy(runDir) && typeof runDir === "string" && purePathIsAbsolute(runDir) ? relativeTo(runDir, repo) : runDir;
  const runText = pyTruthy(run) ? str(run) : null;
  const jev = pyItem(ts, "jev");
  const contract = pyItem(ts, "contract");
  const sources: Record<string, string[]> = {
    站主的任务书: [`${tasks}/${task}/brief.md`],
    规划报告: [`${tasks}/${task}-1-plan/report.md`],
    合同: pyTruthy(pyGet(contract, "md")) ? [str(pyItem(contract, "md"))] : [],
    基准测试: listOf(orList(pyGet(pyItem(ts, "oracle"), "files"))).map(str),
    战前门禁的报告: [`${tasks}/${task}-3-gate-pre/report.md`],
    "合同概述的 JEV 判断": contains(jev, "3j-jev") ? [`${tasks}/${task}-3j-jev/report.md`] : [],
    候选补丁: runText !== null ? [`${runText}/candidate.patch`] : [],
    执行概述与执行报告: runText !== null ? [`${runText}/summary.md`, `${runText}/executor-report.md`] : [],
    战后门禁的报告: [`${tasks}/${task}-6-gate-post/report.md`],
    "执行概述的 JEV 判断": contains(jev, "6j-jev") ? [`${tasks}/${task}-6j-jev/report.md`] : [],
  };
  const wanted: Record<string, string[]> = {
    "1-plan": ["站主的任务书"],
    "2-contract": ["站主的任务书", "规划报告"],
    "3-gate-pre": ["合同", "规划报告"],
    "4-audit-pre": ["合同", "基准测试", "战前门禁的报告", "合同概述的 JEV 判断"],
    "6-gate-post": ["合同", "候选补丁", "执行概述与执行报告", "基准测试"],
    "7-audit-post": ["合同", "候选补丁", "执行概述与执行报告", "战后门禁的报告", "执行概述的 JEV 判断"],
  };
  const lines = [
    `# ${task}-${suffix}（${kind}，内核按例行流转写的任务书）`, "",
    "上一阶段交付通过、下一步按例行流转就是这里，所以这份任务书由内核写（七端改造第 3 条）。要做什么见你的岗位说明；下面的路径都在只读输入目录里照原样能找到。",
    "", "## 材料", "",
  ];
  for (const name of wanted[suffix] ?? []) {
    const paths = sources[name] as string[];
    if (paths.length) lines.push(`- ${name}：${paths.map((item) => BT + item + BT).join("、")}`);
  }
  const stage = stageAt(ts, suffix);
  const problems = pyGet(stage, "problems");
  if (kind === "返工" && pyTruthy(problems)) {
    lines.push("", "## 返工的原因：内核核验没过（原话）", "", ...listOf(problems).map((problem) => `- ${str(problem)}`));
    if (pyTruthy(pyGet(stage, "redelivered"))) {
      lines.push("", "上一个会话已经在同一会话里照这些原话当场重交过一次，还是没过：这一回合换个思路，改不了、要协调人或站主定的，交“阻塞”信说明原因。");
    }
  } else if (kind === "返工") {
    const blockers = pyGet(pyItem(move, "fields"), "阻塞项");
    lines.push("", "## 返工的原因：审核退回（阻塞项原文）", "", textItem(pyTruthy(blockers) ? blockers : "（审核没列阻塞项）"),
      "", `审核报告：${BT}${tasks}/${str(pyItem(move, "from_task"))}/report.md${BT}`);
  }
  const history = pyGet(ts, "audit_history");
  const historyList = pyTruthy(history) ? listOf(history) : [dict()];
  const last = historyList[historyList.length - 1] as PyValue;
  if (kind === "开工" && pyEq(pyGet(last, "verdict"), "返工") && returnStages(pyGet(last, "target")).includes(suffix)) {
    const blockers = pyGet(last, "blockers");
    lines.push("", "## 最近一次审核也退回了这一阶段（阻塞项原文）", "", textItem(pyTruthy(blockers) ? blockers : "（空）"));
  }
  return lines.join(LF) + LF;
}

/** LF.join(lines) 里的一项：必须是字符串（Python 遇到别的类型报 TypeError）。 */
function textItem(value: PyValue): string {
  if (typeof value !== "string") throw new PyCrash("TypeError", `sequence item: expected str instance, ${pyTypeName(value)} found`);
  return value;
}

/** Path(value).relative_to(repo).as_posix()：不在仓库之下照 Python 报 ValueError，文字是两个 str(Path) 的 repr（⑤f 起比文字）。 */
export function relativeTo(value: string, repo: string): string {
  const rel = purePathRelativePosix(value, repo);
  if (rel === null) throw new PyCrash("ValueError", `${pyRepr(purePathStr(value))} is not in the subpath of ${pyRepr(purePathStr(repo))}`);
  return rel;
}

const orList = (value: PyValue): PyValue => (pyTruthy(value) ? value : []);
/** list(value)：list 照原样，dict 照键，str 照码点。 */
function listOf(value: PyValue): PyValue[] {
  if (Array.isArray(value)) return value;
  if (isDict(value)) return [...value.keys()].map((key) => key as PyValue);
  if (typeof value === "string") return codePoints(value);
  throw new PyCrash("TypeError", `'${pyTypeName(value)}' object is not iterable`);
}

/** 阶段状态表加事实与“内核此刻允许的下一步”。 */
export function stageStatusTable(ts: PyDict): string {
  const task = str(pyItem(ts, "task"));
  const rows = ["| 阶段 | 工人 | 状态 | 备注 |", "|---|---|---|---|"];
  for (const suffix of STAGE_ORDER) {
    const stage = stageAt(ts, suffix);
    const note = pyGet(stage, "note");
    const noteText = pyTruthy(note) ? note : "";
    if (typeof noteText !== "string") throw new PyCrash("AttributeError", `'${pyTypeName(noteText)}' object has no attribute 'replace'`);
    rows.push(`| ${task}-${suffix} | ${STAGE_WORKER[suffix]} | ${str(pyItem(stage, "status"))} | ${head(noteText.replaceAll(LF, " "), 160)} |`);
  }
  const contract = pyItem(ts, "contract");
  const oracle = pyItem(ts, "oracle");
  const execution = pyItem(ts, "exec");
  const gatePost = pyItem(ts, "gate_post");
  const contractKey = pyGet(contract, "key");
  const facts = [
    `- 合同：${pyTruthy(contractKey) ? str(contractKey) : "无"}（validate ${pyTruthy(pyGet(contract, "validated")) ? "通过" : "未通过/未写"}）`,
    `- 基准测试：${pyTruthy(pyGet(oracle, "locked")) ? `已锁定 ${strHead(pyItem(oracle, "sha"), 10)}` : "未锁定"}`,
    `- 一审：${orText(pyGet(pyItem(ts, "audit_pre"), "verdict"), "无")}；终审：${orText(pyGet(pyItem(ts, "audit_post"), "verdict"), "无")}`,
    `- 执行：${pyTruthy(pyGet(execution, "run_dir")) ? (pyTruthy(pyGet(execution, "check_ok")) ? "check 通过" : "check 未通过") : "未开始"}`,
    `- 战后门禁：${!pyTruthy(pyGet(gatePost, "ran")) ? "未开始" : pyTruthy(pyGet(gatePost, "ok")) ? "通过"
      : pyTruthy(pyGet(gatePost, "defects")) ? `候选有 ${pyLenValue(pyItem(gatePost, "defects"))} 处缺陷（门禁端举证），待终审裁定` : "未通过"}`,
    `- JEV：${pyTruthy(pyGet(ts, "jev_enabled")) ? "启用" : "未启用"}`,
  ];
  if (pyTruthy(pyGet(orDict(pyGet(ts, "external_facts")), "pending"))) {
    facts.push(`- 仓库外事实：${pyLenValue(pyItem(pyItem(ts, "external_facts"), "pending"))} 条待站主核实，核实之前不能开工合同端`);
  }
  if (pyTruthy(pyGet(ts, "after")) && !pyTruthy(pyGet(ts, "after_released"))) {
    facts.push(`- 依赖：等 ${pyJoin("、", pyGet(ts, "after"))} 结项。规划可以先做，合同端要等内核把基线挪到新末端、写信通知`);
  } else if (pyTruthy(pyGet(ts, "after_released"))) {
    facts.push(`- 依赖 ${pyJoin("、", pyItem(ts, "after"))} 已结项：基线已从 ${strHead(pyItem(pyItem(ts, "after_released"), "previous"), 10)} 挪到 ${strHead(pyItem(ts, "base_head"), 10)}`);
  }
  const chain = pyGet(ts, "rework_chain");
  if (pyTruthy(chain)) {
    facts.push(`- 返工链：${listOf(chain).map((link) => `${str(pyItem(link, "from"))} 的候选 → 返工提交 ${strHead(pyItem(link, "commit"), 10)}（${str(pyItem(link, "contract"))}）`).join("；")}`);
  }
  if (pyEq(pyGet(execution, "attempts_left"), 0n)) facts.push("- 合同预算的 attempt 已经用完：执行端派不出去，要站主决定");
  const reworks = pyGet(ts, "reworks");
  if (pyTruthy(reworks)) {
    if (!isDict(reworks)) throw new PyCrash("AttributeError", `'${pyTypeName(reworks)}' object has no attribute 'items'`);
    const entries = [...reworks].map(([key, count]) => [str(key as PyValue), count] as const).sort((a, b) => cmpCodePoints(a[0], b[0]));
    facts.push(`- 返工次数：${entries.map(([key, count]) => `${key} ${pyPercentD(count)} 次`).join("、")}（执行端以外每个阶段最多 ${MAX_STAGE_REWORKS} 次）`);
  }
  const closed = pyGet(ts, "closed_by_owner");
  if (pyTruthy(closed)) facts.push(`- 站主接手结项：${strHead(pyItem(closed, "ref"), 12)}（${str(pyItem(closed, "note"))}）`);
  const moves = allowedMoves(ts);
  return [...rows, "", ...facts, "", "**内核此刻允许的下一步**（只是提示，投递时照样逐封校验）：",
    moves.map((move) => `- ${move}`).join(LF) || "- （没有：等待工人或站主）"].join(LF);
}

const orText = (value: PyValue, fallback: string): string => (pyTruthy(value) ? str(value) : fallback);

/** 依赖链上游各阶段最近一封信里的下游须知（不是“无”的），只取已经交付通过的阶段。 */
export function upstreamNotes(ts: PyDict, suffix: string | null): string[] {
  const above = new Set<string>();
  const todo = [...(DEPENDS[suffix || ""] ?? [])];
  while (todo.length) {
    const stage = todo.pop() as string;
    if (!above.has(stage)) {
      above.add(stage);
      todo.push(...(DEPENDS[stage] ?? []));
    }
  }
  const notes: string[] = [];
  const stages = stagesOf(ts);
  for (const stage of STAGE_ORDER) {
    const record = orDict(pyGet(stages, stage));
    const handoff = pyGet(orDict(pyGet(record, "fields")), HANDOFF_FIELD);
    const text = pyStrip(pyTruthy(handoff) ? str(handoff) : "");
    if (above.has(stage) && pyEq(pyGet(record, "status"), "delivered") && text && text !== "无" && text !== "无。") {
      notes.push(`- 出自 ${stage}（${STAGE_WORKER[stage]}）：${text}`);
    }
  }
  return notes;
}
