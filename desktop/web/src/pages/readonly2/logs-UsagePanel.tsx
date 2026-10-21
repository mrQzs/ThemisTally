// 用量页签（合同 D03）：固定说明、执行端卡、规划端卡、按 attempt 表、按模型表。
// 占比条的宽度是运行时算出的百分比，用内联 style（合同「样式取值」：内联 style 只出现在这里）。
import { useId, type ReactNode } from 'react';
import { Card, EmptyState, Table, Tag, type TableColumn, type TagTone } from '../../components';
import type { UsageData } from '../../api';
import { InfoNote } from './common-InfoNote';
import { hrefWithMock } from './common-format';
import { numberText, sharePercent, shareText, usageStatusTone, type UsageAttempt, type UsageLike } from './logs-logic';
import './logs-styles.css';

const FOUR_KEYS: readonly { key: 'input' | 'output' | 'cacheRead' | 'cacheWrite'; label: string }[] = [
  { key: 'input', label: 'input' },
  { key: 'output', label: 'output' },
  { key: 'cacheRead', label: 'cacheRead' },
  { key: 'cacheWrite', label: 'cacheWrite' },
];

const COUNT_KINDS: readonly { key: 'known' | 'partial' | 'unknown'; tone: TagTone; title: string }[] = [
  { key: 'known', tone: 'success', title: '已回报' },
  { key: 'partial', tone: 'warning', title: '部分回报' },
  { key: 'unknown', tone: 'neutral', title: '未回报' },
];

interface AttemptRow {
  key: string;
  task: string;
  attempt: string;
  model: string;
  status: ReactNode;
  input: ReactNode;
  output: ReactNode;
  cacheRead: ReactNode;
  cacheWrite: ReactNode;
  total: ReactNode;
}

const ATTEMPT_COLUMNS: readonly TableColumn<AttemptRow>[] = [
  { key: 'task', header: '任务', mono: true },
  { key: 'attempt', header: 'attempt', mono: true },
  { key: 'model', header: '模型', mono: true },
  { key: 'status', header: '状态' },
  { key: 'input', header: 'input', numeric: true },
  { key: 'output', header: 'output', numeric: true },
  { key: 'cacheRead', header: 'cacheRead', numeric: true },
  { key: 'cacheWrite', header: 'cacheWrite', numeric: true },
  { key: 'total', header: '合计', numeric: true },
];

interface ModelRow {
  key: string;
  model: string;
  counts: string;
  share: ReactNode;
  input: ReactNode;
  output: ReactNode;
  total: ReactNode;
}

const MODEL_COLUMNS: readonly TableColumn<ModelRow>[] = [
  { key: 'model', header: '模型', mono: true },
  { key: 'counts', header: '回报情况' },
  { key: 'share', header: '占比', numeric: true },
  { key: 'input', header: 'input', numeric: true },
  { key: 'output', header: 'output', numeric: true },
  { key: 'total', header: '合计', numeric: true },
];

const text = (v: unknown) => (typeof v === 'string' ? v : '');

function attemptRows(usage: UsageLike): AttemptRow[] {
  return (usage.executor?.attempts ?? []).map((a: UsageAttempt, i: number) => {
    const u = (a.usage ?? null) as Record<string, unknown> | null;
    const status = usageStatusTone(a.status);
    const cell = (v: unknown) => (v === undefined || v === null ? <span className="r2-dim">未知</span> : numberText(v));
    return {
      key: `${text(a.task)}/${text(a.attempt)}/${i}`,
      task: text(a.task),
      attempt: text(a.attempt),
      model: text(a.requested_model),
      status: (
        <Tag tone={status.tone} title={status.title ?? undefined}>
          {text(a.status)}
        </Tag>
      ),
      input: cell(u?.input),
      output: cell(u?.output),
      cacheRead: cell(u?.cacheRead),
      cacheWrite: cell(u?.cacheWrite),
      total: cell(u?.totalTokens),
    };
  });
}

