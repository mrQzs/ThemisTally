// 凭据页视图（合同 D01）：四列表格（没有「值」列）、表后一条不可关的 info 说明与「“来源”标签」小节。
// 只显示每个环境变量在哪一层找到，从不显示值；遮蔽占位用 MaskedValue。
import { useId, type ReactNode } from 'react';
import { MaskedValue, isMaskedPlaceholder, Tag, Table, type TableColumn } from '../../components';
import { CircleXIcon } from '../../icons';
import { SecretsIcon } from '../../icons/frame';
import { DisabledAction } from '../../shell/DisabledAction';
import type { SecretsData } from '../../api';
import { InfoNote } from './common-InfoNote';
import { ExternalLinkIcon } from './common-icons';
import { SOURCE_LEGEND, sourceTag, usedBySegments, type UsedByItem } from './secrets-logic';
import './secrets-styles.css';

interface SecretRowView {
  key: string;
  name: ReactNode;
  usedBy: ReactNode;
  source: ReactNode;
  action: ReactNode;
}

const COLUMNS: readonly TableColumn<SecretRowView>[] = [
  { key: 'name', header: '变量名', mono: true },
  { key: 'usedBy', header: '用在哪里' },
  { key: 'source', header: '来源' },
  { key: 'action', header: '操作' },
];

/** id：遮蔽占位用 MaskedValue，否则等宽原样。 */
function IdText({ id }: { id: string }) {
  return isMaskedPlaceholder(id) ? <MaskedValue>{id}</MaskedValue> : <span className="r2-mono">{id}</span>;
}

/** 用在哪里：按出现顺序渲染各段，段间用「、」连接。 */
function UsedByCell({ used }: { used: readonly UsedByItem[] }) {
  const segments = usedBySegments(used);
  return (
    <>
      {segments.map((seg, i) => (
        <span key={`${seg.kind}-${seg.label}-${i}`}>
          {i > 0 ? '、' : null}
          {seg.kind === 'profiles' ? (
            <>
              {'profile '}
              {seg.ids.map((id, k) => (
                <span key={`${id}-${k}`}>
                  {k > 0 ? '、' : null}
                  <IdText id={id} />
                </span>
              ))}
            </>
          ) : (
            <>
              {seg.label}
              {seg.ids.map((id, k) => (
                <span key={`${id}-${k}`}>
                  {' '}
                  <IdText id={id} />
                </span>
              ))}
            </>
          )}
        </span>
      ))}
    </>
  );
}

function SourceCell({ source }: { source: string }) {
  const tag = sourceTag(source);
  const Icon = tag.icon === 'store' ? SecretsIcon : tag.icon === 'missing' ? CircleXIcon : null;
  return (
    <Tag tone={tag.tone} className={tag.icon ? 'r2-tag-icon' : undefined} data-source={source}>
      {Icon ? <Icon width={14} height={14} /> : null}
      {tag.label}
    </Tag>
  );
}

export function SecretsView({ data }: { data: SecretsData }) {
  const legendId = useId();
  const rows: SecretRowView[] = data.secrets.map((s) => ({
    key: s.name,
    name: isMaskedPlaceholder(s.name) ? <MaskedValue>{s.name}</MaskedValue> : <span className="r2-mono">{s.name}</span>,
    usedBy: <UsedByCell used={s.used_by ?? []} />,
    source: <SourceCell source={s.source} />,
    action: (
      <DisabledAction
        label="录入…"
        variant="secondary"
        size="sm"
        icon={<ExternalLinkIcon width={14} height={14} />}
      />
    ),
  }));

  return (
    <div className="r2-stack r2-secrets" data-page="secrets">
      <Table
        className="r2-secrets__table"
        columns={COLUMNS}
        rows={rows}
        rowKey={(r) => r.key}
        rowHeight={44}
        aria-label="凭据变量"
      />
      <InfoNote>录入只在单独的一次性页面里进行，值直接存进系统凭据库；这个界面拿不到值。</InfoNote>
      <section className="r2-card" aria-labelledby={legendId}>
        <h2 id={legendId}>“来源”标签</h2>
        <ul className="r2-sources">
          {SOURCE_LEGEND.map((item) => (
            <li key={item.tag.label}>
              <Tag tone={item.tag.tone}>{item.tag.label}</Tag>
              <span>{item.note}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
