// 疑似凭据的检测与脱敏（迁移第 ① 步 secrets）：逐条照现行 Python 实现，结果会进证据，必须逐字一致（计划 §3.4）。
//   pi_dispatch：redact_secrets、redact_json（含白名单）、redact_obj、redact_tokens、secret_like_paths、_token_shaped、
//                strip_ansi、ENV_NAME_RE、TASK_ID_RE
//   codekit/secrets：looks_like_secret（凭据库本身挪到第 ③ 步）
//   codekit/decisions：normalize、is_sensitive、redact、redact_state
// 正则一律用 pyre.ts 的构件翻译（Python 的 \w、\b、\s、\d、re.I、$ 与 JS 不同，见 pyre.ts 文件头）；替换全部用函数，
// 不用替换串（JS 的替换串里 $ 有特殊含义）；长度与切片按码点。
import { floatRepr, intRepr, type PyDict, type PyKey, type PyValue, dumps, PyJsonError, rawDecode } from "./pyjson.ts";
import {
  D,
  IGNORECASE_ALL,
  NOT_S,
  PY_END,
  S,
  W,
  WB,
  ci,
  codePoints,
  isCfOrCc,
  isDigitChar,
  isLower,
  isSpace,
  isUpper,
  pyIsPrintable,
  pyLen,
  pyNfkc,
  pyRegex,
  pyRstrip,
  pyStrip,
} from "./pyre.ts";
import { WORD } from "./pyunicode.ts";

const NUL = String.fromCharCode(0);
const REDACTED = "<redacted>";

/** Python 的 [\w.-]：\w 加上点与连字符。 */
const W_DOT_DASH = `${W.slice(0, -1)}.\\-]`;
void WORD;

// ---------------------------------------------------------------------------
// pi_dispatch 的规则
// ---------------------------------------------------------------------------

/** ANSI_RE = r"\x1b\[[0-9;?]*[A-Za-z]" */
const ANSI_RE = pyRegex("\\x1b\\[[0-9;?]*[A-Za-z]", true);
/** TASK_ID_RE = r"^[a-z0-9][a-z0-9-]{0,63}$"（match：末尾换行之前也算） */
export const TASK_ID_RE = pyRegex(`^[a-z0-9][a-z0-9-]{0,63}${PY_END}`);
/** ENV_NAME_RE = r"^[A-Za-z_][A-Za-z0-9_]{0,127}$" */
export const ENV_NAME_RE = pyRegex(`^[A-Za-z_][A-Za-z0-9_]{0,127}${PY_END}`);

/** _SECRET_KEY（re.I 下用）：键名像 api key、token、secret、password、credential。 */
const SECRET_KEY =
  `${W_DOT_DASH}*(?:${ci("api")}[ _-]?${ci("key")}|${ci("apikey")}|${ci("access")}[ _-]?${ci("key")}` +
  `|${ci("secret")}[ _-]?${ci("key")}|${ci("private")}[ _-]?${ci("key")}|${ci("auth")}[ _-]?${ci("token")}` +
  `|${ci("token")}|${ci("secret")}|${ci("password")}|${ci("passwd")}|${ci("credential")}|${ci("authorization")})${W_DOT_DASH}*`;
/** _SECRET_KEY_RE = re.compile(r"^%s$" % _SECRET_KEY, re.I) */
const SECRET_KEY_RE = pyRegex(`^${SECRET_KEY}${PY_END}`);
/** _SECRET_TOKEN_RE（re.I）：Bearer 令牌与常见前缀 */
const TOKEN_BODY = `[A-Za-z0-9._~+/=\\-${IGNORECASE_ALL}]`;
const TOKEN_TAIL = `[A-Za-z0-9_\\-${IGNORECASE_ALL}]`;
const SECRET_TOKEN_SOURCE =
  `${WB}${ci("bearer")}${S}+${TOKEN_BODY}{8,}` +
  `|${WB}(?:${ci("sk")}|${ci("pk")}|${ci("rk")}|${ci("ghp")}|${ci("gho")}|${ci("ghu")}|${ci("ghs")}|${ci("github_pat")}` +
  `|${ci("xox")}[aAbBpPrR])[-_]${TOKEN_TAIL}{8,}`;
