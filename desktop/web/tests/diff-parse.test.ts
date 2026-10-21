import { describe, expect, it } from 'vitest';
import { parseDiff, type DiffFile } from '../src/components/diff/parseDiff';
import { splitPairs } from '../src/components/diff/splitPairs';

// 解析与分屏配对（合同 §5.1 的 R1–R10 与 splitPairs）：纯函数，不渲染组件。
const L = (...rows: string[]) => rows.join('\n') + '\n';
const IDX = 'index 1111111111111111111111111111111111111111..2222222222222222222222222222222222222222 100644';

const MOD_FILE = [
  'diff --git a/src/app.ts b/src/app.ts',
  IDX,
  '--- a/src/app.ts',
  '+++ b/src/app.ts',
  '@@ -1,4 +1,5 @@ function main()',
  ' ctx1',
  '-old1',
  '-old2',
  '+new1',
  '+new2',
  '+new3',
  ' ctx2',
  '@@ -20,3 +21,2 @@',
  ' ctx3',
  '-gone',
  ' ctx4',
];
const NEW_FILE = [
  'diff --git a/docs/新文件.md b/docs/新文件.md',
  'new file mode 100644',
  'index 0000000000000000000000000000000000000000..3333333333333333333333333333333333333333',
  '--- /dev/null',
  '+++ b/docs/新文件.md',
  '@@ -0,0 +1,3 @@',
  '+line1',
  '+++ not a header',
  '+line3',
];
const DEL_FILE = [
  'diff --git a/old/removed.txt b/old/removed.txt',
  'deleted file mode 100644',
  'index 4444444444444444444444444444444444444444..0000000000000000000000000000000000000000',
  '--- a/old/removed.txt',
  '+++ /dev/null',
  '@@ -1,3 +0,0 @@',
  '-r1',
  '--- r2 looks like a header',
  '-r3',
];
const P3 = L(...MOD_FILE, ...NEW_FILE, ...DEL_FILE);

function brief(f: DiffFile) {
  return { old: f.oldPath, nw: f.newPath, status: f.status, binary: f.binary, hunks: f.hunks.length, add: f.additions, del: f.deletions };
}
function rowsOf(h: DiffFile['hunks'][number]) {
  return h.lines.map((l) => [l.kind, l.oldNo, l.newNo, l.text, l.noNewline]);
}
function headerOf(h: DiffFile['hunks'][number]) {
  return [h.header, h.oldStart, h.oldLines, h.newStart, h.newLines];
}

describe('parseDiff：三个文件的顺序、路径、状态、计数', () => {
  it('改动、新增、删除三个文件的 brief 逐项对', () => {
    const files = parseDiff(P3);
    expect(files.map(brief)).toEqual([
      { old: 'src/app.ts', nw: 'src/app.ts', status: 'modified', binary: false, hunks: 2, add: 3, del: 3 },
      { old: null, nw: 'docs/新文件.md', status: 'added', binary: false, hunks: 1, add: 3, del: 0 },
      { old: 'old/removed.txt', nw: null, status: 'deleted', binary: false, hunks: 1, add: 0, del: 3 },
    ]);
  });

  it('改动文件两个片段各自从片段头起算，行的 kind、行号、文字逐项对', () => {
    const [f0] = parseDiff(P3);
    expect(f0.hunks.map(headerOf)).toEqual([
      ['@@ -1,4 +1,5 @@ function main()', 1, 4, 1, 5],
      ['@@ -20,3 +21,2 @@', 20, 3, 21, 2],
    ]);
    expect(rowsOf(f0.hunks[0])).toEqual([
      ['context', 1, 1, 'ctx1', false],
      ['del', 2, null, 'old1', false],
      ['del', 3, null, 'old2', false],
      ['add', null, 2, 'new1', false],
      ['add', null, 3, 'new2', false],
      ['add', null, 4, 'new3', false],
      ['context', 4, 5, 'ctx2', false],
    ]);
    expect(rowsOf(f0.hunks[1])).toEqual([
      ['context', 20, 21, 'ctx3', false],
      ['del', 21, null, 'gone', false],
      ['context', 22, 22, 'ctx4', false],
    ]);
  });

  it('新文件 added，新行号 1 到 3；+++ 开头的内容行算新增', () => {
    const [, f1] = parseDiff(P3);
    expect(rowsOf(f1.hunks[0])).toEqual([
      ['add', null, 1, 'line1', false],
      ['add', null, 2, '++ not a header', false],
      ['add', null, 3, 'line3', false],
    ]);
  });

  it('删除的文件 deleted；--- 开头的内容行算删除', () => {
    const [, , f2] = parseDiff(P3);
    expect(rowsOf(f2.hunks[0])).toEqual([
      ['del', 1, null, 'r1', false],
      ['del', 2, null, '-- r2 looks like a header', false],
      ['del', 3, null, 'r3', false],
    ]);
  });
});

