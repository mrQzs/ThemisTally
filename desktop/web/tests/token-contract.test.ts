// W4 契约检查的测试：在临时目录造样本，覆盖合法写法通过、逐类违规失败、路径缺失报错。
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

// npm test 的 cwd 即 desktop/web，据此定位契约检查脚本。
const scriptPath = join(process.cwd(), 'scripts', 'token-contract.mjs');

let workDir: string;

beforeEach(() => {
  workDir = mkdtempSync(join(tmpdir(), 'tt-contract-'));
});

afterEach(() => {
  rmSync(workDir, { recursive: true, force: true });
});

const TOKENS = ':root {\n  --tt-fg: #123456;\n  --tt-bg: #abcdef;\n}\n';

function writeTokens(content: string = TOKENS): string {
  const p = join(workDir, 'tokens.css');
  writeFileSync(p, content, 'utf8');
  return p;
}

function writeSrc(name: string, content: string): void {
  writeFileSync(join(workDir, name), content, 'utf8');
}

function run(srcRel: string, tokensRel: string) {
  const res = spawnSync(
    'node',
    [scriptPath, '--src', join(workDir, srcRel), '--tokens', join(workDir, tokensRel)],
    { encoding: 'utf8' },
  );
  return { code: res.status ?? -1, stdout: res.stdout ?? '', stderr: res.stderr ?? '' };
}

