// 页面框架向 Tab 栏状态段报告加载状态（合同第 4、8 条）。PageFrame 经 useReportPage 上报
// 首次加载、有数据的时间与出错的时间；App 持有最新的一份，传给 TabBar 渲染「上次更新」。
import { createContext, useContext } from 'react';

export type PagePhase = 'loading' | 'data' | 'error';

export interface PageReport {
  phase: PagePhase;
  /** 有数据或出错的时刻（Date.now()）；首次加载为 null。 */
  at: number | null;
}

const NOOP = () => {};

const ShellStatusContext = createContext<((report: PageReport) => void) | null>(null);

export const ShellStatusProvider = ShellStatusContext.Provider;

/** 取上报函数；不在外壳里（如单独测 PageFrame）时退回稳定的空操作。 */
export function useReportPage(): (report: PageReport) => void {
  return useContext(ShellStatusContext) ?? NOOP;
}
