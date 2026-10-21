// 日志与用量页（合同第 9 条 / D02、D03）：load=getUsage（合计型资源，不写 isEmpty，?mock=empty 下仍是 data）；
// 检索走读法 A 的 searchLogs，由本文件以模块级引用传给视图。
import { PageFrame } from '../shell/PageFrame';
import { getUsage, type UsageData } from '../api';
import { LogsView } from './readonly2/logs-LogsView';
import { searchLogs } from './readonly2/common-readers';

export default function LogsPage() {
  return (
    <PageFrame<UsageData>
      title="日志与用量"
      description="在全部证据里检索；按 attempt 与模型统计 token"
      load={getUsage}
    >
      {(data) => <LogsView data={data} searchLogs={searchLogs} />}
    </PageFrame>
  );
}
