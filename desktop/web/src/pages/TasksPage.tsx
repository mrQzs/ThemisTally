// 任务页占位（合同第 9 条）：load=getStatus，空态「还没有 attempt」。
import { PageFrame } from '../shell/PageFrame';
import { getStatus, type StatusData } from '../api';

const isStatusEmpty = (d: StatusData) => d.length === 0;

export default function TasksPage() {
  return (
    <PageFrame<StatusData>
      title="任务"
      load={getStatus}
      isEmpty={isStatusEmpty}
      empty={{ title: '还没有 attempt', description: '在规划端用 /dispatch-pi 派遣第一个任务' }}
    >
      {(data) => <p className="tt-page__read">夹具数据已读到：getStatus，{data.length} 条。</p>}
    </PageFrame>
  );
}
