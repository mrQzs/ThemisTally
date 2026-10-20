// 历史与审计页占位（合同第 9 条）：load=getHistory，空态「还没有配置历史」。
import { PageFrame } from '../shell/PageFrame';
import { getHistory, type HistoryData } from '../api';

const isHistoryEmpty = (d: HistoryData) => d.entries.length === 0;

export default function HistoryPage() {
  return (
    <PageFrame<HistoryData>
      title="历史与审计"
      load={getHistory}
      isEmpty={isHistoryEmpty}
      empty={{ title: '还没有配置历史' }}
    >
      {(data) => <p className="tt-page__read">夹具数据已读到：getHistory，{data.entries.length} 条。</p>}
    </PageFrame>
  );
}
