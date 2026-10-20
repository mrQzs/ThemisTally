import { cleanup, render, fireEvent } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { parseInlines, parseMarkdown } from '../src/components/evidence/markdown';
import { SafeMarkdown } from '../src/components/SafeMarkdown';

afterEach(cleanup);

function md(source: string, extra: Record<string, unknown> = {}) {
  const onOpenLink = vi.fn();
  const r = render(<SafeMarkdown source={source} onOpenLink={onOpenLink} {...extra} />);
  const root = r.container.firstElementChild as HTMLElement;
  expect(root, 'SafeMarkdown 应渲染出一个根元素').not.toBeNull();
  return { ...r, root, onOpenLink };
}
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const tags = (root: Element, selector: string) => Array.from(root.querySelectorAll(selector)).map((e) => e.tagName.toLowerCase());
const texts = (root: Element, selector: string) => Array.from(root.querySelectorAll(selector)).map((e) => e.textContent || '');
const topLists = (root: Element) =>
  Array.from(root.querySelectorAll('ul, ol')).filter((l) => !(l.parentElement && l.parentElement.closest('li')));
function listShape(list: Element): unknown[] {
  return Array.from(list.children).map((li) => {
    const kids = Array.from(li.children);
    const p = kids.find((c) => c.tagName === 'P');
    const subs = kids.filter((c) => c.tagName === 'UL' || c.tagName === 'OL');
    const label = (p ? p.textContent : li.textContent) || '';
    return subs.length ? [label, ...subs.map(listShape)] : label;
  });
}

const ALLOWED_TAGS = new Set(['div', 'span', 'p', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'pre', 'code', 'strong', 'em',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'button']);
function audit(root: Element): string[] {
  const bad: string[] = [];
  for (const el of [root, ...Array.from(root.querySelectorAll('*'))]) {
    const tag = el.tagName.toLowerCase();
    if (!ALLOWED_TAGS.has(tag)) bad.push('不许的元素 ' + tag);
    for (const a of Array.from(el.attributes)) {
      const n = a.name.toLowerCase();
      if (!(n === 'class' || n === 'type' || n === 'start' || n === 'scope' || n.startsWith('aria-') || n.startsWith('data-'))) {
        bad.push(tag + ' 上不许的属性 ' + n);
      }
    }
  }
  return bad;
}

describe('块：标题、段落与打断', () => {
  it('标题 1–6 级渲染成 h2–h6（h6 封顶）；去结尾空格加井号', () => {
    const { root } = md('# A\n## B ##  \n### C\n#### D\n##### E\n###### F');
    expect(tags(root, 'h1,h2,h3,h4,h5,h6')).toEqual(['h2', 'h3', 'h4', 'h5', 'h6', 'h6']);
    expect(texts(root, 'h2,h3,h4,h5,h6').map((t) => t.trim())).toEqual(['A', 'B', 'C', 'D', 'E', 'F']);
    expect(root.querySelectorAll('h1').length).toBe(0);
  });

  it('井号后不是空格、七个井号都不是标题', () => {
    const { root } = md('#5 不是标题\n\n####### 七个井号\n\n#没有空格');
    expect(root.querySelectorAll('h1,h2,h3,h4,h5,h6').length).toBe(0);
    const t = root.textContent || '';
    expect(t).toContain('#5 不是标题');
    expect(t).toContain('####### 七个井号');
    expect(t).toContain('#没有空格');
  });

  it('段落：连续非空行，每行去首尾空白后用换行连接；空行分段', () => {
    const { root } = md('line1\n   line2   \n\nnext');
    expect(Array.from(root.querySelectorAll('p')).map((p) => p.textContent)).toEqual(['line1\nline2', 'next']);
  });

  it('标题、围栏、列表项、表格都能打断段落；CRLF 与单独的 CR 都按换行处理', () => {
    expect(tags(md('para\n# H\nmore').root, 'p,h2')).toEqual(['p', 'h2', 'p']);
    expect(tags(md('para\n```\ncode\n```\nafter').root, 'p,pre')).toEqual(['p', 'pre', 'p']);
    const c = md('para\n- a\n- b');
    expect(c.root.querySelectorAll('ul > li').length).toBe(2);
    expect(Array.from(c.root.querySelectorAll('p')).map((p) => p.textContent)).toEqual(['para', 'a', 'b']);
    const d = md('para\n| a | b |\n|---|---|\n| 1 | 2 |');
    expect(d.root.querySelectorAll('table').length).toBe(1);
    expect(d.root.querySelector('p')!.textContent).toBe('para');
    const crlf = md('a\r\nb\r\n\r\n- x\r\n- y');
    expect(Array.from(crlf.root.querySelectorAll('p')).map((p) => p.textContent)).toEqual(['a\nb', 'x', 'y']);
    expect(md('a\rb').root.querySelector('p')!.textContent).toBe('a\nb');
  });
});

