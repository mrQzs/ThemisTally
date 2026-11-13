// 连接状态钩子（合同第 1 节）：App、TitleBar、PageFrame 三处共用一个状态源，不各写一份判定逻辑。
// 真实模式的唯一判据是 liveClient() 非空（含测试注入；注入 null 表示明确不发请求，也算真实模式）——
// liveModeIsReal() 只认构建期常量、不认注入，所以不用它。夹具分支的状态取 mock 自己的连接状态，
// 真实分支的状态取传输层上报的那个（useConnectionState() 无条件调用，守 hooks 规则，也让状态变化触发重渲染）。
import { liveClient } from '../live/mode';
import { useConnectionState } from '../live/connection';
import { currentMock } from '../mock/scenario';
import { shellConnectionState } from '../mock/shell';
import type { ConnectionState } from '../components';

export function useShellConnection(): { live: boolean; state: ConnectionState } {
  const live = liveClient() !== null;
  const liveState = useConnectionState();
  return { live, state: live ? liveState : shellConnectionState(currentMock()) };
}
