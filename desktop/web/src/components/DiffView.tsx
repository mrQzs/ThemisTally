// 差异视图（UI 文档 7.14、详情页 :387–461）：把 candidate.patch 解析成文件列表与差异行，只按文本显示。
// 自带 git 补丁解析（./diff/parseDiff）与分屏配对（./diff/splitPairs）；来自补丁的文字显示前用 T007 的 stripAnsi。
// 不解释 HTML、不把网址变链接；不渲染 role=status、对话框、菜单；不调 matchMedia、scrollIntoView 等。
import { Fragment, useId, useRef, useState, type ReactNode } from 'react';
import { ChevronDownIcon, ChevronRightIcon, FileDiffIcon } from '../icons';
import { Button } from './Button';
import { SegmentedControl } from './SegmentedControl';
import { Switch } from './Switch';
import { IconButton } from './IconButton';
import { parseDiff, type DiffFile, type DiffLine } from './diff/parseDiff';
import { splitPairs } from './diff/splitPairs';
import { stripAnsi } from './evidence/ansi';
import './DiffView.css';

const MINUS = '−';
const DOT = '·';
const ARROW = ' → ';

export type DiffMode = 'unified' | 'split';

export interface DiffViewProps {
  /** 补丁原文。 */
  patch: string;
  /** 摘要里的标题（通常是 candidate.patch）。 */
  title?: string;
  /** 补丁没有读完：根末尾显示提示条，最后一个文件的注记加「未读完」。 */
  truncated?: boolean;
  /** 点 [继续加载] 时调用。 */
  onLoadMore?: () => void;
  /** 正在加载：[继续加载] 转圈。 */
  loadingMore?: boolean;
  /** 初始显示方式，缺省 unified。 */
  defaultMode?: DiffMode;
  /** 初始是否自动换行，缺省关。 */
  defaultWrap?: boolean;
  className?: string;
}

/** 显示用的路径：deleted 用 oldPath，其余用 newPath；去 ANSI 后只作文本/标题。 */
function displayPath(file: DiffFile): string {
  const raw = file.status === 'deleted' ? file.oldPath : file.newPath;
  return stripAnsi(raw ?? '');
}

function headName(file: DiffFile): string {
  if (file.status === 'renamed') return `${stripAnsi(file.oldPath ?? '')}${ARROW}${stripAnsi(file.newPath ?? '')}`;
  return displayPath(file);
}

function isDefaultCollapsed(file: DiffFile): boolean {
  return !file.binary && file.status === 'added';
}