describe('块：列表', () => {
  it('无序列表：-、*、+ 混用算同一个列表；项里的段落也是 p', () => {
    const { root } = md('- a\n* b\n+ c');
    expect(topLists(root).length).toBe(1);
    expect(topLists(root)[0].tagName).toBe('UL');
    expect(listShape(topLists(root)[0])).toEqual(['a', 'b', 'c']);
    expect(Array.from(topLists(root)[0].children)
      .filter((li) => li.tagName === 'LI' && Array.from(li.children).some((c) => c.tagName === 'P')).length).toBe(3);
  });

  it('有序列表：. 与 ) 都行；首数字不是 1 带 start，是 1 不带', () => {
    expect(md('3. x\n4. y').root.querySelector('ol')!.getAttribute('start')).toBe('3');
    expect(listShape(md('3. x\n4. y').root.querySelector('ol')!)).toEqual(['x', 'y']);
    expect(md('1. x\n2. y').root.querySelector('ol')!.hasAttribute('start')).toBe(false);
    expect(md('2) x').root.querySelector('ol')!.getAttribute('start')).toBe('2');
    expect(md('0. z').root.querySelector('ol')!.getAttribute('start')).toBe('0');
  });

  it('同层有序、无序换了就另起一个列表', () => {
    const { root } = md('- a\n1. b');
    expect(topLists(root).map((l) => l.tagName)).toEqual(['UL', 'OL']);
  });

  it('嵌套：缩进不小于当前项文字起始列的是子列表，同缩进是兄弟，更小退回上一层', () => {
    const { root } = md('- a\n  - b\n    - c\n  - d\n- e');
    expect(topLists(root).length).toBe(1);
    expect(listShape(topLists(root)[0])).toEqual([['a', [['b', ['c']], 'd']], 'e']);
    expect(listShape(topLists(md('- a\n - b').root)[0])).toEqual(['a', 'b']);
    expect(topLists(md('1. a\n  - b').root).map((l) => l.tagName)).toEqual(['OL', 'UL']);
    expect(topLists(md('1. a\n   - b').root).length).toBe(1);
    expect(listShape(topLists(md('- a\n\t- b').root)[0])).toEqual([['a', ['b']]]);
  });

  it('不缩进的惰性续行接到当前项的段落里；空行之后是列表项或缩进够的行才继续', () => {
    expect(listShape(topLists(md('- a\ncontinued').root)[0])).toEqual(['a\ncontinued']);
    expect(topLists(md('- a\n\n- b').root).length).toBe(1);
    expect(listShape(topLists(md('- a\n\n- b').root)[0])).toEqual(['a', 'b']);
    const ended = md('- a\n\nplain');
    expect(topLists(ended.root).length).toBe(1);
    expect(topLists(ended.root)[0].textContent).not.toContain('plain');
    expect(ended.root.textContent).toContain('plain');
    expect(topLists(md('- a\n\n  more').root)[0].textContent).toContain('more');
  });

  it('最多 8 层，更深的项当作第 8 层的兄弟', () => {
    const lines: string[] = [];
    for (let i = 1; i <= 10; i += 1) lines.push('  '.repeat(i - 1) + '- L' + i);
    const { root } = md(lines.join('\n'));
    let maxDepth = 0;
    for (const ul of Array.from(root.querySelectorAll('ul'))) {
      let d = 0;
      for (let e: Element | null = ul; e; e = e.parentElement) if (e.tagName === 'UL') d += 1;
      maxDepth = Math.max(maxDepth, d);
    }
    expect(maxDepth).toBe(8);
    const own = (li: Element) => (Array.from(li.children).find((c) => c.tagName === 'P')?.textContent || '');
    const l8 = Array.from(root.querySelectorAll('li')).find((li) => own(li) === 'L8')!;
    expect(Array.from(l8.parentElement!.children).map(own)).toEqual(['L8', 'L9', 'L10']);
  });
});

