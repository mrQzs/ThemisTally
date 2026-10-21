// 角色卡（合同第 5 节）：article 加 data-role 与 aria-labelledby 指 h3；四种模式各自的标签、键值(dl)与说明；
// 思考档位一律经 EffortPair；底部 [更改…] 禁用。字段已在 roles-logic 归一，这里只渲染。
import { useId } from 'react';
import { CircleCheckIcon, TriangleAlertIcon } from '../../icons';
import { EffortPair, Tag } from '../../components';
import { DisabledAction } from '../../shell/DisabledAction';
import { modeName, resolvedProfile, roleName, type RoleInfo } from './roles-logic';

export interface RoleCardProps {
  role: RoleInfo;
  activePreset: string;
}

export function RoleCard({ role, activePreset }: RoleCardProps) {
  const titleId = useId();
  const mode = role.mode;
  const headless = mode === 'headless';
  return (
    <article className="rl-card" data-role={role.role} aria-labelledby={titleId}>
      <div className="rl-card__head">
        <h3 className="rl-card__title" id={titleId}>
          {roleName(role.role)}
        </h3>
        <div className="rl-card__tags">
          <Tag tone="neutral">{modeName(mode)}</Tag>
          {!role.explicit && <Tag tone="neutral">默认</Tag>}
          {role.differs && <Tag tone="attention">与方案 {activePreset} 不一致</Tag>}
          {headless && role.connected && (
            <Tag tone="success">
              <CircleCheckIcon width={12} height={12} />
              已接通
            </Tag>
          )}
          {headless && !role.connected && (
            <Tag tone="warning">
              <TriangleAlertIcon width={12} height={12} />
              本轮未接通
            </Tag>
          )}
        </div>
      </div>
      <dl className="rl-kv">
        {headless && (
          <>
            <dt>profile</dt>
            <dd>{resolvedProfile(role) ?? '—'}</dd>
          </>
        )}
        {mode === 'interactive_host' && (
          <>
            <dt>宿主</dt>
            <dd>{role.host ?? '—'}</dd>
          </>
        )}
        {headless && (
          <>
            <dt>runtime</dt>
            <dd>
              {role.runtime ?? '—'}（{role.adapter ?? '—'}）
            </dd>
            <dt>模型</dt>
            <dd>
              {role.provider ?? '—'}/{role.model ?? '—'}
            </dd>
          </>
        )}
        <dt>思考档位</dt>
        <dd>
          <EffortPair
            requested={headless ? role.thinking : null}
            effective={headless ? role.effortEffective : null}
          />
        </dd>
      </dl>
      {mode === 'interactive_host' && <p className="rl-card__note">模型由宿主决定，Themis 不切换。</p>}
      {mode === 'manual' && <p className="rl-card__note">规划端亲自写合同</p>}
      {mode === 'disabled' && <p className="rl-card__note">本轮没有实现</p>}
      <div className="rl-card__foot">
        <DisabledAction label="更改…" variant="secondary" size="sm" />
      </div>
    </article>
  );
}
