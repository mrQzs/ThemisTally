// 文本查看器（UI 文档 7.12、领域板 :351–363、Attempt 画面 :320–337）：不可信内容只按文本节点显示。
// 不解释 HTML、去掉 ANSI 转义序列、不把网址自动变成链接；大文件按页加载，一行的分片接起来显示，
// 服务只给占位的行显示成不能展开的隐藏行；文件已变化（409）时在头部与行之间显示 info 提示条。
import { useState, type Ref, type ReactNode, type UIEvent } from 'react';
import { CopyIcon, EyeOffIcon } from '../icons';
import { Banner } from './Banner';
import { Button } from './Button';
import { IconButton } from './IconButton';
import { pagesToLines, type ViewerLine, type ViewerPage } from './evidence/viewerLines';
import './TextViewer.css';

export type { ViewerLine, ViewerPage } from './evidence/viewerLines';

export interface TextViewerProps {
  /** 头部标题（通常是文件名）。 */
  title?: string;
  /** 已加载的各页（顺序即到达顺序）。 */
  pages: readonly ViewerPage[];
  /** 还有没有下一页。 */
  hasMore: boolean;
  /** 点 [继续加载] 时调用。 */
  onLoadMore?: () => void;
  /** 正在加载下一页：底栏按钮转圈，两处 [继续加载] 禁用。 */
  loadingMore?: boolean;
  /** 文件已变化（409）：显示提示条。 */
  changed?: boolean;
  /** 点 [从头读取] 时调用。 */
  onReload?: () => void;
  /** 点复制钮时调用，参数是各文字行用换行连接（隐藏行跳过）。 */
  onCopy: (text: string) => void;
  /** 行号开关的初始状态，缺省开。 */
  defaultLineNumbers?: boolean;
  /** 换行开关的初始状态，缺省关。 */
  defaultWrap?: boolean;
  className?: string;
  /** 指向放行的主体元素 div.tt-viewer__body（甲：日志跟随据此滚到底）。 */
  bodyRef?: Ref<HTMLDivElement>;
  /** 挂在主体元素上的 scroll 回调（scroll 不委托，监听在滚动元素本身）。 */
  onBodyScroll?: (event: UIEvent<HTMLDivElement>) => void;
  /** 加在主体元素 class 上的额外类名（甲：日志跟随用它加限高）。 */
  bodyClassName?: string;
  /** 头部最右端、复制钮之后的额外内容（甲：日志跟随的过滤框与跟随开关）。 */
  headerExtra?: ReactNode;
  /** 主体与底栏之间、占满宽度且不随主体滚动的额外内容（甲：日志跟随的底部状态）。 */
  bottomBar?: ReactNode;
  /** 非空时按 §3 规则过滤显示的行（不分大小写子串，匹配拼好分片、去 ANSI 后的整行；隐藏行不显示，行号不变）。 */
  filter?: string;
}

function hiddenText(reason: string): string {
  if (reason === 'not_json') return '这一行不是合法 JSON，已隐藏';
  if (reason === 'too_long') return '这一行超过 4 MiB，已隐藏';
  return `这一行已隐藏：${reason}`;
}

