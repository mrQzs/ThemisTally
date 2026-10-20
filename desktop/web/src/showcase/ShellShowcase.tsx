// 应用框架演示（合同第 11 条）：两节。data-demo=page-states 五个链接打开总览页的 ?mock= 五态；
// data-demo=disabled-action 四个禁用的写操作入口（站主 Q7 的写法）。
import { DisabledAction } from '../shell/DisabledAction';
import './showcase-shell.css';

const MOCK_LINKS: ReadonlyArray<{ mock: string; label: string }> = [
  { mock: 'loading', label: '加载中' },
  { mock: 'data', label: '有数据' },
  { mock: 'empty', label: '空' },
  { mock: 'error', label: '出错' },
  { mock: 'offline', label: '断线' },
];

export default function ShellShowcase() {
  return (
    <>
      <section className="showcase__section" data-demo="page-states">
        <h2 className="showcase__h2">页面框架 · 五态</h2>
        <div className="showcase__row">
          {MOCK_LINKS.map((m) => (
            <a key={m.mock} className="showcase-shell__link" href={`#/overview?mock=${m.mock}`}>
              {m.label}
            </a>
          ))}
        </div>
        <p className="showcase__muted">打开总览页并带上对应的 ?mock=，看页面框架的加载、有数据、空、出错与断线五种状态。</p>
      </section>

      <section className="showcase__section" data-demo="disabled-action">
        <h2 className="showcase__h2">禁用的写操作入口</h2>
        <div className="showcase__row">
          <DisabledAction label="切换…" />
          <DisabledAction label="更改…" />
          <DisabledAction label="删除" variant="danger" />
          <DisabledAction label="启用…" />
        </div>
        <p className="showcase__muted">第一阶段不做的写操作：禁用的按钮，悬停或聚焦 400ms 后提示「第二阶段接入」。</p>
      </section>
    </>
  );
}
