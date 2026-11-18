// CLI 运行时测试（合同第 9 节，注入数据）：来源五种、能担任、命令截断与 title、版本「—」、操作规则、就绪检查区。
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';

afterEach(cleanup);

const text = (el: any) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string) => Array.from(root.querySelectorAll(sel));
const btn = (root: any, label: string) => qa(root, 'button').find((b: any) => text(b) === label);
function tableRows(table: any): Array<Record<string, any>> {
  const heads = qa(table, 'thead th').map(text);
  return qa(table, 'tbody tr').map((tr: any) => {
    const o: Record<string, any> = {};
    qa(tr, 'td').forEach((td: any, i: number) => {
      o[heads[i] as string] = td;
    });
    return o;
  });
}
function sectionNamed(root: any, title: string): any {
  return qa(root, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return text(id ? document.getElementById(id) : null) === title;
  });
}

const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'env', command: ['C:/tools/node/node.exe', 'C:/tools/pi/dist/cli.js', '--flag-with-a-rather-long-name', '--another'], notes: ['环境变量 THEMIS_PI 已设置', '另一行'] },
  { id: 'claude-code', adapter: 'claude-code', source: 'local', command: ['C:/tools/npm/claude.cmd'], notes: [] },
  { id: 'codex', adapter: 'codex', source: 'path', command: ['codex'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
  { id: 'custom', adapter: 'custom', source: 'zzz', command: ['custom-cli', '--x'], notes: ['n'] },
] as any;

// Quizs 两个信封（ok 情景的取值照 src/mock/quizs.ts）：视图的 quizs 属性是必填的，四处渲染都带上。
const QUIZS = {
  providers: {
    ok: true, exit_code: 0, output: [], messages: [], command: ['config', 'quizs', 'providers', '--json'], elapsed_ms: 0,
    data: {
      providers: [
        { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
        { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
      ],
    },
  },
  live: {
    ok: true, exit_code: 0, output: [], messages: [], command: ['config', 'quizs', 'live', '--json'], elapsed_ms: 0,
    data: {
      live: [
        {
          source: 'mailbox', provider: 'deepseek', problem: null,
          status: {
            state: 'ready', problem: null, missing: [],
            certificate: { expires_at_ms: 1790000000000 }, profile: { valid_until: '2026-11-20T08:00:00.000Z' },
          },
        },
        {
          source: 'env', provider: 'deepseek', problem: null,
          status: {
            state: 'ready', problem: null, missing: [],
            certificate: { expires_at_ms: 1790000000000 }, profile: { valid_until: '2026-11-20T08:00:00.000Z' },
          },
        },
      ],
    },
  },
} as any;

function shortCommand(full: string): string {
  const cps = Array.from(full);
  return cps.length > 40 ? cps.slice(0, 22).join('') + ' … ' + cps.slice(-15).join('') : full;
}

describe('CLI 运行时表', () => {
  it('七列、行序、能担任、来源标签与 notes title', () => {
    const { container } = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const table = sectionNamed(container, '已登记').querySelector('table[aria-label="已登记的 runtime"]') as any;
    expect(qa(table, 'thead th').map(text)).toEqual(['ID', '适配器', '能担任', '命令来源', '命令', '版本', '操作']);
    const rows = tableRows(table);
    expect(rows.map((r) => text(r['ID']))).toEqual(['pi', 'claude-code', 'codex', 'opencode', 'custom']);
    expect(rows.map((r) => text(r['能担任']))).toEqual(['执行端、合同端', '交互式宿主', '交互式宿主', '未接通', '—']);
    const srcs = rows.map((r) => r['命令来源'].querySelector('[data-source]'));
    expect(srcs.map((s: any) => s.getAttribute('data-source'))).toEqual(['env', 'local', 'path', 'missing', 'zzz']);
    expect(srcs.map((s: any) => s.getAttribute('data-tone'))).toEqual(['neutral', 'neutral', 'neutral', 'danger', 'neutral']);
    expect(srcs.map((s: any) => s.getAttribute('title'))).toEqual(['环境变量 THEMIS_PI 已设置\n另一行', null, null, null, 'n']);
    expect(srcs[3].querySelector('svg')?.getAttribute('width')).toBe('12');
  });

  it('命令截断与 title，版本一律 —', () => {
    const { container } = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const rows = tableRows(sectionNamed(container, '已登记').querySelector('table'));
    const full = 'C:/tools/node/node.exe C:/tools/pi/dist/cli.js --flag-with-a-rather-long-name --another';
    expect(text(rows[0]['命令'])).toBe(shortCommand(full));
    expect(rows[0]['命令'].querySelector('[title]')?.getAttribute('title')).toBe(full);
    expect(text(rows[1]['命令'])).toBe('C:/tools/npm/claude.cmd');
    expect(text(rows[3]['命令'])).toBe('—');
    rows.forEach((r) => expect(text(r['版本'])).toBe('—'));
  });

  it('操作规则：[删除…] 与 [探测]、[模型] 都可点', () => {
    const { container } = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const rows = tableRows(sectionNamed(container, '已登记').querySelector('table'));
    const want = [['探测', '模型', '删除…'], ['探测', '删除…'], ['探测', '删除…'], ['删除…'], ['探测', '删除…']];
    rows.forEach((r, i) => {
      const ops = qa(r['操作'], 'button').map(text);
      expect(ops, `第 ${i + 1} 行`).toEqual(want[i]);
      qa(r['操作'], 'button').forEach((b: any) => {
        expect(b.disabled, `${text(b)} 的禁用状态`).toBe(false);
      });
    });
  });
});

describe('就绪检查区', () => {
  it('[运行就绪检查] 禁用 secondary 带 PlayIcon，虚线空框，无按版本核验下拉', () => {
    const { container } = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = sectionNamed(container, '就绪检查');
    const b = btn(sec, '运行就绪检查');
    expect(b?.disabled).toBe(true);
    expect(b?.getAttribute('data-variant')).toBe('secondary');
    expect(b?.querySelector('svg')).not.toBeNull();
    expect(text(sec)).toContain('还没有运行过就绪检查。');
    expect(sec.querySelector('select, [role="combobox"], [role="listbox"]')).toBeNull();
    expect(btn(container, '核验')).toBeUndefined();
  });
});
