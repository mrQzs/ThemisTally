// 角色卡的「改绑定」表单（本片）：入口文件只放按钮，字段、候选联动、底部实时预览与逐字提示都在这里。
// 确认与执行走既有的 useWriteFlow（预览 → 确认 → 执行 → 重读 → 终态）；本文件不跨层引 src/pages，角色中文名、
// 允许的模式与 profile 候选都由入口文件（src/pages/readonly1/roles-logic.ts 的纯函数）算好当 prop 传进来。
import { useState, type ReactNode } from 'react';
import { Button, Dialog, Select, dispatchCommand, type SelectOption } from '../components';
import { DisabledAction } from '../shell/DisabledAction';
import type { BindingChange, WriteArgs } from '../api';
import { useWriteFlow, type WriteSpec } from './useWriteFlow';
import { WriteFlow } from './WriteConfirmDialog';
import { useLivePreview } from './useLivePreview';
import './hub-bind-form.css';

// 逐字原因句（合同 Behavior contract）：只在这里出现，入口文件不写（T013）。
const REASON_NO_PROFILES = '没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile';
// 调度间隔只对调度代理生效：内核 role set 的 --cadence-seconds 只许配 scheduler_agent。
const CADENCE_ROLE = 'scheduler_agent';

export interface RoleBinding {
  mode: string;
  profile: string | null;
  host: string | null;
  cadenceSeconds: number | null;
}

interface RoleBindFormProps {
  role: string;
  /** 角色中文名（入口文件用 roleName 算好传进来，src/writes 不跨层引 src/pages）。 */
  roleLabel: string;
  /** 这个角色允许的模式（入口文件用 allowedModes 算好；没有候选时无头由本文件拿掉）。 */
  modes: readonly SelectOption[];
  /** 已登记的 profile id（入口文件用 profileIds 算好；为空即无头不可选）。 */
  candidates: readonly string[];
  /** 现有绑定：预填与 host/cadence_seconds 的原样传回用。 */
  binding: RoleBinding;
  reload?: () => Promise<void>;
}

// 可选模式：候选为空时拿掉「无头」（Select 不支持单项禁用，不摆一个选了就走不通的项）。
function modeOptionsOf(modes: readonly SelectOption[], candidates: readonly string[]): SelectOption[] {
  return modes
    .filter((m) => candidates.length > 0 || m.value !== 'headless')
    .map((m) => ({ value: m.value, label: m.label }));
}