function modelRows(usage: UsageLike): ModelRow[] {
  const total = usage.executor?.totals?.totalTokens;
  return (usage.executor?.by_model ?? []).map((m, i) => {
    const u = (m.usage ?? null) as Record<string, unknown> | null;
    const pct = sharePercent(u?.totalTokens, total);
    return {
      key: `${text(m.requested_model)}/${i}`,
      model: text(m.requested_model),
      counts: `known ${numberText(m.known)} · partial ${numberText(m.partial)} · unknown ${numberText(m.unknown)}`,
      share: (
        <div className="r2-share">
          <div className="r2-share__track" aria-hidden="true">
            <div className="r2-share__fill" style={{ width: `${pct ?? 0}%` }} />
          </div>
          <span className="r2-share__pct tt-num">{shareText(u?.totalTokens, total)}</span>
        </div>
      ),
      input: u?.input === undefined || u?.input === null ? <span className="r2-dim">未知</span> : numberText(u.input),
      output: u?.output === undefined || u?.output === null ? <span className="r2-dim">未知</span> : numberText(u.output),
      total: u?.totalTokens === undefined || u?.totalTokens === null ? <span className="r2-dim">未知</span> : numberText(u.totalTokens),
    };
  });
}

export function UsagePanel({ usage }: { usage: UsageData }) {
  const attemptsId = useId();
  const modelsId = useId();
  const like = usage as UsageLike;
  const totals = like.executor?.totals ?? {};
  const counts = like.executor?.counts ?? {};
  const skippedLinks = like.executor?.skipped_links;
  const attempts = attemptRows(like);
  const models = modelRows(like);

  return (
    <div className="r2-stack">
      <InfoNote>合计是下界：没有回报的记为未知，不计为 0。</InfoNote>
      <Card title="执行端（Pi）">
        <div className="r2-usage__total">
          <span className="r2-usage__total-num tt-num">{numberText(totals.totalTokens)}</span>
          <span className="r2-usage__total-unit">token（下界）</span>
        </div>
        <ul className="r2-usage__items">
          {FOUR_KEYS.map((k) => (
            <li key={k.key}>
              <span className="r2-usage__key">{k.label}</span>
              {' '}
              <span className="tt-num">{numberText(totals[k.key])}</span>
            </li>
          ))}
        </ul>
        <div className="r2-usage__counts">
          {COUNT_KINDS.map((c) => (
            <Tag key={c.key} tone={c.tone} title={c.title}>
              {c.key} <span className="tt-num">{numberText(counts[c.key])}</span>
            </Tag>
          ))}
        </div>
        {typeof skippedLinks === 'number' && skippedLinks > 0 && (
          <p className="r2-usage__skipped r2-dim">跳过的链接：<span className="tt-num">{numberText(skippedLinks)}</span></p>
        )}
      </Card>
      <Card title="规划端">
        {like.planner == null ? (
          <EmptyState
            title="在设置里指定会话记录目录后统计"
            description="目录在设置里用系统对话框选择，保存后外壳重启本机服务，新目录才生效。"
            action={
              <a className="r2-link" href={hrefWithMock('/settings')}>
                去设置
              </a>
            }
          />
        ) : (
          <p className="r2-dim">规划端用量的显示在后续片接入</p>
        )}
      </Card>
      <section className="r2-card" aria-labelledby={attemptsId}>
        <h2 id={attemptsId} className="r2-usage__heading">按 attempt · 执行端</h2>
        {attempts.length === 0 ? (
          <p className="r2-dim">还没有执行端的用量记录</p>
        ) : (
          <Table
            className="r2-usage__attempts"
            columns={ATTEMPT_COLUMNS}
            rows={attempts}
            rowKey={(r) => r.key}
            rowHeight={40}
            aria-label="按 attempt 的用量"
          />
        )}
      </section>
      <section className="r2-card" aria-labelledby={modelsId}>
        <h2 id={modelsId} className="r2-usage__heading">按模型</h2>
        {models.length === 0 ? (
          <p className="r2-dim">还没有按模型的统计</p>
        ) : (
          <Table
            className="r2-usage__models"
            columns={MODEL_COLUMNS}
            rows={models}
            rowKey={(r) => r.key}
            rowHeight={40}
            aria-label="按模型的用量"
          />
        )}
      </section>
    </div>
  );
}
