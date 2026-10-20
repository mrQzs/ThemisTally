// 总览页占位（合同第 9 条）：load=getStatus，说明是「仓库名 · kit 版本」（来自 getMeta），
// 空态「还没有 attempt」。有数据时显示一行「夹具数据已读到」加函数名与条数。
import { useEffect, useState } from 'react';
import { PageFrame } from '../shell/PageFrame';
import { getStatus, getMeta, getMetaNow, type StatusData } from '../api';

const isStatusEmpty = (d: StatusData) => d.length === 0;

export default function OverviewPage() {
  // 说明来自 getMeta：调一次 getMeta()（数据层入口），并用 getMetaNow() 同步打底，首屏就有说明。
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
    <PageFrame<StatusData>
      title="总览"
      description={desc}
      load={getStatus}
      isEmpty={isStatusEmpty}
      empty={{ title: '还没有 attempt', description: '在规划端用 /dispatch-pi 派遣第一个任务' }}
    >
      {(data) => <p className="tt-page__read">夹具数据已读到：getStatus，{data.length} 条。</p>}
    </PageFrame>
  );
}
