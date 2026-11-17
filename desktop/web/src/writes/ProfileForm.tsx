// profile 新建/编辑两用的表单对话框（合同第三、四、六节）：入口文件只放按钮，字段、提示与标题文字一律在这里。
// 底部实时显示内核预览（命令、警告、报错原文）；[确认…] 交给 A 片确认框走「预览 → 确认 → 执行 → 重读 → 终态」。
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Button, Dialog, SegmentedControl, Select, Tag, TextField, dispatchCommand } from '../components';
import { XIcon } from '../icons';
import { getQuizsProviders, getRuntimes, type WriteAction, type WriteArgs } from '../api';
import { useWriteFlow, type WriteSpec } from './useWriteFlow';
import { WriteFlow } from './WriteConfirmDialog';
import { useLivePreview } from './useLivePreview';
import { sameStringArray, validEnvName, validId, validModel } from './profileRules';
import {
  QUIZS_LEVELS,
  isQuizsRuntime,
  modelInArchive,
  quizsProviderOptions,
  thinkingAllowed,
  thinkingLevelsFor,
  type QuizsProviderOption,
} from './quizsProfile';
import './profile-form.css';

// 逐字提示（合同第三节）：只在这里出现，入口文件不写（T013 / T022 S15 / D09）。
const ID_ERROR = '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
const MODEL_ERROR = '模型要写成 provider/model，两段都只能用字母、数字与 . _ : / @ + -';
const ENV_ERROR = '变量名只能用字母、数字与下划线，不能以数字开头，最长 128 个字符';
const MODEL_HELP = '手填的模型没有核实';
const ENV_HELP = '值在‘凭据’页录入';

// quizs 分支的逐字文案（合同第四、五节）：档案三种读不出的原因、档案外的模型、档位越界与凭据说明。
const QUIZS_READING = '正在读 Quizs 的提供方档案…';
const QUIZS_READ_FAILED = '读不出 Quizs 的提供方档案';
const QUIZS_NO_PROVIDERS = 'Quizs 没有列出可用的提供方档案';
const QUIZS_MODEL_OUTSIDE = '不在 Quizs 已批准的档案里';
const QUIZS_CREDS_NOTE = '凭据由 Quizs 保管';

const THINKING_OPTIONS = [
  { value: 'off', label: 'off' },
  { value: 'minimal', label: 'minimal' },
  { value: 'low', label: 'low' },
  { value: 'medium', label: 'medium' },
  { value: 'high', label: 'high' },
  { value: 'xhigh', label: 'xhigh' },
  { value: 'max', label: 'max' },
];

interface LooseProfile {
  id: string;
  runtime?: string | null;
  provider?: string | null;
  model?: string | null;
  options?: { thinking?: string | null } | null;
  credential_env?: readonly string[] | null;
}

// runtime 下拉的一行：id 是下拉的取值，adapter 用来认 quizs（不看 id）。
interface RuntimeRow {
  id: string;
  adapter: string;
}

// quizs 运行时的提供方档案：读取中、读到（可能一项都转不出来）与读不出三种状态。
type QuizsArchive =
  | { kind: 'loading' }
  | { kind: 'ready'; options: QuizsProviderOption[] }
  | { kind: 'failed'; reason: string };

interface FormInitial {
  id: string;
  runtime: string;
  model: string;
  thinking: string;
  creds: string[];
}

function makeInitial(mode: 'new' | 'edit', profile?: LooseProfile): FormInitial {
  if (mode === 'edit' && profile) {
    return {
      id: profile.id,
      runtime: profile.runtime ?? '',
      // 模型初值按 provider/model 拼成一段（服务侧 validModel 就是按整段校验的）。
      model: `${profile.provider ?? ''}/${profile.model ?? ''}`,
      // thinking 原来缺省时界面显示 high（第六节）；没有就显示 high。
      thinking: profile.options?.thinking ?? 'high',
      creds: [...(profile.credential_env ?? [])],
    };
  }
  return { id: '', runtime: '', model: '', thinking: 'high', creds: [] };
}