describe('块：围栏代码块与表格', () => {
  it('反引号围栏：内容原样、信息串忽略；波浪号围栏；闭合行不短于开头；没有闭合行就到文末', () => {
    const code = md('```js title="x"\nconst a = 1 < 2;\n  **not bold**\n```\n').root.querySelector('pre > code');
    expect(code).not.toBeNull();
    expect((code!.textContent || '').replace(/\n$/, '')).toBe('const a = 1 < 2;\n  **not bold**');
    expect(md('```js title="x"\nconst a = 1 < 2;\n```\n').root.querySelectorAll('strong').length).toBe(0);
    expect((md('~~~\ntilde\n~~~').root.querySelector('pre code')!.textContent || '').replace(/\n$/, '')).toBe('tilde');
    expect((md('````\n```\ninner\n```\n````').root.querySelector('pre code')!.textContent || '').replace(/\n$/, ''))
      .toBe('```\ninner\n```');
    expect((md('```\na\nb').root.querySelector('pre code')!.textContent || '').replace(/\n$/, '')).toBe('a\nb');
    expect(md('``` a`b\nx').root.querySelectorAll('pre').length).toBe(0);
  });

  const TABLE = ['| 左 | 右 | 中 | 无 |', '|:---|---:|:--:|----|', '| a | b | c | d |', '| 1 \\| 2 | x |', '| p | q | r | s | extra |'].join('\n');

  it('结构：外套滚动 div、th[scope=col] 与 td；多的格丢掉、少的补空；\\| 是字面竖线', () => {
    const { root } = md(TABLE);
    const table = root.querySelector('table') as HTMLElement;
    expect(table).not.toBeNull();
    const wrap = table.parentElement as HTMLElement;
    expect(wrap.tagName).toBe('DIV');
    expect(wrap).not.toBe(root);
    const ths = Array.from(table.querySelectorAll('thead > tr > th'));
    expect(ths.map((t) => t.textContent)).toEqual(['左', '右', '中', '无']);
    for (const th of ths) expect(th.getAttribute('scope')).toBe('col');
    const trs = Array.from(table.querySelectorAll('tbody > tr'));
    expect(trs.length).toBe(3);
    expect(trs.map((tr) => Array.from(tr.children).map((td) => td.tagName + ':' + td.textContent))).toEqual([
      ['TD:a', 'TD:b', 'TD:c', 'TD:d'],
      ['TD:1 | 2', 'TD:x', 'TD:', 'TD:'],
      ['TD:p', 'TD:q', 'TD:r', 'TD:s'],
    ]);
  });

  it('对齐用类不用内联样式；不设对齐的列不带这些类', () => {
    const { root } = md(TABLE);
    const cls = Array.from(root.querySelectorAll('thead th')).map((t) => t.getAttribute('class') || '');
    expect(new Set(cls.slice(0, 3)).size).toBe(3);
    expect(cls[3]).not.toBe(cls[0]);
    expect(cls[3]).not.toBe(cls[1]);
    expect(cls[3]).not.toBe(cls[2]);
    expect(new Set(Array.from(root.querySelector('tbody tr')!.children).map((t) => t.getAttribute('class') || '')).size)
      .toBeGreaterThan(2);
    expect(root.querySelectorAll('[style], [align]').length).toBe(0);
  });

  it('格数不同、没有对齐行不算表格；表头不带行也算表格', () => {
    expect(md('| a | b |\n|---|').root.querySelectorAll('table').length).toBe(0);
    expect(md('| a | b |\n|---|---|---|').root.querySelectorAll('table').length).toBe(0);
    const d = md('| a | b |\n|---|---|');
    expect(d.root.querySelectorAll('th').length).toBe(2);
    expect(d.root.querySelectorAll('td').length).toBe(0);
  });

  it('格里可以有行内格式', () => {
    const { root } = md('| **x** | `y` |\n|---|---|\n| *z* | w |');
    expect(root.querySelectorAll('thead th strong').length).toBe(1);
    expect(root.querySelectorAll('thead th code').length).toBe(1);
    expect(root.querySelectorAll('tbody td em').length).toBe(1);
  });
});

