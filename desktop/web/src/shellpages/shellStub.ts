// 内存桩（src/shellpages/shellStub.ts）：按场景给出 ThemisShell 的全部行为，状态只在内存。
// getState 与各返回值深拷贝；各方法返回已兑现或已被拒的 Promise，不经计时器（api.ts :90–96 同法）；
// pick 按场景队列逐个给出、用完重复最后一个；start/restart 在调用里同步发 starting、1500ms 后按场景发 running 或 exited；
// 只在 start、restart 之后才排计时器；dispose 清掉计时器与监听；openExternal 只记下网址，不打开任何东西。
import type { PickOutcome, ServiceState, SettingsPatch, ShellState, ThemisShell } from './themisShell';
import { SHELLPAGE_SCENARIOS, RUNNING_PID, RUNNING_STARTED_AT } from '../mock/shellpages-scenarios';

export interface ShellStub extends ThemisShell {
  dispose(): void;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function basename(path: string): string {
  const parts = path.split('/').filter((s) => s.length > 0);
  return parts.length ? parts[parts.length - 1] : path;
}

const PY_PICKED_PATH = 'C:/Python313/python.exe';
const PY_PICKED_VERSION = '3.13.1';
const KIT_PICKED_PATH = 'C:/ThemisTally-kit';
const KIT_PICKED_VERSION = '2.12.0';
const DIR_PICKED_PATH = 'C:/Transcripts/picked';
const START_MS = 1500;

const VALID_THEME = ['system', 'light', 'dark'];
const VALID_DENSITY = ['standard', 'compact'];
const PATCH_KEYS = ['theme', 'density', 'removeRepo', 'removeTranscriptDir', 'resetPython', 'resetKit'];

export function createShellStub(scenario: string): ShellStub {
  const config = SHELLPAGE_SCENARIOS[scenario] ?? SHELLPAGE_SCENARIOS.ready;
  const state: ShellState = clone(config.base);
  const listeners = new Set<(svc: ServiceState) => void>();
  let startTimer: ReturnType<typeof setTimeout> | null = null;
  let repoIdx = 0;
  let pyIdx = 0;
  let kitIdx = 0;
  let dirIdx = 0;
  let dirSeq = 0;

  const emit = (svc: ServiceState) => {
    state.service = svc;
    listeners.forEach((l) => l(svc));
  };

  const uniqueRepoId = (base: string): string => {
    if (!state.settings.repos.some((r) => r.id === base)) return base;
    let n = 2;
    while (state.settings.repos.some((r) => r.id === `${base}-${n}`)) n += 1;
    return `${base}-${n}`;
  };

  const scheduleResolve = (repo: string) => {
    if (startTimer) clearTimeout(startTimer);
    startTimer = setTimeout(() => {
      startTimer = null;
      if (config.start.kind === 'running') {
        emit({ kind: 'running', repo, pid: RUNNING_PID, startedAt: RUNNING_STARTED_AT });
      } else if (config.start.kind === 'exited') {
        emit({ kind: 'exited', repo, exitCode: config.start.exitCode, at: Date.now() });
      }
      // stuck：不发后续事件，停在 starting。
    }, START_MS);
  };

  const nextTemplate = <T extends { kind: string }>(queue: T[], idx: number): T => {
    if (queue.length === 0) return { kind: 'cancelled' } as T;
    return queue[Math.min(idx, queue.length - 1)];
  };

  const getState = (): Promise<ShellState> => Promise.resolve(clone(state));

  const pickRepo = (): Promise<PickOutcome> => {
    const tpl = nextTemplate(config.repo, repoIdx);
    repoIdx += 1;
    if (tpl.kind === 'cancelled') return Promise.resolve({ kind: 'cancelled' });
    if (tpl.kind === 'rejected') {
      return Promise.resolve({ kind: 'rejected', problem: tpl.problem ?? 'not-git', path: tpl.path ?? '' });
    }
    const path = tpl.path ?? 'C:/Projects/picked-repo';
    const name = basename(path);
    const id = uniqueRepoId(name);
    state.settings.repos.push({ id, name, path, lastOpened: null });
    return Promise.resolve({ kind: 'saved', path, id, state: clone(state) });
  };

  const pickPython = (): Promise<PickOutcome> => {
    const tpl = nextTemplate(config.python, pyIdx);
    pyIdx += 1;
    if (tpl.kind === 'cancelled') return Promise.resolve({ kind: 'cancelled' });
    if (tpl.kind === 'rejected') {
      return Promise.resolve({ kind: 'rejected', problem: tpl.problem ?? 'python-unusable', path: tpl.path ?? '' });
    }
    const path = tpl.path ?? PY_PICKED_PATH;
    state.python = { status: 'ok', source: 'custom', path, version: PY_PICKED_VERSION };
    return Promise.resolve({ kind: 'saved', path, state: clone(state) });
  };

  const pickKit = (): Promise<PickOutcome> => {
    const tpl = nextTemplate(config.kit, kitIdx);
    kitIdx += 1;
    if (tpl.kind === 'cancelled') return Promise.resolve({ kind: 'cancelled' });
    if (tpl.kind === 'rejected') {
      return Promise.resolve({ kind: 'rejected', problem: tpl.problem ?? 'kit-unusable', path: tpl.path ?? '' });
    }
    const path = tpl.path ?? KIT_PICKED_PATH;
    state.kit = { status: 'ok', source: 'external', path, version: KIT_PICKED_VERSION };
    return Promise.resolve({ kind: 'saved', path, state: clone(state) });
  };

  const pickTranscriptDir = (): Promise<PickOutcome> => {
    const tpl = nextTemplate(config.transcriptDir, dirIdx);
    dirIdx += 1;
    if (tpl.kind === 'cancelled') return Promise.resolve({ kind: 'cancelled' });
    if (tpl.kind === 'rejected') {
      return Promise.resolve({ kind: 'rejected', problem: tpl.problem ?? 'kit-unusable', path: tpl.path ?? '' });
    }
    const path = tpl.path ?? DIR_PICKED_PATH;
    dirSeq += 1;
    const id = `picked-dir-${dirSeq}`;
    state.settings.transcriptDirs.push({ id, path });
    return Promise.resolve({ kind: 'saved', path, id, state: clone(state) });
  };

  const validatePatch = (patch: SettingsPatch): string | null => {
    for (const key of Object.keys(patch)) {
      if (!PATCH_KEYS.includes(key)) return `不认识的设置项：${key}`;
    }
    if ('theme' in patch && !VALID_THEME.includes(patch.theme as string)) return 'theme 取值不对';
    if ('density' in patch && !VALID_DENSITY.includes(patch.density as string)) return 'density 取值不对';
    if ('removeRepo' in patch) {
      const id = patch.removeRepo as string;
      if (!state.settings.repos.some((r) => r.id === id)) return '仓库 id 不存在';
      if (id === state.settings.currentRepo) return '不能移除当前仓库';
    }
    if ('removeTranscriptDir' in patch) {
      const id = patch.removeTranscriptDir as string;
      if (!state.settings.transcriptDirs.some((d) => d.id === id)) return '目录 id 不存在';
    }
    if ('resetPython' in patch && patch.resetPython !== true) return 'resetPython 只能为 true';
    if ('resetKit' in patch && patch.resetKit !== true) return 'resetKit 只能为 true';
    return null;
  };

  const saveSettings = (patch: SettingsPatch): Promise<ShellState> => {
    const err = validatePatch(patch);
    if (err) return Promise.reject(new Error(err));
    if ('theme' in patch) state.settings.theme = patch.theme as ShellState['settings']['theme'];
    if ('density' in patch) state.settings.density = patch.density as ShellState['settings']['density'];
    if ('removeRepo' in patch) {
      state.settings.repos = state.settings.repos.filter((r) => r.id !== patch.removeRepo);
    }
    if ('removeTranscriptDir' in patch) {
      state.settings.transcriptDirs = state.settings.transcriptDirs.filter((d) => d.id !== patch.removeTranscriptDir);
    }
    if ('resetPython' in patch) {
      state.python = { status: 'ok', source: 'auto', path: PY_PICKED_PATH, version: PY_PICKED_VERSION };
    }
    if ('resetKit' in patch) {
      state.kit = { status: 'ok', source: 'repo', path: '.agent/kit', version: KIT_PICKED_VERSION };
    }
    return Promise.resolve(clone(state));
  };

  const startService = (repo: string): Promise<void> => {
    if (!state.settings.repos.some((r) => r.id === repo)) {
      return Promise.reject(new Error('repo 不在列表里'));
    }
    const svc = state.service;
    if ((svc.kind === 'starting' || svc.kind === 'running') && svc.repo === repo) {
      return Promise.resolve();
    }
    emit({ kind: 'starting', repo });
    scheduleResolve(repo);
    return Promise.resolve();
  };

  const restartService = (): Promise<void> => {
    const repo = state.settings.currentRepo ?? '';
    emit({ kind: 'starting', repo });
    scheduleResolve(repo);
    return Promise.resolve();
  };

  const openExternal = (url: string): Promise<void> => {
    if (!/^https?:\/\//.test(url)) return Promise.reject(new Error('只允许 http 与 https'));
    return Promise.resolve();
  };

  const on = (event: 'service-state', listener: (svc: ServiceState) => void): (() => void) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  };

  const dispose = () => {
    if (startTimer) clearTimeout(startTimer);
    startTimer = null;
    listeners.clear();
  };

  return { getState, pickRepo, pickPython, pickKit, pickTranscriptDir, saveSettings, startService, restartService, openExternal, on, dispose };
}
