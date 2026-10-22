// 总览 attempt 行列表（合同第 4 节）：需要你判断、运行中、待集成三块共用。四列 状态标签/名称/信息/链接。
// 行列表 ul/li；运行中写已用与工具调用并带 long_idle 标签与 data-long-idle；需要你判断与待集成写用时与检查。
// 底部可接 NextStep 与复制结果。
import { useState } from 'react';
import type { StatusRow } from '../../api';
import { ChevronRightIcon, TriangleAlertIcon } from '../../icons';
import { NextStep, StatusTag, Tag } from '../../components';
import { Section } from './common-Section';
import { CopyNote } from './common-CopyNote';
import { copyText, type CopyResult } from '../../components';
import { evidencePath, eventsPath, navHandler } from './common-links';
import { checksInfo, idleDeltas, liveElapsed, longIdle, rowName, toolCalls } from './overview-logic';

type LinkKind = 'evidence' | 'events';
type InfoKind = 'checks' | 'live';

interface RowProps {
  row: StatusRow;
  linkKind: LinkKind;
  infoKind: InfoKind;
  navigate: (path: string) => void;
}

function AttemptRow({ row, linkKind, infoKind, navigate }: RowProps) {
  const path = linkKind === 'events' ? eventsPath(row.task_id, row.attempt) : evidencePath(row.task_id, row.attempt);
  const linkLabel = linkKind === 'events' ? '跟随事件' : '查看证据';
  const idle = infoKind === 'live' && longIdle(row);
  const deltas = idleDeltas(row);
  const elapsed = liveElapsed(row);
  return (
    <li className="ov-row" data-long-idle={idle ? 'true' : undefined}>
      <StatusTag state={row.state} size="md" />
      <div className="ov-row__main">
        <span className="ov-row__name">{rowName(row)}</span>
        {idle && (
          <Tag tone="warning">
            <TriangleAlertIcon width={12} height={12} />
            长时间没有工具调用
            {deltas != null ? <>（<span className="tt-num">{deltas}</span> 个增量）</> : null}
          </Tag>
        )}
      </div>
      <div className="ov-row__info">
        {infoKind === 'checks' ? (
          checksInfo(row)
        ) : (
          <>
            <span>已用 {elapsed ?? ''}</span>
            <span>工具调用 {toolCalls(row)} 次</span>
          </>
        )}
      </div>
      <a className="ov-row__link" href={`#${path}`} onClick={navHandler(navigate, path)}>
        {linkLabel}
        <ChevronRightIcon width={14} height={14} />
      </a>
    </li>
  );
}

export interface AttemptListProps {
  title: string;
  rows: StatusRow[];
  linkKind: LinkKind;
  infoKind: InfoKind;
  /** 计数胶囊数字（需要你判断）。 */
  pill?: number;
  /** 左边框强调（需要你判断）。 */
  accentBorder?: boolean;
  next?: { text: string; command: string | null };
  navigate: (path: string) => void;
}

export function AttemptList({ title, rows, linkKind, infoKind, pill, accentBorder, next, navigate }: AttemptListProps) {
  const [copyResult, setCopyResult] = useState<CopyResult | null>(null);
  const handleCopy = async (text: string) => {
    setCopyResult(await copyText(text));
  };
  return (
    <Section
      title={title}
      className={accentBorder ? 'ov-judge' : undefined}
      afterTitle={
        pill != null ? (
          <span className="ov-pill tt-num" aria-label={`${pill} 项`}>
            {pill}
          </span>
        ) : undefined
      }
    >
      <ul className="ov-rows">
        {rows.map((row) => (
          <AttemptRow key={row.attempt} row={row} linkKind={linkKind} infoKind={infoKind} navigate={navigate} />
        ))}
      </ul>
      {next && (
        <div className="ov-foot">
          {next.command ? (
            <NextStep command={next.command} onCopy={handleCopy}>
              {next.text}
            </NextStep>
          ) : (
            <NextStep>{next.text}</NextStep>
          )}
          <CopyNote result={copyResult} />
        </div>
      )}
    </Section>
  );
}
