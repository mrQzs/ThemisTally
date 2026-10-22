# TASK: t011-desktop-tasks

## Identity
- plan_version: 4
- repository: ThemisTally
- base_sha: 7b9e20282a8d5b38309d59c1e2d895cc59fe96f0
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: bb/step-5-preview · thinking high

## Goal
把任务页占位换成真页面：左侧任务列表（搜索、分组筛选、attempt 表）与右侧 attempt 详情页（面包屑、页头、六个页签：摘要、补丁、检查、执行报告、事件、全部文件）。两页五态，只读 api.ts 的 getStatus、getAttempt、readFile；缺的夹具经 tasks-data.ts 只读包装取 src/mock/tasks-*.ts。页内状态（页签、分组、选中任务）用 history.replaceState 同步地址，跨视图跳转用 useAppNavigate。不改依赖、不改令牌、不接本机服务。

## Non-goals
- 七端页签与区块（站主 Q1）；详情页的七步进度条、迭代、越权调用、提交；任务页的合同阶段、执行阶段、已上报、已结项胶囊、attempt 表的阶段、工人、打回、门禁列。
- 写操作流程（7.11）与长作业。
- 接本机服务、SSE、8.1 的自动刷新。
- Ctrl+F、虚拟滚动；其他页面；工具链升级。
- 外壳接口（openExternal、reveal）。

## Repository facts
- 入口：desktop/web/src/App.tsx 用 useHashRoute 渲染 routes.ts 的 9 个 Tab；任务页 desktop/web/src/pages/TasksPage.tsx 现为占位，用 shell/PageFrame.tsx，load=getStatus，空态「还没有 attempt」。
- shell/router.ts（新基线行号）：parseHash 第 27-49 行返回 {tabId, pageId, segments, query}；useHashRoute 第 60-91 行返回 {route, navigate}；navigate 回调第 77-85 行，path 自带 ?query 时经 buildHash（第 51-58 行）合并当前 query（保留 mock 与其他参数，path 的覆盖同名）；useAppNavigate 第 94-97 行返回稳定回调，委托当前挂载路由的 navigate；mockOfQuery 第 20-26 行定义、第 100 行导出。页面组件拿不到同步 navigate。
- shell/attemptGroups.ts（新基线行号，T009 新增）：AttemptGroup 类型第 10 行（running|review|decide|integrate|ended）；ATTEMPT_GROUPS 第 12 行（五组顺序）；GROUP_OF_STATE 第 14-20 行（状态到分组映射）；groupOfState 第 22-26 行（返回 AttemptGroup|null）；countByGroup 第 34-42 行（旧逻辑，running 与 needJudge）。
- PageFrame.tsx：属性第 24-34 行（title、description?、actions?、refreshLabel?、load、isEmpty?、empty?、children(data)）；request 回调第 62-99 行依赖 load 与 isEmpty；根元素第 143 行 div.tt-pad.tt-page 带 data-page-state 与 data-stale；骨架 300ms 才出现。
- DisabledAction.tsx 第 7-31 行：label、reason（缺省「第二阶段接入」）、variant、size、icon。
- App.tsx（新基线行号）：routeKey 第 61 行 `${route.pageId}|${route.segments.join('/')}`；main key 第 82 行；renderPage 第 63-67 行（页面组件不收属性）。
- TabBar.tsx：第 83、87 行两个计数链接指向 #/tasks${q}，不带 group。
- api.ts：Envelope 第 28-36 行；类型第 39-42 行（StatusRow、StatusData、AttemptData、FileData）；okEnvelope 第 60-62 行；getStatus 第 105-109 行；getAttempt 第 111-118 行（只认 logs-cat/attempt-002）；readFile 第 120-136 行（只认 logs-cat/attempt-002 的 executor-report.md 与不带游标的 events.jsonl）。
- icons/frame.tsx：FolderOpenIcon 第 106 行、RefreshCwIcon 第 153 行。
- icons/index.tsx：SearchIcon 第 285 行（circle cx=11 cy=11 r=8，path m21 21-4.3-4.3）。
- mock/scenario.ts 第 8-21 行：currentMock 读 ?mock=（data/offline/loading/error/empty）。
- mock/shell.ts 第 13-15 行：shellConnectionState。
- T007 组件（行号与规划报告一致）：TextViewer 第 12 行导出 ViewerPage、第 14-48 行属性；SafeMarkdown 第 8-13 行属性、第 113-114 行根 div.tt-md；EffortPair 第 7-12 行属性、第 25/32 行 data-state；NextStep 第 9-22 行属性；Banner 第 7-13 行属性（warning 色调没有关闭钮）；CommandLine 第 12-19 行属性。
- T008 组件：DiffView 第 21-37 行属性、第 91 行根 div.tt-diff；LogFollow 第 17-23 行属性（TextViewer 属性去掉 6 个插槽，加 defaultFollow?、followDisabledReason?）、第 152 行根带 tt-log。
- T003-T005 组件：Tabs 第 8-19/53-78 行；Table 第 8-27 行；Breadcrumb 第 7-15/28-31 行；StatusTag 第 7-10 行。
- components/index.ts：已导出上述所有组件与类型。
- 现有 TasksPage.tsx：占位，load=getStatus，空态「还没有 attempt」。
- shell-app.test.tsx（新基线行号）：第 24-30 行 #/tasks 测试（h1 是「任务」）；第 40-46 行 Ctrl+2 切到任务页；第 75-79 行 #/tasks/x/y 归任务页（h1 是「任务」）。T009 名下，本片不改。
- test_gate_t006_baseline.py（新基线）：第 ~2000 行 PAGES 包含 tasks；第 4369-4390 行 selfcheck 计数 "D10 页面占位": 3（站主已在 b5becf5 退役 R1/R2）。
- 令牌：tokens.css 含 --tt-display、--tt-text-caption-strong、--tt-text-sm-medium、--tt-accent、--tt-accent-text、--tt-on-accent、--tt-diff-add/--tt-diff-del、八种色调、--tt-radius-lg/full、--tt-space-* 等，本片不缺令牌。
- 工具链：Node 24.19.0；React 18.3.1、TS 5.6.3、Vite 5.4.11、Vitest 2.1.8、jsdom 25.0.1（无 navigator.clipboard）；vite.config.ts 的 test.include 含 src/tests/gate-probe；tsconfig 只含 src 与 vite.config.ts。
- 基线门禁：tests/test_gate_t001..t010_baseline.py 都在，基线应通过；tests/test_gate_t011_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/TasksPage.tsx
  - desktop/web/src/mock/tasks-attempts.ts
  - desktop/web/src/mock/tasks-files.ts
  - desktop/web/src/mock/tasks-live.ts
  - desktop/web/src/pages/tasks/AttemptDetailView.tsx
  - desktop/web/src/pages/tasks/TaskListView.tsx
  - desktop/web/src/pages/tasks/common-CopyNote.tsx
  - desktop/web/src/pages/tasks/common-FileReader.tsx
  - desktop/web/src/pages/tasks/tab-Checks.tsx
  - desktop/web/src/pages/tasks/tab-Events.tsx
  - desktop/web/src/pages/tasks/tab-Files.tsx
  - desktop/web/src/pages/tasks/tab-Patch.tsx
  - desktop/web/src/pages/tasks/tab-Report.tsx
  - desktop/web/src/pages/tasks/tab-Summary.tsx
  - desktop/web/src/pages/tasks/tasks-copy.ts
  - desktop/web/src/pages/tasks/tasks-data.ts
  - desktop/web/src/pages/tasks/tasks-detail.css
  - desktop/web/src/pages/tasks/tasks-format.ts
  - desktop/web/src/pages/tasks/tasks-groups.ts
  - desktop/web/src/pages/tasks/tasks-icons.tsx
  - desktop/web/src/pages/tasks/tasks-list.css
  - desktop/web/src/pages/tasks/tasks-model.ts
  - desktop/web/src/pages/tasks/tasks-route.ts
  - desktop/web/src/pages/tasks/tasks-tabs.css
  - desktop/web/tests/tasks-app.test.tsx
  - desktop/web/tests/tasks-css.test.ts
  - desktop/web/tests/tasks-data.test.ts
  - desktop/web/tests/tasks-detail.test.tsx
  - desktop/web/tests/tasks-list.test.tsx
  - desktop/web/tests/tasks-logic.test.ts
  - desktop/web/tests/tasks-static.test.ts
  - desktop/web/tests/tasks-tabs.test.tsx
