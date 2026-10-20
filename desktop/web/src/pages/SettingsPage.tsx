// 设置页占位（合同第 9 条）：load=getMeta（getMeta 不受 ?mock= 开关影响）。
import { PageFrame } from '../shell/PageFrame';
import { getMeta, type MetaData } from '../api';

export default function SettingsPage() {
  return (
    <PageFrame<MetaData> title="设置" load={getMeta}>
      {() => <p className="tt-page__read">夹具数据已读到：getMeta。</p>}
    </PageFrame>
  );
}
