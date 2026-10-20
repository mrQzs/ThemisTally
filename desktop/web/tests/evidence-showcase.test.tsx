import { cleanup, render, act, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import EvidenceShowcase from '../src/showcase/EvidenceShowcase';
import FormsShowcase from '../src/showcase/FormsShowcase';

afterEach(cleanup);

const DEMOS = ['text-viewer', 'text-viewer-jsonl', 'safe-markdown', 'effort', 'masked-value', 'command-line', 'next-step'];
const textOf = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const demo = (name: string) => {
  const nodes = document.querySelectorAll(`[data-demo="${name}"]`);
  expect(nodes.length, `应恰有一个 data-demo="${name}"`).toBe(1);
  return nodes[0] as HTMLElement;
};
const buttonsByText = (root: ParentNode, text: string) =>
  Array.from(root.querySelectorAll('button')).filter((b) => textOf(b) === text);
const buttonByText = (root: ParentNode, text: string) => {
  const hits = buttonsByText(root, text);
  expect(hits.length, `找不到「${text}」`).toBeGreaterThan(0);
  return hits[0] as HTMLButtonElement;
};
const press = async (btn: HTMLElement) => {
  await act(async () => {
    fireEvent.click(btn);
  });
};
async function settle(cond: () => boolean, label: string) {
  for (let i = 0; i < 120; i += 1) {
    if (cond()) return;
    await act(async () => {
      await new Promise((r) => setTimeout(r, 25));
    });
  }
  throw new Error('等待超时：' + label);
}
const shown = (sec: HTMLElement, n: number) => new RegExp(`已显示\\s*${n}\\s*页`).test(textOf(sec));

describe('EvidenceShowcase 演示', () => {
  it('七节，data-demo 依次为约定值，每节是 section.showcase__section 且有一个 h2.showcase__h2', () => {
    render(<EvidenceShowcase />);
    expect(Array.from(document.querySelectorAll('[data-demo]')).map((e) => e.getAttribute('data-demo'))).toEqual(DEMOS);
    for (const name of DEMOS) {
      const sec = demo(name);
      expect(sec.tagName).toBe('SECTION');
      expect(sec.classList.contains('showcase__section')).toBe(true);
      const h2s = sec.querySelectorAll('h2.showcase__h2');
      expect(h2s.length).toBe(1);
      expect(textOf(h2s[0])).not.toBe('');
      expect(textOf(h2s[0])).not.toMatch(/Button/);
    }
  });

  it('不渲染 role=status、对话框、菜单；没有文字的按钮都有 aria-label；按钮文字不含「亮」「暗」「跟随系统」', () => {
    render(<EvidenceShowcase />);
    expect(document.querySelector('[role="status"]')).toBeNull();
    expect(document.querySelectorAll('[role="dialog"], [role="alertdialog"], [role="menu"], [aria-modal], dialog').length).toBe(0);
    const bad = Array.from(document.querySelectorAll('button'))
      .filter((b) => textOf(b) === '' && !(b.getAttribute('aria-label') || '').trim());
    expect(bad.length).toBe(0);
    for (const b of Array.from(document.querySelectorAll('button'))) {
      expect(textOf(b)).not.toMatch(/亮|暗|跟随系统/);
    }
    expect(textOf(document.body)).not.toContain('跟随系统');
  });

  it('W1 样例在 DOM 里只是文字：没有 img、script、a、带 on 或 href 的元素，没有 ESC 字符，也没有 [31m', () => {
    render(<EvidenceShowcase />);
    expect(document.body.querySelectorAll('img, script, a, iframe, object, embed, style, link').length).toBe(0);
    expect(document.body.querySelectorAll('[onerror], [href], [src], [srcdoc]').length).toBe(0);
    const sec = demo('text-viewer');
    const text = sec.textContent || '';
    expect(text).toContain('<img src=x onerror=alert(1)>');
    expect(text).toContain('<script>alert(1)</script>');
    expect(text).toContain('已按合同实现 logs cat。');
    expect(text).toContain('- self_checks: V01–V08 通过');
    expect(text).toMatch(/https?:\/\/\S+/);
    expect((document.body.textContent || '').includes('\u001b')).toBe(false);
    expect((document.body.textContent || '').includes('[31m')).toBe(false);
    expect(sec.querySelector('.tt-viewer')).not.toBeNull();
  });

  it('text-viewer 一节：[继续加载] 依次加到三页、到末尾；分片显示第 2/2 片；模拟文件已变化出提示条，[从头读取] 回第 1 页', async () => {
    render(<EvidenceShowcase />);
    const sec = demo('text-viewer');
    expect(shown(sec, 1)).toBe(true);
    for (let i = 0; i < 6 && !textOf(sec).includes('已到末尾'); i += 1) {
      const btns = buttonsByText(sec, '继续加载');
      expect(btns.length).toBeGreaterThan(0);
      await press(btns[0]);
      await settle(() => buttonsByText(sec, '正在加载…').length === 0, '加载完成');
    }
    expect(shown(sec, 3)).toBe(true);
    expect(textOf(sec)).toContain('已到末尾');
    expect(textOf(sec)).toMatch(/第\s*2\/2\s*片/);
    expect(buttonsByText(sec, '继续加载').length).toBe(0);
    await press(buttonByText(sec, '模拟文件已变化'));
    await settle(() => sec.querySelector('.tt-banner') !== null, '提示条出现');
    expect(textOf(sec.querySelector('.tt-banner'))).toContain('文件已变化');
    await press(buttonByText(sec.querySelector('.tt-banner')!, '从头读取'));
    await settle(() => shown(sec, 1), '回到第 1 页');
    expect(sec.querySelector('.tt-banner')).toBeNull();
  }, 30000);

  it('text-viewer-jsonl 一节：两种隐藏行说明、第 1/2 片；[继续加载] 给第 2/2 片，最后一页到末尾', async () => {
    render(<EvidenceShowcase />);
    const sec = demo('text-viewer-jsonl');
    const t0 = textOf(sec);
    expect(t0).toContain('这一行不是合法 JSON，已隐藏');
    expect(t0).toContain('这一行超过 4 MiB，已隐藏');
    expect(t0).toMatch(/第\s*1\/2\s*片/);
    expect(t0).toContain('agent_start');
    for (let i = 0; i < 6 && !textOf(sec).includes('已到末尾'); i += 1) {
      const btns = buttonsByText(sec, '继续加载');
      expect(btns.length).toBeGreaterThan(0);
      await press(btns[0]);
      await settle(() => buttonsByText(sec, '正在加载…').length === 0, '加载完成');
    }
    expect(textOf(sec)).toContain('已到末尾');
    expect(textOf(sec)).toMatch(/第\s*2\/2\s*片/);
  }, 30000);

  it('safe-markdown 一节：摘要原文、表、代码块、粗斜体、蛇形名；https 链接渲染成按钮加网址，点了只显示「上次请求打开：…」', async () => {
    render(<EvidenceShowcase />);
    const sec = demo('safe-markdown');
    expect(Array.from(sec.querySelectorAll('h2:not(.showcase__h2)')).map((e) => textOf(e)))
      .toContain('logs-cat.v2 / attempt-002');
    expect(Array.from(sec.querySelectorAll('h3')).map((e) => textOf(e))).toContain('复审需要关注');
    expect(Array.from(sec.querySelectorAll('li')).some((li) => textOf(li).includes('基线：9461d31'))).toBe(true);
    expect(sec.querySelector('table th')).not.toBeNull();
    expect(new Set(Array.from(sec.querySelectorAll('table th')).map((t) => t.getAttribute('class') || '')).size).toBeGreaterThan(1);
    expect(sec.querySelector('pre code')).not.toBeNull();
    expect(sec.querySelector('strong')).not.toBeNull();
    expect(sec.querySelector('em')).not.toBeNull();
    expect(textOf(sec)).toMatch(/[A-Za-z]+_[A-Za-z_]+/);
    expect(sec.querySelectorAll('img, script, a, iframe, b, i, u, blockquote, hr, del, object, embed, style, link, form, input, details, summary').length).toBe(0);
    const links = Array.from(sec.querySelectorAll('button')).filter(
      (b) => b.nextElementSibling && b.nextElementSibling.tagName === 'SPAN' && /^https?:\/\//.test(textOf(b.nextElementSibling)),
    );
    expect(links.length).toBeGreaterThan(0);
    for (const el of Array.from(sec.querySelectorAll('button, span'))) {
      expect(textOf(el)).not.toMatch(/^javascript:/i);
    }
    const url = textOf(links[0].nextElementSibling);
    await press(links[0] as HTMLElement);
    await settle(() => /上次请求打开：\s*https?:\/\/\S+/.test(textOf(sec)), '上次请求打开');
    expect(textOf(sec).replace(/：\s+/g, '：')).toContain('上次请求打开：' + url);
    expect(document.querySelectorAll('[role="dialog"], [role="alertdialog"]').length).toBe(0);
  }, 30000);

  it('effort 一节六种情形；masked-value 一节四种占位', () => {
    render(<EvidenceShowcase />);
    const eff = Array.from(demo('effort').querySelectorAll('.tt-effort'));
    expect(eff.length).toBe(6);
    expect(eff.map((e) => e.getAttribute('data-state')).sort()).toEqual(['differs', 'differs', 'none', 'same', 'same', 'unknown']);
    const texts = eff.map((e) => textOf(e));
    expect(texts).toContain('—');
    expect(texts.filter((t) => /^要求 \S+ · 生效 未知$/.test(t)).length).toBe(1);
    expect(texts.filter((t) => /与要求不同$/.test(t)).length).toBe(2);
    expect(texts.some((t) => /^要求 \S+ · 生效 \S+、\S+$/.test(t))).toBe(true);
    const masked = Array.from(demo('masked-value').querySelectorAll('span[title="内核已遮蔽"]')).map((e) => e.textContent);
    expect(masked.slice().sort()).toEqual(['（含疑似凭据，不显示）', '（值不显示）', '<redacted>', '（疑似凭据的键名）'].sort());
  });

  it('command-line 一节两种尺寸；next-step 一节带命令与不带命令各一个', () => {
    render(<EvidenceShowcase />);
    const cmd = demo('command-line');
    const codes = Array.from(cmd.querySelectorAll('code')).map((c) => c.textContent);
    expect(codes).toContain('bash scripts/dispatch-pi.sh config preset use economy');
    expect(codes).toContain('/plan-task logs-cat');
    const sm = cmd.querySelector('.tt-cmd--sm') as HTMLElement;
    expect(sm && sm.querySelector('code')!.textContent).toBe('/plan-task logs-cat');
    expect(cmd.querySelectorAll('button[aria-label="复制命令"]').length).toBe(2);
    const next = demo('next-step');
    expect(next.querySelectorAll('.tt-cmd--sm').length).toBe(1);
    expect(next.querySelectorAll('svg').length).toBeGreaterThanOrEqual(2);
    expect(next.querySelector('[role]')).toBeNull();
  });

  it('FormsShowcase：连接胶囊那一行加了类 showcase-pill-row，仍是 showcase__row，三个胶囊都在里面（S4b）', () => {
    render(<FormsShowcase />);
    const sec = demo('connection');
    const row = sec.querySelector('.showcase-pill-row') as HTMLElement;
    expect(row).not.toBeNull();
    expect(row.classList.contains('showcase__row')).toBe(true);
    expect(row.querySelectorAll('button.tt-pill').length).toBe(3);
    expect(sec.querySelectorAll('.showcase-pill-row').length).toBe(1);
  });
});
