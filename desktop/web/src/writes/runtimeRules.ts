// 登记运行时表单的命令字段解析与本地校验（合同第七节）：与服务侧 validCommand 同一条规则
// （非空数组、每项非空、不超过 1024 码点、不含控制字符），不强制绝对路径——内核才判绝对路径与疑似凭据。
// 控制字符按 C0（U+0000–U+001F）与 DEL（U+007F）算，与服务的 cleanText 一致。

const MAX_ITEM_CODE_POINTS = 1024;
const CONTROL_RE = /[\u0000-\u001f\u007f]/u;

/** 解析结果：value 为 undefined 表示命令留空（不传 command 这个键）；ok 为假表示这段文本不合法。 */
export type CommandParse = { ok: true; value: string[] | undefined } | { ok: false };

/** 空串（只有空白也算留空）→ 不传 command；否则 JSON.parse 出来必须是非空字符串数组，逐项过服务侧同款规则。 */
export function parseCommand(text: string): CommandParse {
  if (text.trim() === '') return { ok: true, value: undefined };
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { ok: false };
  }
  if (!Array.isArray(parsed) || parsed.length === 0) return { ok: false };
  const out: string[] = [];
  for (const item of parsed) {
    if (typeof item !== 'string') return { ok: false };
    if (item === '') return { ok: false };
    if (Array.from(item).length > MAX_ITEM_CODE_POINTS) return { ok: false };
    if (CONTROL_RE.test(item)) return { ok: false };
    out.push(item);
  }
  return { ok: true, value: out };
}
