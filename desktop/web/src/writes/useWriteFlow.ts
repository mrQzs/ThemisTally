// 写操作流程状态机（UI 设计 8.3）：预览 → 确认 → 执行 → 重读 → 结果。成功只在重读之后才说（W3）；
// 连接中断先轮询 getOperation 再下结论（D12）；计时器在卸载与流程重置时清掉。
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getOperation,
  getPlugins,
  getPresets,
  getRoles,
  preview,
  setPluginEnabled,
  usePreset,
  type Envelope,
  type OperationView,
  type WriteAction,
} from '../api';
import { dispatchCommand } from '../components';
import { writeScenario } from '../mock/writes';
import { pluginSnapshot, presetSnapshot, sameSnapshot } from './snapshots';
import {
  classifyTerminal,
  classifyWrite,
  errorText,
  finalFromReread,
  type FinalState,
  type WriteClass,
} from './writeOutcome';
import type { ConfirmContent, FlowRender, FlowView } from './WriteConfirmDialog';

export interface WriteSpec {
  action: WriteAction;
  args: Record<string, string>;
  /** 对话框标题：动词加对象，如「切换到方案 economy？」。 */
  title: string;
}

// 轮询上限：写路由时限 90 秒再加宽限（D12：119 秒不下结论，120 秒进「结果未知」）。
const POLL_LIMIT_MS = 120000;
const POLL_INTERVAL_MS = 1000;

function successTextOf(action: WriteAction, args: Record<string, string>): string {
  if (action === 'preset.use') return `已切换到方案 ${args.name}`;
  if (action === 'plugin.enable') return `已启用插件 ${args.id}`;
  return `已停用插件 ${args.id}`;
}

function isTerminalState(state: string): boolean {
  return state === 'succeeded' || state === 'failed' || state === 'stale' || state === 'timed_out';
}

type SnapResult = { ok: true; snapshot: unknown } | { ok: false };

// 预览阶段与重读阶段各读一次快照；reread-fail / reread-fail-exit1 让重读按读失败处理（不靠 ?mock=）。
async function readSnapshot(action: WriteAction, isReread: boolean): Promise<SnapResult> {
  if (isReread && (writeScenario() === 'reread-fail' || writeScenario() === 'reread-fail-exit1')) {
    return { ok: false };
  }
  try {
    if (action === 'preset.use') {
      const [presets, roles] = await Promise.all([getPresets(), getRoles()]);
      if (!presets.ok || !roles.ok || !presets.data || !roles.data) return { ok: false };
      return { ok: true, snapshot: presetSnapshot(presets.data, roles.data) };
    }
    const plugins = await getPlugins();
    if (!plugins.ok || !plugins.data) return { ok: false };
    return { ok: true, snapshot: pluginSnapshot(plugins.data) };
  } catch {
    return { ok: false };
  }
}

