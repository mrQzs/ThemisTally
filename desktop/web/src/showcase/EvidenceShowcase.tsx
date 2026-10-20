// 第 5 片（T007）陈列页演示：7 节，data-demo 依次为 text-viewer、text-viewer-jsonl、safe-markdown、effort、
// masked-value、command-line、next-step。复用 App.css 的 showcase__* 类；不挂到陈列页（App.tsx 不引用本组件）。
import { useEffect, useRef, useState } from 'react';
import {
  Button,
  CommandLine,
  dispatchCommand,
  EffortPair,
  MaskedValue,
  NextStep,
  SafeMarkdown,
  TextViewer,
} from '../components';
import type { ViewerPage } from '../components/evidence/viewerLines';
import './showcase-evidence.css';

const ESC = '\u001b';
const LOAD_MS = 200;

// 文本查看器：第 1 页是 UI 文档 9.4 :1196–1197 的执行报告原文（含必须原样显示的文字与 ANSI 序列），
// 第 2、3 页是一行长文本的两片（part 1/2、2/2）加几行普通文字。
const REPORT_PAGE = [
  '## 执行报告',
  '',
  '已按合同实现 logs cat。',
  '',
  '<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字',
  '- self_checks: V01–V08 通过',
  '<script>alert(1)</script>',
  ESC + '[31m红色文字' + ESC + '[0m 尾部',
  'https://example.com/attempt/logs-cat/attempt-002',
  '',
].join('\n');
const LONG_HEAD = '{"type":"tool_result","output":"' + 'a'.repeat(160);
const LONG_TAIL = 'b'.repeat(160) + '"}';
const VIEWER_PAGES: ViewerPage[] = [
  { mode: 'text', text: REPORT_PAGE },
  { mode: 'text', text: LONG_HEAD, part: 1, parts: 2 },
  { mode: 'text', text: LONG_TAIL + '\n这一行是长行的第二片加载完之后才出现的。\n第三行。\n', part: 2, parts: 2 },
];

// 文本查看器（jsonl）：UI 文档 9.4 :1203–1210 的 events 页，第 6 行分两片；第二页给第 2/2 片与后面几行。
const JSONL_PAGES: ViewerPage[] = [
  {
    mode: 'jsonl',
    lines: [
      { n: 1, text: '{"type":"agent_start"}' },
      { n: 2, text: '{"type":"tool_execution_end","toolName":"bash","isError":false}' },
      { n: 3, hidden: 'not_json' },
      { n: 4, hidden: 'too_long' },
      { n: 5, text: '{"type":"message_update","api_key":"<redacted>"}' },
      { n: 6, text: '{"type":"tool_result","output":"' + 'a'.repeat(120), part: 1, parts: 2 },
    ],
  },
  {
    mode: 'jsonl',
    lines: [
      { n: 6, text: 'b'.repeat(120) + '"}', part: 2, parts: 2 },
      { n: 7, text: '{"type":"agent_end","exitCode":0}' },
      { n: 8, text: '{"type":"attempt_closed"}' },
    ],
  },
];

// 安全 Markdown：UI 文档 9.3 :1186 的摘要原文，再加带对齐的表、代码块、粗斜体、蛇形名、
// 一个 https 链接、一个 javascript: 链接与几段原始 HTML。
const MD_SOURCE = [
  '# logs-cat.v2 / attempt-002',
  '',
  '- 基线：9461d31',
  '- 模型：bb/step-5-preview · thinking high',
  '- 用时：28 分 39 秒；token 4,210,385；费用未知',
  '- 检查：8/8（fresh）',
  '- 越界：0',
  '- effort_requested 与 effort_effective 的读法见思考档位一节',
  '',
  '## 复审需要关注',
  '',
  '- 无',
  '',
  '## 表格与代码',
  '',
  '| 检查 | 结果 | 说明 |',
  '|:--|--:|:--:|',
  '| V01 | 通过 | 门禁 |',
  '| V02 | 通过 | 回归 |',
  '',
  '```bash',
  'bash scripts/dispatch-pi.sh logs cat',
  '```',
  '',
  '**粗体** 与 *斜体*；snake_case_name 里的下划线不变斜体。',
  '',
  '[UI 文档](https://example.com/docs/ui-design) 与 [这一条被拒](javascript:alert(1))。',
  '',
  '<img src=x onerror=alert(1)>',
  '',
  '<script>alert(1)</script>',
  '',
  '<b>bold</b> 与 &amp; 与 &lt;i&gt; 都按文字显示。',
].join('\n');

function useLoader(total: number) {
  const [count, setCount] = useState(1);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
  }, []);
  const hasMore = count < total;
  const loadMore = () => {
    if (loading || !hasMore) return;
    setLoading(true);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      setLoading(false);
      setCount((c) => Math.min(c + 1, total));
    }, LOAD_MS);
  };
  const reset = () => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = null;
    setLoading(false);
    setCount(1);
  };
  return { count, loading, hasMore, loadMore, reset };
}