describe('行内', () => {
  it('粗体、斜体、行内代码（星号与下划线两种）', () => {
    const { root } = md('**粗** *斜* `码` __粗2__ _斜2_');
    expect(texts(root, 'strong')).toEqual(['粗', '粗2']);
    expect(texts(root, 'em')).toEqual(['斜', '斜2']);
    expect(texts(root, 'code')).toEqual(['码']);
  });

  it('蛇形名不变斜体；星号不受字母数字限制', () => {
    const src = 'effort_requested 和 a_b_c 以及 x_1 与 y_2 还有 snake_case_name';
    const { root } = md(src);
    expect(root.querySelectorAll('em, strong').length).toBe(0);
    expect(root.textContent).toBe(src);
    expect(texts(md('foo*bar*baz').root, 'em')).toEqual(['bar']);
  });

  it('定界符后是空白、或结尾前是空白时不配对；配不上的定界符与反引号当字面字符', () => {
    for (const src of ['2 * 3 * 4', '**a **', '** a**', '文 * a * 文', '**abc', '*abc', '`abc', 'a `b`` c', 'x_y']) {
      const { root } = md(src);
      expect(root.querySelectorAll('em, strong, code').length, src).toBe(0);
      expect(root.textContent, src).toBe(src);
    }
  });

  it('粗体里可以套斜体', () => {
    const { root } = md('**粗 *斜* 粗**');
    expect(root.querySelectorAll('strong').length).toBe(1);
    expect(texts(root, 'strong em')).toEqual(['斜']);
  });

  it('反斜杠加 ASCII 标点是字面字符；反斜杠加字母原样保留', () => {
    const { root } = md('\\*字面\\* 和 C:\\dir 与 \\\\');
    expect(root.querySelectorAll('em').length).toBe(0);
    expect(root.textContent).toBe('*字面* 和 C:\\dir 与 \\');
  });

  it('代码段：反引号串配同长度串，两头有空格且不全是空格时各去一个', () => {
    const { root } = md('``a`b`` 和 `  x  ` 和 `   ` 和 `` `y` ``');
    expect(texts(root, 'code')).toEqual(['a`b', ' x ', '   ', '`y`']);
    const stars = md('`**x**` 与 `<b>`');
    expect(stars.root.querySelectorAll('strong, b').length).toBe(0);
    expect(texts(stars.root, 'code')).toEqual(['**x**', '<b>']);
  });
});