describe('parseDiff：R1 切行、No newline、片段头、容错', () => {
  it('CRLF 与 LF 结果逐项相同，末尾有没有换行结果相同', () => {
    const lf = parseDiff(P3);
    expect(JSON.stringify(parseDiff(P3.replace(/\n/g, '\r\n')))).toBe(JSON.stringify(lf));
    expect(JSON.stringify(lf).includes('\\r')).toBe(false);
    expect(JSON.stringify(parseDiff(P3.slice(0, -1)))).toBe(JSON.stringify(lf));
  });

  it('No newline 标记记在上一行、不计数、不推进行号；用完后也记给上一行', () => {
    const patch = L(
      'diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt', '@@ -1,2 +1,2 @@',
      ' keep', '-last', '\\ No newline at end of file', '+last2', '\\ No newline at end of file',
      'diff --git a/b.txt b/b.txt', IDX, '--- a/b.txt', '+++ b/b.txt', '@@ -1 +1,2 @@',
      '-x', '+x', '+y', '\\ No newline at end of file',
    );
    const [a, b] = parseDiff(patch);
    expect(rowsOf(a.hunks[0])).toEqual([
      ['context', 1, 1, 'keep', false],
      ['del', 2, null, 'last', true],
      ['add', null, 2, 'last2', true],
    ]);
    expect(rowsOf(b.hunks[0])).toEqual([
      ['del', 1, null, 'x', false],
      ['add', null, 1, 'x', false],
      ['add', null, 2, 'y', true],
    ]);
  });

  it('@@ -1 +1 @@ 行数缺省为 1；余下文字留在 header；下一个片段重新起算', () => {
    const patch = L(
      'diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt',
      '@@ -3 +3 @@ trailing words here', '-a', '+b',
      '@@ -10,2 +12 @@', ' c', '-d', '+e',
    );
    const [f] = parseDiff(patch);
    expect(f.hunks.map(headerOf)).toEqual([
      ['@@ -3 +3 @@ trailing words here', 3, 1, 3, 1],
      ['@@ -10,2 +12 @@', 10, 2, 12, 1],
    ]);
    expect(rowsOf(f.hunks[0])).toEqual([['del', 3, null, 'a', false], ['add', null, 3, 'b', false]]);
  });

  it('不合格 @@ 忽略；用完后多出来的行忽略；空行算空 context；遇到 diff --git 开始下一文件', () => {
    const patch = L(
      'diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt',
      '@@ garbage @@', '+ignored', '@@ -1,2 +1,2', '+ignored too',
      '@@ -1,3 +1,3 @@', ' a', '', ' c', ' extra after the hunk is full', '-ignored',
      'diff --git a/b.txt b/b.txt', IDX, '--- a/b.txt', '+++ b/b.txt', '@@ -1,5 +1,5 @@', ' only', '-one',
    );
    const files = parseDiff(patch);
    expect(files.map((f) => [f.newPath, f.hunks.length])).toEqual([['a.txt', 1], ['b.txt', 1]]);
    expect(rowsOf(files[0].hunks[0])).toEqual([
      ['context', 1, 1, 'a', false],
      ['context', 2, 2, '', false],
      ['context', 3, 3, 'c', false],
    ]);
    expect(rowsOf(files[1].hunks[0])).toEqual([['context', 1, 1, 'only', false], ['del', 2, null, 'one', false]]);
  });
});

