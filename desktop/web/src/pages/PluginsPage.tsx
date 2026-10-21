// 插件页（合同第 9 条 / D04、D05）：load=getPlugins，空态「还没有插件」（plugins、not_installed、problems 都为空才算空）；
// 抽屉详情走读法 A 的 getPlugin，由本文件以模块级引用传给视图。
import { PageFrame } from '../shell/PageFrame';
import { getPlugins, type PluginsData } from '../api';
import { ListChecksIcon } from '../icons';
import { DisabledAction } from '../shell/DisabledAction';
import { PluginsView } from './readonly2/plugins-PluginsView';
import { getPlugin } from './readonly2/common-readers';

const isPluginsEmpty = (d: PluginsData) =>
  d.plugins.length === 0 && d.not_installed.length === 0 && d.problems.length === 0;

export default function PluginsPage() {
  return (
    <PageFrame<PluginsData>
      title="插件"
      description="启停前先预览权限变化；锁与资源哈希由内核核对"
      load={getPlugins}
      isEmpty={isPluginsEmpty}
      empty={{ title: '还没有插件' }}
      actions={
        <DisabledAction label="核对全部" variant="secondary" size="md" icon={<ListChecksIcon width={16} height={16} />} />
      }
    >
      {(data) => <PluginsView data={data} getPlugin={getPlugin} />}
    </PageFrame>
  );
}
