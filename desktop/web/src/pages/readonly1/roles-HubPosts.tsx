// 七端岗位（合同第 6 节）：只读六行表——岗位、运行时、模型、思考档位、来源、替补，没有操作列、没有按钮。
// hub 信封整个收下：读失败时只这一组显示失败信封与 messages（pre），四个角色卡、profile 表、方案表照常。
// 视图只收数据与回调：从 ../../api 只 import type。字段已在 roles-logic 归一，这里只渲染。
import type { ReactNode } from 'react';
import type { Envelope, HubRolesData } from '../../api';
import { EffortPair, Table, Tag, type TableColumn } from '../../components';
import { Section } from './common-Section';
import { hubPostName, normalizeHubPost, type HubPostInfo } from './roles-logic';

const DASH = '—';

interface HubRow {
  rowId: string;
  岗位: ReactNode;
  运行时: string;
  模型: string;
  思考档位: ReactNode;
  来源: ReactNode;
  替补: string;
}

const COLUMNS: readonly TableColumn<HubRow>[] = [
  { key: '岗位', header: '岗位' },
  { key: '运行时', header: '运行时' },
  { key: '模型', header: '模型', mono: true },
  { key: '思考档位', header: '思考档位' },
  { key: '来源', header: '来源' },
  { key: '替补', header: '替补' },
];

// 运行时列：{runtime ?? —}（{adapter ?? —}）（照 RoleCard）。
function runtimeText(runtime: string | null, adapter: string | null): string {
  return `${runtime ?? DASH}（${adapter ?? DASH}）`;
}

// 替补列：替补 profile（没有就省掉）· runtime（adapter） · provider/model，三段用「 · 」连接；替补为 null 是「—」。
// 思考档位不出现在这一列。
function fallbackText(fb: HubPostInfo['fallback']): string {
  if (fb == null) return DASH;
  const segs: string[] = [];
  if (fb.profile != null) segs.push(fb.profile);
  segs.push(runtimeText(fb.runtime, fb.adapter));
  segs.push(`${fb.provider ?? DASH}/${fb.model ?? DASH}`);
  return segs.join(' · ');
}

// 来源列：缺省行 neutral Tag「默认」；配置行是该行的 profile id（等宽）。
function sourceCell(p: HubPostInfo): ReactNode {
  if (p.source === 'config') {
    return p.profile != null ? <span className="tt-table__mono">{p.profile}</span> : DASH;
  }
  return <Tag tone="neutral">默认</Tag>;
}

export interface HubPostsProps {
  hub: Envelope<HubRolesData>;
}

export function HubPosts({ hub }: HubPostsProps) {
  return (
    <Section title="七端岗位">
      {hub.ok && hub.data ? (
        <Table
          className="rl-table rl-hub"
          aria-label="七端岗位"
          rowHeight={40}
          columns={COLUMNS}
          rows={hub.data.posts.map((raw) => {
            const p = normalizeHubPost(raw);
            return {
              rowId: p.post,
              岗位: hubPostName(p.post),
              运行时: runtimeText(p.runtime, p.adapter),
              模型: `${p.provider ?? DASH}/${p.model ?? DASH}`,
              思考档位: <EffortPair requested={p.thinking} effective={null} />,
              来源: sourceCell(p),
              替补: fallbackText(p.fallback),
            };
          })}
          rowKey={(r) => r.rowId}
          rowAttrs={(r) => ({ 'data-post': r.rowId })}
        />
      ) : (
        <div className="rl-hub-err">
          <p className="rl-hub-errtext">
            没能读到七端岗位：命令 {hub.command.join(' ')} 返回退出码 {hub.exit_code}。
          </p>
          <pre className="rl-hub-msg">{hub.messages.join('\n')}</pre>
        </div>
      )}
    </Section>
  );
}
