// 外壳页的示意夹具（src/mock/shellpages-scenarios.ts）：11 个场景的初始状态、pick 队列与 start/restart 结果。
// 本文件是「示意」数据，取值固定，供内存桩演示各状态；路径用正斜杠，反斜杠不写进 TS 字符串。
// 接真实外壳那一片会把这些换成真实取值（过渡断言）。
import { SHELL_PID, SHELL_STARTED_AT } from './shell';
import type { PickProblem, ShellState } from '../shellpages/themisShell';

export type StartOutcome = { kind: 'running' } | { kind: 'exited'; exitCode: number } | { kind: 'stuck' };

/** pick 队列的一项模板：桩据此生成完整的 PickOutcome（saved 会带 id 与新状态）。 */
export interface PickTemplate {
  kind: 'saved' | 'rejected' | 'cancelled';
  path?: string;
  problem?: PickProblem;
}

export interface ScenarioConfig {
  base: ShellState;
  repo: PickTemplate[];
  python: PickTemplate[];
  kit: PickTemplate[];
  transcriptDir: PickTemplate[];
  /** startService / restartService 之后 1500ms 的结果。 */
  start: StartOutcome;
}

const DEMO_REPO = { id: 'demo-repo', name: 'demo-repo', path: 'C:/Projects/demo-repo', lastOpened: '2026-10-18T09:41:07' };
const DOCS_REPO = { id: 'docs-site', name: 'docs-site', path: 'C:/Projects/docs-site', lastOpened: '2026-10-15T16:20:11' };
const PY_AUTO = { status: 'ok', source: 'auto', path: 'C:/Python313/python.exe', version: '3.13.1' } as const;
const KIT_REPO = { status: 'ok', source: 'repo', path: '.agent/kit', version: '2.12.0' } as const;
const APP = { version: '0.0.0', homepage: 'https://github.com/mrQzs/ThemisTally' };

function base(over: Partial<ShellState>): ShellState {
  return {
    app: APP,
    settings: { repos: [DEMO_REPO, DOCS_REPO], currentRepo: 'demo-repo', transcriptDirs: [], theme: 'dark', density: 'standard' },
    currentRepoCheck: 'ok',
    python: PY_AUTO,
    kit: KIT_REPO,
    service: { kind: 'idle' },
    ...over,
  } as ShellState;
}

function repos(repos: ShellState['settings']['repos'], currentRepo: string | null, check: ShellState['currentRepoCheck']): Partial<ShellState> {
  return { settings: { repos, currentRepo, transcriptDirs: [], theme: 'dark', density: 'standard' }, currentRepoCheck: check };
}

const ALL_SAVED: PickTemplate[] = [{ kind: 'saved' }];

export const SHELLPAGE_SCENARIOS: Record<string, ScenarioConfig> = {
  'ready': {
    base: base({}),
    repo: [{ kind: 'saved', path: 'C:/Projects/picked-a' }],
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
  'checking': {
    base: base({}),
    repo: [{ kind: 'saved', path: 'C:/Projects/picked-a' }],
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'stuck' },
  },
  'first-launch': {
    base: base(repos([], null, null)),
    repo: [
      { kind: 'rejected', problem: 'not-git', path: 'C:/Projects/not-a-repo' },
      { kind: 'rejected', problem: 'no-agent', path: 'C:/Projects/no-agent-repo' },
      { kind: 'saved', path: 'C:/Projects/demo-repo' },
    ],
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
  'not-git': {
    base: base(repos([DEMO_REPO], 'demo-repo', 'not-git')),
    repo: ALL_SAVED,
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
  'no-agent': {
    base: base(repos([DEMO_REPO], 'demo-repo', 'no-agent')),
    repo: ALL_SAVED,
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
  'no-python': {
    base: base({ python: { status: 'missing', source: 'auto', path: '', version: '' } }),
    repo: ALL_SAVED,
    python: [{ kind: 'rejected', problem: 'python-unusable', path: 'C:/Python39/python.exe' }, { kind: 'saved' }],
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
  'no-kit': {
    base: base({ kit: { status: 'missing', source: 'repo', path: '', version: '' } }),
    repo: ALL_SAVED,
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
  'exit-1': {
    base: base({}),
    repo: ALL_SAVED,
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'exited', exitCode: 1 },
  },
  'exit-2': {
    base: base({}),
    repo: ALL_SAVED,
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'exited', exitCode: 2 },
  },
  'crash': {
    base: base({ service: { kind: 'exited', repo: 'demo-repo', exitCode: 3, at: Date.parse('2026-10-18T09:41:07') } }),
    repo: ALL_SAVED,
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
  'custom': {
    base: base({
      python: { status: 'ok', source: 'custom', path: 'C:/Python312/python.exe', version: '3.12.4' },
      kit: { status: 'ok', source: 'external', path: 'C:/ThemisTally-kit', version: '2.12.0' },
      settings: {
        repos: [DEMO_REPO, DOCS_REPO],
        currentRepo: 'demo-repo',
        transcriptDirs: [
          { id: 'dir-main', path: 'C:/Transcripts/main' },
          { id: 'dir-archive', path: 'C:/Transcripts/archive' },
        ],
        theme: 'dark',
        density: 'compact',
      },
    }),
    repo: ALL_SAVED,
    python: ALL_SAVED,
    kit: ALL_SAVED,
    transcriptDir: ALL_SAVED,
    start: { kind: 'running' },
  },
};

export const SHELLPAGE_SCENARIO_NAMES: readonly string[] = Object.keys(SHELLPAGE_SCENARIOS);

// running 的 pid 与 startedAt 取自 src/mock/shell.ts（过渡断言）。
export const RUNNING_PID = SHELL_PID;
export const RUNNING_STARTED_AT = SHELL_STARTED_AT;