export function DiffView({
  patch,
  title,
  truncated = false,
  onLoadMore,
  loadingMore = false,
  defaultMode = 'unified',
  defaultWrap = false,
  className,
}: DiffViewProps) {
  const [mode, setMode] = useState<DiffMode>(defaultMode);
  const [wrap, setWrap] = useState(defaultWrap);
  const [current, setCurrent] = useState(0);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const baseId = useId();
  const headRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const files = parseDiff(patch);
  // 当前文件序号越界就回到第一个（patch 变化后）。
  if (files.length > 0 && current >= files.length) setCurrent(0);

  const totalAdd = files.reduce((n, f) => n + f.additions, 0);
  const totalDel = files.reduce((n, f) => n + f.deletions, 0);

  const keyOf = (i: number, file: DiffFile) => `${i}::${displayPath(file)}`;
  const collapsedOf = (i: number, file: DiffFile) => collapsed[keyOf(i, file)] ?? isDefaultCollapsed(file);

  const onToggle = (i: number, file: DiffFile) => {
    const key = keyOf(i, file);
    setCollapsed((prev) => ({ ...prev, [key]: !(prev[key] ?? isDefaultCollapsed(file)) }));
  };
  const onPick = (i: number, file: DiffFile) => {
    setCurrent(i);
    if (!file.binary && collapsedOf(i, file)) setCollapsed((prev) => ({ ...prev, [keyOf(i, file)]: false }));
    headRefs.current[i]?.focus();
  };

  const rootClass = ['tt-diff', className].filter(Boolean).join(' ');
  const bodyId = (i: number) => `${baseId}-b${i}`;
  const nameId = (i: number) => `${baseId}-n${i}`;
  const btnId = (i: number) => `${baseId}-f${i}`;

  const counts = (file: DiffFile): ReactNode => (
    <>
      <span className="tt-num">{`+${file.additions}`}</span>
      <span className="tt-num">{`${MINUS}${file.deletions}`}</span>
    </>
  );

  const eof = (line: DiffLine) =>
    line.noNewline ? <span className="tt-diff__eof">（文件末尾没有换行）</span> : null;

  const renderUnified = (file: DiffFile) => (
    <div className="tt-diff__table">
      {file.hunks.map((hunk, hi) => (
        <Fragment key={hi}>
          <div className="tt-diff__row" data-kind="hunk">{stripAnsi(hunk.header)}</div>
          {hunk.lines.map((line, li) => (
            <div className="tt-diff__row" data-kind={line.kind} key={li}>
              <span className="tt-diff__no tt-num" aria-hidden="true">{line.oldNo ?? ''}</span>
              <span className="tt-diff__no tt-num" aria-hidden="true">{line.newNo ?? ''}</span>
              <span className="tt-diff__sign">{line.kind === 'add' ? '+' : line.kind === 'del' ? MINUS : ''}</span>
              <span className="tt-diff__text">{stripAnsi(line.text)}{eof(line)}</span>
            </div>
          ))}
        </Fragment>
      ))}
    </div>
  );

  const side = (s: 'left' | 'right', kind: string, no: string, sign: string, text: string, mark: boolean) => (
    <Fragment key={s}>
      <span className="tt-diff__no tt-num" data-side={s} data-kind={kind} aria-hidden="true">{no}</span>
      <span className="tt-diff__sign" data-side={s} data-kind={kind}>{sign}</span>
      <span className="tt-diff__text" data-side={s} data-kind={kind}>{text}{mark ? <span className="tt-diff__eof">（文件末尾没有换行）</span> : null}</span>
    </Fragment>
  );
  const emptySide = (s: 'left' | 'right') => side(s, 'empty', '', '', '', false);

  const renderSplit = (file: DiffFile) => (
    <div className="tt-diff__table">
      {file.hunks.map((hunk, hi) => (
        <Fragment key={hi}>
          <div className="tt-diff__row" data-kind="hunk">{stripAnsi(hunk.header)}</div>
          {splitPairs(hunk.lines).map((row, ri) => (
            <div className="tt-diff__row" data-kind="pair" key={ri}>
              {row.kind === 'context'
                ? (
                  <>
                    {side('left', 'context', String(row.line.oldNo ?? ''), '', stripAnsi(row.line.text), row.line.noNewline)}
                    {side('right', 'context', String(row.line.newNo ?? ''), '', stripAnsi(row.line.text), row.line.noNewline)}
                  </>
                )
                : (
                  <>
                    {row.left
                      ? side('left', row.left.kind, String(row.left.oldNo ?? ''), row.left.kind === 'del' ? MINUS : '', stripAnsi(row.left.text), row.left.noNewline)
                      : emptySide('left')}
                    {row.right
                      ? side('right', row.right.kind, String(row.right.newNo ?? ''), row.right.kind === 'add' ? '+' : '', stripAnsi(row.right.text), row.right.noNewline)
                      : emptySide('right')}
                  </>
                )}
            </div>
          ))}
        </Fragment>
      ))}
    </div>
  );

  return (
    <div className={rootClass} data-mode={mode} data-wrap={wrap ? 'true' : 'false'}>
      <div className="tt-diff__bar">
        <span className="tt-diff__summary">
          <FileDiffIcon width={16} height={16} />
          {title != null && <span className="tt-diff__summary-title">{title}</span>}
          {title != null && <span className="tt-diff__summary-sep">{` ${DOT} `}</span>}
          <span>{`${files.length} 个文件`}</span>
          <span className="tt-diff__summary-sep">{` ${DOT} `}</span>
          <span className="tt-diff__plus">{`+${totalAdd}`}</span>
          <span className="tt-diff__summary-sep"> </span>
          <span className="tt-diff__minus">{`${MINUS}${totalDel}`}</span>
        </span>
        <SegmentedControl
          aria-label="差异显示方式"
          value={mode}
          onChange={(v) => setMode(v as DiffMode)}
          options={[{ value: 'unified', label: '统一' }, { value: 'split', label: '分屏' }]}
        />
        <Switch label="自动换行" checked={wrap} onChange={setWrap} />
      </div>
      {files.length === 0 ? (
        <div className="tt-diff__empty">补丁里没有改动</div>
      ) : (
        <div className="tt-diff__main tt-stack-narrow">
          <ul className="tt-diff__files" aria-label="文件">
            {files.map((file, i) => (
              <li key={i}>
                <button
                  type="button"
                  className="tt-diff__file-item"
                  aria-current={i === current ? 'true' : undefined}
                  onClick={() => onPick(i, file)}
                >
                  <span className="tt-diff__file-path" title={displayPath(file)}>
                    <span>{displayPath(file)}</span>
                  </span>
                  {file.binary ? <span className="tt-diff__binary-tag">二进制</span> : counts(file)}
                </button>
              </li>
            ))}
          </ul>
          <div className="tt-diff__content">
            {files.map((file, i) => {
              const isCollapsed = !file.binary && collapsedOf(i, file);
              const noteParts: string[] = [];
              if (file.status === 'added') noteParts.push('新文件');
              if (file.status === 'deleted') noteParts.push('已删除');
              if (isCollapsed) noteParts.push('已折叠');
              if (truncated && i === files.length - 1) noteParts.push('未读完');
              const note = noteParts.join(` ${DOT} `);
              return (
                <section
                  className="tt-diff__file"
                  key={i}
                  data-status={file.status}
                  data-binary={file.binary ? 'true' : 'false'}
                  data-collapsed={isCollapsed ? 'true' : 'false'}
                >
                  <div className="tt-diff__file-head" tabIndex={-1} ref={(el) => { headRefs.current[i] = el; }}>
                    {!file.binary && (
                      <IconButton
                        size="sm"
                        id={btnId(i)}
                        label={isCollapsed ? '展开' : '折叠'}
                        aria-labelledby={`${btnId(i)} ${nameId(i)}`}
                        aria-expanded={isCollapsed ? 'false' : 'true'}
                        aria-controls={bodyId(i)}
                        icon={isCollapsed ? <ChevronRightIcon width={14} height={14} /> : <ChevronDownIcon width={14} height={14} />}
                        onClick={() => onToggle(i, file)}
                      />
                    )}
                    <span className="tt-diff__file-name" id={nameId(i)} title={headName(file)}>{headName(file)}</span>
                    {note !== '' && <span className="tt-diff__file-note">{note}</span>}
                    {!file.binary && counts(file)}
                  </div>
                  <div className="tt-diff__file-body" id={bodyId(i)} hidden={isCollapsed ? true : undefined}>
                    {!isCollapsed && (
                      file.binary ? (
                        <div className="tt-diff__placeholder">二进制文件，不显示内容</div>
                      ) : file.hunks.length === 0 ? (
                        <div className="tt-diff__placeholder">没有内容改动</div>
                      ) : mode === 'split' ? (
                        renderSplit(file)
                      ) : (
                        renderUnified(file)
                      )
                    )}
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      )}
      {truncated && (
        <div className="tt-diff__foot">
          <span>补丁没有读完，只显示了已读到的部分</span>
          {onLoadMore != null &&
            (loadingMore ? (
              <Button loading loadingText="正在加载…" variant="secondary" size="sm">继续加载</Button>
            ) : (
              <Button variant="secondary" size="sm" onClick={onLoadMore}>继续加载</Button>
            ))}
        </div>
      )}
    </div>
  );
}
