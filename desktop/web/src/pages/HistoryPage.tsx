// 历史与审计页（合同第 9 条 / D06、D07）：load=getHistory，空态「还没有配置历史」（entries 与 broken_lines 都为空才算空）；
// 抽屉详情走读法 A 的 getHistoryEntry，由本文件以模块级引用传给视图。
import { PageFrame } from '../shell/PageFrame';
import { getHistory, type HistoryData } from '../api';
import { HistoryView } from './readonly2/history-HistoryView';
import { getHistoryEntry } from './readonly2/common-readers';

const isHistoryEmpty = (d: HistoryData) => d.entries.length === 0 && d.broken_lines.length === 0;

export default function HistoryPage() {
  return (
    <PageFrame<HistoryData>
      title="历史与审计"
      description="每次配置写入都有编号；点一行看前后快照的键级差异，必要时回滚"
      load={getHistory}
      isEmpty={isHistoryEmpty}
      empty={{ title: '还没有配置历史' }}
    >
      {(data) => <HistoryView data={data} getHistoryEntry={getHistoryEntry} />}
    </PageFrame>
  );
}
