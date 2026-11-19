// 宿主接口的「打开设置」入口：服务窗口的 preload 暴露的那组函数里有一个能开出设置外壳窗口。
// SettingsPage 只调这个模块——SettingsPage.tsx 里不许出现那个宿主对象的字样
// （T032 的静态断言点名那个文件不许出现那四类词）。这里就是那个宿主对象的唯一读取点。
export interface HostEnvelope {
  ok?: boolean;
  reason?: string;
}

interface HostBridge {
  openSettings?: () => Promise<HostEnvelope> | HostEnvelope;
}

function hostBridge(): HostBridge | null {
  return (window as unknown as { themisHost?: HostBridge | null }).themisHost ?? null;
}

/** 有没有这个能力：只判断，不调用。 */
export function hostHasOpenSettings(): boolean {
  return typeof hostBridge()?.openSettings === 'function';
}

/** 调一次：没有这个能力时回 null。 */
export function hostOpenSettings(): Promise<HostEnvelope> | null {
  const open = hostBridge()?.openSettings;
  if (typeof open !== 'function') return null;
  return Promise.resolve(open());
}
