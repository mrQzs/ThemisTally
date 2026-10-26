// codekit/protocols.py 里插件管理用到的 strict_json_loads（迁移第 ③e 片：插件的 manifest 与锁）。只移植这一个函数与
// ProtocolError；kit_plugins 把 str(exc) 写进输出，ProtocolError 的 str 就是错误码，所以要对上的是“报哪个码”。
// 次序照 Python：长度 → BOM → UTF-8 → 文法（json.loads，文法错误与解码器递归超限各报一个码）→ 解析成功之后按文档
// 顺序遍历，报遇到的第一处：嵌套深度、键里的孤立代理项、重复键、非有限数、整数范围、值里的孤立代理项。
import { PyUnicodeDecodeError, pyDecodeUtf8 } from "./pyio.ts";
import { type JsonBuilder, type PyDict, PyJsonError, type PyValue, loadsWith } from "./pyjson.ts";

export const DEFAULT_MAX_BYTES = 1_048_576;
export const DEFAULT_MAX_DEPTH = 64;
const MAX_SAFE_INTEGER = 2n ** 53n - 1n;

/** codekit.protocols.ProtocolError（ValueError 的子类）：str(exc) 就是错误码。 */
export class ProtocolError extends Error {
  override readonly name = "ProtocolError";
  readonly code: string;
  constructor(code: string) {
    super(code);
    this.code = code;
  }
}

/** 解析出来、还没检查的值：对象保留全部成员对（重复键要等遍历时按文档顺序报），坏数先记下错误码。 */
type Node =
  | { readonly t: "pairs"; readonly v: [string, Node][] }
  | { readonly t: "list"; readonly v: Node[] }
  | { readonly t: "str"; readonly v: string }
  | { readonly t: "value"; readonly v: PyValue }
  | { readonly t: "bad"; readonly code: string };

/** object_pairs_hook、parse_constant、parse_float、parse_int 四个钩子：坏数不在解析时抛，留给遍历带着位置报。 */
const STRICT: JsonBuilder<Node> = {
  object: (pairs) => ({ t: "pairs", v: pairs }),
  array: (items) => ({ t: "list", v: items }),
  string: (value) => ({ t: "str", v: value }),
  literal: (value) => ({ t: "value", v: value }),
  constant: () => ({ t: "bad", code: "E_JSON_NON_FINITE" }),
  number(raw, isFloat) {
    if (isFloat) {
      const value = Number(raw);
      return Number.isFinite(value) ? { t: "value", v: value } : { t: "bad", code: "E_JSON_NON_FINITE" };
    }
    // 先按位数判定，不做超长整数转换
    if ((raw.startsWith("-") ? raw.length - 1 : raw.length) > 16) return { t: "bad", code: "E_INTEGER_RANGE" };
    const value = BigInt(raw);
    return (value < 0n ? -value : value) > MAX_SAFE_INTEGER ? { t: "bad", code: "E_INTEGER_RANGE" } : { t: "value", v: value };
  },
};

/** 孤立的代理项（Python 的 str 里单独的 U+D800–U+DFFF；成对的已经由解析器拼成一个码点）。 */
const LONE_SURROGATE = /\p{Cs}/u;

function materialize(node: Node, level: number, maxDepth: number): PyValue {
  switch (node.t) {
    case "bad":
      throw new ProtocolError(node.code);
    case "str":
      if (LONE_SURROGATE.test(node.v)) throw new ProtocolError("E_JSON_UNICODE");
      return node.v;
    case "value":
      return node.v;
    case "list":
      if (level + 1 > maxDepth) throw new ProtocolError("E_JSON_LIMIT");
      return node.v.map((item) => materialize(item, level + 1, maxDepth));
    case "pairs": {
      if (level + 1 > maxDepth) throw new ProtocolError("E_JSON_LIMIT");
      const out: PyDict = new Map();
      for (const [key, item] of node.v) {
        if (LONE_SURROGATE.test(key)) throw new ProtocolError("E_JSON_UNICODE");
        if (out.has(key)) throw new ProtocolError("E_JSON_DUPLICATE_KEY");
        out.set(key, materialize(item, level + 1, maxDepth));
      }
      return out;
    }
  }
}

/** codekit.protocols.strict_json_loads(raw)：严格解析 JSON 字节，不合格时抛 ProtocolError。 */
export function strictJsonLoads(raw: Uint8Array, maxBytes = DEFAULT_MAX_BYTES, maxDepth = DEFAULT_MAX_DEPTH): PyValue {
  if (raw.length < 1 || raw.length > maxBytes) throw new ProtocolError("E_JSON_LIMIT");
  if (raw[0] === 0xef && raw[1] === 0xbb && raw[2] === 0xbf) throw new ProtocolError("E_JSON_BOM");
  let text: string;
  try {
    text = pyDecodeUtf8(raw);
  } catch (error) {
    if (error instanceof PyUnicodeDecodeError) throw new ProtocolError("E_JSON_ENCODING");
    throw error;
  }
  let tree: Node;
  try {
    tree = loadsWith(text, STRICT);
  } catch (error) {
    if (error instanceof PyJsonError) throw new ProtocolError(error.kind === "RecursionError" ? "E_JSON_LIMIT" : "E_JSON_SYNTAX");
    throw error;
  }
  return materialize(tree, 0, maxDepth);
}
