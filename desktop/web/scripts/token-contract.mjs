#!/usr/bin/env node
// W4 契约检查：确保 src 下所有 --tt-* 变量都已在令牌文件定义，且没有写死的颜色。
// 零依赖，Node 运行。用法：node scripts/token-contract.mjs --src <目录> --tokens <文件>
// 输出每条违规一行「路径:行号: 规则: 片段」；有违规退出 1，无违规退出 0；路径不存在以非 0 退出。

import { existsSync, statSync, readFileSync, readdirSync } from 'node:fs';
import { resolve, relative, join, extname } from 'node:path';

const SCAN_EXTS = ['.css', '.ts', '.tsx'];

// 148 个 CSS 命名颜色（不含 transparent / currentColor / 全局关键字 / 系统颜色，这些单独放行）。
const NAMED_COLORS = [
  'aliceblue', 'antiquewhite', 'aqua', 'aquamarine', 'azure', 'beige', 'bisque', 'black',
  'blanchedalmond', 'blue', 'blueviolet', 'brown', 'burlywood', 'cadetblue', 'chartreuse',
  'chocolate', 'coral', 'cornflowerblue', 'cornsilk', 'crimson', 'cyan', 'darkblue', 'darkcyan',
  'darkgoldenrod', 'darkgray', 'darkgreen', 'darkgrey', 'darkkhaki', 'darkmagenta',
  'darkolivegreen', 'darkorange', 'darkorchid', 'darkred', 'darksalmon', 'darkseagreen',
  'darkslateblue', 'darkslategray', 'darkslategrey', 'darkturquoise', 'darkviolet', 'deeppink',
  'deepskyblue', 'dimgray', 'dimgrey', 'dodgerblue', 'firebrick', 'floralwhite', 'forestgreen',
  'fuchsia', 'gainsboro', 'ghostwhite', 'gold', 'goldenrod', 'gray', 'green', 'greenyellow',
  'grey', 'honeydew', 'hotpink', 'indianred', 'indigo', 'ivory', 'khaki', 'lavender',
  'lavenderblush', 'lawngreen', 'lemonchiffon', 'lightblue', 'lightcoral', 'lightcyan',
  'lightgoldenrodyellow', 'lightgray', 'lightgreen', 'lightgrey', 'lightpink', 'lightsalmon',
  'lightseagreen', 'lightskyblue', 'lightslategray', 'lightslategrey', 'lightsteelblue',
  'lightyellow', 'lime', 'limegreen', 'linen', 'magenta', 'maroon', 'mediumaquamarine',
  'mediumblue', 'mediumorchid', 'mediumpurple', 'mediumseagreen', 'mediumslateblue',
  'mediumspringgreen', 'mediumturquoise', 'mediumvioletred', 'midnightblue', 'mintcream',
  'mistyrose', 'moccasin', 'navajowhite', 'navy', 'oldlace', 'olive', 'olivedrab', 'orange',
  'orangered', 'orchid', 'palegoldenrod', 'palegreen', 'paleturquoise', 'palevioletred',
  'papayawhip', 'peachpuff', 'peru', 'pink', 'plum', 'powderblue', 'purple', 'rebeccapurple',
  'red', 'rosybrown', 'royalblue', 'saddlebrown', 'salmon', 'sandybrown', 'seagreen', 'seashell',
  'sienna', 'silver', 'skyblue', 'slateblue', 'slategray', 'slategrey', 'snow', 'springgreen',
  'steelblue', 'tan', 'teal', 'thistle', 'tomato', 'turquoise', 'violet', 'wheat', 'white',
  'whitesmoke', 'yellow', 'yellowgreen',
];

const NAMED_COLOR_RE = new RegExp('\\b(?:' + NAMED_COLORS.join('|') + ')\\b', 'i');
const HEX_RE = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/g;
// 函数名与括号之间只认空格与制表符：整份文本扫描时 \s 会跨行，“a color⏎(any)”这类文字会被误报，片段里还带换行。
const COLOR_FUNC_RE = /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/gi;
const TT_TOKEN_RE = /--tt-[a-zA-Z0-9_-]+/g;
const TT_DECL_RE = /--tt-[a-zA-Z0-9_-]+(?=\s*:)/g;

