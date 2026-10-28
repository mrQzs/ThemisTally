// shlex.split(s)（posix=True，不认注释）的逐段移植（迁移第 ④ 步：合同里检查行的命令照它拆成 argv，报错原文进
// derive-json 的提示）。照 CPython 3.12 的 Lib/shlex.py：split 把 whitespace_split 设为真、commenters 设为空，没有
// punctuation_chars。这几个条件下 read_token 只剩四种状态：空白、单词、引号、转义；空白只认空格、制表符、回车、换行，
// 不是 str.isspace。字符按码点读（StringIO.read(1)）。
const WHITESPACE = new Set([" ", "\t", "\r", "\n"]);
const BACKSLASH = String.fromCharCode(92);

/** shlex.split 抛的 ValueError：message 就是 str(exc)。 */
export class ShlexError extends Error {
  override readonly name = "ValueError";
}

const isQuote = (char: string): boolean => char === "'" || char === '"';

/** shlex.split(s)：posix 模式拆参数；引号或转义没有收尾时抛 ShlexError。 */
export function shlexSplit(text: string): string[] {
  const chars = Array.from(text);
  let at = 0;
  let state: string | null = " ";
  const tokens: string[] = [];
  for (;;) {
    // read_token：每个记号重新开始，quoted 与 escapedstate 都在这里复位
    let quoted = false;
    let escapedstate = " ";
    let token = "";
    for (;;) {
      const next = at < chars.length ? (chars[at++] as string) : "";
      if (state === null) {
        token = "";
        break;
      }
      if (state === " ") {
        if (!next) {
          state = null;
          break;
        }
        if (WHITESPACE.has(next)) {
          if (token || quoted) break;
          continue;
        }
        if (next === BACKSLASH) {
          escapedstate = "a";
          state = next;
        } else if (isQuote(next)) {
          state = next;
        } else {
          // 单词字符与 whitespace_split 的其余字符一样：开始一个单词
          token = next;
          state = "a";
        }
      } else if (isQuote(state)) {
        quoted = true;
        if (!next) throw new ShlexError("No closing quotation");
        if (next === state) state = "a";
        else if (next === BACKSLASH && state === '"') {
          escapedstate = state;
          state = next;
        } else token += next;
      } else if (state === BACKSLASH) {
        if (!next) throw new ShlexError("No escaped character");
        // 引号里只有引号本身与反斜杠能转义，别的字符前的反斜杠原样留下
        if (isQuote(escapedstate) && next !== state && next !== escapedstate) token += state;
        token += next;
        state = escapedstate;
      } else {
        if (!next) {
          state = null;
          break;
        }
        if (WHITESPACE.has(next)) {
          state = " ";
          if (token || quoted) break;
          continue;
        }
        if (isQuote(next)) state = next;
        else if (next === BACKSLASH) {
          escapedstate = "a";
          state = next;
        } else token += next;
      }
    }
    // posix 下没有引号的空记号就是文件尾（None），迭代到此为止
    if (!quoted && token === "") return tokens;
    tokens.push(token);
  }
}

/** shlex.quote 的安全字符：re.ASCII 下的单词字符与 @%+=:,./-，其余（包括非 ASCII）都要加引号。 */
const SHLEX_SAFE = /^[A-Za-z0-9_@%+=:,./-]+$/u;

/** shlex.quote(s)：空串写成两个单引号；有不安全的字符时整体加单引号，单引号本身写成 '"'"'。 */
export function shlexQuote(text: string): string {
  if (!text) return "''";
  if (SHLEX_SAFE.test(text)) return text;
  return `'${text.replaceAll("'", `'"'"'`)}'`;
}
