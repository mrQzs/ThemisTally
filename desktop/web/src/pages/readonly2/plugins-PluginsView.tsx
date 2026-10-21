// 插件页视图（合同 D04、D05）：宽表加两个小节；点行或 Enter 打开非模态抽屉，只换内容不关抽屉。
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { CheckIcon, CircleXIcon, TriangleAlertIcon } from '../../icons';
import { PluginsIcon } from '../../icons/frame';
import { DisabledAction } from '../../shell/DisabledAction';
import { Drawer, Tag, Table, type TableColumn } from '../../components';
import type { PluginsData } from '../../api';
import { enabledView, lockView, pluginAction, statusTone, type PluginRow } from './plugins-logic';
import { PluginDrawer, type PluginReader } from './plugins-PluginDrawer';
import './plugins-styles.css';

interface PluginRowView {
  key: string;
  id: ReactNode;
  version: ReactNode;
  enabled: ReactNode;
  lock: ReactNode;
  resource: ReactNode;
  missing: ReactNode;
  status: ReactNode;
  action: ReactNode;
}

const COLUMNS: readonly TableColumn<PluginRowView>[] = [
  { key: 'id', header: 'ID', mono: true },
  { key: 'version', header: '版本', mono: true, numeric: true },
  { key: 'enabled', header: '启用' },
  { key: 'lock', header: '锁' },
  { key: 'resource', header: '资源' },
  { key: 'missing', header: '缺的权限' },
  { key: 'status', header: '状态' },
  { key: 'action', header: '操作' },
];

const LOCK_ICONS = {
  ok: <CheckIcon width={12} height={12} />,
  warn: <TriangleAlertIcon width={12} height={12} />,
  bad: <CircleXIcon width={12} height={12} />,
};

function LockCell({ value, reason }: { value: string; reason: string }) {
  const view = lockView(value, reason);
  if (view.text === '—') return <span className="r2-dim">—</span>;
  return (
    <Tag tone={view.tone} className={view.icon ? 'r2-tag-icon' : undefined} title={view.title ?? undefined}>
      {view.icon ? LOCK_ICONS[view.icon] : null}
      {view.text}
    </Tag>
  );
}

function EnabledCell({ value }: { value: string }) {
  const view = enabledView(value);
  if (view.tone === null) {
    return (
      <span className="r2-plugins__outline" title="没有配置启用名单">
        {view.text}
      </span>
    );
  }
  return <Tag tone={view.tone}>{view.text}</Tag>;
}

function MissingCell({ missing }: { missing: readonly string[] }) {
  if (!missing || missing.length === 0) return <span className="r2-dim">—</span>;
  return (
    <>
      {missing.map((m) => (
        <Tag key={m} tone="danger" mono>
          {m}
        </Tag>
      ))}
    </>
  );
}

function ActionCell({ enabled }: { enabled: string }) {
  const action = pluginAction(enabled);
  if (action.kind === 'detail') return <span className="r2-dim">详情</span>;
  return (
    <span
      className="r2-act"
      onClick={(e) => {
        e.stopPropagation();
      }}
    >
      <DisabledAction label={action.label} variant="ghost" size="sm" />
    </span>
  );
}

function drawerTitle(row: PluginRow): ReactNode {
  return (
    <>
      <PluginsIcon width={20} height={20} className="r2-drawer__icon" />
      <span className="r2-mono">{row.id}</span>
      <Tag tone={statusTone(row.status)} mono>
        {row.status}
      </Tag>
    </>
  );
}

export function PluginsView({ data, getPlugin }: { data: PluginsData; getPlugin: PluginReader }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const notInstalledId = useId();
  const problemsId = useId();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const rows: PluginRow[] = data.plugins ?? [];
  const openRow = rows.find((r) => r.id === openId) ?? null;

  const onRowOpen = (key: string) => {
    setSelectedKey(key);
    setOpenId(key);
  };

  // 关闭后把焦点移到最后打开的那一行（Drawer 清理里的还焦点早于本 effect）。
  const prevOpen = useRef<string | null>(null);
  useEffect(() => {
    const wasOpen = prevOpen.current !== null;
    prevOpen.current = openId;
    if (!wasOpen || openId !== null || selectedKey === null) return;
    const row = rootRef.current?.querySelector('tbody tr[data-selected]') as HTMLElement | null;
    row?.focus();
  }, [openId, selectedKey]);

  const views: PluginRowView[] = rows.map((r) => ({
    key: r.id,
    id: <span className="r2-mono">{r.id}</span>,
    version: <span className="r2-mono tt-num">{r.version}</span>,
    enabled: <EnabledCell value={r.enabled} />,
    lock: <LockCell value={r.lock} reason={r.reason} />,
    resource: <LockCell value={r.resource} reason={r.reason} />,
    missing: <MissingCell missing={r.missing ?? []} />,
    status: (
      <>
        <Tag tone={statusTone(r.status)} mono>
          {r.status}
        </Tag>
        {r.reason ? <span className="r2-plugins__reason">{r.reason}</span> : null}
      </>
    ),
    action: <ActionCell enabled={r.enabled} />,
  }));

  return (
    <div className="r2-stack r2-plugins" data-page="plugins" ref={rootRef}>
      <Table
        className="r2-plugins__table"
        columns={COLUMNS}
        rows={views}
        rowKey={(r) => r.key}
        rowHeight={40}
        onRowOpen={onRowOpen}
        selectedKey={selectedKey ?? undefined}
        aria-label="插件"
      />
      <div className="r2-plugins__notes">
        <section className="r2-card" aria-labelledby={notInstalledId}>
          <h2 id={notInstalledId}>列入但未安装</h2>
          {data.not_installed && data.not_installed.length > 0 ? (
            <ul className="r2-plugins__list">
              {data.not_installed.map((p) => (
                <li key={p} className="r2-mono">
                  {p}
                </li>
              ))}
            </ul>
          ) : (
            <p className="r2-dim">没有</p>
          )}
        </section>
        <section className="r2-card" aria-labelledby={problemsId}>
          <h2 id={problemsId}>问题</h2>
          {data.problems && data.problems.length > 0 ? (
            <ul className="r2-plugins__list">
              {data.problems.map((p) => (
                <li key={p} className="r2-mono">
                  {p}
                </li>
              ))}
            </ul>
          ) : (
            <p className="r2-dim">没有</p>
          )}
        </section>
      </div>
      <Drawer
        open={openRow !== null}
        onClose={() => setOpenId(null)}
        title={openRow ? drawerTitle(openRow) : ''}
        footer={<DisabledAction label="重新核对" variant="secondary" size="md" />}
      >
        {openRow ? <PluginDrawer row={openRow} load={getPlugin} /> : null}
      </Drawer>
    </div>
  );
}
