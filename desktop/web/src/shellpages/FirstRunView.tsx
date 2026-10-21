// 首次启动视图（src/shellpages/FirstRunView.tsx）：卡片里头部 + 四步列表 + 底栏（结构照首启画布 :294–361）。
// 四步依次检查（规则在 firstRunModel）；前三步通过且服务 idle 时自动 startService 一次；错误框挂在出错那一步下面；
// 退出码 1 的「切换到那个窗口」是禁用按钮（站主 Q2-A）；[进入] 四步全过才可用。document.title「首次启动 · Themis Tally」。
import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, CommandLine } from '../components';
import { CircleCheckIcon, CircleDashedIcon, CircleXIcon, LoaderCircleIcon } from '../icons';
import { Logo } from '../shell/Logo';
import { DisabledAction } from '../shell/DisabledAction';
import type { PickOutcome, ShellState } from './themisShell';
import type { ThemisShell } from './themisShell';
import { firstRunModel, type Picks, type StepError, type StepModel, type StepStatus } from './firstRunModel';
import { firstRunHeadline } from './exitCodes';
import { copyText, COPY_RESULT_TEXT, type CopyResult } from './copy';
import { ArrowRightIcon } from './icons';
import './first-run.css';

const STEP_NAMES = ['选择仓库', 'Python', 'kit', '本机服务'];

export interface FirstRunViewProps {
  shell: ThemisShell;
  navigate: (path: string) => void;
}

const ICON_LABEL: Record<StepStatus, string> = {
  pass: '通过',
  fail: '未通过',
  starting: '正在启动',
  wait: '等待',
};

function StepIcon({ status }: { status: StepStatus }) {
  if (status === 'pass') return <CircleCheckIcon width={18} height={18} />;
  if (status === 'fail') return <CircleXIcon width={18} height={18} />;
  if (status === 'starting') return <LoaderCircleIcon width={18} height={18} className="tt-spin" />;
  return <CircleDashedIcon width={18} height={18} />;
}

