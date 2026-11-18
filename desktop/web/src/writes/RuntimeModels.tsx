// 运行时表行内 [模型] 入口与列模型对话框（T055）：点入口起一个 models 作业，对话框里用作业进度卡显示进度，
// 结束后列出 provider、model、是否在允许列表三列（列表来自 pi --list-models，不调用模型）。同类作业同一时间
// 只有一个：忙于别的行时本行禁用并写明正在忙谁。内外两层照 T054，逐字文案都放在本文件（入口文件不写）。
import { useState, type ReactNode } from 'react';
import { Button, Dialog } from '../components';
import { DisabledAction } from '../shell/DisabledAction';
import { JobCard } from '../jobs/JobCard';
import { cancelJob, ensureJob, restartJob, useBusyRuntime, useJob } from '../jobs/jobStore';
import type { JobView } from '../api';
// 样式表接线：放在组件 import 之后（照仓库里组件带自己的样式表的写法）。
import './runtime-models.css';

// 疑似凭据的行内核已脱敏成 <redacted>：原样显示，另加一句 title 说明这是什么。
const REDACTED = '<redacted>';
const REDACTED_TITLE = '疑似凭据，内核已脱敏';

interface ModelsRow {
  provider: string;
  model: string;
  allowed: boolean | null;
}

interface ModelsData {
  runtime: string;
  models: ModelsRow[];
}

// 「有 data」的判定：envelope.data 是对象、runtime 是字符串、models 是数组（内核报错时没有 data）。
function modelsData(job: JobView | null): ModelsData | null {
  const data = job?.envelope?.data;
  if (typeof data !== 'object' || data === null) return null;
  const row = data as Record<string, unknown>;
  if (typeof row.runtime !== 'string' || !Array.isArray(row.models)) return null;
  const models: ModelsRow[] = [];
  for (const item of row.models) {
    if (typeof item !== 'object' || item === null) continue;
    const one = item as Record<string, unknown>;
    if (typeof one.provider !== 'string' || typeof one.model !== 'string') continue;
    models.push({
      provider: one.provider,
      model: one.model,
      allowed: typeof one.allowed === 'boolean' ? one.allowed : null,
    });
  }
  return { runtime: row.runtime, models };
}

// allowed 三态：true「是」、false「否」、null「不限制」（没设允许列表即不限制）。
function allowedText(allowed: boolean | null): string {
  if (allowed === true) return '是';
  if (allowed === false) return '否';
  return '不限制';
}

function ModelsResult({ data }: { data: ModelsData }): ReactNode {
  return (
    <div className="rm-result">
      <p className="rm-note">模型列表来自 pi --list-models，不调用模型</p>
      {data.models.length === 0 ? (
        <p className="rm-empty">没有列出模型</p>
      ) : (
        <table className="rm-table">
          <thead>
            <tr>
              <th>provider</th>
              <th>model</th>
              <th>是否在允许列表</th>
            </tr>
          </thead>
          <tbody>
            {data.models.map((one) => (
              <tr key={`${one.provider}/${one.model}`}>
                <td title={one.provider === REDACTED ? REDACTED_TITLE : undefined}>{one.provider}</td>
                <td title={one.model === REDACTED ? REDACTED_TITLE : undefined}>{one.model}</td>
                <td>{allowedText(one.allowed)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// 内层对话框：只在打开时挂载。body 放作业卡，脚注放 [重新列出]（终态或创建失败才可点）与 [关闭]（不取消作业）。
// 作业在跑时对话框不可被 Esc 与头部关闭钮关掉（命令已发出，别假装取消；照 WriteConfirmDialog 的 dismissible 口径），
// 脚注 [关闭] 照旧能关——关框不取消作业，作业在模块里接着跑。
function RuntimeModelsDialog({ runtime, onClose }: { runtime: string; onClose: () => void }) {
  const { job, elapsedSeconds, createError, creating } = useJob('models', runtime);
  const data = modelsData(job);
  const succeeded = job != null && job.state === 'succeeded';
  const failed = job != null && job.state === 'failed';
  const restartDisabled = !(createError != null || (job != null && job.state !== 'queued' && job.state !== 'running'));
  const running = creating || (job != null && (job.state === 'queued' || job.state === 'running'));

  return (
    <Dialog
      open
      onClose={onClose}
      title={`模型 ${runtime}`}
      dismissible={!running}
      footer={
        <>
          <Button variant="secondary" size="sm" disabled={restartDisabled} onClick={() => { void restartJob('models', runtime); }}>重新列出</Button>
          <Button variant="secondary" size="sm" onClick={onClose}>关闭</Button>
        </>
      }
    >
      <JobCard
        title={`模型 ${runtime}`}
        kind="models"
        job={job}
        elapsedSeconds={elapsedSeconds}
        createError={createError}
        onCancel={() => { void cancelJob('models'); }}
        failedDetail={failed && data != null ? <ModelsResult data={data} /> : undefined}
      >
        {succeeded && data != null ? <ModelsResult data={data} /> : null}
      </JobCard>
    </Dialog>
  );
}

// 外层：本类不忙（或正忙于本行）时可点，点它先 ensureJob（已有作业不另建）再开框；忙于别的行时禁用并写明正在忙谁。
export function ModelsRuntimeAction({ runtime }: { runtime: string }) {
  const [open, setOpen] = useState(false);
  const busy = useBusyRuntime('models');
  if (busy != null && busy !== runtime) {
    return <DisabledAction label="模型" variant="ghost" size="sm" reason={`正在列 ${busy} 的模型`} />;
  }
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => { void ensureJob('models', runtime); setOpen(true); }}>模型</Button>
      {open && <RuntimeModelsDialog runtime={runtime} onClose={() => setOpen(false)} />}
    </>
  );
}
