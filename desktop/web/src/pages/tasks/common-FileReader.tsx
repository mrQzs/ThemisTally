// 页签里的文件读取（合同 §4 的 K8）：读一个证据文件，转成 TextViewer 的页，管分页与行内出错。
// 读取中写「正在读取 <路径>…」；出错写「没能读到 <路径>：命令（<command>）返回退出码 N。」，messages 进 pre 按纯文本显示。
// 都不设 role，也不嵌套 PageFrame。
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Envelope, FileData } from '../../api';
import type { ViewerPage } from '../../components/evidence/viewerLines';

export type FileReadStatus = 'loading' | 'error' | 'data';

export interface FileRead {
  status: FileReadStatus;
  command: string[];
  exit_code: number;
  messages: string[];
  /** 已读到的各页（顺序即到达顺序）。 */
  pages: ViewerPage[];
  /** 还有没有下一页。 */
  hasMore: boolean;
  loadingMore: boolean;
  loadMore: () => void;
  /** 追加一页（事件页签的跟随模拟用）。 */
  append: (page: ViewerPage) => void;
}

interface LooseFile {
  mode?: string;
  text?: string;
  lines?: readonly unknown[];
  done?: boolean;
  next_cursor?: string | null;
}

/** jsonl 模式的一行：给文字（可分片）或只给隐藏原因。 */
type JsonlLineLike =
  | { n: number; text: string; part?: number; parts?: number }
  | { n: number; hidden: string };

/** FileData 的 mode 是字符串，交给 TextViewer 之前转成 ViewerPage。 */
export function toViewerPage(data: FileData): ViewerPage {
  const loose = data as unknown as LooseFile;
  if (loose.mode === 'jsonl') {
    return { mode: 'jsonl', lines: (loose.lines ?? []) as JsonlLineLike[] };
  }
  return { mode: 'text', text: loose.text ?? '' };
}

/** 读一个证据文件；read 变化（换了文件）时重新读第一页。 */
export function useFilePages(read: (cursor?: string) => Promise<Envelope<FileData>>): FileRead {
  const [pages, setPages] = useState<ViewerPage[]>([]);
  const [status, setStatus] = useState<FileReadStatus>('loading');
  const [err, setErr] = useState<{ command: string[]; exit_code: number; messages: string[] }>({
    command: [], exit_code: 0, messages: [],
  });
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const cursorRef = useRef<string | null>(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    setStatus('loading');
    setPages([]);
    setHasMore(false);
    setLoadingMore(false);
    cursorRef.current = null;
    read().then((env) => {
      if (!aliveRef.current) return;
      if (env.ok && env.data != null) {
        const data = env.data;
        setPages([toViewerPage(data)]);
        setHasMore(data.done !== true);
        cursorRef.current = data.next_cursor ?? null;
        setStatus('data');
      } else {
        setErr({ command: env.command, exit_code: env.exit_code, messages: env.messages });
        setStatus('error');
      }
    });
    return () => {
      aliveRef.current = false;
    };
  }, [read]);

  const loadMore = useCallback(() => {
    const cursor = cursorRef.current;
    if (cursor == null) return;
    setLoadingMore(true);
    read(cursor).then((env) => {
      if (!aliveRef.current) return;
      if (env.ok && env.data != null) {
        const data = env.data;
        setPages((prev) => [...prev, toViewerPage(data)]);
        setHasMore(data.done !== true);
        cursorRef.current = data.next_cursor ?? null;
      }
      setLoadingMore(false);
    });
  }, [read]);

  const append = useCallback((page: ViewerPage) => {
    setPages((prev) => [...prev, page]);
  }, []);

  return { status, command: err.command, exit_code: err.exit_code, messages: err.messages, pages, hasMore, loadingMore, loadMore, append };
}

export interface FileReadNoteProps {
  path: string;
  read: FileRead;
}

/** 一次读取失败的命令、退出码与 messages。 */
export interface ReadFailure {
  command: string[];
  exit_code: number;
  messages: string[];
}

/** 页签内的行内出错块（K8）。 */
export function ReadErrorNote({ path, failure }: { path: string; failure: ReadFailure }) {
  return (
    <div className="tasks-tab__read tasks-tab__read--bad">
      <p className="tasks-tab__read-bad">
        没能读到 {path}：命令（{failure.command.join(' ')}）返回退出码 {failure.exit_code}。
      </p>
      <pre className="tasks-tab__read-msg">{failure.messages.join('\n')}</pre>
    </div>
  );
}

/** 页签内的读取中与行内出错块（K8）。 */
export function FileReadNote({ path, read }: FileReadNoteProps) {
  if (read.status === 'loading') {
    return <p className="tasks-tab__read">正在读取 {path}…</p>;
  }
  if (read.status === 'error') {
    return <ReadErrorNote path={path} failure={read} />;
  }
  return null;
}