const SECRET_TOKEN_RE = pyRegex(SECRET_TOKEN_SOURCE);
const SECRET_TOKEN_RE_G = pyRegex(SECRET_TOKEN_SOURCE, true);
/** _SECRET_PEM_RE：PEM 私钥整块；没有结束行时遮到结尾（\Z 即 JS 的 $） */
const SECRET_PEM_RE_G = pyRegex("-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[^]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)", true);
/** _SECRET_KV_RE（re.I）：疑似凭据的键后面的值遮到行尾，连同缩进的续行 */
const SECRET_KV_RE_G = pyRegex(
  `((?:\\\\*["'])?(?<!${W_DOT_DASH})${SECRET_KEY}(?:\\\\*["'])?[ \\t]*[:=][ \\t]*)([^\\n]*)(?:\\n[ \\t]+[^\\n]*)*`,
  true,
);
/** RELEASE_PATTERNS["api key"] */
const RELEASE_API_KEY_SOURCE =
  `${WB}(?:apikey_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}` +
  `|AIza[0-9A-Za-z_-]{35}|xox[abprs]-[A-Za-z0-9-]{10,})${WB}`;
const RELEASE_API_KEY_RE = pyRegex(RELEASE_API_KEY_SOURCE);
const RELEASE_API_KEY_RE_G = pyRegex(RELEASE_API_KEY_SOURCE, true);
/** _json_spans 的候选起点 */
const NUMBER_START = `-?${D}+(?:\\.${D}+)?(?:[eE][+-]?${D}+)?${S}*[,\\]]`;
const JSON_CANDIDATE_RE_G = pyRegex(
  `\\{(?=${S}*["}])|\\[(?=${S}*(?:[\\[{"\\]]|${NUMBER_START}|true${WB}|false${WB}|null${WB}))`,
  true,
);
const LONE_SURROGATE_RE_G = /[\uD800-\uDFFF]/gu;
const BLOCK_SCALAR_RE = pyRegex(`^[|>](?:[+-]?${D}?|${D}[+-])(?:${S}+#[^\\n]*)?$`);
const LEADING_QUOTE_RE = /^\\*(["'])/u;

/** strip_ansi */
export function stripAnsi(text: string): string {
  return text.replace(ANSI_RE, () => "");
}

/** _token_shaped：有凭据、令牌的形状。 */
export function tokenShaped(text: string): boolean {
  return RELEASE_API_KEY_RE.test(text) || SECRET_TOKEN_RE.test(text);
}

/** 键名像凭据（_SECRET_KEY_RE.match）。 */
export function secretKey(key: string): boolean {
  return SECRET_KEY_RE.test(key);
}

/** _value_ends_on_line：敏感值是否在本行完整结束。 */
function valueEndsOnLine(raw: string): boolean {
  const value = pyStrip(raw);
  const chars = codePoints(value);
  const first = chars[0] ?? "";
  const last = chars[chars.length - 1] ?? "";
  if (!value || "{[(".includes(first) || ",\\{[(:".includes(last) || BLOCK_SCALAR_RE.test(value)) return false;
  const quoted = LEADING_QUOTE_RE.exec(value);
  if (!quoted) return true;
  const quote = quoted[1] ?? '"';
  return pyRegex(`(?<!\\\\)${quote}`).test(value.slice(quoted[0].length));
}

function redactedName(out: PyDict): string {
  let name = REDACTED;
  let number = 2;
  while (out.has(name)) {
    name = `<redacted-${number}>`;
    number += 1;
  }
  return name;
}

/** _redact_json：按键名的结构脱敏。 */
function redactJsonPlain(value: PyValue, sensitive = false): PyValue {
  if (value instanceof Map) {
    const out: PyDict = new Map();
    for (const [key, item] of value) {
      const name = typeof key === "string" && tokenShaped(key) ? redactedName(out) : key;
      out.set(name, redactJsonPlain(item, sensitive || (typeof key === "string" && secretKey(key))));
    }
    return out;
  }
  if (Array.isArray(value)) return value.map((item) => redactJsonPlain(item, sensitive));
  if (typeof value === "string") return sensitive && value ? REDACTED : redactSecrets(value);
  return value;
}

/** _json_spans：文本里嵌着的 JSON 对象或数组 → [起点, 终点, 按结构脱敏后重新写出的 JSON]（下标按 UTF-16）。 */
function jsonSpans(text: string): [number, number, string][] {
  const spans: [number, number, string][] = [];
  let covered = 0;
  for (const candidate of text.matchAll(JSON_CANDIDATE_RE_G)) {
    const start = candidate.index ?? 0;
    if (start < covered) continue;
    let rendered: string;
    let end: number;
    try {
      const decoded = rawDecode(text, start);
      if (!(decoded.value instanceof Map) && !Array.isArray(decoded.value)) continue;
      // 一律按脱敏后的结构重新写出：重复的键解码后只剩最后一个值，原文里前面的值可能就是凭据
      rendered = dumps(redactJsonPlain(decoded.value), { ensureAscii: false }).replace(
        LONE_SURROGATE_RE_G,
        (char) => `${String.fromCharCode(92)}u${(char.codePointAt(0) ?? 0).toString(16).padStart(4, "0")}`,
      );
      end = decoded.endUnits;
    } catch (error) {
      if (error instanceof PyJsonError) continue; // ValueError、RecursionError：交给文本规则
      throw error;
    }
    spans.push([start, end, rendered]);
    covered = end;
  }
  return spans;
}

/** redact_secrets：把疑似凭据替换成 <redacted>。 */
export function redactSecrets(input: string): string {
  let text = stripAnsi(input).split(NUL).join("");
  const saved: string[] = [];
  let pieces = "";
  let last = 0;
  for (const [start, end, rendered] of jsonSpans(text)) {
    pieces += text.slice(last, start) + NUL + String(saved.length) + NUL;
    saved.push(rendered);
    last = end;
  }
  text = pieces + text.slice(last);
  text = text.replace(SECRET_PEM_RE_G, () => REDACTED);
  text = text.replace(SECRET_TOKEN_RE_G, () => REDACTED);
  text = text.replace(RELEASE_API_KEY_RE_G, () => REDACTED);
  let out = "";
  last = 0;
  for (const match of text.matchAll(SECRET_KV_RE_G)) {
    out += text.slice(last, match.index) + (match[1] ?? "") + REDACTED;
    last = (match.index ?? 0) + match[0].length;
    if (!valueEndsOnLine(match[2] ?? "")) {
      last = text.length; // 值在本行确定不了结束：遮蔽这条输出的其余部分
      break;
    }
  }
  text = out + text.slice(last);
  return text.replace(new RegExp(`${NUL}([0-9]+)${NUL}`, "gu"), (_whole, index: string) => saved[Number(index)] ?? "");
}

/** redact_tokens：只遮令牌形状，其余原样。 */
export function redactTokens(text: string): string {
  return text.replace(SECRET_TOKEN_RE_G, () => REDACTED).replace(RELEASE_API_KEY_RE_G, () => REDACTED);
}

/** redact_obj：结构里的每个字符串过 redact_secrets（不看键名）。 */
export function redactObj(value: PyValue): PyValue {
  if (typeof value === "string") return redactSecrets(value);
  if (Array.isArray(value)) return value.map(redactObj);
  if (value instanceof Map) return new Map([...value].map(([key, item]) => [key, redactObj(item)]));
  return value;
}

/** redact_json 的白名单：JSON 路径（键名、"*"、"[键=值]"）→ 校验函数。 */
export type AllowList = readonly (readonly [readonly string[], (value: PyValue) => boolean])[];

type Active = readonly [readonly string[], number, (value: PyValue) => boolean];

function allowStep(segment: string, step: PyKey | number, element: PyValue): boolean {
  if (segment === "*") return true;
  if (segment.startsWith("[") && segment.endsWith("]") && segment.includes("=")) {
    const inner = segment.slice(1, -1);
    const at = inner.indexOf("=");
    const key = inner.slice(0, at);
    const want = inner.slice(at + 1);
    return typeof step === "number" && element instanceof Map && element.get(key) === want;
  }
  return typeof step === "string" && step === segment;
}

function redactJsonAllowing(value: PyValue, sensitive: boolean, active: readonly Active[]): PyValue {
  const checks = active.filter(([path, depth]) => depth === path.length).map(([, , check]) => check);
  if (checks.length > 0) return checks.every((check) => check(value)) ? value : REDACTED;
  const pending = active.filter(([path, depth]) => depth < path.length);
  if (value instanceof Map) {
    const out: PyDict = new Map();
    for (const [key, item] of value) {
      const name = typeof key === "string" && tokenShaped(key) ? redactedName(out) : key;
      const follow = pending
        .filter(([path, depth]) => allowStep(path[depth] ?? "", key, item))
        .map(([path, depth, check]) => [path, depth + 1, check] as const);
      out.set(name, redactJsonAllowing(item, sensitive || (typeof key === "string" && secretKey(key)), follow));
    }
    return out;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) =>
      redactJsonAllowing(
        item,
        sensitive,
        pending.filter(([path, depth]) => allowStep(path[depth] ?? "", index, item)).map(([path, depth, check]) => [path, depth + 1, check] as const),
      ),
    );
  }
  if (typeof value === "string") return sensitive && value ? REDACTED : redactSecrets(value);
  return value;
}