// 颜色类属性：color、各 -color、以及承载颜色的简写属性。
function isColorProp(name) {
  const n = name.toLowerCase();
  if (n === 'color' || n.endsWith('color')) return true;
  if (
    n === 'background' || n === 'border' || n === 'outline' ||
    n === 'box-shadow' || n === 'boxshadow' || n === 'fill' || n === 'stroke' ||
    n === 'text-decoration' || n === 'textdecoration'
  ) return true;
  if (/^border-(top|right|bottom|left)(-color)?$/.test(n)) return true;
  if (/^border(top|right|bottom|left)(color)?$/.test(n)) return true; // camelCase：borderTop / borderTopColor
  return false;
}

function stripBlockComments(text) {
  // 去掉 /* */ 注释，但保留换行以维持行号。
  return text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
}

function walk(dir, out) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue;
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walk(p, out);
    else if (SCAN_EXTS.includes(extname(entry.name))) out.push(p);
  }
  return out;
}

function parseArgs(argv) {
  const args = { src: 'src', tokens: 'src/styles/tokens.css' };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--src') args.src = argv[(i += 1)];
    else if (a === '--tokens') args.tokens = argv[(i += 1)];
    else if (a.startsWith('--src=')) args.src = a.slice('--src='.length);
    else if (a.startsWith('--tokens=')) args.tokens = a.slice('--tokens='.length);
    else if (a === '--help' || a === '-h') args.help = true;
    else args.unknown = (args.unknown || []).concat(a);
  }
  return args;
}

function collectDefined(tokensPath) {
  const text = stripBlockComments(readFileSync(tokensPath, 'utf8'));
  const defined = new Set();
  let m;
  TT_DECL_RE.lastIndex = 0;
  while ((m = TT_DECL_RE.exec(text)) !== null) defined.add(m[0]);
  return defined;
}

// 取值里的自定义属性名（--tt-gray-1 之类）换成等长空白：名字里的 gray / navy / gold 不是命名颜色；
// var() 回退值里的命名颜色照样判（var(--tt-a, red) 仍是写死颜色）。
function maskCustomProps(value) {
  return value.replace(/--[A-Za-z0-9_-]+/g, (m) => ' '.repeat(m.length));
}

// 整份文本扫描：声明与 style={{…}} 对象都可能跨行，按偏移量换算行号。
// push(offset, phase, rule, snippet)：phase 决定同一行里的输出顺序（十六进制、颜色函数、命名颜色、变量）。
function scanColorLiterals(text, push) {
  HEX_RE.lastIndex = 0;
  let h;
  while ((h = HEX_RE.exec(text)) !== null) push(h.index, 0, '写死颜色', h[0]);
  COLOR_FUNC_RE.lastIndex = 0;
  let c;
  while ((c = COLOR_FUNC_RE.exec(text)) !== null) push(c.index, 1, '写死颜色', c[0]);
}

function scanCssNamedColors(text, push) {
  // 规则 2：命名颜色，仅当作为颜色类属性的取值。声明只出现在 {、;、} 或文件开头之后：
  // 选择器里的伪类（.btn-color:hover,⏎.tag-red {）不是声明。
  const declRe = /(?:^|[{};])\s*([a-zA-Z-]+)\s*:\s*([^;{}]+)/g;
  let d;
  while ((d = declRe.exec(text)) !== null) {
    if (!isColorProp(d[1])) continue;
    const nm = NAMED_COLOR_RE.exec(maskCustomProps(d[2]));
    if (nm) push(d.index + d[0].length - d[2].length + nm.index, 2, '写死颜色', nm[0]);
  }
}

