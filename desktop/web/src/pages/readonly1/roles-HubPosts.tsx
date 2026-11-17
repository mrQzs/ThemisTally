// 七端岗位（合同第 6 节）：只读六行表——岗位、运行时、模型、思考档位、来源、替补、操作。操作列放两个写入口
// （改绑定… 开表单、恢复缺省… 直接走写流程），逐字句子与表单都在 src/writes/HubBindForm.tsx，入口文件只放按钮。
// hub 信封整个收下：读失败时只这一组显示失败信封与 messages（pre），四个角色卡、profile 表、方案表照常。
// 视图只收数据与回调：从 ../../api 只 import type。字段已在 roles-logic 归一，这里只渲染。
import type { ReactNode } from 'react';
import type { Envelope, HubRolesData, ProfilesData } from '../../api';
import { EffortPair, Table, Tag, type TableColumn } from '../../components';
import { Section } from './common-Section';
import {
  allowedProfiles,
  hubBudgetText,
  hubEffortDiffers,
  hubEffortState,
  hubEffortTriple,
  hubFallbackCandidates,
  hubFallbackExcerpt,
  hubLastTurnMark,
  hubLastTurnText,
  hubMib,
  hubPostName,
  hubTimeoutText,
  normalizeHubPost,
  type HubPostInfo,
  type HubPostLastTurnInfo,
  type HubPostTurnInfo,
} from './roles-logic';
import { useWriteFlow } from '../../writes/useWriteFlow';
import { WriteFlow } from '../../writes/WriteConfirmDialog';
import { HubBindAction, HubUnsetAction } from '../../writes/HubBindForm';
import './roles-hub-turns.css';

const DASH = '—';

interface HubRow {
  rowId: string;
  岗位: ReactNode;
  运行时: string;
  模型: string;
  思考档位: ReactNode;
  来源: ReactNode;
  替补: string;
  时限与工具: string;
  预算: ReactNode;
  最近一回合: ReactNode;
  操作: ReactNode;
}

const COLUMNS: readonly TableColumn<HubRow>[] = [
  { key: '岗位', header: '岗位' },
  { key: '运行时', header: '运行时' },
  { key: '模型', header: '模型', mono: true },
  { key: '思考档位', header: '思考档位' },
  { key: '来源', header: '来源' },
  { key: '替补', header: '替补' },
  { key: '时限与工具', header: '时限与工具' },
  { key: '预算', header: '预算' },
  { key: '最近一回合', header: '最近一回合' },
  { key: '操作', header: '操作' },
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

// 思考档位格：有最近一回合时是三值（要求 · 映射 · 生效，值取自 hubEffortTriple 的三段：label 两字 + 空格 + 值）；
// 没有最近一回合（audit、exec）照旧经 EffortPair，生效未知。生效与要求不同时格末加 warning Tag。
function effortCell(p: HubPostInfo): ReactNode {
  const lastTurn = p.lastTurn;
  if (lastTurn == null) return <EffortPair requested={p.thinking} effective={null} />;
  const parts = hubEffortTriple(lastTurn).split(' · ');
  return (
    <span className="tt-effort" data-state={hubEffortState(lastTurn)}>
      {parts.map((part, i) => (
        <span key={part}>
          {i > 0 ? ' · ' : ''}
          <span className="tt-effort__label">{part.slice(0, 2)}</span>{' '}
          <span className="tt-effort__level">{part.slice(3)}</span>
        </span>
      ))}
      {hubEffortDiffers(lastTurn) && (
        <>
          {' '}
          <Tag tone="warning">与要求不同</Tag>
        </>
      )}
    </span>
  );
}

// 预算格：文字照旧是 hubBudgetText 的整句，只把「入 / 出 / 对象 MiB」那一段包进带 aria-label 的 span
// （读屏念「单次输入 2 MiB、单次回应 8 MiB、单个对象 8 MiB」，屏幕上仍是换算后的数字）。
function budgetCell(turn: HubPostTurnInfo | null): ReactNode {
  const budgets = turn?.budgets ?? null;
  const shown = hubBudgetText(budgets);
  if (budgets == null) return shown;
  const parts = shown.split(' · ');
  const input = hubMib(budgets.max_input_bytes);
  const output = hubMib(budgets.max_response_bytes);
  const object = hubMib(budgets.max_object_bytes);
  return (
    <>
      {parts[0]} · {parts[1]} ·{' '}
      <span aria-label={`单次输入 ${input} MiB、单次回应 ${output} MiB、单个对象 ${object} MiB`}>{parts[2]}</span>
    </>
  );
}

// 最近一回合格：时刻 · 实际载体 · 模型；退回替补或与当前绑定不同时加 Tag；退回的原因文字截断显示，title 给全文。
function lastTurnCell(p: HubPostInfo): ReactNode {
  const lastTurn = p.lastTurn;
  if (lastTurn == null) return hubLastTurnText(null);
  const mark = hubLastTurnMark(lastTurn, p.adapter);
  const excerpt = hubFallbackExcerpt(lastTurn.fallback);
  return (
    <>
      {hubLastTurnText(lastTurn)}
      {mark === '退回替补' && (
        <>
          {' '}
          <Tag tone="warning">退回替补</Tag>
        </>
      )}
      {mark === '与当前绑定不同' && (
        <>
          {' '}
          <Tag tone="neutral">与当前绑定不同</Tag>
        </>
      )}
      {excerpt.shown !== '' && (
        <>
          {' '}
          <span title={excerpt.full}>{excerpt.shown}</span>
        </>
      )}
    </>
  );
}

export interface HubPostsProps {
  hub: Envelope<HubRolesData>;
  profiles?: ProfilesData['profiles'];
  reload?: () => Promise<void>;
}

export function HubPosts({ hub, profiles = [], reload }: HubPostsProps) {
  const { start, flow } = useWriteFlow(reload);
  return (
    <Section title="七端岗位">
      {hub.ok && hub.data ? (
        <>
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
                思考档位: effortCell(p),
                来源: sourceCell(p),
                替补: fallbackText(p.fallback),
                时限与工具: hubTimeoutText(p.turn),
                预算: budgetCell(p.turn),
                最近一回合: lastTurnCell(p),
                操作: (
                  <>
                    <HubBindAction
                      post={p.post}
                      postLabel={hubPostName(p.post)}
                      mainCandidates={allowedProfiles(profiles, p.allowedAdapters)}
                      fallbackCandidatesFor={(id) => hubFallbackCandidates(profiles, p.allowedAdapters, id)}
                      source={p.source}
                      mainProfile={p.profile}
                      fallbackProfile={p.fallback?.profile ?? null}
                      reload={reload}
                    />
                    <HubUnsetAction post={p.post} source={p.source} onStart={start} />
                  </>
                ),
              };
            })}
            rowKey={(r) => r.rowId}
            rowAttrs={(r) => ({ 'data-post': r.rowId })}
          />
          <WriteFlow flow={flow} />
        </>
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
