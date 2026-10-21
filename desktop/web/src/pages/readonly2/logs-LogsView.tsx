// 日志与用量页视图（合同 D02、D03）：Tabs 分检索（缺省）与用量两页签；页签不写进地址。
import { useState } from 'react';
import { Tabs } from '../../components';
import type { UsageData } from '../../api';
import { SearchPanel, type SearchLogsReader } from './logs-SearchPanel';
import { UsagePanel } from './logs-UsagePanel';

const ITEMS = [
  { id: 'search', label: '检索' },
  { id: 'usage', label: '用量' },
] as const;

export function LogsView({ data, searchLogs }: { data: UsageData; searchLogs: SearchLogsReader }) {
  const [tab, setTab] = useState<string>(ITEMS[0].id);
  return (
    <div className="r2-logs" data-page="logs">
      <Tabs items={ITEMS.map((it) => ({ ...it }))} value={tab} onChange={setTab} aria-label="日志与用量">
        {tab === 'search' ? <SearchPanel usage={data} searchLogs={searchLogs} /> : <UsagePanel usage={data} />}
      </Tabs>
    </div>
  );
}
