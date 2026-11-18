// 角色与模型页页头「保存当前为方案…」入口与「保存当前为方案」表单（本片）：把当前角色绑定存成方案。
// 内外两层照 T052：外层只放入口按钮与写流程，字段、预填、底部实时预览与 [确认…] 门控都在打开时才挂载的内层里。
// 本文件不跨层引 src/pages：角色中文名由入口文件（RolesPage 用 roleName）当 prop 传进来。
import { useEffect, useState, type ReactNode } from 'react';
import { Button, Checkbox, Dialog, TextField, dispatchCommand } from '../components';
import { getPresets, getRoles, type WriteArgs } from '../api';
import { validId } from './profileRules';
import { useWriteFlow, type WriteSpec } from './useWriteFlow';
import { WriteFlow } from './WriteConfirmDialog';
import { useLivePreview } from './useLivePreview';
import './hub-bind-form.css';

// 逐字提示句（合同 Behavior contract）：只在这里出现。
const MSG_NAME_REQUIRED = '方案名要填';
const MSG_NAME_INVALID = '方案名不合法：小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
const MSG_DESC_TOO_LONG = '说明最多 200 个字，不能有控制字符';
const MSG_NO_EXPLICIT = '还没有写出绑定的角色：先在角色卡上用 [更改…] 写出绑定';
const MSG_NONE_CHECKED = '还没有勾要存的角色';
const MSG_READ_FAILED = '读不出当前的角色绑定与方案列表：稍后再试';
const MSG_PREVIEWING = '预览中…';

// 说明：按码点计数 ≤200 且不含 C0 控制字符（≤0x1f）、DEL（0x7f）与孤立代理项（与服务 cleanText(value, 1, 200) 同一口径）。
function validDescription(value: string): boolean {
  const points = Array.from(value);
  if (points.length > 200) return false;
  for (const ch of points) {
    const cp = ch.codePointAt(0) ?? 0;
    if (cp <= 0x1f || cp === 0x7f || (cp >= 0xd800 && cp <= 0xdfff)) return false;
  }
  return true;
}

interface PresetSaveFormProps {
  reload?: () => Promise<void>;
  /** 角色中文名（入口文件用 roleName 算好传进来，src/writes 不跨层引 src/pages）。 */
  roleLabel: (code: string) => string;
}

