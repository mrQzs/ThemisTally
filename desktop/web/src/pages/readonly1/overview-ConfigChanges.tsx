// 总览「最近的配置变更」（合同第 4 节）：history 信封整个收下；ok 且 entries 非空按 number 倒序取前 5，
// 空显示「还没有配置历史」，出错显示命令与退出码加 messages（pre 纯文本）；头部「查看全部历史」始终渲染。
import type { Envelope, HistoryData } from '../../api';
import { TriangleAlertIcon } from '../../icons';
import { Tag } from '../../components';
import { RelativeTime } from '../../components/RelativeTime';
import { ActorTag } from '../../components/ActorTag';
import { Section } from './common-Section';
import { HISTORY_PATH, navHandler } from './common-links';
import { actionLabel, topChanges } from './overview-logic';

export interface ConfigChangesProps {
  history: Envelope<HistoryData>;
  navigate: (path: string) => void;
}

export function ConfigChanges({ history, navigate }: ConfigChangesProps) {
  return (
    <Section
      title="最近的配置变更"
      action={
        <a className="common-section__link" href={`#${HISTORY_PATH}`} onClick={navHandler(navigate, HISTORY_PATH)}>
          查看全部历史
        </a>
      }
    >
      {history.ok && history.data ? (
        history.data.entries.length === 0 ? (
          <p className="ov-note">还没有配置历史</p>
        ) : (
          <ul className="ov-changes">
            {topChanges(history.data).map((e) => (
              <li className="ov-change" key={e.number}>
                <span className="ov-change__no tt-num">#{e.number}</span>{' '}
                <RelativeTime iso={e.at} className="ov-change__time" />{' '}
                <span className="ov-change__action" title={actionLabel(e.action) ?? undefined}>
                  {e.action}
                </span>{' '}
                <span className="ov-change__target">{e.target}</span>{' '}
                <span className="ov-change__tags">
                  {(e.external_changes ?? 0) > 0 && (
                    <Tag tone="warning">
                      <TriangleAlertIcon width={12} height={12} />
                      检测到外部改动
                    </Tag>
                  )}
                  <ActorTag actor={e.actor} />
                </span>
              </li>
            ))}
          </ul>
        )
      ) : (
        <div className="ov-change-err">
          <p className="ov-note">
            没能读到配置历史：命令 {history.command.join(' ')} 返回退出码 {history.exit_code}。
          </p>
          <pre className="ov-change-msg">{history.messages.join('\n')}</pre>
        </div>
      )}
    </Section>
  );
}
