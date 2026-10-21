// 检索结果区（合同 D02）：提交前的说明、出错块、结果头与说明行、按 (task, attempt) 分组、摘录高亮。
// 结果条目不可点（Q4 不做跳行）：整块没有链接、没有可聚焦元素。
import type { SearchData } from '../../mock/readonly2-search';
import { excerptSegments, groupMatches } from './logs-logic';
import './logs-styles.css';

export type SearchState =
  | { kind: 'idle' }
  | { kind: 'error'; command: string[]; exit_code: number; messages: string[] }
  | { kind: 'ok'; q: string; max: number; data: SearchData };

const HINT = '输入 Python 正则表达式后检索；全量检索可能要半分钟左右，建议先选任务缩小范围。';
const NOTE = '摘录取自脱敏之后的文本：被遮蔽的值搜不到是正常的，<redacted> 占位本身能搜到；不合法的、超过 4 MiB 的 JSONL 行不参加搜索。';

function Excerpt({ text, q }: { text: string; q: string }) {
  return (
    <span className="r2-item__text">
      {excerptSegments(text, q).map((seg, i) =>
        seg.hit ? <mark key={i}>{seg.text}</mark> : <span key={i}>{seg.text}</span>,
      )}
    </span>
  );
}

function ErrorBlock({ command, exitCode, messages }: { command: string[]; exitCode: number; messages: string[] }) {
  return (
    <div className="r2-search__error">
      <p className="r2-search__error-cmd">没能检索：命令（{command.join(' ')}）返回退出码 {exitCode}。</p>
      <pre className="r2-search__error-msg">{messages.join('\n')}</pre>
    </div>
  );
}

export function SearchResults({ state }: { state: SearchState }) {
  if (state.kind === 'idle') {
    return (
      <div className="r2-results">
        <div className="r2-results__head">
          <span className="r2-results__title">结果</span>
        </div>
        <p className="r2-results__hint">{HINT}</p>
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="r2-results">
        <div className="r2-results__head">
          <span className="r2-results__title">结果</span>
        </div>
        <ErrorBlock command={state.command} exitCode={state.exit_code} messages={state.messages} />
      </div>
    );
  }

  const { data, max, q } = state;
  const groups = groupMatches(data.matches ?? []);
  return (
    <div className="r2-results">
      <div className="r2-results__head">
        <span className="r2-results__title">结果</span>
        <span className="r2-results__count tt-num">{(data.matches ?? []).length} 条 · 上限 {max}</span>
      </div>
      <div className="r2-results__notes">
        {data.truncated && <p>只显示前 {max} 条匹配</p>}
        {typeof data.skipped_large === 'number' && data.skipped_large > 0 && (
          <p>有 {data.skipped_large} 个文件太大或读不出来，没有搜；请用 CLI 查看</p>
        )}
        {typeof data.skipped_links === 'number' && data.skipped_links > 0 && (
          <p>跳过的链接：<span className="tt-num">{data.skipped_links}</span></p>
        )}
        <p>{NOTE}</p>
      </div>
      {(data.matches ?? []).length === 0 ? (
        <p className="r2-results__empty">没有匹配的行</p>
      ) : (
        groups.map((g) => (
          <div className="r2-group" key={`${g.task}/${g.attempt}`}>
            <div className="r2-group__head">
              <span className="r2-group__name">
                {g.task} · {g.attempt}
              </span>
              {' '}
              <span className="r2-group__count">{g.items.length} 处</span>
            </div>
            {g.items.map((m, i) => (
              <div className="r2-item" key={`${m.path}:${m.line}:${i}`}>
                <span className="r2-item__loc">
                  {m.path}:{m.line}
                </span>
                <Excerpt text={m.text} q={q} />
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}