/** redact_json：按键名的结构脱敏；allow 是路由登记的白名单。 */
export function redactJson(value: PyValue, allow?: AllowList): PyValue {
  if (!allow || allow.length === 0) return redactJsonPlain(value);
  return redactJsonAllowing(value, false, allow.map(([path, check]) => [path, 0, check] as const));
}

/** allow_env_name */
export function allowEnvName(value: PyValue): boolean {
  return typeof value === "string" && ENV_NAME_RE.test(value) && !tokenShaped(value);
}

/** allow_id */
export function allowId(value: PyValue): boolean {
  return typeof value === "string" && TASK_ID_RE.test(value) && !tokenShaped(value);
}

/** allow_enum：值相等且类型相同（int、float、bool、None、str 各算一种）。 */
export function allowEnum(...choices: PyValue[]): (value: PyValue) => boolean {
  const kind = (item: PyValue): string => (item === null ? "none" : typeof item);
  return (value) => choices.some((choice) => kind(choice) === kind(value) && choice === value);
}

/** SECRET_NAME_FIELDS：只放环境变量名、不放凭据值的字段路径。 */
export const SECRET_NAME_FIELDS: readonly (readonly string[])[] = [
  ["decisions", "api_key_env"],
  ["profiles", "*", "credential_env"],
  ["env_remove"],
  ["env_keep"],
];

