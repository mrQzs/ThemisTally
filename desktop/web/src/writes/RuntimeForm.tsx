// 登记运行时的表单对话框（合同第六节）：入口文件只放按钮，字段、逐字提示与标题文字一律在这里。
// 底部实时显示内核预览（将运行的命令、警告、报错原文）；[确认…] 交给写确认框走
// 「预览 → 确认 → 执行 → 重读 → 终态」。界面不提供 force：同一个 id 已登记为别的适配器时内核会拒绝。
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Button, Dialog, Select, TextField, dispatchCommand } from '../components';
import { PlusIcon } from '../icons';
import type { WriteArgs } from '../api';
import { useWriteFlow, type WriteSpec } from './useWriteFlow';
import { WriteFlow } from './WriteConfirmDialog';
import { useLivePreview } from './useLivePreview';
import { validId } from './profileRules';
import { parseCommand } from './runtimeRules';
import './runtime-form.css';

// 逐字提示（合同第三节）：只在这里出现，入口文件不写（T013 / T022 S15 / D09）。
const ID_ERROR = '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
const COMMAND_ERROR = '命令要写成 JSON 字符串数组，例如 ["C:/tools/pi.exe"]；每项非空、不超过 1024 个字符、不含控制字符';
const COMMAND_HELP = 'JSON 字符串数组，第一项写命令的绝对路径';

// 适配器五值（与服务的 ADAPTERS、内核 kit_roles.py 的 ADAPTERS 一致），缺省 pi。
const ADAPTER_OPTIONS = [
  { value: 'pi', label: 'pi' },
  { value: 'claude-code', label: 'claude-code' },
  { value: 'codex', label: 'codex' },
  { value: 'opencode', label: 'opencode' },
  { value: 'quizs', label: 'quizs' },
];

function AddRuntimeDialog({
  open,
  onClose,
  reload,
}: {
  open: boolean;
  onClose: () => void;
  reload?: () => Promise<void>;
}) {
  const { start, flow } = useWriteFlow(reload);
  const [id, setId] = useState('');
  const [adapter, setAdapter] = useState('pi');
  const [command, setCommand] = useState('');

  const idValid = validId(id);
  const parsed = parseCommand(command);
  const fieldValid = idValid && parsed.ok;

  // 命令留空不传 command 这个键；非空按 JSON 字符串数组原样传（服务侧空数组不合法）。
  const buildArgs = (): WriteArgs => {
    const args: WriteArgs = { runtime: id, adapter };
    if (parsed.ok && parsed.value !== undefined) args.command = parsed.value;
    return args;
  };

  // 表单合法才调 preview；[确认…] 只在「合法 + 最后一次预览对应当前取值 + 200 + ok」时可点。
  const canPreview = fieldValid;
  const args = buildArgs();
  const { result, current } = useLivePreview('runtime.add', args, canPreview);
  const confirmEnabled = canPreview && current && result !== null && result.ok;

  // 成功（重读之后弹轻提示）才清空表单；执行失败不清，重开还在原来的值。
  const aPieceWasOpen = useRef(false);
  const resetForm = () => {
    setId('');
    setAdapter('pi');
    setCommand('');
  };
  useEffect(() => {
    if (aPieceWasOpen.current && !flow.open && flow.toast) resetForm();
    aPieceWasOpen.current = flow.open;
  }, [flow.open, flow.toast]);

  const onConfirm = () => {
    const spec: WriteSpec = { action: 'runtime.add', args: buildArgs() };
    onClose();
    start(spec);
  };

  const renderBottom = (): ReactNode => {
    if (!fieldValid) return null;
    if (!result || !current) return <p className="rt-msg rt-msg--muted">预览中…</p>;
    return (
      <div className="rt-preview">
        {result.error ? (
          <p className="rt-preview__error">{result.error}</p>
        ) : (
          <>
            <code className="rt-preview__cmd">{dispatchCommand(result.command)}</code>
            {result.warnings.map((w, i) => (
              <p key={i} className="rt-preview__warn">{w}</p>
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
        title="登记运行时"
        footer={
          <>
            <Button variant="secondary" onClick={onClose}>取消</Button>
            <Button variant="primary" disabled={!confirmEnabled} onClick={onConfirm}>确认…</Button>
          </>
        }
      >
        <div className="rt-form">
          <TextField
            label="ID"
            value={id}
            onChange={(e) => setId(e.target.value)}
            mono
            error={id !== '' && !idValid ? ID_ERROR : undefined}
          />
          <Select label="适配器" value={adapter} onChange={(e) => setAdapter(e.target.value)} options={ADAPTER_OPTIONS} />
          <TextField
            label="命令"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            mono
            help={COMMAND_HELP}
            error={command !== '' && !parsed.ok ? COMMAND_ERROR : undefined}
          />
          <div className="rt-bottom">{renderBottom()}</div>
        </div>
      </Dialog>
      <WriteFlow flow={flow} />
    </>
  );
}

/** 运行时页页头 [手动登记…]：可点（离线也可点，同 [新建 profile] 口径），primary/md；点开登记表单对话框。 */
export function AddRuntimeAction({ reload }: { reload?: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="primary" size="md" onClick={() => setOpen(true)}>
        <PlusIcon width={16} height={16} />
        手动登记…
      </Button>
      <AddRuntimeDialog open={open} onClose={() => setOpen(false)} reload={reload} />
    </>
  );
}
