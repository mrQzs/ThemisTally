// 证书列纯逻辑测试（合同第 7 节）：matchLiveRow 的对上/兑底与 hubCertInfo 的逐情形（合同第 4、5 节的表）。
// 期望值全是字面量；被测的是 roles-logic 里的真实实现（岗位行也经真实的 normalizeHubPost 归一）。
import { describe, expect, it } from 'vitest';
import { hubCertInfo, matchLiveRow, normalizeHubPost } from '../src/pages/readonly1/roles-logic';
import type { Envelope, HubPostRow, QuizsLiveData, QuizsLiveRow } from '../src/api';

type LiveStatus = NonNullable<QuizsLiveRow['status']>;

const row = (o: Partial<QuizsLiveRow>): QuizsLiveRow => ({ source: 'mailbox', provider: null, problem: null, status: null, ...o });

const status = (state: string | null, o: Partial<LiveStatus> = {}): LiveStatus | null =>
  state === null ? null : { state, problem: null, missing: [], certificate: null, profile: null, ...o };

const okEnv = (data: unknown): Envelope<QuizsLiveData> =>
  ({ ok: true, exit_code: 0, data, output: [], messages: [], command: [], elapsed_ms: 0 }) as Envelope<QuizsLiveData>;

const failEnv = (messages: string[]): Envelope<QuizsLiveData> =>
  ({ ok: false, exit_code: 1, data: null, output: [], messages, command: ['config', 'quizs', 'live', '--json'], elapsed_ms: 0 }) as Envelope<QuizsLiveData>;

const nullDataEnv = (): Envelope<QuizsLiveData> =>
  ({ ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 }) as unknown as Envelope<QuizsLiveData>;

// 岗位行走真实的 normalizeHubPost：adapter 与 provider 之外的字段按缺省值归一，不影响证书格的判断。
const post = (adapter: string | null, provider: string | null) =>
  normalizeHubPost({ post: 'coordinator', source: 'default', allowed_adapters: [], adapter, provider } as unknown as HubPostRow);

const quizsPost = post('quizs', 'deepseek');

describe('matchLiveRow（合同第 4 节）', () => {
  it('provider 精确对上：取第一条 provider 相同的行', () => {
    const rows = [row({ source: 'mailbox', provider: 'deepseek' }), row({ source: 'env', provider: 'deepseek' })];
    expect(matchLiveRow(rows, 'deepseek')).toBe(rows[0]);
  });

  it('信箱与 env 同名时取信箱（行序里信箱在前，取第一条）', () => {
    const rows = [row({ source: 'mailbox', provider: 'minimax' }), row({ source: 'env', provider: 'minimax' })];
    expect(matchLiveRow(rows, 'minimax')).toBe(rows[0]);
  });

  it('对不上时用 source===env 且 provider 为 null 的那条兑底', () => {
    const rows = [row({ source: 'mailbox', provider: 'minimax' }), row({ source: 'env', provider: null })];
    expect(matchLiveRow(rows, 'deepseek')).toBe(rows[1]);
  });

  it('env 那条 provider 不是 null 时不兑底（结果是 null）', () => {
    const rows = [row({ source: 'env', provider: 'deepseek' })];
    expect(matchLiveRow(rows, 'minimax')).toBe(null);
  });

  it('岗位 provider 为 null 时第一条不命中，直接走 env 兑底', () => {
    const rows = [row({ source: 'mailbox', provider: 'deepseek' }), row({ source: 'env', provider: null })];
    expect(matchLiveRow(rows, null)).toBe(rows[1]);
  });

  it('rows 是空数组时 null', () => {
    expect(matchLiveRow([], 'deepseek')).toBe(null);
    expect(matchLiveRow([], null)).toBe(null);
  });
});

describe('hubCertInfo 的纯文字情形（合同第 5 节的表）', () => {
  it('adapter 不是 quizs → 纯文字「—」，无 title', () => {
    expect(hubCertInfo(post('pi', 'bb'), okEnv({ live: [] }))).toEqual({ text: '—', state: null, tagged: false, title: null });
    expect(hubCertInfo(post(null, null), okEnv({ live: [] }))).toEqual({ text: '—', state: null, tagged: false, title: null });
  });

  it('live 为 null（还没回来）→ 纯文字「读取中」', () => {
    expect(hubCertInfo(quizsPost, null)).toEqual({ text: '读取中', state: null, tagged: false, title: null });
  });

  it('信封 ok:false → 纯文字「读不出」，title 是 messages 用换行连起来', () => {
    expect(hubCertInfo(quizsPost, failEnv(['读不到 live', '第二行'])))
      .toEqual({ text: '读不出', state: null, tagged: false, title: '读不到 live\n第二行' });
  });

  it('messages 是空数组 → 失败信封的「读不出」不带 title', () => {
    expect(hubCertInfo(quizsPost, failEnv([]))).toEqual({ text: '读不出', state: null, tagged: false, title: null });
  });

  it('ok:true 但 data 为 null → 纯文字「读不出」', () => {
    expect(hubCertInfo(quizsPost, nullDataEnv())).toEqual({ text: '读不出', state: null, tagged: false, title: null });
  });

  it('data.live 不是数组 → 纯文字「读不出」', () => {
    expect(hubCertInfo(quizsPost, okEnv({ live: 'x' }))).toEqual({ text: '读不出', state: null, tagged: false, title: null });
    expect(hubCertInfo(quizsPost, okEnv({}))).toEqual({ text: '读不出', state: null, tagged: false, title: null });
  });

  it('对不上任何一套（data.live 是空数组）→ 纯文字「没有 live 文件」', () => {
    expect(hubCertInfo(quizsPost, okEnv({ live: [] }))).toEqual({ text: '没有 live 文件', state: null, tagged: false, title: null });
  });

  it('env 那条 provider 不是 null 时也算对不上 → 纯文字「没有 live 文件」', () => {
    const live = okEnv({ live: [row({ source: 'env', provider: 'deepseek' })] });
    expect(hubCertInfo(post('quizs', 'minimax'), live)).toEqual({ text: '没有 live 文件', state: null, tagged: false, title: null });
  });
});

