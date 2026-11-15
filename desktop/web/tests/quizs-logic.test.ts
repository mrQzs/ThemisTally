// Quizs 纯函数测试（合同第 9 节）：逐字表的每个取值、认不出的枚举值、null 与非法值，以及两个信封的失败判定。
import { describe, expect, it } from 'vitest';
import {
  billingLabel,
  formatIsoUtc,
  formatMsUtc,
  liveNextStep,
  liveSourceLabel,
  liveStateLabel,
  liveUnavailable,
  nextStepCell,
  providersUnavailable,
} from '../src/pages/readonly1/runtimes-quizs-logic';
import { formatLocalUtc } from '../src/components/RelativeTime';

const okEnv = (data: unknown): any => ({
  ok: true, exit_code: 0, data, output: [], messages: [], command: ['gate'], elapsed_ms: 0,
});
const badEnv = (command: string[], exitCode: number | null): any => ({
  ok: false, exit_code: exitCode, data: null, output: [], messages: [], command, elapsed_ms: 0,
});

describe('billingLabel', () => {
  it('三个枚举值各有中文名，认不出的（含 <redacted>）原样显示', () => {
    expect(billingLabel('none_test_only')).toBe('仅测试');
    expect(billingLabel('step_plan_credits')).toBe('套餐额度');
    expect(billingLabel('deepseek_prepaid_balance')).toBe('预付余额');
    expect(billingLabel('<redacted>')).toBe('<redacted>');
    expect(billingLabel('something_else')).toBe('something_else');
  });
});

describe('liveStateLabel', () => {
  it('五个状态各有标签与色调（只有「就绪」不醒目）', () => {
    expect(liveStateLabel('ready')).toEqual({ label: '就绪', tone: 'success' });
    expect(liveStateLabel('expired')).toEqual({ label: '已过期', tone: 'danger' });
    expect(liveStateLabel('build_mismatch')).toEqual({ label: '构建不一致', tone: 'warning' });
    expect(liveStateLabel('invalid')).toEqual({ label: '无效', tone: 'danger' });
    expect(liveStateLabel('missing')).toEqual({ label: '缺文件', tone: 'warning' });
  });

  it('status 为 null 是「读不出」，认不出的状态（含 <redacted>）是「未知」', () => {
    expect(liveStateLabel(null)).toEqual({ label: '读不出', tone: 'danger' });
    expect(liveStateLabel('<redacted>')).toEqual({ label: '未知', tone: 'neutral' });
    expect(liveStateLabel('weird')).toEqual({ label: '未知', tone: 'neutral' });
  });
});

describe('liveSourceLabel', () => {
  it('信箱 / 环境变量，认不出原样返回', () => {
    expect(liveSourceLabel('mailbox')).toBe('信箱');
    expect(liveSourceLabel('env')).toBe('环境变量');
    expect(liveSourceLabel('other')).toBe('other');
  });
});

describe('liveNextStep', () => {
  it('七个取值逐字对上', () => {
    expect(liveNextStep('ready', [])).toBe('不用动');
    expect(liveNextStep('expired', [])).toBe('续期后再看');
    expect(liveNextStep('build_mismatch', [])).toBe('重新构建这一套');
    expect(liveNextStep('invalid', [])).toBe('换一套能用的');
    expect(liveNextStep('missing', [])).toBe('补齐缺的文件');
    expect(liveNextStep(null, [])).toBe('看这一套自己的问题');
    expect(liveNextStep('weird', [])).toBe('按这一套的说明处理');
  });

  it('missing 状态追加「缺 <文件名>」，多个用「、」连接；其它状态不显示 missing 列表', () => {
    expect(liveNextStep('missing', ['qualification.json'])).toBe('补齐缺的文件：缺 qualification.json');
    expect(liveNextStep('missing', ['plan.json', 'profile.json'])).toBe('补齐缺的文件：缺 plan.json、profile.json');
    expect(liveNextStep('ready', ['plan.json'])).toBe('不用动');
    expect(liveNextStep('weird', ['plan.json'])).toBe('按这一套的说明处理');
    expect(liveNextStep(null, ['plan.json'])).toBe('看这一套自己的问题');
  });
});

describe('nextStepCell', () => {
  it('下一步文本在前、问题文字在后，中间「；」；问题文字内部 problem 与 status.problem 也用「；」', () => {
    expect(nextStepCell('不用动', 'P1', 'S1')).toBe('不用动；P1；S1');
    expect(nextStepCell('不用动', 'P2', null)).toBe('不用动；P2');
    expect(nextStepCell('不用动', null, 'S2')).toBe('不用动；S2');
    expect(nextStepCell('续期后再看', null, null)).toBe('续期后再看');
  });

  it('下一步文本为空时只写问题文字；两段都空显示「—」', () => {
    expect(nextStepCell('', 'P1', 'S1')).toBe('P1；S1');
    expect(nextStepCell('', 'P1', null)).toBe('P1');
    expect(nextStepCell('', null, null)).toBe('—');
  });
});

describe('formatMsUtc', () => {
  it('毫秒整数经 formatLocalUtc；null、不是数、解析不了显示「—」', () => {
    expect(formatMsUtc(1790000000000)).toBe(formatLocalUtc(new Date(1790000000000).toISOString()));
    expect(formatMsUtc(null)).toBe('—');
    expect(formatMsUtc(undefined)).toBe('—');
    expect(formatMsUtc('not-a-number' as unknown as number)).toBe('—');
    expect(formatMsUtc(Number.NaN)).toBe('—');
  });
});

describe('formatIsoUtc', () => {
  it('ISO 字符串经 formatLocalUtc；null 与解析不了的显示「—」', () => {
    expect(formatIsoUtc('2026-11-20T08:00:00.000Z')).toBe(formatLocalUtc('2026-11-20T08:00:00.000Z'));
    expect(formatIsoUtc(null)).toBe('—');
    expect(formatIsoUtc(undefined)).toBe('—');
    expect(formatIsoUtc('not-a-date')).toBe('—');
  });
});

describe('providersUnavailable / liveUnavailable', () => {
  it('ok 且 data 非空才算读到了', () => {
    expect(providersUnavailable(okEnv({ providers: [] }))).toBe(false);
    expect(providersUnavailable(okEnv(null))).toBe(true);
    expect(providersUnavailable(badEnv(['config', 'quizs', 'providers', '--json'], 1))).toBe(true);
    expect(liveUnavailable(okEnv({ live: [] }))).toBe(false);
    expect(liveUnavailable(okEnv(null))).toBe(true);
    expect(liveUnavailable(badEnv(['config', 'quizs', 'live', '--json'], null))).toBe(true);
  });
});
