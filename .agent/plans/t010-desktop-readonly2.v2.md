# TASK: t010-desktop-readonly2

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 190f82fea704a58ff89d5939b35a2951198907b8
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
  - api.ts 只有 13 个读函数：getMeta、getStatus、getAttempt、readFile、getRoles、getProfiles、getPresets、diffPresets、getRuntimes、getPlugins、getHistory、getUsage、listSecrets；没有 searchLogs、getHistoryEntry、getPlugin（走读法 A）。Envelope 字段 ok/exit_code/data/output/messages/command/elapsed_ms；error 报错原文 ERROR_MESSAGE；read() 规则：loading 永不兑现、error 返回 exit_code 2 与报错原文、data/offline/empty 深拷贝，empty 只清空 secrets/plugins/history。
  - mock/scenario.ts 的 currentMock() 与 MockMode；src/mock/ 现恰有 14 份 JSON（attempt、file-events、file-executor-report、history、meta、plugins、preset-diff、presets、profiles、roles、runtimes、secrets、status、usage）与 3 份 .ts（scenario、empty、shell）。
  - router.ts parseHash(hash) 返回 {tabId, pageId, segments, query}，mockOfQuery 导出；shell/relativeTime.ts relativeTime(from, now)。
  - 组件：Drawer（role=dialog、aria-modal=false、footer prop、Esc stopPropagation、useOverlayFocus 只在 open 由假变真时记一次触发元素）、Table（columns/rows/rowKey/rowHeight 40|44|52/onRowOpen/selectedKey/className/aria-label；data-selected、roving tabindex、current 按 key）、Tabs（items/value/onChange/aria-label）、Tag（tone/mono）、Banner（tone info|warning|danger、action；info 恒带关闭钮、danger 是 role=alert）、Card、EmptyState（icon/title/description/action）、TextField（label/help/error/mono）、Select（label/options/help/error）、MaskedValue（isMaskedPlaceholder、span.tt-masked title 内核已遮蔽）、DisabledAction（label/reason 缺省「第二阶段接入」/variant/size/icon）、IconButton、Tooltip、Button、overlay/{useOverlayFocus, focusable, MountLayer}。
  - icons：icons/frame.tsx 有 SecretsIcon、PluginsIcon；icons/index.tsx 有 CircleXIcon、RotateCcwIcon、InfoIcon、TriangleAlertIcon、XIcon、CheckIcon、ListChecksIcon、LockIcon、CopyIcon，没有 ExternalLinkIcon（故在 readonly2/common-icons.tsx 自写）。
  - Drawer.css:3–7 的 top 仍为 0，文件头 :1–2 写「顶边取 0（本片没有标题栏）」（Q3 待改）。src/pages/readonly2/ 尚不存在。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript 5.6.3 + Vite 5.4.11 + Vitest 2.1.8；@testing-library/react 16.1.0、@testing-library/dom 10.4.0、jsdom 25.0.1，无 user-event；vite.config.ts 的 test.include 含 src、tests、gate-probe；tsconfig.json 只含 src 与 vite.config.ts（测试不进 tsc）；锁文件 desktop/web/package-lock.json（lockfileVersion 3），npm ci 可复现。
- 基线检查：worktree HEAD = base_sha = 841e481e02e5f8a656ec6d9c59246722e66e3e77（站主把 T006 门禁里四页占位断言退役后的末端）。tests/test_gate_t010_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（V01 基线应失败）。T001–T008 门禁都在，基线上应通过（V02 回归）。
- 新末端（841e481）核对结果：
  - G6 REAL_PAGES 已在 :2010，且已含这四页；:2048 守卫、:2049–:2050 两条断言、:2045–:2047 保留断言；本片不再需要改门禁，执行端也不碰 tests/。
  - 接口核对：api.ts 读函数仍是 13 个（无 searchLogs/getHistoryEntry/getPlugin），走读法 A；Drawer.css top 仍为 0；readonly2/ 尚不存在；src/pages/ 顶层恰有 9 个 *Page.tsx，src/mock/ 恰有 14 份 JSON。

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