describe('hubCertInfo 的 Tag 情形（对上的那一套，合同第 5 节）', () => {
  it('status 为 null → tagged 为真、state 为 null、title 是 row.problem', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', problem: 'quizs live status 失败（退出码 127）：本机 PATH 上没有 quizs' })] });
    expect(hubCertInfo(quizsPost, live))
      .toEqual({ text: '', state: null, tagged: true, title: 'quizs live status 失败（退出码 127）：本机 PATH 上没有 quizs' });
  });

  it('五个 state 原样透传：ready/expired/build_mismatch/invalid/missing', () => {
    for (const state of ['ready', 'expired', 'build_mismatch', 'invalid', 'missing']) {
      const live = okEnv({ live: [row({ provider: 'deepseek', status: status(state) })] });
      const info = hubCertInfo(quizsPost, live);
      expect(info.tagged, state + ' 应是 Tag 情形').toBe(true);
      expect(info.state, state + ' 原样透传给界面').toBe(state);
      expect(info.text, state + ' 的文字由界面的 liveStateLabel 给').toBe('');
    }
  });

  it('认不出的 state 也原样透传（<redacted> 之类，界面上是「未知」）', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', status: status('<redacted>') })] });
    expect(hubCertInfo(quizsPost, live)).toEqual({ text: '', state: '<redacted>', tagged: true, title: null });
  });

  it('status.missing 非空 → title 是「缺 qualification.json」', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', status: status('missing', { missing: ['qualification.json'] }) })] });
    expect(hubCertInfo(quizsPost, live).title).toBe('缺 qualification.json');
  });

  it('status.missing 是空数组 → 不给「缺 …」的 title（走 status.problem）', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', status: status('missing', { problem: '档案对不上' }) })] });
    expect(hubCertInfo(quizsPost, live).title).toBe('档案对不上');
  });

  it('title 取值顺序：row.problem 优先于「缺 …」，「缺 …」优先于 status.problem', () => {
    const all = okEnv({ live: [row({ provider: 'deepseek', problem: '信箱这一套的问题', status: status('missing', { missing: ['a.json', 'b.json'], problem: '状态自己的问题' }) })] });
    expect(hubCertInfo(quizsPost, all).title).toBe('信箱这一套的问题');
    const missingFirst = okEnv({ live: [row({ provider: 'deepseek', status: status('missing', { missing: ['a.json', 'b.json'], problem: '状态自己的问题' }) })] });
    expect(hubCertInfo(quizsPost, missingFirst).title).toBe('缺 a.json、b.json');
    const onlyStatus = okEnv({ live: [row({ provider: 'deepseek', status: status('expired', { problem: '状态自己的问题' }) })] });
    expect(hubCertInfo(quizsPost, onlyStatus).title).toBe('状态自己的问题');
  });

  it('三个说明文字都没有 → 不给 title', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', status: status('ready') })] });
    expect(hubCertInfo(quizsPost, live)).toEqual({ text: '', state: 'ready', tagged: true, title: null });
  });

  it('空字符串的 problem 不算有：跳过它看后面的说明文字', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', problem: '', status: status('expired', { problem: '' }) })] });
    expect(hubCertInfo(quizsPost, live).title).toBe(null);
  });

  it('minimax 的岗位对不上 mailbox 那一套，用 env（provider 为 null）那一套兑底', () => {
    const live = okEnv({ live: [row({ source: 'env', provider: null, status: status('expired') })] });
    expect(hubCertInfo(post('quizs', 'minimax'), live)).toEqual({ text: '', state: 'expired', tagged: true, title: null });
  });

  it('岗位 provider 为 null 时直接走 env 兑底', () => {
    const live = okEnv({ live: [row({ source: 'mailbox', provider: 'deepseek' }), row({ source: 'env', provider: null, status: status('invalid') })] });
    expect(hubCertInfo(post('quizs', null), live)).toEqual({ text: '', state: 'invalid', tagged: true, title: null });
  });
});
