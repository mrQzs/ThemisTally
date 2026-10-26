// 写确认框（UI 设计 7.11）：标题动词加对象；依次是将运行的命令、变化、影响与风险；按钮随状态变。
// 报错与 WARN 一律按纯文本显示（<pre> 或文本节点，不经 SafeMarkdown），<b>x</b> 原样显示成文字。
import type { ReactNode } from 'react';
import { Banner, Button, CommandLine, Dialog, Skeleton, Toast } from '../components';
import type { BindingChange } from '../api';
// 样式表接线：放在组件 import 之后（照仓库里组件带自己的样式表的写法）。
import './write-flow.css';

export interface ConfirmContent {
  command: string;
  changes: BindingChange[];
  warnings: string[];
  running: string[];
  notes: string[];
}

export type FlowView =
  | { phase: 'previewing' }
  | { phase: 'previewFailed'; message: string }
  | { phase: 'confirmable'; content: ConfirmContent; notice?: string }
  | { phase: 'executing'; content: ConfirmContent }
  | { phase: 'confirming'; content: ConfirmContent }
  | { phase: 'rereading'; content: ConfirmContent }
  | { phase: 'doneWithWarning'; warnings: string[] }
  | { phase: 'failed'; error: string; reason: string | null }
  | { phase: 'partiallyWritten'; error: string; reason: string | null }
  | { phase: 'unknown' }
  | { phase: 'stale' }
  | { phase: 'expired' }
  | { phase: 'rereadFailed'; warnings: string[] }
  | { phase: 'rejected'; error: string };

// 执行中、确认结果中、重读中：命令已发出，对话框不能关闭。
const LOCKED_PHASES = new Set(['executing', 'confirming', 'rereading']);

export interface WriteConfirmDialogProps {
  open: boolean;
  title: string;
  view: FlowView;
  onCancel: () => void;
  onConfirm: () => void;
  onRepreview: () => void;
  onAck: () => void;
  onHistory: () => void;
}

// useWriteFlow（.ts，不能写 JSX）交出的渲染状态；WriteFlow 负责把它画成对话框加轻提示。
export interface FlowRender extends WriteConfirmDialogProps {
  toast: string | null;
  onToastClose: () => void;
}

export function WriteFlow({ flow }: { flow: FlowRender }) {
  return (
    <>
      <WriteConfirmDialog
        open={flow.open}
        title={flow.title}
        view={flow.view}
        onCancel={flow.onCancel}
        onConfirm={flow.onConfirm}
        onRepreview={flow.onRepreview}
        onAck={flow.onAck}
        onHistory={flow.onHistory}
      />
      <Toast open={flow.toast !== null} onClose={flow.onToastClose}>
        {flow.toast ?? ''}
      </Toast>
    </>
  );
}

function Changes({ changes }: { changes: BindingChange[] }) {
  if (changes.length === 0) return <p className="wf-changes__empty">预览没有列出变化</p>;
  return (
    <div className="wf-changes">
      {changes.map((c) => (
        <div key={c.role} className="wf-change">
          <span className="wf-change__role">{c.role}</span>
          <span className="wf-change__from">{c.from}</span>
          <span className="wf-change__arrow" aria-hidden="true">→</span>
          <span className="wf-change__to">{c.to}</span>
        </div>
      ))}
    </div>
  );
}

function Risks({ content }: { content: ConfirmContent }) {
  const hasRisk = content.warnings.length > 0 || content.running.length > 0 || content.notes.length > 0;
  if (!hasRisk) return null;
  return (
    <div className="wf-section">
      <span className="wf-label">影响与风险</span>
      {content.running.map((r) => (
        <p key={r} className="wf-risk">有 attempt 正在运行：{r}。它不受影响，但这次改动需要你确认。</p>
      ))}
      {content.warnings.map((w, i) => (
        <p key={`w${i}`} className="wf-risk">{w}</p>
      ))}
      {content.notes.map((n, i) => (
        <p key={`n${i}`} className="wf-note">{n}</p>
      ))}
    </div>
  );
}

function Content({ content }: { content: ConfirmContent }) {
  return (
    <div className="wf-content">
      <div className="wf-section">
        <span className="wf-label">将运行的命令</span>
        <CommandLine command={content.command} size="sm" onCopy={() => {}} />
      </div>
      <div className="wf-section">
        <span className="wf-label">变化</span>
        <Changes changes={content.changes} />
      </div>
      <Risks content={content} />
    </div>
  );
}

