// attempt 详情视图（合同第 3、4 节）：面包屑、页头（状态标签、思考档位、元信息 dl）、下一步与六个页签。
// 只收数据与回调，不调 api.ts；取数在 TasksPage 里经 loadAttemptDetail 并行完成。
import { Breadcrumb, EffortPair, NextStep, StatusTag, Tabs, type TabItem } from '../../components';
import type { AttemptData, Envelope, StatusRow } from '../../api';
import { CopyNote } from '../../components/CopyNote';
import type { ReadFailure } from './common-FileReader';
import { TabSummary } from './tab-Summary';
import { TabPatch } from './tab-Patch';
import { TabChecks } from './tab-Checks';
import { TabReport } from './tab-Report';
import { TabEvents } from './tab-Events';
import { TabFiles } from './tab-Files';
import { checksSummary, nextStepOf, taskRow } from './tasks-model';
import { formatDuration, formatLocalTime, formatThousands } from './tasks-format';
import { crumbHandler, hrefWithMock, TASK_TABS, type TaskTabId } from './tasks-route';
import { copyText, type CopyResult } from '../../components';
import { useState } from 'react';
import './tasks-detail.css';

const TAB_ITEMS: readonly TabItem[] = [
  { id: 'summary', label: '摘要' },
  { id: 'patch', label: '补丁' },
  { id: 'checks', label: '检查' },
  { id: 'report', label: '执行报告' },
  { id: 'events', label: '事件' },
  { id: 'files', label: '全部文件' },
];

const DASH = '—';

function orDash(value: string | null): string {
  return value == null || value === '' ? DASH : value;
}

export interface AttemptDetailViewProps {
  task: string;
  attempt: string;
  /** status 里的行；?mock=empty 或不在 status 里时为 null。 */
  row: StatusRow | null;
  /** logs show 的信封；读不到时 ok 为假。 */
  attemptEnv: Envelope<AttemptData> | null;
  tab: TaskTabId;
  onTabChange: (tab: TaskTabId) => void;
  mock: string;
  navigate: (path: string) => void;
}

export function AttemptDetailView({
  task, attempt, row, attemptEnv, tab, onTabChange, mock, navigate,
}: AttemptDetailViewProps) {
  const [copy, setCopy] = useState<CopyResult | null>(null);
  const onCopy = (text: string) => {
    void copyText(text).then(setCopy);
  };
  const loose = row == null ? null : taskRow(row);
  const detail = attemptEnv != null ? attemptEnv.data : null;
  // 状态：logs show 的 state 优先（它是这一份 attempt 的权威读数），取不到时用 status 行里的。
  const state = detail != null && detail.state !== '' ? detail.state : loose != null ? loose.state : '';
  const evidence = detail != null ? detail.evidence : [];
  const skippedLinks = detail != null && typeof detail.skipped_links === 'number' ? detail.skipped_links : 0;
  // logs show 读不到（status 里却有这一行）：页头照常，摘要、检查、全部文件三个页签显示行内出错块。
  const attemptFailure: ReadFailure | null =
    attemptEnv != null && !attemptEnv.ok
      ? { command: attemptEnv.command, exit_code: attemptEnv.exit_code, messages: attemptEnv.messages }
      : null;

  // 页头第一行：状态标签与思考档位；行里没有 effort_requested 字段时写「未知」。
  const hasEffort = loose != null && Object.prototype.hasOwnProperty.call(loose, 'effort_requested');
  const stateAt = detail != null ? detail.state_at : undefined;
  const local = formatLocalTime(stateAt ?? null);

  const version = loose != null && typeof loose.plan_version === 'number' ? `v${loose.plan_version}` : null;
  const duration = loose == null ? null : formatDuration(loose.wall_seconds);
  const tokens = loose == null ? DASH : formatThousands(loose.tokens);
  const cost =
    loose == null
      ? DASH
      : typeof loose.cost === 'string' && loose.cost !== ''
        ? loose.cost
        : loose.cost_status === 'unknown'
          ? '未知（只报 token）'
          : DASH;
  const violations = loose != null && typeof loose.violations === 'number' ? String(loose.violations) : null;
  const checks = checksSummary(loose);
  const next = nextStepOf(state, task, attempt);

  return (
    <div className="tasks-detail" data-page="detail">
      <div className="tasks-detail__crumb" onClick={crumbHandler(navigate)}>
        <Breadcrumb
          items={[
            { label: '任务', href: hrefWithMock('/tasks', mock) },
            { label: task, href: hrefWithMock(`/tasks/${encodeURIComponent(task)}`, mock) },
            { label: attempt },
          ]}
        />
      </div>
      <div className="tasks-detail__head">
        {state !== '' && <StatusTag state={state} size="md" />}
        {hasEffort ? (
          <EffortPair requested={loose!.effort_requested} effective={loose!.effort_effective} />
        ) : (
          <span className="tasks-detail__head-note">思考档位 未知</span>
        )}
      </div>
      <dl className="tasks-detail__meta">
        <div className="tasks-detail__meta-item">
          <dt>版本</dt>
          <dd>{orDash(version)}</dd>
        </div>
        <div className="tasks-detail__meta-item">
          <dt>状态时间</dt>
          <dd title={stateAt ?? undefined}>{orDash(local)}</dd>
        </div>
        <div className="tasks-detail__meta-item">
          <dt>用时</dt>
          <dd>{orDash(duration)}</dd>
        </div>
        <div className="tasks-detail__meta-item">
          <dt>token</dt>
          <dd>{tokens}</dd>
        </div>
        <div className="tasks-detail__meta-item">
          <dt>费用</dt>
          <dd>{cost}</dd>
        </div>
        <div className="tasks-detail__meta-item">
          <dt>检查</dt>
          <dd>{checks}</dd>
        </div>
        <div className="tasks-detail__meta-item">
          <dt>越界</dt>
          <dd>{orDash(violations)}</dd>
        </div>
      </dl>
      <div className="tasks-detail__next">
        {next != null &&
          (next.command == null ? (
            <NextStep title="下一步">{next.text}</NextStep>
          ) : (
            <NextStep title="下一步" command={next.command} onCopy={onCopy}>
              {next.text}
            </NextStep>
          ))}
        <CopyNote result={copy} />
      </div>
      <div className="tasks-detail__tabs">
        <Tabs
          items={TAB_ITEMS.map((it) => ({ ...it }))}
          value={tab}
          onChange={(id) => onTabChange(id as TaskTabId)}
          aria-label="证据"
        >
          {tab === 'summary' && <TabSummary task={task} attempt={attempt} attemptEnv={attemptEnv} />}
          {tab === 'patch' && <TabPatch task={task} attempt={attempt} />}
          {tab === 'checks' && <TabChecks task={task} attempt={attempt} row={row} evidence={evidence} attemptFailure={attemptFailure} />}
          {tab === 'report' && <TabReport task={task} attempt={attempt} />}
          {tab === 'events' && <TabEvents task={task} attempt={attempt} state={state} />}
          {tab === 'files' && <TabFiles task={task} attempt={attempt} evidence={evidence} skippedLinks={skippedLinks} attemptFailure={attemptFailure} />}
        </Tabs>
      </div>
    </div>
  );
}

export { TASK_TABS };
