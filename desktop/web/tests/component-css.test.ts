import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

// 组件 CSS 取值的静态核对（与门禁 S5 同向，执行端自测用）：读 CSS 文本，断言关键取值在。
const read = (rel: string) => readFileSync(join(process.cwd(), rel), 'utf8');

describe('组件 CSS 取值', () => {
  it('Table.css：表头 sticky + z-sticky、行高 40/44/52、数字列右对齐、选中行左 2px 主色', () => {
    const css = read('src/components/Table.css');
    expect(css).toMatch(/position:\s*sticky/);
    expect(css).toMatch(/z-index:\s*var\(--tt-z-sticky\)/);
    expect(css).toMatch(/data-row-height="40"\][^{]*\{[^}]*height:\s*40px/);
    expect(css).toMatch(/data-row-height="44"\][^{]*\{[^}]*height:\s*44px/);
    expect(css).toMatch(/data-row-height="52"\][^{]*\{[^}]*height:\s*52px/);
    expect(css).toMatch(/\.tt-num\s*\{[^}]*text-align:\s*right/);
    expect(css).toMatch(/inset\s+2px\s+0\s+0\s+var\(--tt-primary\)/);
    expect(css).toMatch(/white-space:\s*nowrap/);
  });

  it('ConnectionPill.css：三态色调、浮层宽 240、层级 popover', () => {
    const css = read('src/components/ConnectionPill.css');
    expect(css).toMatch(/var\(--tt-tone-success-fg\)/);
    expect(css).toMatch(/data-state="reconnecting"\][^{]*\{[^}]*var\(--tt-tone-warning-fg\)/);
    expect(css).toMatch(/data-state="disconnected"\][^{]*\{[^}]*var\(--tt-danger-text\)/);
    expect(css).toMatch(/width:\s*240px/);
    expect(css).toMatch(/z-index:\s*var\(--tt-z-popover\)/);
    expect(css).toMatch(/position:\s*absolute/);
  });

  it('SegmentedControl / Switch / Checkbox / Tabs / TextField：关键取值在', () => {
    expect(read('src/components/SegmentedControl.css')).toMatch(/aria-checked="true"/);
    expect(read('src/components/SegmentedControl.css')).toMatch(/height:\s*28px/);
    expect(read('src/components/Switch.css')).toMatch(/var\(--tt-radius-full\)/);
    expect(read('src/components/Switch.css')).toMatch(/width:\s*32px/);
    expect(read('src/components/Checkbox.css')).toMatch(/width:\s*16px/);
    expect(read('src/components/Tabs.css')).toMatch(/height:\s*38px/);
    expect(read('src/components/Tabs.css')).toMatch(/border-bottom:\s*2px\s+solid\s+var\(--tt-primary\)/);
    expect(read('src/components/TextField.css')).toMatch(/height:\s*32px/);
    expect(read('src/components/Select.css')).toMatch(/appearance:\s*none/);
  });

  it('Skeleton.css：用 tt-skel、无动画/过渡/渐变', () => {
    const css = read('src/components/Skeleton.css');
    expect(css).toMatch(/\.tt-skel/);
    expect(css).not.toMatch(/animation|transition|gradient|@keyframes/);
  });
});
