// T046 quizs 纯逻辑的自测（合同第 9 步；D02、D03）：认 quizs 看适配器不看 id，档案转模型选项与档位的规则。
// 只测纯函数：不渲染组件、不碰计时器；反例取值先证合法基线，再只改受测条件（审核 B1 的口径）。
import { describe, expect, it } from 'vitest';
import {
  QUIZS_LEVELS,
  isQuizsRuntime,
  modelInArchive,
  quizsProviderOptions,
  thinkingAllowed,
  thinkingLevelsFor,
} from '../src/writes/quizsProfile';
import type { QuizsProviderRow } from '../src/api';
import { validModel } from '../src/writes/profileRules';

// 运行时两行：id 叫 quizs-cli 的那行 adapter 是 quizs；另有一行 id 叫 quizs 而 adapter 是 pi 的反例。
const RUNTIMES = [
  { id: 'pi', adapter: 'pi' },
  { id: 'quizs-cli', adapter: 'quizs' },
];
// 档案 ok 情景的两行（src/mock/quizs.ts 的 PROVIDER_ROWS）。
const OK_ROWS: QuizsProviderRow[] = [
  { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
  { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
];

describe('T046 纯逻辑：isQuizsRuntime（认适配器不认 id）', () => {
  it('所选 runtime 那一行的 adapter 是 quizs 才算', () => {
    expect(isQuizsRuntime('quizs-cli', RUNTIMES)).toBe(true);
    expect(isQuizsRuntime('pi', RUNTIMES)).toBe(false);
  });

  it('id 叫 quizs 而 adapter 是 pi 的不算；列表里找不到按非 quizs 走', () => {
    expect(isQuizsRuntime('quizs', [{ id: 'quizs', adapter: 'pi' }])).toBe(false);
    expect(isQuizsRuntime('nope', RUNTIMES)).toBe(false);
    expect(isQuizsRuntime('quizs-cli', [])).toBe(false);
  });
});

describe('T046 纯逻辑：QUIZS_LEVELS 是服务放行的六值', () => {
  it('恰好 off/low/medium/high/xhigh/max，没有 minimal', () => {
    expect([...QUIZS_LEVELS]).toEqual(['off', 'low', 'medium', 'high', 'xhigh', 'max']);
    expect((QUIZS_LEVELS as readonly string[]).includes('minimal'), '服务 QUIZS_THINKING_ENUM 没有 minimal').toBe(false);
  });
});

describe('T046 纯逻辑：quizsProviderOptions 把档案转成模型选项', () => {
  it('value 与 label 都是 provider/model 一段；档位按原顺序跟随', () => {
    const options = quizsProviderOptions(OK_ROWS);
    expect(options.map((o) => o.value)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(options.map((o) => o.label)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(options[0].thinking).toEqual(['low', 'medium', 'high']);
    expect(options[1].thinking).toEqual(['low', 'high']);
  });

  it('<redacted>、非字符串与空串的 provider/model 都不进选项', () => {
    const rows: QuizsProviderRow[] = [
      { provider: '<redacted>', model: 'm', thinking: ['low'], billing: 'b' },
      { provider: 'p', model: '<redacted>', thinking: ['low'], billing: 'b' },
      { provider: null, model: 'm', thinking: [], billing: 'b' },
      { provider: 'p', model: null, thinking: [], billing: 'b' },
      { provider: '', model: 'm', thinking: [], billing: 'b' },
      { provider: 'p', model: '', thinking: [], billing: 'b' },
    ];
    expect(quizsProviderOptions(rows)).toEqual([]);
  });

  it('拼起来过不了 validModel 的不进选项（两段都只能字母数字与 . _ : / @ + -）', () => {
    // 反例取值先过合法基线：'!' 不在 MODEL_SEGMENT_RE 的段字符类里，两段都过不了。
    expect(validModel('p!/m')).toBe(false);
    expect(validModel('p/m!')).toBe(false);
    const rows: QuizsProviderRow[] = [
      { provider: 'p!', model: 'm', thinking: [], billing: 'b' },
      { provider: 'p', model: 'm!', thinking: [], billing: 'b' },
    ];
    expect(quizsProviderOptions(rows)).toEqual([]);
  });

  it('两段都合法的值要留下：连字符在段字符类里，p/no-slash 过得了 validModel', () => {
    expect(validModel('p/no-slash')).toBe(true);
    const rows: QuizsProviderRow[] = [{ provider: 'p', model: 'no-slash', thinking: ['low'], billing: 'b' }];
    expect(quizsProviderOptions(rows).map((o) => o.value)).toEqual(['p/no-slash']);
  });

  it('同 value 只留第一项；档位按六值过滤、保序、去重', () => {
    const rows: QuizsProviderRow[] = [
      { provider: 'p', model: 'm', thinking: ['high', 'low', 'high', 'bogus', 'minimal', 'off'], billing: 'b' },
      { provider: 'p', model: 'm', thinking: ['max'], billing: 'b2' },
    ];
    const options = quizsProviderOptions(rows);
    expect(options.length, '同 value 只留第一项').toBe(1);
    expect(options[0].thinking, '六值之外与重复的档位不进').toEqual(['high', 'low', 'off']);
  });

  it('thinking 不是数组时档位为空，但选项仍在', () => {
    const rows = [
      { provider: 'p', model: 'm', thinking: 'low', billing: 'b' },
      { provider: 'q', model: 'n', thinking: null, billing: 'b' },
    ] as unknown as QuizsProviderRow[];
    const options = quizsProviderOptions(rows);
    expect(options.map((o) => o.value)).toEqual(['p/m', 'q/n']);
    expect(options[0].thinking).toEqual([]);
    expect(options[1].thinking).toEqual([]);
  });
});

describe('T046 纯逻辑：档位范围与档案归属', () => {
  it('有档案项给它的档位；没有（模型不在档案里或档案不明）给六值', () => {
    const options = quizsProviderOptions(OK_ROWS);
    expect(thinkingLevelsFor(options[1])).toEqual(['low', 'high']);
    expect([...thinkingLevelsFor(null)]).toEqual(['off', 'low', 'medium', 'high', 'xhigh', 'max']);
  });

  it('档位在不在允许范围；模型在不在档案里', () => {
    const options = quizsProviderOptions(OK_ROWS);
    expect(thinkingAllowed('high', ['low', 'high'])).toBe(true);
    expect(thinkingAllowed('medium', ['low', 'high'])).toBe(false);
    expect(thinkingAllowed('high', [])).toBe(false);
    expect(modelInArchive('deepseek/deepseek-chat', options)).toBe(true);
    expect(modelInArchive('stepfun/step-4', options)).toBe(false);
    expect(modelInArchive('stepfun/step-4', [])).toBe(false);
  });
});
