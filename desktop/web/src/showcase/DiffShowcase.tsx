// 第 7 片（T008）陈列页演示：两节，data-demo 依次为 diff-view、log-follow。复用 App.css 的 showcase__* 类。
// 不挂到陈列页（App.tsx 不引用本组件，T006 落地后自动收进）；不可信内容只按文本显示，ANSI 的 ESC 用 Unicode 转义写。
import { useEffect, useRef, useState } from 'react';
import { Button } from '../components';
import { DiffView } from '../components/DiffView';
import { LogFollow } from '../components/LogFollow';
import type { ViewerPage } from '../components/evidence/viewerLines';
import './showcase-diff.css';

const ESC = '\u001b';
const LONG = 'x'.repeat(2100);
const REASON = 'attempt 已结束，没有新事件';
const APPEND_MS = 400;
const MAX_APPEND = 494;
const BASE_MAX_N = 22;

// diff-view：改动文件（两个片段）、新文件（缺省折叠）、删除的文件（含以 -- 开头的删除行）、
// 改名（相似度 100%，无片段）、二进制新文件（GIT binary patch 加 literal 0）、超长行、
// 以及含 <script>、<img onerror>、ANSI、网址、末行 No newline 的文件。
const PATCH = [
  'diff --git a/src/attempts/run.py b/src/attempts/run.py',
  'index 1111111..2222222 100644',
  '--- a/src/attempts/run.py',
  '+++ b/src/attempts/run.py',
  '@@ -10,7 +10,9 @@ def run(cfg):',
  '     timeout = cfg.timeout',
  '-    retries = 1',
  '-    verbose = False',
  '+    retries = 3',
  '+    verbose = True',
  '+    strict = True',
  '     return Attempt(timeout, retries, verbose)',
  '@@ -40,3 +42,2 @@ def cleanup():',
  '     close()',
  '-    gc.collect()',
  '     done()',
  'diff --git a/docs/NEW_NOTES.md b/docs/NEW_NOTES.md',
  'new file mode 100644',
  'index 0000000..3333333',
  '--- /dev/null',
  '+++ b/docs/NEW_NOTES.md',
  '@@ -0,0 +1,2 @@',
  '+第一行笔记',
  '+第二行笔记',
  'diff --git a/src/legacy/old.py b/src/legacy/old.py',
  'deleted file mode 100644',
  'index 4444444..0000000',
  '--- a/src/legacy/old.py',
  '+++ /dev/null',
  '@@ -1,3 +0,0 @@',
  '-import os',
  '--- 这一段是被删掉的旧实现',
  '-os.exit(0)',
  'diff --git a/config/old-name.json b/config/new-name.json',
  'similarity index 100%',
  'rename from config/old-name.json',
  'rename to config/new-name.json',
  'diff --git a/assets/logo.png b/assets/logo.png',
  'new file mode 100644',
  'index 0000000..5555555',
  'GIT binary patch',
  'literal 0',
  'HcmV?d00001',
  '',
  'literal 0',
  'HcmV?d00001',
  '',
  'diff --git a/data/blob.txt b/data/blob.txt',
  'index 6666666..7777777 100644',
  '--- a/data/blob.txt',
  '+++ b/data/blob.txt',
  '@@ -1 +1 @@',
  '-' + LONG,
  '+' + LONG + 'END',
  'diff --git a/notes/readme.txt b/notes/readme.txt',
  'index 8888888..9999999 100644',
  '--- a/notes/readme.txt',
  '+++ b/notes/readme.txt',
  '@@ -1,1 +1,5 @@',
  ' 正常上下文',
  '+<script>alert(1)</script>',
  '+<img src=x onerror=alert(1)>',
  '+' + ESC + '[31m红色警告' + ESC + '[0m 详见 https://example.com/attempt/002',
  '+最后一行没有换行',
  '\\ No newline at end of file',
].join('\n') + '\n';

const TRUNCATED_PATCH = [
  'diff --git a/partial.log b/partial.log',
  'index aaaaaaa..bbbbbbb 100644',
  '--- a/partial.log',
  '+++ b/partial.log',
  '@@ -1,2 +1,2 @@',
  '-旧的一行',
  '+新的一行',
].join('\n') + '\n';

// log-follow：初始页含第 6 行第 1/2 片；第 2、3 页给第 2/2 片与之后的事件，其中有 <script>、ANSI、超长行。
const LOG_PAGES: ViewerPage[] = [
  {
    mode: 'jsonl',
    lines: [
      { n: 1, text: '{"type":"agent_start","ts":"2025-01-02T09:00:00Z"}' },
      { n: 2, text: '{"type":"tool_execution_end","toolName":"bash","isError":false}' },
      { n: 3, hidden: 'not_json' },
      { n: 4, hidden: 'too_long' },
      { n: 5, text: '{"type":"message_update","api_key":"<redacted>"}' },
      { n: 6, text: '{"type":"tool_result","output":"' + 'a'.repeat(60), part: 1, parts: 2 },
    ],
  },
  {
    mode: 'jsonl',
    lines: [
      { n: 6, text: 'b'.repeat(60) + '"}', part: 2, parts: 2 },
      { n: 7, text: '<script>alert(1)</script>' },
      { n: 8, text: ESC + '[31m红色警告' + ESC + '[0m 结束' },
      { n: 9, text: '{"type":"note","text":"' + 'y'.repeat(2100) + '"}' },
      { n: 10, text: '{"type":"tool_execution_start","toolName":"read"}' },
      { n: 11, text: '{"type":"tool_execution_end","toolName":"read","isError":false}' },
      { n: 12, text: '{"type":"message","text":"读取配置完成"}' },
      { n: 13, text: '{"type":"tool_execution_start","toolName":"write"}' },
      { n: 14, text: '{"type":"tool_execution_end","toolName":"write","isError":false}' },
    ],
  },
  {
    mode: 'jsonl',
    lines: [
      { n: 15, text: '{"type":"message","text":"写入完成"}' },
      { n: 16, text: '{"type":"agent_step","index":16}' },
      { n: 17, text: '{"type":"agent_step","index":17}' },
      { n: 18, text: '{"type":"agent_step","index":18}' },
      { n: 19, text: '{"type":"agent_step","index":19}' },
      { n: 20, text: '{"type":"agent_step","index":20}' },
      { n: 21, text: '{"type":"agent_step","index":21}' },
      { n: 22, text: '{"type":"attempt_closed","exitCode":0}' },
    ],
  },
];

