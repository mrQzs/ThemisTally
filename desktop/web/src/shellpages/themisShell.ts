// themisShell：桌面外壳宿主接口的类型（架构文档 D10 的 window.themisShell，UI 文档 8.9 :1122 的方法名）。
// 本片只有类型，不导出值；本片不写 window.themisShell 的全局声明，也不读它（接真实外壳那一片再做）。
// 十个成员：9 个方法加 on；没有切换窗口的函数（8.9 没有，站主 Q2-A，本片不加）。
// PickOutcome 三种：cancelled / saved / rejected；problem 四种；服务四种状态：idle / starting / running / exited。

/** 仓库自检结果：当前仓库是否可用；没有当前仓库时 null。 */
export type RepoCheck = 'ok' | 'not-git' | 'no-agent';

/** 选择被拒的原因：仓库不是 Git、仓库未接入、python 不可用、kit 不可用。 */
export type PickProblem = 'not-git' | 'no-agent' | 'python-unusable' | 'kit-unusable';

/** 一次选择的结果：取消、已保存（带路径、可选 id 与新状态）、被拒（带原因与路径）。 */
export type PickOutcome =
  | { kind: 'cancelled' }
  | { kind: 'saved'; path: string; id?: string; state: ShellState }
  | { kind: 'rejected'; problem: PickProblem; path: string };

export interface RepoEntry {
  id: string;
  name: string;
  path: string;
  /** 上次打开的 ISO 时刻；从未打开过为 null。 */
  lastOpened: string | null;
}

export interface TranscriptDirEntry {
  id: string;
  path: string;
}

/** 本机服务的四种状态。starting 带 repo；running 带 repo/pid/startedAt；exited 带 repo/exitCode/at。 */
export type ServiceState =
  | { kind: 'idle' }
  | { kind: 'starting'; repo: string }
  | { kind: 'running'; repo: string; pid: number; startedAt: string }
  | { kind: 'exited'; repo: string; exitCode: number; at: number };

export interface ShellSettings {
  repos: RepoEntry[];
  /** 当前仓库的 id；没有当前仓库为 null。 */
  currentRepo: string | null;
  transcriptDirs: TranscriptDirEntry[];
  theme: 'system' | 'light' | 'dark';
  density: 'standard' | 'compact';
}

export interface ShellState {
  app: { version: string; homepage: string };
  settings: ShellSettings;
  /** 当前仓库的自检；没有当前仓库时 null。 */
  currentRepoCheck: RepoCheck | null;
  python: { status: 'ok' | 'missing'; source: 'auto' | 'custom'; path: string; version: string };
  kit: { status: 'ok' | 'missing'; source: 'repo' | 'external'; path: string; version: string };
  service: ServiceState;
}

/** saveSettings 只认这六个键，不接受任何路径；别的键、取值不对、id 不存在都被拒，状态不变。 */
export interface SettingsPatch {
  theme?: 'system' | 'light' | 'dark';
  density?: 'standard' | 'compact';
  removeRepo?: string;
  removeTranscriptDir?: string;
  resetPython?: true;
  resetKit?: true;
}

export interface ThemisShell {
  getState(): Promise<ShellState>;
  pickRepo(): Promise<PickOutcome>;
  pickPython(): Promise<PickOutcome>;
  pickKit(): Promise<PickOutcome>;
  pickTranscriptDir(): Promise<PickOutcome>;
  saveSettings(patch: SettingsPatch): Promise<ShellState>;
  startService(repo: string): Promise<void>;
  restartService(): Promise<void>;
  openExternal(url: string): Promise<void>;
  on(event: 'service-state', listener: (state: ShellState['service']) => void): () => void;
}
