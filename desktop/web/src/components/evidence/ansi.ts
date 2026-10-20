// 证据文字里的 ANSI 转义序列清理（UI 文档 7.12：转义序列去掉，不解释颜色）。
// 纯函数：只去序列，不动普通文字；正则不用嵌套量词，256 KiB 的病态输入也能线性时间完成。

const ESC = '\u001b';
const BEL = '\u0007';

// OSC：ESC ] 起，到 BEL 或到 ESC 加反斜杠为止（窗口标题、超链接等）。
const OSC_RE = new RegExp(ESC + '\\][^' + BEL + ESC + ']*(?:' + BEL + '|' + ESC + '\\\\)', 'g');
// CSI：ESC [ 或 U+009B 起，参数字节 0x30–0x3F、中间字节 0x20–0x2F、结束字节 0x40–0x7E。
const CSI_RE = new RegExp('(?:' + ESC + '\\[|\\u009b)[\\u0030-\\u003f]*[\\u0020-\\u002f]*[\\u0040-\\u007e]', 'g');
// 其余 ESC 双字符序列（ESC 加一个 0x20–0x7E 的字符）。
const ESC_PAIR_RE = new RegExp(ESC + '[\\u0020-\\u007e]', 'g');
// 最后剩下的 ESC 与 U+009B 一律去掉。
const LEFTOVER_RE = new RegExp('[' + ESC + '\\u009b]', 'g');

/** 去掉 text 里的 ANSI 转义序列；普通文字（含没有 ESC 的「[31m」）原样保留。 */
export function stripAnsi(text: string): string {
  if (text.indexOf(ESC) < 0 && text.indexOf('\u009b') < 0) return text;
  return text
    .replace(OSC_RE, '')
    .replace(CSI_RE, '')
    .replace(ESC_PAIR_RE, '')
    .replace(LEFTOVER_RE, '');
}
