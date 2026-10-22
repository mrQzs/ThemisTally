// 共用件测试（T013 D01）：T013 把 T009、T010 的四样重复件各并成一份共用件，这里逐条验共用件的取值。
// copyText 三种结果与缺省取 navigator.clipboard、三条结果文字；13 条动作说明（表外与 Object.prototype 上的名字为 null）；
// actorTone 五类色调；formatLocalUtc 的格式与解析不了；RelativeTime 的 title 等于 formatLocalUtc；原有导出与属性不变。
import { afterEach, describe, expect, it } from 'vitest';
import { createElement } from 'react';
import { render, cleanup } from '@testing-library/react';
import { copyText, COPY_RESULT_TEXT, type CopyResult } from '../src/components/copyText';
import { ACTION_TITLES, actionTitle } from '../src/components/actionTitle';
import { actorTone, ActorTag } from '../src/components/ActorTag';
import { formatLocalUtc, RelativeTime } from '../src/components/RelativeTime';
import * as barrel from '../src/components';

afterEach(cleanup);

/** 临时把 navigator.clipboard 换成给定值，跑完还原（jsdom 里默认没有剪贴板接口）。 */
async function withNavigatorClipboard(clip: unknown, run: () => Promise<CopyResult>): Promise<CopyResult> {
  const desc = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  Object.defineProperty(navigator, 'clipboard', { value: clip, configurable: true, writable: true });
  try {
    return await run();
  } finally {
    if (desc) Object.defineProperty(navigator, 'clipboard', desc);
    else delete (navigator as { clipboard?: unknown }).clipboard;
  }
}

describe('copyText：三态与缺省取 navigator.clipboard', () => {
  it('成功 copied；没有 writeText 或没有接口 unavailable', async () => {
    expect(await copyText('a', { writeText: async () => {} })).toBe('copied');
    expect(await copyText('a', {})).toBe('unavailable');
    expect(await copyText('a', null)).toBe('unavailable');
    expect(await withNavigatorClipboard(undefined, () => copyText('a'))).toBe('unavailable');
  });

  it('抛错或被拒 failed；缺省读 navigator.clipboard 并原样传文字', async () => {
    expect(await copyText('a', { writeText: async () => { throw new Error('x'); } })).toBe('failed');
    expect(await copyText('a', { writeText: () => Promise.reject(new Error('x')) })).toBe('failed');
    const seen: string[] = [];
    const ok = await withNavigatorClipboard({ writeText: async (t: string) => { seen.push(t); } }, () => copyText('要复制的文字'));
    expect(ok).toBe('copied');
    expect(seen).toEqual(['要复制的文字']);
  });

  it('三条结果文字逐字不变', () => {
    expect(COPY_RESULT_TEXT).toEqual({
      copied: '已复制',
      unavailable: '这个环境没有剪贴板接口',
      failed: '复制失败',
    });
    expect(Object.keys(COPY_RESULT_TEXT).sort()).toEqual(['copied', 'failed', 'unavailable']);
  });
});

describe('actionTitle：13 条逐字，表外与原型名返回 null', () => {
  it('ACTION_TITLES 恰有 13 条，逐字与合同相同', () => {
    expect(ACTION_TITLES).toEqual({
      'config.set': '设置配置键',
      'config.unset': '删除配置键',
      'config.rollback': '回滚配置',
      'preset.use': '切换方案',
      'preset.save': '保存方案',
      'preset.remove': '删除方案',
      'role.set': '修改角色绑定',
      'profile.add': '新建 profile',
      'profile.edit': '修改 profile',
      'profile.remove': '删除 profile',
      'runtime.add': '登记 runtime',
      'runtime.remove': '删除 runtime',
      external: '检测到界面与命令之外的改动',
    });
  });

  it('表内取到中文说明，表外返回 null', () => {
    for (const [action, text] of Object.entries(ACTION_TITLES)) {
      expect(actionTitle(action), action).toBe(text);
    }
    for (const action of ['', 'zzz.unknown', 'config', 'config.set ', 'CONFIG.SET', 'preset.use.x']) {
      expect(actionTitle(action), action).toBeNull();
    }
  });

  it('Object.prototype 上的名字也返回 null', () => {
    for (const name of ['constructor', 'toString', 'valueOf', 'hasOwnProperty', '__proto__', 'isPrototypeOf', 'propertyIsEnumerable', 'toLocaleString']) {
      expect(actionTitle(name), name).toBeNull();
    }
  });
});

