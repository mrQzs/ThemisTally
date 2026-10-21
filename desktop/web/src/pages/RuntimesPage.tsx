// CLI 运行时页（合同第 2、6 条）：读 getRuntimes，空态「还没有登记的 runtime」；页头两个写入口禁用。
import { PageFrame } from '../shell/PageFrame';
import { DisabledAction } from '../shell/DisabledAction';
import { PlusIcon, SearchIcon } from '../icons';
import { getRuntimes, type Envelope, type RuntimesData } from '../api';
import { RuntimesView } from './readonly1/runtimes-RuntimesView';

const loadRuntimes = (): Promise<Envelope<RuntimesData>> => getRuntimes();

const isRuntimesEmpty = (d: RuntimesData) => d.runtimes.length === 0;

export default function RuntimesPage() {
  return (
    <PageFrame<RuntimesData>
      title="CLI 运行时"
      description="每个 runtime 是一个 CLI 的一份安装；命令来源依次是环境变量（只对 pi）、本机文件、PATH"
      load={loadRuntimes}
      isEmpty={isRuntimesEmpty}
      empty={{ title: '还没有登记的 runtime', description: '在命令行里用 config runtime scan --add 登记；界面上的登记入口在第二阶段接入' }}
      actions={
        <>
          <DisabledAction label="扫描 PATH" icon={<SearchIcon width={16} height={16} />} />
          <DisabledAction label="手动登记…" variant="primary" icon={<PlusIcon width={16} height={16} />} />
        </>
      }
    >
      {(data) => <RuntimesView runtimes={data.runtimes} />}
    </PageFrame>
  );
}