function scanTsxNamedColors(text, push) {
  // 规则 2：命名颜色，只在 style={{ ... }} 对象里、且键为颜色类属性时判定。
  const styleRe = /style=\{\{([^}]*)\}\}/g;
  let s;
  while ((s = styleRe.exec(text)) !== null) {
    const body = s.index + 'style={{'.length;
    const pairRe = /([A-Za-z_$][\w$]*)\s*:\s*(['"])([^'"]*)\2/g;
    let p;
    while ((p = pairRe.exec(s[1])) !== null) {
      if (!isColorProp(p[1])) continue;
      const nm = NAMED_COLOR_RE.exec(maskCustomProps(p[3]));
      if (nm) push(body + p.index + p[0].length - 1 - p[3].length + nm.index, 2, '写死颜色', nm[0]);
    }
  }
}

function scanVariables(text, defined, isCss, push) {
  // 规则 1：未定义变量；CSS 里 --tt-x: 的声明不论令牌里有没有定义都算违规（在组件里自行定义）。
  let start = 0;
  for (const line of text.split('\n')) {
    TT_TOKEN_RE.lastIndex = 0;
    const seen = new Set();
    let m;
    while ((m = TT_TOKEN_RE.exec(line)) !== null) {
      const declared = isCss && /^\s*:/.test(line.slice(m.index + m[0].length));
      if ((defined.has(m[0]) && !declared) || seen.has(m[0])) continue;
      seen.add(m[0]);
      push(start + m.index, 3, '未定义变量', m[0]);
    }
    start += line.length + 1;
  }
}

function lineStarts(text) {
  const starts = [0];
  for (let i = 0; i < text.length; i += 1) if (text[i] === '\n') starts.push(i + 1);
  return starts;
}

function lineOf(starts, offset) {
  let lo = 0;
  let hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= offset) lo = mid;
    else hi = mid - 1;
  }
  return lo + 1;
}

function scanFile(text, defined, isTsx) {
  const starts = lineStarts(text);
  const found = [];
  const push = (offset, phase, rule, snippet) => found.push({ line: lineOf(starts, offset), phase, offset, rule, snippet });
  scanColorLiterals(text, push);
  if (isTsx) scanTsxNamedColors(text, push);
  else scanCssNamedColors(text, push);
  scanVariables(text, defined, !isTsx, push);
  return found.sort((a, b) => a.line - b.line || a.phase - b.phase || a.offset - b.offset);
}

function main(argv) {
  const args = parseArgs(argv);
  if (args.help) {
    process.stdout.write(
      '用法：node scripts/token-contract.mjs [--src <目录>] [--tokens <文件>]\n' +
      '缺省 --src src --tokens src/styles/tokens.css\n',
    );
    return 0;
  }

  const srcPath = resolve(process.cwd(), args.src);
  const tokensPath = resolve(process.cwd(), args.tokens);

  if (!existsSync(tokensPath) || !statSync(tokensPath).isFile()) {
    process.stderr.write(`契约检查：令牌文件不存在或不是文件：${args.tokens}\n`);
    return 2;
  }
  if (!existsSync(srcPath) || !statSync(srcPath).isDirectory()) {
    process.stderr.write(`契约检查：源码目录不存在或不是目录：${args.src}\n`);
    return 2;
  }

  const defined = collectDefined(tokensPath);
  const files = walk(srcPath, []).filter((f) => {
    if (resolve(f) === tokensPath) return false; // 排除令牌文件自身
    if (extname(f) === '.css' || extname(f) === '.ts' || extname(f) === '.tsx') {
      return !f.split(/[\\/]/).pop().includes('.test.'); // 排除 *.test.*
    }
    return false;
  });

  const violations = [];
  for (const file of files) {
    const isTsx = extname(file) === '.tsx' || extname(file) === '.ts';
    const rel = relative(process.cwd(), file).split('\\').join('/');
    const text = stripBlockComments(readFileSync(file, 'utf8'));
    for (const v of scanFile(text, defined, isTsx)) violations.push(`${rel}:${v.line}: ${v.rule}: ${v.snippet}`);
  }

  if (violations.length > 0) {
    for (const v of violations) process.stdout.write(`${v}\n`);
    process.stderr.write(`契约检查：发现 ${violations.length} 处违规。\n`);
    return 1;
  }
  process.stdout.write('契约检查：通过，无违规。\n');
  return 0;
}

process.exit(main(process.argv.slice(2)));
