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
const COLOR_FUNC_RE = /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)\s*\(/gi;
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

function scanCssLine(line, defined, push) {
  // 规则 2：十六进制与颜色函数（任意取值均判）。
  HEX_RE.lastIndex = 0;
  let h;
  while ((h = HEX_RE.exec(line)) !== null) push('写死颜色', h[0]);
  COLOR_FUNC_RE.lastIndex = 0;
  let c;
  while ((c = COLOR_FUNC_RE.exec(line)) !== null) push('写死颜色', c[0]);

  // 规则 2：命名颜色，仅当作为颜色类属性的取值。
  const declRe = /([a-zA-Z-]+)\s*:\s*([^;{}]+)/g;
  let d;
  while ((d = declRe.exec(line)) !== null) {
    if (!isColorProp(d[1])) continue;
    const nm = NAMED_COLOR_RE.exec(d[2]);
    if (nm) push('写死颜色', nm[0]);
  }

  // 规则 1：未定义变量。
  scanUndefined(line, defined, push);
}

function scanTsxLine(line, defined, push) {
  // 规则 2：十六进制（字符串里同样识别）与颜色函数。
  HEX_RE.lastIndex = 0;
  let h;
  while ((h = HEX_RE.exec(line)) !== null) push('写死颜色', h[0]);
  COLOR_FUNC_RE.lastIndex = 0;
  let c;
  while ((c = COLOR_FUNC_RE.exec(line)) !== null) push('写死颜色', c[0]);

  // 规则 2：命名颜色，只在 style={{ ... }} 对象里、且键为颜色类属性时判定。
  const styleRe = /style=\{\{([^}]*)\}\}/g;
  let s;
  while ((s = styleRe.exec(line)) !== null) {
    const pairRe = /([A-Za-z_$][\w$]*)\s*:\s*(['"])([^'"]*)\2/g;
    let p;
    while ((p = pairRe.exec(s[1])) !== null) {
      if (!isColorProp(p[1])) continue;
      const nm = NAMED_COLOR_RE.exec(p[3]);
      if (nm) push('写死颜色', nm[0]);
    }
  }

  // 规则 1：未定义变量。
  scanUndefined(line, defined, push);
}

function scanUndefined(line, defined, push) {
  TT_TOKEN_RE.lastIndex = 0;
  const seen = new Set();
  let m;
  while ((m = TT_TOKEN_RE.exec(line)) !== null) {
    if (defined.has(m[0]) || seen.has(m[0])) continue;
    seen.add(m[0]);
    push('未定义变量', m[0]);
  }
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
    const lines = stripBlockComments(readFileSync(file, 'utf8')).split(/\r?\n/);
    lines.forEach((line, idx) => {
      const lineNo = idx + 1;
      const push = (rule, snippet) => violations.push(`${rel}:${lineNo}: ${rule}: ${snippet}`);
      if (isTsx) scanTsxLine(line, defined, push);
      else scanCssLine(line, defined, push);
    });
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
