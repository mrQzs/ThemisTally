// profile 新建/编辑两用的表单对话框（合同第三、四、六节）：入口文件只放按钮，字段、提示与标题文字一律在这里。
// 底部实时显示内核预览（命令、警告、报错原文）；[确认…] 交给 A 片确认框走「预览 → 确认 → 执行 → 重读 → 终态」。
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Button, Dialog, SegmentedControl, Select, Tag, TextField, dispatchCommand } from '../components';
import { XIcon } from '../icons';
import { getRuntimes, type WriteAction, type WriteArgs } from '../api';
import { useWriteFlow, type WriteSpec } from './useWriteFlow';
import { WriteFlow } from './WriteConfirmDialog';
import { useLivePreview } from './useLivePreview';
import { sameStringArray, validEnvName, validId, validModel } from './profileRules';
import './profile-form.css';

// 逐字提示（合同第三节）：只在这里出现，入口文件不写（T013 / T022 S15 / D09）。
const ID_ERROR = '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
const MODEL_ERROR = '模型要写成 provider/model，两段都只能用字母、数字与 . _ : / @ + -';
const ENV_ERROR = '变量名只能用字母、数字与下划线，不能以数字开头，最长 128 个字符';
const MODEL_HELP = '手填的模型没有核实';
const ENV_HELP = '值在‘凭据’页录入';

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
  const [runtimes, setRuntimes] = useState<string[]>([]);

  const action: WriteAction = mode === 'new' ? 'profile.add' : 'profile.edit';

  // 对话框打开时由 src/writes 调 getRuntimes() 填 runtime 下拉；新建模式缺省选第一个已登记的 runtime。
  useEffect(() => {
    if (!open) return;
    let alive = true;
    getRuntimes().then(
      (env) => {
        if (!alive) return;
        const ids = env.ok && env.data ? env.data.runtimes.map((r) => r.id) : [];
        setRuntimes(ids);
        if (mode === 'new') setRuntime((cur) => cur || ids[0] || '');
      },
      () => {
        if (alive) setRuntimes([]);
      },
    );
    return () => {
      alive = false;
    };
  }, [open, mode]);

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
  const credsChanged = !sameStringArray(creds, initial.creds);
  // 凭据变量改成空的：服务侧空数组不合法，本片不做清空。
  const clearingCred = mode === 'edit' && credsChanged && creds.length === 0 && initial.creds.length > 0;
  const runtimeChanged = mode === 'edit' && runtime !== initial.runtime;
  const modelChanged = mode === 'edit' && model !== initial.model;
  const thinkingChanged = thinking !== initial.thinking;
  const hasChanges = mode === 'new' || runtimeChanged || modelChanged || thinkingChanged || credsChanged;

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
    if (thinkingChanged) args.thinking = thinking;
    if (creds.length > 0 && (mode === 'new' || credsChanged)) args.credential_env = creds;
    return args;
  };

  // 表单合法才调 preview；[确认…] 只在「合法 + 有改动 + 最后一次预览对应当前取值 + 200 + ok」时可点。
  const canPreview = fieldValid && hasRuntime && !clearingCred && hasChanges;
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

  const onConfirm = () => {
    const spec: WriteSpec = { action, args: buildArgs() };
    onClose();
    start(spec);
  };

  const runtimeOptions = runtimes.map((r) => ({ value: r, label: r }));
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
          <TextField
            label="模型"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            mono
            help={MODEL_HELP}
            error={model !== '' && !modelValid ? MODEL_ERROR : undefined}
          />
          <div className="pf-field">
            <span className="pf-field__label">thinking</span>
            <SegmentedControl aria-label="thinking" options={THINKING_OPTIONS} value={thinking} onChange={setThinking} />
          </div>
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