export function TextViewer({
  title,
  pages,
  hasMore,
  onLoadMore,
  loadingMore = false,
  changed = false,
  onReload,
  onCopy,
  defaultLineNumbers = true,
  defaultWrap = false,
  className,
  bodyRef,
  onBodyScroll,
  bodyClassName,
  headerExtra,
  bottomBar,
  filter,
}: TextViewerProps) {
  const [lineNumbers, setLineNumbers] = useState(defaultLineNumbers);
  const [wrap, setWrap] = useState(defaultWrap);
  const [dismissed, setDismissed] = useState(false);
  const [prevChanged, setPrevChanged] = useState(changed);
  // 关闭过的提示条：changed 仍是真时不重新出现，从假再变真时重新出现。
  if (changed !== prevChanged) {
    setPrevChanged(changed);
    if (changed) setDismissed(false);
  }
  const lines = pagesToLines(pages);
  // 提示条藏起来只是不显示，[继续加载] 的禁用单独看 changed（文件已变化时不许再翻页）。
  const showBanner = changed && !dismissed;
  // 过滤（甲，§3）：空串不过滤；否则不分大小写匹配拼好分片、去 ANSI 后的整行；隐藏行不显示。
  const filtering = filter != null && filter !== '';
  const needle = filtering ? filter.toLowerCase() : '';
  const indexed = lines.map((line, i) => ({ line, i }));
  const rows = filtering
    ? indexed.filter(({ line }) => line.hidden == null && line.text.toLowerCase().includes(needle))
    : indexed;
  const copyText = () => onCopy(rows.filter(({ line }) => line.hidden == null).map(({ line }) => line.text).join('\n'));
  const lastIndex = lines.length - 1;

  const rootClass = ['tt-viewer', lineNumbers ? '' : 'tt-viewer--no-num', wrap ? 'tt-viewer--wrap' : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  const bodyClass = ['tt-viewer__body', bodyClassName].filter(Boolean).join(' ');
  return (
    <div className={rootClass}>
      <div className="tt-viewer__head">
        <span className="tt-viewer__title">{title}</span>
        <div className="tt-viewer__tools">
          <button
            type="button"
            className="tt-viewer__toggle"
            aria-pressed={lineNumbers}
            onClick={() => setLineNumbers((v) => !v)}
          >
            行号
          </button>
          <button
            type="button"
            className="tt-viewer__toggle"
            aria-pressed={wrap}
            onClick={() => setWrap((v) => !v)}
          >
            换行
          </button>
          <IconButton size="sm" label="复制已显示的文字" tooltip="复制" icon={<CopyIcon width={14} height={14} />} onClick={copyText} />
          {headerExtra}
        </div>
      </div>
      {showBanner && (
        <Banner
          tone="info"
          onClose={() => setDismissed(true)}
          action={
            onReload != null ? (
              <Button variant="secondary" size="sm" onClick={onReload}>
                从头读取
              </Button>
            ) : undefined
          }
        >
          文件已变化
        </Banner>
      )}
      <div className={bodyClass} ref={bodyRef} onScroll={onBodyScroll}>
        {filtering && rows.length === 0 ? (
          <div className="tt-viewer__empty">没有匹配的行</div>
        ) : (
          rows.map(({ line, i }) => {
            const parted = line.part != null && line.parts != null;
            const tail = parted && line.part! < line.parts! && i === lastIndex && hasMore;
            return (
              <div className="tt-viewer__row" key={line.n}>
                {lineNumbers && (
                  <span className="tt-viewer__num tt-num" aria-hidden="true">
                    {line.n}
                  </span>
                )}
                <div className="tt-viewer__content">
                  {parted && <span className="tt-viewer__part">{`第 ${line.part}/${line.parts} 片`}</span>}
                  {line.hidden != null ? (
                    <span className="tt-viewer__hidden">
                      <EyeOffIcon width={14} height={14} />
                      <span>{hiddenText(line.hidden)}</span>
                    </span>
                  ) : (
                    <span className="tt-viewer__text">{line.text}</span>
                  )}
                  {tail && (
                    <Button variant="secondary" size="sm" disabled={changed || loadingMore} onClick={onLoadMore}>
                      继续加载
                    </Button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
      {bottomBar}
      <div className="tt-viewer__foot">
        <span>{`已显示 ${pages.length} 页`}</span>
        {!hasMore && <span>已到末尾</span>}
        {hasMore && onLoadMore != null &&
          (loadingMore ? (
            <Button variant="secondary" size="sm" loading loadingText="正在加载…">
              继续加载
            </Button>
          ) : (
            <Button variant="secondary" size="sm" disabled={changed} onClick={onLoadMore}>
              继续加载
            </Button>
          ))}
      </div>
    </div>
  );
}
