// CLI 运行时页（合同第 2、6 条）：并行读 getRuntimes 与两个 Quizs 读函数；只有 runtimes 失败才整页失败，
// 两个 Quizs 信封整个放进 data.quizs（Quizs 读失败只在区块里显示，页面其余照常）。空态「还没有登记的
// runtime」；页头 [扫描 PATH] 可点（走作业接口，由 src/writes 的 ScanRuntimesAction 接上），[手动登记…] 由 src/writes 的
// AddRuntimeAction 接上。空态（一个 runtime 都没有）也摆 Quizs 一块：EmptyState 之后接 QuizsBlock，
// 直接挂在页面下（视图根之外），间距靠 .tt-page 自己的 gap，不加任何样式。
import { PageFrame } from '../shell/PageFrame';
import {
  getQuizsLive,
  getQuizsProviders,
  getRuntimes,
  type Envelope,
  type QuizsLiveData,
  type QuizsProvidersData,
  type RuntimesData,
} from '../api';
import { EmptyState } from '../components';
import { RuntimesView } from './readonly1/runtimes-RuntimesView';
import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';
import { AddRuntimeAction } from '../writes/RuntimeForm';
import { ScanRuntimesAction } from '../writes/RuntimeScan';

// 并行读三条：runtimes 失败（!ok 或 data 为空）时整页返回那个信封；成功时两个 Quizs 信封整个放进 data.quizs，
// 不参与整页失败判定。
const loadRuntimes = (): Promise<
  Envelope<{ runtimes: RuntimesData; quizs: { providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> } }>
> =>
  Promise.all([getRuntimes(), getQuizsProviders(), getQuizsLive()]).then(([runtimes, providers, live]) => {
    if (!runtimes.ok || runtimes.data == null) {
      // 整页失败：命令、退出码与 messages 原样带回（失败信封的 data 与成功态形状不同，按七个字段重建）。
      const { ok, exit_code, output, messages, command, elapsed_ms } = runtimes;
      return { ok, exit_code, output, messages, command, elapsed_ms, data: null };
    }
    return {
      ok: true,
      exit_code: 0,
      data: { runtimes: runtimes.data, quizs: { providers, live } },
      output: [],
      messages: [],
      command: runtimes.command,
      elapsed_ms: 0,
    };
  });

// 空态仍只看 runtimes 的长度（Quizs 读失败不影响空态判定）；参数只要够读到 runtimes 就行。
const isRuntimesEmpty = (d: { runtimes: RuntimesData }) => d.runtimes.runtimes.length === 0;

export default function RuntimesPage() {
  return (
    <PageFrame<{
      runtimes: RuntimesData;
      quizs: { providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> };
    }>
      title="CLI 运行时"
      description="每个 runtime 是一个 CLI 的一份安装；命令来源依次是环境变量（只对 pi）、本机文件、PATH"
      load={loadRuntimes}
      isEmpty={isRuntimesEmpty}
      actions={(reload) => (
        <>
          <ScanRuntimesAction reload={reload} />
          <AddRuntimeAction reload={reload} />
        </>
      )}
    >
      {(data, reload) =>
        isRuntimesEmpty(data) ? (
          <>
            <EmptyState title="还没有登记的 runtime" description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）" />
            <QuizsBlock quizs={data.quizs} />
          </>
        ) : (
          <RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />
        )
      }
    </PageFrame>
  );
}