describe('parseDiff：R3–R5 路径、R4 回退、R8 状态', () => {
  it('改名（纯改名与带片段）都是 renamed', () => {
    const patch = L(
      'diff --git a/old/a.txt b/new/b.txt', 'similarity index 100%', 'rename from old/a.txt', 'rename to new/b.txt',
      'diff --git a/x.txt b/y.txt', 'similarity index 90%', 'rename from x.txt', 'rename to y.txt',
      'index aaaaaaa..bbbbbbb 100644', '--- a/x.txt', '+++ b/y.txt', '@@ -1 +1 @@', '-a', '+b',
    );
    expect(parseDiff(patch).map(brief)).toEqual([
      { old: 'old/a.txt', nw: 'new/b.txt', status: 'renamed', binary: false, hunks: 0, add: 0, del: 0 },
      { old: 'x.txt', nw: 'y.txt', status: 'renamed', binary: false, hunks: 1, add: 1, del: 1 },
    ]);
  });

  it('二进制两种写法：Binary files 一行；GIT binary patch 整块跳到下一个 diff --git', () => {
    const patch = L(
      'diff --git a/img/logo.png b/img/logo.png', 'new file mode 100644',
      'index 0000000000000000000000000000000000000000..5555555555555555555555555555555555555555',
      'GIT binary patch', 'literal 12', 'Tcmb(d$jHrq^!}H5r`c', '--- a/fake', '+++ b/fake', '@@ -1 +1 @@', '+nope', '-nope', '',
      'literal 0', 'HcmV?d00001', '',
      'diff --git a/after.txt b/after.txt', IDX, '--- a/after.txt', '+++ b/after.txt', '@@ -1 +1 @@', '-a', '+b',
      'diff --git a/bin/data.bin b/bin/data.bin', IDX, 'Binary files a/bin/data.bin and b/bin/data.bin differ',
      'diff --git a/n.bin b/n.bin', 'new file mode 100644', IDX, 'Binary files /dev/null and b/n.bin differ',
      'diff --git a/gone.bin b/gone.bin', 'deleted file mode 100644', IDX, 'Binary files a/gone.bin and /dev/null differ',
      'diff --git a/z.txt b/z.txt', IDX, '--- a/z.txt', '+++ b/z.txt', '@@ -1 +1 @@', '-z', '+Z',
    );
    const files = parseDiff(patch);
    expect(files.map((f) => [f.status === 'deleted' ? f.oldPath : f.newPath, f.status, f.binary, f.hunks.length, f.additions, f.deletions])).toEqual([
      ['img/logo.png', 'added', true, 0, 0, 0],
      ['after.txt', 'modified', false, 1, 1, 1],
      ['bin/data.bin', 'modified', true, 0, 0, 0],
      ['n.bin', 'added', true, 0, 0, 0],
      ['gone.bin', 'deleted', true, 0, 0, 0],
      ['z.txt', 'modified', false, 1, 1, 1],
    ]);
    expect([files[2].oldPath, files[2].newPath]).toEqual(['bin/data.bin', 'bin/data.bin']);
  });

  it('路径解码：C 风格还原、八进制 UTF-8、坏字节替换字符、制表符截断', () => {
    const patch = L(
      'diff --git "a/dir/\\344\\270\\255\\346\\226\\207.txt" "b/dir/\\344\\270\\255\\346\\226\\207.txt"', 'old mode 100644', 'new mode 100755',
      'diff --git "a/we\\"ird\\\\name.txt" "b/we\\"ird\\\\name.txt"', IDX, '--- "a/we\\"ird\\\\name.txt"', '+++ "b/we\\"ird\\\\name.txt"',
      '@@ -1 +1 @@', '-a', '+b',
      'diff --git a/with space.txt b/with space.txt', IDX, '--- a/with space.txt\t', '+++ b/with space.txt\t', '@@ -1 +1 @@', '-a', '+b',
      'diff --git "a/bad\\377.txt" "b/bad\\377.txt"', 'old mode 100644', 'new mode 100755',
    );
    expect(parseDiff(patch).map((f) => [f.oldPath, f.newPath, f.status])).toEqual([
      ['dir/中文.txt', 'dir/中文.txt', 'modified'],
      ['we"ird\\name.txt', 'we"ird\\name.txt', 'modified'],
      ['with space.txt', 'with space.txt', 'modified'],
      ['bad\ufffd.txt', 'bad\ufffd.txt', 'modified'],
    ]);
  });

  it('没有 ---、+++、rename 时路径取自 diff --git 行（中点、b/ 切开、空文件、只改权限）', () => {
    const patch = L(
      'diff --git a/my file.txt b/my file.txt', 'old mode 100644', 'new mode 100755',
      'diff --git a/foo b/bar',
      'diff --git a/empty.txt b/empty.txt', 'new file mode 100644', 'index 0000000..e69de29',
      'diff --git a/gone.txt b/gone.txt', 'deleted file mode 100644', 'index e69de29..0000000',
      'diff --git a/p b/p', '--- a/real.txt', '+++ b/real.txt', '@@ -1 +1 @@', '-a', '+b',
    );
    const files = parseDiff(patch);
    expect(files.length).toBe(5);
    expect(brief(files[0])).toEqual({ old: 'my file.txt', nw: 'my file.txt', status: 'modified', binary: false, hunks: 0, add: 0, del: 0 });
    expect([files[1].oldPath, files[1].newPath, files[1].status]).toEqual(['foo', 'bar', 'renamed']);
    expect([files[2].newPath, files[2].status, files[2].hunks.length]).toEqual(['empty.txt', 'added', 0]);
    expect([files[3].oldPath, files[3].status, files[3].hunks.length]).toEqual(['gone.txt', 'deleted', 0]);
    expect([files[4].oldPath, files[4].newPath]).toEqual(['real.txt', 'real.txt']);
  });

  it('第一个 diff --git 之前的行忽略；空串与乱码返回空列表', () => {
    expect(parseDiff('')).toEqual([]);
    expect(parseDiff('\n')).toEqual([]);
    expect(parseDiff('hello world\nthis is not a patch\n+++ b/x\n--- a/x\n@@ -1 +1 @@\n-a\n+b\n')).toEqual([]);
    expect(parseDiff('\u0000\u0001\u0002 \ufffd\r\r\n\n\n')).toEqual([]);
    expect(parseDiff('From: someone\nSubject: [PATCH] x\n\n' + P3).map(brief)).toEqual(parseDiff(P3).map(brief));
  });
});