// 表单本体：外层只在打开时挂载它（{open && <RoleBindFormDialog … />}），所以预填、两个字段的取值与底部
// 实时预览每次打开都按当时的 props 重算，关掉时未保存的取值连同预览结果一起丢掉。
function RoleBindFormDialog({
  onClose,
  onConfirm,
  role,
  roleLabel,
  modes,
  candidates,
  binding,
}: RoleBindFormProps & { onClose: () => void; onConfirm: (spec: WriteSpec) => void }) {
  const options = modeOptionsOf(modes, candidates);

  // 预填（内核 role set 整条替换绑定，不预填会悄悄丢掉 host 与 cadence_seconds）：模式——现有模式在可选列表里
  // 就用它，否则第一个可选；profile——现有绑定 profile 在候选里就用它，否则第一个候选。
  const initialMode = options.some((m) => m.value === binding.mode) ? binding.mode : options[0]?.value ?? '';
  const initialProfile =
    binding.profile != null && candidates.includes(binding.profile) ? binding.profile : candidates[0] ?? '';
  const [mode, setMode] = useState(initialMode);
  const [profile, setProfile] = useState(initialProfile);

  const headless = mode === 'headless';
  // 内层只在表单开着时挂载：取值合法才在 300ms 防抖后调 preview（页面上同时只有一个开着的表单）。
  const canPreview = mode !== '' && (!headless || profile !== '');
  const buildArgs = (): WriteArgs => {
    const args: WriteArgs = { role, target: headless ? profile : mode };
    // host 只回传给交互式宿主（内核对模式词配 --host 直接报错），且现有绑定也是交互式宿主、host 非空才带。
    if (!headless && mode === 'interactive_host' && binding.mode === 'interactive_host' && binding.host != null) {
      args.host = binding.host;
    }
    // cadence_seconds 只回传给调度代理的无头（内核整条替换，不传就丢；对模式词配 --cadence-seconds 直接报错）。
    if (headless && role === CADENCE_ROLE && binding.mode === 'headless' && binding.cadenceSeconds != null) {
      args.cadence_seconds = String(binding.cadenceSeconds);
    }
    return args;
  };
  const { result, current } = useLivePreview('role.set', buildArgs(), canPreview);
  const confirmEnabled = canPreview && current && result !== null && result.ok;

  const onConfirmClick = () => {
    const spec: WriteSpec = { action: 'role.set', args: buildArgs() };
    onClose();
    onConfirm(spec);
  };

  const renderBottom = (): ReactNode => {
    if (!canPreview) return null;
    if (!result || !current) return <p className="hb-msg hb-msg--muted">预览中…</p>;
    const change = result.bindingChanges.find((c: BindingChange) => c.role === role) ?? null;
    return (
      <div className="hb-preview">
        {result.error ? (
          <p className="hb-preview__error">{result.error}</p>
        ) : (
          <>
            <code className="hb-preview__cmd">{dispatchCommand(result.command)}</code>
            {change != null && (
              <div className="hb-diff">
                <p className="hb-diff__line">{change.from} → {change.to}</p>
              </div>
            )}
            {result.warnings.map((w, i) => (
              <p key={i} className="hb-preview__warn">{w}</p>
            ))}
          </>
        )}
      </div>
    );
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={`改绑定：${roleLabel}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button variant="primary" disabled={!confirmEnabled} onClick={onConfirmClick}>确认…</Button>
        </>
      }
    >
      <div className="hb-form">
        <Select
          label="模式"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          options={options}
          help={candidates.length === 0 ? REASON_NO_PROFILES : undefined}
        />
        {headless && (
          <Select
            label="profile"
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            options={candidates.map((id) => ({ value: id, label: id }))}
          />
        )}
        <div className="hb-bottom">{renderBottom()}</div>
      </div>
    </Dialog>
  );
}

// 外层：写流程留在这里，表单关掉也照常渲染确认框、执行、重读与终态；表单本体只在打开时挂载。
function RoleBindDialog({
  open,
  onClose,
  role,
  roleLabel,
  modes,
  candidates,
  binding,
  reload,
}: RoleBindFormProps & { open: boolean; onClose: () => void }) {
  const { start, flow } = useWriteFlow(reload);

  return (
    <>
      {open && (
        <RoleBindFormDialog
          role={role}
          roleLabel={roleLabel}
          modes={modes}
          candidates={candidates}
          binding={binding}
          onClose={onClose}
          onConfirm={start}
        />
      )}
      <WriteFlow flow={flow} />
    </>
  );
}

/** 「更改…」入口：这个角色还有可选的模式时可点（secondary/sm）并打开表单；一个模式都不给（未知角色码），
 * 或只允许无头又没有已登记的 profile 时禁用——只有后一种给出原因句。 */
export function RoleBindAction(props: RoleBindFormProps) {
  const [open, setOpen] = useState(false);
  const options = modeOptionsOf(props.modes, props.candidates);
  if (options.length === 0) {
    const noCandidates = props.modes.length > 0 && props.candidates.length === 0;
    return (
      <DisabledAction
        label="更改…"
        variant="secondary"
        size="sm"
        reason={noCandidates ? REASON_NO_PROFILES : undefined}
      />
    );
  }
  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>更改…</Button>
      <RoleBindDialog {...props} open={open} onClose={() => setOpen(false)} />
    </>
  );
}
