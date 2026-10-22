// 任务页样式取值自测（合同 Steps 11、D13、§8）：三份 CSS 的取值、令牌、px 注释与 W4 的坑。
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (name: string) => readFileSync(resolve(process.cwd(), 'src/pages/tasks', name), 'utf8');

const LIST = read('tasks-list.css');
const DETAIL = read('tasks-detail.css');
const TABS = read('tasks-tabs.css');
const ALL = `${LIST}\n${DETAIL}\n${TABS}`;
const tok = (name: string) => `var(--tt-${name})`;

/** 一条规则：选择器之后、第一个 } 之前的声明块（去掉注释）。 */
function block(css: string, selector: string): string {
  const at = css.indexOf(selector);
  expect(at, `找不到选择器 ${selector}`).toBeGreaterThanOrEqual(0);
  const open = css.indexOf('{', at);
  const close = css.indexOf('}', open);
  return css.slice(open + 1, close).replace(/\/\*[\s\S]*?\*\//g, '');
}

function decl(body: string, name: string): string {
  const m = new RegExp(`(?:^|;)\\s*${name}\\s*:\\s*([^;]+)`, 'i').exec(body);
  expect(m, `声明块里没有 ${name}`).toBeTruthy();
  return m![1].trim();
}

describe('列表样式取值', () => {
  it('两栏、左栏、左栏头', () => {
    const cols = block(ALL, '.tasks-list__cols');
    expect(decl(cols, 'display')).toBe('flex');
    expect(decl(cols, 'gap')).toBe(tok('space-4'));
    expect(decl(cols, 'align-items')).toBe('flex-start');
    const left = block(ALL, '.tasks-list__left {');
    expect(decl(left, 'width')).toBe('320px');
    expect(decl(left, 'flex')).toBe('none');
    expect(decl(left, 'background')).toBe(tok('surface-1'));
    expect(decl(left, 'border')).toBe(`1px solid ${tok('border')}`);
    expect(decl(left, 'border-radius')).toBe(tok('radius-lg'));
    const head = block(ALL, '.tasks-list__head');
    expect(decl(head, 'display')).toBe('flex');
    expect(decl(head, 'flex-direction')).toBe('column');
    expect(decl(head, 'gap')).toBe(tok('space-2'));
    expect(decl(head, 'padding')).toBe(tok('space-3'));
  });

  it('搜索框：高 32、左右内边距、边框、圆角、字号', () => {
    const input = block(ALL, '.tasks-list__search-input');
    expect(decl(input, 'height')).toBe('32px');
    expect(decl(input, 'padding-left')).toBe(tok('space-8'));
    expect(decl(input, 'padding-right')).toBe(tok('space-2'));
    expect(decl(input, 'border')).toBe(`1px solid ${tok('border-strong')}`);
    expect(decl(input, 'border-radius')).toBe(tok('radius-md'));
    expect(decl(input, 'font')).toBe(tok('text-md'));
  });

  it('胶囊：平时、按下、间距', () => {
    const chip = block(ALL, '.tasks-list__chip {');
    expect(decl(chip, 'height')).toBe('28px');
    expect(decl(chip, 'padding-left')).toBe(tok('space-2'));
    expect(decl(chip, 'padding-right')).toBe(tok('space-2'));
    expect(decl(chip, 'border-radius')).toBe(tok('radius-full'));
    expect(decl(chip, 'font')).toBe(tok('text-sm-medium'));
    expect(decl(chip, 'background')).toBe(tok('surface-1'));
    expect(decl(chip, 'border')).toBe(`1px solid ${tok('border-strong')}`);
    expect(decl(chip, 'color')).toBe(tok('text-2'));
    const pressed = block(ALL, '.tasks-list__chip[aria-pressed="true"]');
    expect(decl(pressed, 'background')).toBe(tok('surface-selected'));
    expect(decl(pressed, 'border')).toBe(`1px solid ${tok('primary')}`);
    expect(decl(pressed, 'color')).toBe(tok('text-1'));
    expect(decl(block(ALL, '.tasks-list__chips'), 'gap')).toBe(tok('space-1'));
  });

  it('任务项：最小高、内边距、下边框、选中、竖条、悬停', () => {
    const item = block(ALL, '.tasks-list__item {');
    expect(decl(item, 'min-height')).toBe('52px');
    expect(decl(item, 'padding')).toBe(`${tok('space-2')} ${tok('space-3')}`);
    expect(decl(item, 'border-bottom')).toMatch(/^1px/);
    expect(decl(block(ALL, '.tasks-list__item[aria-selected="true"]'), 'background')).toBe(tok('surface-selected'));
    expect(decl(block(ALL, '.tasks-list__item[aria-selected="true"]'), 'box-shadow'))
      .toBe(`inset 2px 0 0 ${tok('primary')}`);
    expect(decl(block(ALL, '.tasks-list__item:hover'), 'background')).toBe(tok('surface-3'));
    expect(decl(block(ALL, '.tasks-list__danger'), 'color')).toBe(tok('danger-text'));
  });

  it('右栏头、attempt 表、下一步区', () => {
    const head = block(ALL, '.tasks-list__right-head');
    expect(decl(head, 'padding')).toBe(`${tok('space-3')} ${tok('space-4')}`);
    const wrap = block(ALL, '.tasks-list__table .tt-table-wrap');
    expect(decl(wrap, 'border')).toBe('0');
    expect(decl(wrap, 'border-radius')).toBe('0');
    expect(decl(wrap, 'border-top')).toBe(`1px solid ${tok('border')}`);
    expect(decl(block(ALL, '.tasks-list__table-wrap'), 'min-width')).toBe('1040px');
    expect(decl(block(ALL, '.tasks-list__next'), 'margin')).toBe(tok('space-4'));
    expect(decl(block(ALL, '.tasks-list__right'), 'min-width')).toBe('0');
  });
});

describe('详情样式取值', () => {
  it('面包屑条与窄内容区', () => {
    const crumb = block(DETAIL, '.tasks-detail__crumb {');
    expect(decl(crumb, 'padding')).toBe(`${tok('space-5')} ${tok('space-6')} 0`);
    expect(DETAIL).toContain('@container tt-content');
    expect(DETAIL).toContain('max-width: 807px');
    expect(decl(block(DETAIL, '.tasks-detail__crumb {', ), 'padding')).toBe(`${tok('space-5')} ${tok('space-6')} 0`);
    const narrow = DETAIL.slice(DETAIL.indexOf('@container'));
    expect(narrow).toContain(`padding: ${tok('space-4')}`);
  });

  it('页头、dl、下一步区、页签列表', () => {
    const head = block(DETAIL, '.tasks-detail__head');
    expect(decl(head, 'display')).toBe('flex');
    expect(decl(head, 'flex-wrap')).toBe('wrap');
    expect(decl(head, 'gap')).toBe(tok('space-2'));
    const meta = block(DETAIL, '.tasks-detail__meta {');
    expect(decl(meta, 'display')).toBe('flex');
    expect(decl(meta, 'flex-wrap')).toBe('wrap');
    expect(decl(meta, 'gap')).toBe(`${tok('space-0_5')} ${tok('space-3')}`);
    expect(decl(block(DETAIL, '.tasks-detail__tabs .tt-tabs__list'), 'overflow-x')).toBe('auto');
    expect(decl(block(DETAIL, '.tasks-detail__tabs'), 'min-width')).toBe('0');
  });
});

describe('页签样式取值与通用规则', () => {
  it('摘要卡、检查表与文件表最小宽', () => {
    const sum = block(TABS, '.tasks-tab__summary');
    expect(decl(sum, 'max-width')).toBe('880px');
    expect(decl(sum, 'padding')).toBe(`${tok('space-5')} ${tok('space-6')}`);
    expect(decl(sum, 'background')).toBe(tok('surface-1'));
    expect(decl(sum, 'border')).toBe(`1px solid ${tok('border')}`);
    expect(decl(sum, 'border-radius')).toBe(tok('radius-lg'));
    expect(decl(block(TABS, '.tasks-tab__table .tt-table-wrap'), 'min-width')).toBe('560px');
    expect(decl(block(TABS, '.tasks-tab'), 'min-width')).toBe('0');
  });

  it('令牌：圆角、字号、层级、阴影只用 --tt-*；grid 里没有裸 1fr', () => {
    for (const css of [LIST, DETAIL, TABS]) {
      for (const m of css.matchAll(/([-a-z]+)\s*:\s*([^;{}]+);/g)) {
        const name = m[1];
        const value = m[2].replace(/\s+/g, '');
        if (name === 'border-radius') expect(value).toMatch(/^(var\(--tt-radius-[\w-]+\)|0|0px|inherit)+$/);
        if (name === 'z-index') expect(value).toMatch(/^var\(--tt-z-/);
        if (name === 'box-shadow' && value !== 'none') expect(value).toContain('var(--tt-');
        if (name === 'font' || name === 'font-size') expect(value).toMatch(/^(var\(--tt-|inherit)/);
        if (name === 'grid-template-columns') {
          expect(value.replace(/minmax\([^)]*\)/g, '')).not.toMatch(/(?<![\w(])1fr/);
        }
      }
    }
  });

  it('px 字面量同一行带出处注释；没有十六进制颜色与颜色函数', () => {
    for (const css of [LIST, DETAIL, TABS]) {
      css.split('\n').forEach((line, i) => {
        const code = line.replace(/\/\*[\s\S]*?\*\//g, '');
        const sawComment = line.includes('/*');
        for (const m of code.matchAll(/(?<![\w.#-])(-?\d*\.?\d+)px\b/g)) {
          if (Math.abs(Number(m[1])) === 0 || Math.abs(Number(m[1])) === 1) continue;
          expect(sawComment, `第 ${i + 1} 行的 ${m[0]} 没有同一行的出处注释：${line.trim()}`).toBe(true);
        }
        expect(line, `第 ${i + 1} 行不写十六进制颜色`).not.toMatch(/#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/);
        expect(line, `第 ${i + 1} 行不写颜色函数`).not.toMatch(/\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(/i);
      });
    }
  });

  it('三份 CSS 各有独有的类选择器（接进构建产物的前提）', () => {
    const own = (css: string) => {
      const out = new Set<string>();
      for (const m of css.matchAll(/\.([A-Za-z_][\w-]*)/g)) out.add(m[1]);
      return out;
    };
    const l = own(LIST);
    const d = own(DETAIL);
    const t = own(TABS);
    expect([...l].filter((c) => !d.has(c) && !t.has(c)).length).toBeGreaterThan(0);
    expect([...d].filter((c) => !l.has(c) && !t.has(c)).length).toBeGreaterThan(0);
    expect([...t].filter((c) => !l.has(c) && !d.has(c)).length).toBeGreaterThan(0);
  });
});