describe('parseDiff：R10 性能', () => {
  const MIB = 1024 * 1024;
  function timed(label: string, patch: string) {
    const t0 = Date.now();
    parseDiff(patch);
    const dt = Date.now() - t0;
    expect(dt, label + ' 应在 2 秒内返回，实际 ' + dt + 'ms').toBeLessThan(2000);
  }

  it('1 MiB 的病态输入各在 2 秒内返回', () => {
    timed('一条 1 MiB 长行', 'x'.repeat(MIB));
    timed('长 diff --git 行', 'diff --git a/' + 'a'.repeat(MIB) + ' b/b\n');
    timed('未闭合的长引号路径', 'diff --git "' + 'a'.repeat(MIB) + '\n');
    timed('长反斜杠引号路径', 'diff --git "' + '\\'.repeat(MIB) + '"\n');
    timed('片段里的长行', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-' + 'a'.repeat(MIB) + '\n+' + 'b'.repeat(MIB) + '\n');
    timed('长 @@ 行（数字）', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -' + '1'.repeat(MIB) + ' +1 @@\n');
    timed('1 MiB 的反斜杠行', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n a\n' + '\\'.repeat(MIB) + '\n');
  }, 30000);

  it('2 万个文件头、很大的行数、成片的 @@ 与反斜杠行都线性', () => {
    const many = Array.from({ length: 20000 }, (_, i) => 'diff --git a/f' + i + ' b/f' + i).join('\n') + '\n';
    const t0 = Date.now();
    const files = parseDiff(many);
    expect(Date.now() - t0, '2 万个文件头应在 2 秒内返回').toBeLessThan(2000);
    expect(files.length).toBe(20000);
    const big = parseDiff('diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,999999999 +1,999999999 @@\n a\n-b\n+c\n');
    expect(big[0].hunks[0].lines.length).toBe(3);
    timed('10 万个片段头', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n' + '@@ -1 +1 @@\n'.repeat(100000));
  }, 30000);
});

describe('splitPairs：分屏配对', () => {
  function linesFor(spec: string) {
    const kinds: Record<string, string> = { c: ' ', d: '-', a: '+' };
    const body = spec.split('').map((ch, i) => kinds[ch] + 'x' + i);
    const oldN = spec.split('').filter((ch) => ch !== 'a').length;
    const newN = spec.split('').filter((ch) => ch !== 'd').length;
    const patch = L('diff --git a/s.txt b/s.txt', '--- a/s.txt', '+++ b/s.txt', '@@ -1,' + oldN + ' +1,' + newN + ' @@', ...body);
    return parseDiff(patch)[0].hunks[0].lines;
  }

  it('各形态的配对行数对；不改输入；空数组返回空数组', () => {
    const cases: Array<[string, number]> = [
      ['cddaaac', 5], ['cdc', 3], ['cac', 3], ['dac', 2], ['ad', 1], ['aad', 2], ['dd', 2], ['aa', 2], ['cc', 2],
      ['dadc', 3], ['dadadc', 4], ['cdacdaac', 6],
    ];
    for (const [spec, rows] of cases) {
      expect(splitPairs(linesFor(spec)).length, spec + ' 应得 ' + rows + ' 行').toBe(rows);
    }
    expect(splitPairs([])).toEqual([]);
    const lines = linesFor('cddaaac');
    const before = JSON.stringify(lines);
    splitPairs(lines);
    expect(JSON.stringify(lines)).toBe(before);
  });

  it('两删三加：第 k 删配第 k 增，第三行左侧空', () => {
    const rows = splitPairs(linesFor('cddaaac'));
    const pairs = rows.filter((r) => r.kind === 'pair');
    expect(pairs.length).toBe(3);
    expect(pairs[0].kind === 'pair' && pairs[0].left!.text).toBe('x1');
    expect(pairs[0].kind === 'pair' && pairs[0].right!.text).toBe('x3');
    expect(pairs[2].kind === 'pair' && pairs[2].left).toBeNull();
    expect(pairs[2].kind === 'pair' && pairs[2].right!.text).toBe('x5');
  });
});