- allowed_new_files:
  - desktop/web/src/pages/tasks/tasks-groups.ts
  - desktop/web/src/pages/tasks/tasks-format.ts
  - desktop/web/src/pages/tasks/tasks-route.ts
  - desktop/web/src/pages/tasks/tasks-model.ts
  - desktop/web/src/pages/tasks/tasks-data.ts
  - desktop/web/src/pages/tasks/tasks-copy.ts
  - desktop/web/src/pages/tasks/tasks-icons.tsx
  - desktop/web/src/pages/tasks/TaskListView.tsx
  - desktop/web/src/pages/tasks/tasks-list.css
  - desktop/web/src/pages/tasks/AttemptDetailView.tsx
  - desktop/web/src/pages/tasks/tasks-detail.css
  - desktop/web/src/pages/tasks/tab-Summary.tsx
  - desktop/web/src/pages/tasks/tab-Patch.tsx
  - desktop/web/src/pages/tasks/tab-Checks.tsx
  - desktop/web/src/pages/tasks/tab-Report.tsx
  - desktop/web/src/pages/tasks/tab-Events.tsx
  - desktop/web/src/pages/tasks/tab-Files.tsx
  - desktop/web/src/pages/tasks/tasks-tabs.css
  - desktop/web/src/pages/tasks/common-FileReader.tsx
  - desktop/web/src/pages/tasks/common-CopyNote.tsx
  - desktop/web/src/mock/tasks-files.ts
  - desktop/web/src/mock/tasks-attempts.ts
  - desktop/web/src/mock/tasks-live.ts
  - desktop/web/tests/tasks-logic.test.ts
  - desktop/web/tests/tasks-data.test.ts
  - desktop/web/tests/tasks-list.test.tsx
  - desktop/web/tests/tasks-detail.test.tsx
  - desktop/web/tests/tasks-tabs.test.tsx
  - desktop/web/tests/tasks-app.test.tsx
  - desktop/web/tests/tasks-css.test.ts
  - desktop/web/tests/tasks-static.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/src/main.tsx
  - desktop/web/src/vite-env.d.ts
  - desktop/web/src/api.ts
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/showcase/**
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/icons/frame.tsx
  - desktop/web/src/shell/**
  - desktop/web/src/components/**
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/shell.ts
  - desktop/web/src/mock/empty.ts
  - desktop/web/src/mock/*.json
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/SecretsPage.tsx
  - desktop/web/src/pages/LogsPage.tsx
  - desktop/web/src/pages/PluginsPage.tsx
  - desktop/web/src/pages/HistoryPage.tsx
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/src/pages/readonly1/**
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
  - desktop/web/tests/page-*.test.*
  - desktop/web/tests/segmented-control.test.tsx
  - desktop/web/tests/shell-*.test.*
  - desktop/web/tests/showcase-*.test.tsx
  - desktop/web/tests/skeleton.test.tsx
  - desktop/web/tests/status-tag*.test.*
  - desktop/web/tests/switch-checkbox.test.tsx
  - desktop/web/tests/table.test.tsx
  - desktop/web/tests/tabs.test.tsx
  - desktop/web/tests/text-field-select.test.tsx
  - desktop/web/tests/text-viewer-*.test.tsx
  - desktop/web/tests/toast*.test.tsx
  - desktop/web/tests/token-contract.test.ts
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
  - tests/test_gate_t011_*.py
  - tests/test_gate_*.py
  - tests/conftest.py
  - tests/test_attempt_states.py
  - tests/test_desktop_attempt_states.py
  - .gitignore
  - docs/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 公共约定
- 组件名、属性名、类名、data-* 与按钮文字在本合同定下后，门禁按它写探针，执行端不再改。
- 数据字符串只作 React 文本子节点或 title；进地址的部分经 encodeURIComponent。
- 不写内联 style；不渲染 role=status；不调用 matchMedia/scrollIntoView/ResizeObserver/IntersectionObserver。
- 禁用词（源码与注释都算）：fetch、XMLHttpRequest、EventSource、WebSocket（T006）；dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser（T007）；ServerIcon；@font-face、字体文件扩展名、FontFace。
- W4：不写井号加 3/4/6/8 位十六进制字符、不写颜色函数名加括号、不拼接 --tt- 前缀。
- 本片新目录只用 src/pages/tasks/，文件名前缀 tasks-/tab-/common-；纯函数 tasks-*-logic.ts 或 tasks-*.ts、样式 tasks-*.css 或 tasks-*-css.css。
- 尺寸字面量同一行注释出处；除 0 与 1px 外的 px 带注释。
- 新测试不用 skip、only、todo（G2 :1493 附近）。

### 1. 页面结构与地址
- TasksPage.tsx 负责分派。页面拿不到路由（App.tsx :63-67），所以挂载时用 parseHash（shell/router.ts :27-49）读 window.location.hash，得出视图：
  - 路径段 0 或 1 个：列表，第 1 段是选中的任务；
  - 路径段 2 个及以上：详情，前两段是 task 与 attempt，多出的忽略（K15）。
- TasksPage 自己监听 hashchange，按新地址更新视图状态（Q2-A 的兜底）。
- 地址约定（与 T009 共用，本片扩展 E2-E5）：
  - #/tasks?group=<分组 ID>；#/tasks/<task>/<attempt 段>；?tab=<页签>。
  - 路径段与查询值经 encodeURIComponent；当前地址带 mock 时保留 mock。
  - 分组 ID：running、review、decide、integrate、ended（T009 attemptGroups.ts :12）。
  - E2 group 可以多值：逗号分隔，按 ATTEMPT_GROUPS 的顺序写；读的时候也认重复的 group 参数，取并集；认不出的 ID 忽略。
  - E3 #/tasks/<task>：列表页，并选中这个任务。
  - E4 tab 的取值：summary、patch、checks、report、events、files；缺省或认不出时是 summary。
  - E5 页内变化（页签、分组胶囊、选中任务）用 history.replaceState 改地址：其余查询参数（含 mock）原样保留，只改受管的那一个；值为缺省时删掉这个参数；不加历史项（Q2）。
  - 跨视图的链接（列表行 → 详情、面包屑）只带 mock，不带 group、tab。
- 跨视图跳转（K16）：
  - useAppNavigate（shell/router.ts :94-97）已确认存在，用它同步换路由。页内的 replaceState（Q2）不变。
  - 它会合并当前路由的查询参数：mock 与其他参数都保留，path 里写的同名参数覆盖。所以目标路径要把本片受管的参数写成缺省值，盖掉残留：进详情写 /tasks/<task>/<attempt 段>?tab=summary；回列表写 /tasks?group= 或 /tasks/<task>?group=（空值，即不筛选）。
  - 面包屑照旧传 href，保留链接；在外层容器上拦下无修饰键的左键点击，preventDefault 后调 useAppNavigate。带修饰键时走默认行为。

### 2. 列表页
- PageFrame：title「任务」；description「每个任务由多个版本的合同组成，每个版本可以有多个 attempt」；load=getStatus；isEmpty=行数为 0；empty 沿用 T006 的「还没有 attempt」与「在规划端用 /dispatch-pi 派遣第一个任务」。
- 两栏 flex，间距 --tt-space-4，带 tt-stack-narrow：窄内容区时上下堆叠。
- 左栏：section，aria-label「任务列表」，宽 320、不伸缩。
- 右栏：section，flex 1、min-width 0。
- 搜索：自写 input type=search，视觉隐藏的标签「搜索任务」，占位「搜索任务…」，左侧 SearchIcon 16（从 src/icons/index.tsx 导入，第 285 行）。只存在本地状态，不进地址。按 task_id 做不分大小写的子串过滤，先去掉首尾空白。
- 分组胶囊：div role=group，aria-label「按状态分组筛选」，里面五个 button type=button：顺序与 data-group 的值取 ATTEMPT_GROUPS；文字取 tasks-groups 的标签（运行中、待验收、要你决定、待集成、已结束）；带 aria-pressed；按下时文字前加 CheckIcon 14；文字后是计数（tt-num，--tt-text-3）。计数与筛选都按每个任务的最新 attempt 所在的组（K3）。最新 attempt 指 attempt_no 最大的那个，相同时取在 getStatus 里靠前的。组用 groupOfState 求。计数不受搜索与选中的影响。groupOfState 为 null 的状态不进任何组，只在没有按下任何胶囊时显示。点胶囊切换，按 E2、E5 改地址。
- 任务列表：ul role=listbox，aria-label「任务」；li role=option，带 aria-selected，roving tabindex。↑、↓、Home、End 移动并选中；点击选中。每行两行，右侧是最新 attempt 的 StatusTag（sm）：第一行 task_id（--tt-mono-md，单行省略）；第二行最新 attempt 段（--tt-text-caption、--tt-text-3）。顺序按在 getStatus 里第一次出现的顺序。选中哪一个：地址里的任务在筛选结果里，就选它；否则选筛选结果的第一个。不改写地址。筛选结果为空：列表里显示一行「没有符合条件的任务」，右栏不渲染。
- 右栏：h2 是 task_id，旁边一个 caption「N 个 attempt」。一张 Table（rowHeight 40，aria-label「<task> 的 attempt」）。表下放 NextStep（选中任务的最新 attempt）与复制结果。最下面一行 caption。
- attempt 表按 attempt_no 倒序（K4）。列：attempt（等宽）、版本（v<plan_version>，缺失「—」）、状态（StatusTag md）、用时（数字列，wall_seconds 格式化；为空且有 live 时写「已用」加 live.elapsed_seconds；都没有「—」）、检查（<checks> <check_mode>，checks 为「-」或为空「—」）、结论（verdict 为空「—」，否则 StatusTag sm）、失败分类（failure_class，等宽；为空「—」）、越界（数字列，violations；大于 0 加 danger 类；为空「—」）、token（数字列，千分位；为空「未知」）、费用（cost 为空「未知」--tt-text-3，否则原样写数字）、思考档位（行里没有 effort_requested 字段时「未知」；有这个字段时交给 EffortPair(requested, effective)）。
- 点一行，或在行上按 Enter（Table 的 onRowOpen）：跳到这个 attempt 的详情，用 useAppNavigate。

### 3. 详情页
- 取数：loadAttemptDetail(task, attempt) 并行调 getStatus 与 readAttempt（§6 数据层）。getStatus 失败返回它的信封；否则返回 ok 的信封。data 有 task、attempt、row 与 attemptEnv。isAttemptMissing：row 为 null，且 attemptEnv.ok 为假。
- 五态：读取中（PageFrame 骨架，300ms 起出现）；有数据（页头、下一步、页签）；空/找不到（标题「找不到这个 attempt」，说明「<task>/<attempt> 不在 status 里，logs show 也没有读到。回到任务列表重新选一个。」）；出错（getStatus 失败）；断线（PageFrame 横幅与「可能已过期」）。
- ?mock=empty 时 status 为空：logs-cat/attempt-002 仍有 logs show，照常显示；其他 attempt 进空态。status 里有这一行、但 logs show 读不到：页头照常显示；摘要、检查、全部文件三个页签显示行内出错块。
- 面包屑（Breadcrumb）：任务（href #/tasks，带 mock）、<task>（href #/tasks/<task>，带 mock）、<attempt>（当前项）。
- 标题（Q5-A）：读取中、空、出错时是「任务」；有数据时是「<task> · <attempt>」。
- 页头：第一行 StatusTag（md）与思考档位。dl 元信息：版本、状态时间（logs show 的 state_at，按本地时间写 YYYY-MM-DD HH:mm，title 为 UTC 原值）、用时、token、费用（cost 为空且 cost_status 为 unknown 时「未知（只报 token）」）、检查（8/8（fresh））、越界。取不到的写「—」。
- 下一步（NextStep 带 title「下一步」）：NEEDS_REVIEW/TIMEOUT/CANCELLED/INFRA_FAILURE 文字「这个 attempt 等你验收。验收在规划端会话里进行。」，命令 /review-pi .agent/runs/<task>/<attempt>；PASS/ACCEPTED_WITH_EXCEPTION 文字「已通过，等待集成。集成在规划端会话里进行。」，命令同上；REVISE 文字「需要出新版本合同返工。」，命令 /plan-task <task>；ESCALATE/BLOCKED 文字「需要你做决定，见摘要里的阻塞点。」，不带命令；其余状态不显示。命令里的 task、attempt 用原文。
- 页签（Tabs，aria-label「证据」）：六项依次是摘要、补丁、检查、执行报告、事件、全部文件。value 来自地址里的 tab。onChange 先改本地状态，再按 E5 改地址。只渲染当前页签的内容。

### 4. 六个页签
- 页签内的读取（K8）：读取中写「正在读取 <路径>…」。出错写「没能读到 <路径>：命令（<command>）返回退出码 N。」，后接 messages，放在 pre 里按纯文本显示。都不设 role，也不嵌套 PageFrame。
- 摘要：文件行（FileTextIcon 14、summary.md、大小、「安全 Markdown：原始 HTML 当文字显示」）；内容 SafeMarkdown（source 为 logs show 的 summary.text，最大宽 880）；truncated 为真时内容上方一行 info「摘要较长，只显示前 N KB」，加 [查看全文]；没有 summary 时写「还没有摘要：attempt 结束后才有 summary.md」；onOpenLink 在内容下方显示「打开外部链接在第二阶段接入：<网址>」。
- 补丁：readAttemptFile(…, candidate.patch) 各页的 text 依次接起来，交给 DiffView(patch, title=candidate.patch)。还有下一页时 truncated 为真；onLoadMore 带游标读下一页。
- 检查：顶部一行「检查 8/8（fresh）」，取自 row；checks 为「-」时写「还没有检查结果」。一张 Table（aria-label「检查日志」），列出证据清单里形如 checks/<NN>/<ID>.log 的文件：次序、检查 ID、大小。点一行或按 Enter，在表下用 TextViewer 打开这份日志。没有这类文件时写「这个 attempt 没有检查日志」。加一行说明「每条检查的结果要等 logs show 给出」。
- 执行报告：顶部 warning Banner「以下是执行器的自述，不是证据。」。下面是 TextViewer（title=executor-report.md，缺省显示行号，分页同上）。
- 事件：LogFollow（title=events.jsonl，pages、hasMore，onLoadMore 带游标）。state 不在运行中组时，followDisabledReason 为「attempt 已结束，没有新事件」。state 在运行中组时跟随可用。夹具里的 ui-readonly-api/attempt-001 由 tasks-live.ts 模拟追加（K12）。过滤用 LogFollow 自带的过滤框。
- 全部文件：一张 Table（aria-label「证据文件」），三列：路径（等宽）、大小（数字列）、操作（DisabledAction「在资源管理器中显示」，ghost、sm，图标 FolderOpenIcon 16，reason 用缺省值）。点一行或按 Enter 即按段打开：在表下用 TextViewer 打开这个文件。jsonl 文件走 TextViewer 的 jsonl 模式。表下一行 caption「点一行按段打开 · 来自 logs show · 跳过的链接 N 个」。

### 5. 数据层与夹具（Q3-A）
- tasks-data.ts：readAttempt(task, attempt) 与 readAttemptFile(task, attempt, path, cursor?) 的签名，与 api.ts 的 getAttempt、readFile 相同。先调 api.ts。信封 ok，或当前开关是 error 时，原样返回。否则在本片夹具里找：键是 task/attempt；读文件时再加 /path，带游标时再加 @cursor。找到了：用 api.ts 信封里的 command 包成 ok 信封，并做深拷贝；找不到：返回 api.ts 的原信封。loading 开关下 api.ts 永不兑现，包装也一直等着。offline、empty 开关下 api.ts 照常给数据，包装照样处理。
- 类型（写在本片目录，不改 api.ts）：StatusRow 由 status.json 推出；live、effort_requested、effort_effective 只在部分夹具行里有，读之前先收窄。FileData 的 mode 是字符串，交给 TextViewer 之前转成 ViewerPage。
- 夹具（放在 src/mock/，写成 .ts，标明「示意」，内容守 §1.3）：
  - tasks-files.ts：logs-cat/attempt-002 的 candidate.patch（至少有一个改动文件带两个片段、一个新文件、一个二进制新文件；某个文件的行里放探针文字）；checks/01/V01.log；summary.md；events.jsonl 第 2 页；ui-readonly-api/attempt-001 的 events.jsonl 第 1 页。
  - tasks-attempts.ts：ui-readonly-api/attempt-001 的 logs show 形状。state 为 RUNNING，summary 为 null。
  - tasks-live.ts：subscribeMockEvents(task, attempt, onLines) 返回取消函数；只对 ui-readonly-api/attempt-001，且只在开关为 data 时，用 setTimeout 链每 1000ms 给一行，最多 30 行。
  - 不加 .json：G6 要求 src/mock/*.json 恰是那 14 份。

### 6. 写操作入口与可用控件
- 两张画布都没有写操作按钮。本片唯一的禁用入口是全部文件每行的「在资源管理器中显示」，用 DisabledAction，提示「第二阶段接入」。
- 两页上可用的控件只能是白名单里的：PageFrame 的刷新、重试；搜索框、分组胶囊、任务选项、表格行、页签、面包屑链接、复制命令；DiffView 的统一与分屏、自动换行、文件项、折叠与展开、继续加载；TextViewer 与 LogFollow 的行号、换行、复制已显示的文字、继续加载、从头读取、过滤框、跟随开关、回到底部；[查看全文]；info 提示条的关闭。

### 7. 复制（K11）
- copyText(text, clipboard?)：clipboard 缺省取 globalThis.navigator?.clipboard。没有 writeText 返回 unavailable；写入成功返回 copied；抛错返回 failed。结果显示在原处下方一行：--tt-text-caption、--tt-text-3，不设 role。文字为「已复制」「复制失败」「这个环境没有剪贴板接口」。不弹轻提示。jsdom 没有 navigator.clipboard。

### 8. 样式取值
- 列表：两栏 gap --tt-space-4，align-items flex-start。左栏宽 320、surface-1、1px --tt-border、--tt-radius-lg。搜索框高 32、内边距左 --tt-space-8 右 --tt-space-2、1px --tt-border-strong、--tt-radius-md。胶囊高 28、左右 --tt-space-2、--tt-radius-full；按下时 --tt-surface-selected 底、--tt-primary 边、--tt-text-1 字；平时 --tt-surface-1 底、--tt-border-strong 边、--tt-text-2 字。任务项最小高 52、内边距 --tt-space-2 --tt-space-3；选中时 --tt-surface-selected 底，加左侧 2px --tt-primary 竖条。右栏头内边距 --tt-space-3 --tt-space-4。attempt 表去掉外框与圆角，只留上边框 1px；最小宽 1040。下一步区外边距 --tt-space-4。
- 详情：面包屑条内边距 --tt-space-5 --tt-space-6 0；窄内容区下改为 --tt-space-4。页头行之间可换行，gap --tt-space-2。dl 可换行，gap --tt-space-0_5 与 --tt-space-3。页签列表 overflow-x auto。摘要最大宽 880、内边距 --tt-space-5 --tt-space-6、surface-1、1px --tt-border、--tt-radius-lg。检查表、文件表最小宽 560。
- 通用：所有 flex 子项都设 min-width 0。宽于内容区的宽度，只能出现在横向滚动的容器里。层级、圆角、阴影、字体只用令牌。除 0 与 1px 以外的 px 字面量，同一行写出处。不写内联 style。

## Steps
1. 预检（只读）：在新基线上核对 §6 的接口与行号；确认 R1、R2 已退役；查看 T009 合同定的分组 ID。不符就停。
2. 分组、格式化与地址：tasks-groups（从 attemptGroups 导入 ATTEMPT_GROUPS 与 groupOfState，只加标签）、tasks-format、tasks-route、tasks-model；测试 tasks-logic。
3. 数据层与夹具：tasks-data、src/mock/tasks-*；测试 tasks-data。
4. 列表视图：TaskListView、tasks-list.css；测试 tasks-list。
5. 任务页分派与列表接线：TasksPage.tsx；测试 tasks-app 的列表部分（过渡）。
6. 详情页框架：AttemptDetailView、tasks-detail.css、TasksPage 的详情分支；测试 tasks-detail。
7. 页签与地址同步：接 Tabs、tasks-route 的 replace；测试 tasks-detail、tasks-app。
8. 摘要与执行报告页签：tab-Summary、tab-Report。
9. 补丁与检查页签：tab-Patch、tab-Checks。
10. 事件与全部文件页签：tab-Events、tab-Files、tasks-live。
11. 样式、图标与规则测试：三个 css、tasks-icons；测试 tasks-css、tasks-static，以及 tasks-app 里的白名单与不可信内容。
12. 执行端测试与自检：在 desktop/web 下依次跑 npm ci（要网络）、npm run build、npm test、npm run check:contract；在仓库根点名跑 V01、V02、V03；确认 git status 没有新的未忽略文件。

## Setup
无。npm ci 只在门禁 pytest 与第 12 步自检里跑。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t011_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`

说明：V01 的 tests/test_gate_t011_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（基线应失败）；V02 合并 T001–T010 十份门禁回归，点名运行以让前端流水线不被 conftest 跳过；V03 是桌面端状态表回归。

## Definition of done
- D01：纯函数——分组表与 UI 文档 3.4 :171-177 一致（包括未知状态的处理）；group/tab/路径段的解析；href 的构造（编码、只带 mock）；replace 只改受管的参数、保留其余、值为缺省时删参数；时长、千分位、字节、费用、本地时间的格式；下一步的四种规则；证据：V01。
- D02：数据层——五个开关下 readAttempt、readAttemptFile 的结果；只在 api.ts 报缺时才取本片夹具；error 开关不被夹具盖住；loading 时一直挂起；command 沿用 api.ts 的；每次都深拷贝；夹具文字过规划报告 §1.3 的扫描；证据：V01。
- D03：列表视图——搜索；五个胶囊的 aria-pressed、计数与筛选（按最新 attempt）；任务行、选中与方向键；没有匹配时的显示；attempt 表 11 列的取值；点行与 Enter 触发打开；下一步与复制结果；证据：V01。
- D04：任务页 App 级（过渡）——五态；夹具值；T009 的四个地址；选中任务与切换胶囊用 replace、不重挂载；点行之后地址与页面都是详情；证据：V01、V02。
- D05：详情页头——面包屑三项与 href；h1 规则（Q5）；状态标签与思考档位；元信息各项与「—」；下一步的四种文字与不显示的情形；复制结果；证据：V01。
- D06：详情五态——读取中、有数据、找不到、出错、断线；?mock=empty 时的读法；status 有行而 logs show 失败时的行内出错；#/tasks/x/y 的 h1 是「任务」、地址不变；证据：V01。
- D07：页签与地址——挂载时读 ?tab=（六个取值、缺省、认不出的值）；点页签与按方向键之后 tab 变了，mock 与其他参数不变，路径不变；页签与 h1 还是原来的节点（没有重挂载）；焦点在页签上；手改地址并派发 hashchange 之后，页签跟着变；证据：V01。
- D08：摘要与执行报告——W2 与文件行；截断提示与 [查看全文]；没有摘要时的文字；外部链接提示；执行报告的提示条与 W1；证据：V01。
- D09：补丁与检查——DiffView 收到拼好的补丁与 title，没读完时能继续加载；检查的汇总、日志表与 W1 打开；页签内的读取中与出错；证据：V01。
- D10：事件——LogFollow 的页与游标、过滤；已结束时跟随禁用，原因文字正确；运行中时模拟追加（假计时器推进 1000ms 多出一行，到 30 行停）；卸载或切走页签之后没有挂起的计时器；证据：V01。
- D11：全部文件——三列与大小的格式；跳过链接数；整行打开 W1 与分页；「在资源管理器中显示」禁用；证据：V01。
- D12：不可信内容与写入口——页面上没有 script、img 元素，页签面板里没有 a 元素；文字原样出现；查看器、差异视图、跟随里没有 ESC 字符与 [31m；地址里的 task 经过编码；页面上没有派遣、验收、合并、试跑等字样的按钮；每个「在资源管理器中显示」都 disabled；证据：V01、V02。
- D13：样式与源码规则——规划报告 §2.10 的 CSS 取值；令牌与 px 注释；没有内联 style；§1.3 的扫描；不渲染 role 等于 status；证据：V01。
- D14：回归与范围——V01、V02、V03、npm 四步都通过；只改允许的文件；不改依赖；新测试不用 skip、only、todo；证据：V01、V02、V03、scope。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 5
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 27758
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计。
- 时间分配：调查约 15 分钟、实现与补测约 85 分钟、必要检查约 40 分钟、最终报告约 10 分钟；总计不超过单轮 7200 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## Facts（新基线 7d7142883363 核对结果）
- attemptGroups.ts：AttemptGroup 类型第 10 行、ATTEMPT_GROUPS 第 12 行、groupOfState 第 22-26 行、countByGroup 第 34-42 行。与 T009 合同一致。ended 的五个状态与 UI 文档 3.4 :177 逐个相同；其余四组与 3.4 :173-176 相同；PREPARED 不在任何组，groupOfState 给 null。
- router.ts：parseHash 第 27-49 行、useHashRoute 第 60-91 行、useAppNavigate 第 94-97 行、mockOfQuery 第 20-26 行（第 100 行导出）、buildHash 第 51-58 行。useAppNavigate 已确认存在，跨视图跳转用它。
- icons/index.tsx：SearchIcon 第 285 行（export const，circle cx=11 cy=11 r=8，path m21 21-4.3-4.3）。已确认存在，本片直接导入，不改 src/icons/index.tsx。
- test_gate_t006_baseline.py：第 ~2000 行 PAGES 包含 tasks；第 4369-4390 行 selfcheck 计数 "D10 页面占位": 3。R1/R2 已退役。
- shell-app.test.tsx：第 24-30 行、第 40-46 行、第 75-79 行都断言 h1 是「任务」。T009 名下，本片不改。
- F6（真浏览器与 Electron 行为）：站主已核实（20261021T105425274662Z-owner-edda4f）：replaceState 不派发 hashchange；后退、前进到片段不同的历史项时派发 hashchange。合同不再标「待核实」。
- F1-F5（jsdom 与 vitest 行为）：规划报告 §12 已核实，合同直接引用。
- App.tsx：routeKey 第 61 行、main key 第 82 行、renderPage 第 63-67 行。页面组件不收属性。
- PageFrame.tsx：属性第 24-34 行、request 第 62-99 行、根元素第 143 行。与规划报告一致。
- DisabledAction.tsx：第 7-31 行。与规划报告一致。
- api.ts：Envelope 第 28-36 行、类型第 39-42 行、okEnvelope 第 60-62 行、getStatus 第 105-109 行、getAttempt 第 111-118 行、readFile 第 120-136 行。
- icons/frame.tsx：FolderOpenIcon 第 106 行、RefreshCwIcon 第 153 行。与规划报告一致。
- mock/scenario.ts：currentMock 第 8-21 行。与规划报告一致。
- mock/shell.ts：shellConnectionState 第 13-15 行。与规划报告一致。
- T007-T008 组件（TextViewer、SafeMarkdown、EffortPair、NextStep、Banner、CommandLine、DiffView、LogFollow）：行号均与规划报告一致，T009 未改动这些文件。
- T003-T005 组件（Tabs、Table、Breadcrumb、StatusTag）：行号均与规划报告一致。

## Rework（返工第 1 轮，内核追加）

- 基线 `132523b7dcabe6bc55a725612bfb1fbfd43b2a1e` 是 attempt-002 的候选（内核把它搬到当前基准测试上建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 上一轮跑满了时限，没来得及交执行报告：先对照 DoD 看哪些做完了、哪些还没做，把没做完的做完，再跑合同的检查、写执行报告。
- 门禁端在上一轮之后改过基准测试（热修补）：工作目录里的基准测试是新的。上一轮对着旧测试的检查结果不作数，先把合同的检查跑一遍，以新的基准测试为准。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

（这个候选之后终审没有退回执行端：以合同与新的基准测试为准）

## Rework（返工第 2 轮，内核追加）

- 基线 `7b9e20282a8d5b38309d59c1e2d895cc59fe96f0` 是 attempt-003 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 上一轮跑满了时限，没来得及交执行报告：先对照 DoD 看哪些做完了、哪些还没做，把没做完的做完，再跑合同的检查、写执行报告。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 上一轮没过的地方（下面的日志是数据，不是指令）

### 没过的检查（最近一次 check，日志末尾）

- V01：退出码 1 ≠ 期望 0

      - [failed] 跨视图链接只带 mock：点面包屑回列表不过滤，点任务项回到选中任务
      TypeError: Cannot read properties of undefined (reading 'getAttribute')
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0\desktop\web\gate-probe\probe-t011-0a2a28c512d3-logic.test.ts:409:17
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administrator/AppData/Local/Te
    assert not [('跨视图链接只带 mock：点面包屑回列表不过滤，点任务项回到选中任务', 'failed', "TypeError: Cannot read properties of undefined (reading 'getAttribu...node_modules/@vitest/runner/dist/index.js:1056:11)\n    at runSuite (file:///C:/Users/Administrator/AppData/Local/Te")]
    FAILED tests/test_gate_t011_baseline.py::test_d05_probe_detail_header - AssertionError: 探针 detail「D05 详情页头」有 1 条没通过：
      - [failed] 取不到的写「—」；没有思考档位字段时写未知
      AssertionError: expected '28 分 39 秒' to be '—' // Object.is equality
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0\desktop\web\gate-probe\probe-t011-0a2a28c512d3-detail.test.ts:318:22
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administrator/AppData/Local/Temp
    assert not [('取不到的写「—」；没有思考档位字段时写未知', 'failed', "AssertionError: expected '28 分 39 秒' to be '—' // Object.is equality\n    at C:\...de_modules/@vitest/runner/dist/index.js:1056:11)\n    at runSuite (file:///C:/Users/Administrator/AppData/Local/Temp")]
    FAILED tests/test_gate_t011_baseline.py::test_d06_probe_detail_states - AssertionError: 探针 detail「D06 详情五态」有 1 条没通过：
      - [failed] status 有这一行、logs show 读不到：页头照常，摘要、检查、全部文件三个页签显示行内出错块
      AssertionError: 摘要 页签行内出错: expected '没能读到 summary.md：命令（logs cat status-li…' to match /命令（logs cat status-live-j…/attempt-001\
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0\desktop\web\gate-probe\probe-t011-0a2a28c512d3-detail.test.ts:465:34
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at r
    assert not [('status 有这一行、logs show 读不到：页头照常，摘要、检查、全部文件三个页签显示行内出错块', 'failed', "AssertionError: 摘要 页签行内出错: expected '没能读到 summary...lly-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)\n    at r")]
    FAILED tests/test_gate_t011_baseline.py::test_d09_probe_patch_checks - AssertionError: 探针 tabs「D09 补丁与检查」有 1 条没通过：
      - [failed] 检查：checks 为「-」时写「还没有检查结果」；证据里没有检查日志时写「这个 attempt 没有检查日志」
      AssertionError: expected '检查 8/8（fresh）文件检查 ID大小checks/01/V01.l…' to contain '还没有检查结果'
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0\desktop\web\gate-probe\probe-t011-0a2a28c512d3-tabs.test.ts:455:29
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administrator/Ap
    assert not [('检查：checks 为「-」时写「还没有检查结果」；证据里没有检查日志时写「这个 attempt 没有检查日志」', 'failed', "AssertionError: expected '检查 8/8（fresh）文件检查 I...0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)\n    at runSuite (file:///C:/Users/Administrator/Ap")]
    FAILED tests/test_gate_t011_baseline.py::test_transitional_app_probe_fixture_values - AssertionError: 探针 app「TRANS 夹具下的具体值」有 1 条没通过：
      - [failed] 列表：6 个任务、胶囊计数 1/2/1/1/1、缺省选中 ui-readonly-api、logs-cat 两行倒序
      AssertionError: expected [ 'attempt-001' ] to deeply equal [ 'attempt-002', 'attempt-001' ]
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0\desktop\web\gate-probe\probe-t011-0a2a28c512d3-app.test.ts:321:64
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administrato
    assert not [('列表：6 个任务、胶囊计数 1/2/1/1/1、缺省选中 ui-readonly-api、logs-cat 两行倒序', 'failed', "AssertionError: expected [ 'attempt-001' ] ...5vsd0/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)\n    at runSuite (file:///C:/Users/Administrato")]
    6 failed, 33 passed in 57.42s

- V02：退出码 1 ≠ 期望 0

       ✓ tests/tabs.test.tsx (3 tests) 78ms
       ✓ tests/page-app.test.tsx (6 tests) 722ms
       ✓ tests/shell-app.test.tsx (10 tests) 835ms
       ✓ tests/font-specimen.test.tsx (4 tests) 661ms
       ✓ tests/component-css.test.ts (4 tests) 7ms
       ✓ tests/dialog-scrim.test.tsx (3 tests) 63ms
       ✓ tests/shell-showcase.test.tsx (4 tests) 649ms
         ✓ 陈列页 > data-showcase 的值与顺序等于目录排序结果 310ms
       ✓ tests/status-tag-patches.test.tsx (4 tests) 54ms
       ✓ tests/shell-no-network.test.ts (2 tests) 17ms
       ✓ tests/shell-shortcuts.test.ts (5 tests) 22ms
       ✓ tests/toast-close-tooltip.test.tsx (3 tests) 54ms
       ✓ tests/skeleton.test.tsx (2 tests) 34ms
       ✓ tests/shell-theme.test.ts (2 tests) 6ms
       ✓ tests/shell-router.test.ts (6 tests) 15ms
       ✓ tests/status-tag.test.tsx (8 tests) 51ms
      
      ⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯
      
       FAIL  tests/tasks-static.test.ts > 禁用词与源码规则 > 本片新图标只用 Svg 包装与现成图标；SearchIcon 不重写
      Error: ENOENT: no such file or directory, open 'C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t011-desktop-tasks-a003-verify-lhp5vsd0\desktop\docs\ui-design\pages\05-attempt-详情-Themis-Tally.html'
       ❯ read tests/tasks-static.test.ts:7:31
            5| 
            6| const root = resolve(process.cwd(), '..');
            7| const read = (rel: string) => readFileSync(resolve(root, rel), 'utf8');
             |                               ^
            8| const web = process.cwd();
            9| const readWeb = (rel: string) => readFileSync(resolve(web, rel), 'utf8…
       ❯ tests/tasks-static.test.ts:102:20
      
      ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
      
       Test Files  1 failed | 73 passed (74)
            Tests  1 failed | 688 passed (689)
         Start at  01:03:38
         Duration  10.00s (transform 5.05s, setup 0ms, collect 29.81s, tests 24.26s, environment 60.25s, prepare 9.05s)
      
    assert 1 == 0
     +  where 1 = <test_gate_t010_baseline.Step object at 0x00000000046B99D0>.code
    9 failed, 406 passed in 410.51s (0:06:50)
