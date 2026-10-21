# TASK: t012-desktop-shellpages

## Identity
- plan_version: 4
- repository: ThemisTally
- base_sha: 3e488fb7c2e3b5ecae9a7ef5ea1421ac5c5bb704
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: bb/step-5-preview · thinking high

## Goal
交付 T012 第 11 片（桌面端前端外壳页：首次启动、设置、服务状态与恢复）：在 desktop/web/ 新增 src/shellpages/ 下的 themisShell 接口与内存桩、外壳窗口外框、首次启动视图、服务状态视图、设置的五组视图、两个对话框、主题 context、图标与夹具；把 src/App.tsx 按 §2.3 一处改动（根上外壳窗口分支 #/first-run 与 #/service-status 整窗渲染、主题状态上提经 ThemePrefProvider 交给设置页、原函数体改名 ServiceApp），把 src/pages/SettingsPage.tsx 换成用 PageFrame 的外壳设置页；新增 src/mock/shellpages-scenarios.ts 与 8 个 tests/shellpages-* 测试。不改依赖、不改 router.ts、不接本机服务、不新增 .json 夹具。

## Non-goals
- 真实 Electron 外壳、preload 与 IPC；window.themisShell 的全局声明与读取；window.themisHost（含 reauth、openSettings）。
- 接本机服务、SSE；写操作流程（7.11）；6.11 列的那几页。
- 首启画布的第 5 步「工人」不做（站主 C3）：任务书与 6.1 都定四步；工人是否就绪要从服务取，外壳页不读服务。
- 真正切换到另一个窗口：8.9 没有这个函数，站主定为显示禁用按钮（Q2-A），不扩充接口。
- 断线画布的「会话已失效」（401）：属于 themisHost.reauth，不归本片。
- 密度对表格行高的实际作用：本片只保存设置，T005 Table 没有 32 这一档。
- 设置变化后外壳重启服务：由真实外壳做，桩不模拟。启动时按外壳保存的主题初始化：留给接真实外壳那一片。
- 工具链升级；新依赖；不改 README、package.json、锁文件、vite.config.ts、tsconfig.json、index.html、scripts/**、public/**、fonts/**、THIRD_PARTY_NOTICES.md；不改 api.ts、main.tsx、src/styles/**、src/shell/**（含 router.ts、routes.ts）、components/index.ts、icons/index.tsx、既有组件、T009–T011 的文件。

## Repository facts
- 入口：desktop/web/src/main.tsx 挂载 src/App.tsx；routes.ts 按默认导出引入各 *Page.tsx。
- 现状（在 ce051d4 上核对，行号指该提交）：
  - src/App.tsx：:1–3 文件头注释；:4–17 import；:19 `export default function App()`；:20 `const [theme, setTheme] = useState<ThemePref>('dark')`；:21 `const { route, navigate } = useHashRoute()`；:22 `const meta = getMetaNow()`；:26–28 `useEffect(() => { applyTheme(theme) }, [theme])`；:51 getStatus；:72 `<TitleBar theme={theme} onThemeChange={setTheme} repoName={meta.repo_name} />`。:21–24、:30–87 为原函数体其余部分。
  - src/pages/SettingsPage.tsx：现为占位（`<PageFrame<MetaData> title="设置" load={getMeta}>` + 一行「夹具数据已读到：getMeta。」）。
  - src/shell/router.ts：:27–43 parseHash（未知路径归总览）；:45–53 useHashRoute（:46 初值取 location.hash，:49–53 监听 hashchange）；:55–65 navigate（先同步改状态再写地址，写地址在 setState 更新函数里）。本片不导入、不修改 router.ts。
  - src/shell/PageFrame.tsx：:24–34 props（title、description、actions、refreshLabel、load、isEmpty、empty、children）；:46 断线判断；:62–99 request；:102–106 挂载时加载一次；:127 Promise 被拒写「没有收到服务的回应」；:143 根元素 data-page-state；:160–165 断线 Banner。
  - src/shell/theme.ts：:3 ThemePref、:5–12 applyTheme（唯一写 data-theme）。src/shell/Logo.tsx：:4–25，内联 svg 18×20、role=img、aria-label「Themis Tally 标识」，填色类 tt-logo__mark/tt-logo__tally（规则在 TitleBar.css :16–17）。src/shell/DisabledAction.tsx：:7–31，props label、reason（缺省「第二阶段接入」）、variant、size、icon；用 Tooltip 包 disabled Button，Button 带 tt-disabled-action（pointer-events:none）。src/shell/relativeTime.ts：:4–18，relativeTime(from, now)、clockTime(at)（:14–18）。
  - src/api.ts：:82–96 用 Promise.resolve/reject 兑现、loading 时永不兑现（`pending()`），不用计时器；Envelope 字段 ok/exit_code/data/output/messages/command/elapsed_ms；getMetaNow() 同步取 meta。本片不导入 api.ts。
  - src/mock/shell.ts：SHELL_PID=18244、SHELL_STARTED_AT='2026-10-18 09:41:07'。src/mock/meta.json：kit_version 2.12.0。
  - src/mock/ 恰 14 份 JSON（attempt、file-events、file-executor-report、history、meta、plugins、preset-diff、presets、profiles、roles、runtimes、secrets、status、usage）与 3 份 .ts（scenario、empty、shell）。src/pages 顶层恰 9 个 *Page.tsx。src/shellpages/ 不存在。
  - 图标：icons/index.tsx 的 CircleDashedIcon :37、CircleXIcon :50、LoaderCircleIcon :58、CircleCheckIcon :82、ServerCrashIcon :119、CopyIcon :238；icons/frame.tsx 的 FolderPlusIcon :113、RefreshCwIcon :153。包装照 icons/index.tsx :7–26（tt-i、stroke currentColor、aria-hidden）。
  - 组件签名：Button {variant, size, loading, loadingText}（Button.css :14–16 sm 28/md 32/lg 36）；Tag {tone（含 brand）, mono}；Banner {tone（danger 为 role=alert）, action}；Dialog {open, onClose, title, children, footer}（Dialog.css :13 宽 560，焦点陷阱、Esc 关闭）；SegmentedControl {options:{value,label}, value, onChange, 'aria-label'}（role=radiogroup）；KeyValueList {items:{label,value,mono?}}；CommandLine {command, size:'md'|'sm', onCopy}；Table（单元格不放可聚焦元素）；Tooltip 经 DisabledAction 用到。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript 5.6.3 + Vite 5.4.11 + Vitest 2.1.8；@testing-library/react 16.1.0、@testing-library/dom 10.4.0、jsdom 25.0.1，无 user-event；vite.config.ts 的 test.include 含 src、tests、gate-probe；tsconfig.json 只含 src 与 vite.config.ts（测试不进 tsc）；锁文件 desktop/web/package-lock.json（lockfileVersion 3），npm ci 可复现。
- 基线检查：worktree HEAD = base_sha = ce051d4dba05a2f9695e085ba7feb1025f1c6119，git status 干净。ce051d4 已退役 T006 门禁里设置页的占位文字与 getMeta 断言（C1 / §8.1 的 R1）：tests/test_gate_t006_baseline.py 的 SHELL_PAGES=['settings']（:2011），D10 第一条（:2046–2048）对设置页不查加载函数，h1 与 data-page-state 照旧验。T001–T008 门禁都在，基线上应通过（V02 回归）；本片门禁 tests/test_gate_t012_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（V01 基线应失败）。

## Scope
- allowed_modified_files:
  - desktop/web/src/App.tsx
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/src/shellpages/themisShell.ts
  - desktop/web/src/shellpages/shellStub.ts
  - desktop/web/src/shellpages/shellContext.tsx
  - desktop/web/src/shellpages/shellWindowRoute.ts
  - desktop/web/src/shellpages/ShellWindow.tsx
  - desktop/web/src/shellpages/shell-window.css
  - desktop/web/src/shellpages/firstRunModel.ts
  - desktop/web/src/shellpages/FirstRunView.tsx
  - desktop/web/src/shellpages/first-run.css
  - desktop/web/src/shellpages/exitCodes.ts
  - desktop/web/src/shellpages/ServiceStatusView.tsx
  - desktop/web/src/shellpages/service-status.css
  - desktop/web/src/shellpages/SettingsView.tsx
  - desktop/web/src/shellpages/settings.css
  - desktop/web/src/shellpages/ExternalLinkDialog.tsx
  - desktop/web/src/shellpages/LicensesDialog.tsx
  - desktop/web/src/shellpages/licenses.ts
  - desktop/web/src/shellpages/themePref.tsx
  - desktop/web/src/shellpages/copy.ts
  - desktop/web/src/shellpages/format.ts
  - desktop/web/src/shellpages/icons.tsx
  - desktop/web/src/mock/shellpages-scenarios.ts
  - desktop/web/tests/shellpages-stub.test.ts
  - desktop/web/tests/shellpages-route.test.ts
  - desktop/web/tests/shellpages-first-run.test.tsx
  - desktop/web/tests/shellpages-service-status.test.tsx
  - desktop/web/tests/shellpages-settings.test.tsx
  - desktop/web/tests/shellpages-app.test.tsx
  - desktop/web/tests/shellpages-isolation.test.tsx
  - desktop/web/tests/shellpages-static.test.ts
- allowed_new_files:
  - desktop/web/src/shellpages/themisShell.ts
  - desktop/web/src/shellpages/shellStub.ts
  - desktop/web/src/shellpages/shellContext.tsx
  - desktop/web/src/shellpages/shellWindowRoute.ts
  - desktop/web/src/shellpages/ShellWindow.tsx
  - desktop/web/src/shellpages/shell-window.css
  - desktop/web/src/shellpages/firstRunModel.ts
  - desktop/web/src/shellpages/FirstRunView.tsx
  - desktop/web/src/shellpages/first-run.css
  - desktop/web/src/shellpages/exitCodes.ts
  - desktop/web/src/shellpages/ServiceStatusView.tsx
  - desktop/web/src/shellpages/service-status.css
  - desktop/web/src/shellpages/SettingsView.tsx
  - desktop/web/src/shellpages/settings.css
  - desktop/web/src/shellpages/ExternalLinkDialog.tsx
  - desktop/web/src/shellpages/LicensesDialog.tsx
  - desktop/web/src/shellpages/licenses.ts
  - desktop/web/src/shellpages/themePref.tsx
  - desktop/web/src/shellpages/copy.ts
  - desktop/web/src/shellpages/format.ts
  - desktop/web/src/shellpages/icons.tsx
  - desktop/web/src/mock/shellpages-scenarios.ts
  - desktop/web/tests/shellpages-stub.test.ts
  - desktop/web/tests/shellpages-route.test.ts
  - desktop/web/tests/shellpages-first-run.test.tsx
  - desktop/web/tests/shellpages-service-status.test.tsx
  - desktop/web/tests/shellpages-settings.test.tsx
  - desktop/web/tests/shellpages-app.test.tsx
  - desktop/web/tests/shellpages-isolation.test.tsx
  - desktop/web/tests/shellpages-static.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/src/App.css
  - desktop/web/src/main.tsx
  - desktop/web/src/vite-env.d.ts
  - desktop/web/src/api.ts
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/showcase/**
  - desktop/web/src/shell/**
  - desktop/web/src/components/**
  - desktop/web/src/icons/**
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/empty.ts
  - desktop/web/src/mock/shell.ts
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/TasksPage.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/SecretsPage.tsx
  - desktop/web/src/pages/LogsPage.tsx
  - desktop/web/src/pages/PluginsPage.tsx
  - desktop/web/src/pages/HistoryPage.tsx
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/pages/readonly2/**
  - desktop/web/src/pages/tasks/**
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
  - tests/test_gate_*.py
  - tests/test_gate_t012_*.py
  - tests/conftest.py
  - docs/**
  - .gitignore
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 公共约定
- 本合同的组件名、属性名、类名、data-* 取值、按钮文字与场景名定下后不再改；门禁按它写探针、解析 CSS。
- 文件边界：不改 router.ts、routes.ts 与 src/shell/ 其他文件；不改 components/index.ts、icons/index.tsx；不改 api.ts、main.tsx、styles/**、已有组件、package.json 与锁文件；不碰 T009–T011 的文件（src/pages/readonly1/**、readonly2/**、tasks/** 等）。
- 新文件名：src/shellpages/ 里不用 *Page.tsx、*Showcase.tsx、DiffView*、LogFollow*（G6 :3283–3285 数 src/pages 顶层恰有 9 个 *Page.tsx；陈列页按 *Showcase.tsx 自动收集）。SettingsView 写在一个文件里，不额外拆分。
- 夹具只能写成 .ts（G6 的 test_s2_fixtures_equal_ui_doc :3320–3322 要求 src/mock/*.json 恰是那 14 份），文件头标明「示意」。
- 桩的各方法不经计时器兑现：getState、pick*、saveSettings、openExternal、startService、restartService 都返回已兑现或已被拒的 Promise（Promise.resolve / Promise.reject，同 api.ts :90–96）。原因：G6 的 mountApp 写地址、渲染之后只排空 12 个微任务（settle :801–807；mountApp :832–846），设置页要在这之内到 data。
- 源码扫描（本片的 ts、tsx、css 与夹具都在范围里）：
  - 整词：fetch、XMLHttpRequest、EventSource、WebSocket。扫 src 下全部文件，注释与字符串都算（shell-no-network.test.ts；G6 :3325–3340）。
  - 子串：dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser（G6 :203–206、G7 :93、G8 :121）。
  - 不写 role 等于 status；不调 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver（G6 :315–324；扫描范围 new_source_files :3351–3360，含 App.tsx、mock/**、pages/**；shellpages/** 自愿照守）。首启画布 :341 的 role=status 改成 aria-live=polite。
  - 字符串 data-theme：G6 :3455–3474 只许 theme.ts 写，扫同一批文件；本片新行不写 data-theme。
  - W4（scripts/token-contract.mjs :38–41、:141–156；G6 :3363–3373）：井号加 3、4、6、8 位十六进制字符；颜色函数名加括号（行注释与字符串里也算）；tokens.css 里没有定义的 --tt- 名；在 css 里声明 --tt- 自定义属性。
  - G3 :659–663：.woff2 等字体扩展名、sarasa-mono-sc-、@font-face、FontFace；许可清单只写项目名与许可，不写字体文件名。G4 :371：不出现 ServerIcon，用已有的 ServerCrashIcon。
  - 不写 localStorage、sessionStorage（G6 :1482–1483）；不调 window.open、window.confirm（jsdom 没有实现）。
- 样式：令牌照用；除 0 与 1px 以外的 px 字面量，同一行写出处（画布行号、UI 文档节号或 handoff 行号）；不写内联 style；不在 css 里写 [data-theme] 选择器；每份新 css 都要被某个能从 App.tsx 或 pages/SettingsPage.tsx 经 import 走到的模块 import（worker.md :43；K20）。
- PageFrame 的 load、isEmpty 必须是稳定引用：设置页的 load 用 useCallback，依赖只有 shell；shell 实例按场景缓存，引用稳定。
- 新测试不用 skip、only、todo（G2 :1493–1502）。

### 进入方式（定法与理由）
- 地址与渲染位置：首次启动 #/first-run（第一段决定，后面的段忽略）、服务状态与恢复 #/service-status 由 App 根上的外壳窗口整窗渲染；设置 #/settings 仍是服务窗口内容区的 Tab（不变）。
- 外壳窗口由两部分组成：一条最简标题栏（Logo 18×20 与产品名，右侧留 140 给系统按钮，同 5.2 :352）；居中的卡片。没有仓库菜单、连接胶囊、主题菜单与 Tab 栏，也不装快捷键。
- 桩的场景：查询参数 shell=<场景>，与 mock 并存、两者互不解释。缺省：#/first-run 与 #/settings 为 ready，#/service-status 为 crash。外壳窗口跳往服务窗口时（[进入]、[打开设置]、重启成功）保留整个查询串；查询串里没有 shell 时补上当前场景，两边用同一个桩实例。
- 理由：6.1、6.12 要替代整个窗口（任务书目标 5）；在根上分支时服务窗口根本不挂载，App 不调 getMetaNow、getStatus，外壳窗口运行时对 api.ts 是零调用，可直接断言隔离。不改 router.ts（T009 在改；parseHash 会把 #/first-run 当作未知路径归到总览 router.ts :41–42，根上的钩子自己读 location.hash，路由表不需要认识这两个地址）。不复用 ?mock=（它的五个取值是服务数据开关，G6 的 D07 与多条 App 级断言靠它）。
- 人工对照（H1）：#/first-run?shell=checking 对首启画布缺省变体；#/first-run?shell=no-agent 对「仓库未接入」；#/first-run?shell=ready 对浅色稿（先切亮）；#/service-status?shell=exit-1 对断线画布「本机服务已停止」（退出码 1）；#/settings 对设置画布与浅色稿。

### App.tsx 的改动（站主 Q1-A 批准，只此一处）
- :1–3 文件头注释末尾加一句：#/first-run、#/service-status 由根上的外壳窗口整窗渲染，不挂服务窗口；主题偏好在根上，经 ThemePrefProvider 交给设置页。
- :17 之后加两行导入：`import { ShellWindow, useShellWindowRoute } from './shellpages/ShellWindow';`、`import { ThemePrefProvider } from './shellpages/themePref';`。
- :19 的 export default function App 改成新的根组件：原 :20 的主题状态与原 :26–28 的 applyTheme 效果移到这里；原函数体改名 ServiceApp，从参数拿 theme 与 setTheme。改后开头：

      export default function App() {
        const [theme, setTheme] = useState<ThemePref>('dark');
        const { shellWindow, navigateShell } = useShellWindowRoute();
        useEffect(() => { applyTheme(theme); }, [theme]);
        return (
          <ThemePrefProvider theme={theme} onThemeChange={setTheme}>
            {shellWindow ? (
              <ShellWindow route={shellWindow} navigate={navigateShell} />
            ) : (
              <ServiceApp theme={theme} setTheme={setTheme} />
            )}
          </ThemePrefProvider>
        );
      }

      interface ServiceAppProps { theme: ThemePref; setTheme: (pref: ThemePref) => void; }
      function ServiceApp({ theme, setTheme }: ServiceAppProps) {
        const { route, navigate } = useHashRoute();
        // 以下是原 :22–87 去掉 :26–28，原样不动

- 原函数体其余部分（:21–24、:30–87）原样留在 ServiceApp 里；只删原 :20 与原 :26–28（已移到根上）；:25、:29 两个空行可并成一个。
- :72 的 `<TitleBar theme={theme} onThemeChange={setTheme} repoName={meta.repo_name} />` 一字不改。
- 规模约增 25 行、删 4 行；git diff 会把 :19 的改写记成一删一增、可能多删一个空行，diff 上显示删 5–6 行，不算超范围。不改导出方式（仍默认导出 App）；不改 TitleBar、TabBar、内容区的 key（:61、:82）与快捷键（:31–38）的写法。
- 根组件不调 api.ts 的任何函数；getMetaNow（:22）、getStatus（:51）仍只在 ServiceApp 里。
- 新加的行里不写 data-theme、role=status、十六进制颜色与颜色函数；不写「字体 · 等距更纱黑体 SC」「Button 按钮」「Banner 提示条」「弹出轻提示」「已复制到剪贴板」与 showcase__（G6 :3892–3896）。

### themisShell 接口（src/shellpages/themisShell.ts，只有类型）
- 方法名照 8.9 :1122；十个成员（9 个方法加 on）：
  - getState(): Promise<ShellState>
  - pickRepo()、pickPython()、pickKit()、pickTranscriptDir(): Promise<PickOutcome>；结果三种：{ kind: 'cancelled' }；{ kind: 'saved', path, id?, state }（外壳校验通过并已保存）；{ kind: 'rejected', problem, path }（没保存）。problem 只有四种：pickRepo 为 not-git 或 no-agent；pickPython 为 python-unusable；pickKit 为 kit-unusable；pickTranscriptDir 不拒绝。pickRepo 只把仓库加进列表，不切换当前仓库；首次启动拿到 id 后由 startService 启动它。
  - saveSettings(patch): Promise<ShellState>；只认这些键（不接受任何路径）：theme（system/light/dark）、density（standard/compact）、removeRepo（仓库 id，不能是当前仓库）、removeTranscriptDir（目录 id）、resetPython（true）、resetKit（true）。别的键、取值不对、id 不存在：Promise 被拒，状态不变。
  - startService(repo: string): Promise<void>；repo 是列表里的 id，不在列表里就拒；同一仓库已在启动或运行中时什么也不做（幂等）。
  - restartService(): Promise<void>
  - openExternal(url): Promise<void>；只认 http 与 https，别的协议被拒。
  - on('service-state', listener): () => void；返回取消订阅的函数。
  - 8.9 没有切换窗口的函数，本片不加（Q2-A）。
- ShellState 字段：app（version、homepage）；settings（repos 每项 id/name/path/lastOpened（ISO 或 null）、currentRepo（id 或 null）、transcriptDirs 每项 id/path、theme、density）；currentRepoCheck（ok/not-git/no-agent，没有当前仓库时 null）；python（status ok/missing、source auto/custom、path、version）；kit（status ok/missing、source repo/external、path、version）；service 四种（idle；starting 带 repo；running 带 repo/pid/startedAt；exited 带 repo/exitCode/at）。会话目录按列表做。
- 本片不写 window.themisShell 的全局声明，也不读它。

### 桩与夹具（src/shellpages/shellStub.ts、shellContext.tsx、src/mock/shellpages-scenarios.ts）
- createShellStub(scenario) 返回 ThemisShell，外加 dispose()：状态只在内存；getState 与各返回值深拷贝；各方法返回已兑现或已被拒的 Promise、不经计时器；pick 按场景队列逐个给出、用完后重复最后一个；start 与 restart 在调用里同步发 starting、1500ms 后按场景发 running 或 exited（running 的 pid 18244、startedAt 取 src/mock/shell.ts 的 SHELL_STARTED_AT；exited 带退出码与时刻；1500ms 照断线画布 :439、:444 的演示时长）；只在 startService、restartService 之后才排计时器；dispose 清掉计时器与监听；openExternal 只记下网址（供测试读），不打开任何东西。
- shellContext.tsx：ThemisShellProvider；useThemisShell(windowDefault)；没有 Provider 时按 shell= 场景取缓存的桩实例（同一场景同一实例、引用稳定）；resetShellStubs() 给测试清缓存与计时器。
- src/mock/shellpages-scenarios.ts（.ts，标「示意」）11 个场景：ready（缺省：demo-repo 当前且 ok，另有 docs-site；Python 自动检测 3.13.1；kit 仓库里装好的 2.12.0；服务 idle；start 之后 running，四个 pick 各给一个 saved）；checking（start 之后停在 starting）；first-launch（没有仓库；pickRepo 依次 not-git、no-agent、saved demo-repo）；not-git；no-agent；no-python（Python missing；pickPython 先 rejected（C:/Python39/python.exe）再 saved 3.13.1）；no-kit；exit-1（start/restart 之后都是 exited 1）；exit-2（exited 2）；crash（缺省服务状态；exited 3；start/restart 之后 running）；custom（Python 手动 3.12.4、kit 外部目录、两个会话目录、密度紧凑；同 ready）。
- 夹具取值（示意）：仓库 demo-repo（C:/Projects/demo-repo，上次打开 2026-10-18 09:41:07）与 docs-site（C:/Projects/docs-site，上次打开 2026-10-15 16:20:11）；Python C:/Python313/python.exe 3.13.1；kit 2.12.0；app.version 0.0.0；homepage 用 https://github.com/mrQzs/ThemisTally（README :106 去 .git，标明示意）。夹具文字避开公共约定各项扫描；路径写进 TS 字符串时反斜杠要转义。

### 首次启动（FirstRunView.tsx、firstRunModel.ts、first-run.css）
- 结构照首启画布 :294–361：卡片（:295，宽 560 居中）里依次是头部（Logo 56×64、h1「欢迎使用 Themis Tally」、说明「选一个已经接入 Themis Tally 的 Git 仓库」）、四步列表（ol）、底栏（左说明、右 [进入]）。每步一行：编号圆 22（:306）、步名宽 72（:307）、值（等宽、单行省略）、操作、状态图标 18。
- 状态图标外包 span，role=img，aria-label 依次「通过」「未通过」「正在启动」「等待」：通过 CircleCheckIcon（--tt-tone-success-fg）；未通过 CircleXIcon（--tt-danger-text）；转圈 LoaderCircleIcon 加 tt-spin（--tt-tone-info-fg；减少动效时静止，文字仍有「…」）；等待 CircleDashedIcon（--tt-text-disabled）。
- 依次检查，规则写成纯函数 firstRunModel（输入 ShellState 与最近一次 pick 的结果）：
  - 第 1 步：最近一次 pickRepo 被拒→✗（路径取被拒那个）；saved→✓（路径取保存那个）；否则看 currentRepo 与 currentRepoCheck：没有仓库→待选择（值「还没有选择仓库」、操作 [选择…]、等待图标）；ok→✓；not-git/no-agent→✗；有仓库时操作是 [更换…]（:309）。
  - 第 2 步：第 1 步没通过→「等待上一步」并置灰（handoff :162）；否则 python ok→✓（值是版本）、missing→✗。
  - 第 3 步：同理看 kit；值写「2.12.0（仓库里装好的）」或「2.12.0（外部目录）」。
  - 第 4 步：前三步没全过→等待上一步；service starting→转圈「正在启动…」；running→✓「已启动 · pid N」；exited→✗「已退出 · 退出码 N」；idle→等待图标「等待启动」。值所在元素带 aria-live=polite。
- 自动启动：前三步都通过且（service 为 idle，或 service.repo 不是要启动的仓库）时调一次 startService(id)；用 ref 记已请求过的 id，不重复调；service 为 exited 时不自动重启。先订阅 service-state 再调 getState，之后以最近一次 service-state 为准；卸载时取消订阅。
- 错误框挂在出错那一步下面：role=alert，左缩进 34（:314），danger 色调。首句照 6.1 :446–451（加句号），次句写下一步：
  - not-git：首句「这个文件夹不是 Git 仓库。」；次句「换一个 Git 仓库再试。」；[重新选择] → pickRepo()。
  - no-agent：首句「这个仓库还没有接入 Themis Tally。」；次句「在终端里运行下面的命令接入，然后重新选择。」；CommandLine（size md）`python <ThemisTally>/scripts/kit_install.py install <仓库路径>`（6.1 :447；<ThemisTally> 原样保留）；[重新选择] → pickRepo()。
  - no-python：首句「找不到 Python 3.10 及以上。」；次句「安装后重试，或指定 python.exe。」；[指定 python.exe…] → pickPython()。
  - no-kit：首句「找不到 Themis Tally 的 kit。」；次句「在仓库里用 kit_install 装好，或指定 kit 目录。」；[指定 kit 目录…] → pickKit()。
  - 退出码 1：首句「这个仓库已经在另一个窗口里打开了。」；次句「切换到那个窗口继续。」；操作是 DisabledAction [切换到那个窗口]（禁用，reason「接入真实外壳后可用」，Q2-A）；第 1 步的 [更换…] 照常可用。
  - 退出码 2：首句「应用文件不完整，请重新安装。」；无次句；无按钮。
  - 其他退出码：首句「本机服务没能启动（退出码 N）。」；次句「重新启动；反复出现时打开设置检查 Python 与 kit。」；[重新启动] → startService(id)（K14）。
- 退出码 1 的禁用按钮：用 src/shell/DisabledAction.tsx，label「切换到那个窗口」，reason「接入真实外壳后可用」；variant、size 与同框其他按钮一致；点它不调任何桩函数。reason 的文字是过渡断言。
- 错误框补充：pickPython 被拒时多一行「所选的 python.exe 不能用：<路径>（要能运行，且是 3.10 及以上）」；pickKit 被拒时多一行「所选目录里的 kit 不能用：<路径>（要能运行 pi_dispatch.py --version）」。
- 复制：CommandLine 的 onCopy 调 copyText；结果写在命令下方一行「已复制」「复制失败」或「这个环境没有剪贴板接口」，不设 role。
- [进入]：Button primary、lg（高 36，handoff :162），文字后 ArrowRightIcon 16；四步全部通过（service running）才可用，否则 disabled；点了调 navigateShell('/overview')，保留查询串。
- 底栏左说明：全部通过「四项检查都通过了」；no-agent「接入后点“重新选择”再检查一次」；其他出错「处理好上面标出的问题，再接着检查」；其余「四步依次检查，全部通过后才能进入」。
- document.title「首次启动 · Themis Tally」。

### 服务状态与恢复（ServiceStatusView.tsx、service-status.css、exitCodes.ts）
- 结构照断线画布 :362–368，做成整页：卡片宽 440（:363）居中，内容依次：ServerCrashIcon 32（:364，--tt-danger-text，aria-hidden）；h1「本机服务已停止」（6.12 :756）；一行「退出码 N · HH:MM:SS。重启后会重新读取数据。」（:366，退出码放带 data-exit-code 的 code 元素，时刻用 clockTime；service 不是 exited 时退出码写「—」）；一段说明（退出码 1「这个仓库已经在另一个窗口里打开了。」、2「应用文件不完整，请重新安装。」、其他「本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。」；映射写在 exitCodes.ts，首启第 4 步也用它）；[重启服务]（primary、lg，RefreshCwIcon 16，点了调一次 restartService()，进入加载态「正在重启…」，收到 running → navigateShell('/overview')，收到 exited → 换新退出码/时刻/说明并恢复）；[打开设置]（secondary、lg，点了 navigateShell('/settings')，照 6.12 :756 补上）。
- 只有点了重启、之后收到 running 才跳回服务窗口；直接打开这一页按当前状态显示（K15）。不设 role=alert；document.title「本机服务已停止 · Themis Tally」。
- 退出码 1 有两种含义（架构文档 5.1 :712–715），本片照 6.1 的表写，接真实外壳那一片再定。

### 外壳窗口外框（ShellWindow.tsx、shell-window.css）
- 根元素 div.tt-app 带 data-shell-window（first-run 或 service-status）；高 100vh、纵向 flex、overflow hidden。标题栏高 40（5.2 :350）、--tt-titlebar 底、下边框 1px --tt-border、左内边距 --tt-space-3、元素间距 --tt-space-2、右内边距 140（5.2 :352）；内容是 Logo 与「Themis Tally」（--tt-title-sm）；不渲染拖动区与系统按钮。主区 flex 1、overflow-y auto、内边距 --tt-space-8 --tt-space-4（首启画布 :294）；卡片用 margin auto 居中（安全居中，卡片比窗口高时能滚到顶部）。按 route.page 渲染 FirstRunView 或 ServiceStatusView；用 useThemisShell 按场景取桩，缺省场景见进入方式。shell-window.css 由 ShellWindow.tsx 引入；ShellWindow.tsx 由 App.tsx 引入（K20 接线）。

### 设置（SettingsPage.tsx、SettingsView.tsx、settings.css）
- SettingsPage：用 PageFrame，title「设置」、description「设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置」；load = useCallback(() => 把 shell.getState() 包成 ok 信封, [shell])（信封类型从 PageFrameProps 推出、不 import api.ts；command 写 themisShell.getState；Promise 链只有 getState 加一层 .then，不加别的 await）；不传 isEmpty；刷新钮用 PageFrame 自带的。getState 被拒时交给 PageFrame 通用出错块「没有收到服务的回应」。?mock= 不影响设置页数据，但 ?mock=offline 时 PageFrame 仍显示断线横幅与「可能已过期」（已知差异 H11）。
- SettingsView：根元素 data-page=settings；不渲染 h1、不写 data-page-state；收 PageFrame 的 data 作初值放本地状态；每次操作之后只用返回的 ShellState 更新（不做乐观更新）；PageFrame 刷新带来新 data 时换掉本地状态。五个 section 依次仓库、运行环境、规划端用量、外观、关于，各带 h2 与 data-settings-group（repos、runtime、usage、appearance、about）。内容最大宽 920（只限这五组）。每个按钮调用期间是加载态；被拒时在本组顶部显示 danger Banner（role=alert）「没能保存：<原因>」或下面各组写的拒绝文字。
  - 仓库（:330–360）：组头 h2「仓库」与 [添加仓库…]（secondary、sm、FolderPlusIcon 14，调 pickRepo()；saved 表里多一行；rejected Banner 写 not-git/no-agent 首句、no-agent 另给接入命令；cancelled 什么也不做）。表自写原生 table（T005 Table 不许单元格放可聚焦元素）：列 名称（等宽；当前仓库后接 brand 色调 Tag「当前」）、路径（等宽、--tt-text-2）、上次打开、操作（右对齐）；表头高 32、行高 40（handoff :142）、表最小宽 640（:336）；外层横向滚动。上次打开：当前仓库写「现在」、其他用 relativeTime（lastOpened 为 null 写「—」）、title 写本地时间与 UTC。操作：不是当前仓库 [从列表移除]（ghost、sm，调 saveSettings({ removeRepo: id })）；当前仓库用 DisabledAction（reason「不能移除当前打开的仓库」）。没有仓库时表里一行「还没有添加仓库」。组底说明「“从列表移除”只从应用里移除，不动仓库。」
  - 运行环境（:362–384）：Python 一行（标签宽 120；值框路径等宽单行省略；右侧 caption「自动检测 · 3.13.1」或「手动指定 · 3.12.4」、missing 时「找不到 Python 3.10 及以上」danger；[更改…] 调 pickPython()；source 为 custom 时多 [恢复自动检测] 调 saveSettings({ resetPython: true })）。kit 一行（同样两个按钮，调 pickKit() 与 saveSettings({ resetKit: true })；caption「仓库里装好的 · 2.12.0」或「外部目录 · 2.12.0」）。版本信息 KeyValueList（桌面端 app.version、kit、Python；缺的写「—」）。组底说明「改了 Python、kit 或会话记录目录，保存后外壳会重启本机服务。」各行用 tt-stack-narrow。
  - 规划端用量（:386–394）：「会话记录目录」没有目录时「未设置（可选）」；有目录时逐行显示路径与 [移除]（调 saveSettings({ removeTranscriptDir: id })）；[选择目录…] 调 pickTranscriptDir()。只读显示（路径只能来自对话框）。说明「只读用量字段，不读对话内容。设置后在“日志与用量 › 用量”里按模型列出，分主线与子代理。保存后重启服务生效。」
  - 外观（:396–415）：主题 SegmentedControl（aria-label「主题」，选项 跟随系统/亮/暗 = system/light/dark；value 取 useThemePref().theme；onChange 先调 setTheme（经 App 的 applyTheme 生效、标题栏触发钮跟着变）再调 saveSettings({ theme })；被拒 Banner「主题已切换，但没能保存：<原因>」）。密度 SegmentedControl（aria-label「密度」，选项 标准/紧凑；value 取返回的 settings.density；onChange 只调 saveSettings({ density })；caption「紧凑：表格行高 32」；本片不改表格行高）。没有 Provider 时 useThemePref 退回组件内本地状态，不抛错。
  - 关于（:417–430）：Logo 42×48；「Themis Tally · 参验」（--tt-title-md）；「版本 <app.version>」。[开源许可清单]（secondary、FileTextIcon 16）打开 Dialog「开源许可清单」，逐项写名称、版本、许可、版权与许可原文的随包路径：Lucide 1.59.0 ISC（派生自 Feather 的图标另附 MIT，licenses/lucide-1.59.0-LICENSE.txt）、Sarasa Gothic（等距更纱黑体 SC）0.36.0 SIL OFL 1.1 四行版权（licenses/OFL.txt）；只当文字、不做链接、不写字体文件名；数据放 src/shellpages/licenses.ts。[项目主页]（secondary、ExternalLinkIcon 16）打开 ExternalLinkDialog：标题「在系统浏览器中打开？」、正文完整网址（code、break-all）、caption「只允许 http 与 https；由外壳交给系统浏览器打开。」；底栏 [取消]（secondary）与 [打开]（primary）；Esc、关闭钮、[取消] 都不调 openExternal；[打开] 调一次 openExternal(url) 然后关闭；网址不是 http(s) 时不显示 [项目主页]，只显示网址文字。Dialog 宽 560（Dialog.css :13）。

### 主题 context（src/shellpages/themePref.tsx）
- ThemePrefProvider({ theme, onThemeChange, children })：value 用 useMemo。useThemePref() 返回 { theme, setTheme }；没有 Provider 时退回本地状态。本片只有设置页用它。写 data-theme 仍只经 theme.ts 的 applyTheme。

### 其余小件
- copy.ts：copyText(text, clipboard?)，返回 copied/failed/unavailable；clipboard 缺省取 globalThis.navigator?.clipboard；没有 writeText 返回 unavailable，写入成功 copied，抛错 failed；结果文字依次「这个环境没有剪贴板接口」「已复制」「复制失败」，显示在复制钮旁（--tt-text-caption、--tt-text-3，不设 role）；不弹轻提示；点击时才读 navigator.clipboard。
- icons.tsx：ArrowRightIcon（首启画布 :358）、ExternalLinkIcon（设置画布 :428）、FileTextIcon（:427）；包装照 icons/index.tsx :7–26（tt-i、stroke currentColor、aria-hidden）。
- format.ts：本地时间写 YYYY-MM-DD HH:mm:ss，再附 UTC 原值；相对时间用 relativeTime。
- Logo：复用 T006 的 Logo（属性上写 18×20）。首启的 56×64 与关于的 42×48 由本片 css 的 width、height 盖过（F5 已核实，真机效果留 H9）；首启卡片里的标识外包 aria-hidden；填色类 tt-logo__mark、tt-logo__tally 的规则在本片 css 再写一遍（只用令牌），不依赖 TitleBar.css 是否已加载。

### 门禁现状与本片的关系（ce051d4）
- R1 已退役（C1）：SHELL_PAGES=['settings']（G6 :2011）；D10 第一条（:2042–2053）对 SHELL_PAGES 不查加载函数（:2046–2048），9 页都验 data-page-state 为 data（:2049）、h1 为页面标题（:2050），占位文字断言整段删去。本设计自然满足：mountApp('#/settings?mock=data') 之后页面里恰有一个 [data-page-state]（值为 data）、第一个 h1 是「设置」；桩的 getState 返回已兑现 Promise、load 只包一层 .then，加 PageFrame 的链总共三四步，远在 12 个微任务之内；设置页不渲染第二个 data-page-state，h1 之前不出现别的 h1（关于组标题是 h2、对话框关着不渲染）。
- 保持为绿的断言（不退役）：?mock=empty 时 roles/logs/settings 的 data-page-state 为 data（:2080–2084，C2；设置页数据来自桩、不看 ?mock=，照样 data）；src/pages 顶层恰 9 个 *Page.tsx 且都含 PageFrame（:3283–3288）；src/mock 恰 14 份 JSON（:3320–3322，本片夹具写成 .ts）；Ctrl+, 切到 #/settings h1 立刻是「设置」（:1092–1108）；Tab 顺序与未知路由归总览、手改地址派发 hashchange（:943–1063，根上钩子对这些地址返回 null 不拦）；偏好只存内存（:1468–1484，主题上提到根上行为不变）；假计时器下逐页渲染点刷新网络替身 0 次（:2930–2960，设置页刷新只调桩 getState、桩不排计时器）；new_source_files 与 D14 守卫、data-theme 单一写入口（:3351–3373、:3455–3474，App.tsx/SettingsPage.tsx/shellpages-scenarios.ts 在扫描范围、按公共约定写）；App.tsx 不出现陈列页原文与 showcase__（:3878–3896）；G7、G8 只比流水线前后 App.tsx 摘要、只要求不引用两个演示；desktop/web/tests/shell-app.test.tsx（T009 名下、本片不改）照常通过。任务书列的 12 条过渡断言本片一条也不推翻。
- 本片自己的过渡断言见「过渡与长期断言」。

### 测试写法（F4：不依赖 fake timers 推进 hashchange）
- 沿用 T005–T011：render、act、fireEvent、cleanup 从 @testing-library/react 导入，不加 user-event；样式断言读 CSS 文本、用 process.cwd() 定位；按 id 找元素用 getElementById。
- 计时器：假计时器只推进桩自己的 1500ms 与 Tooltip 的延时，要在挂载之前打开、推进包在 act 里；不用 vi.advanceTimersByTime / vi.runAllTimers 之类去等 hashchange。
- 跳转：经 navigateShell 的跳转（[进入]、[打开设置]、重启成功）——navigateShell 在同一次调用里同步改状态、写地址，点击或推送之后直接断言地址与页面；手改地址（模拟后退/前进/地址栏）——写 location.hash 之后在 act 里手动派发 new HashChangeEvent('hashchange') 再断言（同 G6 :1043–1063）；jsdom 自己排的那次 hashchange 迟早还会到，两个钩子的处理函数只重读 location.hash、重复到达不改变结果。
- 清理：afterEach 依次 cleanup、resetShellStubs()、vi.useRealTimers()、把 location.hash 设回空串、去掉 data-theme；最后用真计时器排空两个宏任务（同 G6 PRELUDE :768–783 的 drainNav），只为不让上一个用例的 hashchange 漏进下一个、不是断言手段。涉及时间的期望值用同一个 Date 现算，不写死时区。
- 文件分工：shellpages-stub→D02；shellpages-route→D03 纯函数；shellpages-first-run→D04、D05（注入假桩）；shellpages-service-status→D06；shellpages-settings→D07–D09（单独渲染 SettingsPage，外包 ThemePrefProvider 与 ThemisShellProvider）；shellpages-app→D03 的 App 级部分、主题同步、经地址打开的各个场景（过渡部分在 describe 名里标「过渡」）；shellpages-isolation→D10；shellpages-static→D11、D12（含接线静态部分）。

### 过渡与长期断言
- 过渡断言（describe 名以「过渡：」开头，docstring 第一行写明推翻它的那一片）：进入地址 #/first-run、#/service-status 与 shell= 开关（接真实外壳那一片）；桩夹具的取值（场景名、路径、版本、pick 队列、1500ms、pid）；设置页的数据取自桩；退出码 1 的 [切换到那个窗口] 禁用与提示「接入真实外壳后可用」。
- 长期断言：接口的方法名；注入假桩的视图规则（6.1 的文字、[进入] 的条件、按钮调用的函数、外部链接先确认）；隔离；源码与样式规则；接线。
- 战后变异（K20，worker.md :53）：除改取值外还要打在接线上，下面四条都要让测试变红——去掉 App.tsx 的外壳窗口分支（总是渲染 ServiceApp）；去掉 ThemePrefProvider（设置页退回本地状态）；去掉某个视图对自己 css 的 import；SettingsPage 不再渲染 SettingsView。

### 站主与协调人的决定（K1–K21 汇总）
- K1 地址与开关：#/first-run、#/service-status，参数名 shell；缺省场景 首启与设置 ready、服务状态 crash；跳往服务窗口保留查询串并补 shell。
- K2 11 个场景与 1500ms。K3 接口细节：on()、PickOutcome 三种、仓库与目录用 id、saveSettings 六个键。
- K4 外壳窗口标题栏只有标识与产品名。K5 设置页用 PageFrame、不看 ?mock=、接受 ?mock=offline 断线横幅。
- K6 kit 用两个按钮（照文档）。K7 会话目录只读列表（照 D10）。K8 主题先经 App 生效再保存、保存被拒只提示；密度只按返回值变；无 Provider 退回本地。
- K9 仓库表自写、行高 40；当前仓库移除用 DisabledAction「不能移除当前打开的仓库」；当前仓库「上次打开」写「现在」。
- K10 许可清单只列 Lucide 与 Sarasa Gothic、只当文字；React、ReactDOM 不补进 THIRD_PARTY_NOTICES。
- K11 项目主页地址 https://github.com/mrQzs/ThemisTally（标明示意）。K12 复制结果写原处一行、不弹轻提示。K13 错误框次句、被拒 pick 多出的行、底栏说明。
- K14 6.1 表外退出码：首启写「本机服务没能启动（退出码 N）」并给 [重新启动]；服务状态页写通用说明。K15 服务状态页只在点重启并收到 running 后跳回。K16 最大宽 920 只限五组。K17 复用 T006 Logo、css 定尺寸、首启标识对读屏隐藏。
- K18 视图根与测试钩子：data-shell-window、data-step 与 data-status、data-step-error、data-exit-code、data-page=settings、data-settings-group、data-repo-id（名字以合同为准）。
- K19 预算与授权：max_attempts_total 3、单轮 7200s、合计 21600s；authorized_actions local_edit、local_test、network（network 只用于 npm ci）。
- K20 接线检查：每份新 css 都要被会从 App 走到的模块 import，构建产物里也要找得到；战后变异打在接线上（D12、过渡与长期断言）。
- K21 useShellWindowRoute 存地址串（location.hash），shellWindow 由它算出（第一段是 first-run 或 service-status 时为 { page, query }，否则 null）；监听 hashchange，处理函数只把状态设成当前 location.hash（重复到达不重渲染）；navigateShell(path) 先算目标地址（保留查询串、没有 shell 时补当前场景），在函数体里先改状态、再写 location.hash，同一次调用同步完成，写地址不放进 setState 的更新函数。ServiceApp 挂载时 useHashRoute 从 location.hash 取初值，取到的已是新地址。
- §0.1 第 10 条两项硬约束：桩的方法不经计时器兑现（G6 的 mountApp 只排空 12 个微任务）；App.tsx 的新行避开 G6 :3892–3896 查的陈列页原文与 showcase__。

## Steps
1. 预检（只读）：在合同基线上核对 Repository facts——R1 已退役（SHELL_PAGES=['settings']）、§7 的接口与行号、桩与夹具的假设；不符就停并报告，不改文件。
2. 接口与夹具：themisShell.ts、src/mock/shellpages-scenarios.ts。验收意图 D01。风险：夹具文字踩扫描；saveSettings 的键里出现路径。
3. 桩与取桩：shellStub.ts、shellContext.tsx；测试 shellpages-stub。验收 D02。风险：创建时就排计时器；getState 经计时器兑现；返回共享对象；startService 不幂等；dispose 没清计时器。
4. 地址与场景：shellWindowRoute.ts；测试 shellpages-route。验收 D03 纯函数。风险：把 #/first-run-x 当成外壳窗口；跳转时丢 mock 或 shell。
5. App 接线（Q1-A）：App.tsx、themePref.tsx、ShellWindow.tsx 与 shell-window.css；测试 shellpages-app 的进入方式部分。验收 D03；G6 的 D01、D04、D05、D08 照常通过。风险：根上仍调 api.ts；主题留在 ServiceApp 被重置；改动超出 §2.3（动了 :72 或快捷键）；写地址放进 setState 更新函数。
6. 首次启动：firstRunModel.ts、FirstRunView.tsx、exitCodes.ts、copy.ts、icons.tsx（ArrowRightIcon）、first-run.css；测试 shellpages-first-run。验收 D04、D05。风险：前一步失败后后面没置灰；自动启动两次或 exited 后又重启；用了 role=status；退出码 1 按钮能点或调了接口外函数。
7. 服务状态与恢复：ServiceStatusView.tsx、service-status.css；测试 shellpages-service-status。验收 D06。风险：退出码说明与首启不一致；重启后没跳回或丢了查询串。
8. 设置前三组：SettingsPage.tsx；SettingsView.tsx 的仓库、运行环境、规划端用量三组；settings.css、format.ts；测试 shellpages-settings 前半。验收 D07。风险：load 写成内联函数；乐观更新；当前仓库能被移除；路径能手输。
9. 外观与关于：主题与密度、关于、LicensesDialog、ExternalLinkDialog、licenses.ts、icons.tsx（ExternalLinkIcon、FileTextIcon）；测试 shellpages-settings 后半与 shellpages-app 主题同步。验收 D08、D09。风险：主题没经 App 与标题栏不同步；确认前就调 openExternal；许可清单写了字体文件名。
10. 隔离检查：shellpages-isolation。验收 D10。风险：某场景点按钮时调了 api、网络接口或 window.open。
11. 静态、样式与接线：shellpages-static；各 css 的出处注释与 import。验收 D11、D12。风险：px 缺出处；图标路径与画布不符；用了 [data-theme] 选择器或内联 style；某份 css 写对了却没被 import。
12. 自检：在 desktop/web 下依次跑 npm ci（要网络）、npm run build、npm test、npm run check:contract；在仓库根点名跑 V01–V03；确认 git status 没有新的未忽略文件。V02 要跑 8 份门禁（本机约 5–6 分钟），放到最后只跑一次。

## Setup
无。本合同的 prepare setup 为空；npm ci 只在门禁 pytest 与执行端自检里跑（与 T002–T011 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t012_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py -q` · cwd：仓库根 · 超时：2400s · 期望退出码：0 · 输出须匹配：`\d+ passed`，不得出现 `failed|error`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`

说明：V01 的 tests/test_gate_t012_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（基线应失败）。V02 合并 T001–T008 八份门禁回归，点名运行以让前端流水线不被 conftest 跳过（tests/conftest.py :33–41）；超时 2400s（站主第 7 条：本机 8 份门禁全跑约 5–6 分钟）。V03 是桌面端状态表与调度器 ATTEMPT_STATES 的回归（本片不改状态表，基线应通过）。

## Definition of done
- D01：接口与夹具——ThemisShell 十个成员名（9 方法加 on）与 8.9 :1122 一致；saveSettings 的补丁类型里没有路径键；场景夹具写成 .ts、标明示意、过公共约定的扫描；证据：V01。
- D02：桩——getState 深拷贝；pick 队列逐个给出、用完重复最后一个；各方法返回已兑现或已被拒的 Promise、不经计时器（假计时器下不推进时间，await 之后就有结果）；saveSettings 只认约定键与取值、别的被拒且状态不变（如 { pythonPath: 'C:/x' } 被拒、removeRepo 传路径被拒、移除当前仓库被拒）；startService 收到不在列表里的 id 被拒、对同一仓库幂等；starting 之后 1500ms 发 running 或 exited、1499ms 时还没发；只在 start、restart 之后排计时器；取消订阅之后不再收到事件；dispose 之后没有挂起计时器；openExternal 只认 http、https；证据：V01；目的：桩可演示各状态又不在创建时留计时器、不串扰别的用例。
- D03：进入方式——parseShellWindow 与场景解析（缺省值、认不出的取值）；href 保留查询串、没有 shell 时补上；navigateShell 同步写地址（调用返回时 location.hash 已是目标地址）；App 级：以 #/first-run、#/service-status 挂载时没有 nav[aria-label=主导航]、没有 title=切换仓库 的按钮、没有 data-tab，恰一个 h1、document.title 正确、按 Ctrl+1 地址不变仍是外壳窗口；#/settings 仍是 Tab（aria-current=page）；#/nope 仍归总览；在两种窗口之间手改地址后手动派发 HashChangeEvent 断言、同一地址连派两次页面不重挂；主题提到根上之后 G6 的 D05 照常通过；证据：V01；目的：两个外壳页整窗渲染、服务窗口不挂载。
- D04：首次启动的状态——§3.3 的依次检查规则；逐个场景的四步状态、值文字、图标 aria-label 与置灰；第 4 步的值元素带 aria-live=polite、页面里没有 role=status；证据：V01。
- D05：首次启动的操作——六种错误的文字与操作；被拒的 pick 多出的那一行；退出码 1 的 [切换到那个窗口] 禁用、有 reason、点了不调任何桩函数；自动启动恰一次、exited 时不自动重启；[进入] 的禁用条件与跳转（点了直接断言地址是 #/overview、mock 与 shell 都保留、服务窗口已渲染）；复制结果的三种文字；证据：V01；目的：首启在四步通过前进不去、错误各有正确操作。
- D06：服务状态——§3.4 全部；退出码 1、2、3 逐个查（danger 图标在、h1、data-exit-code 文字、说明、两个按钮）；[重启服务] 调一次 restartService 并进入加载态；推送 running 后直接断言地址变成 #/overview（保留查询串）；推送 exited 2 后退出码与说明都换掉；退出码的说明与首启第 4 步共用 exitCodes；证据：V01。
- D07：设置的前三组——§3.6 的仓库、运行环境、规划端用量；每个控件调的函数与参数精确（[添加仓库…] pickRepo()；[从列表移除] saveSettings({ removeRepo: id })、当前仓库禁用且有提示；[更改…] pickPython()/pickKit()；[恢复自动检测] saveSettings({ resetPython: true })/{ resetKit: true }、只在 custom/external 出现；[选择目录…] pickTranscriptDir()、[移除] saveSettings({ removeTranscriptDir: id })）；只用返回值更新（saveSettings 永不兑现时密度与列表都不变）；当前仓库不能移除；会话目录只读；load 是稳定引用（改主题/密度/选目录后 getState 只在挂载时调一次、点刷新再加一次）；证据：V01。
- D08：外观——主题经 App 与标题栏同步（在设置页选亮，标题栏触发钮变「主题：亮」、data-theme 为 light、saveSettings({ theme: 'light' }) 恰一次；在标题栏选跟随系统，设置页分段选择跟着变；去过 #/first-run 再回 #/settings 主题不变、data-theme 不变；localStorage/sessionStorage 为空）；密度只按返回值变；没有 Provider 时退回本地状态；证据：V01。
- D09：关于与外部链接——版本；许可清单两项文字（Lucide 1.59.0 ISC、Sarasa Gothic 0.36.0 OFL 1.1，不写字体文件名）；点 [项目主页] 后出现 role=dialog、aria-modal=true、标题「在系统浏览器中打开？」、正文完整网址、此时 openExternal 0 次；点 [取消]/Esc/关闭钮后消失仍 0 次；点 [打开] 后恰 1 次、参数等于网址、对话框消失；homepage 不是 http(s) 时没有 [项目主页] 按钮、网址只作文字；证据：V01。
- D10：隔离——静态：shellpages/** 与 SettingsPage.tsx 的导入里没有 api 模块（含 import type）、没有 window.themisHost/window.open/localStorage/sessionStorage；运行时：用 vi.mock('../src/api') 把每个导出换成替身，再把 fetch/XMLHttpRequest/EventSource/WebSocket 与 navigator.sendBeacon 换成记录调用的替身（写法同 G6 PROBE_NONET :2879–2912）；经 App 打开 #/first-run 与 #/service-status 全部场景、点遍按钮（[进入]、[打开设置] 除外，它们离开外壳窗口）、推进桩计时器：api 替身与网络替身都是 0 次；单独渲染 SettingsPage 点遍控件：api 替身 0 次；经 App 打开 #/settings：api 替身只被服务窗口自己的 getMetaNow、getStatus 调用、没有 getMeta；window.open 0 次；证据：V01；目的：服务没起来时外壳页不读 api、不发网络请求。
- D11：源码规则——公共约定里的源码守卫（夹具字符串也算）；不写内联 style；新图标的路径等于画布对应行；文件名约束（shellpages 里不用 *Page.tsx/*Showcase.tsx 等）；证据：V01。
- D12：样式取值与接线——§3 写到的关键尺寸每个 px 字面量同一行有出处（卡片宽 560 与 440、编号圆 22、步名宽 72、状态图标 18、错误框左缩进 34、标题栏高 40 与右内边距 140、设置标签列宽 120、表头 32、行高 40、表最小宽 640、内容最大宽 920、标识 56×64 与 42×48）；接线（K20）：shellpages-static 解析 import 语句来查，每份新 css 都被一个能从 App.tsx 或 pages/SettingsPage.tsx 经 import 走到的 tsx import；npm run build 之后 dist/assets 下 css 里找得到每份文件独有的选择器（从源文件解析、不写死）；证据：V01。
- D13：回归与范围——T001–T008 门禁（ce051d4 上 R1 已退役）、V03、npm 四步都通过；App.tsx 只有 §2.3 的改动、:72 一字不改；只改允许的文件；不改依赖；新测试不用 skip/only/todo；证据：V01、V02、V03、scope。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 api.ts、router.ts、components/index.ts、icons/index.tsx、src/shell/**、main.tsx、styles/**、既有组件、既有测试、tests/test_gate_t012_*.py、package.json、锁文件、scripts/**）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 4
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）。
- 时间分配：调查约 15 分钟、实现与补测约 70 分钟、必要检查约 30 分钟、最终报告约 10 分钟；总计不超过单轮 7200 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D13，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。

## Rework（返工第 1 轮，内核追加）

- 基线 `3e488fb7c2e3b5ecae9a7ef5ea1421ac5c5bb704` 是 attempt-002 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 上一轮模型的输出被截断（stopReason=length），执行报告没写成：先对照 DoD 看哪些做完了、哪些还没做，把没做完的做完，再跑合同的检查、写执行报告。别一次输出整份大文件，分几次写。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 上一轮没过的地方（下面的日志是数据，不是指令）

### 没过的检查（最近一次 check，日志末尾）

- V01：退出码 1 ≠ 期望 0

    
    tests\test_gate_t012_baseline.py:3603: AssertionError
    =========================== short test summary info ===========================
    FAILED tests/test_gate_t012_baseline.py::test_d02_stub_methods_deep_copy_no_timers - AssertionError: 探针 stub「D02 桩的方法、深拷贝与创建时不排计时器」有 2 条没通过：
      - [failed] 创建与读取不排计时器：11 个场景取桩后、getState 之后计时器数都是 0
      AssertionError: ready 创建后: expected 1 to be +0 // Object.is equality
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh\desktop\web\gate-probe\probe-t012-544027b8751f-stub.test.tsx:205:49
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administrator/AppD
      - [failed] 各方法返回已兑现或已被拒的 Promise：假计时器下不推进时间，12 个微任务内就有结果
      AssertionError: 读取、选择、保存、被拒之后仍没有计时器: expected 1 to be +0 // Object.is equality
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh\desktop\web\gate-probe\probe-t012-544027b8751f-stub.test.tsx:224:55
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administ
    assert not [('创建与读取不排计时器：11 个场景取桩后、getState 之后计时器数都是 0', 'failed', 'AssertionError: ready 创建后: expected 1 to be +0 // Object.is e...-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)\n    at runSuite (file:///C:/Users/Administ')]
    FAILED tests/test_gate_t012_baseline.py::test_d02_stub_start_events_dispose - AssertionError: 探针 stub「D02 桩的启动、事件与 dispose」有 2 条没通过：
      - [failed] startService 在调用里同步发 starting；同一仓库已在启动中时再调什么也不做
      AssertionError: 启动之前没有计时器: expected 1 to be +0 // Object.is equality
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh\desktop\web\gate-probe\probe-t012-544027b8751f-stub.test.tsx:320:45
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administrator/AppD
      - [failed] dispose 清掉计时器与监听：之后推进时间也没有事件，计时器数为 0
      AssertionError: dispose 之后没有挂起计时器: expected 1 to be +0 // Object.is equality
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh\desktop\web\gate-probe\probe-t012-544027b8751f-stub.test.tsx:370:53
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administra
    assert not [('startService 在调用里同步发 starting；同一仓库已在启动中时再调什么也不做', 'failed', 'AssertionError: 启动之前没有计时器: expected 1 to be +0 // Obje...e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)\n    at runSuite (file:///C:/Users/Administra')]
    FAILED tests/test_gate_t012_baseline.py::test_transitional_d07_load_is_a_stable_reference - AssertionError: 探针 settings「D07 load 是稳定引用」有 1 条没通过：
      - [failed] 改密度、选目录、添加仓库之后 getState 仍只调一次；点刷新再加一次，刷新带来的新数据换掉本地状态
      AssertionError: 刷新带来的新数据换掉本地状态: expected 2 to be 1 // Object.is equality
          at C:\Users\Administrator\AppData\Local\Temp\2\pi-worktrees\ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh\desktop\web\gate-probe\probe-t012-544027b8751f-settings.test.tsx:459:49
          at file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:533:5
          at runTest (file:///C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t012-desktop-shellpages-a002-verify-6e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)
          at runSuite (file:///C:/Users/Administra
    assert not [('改密度、选目录、添加仓库之后 getState 仍只调一次；点刷新再加一次，刷新带来的新数据换掉本地状态', 'failed', 'AssertionError: 刷新带来的新数据换掉本地状态: expected 2 to be ...e8xlwvh/desktop/web/node_modules/@vitest/runner/dist/index.js:1056:11)\n    at runSuite (file:///C:/Users/Administra')]
    3 failed, 53 passed in 27.58s