describe('链接', () => {
  it('http(s) 放行：按钮加紧跟的 span（网址），没有 a 与 href；点击调一次 onOpenLink(原网址)', () => {
    const url = 'https://example.com/a?b=1&c=2';
    const { root, onOpenLink } = md('看 [官网](' + url + ') 吧');
    expect(root.querySelectorAll('a, [href]').length).toBe(0);
    const btns = Array.from(root.querySelectorAll('button'));
    expect(btns.length).toBe(1);
    expect(btns[0].getAttribute('type')).toBe('button');
    expect(btns[0].textContent).toBe('官网');
    const next = btns[0].nextElementSibling as HTMLElement;
    expect(next && next.tagName).toBe('SPAN');
    expect(next.textContent).toBe(url);
    fireEvent.click(btns[0]);
    expect(onOpenLink).toHaveBeenCalledTimes(1);
    expect(onOpenLink).toHaveBeenCalledWith(url);
  });

  it('协议不分大小写，网址原样传回；不解码实体', () => {
    const a = md('[a](HtTpS://X.example/Path)');
    fireEvent.click(a.root.querySelector('button')!);
    expect(a.onOpenLink).toHaveBeenCalledWith('HtTpS://X.example/Path');
    const b = md('[a](http://x.example/?a=1&amp;b=2)');
    fireEvent.click(b.root.querySelector('button')!);
    expect(b.onOpenLink).toHaveBeenCalledWith('http://x.example/?a=1&amp;b=2');
    expect(b.root.querySelector('button + span')!.textContent).toBe('http://x.example/?a=1&amp;b=2');
  });

  it('被拒的（javascript:、data:、mailto:、相对地址、//host 等）只渲染链接文字', () => {
    const bad = ['javascript:alert', 'JAVASCRIPT:alert', 'data:text/plain,hi', 'mailto:a@b.example', '/rel/path', '../x',
      '//evil.example/x', 'ftp://x.example', 'http:/x.example', 'https://', 'http://', '#frag', 'vbscript:x'];
    for (const url of bad) {
      const { root, onOpenLink } = md('[文字](' + url + ')');
      expect(root.querySelectorAll('button, a').length, url).toBe(0);
      expect(root.textContent, url).toBe('文字');
      expect(onOpenLink).not.toHaveBeenCalled();
    }
  });

  it('链接文字为空、![…](…) 形式、带标题的链接都不算链接；尖括号自动链接与裸网址也不变链接', () => {
    for (const src of ['[](https://x.example)', '![alt](https://x.example/a.png)', '[a](https://x.example "title")']) {
      const { root } = md(src);
      expect(root.querySelectorAll('button, a, img').length, src).toBe(0);
      expect(root.textContent, src).toBe(src);
    }
    const { root } = md('<https://auto.example> 与 https://bare.example/x');
    expect(root.querySelectorAll('button, a').length).toBe(0);
    expect(root.textContent).toBe('<https://auto.example> 与 https://bare.example/x');
  });
});

describe('原始 HTML 与不支持的语法', () => {
  it('原始 HTML 原样当文字，不解码实体', () => {
    const src = '<img src=x onerror=alert(1)>\n\n<script>alert(1)</script>\n\n<b>bold</b> &amp; &lt;i&gt; &copy;\n\n<div style="x">y</div>';
    const { root } = md(src);
    expect(root.querySelectorAll('img, script, b, i, style, iframe').length).toBe(0);
    expect(root.querySelectorAll('[style], [onerror]').length).toBe(0);
    const t = root.textContent || '';
    expect(t).toContain('<img src=x onerror=alert(1)>');
    expect(t).toContain('<script>alert(1)</script>');
    expect(t).toContain('<b>bold</b> &amp; &lt;i&gt; &copy;');
    expect(t).toContain('<div style="x">y</div>');
  });

  it('引用块、分隔线、Setext 标题、缩进代码、删除线、任务列表都原样当文字', () => {
    expect(md('> quote\n> more').root.querySelector('p')!.textContent).toBe('> quote\n> more');
    expect(md('> quote\n> more').root.querySelectorAll('blockquote').length).toBe(0);
    expect(md('---').root.textContent).toBe('---');
    expect(md('---').root.querySelectorAll('hr').length).toBe(0);
    expect(md('Title\n===').root.querySelector('p')!.textContent).toBe('Title\n===');
    expect(md('    indented').root.querySelectorAll('pre').length).toBe(0);
    expect(md('    indented').root.textContent).toBe('indented');
    expect(md('~~del~~ [^1]').root.querySelectorAll('del, s').length).toBe(0);
    expect(md('~~del~~ [^1]').root.textContent).toBe('~~del~~ [^1]');
    expect(md('- [ ] t').root.querySelectorAll('input').length).toBe(0);
    expect(listShape(topLists(md('- [ ] t').root)[0])).toEqual(['[ ] t']);
  });
});

