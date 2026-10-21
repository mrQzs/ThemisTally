// 插件抽屉（合同 D05）：manifest、资源哈希核对、锁三节；打开或换行时调读取函数，只认最后一次请求。
import { useEffect, useState } from 'react';
import { Banner, IconButton, Tag, type TagTone } from '../../components';
import { CopyIcon } from '../../icons';
import type { Envelope } from '../../api';
import type { PluginShowData } from '../../mock/readonly2-plugin-show';
import { copyText, COPY_RESULT_TEXT, type CopyResult } from './common-copy';
import { drawerWarning, joinList, lockView, type PluginRow } from './plugins-logic';
import './plugins-styles.css';

export type PluginReader = (id: string) => Promise<Envelope<PluginShowData>>;

type State =
  | { kind: 'loading' }
  | { kind: 'error'; command: string[]; exit_code: number; messages: string[] }
  | { kind: 'ok'; data: PluginShowData };

const RESULT_TONE: Record<string, TagTone> = {
  success: 'success',
  warning: 'warning',
  danger: 'danger',
  neutral: 'neutral',
};

export function PluginDrawer({ row, load }: { row: PluginRow; load: PluginReader }) {
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [copy, setCopy] = useState<CopyResult | null>(null);

  // 打开或换行时重新读取；只认最后一次请求，卸载后不写状态。
  useEffect(() => {
    let alive = true;
    setState({ kind: 'loading' });
    load(row.id)
      .then((env) => {
        if (!alive) return;
        if (env.ok && env.data) setState({ kind: 'ok', data: env.data });
        else setState({ kind: 'error', command: env.command, exit_code: env.exit_code, messages: env.messages });
      })
      .catch(() => {
        if (!alive) return;
        setState({ kind: 'error', command: [], exit_code: 2, messages: [] });
      });
    return () => {
      alive = false;
    };
  }, [row.id, load]);

  const missing = state.kind === 'ok'
    && Array.isArray(state.data.config?.missing_permissions)
    ? state.data.config.missing_permissions
    : row.missing ?? [];
  const missingSet = new Set(missing);

  const onCopy = () => {
    if (state.kind !== 'ok') return;
    void copyText(state.data.lock.lock_sha256).then(setCopy);
  };

  return (
    <div className="r2-drawer" data-drawer="plugin">
      {row.status !== 'READY' && <Banner tone="warning">{drawerWarning(row.status, row.reason, missing)}</Banner>}
      {state.kind === 'loading' && <p className="r2-dim">正在读取…</p>}
      {state.kind === 'error' && (
        <div className="r2-drawer__error">
          <p className="r2-drawer__error-cmd">
            没能读到详情：命令（{state.command.join(' ')}）返回退出码 {state.exit_code}。
          </p>
          <pre className="r2-drawer__error-msg">{state.messages.join('\n')}</pre>
        </div>
      )}
      {state.kind === 'ok' && (
        <>
          <section className="r2-drawer__section">
            <h3>manifest</h3>
            <dl className="r2-dl">
              <dt>ID</dt>
              <dd className="r2-mono">{state.data.plugin_id}</dd>
              <dt>版本</dt>
              <dd className="r2-mono">{state.data.version}</dd>
              <dt>启用</dt>
              <dd>
                {row.enabled}
                {row.enabled === '不限制' ? '（没有配置启用名单）' : ''}
              </dd>
              <dt>权限</dt>
              <dd className="r2-drawer__tags">
                {(state.data.permissions ?? []).map((p) => (
                  <Tag key={p} tone={missingSet.has(p) ? 'danger' : 'neutral'} mono>
                    {p}
                    {missingSet.has(p) ? '（缺）' : ''}
                  </Tag>
                ))}
              </dd>
              <dt>api_version</dt>
              <dd className="r2-mono">{state.data.api_version}</dd>
              <dt>capabilities</dt>
              <dd>{joinList(state.data.capabilities)}</dd>
              <dt>platforms</dt>
              <dd>{joinList(state.data.platforms)}</dd>
              <dt>depends_on</dt>
              <dd>{joinList(state.data.depends_on)}</dd>
              <dt>conflicts</dt>
              <dd>{joinList(state.data.conflicts)}</dd>
            </dl>
          </section>
          <section className="r2-drawer__section">
            <h3>资源哈希核对</h3>
            <div className="r2-res">
              <div className="r2-res__head">
                <span>路径</span>
                <span>sha256</span>
                <span>结果</span>
              </div>
              {(state.data.resources ?? []).map((r) => {
                const view = lockView(r.status, r.detail);
                return (
                  <div className="r2-res__row" key={`${r.path}-${r.sha256}`}>
                    <span className="r2-res__path r2-mono" title={r.path}>
                      {r.path}
                    </span>
                    <span className="r2-res__sha r2-mono r2-dim" title={r.sha256}>
                      {r.sha256.slice(0, 12)}…
                    </span>
                    <span className="r2-res__result" data-tone={RESULT_TONE[view.tone] ?? 'neutral'}>
                      {view.text}
                      {r.detail ? `（${r.detail}）` : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
          <section className="r2-drawer__section">
            <h3>锁</h3>
            <dl className="r2-dl">
              <dt>generation</dt>
              <dd className="r2-mono tt-num">{state.data.lock.generation}</dd>
              <dt>lock_sha256</dt>
              <dd className="r2-drawer__lock">
                <code className="r2-mono r2-break">{state.data.lock.lock_sha256}</code>
                <IconButton label="复制 lock_sha256" icon={<CopyIcon width={14} height={14} />} size="sm" onClick={onCopy} />
                {copy ? <span className="r2-copy-result">{COPY_RESULT_TEXT[copy]}</span> : null}
              </dd>
            </dl>
          </section>
        </>
      )}
    </div>
  );
}
