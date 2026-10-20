// 夹具开关：每次调用时读 location.hash 里的 ?mock= 取值，决定数据层与连接状态走哪条路。
// 五个取值：data（缺省）、offline、loading、error、empty；认不出的值按 data 处理。
// 路由只认路径第一段决定页面，查询里的 mock 由本模块解释（合同第 1、7 条）。
export type MockMode = 'data' | 'offline' | 'loading' | 'error' | 'empty';

const MODES: readonly MockMode[] = ['data', 'offline', 'loading', 'error', 'empty'];

export function currentMock(): MockMode {
  const hash = typeof window !== 'undefined' ? window.location.hash || '' : '';
  const q = hash.indexOf('?');
  if (q < 0) return 'data';
  const query = hash.slice(q + 1);
  for (const part of query.split('&')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    if (part.slice(0, eq) !== 'mock') continue;
    const value = part.slice(eq + 1) as MockMode;
    if (MODES.includes(value)) return value;
  }
  return 'data';
}
