// 信件（迁移第 ⑤a 片，kit_hub.py 610–744 行）：stage_of、render_letter、parse_letter、letter_errors。
// 逐字照 Python：splitlines、strip 用 base 的 Python 语义；任务号的两个正则交给 pyregex（数字类认 Unicode 数字，$ 也匹配
// 末尾的换行之前）；FIELD_LINE_RE（行首最短的非空白、冒号、可选的空格或制表符、其余）要分组，pyregex 不记捕获组，照它的语义手写。
import { newMsgId } from "@themis/base/clock";
import { PyCrash, pyStrValue, pyTypeName } from "@themis/base/pyfmt";
import type { PyValue } from "@themis/base/pyjson";
import { codePoints, isSpace, pySplitlines, pyStrip } from "@themis/base/pyre";
import { compilePy } from "@themis/base/pyregex";
import {
  COORDINATOR, COORDINATOR_TYPES, FIELDS, KERNEL, KERNEL_TYPES, KNOWN_FIELDS, MAX_BODY_LINES, OWNER, OWNER_TYPES, RETURN_TARGETS,
  ROSTER, ROUTED_TYPES, STAGE_ORDER, VERDICTS, WORKER_TYPES, WORKERS,
} from "./constants.ts";
import { HubError } from "./errors.ts";

export { newMsgId };

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);
const TAB = String.fromCharCode(9);

const MAIN_TASK = compilePy(`^T${BS}d{3,6}$`);
const STAGE_TASK = compilePy(`^(T${BS}d{3,6})-(${STAGE_ORDER.join("|")})$`);

/** 'T001-3-gate-pre' → ['T001', '3-gate-pre']；'T001' → ['T001', null]；其他 → [null, null]。 */
export function stageOf(taskId: string | null | undefined): [string | null, string | null] {
  const text = taskId || "";
  const stage = STAGE_TASK.match(text);
  if (stage) {
    // 整段匹配里第一个连字符之前是主任务号（数字里没有连字符）；$ 匹配在末尾换行之前时整段不含那个换行
    const at = stage.group.indexOf("-");
    return [stage.group.slice(0, at), stage.group.slice(at + 1)];
  }
  return MAIN_TASK.match(text) ? [text, null] : [null, null];
}

export type Meta = ReadonlyMap<string, string>;

const META_KEYS = ["msg-id", "from", "to", "task-id", "in-reply-to", "type"] as const;

export function renderLetter(meta: Meta, fields: ReadonlyMap<string, PyValue>): string {
  const lines = ["---", ...META_KEYS.map((key) => `${key}: ${meta.get(key) ?? ""}`), "---"];
  const ordered = [...KNOWN_FIELDS.filter((key) => fields.has(key)), ...[...fields.keys()].filter((key) => !KNOWN_FIELDS.includes(key))];
  for (const key of ordered) {
    const parts = pySplitlines(pyStrip(pyStrValue(fields.get(key) as PyValue)) || "无");
    lines.push(`${key}: ${parts[0]}`, ...parts.slice(1).map((part) => `  ${part}`));
  }
  return lines.join(LF) + LF;
}

/** 解析信件：交回 [头部, 正文字段, 正文行数]。不认识的行接到上一个字段后面（续行）。 */
export function parseLetter(text: string): [Map<string, string>, Map<string, string>, number] {
  const lines = pySplitlines(text);
  if (!lines.length || pyStrip(lines[0] as string) !== "---") throw new HubError("信件要以 --- 开头");
  const end = lines.findIndex((line, index) => index > 0 && pyStrip(line) === "---");
  if (end < 0) throw new HubError("信件头部没有结束的 ---");
  const meta = new Map<string, string>();
  for (const line of lines.slice(1, end)) {
    const at = line.indexOf(":");
    if (at >= 0) meta.set(pyStrip(line.slice(0, at)), pyStrip(line.slice(at + 1)));
  }
  const body = lines.slice(end + 1);
  while (body.length && !pyStrip(body[body.length - 1] as string)) body.pop();
  const fields = new Map<string, string>();
  let current: string | null = null;
  for (const line of body) {
    const match = fieldLine(line);
    if (match && KNOWN_FIELDS.includes(match[0])) {
      current = match[0];
      fields.set(current, pyStrip(match[1]));
    } else if (current !== null) {
      fields.set(current, stripLf(`${fields.get(current)}${LF}${line.startsWith("  ") ? line.slice(2) : line}`));
    }
  }
  return [meta, fields, body.length];
}

