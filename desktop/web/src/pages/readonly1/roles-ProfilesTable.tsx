// profile 表（合同第 5 节）：Table rowHeight 40、aria-label「profile」；列 ID/runtime/模型/thinking/凭据变量/被引用/操作；
// thinking 缺失「缺省」；凭据变量每变量一个 mono neutral Tag；被引用取当前无头且 profile 相符的角色名；操作禁用。
import type { ReactNode } from 'react';
import type { ProfilesData } from '../../api';
import { Table, type TableColumn } from '../../components';
import { Tag } from '../../components';
import { DisabledAction } from '../../shell/DisabledAction';
import { Section } from './common-Section';
import { profileRefs, type RoleInfo } from './roles-logic';

type LooseProfile = {
  id: string;
  runtime?: string | null;
  provider?: string | null;
  model?: string | null;
  options?: { thinking?: string | null } | null;
  credential_env?: readonly string[] | null;
};

interface ProfileRow {
  rowId: string;
  ID: ReactNode;
  runtime: ReactNode;
  模型: ReactNode;
  thinking: ReactNode;
  凭据变量: ReactNode;
  被引用: ReactNode;
  操作: ReactNode;
}

const COLUMNS: readonly TableColumn<ProfileRow>[] = [
  { key: 'ID', header: 'ID', mono: true },
  { key: 'runtime', header: 'runtime', mono: true },
  { key: '模型', header: '模型', mono: true },
  { key: 'thinking', header: 'thinking', mono: true },
  { key: '凭据变量', header: '凭据变量' },
  { key: '被引用', header: '被引用' },
  { key: '操作', header: '操作' },
];

export interface ProfilesTableProps {
  profiles: ProfilesData['profiles'];
  roles: readonly RoleInfo[];
}

export function ProfilesTable({ profiles, roles }: ProfilesTableProps) {
  const rows: ProfileRow[] = profiles.map((raw) => {
    const p = raw as unknown as LooseProfile;
    const thinking = p.options && typeof p.options.thinking === 'string' ? p.options.thinking : null;
    const creds = Array.isArray(p.credential_env) ? p.credential_env : [];
    return {
      rowId: p.id,
      ID: p.id,
      runtime: p.runtime ?? '—',
      模型: `${p.provider ?? '—'}/${p.model ?? '—'}`,
      thinking: thinking ?? <span className="rl-dim">缺省</span>,
      凭据变量:
        creds.length > 0 ? (
          <>
            {creds.map((c) => (
              <Tag key={c} tone="neutral" mono>
                {c}
              </Tag>
            ))}
          </>
        ) : (
          '—'
        ),
      被引用: profileRefs(roles, p.id),
      操作: (
        <>
          <DisabledAction label="编辑" variant="ghost" size="sm" />
          <DisabledAction label="删除" variant="ghost" size="sm" />
        </>
      ),
    };
  });

  return (
    <Section title="profile" description="一个 CLI、一个模型与选项的组合">
      {rows.length === 0 ? (
        <p className="rl-note">还没有 profile</p>
      ) : (
        <Table
          className="rl-table rl-profile"
          aria-label="profile"
          rowHeight={40}
          columns={COLUMNS}
          rows={rows}
          rowKey={(r) => r.rowId}
        />
      )}
    </Section>
  );
}
