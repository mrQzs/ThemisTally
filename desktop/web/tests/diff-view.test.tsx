import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DiffView } from '../src/components/DiffView';

// 差异视图（合同 §5.2）：jsdom 不排版，探针只看结构、属性、焦点与文字。
afterEach(cleanup);

const L = (...rows: string[]) => rows.join('\n') + '\n';
const ESC = '\u001b';
const IDX = 'index 1111111111111111111111111111111111111111..2222222222222222222222222222222222222222 100644';
const MOD_FILE = [
  'diff --git a/src/app.ts b/src/app.ts', IDX, '--- a/src/app.ts', '+++ b/src/app.ts',
  '@@ -1,4 +1,5 @@ function main()', ' ctx1', '-old1', '-old2', '+new1', '+new2', '+new3', ' ctx2',
  '@@ -20,3 +21,2 @@', ' ctx3', '-gone', ' ctx4',
];
const NEW_FILE = [
  'diff --git a/docs/新文件.md b/docs/新文件.md', 'new file mode 100644',
  'index 0000000000000000000000000000000000000000..3333333333333333333333333333333333333333',
  '--- /dev/null', '+++ b/docs/新文件.md', '@@ -0,0 +1,3 @@', '+line1', '+++ not a header', '+line3',
];
const DEL_FILE = [
  'diff --git a/old/removed.txt b/old/removed.txt', 'deleted file mode 100644',
  'index 4444444444444444444444444444444444444444..0000000000000000000000000000000000000000',
  '--- a/old/removed.txt', '+++ /dev/null', '@@ -1,3 +0,0 @@', '-r1', '--- r2 looks like a header', '-r3',
];
const P3 = L(...MOD_FILE, ...NEW_FILE, ...DEL_FILE);

function mount(patch: string, props: Record<string, unknown> = {}) {
  const r = render(<DiffView patch={patch} {...props} />);
  const root = r.container.querySelector('.tt-diff') as HTMLElement;
  expect(root).not.toBeNull();
  const update = (next: string, extra: Record<string, unknown> = {}) => r.rerender(<DiffView patch={next} {...props} {...extra} />);
  return { ...r, root, update };
}
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const squash = (s: string | null | undefined) => (s || '').replace(/\s+/g, '');
const sections = (root: HTMLElement) => Array.from(root.querySelectorAll('section.tt-diff__file')) as HTMLElement[];
const items = (root: HTMLElement) => Array.from(root.querySelectorAll('ul.tt-diff__files > li > button.tt-diff__file-item')) as HTMLButtonElement[];
const headOf = (sec: HTMLElement) => sec.querySelector('.tt-diff__file-head') as HTMLElement;
const bodyOf = (sec: HTMLElement) => sec.querySelector('.tt-diff__file-body') as HTMLElement;
const foldBtn = (sec: HTMLElement) => headOf(sec).querySelector('button') as HTMLButtonElement | null;
const rowsOf = (sec: HTMLElement) => Array.from(bodyOf(sec).querySelectorAll('.tt-diff__row')) as HTMLElement[];
const noteOf = (sec: HTMLElement) => { const el = headOf(sec).querySelector('.tt-diff__file-note'); return el ? textOf(el) : null; };
const collapsedOf = (root: HTMLElement) => sections(root).map((s) => s.getAttribute('data-collapsed') === 'true');
const currentOf = (root: HTMLElement) => items(root).map((b) => b.getAttribute('aria-current') === 'true');
function unifiedRow(row: HTMLElement) {
  const kind = row.getAttribute('data-kind');
  if (kind === 'hunk') return [kind, textOf(row)];
  const nos = Array.from(row.querySelectorAll('.tt-diff__no')).map((e) => (e.textContent || '').trim());
  const sign = (row.querySelector('.tt-diff__sign')?.textContent || '').trim();
  return [kind, nos[0], nos[1], sign, row.querySelector('.tt-diff__text')?.textContent || ''];
}
function radio(root: HTMLElement, label: string) {
  const group = root.querySelector('[role="radiogroup"][aria-label="差异显示方式"]') as HTMLElement;
  return Array.from(group.querySelectorAll('button')).find((b) => textOf(b) === label) as HTMLButtonElement;
}
function wrapSwitch(root: HTMLElement) {
  return Array.from(root.querySelectorAll('[role="switch"]')).find((e) => textOf(e) === '自动换行') as HTMLElement;
}
function pairRow(row: HTMLElement) {
  if (row.getAttribute('data-kind') === 'hunk') return ['hunk', textOf(row)];
  const side = (s: string) => {
    const cs = Array.from(row.querySelectorAll(`[data-side="${s}"]`)) as HTMLElement[];
    return [cs[0].getAttribute('data-kind'), (cs[0].textContent || '').trim(), (cs[1].textContent || '').trim(), cs[2].textContent || ''];
  };
  return [...side('left'), ...side('right')];
}

