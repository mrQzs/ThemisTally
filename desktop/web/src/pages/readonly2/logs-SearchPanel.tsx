// 检索页签（合同 D02）：一个表单（检索词、任务、最多条数）加 [检索]；两条校验不通过时不调读取函数；
// 只认最后一次请求，卸载后不写状态。
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Button, Select, TextField } from '../../components';
import type { Envelope, UsageData } from '../../api';
import type { SearchData } from '../../mock/readonly2-search';
import { taskOptions } from './logs-logic';
import { SearchResults, type SearchState } from './logs-SearchResults';
import './logs-styles.css';

export type SearchLogsReader = (q: string, task: string | null, max: number) => Promise<Envelope<SearchData>>;

const EMPTY_Q = '先输入要检索的内容';
const BAD_MAX = '最多条数必须是不小于 1 的整数';

function parseMax(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  if (!Number.isInteger(n) || n < 1) return null;
  return n;
}

export function SearchPanel({ usage, searchLogs }: { usage: UsageData; searchLogs: SearchLogsReader }) {
  const [q, setQ] = useState('');
  const [task, setTask] = useState('');
  const [max, setMax] = useState('50');
  const [qError, setQError] = useState<string | undefined>(undefined);
  const [maxError, setMaxError] = useState<string | undefined>(undefined);
  const [pending, setPending] = useState(false);
  const [state, setState] = useState<SearchState>({ kind: 'idle' });
  const reqRef = useRef(0);
  const mountedRef = useRef(true);

  // 卸载后不再写状态。
  useEffect(() => () => {
    mountedRef.current = false;
  }, []);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = q.trim();
    const maxValue = parseMax(max);
    const qBad = !trimmed;
    const maxBad = maxValue === null;
    setQError(qBad ? EMPTY_Q : undefined);
    setMaxError(maxBad ? BAD_MAX : undefined);
    if (qBad || maxBad || maxValue === null) return;
    const my = (reqRef.current += 1);
    setPending(true);
    searchLogs(trimmed, task || null, maxValue)
      .then((env) => {
        if (!mountedRef.current || my !== reqRef.current) return;
        setPending(false);
        if (env.ok && env.data) {
          setState({ kind: 'ok', q: trimmed, max: maxValue, data: env.data });
        } else {
          setState({ kind: 'error', command: env.command, exit_code: env.exit_code, messages: env.messages });
        }
      })
      .catch(() => {
        if (!mountedRef.current || my !== reqRef.current) return;
        setPending(false);
        setState({ kind: 'error', command: [], exit_code: 2, messages: [] });
      });
  };

  return (
    <div className="r2-search">
      <form className="r2-search__form" onSubmit={onSubmit}>
        <TextField
          className="r2-search__q"
          label="检索"
          help="Python 正则表达式"
          mono
          type="search"
          placeholder="例如 logs[_ ]cat"
          value={q}
          error={qError}
          onChange={(e) => setQ(e.target.value)}
        />
        <Select
          className="r2-search__task"
          label="任务"
          options={taskOptions(usage)}
          value={task}
          onChange={(e) => setTask(e.target.value)}
        />
        <TextField
          className="r2-search__max"
          label="最多条数"
          type="number"
          min={1}
          value={max}
          error={maxError}
          onChange={(e) => setMax(e.target.value)}
        />
        <Button type="submit" variant="primary" loading={pending} loadingText="正在检索…">
          检索
        </Button>
      </form>
      <SearchResults state={state} />
    </div>
  );
}
