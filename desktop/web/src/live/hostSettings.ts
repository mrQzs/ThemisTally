// 宿主接口的「打开设置」入口：服务窗口的 preload 暴露的那组函数里有一个能开出设置外壳窗口。
// SettingsPage 只调这个模块——SettingsPage.tsx 里不许出现那个宿主对象的字样
// （T032 的静态断言点名那个文件不许出现那四类词）。这里就是那个宿主对象的唯一读取点。
// 外观三件套（读、订阅、保存）也在这里：宿主只在外观真的变了时才广播，页面只持有当前值。
import type { ThemePref } from '../shell/theme';
import type { ShellAppearance } from '../shellpages/themisShell';

export interface HostEnvelope {
  ok?: boolean;
  reason?: string;
  value?: { theme: string; density: string };
}

interface HostBridge {
  openSettings?: () => Promise<HostEnvelope> | HostEnvelope;
  getAppearance?: () => unknown;
  onAppearance?: (listener: (appearance: ShellAppearance) => void) => unknown;
  saveTheme?: (pref: ThemePref) => HostEnvelope | Promise<HostEnvelope>;
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

// 逐字段校验：theme 只认三种，非法取缺省暗；density 只认两种，非法取缺省标准。
function readAppearance(value: unknown): ShellAppearance | null {
  if (value === null || typeof value !== 'object') return null;
  const raw = value as { theme?: unknown; density?: unknown };
  const theme = raw.theme === 'light' || raw.theme === 'system' ? raw.theme : 'dark';
  const density = raw.density === 'compact' ? 'compact' : 'standard';
  return { theme, density };
}

/** 服务窗口的当前外观：同步读一次。没有这个能力、抛错、回值不是对象都回 null，不抛到调用方。 */
export function hostGetAppearance(): ShellAppearance | null {
  const get = hostBridge()?.getAppearance;
  if (typeof get !== 'function') return null;
  try {
    return readAppearance(get());
  } catch {
    return null;
  }
}

/** 订阅宿主的外观广播：监听只收外观一个实参。退订不是函数、调用抛错都回空退订函数；
 * 退订函数真的能退——调过之后监听不再收到事件。 */
export function hostOnAppearance(listener: (appearance: ShellAppearance) => void): () => void {
  const on = hostBridge()?.onAppearance;
  if (typeof on !== 'function') return () => {};
  let live = true;
  const forward = (appearance: ShellAppearance): void => {
    if (live) listener(appearance);
  };
  try {
    const off = on(forward);
    return () => {
      live = false;
      if (typeof off === 'function') (off as () => void)();
    };
  } catch {
    return () => {};
  }
}

/** 保存主题偏好：只转交 pref 一个实参，信封原样（不拆）。没有这个能力、调用抛错回 null。 */
export function hostSaveTheme(pref: ThemePref): Promise<HostEnvelope> | null {
  const save = hostBridge()?.saveTheme;
  if (typeof save !== 'function') return null;
  try {
    return Promise.resolve(save(pref));
  } catch {
    return null;
  }
}
