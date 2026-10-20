// 日志与用量页占位（合同第 9 条）：load=getUsage（合计型资源，不写条数）。
import { PageFrame } from '../shell/PageFrame';
import { getUsage, type UsageData } from '../api';

export default function LogsPage() {
  return (
    <PageFrame<UsageData> title="日志与用量" load={getUsage}>
      {() => <p className="tt-page__read">夹具数据已读到：getUsage。</p>}
    </PageFrame>
  );
}
