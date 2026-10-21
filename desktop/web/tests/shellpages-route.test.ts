// 执行端测试（D03 纯函数）：parseShellWindow 与场景解析（缺省值、认不出的取值）。
import { describe, expect, it } from 'vitest';
import { parseShellWindow, scenarioOf } from '../src/shellpages/shellWindowRoute';

describe('D03 parseShellWindow', () => {
  it('第一段是 first-run、service-status 时给出 page 与 query', () => {
    const a = parseShellWindow('#/first-run');
    expect(a).toBeTruthy();
    expect(a!.page).toBe('first-run');
    const b = parseShellWindow('#/service-status?mock=data&shell=exit-1');
    expect(b!.page).toBe('service-status');
    expect(b!.query).toContain('shell=exit-1');
    expect(b!.query).toContain('mock=data');
    expect(parseShellWindow('#/first-run/extra')!.page).toBe('first-run');
  });

  it('别的地址给 null（含前缀相近的）', () => {
    for (const hash of ['', '#', '#/', '#/overview', '#/settings', '#/nope', '#/first-run-x', '#/service-status-x', '#/tasks/first-run']) {
      expect(parseShellWindow(hash), hash).toBeNull();
    }
  });
});

describe('D03 scenarioOf', () => {
  it('认得出的 shell= 优先，否则按页面取缺省', () => {
    expect(scenarioOf('first-run', 'mock=data')).toBe('ready');
    expect(scenarioOf('service-status', 'mock=data')).toBe('crash');
    expect(scenarioOf('first-run', 'shell=checking')).toBe('checking');
    expect(scenarioOf('service-status', 'shell=exit-1')).toBe('exit-1');
    expect(scenarioOf('first-run', 'shell=nope')).toBe('ready');
    expect(scenarioOf('service-status', 'shell=nope')).toBe('crash');
  });
});
