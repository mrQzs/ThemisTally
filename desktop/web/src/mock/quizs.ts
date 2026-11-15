// Quizs 夹具（合同第 3 步）：src/mock 下的桩只能是 .ts（不加 JSON）。形状只写真内核交得出的字段
// （ts/packages/ui/src/redaction.ts 的 QUIZS_PROVIDERS_ALLOW 与 QUIZS_LIVE_ALLOW）：providers 每行
// provider/model/thinking/billing，live 每套 source/provider/problem/status（state、problem、missing、
// certificate.expires_at_ms、profile.valid_until）。id、build_id、live_dir、plan.*、issued_at_ms、
// capabilities 一类键服务不登记，前端拿不到也就不写。
// 纯类型导入（编译后擦除，不产生运行时循环）。
import type { Envelope, QuizsLiveData, QuizsProviderRow, QuizsProvidersData, QuizsLiveRow, QuizsLiveStatus } from '../api';

export type QuizsScenario = 'ok' | 'expired' | 'missing' | 'broken' | 'empty';

const SCENARIOS: readonly QuizsScenario[] = ['ok', 'expired', 'missing', 'broken', 'empty'];

const PROVIDERS_COMMAND = ['config', 'quizs', 'providers', '--json'];
const LIVE_COMMAND = ['config', 'quizs', 'live', '--json'];

// 提供方档案两行（取值出处：站主在本机核实的 Quizs 输出——stepfun 是套餐额度、思考档位 low/medium/high，
// deepseek 是预付余额、思考档位 low/high）。
const PROVIDER_ROWS: readonly QuizsProviderRow[] = [
  { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
  { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
];

// live 两套共用的到期时刻：证书是未来的毫秒整数，档案有效期是带毫秒的 ISO 8601 UTC 字符串。
const READY_EXPIRES_MS = 1790000000000;
const PAST_EXPIRES_MS = 1700000000000;
const VALID_UNTIL = '2026-11-20T08:00:00.000Z';

// 一套 live 的状态：problem 与 missing 都按内核口径（就绪时都是空的）。
function liveStatus(state: string, missing: string[], expiresAtMs: number): QuizsLiveStatus {
  return {
    state,
    problem: null,
    missing,
    certificate: { expires_at_ms: expiresAtMs },
    profile: { valid_until: VALID_UNTIL },
  };
}

// live 一套：信箱或环境变量，提供方都是 deepseek。每次调用都给新对象（桩数据不许被上一次读改坏）。
function liveRow(source: 'mailbox' | 'env', status: QuizsLiveStatus | null, problem: string | null): QuizsLiveRow {
  return { source, provider: 'deepseek', problem, status };
}

// 两套 live：一封信箱、一套环境变量。就绪情景里两套都是就绪；expired / missing 只动信箱那一套，
// 环境变量那一套仍是就绪（合同第 3 步）。
function liveRows(state: string, missing: string[], expiresAtMs: number): QuizsLiveRow[] {
  return [
    liveRow('mailbox', liveStatus(state, missing, expiresAtMs), null),
    liveRow('env', liveStatus('ready', [], READY_EXPIRES_MS), null),
  ];
}

// 没设 QUIZS_CMD 时内核的报错原文不在已核实事实里，这里只写以「ERROR: 」开头的情景说明，不冒充内核原文。
const PROVIDERS_ERROR = 'ERROR: 没有设置 QUIZS_CMD，读不到 Quizs 提供方档案';

// live 命令照常退出 0：每一套的 problem 写「quizs live status 失败（退出码 127）：…」。
const LIVE_PROBLEM = 'quizs live status 失败（退出码 127）：本机 PATH 上没有 quizs';

/** 读 location.hash 查询串里的 quizs 键（写法照 mock/writes.ts 的 writeScenario）：缺省或认不出按 ok。 */
export function quizsScenario(): QuizsScenario {
  const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
  const q = hash.indexOf('?');
  if (q < 0) return 'ok';
  const query = hash.slice(q + 1);
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    if (part.slice(0, eq) !== 'quizs') continue;
    const value = part.slice(eq + 1) as QuizsScenario;
    if (SCENARIOS.includes(value)) return value;
  }
  return 'ok';
}

function providersEnvelope(command: string[], data: QuizsProvidersData | null, messages: string[]): Envelope<QuizsProvidersData> {
  return { ok: data != null, exit_code: data != null ? 0 : 1, data, output: [], messages, command, elapsed_ms: 0 };
}

function liveEnvelope(command: string[], data: QuizsLiveData): Envelope<QuizsLiveData> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

/** 提供方档案信封：broken 情景是 ok:false、退出码 1、data null、恰一行以「ERROR: 」开头的报错。 */
export function quizsProvidersEnvelope(): Envelope<QuizsProvidersData> {
  const scenario = quizsScenario();
  if (scenario === 'broken') return providersEnvelope(PROVIDERS_COMMAND, null, [PROVIDERS_ERROR]);
  const providers = scenario === 'empty' ? [] : PROVIDER_ROWS.map((row) => ({ ...row, thinking: [...row.thinking] }));
  return providersEnvelope(PROVIDERS_COMMAND, { providers }, []);
}

/** live 信封：broken 情景下命令照常退出 0，两套各自读不出状态（status 为 null，problem 写退出码 127）。 */
export function quizsLiveEnvelope(): Envelope<QuizsLiveData> {
  const scenario = quizsScenario();
  const command = LIVE_COMMAND;
  if (scenario === 'expired') return liveEnvelope(command, { live: liveRows('expired', [], PAST_EXPIRES_MS) });
  if (scenario === 'missing') return liveEnvelope(command, { live: liveRows('missing', ['qualification.json'], READY_EXPIRES_MS) });
  if (scenario === 'broken') {
    const live: QuizsLiveRow[] = [
      liveRow('mailbox', null, LIVE_PROBLEM),
      liveRow('env', null, LIVE_PROBLEM),
    ];
    return liveEnvelope(command, { live });
  }
  if (scenario === 'empty') return liveEnvelope(command, { live: [] });
  return liveEnvelope(command, { live: liveRows('ready', [], READY_EXPIRES_MS) });
}
