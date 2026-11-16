// 七端岗位两个写入口与「改绑定」表单（B 片）：入口文件只放按钮，字段、候选联动、底部实时预览与逐字提示都在这里。
// 确认与执行走既有的 useWriteFlow（预览 → 确认 → 执行 → 重读 → 终态）；本文件不跨层引 src/pages，岗位中文名与
// 主选/替补候选都由入口文件（src/pages/readonly1/roles-logic.ts 的纯函数）算好当 prop 传进来。
import { useState, type ReactNode } from 'react';
import { Button, Dialog, Select, dispatchCommand } from '../components';
import { DisabledAction } from '../shell/DisabledAction';
import type { HubChange, WriteArgs } from '../api';
import { hubChangeLines } from './hubChangeLines';
import { useWriteFlow, type WriteSpec } from './useWriteFlow';
import { WriteFlow } from './WriteConfirmDialog';
import { useLivePreview } from './useLivePreview';
import './hub-bind-form.css';

// 逐字原因句（合同 Behavior contract）：只在这里出现，入口文件不写（T013）。
const REASON_NO_CANDIDATES = '没有能用在这个岗位的 profile：先在「CLI 运行时」页登记运行时，再新建 profile';
const REASON_UNSET_DEFAULT = '这个岗位现在用的是内核缺省，没有要恢复的配置';

interface HubBindFormProps {
  post: string;
  /** 岗位中文名（入口文件用 hubPostName 算好传进来，src/writes 不跨层引 src/pages）。 */
  postLabel: string;
  /** 主选候选（入口文件用 allowedProfiles 算好；为空即「改绑定…」禁用）。 */
  mainCandidates: readonly string[];
  /** 某个主选下的替补候选（入口文件用 hubFallbackCandidates 包一层传进来）。 */
  fallbackCandidatesFor: (mainProfileId: string) => string[];
  source: 'default' | 'config';
  /** 现有主绑定 profile id（预填用；缺省行是 null）。 */
  mainProfile: string | null;
  /** 现有替补 profile id（预填用；没有替补时 null）。 */
  fallbackProfile: string | null;
  reload?: () => Promise<void>;
}

function HubBindDialog({
  open,
  onClose,
  post,
  postLabel,
  mainCandidates,
  fallbackCandidatesFor,
  source,
  mainProfile,
  fallbackProfile,
  reload,
}: HubBindFormProps & { open: boolean; onClose: () => void }) {
  const { start, flow } = useWriteFlow(reload);

  // 预填（内核 hub set 整条替换绑定，不预填会悄悄清掉原来的替补）：主选——配置行且现有主绑定在候选里 → 预填它，
  // 否则第一个候选；替补——配置行且现有替补在该主选下的替补候选里 → 预填它，否则空。
  const initialMain =
    source === 'config' && mainProfile != null && mainCandidates.includes(mainProfile)
      ? mainProfile
      : mainCandidates[0] ?? '';
  const initialFallback =
    source === 'config' && fallbackProfile != null && fallbackCandidatesFor(initialMain).includes(fallbackProfile)
      ? fallbackProfile
      : '';
  const [main, setMain] = useState(initialMain);
  const [fallback, setFallback] = useState(initialFallback);

  const fbCandidates = fallbackCandidatesFor(main);
  const fbEnabled = fbCandidates.length > 0;

  // 只有表单开着且主选非空才在 300ms 防抖后调 preview（关着的表单不预览，页面上同时只有一个开着的表单）。
  const canPreview = open && main !== '';
  const buildArgs = (): WriteArgs => {
    const args: WriteArgs = { post, profile: main };
    if (fallback !== '') args.fallback = fallback;
    return args;
  };
  const { result, current } = useLivePreview('hub.set', buildArgs(), canPreview);
  const confirmEnabled = canPreview && current && result !== null && result.ok;

  // 切换主选：替补候选随之变。换成非 quizs（替补候选空）时清空并禁用替补；换成 quizs 时恢复可选，当前替补不在新候选里则清空。
  const onMainChange = (value: string) => {
    setMain(value);
    if (!fallbackCandidatesFor(value).includes(fallback)) setFallback('');
  };

  const onConfirm = () => {
    const spec: WriteSpec = { action: 'hub.set', args: buildArgs() };
    onClose();
    start(spec);
  };

  const renderBottom = (): ReactNode => {
    if (!canPreview) return null;
    if (!result || !current) return <p className="hb-msg hb-msg--muted">预览中…</p>;
    const change = result.hubChanges.find((c: HubChange) => c.post === post) ?? null;
    return (
      <div className="hb-preview">
        {result.error ? (
          <p className="hb-preview__error">{result.error}</p>
        ) : (
          <>
            <code className="hb-preview__cmd">{dispatchCommand(result.command)}</code>
            {change != null && (
              <div className="hb-diff">
                {hubChangeLines(change).map((line, i) => (
                  <p key={i} className="hb-diff__line">{line}</p>
                ))}
              </div>
            )}
            {result.warnings.map((w, i) => (
              <p key={i} className="hb-preview__warn">{w}</p>
            ))}
            {result.runningTurns.map((t, i) => (
              <p key={i} className="hb-preview__turn">{t}</p>
            ))}
          </>
        )}
      </div>
    );
  };

  const mainOptions = mainCandidates.map((id) => ({ value: id, label: id }));
  const fbOptions = [{ value: '', label: '不设替补' }, ...fbCandidates.map((id) => ({ value: id, label: id }))];

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        title={`改绑定：${postLabel}`}
        footer={
          <>
            <Button variant="secondary" onClick={onClose}>取消</Button>
            <Button variant="primary" disabled={!confirmEnabled} onClick={onConfirm}>确认…</Button>
          </>
        }
      >
        <div className="hb-form">
          <Select label="主绑定" value={main} onChange={(e) => onMainChange(e.target.value)} options={mainOptions} />
          <Select
            label="替补"
            value={fallback}
            onChange={(e) => setFallback(e.target.value)}
            options={fbOptions}
            disabled={!fbEnabled}
          />
          <div className="hb-bottom">{renderBottom()}</div>
        </div>
      </Dialog>
      <WriteFlow flow={flow} />
    </>
  );
}

/** 「改绑定…」入口：有主选候选时可点（ghost/sm）并打开表单；没有候选时禁用并给出原因句。 */
export function HubBindAction(props: HubBindFormProps) {
  const [open, setOpen] = useState(false);
  if (props.mainCandidates.length === 0) {
    return <DisabledAction label="改绑定…" variant="ghost" size="sm" reason={REASON_NO_CANDIDATES} />;
  }
  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>改绑定…</Button>
      <HubBindDialog {...props} open={open} onClose={() => setOpen(false)} />
    </>
  );
}

/** 「恢复缺省…」入口：配置行可点（ghost/sm）并直接走既有写流程；缺省行禁用并给出原因句。 */
export function HubUnsetAction({
  post,
  source,
  onStart,
}: {
  post: string;
  source: 'default' | 'config';
  onStart: (spec: WriteSpec) => void;
}) {
  if (source === 'config') {
    return (
      <Button variant="ghost" size="sm" onClick={() => onStart({ action: 'hub.unset', args: { post } })}>
        恢复缺省…
      </Button>
    );
  }
  return <DisabledAction label="恢复缺省…" variant="ghost" size="sm" reason={REASON_UNSET_DEFAULT} />;
}
