// 总览视图（合同第 4 节）：指标卡、需要你判断、运行中、待集成、最近的配置变更；前三块无行不渲染，配置变更总渲染。
// 只收数据与回调（history 是整个信封，供配置变更区分 ok/出错），不调 api。
import type { Envelope, HistoryData, StatusData } from '../../api';
import { MetricCard } from './overview-MetricCard';
import { AttemptList } from './overview-AttemptList';
import { ConfigChanges } from './overview-ConfigChanges';
import { CARD_META, firstAttemptIn, metricCounts, reviewCommand, rowsInGroups } from './overview-logic';
// 样式表接线（终审 B1）：放在组件 import 之后，使本表晚于 common-section.css 载入（.common-section 的 border 简写会盖掉同特异性的 .ov-judge 左边框）。
import './overview-styles.css';

export interface OverviewData {
  status: StatusData;
  history: Envelope<HistoryData>;
}

export interface OverviewViewProps {
  status: StatusData;
  history: Envelope<HistoryData>;
  navigate: (path: string) => void;
}

export function OverviewView({ status, history, navigate }: OverviewViewProps) {
  const counts = metricCounts(status);
  const judge = rowsInGroups(status, ['review', 'decide']);
  const running = rowsInGroups(status, ['running']);
  const integrate = rowsInGroups(status, ['integrate']);
  const firstReview = firstAttemptIn(status, ['review']);
  const firstIntegrate = firstAttemptIn(status, ['integrate']);

  return (
    <div className="ov" data-page="overview">
      <div className="ov-metrics tt-grid-4">
        {CARD_META.map((c) => (
          <MetricCard key={c.id} group={c.id} label={c.label} count={counts[c.id]} navigate={navigate} />
        ))}
      </div>
      {judge.length > 0 && (
        <AttemptList
          title="需要你判断"
          rows={judge}
          linkKind="evidence"
          infoKind="checks"
          pill={judge.length}
          accentBorder
          next={
            firstReview
              ? { text: '验收在规划端会话里进行：', command: reviewCommand(firstReview) }
              : { text: '需要你做决定，见摘要里的阻塞点。', command: null }
          }
          navigate={navigate}
        />
      )}
      {running.length > 0 && (
        <AttemptList title="运行中" rows={running} linkKind="events" infoKind="live" navigate={navigate} />
      )}
      {integrate.length > 0 && (
        <AttemptList
          title="待集成"
          rows={integrate}
          linkKind="evidence"
          infoKind="checks"
          next={{ text: '集成在规划端会话里进行：', command: reviewCommand(firstIntegrate as string) }}
          navigate={navigate}
        />
      )}
      <ConfigChanges history={history} navigate={navigate} />
    </div>
  );
}
