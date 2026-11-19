// CLI 运行时页（合同第 2、6 条）：并行读 getRuntimes 与两个 Quizs 读函数；只有 runtimes 失败才整页失败，
// 两个 Quizs 信封整个放进 data.quizs（Quizs 读失败只在区块里显示，页面其余照常）。页头 [扫描 PATH] 可点
// （走作业接口，由 src/writes 的 ScanRuntimesAction 接上），[手动登记…] 由 src/writes 的 AddRuntimeAction
// 接上。页面状态由 isEmpty 定：一个 runtime 都没有时仍是 empty，视图根照常渲染——空态由视图在
// 「已登记」那一节里显示，就绪检查一节与 Quizs 一块也都在视图根里。
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
import { RuntimesView } from './readonly1/runtimes-RuntimesView';
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
      {(data, reload) => (
        <RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />
      )}
    </PageFrame>
  );
}
