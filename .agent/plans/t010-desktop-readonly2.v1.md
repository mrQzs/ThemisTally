# TASK: t010-desktop-readonly2

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 71face638f131966b43b31b88b00034d25048084
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T010 第 9 片（桌面端前端只读页面二：凭据、日志与用量、插件、历史与审计）：在 desktop/web/ 把四个占位页面换成真页面（各用 PageFrame），新增 src/pages/readonly2/ 下的视图与逻辑、src/mock/readonly2-*.ts 三份夹具与九个 tests/readonly2-* 测试，并只改 src/components/Drawer.css 的 top 与文件头注释一处（站主 Q3 选 a）；不改依赖、不改 api.ts、不接服务、不新增 .json 夹具。

## Non-goals
- 其他页面；写操作流程与确认框（凭据录入作业、插件启停预览、历史回滚确认框）；长作业（检索作业的进度与取消、核对、凭据录入作业）；接本机服务、SSE、轮询；七端内容；工具链。
- 检索结果在文本查看器里打开并跳到那一行（Q4 不做，结果条目不可点）。
- 画布上被拿掉的七端内容（凭据页说明后半句与工人名、用量页的全部工人汇总与按工人表、最近 N / M 条与显示全部）。
- 不改 README、package.json、锁文件、vite.config.ts、tsconfig.json、index.html、scripts/**、public/**、fonts/**；不改 api.ts、components/index.ts、icons/index.tsx、src/shell/**、src/App.*、main.tsx、src/styles/**、其余页面、readonly1/、tasks/、既有组件（Q3 的 Drawer.css 例外）。

## Repository facts
- 入口：desktop/web/src/pages/{Secrets,Logs,Plugins,History}Page.tsx 当前是占位页（PageFrame + listSecrets/getUsage/getPlugins/getHistory，children 里一行「夹具数据已读到」）；routes.ts 按默认导出引入；App.tsx:61、:82 用含 query 的 routeKey 重挂载 main，页面组件拿不到 props。
- 调用关系与现有约定（在 841e481 上核对）：
  - PageFrame（src/shell/PageFrame.tsx:24–34）props：title、description、actions、refreshLabel（缺省「刷新」）、load、isEmpty、empty（{title, description?}）、children；五态 loading/data/empty/error，根 data-page-state，断线 data-stale 与「可能已过期」Tag、Banner 里 [重新连接]。
  - api.ts 只有 13 个读函数：getMeta、getStatus、getAttempt、readFile、getRoles、getProfiles、getPresets、diffPresets、getRuntimes、getPlugins、getHistory、getUsage、listSecrets；没有 searchLogs、getHistoryEntry、getPlugin（与规划一致，走读法 A）。Envelope 字段 ok/exit_code/data/output/messages/command/elapsed_ms；error 报错原文 ERROR_MESSAGE；read() 规则：loading 永不兑现、error 返回 exit_code 2 与报错原文、data/offline/empty 深拷贝，empty 只清空 secrets/plugins/history。
  - mock/scenario.ts 的 currentMock() 与 MockMode；src/mock/ 现恰有 14 份 JSON（attempt、file-events、file-executor-report、history、meta、plugins、preset-diff、presets、profiles、roles、runtimes、secrets、status、usage）与 3 份 .ts（scenario、empty、shell）。
  - router.ts parseHash(hash) 返回 {tabId, pageId, segments, query}，mockOfQuery 导出；shell/relativeTime.ts relativeTime(from, now)。
  - 组件：Drawer（role=dialog、aria-modal=false、footer prop、Esc stopPropagation、useOverlayFocus 只在 open 由假变真时记一次触发元素）、Table（columns/rows/rowKey/rowHeight 40|44|52/onRowOpen/selectedKey/className/aria-label；data-selected、roving tabindex、current 按 key）、Tabs（items/value/onChange/aria-label）、Tag（tone/mono）、Banner（tone info|warning|danger、action；info 恒带关闭钮、danger 是 role=alert）、Card、EmptyState（icon/title/description/action）、TextField（label/help/error/mono）、Select（label/options/help/error）、MaskedValue（isMaskedPlaceholder、span.tt-masked title 内核已遮蔽）、DisabledAction（label/reason 缺省「第二阶段接入」/variant/size/icon）、IconButton、Tooltip、Button、overlay/{useOverlayFocus, focusable, MountLayer}。
  - icons：icons/frame.tsx 有 SecretsIcon、PluginsIcon；icons/index.tsx 有 CircleXIcon、RotateCcwIcon、InfoIcon、TriangleAlertIcon、XIcon、CheckIcon、ListChecksIcon、LockIcon、CopyIcon，没有 ExternalLinkIcon（故在 readonly2/common-icons.tsx 自写）。
  - Drawer.css:3–7 的 top 仍为 0，文件头 :1–2 写「顶边取 0（本片没有标题栏）」（Q3 待改）。src/pages/readonly2/ 尚不存在。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript 5.6.3 + Vite 5.4.11 + Vitest 2.1.8；@testing-library/react 16.1.0、@testing-library/dom 10.4.0、jsdom 25.0.1，无 user-event；vite.config.ts 的 test.include 含 src、tests、gate-probe；tsconfig.json 只含 src 与 vite.config.ts（测试不进 tsc）；锁文件 desktop/web/package-lock.json（lockfileVersion 3），npm ci 可复现。
- 基线检查：worktree HEAD = base_sha = 841e481e02e5f8a656ec6d9c59246722e66e3e77（站主把 T006 门禁里四页占位断言退役后的末端）。tests/test_gate_t010_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（V01 基线应失败）。T001–T008 门禁都在，基线上应通过（V02 回归）。
- 规划引用在新末端（841e481）上的核对结果（行号与接口有出入的逐条写明）：
  - G6 REAL_PAGES：规划 §10 说把 secrets/logs/plugins/history 加进 :2008 的 REAL_PAGES（Q2）。在 841e481 上 REAL_PAGES 已在 :2010，且已含这四页；:2048 的 if (!REAL_PAGES.includes(p.id)) 已把「夹具数据已读到」与函数名两条断言跳过（R1/R2 已随 Q2 退役）。所以本片不再需要改门禁，执行端也不碰 tests/。
  - :2047–2048：规划 §10 把这两行当 R1/R2；在 841e481 上守卫在 :2048、两条断言在 :2049–:2050。四页仍需满足守卫外的断言：:2045 调用各自加载函数、:2046 data-page-state=data、:2047 h1=标题。
  - D10 第一个 it 在 841e481 是 :2041（规划说 :2039–2052）；凭据说明原文与「重新检查」「没有刷新」在 :2067–:2069（规划说 :2064–:2067）；三页空态标题与「日志在 empty 下仍是 data」在 :2071–:2083（规划说 :2070–:2083）。均为行号平移，语义不变。
  - 其余 G6 行号（规划取 b5becf5）在 841e481 上整体平移数行：S1 与 14 份 JSON :3271、:3321–:3323；PageFrame 检查 :3288–:3289；D08 :3326；D14 禁用词 :3344、new_source_files :3352、守卫 :3364；新测试不跳过 :3405。语义不变。
  - 接口核对：api.ts 读函数仍是 13 个（无 searchLogs/getHistoryEntry/getPlugin），走读法 A 不变；PageFrame、router.parseHash、Drawer、Table、Tabs、MaskedValue、DisabledAction 的签名与规划 §9 一致；Drawer.css top 仍为 0；readonly2/ 尚不存在；src/pages/ 顶层恰有 9 个 *Page.tsx，src/mock/ 恰有 14 份 JSON。
  - 规划引用的 UI 文档、handoff、画布与内核脚本行号本回合未逐条重读，按规划端结论沿用；仓库事实以本回合实际读到的文件为准。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/SecretsPage.tsx
  - desktop/web/src/pages/LogsPage.tsx
  - desktop/web/src/pages/PluginsPage.tsx
  - desktop/web/src/pages/HistoryPage.tsx
  - desktop/web/src/components/Drawer.css
- allowed_new_files:
  - desktop/web/src/pages/readonly2/common-icons.tsx
  - desktop/web/src/pages/readonly2/common-format.ts
  - desktop/web/src/pages/readonly2/common-InfoNote.tsx
  - desktop/web/src/pages/readonly2/common-styles.css
  - desktop/web/src/pages/readonly2/common-copy.ts
  - desktop/web/src/pages/readonly2/common-readers.ts
  - desktop/web/src/pages/readonly2/secrets-SecretsView.tsx
  - desktop/web/src/pages/readonly2/secrets-logic.ts
  - desktop/web/src/pages/readonly2/secrets-styles.css
  - desktop/web/src/pages/readonly2/logs-LogsView.tsx
  - desktop/web/src/pages/readonly2/logs-SearchPanel.tsx
  - desktop/web/src/pages/readonly2/logs-SearchResults.tsx
  - desktop/web/src/pages/readonly2/logs-UsagePanel.tsx
  - desktop/web/src/pages/readonly2/logs-logic.ts
  - desktop/web/src/pages/readonly2/logs-styles.css
  - desktop/web/src/pages/readonly2/plugins-PluginsView.tsx
  - desktop/web/src/pages/readonly2/plugins-PluginDrawer.tsx
  - desktop/web/src/pages/readonly2/plugins-logic.ts
  - desktop/web/src/pages/readonly2/plugins-styles.css
  - desktop/web/src/pages/readonly2/history-HistoryView.tsx
  - desktop/web/src/pages/readonly2/history-HistoryDrawer.tsx
  - desktop/web/src/pages/readonly2/history-KeyDiff.tsx
  - desktop/web/src/pages/readonly2/history-ActorTag.tsx
  - desktop/web/src/pages/readonly2/history-logic.ts
  - desktop/web/src/pages/readonly2/history-styles.css
  - desktop/web/src/mock/readonly2-search.ts
  - desktop/web/src/mock/readonly2-history-entries.ts
  - desktop/web/src/mock/readonly2-plugin-show.ts
  - desktop/web/tests/readonly2-logic.test.ts
  - desktop/web/tests/readonly2-readers.test.ts
  - desktop/web/tests/readonly2-secrets.test.tsx
  - desktop/web/tests/readonly2-logs.test.tsx
  - desktop/web/tests/readonly2-plugins.test.tsx
  - desktop/web/tests/readonly2-history.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/readonly2-css.test.ts
  - desktop/web/tests/readonly2-static.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/src/main.tsx
  - desktop/web/src/vite-env.d.ts
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/showcase/**
  - desktop/web/src/shell/**
  - desktop/web/src/api.ts
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/empty.ts
  - desktop/web/src/mock/shell.ts
  - desktop/web/src/icons/**
  - desktop/web/src/components/index.ts
  - desktop/web/src/components/Button.*
  - desktop/web/src/components/Tag.*
  - desktop/web/src/components/StatusTag.*
  - desktop/web/src/components/Card.*
  - desktop/web/src/components/Banner.*
  - desktop/web/src/components/IconButton.*
  - desktop/web/src/components/Tooltip.*
  - desktop/web/src/components/Menu.*
  - desktop/web/src/components/Dialog.*
  - desktop/web/src/components/Drawer.tsx
  - desktop/web/src/components/Toast.*
  - desktop/web/src/components/SegmentedControl.*
  - desktop/web/src/components/Switch.*
  - desktop/web/src/components/Checkbox.*
  - desktop/web/src/components/Tabs.*
  - desktop/web/src/components/TextField.*
  - desktop/web/src/components/Select.*
  - desktop/web/src/components/Table.*
  - desktop/web/src/components/KeyValueList.*
  - desktop/web/src/components/EmptyState.*
  - desktop/web/src/components/Skeleton.*
  - desktop/web/src/components/ConnectionPill.*
  - desktop/web/src/components/Breadcrumb.*
  - desktop/web/src/components/TextViewer.*
  - desktop/web/src/components/SafeMarkdown.*
  - desktop/web/src/components/EffortPair.*
  - desktop/web/src/components/MaskedValue.*
  - desktop/web/src/components/CommandLine.*
  - desktop/web/src/components/NextStep.*
  - desktop/web/src/components/DiffView.*
  - desktop/web/src/components/LogFollow.*
  - desktop/web/src/components/overlay/**
  - desktop/web/src/components/field/**
  - desktop/web/src/components/evidence/**
  - desktop/web/src/components/diff/**
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/src/pages/TasksPage.tsx
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/pages/tasks/**
  - desktop/web/tests/base-reset.test.ts
  - desktop/web/tests/component-css.test.ts
  - desktop/web/tests/connection-pill.test.tsx
  - desktop/web/tests/data-atoms.test.tsx
  - desktop/web/tests/dialog-scrim.test.tsx
  - desktop/web/tests/dialog.test.tsx
  - desktop/web/tests/diff-css.test.ts
  - desktop/web/tests/diff-parse.test.ts
  - desktop/web/tests/diff-showcase.test.tsx
  - desktop/web/tests/diff-static.test.ts
  - desktop/web/tests/diff-view.test.tsx
  - desktop/web/tests/drawer.test.tsx
  - desktop/web/tests/evidence-atoms.test.tsx
  - desktop/web/tests/evidence-effort.test.tsx
  - desktop/web/tests/evidence-markdown.test.tsx
  - desktop/web/tests/evidence-showcase.test.tsx
  - desktop/web/tests/evidence-static.test.ts
  - desktop/web/tests/evidence-text-viewer.test.tsx
  - desktop/web/tests/font-specimen.test.tsx
  - desktop/web/tests/forms-patches-css.test.ts
  - desktop/web/tests/forms-patches.test.tsx
  - desktop/web/tests/icon-button.test.tsx
  - desktop/web/tests/log-follow.test.tsx
  - desktop/web/tests/menu.test.tsx
  - desktop/web/tests/segmented-control.test.tsx
  - desktop/web/tests/shell-api.test.ts
  - desktop/web/tests/shell-app.test.tsx
  - desktop/web/tests/shell-menu.test.tsx
  - desktop/web/tests/shell-no-network.test.ts
  - desktop/web/tests/shell-page-frame.test.tsx
  - desktop/web/tests/shell-router.test.ts
  - desktop/web/tests/shell-shortcuts.test.ts
  - desktop/web/tests/shell-showcase.test.tsx
  - desktop/web/tests/shell-tabbar.test.tsx
  - desktop/web/tests/shell-theme.test.ts
  - desktop/web/tests/shell-titlebar.test.tsx
  - desktop/web/tests/showcase-forms.test.tsx
  - desktop/web/tests/showcase-overlays.test.tsx
  - desktop/web/tests/skeleton.test.tsx
  - desktop/web/tests/status-tag-patches.test.tsx
  - desktop/web/tests/status-tag.test.tsx
  - desktop/web/tests/switch-checkbox.test.tsx
  - desktop/web/tests/table.test.tsx
  - desktop/web/tests/tabs.test.tsx
  - desktop/web/tests/text-field-select.test.tsx
  - desktop/web/tests/text-viewer-slots.test.tsx
  - desktop/web/tests/toast-close-tooltip.test.tsx
  - desktop/web/tests/toast.test.tsx
  - desktop/web/tests/token-contract.test.ts
  - desktop/web/tests/page-*
  - desktop/web/tests/tasks-*
  - desktop/web/README.md
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/index.html
  - desktop/web/vite.config.ts
  - desktop/web/tsconfig.json
  - desktop/web/scripts/**
  - desktop/web/public/**
  - desktop/web/fonts/**
  - desktop/web/THIRD_PARTY_NOTICES.md
  - tests/**
  - tests/test_gate_t010_*.py
  - docs/**
  - .gitignore
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 公共约定（§5.0）
- 视图根带 data-page（secrets、logs、plugins、history），抽屉内容根带 data-drawer（plugin、history）；视图不写 data-page-state、不渲染 h1。
- 区块用 section，aria-labelledby 指向它的 h2，id 用 useId。
- 数据里的字符串只作文本子节点或 title；地址例外经 encodeURIComponent。
- 数字千分位手写，不用 Intl/toLocaleString，缺失显示「未知」。
- 时间 formatLocalUtc(iso) 返回「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」，解析不了返回 null；相对时间用 relativeTime(from, Date.now())，不每秒刷新。
- hrefWithMock(path) 用 parseHash(location.hash).query 自己取 mock，当前地址有 mock 时才加 ?mock=。
- 标签用 Tag，带图标的加类设 gap --tt-space-1。
- 尺寸字面量同一行写出处注释；颜色、字体、圆角、阴影、层级只用令牌；间距就近取 --tt-space-*、平局取小；内联 style 只用于运行时算出的占比条宽度。
- 源码守卫（规划 §1）全部适用，夹具字符串也算：不写 role=status；不出现 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver；字符串与注释里不写井号加 3/4/6/8 位十六进制、不写颜色函数名加括号；整词不出现 fetch、XMLHttpRequest、EventSource、WebSocket；不出现 dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser；不出现 ServerIcon；不出现字体扩展名、sarasa-mono-sc-、@font-face、FontFace、document.fonts；W4 令牌检查通过。

### 数据来源与页内读取函数（读法 A，规划 §2.2）
- 列表用 api.ts 的 listSecrets、getUsage、getPlugins、getHistory（模块级引用传入 PageFrame）；视图只收数据与读取函数，不直接调 api.ts（可 import type）。
- common-readers.ts 写 searchLogs(q, task, max)、getHistoryEntry(n)、getPlugin(id)，读 src/mock/readonly2-*.ts，信封与 ?mock= 规则同 api.ts：每次读 currentMock()；loading 返回永不兑现 Promise；error 返回 ok:false、exit_code 2、data null、报错原文；empty 时 searchLogs 返回空 matches（truncated 假、两计数 0）；data/offline 返回深拷贝；夹具之外的参数返回 ok:false、exit_code 2、「ERROR 夹具里没有这份数据：…」；返回已兑现 Promise，不用计时器。
- command 数组：searchLogs 为 [logs, search, q]，有 task 时加 [--task, task]，最后加 [--max, N]；getHistoryEntry 为 [config, history, show, n]；getPlugin 为 [plugins, show, id]。data 形状照 KL:921–922、KC:1167–1186、KP:471–489（详见规划 §2.2）。
- 夹具（.ts，标「示意」）：readonly2-search.ts（固定模式 logs[_ ]cat，两个 attempt 各至少一组，skipped_large≥1，按 task 过滤后多于 max 截成前 max 并置 truncated，摘录≤200 字，路径只用 .md/.txt/.log/.json/.jsonl）；readonly2-history-entries.ts（42 两键差异、41 本机文件两 64 位十六进制 sha256、40 diff 为 null 且 note 疑似凭据不显示）；readonly2-plugin-show.ts（三个插件与 plugins.json 一致，docs-checks 的 permissions 含 fs.read、fs.write，缺 fs.write，资源两行一致，锁有 generation 与 64 位十六进制 lock_sha256）。夹具字符串同样受守卫。
- 不动 api.ts，不改 LATER_API 与 test_transitional_d06_api_only_thirteen_functions。

### 凭据（SecretsView，规划 §2.3）
- 说明原文「这里只显示每个环境变量在哪一层找到，从不显示值」；refreshLabel「重新检查」；页面上没有文字恰为「刷新」的按钮；空态标题「还没有要检查的凭据变量」；isEmpty=secrets 为空。
- 表（T005 Table，rowHeight 44，aria-label「凭据变量」，最小宽 720）四列：变量名、用在哪里、来源、操作；没有「值」列，页面上不出现夹具之外的值文字。
- 变量名等宽；值是 7.13 遮蔽占位（isMaskedPlaceholder）时用 MaskedValue。用在哪里按出现顺序：kind=profile 显示 profile <id>、相邻 profile 合并、kind=decisions 显示「决策模型」、未知 kind 原样带 id、各段用「、」连接、id 等宽、id 是遮蔽占位用 MaskedValue。来源：env 环境变量、credential_store 系统凭据库、file 0600 文件三者 success；none 没有 danger；其他原样 neutral；图标照画布（系统凭据库 SecretsIcon 14、没有 CircleXIcon 14、另两种不带图标）；标签带 data-source。操作：[录入…] DisabledAction（secondary、sm、ExternalLinkIcon 14）。
- 表下一条不可关的 info 说明（InfoNote，不用 Banner）与一个「“来源”标签」小节照画布。

### 日志与用量（LogsView、SearchPanel、SearchResults、UsagePanel，规划 §5.3、§5.4）
- 说明「在全部证据里检索；按 attempt 与模型统计 token」；load=getUsage，不传 isEmpty（?mock=empty 下仍是 data）；usage 读取失败整页出错，检索页签也看不到。
- 用 T005 Tabs（aria-label「日志与用量」）分检索（缺省）与用量两页签。
- 检索：表单（检索词、任务、最多条数初值 50、[检索]）；校验空检索词与非法最多条数时都不调用读取函数；提交调一次 searchLogs(q, task 或 null, max)、读取中按钮转圈、只认最后一次请求、卸载后不写状态。结果区：提交前说明、ok 为假的出错块（命令、退出码、messages 纯文本）、有结果写「结果」与「N 条 · 上限 M」、说明行顺序（truncated「只显示前 M 条匹配」、skipped_large「有 K 个文件太大或读不出来，没有搜；请用 CLI 查看」、skipped_links「跳过的链接：L」、固定说明「摘录取自脱敏之后的文本…」）、空 matches 写「没有匹配的行」、按 (task,attempt) 首次出现分组、组头 task · attempt 与 N 处、每条两行 path:line 与摘录（单行省略）。高亮按段渲染命中包 mark（--tt-highlight 底、--tt-text-1），JS 编译失败或检索词含带量词分组（右括号后紧跟 * + ? {）时不高亮整行照常；摘录≤200 字。结果条目不可点（Q4）。
- 用量：顶部 InfoNote「合计是下界：没有回报的记为未知，不计为 0。」；执行端卡（合计 totalTokens 与 token（下界）、input/output/cacheRead/cacheWrite、三个计数标签 known success「已回报」/partial warning「部分回报」/unknown neutral「未回报」、skipped_links 提示）；规划端卡（planner 为 null 时空状态与链接 [去设置] hrefWithMock('/settings')；不为 null 时一行「规划端用量的显示在后续片接入」）；按 attempt 表（T005 Table，rowHeight 40，最小宽 900，列任务/attempt/模型/状态/input/output/cacheRead/cacheWrite/合计；状态 Tag 文字原样、tone success/warning/neutral 与 title；null 显示「未知」；空写「还没有执行端的用量记录」）；按模型表（列模型/回报情况写成 known a · partial b · unknown c/占比/input/output/合计；占比一位小数加 %，分母为 0 显示「—」；条形轨道高 8、--tt-radius-full、--tt-surface-3 底，填充 --tt-navy-500，宽度用内联 style 百分比；空写「还没有按模型的统计」）。数字都带 tt-num。

### 插件（PluginsView、PluginDrawer，规划 §5.5）
- 说明「启停前先预览权限变化；锁与资源哈希由内核核对」；actions 放 [核对全部] DisabledAction（secondary、ListChecksIcon 16）；isEmpty：plugins、not_installed、problems 都为空才算空；空态标题「还没有插件」。
- 表（T005 Table，rowHeight 40，aria-label「插件」，最小宽 860，onRowOpen 打开抽屉）：ID、版本（等宽，版本 tt-num）；启用（是/否/不限制 或 启用/停用/不限制）按规则上色；锁、资源四类取值（一致 success+CheckIcon 12；漂移/不一致 warning+TriangleAlertIcon 12；以「无效」开头 danger+CircleXIcon 12；「-」显示「—」；其他 warning；非一致时 title 为 reason）；缺的权限每项 danger 等宽 Tag、空写「—」；状态等宽 Tag（READY success、DRIFT warning、BLOCKED danger、其他 neutral，reason 非空右侧接 caption）；操作（启用/是→[停用…]、停用/否→[启用…]、不限制→文字「详情」）。
- 表下两个小节（列入但未安装、问题），为空写「没有」。
- 抽屉（T004 Drawer，非模态）：标题 PluginsIcon 20 + 插件 ID（等宽）+ 状态 Tag；status 非 READY 时一条 warning Banner；manifest 小节（dl，标签列宽 96，含 ID/版本/启用/权限/api_version/capabilities/platforms/depends_on/conflicts，checks 不显示）；资源哈希核对小节（三列 路径/sha256/结果，sha256 前 12 位加…、title 全文）；锁小节（generation、lock_sha256 word-break break-all，旁边 IconButton「复制 lock_sha256」与复制结果文字）；footer [重新核对] DisabledAction secondary。

### 历史与审计（HistoryView、HistoryDrawer、KeyDiff、ActorTag，规划 §5.6）
- 说明「每次配置写入都有编号；点一行看前后快照的键级差异，必要时回滚」；isEmpty：entries 与 broken_lines 都为空才算空；空态标题「还没有配置历史」；broken_lines 非空时顶部 warning Banner「历史里有 N 行读不出来」。
- 表（T005 Table，rowHeight 40，aria-label「配置历史」，最小宽 1000，onRowOpen）行按 number 倒序，各列：编号 #number（运行时拼，等宽 tt-num）、时间（相对时间，title 为 formatLocalUtc，解析不了原样不带 title）、资源（config 配置、local 本机文件、其他原样）、动作（等宽，title 为中文说明）、对象（等宽，空写「—」）、执行者（ActorTag 等宽 Tag，user-ui brand、user neutral、agent: info、undeclared warning、其他 neutral）、确认（原样）、状态（published 已发布、aborted 已中止、unknown 未知、null 进行中或已中断，resolved 后接（补判），title 原状态码）、改动的键（每个等宽 neutral Tag，null 时显示 note，占位用 MaskedValue 否则 caption）、外部改动（>0 时 warning Tag「检测到外部改动」title 说明，否则「—」）。表下一行注记；external_before_first>0 时表上方一行注记。
- 抽屉（画布 drawer=42）：标题 #n · action target；dl（时间/动作/执行者/确认/状态）；external_changes>0 时 warning Banner；键级差异小节按顺序判断取第一条：resource 为 local→本机文件说明；diff 非空数组→KeyDiff；diff 空数组→「没有改动的键」；diff 为 null 且 note 是占位或含疑似凭据→占位逐键两格 MaskedValue 或只显示 note 原文，下面加 LockIcon 12 与「快照里有疑似凭据，只存了哈希。」；其他→entry.note 或「快照缺失，没有逐键差异」。footer 说明文字与 [回滚到这一条之后] DisabledAction secondary（RotateCcwIcon 16）。
- KeyDiff：三列 键、之前、之后；之前「− 值」（减号 U+2212、--tt-diff-del 底）、之后「+ 值」（--tt-diff-add 底）；值块 --tt-mono-sm、--tt-radius-sm；字符串原样、null 写「未设置」、数字布尔转字符串、对象数组写 JSON；字符串是占位用 MaskedValue 不带底色；键 word-break break-all。

### 抽屉、焦点与 Esc（规划 §2.7、K24、K25）
- 用 T004 Drawer：role=dialog、aria-modal=false；没有遮罩、不困焦点、点抽屉外不关；打开时焦点进头部「关闭（Esc）」钮；焦点在抽屉里按 Esc 关闭并 stopPropagation；关闭后焦点回打开时 activeElement。
- 关闭钮工具提示出现后（400ms），焦点在钮上按 Esc，Tooltip 先关提示、抽屉不关，再按一次才关（K25，T004 既有行为，不改）。
- 焦点在抽屉外按 Esc 不关（K6，不在页面层补全局 Esc）。
- 打开方式：Table onRowOpen（点击行或 Enter）；开着时点另一行只换内容；选中行取最后打开的那一行、关闭后保留（K7）。
- 换行后关闭的焦点（K24）：视图在关闭后的 effect 里把焦点移到 data-selected 的那一行（tbody tr[data-selected]），回到最后打开的那一行（React 18.3.1 先跑清理再按子先父后跑 effect，故晚于 Drawer 清理里的还焦点）。
- 单元格里不放可聚焦元素；[详情] 只显示文字「详情」整行可打开；行内禁用入口外面包 span 拦 click 冒泡（K8、K9）。
- 抽屉里的读取：打开或换行时调读取函数；读取中「正在读取…」；出错「没能读到详情：命令（…）返回退出码 N。」messages 放 pre；只认最后一次请求；卸载后不写状态。抽屉挂 body 下（MountLayer），切换路由随页面卸载消失。

### 写入口（规划 §2.8、K10、K27）
- 全部用 DisabledAction，reason 缺省「第二阶段接入」：凭据每行 [录入…]（secondary、sm、ExternalLinkIcon 14）；插件页头 [核对全部]（secondary、md、ListChecksIcon 16）、行内 [停用…]/[启用…]（ghost、sm）、抽屉底栏 [重新核对]（secondary、md）；历史抽屉底栏 [回滚到这一条之后]（secondary、md、RotateCcwIcon 16）；日志读法 A 下 [检索] 可用。
- 页面可用按钮白名单：PageFrame 刷新（凭据页叫重新检查）与重试、Tabs 两页签、[检索]、抽屉关闭钮、[复制 lock_sha256]；可用链接只有 [去设置]。
- 历史抽屉底栏说明：最新一条「这是最新的一条，回滚后没有变化」；本机文件「本机文件不存快照，不能回滚」；其余不写；按钮提示仍「第二阶段接入」。写入口个数不含 offline 时 PageFrame 自带的 [重新连接]。

### 遮蔽值（规划 §2.9、7.13）
- 后端字符串逐字等于 7.13 四个占位之一时一律用 T007 MaskedValue（LockIcon 14、--tt-text-3 斜体、title「内核已遮蔽」）：凭据变量名与 used_by 的 id、历史表改动的键的 note、历史抽屉键级差异的旧值新值与第 4 种情形占位。不是占位的说明按普通文字，不套 MaskedValue。凭据页本身没有值可显示（没有值列与占位用遮蔽样式分开验收）。

### 过渡与长期断言（规划 §2.10、§7.4）
- 过渡断言（docstring 第一行「接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据；页内读取函数并入 api.ts）」）：经 ?mock= 渲染 App 的四页五态；由夹具得到的具体值（行数、数字、写入口个数）；页内读取函数返回的夹具与参数规则。
- 长期断言：视图组件（注入数据与读取函数）、纯函数、CSS 取值、源码规则、写入口全部禁用这条规则本身、抽屉的焦点与 Esc。

### 页面结构与边界（任务书 §4）
- 每个页面文件含 PageFrame；顶层不新增 *Page.tsx（readonly2 里文件名不以 Page.tsx 结尾）；视图不写 data-page-state、不渲染 h1；整页恰有一个带 data-page-state 的元素。
- 夹具只能是 .ts，不写 .json（G6 S2 要求 src/mock/ 恰 14 份 JSON）；src/pages/ 顶层仍恰 9 个 *Page.tsx 且都含 PageFrame；PageFrame 的 load 与 isEmpty 用模块级引用。

## Steps
1. 预检（只读）：核对 Repository facts 与基线（尤其 G6 REAL_PAGES 在 :2010 已含四页、:2045–:2047 保留断言、api.ts 13 个读函数、Drawer.css top=0、mock 恰 14 JSON、pages 恰 9 个 *Page.tsx）；不符就停并报告。不改文件。
2. 公共件：common-icons、common-format、common-InfoNote、common-copy、common-styles；测试 readonly2-logic 公共部分。验收：千分位、本地与 UTC 时间、保留 mock 的地址、复制三结果、图标 fill/stroke 只用 none 与 currentColor。风险：本地时间期望值写死时区。
3. 页内读取函数与夹具：common-readers.ts、src/mock/readonly2-*.ts；测试 readonly2-readers。验收：五开关值效果、夹具之外参数、深拷贝、command 数组、检索按 task 过滤与按 max 截断与 truncated。风险：夹具写成 .json（S2 变红）、字符串碰到守卫。
4. 凭据页：secrets-* 与 SecretsPage.tsx；测试 readonly2-secrets。验收：D01。风险：多出值列或值文字、none 映射错、改说明或空态标题。
5. 用量页签：logs-UsagePanel 与 logs-logic 用量部分；测试 readonly2-logs 用量部分。验收：D03。风险：状态码翻中文、null 显示 0、占比条用金色。
6. 检索页签：logs-SearchPanel、logs-SearchResults 与 logs-logic 检索部分；测试 readonly2-logs 检索部分。验收：D02。风险：截断提示写命中条数、过期回应覆盖新结果、高亮回溯卡死。
7. 日志与用量页接线：logs-LogsView 与 LogsPage.tsx。验收：页签切换、PageFrame 五态、?mock=empty 下仍是 data。风险：给 LogsPage 传 isEmpty、把页签写进地址。
8. 插件页与抽屉：plugins-* 与 PluginsPage.tsx；测试 readonly2-plugins。验收：D04、D05。风险：关闭清 selectedKey、换行后焦点回最早行、[详情] 做成可聚焦、点禁用钮开抽屉。
9. 历史与审计页与差异抽屉：history-* 与 HistoryPage.tsx；测试 readonly2-history。验收：D06、D07。风险：执行者色调对调、按正序排、遮蔽值普通文字、源码写出井号加数字。
10. App 级接线与五态（过渡）：readonly2-app。验收：D08 与 D09 过渡部分；与 G6 D10 保留断言一致。
11. 样式与源码规则：readonly2-css、readonly2-static。验收：D10、D11。
12. 自检：在 desktop/web 下依次跑 npm ci（要网络）、npm run build、npm test、npm run check:contract；在仓库根点名跑 V01、V02、V03；确认 git status 没有新的未忽略文件。V02 放最后只跑一次。风险：V02 跑 8 份门禁很慢。

## Setup
无。本合同的 prepare setup 为空；npm ci 只在门禁 pytest 与执行端自检里跑（与 T002–T008 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t010_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
说明：V01 的 tests/test_gate_t010_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（基线应失败）。V02 合并 T001–T008 八份门禁回归，点名运行以让前端流水线不被 conftest 跳过。V03 是桌面端状态表与调度器 ATTEMPT_STATES 的回归（本片不改状态表，基线应通过）。

## Definition of done
- D01：凭据——四列、无「值」表头或单元格、页面不出现夹具外的值文字；来源四种取值与未知值的文字/tone/图标/data-source；用在哪里的合并规则；变量名与 id 是遮蔽占位时渲染 span.tt-masked（title 内核已遮蔽、含 LockIcon）；每行 [录入…] 禁用；info 说明与来源小节；说明原文、重新检查、没有刷新按钮、空态标题都与 T006 一致；证据：V01；目的：凭据页从不显示值、占位用遮蔽样式。
- D02：检索——表单默认值与两条校验文字；提交时读取函数恰好调用一次、参数正确、读取中按钮转圈、只认最后一次请求；ok 为假的出错块（命令/退出码/messages 纯文本）；分组顺序与 N 处、path:line；截断提示数等于上限、skipped_large/skipped_links 提示、空结果文字；高亮段在 mark 里、编译失败与带量词分组不高亮；摘录含 <img src=x onerror=…> 与 <script> 时 DOM 无对应元素；证据：V01；目的：检索结果如实反映截断与跳过、不可信内容只按文本显示。
- D03：用量——固定说明；执行端卡合计/四项/三个计数标签（文字原样、title 中文）；规划端空状态与 [去设置] href（有 mock 时带上）；按 attempt 表状态 Tag 文字原样/tone/title、null 显示未知；按模型表回报情况文字/占比文字/条宽；两表为空文字；证据：V01。
- D04：插件表——各列取值与色调、启用三种写法加未知、锁与资源四类取值、状态与 reason；操作列三种情形、两个小节；页头 [核对全部] 禁用；isEmpty 规则；证据：V01。
- D05：插件抽屉——点击行或 Enter 打开、aria-modal=false 无遮罩；打开后焦点在关闭钮；400ms 内 Esc 关闭且焦点回触发行；提示出现后第一次 Esc 只关提示、第二次关抽屉；焦点在抽屉外 Esc 不关、点抽屉外不关；开着时点另一行只换内容、换行后 Esc 焦点回后打开那行、关闭后触发行仍是当前行；读取中/出错/有数据三态、过期回应丢弃；warning 文字、manifest/资源/锁三小节、复制三结果、[重新核对] 禁用；证据：V01；目的：非模态抽屉的焦点与 Esc 行为正确、换行后焦点回最后一行。
- D06：历史表——倒序、编号、相对时间与 title 格式、资源/动作中文 title/对象；执行者五种 tone；确认；状态四种写法加（补判）；改动的键与遮蔽 note；外部改动标签；broken_lines warning；两行注记；isEmpty 规则；证据：V01。
- D07：差异抽屉——标题、dl、外部改动提示条；键级差异五种情形；KeyDiff 符号 U+2212 与加号、底色令牌、未设置与遮蔽两种写法；footer 两种说明、[回滚到这一条之后] 禁用；焦点与 Esc 同 D05；证据：V01。
- D08：五态（经 ?mock=，过渡）——四页 loading 299ms 无骨架/300ms 有；data；empty 时凭据/插件/历史显示 T006 空态标题、日志与用量仍 data；error 出错块命令依次 config show/logs usage/plugins list/config history、退出码 2、报错原文；offline role=alert/可能已过期/data-stale、数据照常；整页恰一个 data-page-state；证据：V01。
- D09：写入口——§2.8 入口全部 disabled、悬停 400ms 出现 role=tooltip 文字「第二阶段接入」；各页可用按钮只在白名单内；夹具下个数（不含 offline 重新连接）凭据 2、插件 3（抽屉开 4）、历史 0（抽屉开 1）；证据：V01。
- D10：样式与 1024 前提——§5.7 取值；令牌与 px 注释；宽表都在可横向滚动容器；内联 style 只出现在占比条；证据：V01。
- D11：源码规则——§1 禁用词与守卫（夹具字符串也算）；四个页面文件都含 PageFrame、load 与 isEmpty 不是内联函数；src/mock/ 仍恰 14 份 JSON、src/pages/ 顶层仍恰 9 个 *Page.tsx；证据：V01。
- D12：回归与范围——T001–T008 门禁、V03、npm 四步通过；只改允许文件、不改依赖；新测试不用 skip/only/todo；证据：scope、V02、V03。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 api.ts、components/index.ts、icons/index.tsx、src/shell/**、App.*、main.tsx、styles/**、既有组件（Drawer.css 的 top 与文件头注释除外）、既有测试、tests/test_gate_t010_*.py、package.json、锁文件、scripts/**）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）。
- 时间分配：调查约 15 分钟、实现与补测约 70 分钟、必要检查约 30 分钟、最终报告约 10 分钟；总计不超过单轮 7200 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。