### 公共约定
- 视图根带 data-page（secrets、logs、plugins、history），抽屉内容根带 data-drawer（plugin、history）；视图不写 data-page-state、不渲染 h1。
- 区块用 section，aria-labelledby 指向它的 h2，id 用 useId。
- 数据里的字符串只作文本子节点或 title；地址例外经 encodeURIComponent。
- 数字千分位手写，不用 Intl/toLocaleString，缺失（null、undefined、非数）显示「未知」。
- 时间：formatLocalUtc(iso) 返回「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」（全角括号），解析不了返回 null；相对时间用 relativeTime(from, Date.now())，不每秒刷新。
- 保留 mock 的地址：hrefWithMock(path) 用 parseHash(location.hash).query 自己取 mock，当前地址有 mock 时才加 ?mock=；返回值以 # 开头（如 #/settings?mock=data）。
- 标签用 Tag，带图标的加类设 gap --tt-space-1。
- 表格行高：凭据 44，插件、历史、按 attempt 与按模型用量 40（出处 docs/ui-design/handoff.md:142）。
- 尺寸字面量同一行写出处注释；颜色、字体、圆角、阴影、层级只用令牌；间距就近取 --tt-space-*、平局取小；内联 style 只用于运行时算出的占比条宽度。
- 源码守卫（全部适用，夹具字符串也算）：不写 role=status；不出现 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver；字符串与注释里不写井号加 3/4/6/8 位十六进制、不写颜色函数名加括号；整词不出现 fetch、XMLHttpRequest、EventSource、WebSocket；不出现 dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser；不出现 ServerIcon；不出现字体扩展名、sarasa-mono-sc-、@font-face、FontFace、document.fonts；W4 令牌检查通过。

### 数据来源与页内读取函数（读法 A）
- 列表用 api.ts 的 listSecrets、getUsage、getPlugins、getHistory（模块级引用传入 PageFrame）；视图只收数据与读取函数，不直接调 api.ts（可 import type）。
- common-readers.ts 写 searchLogs(q, task, max)、getHistoryEntry(n)、getPlugin(id)，读 src/mock/readonly2-*.ts，信封与 ?mock= 规则同 api.ts：每次读 currentMock()；loading 返回永不兑现 Promise；error 返回 ok:false、exit_code 2、data null、报错原文；empty 时 searchLogs 返回空 matches（truncated 假、两计数 0）；data/offline 返回深拷贝；夹具之外的参数返回 ok:false、exit_code 2、「ERROR 夹具里没有这份数据：…」；返回已兑现 Promise，不用计时器。
- command 数组：searchLogs 为 [logs, search, q]，有 task 时加 [--task, task]，最后加 [--max, N]；getHistoryEntry 为 [config, history, show, n]；getPlugin 为 [plugins, show, id]。
- 数据形状：
  - searchLogs 的 data：matches（每项 task、attempt、path、line、text）、truncated、skipped_links、skipped_large。
  - getHistoryEntry 的 data：config 记录为 number、state、note、diff（null，或每项 key、old、new 的数组）；本机文件记录为 number、resource、state、before_sha256、after_sha256、note。
  - getPlugin 的 data：plugin_id、lock_status、resource_status、problems、version、api_version、capabilities、permissions、platforms、depends_on、conflicts、checks、lock（generation、lock_sha256）、resources（每项 path、id、sha256、status、detail）、config（enabled、allowed_permissions、missing_permissions）。
- 夹具（.ts，标「示意」）：
  - readonly2-search.ts：固定模式 logs[_ ]cat，两个 attempt 各至少一组匹配；匹配路径只用 .md/.txt/.log/.json/.jsonl；skipped_large≥1；按 task 过滤后多于 max 时截成前 max 并置 truncated；摘录≤200 字。
  - readonly2-history-entries.ts：42（两键差异：active_preset、roles.execution.profile）、41（本机文件，两个 64 位十六进制 sha256）、40（diff 为 null，note「疑似凭据，不显示」）三条。
  - readonly2-plugin-show.ts：三个插件与 plugins.json 一致；docs-checks 的 permissions 含 fs.read、fs.write，缺 fs.write；资源两行一致（manifest.json、checks/headings.py）；锁有 generation 与 64 位十六进制 lock_sha256。
  - 夹具字符串同样受上面源码守卫约束。
- 不动 api.ts，不改 LATER_API 与 test_transitional_d06_api_only_thirteen_functions。