function TextViewerSection() {
  const { count, loading, hasMore, loadMore, reset } = useLoader(VIEWER_PAGES.length);
  const [changed, setChanged] = useState(false);
  const [copied, setCopied] = useState('');
  return (
    <section className="showcase__section" data-demo="text-viewer">
      <h2 className="showcase__h2">文本查看器</h2>
      <div className="showcase__stack">
        <div className="showcase-evidence__viewer">
          <TextViewer
            title="executor-report.md"
            pages={VIEWER_PAGES.slice(0, count)}
            hasMore={hasMore}
            loadingMore={loading}
            changed={changed}
            onLoadMore={loadMore}
            onReload={() => { reset(); setChanged(false); }}
            onCopy={setCopied}
          />
        </div>
        <div className="showcase__row">
          <Button variant="secondary" size="sm" onClick={() => setChanged(true)}>
            模拟文件已变化
          </Button>
          <span className="showcase__label">{copied ? '已复制：' : '点复制钮会把显示出来的文字交给调用方'}</span>
        </div>
        {copied !== '' && <div className="showcase-evidence__copy">{copied}</div>}
      </div>
      <p className="showcase__muted">
        不可信内容只按文本节点显示：不解释 HTML、去掉 ANSI 转义序列、不把网址变成链接；一行的分片接起来显示，行尾与底栏都有 [继续加载]。
      </p>
    </section>
  );
}

function TextViewerJsonlSection() {
  const { count, loading, hasMore, loadMore } = useLoader(JSONL_PAGES.length);
  return (
    <section className="showcase__section" data-demo="text-viewer-jsonl">
      <h2 className="showcase__h2">文本查看器（事件流）</h2>
      <div className="showcase__stack">
        <div className="showcase-evidence__viewer">
          <TextViewer
            title="events.jsonl"
            pages={JSONL_PAGES.slice(0, count)}
            hasMore={hasMore}
            loadingMore={loading}
            onLoadMore={loadMore}
            onCopy={() => {}}
          />
        </div>
      </div>
      <p className="showcase__muted">解析不了与超长的行只给占位：显示成不能展开的隐藏行，复制时跳过。</p>
    </section>
  );
}

function SafeMarkdownSection() {
  const [opened, setOpened] = useState('');
  return (
    <section className="showcase__section" data-demo="safe-markdown">
      <h2 className="showcase__h2">安全 Markdown</h2>
      <div className="showcase-evidence__md">
        <SafeMarkdown source={MD_SOURCE} onOpenLink={setOpened} />
      </div>
      <div className="showcase__row">
        <span className="showcase__label">{opened !== '' ? `上次请求打开：${opened}` : '点链接只在这里记下网址，不弹框'}</span>
      </div>
      <p className="showcase__muted">原始 HTML 当文字；不安全协议的链接只留文字；http(s) 渲染成按钮加网址，点击交给调用方。</p>
    </section>
  );
}

function EffortSection() {
  return (
    <section className="showcase__section" data-demo="effort">
      <h2 className="showcase__h2">思考档位</h2>
      <div className="showcase__stack">
        <EffortPair requested="high" effective="high" />
        <EffortPair requested="max" effective="high" />
        <EffortPair requested="high" effective={null} />
        <EffortPair requested={null} effective="high" />
        <EffortPair requested="max" effective={['high', 'max']} />
        <EffortPair requested="high" effective={['high', 'high']} />
      </div>
      <p className="showcase__muted">逐字相同才算一致；生效有多个时原样列出，任一不同即不一致；生效缺失是未知；没有要求只显示「—」。</p>
    </section>
  );
}

function MaskedValueSection() {
  return (
    <section className="showcase__section" data-demo="masked-value">
      <h2 className="showcase__h2">遮蔽值</h2>
      <div className="showcase__stack">
        <MaskedValue>（含疑似凭据，不显示）</MaskedValue>
        <MaskedValue>（值不显示）</MaskedValue>
        <MaskedValue>&lt;redacted&gt;</MaskedValue>
        <MaskedValue>（疑似凭据的键名）</MaskedValue>
      </div>
      <p className="showcase__muted">后端给出的占位原样显示，前面加 lock 图标 14，工具提示「内核已遮蔽」。</p>
    </section>
  );
}

function CommandLineSection() {
  const [copied, setCopied] = useState('');
  return (
    <section className="showcase__section" data-demo="command-line">
      <h2 className="showcase__h2">命令行</h2>
      <div className="showcase__stack">
        <CommandLine command={dispatchCommand(['config', 'preset', 'use', 'economy'])} onCopy={setCopied} />
        <CommandLine size="sm" command="/plan-task logs-cat" onCopy={setCopied} />
        <span className="showcase__label">{copied !== '' ? `已复制：${copied}` : '参数由后端给出（已脱敏），原样拼接'}</span>
      </div>
      <p className="showcase__muted">右侧复制钮把整条命令交给调用方；小号样式用在「下一步」里。</p>
    </section>
  );
}

function NextStepSection() {
  const [copied, setCopied] = useState('');
  return (
    <section className="showcase__section" data-demo="next-step">
      <h2 className="showcase__h2">下一步</h2>
      <div className="showcase__stack">
        <NextStep title="下一步" command="/plan-task logs-cat" onCopy={setCopied}>
          差异视图不在这片里，先在规划端会话里看日志：
        </NextStep>
        <NextStep>这一条不带命令，只有说明文字。</NextStep>
        <span className="showcase__label">{copied !== '' ? `已复制：${copied}` : 'info 色调的卡片，不是提示条，也不设 role'}</span>
      </div>
      <p className="showcase__muted">用于第一阶段界面上不能做、要回到规划端会话做的事。</p>
    </section>
  );
}

export default function EvidenceShowcase() {
  return (
    <>
      <TextViewerSection />
      <TextViewerJsonlSection />
      <SafeMarkdownSection />
      <EffortSection />
      <MaskedValueSection />
      <CommandLineSection />
      <NextStepSection />
    </>
  );
}
