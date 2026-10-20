// ?mock=empty 时列表资源的空形状（合同第 7 条）。只对五个列表资源生效：status、runtimes、secrets、plugins、history。
// 其余资源照常返回夹具；getMeta 不受开关影响。
import type { StatusRow, RuntimesData, SecretsData, PluginsData, HistoryData } from '../api';

export const EMPTY_STATUS: StatusRow[] = [];

export const EMPTY_RUNTIMES: RuntimesData = { runtimes: [] };

export const EMPTY_SECRETS: SecretsData = { secrets: [] };

export const EMPTY_PLUGINS: PluginsData = {
  plugins_root_link: false,
  plugins: [],
  not_installed: [],
  problems: [],
};

export const EMPTY_HISTORY: HistoryData = { entries: [], broken_lines: [], external_before_first: 0 };
