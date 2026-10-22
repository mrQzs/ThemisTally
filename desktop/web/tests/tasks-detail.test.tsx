// attempt 详情页头自测（合同 Steps 6、D05、D06）：面包屑与 href、h1 规则、状态标签与思考档位、元信息 dl、下一步与复制。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AttemptDetailView } from '../src/pages/tasks/AttemptDetailView';
import type { AttemptData, Envelope, StatusRow } from '../src/api';

afterEach(cleanup);

const row = (over: Record<string, unknown> = {}): StatusRow => ({
  attempt: 'logs-cat/attempt-002', task_id: 'logs-cat', plan_version: 2, attempt_no: 2, state: 'NEEDS_REVIEW',
  started: true, exit_code: 0, wall_seconds: 1719.4, events_ok: true, violations: 0, checks: '8/8',
  check_mode: 'fresh', verdict: null, failure_class: null, human_minutes: 0.0, tokens: 4210385, cost: null,
  cost_status: 'unknown', effort_requested: 'max', effort_effective: 'high',
  ...over,
} as unknown as StatusRow);

function attemptEnv(over: Record<string, unknown> = {}): Envelope<AttemptData> {
  return {
    ok: true, exit_code: 0, output: [], messages: [], elapsed_ms: 0,
    command: ['logs', 'show', 'logs-cat/attempt-002'],
    data: {
      task: 'logs-cat', attempt: 'attempt-002', state: 'NEEDS_REVIEW', state_at: '2026-10-18T06:21:40Z',
      summary: { bytes: 512, truncated: false, text: '# 标题\n\n正文' },
      evidence: [{ path: 'summary.md', bytes: 512 }, { path: 'candidate.patch', bytes: 18342 }],
      skipped_links: 0,
      ...over,
    } as unknown as AttemptData,
  };
}

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: Element | null, sel: string) => Array.from((root ?? document).querySelectorAll(sel));
function dlOf() {
  const out: Record<string, string> = {};
  qa(document, 'dt').forEach((dt) => {
    const dd = dt.nextElementSibling;
    out[text(dt)] = dd ? text(dd) : '';
  });
  return out;
}

function mount(over: { row?: StatusRow | null; env?: Envelope<AttemptData> | null; tab?: string } = {}) {
  const onTabChange = vi.fn();
  const navigate = vi.fn();
  render(
    <AttemptDetailView
      task="logs-cat"
      attempt="attempt-002"
      row={over.row === undefined ? row() : over.row}
      attemptEnv={over.env === undefined ? attemptEnv() : over.env}
      tab={(over.tab ?? 'summary') as never}
      onTabChange={onTabChange}
      mock="offline"
      navigate={navigate}
    />,
  );
  return { onTabChange, navigate };
}