/** secret_like_paths 里代替有令牌形状的键名的那一级。 */
export const SECRET_KEY_SHOWN = "（疑似凭据的键名）";

function secretNameField(path: readonly string[], value: PyValue): boolean {
  const matches = SECRET_NAME_FIELDS.some(
    (rule) => rule.length === path.length && rule.every((part, index) => part === "*" || part === path[index]),
  );
  if (!matches) return false;
  const names = Array.isArray(value) ? value : [value];
  return names.every((name) => typeof name === "string" && ENV_NAME_RE.test(name));
}

/** Python 的 str(key)。 */
export function pyStr(key: PyKey): string {
  if (typeof key === "string") return key;
  if (typeof key === "bigint") return intRepr(key);
  if (typeof key === "number") return floatRepr(key);
  if (key === true) return "True";
  if (key === false) return "False";
  return "None";
}

function emptyValue(item: PyValue): boolean {
  return item === null || item === "" || (Array.isArray(item) && item.length === 0) || (item instanceof Map && item.size === 0);
}

/** secret_like_paths：结构里疑似凭据的位置（键路径用点连接）。 */
export function secretLikePaths(value: PyValue, path: readonly string[] = []): string[] {
  const found: string[] = [];
  if (value instanceof Map) {
    for (const [key, item] of value) {
      if (tokenShaped(pyStr(key))) {
        found.push([...path, SECRET_KEY_SHOWN].join("."));
        continue;
      }
      const sub = [...path, pyStr(key)];
      if (secretKey(pyStr(key)) && !emptyValue(item) && !secretNameField(sub, item)) {
        found.push(sub.join("."));
        continue;
      }
      found.push(...secretLikePaths(item, sub));
    }
  } else if (Array.isArray(value)) {
    value.forEach((item, index) => found.push(...secretLikePaths(item, [...path, String(index)])));
  } else if (typeof value === "string" && tokenShaped(value)) {
    found.push(path.join(".") || "（顶层）");
  }
  return found;
}