### 凭据（SecretsView）
- 说明原文「这里只显示每个环境变量在哪一层找到，从不显示值」；refreshLabel「重新检查」；页面上没有文字恰为「刷新」的按钮；空态标题「还没有要检查的凭据变量」；isEmpty=secrets 为空。
- 表（Table，rowHeight 44，aria-label「凭据变量」，最小宽 720）四列：变量名、用在哪里、来源、操作；没有「值」列，页面上不出现夹具之外的值文字。
- 变量名等宽；值是遮蔽占位（isMaskedPlaceholder）时用 MaskedValue。
- 用在哪里按出现顺序：kind=profile 显示「profile <id>」、相邻 profile 合并成「profile a、b」、kind=decisions 显示「决策模型」、未知 kind 原样带 id、各段用「、」连接、id 等宽、id 是遮蔽占位用 MaskedValue。合并示例：profile p1、p2、决策模型；profile p1、决策模型、profile p2；决策模型、profile p3、weird w1、weird2。
- 来源：env 环境变量、credential_store 系统凭据库、file 0600 文件三者 success；none 没有 danger；其他原样 neutral；图标照画布（系统凭据库 SecretsIcon 14、没有 CircleXIcon 14、另两种不带图标）；标签带 data-source。
- 操作：[录入…] DisabledAction（secondary、sm、ExternalLinkIcon 14）。
- 表后一条不可关的 info 说明（InfoNote，不用 Banner，不设 role），原文「录入只在单独的一次性页面里进行，值直接存进系统凭据库；这个界面拿不到值。」；表后还有「来源」标签小节，照画布（docs/ui-design/screens/Secrets.dc.html）列出 环境变量、系统凭据库、0600 文件、没有 四个标签。
- 整张表的横向滚动只发生在 Table 的容器里；操作列靠右。

### 日志与用量（LogsView、SearchPanel、SearchResults、UsagePanel）
- 说明「在全部证据里检索；按 attempt 与模型统计 token」；load=getUsage，不传 isEmpty（?mock=empty 下仍是 data）；usage 读取失败整页出错，检索页签也看不到。
- 用 Tabs（aria-label「日志与用量」）分检索（缺省）与用量两页签。
- 检索表单（同一 form，用 TextField 与 Select）：
  - 检索：label「检索」，help「Python 正则表达式」，mono，type=search，placeholder「例如 logs[_ ]cat」，初值空；
  - 任务：label「任务」，Select，首项「全部任务」值为空串，其余取 usage.executor.attempts 里 task 的去重、按首次出现排序；
  - 最多条数：label「最多条数」，type=number，min=1，初值 50；
  - [检索]：Button primary，type=submit；onSubmit 先 preventDefault。
