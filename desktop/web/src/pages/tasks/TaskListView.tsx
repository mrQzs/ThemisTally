// 任务列表视图（合同第 2 节）：左栏搜索、五颗分组胶囊与任务列表，右栏 attempt 表、下一步与复制结果。
// 只收数据与回调，不调 api.ts；分组只来自 attemptGroups（groupOfState）。
import { useId, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from 'react';
import { Breadcrumb, Table, StatusTag, NextStep, EffortPair, type TableColumn } from '../../components';
import { SearchIcon, CheckIcon } from '../../icons';
import type { StatusRow } from '../../api';
import { CopyNote } from './common-CopyNote';
import { GROUP_LABELS, ATTEMPT_GROUPS, type AttemptGroup } from './tasks-groups';
import {
  attemptsOf,
  attemptSeg,
  buildTasks,
  checksText,
  countTasksByGroup,
  durationText,
  filterTasks,
  groupOfLatest,
  nextStepOf,
  taskRow,
  type TaskEntry,
  type TaskRow,
} from './tasks-model';
import { formatThousands } from './tasks-format';
import { crumbHandler, hrefWithMock } from './tasks-route';
import { copyText, type CopyResult } from './tasks-copy';
import './tasks-list.css';

/** attempt 表的一行：列值是已经算好的文字或节点。 */
interface AttemptRow {
  attempt: string;
  version: string;
  state: ReactNode;
  duration: string;
  checks: string;
  verdict: ReactNode;
  failure: string;
  violations: ReactNode;
  tokens: string;
  cost: ReactNode;
  effort: ReactNode;
}

const COLUMNS: readonly TableColumn<AttemptRow>[] = [
  { key: 'attempt', header: 'attempt', mono: true },
  { key: 'version', header: '版本' },
  { key: 'state', header: '状态' },
  { key: 'duration', header: '用时' },
  { key: 'checks', header: '检查' },
  { key: 'verdict', header: '结论' },
  { key: 'failure', header: '失败分类', mono: true },
  { key: 'violations', header: '越界', numeric: true },
  { key: 'tokens', header: 'token', numeric: true },
  { key: 'cost', header: '费用' },
  { key: 'effort', header: '思考档位' },
];

function toAttemptRow(row: TaskRow): AttemptRow {
  const verdict = typeof row.verdict === 'string' && row.verdict !== '' ? row.verdict : null;
  const failure = typeof row.failure_class === 'string' && row.failure_class !== '' ? row.failure_class : '—';
  const violations = typeof row.violations === 'number' ? row.violations : null;
  const cost = typeof row.cost === 'string' && row.cost !== '' ? row.cost : null;
  // 思考档位：行里没有 effort_requested 字段时写「未知」，有这个字段时交给 EffortPair。
  const hasEffort = Object.prototype.hasOwnProperty.call(row, 'effort_requested');
  return {
    attempt: attemptSeg(row.attempt),
    version: typeof row.plan_version === 'number' ? `v${row.plan_version}` : '—',
    state: <StatusTag state={row.state} size="md" />,
    duration: durationText(row),
    checks: checksText(row),
    verdict: verdict == null ? '—' : <StatusTag state={verdict} size="sm" />,
    failure,
    violations:
      violations == null ? '—' : violations > 0 ? <span className="tasks-list__danger">{violations}</span> : String(violations),
    tokens: typeof row.tokens === 'number' ? formatThousands(row.tokens) : '未知',
    cost: cost == null ? <span className="tasks-list__muted">未知</span> : cost,
    effort: hasEffort ? (
      <EffortPair requested={row.effort_requested} effective={row.effort_effective} />
    ) : (
      '未知'
    ),
  };
}

export interface TaskListViewProps {
  rows: readonly StatusRow[];
  /** 地址里选中的任务（可为空或不在筛选结果里）。 */
  selectedTask: string | null;
  /** 按下的分组。 */
  groups: readonly AttemptGroup[];
  /** 选中任务、切胶囊都只改地址，不重挂载。 */
  onSelectTask: (task: string) => void;
  onGroupsChange: (groups: AttemptGroup[]) => void;
  /** 跨视图跳详情。 */
  onOpenAttempt: (task: string, attempt: string) => void;
  /** 当前 ?mock= 值（面包屑与跨视图链接只带它）。 */
  mock: string;
  /** 跨视图跳转（K16）。 */
  navigate: (path: string) => void;
}

export function TaskListView({
  rows,
  selectedTask,
  groups,
  onSelectTask,
  onGroupsChange,
  onOpenAttempt,
  mock,
  navigate,
}: TaskListViewProps) {
  const searchId = useId();
  const [query, setQuery] = useState('');
  const [copy, setCopy] = useState<CopyResult | null>(null);

  const all = buildTasks(rows);
  // 筛选：按下胶囊时只留最新 attempt 在该组的任务；一颗都没按下时不过滤（PREPARED 与未知状态只在不过滤时显示）。
  const pressedSet = new Set<AttemptGroup>(groups);
  const byGroup = pressedSet.size === 0
    ? all
    : all.filter((entry) => {
        const g = groupOfLatest(entry);
        return g != null && pressedSet.has(g);
      });
  const entries = filterTasks(byGroup, query);
  const counts = countTasksByGroup(all);
  const pressed = new Set<AttemptGroup>(groups);
  // 选中哪一个：地址里的任务在筛选结果里就选它，否则选筛选结果的第一个；不改写地址。
  const selected: TaskEntry | null = entries.find((e) => e.task_id === selectedTask) ?? entries[0] ?? null;

  const onItemKeyDown = (event: KeyboardEvent<HTMLLIElement>, index: number) => {
    const n = entries.length;
    let next = -1;
    if (event.key === 'ArrowDown') next = Math.min(n - 1, index + 1);
    else if (event.key === 'ArrowUp') next = Math.max(0, index - 1);
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = n - 1;
    if (next < 0 || next >= n || next === index) return;
    event.preventDefault();
    const entry = entries[next];
    if (entry) onSelectTask(entry.task_id);
  };

  const onCapsule = (group: AttemptGroup) => (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const next = pressed.has(group) ? groups.filter((g) => g !== group) : [...groups, group];
    onGroupsChange(ATTEMPT_GROUPS.filter((g) => next.includes(g)));
  };

  const next = selected == null
    ? null
    : nextStepOf(selected.latest.state, selected.task_id, attemptSeg(selected.latest.attempt));
  const onCopy = (text: string) => {
    void copyText(text).then(setCopy);
  };

  return (
    <div className="tasks-list" data-page="tasks">
      {selectedTask != null && selectedTask !== '' && (
        <div className="tasks-list__crumb" onClick={crumbHandler(navigate)}>
          <Breadcrumb
            items={[
              { label: '任务', href: hrefWithMock('/tasks', mock) },
              { label: selectedTask },
            ]}
          />
        </div>
      )}
      <div className="tasks-list__cols tt-stack-narrow">
        <section className="tasks-list__left" aria-label="任务列表">
          <div className="tasks-list__head">
            <div className="tasks-list__search">
              <SearchIcon width={16} height={16} className="tasks-list__search-icon" />
              <label className="tasks-list__search-label" htmlFor={searchId}>搜索任务</label>
              <input
                id={searchId}
                className="tasks-list__search-input"
                type="search"
                placeholder="搜索任务…"
                aria-label="搜索任务"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <div className="tasks-list__chips" role="group" aria-label="按状态分组筛选">
              {ATTEMPT_GROUPS.map((group) => {
                const on = pressed.has(group);
                return (
                  <button
                    key={group}
                    type="button"
                    className="tasks-list__chip"
                    data-group={group}
                    aria-pressed={on}
                    onClick={onCapsule(group)}
                  >
                    {on && <CheckIcon width={14} height={14} />}
                    <span className="tasks-list__chip-label">{GROUP_LABELS[group]}</span>
                    <span className="tasks-list__chip-num tt-num">{counts[group]}</span>
                  </button>
                );
              })}
            </div>
          </div>
          {entries.length === 0 ? (
            <p className="tasks-list__none">没有符合条件的任务</p>
          ) : (
            <ul className="tasks-list__items" role="listbox" aria-label="任务">
              {entries.map((entry, i) => {
                const isSel = selected != null && entry.task_id === selected.task_id;
                return (
                  <li
                    key={entry.task_id}
                    className="tasks-list__item"
                    role="option"
                    aria-selected={isSel}
                    tabIndex={isSel ? 0 : -1}
                    onClick={() => onSelectTask(entry.task_id)}
                    onKeyDown={(e) => onItemKeyDown(e, i)}
                  >
                    <span className="tasks-list__item-main">
                      <span className="tasks-list__item-id">{entry.task_id}</span>{' '}
                      <span className="tasks-list__item-seg">{attemptSeg(entry.latest.attempt)}</span>
                    </span>
                    <StatusTag state={entry.latest.state} size="sm" />
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        {selected != null && (
          <section className="tasks-list__right">
            <div className="tasks-list__right-head">
              <h2 className="tasks-list__right-title">{selected.task_id}</h2>
              <span className="tasks-list__right-count">{selected.rows.length} 个 attempt</span>
            </div>
            <div className="tasks-list__table">
              <Table<AttemptRow>
                className="tasks-list__table-wrap"
                aria-label={`${selected.task_id} 的 attempt`}
                columns={COLUMNS}
                rows={attemptsOf(selected).map(toAttemptRow)}
                rowKey={(row) => row.attempt}
                rowHeight={40}
                onRowOpen={(attempt) => onOpenAttempt(selected.task_id, attempt)}
              />
            </div>
            <div className="tasks-list__next">
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
            <p className="tasks-list__foot">费用为空时显示「未知」；越界大于 0 时标红。</p>
          </section>
        )}
      </div>
    </div>
  );
}
