// 页内读取函数（读法 A）：UI 文档 8.9 没有示例的三个读函数——searchLogs、getHistoryEntry、getPlugin。
// 信封与 ?mock= 规则同 api.ts：每次读 currentMock()；loading 返回永不兑现的 Promise；error 返回 ok false、
// exit_code 2、data null 与报错原文；empty 时检索返回空 matches；data 与 offline 返回深拷贝；夹具之外的参数
// 返回 ok false、exit_code 2 与「ERROR 夹具里没有这份数据：…」。接本机服务后这三个函数并入 api.ts。
import type { Envelope } from '../../api';
import { currentMock, type MockMode } from '../../mock/scenario';
import { SEARCH_FIXTURE, SEARCH_PATTERN, type SearchData } from '../../mock/readonly2-search';
import { HISTORY_ENTRIES, type HistoryEntryData } from '../../mock/readonly2-history-entries';
import { PLUGIN_SHOWS, type PluginShowData } from '../../mock/readonly2-plugin-show';

// error 开关的报错原文（Main 画布 :237–238），与 api.ts 同一句。
const ERROR_MESSAGE = 'ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied';

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function okEnvelope<T>(command: string[], data: T): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

function missingEnvelope(command: string[], detail: string): Envelope<never> {
  return {
    ok: false,
    exit_code: 2,
    data: null,
    output: [],
    messages: [`ERROR 夹具里没有这份数据：${detail}`],
    command,
    elapsed_ms: 0,
  };
}

function errorEnvelope<T>(command: string[]): Envelope<T> {
  return { ok: false, exit_code: 2, data: null, output: [], messages: [ERROR_MESSAGE], command, elapsed_ms: 0 };
}

// loading：永不兑现的 Promise，不用计时器（假计时器下也拿不到结果）。
function pending<T>(): Promise<Envelope<T>> {
  return new Promise<Envelope<T>>(() => {});
}

// loading / error 两个开关先于参数校验：整次请求挂起或内核报错，与参数是否在夹具里无关。
function read<T>(command: string[], produce: (mode: MockMode) => Envelope<T>): Promise<Envelope<T>> {
  const mode = currentMock();
  if (mode === 'loading') return pending();
  if (mode === 'error') return Promise.resolve(errorEnvelope<T>(command));
  return Promise.resolve(produce(mode));
}

function searchCommand(q: string, task: string | null, max: number): string[] {
  const command = ['logs', 'search', q];
  if (task) command.push('--task', task);
  command.push('--max', String(max));
  return command;
}

/** logs search <q> [--task <task>] --max <max>：在全部证据里检索正则表达式。 */
export function searchLogs(q: string, task: string | null, max: number): Promise<Envelope<SearchData>> {
  const command = searchCommand(q, task, max);
  return read(command, (mode) => {
    if (mode === 'empty') {
      return okEnvelope(command, { matches: [], truncated: false, skipped_links: 0, skipped_large: 0 });
    }
    if (q !== SEARCH_PATTERN) return missingEnvelope(command, q);
    const all = SEARCH_FIXTURE.matches;
    if (task && !all.some((m) => m.task === task)) return missingEnvelope(command, `task ${task}`);
    const filtered = task ? all.filter((m) => m.task === task) : all;
    const matches = filtered.slice(0, Math.max(0, max));
    return okEnvelope(command, {
      matches: clone(matches),
      truncated: filtered.length > matches.length,
      skipped_links: SEARCH_FIXTURE.skipped_links,
      skipped_large: SEARCH_FIXTURE.skipped_large,
    });
  });
}

/** config history show <n>：一条配置历史的详情（键级差异或本机文件哈希）。 */
export function getHistoryEntry(n: number): Promise<Envelope<HistoryEntryData>> {
  const command = ['config', 'history', 'show', String(n)];
  return read(command, () =>
    Object.prototype.hasOwnProperty.call(HISTORY_ENTRIES, n)
      ? okEnvelope(command, clone(HISTORY_ENTRIES[n]))
      : missingEnvelope(command, String(n)),
  );
}

/** plugins show <id>：一个插件的 manifest、资源哈希与锁。 */
export function getPlugin(id: string): Promise<Envelope<PluginShowData>> {
  const command = ['plugins', 'show', id];
  return read(command, () =>
    Object.prototype.hasOwnProperty.call(PLUGIN_SHOWS, id)
      ? okEnvelope(command, clone(PLUGIN_SHOWS[id]))
      : missingEnvelope(command, id),
  );
}
