// 总览页（合同第 2、4 条）：并行读 getStatus 与 getHistory，getStatus 失败返回它的信封；
// 说明「仓库名 · kit 版本」来自 getMetaNow() 打底、getMeta() 刷新；空态「还没有 attempt」。
import { useEffect, useState } from 'react';
import { PageFrame } from '../shell/PageFrame';
import { useAppNavigate } from '../shell/router';
import { getHistory, getMeta, getMetaNow, getStatus, type Envelope, type HistoryData, type StatusData } from '../api';
import { OverviewView, type OverviewData } from './readonly1/overview-OverviewView';

const loadOverview = (): Promise<Envelope<OverviewData>> =>
  Promise.all([getStatus(), getHistory()]).then(([status, history]) => {
    if (!status.ok || status.data == null) return status as unknown as Envelope<OverviewData>;
    return {
      ok: true,
      exit_code: 0,
      data: { status: status.data, history },
      output: [],
      messages: [],
      command: status.command,
      elapsed_ms: 0,
    };
  });

const isOverviewEmpty = (d: OverviewData) => d.status.length === 0;

export default function OverviewPage() {
  const navigate = useAppNavigate();
  const seed = getMetaNow();
  const [desc, setDesc] = useState(() => `${seed.repo_name} · kit ${seed.kit_version}`);
  useEffect(() => {
    let alive = true;
    getMeta().then((env) => {
      if (alive && env.ok && env.data) setDesc(`${env.data.repo_name} · kit ${env.data.kit_version}`);
    });
    return () => {
      alive = false;
    };
  }, []);
  return (
    <PageFrame<OverviewData>
      title="总览"
      description={desc}
      load={loadOverview}
      isEmpty={isOverviewEmpty}
      empty={{ title: '还没有 attempt', description: '在规划端用 /dispatch-pi 派遣第一个任务' }}
    >
      {(data) => <OverviewView status={data.status} history={data.history} navigate={navigate} />}
    </PageFrame>
  );
}
