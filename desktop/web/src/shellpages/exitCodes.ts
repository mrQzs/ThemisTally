// 退出码说明（src/shellpages/exitCodes.ts）：映射写在本地，服务状态页与首启第 4 步共用（D06）。
// 取自架构文档 5.1 :712–715 与 UI 文档 6.1 的表；本片照 6.1 写，接真实外壳那一片再定退出码 1 的两种含义。
// 视图里不另写这几句，只从本模块取。

const ALREADY_OPEN = '这个仓库已经在另一个窗口里打开了。';
const INCOMPLETE = '应用文件不完整，请重新安装。';
const UNEXPECTED = '本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。';

/** 服务状态页的一段说明。 */
export function stoppedNote(code: number): string {
  if (code === 1) return ALREADY_OPEN;
  if (code === 2) return INCOMPLETE;
  return UNEXPECTED;
}

/** 首启第 4 步错误框的首句。 */
export function firstRunHeadline(code: number): string {
  if (code === 1) return ALREADY_OPEN;
  if (code === 2) return INCOMPLETE;
  return `本机服务没能启动（退出码 ${code}）。`;
}
