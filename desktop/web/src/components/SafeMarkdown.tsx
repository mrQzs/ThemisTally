// 安全 Markdown（UI 文档 7.12、Attempt 画面 :105–118）：摘要与复审记录用。
// 只渲染标题、段落、列表、表格、代码块、粗体、斜体、行内代码与放行的 http(s) 链接；原始 HTML 当文字，
// 链接不渲染 a 与网址属性，点击时交给调用方（onOpenLink）。解析在 evidence/markdown.ts，是纯函数。
import { Fragment, type ReactNode } from 'react';
import { parseMarkdown, type MdAlign, type MdBlock, type MdInline } from './evidence/markdown';
import './SafeMarkdown.css';

export interface SafeMarkdownProps {
  /** Markdown 原文（不可信）。 */
  source: string;
  /** 点放行的链接时调用，参数是原网址。 */
  onOpenLink: (url: string) => void;
  className?: string;
}

function alignClass(align: MdAlign): string | undefined {
  if (align === 'left') return 'tt-md__al-left';
  if (align === 'right') return 'tt-md__al-right';
  if (align === 'center') return 'tt-md__al-center';
  return undefined;
}

function renderInlines(nodes: readonly MdInline[], onOpenLink: (url: string) => void): ReactNode[] {
  return nodes.map((node, i) => {
    switch (node.type) {
      case 'text':
        return <Fragment key={i}>{node.value}</Fragment>;
      case 'code':
        return <code key={i}>{node.value}</code>;
      case 'strong':
        return <strong key={i}>{renderInlines(node.children, onOpenLink)}</strong>;
      case 'em':
        return <em key={i}>{renderInlines(node.children, onOpenLink)}</em>;
      case 'link':
        return (
          <Fragment key={i}>
            <button type="button" className="tt-md__link" onClick={() => onOpenLink(node.url)}>
              {renderInlines(node.children, onOpenLink)}
            </button>
            <span className="tt-md__url">{node.url}</span>
          </Fragment>
        );
      default:
        return null;
    }
  });
}

function renderBlocks(list: readonly MdBlock[], onOpenLink: (url: string) => void): ReactNode[] {
  return list.map((block, i) => {
    switch (block.type) {
      case 'heading': {
        const Tag = `h${Math.min(block.level + 1, 6)}` as 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
        return <Tag key={i}>{renderInlines(block.inlines, onOpenLink)}</Tag>;
      }
      case 'paragraph':
        return <p key={i}>{renderInlines(block.inlines, onOpenLink)}</p>;
      case 'code':
        return (
          <pre key={i}>
            <code>{block.text}</code>
          </pre>
        );
      case 'list': {
        const items = block.items.map((item, j) => (
          <li key={j}>
            {item.inlines.length > 0 && <p>{renderInlines(item.inlines, onOpenLink)}</p>}
            {renderBlocks(item.children, onOpenLink)}
          </li>
        ));
        return block.ordered ? (
          <ol key={i} start={block.start ?? undefined}>
            {items}
          </ol>
        ) : (
          <ul key={i}>{items}</ul>
        );
      }
      case 'table':
        return (
          <div className="tt-md__scroll" key={i}>
            <table>
              <thead>
                <tr>
                  {block.header.map((cell, j) => (
                    <th key={j} scope="col" className={alignClass(cell.align)}>
                      {renderInlines(cell.inlines, onOpenLink)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, r) => (
                  <tr key={r}>
                    {row.map((cell, c) => (
                      <td key={c} className={alignClass(cell.align)}>
                        {renderInlines(cell.inlines, onOpenLink)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      default:
        return null;
    }
  });
}

export function SafeMarkdown({ source, onOpenLink, className }: SafeMarkdownProps) {
  const rootClass = className ? `tt-md ${className}` : 'tt-md';
  return <div className={rootClass}>{renderBlocks(parseMarkdown(source), onOpenLink)}</div>;
}
