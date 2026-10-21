// 首次启动的依次检查规则（src/shellpages/firstRunModel.ts）：纯函数，输入 ShellState 与最近一次 pick 的结果，输出四步模型。
// 四步：选择仓库、Python、kit、本机服务（站主 C3：不做第 5 步「工人」，工人是否就绪要从服务取，外壳页不读服务）。
// 依次检查：前一步没通过，后面「等待上一步」并置灰；退出码说明共用 exitCodes.ts（首句在视图里经 exitCodes 取）。
import type { PickOutcome, ShellState } from './themisShell';

export type StepStatus = 'pass' | 'fail' | 'wait' | 'starting';

export type StepErrorKind = 'not-git' | 'no-agent' | 'no-python' | 'no-kit' | 'exit-1' | 'exit-2' | 'exit-other';

export interface StepError {
  kind: StepErrorKind;
  /** not-git/no-agent 的仓库路径；no-python/no-kit 的被拒路径。 */
  path?: string;
  /** exit-other 的退出码。 */
  code?: number;
}

export interface StepModel {
  status: StepStatus;
  value: string;
  /** 第 4 步的值元素带 aria-live=polite。 */
  live: boolean;
  /** 等待上一步时置灰。 */
  dimmed: boolean;
  /** 第 1 步的操作：没有仓库 [选择…]、有仓库 [更换…]。 */
  action?: 'choose' | 'change';
  error?: StepError;
}

export interface Picks {
  repo?: PickOutcome;
  python?: PickOutcome;
  kit?: PickOutcome;
}

export interface FirstRunModel {
  steps: StepModel[];
  /** 要启动的仓库 id（保存的那个，或当前仓库）。 */
  repoToStart: string | null;
  /** 前三步是否都通过。 */
  steps123pass: boolean;
  /** 四步是否都通过（服务 running）。 */
  allPass: boolean;
  /** 是否有任一步带错误框。 */
  hasError: boolean;
  /** 第 1 步是否是「仓库未接入」。 */
  noAgent: boolean;
}

function exitError(code: number): StepError {
  if (code === 1) return { kind: 'exit-1' };
  if (code === 2) return { kind: 'exit-2' };
  return { kind: 'exit-other', code };
}

export function firstRunModel(state: ShellState, picks: Picks): FirstRunModel {
  const steps: StepModel[] = [];

  // 第 1 步：选择仓库。最近一次 pickRepo 被拒→✗（路径取被拒那个）；saved→✓（路径取保存那个）；
  // 否则看 currentRepo 与 currentRepoCheck。
  let step1: StepModel;
  let repoToStart: string | null = null;
  const repoPick = picks.repo;
  if (repoPick && repoPick.kind === 'saved') {
    step1 = { status: 'pass', value: repoPick.path, live: false, dimmed: false };
    repoToStart = repoPick.id ?? null;
  } else if (repoPick && repoPick.kind === 'rejected') {
    const kind: StepErrorKind = repoPick.problem === 'no-agent' ? 'no-agent' : 'not-git';
    step1 = { status: 'fail', value: repoPick.path, live: false, dimmed: false, error: { kind, path: repoPick.path } };
  } else {
    const cur = state.settings.currentRepo;
    const curRepo = state.settings.repos.find((r) => r.id === cur);
    if (!cur) {
      step1 = { status: 'wait', value: '还没有选择仓库', live: false, dimmed: false, action: 'choose' };
    } else if (state.currentRepoCheck === 'ok') {
      step1 = { status: 'pass', value: curRepo?.path ?? '', live: false, dimmed: false, action: 'change' };
      repoToStart = cur;
    } else {
      const kind: StepErrorKind = state.currentRepoCheck === 'no-agent' ? 'no-agent' : 'not-git';
      step1 = {
        status: 'fail',
        value: curRepo?.path ?? '',
        live: false,
        dimmed: false,
        action: 'change',
        error: { kind, path: curRepo?.path ?? '' },
      };
    }
  }
  steps.push(step1);

  // 第 2 步：Python。第 1 步没通过→等待上一步；否则 ok→✓（值是版本）、missing→✗。
  if (step1.status !== 'pass') {
    steps.push({ status: 'wait', value: '等待上一步', live: false, dimmed: true });
  } else if (state.python.status === 'ok') {
    steps.push({ status: 'pass', value: state.python.version, live: false, dimmed: false });
  } else {
    const pyPick = picks.python;
    const path = pyPick && pyPick.kind === 'rejected' ? pyPick.path : undefined;
    steps.push({
      status: 'fail',
      value: state.python.path || state.python.version || '—',
      live: false,
      dimmed: false,
      error: { kind: 'no-python', path },
    });
  }

  // 第 3 步：kit。同理；值写「2.12.0（仓库里装好的）」或「2.12.0（外部目录）」。
  if (steps[1].status !== 'pass') {
    steps.push({ status: 'wait', value: '等待上一步', live: false, dimmed: true });
  } else if (state.kit.status === 'ok') {
    const src = state.kit.source === 'repo' ? '仓库里装好的' : '外部目录';
    steps.push({ status: 'pass', value: `${state.kit.version}（${src}）`, live: false, dimmed: false });
  } else {
    const kitPick = picks.kit;
    const path = kitPick && kitPick.kind === 'rejected' ? kitPick.path : undefined;
    steps.push({
      status: 'fail',
      value: state.kit.version || '—',
      live: false,
      dimmed: false,
      error: { kind: 'no-kit', path },
    });
  }

  // 第 4 步：本机服务。前三步没全过→等待上一步；starting→转圈；running→✓；exited→✗；idle→等待启动。
  const steps123pass = steps[0].status === 'pass' && steps[1].status === 'pass' && steps[2].status === 'pass';
  if (!steps123pass) {
    steps.push({ status: 'wait', value: '等待上一步', live: true, dimmed: true });
  } else {
    const svc = state.service;
    if (svc.kind === 'starting') {
      steps.push({ status: 'starting', value: '正在启动…', live: true, dimmed: false });
    } else if (svc.kind === 'running') {
      steps.push({ status: 'pass', value: `已启动 · pid ${svc.pid}`, live: true, dimmed: false });
    } else if (svc.kind === 'exited') {
      steps.push({ status: 'fail', value: `已退出 · 退出码 ${svc.exitCode}`, live: true, dimmed: false, error: exitError(svc.exitCode) });
    } else {
      steps.push({ status: 'wait', value: '等待启动', live: true, dimmed: false });
    }
  }

  const allPass = steps.every((s) => s.status === 'pass');
  const hasError = steps.some((s) => s.error != null);
  const noAgent = step1.error?.kind === 'no-agent';

  return { steps, repoToStart, steps123pass, allPass, hasError, noAgent };
}
