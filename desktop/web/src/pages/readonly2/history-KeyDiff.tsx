// 键级差异（合同 D07）：三列 键、之前、之后；之前写「− 值」、之后写「+ 值」；
// null 写「未设置」（不带符号与底色），遮蔽占位用 MaskedValue（不带底色），对象与数组写 JSON 文本。
import { isMaskedPlaceholder, MaskedValue } from '../../components';
import type { HistoryKeyDiff } from './history-logic';
import './history-styles.css';

const MINUS = String.fromCharCode(0x2212);

function valueText(value: unknown): string {
  if (value === null || value === undefined) return '未设置';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value) ?? '';
}

function Cell({ value, side }: { value: unknown; side: 'del' | 'add' }) {
  if (value === null || value === undefined) {
    return <span className="r2-diff__none">未设置</span>;
  }
  if (typeof value === 'string' && isMaskedPlaceholder(value)) {
    return (
      <span className="r2-diff__cell">
        <MaskedValue>{value}</MaskedValue>
      </span>
    );
  }
  return (
    <span className={`r2-diff__cell r2-diff__cell--${side}`}>
      {side === 'del' ? MINUS : '+'} {valueText(value)}
    </span>
  );
}

/** 第 4 种情形里的逐键行：之前与之后两格都用 MaskedValue 显示同一个占位，不带底色。 */
export function MaskedKeyDiff({ placeholder, keys }: { placeholder: string; keys: readonly string[] }) {
  return (
    <div className="r2-diff">
      <div className="r2-diff__head">
        <span>键</span>
        <span>之前</span>
        <span>之后</span>
      </div>
      {keys.map((k) => (
        <div className="r2-diff__row" key={k}>
          <code className="r2-diff__key">{k}</code>
          <span className="r2-diff__cell">
            <MaskedValue>{placeholder}</MaskedValue>
          </span>
          <span className="r2-diff__cell">
            <MaskedValue>{placeholder}</MaskedValue>
          </span>
        </div>
      ))}
    </div>
  );
}

export function KeyDiff({ diff }: { diff: readonly HistoryKeyDiff[] }) {
  return (
    <div className="r2-diff">
      <div className="r2-diff__head">
        <span>键</span>
        <span>之前</span>
        <span>之后</span>
      </div>
      {diff.map((k) => (
        <div className="r2-diff__row" key={k.key}>
          <code className="r2-diff__key">{k.key}</code>
          <Cell value={k.old} side="del" />
          <Cell value={k.new} side="add" />
        </div>
      ))}
    </div>
  );
}