describe('元素与属性的允许集合', () => {
  it('一份混合文档：元素与属性都在允许集合里；className 加在根上；空文档不报错', () => {
    const big = ['# T', '', '段落 **b** *i* `c` [ok](https://x.example) [bad](javascript:alert) <img src=x onerror=alert(1)>', '',
      '- a', '  - b', '3. c', '', '```', '<script>alert(1)</script>', '```', '', '| h | i |', '|:--|--:|', '| 1 | 2 |', '',
      '> q', '---', '[](https://x.example)'].join('\n');
    const { root } = md(big);
    expect(audit(root)).toEqual([]);
    expect(root.querySelectorAll('img, script, a').length).toBe(0);
    expect(document.querySelector('[role="status"]')).toBeNull();
    expect(md('x', { className: 'gate-md' }).root.classList.contains('gate-md')).toBe(true);
    expect(md('').root).not.toBeNull();
  });
});

describe('返工修复的回归（B2、B5、B6、B7）', () => {
  const readCss = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');
  const ruleBodies = (css: string, selectorRe: RegExp) => {
    const out: string[] = [];
    for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const selector = m[1].trim().replace(/\s+/g, ' ');
      if (selectorRe.test(selector)) out.push(m[2]);
    }
    return out;
  };

  it('行内代码的规则只盖到非 pre 里的 code，代码块里的字体、边框、底色、内边距、圆角不被盖掉（返工 B2）', () => {
    const css = readCss('src/components/SafeMarkdown.css').replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
    const inline = ruleBodies(css, /^\.tt-md\s*:not\(pre\)\s*>\s*code$/);
    expect(inline.length, '行内代码规则应限定到非 pre 内的 code').toBe(1);
    expect(inline[0]).toMatch(/font:\s*var\(--tt-mono-sm\)/);
    expect(inline[0]).toMatch(/background:\s*var\(--tt-surface-2\)/);
    expect(inline[0]).toMatch(/border-radius:\s*var\(--tt-radius-sm\)/);
    expect(ruleBodies(css, /^\.tt-md code$/).length, '不该有不限定的 .tt-md code 规则').toBe(0);
    const pre = ruleBodies(css, /^\.tt-md pre$/);
    expect(pre.length).toBe(1);
    expect(pre[0]).toMatch(/font:\s*var\(--tt-mono-md\)/);
    expect(pre[0]).toMatch(/white-space:\s*pre/);
    const { root } = md('```\ncode\n```');
    expect(root.querySelectorAll('pre > code').length).toBe(1);
  });

  it('列表项里缩进到项文字列的围栏与标题并入项的文字，列表不被拦腰截断（返工 B5）', () => {
    const fenced = md('- a\n  ```\n  x\n  ```\n- b');
    expect(fenced.root.querySelectorAll('pre').length, '围栏并入项文字，不再另起代码块').toBe(0);
    expect(topLists(fenced.root).length, '只有一个列表').toBe(1);
    expect(Array.from(fenced.root.querySelectorAll('li')).length).toBe(2);
    expect(textOf(fenced.root)).toContain('x');
    const headed = md('- a\n  # x\n- b');
    expect(headed.root.querySelectorAll('h1,h2,h3,h4,h5,h6').length, '标题并入项文字，不再另起标题').toBe(0);
    expect(topLists(headed.root).length).toBe(1);
    expect(Array.from(headed.root.querySelectorAll('li')).length).toBe(2);
    expect(textOf(headed.root)).toContain('# x');
    const afterSub = md('- a\n  - b\n  ```\n  x\n  ```\n- c');
    expect(afterSub.root.querySelectorAll('pre').length).toBe(0);
    expect(topLists(afterSub.root).length).toBe(1);
    expect(Array.from(afterSub.root.querySelectorAll('li')).length).toBe(3);
    const out = md('- a\n```\nx\n```');
    expect(out.root.querySelectorAll('pre').length, '缩进更小才结束列表').toBe(1);
    expect(out.root.querySelectorAll('li').length).toBe(1);
  });

  it('网址认括号配对：带括号的合法网址成链接，带括号的被拒网址只留链接文字（返工 B7）', () => {
    const ok = md('[w](https://h/a_(b))');
    const btn = ok.root.querySelector('button') as HTMLElement;
    expect(btn).not.toBeNull();
    expect(btn.textContent).toBe('w');
    expect((btn.nextElementSibling as HTMLElement).textContent).toBe('https://h/a_(b)');
    fireEvent.click(btn);
    expect(ok.onOpenLink).toHaveBeenCalledWith('https://h/a_(b)');
    for (const url of ['javascript:alert(1)', 'data:text/html,f(1)', 'vbscript:msgbox(1)']) {
      const { root, onOpenLink } = md('[这一条被拒](' + url + ')');
      expect(root.querySelectorAll('button, a').length, url).toBe(0);
      expect(root.textContent, url + ' 应只剩链接文字').toBe('这一条被拒');
      expect(onOpenLink).not.toHaveBeenCalled();
    }
  });

  it('N 个 [ 共用一个 ]( 加长网址也是线性（返工 B6）', () => {
    const n = 131072;
    const src = '['.repeat(n) + '](' + 'y'.repeat(2 * n - 2);
    const t0 = Date.now();
    const out = parseMarkdown(src);
    const used = Date.now() - t0;
    expect(used, '256 KiB 的 ' + n + ' 个 [ 加 ]( 加长网址用时 ' + used + 'ms').toBeLessThan(2000);
    expect(out.length).toBeGreaterThan(0);
  }, 30000);
});