function DiffViewSection() {
  return (
    <section className="showcase__section" data-demo="diff-view">
      <h2 className="showcase__h2">差异视图</h2>
      <div className="showcase__stack">
        <div className="showcase-diff__view">
          <DiffView patch={PATCH} title="candidate.patch" />
        </div>
        <div className="showcase-diff__view">
          <DiffView patch={TRUNCATED_PATCH} title="candidate.patch（节选）" truncated onLoadMore={() => {}} />
        </div>
      </div>
      <p className="showcase__muted">补丁是不可信内容：路径、片段头与行只按文本显示，去掉 ANSI，不解释 HTML；新文件缺省折叠，二进制不显示内容，改名显示「旧 → 新」。</p>
    </section>
  );
}

function LogFollowSection() {
  const [loaded, setLoaded] = useState(1);
  const [loading, setLoading] = useState(false);
  const [appended, setAppended] = useState<{ n: number; text: string }[]>([]);
  const [attemptEnded, setAttemptEnded] = useState(false);
  const [copyMsg, setCopyMsg] = useState('');
  const loadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const appendTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const appendCount = useRef(0);

  useEffect(() => () => {
    if (loadTimer.current !== null) clearTimeout(loadTimer.current);
    if (appendTimer.current !== null) clearInterval(appendTimer.current);
  }, []);

  const hasMore = loaded < LOG_PAGES.length;
  const pages: ViewerPage[] = [
    ...LOG_PAGES.slice(0, loaded),
    ...appended.map((l) => ({ mode: 'jsonl' as const, lines: [l] })),
  ];

  const loadMore = () => {
    if (loading || !hasMore) return;
    setLoading(true);
    loadTimer.current = setTimeout(() => {
      loadTimer.current = null;
      setLoading(false);
      setLoaded((c) => Math.min(c + 1, LOG_PAGES.length));
    }, 200);
  };
  const stopAppend = () => {
    if (appendTimer.current !== null) {
      clearInterval(appendTimer.current);
      appendTimer.current = null;
    }
  };
  const startAppend = () => {
    if (appendTimer.current !== null) return;
    appendTimer.current = setInterval(() => {
      const count = appendCount.current + 1;
      if (count > MAX_APPEND) {
        stopAppend();
        return;
      }
      appendCount.current = count;
      setAppended((prev) => [...prev, { n: BASE_MAX_N + count, text: `{"type":"appended","seq":${count}}` }]);
    }, APPEND_MS);
  };
  const onCopy = (text: string) => {
    const clip = (navigator as { clipboard?: { writeText?: (t: string) => Promise<void> } }).clipboard;
    if (!clip || typeof clip.writeText !== 'function') {
      setCopyMsg('这个环境没有剪贴板接口');
      return;
    }
    clip.writeText(text).then(
      () => setCopyMsg(`已复制 ${text.length} 个字符`),
      () => setCopyMsg('复制失败'),
    );
  };

  return (
    <section className="showcase__section" data-demo="log-follow">
      <h2 className="showcase__h2">日志跟随</h2>
      <div className="showcase__stack">
        <div className="showcase-diff__log">
          <LogFollow
            title="ui-readonly-api / events.jsonl"
            pages={pages}
            hasMore={hasMore}
            loadingMore={loading}
            onLoadMore={loadMore}
            onCopy={onCopy}
            followDisabledReason={attemptEnded ? REASON : undefined}
          />
        </div>
        <div className="showcase__row">
          <Button variant="secondary" size="sm" onClick={startAppend}>开始追加</Button>
          <Button variant="secondary" size="sm" onClick={stopAppend}>停止追加</Button>
          <Button variant="secondary" size="sm" onClick={() => setAttemptEnded((v) => !v)}>模拟 attempt 已结束</Button>
          <span className="showcase__label">{copyMsg || '点复制钮把显示出来的文字交给调用方'}</span>
        </div>
      </div>
      <p className="showcase__muted">贴底时跟随最新内容，往上看超过阈值就暂停，[回到底部] 或停 150ms 内回底恢复；过滤框按文字包含筛选，隐藏行不显示、行号不变。</p>
    </section>
  );
}

export default function DiffShowcase() {
  return (
    <>
      <DiffViewSection />
      <LogFollowSection />
    </>
  );
}
