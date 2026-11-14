// 实时 status 钩子：真实模式订阅事件流，有 ok:true 的推送时返回最新 status，还没有推送时返回首屏值
// （每次渲染都取最新的 initial，不缓存旧值）；夹具模式原样返回 initial，不订阅、不建流、不起计时器。
import { useSyncExternalStore } from 'react';
import { liveEvents } from './events';
import { liveModeIsReal } from './mode';
import type { StatusData } from '../api';

export function useLiveStatus(initial: StatusData): StatusData {
  // 开关只看构建期常量：dev server 与 vitest 走夹具，事件流那边一个订阅都不会有。
  if (!liveModeIsReal()) return initial;
  const pushed = useSyncExternalStore(liveEvents.subscribe, liveEvents.getStatus);
  return pushed ?? initial;
}
