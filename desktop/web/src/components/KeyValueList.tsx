// 键值列表（组件板 :451、UI 文档 7.23）：dl，每项一对 dt、dd；两列网格，标签列 minmax(96px, max-content)、值列 minmax(0, 1fr)。
import { Fragment } from 'react';
import './KeyValueList.css';

export interface KeyValueItem {
  label: string;
  value: string;
  /** 值用等宽。 */
  mono?: boolean;
}

export interface KeyValueListProps {
  items: KeyValueItem[];
}

export function KeyValueList({ items }: KeyValueListProps) {
  return (
    <dl className="tt-kv">
      {items.map((item, i) => (
        <Fragment key={`${item.label}-${i}`}>
          <dt className="tt-kv__key">{item.label}</dt>
          <dd className={item.mono ? 'tt-kv__val tt-kv__val--mono' : 'tt-kv__val'}>{item.value}</dd>
        </Fragment>
      ))}
    </dl>
  );
}