describe('面包屑与页头', () => {
  it('面包屑三项与 href：只带 mock，末项是当前项', () => {
    mount();
    const nav = qa(document, 'nav[aria-label="面包屑"]')[0];
    const links = qa(nav, 'a');
    expect(links.map(text)).toEqual(['任务', 'logs-cat']);
    expect(links[0].getAttribute('href')).toBe('#/tasks?mock=offline');
    expect(links[1].getAttribute('href')).toBe('#/tasks/logs-cat?mock=offline');
    const current = qa(nav, '[aria-current="page"]');
    expect(current.length).toBe(1);
    expect(text(current[0])).toBe('attempt-002');
  });

  it('无修饰键左键被拦下并换路由，带修饰键走默认行为', () => {
    const { navigate } = mount();
    const link = qa(document, 'nav[aria-label="面包屑"] a').filter((a) => text(a) === 'logs-cat')[0];
    const keep = (init: Record<string, unknown> = {}) => {
      let appPrevented = false;
      const listener = (e: Event) => {
        appPrevented = e.defaultPrevented;
        e.preventDefault();
      };
      document.addEventListener('click', listener);
      try {
        fireEvent.click(link, init);
      } finally {
        document.removeEventListener('click', listener);
      }
      return appPrevented;
    };
    expect(keep()).toBe(true);
    expect(navigate).toHaveBeenCalledWith('/tasks/logs-cat?mock=offline');
    expect(keep({ metaKey: true })).toBe(false);
    expect(navigate).toHaveBeenCalledTimes(1);
  });

  it('状态标签 md 与思考档位', () => {
    mount();
    const tag = qa(document, '.tt-status[data-size="md"]')[0];
    expect(text(tag)).toBe('待验收');
    const effort = qa(tag.parentElement!, '.tt-effort')[0];
    expect(effort).toBeTruthy();
    expect(text(effort)).toContain('max');
    expect(text(effort)).toContain('high');
  });

  it('dl 元信息各项与「—」', () => {
    mount();
    const dl = dlOf();
    expect(dl['版本']).toBe('v2');
    expect(dl['用时']).toBe('28 分 39 秒');
    expect(dl['token']).toBe('4,210,385');
    expect(dl['费用']).toBe('未知（只报 token）');
    expect(dl['检查']).toBe('8/8（fresh）');
    expect(dl['越界']).toBe('0');
    const at = qa(document, 'dt').filter((dt) => text(dt) === '状态时间')[0].nextElementSibling!;
    const d = new Date('2026-10-18T06:21:40Z');
    const p = (n: number) => String(n).padStart(2, '0');
    const want = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
    expect(text(at)).toBe(want);
    expect(at.getAttribute('title')).toBe('2026-10-18T06:21:40Z');
  });

  it('status 里没有这一行时写「—」；没有 effort_requested 字段时写未知', () => {
    const sparse = row({ tokens: null, wall_seconds: null, violations: null, checks: null, check_mode: null });
    delete (sparse as unknown as Record<string, unknown>).effort_requested;
    mount({ row: sparse });
    const dl = dlOf();
    expect(dl['用时']).toBe('—');
    expect(dl['token']).toBe('未知');
    expect(dl['检查']).toBe('—');
    expect(dl['越界']).toBe('—');
    const head = qa(document, '.tt-status[data-size="md"]')[0].parentElement!;
    expect(text(head)).toContain('未知');
  });

  it('下一步四种文字与命令、其余状态不显示', () => {
    const cases: Array<[string, string, string]> = [
      ['NEEDS_REVIEW', '这个 attempt 等你验收。验收在规划端会话里进行。', '/review-pi .agent/runs/logs-cat/attempt-002'],
      ['PASS', '已通过，等待集成。集成在规划端会话里进行。', '/review-pi .agent/runs/logs-cat/attempt-002'],
      ['REVISE', '需要出新版本合同返工。', '/plan-task logs-cat'],
      ['ESCALATE', '需要你做决定，见摘要里的阻塞点。', ''],
      ['RUNNING', '', ''],
    ];
    for (const [state, want, command] of cases) {
      cleanup();
      mount({ row: row({ state }), env: attemptEnv({ state }) });
      const next = qa(document, '.tt-next');
      if (!want) {
        expect(next.length, state + ' 不显示下一步').toBe(0);
        continue;
      }
      expect(next.length, state + ' 应显示下一步').toBe(1);
      expect(text(next[0])).toContain(want);
      expect(text(next[0])).toContain('下一步');
      if (command) expect(text(next[0])).toContain(command);
      else expect(qa(next[0], '.tt-cmd').length, '升级与阻塞不带命令').toBe(0);
    }
  });

  it('复制结果三种文字', async () => {
    mount();
    const copy = () => qa(document, '[aria-label="复制命令"]')[0];
    expect(copy()).toBeTruthy();
    await act(async () => {
      fireEvent.click(copy());
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(text(document.body)).toContain('这个环境没有剪贴板接口');
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(window.navigator, 'clipboard', { value: { writeText }, configurable: true });
    await act(async () => {
      fireEvent.click(copy());
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(text(document.body)).toContain('已复制');
    expect(writeText).toHaveBeenCalledWith('/review-pi .agent/runs/logs-cat/attempt-002');
    const bad = vi.fn(() => Promise.reject(new Error('x')));
    Object.defineProperty(window.navigator, 'clipboard', { value: { writeText: bad }, configurable: true });
    await act(async () => {
      fireEvent.click(copy());
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(text(document.body)).toContain('复制失败');
    delete (window.navigator as unknown as { clipboard?: unknown }).clipboard;
  });
});

describe('页签', () => {
  it('六个页签、aria-label 与 onChange', () => {
    const { onTabChange } = mount();
    const list = qa(document, '[role="tablist"]')[0];
    expect(list.getAttribute('aria-label')).toBe('证据');
    expect(qa(document, '[role="tab"]').map(text)).toEqual(['摘要', '补丁', '检查', '执行报告', '事件', '全部文件']);
    fireEvent.click(qa(document, '[role="tab"]').filter((t) => text(t) === '补丁')[0]);
    expect(onTabChange).toHaveBeenCalledWith('patch');
    expect(qa(document, '[role="tabpanel"]').length).toBe(1);
  });
});
