// 插件页占位（合同第 9 条）：load=getPlugins，空态「还没有插件」。
import { PageFrame } from '../shell/PageFrame';
import { getPlugins, type PluginsData } from '../api';

const isPluginsEmpty = (d: PluginsData) => d.plugins.length === 0;

export default function PluginsPage() {
  return (
    <PageFrame<PluginsData>
      title="插件"
      load={getPlugins}
      isEmpty={isPluginsEmpty}
      empty={{ title: '还没有插件' }}
    >
      {(data) => <p className="tt-page__read">夹具数据已读到：getPlugins，{data.plugins.length} 条。</p>}
    </PageFrame>
  );
}