- 校验（不通过都不调用读取函数）：检索词去首尾空白后为空，检索框下显示「先输入要检索的内容」并 aria-invalid；最多条数不是不小于 1 的整数，显示「最多条数必须是不小于 1 的整数」；不在 JS 里校验正则语法（交给内核报错）。
- 提交：调一次 searchLogs(q, task 或 null, max)；读取中按钮 loading（aria-busy、disabled、转圈），文字「正在检索…」；只认最后一次请求；卸载后不写状态。
- 结果区：
  - 提交前说明：「输入 Python 正则表达式后检索；全量检索可能要半分钟左右，建议先选任务缩小范围。」
  - 信封 ok 为假：出错块「没能检索：命令（参数用空格连接）返回退出码 N。」，messages 放 pre 里按纯文本显示。
  - 有结果时头部写「结果」与「N 条 · 上限 M」（M 是这次提交的 max，不写用时）。
  - 头部下说明行顺序固定：truncated 为真「只显示前 M 条匹配」；skipped_large 大于 0「有 K 个文件太大或读不出来，没有搜；请用 CLI 查看」；skipped_links 大于 0「跳过的链接：L」；最后一行固定说明全文「摘录取自脱敏之后的文本：被遮蔽的值搜不到是正常的，<redacted> 占位本身能搜到；不合法的、超过 4 MiB 的 JSONL 行不参加搜索。」（出错时不显示这行固定说明）。
  - matches 为空：显示「没有匹配的行」，说明行照常显示。
  - 分组：按 (task, attempt) 首次出现的顺序；组头写「task · attempt」（--tt-mono-sm、字重 600）与「N 处」；每条两行，第一行「path:line」（--tt-mono-sm、--tt-text-2，不是链接），第二行摘录（--tt-mono-md、white-space pre、单行省略、min-width 0）。
  - 高亮：摘录按段渲染，命中段包在 mark 里（--tt-highlight 底、--tt-text-1），全部是文本节点；命中段用 JS 的 RegExp(检索词, g) 求，空匹配跳过、不生成 mark；不高亮整行照常的两种情况：JS 编译失败；检索词含带量词的分组（右括号后紧跟 *、+、?、{）。mark 的样式写在以 mark 元素为选择器的规则里。摘录最长 200 字。
  - 结果条目不可点（Q4 不做跳行）。
- 用量：
  - 顶部 InfoNote「合计是下界：没有回报的记为未知，不计为 0。」。
  - 执行端卡（Card，标题「执行端（Pi）」）：totals.totalTokens（--tt-display、tt-num）后接「token（下界）」；input、output、cacheRead、cacheWrite 四项，键名原样、与数字相邻（如 input 7,654,321，中间无标点）；三个计数标签文字 known N（success，title「已回报」）、partial N（warning，title「部分回报」）、unknown N（neutral，title「未回报」），N 前各一个空格；skipped_links 大于 0 时加一行「跳过的链接：N」，为 0 不显示。
  - 规划端卡（标题「规划端」）：planner 为 null 时空状态，标题「在设置里指定会话记录目录后统计」、说明「目录在设置里用系统对话框选择，保存后外壳重启本机服务，新目录才生效。」，action 是链接 [去设置]（a 元素，href 为 hrefWithMock('/settings')）；不为 null 时只写一行「规划端用量的显示在后续片接入」。
  - 按 attempt 表（Table，rowHeight 40，aria-label「按 attempt 的用量」，最小宽 900）：列任务、attempt、模型、状态、input、output、cacheRead、cacheWrite、合计；状态是 Tag 文字原样，tone 与 title：known success「已回报」、partial warning「部分回报」、unknown neutral「未回报」，其他值 neutral、不带 title；usage 为 null 或缺键显示「未知」（--tt-text-3）；attempts 为空显示「还没有执行端的用量记录」。
  - 按模型表（rowHeight 40，aria-label「按模型的用量」，最小宽 900）：列模型、回报情况（「known a · partial b · unknown c」）、占比、input、output、合计；占比 = 该行 totalTokens / executor.totals.totalTokens，一位小数加 %，分母为 0 或缺失显示「—」；条形轨道高 8、--tt-radius-full、--tt-surface-3 底，填充 --tt-navy-500，宽度用内联 style 的百分比；by_model 为空显示「还没有按模型的统计」。
  - 数字都带 tt-num。

### 插件（PluginsView、PluginDrawer）
- 说明「启停前先预览权限变化；锁与资源哈希由内核核对」；actions 放 [核对全部] DisabledAction（secondary、ListChecksIcon 16）；isEmpty：plugins、not_installed、problems 都为空才算空；空态标题「还没有插件」。
- 表（Table，rowHeight 40，aria-label「插件」，最小宽 860，onRowOpen 打开抽屉）：
  - ID、版本：等宽，版本 tt-num。
  - 启用列：启用或是 → brand；停用或否 → neutral；不限制 → 不套 Tag（描边样式）、title「没有配置启用名单」；其他值原样 neutral。
  - 锁、资源：一致 success 加 CheckIcon 12；漂移、不一致 warning 加 TriangleAlertIcon 12；以「无效」开头 danger 加 CircleXIcon 12；「-」显示「—」（--tt-text-3）；其他值 warning；不是「一致」时 title 为 reason。
  - 缺的权限：每项 danger 等宽 Tag；为空显示「—」。
  - 状态：等宽 Tag 文字原样；READY success、DRIFT warning、BLOCKED danger、其他 neutral；reason 非空时右侧接 --tt-text-caption、--tt-text-3 的 reason。
  - 操作：启用或是 → [停用…]；停用或否 → [启用…]；不限制 → 文字「详情」。
- 表下两个小节：「列入但未安装」列 not_installed（等宽），为空写「没有」；「问题」列 problems，为空写「没有」。
- 抽屉（Drawer，非模态）：
  - 标题：PluginsIcon 20（aria-hidden）、插件 ID（等宽）、状态 Tag。
  - status 不是 READY 时一条 warning Banner：reason 非空写「reason。」；缺的权限非空再接「缺的权限：a、b。」；两者都空写状态码。
  - manifest 小节（h3）：dl，标签列宽 96；依次 ID、版本；启用（不限制时后接「（没有配置启用名单）」）；权限每项等宽 Tag、属于 missing 的 danger 并加「（缺）」；api_version、capabilities、platforms、depends_on、conflicts 用「、」连接、为空写「（无）」；checks 不显示。
  - 资源哈希核对小节：三列 路径、sha256、结果（minmax(0,1fr) 120px 64px）；sha256 显示前 12 位加「…」，title 为全文；结果按锁列色调规则着色；detail 非空时后接「（detail）」。
  - 锁小节：generation 等宽、tt-num；lock_sha256 等宽、word-break break-all，旁边一个 IconButton「复制 lock_sha256」（CopyIcon 14）与复制结果文字。
  - footer：[重新核对]，DisabledAction secondary。
  - 抽屉里的读取：打开或换行时调读取函数；读取中「正在读取…」；出错「没能读到详情：命令（…）返回退出码 N。」，messages 放 pre；只认最后一次请求；卸载后不写状态。抽屉挂 body 下（MountLayer），切换路由随页面卸载消失。

### 公共件（InfoNote、复制、图标）
- InfoNote：一个 div，InfoIcon 16（aria-hidden）加文字；--tt-tone-info-bg 底、--tt-tone-info-fg 字、--tt-text-sm、--tt-radius-md；内边距 --tt-space-3、间距 --tt-space-2；不设 role、没有关闭钮；不用 Banner。
- copyText(text, clipboard?)：clipboard 缺省取 globalThis.navigator?.clipboard；没有 writeText 返回 unavailable，写入成功返回 copied，抛错返回 failed；结果文字依次「这个环境没有剪贴板接口」「已复制」「复制失败」，显示在复制钮旁（--tt-text-caption、--tt-text-3，不设 role）；不弹轻提示；点击时才读 navigator.clipboard。
- ExternalLinkIcon 自写，fill、stroke 只用 none 与 currentColor。

### 历史与审计（HistoryView、HistoryDrawer、KeyDiff、ActorTag）
- 说明「每次配置写入都有编号；点一行看前后快照的键级差异，必要时回滚」；isEmpty：entries 与 broken_lines 都为空才算空；空态标题「还没有配置历史」；broken_lines 非空时顶部 warning Banner「历史里有 N 行读不出来」。
- 表（Table，rowHeight 40，aria-label「配置历史」，最小宽 1000，onRowOpen）行按 number 倒序，各列：
  - 编号：#number（运行时拼），等宽 tt-num。
  - 时间：相对时间，title 为 formatLocalUtc，解析不了原样不带 title。
  - 资源：config 配置、local 本机文件、其他原样。
  - 动作：等宽；title 取 UI 文档 10.4 的中文说明（config.set / config.unset 设置 / 删除配置键；config.rollback 回滚配置；preset.use / preset.save / preset.remove 切换 / 保存 / 删除方案；role.set 修改角色绑定；profile.add / profile.edit / profile.remove 新建 / 修改 / 删除 profile；runtime.add / runtime.remove 登记 / 删除 runtime；external 检测到界面与命令之外的改动）；表外动作不带 title。
  - 对象：等宽，空写「—」。
  - 执行者：ActorTag（等宽 Tag），user-ui brand、user neutral、agent: info、undeclared warning、其他 neutral。
  - 确认：原样（flag、none），等宽、--tt-text-2。
  - 状态：published 已发布、aborted 已中止、unknown 未知、null 进行中或已中断；resolved 为真后接「（补判）」；title 为原状态码。
  - 改动的键：changed_keys 每个等宽 neutral Tag；changed_keys 为 null 时显示 note（遮蔽占位用 MaskedValue，否则 --tt-text-caption、--tt-text-3）；changed_keys 与 note 都没有写「—」。
  - 外部改动：external_changes 大于 0 时一个 warning Tag（TriangleAlertIcon 12）「检测到外部改动」，title「这条之后发现 N 次在配置中心之外的改动」；否则「—」。
- 表下一行注记「时间显示相对时间，悬停显示本地时间与 UTC；动作悬停显示中文说明。」。
- external_before_first 大于 0 时表上方加一行注记「第 1 条之前：配置中心之外已有的内容（记为基线，发现 N 次）」。
- 抽屉（画布 docs/ui-design/screens/History.dc.html 的差异抽屉 drawer=42）：
  - 标题「#n · action target」。
  - dl，标签列宽 96：时间（formatLocalUtc）、动作（等宽，后接 --tt-text-3 的中文说明）、执行者（等宽）、确认、状态。
  - external_changes 大于 0 时一条 warning Banner「这条之后检测到 N 次界面与命令之外的改动。」。
  - 「键级差异」小节（h3），按顺序判断取第一条成立的：
    1. resource 为 local：「本机文件不存快照，这一条只有审计记录，不能回滚。」
    2. diff 是非空数组：KeyDiff。
    3. diff 是空数组：「没有改动的键」。
    4. diff 为 null，且列表行的 note 是遮蔽占位，或列表或详情里的 note 含「疑似凭据」：列表的 changed_keys 非空、且 note 是占位（9.10 第 40 条的样子）时，逐键一行、之前与之后两格都用 MaskedValue 显示这个占位；否则（内核实际形状：changed_keys 为 null，note 是「疑似凭据，不显示」或「疑似凭据，未存内容」）不列键行、只显示 note 原文（--tt-text-3）；两种都在下面加一行 LockIcon 12 与「快照里有疑似凭据，只存了哈希。」。
    5. 其他：显示 entry.note；没有 note 写「快照缺失，没有逐键差异」。
  - footer：说明文字（见写入口），加 [回滚到这一条之后] DisabledAction secondary（RotateCcwIcon 16）。
  - 抽屉里的读取同插件抽屉（读取中「正在读取…」、出错块、只认最后一次、卸载后不写状态）。
- KeyDiff：
  - 三列 键、之前、之后（150px minmax(0,1fr) minmax(0,1fr)）。
  - 之前那格写「− 值」（减号 U+2212，--tt-diff-del 底）；之后那格写「+ 值」（--tt-diff-add 底）；值块用 --tt-mono-sm、--tt-radius-sm。
  - 值的文字：字符串原样；null 写「未设置」（--tt-text-3，不带符号与底色）；数字与布尔转成字符串；对象与数组写 JSON 文本。
  - 字符串是遮蔽占位时用 MaskedValue，不带底色；键 word-break break-all。

### 抽屉、焦点与 Esc
- 用 Drawer：role=dialog、aria-modal=false；没有遮罩、不困焦点、点抽屉外不关；打开时焦点进头部「关闭（Esc）」钮；焦点在抽屉里按 Esc 关闭并 stopPropagation；关闭后焦点回打开时 activeElement。
- 关闭钮工具提示出现后（400ms），焦点在钮上按 Esc，Tooltip 先关提示、抽屉不关，再按一次才关（既有行为，不改）。
- 焦点在抽屉外按 Esc 不关（不在页面层补全局 Esc）。
- 打开方式：Table onRowOpen（点击行或 Enter）；开着时点另一行只换内容；选中行取最后打开的那一行、关闭后保留。
- 换行后关闭的焦点：视图在关闭后的 effect 里把焦点移到 data-selected 的那一行（tbody tr[data-selected]），回到最后打开的那一行（React 18.3.1 先跑清理再按子先父后跑 effect，故晚于 Drawer 清理里的还焦点）。
- 单元格里不放可聚焦元素；[详情] 只显示文字「详情」整行可打开；行内禁用入口外面包 span 拦 click 冒泡。

### 写入口
- 全部用 DisabledAction，reason 缺省「第二阶段接入」：凭据每行 [录入…]（secondary、sm、ExternalLinkIcon 14）；插件页头 [核对全部]（secondary、md、ListChecksIcon 16）、行内 [停用…]/[启用…]（ghost、sm）、抽屉底栏 [重新核对]（secondary、md）；历史抽屉底栏 [回滚到这一条之后]（secondary、md、RotateCcwIcon 16）；日志读法 A 下 [检索] 可用。
- 页面可用按钮白名单：PageFrame 刷新（凭据页叫重新检查）与重试、Tabs 两页签、[检索]、抽屉关闭钮、[复制 lock_sha256]；可用链接只有 [去设置]。
- 历史抽屉底栏说明：最新一条「这是最新的一条，回滚后没有变化」；本机文件「本机文件不存快照，不能回滚」；其余不写；按钮提示仍「第二阶段接入」。写入口个数不含 offline 时 PageFrame 自带的 [重新连接]。

### 遮蔽值
- 后端字符串逐字等于 UI 文档 7.13 四个占位之一时一律用 MaskedValue（LockIcon 14、--tt-text-3 斜体、title「内核已遮蔽」）：凭据变量名与 used_by 的 id、历史表改动的键的 note、历史抽屉键级差异的旧值新值与第 4 种情形占位。不是占位的说明按普通文字，不套 MaskedValue。凭据页本身没有值可显示（没有值列与占位用遮蔽样式分开验收）。

### 样式取值
- 宽表最小宽：凭据 720、插件 860、按 attempt 与按模型 900、历史 1000；最小宽写在以 .tt-table 为选择器的规则上（不用 .tt-table-wrap）；最后一列靠右。
- 占比条：高 8、最小宽 60px；百分比文字宽 44px。
- mark：圆角 --tt-radius-sm、内边距 0 1px；样式写在以 mark 元素为选择器的规则里。
- KeyDiff 值块：内边距 1px --tt-space-1；三列 150px minmax(0,1fr) minmax(0,1fr)。
- 抽屉 dl：两列 96px minmax(0, 1fr)、间距 --tt-space-1 --tt-space-3；小节间距 --tt-space-4。
- 资源表：三列 minmax(0, 1fr) 120px 64px、表头高 32px、行与键级差异行高 36px。
- 小节卡：--tt-surface-1 底、1px --tt-border、--tt-radius-lg、内边距 --tt-space-3 --tt-space-4；小节标题 h2 用 --tt-title-sm，外边距 0 0 --tt-space-2。
- 检索表单卡：flex、可换行、gap --tt-space-3、内边距 --tt-space-3 --tt-space-4；检索框 flex 1 1 320px；任务下拉宽 200px；最多条数宽 96px。
- 检索结果：头部内边距 --tt-space-2 --tt-space-4；组头高 32px 且 --tt-surface-2 底；每条内边距 --tt-space-2 --tt-space-4、两行间距 --tt-space-0_5；摘录 --tt-mono-md 且 white-space pre；path:line 用 --tt-mono-sm 与 --tt-text-2。
- 用量：合计数字 --tt-display；两张卡之间 --tt-space-4。
- InfoNote：--tt-tone-info-bg 底、--tt-tone-info-fg 字、--tt-radius-md。
- 令牌与 px：尺寸字面量同一行写出处注释（画布 docs/ui-design/screens/{Secrets,Logs,Plugins,History}.dc.html 行号、UI 文档 docs/themis-tally-3.0-桌面端-UI设计.md 节号或「规划端定」）；颜色、字体、圆角、阴影、层级只用令牌。
- 1024 规则：所有宽表都在 overflow auto 的容器里；grid 里的 1fr 一律写 minmax(0, 1fr)；会被压缩的 flex 子元素写 min-width: 0；长的等宽串（sha256、路径、键名）用 word-break 或省略号；页面与抽屉里没有超过内容宽度的固定宽度。
- 内联 style 只用于运行时算出的占比条宽度（只出现在 logs-UsagePanel.tsx）。

### 过渡与长期断言
- 过渡断言（docstring 第一行「接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据；页内读取函数并入 api.ts）」）：经 ?mock= 渲染 App 的四页五态；由夹具得到的具体值（行数、数字、写入口个数）；页内读取函数返回的夹具与参数规则。
- 长期断言：视图组件（注入数据与读取函数）、纯函数、CSS 取值、源码规则、写入口全部禁用这条规则本身、抽屉的焦点与 Esc。

### 页面结构与边界
- 每个页面文件含 PageFrame；顶层不新增 *Page.tsx（readonly2 里文件名不以 Page.tsx 结尾）；视图不写 data-page-state、不渲染 h1；整页恰有一个带 data-page-state 的元素。
- 必须创建的文件（allowed_new_files 是许可，同时也是义务）：28 个新源码与夹具（common-*、secrets-*、logs-*、plugins-*、history-*、src/mock/readonly2-*.ts，含 logs-styles.css）与 9 个测试全部要建。
- LogsPage、PluginsPage、HistoryPage 从 ./readonly2/common-readers 引入 searchLogs/getPlugin/getHistoryEntry，并以模块级引用传给视图。
- 占比条与内联 style 只在 logs-UsagePanel.tsx。
- Drawer.css 的 top 改为 40px，同行写出处注释；文件头注释写出 40 并删掉「顶边取 0」。
- 夹具只能是 .ts，不写 .json（src/mock/ 恰 14 份 JSON）；src/pages/ 顶层仍恰 9 个 *Page.tsx 且都含 PageFrame；PageFrame 的 load 与 isEmpty 用模块级引用。

## Steps
1. 预检（只读）：核对 Repository facts 与基线（尤其 G6 REAL_PAGES 在 :2010 已含四页、:2045–:2047 保留断言、api.ts 13 个读函数、Drawer.css top=0、mock 恰 14 JSON、pages 恰 9 个 *Page.tsx）；不符就停并报告。不改文件。
2. 公共件：common-icons、common-format、common-InfoNote、common-copy、common-styles；测试 readonly2-logic 公共部分。验收：千分位、本地与 UTC 时间、保留 mock 的地址、复制三结果、图标 fill/stroke 只用 none 与 currentColor。风险：本地时间期望值写死时区。
3. 页内读取函数与夹具：common-readers.ts、src/mock/readonly2-*.ts；测试 readonly2-readers。验收：五开关值效果、夹具之外参数、深拷贝、command 数组、检索按 task 过滤与按 max 截断与 truncated。风险：夹具写成 .json（S2 变红）、字符串碰到守卫。
4. 凭据页：secrets-* 与 SecretsPage.tsx；测试 readonly2-secrets。验收：D01。风险：多出值列或值文字、none 映射错、改说明或空态标题。
5. 用量页签：logs-UsagePanel、logs-styles.css 与 logs-logic 用量部分；测试 readonly2-logs 用量部分。验收：D03。风险：状态码翻中文、null 显示 0、占比条用金色。
6. 检索页签：logs-SearchPanel、logs-SearchResults、logs-styles.css 与 logs-logic 检索部分；测试 readonly2-logs 检索部分。验收：D02。风险：截断提示写命中条数、过期回应覆盖新结果、高亮回溯卡死。
7. 日志与用量页接线：logs-LogsView 与 LogsPage.tsx（从 common-readers 以模块级引用传入 searchLogs）。验收：页签切换、PageFrame 五态、?mock=empty 下仍是 data。风险：给 LogsPage 传 isEmpty、把页签写进地址。
8. 插件页与抽屉：plugins-* 与 PluginsPage.tsx（从 common-readers 以模块级引用传入 getPlugin）；测试 readonly2-plugins。验收：D04、D05。风险：关闭清 selectedKey、换行后焦点回最早行、[详情] 做成可聚焦、点禁用钮开抽屉。
9. 历史与审计页与差异抽屉：history-* 与 HistoryPage.tsx（从 common-readers 以模块级引用传入 getHistoryEntry）；测试 readonly2-history。验收：D06、D07。风险：执行者色调对调、按正序排、遮蔽值普通文字、源码写出井号加数字。
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
- D09：写入口——写入口小节列出的入口全部 disabled、悬停 400ms 出现 role=tooltip 文字「第二阶段接入」；各页可用按钮只在白名单内；夹具下个数（不含 offline 重新连接）凭据 2、插件 3（抽屉开 4）、历史 0（抽屉开 1）；证据：V01。
- D10：样式与 1024 前提——见 Behavior contract 的「样式取值」小节；令牌与 px 注释；宽表都在可横向滚动容器；内联 style 只出现在占比条；证据：V01。
- D11：源码规则——公共约定里的源码守卫（夹具字符串也算）；四个页面文件都含 PageFrame、load 与 isEmpty 不是内联函数；src/mock/ 仍恰 14 份 JSON、src/pages/ 顶层仍恰 9 个 *Page.tsx；证据：V01。
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
