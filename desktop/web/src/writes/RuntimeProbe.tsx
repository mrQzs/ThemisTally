// 运行时表行内 [探测] 入口与探测对话框（T055）：点入口起一个 runtime-probe 作业，对话框里用作业进度卡
// 显示进度，结束后显示探测结果（版本、命令来源、命令；pi 再加缺少的参数与思考级别）。ok 为假的 failed
// 照样显示探测到的东西，并点明没过的那一项；没有 data 的 failed 只显示内核报错原文。
// 内外两层照 T054：外层只放入口按钮与忙闲，对话框只在打开时挂载；逐字文案都放在本文件（入口文件不写）。
import { useState, type ReactNode } from 'react';
import { Button, Dialog } from '../components';
import { DisabledAction } from '../shell/DisabledAction';
import { JobCard } from '../jobs/JobCard';
import { cancelJob, ensureJob, restartJob, useBusyRuntime, useJob } from '../jobs/jobStore';
import type { JobView } from '../api';
// 样式表接线：放在组件 import 之后（照仓库里组件带自己的样式表的写法）。
import './runtime-probe.css';

// 命令来源的四个标签（与运行时表一致；runtimes-logic.ts 那份不引，这里照抄一张小表）。
const SOURCE_LABELS: Record<string, string> = {
  env: '环境变量',
  local: '本机文件',
  path: 'PATH',
  missing: '找不到',
};

interface ProbeHelp {
  exit_code: number;
  missing_flags: string[];
  thinking_levels: string[];
}

interface ProbeData {
  runtime: string;
  source: string;
  command: string[] | null;
  version: string;
  version_exit_code: number;
  help: ProbeHelp | null;
  ok: boolean;
}

// 「有 data」的判定：envelope.data 是对象、runtime 是字符串、version_exit_code 是数字（内核报错时没有 data）。
function probeData(job: JobView | null): ProbeData | null {
  const data = job?.envelope?.data;
  if (typeof data !== 'object' || data === null) return null;
  const row = data as Record<string, unknown>;
  if (typeof row.runtime !== 'string' || typeof row.version_exit_code !== 'number') return null;
  const raw = row.help;
  const help = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : null;
  const flags = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []);
  return {
    runtime: row.runtime,
    source: typeof row.source === 'string' ? row.source : '',
    command: Array.isArray(row.command) ? flags(row.command) : null,
    version: typeof row.version === 'string' ? row.version : '',
    version_exit_code: row.version_exit_code,
    help: help == null ? null : {
      exit_code: typeof help.exit_code === 'number' ? help.exit_code : 0,
      missing_flags: flags(help.missing_flags),
      thinking_levels: flags(help.thinking_levels),
    },
    ok: row.ok === true,
  };
}

// 探测结果块：版本（空串写「版本未知」）、命令来源、命令（数组空格连、null 写「—」）；
// pi（带 help）再加缺少的参数（空写「无」）与思考级别（「、」连，空写「无」）。
function ProbeResult({ data }: { data: ProbeData }): ReactNode {
  return (
    <dl className="rp-result">
      <div className="rp-row">
        <dt>版本</dt>
        <dd>{data.version === '' ? '版本未知' : data.version}</dd>
      </div>
      <div className="rp-row">
        <dt>命令来源</dt>
        <dd>{SOURCE_LABELS[data.source] ?? data.source}</dd>
      </div>
      <div className="rp-row">
        <dt>命令</dt>
        <dd className="rp-mono">{data.command == null ? '—' : data.command.join(' ')}</dd>
      </div>
      {data.help != null && (
        <>
          <div className="rp-row">
            <dt>缺少的参数</dt>
            <dd className="rp-mono">{data.help.missing_flags.length === 0 ? '无' : data.help.missing_flags.join('、')}</dd>
          </div>
          <div className="rp-row">
            <dt>思考级别</dt>
            <dd>{data.help.thinking_levels.length === 0 ? '无' : data.help.thinking_levels.join('、')}</dd>
          </div>
        </>
      )}
    </dl>
  );
}

// ok 为假时点明没过的那一项（放在内核报错原文之前）。
function ProbeFailedItems({ data }: { data: ProbeData }): ReactNode {
  const items: string[] = [];
  if (data.version_exit_code !== 0) items.push(`版本命令退出码 ${data.version_exit_code}`);
  if (data.help != null && data.help.exit_code !== 0) items.push(`${data.runtime} --help 退出码 ${data.help.exit_code}`);
  if (data.help != null && data.help.missing_flags.length > 0) items.push(`pi 缺少参数：${data.help.missing_flags.join('、')}`);
  if (items.length === 0) return null;
  return (
    <ul className="rp-failed">
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  );
}

// 内层对话框：只在打开时挂载。body 放作业卡，脚注放 [重新探测]（终态或创建失败才可点）与 [关闭]（不取消作业）。
// 作业在跑时对话框不可被 Esc 与头部关闭钮关掉（命令已发出，别假装取消；照 WriteConfirmDialog 的 dismissible 口径），
// 脚注 [关闭] 照旧能关——关框不取消作业，作业在模块里接着跑。
function RuntimeProbeDialog({ runtime, onClose }: { runtime: string; onClose: () => void }) {
  const { job, elapsedSeconds, createError, creating } = useJob('runtime-probe', runtime);
  const data = probeData(job);
  const succeeded = job != null && job.state === 'succeeded';
  const failed = job != null && job.state === 'failed';
  const restartDisabled = !(createError != null || (job != null && job.state !== 'queued' && job.state !== 'running'));
  const running = creating || (job != null && (job.state === 'queued' || job.state === 'running'));

  return (
    <Dialog
      open
      onClose={onClose}
      title={`探测 ${runtime}`}
      dismissible={!running}
      footer={
        <>
          <Button variant="secondary" size="sm" disabled={restartDisabled} onClick={() => { void restartJob('runtime-probe', runtime); }}>重新探测</Button>
          <Button variant="secondary" size="sm" onClick={onClose}>关闭</Button>
        </>
      }
    >
      <JobCard
        title={`探测 ${runtime}`}
        kind="runtime-probe"
        job={job}
        elapsedSeconds={elapsedSeconds}
        createError={createError}
        onCancel={() => { void cancelJob('runtime-probe'); }}
        failedDetail={failed && data != null ? <><ProbeResult data={data} /><ProbeFailedItems data={data} /></> : undefined}
      >
        {succeeded && data != null ? <ProbeResult data={data} /> : null}
      </JobCard>
    </Dialog>
  );
}

// 外层：本类不忙（或正忙于本行）时可点，点它先 ensureJob（已有作业不另建）再开框；忙于别的行时禁用并写明正在忙谁。
export function ProbeRuntimeAction({ runtime }: { runtime: string }) {
  const [open, setOpen] = useState(false);
  const busy = useBusyRuntime('runtime-probe');
  if (busy != null && busy !== runtime) {
    return <DisabledAction label="探测" variant="ghost" size="sm" reason={`正在探测 ${busy}`} />;
  }
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => { void ensureJob('runtime-probe', runtime); setOpen(true); }}>探测</Button>
      {open && <RuntimeProbeDialog runtime={runtime} onClose={() => setOpen(false)} />}
    </>
  );
}