export function FirstRunView({ shell, navigate }: FirstRunViewProps) {
  const [state, setState] = useState<ShellState | null>(null);
  const [picks, setPicks] = useState<Picks>({});
  const [copyResult, setCopyResult] = useState<CopyResult | null>(null);
  const requestedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    document.title = '首次启动 · Themis Tally';
  }, []);

  // 先订阅 service-state 再调 getState，之后以最近一次 service-state 为准；卸载时取消订阅。
  useEffect(() => {
    const off = shell.on('service-state', (svc) => {
      setState((prev) => (prev ? { ...prev, service: svc } : prev));
    });
    shell.getState().then(setState).catch(() => {});
    return off;
  }, [shell]);

  const model = state ? firstRunModel(state, picks) : null;

  // 自动启动：前三步通过且（service idle，或 service.repo 不是要启动的仓库）时调一次；exited 不自动重启。
  useEffect(() => {
    if (!state || !model) return;
    if (!model.steps123pass || !model.repoToStart) return;
    if (state.service.kind === 'exited') return;
    const svcRepo = state.service.kind === 'idle' ? null : state.service.repo;
    const needStart = state.service.kind === 'idle' || svcRepo !== model.repoToStart;
    if (needStart && !requestedRef.current.has(model.repoToStart)) {
      requestedRef.current.add(model.repoToStart);
      shell.startService(model.repoToStart);
    }
  }, [state, model, shell]);

  const applyPick = useCallback((which: keyof Picks, r: PickOutcome) => {
    setPicks((p) => ({ ...p, [which]: r }));
    if (r.kind === 'saved') setState(r.state);
  }, []);

  const onPickRepo = useCallback(async () => {
    setCopyResult(null);
    applyPick('repo', await shell.pickRepo());
  }, [shell, applyPick]);

  const onPickPython = useCallback(async () => {
    applyPick('python', await shell.pickPython());
  }, [shell, applyPick]);

  const onPickKit = useCallback(async () => {
    applyPick('kit', await shell.pickKit());
  }, [shell, applyPick]);

  const onRestart = useCallback(() => {
    if (model?.repoToStart) shell.startService(model.repoToStart);
  }, [shell, model]);

  const onCopy = useCallback(
    async (text: string) => {
      setCopyResult(await copyText(text));
    },
    [],
  );

  const footNote = model
    ? model.allPass
      ? '四项检查都通过了'
      : model.noAgent
        ? '接入后点“重新选择”再检查一次'
        : model.hasError
          ? '处理好上面标出的问题，再接着检查'
          : '四步依次检查，全部通过后才能进入'
    : '四步依次检查，全部通过后才能进入';

  const renderError = (error: StepError, index: number) => {
    const small = { variant: 'secondary' as const, size: 'sm' as const };
    return (
      <div key={`err-${index}`} className="tt-fr__err" role="alert" data-step-error={index}>
        {error.kind === 'not-git' && (
          <>
            <span>这个文件夹不是 Git 仓库。</span>
            <span>换一个 Git 仓库再试。</span>
            <div>
              <Button {...small} onClick={onPickRepo}>
                重新选择
              </Button>
            </div>
          </>
        )}
        {error.kind === 'no-agent' && (
          <>
            <span>这个仓库还没有接入 Themis Tally。</span>
            <span>在终端里运行下面的命令接入，然后重新选择。</span>
            <CommandLine size="md" command={`python <ThemisTally>/scripts/kit_install.py install ${error.path ?? ''}`} onCopy={onCopy} />
            {copyResult && <span className="tt-fr__copyres">{COPY_RESULT_TEXT[copyResult]}</span>}
            <div>
              <Button {...small} onClick={onPickRepo}>
                重新选择
              </Button>
            </div>
          </>
        )}
        {error.kind === 'no-python' && (
          <>
            <span>找不到 Python 3.10 及以上。</span>
            <span>安装后重试，或指定 python.exe。</span>
            {error.path && <span>{`所选的 python.exe 不能用：${error.path}（要能运行，且是 3.10 及以上）`}</span>}
            <div>
              <Button {...small} onClick={onPickPython}>
                指定 python.exe…
              </Button>
            </div>
          </>
        )}
        {error.kind === 'no-kit' && (
          <>
            <span>找不到 Themis Tally 的 kit。</span>
            <span>在仓库里用 kit_install 装好，或指定 kit 目录。</span>
            {error.path && <span>{`所选目录里的 kit 不能用：${error.path}（要能运行 pi_dispatch.py --version）`}</span>}
            <div>
              <Button {...small} onClick={onPickKit}>
                指定 kit 目录…
              </Button>
            </div>
          </>
        )}
        {error.kind === 'exit-1' && (
          <>
            <span>{firstRunHeadline(1)}</span>
            <span>切换到那个窗口继续。</span>
            <div>
              <DisabledAction {...small} label="切换到那个窗口" reason="接入真实外壳后可用" />
            </div>
          </>
        )}
        {error.kind === 'exit-2' && <span>{firstRunHeadline(2)}</span>}
        {error.kind === 'exit-other' && (
          <>
            <span>{firstRunHeadline(error.code ?? 0)}</span>
            <span>重新启动；反复出现时打开设置检查 Python 与 kit。</span>
            <div>
              <Button {...small} onClick={onRestart}>
                重新启动
              </Button>
            </div>
          </>
        )}
      </div>
    );
  };

  const renderStep = (step: StepModel, index: number) => (
    <li key={index} className={`tt-fr__step${step.dimmed ? ' tt-fr__step--wait' : ''}`} data-step={index + 1} data-status={step.status}>
      <div className="tt-fr__row">
        <span className="tt-fr__no" aria-hidden="true">
          {index + 1}
        </span>
        <span className="tt-fr__name">{STEP_NAMES[index]}</span>
        {index === 0 ? (
          <code className="tt-fr__path">{step.value}</code>
        ) : step.live ? (
          <span className="tt-fr__val" aria-live="polite">
            {step.value}
          </span>
        ) : (
          <span className="tt-fr__val">{step.value}</span>
        )}
        {step.action === 'choose' && (
          <Button variant="ghost" size="sm" onClick={onPickRepo}>
            选择…
          </Button>
        )}
        {step.action === 'change' && (
          <Button variant="ghost" size="sm" onClick={onPickRepo}>
            更换…
          </Button>
        )}
        <span className={`tt-fr__icon tt-fr__icon--${step.status}`} role="img" aria-label={ICON_LABEL[step.status]}>
          <StepIcon status={step.status} />
        </span>
      </div>
      {step.error && renderError(step.error, index)}
    </li>
  );

  return (
    <section className="tt-fr" aria-labelledby="tt-fr-title">
      <div className="tt-fr__head">
        <span className="tt-fr__logo" aria-hidden="true">
          <Logo />
        </span>
        <h1 id="tt-fr-title" className="tt-fr__title">
          欢迎使用 Themis Tally
        </h1>
        <p className="tt-fr__sub">选一个已经接入 Themis Tally 的 Git 仓库</p>
      </div>
      <ol className="tt-fr__steps">{model ? model.steps.map(renderStep) : null}</ol>
      <div className="tt-fr__foot">
        <span className="tt-fr__note">{footNote}</span>
        <Button variant="primary" size="lg" disabled={!model?.allPass} onClick={() => navigate('/overview')}>
          进入
          <ArrowRightIcon width={16} height={16} />
        </Button>
      </div>
    </section>
  );
}
