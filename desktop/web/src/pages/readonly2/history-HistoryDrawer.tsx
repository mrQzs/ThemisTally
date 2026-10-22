// 历史与审计抽屉（合同 D07）：标题、dl、外部改动提示条、键级差异五种情形、底栏说明与禁用的回滚入口。
// 打开或换行时调读取函数，只认最后一次请求，卸载后不写状态。
import { useEffect, useState } from 'react';
import { Banner } from '../../components';
import { actionTitle } from '../../components/actionTitle';
import { formatLocalUtc } from '../../components/RelativeTime';
import { LockIcon } from '../../icons';
import type { Envelope } from '../../api';
import { KeyDiff, MaskedKeyDiff } from './history-KeyDiff';
import {
  diffKind,
  stateText,
  type HistoryDetail,
  type HistoryEntry,
} from './history-logic';
import './history-styles.css';

export type HistoryReader = (n: number) => Promise<Envelope<HistoryDetail>>;

type State =
  | { kind: 'loading' }
  | { kind: 'error'; command: string[]; exit_code: number; messages: string[] }
  | { kind: 'ok'; detail: HistoryDetail };

export function HistoryDrawer({ entry, load }: { entry: HistoryEntry; load: HistoryReader }) {
  const [state, setState] = useState<State>({ kind: 'loading' });

  useEffect(() => {
    let alive = true;
    setState({ kind: 'loading' });
    load(entry.number)
      .then((env) => {
        if (!alive) return;
        if (env.ok && env.data) setState({ kind: 'ok', detail: env.data });
        else setState({ kind: 'error', command: env.command, exit_code: env.exit_code, messages: env.messages });
      })
      .catch(() => {
        if (!alive) return;
        setState({ kind: 'error', command: [], exit_code: 2, messages: [] });
      });
    return () => {
      alive = false;
    };
  }, [entry.number, load]);

  const kind = state.kind === 'ok' ? diffKind(entry, state.detail) : null;
  const external = typeof entry.external_changes === 'number' ? entry.external_changes : 0;

  return (
    <div className="r2-drawer" data-drawer="history">
      <dl className="r2-dl">
        <dt>时间</dt>
        <dd className="r2-mono">{formatLocalUtc(entry.at) ?? entry.at}</dd>
        <dt>动作</dt>
        <dd>
          <span className="r2-mono">{entry.action}</span>
          {actionTitle(entry.action) ? <span className="r2-plugins__reason">{actionTitle(entry.action)}</span> : null}
        </dd>
        <dt>执行者</dt>
        <dd className="r2-mono">{entry.actor}</dd>
        <dt>确认</dt>
        <dd className="r2-mono">{entry.confirmation}</dd>
        <dt>状态</dt>
        <dd>{stateText(entry)}</dd>
      </dl>
      {external > 0 && <Banner tone="warning">这条之后检测到 {external} 次界面与命令之外的改动。</Banner>}
      <section className="r2-drawer__section">
        <h3>键级差异</h3>
        {state.kind === 'loading' && <p className="r2-dim">正在读取…</p>}
        {state.kind === 'error' && (
          <div className="r2-drawer__error">
            <p className="r2-drawer__error-cmd">
              没能读到详情：命令（{state.command.join(' ')}）返回退出码 {state.exit_code}。
            </p>
            <pre className="r2-drawer__error-msg">{state.messages.join('\n')}</pre>
          </div>
        )}
        {state.kind === 'ok' && kind?.kind === 'local' && (
          <p className="r2-dim">本机文件不存快照，这一条只有审计记录，不能回滚。</p>
        )}
        {state.kind === 'ok' && kind?.kind === 'keys' && <KeyDiff diff={kind.diff} />}
        {state.kind === 'ok' && kind?.kind === 'empty' && <p className="r2-dim">没有改动的键</p>}
        {state.kind === 'ok' && kind?.kind === 'masked-keys' && (
          <>
            <MaskedKeyDiff placeholder={kind.placeholder} keys={kind.keys} />
            <MaskedSnapshotNote />
          </>
        )}
        {state.kind === 'ok' && kind?.kind === 'masked-note' && (
          <>
            <p className="r2-dim">{kind.note}</p>
            <MaskedSnapshotNote />
          </>
        )}
        {state.kind === 'ok' && kind?.kind === 'note' && (
          <p className="r2-dim">{kind.note ?? '快照缺失，没有逐键差异'}</p>
        )}
      </section>
    </div>
  );
}

function MaskedSnapshotNote() {
  return (
    <p className="r2-drawer__lock-note">
      <LockIcon width={12} height={12} />
      快照里有疑似凭据，只存了哈希。
    </p>
  );
}
