// CLI 运行时视图（合同第 6 节）：已登记表（七列）与就绪检查区；版本一律「—」；操作全部禁用。
// 只收数据，不调 api。
import type { ReactNode } from 'react';
import type { RuntimesData } from '../../api';
import { Table, Tag, type TableColumn } from '../../components';
import { CircleXIcon, PlayIcon } from '../../icons';
import { DisabledAction } from '../../shell/DisabledAction';
import { Section } from './common-Section';
import {
  canModels,
  canProbe,
  canServe,
  commandFull,
  commandText,
  isUnconnected,
  sourceLabel,
  sourceTone,
} from './runtimes-logic';
// 样式表接线（终审 B1）：放在组件 import 之后，使本表晚于 common-section.css 载入。
import './runtimes-styles.css';

interface RuntimeRowData {
  rowId: string;
  ID: ReactNode;
  适配器: ReactNode;
  能担任: ReactNode;
  命令来源: ReactNode;
  命令: ReactNode;
  版本: ReactNode;
  操作: ReactNode;
}

const COLUMNS: readonly TableColumn<RuntimeRowData>[] = [
  { key: 'ID', header: 'ID', mono: true },
  { key: '适配器', header: '适配器' },
  { key: '能担任', header: '能担任' },
  { key: '命令来源', header: '命令来源' },
  { key: '命令', header: '命令', mono: true },
  { key: '版本', header: '版本' },
  { key: '操作', header: '操作' },
];

export interface RuntimesViewProps {
  runtimes: RuntimesData['runtimes'];
}

export function RuntimesView({ runtimes }: RuntimesViewProps) {
  const rows: RuntimeRowData[] = runtimes.map((rt) => {
    const full = commandFull(rt.command);
    return {
      rowId: rt.id,
      ID: rt.id,
      适配器: rt.adapter,
      能担任: isUnconnected(rt.id) ? <span className="rt-dim">{canServe(rt.id)}</span> : canServe(rt.id),
      命令来源: (
        <Tag tone={sourceTone(rt.source)} data-source={rt.source} title={rt.notes.length ? rt.notes.join('\n') : undefined}>
          {rt.source === 'missing' && <CircleXIcon width={12} height={12} />}
          {sourceLabel(rt.source)}
        </Tag>
      ),
      命令: (
        <span className="rt-cmd" title={full ?? undefined}>
          {commandText(rt.command)}
        </span>
      ),
      版本: '—',
      操作: (
        <>
          {canProbe(rt.source) && <DisabledAction label="探测" variant="ghost" size="sm" />}
          {canModels(rt.adapter, rt.source) && <DisabledAction label="模型" variant="ghost" size="sm" />}
          <DisabledAction label="删除…" variant="ghost" size="sm" />
        </>
      ),
    };
  });

  return (
    <div className="rt" data-page="runtimes">
      <Section title="已登记">
        <Table
          className="rt-table"
          aria-label="已登记的 runtime"
          rowHeight={40}
          columns={COLUMNS}
          rows={rows}
          rowKey={(r) => r.rowId}
        />
      </Section>
      <Section title="就绪检查">
        <div className="rt-ready-area">
          <DisabledAction label="运行就绪检查" variant="secondary" icon={<PlayIcon width={16} height={16} />} />
          <p className="rt-ready">
            还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据；运行入口在第二阶段接入。
          </p>
        </div>
      </Section>
    </div>
  );
}
