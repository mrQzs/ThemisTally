// 方案表（合同第 5 节）：列 名称/说明/包含的角色/当前/操作；当前行写「当前方案不能删」，其余行 [使用][删除…] 禁用、
// [查看差异] 可用；差异面板同时只开一个，只认最后一次请求（过期回应丢弃）。
import { useId, useRef, useState, type ReactNode } from 'react';
import type { Envelope, PresetDiffData, PresetsData } from '../../api';
import { Button, Table, type TableColumn } from '../../components';
import { CheckIcon } from '../../icons';
import { Tag } from '../../components';
import { DisabledAction } from '../../shell/DisabledAction';
import { Section } from './common-Section';
import { presetRoleTitle } from './roles-logic';
import { PresetDiff, type PresetDiffState } from './roles-PresetDiff';

interface PresetRow {
  rowId: string;
  名称: ReactNode;
  说明: ReactNode;
  包含的角色: ReactNode;
  当前: ReactNode;
  操作: ReactNode;
}

const COLUMNS: readonly TableColumn<PresetRow>[] = [
  { key: '名称', header: '名称', mono: true },
  { key: '说明', header: '说明' },
  { key: '包含的角色', header: '包含的角色' },
  { key: '当前', header: '当前' },
  { key: '操作', header: '操作' },
];

export interface PresetsTableProps {
  presets: PresetsData['presets'];
  active: string;
  totalRoles: number;
  onDiff: (a: string, b: string) => Promise<Envelope<PresetDiffData>>;
}

export function PresetsTable({ presets, active, totalRoles, onDiff }: PresetsTableProps) {
  const [openName, setOpenName] = useState<string | null>(null);
  const [diff, setDiff] = useState<PresetDiffState | null>(null);
  const reqRef = useRef(0);
  // 面板 id 用 useId 加行序号：各行互不相同，也不拿方案名拼（收起的按钮不给 aria-controls）。
  const diffId = useId();
  const openIndex = openName === null ? -1 : presets.findIndex((p) => p.name === openName);
  const panelId = `${diffId}-${openIndex}`;

  const toggle = (name: string) => {
    const my = (reqRef.current += 1);
    if (openName === name) {
      setOpenName(null);
      setDiff(null);
      return;
    }
    setOpenName(name);
    setDiff({ status: 'loading' });
    onDiff(active, name).then((env) => {
      if (my !== reqRef.current) return;
      if (env.ok && env.data) setDiff({ status: 'data', data: env.data });
      else
        setDiff({
          status: 'error',
          command: env.command.join(' '),
          exit_code: env.exit_code,
          messages: env.messages,
        });
    });
  };

  const rows: PresetRow[] = presets.map((p, i) => {
    const isCurrent = p.name === active;
    return {
      rowId: p.name,
      名称: p.name,
      说明: p.description,
      包含的角色: <span title={presetRoleTitle(p.roles)}>{p.roles.length} 个角色</span>,
      当前: p.active ? (
        <Tag tone="brand">
          <CheckIcon width={12} height={12} />
          当前
        </Tag>
      ) : (
        '—'
      ),
      操作: isCurrent ? (
        '当前方案不能删'
      ) : (
        <>
          <DisabledAction label="使用" variant="ghost" size="sm" />
          <DisabledAction label="删除…" variant="ghost" size="sm" />
          <Button
            variant="ghost"
            size="sm"
            aria-expanded={openName === p.name}
            aria-controls={openName === p.name ? `${diffId}-${i}` : undefined}
            onClick={() => toggle(p.name)}
          >
            查看差异
          </Button>
        </>
      ),
    };
  });

  return (
    <Section title="方案" description="一组角色绑定，可以一键切换">
      <Table
        className="rl-table rl-preset"
        aria-label="方案"
        rowHeight={40}
        columns={COLUMNS}
        rows={rows}
        rowKey={(r) => r.rowId}
      />
      {openName !== null && (
        <PresetDiff id={panelId} active={active} name={openName} state={diff} totalRoles={totalRoles} />
      )}
    </Section>
  );
}