function ProfileFormDialog({
  open,
  onClose,
  mode,
  profile,
  reload,
}: {
  open: boolean;
  onClose: () => void;
  mode: 'new' | 'edit';
  profile?: LooseProfile;
  reload?: () => Promise<void>;
}) {
  const { start, flow } = useWriteFlow(reload);
  const [initial] = useState<FormInitial>(() => makeInitial(mode, profile));
  const [id, setId] = useState(initial.id);
  const [runtime, setRuntime] = useState(initial.runtime);
  const [model, setModel] = useState(initial.model);
  const [thinking, setThinking] = useState(initial.thinking);
  const [creds, setCreds] = useState<string[]>(initial.creds);
  const [envInput, setEnvInput] = useState('');
  const [envError, setEnvError] = useState<string | null>(null);
  const [runtimes, setRuntimes] = useState<RuntimeRow[]>([]);
  // null：没读过档案（非 quizs 运行时，或对话框还没开）。
  const [archive, setArchive] = useState<QuizsArchive | null>(null);
  // quizs 分支的档位改动口径：用户点过档位段就算改动（点回初值也照传）。
  const [thinkingTouched, setThinkingTouched] = useState(false);

  const action: WriteAction = mode === 'new' ? 'profile.add' : 'profile.edit';

  // 对话框打开时由 src/writes 调 getRuntimes() 填 runtime 下拉；新建模式缺省选第一个已登记的 runtime。
  useEffect(() => {
    if (!open) return;
    let alive = true;
    getRuntimes().then(
      (env) => {
        if (!alive) return;
        const rows: RuntimeRow[] = env.ok && env.data ? env.data.runtimes.map((r) => ({ id: r.id, adapter: r.adapter })) : [];
        setRuntimes(rows);
        if (mode === 'new') setRuntime((cur) => cur || rows[0]?.id || '');
      },
      () => {
        if (alive) setRuntimes([]);
      },
    );
    return () => {
      alive = false;
    };
  }, [open, mode]);

  // quizs 运行时的提供方档案：对话框打开、且所选运行时的适配器是 quizs 时读一次（每次打开只读一次，
  // 几个 quizs 运行时共用同一份；非 quizs 一次都不调）。迟到的结果按 alive 丢弃，重新打开会重读。
  // 反直觉处：结果还在路上时 effect 重跑（运行时列表换了数组、换了运行时）会把这次读作废，这时要把
  // 「本次打开已经读过档案」的标记复位，重跑照样再读一次；结果已经回来（读到或读不出都算）就不复位，
  // 不多读。
  const archiveRead = useRef(false);
  useEffect(() => {
    if (!open) {
      archiveRead.current = false;
      setArchive(null);
      setThinkingTouched(false);
      return;
    }
    if (!isQuizsRuntime(runtime, runtimes) || archiveRead.current) return;
    archiveRead.current = true;
    let alive = true;
    // settled：这次读的结果回来没有（成功或失败都算回来）。
    let settled = false;
    setArchive({ kind: 'loading' });
    getQuizsProviders().then(
      (env) => {
        settled = true; // 必须在 if (!alive) return; 之前：作废的读也算结果回来，不许让标记复位
        if (!alive) return;
        if (!env.ok || env.data == null) {
          const first = env.messages.length > 0 ? env.messages[0] : null;
          setArchive({ kind: 'failed', reason: first === null ? QUIZS_READ_FAILED : `${QUIZS_READ_FAILED}：${first}` });
          return;
        }
        const options = quizsProviderOptions(env.data.providers);
        setArchive(options.length > 0 ? { kind: 'ready', options } : { kind: 'failed', reason: QUIZS_NO_PROVIDERS });
      },
      () => {
        settled = true;
        if (alive) setArchive({ kind: 'failed', reason: QUIZS_READ_FAILED });
      },
    );
    return () => {
      alive = false;
      // 结果还在路上就被重跑：复位「已读过」，重跑时照样读；结果已经回来的不复位（否则每次重跑都重读）。
      if (!settled) archiveRead.current = false;
    };
  }, [open, runtime, runtimes]);

  // 成功（重读之后弹轻提示）才清空表单；执行失败不清，重开还在原来的值。
  const aPieceWasOpen = useRef(false);
  const resetForm = () => {
    setId(initial.id);
    setRuntime(initial.runtime);
    setModel(initial.model);
    setThinking(initial.thinking);
    setCreds([...initial.creds]);
    setEnvInput('');
    setEnvError(null);
  };
  useEffect(() => {
    if (aPieceWasOpen.current && !flow.open && flow.toast) resetForm();
    aPieceWasOpen.current = flow.open;
  }, [flow.open, flow.toast]);

  const idValid = validId(id);
  const modelValid = validModel(model);
  const fieldValid = idValid && modelValid;
  const hasRuntime = runtimes.length > 0;
  const quizs = isQuizsRuntime(runtime, runtimes);
  // quizs 分支的凭据由 Quizs 保管：界面不加也不撤，改动检测只对非 quizs 算。
  const credsChanged = !quizs && !sameStringArray(creds, initial.creds);
  // 凭据变量改成空的：服务侧空数组不合法，本片不做清空。
  const clearingCred = mode === 'edit' && !quizs && credsChanged && creds.length === 0 && initial.creds.length > 0;
  const runtimeChanged = mode === 'edit' && runtime !== initial.runtime;
  const modelChanged = mode === 'edit' && model !== initial.model;
  const thinkingChanged = thinking !== initial.thinking;
  const hasChanges = mode === 'new' || runtimeChanged || modelChanged || thinkingChanged || credsChanged;

  // 档案三态转成控面：quizs 且读到有选项 → 模型从档案里选；其余（读取中、读不出、非 quizs）→ 手填文本框照旧。
  const archiveOptions = archive !== null && archive.kind === 'ready' ? archive.options : [];
  const hasArchive = quizs && archiveOptions.length > 0;
  const archiveOption = hasArchive ? archiveOptions.find((o) => o.value === model) ?? null : null;
  const modelOutsideArchive = hasArchive && !modelInArchive(model, archiveOptions);
  const archiveLoading = quizs && (archive === null || archive.kind === 'loading');
  // 档位可选项：模型在档案里 → 该档案允许的档位；quizs 但档案不明或读不出 → 六值；非 quizs → 七段。
  const thinkingLevels: readonly string[] = quizs
    ? thinkingLevelsFor(archiveOption)
    : THINKING_OPTIONS.map((o) => o.value);
  const thinkingOptions = thinkingLevels.map((value) => ({ value, label: value }));
  // 档位从不自动改：当前档位不在所选档案允许的范围里就一个段都不选、写明原因并不调预览。
  const thinkingOutOfRange = archiveOption !== null && !thinkingAllowed(thinking, archiveOption.thinking);
  const quizsNote = !quizs
    ? null
    : archiveLoading
      ? QUIZS_READING
      : archive !== null && archive.kind === 'failed'
        ? archive.reason
        : null;

  // 新建时模型为空：档案读到之后自动选第一项（不替用户改已有取值）。
  useEffect(() => {
    if (!hasArchive || mode !== 'new' || model !== '') return;
    setModel(archiveOptions[0].value);
  }, [hasArchive, mode, archiveOptions, model]);

  // 只传与打开时初值不同的字段（编辑）；thinking 原来缺省、界面显示 high 但没动过就不传；数组按顺序原样传。
  const buildArgs = (): WriteArgs => {
    const args: WriteArgs = { profile: id };
    if (mode === 'new') {
      args.runtime = runtime;
      args.model = model;
    } else {
      if (runtimeChanged) args.runtime = runtime;
      if (modelChanged) args.model = model;
    }
    // quizs 分支：用户点过档位段就算改动（点回初值也照传 --thinking=），不把档案不认的档位悄悄交上去。
    if (quizs ? thinkingTouched || thinkingChanged : thinkingChanged) args.thinking = thinking;
    if (!quizs && creds.length > 0 && (mode === 'new' || credsChanged)) args.credential_env = creds;
    return args;
  };

  // 表单合法才调 preview；[确认…] 只在「合法 + 有改动 + 最后一次预览对应当前取值 + 200 + ok」时可点。
  // quizs 分支再加三条：档案不在读取中、模型在档案里、档位在档案允许的范围内。
  const quizsBlocked = quizs && (archiveLoading || modelOutsideArchive || thinkingOutOfRange);
  const canPreview = fieldValid && hasRuntime && !clearingCred && hasChanges && !quizsBlocked;
  const args = buildArgs();
  const { result, current } = useLivePreview(action, args, canPreview);
  const confirmEnabled = canPreview && current && result !== null && result.ok;

  const addEnv = () => {
    const name = envInput.trim();
    if (!name) return;
    if (!validEnvName(name)) {
      setEnvError(ENV_ERROR);
      return;
    }
    if (!creds.includes(name)) setCreds([...creds, name]);
    setEnvInput('');
    setEnvError(null);
  };
  const removeEnv = (name: string) => {
    setCreds(creds.filter((c) => c !== name));
    setEnvError(null);
  };
  // 档位段的点击：quizs 分支里点过即算改动（buildArgs 照此传 --thinking=）。
  const onThinkingChange = (value: string) => {
    setThinking(value);
    setThinkingTouched(true);
  };

  const onConfirm = () => {
    const spec: WriteSpec = { action, args: buildArgs() };
    onClose();
    start(spec);
  };

  const runtimeOptions = runtimes.map((r) => ({ value: r.id, label: r.id }));
  const title = mode === 'new' ? '新建 profile' : `修改 profile ${initial.id}`;

  const renderBottom = (): ReactNode => {
    if (!hasRuntime) return <p className="pf-msg">先登记 runtime</p>;
    if (clearingCred) return <p className="pf-msg">内核没有清空凭据变量的写法</p>;
    if (!fieldValid) return null;
    if (!hasChanges) return <p className="pf-msg">还没有改动</p>;
    if (!result || !current) return <p className="pf-msg pf-msg--muted">预览中…</p>;
    return (
      <div className="pf-preview">
        {result.error ? (
          <p className="pf-preview__error">{result.error}</p>
        ) : (
          <>
            <code className="pf-preview__cmd">{dispatchCommand(result.command)}</code>
            {result.warnings.map((w, i) => (
              <p key={i} className="pf-preview__warn">{w}</p>
            ))}
          </>
        )}
      </div>
    );
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        title={title}
        footer={
          <>
            <Button variant="secondary" onClick={onClose}>取消</Button>
            <Button variant="primary" disabled={!confirmEnabled} onClick={onConfirm}>确认…</Button>
          </>
        }
      >
        <div className="pf-form">
          <TextField
            label="ID"
            value={id}
            onChange={(e) => setId(e.target.value)}
            readOnly={mode === 'edit'}
            mono
            error={id !== '' && !idValid ? ID_ERROR : undefined}
          />
          <Select label="runtime" value={runtime} onChange={(e) => setRuntime(e.target.value)} options={runtimeOptions} />
          {hasArchive ? (
            <Select
              label="模型"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              options={modelOutsideArchive ? [{ value: model, label: model }, ...archiveOptions] : archiveOptions}
              error={modelOutsideArchive ? QUIZS_MODEL_OUTSIDE : undefined}
            />
          ) : (
            <>
              <TextField
                label="模型"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                mono
                help={MODEL_HELP}
                error={model !== '' && !modelValid ? MODEL_ERROR : undefined}
              />
              {quizsNote !== null && <p className="pf-note">{quizsNote}</p>}
            </>
          )}
          <div className="pf-field">
            <span className="pf-field__label">thinking</span>
            <SegmentedControl aria-label="thinking" options={thinkingOptions} value={thinking} onChange={onThinkingChange} />
            {thinkingOutOfRange && <p className="pf-warn">{thinking} 不在这个档案允许的档位里</p>}
          </div>
          {quizs ? (
            <div className="pf-env" role="group" aria-label="凭据变量">
              <p className="pf-note">{QUIZS_CREDS_NOTE}</p>
            </div>
          ) : (
            <>
              <div className="pf-env">
                <TextField
                  label="凭据变量"
                  value={envInput}
                  onChange={(e) => setEnvInput(e.target.value)}
                  mono
                  help={ENV_HELP}
                  error={envError ?? undefined}
                />
                <Button variant="secondary" size="sm" onClick={addEnv}>添加</Button>
              </div>
              {creds.length > 0 && (
                <div className="pf-env__tags">
                  {creds.map((name) => (
                    <span key={name} className="pf-env__tag">
                      <Tag tone="neutral" mono>{name}</Tag>
                      <Button variant="ghost" size="sm" aria-label={`移除 ${name}`} className="pf-env__remove" onClick={() => removeEnv(name)}>
                        <XIcon width={14} height={14} />
                      </Button>
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
          <div className="pf-bottom">{renderBottom()}</div>
        </div>
      </Dialog>
      <WriteFlow flow={flow} />
    </>
  );
}

/** 角色页页头 [新建 profile]：可点（离线也可点，同 A 片口径），secondary/md；点开新建表单对话框。 */
export function NewProfileAction({ reload }: { reload?: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="secondary" size="md" onClick={() => setOpen(true)}>新建 profile</Button>
      <ProfileFormDialog open={open} mode="new" onClose={() => setOpen(false)} reload={reload} />
    </>
  );
}

/** profile 表 [编辑]：ghost/sm，可点；点开带初值的编辑表单对话框（点了不冒泡，行本来就不可点）。 */
export function EditProfileAction({ profile, reload }: { profile: LooseProfile; reload?: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); setOpen(true); }}>编辑</Button>
      <ProfileFormDialog open={open} mode="edit" profile={profile} onClose={() => setOpen(false)} reload={reload} />
    </>
  );
}