// ---------------------------------------------------------------------------
// codekit/secrets.looks_like_secret
// ---------------------------------------------------------------------------

/** MAX_SECRET_CHARS */
export const MAX_SECRET_CHARS = 4096;

/** looks_like_secret：粘贴错误的廉价检查（非空、无空白、可打印、长度在 8 到上限之间，按码点）。 */
export function looksLikeSecret(value: PyValue): boolean {
  if (typeof value !== "string") return false;
  const stripped = pyStrip(value);
  const length = pyLen(stripped);
  return 8 <= length && length <= MAX_SECRET_CHARS && !codePoints(stripped).some(isSpace) && pyIsPrintable(stripped);
}

// ---------------------------------------------------------------------------
// codekit/decisions：出站边界的脱敏
// ---------------------------------------------------------------------------

const AZ_CI = `A-Za-z${IGNORECASE_ALL}`;
/** _SECRET_WORDS（(?i)） */
const SECRET_WORDS_RE = pyRegex(
  `(${ci("api")}[_ -]?${ci("key")}|${ci("access")}[_ -]?${ci("token")}|${ci("authorization")}${S}*:` +
    `|${ci("bearer")}${S}+[${AZ_CI}0-9._\\-]{8,}|${ci("password")}|${ci("passwd")}|${ci("client")}[_ -]?${ci("secret")}` +
    `|${ci("session")}[_ -]?${ci("cookie")}|${ci("private")}[_ -]?${ci("key")}|${ci("BEGIN")} [${AZ_CI} ]*${ci("PRIVATE")} ${ci("KEY")})`,
);
/** _SECRET_ASSIGNMENT（(?i)） */
const SECRET_ASSIGNMENT_SOURCE =
  `${WB}[${AZ_CI}][${AZ_CI}0-9]*(?:[_-][${AZ_CI}0-9]+)*[_-]` +
  `(?:${ci("SECRET")}|${ci("SECRET")}[_-]?${W}*${ci("KEY")}|${ci("API")}[_-]?${ci("KEY")}|${ci("KEY")}|${ci("TOKEN")}` +
  `|${ci("PASSWORD")}|${ci("PASSWD")}|${ci("CREDENTIAL")}${ci("S")}?|${ci("AUTH")})${WB}${S}*[:=]${S}*${NOT_S}*`;
const SECRET_ASSIGNMENT_RE = pyRegex(SECRET_ASSIGNMENT_SOURCE);
const SECRET_ASSIGNMENT_RE_G = pyRegex(SECRET_ASSIGNMENT_SOURCE, true);
/** _TOKEN_SHAPES */
const TOKEN_SHAPES_SOURCE =
  `${WB}(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|` +
  `AIza[0-9A-Za-z_-]{30,}|apikey_[A-Za-z0-9_]{20,}|eyJ[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{5,})${WB}`;
