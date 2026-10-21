// 历史与审计页视图（合同 D06）：十列宽表，行按编号倒序；点行或 Enter 打开差异抽屉，只换内容不关抽屉。
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Banner, Drawer, MaskedValue, Table, Tag, isMaskedPlaceholder, type TableColumn } from '../../components';
import { RotateCcwIcon, TriangleAlertIcon } from '../../icons';
import { DisabledAction } from '../../shell/DisabledAction';
import type { HistoryData } from '../../api';
import { ActorTag } from './history-ActorTag';
import { HistoryDrawer, type HistoryReader } from './history-HistoryDrawer';
import {
  actionTitle,
  drawerTitle,
  resourceLabel,
  rollbackNote,
  sortedEntries,
  stateText,
  timeCell,
  type HistoryEntry,
} from './history-logic';
import './history-styles.css';

interface HistoryRowView {
  key: string;
  number: ReactNode;
  at: ReactNode;
  resource: ReactNode;
  action: ReactNode;
  target: ReactNode;
  actor: ReactNode;
  confirmation: ReactNode;
  state: ReactNode;
  changedKeys: ReactNode;
  external: ReactNode;
}

const COLUMNS: readonly TableColumn<HistoryRowView>[] = [
  { key: 'number', header: '编号', numeric: true, mono: true },
  { key: 'at', header: '时间' },
  { key: 'resource', header: '资源' },
  { key: 'action', header: '动作', mono: true },
  { key: 'target', header: '对象', mono: true },
  { key: 'actor', header: '执行者' },
  { key: 'confirmation', header: '确认', mono: true },
  { key: 'state', header: '状态' },
  { key: 'changedKeys', header: '改动的键' },
  { key: 'external', header: '外部改动' },
];

function ChangedKeysCell({ entry }: { entry: HistoryEntry }) {
  const keys = entry.changed_keys;
  if (keys && keys.length > 0) {
    return (
      <>
        {keys.map((k) => (
          <Tag key={k} tone="neutral" mono>
            {k}
          </Tag>
        ))}
      </>
    );
  }
  const note = entry.note;
  if (note) {
    return isMaskedPlaceholder(note) ? <MaskedValue>{note}</MaskedValue> : <span className="r2-history__note">{note}</span>;
  }
  return <span className="r2-dim">—</span>;
}

export function HistoryView({ data, getHistoryEntry }: { data: HistoryData; getHistoryEntry: HistoryReader }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [openNumber, setOpenNumber] = useState<number | null>(null);
  const entries: HistoryEntry[] = data.entries ?? [];
  const rowsData = sortedEntries(entries);
  const newestNumber = rowsData.length > 0 ? rowsData[0].number : 0;
  const openEntry = rowsData.find((e) => e.number === openNumber) ?? null;
  const broken = data.broken_lines ?? [];
  const before = typeof data.external_before_first === 'number' ? data.external_before_first : 0;
  const now = Date.now();

  const onRowOpen = (key: string) => {
    const n = Number(key);
    setSelectedKey(key);
    setOpenNumber(n);
  };

  // 关闭后把焦点移到最后打开的那一行（Drawer 清理里的还焦点早于本 effect）。
  const prevOpen = useRef<number | null>(null);
  useEffect(() => {
    const wasOpen = prevOpen.current !== null;
    prevOpen.current = openNumber;
    if (!wasOpen || openNumber !== null || selectedKey === null) return;
    const row = rootRef.current?.querySelector('tbody tr[data-selected]') as HTMLElement | null;
    row?.focus();
  }, [openNumber, selectedKey]);

  const views: HistoryRowView[] = rowsData.map((e) => {
    const time = timeCell(e.at, now);
    const title = actionTitle(e.action);
    const external = typeof e.external_changes === 'number' ? e.external_changes : 0;
    return {
      key: String(e.number),
      number: <span className="r2-mono">{`#${e.number}`}</span>,
      at: (
        <span className="r2-history__time" title={time.title ?? undefined}>
          {time.text}
        </span>
      ),
      resource: <span>{resourceLabel(e.resource)}</span>,
      action: (
        <span className="r2-mono" title={title ?? undefined}>
          {e.action}
        </span>
      ),
      target: <span className="r2-mono">{e.target ? e.target : '—'}</span>,
      actor: <ActorTag actor={e.actor} />,
      confirmation: <span className="r2-history__confirm">{e.confirmation}</span>,
      state: (
        <span className="r2-history__state" title={e.state ?? undefined}>
          {stateText(e)}
        </span>
      ),
      changedKeys: <ChangedKeysCell entry={e} />,
      external: external > 0 ? (
        <Tag tone="warning" className="r2-tag-icon" title={`这条之后发现 ${external} 次在配置中心之外的改动`}>
          <TriangleAlertIcon width={12} height={12} />
          检测到外部改动
        </Tag>
      ) : (
        <span className="r2-dim">—</span>
      ),
    };
  });

  return (
    <div className="r2-stack r2-history" data-page="history" ref={rootRef}>
      {broken.length > 0 && <Banner tone="warning">历史里有 {broken.length} 行读不出来</Banner>}
      {before > 0 && (
        <p className="r2-history__baseline">
          第 1 条之前：配置中心之外已有的内容（记为基线，发现 {before} 次）
        </p>
      )}
      <Table
        className="r2-history__table"
        columns={COLUMNS}
        rows={views}
        rowKey={(r) => r.key}
        rowHeight={40}
        onRowOpen={onRowOpen}
        selectedKey={selectedKey ?? undefined}
        aria-label="配置历史"
      />
      <p className="r2-history__note-line">
        时间显示相对时间，悬停显示本地时间与 UTC；动作悬停显示中文说明。
      </p>
      <Drawer
        open={openEntry !== null}
        onClose={() => setOpenNumber(null)}
        title={openEntry ? drawerTitle(openEntry) : ''}
        footer={
          <div className="r2-drawer__footer">
            {openEntry && rollbackNote(openEntry, newestNumber) ? (
              <span className="r2-drawer__note-text">{rollbackNote(openEntry, newestNumber)}</span>
            ) : null}
            <DisabledAction
              label="回滚到这一条之后"
              variant="secondary"
              size="md"
              icon={<RotateCcwIcon width={16} height={16} />}
            />
          </div>
        }
      >
        {openEntry ? <HistoryDrawer entry={openEntry} load={getHistoryEntry} /> : null}
      </Drawer>
    </div>
  );
}