describe('parseMarkdown 的性能与 parseInlines 的细节', () => {
  const SIZE = 256 * 1024;
  const timed = (name: string, source: string) => {
    const t0 = Date.now();
    const out = parseMarkdown(source);
    const used = Date.now() - t0;
    expect(used, name + ' 用时 ' + used + 'ms').toBeLessThan(2000);
    expect(out).toBeDefined();
  };

  it('256 KiB 的病态输入都在 2 秒内返回', () => {
    timed('全是 *', '*'.repeat(SIZE));
    timed('全是 _', '_'.repeat(SIZE));
    timed('全是 [', '['.repeat(SIZE));
    timed('全是反引号', '`'.repeat(SIZE));
    timed('[a]( 重复', '[a]('.repeat(SIZE / 4));
    timed('**a 重复', '**a'.repeat(Math.floor(SIZE / 3)));
    const lines: string[] = [];
    for (let i = 0; i < 2000; i += 1) lines.push(' '.repeat(2 * i) + '- x');
    timed('逐行缩进的列表', lines.join('\n'));
    timed('混合', '*_`[]()!\\<>|-# '.repeat(Math.floor(SIZE / 15)));
    timed('竖线表头重复', '| a '.repeat(Math.floor(SIZE / 4)));
    timed('围栏不闭合', '```\n' + 'x\n'.repeat(SIZE / 2));
  }, 60000);

  it('经 SafeMarkdown 渲染 64 KiB 的病态输入也不卡死', () => {
    for (const src of ['*'.repeat(64 * 1024), '[a]('.repeat(16 * 1024), '`a'.repeat(32 * 1024)]) {
      const t0 = Date.now();
      const { unmount } = md(src);
      expect(Date.now() - t0, src.slice(0, 8)).toBeLessThan(5000);
      unmount();
    }
  }, 60000);

  it('parseInlines 是纯函数：同样的输入得到同样的结构', () => {
    const src = '**粗** *斜* `码` [a](https://x.example) [b](javascript:x) <b>c</b>';
    expect(parseInlines(src)).toEqual(parseInlines(src));
    const nodes = parseInlines(src);
    const kinds = nodes.map((n) => n.type);
    expect(kinds).toContain('strong');
    expect(kinds).toContain('em');
    expect(kinds).toContain('code');
    expect(kinds).toContain('link');
    expect(nodes.filter((n) => n.type === 'link')).toEqual([
      { type: 'link', children: [{ type: 'text', value: 'a' }], url: 'https://x.example' },
    ]);
    expect(nodes.filter((n) => n.type === 'code')).toEqual([{ type: 'code', value: '码' }]);
    expect(nodes.filter((n) => n.type === 'text').map((n) => (n.type === 'text' ? n.value : '')).join('|'))
      .toBe(' | | | |b| <b>c</b>');
  });
});