describe('结构与统一视图', () => {
  it('根、工具栏、摘要、分段选择、开关、主区、文件列表', () => {
    const { root } = mount(P3, { title: 'candidate.patch' });
    expect(root.getAttribute('data-mode')).toBe('unified');
    expect(root.getAttribute('data-wrap')).toBe('false');
    const bar = root.querySelector('.tt-diff__bar') as HTMLElement;
    const summary = bar.querySelector('.tt-diff__summary') as HTMLElement;
    expect(textOf(summary)).toBe('candidate.patch · 3 个文件 · +6 −6');
    expect((summary.textContent || '').includes('−')).toBe(true);
    const icon = summary.querySelector('svg') as SVGElement;
    expect(icon.getAttribute('width')).toBe('16');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    expect(radio(root, '统一').getAttribute('aria-checked')).toBe('true');
    expect(radio(root, '分屏').getAttribute('aria-checked')).toBe('false');
    expect(wrapSwitch(root).getAttribute('aria-checked')).toBe('false');
    const main = root.querySelector('.tt-diff__main') as HTMLElement;
    expect(main.classList.contains('tt-stack-narrow')).toBe(true);
    expect((root.querySelector('ul.tt-diff__files') as HTMLElement).getAttribute('aria-label')).toBe('文件');
    expect(sections(root).length).toBe(3);
    expect(document.querySelector('[role="status"]')).toBeNull();
  });

  it('没有 title 时摘要去掉第一段；defaultMode、defaultWrap、className 生效', () => {
    const a = mount(P3);
    expect(textOf(a.root.querySelector('.tt-diff__summary'))).toBe('3 个文件 · +6 −6');
    a.unmount();
    const b = mount(P3, { defaultMode: 'split', defaultWrap: true, className: 'extra-x' });
    expect(b.root.getAttribute('data-mode')).toBe('split');
    expect(b.root.getAttribute('data-wrap')).toBe('true');
    expect(b.root.classList.contains('extra-x')).toBe(true);
  });

  it('统一视图：行的顺序、data-kind、两列行号、加号与 −、片段头整行', () => {
    const { root } = mount(P3);
    expect(rowsOf(sections(root)[0]).map(unifiedRow)).toEqual([
      ['hunk', '@@ -1,4 +1,5 @@ function main()'],
      ['context', '1', '1', '', 'ctx1'],
      ['del', '2', '', '−', 'old1'],
      ['del', '3', '', '−', 'old2'],
      ['add', '', '2', '+', 'new1'],
      ['add', '', '3', '+', 'new2'],
      ['add', '', '4', '+', 'new3'],
      ['context', '4', '5', '', 'ctx2'],
      ['hunk', '@@ -20,3 +21,2 @@'],
      ['context', '20', '21', '', 'ctx3'],
      ['del', '21', '', '−', 'gone'],
      ['context', '22', '22', '', 'ctx4'],
    ]);
    for (const n of Array.from(sections(root)[0].querySelectorAll('.tt-diff__no'))) {
      expect(n.getAttribute('aria-hidden')).toBe('true');
      expect(n.classList.contains('tt-num')).toBe(true);
    }
    for (const s of Array.from(sections(root)[0].querySelectorAll('.tt-diff__sign'))) {
      expect(s.hasAttribute('aria-hidden')).toBe(false);
    }
  });

  it('新文件展开后只有加行；删除的文件只有删行，--- 开头内容保留两个减号', () => {
    const { root } = mount(P3);
    fireEvent.click(foldBtn(sections(root)[1]) as HTMLElement);
    expect(rowsOf(sections(root)[1]).map(unifiedRow)).toEqual([
      ['hunk', '@@ -0,0 +1,3 @@'],
      ['add', '', '1', '+', 'line1'],
      ['add', '', '2', '+', '++ not a header'],
      ['add', '', '3', '+', 'line3'],
    ]);
    expect(rowsOf(sections(root)[2]).map(unifiedRow)).toEqual([
      ['hunk', '@@ -1,3 +0,0 @@'],
      ['del', '1', '', '−', 'r1'],
      ['del', '2', '', '−', '-- r2 looks like a header'],
      ['del', '3', '', '−', 'r3'],
    ]);
  });

  it('文件头的路径、注记、计数与 data-*', () => {
    const { root } = mount(P3);
    const secs = sections(root);
    expect(secs.map((s) => s.getAttribute('data-status'))).toEqual(['modified', 'added', 'deleted']);
    expect(secs.map((s) => s.getAttribute('data-binary') === 'true')).toEqual([false, false, false]);
    expect(collapsedOf(root)).toEqual([false, true, false]);
    expect(secs.map((s) => squash(textOf(headOf(s))))).toEqual(['src/app.ts+3−3', 'docs/新文件.md新文件·已折叠+3−0', 'old/removed.txt已删除+0−3']);
    expect(secs.map(noteOf)).toEqual([null, '新文件 · 已折叠', '已删除']);
    expect(headOf(secs[0]).getAttribute('tabindex')).toBe('-1');
  });

  it('文件列表：计数、title、两层 span、type=button、缺省第一个是当前', () => {
    const { root } = mount(P3);
    const its = items(root);
    expect(its.map((b) => b.getAttribute('type'))).toEqual(['button', 'button', 'button']);
    expect(its.map((b) => b.getAttribute('aria-current'))).toEqual(['true', null, null]);
    const paths = its.map((b) => b.querySelector('.tt-diff__file-path') as HTMLElement);
    expect(paths.map((p) => p.getAttribute('title'))).toEqual(['src/app.ts', 'docs/新文件.md', 'old/removed.txt']);
    for (const p of paths) expect(textOf(p.querySelector(':scope > span'))).toBe(p.getAttribute('title'));
    expect(its.map((b) => Array.from(b.querySelectorAll('.tt-num')).map((e) => textOf(e)))).toEqual([['+3', '−3'], ['+3', '−0'], ['+0', '−3']]);
  });
});