const TOKEN_SHAPES_RE = pyRegex(TOKEN_SHAPES_SOURCE);
const TOKEN_SHAPES_RE_G = pyRegex(TOKEN_SHAPES_SOURCE, true);
/** _EMAIL、_INTL_PHONE、_LONG_HEX、_HIGH_ENTROPY */
const EMAIL_RE_G = pyRegex(`${WB}[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}${WB}`, true);
const PHONE_SEP = `(?:${S}|[.\\-])`;
const INTL_PHONE_RE_G = pyRegex(`(?<!${D}|\\+)\\+${D}{1,3}${PHONE_SEP}?(?:${D}${PHONE_SEP}?){7,13}${D}(?!${D})`, true);
const LONG_HEX_RE_G = pyRegex(`${WB}[a-fA-F0-9]{40,}${WB}`, true);
const HIGH_ENTROPY_RE_G = pyRegex("(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/_-]{40,}={0,2}(?![A-Za-z0-9+/=_-])", true);

/** decisions.normalize：NFKC（与 Python 的 Unicode 版本一致，见 pyre.pyNfkc），再去掉 Cf、Cc 类别的字符（换行与 TAB 保留）。 */
export function normalize(text: string): string {
  return codePoints(pyNfkc(text))
    .filter((char) => !isCfOrCc(char) || char === "\n" || char === "\t")
    .join("");
}

/** decisions.is_sensitive */
export function isSensitive(text: string): boolean {
  const probe = normalize(text);
  return SECRET_WORDS_RE.test(probe) || SECRET_ASSIGNMENT_RE.test(probe) || TOKEN_SHAPES_RE.test(probe);
}

function maskCredential(run: string): string {
  const chars = codePoints(run);
  const mixed = chars.some(isUpper) && chars.some(isLower) && chars.some(isDigitChar);
  return mixed ? "[secret]" : run;
}

/** decisions.redact：遮令牌、赋值、长 hex、高熵串、邮箱与国际电话；过长时按码点取头尾。 */
export function decisionsRedact(text: string, limit = 4000): string {
  let out = normalize(text);
  out = out.replace(TOKEN_SHAPES_RE_G, () => "[secret]");
  out = out.replace(SECRET_ASSIGNMENT_RE_G, (whole) => `${pyRstrip(whole.split(/[:=]/u)[0] ?? "")}=[secret]`);
  out = out.replace(LONG_HEX_RE_G, () => "[hex]");
  out = out.replace(HIGH_ENTROPY_RE_G, (run) => maskCredential(run));
  out = out.replace(EMAIL_RE_G, () => "[email]");
  out = out.replace(INTL_PHONE_RE_G, () => "[phone]");
  const chars = codePoints(out);
  if (chars.length > limit) {
    const half = Math.floor(limit / 2);
    // Python 的 out[-half:]：half 为 0 时是整串
    const tail = half === 0 ? chars : chars.slice(chars.length - half);
    out = `${chars.slice(0, half).join("")}\n[...]\n${tail.join("")}`;
  }
  return out;
}

/** decisions.redact_state：递归脱敏每个字符串；返回（脱敏后的值, 改动过的字符串个数）。dict 的键转成 str。 */
export function redactState(value: PyValue, limit = 6000): [PyValue, number] {
  if (typeof value === "string") {
    const out = decisionsRedact(value, limit);
    return [out, out === value ? 0 : 1];
  }
  if (value instanceof Map) {
    const result: PyDict = new Map();
    let changed = 0;
    for (const [key, item] of value) {
      const [out, count] = redactState(item, limit);
      result.set(pyStr(key), out);
      changed += count;
    }
    return [result, changed];
  }
  if (Array.isArray(value)) {
    let changed = 0;
    const items = value.map((item) => {
      const [out, count] = redactState(item, limit);
      changed += count;
      return out;
    });
    return [items, changed];
  }
  return [value, 0];
}
