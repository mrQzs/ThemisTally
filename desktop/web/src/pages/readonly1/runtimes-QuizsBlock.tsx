// Quizs 一块（合同第 6 节）：只读展示——提供方档案表（四列）与 live 套表（六列，问题文字并入「下一步」列）。
// 两个信封整个收下：providers 或 live 任一读失败只在这一块里写出来，已登记与就绪检查照常。
// 区块里没有任何按钮与复制入口；文案、标签色调与时刻的纯函数在 runtimes-quizs-logic，这里只负责摆。
import type { ReactNode } from 'react';
import type { Envelope, QuizsLiveData, QuizsProvidersData } from '../../api';
import { Table, Tag, type TableColumn } from '../../components';
import { Section } from './common-Section';
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
} from './runtimes-quizs-logic';

const DASH = '—';

interface ProviderRowData {
  rowId: string;
  提供方: string;
  模型: string;
  思考档位: string;
  计费: string;
}

const PROVIDER_COLUMNS: readonly TableColumn<ProviderRowData>[] = [
  { key: '提供方', header: '提供方' },
  { key: '模型', header: '模型' },
  { key: '思考档位', header: '思考档位' },
  { key: '计费', header: '计费' },
];

interface LiveRowData {
  rowId: string;
  提供方: string;
  来源: string;
  状态: ReactNode;
  证书到期: string;
  档案有效期: string;
  下一步: string;
}

const LIVE_COLUMNS: readonly TableColumn<LiveRowData>[] = [
  { key: '提供方', header: '提供方' },
  { key: '来源', header: '来源' },
  { key: '状态', header: '状态' },
  { key: '证书到期', header: '证书到期' },
  { key: '档案有效期', header: '档案有效期' },
  { key: '下一步', header: '下一步' },
];

/** 退出码的写法：超时（504）一类信封的退出码是 null，那时写「没有返回退出码」。 */
function exitCodeText(exitCode: number | null): string {
  return typeof exitCode === 'number' ? `返回退出码 ${exitCode}` : '没有返回退出码';
}

export function QuizsBlock({
  quizs,
}: {
  quizs: { providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> };
}) {
  const providers = quizs.providers;
  const live = quizs.live;
  // 两个信封整个收下：读失败只在这一块里写出来（不参与整页失败判定），成功时按各自的数据渲染。
  const providersBad = providersUnavailable(providers);
  const liveBad = liveUnavailable(live);
  const providerRows = providersBad ? [] : (providers.data?.providers ?? []);
  const liveRows = liveBad ? [] : (live.data?.live ?? []);
  // 提供方名作 rowId：服务不保证提供方名唯一，重名时加序号，避免行键重复。
  const names = new Map<string, number>();
  for (const row of providerRows) {
    const name = row.provider ?? DASH;
    names.set(name, (names.get(name) ?? 0) + 1);
  }
  return (
    <Section title="Quizs">
      {providersBad ? (
        <div className="rt-quizs-err">
          <p className="rt-quizs-errtext">Quizs 跑不起来</p>
          <p className="rt-quizs-errtext">
            命令 {providers.command.join(' ')} {exitCodeText(providers.exit_code)}。
          </p>
          <pre className="rt-quizs-msg">{providers.messages.join('\n')}</pre>
        </div>
      ) : providerRows.length === 0 ? (
        <p className="rt-quizs-empty">还没有 Quizs 提供方档案</p>
      ) : (
        <Table
          className="rt-quizs-table"
          aria-label="Quizs 提供方档案"
          rowHeight={40}
          columns={PROVIDER_COLUMNS}
          rows={providerRows.map((row, i) => {
            const name = row.provider ?? DASH;
            return {
              rowId: (names.get(name) ?? 0) > 1 ? `${name} ${i + 1}` : name,
              提供方: name,
              模型: row.model ?? DASH,
              思考档位: row.thinking.length > 0 ? row.thinking.join('、') : DASH,
              计费: billingLabel(row.billing),
            };
          })}
          rowKey={(r) => r.rowId}
        />
      )}
      {liveBad ? (
        <div className="rt-quizs-err">
          <p className="rt-quizs-errtext">
            没能读到 Quizs 的 live 套：命令 {live.command.join(' ')} {exitCodeText(live.exit_code)}。
          </p>
          <pre className="rt-quizs-msg">{live.messages.join('\n')}</pre>
        </div>
      ) : liveRows.length === 0 ? (
        <p className="rt-quizs-empty">还没有 Quizs live 套</p>
      ) : (
        <Table
          className="rt-quizs-table"
          aria-label="Quizs live 套"
          rowHeight={40}
          columns={LIVE_COLUMNS}
          rows={liveRows.map((row, i) => {
            const status = row.status;
            const state = liveStateLabel(status?.state ?? null);
            return {
              rowId: `${row.source ?? DASH} ${i + 1}`,
              提供方: row.provider ?? DASH,
              来源: liveSourceLabel(row.source),
              状态: <Tag tone={state.tone}>{state.label}</Tag>,
              证书到期: formatMsUtc(status?.certificate?.expires_at_ms),
              档案有效期: formatIsoUtc(status?.profile?.valid_until),
              下一步: nextStepCell(
                liveNextStep(status?.state ?? null, status?.missing ?? []),
                row.problem,
                status?.problem ?? null,
              ),
            };
          })}
          rowKey={(r) => r.rowId}
        />
      )}
    </Section>
  );
}