describe('token-contract 合法写法放行', () => {
  it('只引用已定义令牌的 CSS 通过，且排除令牌文件自身', () => {
    writeTokens();
    writeSrc(
      'ok.css',
      '.a { color: var(--tt-fg); background: transparent; border-color: currentColor; }\n',
    );
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(0);
  });

  it('命名颜色不在颜色类属性里不判违规', () => {
    writeTokens();
    writeSrc('content.css', '.a { content: "red"; }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(0);
  });

  it('TSX 合法内联样式通过', () => {
    writeTokens();
    writeSrc(
      'ok.tsx',
      "export const el = <div style={{ display: 'flex', color: 'var(--tt-fg)' }} />;\n",
    );
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(0);
  });

  it('*.test.* 文件被排除', () => {
    writeTokens();
    writeSrc('skip.test.css', '.a { color: #fff; }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(0);
  });
});

describe('token-contract 逐类违规失败', () => {
  it('未定义变量：规则 1', () => {
    writeTokens();
    writeSrc('undef.css', '.a { color: var(--tt-missing); }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('未定义变量');
    expect(r.stdout).toContain('--tt-missing');
  });

  it('十六进制：规则 2（CSS）', () => {
    writeTokens();
    writeSrc('hex.css', '.a { color: #fff; }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('写死颜色');
    expect(r.stdout).toContain('#fff');
  });

  it('颜色函数 rgba()：规则 2', () => {
    writeTokens();
    writeSrc('rgba.css', '.a { background: rgba(0, 0, 0, 0.5); }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('写死颜色');
  });

  it('命名颜色作为颜色属性取值：规则 2', () => {
    writeTokens();
    writeSrc('named.css', '.a { color: rebeccapurple; }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('写死颜色');
    expect(r.stdout).toContain('rebeccapurple');
  });

  it('TSX 字符串里的十六进制：规则 2', () => {
    writeTokens();
    writeSrc('hex.tsx', "export const s = { color: '#abc' };\n");
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('写死颜色');
    expect(r.stdout).toContain('#abc');
  });

  it('TSX style 对象里的命名颜色：规则 2', () => {
    writeTokens();
    writeSrc('style.tsx', "export const el = <div style={{ backgroundColor: 'red' }} />;\n");
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('写死颜色');
    expect(r.stdout).toContain('red');
  });

  it('以 # 开头的锚点被判十六进制', () => {
    writeTokens();
    writeSrc('anchor.tsx', "export const href = '#add';\n");
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('#add');
  });
});

// T002 终审 B2–B4 的回归用例。
const PRIMITIVES = ':root {\n  --tt-bg: #ffffff;\n  --tt-a: #000000;\n  --tt-gray-1: #f5f5f5;\n  --tt-navy-500: #1f2a44;\n  --tt-gold-500: #c9a227;\n}\n';

describe('token-contract 令牌名不是命名颜色（B2）', () => {
  it('CSS 引用 gray / navy / gold 原色令牌通过', () => {
    writeTokens(PRIMITIVES);
    writeSrc(
      'primitives.css',
      '.a { color: var(--tt-gray-1); background: var(--tt-navy-500); border: 1px solid var(--tt-gold-500); }\n',
    );
    const r = run('.', 'tokens.css');
    expect(r.stdout).not.toContain('写死颜色');
    expect(r.code).toBe(0);
  });

  it('TSX style 里引用原色令牌通过', () => {
    writeTokens(PRIMITIVES);
    writeSrc('primitives.tsx', "export const el = <div style={{ color: 'var(--tt-gray-1)' }} />;\n");
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(0);
  });

  it('var() 回退值里的命名颜色仍判违规', () => {
    writeTokens(PRIMITIVES);
    writeSrc('fallback.css', '.a { color: var(--tt-a, red); }\n.b { box-shadow: 0 0 0 1px var(--tt-a), 0 1px black; }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout).toContain('fallback.css:1: 写死颜色: red');
    expect(r.stdout).toContain('fallback.css:2: 写死颜色: black');
  });
});

describe('token-contract 多行写法（B3）', () => {
  it('多行 style={{…}} 里的命名颜色判违规，行号是颜色所在行', () => {
    writeTokens();
    writeSrc('multi.tsx', "export const el = (\n  <div\n    style={{\n      color: 'red',\n      width: 3,\n    }}\n  />\n);\n");
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout.trim()).toMatch(/multi\.tsx:4: 写死颜色: red$/);
  });

  it('CSS 声明跨行时的命名颜色判违规', () => {
    writeTokens();
    writeSrc('multi.css', '.a {\n  box-shadow:\n    0 0 0 1px red;\n}\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout.trim()).toMatch(/multi\.css:3: 写死颜色: red$/);
  });

  it('颜色函数名与括号不在同一行时不判（文字里的“color⏎(…)”不是颜色）', () => {
    writeTokens();
    writeSrc('text.tsx', 'export const el = (\n  <p>\n    choose a color\n    (any)\n  </p>\n);\n');
    const r = run('.', 'tokens.css');
    expect(r.stdout).not.toContain('写死颜色');
    expect(r.code).toBe(0);
  });

  it('选择器里的伪类不是声明，跨行的选择器列表也一样', () => {
    writeTokens();
    writeSrc(
      'selectors.css',
      '.btn-color:hover,\n.tag-red {\n  color: var(--tt-fg);\n}\n.fill:hover, .icon-white { color: var(--tt-fg); }\n',
    );
    const r = run('.', 'tokens.css');
    expect(r.stdout).not.toContain('写死颜色');
    expect(r.code).toBe(0);
  });

  it('嵌套规则之后的声明照样判', () => {
    writeTokens();
    writeSrc('nested.css', '.a {\n  .b { color: var(--tt-fg); }\n  color: red;\n}\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout.trim()).toMatch(/nested\.css:3: 写死颜色: red$/);
  });

  it('单行的行号与输出顺序不变', () => {
    writeTokens();
    writeSrc('order.css', '.ok { color: var(--tt-fg); }\n.a { color: red; background: #fff; border-color: var(--tt-x); }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout.trim().split('\n').map((l) => l.replace(/^.*order\.css:/, ''))).toEqual([
      '2: 写死颜色: #fff',
      '2: 写死颜色: red',
      '2: 未定义变量: --tt-x',
    ]);
  });
});

describe('token-contract 组件里重写令牌（B4）', () => {
  it('组件 CSS 里声明已定义的 --tt-* 判违规，引用照常通过', () => {
    writeTokens();
    writeSrc('override.css', '.a { --tt-bg: 1px; }\n.b { color: var(--tt-bg); }\n');
    const r = run('.', 'tokens.css');
    expect(r.code).toBe(1);
    expect(r.stdout.trim()).toMatch(/override\.css:1: 未定义变量: --tt-bg$/);
  });
});

describe('token-contract 路径缺失报错', () => {
  it('源码目录不存在：非 0 退出', () => {
    writeTokens();
    const r = run('no-such-dir', 'tokens.css');
    expect(r.code).not.toBe(0);
    expect(r.stderr.length).toBeGreaterThan(0);
  });

  it('令牌文件不存在：非 0 退出', () => {
    writeSrc('ok.css', '.a { color: var(--tt-fg); }\n');
    const r = run('.', 'no-such-tokens.css');
    expect(r.code).not.toBe(0);
    expect(r.stderr.length).toBeGreaterThan(0);
  });
});
