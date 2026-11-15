// CLI 运行时页（合同第 2、6 条）：读 getRuntimes，空态「还没有登记的 runtime」；页头 [扫描 PATH] 仍禁用
// （服务没有 config runtime scan 写路由），[手动登记…] 由 src/writes 的 AddRuntimeAction 接上。
import { PageFrame } from '../shell/PageFrame';
import { DisabledAction } from '../shell/DisabledAction';
import { SearchIcon } from '../icons';
import { getRuntimes, type Envelope, type RuntimesData } from '../api';
import { RuntimesView } from './readonly1/runtimes-RuntimesView';
import { AddRuntimeAction } from '../writes/RuntimeForm';

const loadRuntimes = (): Promise<Envelope<RuntimesData>> => getRuntimes();

const isRuntimesEmpty = (d: RuntimesData) => d.runtimes.length === 0;

export default function RuntimesPage() {
  return (
    <PageFrame<RuntimesData>
      title="CLI 运行时"
      description="每个 runtime 是一个 CLI 的一份安装；命令来源依次是环境变量（只对 pi）、本机文件、PATH"
      load={loadRuntimes}
      isEmpty={isRuntimesEmpty}
      empty={{ title: '还没有登记的 runtime', description: '用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）' }}
      actions={(reload) => (
        <>
          <DisabledAction label="扫描 PATH" icon={<SearchIcon width={16} height={16} />} />
          <AddRuntimeAction reload={reload} />
        </>
      )}
    >
      {(data, reload) => <RuntimesView runtimes={data.runtimes} reload={reload} />}
    </PageFrame>
  );
}
