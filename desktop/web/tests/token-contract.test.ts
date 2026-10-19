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