/** FIELD_LINE_RE.match(line)：从行首起最短的一段非空白之后紧跟半角或全角冒号，再可选一个空格或制表符；交回 [字段名, 其余]。 */
function fieldLine(line: string): [string, string] | null {
  const chars = codePoints(line);
  for (let at = 1; at < chars.length; at += 1) {
    if (isSpace(chars[at - 1] as string)) return null;
    if (chars[at] === ":" || chars[at] === "：") {
      const rest = chars.slice(at + 1);
      return [chars.slice(0, at).join(""), (rest[0] === " " || rest[0] === TAB ? rest.slice(1) : rest).join("")];
    }
  }
  return null;
}

/** str.strip(LF)：只去两端的换行。 */
function stripLf(text: string): string {
  let start = 0;
  let end = text.length;
  while (start < end && text[start] === LF) start += 1;
  while (end > start && text[end - 1] === LF) end -= 1;
  return text.slice(start, end);
}

/** RETURN_SEP_RE.split(value) 去掉空段：分隔是顿号、全角逗号、逗号、斜杠与 Python 的空白（可以连着几个）。 */
export function splitReturnNames(value: string): string[] {
  const names: string[] = [];
  let current = "";
  for (const char of value) {
    if (char === "、" || char === "，" || char === "," || char === "/" || isSpace(char)) {
      if (current) names.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  if (current) names.push(current);
  return names;
}

const hasOwn = (record: object, key: string): boolean => Object.prototype.hasOwnProperty.call(record, key);

/** 形状校验（不看状态）：头部齐全、类型与发信人相符、正文六个字段都在、不超过 40 行。 */
export function letterErrors(meta: Meta, fields: ReadonlyMap<string, PyValue>, bodyLines: number): string[] {
  const errors: string[] = [];
  for (const key of ["from", "to", "task-id", "in-reply-to", "type"]) if (!meta.get(key)) errors.push(`头部缺 ${key}`);
  const sender = meta.get("from") ?? "";
  const kind = meta.get("type") ?? "";
  const allowed: readonly string[] = sender === OWNER ? OWNER_TYPES : sender === COORDINATOR ? COORDINATOR_TYPES
    : sender === KERNEL ? [...KERNEL_TYPES, ...ROUTED_TYPES] : WORKERS.includes(sender) ? WORKER_TYPES : [];
  if (!allowed.length) errors.push(`发信人 ${sender} 不在名册里`);
  else if (!allowed.includes(kind)) errors.push(`${sender} 不能发 ${kind || "空类型"}（可以发：${allowed.join(" | ")}）`);
  const receiver = meta.get("to") ?? "";
  if (receiver && !hasOwn(ROSTER, receiver) && receiver !== OWNER) errors.push(`收信人 ${receiver} 不在名册里`);
  const [main, suffix] = stageOf(meta.get("task-id") ?? "");
  if (meta.get("task-id") && main === null) errors.push(`task-id ${meta.get("task-id")} 不是主任务号（T001）或阶段任务（T001-1-plan）`);
  for (const key of FIELDS) if (!pyStrip(pyStrValue(fields.get(key) ?? ""))) errors.push(`正文缺“${key}”（没有就写“无”）`);
  if (bodyLines > MAX_BODY_LINES) errors.push(`正文 ${bodyLines} 行，超过 ${MAX_BODY_LINES} 行：细节放进 report.md`);
  if (sender === "audit-sonnet" && kind === "交付") {
    const verdict = fields.get("结论");
    if (typeof verdict !== "string" || !(VERDICTS as readonly string[]).includes(verdict)) {
      errors.push("审核端的交付要写“结论: 通过”或“结论: 返工”");
    } else if (verdict === "返工") {
      const names = splitReturnNames(splitArgument(fields.get("退回")));
      const targets = Object.keys(RETURN_TARGETS);
      if (!names.length || names.some((name) => !hasOwn(RETURN_TARGETS, name))) {
        errors.push(`返工要写“退回: ${targets.join(" | ")}”之一，几个对象用“、”隔开`);
      } else if (suffix === "4-audit-pre" && names.some((name) => !["1-plan", "2-contract", "3-gate-pre"].includes(RETURN_TARGETS[name] as string))) {
        errors.push("一审只能退回规划端、合同端或门禁端（还没有执行）");
      }
      const blockers = pyStrip(pyStrValue(fields.get("阻塞项") ?? ""));
      if (blockers === "" || blockers === "无") errors.push("返工要写“阻塞项”：逐条列出必须改的问题（只列会导致打回的）");
    }
  }
  return errors;
}

/** RETURN_SEP_RE.split(fields.get("退回") or "") 的参数：假值换成空串，其余必须是字符串（Python 的 re.split 不收别的）。 */
function splitArgument(value: PyValue | undefined): string {
  if (value === undefined || value === null || value === false || value === "" || value === 0n || value === 0) return "";
  if (typeof value === "string") return value;
  if ((Array.isArray(value) && !value.length) || (value instanceof Map && !value.size)) return "";
  throw new PyCrash("TypeError", `expected string or bytes-like object, got '${pyTypeName(value)}'`);
}