describe('actorTone：五类色调', () => {
  it('user-ui brand、user neutral、agent: 开头 info、undeclared warning、其他 neutral', () => {
    expect(actorTone('user-ui')).toBe('brand');
    expect(actorTone('user')).toBe('neutral');
    expect(actorTone('agent:planning_review')).toBe('info');
    expect(actorTone('agent:')).toBe('info');
    expect(actorTone('undeclared')).toBe('warning');
    expect(actorTone('something-else')).toBe('neutral');
    expect(actorTone('')).toBe('neutral');
    expect(actorTone('user-ui-x')).toBe('neutral');
    expect(actorTone('agentx')).toBe('neutral');
  });

  it('ActorTag 仍按 actorTone 上色，属性仍是 actor 必填加 className 可选', () => {
    const { container } = render(createElement(ActorTag, { actor: 'agent:execution', className: 'extra' }));
    const tag = container.querySelector('[data-tone]') as HTMLElement;
    expect(tag.getAttribute('data-tone')).toBe('info');
    expect(tag.textContent).toBe('agent:execution');
    expect(tag.className).toContain('extra');
    expect(tag.className).toContain('tt-tag--mono');
  });
});

describe('formatLocalUtc：本地时间加全角括号里的 UTC', () => {
  it('格式是「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」', () => {
    const iso = '2026-10-18T02:02:11Z';
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    const want =
      `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` +
      `（UTC ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}）`;
    expect(formatLocalUtc(iso)).toBe(want);
    expect(formatLocalUtc(iso)).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}（UTC \d{2}:\d{2}:\d{2}）$/);
  });

  it('解析不了返回 null', () => {
    expect(formatLocalUtc('not-a-time')).toBeNull();
    expect(formatLocalUtc('')).toBeNull();
  });
});

describe('RelativeTime：title 等于 formatLocalUtc', () => {
  it('解析得了挂 time，dateTime 为原文，title 是本地加 UTC', () => {
    const iso = '2026-10-18T02:02:11Z';
    const { container } = render(createElement(RelativeTime, { iso, className: 'rt', now: new Date('2026-10-18T03:00:00Z').getTime() }));
    const time = container.querySelector('time') as HTMLElement;
    expect(time.getAttribute('dateTime')).toBe(iso);
    expect(time.getAttribute('title')).toBe(formatLocalUtc(iso));
    expect(time.textContent).toBe('57 分钟前');
    expect(time.className).toBe('rt');
  });

  it('解析不了原样显示，不带 title 与 dateTime', () => {
    const { container } = render(createElement(RelativeTime, { iso: 'not-a-time' }));
    expect(container.querySelector('time')).toBeNull();
    const span = container.querySelector('span') as HTMLElement;
    expect(span.textContent).toBe('not-a-time');
    expect(span.getAttribute('title')).toBeNull();
    expect(span.getAttribute('dateTime')).toBeNull();
  });
});

describe('components 桶：四样共用件都从 index.ts 导出', () => {
  it('名字与类型都在，且与直接引模块是同一份', () => {
    expect(barrel.copyText).toBe(copyText);
    expect(barrel.COPY_RESULT_TEXT).toBe(COPY_RESULT_TEXT);
    expect(barrel.actionTitle).toBe(actionTitle);
    expect(barrel.ACTION_TITLES).toBe(ACTION_TITLES);
    expect(barrel.actorTone).toBe(actorTone);
    expect(barrel.formatLocalUtc).toBe(formatLocalUtc);
    expect(barrel.ActorTag).toBe(ActorTag);
    expect(barrel.RelativeTime).toBe(RelativeTime);
  });
});
