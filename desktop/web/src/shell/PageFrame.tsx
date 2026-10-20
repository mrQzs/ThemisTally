// 页面框架（合同第 8 条，照 Main 画布 :63–84、:205–241 与 UI 文档 5.5、6、8.1、8.2）：五态 loading/data/empty/error。
// 挂载时调 load；ok 且 isEmpty 真时渲染 EmptyState，否则 children(data)；ok 假时渲染出错块；Promise 被拒时只写
// 「没有收到服务的回应」。刷新保留数据、按钮进入加载态。只认最近一次请求，卸载后不再写状态，并向 Tab 栏状态段上报。
// 断线时页面头下方一条 danger Banner 与禁用的[重新连接]，有数据时标题旁加「可能已过期」Tag，根元素带 data-stale。
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Button, Banner, EmptyState, Skeleton, Tag } from '../components';
import { CircleXIcon } from '../icons';
import { RefreshCwIcon } from '../icons/frame';
import { DisabledAction } from './DisabledAction';
import { useReportPage } from './ShellStatusContext';
import { currentMock } from '../mock/scenario';
import { shellConnectionState } from '../mock/shell';
import type { Envelope } from '../api';
import './PageFrame.css';

type Phase = 'loading' | 'data' | 'empty' | 'error';

interface ErrorInfo {
  command: string[];
  exit_code: number;
  messages: string[];
}

export interface PageFrameProps<T> {
  title: string;
  description?: string;
  actions?: ReactNode;
  /** 刷新钮文字，缺省「刷新」。 */
  refreshLabel?: string;
  load: () => Promise<Envelope<T>>;
  isEmpty?: (data: T) => boolean;
  empty?: { title: string; description?: string };
  children: (data: T) => ReactNode;
}

export function PageFrame<T>({
  title,
  description,
  actions,
  refreshLabel = '刷新',
  load,
  isEmpty,
  empty,
  children,
}: PageFrameProps<T>) {
  const offline = shellConnectionState(currentMock()) === 'disconnected';
  const [phase, setPhase] = useState<Phase>('loading');
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<ErrorInfo | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const reqRef = useRef(0);
  const mountedRef = useRef(true);
  const reportPage = useReportPage();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const request = useCallback(
    (isRefresh: boolean) => {
      const my = (reqRef.current += 1);
      if (isRefresh) setRefreshing(true);
      load()
        .then((env) => {
          if (!mountedRef.current || my !== reqRef.current) return;
          const now = Date.now();
          if (env.ok && env.data != null) {
            const emptyNow = isEmpty ? isEmpty(env.data) : false;
            if (emptyNow) {
              setData(env.data);
              setErr(null);
              setPhase('empty');
            } else {
              setData(env.data);
              setErr(null);
              setPhase('data');
            }
            reportPage({ phase: 'data', at: now });
          } else {
            setErr({ command: env.command, exit_code: env.exit_code, messages: env.messages });
            setPhase('error');
            reportPage({ phase: 'error', at: now });
          }
          if (isRefresh) setRefreshing(false);
        })
        .catch(() => {
          if (!mountedRef.current || my !== reqRef.current) return;
          const now = Date.now();
          setErr(null);
          setPhase('error');
          reportPage({ phase: 'error', at: now });
          if (isRefresh) setRefreshing(false);
        });
    },
    [load, isEmpty, reportPage],
  );

  // 挂载时首次加载，并向状态段上报「正在读取」。
  useEffect(() => {
    reportPage({ phase: 'loading', at: null });
    request(false);
    // request 依赖稳定的 load/isEmpty/reportPage，挂载跑一次。
  }, [request]);

  const hasData = phase === 'data' || phase === 'empty';

  const renderBody = () => {
    if (phase === 'loading') return <Skeleton />;
    if (phase === 'error') {
      return (
        <div className="tt-page__error">
          <div className="tt-page__error-head">
            <CircleXIcon width={20} height={20} className="tt-page__error-icon" />
            <span className="tt-page__error-title">没能读到数据</span>
          </div>
          {err ? (
            <>
              <p className="tt-page__error-cmd">
                命令（{err.command.join(' ')}）返回退出码 {err.exit_code}。内核报错如下（纯文本，已脱敏）：
              </p>
              <pre className="tt-page__error-msg">{err.messages.join('\n')}</pre>
            </>
          ) : (
            <p className="tt-page__error-cmd">没有收到服务的回应</p>
          )}
          <Button variant="primary" loading={refreshing} loadingText="重试中…" onClick={() => request(true)}>
            <RefreshCwIcon width={16} height={16} />
            重试
          </Button>
        </div>
      );
    }
    if (phase === 'empty' && empty) {
      return <EmptyState title={empty.title} description={empty.description} />;
    }
    return <>{data != null ? children(data) : null}</>;
  };

  return (
    <div className="tt-pad tt-page" data-page-state={phase} data-stale={offline || undefined}>
      <div className="tt-page__head">
        <div className="tt-page__heading">
          <div className="tt-page__title-row">
            <h1 className="tt-page__title">{title}</h1>
            {offline && phase === 'data' && <Tag tone="neutral">可能已过期</Tag>}
          </div>
          {description && <p className="tt-page__desc">{description}</p>}
        </div>
        <div className="tt-page__actions">
          {actions}
          <Button variant="secondary" loading={refreshing} loadingText="刷新中…" onClick={() => request(true)}>
            <RefreshCwIcon width={16} height={16} />
            {refreshLabel}
          </Button>
        </div>
      </div>
      {offline && (
        <Banner tone="danger">
          与本机服务的连接断开。下面是断开前的数据，可能已过期。{' '}
          <DisabledAction label="重新连接" reason="接入本机服务后可用" variant="secondary" size="sm" />
        </Banner>
      )}
      {renderBody()}
    </div>
  );
}
