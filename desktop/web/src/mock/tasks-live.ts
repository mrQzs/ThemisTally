// 运行中 attempt 的事件跟随模拟（示意，接本机服务那一片换成 subscribeEvents）：
// 只对 ui-readonly-api/attempt-001，且只在开关为 data 时生效，用 setTimeout 链每 1000ms 给一行，最多 30 行。
// 返回取消函数；卸载或切走页签时调它清掉挂起的计时器。
import { currentMock } from '../mock/scenario';

const INTERVAL_MS = 1000; // 追加节奏：1000ms 一行
const MAX_LINES = 30; // 最多追加 30 行

export interface LiveEventLine {
  n: number;
  text: string;
}

/** 订阅运行中 attempt 的新事件行；返回取消函数。 */
export function subscribeMockEvents(
  task: string,
  attempt: string,
  onLines: (lines: LiveEventLine[]) => void,
): () => void {
  if (task !== 'ui-readonly-api' || attempt !== 'attempt-001') return () => {};
  if (currentMock() !== 'data') return () => {};
  let sent = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const tick = () => {
    timer = null;
    if (sent >= MAX_LINES) return;
    sent += 1;
    onLines([{ n: sent, text: `{"type":"tool_execution_end","toolName":"bash","isError":false,"seq":${sent}}` }]);
    if (sent < MAX_LINES) timer = setTimeout(tick, INTERVAL_MS);
  };
  timer = setTimeout(tick, INTERVAL_MS);
  return () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  };
}