export function useWriteFlow(reload?: () => Promise<void>): { start: (spec: WriteSpec) => void; flow: FlowRender } {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [view, setView] = useState<FlowView>({ phase: 'previewing' });
  const [toast, setToast] = useState<string | null>(null);

  const specRef = useRef<WriteSpec | null>(null);
  const contentRef = useRef<ConfirmContent | null>(null);
  const snapRef = useRef<unknown>(null);
  const confirmRef = useRef('');
  const clsRef = useRef<{ cls: WriteClass; envelope: Envelope<null> | null } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const flowRef = useRef(0);
  const mountedRef = useRef(true);
  const reloadRef = useRef(reload);
  reloadRef.current = reload;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollRef.current !== null) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const isCurrent = useCallback((id: number) => mountedRef.current && id === flowRef.current, []);

  const resetFlow = useCallback(() => {
    flowRef.current += 1;
    stopPolling();
    setDialogOpen(false);
    setView({ phase: 'previewing' });
    specRef.current = null;
    contentRef.current = null;
    snapRef.current = null;
    confirmRef.current = '';
    clsRef.current = null;
  }, [stopPolling]);

  const contentOf = useCallback((): ConfirmContent => {
    return contentRef.current ?? { command: '', changes: [], warnings: [], running: [], notes: [] };
  }, []);

  const applyFinal = useCallback(
    (final: FinalState) => {
      switch (final.phase) {
        case 'done': {
          const spec = specRef.current;
          setToast(spec ? successTextOf(spec.action, spec.args) : '');
          resetFlow();
          void reloadRef.current?.().catch(() => {});
          return;
        }
        case 'doneWithWarning':
          setView({ phase: 'doneWithWarning', warnings: final.warnings });
          return;
        case 'failed':
          setView({ phase: 'failed', error: final.error, reason: final.reason });
          return;
        case 'partiallyWritten':
          setView({ phase: 'partiallyWritten', error: final.error, reason: final.reason });
          return;
        case 'unknown':
          setView({ phase: 'unknown' });
          return;
        case 'rereadFailed':
          setView({ phase: 'rereadFailed', warnings: final.warnings });
          return;
      }
    },
    [resetFlow],
  );

  const doReread = useCallback(
    async (my: number) => {
      const spec = specRef.current;
      const stored = clsRef.current;
      if (!spec || !stored) return;
      const snap = await readSnapshot(spec.action, true);
      if (!isCurrent(my)) return;
      if (!snap.ok) {
        applyFinal(finalFromReread(stored.cls, false, false, stored.envelope));
        return;
      }
      const changed = !sameSnapshot(snapRef.current, snap.snapshot);
      applyFinal(finalFromReread(stored.cls, true, changed, stored.envelope));
    },
    [applyFinal, isCurrent],
  );

  const startPolling = useCallback(
    (my: number) => {
      stopPolling();
      setView({ phase: 'confirming', content: contentOf() });
      let elapsed = 0;
      pollRef.current = setInterval(() => {
        elapsed += POLL_INTERVAL_MS;
        void getOperation(confirmRef.current).then(
          (reply) => {
            if (!isCurrent(my)) {
              stopPolling();
              return;
            }
            if (reply.status === 404) {
              stopPolling();
              setView({ phase: 'unknown' });
              return;
            }
            const op: OperationView | null = reply.body.data;
            if (op && isTerminalState(op.state)) {
              stopPolling();
              proceed(classifyTerminal(op), op.envelope, my);
              return;
            }
            if (elapsed >= POLL_LIMIT_MS) {
              stopPolling();
              setView({ phase: 'unknown' });
            }
          },
          () => {
            if (!isCurrent(my)) {
              stopPolling();
              return;
            }
            if (elapsed >= POLL_LIMIT_MS) {
              stopPolling();
              setView({ phase: 'unknown' });
            }
          },
        );
      }, POLL_INTERVAL_MS);
    },
    [contentOf, isCurrent, stopPolling],
  );

  const proceed = useCallback(
    (cls: WriteClass, envelope: Envelope<null> | null, my: number) => {
      switch (cls.kind) {
        case 'success':
        case 'successWarn':
        case 'failedExit':
        case 'timeout':
        case 'serverError':
          clsRef.current = { cls, envelope };
          setView({ phase: 'rereading', content: contentOf() });
          void doReread(my);
          return;
        case 'stale':
          setView({ phase: 'stale' });
          return;
        case 'expired':
          setView({ phase: 'expired' });
          return;
        case 'rejected':
          setView({ phase: 'rejected', error: errorText(envelope) });
          return;
        case 'busy':
        case 'checkOperation':
          void queryOp(my, cls.kind);
          return;
        default:
          startPolling(my);
          return;
      }
    },
    [contentOf, doReread, startPolling],
  );

  const queryOp = useCallback(
    async (my: number, branch: 'busy' | 'checkOperation') => {
      const reply = await getOperation(confirmRef.current).then(
        (r) => ({ ok: true as const, r }),
        () => ({ ok: false as const }),
      );
      if (!isCurrent(my)) return;
      if (!reply.ok || reply.r.status === 404) {
        if (branch === 'busy') {
          setView({ phase: 'confirmable', content: contentOf(), notice: '服务繁忙，请稍后再确认' });
        } else {
          setView({ phase: 'unknown' });
        }
        return;
      }
      const op: OperationView | null = reply.r.body.data;
      if (op && isTerminalState(op.state)) {
        proceed(classifyTerminal(op), op.envelope, my);
        return;
      }
      startPolling(my);
    },
    [contentOf, isCurrent, proceed, startPolling],
  );

  const runPreview = useCallback(
    async (spec: WriteSpec, my: number) => {
      const [prevRes, snapRes] = await Promise.all([
        preview(spec.action, spec.args).then(
          (r) => ({ ok: true as const, r }),
          () => ({ ok: false as const }),
        ),
        readSnapshot(spec.action, false).then(
          (s) => ({ ok: true as const, s }),
          () => ({ ok: false as const }),
        ),
      ]);
      if (!isCurrent(my)) return;
      if (!prevRes.ok) {
        setView({ phase: 'previewFailed', message: '预览失败：服务没有回应' });
        return;
      }
      const r = prevRes.r;
      if (r.status === 503) {
        setView({ phase: 'previewFailed', message: '服务繁忙，请稍后重试' });
        return;
      }
      if (r.status !== 200 || !r.body.ok || !r.body.data) {
        setView({ phase: 'previewFailed', message: errorText(r.body) });
        return;
      }
      if (!snapRes.ok || !snapRes.s.ok) {
        setView({ phase: 'previewFailed', message: '读取当前状态失败' });
        return;
      }
      const data = r.body.data;
      snapRef.current = snapRes.s.snapshot;
      confirmRef.current = data.confirmation;
      const content = {
        // 预览命令带 --dry-run --json（第二节）；「将运行的命令」要的是真正会跑的写命令，去掉这两个开关。
        command: dispatchCommand(data.command.filter((a) => a !== '--dry-run' && a !== '--json')),
        changes: data.binding_changes,
        warnings: data.warnings,
        running: data.running_attempts,
        notes: data.notes,
      };
      contentRef.current = content;
      setView({ phase: 'confirmable', content });
    },
    [isCurrent],
  );

  const open = useCallback(
    (spec: WriteSpec) => {
      const my = (flowRef.current += 1);
      stopPolling();
      specRef.current = spec;
      contentRef.current = null;
      snapRef.current = null;
      confirmRef.current = '';
      clsRef.current = null;
      setTitle(spec.title);
      setDialogOpen(true);
      setView({ phase: 'previewing' });
      void runPreview(spec, my);
    },
    [runPreview, stopPolling],
  );

  const confirm = useCallback(() => {
    const spec = specRef.current;
    if (!spec) return;
    const my = flowRef.current;
    setView({ phase: 'executing', content: contentOf() });
    const call =
      spec.action === 'preset.use'
        ? usePreset(spec.args.name, confirmRef.current)
        : setPluginEnabled(spec.args.id, spec.action === 'plugin.enable', confirmRef.current);
    call.then(
      (reply) => {
        if (isCurrent(my)) proceed(classifyWrite(reply.status, reply.body), reply.body, my);
      },
      () => {
        if (isCurrent(my)) startPolling(my);
      },
    );
  }, [contentOf, isCurrent, proceed, startPolling]);

  const repreview = useCallback(() => {
    const spec = specRef.current;
    if (!spec) return;
    const my = (flowRef.current += 1);
    stopPolling();
    setView({ phase: 'previewing' });
    void runPreview(spec, my);
  }, [runPreview, stopPolling]);

  const onAck = useCallback(() => {
    void reloadRef.current?.().catch(() => {});
    resetFlow();
  }, [resetFlow]);

  const onHistory = useCallback(() => {
    if (typeof window !== 'undefined') window.location.hash = '#/history';
    resetFlow();
  }, [resetFlow]);

  const flow: FlowRender = {
    open: dialogOpen,
    title,
    view,
    toast,
    onCancel: resetFlow,
    onConfirm: confirm,
    onRepreview: repreview,
    onAck,
    onHistory,
    onToastClose: () => setToast(null),
  };

  return { start: open, flow };
}
