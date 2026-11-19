// CLI 运行时视图（合同第 6 节）：已登记表（七列）、就绪检查区与 Quizs 一块；版本一律「—」。
// [探测]、[模型] 与 [运行就绪检查] 都走 src/writes 下的作业入口（同类作业同时只一个，忙时禁用并写明正在忙谁），
// [删除…] 走既有写流程。视图只收数据，不调 api。一个 runtime 都没有时视图照旧渲染：「已登记」那一节
// 改成空态（标题与说明两段原文不变），就绪检查一节与 Quizs 一块照常摆在视图根里。
import type { ReactNode } from 'react';
import type { Envelope, QuizsLiveData, QuizsProvidersData, RuntimesData } from '../../api';
import { Button, EmptyState, Table, Tag, type TableColumn } from '../../components';
import { CircleXIcon } from '../../icons';
import { ModelsRuntimeAction } from '../../writes/RuntimeModels';
import { ProbeRuntimeAction } from '../../writes/RuntimeProbe';
import { RuntimeDoctor } from '../../writes/RuntimeDoctor';
import { Section } from './common-Section';
import { QuizsBlock } from './runtimes-QuizsBlock';
import { useWriteFlow } from '../../writes/useWriteFlow';
import { WriteFlow } from '../../writes/WriteConfirmDialog';
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
  quizs: { providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> };
  reload?: () => Promise<void>;
}

export function RuntimesView({ runtimes, quizs, reload }: RuntimesViewProps) {
  const { start, flow } = useWriteFlow(reload);
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
          {canProbe(rt.source) && <ProbeRuntimeAction runtime={rt.id} />}
          {canModels(rt.adapter, rt.source) && <ModelsRuntimeAction runtime={rt.id} />}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => start({ action: 'runtime.remove', args: { runtime: rt.id } })}
          >
            删除…
          </Button>
        </>
      ),
    };
  });

  return (
    <div className="rt" data-page="runtimes">
      <Section title="已登记">
        {runtimes.length === 0 ? (
          <EmptyState title="还没有登记的 runtime" description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）" />
        ) : (
          <Table
            className="rt-table"
            aria-label="已登记的 runtime"
            rowHeight={40}
            columns={COLUMNS}
            rows={rows}
            rowKey={(r) => r.rowId}
          />
        )}
      </Section>
      <Section title="就绪检查">
        <div className="rt-ready-area">
          <RuntimeDoctor />
        </div>
      </Section>
      <QuizsBlock quizs={quizs} />
      <WriteFlow flow={flow} />
    </div>
  );
}