function Body({ view }: { view: FlowView }): ReactNode {
  switch (view.phase) {
    case 'previewing':
      return (
        <div className="wf-section">
          <span className="wf-label">变化</span>
          <Skeleton />
        </div>
      );
    case 'confirmable':
      return (
        <>
          {view.notice && <Banner tone="info">{view.notice}</Banner>}
          <Content content={view.content} />
        </>
      );
    case 'executing':
    case 'rereading':
      return <Content content={view.content} />;
    case 'confirming':
      return (
        <>
          <Banner tone="info">连接中断，正在确认结果…</Banner>
          <Content content={view.content} />
        </>
      );
    case 'doneWithWarning':
      return (
        <Banner tone="warning">
          {view.warnings.map((w, i) => (
            <p key={i} className="wf-warn-line">{w}</p>
          ))}
        </Banner>
      );
    case 'failed':
      return (
        <Banner tone="danger">
          {view.reason && <span className="wf-reason">{view.reason}</span>}
          <pre className="wf-error">{view.error}</pre>
        </Banner>
      );
    case 'partiallyWritten':
      return (
        <Banner tone="warning">
          <span className="wf-partial">已部分写入，结果待核实</span>
          {view.reason && <span className="wf-reason">{view.reason}</span>}
          <pre className="wf-error">{view.error}</pre>
        </Banner>
      );
    case 'unknown':
      return <Banner tone="warning">结果未知，请在历史与审计里核对</Banner>;
    case 'stale':
      return <Banner tone="warning">配置在你确认之前被改动了，请重新预览</Banner>;
    case 'expired':
      return <Banner tone="warning">确认已失效（过期、已用过或参数不符），请重新预览</Banner>;
    case 'rereadFailed':
      return (
        <Banner tone="warning">
          <span>命令已成功，但重新读取失败，请刷新</span>
          {view.warnings.map((w, i) => (
            <p key={i} className="wf-warn-line">{w}</p>
          ))}
        </Banner>
      );
    case 'rejected':
      return (
        <Banner tone="danger">
          <span className="wf-reason">请求被拒</span>
          <pre className="wf-error">{view.error}</pre>
        </Banner>
      );
    case 'previewFailed':
      return <Banner tone="danger">{view.message}</Banner>;
    default:
      return null;
  }
}

function Footer({ view, onCancel, onConfirm, onRepreview, onAck, onHistory }: WriteConfirmDialogProps): ReactNode {
  switch (view.phase) {
    case 'previewing':
      return (
        <>
          <Button variant="secondary" onClick={onCancel}>取消</Button>
          <Button variant="primary" disabled>确认…</Button>
        </>
      );
    case 'confirmable':
      return (
        <>
          <Button variant="secondary" onClick={onCancel}>取消</Button>
          <Button variant="primary" onClick={onConfirm}>确认…</Button>
        </>
      );
    case 'executing':
      return (
        <>
          <Button variant="secondary" disabled>取消</Button>
          <Button variant="primary" loading loadingText="执行中…">确认…</Button>
        </>
      );
    case 'confirming':
      return (
        <>
          <Button variant="secondary" disabled>取消</Button>
          <Button variant="primary" loading loadingText="确认结果中…">确认…</Button>
        </>
      );
    case 'rereading':
      return (
        <>
          <Button variant="secondary" disabled>取消</Button>
          <Button variant="primary" loading loadingText="重读中…">确认…</Button>
        </>
      );
    case 'doneWithWarning':
      return <Button variant="primary" onClick={onAck}>知道了</Button>;
    case 'failed':
      return (
        <>
          <Button variant="secondary" onClick={onRepreview}>重新预览</Button>
          <Button variant="primary" onClick={onCancel}>关闭</Button>
        </>
      );
    case 'partiallyWritten':
      return (
        <>
          <Button variant="secondary" onClick={onHistory}>查看历史</Button>
          <Button variant="primary" onClick={onCancel}>关闭</Button>
        </>
      );
    case 'unknown':
      return (
        <>
          <Button variant="secondary" onClick={onHistory}>打开历史</Button>
          <Button variant="primary" onClick={onCancel}>关闭</Button>
        </>
      );
    case 'stale':
    case 'expired':
      return <Button variant="primary" onClick={onRepreview}>重新预览</Button>;
    case 'rereadFailed':
    case 'rejected':
      return <Button variant="primary" onClick={onCancel}>关闭</Button>;
    case 'previewFailed':
      return (
        <>
          <Button variant="secondary" onClick={onRepreview}>重新预览</Button>
          <Button variant="primary" onClick={onCancel}>关闭</Button>
        </>
      );
    default:
      return null;
  }
}

export function WriteConfirmDialog(props: WriteConfirmDialogProps) {
  const { open, title, view, onCancel } = props;
  const dismissible = !LOCKED_PHASES.has(view.phase);
  return (
    <Dialog open={open} onClose={onCancel} title={title} dismissible={dismissible} footer={<Footer {...props} />}>
      <Body view={view} />
    </Dialog>
  );
}
