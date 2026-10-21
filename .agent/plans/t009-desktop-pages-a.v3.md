# TASK: t009-desktop-pages-a

## Identity
- plan_version: 3
- repository: ThemisTally
- base_sha: b8df7382cd42bcbb1a6a932a9af1769578bf9ee0
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: bb/step-5-preview · thinking high

## Goal
把总览、角色与模型、CLI 运行时三页的占位换成真页面。
新增 src/pages/readonly1/ 下的只读视图与纯函数、两个通用组件（RelativeTime、ActorTag）、四个图标与执行端测试；三页只调 T006 api.ts 的读函数，写入口一律用 T006 的 DisabledAction 禁用。不改依赖、不改令牌、不接本机服务。

## Non-goals
- 任务页、attempt 详情页、凭据、日志与用量、插件、历史与审计、设置页。
- 写操作流程（7.11）；长作业执行（扫描 PATH、探测、列模型、就绪检查、按记录核验，7.17、8.4）。
- 接本机服务与 SSE；8.1 的自动刷新；相对时间每秒更新。
- 七端区块（站主 Q1）；7.22 就绪卡（留给接作业那一片）。
- 工具链升级、新依赖。

## Repository facts
- 入口：desktop/web/src/App.tsx 用 useHashRoute 渲染 routes.ts 的 9 个 Tab；三页页面文件 desktop/web/src/pages/{Overview,Roles,Runtimes}Page.tsx 现为占位，用 shell/PageFrame.tsx。
- router.ts：导出 useHashRoute（返回 {route,navigate}）、parseHash（返回 {tabId,pageId,segments,query}）、mockOfQuery；navigate(path) 只保留整段 prev.query 作 ?query，path 自带 ? 会拼出双 ?，不能叠加 group/tab；页面组件拿不到同步 navigate。需 T2 加法改动。
- attemptGroups.ts：只导出 countByGroup(rows)→{running,needJudge}（RUNNING/NEED_JUDGE 私有，needJudge 合并待验收与要你决定）；未导出分组 ID 与状态到分组的函数。需 T3 加法改动。
- PageFrame.tsx：已提供 title/description/actions?/refreshLabel?/load/isEmpty?/empty?/children(data)；根 className=「tt-pad tt-page」、带 data-page-state；actions 在刷新钮之前渲染；空态只渲染 EmptyState。
- App.tsx：<main> 已带 tt-content（容器查询）；tt-pad 由 PageFrame 根提供，窄内容区容器查询已生效。
- api.ts：13 个读函数返回 Envelope<T>；类型由 typeof 各 mock JSON 推出。status 行含 attempt/task_id/plan_version/state/wall_seconds/checks/live{tool_calls,elapsed_seconds,deltas_since_last_tool,long_idle}；history.entries 含 number/at/action/target/actor/external_changes；meta 含 repo_name/kit_version；roles 含 active_preset 与 roles[]（role/explicit/binding{mode,host,profile}/differs_from_preset/profile/runtime/adapter/provider/model/thinking/connected/effort_effective，仅 execution 行有后段字段，TS 联合类型需本地收窄）；profiles 含 id/runtime/provider/model/options.thinking/credential_env；presets 含 active_preset 与 presets[]（name/description/roles/active）；preset-diff 含 a/b/roles[]（role/a/b/same）；runtimes 含 id/adapter/source/command/notes。另导出同步版 getMetaNow。
- mock/scenario.ts：currentMock 读 ?mock=（data/offline/loading/error/empty）；empty 只清 status/runtimes/secrets/plugins/history；getMeta 不受影响。mock/shell.ts 的 shellConnectionState 供断线判断。
- T007 组件：index.ts 已导出 EffortPair（requested/effective，根 span.tt-effort 带 data-state）、NextStep（children/title?/command?+onCopy?）、Table（className 加滚动容器、rowHeight 40/44/52、aria-label 必填、列 numeric/mono）、SegmentedControl（value/onChange、仅文字标签）、Tag、StatusTag、Button、EmptyState、Tooltip。
- 图标：icons/index.tsx 已有 LoaderCircle/Scale/CircleArrowUp/GitMerge/CircleCheck/TriangleAlert/ChevronRight/Check/CircleX/ListChecks/Info/Lock/Copy/EyeOff 等；缺 Plus/Search/Play/ArrowRight。
- 令牌：tokens.css 含 --tt-display、--tt-text-caption-strong、--tt-text-sm-medium、--tt-accent、--tt-accent-text、--tt-on-accent、--tt-diff-add/--tt-diff-del、八种色调、--tt-radius-lg/full、--tt-space-* 等，本片不缺令牌。
- 既有测试：tests/shell-app.test.tsx 第 32–37 行「总览占位显示夹具数据与条数」断言 body 含「夹具数据已读到：getStatus，7 条」；Q2 只改这一条。
- 工具链：Node 24.19.0；React 18.3.1、TS 5.6.3、Vite 5.4.11、Vitest 2.1.8、@testing-library/react 16.1.0、jsdom 25.0.1（无 navigator.clipboard）；vite.config.ts 的 test.include 含 src/tests/gate-probe；tsconfig 只含 src 与 vite.config.ts。
- 基线门禁：tests/test_gate_t001..t008_baseline.py 都在，基线应通过；tests/test_gate_t009_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在。
- 与规划报告不符（供协调人转站主）：(1) 任务标识不一致，内核要求 # TASK: t009-desktop-pages-a，任务书正文写 t009-desktop-readonly-1.v1.md；本合同 header 按内核写 t009-desktop-pages-a。(2) T4 已满足（main 带 tt-content，tt-pad 在 PageFrame），不改 App.tsx。(3) T5 已满足（PageFrame 有 actions，空态附加内容本片不需要），不改 PageFrame；actions 在刷新钮之前属 H1 视觉项。(4) T6 已满足（api.ts 类型由 mock JSON 推出，roles 联合类型本地收窄），不改 api.ts。(5) T2/T3 仍需改 T006，见 Behavior contract 第 1、2 条。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/components/index.ts
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/shell/router.ts
  - desktop/web/src/shell/attemptGroups.ts
  - desktop/web/tests/shell-app.test.tsx
  - desktop/web/src/components/ActorTag.tsx
  - desktop/web/src/components/RelativeTime.tsx
  - desktop/web/src/pages/readonly1/common-CopyNote.tsx
  - desktop/web/src/pages/readonly1/common-Section.tsx
  - desktop/web/src/pages/readonly1/common-copyText.ts
  - desktop/web/src/pages/readonly1/common-links.ts
  - desktop/web/src/pages/readonly1/common-section.css
  - desktop/web/src/pages/readonly1/overview-AttemptList.tsx
  - desktop/web/src/pages/readonly1/overview-ConfigChanges.tsx
  - desktop/web/src/pages/readonly1/overview-MetricCard.tsx
  - desktop/web/src/pages/readonly1/overview-OverviewView.tsx
  - desktop/web/src/pages/readonly1/overview-logic.ts
  - desktop/web/src/pages/readonly1/overview-styles.css
  - desktop/web/src/pages/readonly1/roles-PresetBar.tsx
  - desktop/web/src/pages/readonly1/roles-PresetDiff.tsx
  - desktop/web/src/pages/readonly1/roles-PresetsTable.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/src/pages/readonly1/roles-RoleCard.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/pages/readonly1/roles-logic.ts
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
  - desktop/web/src/pages/readonly1/runtimes-logic.ts
  - desktop/web/src/pages/readonly1/runtimes-styles.css
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/page-common.test.tsx
  - desktop/web/tests/page-css.test.ts
  - desktop/web/tests/page-logic.test.ts
  - desktop/web/tests/page-overview.test.tsx
  - desktop/web/tests/page-roles.test.tsx
  - desktop/web/tests/page-runtimes.test.tsx
  - desktop/web/tests/page-static.test.ts