// 内层：只在表单打开时挂载。读取中/读到/读不出三态，四个字段、底部实时预览与 [确认…] 门控都在这里；
// 关掉（取消、Esc、确认）后未保存的取值连同勾选状态一并丢弃，再打开按当时读到的 roles 与 presets 重新算。
function PresetSaveFormDialog({
  onClose,
  onConfirm,
  roleLabel,
}: PresetSaveFormProps & { onClose: () => void; onConfirm: (spec: WriteSpec) => void }) {
  const [load, setLoad] = useState<'loading' | 'loaded' | 'failed'>('loading');
  const [explicitRoles, setExplicitRoles] = useState<string[]>([]);
  const [presetNames, setPresetNames] = useState<string[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [overwrite, setOverwrite] = useState(false);

  // 打开时各读一次 roles 与 presets：任一读不出按读失败处理（[确认…] 不可点、不调预览）。
  // explicit === true 的角色才列出，次序照读到的；缺省全选；卸载之后不写状态。
  useEffect(() => {
    let on = true;
    Promise.all([getRoles(), getPresets()]).then(([roles, presets]) => {
      if (!on) return;
      if (!roles.ok || !roles.data || !presets.ok || !presets.data) {
        setLoad('failed');
        return;
      }
      const list = roles.data.roles.filter((r) => r.explicit === true).map((r) => r.role);
      const initial: Record<string, boolean> = {};
      for (const code of list) initial[code] = true;
      setExplicitRoles(list);
      setChecked(initial);
      setPresetNames(presets.data.presets.map((p) => p.name));
      setLoad('loaded');
    });
    return () => {
      on = false;
    };
  }, []);

  const checkedRoles = explicitRoles.filter((code) => checked[code]);
  const hasExplicit = explicitRoles.length > 0;
  const nameValid = name !== '' && validId(name);
  const descValid = description === '' || validDescription(description);
  const isDuplicate = presetNames.includes(name);

  // roles 一律显式带（全选也带，按读到的角色次序排）；description 非空才带；force 只在重名且勾了覆盖时才带。
  const buildArgs = (): WriteArgs => {
    const args: WriteArgs = { name, roles: checkedRoles };
    if (description !== '') args.description = description;
    if (isDuplicate && overwrite) args.force = 'true';
    return args;
  };

  const canPreview =
    load === 'loaded' &&
    hasExplicit &&
    checkedRoles.length > 0 &&
    nameValid &&
    descValid &&
    (!isDuplicate || overwrite);

  const { result, current } = useLivePreview('preset.save', buildArgs(), canPreview);
  const confirmEnabled = canPreview && current && result !== null && result.ok;

  // 方案名一改就把覆盖勾选复位成没勾（否则改个名会带着 force 走）。
  const onNameChange = (value: string) => {
    setName(value);
    setOverwrite(false);
  };

  const nameError = name === '' ? MSG_NAME_REQUIRED : !validId(name) ? MSG_NAME_INVALID : undefined;
  const descError = description === '' ? undefined : !validDescription(description) ? MSG_DESC_TOO_LONG : undefined;

  // 先关表单，再 start(spec)（同一批更新里）；写流程由外层的 useWriteFlow 接管。
  const onConfirmClick = () => {
    const spec: WriteSpec = { action: 'preset.save', args: buildArgs() };
    onClose();
    onConfirm(spec);
  };

  const renderBottom = (): ReactNode => {
    if (load === 'loading') return <p className="hb-msg hb-msg--muted">{MSG_PREVIEWING}</p>;
    if (load === 'failed') return <p className="hb-msg hb-msg--muted">{MSG_READ_FAILED}</p>;
    if (!hasExplicit) return <p className="hb-msg hb-msg--muted">{MSG_NO_EXPLICIT}</p>;
    if (checkedRoles.length === 0) return <p className="hb-msg hb-msg--muted">{MSG_NONE_CHECKED}</p>;
    if (!canPreview) return null;
    if (!result || !current) return <p className="hb-msg hb-msg--muted">{MSG_PREVIEWING}</p>;
    if (result.error) return <p className="hb-preview__error">{result.error}</p>;
    return (
      <div className="hb-preview">
        <code className="hb-preview__cmd">{dispatchCommand(result.command)}</code>
        {result.warnings.map((w, i) => (
          <p key={i} className="hb-preview__warn">{w}</p>
        ))}
      </div>
    );
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="保存当前为方案"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button variant="primary" disabled={!confirmEnabled} onClick={onConfirmClick}>确认…</Button>
        </>
      }
    >
      <div className="hb-form">
        <TextField
          label="方案名"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          error={nameError}
          mono
        />
        {isDuplicate && (
          <>
            <p className="hb-msg hb-msg--muted">会覆盖方案 {name}</p>
            <Checkbox
              checked={overwrite}
              onChange={(next) => setOverwrite(next)}
              label={`覆盖方案 ${name}`}
            />
          </>
        )}
        <TextField
          label="说明"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          error={descError}
        />
        {hasExplicit && (
          <>
            <p className="hb-msg hb-msg--muted">要存的角色</p>
            {explicitRoles.map((code) => (
              <Checkbox
                key={code}
                checked={checked[code] === true}
                onChange={(next) => setChecked((prev) => ({ ...prev, [code]: next }))}
                label={roleLabel(code)}
              />
            ))}
          </>
        )}
        <div className="hb-bottom">{renderBottom()}</div>
      </div>
    </Dialog>
  );
}

// 外层：写流程留在这里，表单关掉也照常渲染确认框、执行、重读与终态；表单本体只在打开时挂载。
// 入口按钮一直可点（加载、出错、离线各态都可点，与 [新建 profile] 同口径），secondary/md。
export function PresetSaveAction({ reload, roleLabel }: PresetSaveFormProps) {
  const [open, setOpen] = useState(false);
  const { start, flow } = useWriteFlow(reload);
  return (
    <>
      <Button variant="secondary" size="md" onClick={() => setOpen(true)}>保存当前为方案…</Button>
      {open && <PresetSaveFormDialog roleLabel={roleLabel} onClose={() => setOpen(false)} onConfirm={start} />}
      <WriteFlow flow={flow} />
    </>
  );
}
