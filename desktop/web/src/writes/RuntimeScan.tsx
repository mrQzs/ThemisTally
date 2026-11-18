// 运行时页页头 [扫描 PATH] 入口与扫描对话框（T054）：点入口起一个 runtime-scan 作业，对话框里用作业进度卡
// 显示进度与结果；找到且还没同名 runtime 的适配器给 [登记…]（走既有 runtime.add 的预览 → 确认 → 执行 → 重读）。
// 内外两层照 T053：外层只放入口按钮与写流程，对话框只在打开时挂载；逐字文案都放在本文件（入口文件不写）。
import { useEffect, useState, type ReactNode } from 'react';
import { Button, Dialog } from '../components';
import { SearchIcon } from '../icons';
import { getRuntimes, type Envelope, type JobView } from '../api';
import { cancelJob, ensureJob, restartJob, useJob } from '../jobs/jobStore';
import { JobCard } from '../jobs/JobCard';
import { useWriteFlow, type WriteSpec } from './useWriteFlow';
import { WriteFlow } from './WriteConfirmDialog';
// 样式表接线：放在组件 import 之后（照仓库里组件带自己的样式表的写法）。
import './runtime-scan.css';

// 扫描结果一行（服务的 found[] 里前端要用的三列）。
interface ScanFound {
  adapter: string;
  path: string | null;
  version: string | null;
}

// 服务信封的 data.found → 前端行：缺键或类型不对的项跳过（按服务给的次序，五个适配器各一行）。
function parseFound(data: unknown): ScanFound[] {
  if (typeof data !== 'object' || data === null) return [];
  const found = (data as Record<string, unknown>).found;
  if (!Array.isArray(found)) return [];
  const rows: ScanFound[] = [];
  for (const item of found) {
    if (typeof item !== 'object' || item === null) continue;
    const row = item as Record<string, unknown>;
    if (typeof row.adapter !== 'string') continue;
    rows.push({
      adapter: row.adapter,
      path: typeof row.path === 'string' ? row.path : null,
      version: typeof row.version === 'string' ? row.version : null,
    });
  }
  return rows;
}

// 结果表一行的操作列：没找到（路径空）→ 空；读不出已登记表 → 空（不给登记…）；已登记 → 「已登记」；否则 → [登记…]。
function operationCell(row: ScanFound, registered: Set<string> | null, onRegister: (adapter: string) => void): ReactNode {
  if (row.path == null) return null;
  if (registered == null) return null;
  if (registered.has(row.adapter)) return <span className="rs-registered">已登记</span>;
  return (
    <Button variant="secondary" size="sm" onClick={() => onRegister(row.adapter)}>登记…</Button>
  );
}

function ScanResult({
  registered,
  readFailed,
  envelope,
  onRegister,
}: {
  registered: Set<string> | null;
  readFailed: boolean;
  envelope: Envelope<unknown> | null;
  onRegister: (adapter: string) => void;
}) {
  const found = parseFound(envelope?.data);
  return (
    <div className="rs-result">
      {readFailed && <p className="rs-readfail">读不出已登记的 runtime，暂时不能登记</p>}
      <table className="rs-table">
        <thead>
          <tr>
            <th>适配器</th>
            <th>路径</th>
            <th>版本</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {found.map((row) => (
            <tr key={row.adapter}>
              <td>{row.adapter}</td>
              <td className="rs-mono">{row.path ?? '—'}</td>
              <td>{row.version ?? '—'}</td>
              <td>{operationCell(row, registered, onRegister)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// 内层对话框：只在打开时挂载。打开时读一次 getRuntimes 判断哪些已登记；body 放作业卡，脚注放 [重新扫描] 与 [关闭]。
function RuntimeScanDialog({ onClose, onRegister }: { onClose: () => void; onRegister: (adapter: string) => void }) {
  const { job, elapsedSeconds, createError } = useJob('runtime-scan');
  // registered：已登记运行时的 id 集合；null 表示还没读到或读不出。readFailed：getRuntimes 读失败。
  const [registered, setRegistered] = useState<Set<string> | null>(null);
  const [readFailed, setReadFailed] = useState(false);

  useEffect(() => {
    let on = true;
    getRuntimes().then((env) => {
      if (!on) return;
      if (env.ok && env.data) {
        setRegistered(new Set(env.data.runtimes.map((r) => r.id)));
        setReadFailed(false);
      } else {
        setRegistered(null);
        setReadFailed(true);
      }
    });
    return () => {
      on = false;
    };
  }, []);

  const terminal = job != null && (job.state === 'succeeded' || job.state === 'failed' || job.state === 'cancelled' || job.state === 'timed_out');
  const rescanDisabled = !(terminal || createError != null);

  return (
    <Dialog
      open
      onClose={onClose}
      title="扫描 PATH"
      footer={
        <>
          <Button variant="secondary" disabled={rescanDisabled} onClick={() => { void restartJob('runtime-scan'); }}>重新扫描</Button>
          <Button variant="secondary" onClick={onClose}>关闭</Button>
        </>
      }
    >
      <JobCard title="扫描 PATH" job={job} elapsedSeconds={elapsedSeconds} createError={createError} onCancel={() => { void cancelJob('runtime-scan'); }}>
        <ScanResult registered={registered} readFailed={readFailed} envelope={job?.envelope ?? null} onRegister={onRegister} />
      </JobCard>
    </Dialog>
  );
}

// 外层：入口按钮一直可点（加载、出错、离线各态都可点，与 [保存当前为方案…] 同口径），secondary/md、带 SearchIcon；
// 写流程留在这里，对话框关掉也照常渲染确认框、执行、重读与终态。点入口先 ensureJob（已有作业不另建）再开框。
export function ScanRuntimesAction({ reload }: { reload?: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const { start, flow } = useWriteFlow(reload);
  return (
    <>
      <Button variant="secondary" size="md" onClick={() => { ensureJob('runtime-scan'); setOpen(true); }}>
        <SearchIcon width={16} height={16} />
        扫描 PATH
      </Button>
      {open && <RuntimeScanDialog
        onClose={() => setOpen(false)}
        onRegister={(adapter) => {
          // 先关掉扫描对话框，再走既有 runtime.add 的写流程（args 只有 runtime 与 adapter，都是适配器名，不带 command）。
          setOpen(false);
          const spec: WriteSpec = { action: 'runtime.add', args: { runtime: adapter, adapter: adapter } };
          start(spec);
        }}
      />}
      <WriteFlow flow={flow} />
    </>
  );
}
