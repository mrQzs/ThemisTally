// 作业进度卡（T054）：运行中显示不确定进度条、已用秒数与 [取消]；结束后在同一位置显示结局——
// succeeded 渲染 children（结果表）、failed「扫描失败」+ 内核报错原文、cancelled「已取消」、
// timed_out「超时（超过 150 秒），已停止」。进度条用 progressbar 角色（不渲染 status 类角色）；组件带自己的样式表（import 放在组件 import 之后）。
import { useState, type ReactNode } from 'react';
import { Button } from '../components';
import type { Envelope, JobView } from '../api';
// 样式表接线：放在组件 import 之后（照仓库里组件带自己的样式表的写法）。
import './job-card.css';

// 前端自己维护的作业时限表（照 ts/packages/ui/src/jobroutes.ts 的 JOB_TIMEOUTS；本片只登记 runtime-scan）。
const JOB_TIMEOUT_SECONDS: Record<string, number> = { 'runtime-scan': 150 };

export interface JobCardProps {
  title: string;
  job: JobView | null;
  elapsedSeconds: number;
  createError: Envelope<unknown> | null;
  onCancel: () => void;
  children?: ReactNode;
}

// 内核报错原文：messages 逐行照显示；为空时按退出码给占位（退出码为 null 时只给「内核报错」）。
function errorText(env: Envelope<unknown> | null): string {
  const msgs = env?.messages ?? [];
  if (msgs.length > 0) return msgs.join('\n');
  const code = env?.exit_code;
  return code == null ? '内核报错' : `内核报错（退出码 ${code}）`;
}

export function JobCard({ title, job, elapsedSeconds, createError, onCancel, children }: JobCardProps) {
  // 取消请求发出去后就地禁用 [取消]（不重复发）；终态由下一次查询给出。
  const [cancelSent, setCancelSent] = useState(false);
  const state = job?.state ?? null;
  const running = state === 'queued' || state === 'running';

  return (
    <div className="jc">
      <div className="jc-title">{title}</div>
      {createError != null && (
        <div className="jc-error">
          <p className="jc-failed">扫描失败</p>
          <pre className="jc-error__text">{errorText(createError)}</pre>
        </div>
      )}
      {createError == null && job == null && (
        <div className="jc-running">
          <div className="jc-progress" role="progressbar" aria-label="扫描进行中" />
          <p className="jc-elapsed">{`已用 ${elapsedSeconds} 秒`}</p>
        </div>
      )}
      {job != null && running && (
        <div className="jc-running">
          <div className="jc-progress" role="progressbar" aria-label="扫描进行中" />
          <p className="jc-elapsed">{`已用 ${elapsedSeconds} 秒`}</p>
          <Button variant="secondary" size="sm" className="jc-cancel" disabled={cancelSent} onClick={() => { setCancelSent(true); onCancel(); }}>取消</Button>
        </div>
      )}
      {job != null && state === 'succeeded' && <div className="jc-result">{children}</div>}
      {job != null && state === 'failed' && (
        <div className="jc-error">
          <p className="jc-failed">扫描失败</p>
          <pre className="jc-error__text">{errorText(job.envelope)}</pre>
        </div>
      )}
      {job != null && state === 'cancelled' && <p className="jc-cancelled">已取消</p>}
      {job != null && state === 'timed_out' && <p className="jc-timeout">{`超时（超过 ${JOB_TIMEOUT_SECONDS['runtime-scan']} 秒），已停止`}</p>}
    </div>
  );
}