- allowed_new_files:
  - desktop/web/src/pages/readonly1/common-Section.tsx
  - desktop/web/src/pages/readonly1/common-section.css
  - desktop/web/src/pages/readonly1/common-links.ts
  - desktop/web/src/pages/readonly1/common-copyText.ts
  - desktop/web/src/pages/readonly1/common-CopyNote.tsx
  - desktop/web/src/pages/readonly1/overview-OverviewView.tsx
  - desktop/web/src/pages/readonly1/overview-MetricCard.tsx
  - desktop/web/src/pages/readonly1/overview-AttemptList.tsx
  - desktop/web/src/pages/readonly1/overview-ConfigChanges.tsx
  - desktop/web/src/pages/readonly1/overview-logic.ts
  - desktop/web/src/pages/readonly1/overview-styles.css
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/pages/readonly1/roles-RoleCard.tsx
  - desktop/web/src/pages/readonly1/roles-PresetBar.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/src/pages/readonly1/roles-PresetsTable.tsx
  - desktop/web/src/pages/readonly1/roles-PresetDiff.tsx
  - desktop/web/src/pages/readonly1/roles-logic.ts
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
  - desktop/web/src/pages/readonly1/runtimes-logic.ts
  - desktop/web/src/pages/readonly1/runtimes-styles.css
  - desktop/web/src/components/RelativeTime.tsx
  - desktop/web/src/components/ActorTag.tsx
  - desktop/web/tests/page-logic.test.ts
  - desktop/web/tests/page-common.test.tsx
  - desktop/web/tests/page-overview.test.tsx
  - desktop/web/tests/page-roles.test.tsx
  - desktop/web/tests/page-runtimes.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/page-css.test.ts
  - desktop/web/tests/page-static.test.ts
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
  - desktop/web/src/mock/**
  - desktop/web/src/icons/frame.tsx
  - desktop/web/src/shell/DisabledAction.css
  - desktop/web/src/shell/DisabledAction.tsx
  - desktop/web/src/shell/Logo.tsx
  - desktop/web/src/shell/PageFrame.css
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/src/shell/ShellMenu.css
  - desktop/web/src/shell/ShellMenu.tsx
  - desktop/web/src/shell/ShellStatusContext.tsx
  - desktop/web/src/shell/TabBar.css
  - desktop/web/src/shell/TabBar.tsx
  - desktop/web/src/shell/TitleBar.css
  - desktop/web/src/shell/TitleBar.tsx
  - desktop/web/src/shell/relativeTime.ts
  - desktop/web/src/pages/HistoryPage.tsx
  - desktop/web/src/pages/LogsPage.tsx
  - desktop/web/src/pages/PluginsPage.tsx
  - desktop/web/src/pages/SecretsPage.tsx
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/src/pages/TasksPage.tsx
  - desktop/web/src/components/Banner.*
  - desktop/web/src/components/Breadcrumb.*
  - desktop/web/src/components/Button.*
  - desktop/web/src/components/Card.*
  - desktop/web/src/components/Checkbox.*
  - desktop/web/src/components/CommandLine.*
  - desktop/web/src/components/ConnectionPill.*
  - desktop/web/src/components/Dialog.*
  - desktop/web/src/components/DiffView.*
  - desktop/web/src/components/Drawer.*
  - desktop/web/src/components/EffortPair.*
  - desktop/web/src/components/EmptyState.*
  - desktop/web/src/components/IconButton.*
  - desktop/web/src/components/KeyValueList.*
  - desktop/web/src/components/LogFollow.*
  - desktop/web/src/components/MaskedValue.*
  - desktop/web/src/components/Menu.*
  - desktop/web/src/components/NextStep.*
  - desktop/web/src/components/SafeMarkdown.*
  - desktop/web/src/components/SegmentedControl.*
  - desktop/web/src/components/Select.*
  - desktop/web/src/components/Skeleton.*
  - desktop/web/src/components/StatusTag.*
  - desktop/web/src/components/Switch.*
  - desktop/web/src/components/Table.*
  - desktop/web/src/components/Tabs.*
  - desktop/web/src/components/Tag.*
  - desktop/web/src/components/TextField.*
  - desktop/web/src/components/TextViewer.*
  - desktop/web/src/components/Toast.*
  - desktop/web/src/components/Tooltip.*
  - desktop/web/src/components/overlay/**
  - desktop/web/src/components/field/**
  - desktop/web/src/components/evidence/**
  - desktop/web/src/components/diff/**
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
  - tests/test_gate_t009_*.py
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
- 结构：区块 section + aria-labelledby 指 h2；角色卡 article + aria-labelledby 指 h3；行列表 ul/li；id 用 useId。各页视图根加 data-page=overview/roles/runtimes。
- 本片新目录只用 src/pages/readonly1/，文件名前缀 overview-/roles-/runtimes-/common-；纯函数 <前缀>-logic.ts、样式 <前缀>-styles.css。
- 尺寸字面量同一行注释出处；除 0 与 1px 外的 px 带注释。

### 1. 对 T006 的加法改动（T2、T3）
- router.ts（T2）：扩展 navigate，使 path 可自带 ?query；合并当前 query 参数（保留 mock 与其他参数，path 的 query 覆盖同名），结果 #<pathname>?<merged>；path 无 query 时行为与现状完全相同（签名不变）。新增导出 useAppNavigate()：返回稳定回调，委托当前挂载路由的 navigate（effect 注册），供页面组件（不接 props）同步换路由。useHashRoute/parseHash 行为与签名不变。查询参数交给页面的方式：页面用已导出的 parseHash(window.location.hash) 读 segments 与 query；本片三页不读查询参数（任务页那一片读 group/tab）。
- attemptGroups.ts（T3）：新增 export type AttemptGroup = running|review|decide|integrate|ended；export const ATTEMPT_GROUPS: readonly AttemptGroup[]；export function groupOfState(state: string): AttemptGroup | null（映射：running=PREPARING/RUNNING/COLLECTING；review=NEEDS_REVIEW/TIMEOUT/CANCELLED/INFRA_FAILURE；decide=ESCALATE/BLOCKED；integrate=PASS/ACCEPTED_WITH_EXCEPTION；ended=INTEGRATED/REVISE/ABANDONED/SUPERSEDED/PREPARE_FAILED；其他 null）。countByGroup/StatusCounts 行为与签名不变。

### 2. 页面结构与组合读取
- 页面文件只取数并用 PageFrame；视图组件（readonly1）只收数据与回调，不调 api；测试大多直接渲染视图注入数据。
- 总览 load：并行 getStatus 与 getHistory；getStatus 失败返回它的信封；成功 data={status, history(整个信封)}；isEmpty=(d)=>d.status.length===0；description 用 getMetaNow()+getMeta()（仓库名 · kit 版本）。
- 角色 load：并行 getRoles/getProfiles/getPresets；任一失败按 roles→profiles→presets 顺序返回第一个失败信封；成功 data={roles,profiles,presets}（各 data）；不传 isEmpty。
- 运行时 load：getRuntimes；isEmpty=(d)=>d.runtimes.length===0。
- PageFrame 的 load、isEmpty 用模块级稳定函数（不内联）。
- 页头说明：总览「仓库名 · kit 版本」；角色「四个角色各用哪个 CLI 与模型；方案可以一键切换」；运行时「每个 runtime 是一个 CLI 的一份安装；命令来源依次是环境变量（只对 pi）、本机文件、PATH」。
- 保持 T006 门禁 D10：三页各调 getStatus/getRoles/getRuntimes；h1 与 data-page-state=data；总览说明形如 demo-repo · kit 2.12.0；角色说明原文。角色页不传 isEmpty（?mock=empty 时仍 data）。

### 3. 通用组件与图标（components/、icons/index.tsx）
- RelativeTime（RelativeTime.tsx）：属性 iso、now?（`now?: number`，毫秒时间戳）、className?；渲染 time，dateTime=原文，文字为相对时间（<60s N 秒前；<60m N 分钟前；<24h N 小时前；否则 N 天前；差值 max(0,now-t) 向下取整到秒），title 为「本地时间 YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」——全角括号，本地时间是形如 `2026-10-18 10:02:11` 的数字串、前面不带「本地」二字，例：某时间戳本地为 2026-10-18 10:02:11、UTC 为 02:02:11 时，title 恰为 `2026-10-18 10:02:11（UTC 02:02:11）`；解析不了原样显示、不带 title/dateTime；不每秒更新。
- ActorTag（ActorTag.tsx）：属性 `actor: string`（必填，要显示的 actor 原文）与可选 `className?: string`；用 Tag，mono；色调 user-ui=brand、user=neutral、agent:<role>=info、undeclared=warning、其他=neutral。
- index.ts 末尾追加 RelativeTime/RelativeTimeProps/ActorTag/ActorTagProps 导出；不出现 overlay。
- icons/index.tsx 末尾追加 4 个图标：PlusIcon（path M5 12h14、M12 5v14）、SearchIcon（circle cx 11 cy 11 r 8 加 path m21 21-4.3-4.3）、PlayIcon（polygon points 6 3 20 12 6 21 6 3）、ArrowRightIcon（path M5 12h14、m12 5 7 7-7 7）；沿用 Svg 包装；fill/stroke 只用 none 与 currentColor；开工先查重，同名只留一份。

### 4. 总览（overview-*，照报告 §5.1）
- 视图 OverviewView，根 data-page=overview。
- 指标卡四张：依次 运行中/待验收/要你决定/待集成，data-metric=running/review/decide/integrate；整张是 a 链接，href=#/tasks?group=<分组ID>（分组ID 取 T3 的 AttemptGroup 名），点击规则见第 7 条；计数按 groupOfState 逐行统计（不在 3.4 里的状态不计不显示）；夹具得 1/2/1/1；0 也显示 0；色调条 3px（运行中 --tt-tone-info-fg、待验收 --tt-accent、要你决定 --tt-tone-escalate-fg、待集成 --tt-tone-brand-fg），图标同色，数字 --tt-display、tt-num。
- 区块顺序：指标卡、需要你判断、运行中、待集成、最近的配置变更；前三块无行时整块不渲染；配置变更总渲染。
- 需要你判断：待验收+要你决定两组的行，保持 getStatus 顺序；h2 后金色计数胶囊（aria-label N 项），左边框 3px --tt-accent；底部 NextStep（不带 title）：有待验收行时文字「验收在规划端会话里进行：」命令 /review-pi .agent/runs/<attempt>（取待验收组显示顺序第一行的 attempt 原文）；只有要你决定行时文字「需要你做决定，见摘要里的阻塞点。」不带命令；复制结果见第 6 条。
- 运行中：每行已用 <live.elapsed_seconds>（时长格式化）与工具调用 N 次（live.tool_calls）；live.long_idle 真时名称下加 warning Tag「长时间没有工具调用（N 个增量）」（TriangleAlert 12，N=deltas_since_last_tool，tt-num，无 N 只写「长时间没有工具调用」）；行带 data-long-idle；链接 [跟随事件] href=#/tasks/<task>/<attempt段>?tab=events。
- 待集成：行同需要你判断（[查看证据] href=#/tasks/<task>/<attempt段>）；底部 NextStep 文字「集成在规划端会话里进行：」命令 `/review-pi .agent/runs/<attempt>`（取待集成组显示顺序第一行的 attempt 原文）。
- attempt 行（AttemptList）：四列 状态标签(StatusTag md)/名称/信息/链接；名称=<task_id>.v<plan_version> · <attempt段>（plan_version 缺失只写 <task_id> · <attempt段>；attempt段=attempt 字段最后一个斜杠之后），等宽省略；信息 --tt-text-sm/--tt-text-2（需要你判断与待集成写用时与「检查 8/8」用 · 连，都没有留空——checks 为 `-`、空串或 null 时视为没有检查，不写「检查 …」；运行中写已用与工具调用）；[查看证据]/[跟随事件] 为 a 带 ChevronRight 14。
- 时长：秒向下取整；<60 秒 N 秒；<1 小时 M 分 S 秒；否则 H 小时 M 分；非数或负数不显示。夹具：1719.4→28 分 39 秒、1800→30 分 0 秒、1146→19 分 6 秒、640.2→10 分 40 秒。
- 最近的配置变更（ConfigChanges）：h2「最近的配置变更」右侧链接「查看全部历史」指 #/history（该链接在区块头部，与 history 是否出错无关、始终渲染）；history.ok 真时 entries 按 number 倒序取前 5，每行 编号（井号加 number，等宽 tt-num --tt-text-2）/RelativeTime（--tt-text-3）/动作（等宽，title 为 10.4 中文说明，无对应不带 title）/对象（等宽省略）/右侧 external_changes>0 时 warning Tag「检测到外部改动」（TriangleAlert 12）加 ActorTag；entries 空显示「还没有配置历史」；history.ok 假显示「没能读到配置历史：命令 <command 空格连> 返回退出码 N。」加 messages（pre 纯文本）。

### 5. 角色与模型（roles-*，照报告 §5.2）
- 视图 RolesView，根 data-page=roles；页头 actions：[保存当前为方案…]、[新建 profile]（DisabledAction）。
- 当前方案（PresetBar）：SegmentedControl 选项为方案名，值本地选中（初值 active_preset，改选只改本地）；说明：选中=当前时「当前：<active> · N 个角色」（N=该方案 roles 长度），选了别的「已选 <name> · 切换在第二阶段接入」；[切换…] DisabledAction primary md 始终禁用；无方案时只显示「还没有方案：把当前的角色绑定存成方案，之后就能一键切换」，不渲染分段与 [切换…]，方案表不渲染。
- 角色卡（RoleCard，两列 grid，带 data-role=角色码）：角色名 planning_review=规划审核端、contract=合同端、execution=执行端、scheduler_agent=调度代理，其他原样；模式名 headless=无头、interactive_host=交互式宿主、manual=手工、disabled=关闭，其他原样；标签：模式(neutral)、explicit 假「默认」(neutral)、differs_from_preset 真「与方案 <active_preset> 不一致」(attention)、无头时 connected 真「已接通」(success,CircleCheck 12) 假「本轮未接通」(warning,TriangleAlert 12)；键值(dl)：无头 profile(role.profile 否则 binding.profile)/runtime(<runtime>（<adapter>）)/模型(<provider>/<model>)/思考档位；交互式宿主 宿主(binding.host)/思考档位；手工/关闭/未知 只思考档位；思考档位一律用 EffortPair（无头 requested=role.thinking effective=role.effort_effective；其他 requested=null 显示「—」）；说明：交互式宿主「模型由宿主决定，Themis 不切换。」手工「规划端亲自写合同」关闭「本轮没有实现」无头无说明；底部 [更改…] DisabledAction secondary sm。
- profile 表（ProfilesTable）：h2「profile」说明「一个 CLI、一个模型与选项的组合」；Table rowHeight 40 aria-label「profile」；列 ID(等宽)/runtime(等宽)/模型(provider/model 等宽)/thinking(options.thinking 等宽，缺失「缺省」--tt-text-3)/凭据变量(每变量一个 mono neutral Tag，空「—」)/被引用(当前无头且 profile=该行 ID 的角色名用、连，无「—」)/操作([编辑][删除] DisabledAction ghost sm)；profiles 空显示「还没有 profile」。
- 方案表（PresetsTable）：h2「方案」说明「一组角色绑定，可以一键切换」；列 名称(等宽)/说明/包含的角色(「N 个角色」，title 中文角色名、连)/当前(active 真 brand Tag「当前」带 Check 12，否则「—」)/操作（当前行显示「当前方案不能删」；其余行 [使用][删除…] DisabledAction ghost sm，[查看差异] 可用）。
- 差异面板（PresetDiff）：[查看差异] 点击切换展开/收起，同时只开一个，按钮带 aria-expanded/aria-controls；展开时调 diffPresets(active,该行方案名)；面板在方案表下方；头「<active> 与 <name> 的差异 · 」后接等宽 config preset diff <active> <name>；读取中「正在读取…」；出错「没能读到差异：命令 … 返回退出码 N。」加 messages(pre 纯文本)；有数据：same 假角色显示 角色名、− <a 绑定>、→、+ <b 绑定>（减号 U+2212），same 真角色显示「相同」，角色总数多于差异行数时末行「其余 M 个角色 相同」；绑定文字 无头 · <profile>、交互式宿主 · <host>、手工、关闭、未知原样、缺失「—」；只认最后一次请求结果（过期回应丢弃）。

### 6. CLI 运行时（runtimes-*，照报告 §5.3）
- 视图 RuntimesView，根 data-page=runtimes；页头 actions：[扫描 PATH]（SearchIcon）、[手动登记…]（PlusIcon，primary）（均 DisabledAction）。
- 已登记：h2「已登记」；Table rowHeight 40 aria-label「已登记的 runtime」；列 ID(等宽)/适配器/能担任/命令来源/命令/版本/操作；能担任 pi=执行端、合同端；claude-code、codex=交互式宿主；opencode=未接通(--tt-text-3)；其他「—」；命令来源 env=环境变量、local=本机文件、path=PATH(neutral)，missing=找不到(danger,CircleX 12)，其他原样 neutral；notes 非空用换行连放进标签 title；命令 null「—」，否则空格连，按码点超 40 字符显示前 22、「 … 」、后 15，title 全文；版本一律「—」（Q3）；操作全部禁用：[探测](source 非 missing 才有)、[模型](adapter=pi 且 source 非 missing 才有)、[删除…](总有)；来源标签带 data-source。
- 就绪检查区（C4）：h2「就绪检查」加 [运行就绪检查]（PlayIcon secondary 禁用）；下方虚线空框「还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据；运行入口在第二阶段接入。」；不放按版本核验的下拉与 [核验]。
- 空态：runtimes 空数组时「还没有登记的 runtime」说明「在命令行里用 config runtime scan --add 登记；界面上的登记入口在第二阶段接入」。

### 7. 链接、复制与写入口白名单
- 点击：无修饰键左键先 preventDefault 再用 useAppNavigate 同步换路由（地址保留 mock）；带 metaKey/ctrlKey/shiftKey/altKey 或非左键走默认行为。href 与导航路径都经 encodeURIComponent，当前 mock 保留。
- 复制：common-copyText.ts 的 copyText(text, clipboard?)：clipboard 缺省 globalThis.navigator?.clipboard；无 writeText 返回 unavailable；成功 copied；抛错 failed。NextStep 的 onCopy 调它，结果显示一行（--tt-text-caption/--tt-text-3，无 role）：「已复制」「复制失败」「这个环境没有剪贴板接口」；不弹轻提示。
- 写入口全部 DisabledAction（reason 缺省「第二阶段接入」）；页面根里可用的按钮只在白名单：刷新（PageFrame 的）、分段选择段、[查看差异]、NextStep 里的复制命令；可用链接：指标卡、[查看证据]、[跟随事件]、[查看全部历史]。夹具下写入口个数：角色页 13、运行时页 9（过渡）。

### 8. 样式关键值（照报告 §5.4；尺寸字面量同行注释出处）
- 指标卡网格四列 minmax(0,1fr) 间距 --tt-space-4，带 tt-grid-4；卡 surface-1、1px --tt-border、--tt-radius-lg、overflow hidden、无下划线，内边距 --tt-space-3 --tt-space-4 --tt-space-3 --tt-space-5，悬停 --tt-surface-2，色调条宽 3px。
- 区块卡 surface-1、1px --tt-border、--tt-radius-lg；头部内边距 --tt-space-3 --tt-space-4；h2 --tt-title-sm；说明 --tt-text-caption/--tt-text-3；右侧链接 --tt-text-sm/--tt-link 无下划线。
- 需要你判断左边框 3px solid --tt-accent；计数胶囊 最小宽 20、高 18、--tt-radius-full、--tt-accent 底、--tt-on-accent 字、--tt-text-caption-strong。
- attempt 行四列 104px minmax(0,1fr) auto auto，间距 --tt-space-3，最小高 44，左右 --tt-space-4，上边框 1px --tt-border，悬停 --tt-surface-3；行内链接高 28、左右 --tt-space-2、--tt-radius-md、--tt-text-sm-medium、无下划线。
- 配置变更行五列 48px 92px 120px minmax(0,1fr) auto，高 36，间距 --tt-space-3，左右 --tt-space-4；下一步与复制结果外边距 --tt-space-3 --tt-space-4 --tt-space-4。
- 当前方案区块 flex 可换行、间距 --tt-space-3 --tt-space-4、内边距 --tt-space-3 --tt-space-4；角色卡网格两列 minmax(0,1fr) 间距 --tt-space-4 带 tt-grid-2，卡内边距 --tt-space-4、纵向间距 --tt-space-2，键值两列 64px minmax(0,1fr)。
- 表格：className 加在 Table 滚动容器（复合选择器盖过 .tt-table-wrap：无边框无圆角，上边框 1px --tt-border）；最小宽 profile 860、方案 760、运行时 900；最后一列靠右；命令单元格最大宽 280、等宽单行超出隐藏。
- 差异面板内边距 --tt-space-3、--tt-radius-md、--tt-surface-2、1px --tt-border；四列 96px minmax(0,1fr) 24px minmax(0,1fr)；值块 --tt-diff-del/--tt-diff-add 底、内边距 --tt-space-0_5 --tt-space-1、--tt-radius-sm、--tt-mono-sm。
- 就绪检查空框内边距 --tt-space-5、居中、1px dashed --tt-border-strong、--tt-radius-md、--tt-text-sm/--tt-text-3。
- 层级/圆角/阴影/字体只用令牌；除 0 与 1px 外的 px 字面量同一行带出处注释。

### 9. 测试（desktop/web/tests/page-*）
- 沿用 T005–T007 写法：render/act/fireEvent/cleanup 从 @testing-library/react 导入，不加 user-event；样式断言读 CSS 文本、用 process.cwd() 定位；按 id 用 getElementById。
- 涉及时间用 vi.useFakeTimers() 与 vi.setSystemTime()；本地时间期望值用同一个 Date 现算，不写死时区。App 级测试先设 location.hash，afterEach 设回空串；要读到夹具先 await act(async()=>{})；要看骨架屏推进 300ms。
- 文件：page-logic.test.ts（纯函数：分组计数、时长、行文字、下一步命令、配置变更排序截取、绑定文字、被引用、来源标签、能担任、中间截断、操作出现规则、保留 mock 的地址拼接、copyText 三态）；page-common.test.tsx（RelativeTime 四档与边界 59/60 秒、59/60 分、23/24 小时、title、解析不了；ActorTag 五色；Section）；page-overview.test.tsx（注入数据：分组计数、行、long_idle 有无、空区块不渲染、下一步两种文字命令、配置变更 5 条上限倒序、外部改动标签、history 出错与为空、链接 href 与点击后地址）；page-roles.test.tsx（RoleCard 四模式四档标签；PresetBar；ProfilesTable；PresetsTable 与 PresetDiff 读取中/出错/有数据/收起/过期丢弃）；page-runtimes.test.tsx（来源五种、能担任、截断与 title、版本「—」、操作规则、就绪检查区）；page-app.test.tsx（过渡：三页 ?mock= 五态、夹具值、点指标卡后路由、写入口个数与提示、可用按钮白名单）；page-css.test.ts（§8 取值、令牌、px 注释）；page-static.test.ts（本片源码无两组禁用词、ServerIcon、role=status、内联 style、四个禁用接口；不出现 3.4 分组状态码字面量，分组只来自 attemptGroups）。
- 按 Q2 只改 tests/shell-app.test.tsx 第 32–37 行「总览占位显示夹具数据与条数」一条，改为断言真页面（如存在 [data-page=overview] 与四张 [data-metric] 卡，计数 1/2/1/1）；其余 T006 测试不改。

### 10. 过渡断言
- 只在本片成立、接本机服务那一片推翻：经 ?mock= 渲染 App 三页的五态；夹具具体值（指标 1/2/1/1、各行文字、写入口个数 13 与 9）。docstring 第一行写「接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据）」。
- 长期断言：视图组件（注入数据）、纯函数、两个通用组件、图标路径、CSS 取值、源码规则、写入口全部禁用这条规则本身。

## Steps
1. 预检（只读）：核对 Repository facts 与 §9 接口；确认 T008 已落地与图标/导出无重名；不符就停。
2. 通用组件与图标：RelativeTime、ActorTag；index.ts、icons/index.tsx 追加；测试 page-common。
3. 纯函数：overview-logic、roles-logic、runtimes-logic、common-links、common-copyText；测试 page-logic。
4. 总览视图：Section、MetricCard、AttemptList、ConfigChanges、OverviewView、CopyNote 与 CSS；测试 page-overview。
5. 总览页接线：OverviewPage；page-app 总览部分（过渡）。
6. 角色卡与当前方案：RoleCard、PresetBar；page-roles 部分。
7. profile 表、方案表与差异面板：ProfilesTable、PresetsTable、PresetDiff；page-roles 其余。
8. 角色页接线：RolesPage；page-app 角色部分。
9. 运行时视图与接线：RuntimesView、runtimes-styles.css、RuntimesPage；page-runtimes 与 page-app 运行时部分。
10. 写入口与可用按钮扫描：page-app 三页扫描（过渡）+ 视图级规则（长期）。
11. 样式与源码规则：page-css、page-static。
12. 执行端测试与自检：desktop/web 下 npm ci（要网络）、npm run build、npm test、npm run check:contract；仓库根点名跑 V01 与 V03（V02 超时 12600s 超过单轮上限 7200s，由验收端运行，执行端不自跑）；确认 git status 没有新的未忽略文件。

## Setup
无。npm ci 只在门禁 pytest 与第 12 步自检里跑。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t009_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py -q` · cwd：仓库根 · 超时：12600s · 期望退出码：0 · 输出须匹配 `\d+ passed`，不得出现 `failed|error`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `\d+ passed`

说明：V01 的 tests/test_gate_t009_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（基线应失败）；V02 合并 T001–T008 八份门禁回归，点名运行以让前端流水线不被 conftest 跳过；V03 是桌面端状态表回归。V02 超时 12600s 超过单轮 7200s，由验收端运行，执行端自检只跑 V01 与 V03。

## Definition of done
- D01：指标卡四张，顺序与 data-metric 正确，计数来自 groupOfState 的分组，夹具得 1/2/1/1（过渡）；色调条四色正确；整张卡是链接，点击后路由为任务页、group 为对应分组 ID、原 mock 保留，带修饰键不拦截；证据：V01、V02。
- D02：需要你判断只含待验收与要你决定两组、保持 getStatus 顺序；行名称/用时/检查/[查看证据] 地址正确；计数胶囊与 aria-label、金色左边框；下一步两种文字与命令精确到 attempt；复制三态文字；无行不渲染；证据：V01。
- D03：运行中显示已用时间与工具调用次数；long_idle 真才有 warning 标签且带增量数；[跟随事件] 地址带 tab=events；待集成下一步正确；无行不渲染；证据：V01。
- D04：最近的配置变更最多 5 条按编号倒序；相对时间与 title；动作中文 title；对象；外部改动标签；执行者色调；空与出错文字；查看全部历史链接；证据：V01。
- D05：总览五态：组合读取；status 出错时页面级出错块显示 status 命令，history 出错只在区块里显示；空态标题说明；断线数据仍在；首次加载骨架屏；证据：V01。
- D06：角色卡四张、名称与角色码正确；四种模式各自的标签、键值与说明；默认/不一致/已接通/本轮未接通出现条件；思考档位四种情形都经 EffortPair 显示；[更改…] 禁用；证据：V01。
- D07：当前方案分段选项与初值；说明两种文字；[切换…] 始终禁用且有提示；无方案时文字；证据：V01。
- D08：profile 表各列正确（thinking 缺省、凭据标签、被引用）；[编辑][删除] 禁用；空时文字；证据：V01。
- D09：方案表各列正确；当前行说明文字；[使用][删除…] 禁用；[查看差异] 可用，展开调一次 diffPresets(active,name)，读取中/出错/有数据三态，能收起，同时只开一个，过期回应丢弃；差异行绑定文字正确、减号 U+2212；证据：V01。
- D10：CLI 运行时各列正确；能担任映射；来源标签四种取值加未知值、notes 进 title；命令为空显示、截断规则、title 全文；版本「—」；操作按规则出现且都禁用；页头两个入口禁用；就绪检查区；空态；证据：V01。
- D11：三页所有写入口都禁用且悬停出 role=tooltip 文字「第二阶段接入」；页面根里可用按钮只在白名单之内；夹具下写入口个数 13 与 9（过渡）；证据：V01。
- D12：RelativeTime 规则与 title 格式；ActorTag 色调；index.ts 只追加两组导出；4 个新图标路径等于画布对应行、已有图标与导出不变；证据：V01。
- D13：§8 的取值、令牌与 px 注释；没有内联 style；两组禁用词、ServerIcon、role=status、四个禁用接口都不出现；不另写 3.4 分组表；W4 通过；证据：V01。
- D14：回归——T001–T008 门禁、V03、npm 四步都通过；只改允许的文件；不改依赖；新测试不用 skip/only/todo；证据：V02、V03、scope、review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 src/components/** 的既有组件、src/icons/frame.tsx、src/styles/**、src/main.tsx、package.json、锁文件、门禁测试 tests/test_gate_t009_*.py）。
- 需要新增或升级依赖、写 .npmrc、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计。
- 时间分配：调查约 15 分钟、实现与补测约 65 分钟、必要检查约 30 分钟、最终报告约 10 分钟；总计不超过单轮 7200 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。

## Rework（返工第 1 轮，内核追加）

- 基线 `b8df7382cd42bcbb1a6a932a9af1769578bf9ee0` 是 attempt-001 的候选（内核把它搬到当前基准测试上建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 门禁端在上一轮之后改过基准测试（热修补）：工作目录里的基准测试是新的。上一轮对着旧测试的检查结果不作数，先把合同的检查跑一遍，以新的基准测试为准。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

B1【执行端】overview-styles.css、roles-styles.css、runtimes-styles.css 没有被任何模块 import（desktop/web 里只有 tests/page-css.test.ts:9 按文本读它们；src/pages/readonly1/ 下唯一的样式表引入是 common-Section.tsx:3 的 common-section.css；main.tsx、App.tsx、vite.config.ts、index.html 都没引）。Vite 只打包被 import 的 CSS，真实构建里三页缺页面样式：色调条、计数胶囊、金色左边框、行网格、角色卡、差异面板、表格最小宽、就绪检查虚线框全不生效。要求：在 overview-OverviewView.tsx、roles-RolesView.tsx、runtimes-RuntimesView.tsx 各自引入对应样式表，import 写在组件 import 之后，使其晚于 common-section.css 载入（.common-section 的 border 简写与 .ov-judge 的 border-left 同特异性，顺序反了金色左边框丢失），或把选择器抬成 .common-section.ov-judge；在 tests/page-css.test.ts 补一条『三份页面样式表各被 src 下某个 .ts/.tsx 模块 import』的断言；npm run build 后 dist/assets/*.css 里应能搜到 .ov-metric、.rl-card、.rt-ready；CSS 取值、px 注释、令牌规则保持原样。
B2【门禁端，热修补】tests/test_gate_t009_baseline.py 的 css_value_problems、test_d13_css_values_match_section_8、test_d13_css_tokens_px_comments_and_w4、test_d01_tone_stripe_colors 都用 css_text() 读四份 CSS 的文本，不证明样式表被应用，候选没接线时仍全绿，D01 色调条与 D13 取值因此是空心断言。要求：加一条留在仓库里的回归断言，证明四份 CSS 都进了应用——静态（src 下有 .ts/.tsx 以 import 引入每一份）和/或流水线（npm run build 后 dist/assets/*.css 含每份 CSS 里一个独有的类选择器，从文件里解析，不写死类名）；自检里加『去掉某条 import』的变异，必须报问题；只加不放宽既有断言。这条在当前候选上应红，B1 完成后应绿。
B3【战后门禁】tests/test_gate_t009_whitebox.py 与变异清单同样漏了接线：157 个变异全 caught，但每条变异的 old 文本里都没有 import 或 .css，白盒里也没有『样式表被引入』的断言，所以『候选缺陷：无』不成立。要求：白盒加同一断言；变异清单加『删掉 overview/roles/runtimes 任一份样式表的 import』三条，在返工后的候选上重跑，全部 caught。