describe('折叠、当前文件与补丁变化', () => {
  it('新文件缺省折叠：aria-expanded、hidden、没有行、注记；点开后有行、注记变化', () => {
    const { root } = mount(P3);
    const sec = sections(root)[1];
    const btn = foldBtn(sec) as HTMLButtonElement;
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(bodyOf(sec).hasAttribute('hidden')).toBe(true);
    expect(rowsOf(sec).length).toBe(0);
    expect(btn.getAttribute('aria-controls')).toBe(bodyOf(sec).id);
    const before = btn.getAttribute('aria-label');
    fireEvent.click(btn);
    const open = sections(root)[1];
    expect(foldBtn(open)!.getAttribute('aria-expanded')).toBe('true');
    expect(foldBtn(open)!.getAttribute('aria-label')).not.toBe(before);
    expect(bodyOf(open).hasAttribute('hidden')).toBe(false);
    expect(rowsOf(open).length).toBeGreaterThan(0);
    expect(noteOf(open)).toBe('新文件');
  });

  it('其他文本文件缺省展开；aria-controls 指向存在的元素；aria-labelledby 含自己与路径；id 不重复', () => {
    const a = mount(P3);
    const b = mount(P3);
    const ids: string[] = [];
    for (const root of [a.root, b.root]) {
      for (const sec of sections(root)) {
        const btn = foldBtn(sec) as HTMLButtonElement;
        const body = bodyOf(sec);
        expect(document.getElementById(btn.getAttribute('aria-controls') || '')).toBe(body);
        const name = headOf(sec).querySelector('.tt-diff__file-name') as HTMLElement;
        expect((btn.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean)).toEqual([btn.id, name.id]);
        ids.push(btn.id, name.id, body.id);
      }
      expect(sections(root).map((s) => foldBtn(s)!.getAttribute('aria-expanded'))).toEqual(['true', 'false', 'true']);
    }
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('点列表项：设为当前、折叠着就展开、焦点移到文件头', async () => {
    const { root } = mount(P3);
    fireEvent.click(items(root)[1]);
    expect(currentOf(root)).toEqual([false, true, false]);
    expect(items(root)[0].hasAttribute('aria-current')).toBe(false);
    expect(foldBtn(sections(root)[1])!.getAttribute('aria-expanded')).toBe('true');
    for (let i = 0; i < 40 && document.activeElement !== headOf(sections(root)[1]); i += 1) {
      await act(async () => { await new Promise((r) => setTimeout(r, 25)); });
    }
    expect(document.activeElement).toBe(headOf(sections(root)[1]));
  });

  it('patch 变化：折叠按序号加路径记；当前文件越界回第一个', () => {
    const m = mount(P3);
    fireEvent.click(foldBtn(sections(m.root)[0]) as HTMLElement);
    fireEvent.click(foldBtn(sections(m.root)[1]) as HTMLElement);
    expect(collapsedOf(m.root)).toEqual([true, false, false]);
    m.update(P3.replace('ctx1', 'ctx1 changed'));
    expect(collapsedOf(m.root)).toEqual([true, false, false]);
    m.update(L(...DEL_FILE, ...NEW_FILE, ...MOD_FILE));
    expect(collapsedOf(m.root)).toEqual([false, false, false]);
    const n = mount(P3);
    fireEvent.click(items(n.root)[2]);
    n.update(L(...MOD_FILE, ...NEW_FILE));
    expect(currentOf(n.root)).toEqual([true, false]);
    n.update(P3);
    fireEvent.click(items(n.root)[1]);
    n.update(L(...NEW_FILE, ...MOD_FILE, ...DEL_FILE));
    expect(currentOf(n.root)).toEqual([false, true, false]);
  });

  it('没读完：foot、说明、注记「未读完」、[继续加载]、loadingMore', () => {
    const onLoadMore = vi.fn();
    const none = mount(P3, { truncated: true });
    const foot = none.root.lastElementChild as HTMLElement;
    expect(foot.classList.contains('tt-diff__foot')).toBe(true);
    expect(textOf(foot)).toBe('补丁没有读完，只显示了已读到的部分');
    expect(sections(none.root).map(noteOf)).toEqual([null, '新文件 · 已折叠', '已删除 · 未读完']);
    none.unmount();
    const m = mount(P3, { truncated: true, onLoadMore });
    const btn = Array.from(m.root.querySelectorAll('button')).find((b) => textOf(b) === '继续加载') as HTMLButtonElement;
    expect(btn.getAttribute('data-variant')).toBe('secondary');
    expect(btn.getAttribute('data-size')).toBe('sm');
    fireEvent.click(btn);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
    m.update(P3, { truncated: true, onLoadMore, loadingMore: true });
    const busy = Array.from(m.root.querySelectorAll('button')).find((b) => textOf(b) === '正在加载…') as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(busy.getAttribute('aria-busy')).toBe('true');
  });

  it('没有文件时只有工具栏与「补丁里没有改动」，不渲染列表', () => {
    for (const patch of ['', '--- a/x.txt\n+++ b/x.txt\n@@ -1 +1 @@\n-a\n+b\n', 'hello\nworld\n']) {
      const { root, unmount } = mount(patch);
      expect(root.querySelector('.tt-diff__bar')).not.toBeNull();
      expect(textOf(root.querySelector('.tt-diff__empty'))).toBe('补丁里没有改动');
      expect(root.querySelector('ul.tt-diff__files')).toBeNull();
      expect(sections(root).length).toBe(0);
      unmount();
    }
  });
});

describe('分屏、换行、eof、超长行', () => {
  it('切模式与换行只改 data-mode/data-wrap 与行结构，折叠与当前文件不变', () => {
    const { root } = mount(P3);
    fireEvent.click(foldBtn(sections(root)[0]) as HTMLElement);
    fireEvent.click(items(root)[2]);
    const collapsed = collapsedOf(root);
    const current = currentOf(root);
    fireEvent.click(radio(root, '分屏'));
    expect(root.getAttribute('data-mode')).toBe('split');
    expect(collapsedOf(root)).toEqual(collapsed);
    expect(currentOf(root)).toEqual(current);
    fireEvent.click(wrapSwitch(root));
    expect(root.getAttribute('data-wrap')).toBe('true');
    expect(collapsedOf(root)).toEqual(collapsed);
    expect(currentOf(root)).toEqual(current);
  });

  it('分屏配对：两删三加得三行、第三行左 empty；两侧行号与符号；片段头一格占满', () => {
    const { root } = mount(P3, { defaultMode: 'split' });
    const rows = rowsOf(sections(root)[0]);
    expect(rows.map((r) => r.getAttribute('data-kind'))).toEqual(['hunk', 'pair', 'pair', 'pair', 'pair', 'pair', 'hunk', 'pair', 'pair', 'pair']);
    expect(rows.map(pairRow)).toEqual([
      ['hunk', '@@ -1,4 +1,5 @@ function main()'],
      ['context', '1', '', 'ctx1', 'context', '1', '', 'ctx1'],
      ['del', '2', '−', 'old1', 'add', '2', '+', 'new1'],
      ['del', '3', '−', 'old2', 'add', '3', '+', 'new2'],
      ['empty', '', '', '', 'add', '4', '+', 'new3'],
      ['context', '4', '', 'ctx2', 'context', '5', '', 'ctx2'],
      ['hunk', '@@ -20,3 +21,2 @@'],
      ['context', '20', '', 'ctx3', 'context', '21', '', 'ctx3'],
      ['del', '21', '−', 'gone', 'empty', '', '', ''],
      ['context', '22', '', 'ctx4', 'context', '22', '', 'ctx4'],
    ]);
    for (const hunk of rows.filter((r) => r.getAttribute('data-kind') === 'hunk')) {
      expect(hunk.querySelectorAll('[data-side]').length).toBe(0);
    }
  });

  it('No newline：eof 注记，反斜杠标记行不出现在 DOM；分屏两侧各一个 eof', () => {
    const NONL = L('diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt', '@@ -1,2 +1,2 @@',
      ' keep', '-last', '\\ No newline at end of file', '+last2', '\\ No newline at end of file');
    const { root } = mount(NONL);
    const rows = rowsOf(sections(root)[0]);
    expect(rows.map((r) => r.getAttribute('data-kind'))).toEqual(['hunk', 'context', 'del', 'add']);
    expect(rows.map((r) => r.querySelectorAll('.tt-diff__eof').length)).toEqual([0, 0, 1, 1]);
    expect(root.textContent || '').not.toMatch(/No newline/);
    fireEvent.click(radio(root, '分屏'));
    const pairs = rowsOf(sections(root)[0]);
    expect(pairs[2].querySelectorAll('.tt-diff__eof').length).toBe(2);
  });

  it('超长行（2500 字符）完整显示', () => {
    const long = 'x'.repeat(2500);
    const patch = L('diff --git a/l.txt b/l.txt', IDX, '--- a/l.txt', '+++ b/l.txt', '@@ -1 +1 @@', '-' + long, '+' + long + 'y');
    const { root } = mount(patch);
    const texts = Array.from(root.querySelectorAll('.tt-diff__row:not([data-kind="hunk"]) .tt-diff__text')).map((e) => e.textContent || '');
    expect(texts).toEqual([long, long + 'y']);
  });
});

describe('只按文本显示（W1）', () => {
  const EVIL = L(
    'diff --git a/evil<script>alert(1)</script>.txt b/evil<script>alert(1)</script>.txt', IDX,
    '--- a/evil<script>alert(1)</script>.txt', '+++ b/evil<script>alert(1)</script>.txt',
    '@@ -1,2 +1,5 @@ <img src=x onerror=alert(1)> ' + ESC + '[31mhdr' + ESC + '[0m',
    ' <script>alert(1)</script>', '+<img src=x onerror=alert(1)>', '+' + ESC + '[31mred words' + ESC + '[0m tail',
    '+see https://example.com/a?b=1&c=2 now', '+<a href="javascript:alert(1)">x</a>', '-bye',
  );

  it('脚本、图片、ANSI、网址只是文字；没有 script/img/a 元素；路径除文字外只在 title', () => {
    const { root } = mount(EVIL, { title: 'evil.patch' });
    expect(root.querySelectorAll('script, img, a, iframe, object, embed, style, link').length).toBe(0);
    expect(root.querySelectorAll('[onerror], [href], [src], [srcdoc]').length).toBe(0);
    const text = root.textContent || '';
    expect(text).toContain('<script>alert(1)</script>');
    expect(text).toContain('<img src=x onerror=alert(1)>');
    expect(text).toContain('red words tail');
    expect(text).toContain('@@ -1,2 +1,5 @@ <img src=x onerror=alert(1)> hdr');
    expect(text.includes(ESC)).toBe(false);
    expect(text.includes('[31m')).toBe(false);
    for (const el of [root, ...Array.from(root.querySelectorAll('*'))] as Element[]) {
      for (const attr of Array.from(el.attributes)) {
        expect(attr.name.startsWith('on')).toBe(false);
        if (attr.name === 'title') { expect(attr.value.includes(ESC)).toBe(false); continue; }
        expect(attr.value).not.toMatch(/script|onerror|alert|example\.com|red words|[<>]/i);
      }
    }
  });
});
