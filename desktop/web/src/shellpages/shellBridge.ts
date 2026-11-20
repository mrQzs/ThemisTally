// 外壳桥（src/shellpages/shellBridge.ts）：整个前端唯一读取 window.themisShell 的地方，也是 themisShell 全局声明的唯一处。
// 核对接口十个成员，缺一个或某个不是函数就当作没有外壳（返回 null）；齐全则按原对象用 WeakMap 缓存一份只做转发的包装。
// 真外壳暴露的对象是冻结的、不能往上挂缓存属性，所以缓存用 WeakMap 按原对象记；同一个原对象永远返回同一个包装引用。
// 包装只做转发、不拆信封：外壳页 preload 自己拆信封（ok 为真 resolve value，否则 reject new Error(reason)），
// 前端不判断返回值像不像信封。被拒的 Promise 过桥后只剩 Error.message，所以错误文案只取 message、不自己拼前缀。
// openExternal 被用户取消时 reject 的 message 逐字是 cancelled，前端当作正常结束、不显示错误。
import type { SettingsPatch, ShellAppearance, ShellState, ThemisShell } from './themisShell';

declare global {
  interface Window {
    themisShell?: unknown;
  }
}

// 接口十个成员名：九个方法加 on（类型见 themisShell.ts，一个字不改）。
export const SHELL_MEMBERS: readonly string[] = [
  'getState',
  'pickRepo',
  'pickPython',
  'pickKit',
  'pickTranscriptDir',
  'saveSettings',
  'startService',
  'restartService',
  'openExternal',
  'on',
];

const NO_SHELL = '没有连上外壳';
const CANCELLED = 'cancelled';

// 按原对象缓存包装；原对象被冻结不能挂属性，只能当 WeakMap 的键。resetShellBridge 换一张新表清掉缓存。
let wrappers = new WeakMap<object, ThemisShell>();

function isCompleteShell(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== 'object') return false;
  return SHELL_MEMBERS.every((name) => typeof (value as Record<string, unknown>)[name] === 'function');
}

function wrap(target: Record<string, unknown>): ThemisShell {
  const wrapper: Record<string, unknown> = {};
  for (const name of SHELL_MEMBERS) {
    const method = target[name] as (...args: unknown[]) => unknown;
    if (name === 'on') {
      const on = method as (event: 'service-state', listener: (svc: ShellState['service']) => void) => unknown;
      wrapper.on = (event: 'service-state', listener: (svc: ShellState['service']) => void): (() => void) => {
        const off = on(event, listener);
        return typeof off === 'function' ? () => (off as () => void)() : () => {};
      };
    } else if (name === 'openExternal') {
      wrapper.openExternal = (url: string): Promise<void> =>
        (method(url) as Promise<void>).catch((e: unknown) => {
          if (e instanceof Error && e.message === CANCELLED) return;
          throw e;
        });
    } else {
      wrapper[name] = (...args: unknown[]): unknown => method(...args);
    }
  }
  return wrapper as unknown as ThemisShell;
}

// 每次调用都重新读一次 window.themisShell，不在模块加载时缓存「有没有外壳」这个结论；缓存的是包装。
export function shellBridgeInstance(): ThemisShell | null {
  const value = window.themisShell;
  if (!isCompleteShell(value)) return null;
  let wrapper = wrappers.get(value);
  if (!wrapper) {
    wrapper = wrap(value);
    wrappers.set(value, wrapper);
  }
  return wrapper;
}

let unavailable: ThemisShell | null = null;

// 「外壳不可用」实例：九个方法都返回被拒的 Promise（message 逐字「没有连上外壳」）；on 同步返回空退订函数
// （页面挂载时就会调它，不能抛错、不能返回 Promise）。模块级单例，多次调用返回同一个引用。
export function unavailableShell(): ThemisShell {
  if (unavailable) return unavailable;
  const reject = (): Promise<never> => Promise.reject(new Error(NO_SHELL));
  const noop = (): void => {};
  unavailable = {
    getState: () => reject(),
    pickRepo: () => reject(),
    pickPython: () => reject(),
    pickKit: () => reject(),
    pickTranscriptDir: () => reject(),
    saveSettings: (_patch: SettingsPatch) => reject(),
    startService: (_repo: string) => reject(),
    restartService: () => reject(),
    openExternal: (_url: string) => reject(),
    on: () => noop,
  };
  return unavailable;
}

// 清掉包装缓存，给测试用（不清单例；原对象失效后 WeakMap 的键自然失效）。
export function resetShellBridge(): void {
  wrappers = new WeakMap();
}

// 外观能力的判据：十成员齐全（仍是「有外壳」的判据）且另有 getAppearance 函数。
// 只有十个成员的旧外壳仍被认作有外壳，但外观能力按没有处理。
function shellWithAppearance(): Record<string, unknown> | null {
  const value = window.themisShell;
  if (!isCompleteShell(value)) return null;
  if (typeof (value as Record<string, unknown>).getAppearance !== 'function') return null;
  return value as Record<string, unknown>;
}

// 逐字段校验：theme 只认三种，非法取缺省暗；density 只认两种，非法取缺省标准。
function readAppearance(value: unknown): ShellAppearance | null {
  if (value === null || typeof value !== 'object') return null;
  const raw = value as { theme?: unknown; density?: unknown };
  const theme = raw.theme === 'light' || raw.theme === 'system' ? raw.theme : 'dark';
  const density = raw.density === 'compact' ? 'compact' : 'standard';
  return { theme, density };
}

// 外壳页的当前外观：同步读一次。没有外观能力、抛错、回值不是对象都回 null，不抛到调用方。
export function shellAppearanceNow(): ShellAppearance | null {
  const shell = shellWithAppearance();
  if (shell === null) return null;
  try {
    return readAppearance((shell.getAppearance as () => unknown)());
  } catch {
    return null;
  }
}

// 订阅外壳的外观广播：经原对象的 on('appearance', listener)（Electron 的事件对象不过桥，监听只收外观一个实参）。
// 退订不是函数、on 抛错都回空退订函数；退订函数真的能退——调过之后监听不再收到事件。
export function shellOnAppearance(listener: (appearance: ShellAppearance) => void): () => void {
  const shell = shellWithAppearance();
  if (shell === null) return () => {};
  let live = true;
  const forward = (appearance: ShellAppearance): void => {
    if (live) listener(appearance);
  };
  try {
    const off = (shell.on as (event: 'appearance', fn: (appearance: ShellAppearance) => void) => unknown)(
      'appearance',
      forward,
    );
    return () => {
      live = false;
      if (typeof off === 'function') (off as () => void)();
    };
  } catch {
    return () => {};
  }
}
