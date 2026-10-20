// CLI 运行时页占位（合同第 9 条）：load=getRuntimes，空态「还没有登记的 runtime」。
import { PageFrame } from '../shell/PageFrame';
import { getRuntimes, type RuntimesData } from '../api';

const isRuntimesEmpty = (d: RuntimesData) => d.runtimes.length === 0;

export default function RuntimesPage() {
  return (
    <PageFrame<RuntimesData>
      title="CLI 运行时"
      load={getRuntimes}
      isEmpty={isRuntimesEmpty}
      empty={{ title: '还没有登记的 runtime' }}
    >
      {(data) => <p className="tt-page__read">夹具数据已读到：getRuntimes，{data.runtimes.length} 条。</p>}
    </PageFrame>
  );
}
