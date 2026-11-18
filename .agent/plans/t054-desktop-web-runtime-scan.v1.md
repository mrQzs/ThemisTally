# TASK: t054-desktop-web-runtime-scan

<!-- 合同 v1：T054「[扫描 PATH]：运行时页接上作业接口，扫出本机的 CLI、逐个登记」。
     页头的 [扫描 PATH] 从灰变可点：点了起一个 runtime-scan 长作业（POST /api/v1/jobs），
     对话框里用作业进度卡显示进度（已用秒数每秒更新、可取消），结束后列出本机找到的五个 CLI
     （适配器、路径、版本），找到且还没有同名 runtime 的那一行给 [登记…]（走既有 runtime.add 的
     预览 → 确认 → 执行，写完重读整页）。同一时间只有一个扫描作业；关掉对话框再打开接着看同一个作业。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片不改本机服务（ts/packages/ui/**），不改 components/**、shell/**、readonly1/**、readonly2/**。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 4e174d913d58f4ef94059d1b9d0d9660a0044103
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
运行时页页头的 [扫描 PATH] 从灰变可点：点了起一个 runtime-scan 作业（`POST /api/v1/jobs`，正文恰是 `{"kind":"runtime-scan"}`），对话框里用作业进度卡显示进度（已用秒数每秒更新、可取消），作业结束后在同一位置显示结果：本机找到的五个 CLI 各一行（适配器、路径、版本），找到且还没有同名 runtime 的那一行给 [登记…]（走既有 `runtime.add` 的预览 → 确认 → 执行，写完重读整页）；同一时间只有一个扫描作业，关掉对话框再打开接着显示同一个作业的进度或结果，不另开一个。

## Non-goals
- 不改本机服务（`ts/packages/ui/**` 一个字不改）：作业路由、作业表与内核的 `config runtime scan` 都已就位。
- 不接 [探测]、[模型]、[运行就绪检查]、[核验]（作业客户端与作业卡做成以后能接的样子，本片只接扫描）。
- 不做凭据录入、资格认证、续期按钮；不做方案表空态的 [保存当前为方案…] 按钮；不做「登记全部」。
- 不改 `desktop/web/src/components/**`、`desktop/web/src/shell/**`、`desktop/web/src/pages/readonly1/**`、`desktop/web/src/pages/readonly2/**`；新组件不进 `components/index.ts`。
- 不改既有的写流程文件（`src/writes/useWriteFlow.ts`、`WriteConfirmDialog.tsx`、`writeOutcome.ts`、`snapshots.ts`、`useLivePreview.ts`、`RuntimeForm.tsx`、`runtimeRules.ts`、`profileRules.ts` 与三份既有 CSS）；本片复用它们的既有文字表与 `runtime.add` 分派。
- 不改 `src/mock/writes.ts`（`WriteScenario` 一个值都不加）、`src/mock/quizs.ts`、`src/mock/hub-roles.ts`、`src/mock/*.json`（src/mock 不加 JSON）；`src/pages` 顶层不加 `*Page.tsx`。
- 不改 `desktop/web/tests/live-api.test.ts`、`desktop/web/tests/live-transport.test.ts`（transport 与 api 的新用例放新文件）。
- 不新增依赖、不改锁文件（`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字不动）。

## Repository facts
以下事实都在本回合的工作目录里逐条读过（行号按基线 00e299d9）。

### 本机服务（不改，只照它的规则写前端）
- `ts/packages/ui/src/jobroutes.ts`
  - `:29` `JOBS_PATH = "/api/v1/jobs"`；`:32` `JOB_KINDS` 六个 kind（`doctor / doctor-record / runtime-scan / runtime-probe / models / search`）。
  - `:39` `JOB_ARGV["runtime-scan"] = ["config","runtime","scan","--json"]`；`:50-56` `JOB_TIMEOUTS["runtime-scan"] = 150`（doctor 600、models 120、search 180）；`:59` `JOB_ALLOW` 六类全是 undefined（作业结果一律按键名脱敏）；`:62-70` `SCHEMA["runtime-scan"]` 的 required 与 optional 都是空数组（正文只有 `kind` 一个键）。
  - `:150-196` `validateJob`：正文必须是 JSON 对象；`kind` 必须是六个之一；**键恰好**（多一个键回 400「请求体含有未知键」）；`runtime-scan` 没有别的必填/可选键。
  - `:246-262` 创建路由：`POST /api/v1/jobs`，成功回 **201**，正文是八键作业对象（当下 state=queued）；`:264-269` 查询路由 `GET /api/v1/jobs/<id>` 回 200；`:271-277` 取消路由 `POST /api/v1/jobs/<id>/cancel`，**正文必须是 JSON 对象**（空对象 `{}` 合法）。
  - `:106-119` `cancelJob`：不在表里回 404；已终态回 **409**（`作业已经结束`）；否则 abort 并等子进程树结束后回 200 与当时的八键作业对象。
- `ts/packages/ui/src/jobs.ts`
  - `:136-148` `jobView` 的八键：`id / kind / state / reason / created_ms / started_ms / finished_ms / envelope`（不套七字段信封、不套 data）。
  - `:17` 六个状态：`queued | running | succeeded | failed | cancelled | timed_out`；`:33-35` `isTerminal`。
  - `:12` 作业号是 43 个 base64url 字符（不透明，前端原样传回即可）。
- `ts/packages/ui/src/kernelenvelope.ts`
  - `:65-71` `envelopeBody`：信封七字段是蛇形（`ok / exit_code / data / output / messages / command / elapsed_ms`），与前端 `Envelope` 接口逐字一致；`:83-91` 超时信封的 messages 是一行 `ERROR: 命令超时（N 秒）…`；作业被取消时 `envelope` 是 null。
- `scripts/kit_roles.py`
  - `:45-55` `ADAPTERS` 五个适配器与各自的 program：`pi→pi`、`claude-code→claude`、`codex→codex`、`opencode→opencode`、`quizs→quizs`。
  - `:818-843` `_runtime_scan --json` 的输出是 `{"found":[{"adapter","program","path","version","exit_code"}],"added":[]}`；PATH 上没有的适配器 `path / version / exit_code` 都是 null。

### 前端现状
- `desktop/web/src/live/transport.ts`
  - `:107` `createLiveClient`；`:132` 内部 `request(path, query, shape, timeoutSeconds)`（**唯一**的 `new AbortController(`、唯一的 `setTimeout(`、唯一的 `credentials: 'same-origin'` 与那两处中止判定都在这里——t037 S01 按出现次数静态钉住）；`:177` `get<T>`；`:190` `post<T>`（正文归成信封，拿不到回应时 reject）；`:206` `getRaw<T>`（正文原样交回，非 JSON 时按状态码合成失败信封）。
  - `:16` `TIMEOUT_GRACE_SECONDS = 5`（客户端中止 = 服务端时限 + 5 秒）。
- `desktop/web/src/live/mode.ts`：`:11-17` `LiveClient` 类型三个成员（get / post / getRaw）；导出恰好四个名字（t037 S02 钉住）；`:33` `setLiveClientForTests`（包内测试注入假客户端的既有做法）。
- `desktop/web/src/api.ts`
  - `:82` `WriteArgs`；`:85` `HttpReply<T>`（status + 七字段信封）；`:288-290` 三个时限常量（预览 30、操作查询 30、写 90）；`:311` `writeArgs`（预览与执行共用同一份整理规则）；`:621` `getRuntimes`；`:710` `preview`；`:720` `getOperation`（`getRaw` + 状态码分类，是作业查询的写法样板）；`:906` `addRuntime`（`POST /api/v1/runtimes/<id>/add`，正文只有 `adapter` 与 `confirmation`）。
- `desktop/web/src/mock/scenario.ts`：五个开关 `data | offline | loading | error | empty`（`currentMock()` 每次调用时读 `location.hash` 里的 `?mock=`）。
- `desktop/web/src/mock/runtimes.json`：已登记 `pi`、`claude-code`、`opencode`（各有 id 与 adapter）。
- `desktop/web/src/writes/useWriteFlow.ts`：`titleOf` / `successTextOf` / `changeSummaryOf` 三张文字表里已有 `runtime.add` 的分支（标题 `登记运行时 X？`、轻提示 `已登记运行时 X`、摘要 `已登记表里加上 X（适配器 a）`）；`readSnapshot` 有 `runtime.add` 分支（读 `getRuntimes()`）；执行分派里已有 `runtime.add → addRuntime(...)`；`dangerOf` 不含 `runtime.add`。
- `desktop/web/src/writes/PresetSaveForm.tsx`：T053 的内外两层样板（外层 `useWriteFlow(reload)` + `{open && <内层/>}` + `<WriteFlow flow={flow} />`；内层只在打开时挂载；[确认…] 先 `onClose()` 再 `start(spec)`）——本片的扫描对话框照这个形状。
- `desktop/web/src/pages/RuntimesPage.tsx`：`:60` 页头第一个按钮是 `<DisabledAction label="扫描 PATH" icon={<SearchIcon width={16} height={16} />} />`，`:61` 是 `<AddRuntimeAction reload={reload} />`；文件头 `:3` 的注释「页头 [扫描 PATH] 仍禁用（服务没有 config runtime scan 写路由）」已不对；children 是 `(data, reload) =>`，视图拿到 `reload={reload}`。
- `desktop/web/src/pages/readonly1/runtimes-logic.ts`：`:49` `canProbe(source)` = source ≠ missing；`:54` `canModels(adapter, source)` = adapter 是 pi 且 source ≠ missing。桩下运行时页的禁用按钮恰 5 个：pi 的 [探测] 与 [模型]、claude-code 的 [探测]、[运行就绪检查]、页头 [扫描 PATH]；[扫描 PATH] 变可点后是 **4** 个。
- `desktop/web/src/components/Dialog.tsx`：`open` 为假时 `return null`；props 是 `open / onClose / title / children / footer / dismissible`。`components/index.ts` 按字节冻结（t008 :105、t009 :155），新组件不许进。
- `desktop/web/vite.config.ts`：vitest 的 include 覆盖 `src/**/*.test.{ts,tsx}`、`tests/**/*.test.{ts,tsx}`、`gate-probe/**`；`desktop/web/tsconfig.json` 的 include 只有 `["src","vite.config.ts"]`（`tests/` 不过 `tsc --noEmit`）；`desktop/web/package.json`：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`、`npm run build` = `tsc --noEmit && vite build`。

### 门禁与既有测试的核查结论（本片**必然**要改的那几处，逐条读过）
- `tests/test_gate_t009_baseline.py`
  - `:2877-2886` 页头用例：按钮次序断言 `['扫描 PATH','手动登记…','刷新']` 成立（次序不变），但 `:2881` 的 `expect(buttons[0].disabled).toBe(true)` 与 it 标题里的「禁用」要改；`:2883` 断言页头第一个按钮里带 svg（SearchIcon 要留着）。
  - `:2942-2954` `tooltipTexts()` 只遍历**禁用**按钮——[扫描 PATH] 变可点后，「第二阶段接入」的悬停断言不受影响。
  - `:2970-2977` 运行时页用例：`:2974` 的白名单 `outsideWhitelist(['删除…','手动登记…'])` 要加 `'扫描 PATH'`（它变成可点按钮）。
- `tests/test_gate_t041_baseline.py`
  - `:320-326` 静态用例 `test_s05_runtimes_page_entry`：`:326` 的 `assert '<DisabledAction label="扫描 PATH"' in text` 要改成断言新的入口记号；`:325` 的 `AddRuntimeAction` 断言照旧；`:329-332` 的禁字表照旧（入口文件里不许出现确认框标题、轻提示与内核原文）。
  - `:592-601` 探针：`:597` 的 `expect(bs[0].disabled, '[扫描 PATH] 仍禁用（本片不做扫描）').toBe(true)` 要改成断言可点；`:596` 的按钮次序断言照旧。
- `tests/test_gate_t043_baseline.py`
  - `:453-458` 页头仍要从 `'../api'` 命名引入 `getRuntimes / getQuizsProviders / getQuizsLive`（本片不改 api 的引入）；`:459-462` 的记号表里 `'<DisabledAction label="扫描 PATH"'` 这一枚要换成新的入口记号；`:463` 的 children 断言照旧。
- `tests/test_gate_t045_baseline.py`
  - `:560` 的 it 标题正则写死「运行时页 5」；`:563-565` 的 token 表写死 `("运行时页 5", r"toBe\(5\)")`。页内测试把禁用数改成 4 之后，**这两处都要跟着改**，否则 t045 必红。
- `tests/test_gate_t049_baseline.py`
  - `:270-271` 静态断言 `'<DisabledAction label="扫描 PATH"' not in code` 的反面（要换成新入口记号）；`:467-472` 与 `:585-586` 两处探针的 `expect(buttons[0].disabled, '[扫描 PATH] 照旧禁用').toBe(true)` 要改成断言可点；`:471`/`:585` 的按钮次序断言照旧。
- `tests/test_gate_t037_baseline.py`：`:225-259` S01 按出现次数钉住 `transport.ts` 里的 `new AbortController(` / `setTimeout(` / `credentials: 'same-origin'` 各一处与两处中止判定；`:262-303` S02 钉住 `mode.ts` 的导出恰好四个；`:309-310` S03 钉住 `api.ts` 全文不出现网络接口名（连注释）。
- `tests/test_gate_t010_baseline.py`：`:107-110` 禁用词与禁用调用（`innerHTML`、`eval(`、`matchMedia`、`scrollIntoView`、`ResizeObserver` 等）与网络接口名；`:513-514` 不许渲染 `role="status"`；`:100-104` src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 `*Page.tsx`。
- `tests/test_gate_t048_baseline.py`：`:130-140` 按字节冻结清单（`mock/quizs.ts`、`mock/hub-roles.ts`、`runtimes-quizs-logic.ts`、`roles-styles.css`、三份既有包内测试、`package.json`、`package-lock.json`——`api.ts` 不在其中）；`:546-551` src/mock 仍恰 14 份 JSON、src/pages 顶层仍恰 9 个 `*Page.tsx`。
- `tests/test_gate_t022_baseline.py`（:224-240 api.ts 的导出按包含核对，加导出合法）、`tests/test_gate_t023_baseline.py`（`:319-328` S10 children 与 `reload={reload}`；`:331-348` S11 入口文件禁字）、`tests/test_gate_t008_baseline.py`（`:104-107` `components/index.ts` 与 `icons/index.tsx` 按字节只许末尾追加）、`tests/test_gate_t002_baseline.py:1496`（`desktop/web` 下所有 `*.test.*` 不许 `skip`/`only`/`todo`）。
- 包内测试：`desktop/web/tests/page-app.test.tsx:91-98`（describe 标题「写入口个数（过渡）」一字不动；`:93` 的 it 标题与 `:98` 的 `toBe(5)` 要改成 4）；`desktop/web/tests/page-runtimes-empty.test.tsx:109-110`（按钮次序照旧，`:110` 的「[扫描 PATH] 照旧禁用」要改成断言可点）。
- 关键字搜索（`扫描 PATH`、`runtime-scan`、`jobs`、`RuntimesPage`、`DisabledAction`、`SearchIcon`、`第二阶段接入`、`postRaw`、`getRaw`，范围 `desktop/web/tests/` 与 `tests/`）：命中只有上面列出的这些。

### 工具链与锁文件
- `desktop/web` 用 npm（vitest 2.1.8、TypeScript 5.6.3、React 18.3.1）；仓库门禁用 `python -m pytest`。
- `dependency_changes: forbidden`：`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字都不许动（t048 还按字节冻结了前两个）。

### 基线检查
- 本回合（合同端）只读，没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 合同检查在基线上的结果由内核在执行之前跑过（基线检查记录）；执行端不必再跑一遍整套测试。

## Scope
- allowed_modified_files:
  - desktop/web/src/live/transport.ts
  - desktop/web/src/live/mode.ts
  - desktop/web/src/api.ts
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/page-runtimes-empty.test.tsx
  - tests/test_gate_t009_baseline.py
  - tests/test_gate_t041_baseline.py
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t049_baseline.py
- allowed_new_files:
  - desktop/web/src/mock/jobs.ts
  - desktop/web/src/jobs/jobStore.ts
  - desktop/web/src/jobs/JobCard.tsx
  - desktop/web/src/jobs/job-card.css
  - desktop/web/src/writes/RuntimeScan.tsx
  - desktop/web/src/writes/runtime-scan.css
  - desktop/web/tests/jobs-api.test.ts
  - desktop/web/tests/jobs-store.test.ts
  - desktop/web/tests/jobs-scan-page.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t054_*.py
  - tests/test_gate_t001_baseline.py
  - tests/test_gate_t002_baseline.py
  - tests/test_gate_t003_baseline.py
  - tests/test_gate_t004_baseline.py
  - tests/test_gate_t005_baseline.py
  - tests/test_gate_t006_baseline.py
  - tests/test_gate_t007_baseline.py
  - tests/test_gate_t008_baseline.py
  - tests/test_gate_t010_baseline.py
  - tests/test_gate_t011_baseline.py
  - tests/test_gate_t012_baseline.py
  - tests/test_gate_t013_baseline.py
  - tests/test_gate_t014_baseline.py
  - tests/test_gate_t015_baseline.py
  - tests/test_gate_t016_baseline.py
  - tests/test_gate_t017_baseline.py
  - tests/test_gate_t018_baseline.py
  - tests/test_gate_t019_baseline.py
  - tests/test_gate_t020_baseline.py
  - tests/test_gate_t021_baseline.py
  - tests/test_gate_t022_baseline.py
  - tests/test_gate_t023_baseline.py
  - tests/test_gate_t024_baseline.py
  - tests/test_gate_t025_baseline.py
  - tests/test_gate_t026_baseline.py
  - tests/test_gate_t027_baseline.py
  - tests/test_gate_t028_baseline.py
  - tests/test_gate_t030_baseline.py
  - tests/test_gate_t031_baseline.py
  - tests/test_gate_t032_baseline.py
  - tests/test_gate_t033_baseline.py
  - tests/test_gate_t034_baseline.py
  - tests/test_gate_t035_baseline.py
  - tests/test_gate_t036_baseline.py
  - tests/test_gate_t037_baseline.py
  - tests/test_gate_t038_baseline.py
  - tests/test_gate_t039_baseline.py
  - tests/test_gate_t040_baseline.py
  - tests/test_gate_t042_baseline.py
  - tests/test_gate_t044_baseline.py
  - tests/test_gate_t046_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t048_baseline.py
  - tests/test_gate_t050_baseline.py
  - tests/test_gate_t051_baseline.py
  - tests/test_gate_t052_baseline.py
  - tests/test_gate_t053_baseline.py
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/pages/readonly2/**
  - desktop/web/src/pages/HistoryPage.tsx
  - desktop/web/src/pages/LogsPage.tsx
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/PluginsPage.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/SecretsPage.tsx
  - desktop/web/src/pages/SettingsPage.tsx
  - desktop/web/src/pages/TasksPage.tsx
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/mock/quizs.ts
  - desktop/web/src/mock/hub-roles.ts
  - desktop/web/src/mock/shell.ts
  - desktop/web/src/mock/empty.ts
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/tasks-*.ts
  - desktop/web/src/mock/readonly2-*.ts
  - desktop/web/src/writes/RuntimeForm.tsx
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/profileRules.ts
  - desktop/web/src/writes/runtimeRules.ts
  - desktop/web/src/writes/hubChangeLines.ts
  - desktop/web/src/writes/HubBindForm.tsx
  - desktop/web/src/writes/RoleBindForm.tsx
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/PresetSaveForm.tsx
  - desktop/web/src/writes/runtime-form.css
  - desktop/web/src/writes/hub-bind-form.css
  - desktop/web/src/writes/profile-form.css
  - desktop/web/src/writes/write-flow.css
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/page-runtimes.test.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - ts/package.json
  - ts/bun.lock
  - ts/packages/ui/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 入口（页头）
- `desktop/web/src/pages/RuntimesPage.tsx` 的页头第一个按钮从 `<DisabledAction label="扫描 PATH" icon={<SearchIcon width={16} height={16} />} />` 换成 `<ScanRuntimesAction reload={reload} />`；`ScanRuntimesAction` 从 `../writes/RuntimeScan` 引入。
- 按钮文字逐字「扫描 PATH」，`variant="secondary"`、`size="md"`，**一直可点**（加载、出错、离线各态都可点，与 [保存当前为方案…] 同口径）；**带 SearchIcon 16×16**（t009 :2883 断言页头第一个按钮里有 svg）。
- 页头次序不变：`['扫描 PATH','手动登记…','刷新']`。
- `RuntimesPage.tsx` 删掉 `DisabledAction` 与 `SearchIcon` 两个 import（`SearchIcon` 移到 `src/writes/RuntimeScan.tsx` 里用）；文件头 `:3` 的注释改成新的事实（扫描走作业接口，页头的 [扫描 PATH] 可点）。
- `RuntimesPage.tsx` 的其余部分一字不改：并行三读 `getRuntimes / getQuizsProviders / getQuizsLive`、失败判定、`isRuntimesEmpty`、children 的 `(data, reload) =>`、视图的 `reload={reload}`、空态「还没有登记的 runtime」、Quizs 一块、页头说明原文。

### 传输层（`live/transport.ts` 与 `live/mode.ts`）
- `live/transport.ts` 的 `createLiveClient` 返回的对象加第四个公开方法：
  `postRaw<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: T }>`。
  - 请求形状与 `post` 相同：POST、`Content-Type: application/json`、`X-Themis-UI: 1`、正文 `JSON.stringify(body)`、credentials 与 signal 由内部 `request` 补上。
  - **复用内部 `request`**：不许另起一条请求代码（t037 S01 按出现次数钉住 `new AbortController(`、`setTimeout(`、`credentials: 'same-origin'` 各一处与两处中止判定）。
  - 状态码与正文原样交回（作业对象不是信封，不能归成信封）；401 先 `runReauth()` 再回合成的 401 失败信封（照 `getRaw`）；正文不是合法 JSON 时按状态码合成失败信封（照 `getRaw`）；拿不到回应时 reject（照 `post`）。
- `live/mode.ts` 的 `LiveClient` 类型加 `postRaw` 成员（签名与上面逐字一致）；**导出集合仍是恰好四个名字**（不新导出别的东西）；`import type { Envelope } from '../api'` 照旧。
- `desktop/web/tests/live-transport.test.ts` 与 `live-api.test.ts` 不许改；postRaw 的用例放新文件。

### api.ts（三个导出 + 三个类型）
- 新增类型：
  - `export type JobKind = 'runtime-scan';`（本片只登记这一类；服务还有五类，前端本片不接）。
  - `export type JobState = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'timed_out';`（六个值，与服务一致）。
  - `export interface JobView { id: string; kind: JobKind; state: JobState; reason: string | null; created_ms: number; started_ms: number | null; finished_ms: number | null; envelope: Envelope<unknown> | null; }`（八键，与 `jobView` 一一对应；`envelope` 不是合法七字段信封时取 null）。
- 新增三个同步导出（照 `getOperation` 的写法，返回 `Promise<HttpReply<JobView>>`）：
  - `export function startJob(kind: JobKind): Promise<HttpReply<JobView>>`
    - 真实分支：`POST /api/v1/jobs`，正文**恰是** `{ kind }`（`runtime-scan` 时正文恰是 `{"kind":"runtime-scan"}`，不许多带键）；时限 **15 秒**。
    - 201 → `{ status: 201, body: okEnvelope<JobView>([], toJobView(rawBody)) }`；其他状态码 → 服务的错误信封**原样交回**（400/404/409/503 都是七字段信封）；正文不是合法作业对象时 `toJobView` 取 null（不抛）。
  - `export function getJob(id: string): Promise<HttpReply<JobView>>`
    - 真实分支：`GET /api/v1/jobs/${encodeURIComponent(id)}`（走 `getRaw`）；时限 **15 秒**；200 → `okEnvelope` 包着 `toJobView`；其他状态码 → 错误信封原样交回（404 的 `没有这个作业` 也在里面）。
  - `export function cancelJob(id: string): Promise<HttpReply<JobView>>`
    - 真实分支：`POST /api/v1/jobs/${encodeURIComponent(id)}/cancel`，正文**恰是** `{}`（服务要求正文是 JSON 对象）；时限 **30 秒**（取消要等服务端等子进程树结束）；200 → `okEnvelope` 包着 `toJobView`；409/404 → 错误信封原样交回。
  - 三个函数的桩分支一律转给 `src/mock/jobs.ts`（`mockStartJob / mockGetJob / mockCancelJob`），返回同一种 `HttpReply<JobView>`。
  - `api.ts` 全文**不许出现**网络接口名（fetch / XMLHttpRequest / EventSource / WebSocket，连注释也不许——t037 S03）。既有导出与既有函数一个都不改。

### 桩（`src/mock/jobs.ts`，新文件）
- 作业表放在模块里（`Map`），**不用计时器**：每次调用都回已兑现的 Promise。
- `?mock=` 五值的语义：
  - `loading`：作业一直是 `running`；取消后落 `cancelled`。
  - `error`：第一次查询就落 `failed`（envelope：`ok:false`、`exit_code:1`、`messages` 一行 `ERROR 扫描失败：内核报错（示意）`）。
  - `data` / `offline` / `empty`：第一次查询 `running`，第二次查询 `succeeded`。
- `succeeded` 的信封：`ok:true`、`exit_code:0`、`data` 是 `{"found":[...],"added":[]}`，`found` 五行（照 `scripts/kit_roles.py` 的形状，program 分别是 pi / claude / codex / opencode / quizs）：
  - `pi`：path `C:/tools/pi/pi.exe`，version `0.1.2`，exit_code 0；
  - `claude-code`：path `C:/tools/npm/claude.cmd`，version `1.0.9`，exit_code 0；
  - `codex`：path `C:/tools/codex/codex.exe`，version `0.5.0`，exit_code 0；
  - `opencode` 与 `quizs`：path / version / exit_code 都是 null（PATH 上没有）。
  - 桩下 `src/mock/runtimes.json` 已登记 pi、claude-code、opencode，所以 data 模式下三种行都会出现：pi 与 claude-code 是「已登记」，codex 给 [登记…]，opencode 与 quizs 是「没找到」（opencode 虽然已登记但 PATH 上没有，没有按钮）。
- 取消：作业没结束 → 回 200 并把状态落 `cancelled`（envelope 为 null）；已经结束 → 回 **409** 的错误信封（`作业已经结束`）。
- 查一个不存在的作业号 → 回 **404** 的错误信封（`没有这个作业`）。
- `src/mock/jobs.ts` 不许出现 `WriteScenario`、不许改 `mock/writes.ts`、不许加 JSON。

### 作业状态模块（`src/jobs/jobStore.ts`，新文件）
- 模块级状态按 kind 分开存（本片只有 `runtime-scan` 一类）：`{ job, t0, createError, creating }`。
  - `job` 是 `JobView | null`；`t0` 是**创建回应到达时**的本地时间戳（毫秒）；`createError` 是创建失败的信封；`creating` 表示创建在途。
- 导出：
  - `ensureJob(kind: JobKind): Promise<JobView | null>`——**没有作业也没有在途的创建**时才创建；在途的创建大家共用（连点两下只发一次 `POST /api/v1/jobs`）；已有作业（排队、运行中或已结束）时直接返回它，不另开一个。
  - `restartJob(kind: JobKind): Promise<JobView | null>`——只在作业已到终态或创建失败时可用：丢掉旧作业，重新创建一个（新的 t0）。
  - `cancelJob(kind: JobKind): Promise<void>`——发 `POST /api/v1/jobs/<id>/cancel`；作业已经结束（409）不当成失败，照下一次查询的结果走。
  - `useJob(kind: JobKind)`——React 钩子（`useSyncExternalStore` 订阅模块状态），返回 `{ job, elapsedSeconds, createError, creating, restart, cancel }`。
  - `resetJobStoreForTests()`——**只给包内测试用的复位导出**（照 `setLiveClientForTests` 的既有做法）：清掉全部 kind 的作业、t0、错误与在途标记，并停掉轮询计时器。包内测试在 `afterEach` 调它，模块状态不在用例之间残留。
- 已用秒数：`elapsedSeconds = Math.floor((Date.now() - t0) / 1000)`；`t0` 存在模块里，关掉对话框再打开接着算（不归零）。
- 查询轮询：
  - **只在有组件挂着、作业又没到终态时**轮询；用 `setTimeout` 链，每 **1000 毫秒**查一次（不用 `setInterval`）。
  - 组件卸载即停（不再发查询请求）；重新打开时**先查一次**，再接着每秒查。
  - 服务端的作业不受前端影响，照跑（关掉对话框不取消作业）。
  - 每次轮询都要让订阅者重渲染（已用秒数每秒走一格）。
- 错误处理：
  - 查询回 **404**（服务重启过、作业已不在表里）→ 按**失败**处理：显示服务的报错原文，并**允许重新扫描**（[重新扫描] 可点）。
  - 查询的其他失败与断线（reject 或 5xx）→ 当作**暂时的**：保留原状态（作业还在跑就继续显示进度），下一秒再查；连续失败不弹错误。
  - 创建失败（非 201、reject）→ 记 `createError`，对话框里显示创建失败的原因，**允许重新扫描**。
- 取消不改变前端的其它行为：取消请求发出去后，作业的终态由下一次查询给出（`cancelled`）。

### 作业进度卡（`src/jobs/JobCard.tsx` 与 `src/jobs/job-card.css`，新文件）
- 组件不进 `components/index.ts`（t008 :105、t009 :155 按字节冻结它）；从 `src/jobs/` 直接 import。
- 形状：`JobCard` 接受 title、作业、已用秒数、错误、`onCancel` 与 children（结果内容）。
- 运行中（`queued` / `running`）：
  - 标题一行；
  - 一条**不确定进度条**（`role="progressbar"`，用 `--tt-primary` 令牌 + CSS 动画；`prefers-reduced-motion: reduce` 时动画停住）；
  - 逐字「已用 N 秒」（N 是整数秒）；
  - 一个 [取消] 按钮（文字逐字「取消」，secondary 样式）。
- 结束后在同一位置显示结果：
  - `succeeded`：渲染 children（结果表）。
  - `failed`：逐字「扫描失败」+ 内核报错原文（`envelope.messages` 逐行照显示）；`messages` 为空时逐字「内核报错（退出码 N）」（`exit_code` 为 null 时逐字「内核报错」）。
  - `cancelled`：中性文字逐字「已取消」。
  - `timed_out`：警告文字逐字「超时（超过 150 秒），已停止」（150 是前端的作业时限表 `runtime-scan` 的值，照抄 `ts/packages/ui/src/jobroutes.ts` 的 `JOB_TIMEOUTS`；前端自己维护这张表，只登记 `runtime-scan: 150`）。
- **不许渲染 `role="status"`**（t010 :513-514、t048 的禁词表）；不许出现禁词（`XMLHttpRequest` / `EventSource` / `WebSocket` / `dangerouslySetInnerHTML` / `innerHTML` / `outerHTML` / `insertAdjacentHTML` / `eval(` / `new Function` / `document.write` / `srcdoc` / `DOMParser` / `matchMedia` / `scrollIntoView` / `ResizeObserver` / `IntersectionObserver`）；CSS 只用既有 `--tt-*` 令牌，不写十六进制颜色与颜色函数，不写内联 `style={{`。

### 扫描对话框（`src/writes/RuntimeScan.tsx` 与 `src/writes/runtime-scan.css`，新文件）
- 内外两层照 T053：外层 `ScanRuntimesAction({ reload })` 只做入口按钮、`useWriteFlow(reload)`、`{open && <内层/>}`、`<WriteFlow flow={flow} />`；内层对话框只在打开时挂载。
- 点 [扫描 PATH] 时：先 `ensureJob('runtime-scan')`（不 await 完再开框），再打开对话框。已有作业时不另建。
- 对话框：标题逐字「扫描 PATH」；body 里放作业卡；脚注放两个按钮：[重新扫描] 与 [关闭]。
  - [重新扫描]：**作业排队或运行时禁用**（对应 §8.4 的「按钮在运行期间禁用」）；作业已结束或创建失败时可点，点了调 `restartJob`。
  - [关闭]：关掉对话框，**不取消作业**（作业照跑，状态在模块里）。
- 打开时读一次 `getRuntimes()`（判断哪些已经登记）：
  - 读成功：某个 runtime 的 `id` 等于适配器名 → 那一行显示逐字「已登记」，不给按钮。
  - 读失败：不显示任何 [登记…]，只显示逐字「读不出已登记的 runtime，暂时不能登记」。
- 结果表（作业 `succeeded` 时放在作业卡的 children 里）：
  - 列头逐字「适配器」「路径」「版本」「操作」（四列）。
  - 行：作业信封 `data.found` 的每一行，次序照服务给的次序（五个适配器各一行）。
  - 路径列：找到的写路径（等宽字体），没找到的写逐字「—」；版本列：找到的写版本，没找到的写逐字「—」。
  - 操作列：找到且**没有**同名 runtime → 一个 [登记…] 按钮（文字逐字「登记…」）；找到但已登记 → 逐字「已登记」；没找到 → 空（没有按钮）。
- [登记…] 的流程：
  - **先关掉对话框**，再 `start({ action: 'runtime.add', args: { runtime: <适配器名>, adapter: <适配器名> } })`（`runtime` 与 `adapter` 都是适配器名，**不带 `command`**）。
  - 走既有 `useWriteFlow`：预览 → 确认框（标题逐字「登记运行时 <适配器名>？」）→ 执行 `POST /api/v1/runtimes/<适配器名>/add`（正文只有 `adapter` 与 `confirmation`）→ 重读整页 → 成功轻提示逐字「已登记运行时 <适配器名>」。
  - 预览的 args 只有 `runtime` 与 `adapter` 两个键；既有文字表与既有分派一个都不改。
- 入口文件（`RuntimesPage.tsx`）里不许出现确认框标题、成功轻提示与内核原文（t023 S11、t041 的禁字表）；逐字文案都放在 `src/writes/RuntimeScan.tsx` 里。

### 边界输入
- 作业还在排队（`queued`）：作业卡显示进度条与「已用 0 秒」（或已过的秒数），[取消] 可点，[重新扫描] 禁用。
- 服务重启过、作业号查不到（404）：显示服务的报错原文（「没有这个作业」那一行），[重新扫描] 可点。
- 查询时断线：保持原状态（继续显示进度），下一秒再查，不弹错误。
- 创建作业失败（400/503/断线）：对话框里显示创建失败的原因，[重新扫描] 可点。
- 扫描结果里某个适配器 PATH 上没有：那一行路径与版本都是「—」，没有按钮（哪怕它已经登记）。
- 已登记的适配器：那一行显示「已登记」，没有 [登记…]。
- 读不出已登记表：所有行都不给 [登记…]，只显示「读不出已登记的 runtime，暂时不能登记」。
- 对话框关着时：DOM 里没有作业卡与结果表（内层组件不挂载），但作业照跑；再打开时接着显示同一个作业。
- 作业已经结束（succeeded）时再点页头的 [扫描 PATH]：只打开对话框显示结果，**不**再发创建请求。

### 并发、取消与状态变化
- 同一时间只有一个扫描作业：`ensureJob` 保证在途的创建共用、已有作业不重开；[重新扫描] 是显式的替换（旧的作业对象丢掉，新作业有新的 t0）。
- 轮询只在组件挂着且作业没终态时进行；卸载即停（`setTimeout` 链要在卸载时清掉，不许留下悬挂的计时器）；重开先查一次再接着每秒查。
- 取消：只发一次 `POST /api/v1/jobs/<id>/cancel`；取消请求在途时 [取消] 按钮禁用（不重复发）。取消后作业的终态由下一次查询给出。
- 写流程（runtime.add）与作业互不干扰：写流程的轮询与作业的轮询是两条独立的链。

### 兼容性（本片推翻的旧断言，逐处写明只改哪一处）
以下文件的这一处要改，**只改这一处**，其余一个字不动：
- `tests/test_gate_t009_baseline.py`
  - `:2877` 的 it 标题里「[扫描 PATH]（SearchIcon）禁用」改成「[扫描 PATH]（SearchIcon）可点」；`:2881` 的 `expect(buttons[0].disabled).toBe(true)` 改成 `toBe(false)`；`:2880` 的按钮次序断言与 `:2883-2885` 照旧。
  - `:2974` 的白名单 `outsideWhitelist(['删除…','手动登记…'])` 里加 `'扫描 PATH'`；`:2970` 的 it 标题与 `:2975-2976` 照旧（还有别的禁用按钮，悬停提示仍是「第二阶段接入」）。
- `tests/test_gate_t041_baseline.py`
  - `:326` 的 `assert '<DisabledAction label="扫描 PATH"' in text, "[扫描 PATH] 应照旧是 DisabledAction（次序不变）"` 改成断言新入口记号（例如 `assert 'ScanRuntimesAction' in text, "[扫描 PATH] 应由 src/writes 的 ScanRuntimesAction 渲染（次序不变）"`）；`:320` 的 docstring 同步改一句；`:325`、`:327-332` 照旧。
  - `:592` 的 it 标题里「[扫描 PATH] 仍禁用」改成「[扫描 PATH] 可点」；`:597` 的 `expect(bs[0].disabled, '[扫描 PATH] 仍禁用（本片不做扫描）').toBe(true)` 改成 `toBe(false)`；`:596` 的次序断言与 `:598-600` 照旧。
- `tests/test_gate_t043_baseline.py`
  - `:459-462` 的记号表里 `'<DisabledAction label="扫描 PATH"'` 这一枚换成新的入口记号（例如 `'ScanRuntimesAction'`）；另三枚（`title="CLI 运行时"`、`AddRuntimeAction`、`还没有登记的 runtime`）照旧；`:453-458` 与 `:463` 照旧。
- `tests/test_gate_t045_baseline.py`
  - `:560` 的正则 `it\('角色页 \d+（[^']*）?、运行时页 5、总览 0'` 里的「运行时页 5」改成「运行时页 4」；
  - `:563` 的 token 表 `("运行时页 5", r"toBe\(5\)")` 改成 `("运行时页 4", r"toBe\(4\)")`；`:564-565` 与 `:553-559` 照旧。
- `tests/test_gate_t049_baseline.py`
  - `:270-271` 的 `if '<DisabledAction label="扫描 PATH"' not in code:` 改成断言新入口记号（例如 `'ScanRuntimesAction' not in code` → problems 里写「[扫描 PATH] 应由 src/writes 的 ScanRuntimesAction 渲染」）；`:272-275` 照旧。
  - `:472` 的 `expect((buttons[0] as HTMLButtonElement).disabled, '[扫描 PATH] 照旧禁用').toBe(true)` 改成 `toBe(false)`；`:471` 的次序断言照旧。
  - `:586` 的同一句改成 `toBe(false)`；`:585` 的次序断言照旧。
- `desktop/web/tests/page-app.test.tsx`
  - `:93` 的 it 标题里「运行时页 5」改成「运行时页 4」；`:98` 的 `expect(disabled().length, '运行时页').toBe(5)` 改成 `toBe(4)`；`:91` 的 describe 标题「写入口个数（过渡）」一字不动（t037 S06 认它）；`:95` 的角色页 6 与 `:100` 的总览 0 照旧。
- `desktop/web/tests/page-runtimes-empty.test.tsx`
  - `:110` 的 `expect((buttons[0] as HTMLButtonElement).disabled, '[扫描 PATH] 照旧禁用').toBe(true)` 改成 `toBe(false)`；`:109` 的按钮次序断言与 `:111` 照旧。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件** `tests/test_gate_t054_baseline.py`（只读；基线上还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/live/transport.ts`**：加 `postRaw<T>`（复用内部 `request`，请求形状照 `post`，正文原样交回，401 照 `getRaw`，拿不到回应时 reject）；**不改** `get` / `post` / `getRaw` / `request` / 六条定稿文案，`new AbortController(`、`setTimeout(`、`credentials: 'same-origin'` 的出现次数与那两处中止判定保持不变。
3. **`desktop/web/src/live/mode.ts`**：`LiveClient` 类型加 `postRaw` 成员；导出集合仍是四个名字；其余一字不改。
4. **`desktop/web/src/api.ts`**：加 `JobKind` / `JobState` / `JobView` 三个类型与 `toJobView`（八键投影，envelope 用 `isEnvelope` 校验，不合法取 null）；加 `startJob` / `getJob` / `cancelJob` 三个导出（真实分支走 `postRaw` / `getRaw`，时限 15 / 15 / 30 秒；桩分支转 `src/mock/jobs.ts`）；既有导出与既有函数一个不改；全文不许出现网络接口名。
5. **新建 `desktop/web/src/mock/jobs.ts`**：模块级作业表 + 五个开关的状态机 + 扫描夹具（五行 found）+ 取消（200 / 409）+ 404；不用计时器。
6. **新建 `desktop/web/src/jobs/jobStore.ts`**：模块级状态（job / t0 / createError / creating）、`ensureJob` / `restartJob` / `cancelJob` / `useJob` / `resetJobStoreForTests`、每秒轮询（卸载即停，重开先查一次）、404 按失败处理、其他失败当暂时的。
7. **新建 `desktop/web/src/jobs/JobCard.tsx` 与 `src/jobs/job-card.css`**：运行中（进度条 + 「已用 N 秒」+ [取消]）与四种结局（succeeded 渲染 children、failed「扫描失败」+ 内核原文、cancelled「已取消」、timed_out「超时（超过 150 秒），已停止」）；不用 `role="status"`；CSS 只用令牌。
8. **新建 `desktop/web/src/writes/RuntimeScan.tsx` 与 `src/writes/runtime-scan.css`**：外层 `ScanRuntimesAction`（按钮逐字「扫描 PATH」、secondary/md、SearchIcon 16×16、一直可点）+ 内层对话框（标题逐字「扫描 PATH」、作业卡、结果表四列、已登记判定、[重新扫描]（运行期间禁用）与 [关闭]、[登记…] 先关框再 `start(runtime.add)`）；`useWriteFlow` 的既有文字表与分派一个不改。
9. **`desktop/web/src/pages/RuntimesPage.tsx`**：换掉页头第一个按钮、删 `DisabledAction` 与 `SearchIcon` 的 import、加 `ScanRuntimesAction` 的 import、改文件头注释；其余一字不改。
10. **逐处改旧断言**（照「兼容性」一节，逐条只改那一处）：
    - `tests/test_gate_t009_baseline.py`（:2877 的标题、:2881、:2974 的白名单）；
    - `tests/test_gate_t041_baseline.py`（:320 的 docstring、:326、:592 的标题、:597）；
    - `tests/test_gate_t043_baseline.py`（:459-462 的记号表一枚）；
    - `tests/test_gate_t045_baseline.py`（:560 的正则、:563 的 token 表）；
    - `tests/test_gate_t049_baseline.py`（:270-271、:472、:586）；
    - `desktop/web/tests/page-app.test.tsx`（:93 的标题、:98 的数）与 `desktop/web/tests/page-runtimes-empty.test.tsx`（:110）。
    - 改完把仍钉着「扫描 PATH …禁用」「运行时页 5」「toBe(5)」的旧口径再搜一遍（关键字：`扫描 PATH`、`DisabledAction`、`运行时页 5`、`toBe\(5\)`），确认没有漏网的旧断言。
11. **新增三份包内测试**（不许 `skip`/`only`/`todo`——`tests/test_gate_t002_baseline.py:1496` 会扫全部 `*.test.*`；测真实实现，不把业务逻辑抄一份进测试；不 mock 被测组件）：
    - `desktop/web/tests/jobs-api.test.ts`：用 `setLiveClientForTests` 注入假客户端（照 `desktop/web/tests/live-api.test.ts` 的写法），断言
      (a) `startJob('runtime-scan')` 发 `POST /api/v1/jobs`，正文**恰是** `{"kind":"runtime-scan"}`（键数 1、值逐字）；
      (b) `getJob(id)` 发 `GET /api/v1/jobs/<id>`；
      (c) `cancelJob(id)` 发 `POST /api/v1/jobs/<id>/cancel`，正文恰是 `{}`；
      (d) 201/200 → 成功信封里 data 是八键作业视图；404/409 → 错误信封原样交回（状态码与 messages 逐字）。
    - `desktop/web/tests/jobs-store.test.ts`：`afterEach` 调 `resetJobStoreForTests()`；断言
      (a) 连点两次 `ensureJob` 只发一次创建请求；
      (b) 已有作业时 `ensureJob` 不再发创建请求；
      (c) `restartJob` 在作业未终态时不可用（要么按合同语义拒绝、要么不新建），终态后可用且发新的创建请求；
      (d) 轮询：挂载时每秒查一次（用假计时器或真实等待，照现有测试的写法），卸载后不再查；
      (e) 查询回 404 → 按失败处理并允许重新扫描；查询 reject → 状态保留、下一秒再查。
    - `desktop/web/tests/jobs-scan-page.test.tsx`：渲染 `ScanRuntimesAction`（或挂整页 App），用假客户端与桩模式各测一遍，断言
      (a) 点 [扫描 PATH] 发创建请求（正文恰是 `{"kind":"runtime-scan"}`），随后每秒发 `GET /api/v1/jobs/<id>`；
      (b) 运行中显示「已用 N 秒」并随时间增加，[取消] 发 `POST /api/v1/jobs/<id>/cancel`；
      (c) 四种结局的文字（succeeded 显示结果表；failed 显示「扫描失败」与内核原文；cancelled 显示「已取消」；timed_out 显示「超时（超过 150 秒），已停止」）；
      (d) 结果表三种行：已登记（无按钮）、[登记…]（有按钮）、没找到（路径与版本是「—」，无按钮）；
      (e) 点 [登记…] → 关掉扫描对话框 → 确认框打开（标题逐字「登记运行时 codex？」）→ 预览的 args 只有 `runtime` 与 `adapter` → 执行请求 `POST /api/v1/runtimes/codex/add` 的正文只有 `adapter` 与 `confirmation` → 成功后 `reload` 被调用；
      (f) 关掉对话框再打开：接着显示同一个作业，**不再发创建请求**；
      (g) 桩模式下 data / loading / error 三种开关的表现（loading 一直 running；error 落 failed）。
12. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → V04 → R01**（本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
13. 写执行报告；遇到合同未定义的行为（例如门禁端交付的 `tests/test_gate_t054_baseline.py` 与合同的「写法钉死」有实质冲突），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t054_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test -- tests/jobs-api.test.ts tests/jobs-store.test.ts tests/jobs-scan-page.test.tsx` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py -q` · cwd：仓库根 · 超时：3120s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：页头 [扫描 PATH] 是可点的 secondary/md 按钮（一直可点、带 SearchIcon、页头次序不变），点开「扫描 PATH」对话框；RuntimesPage 的其余部分一字不改（并行三读、失败判定、children、`reload={reload}`、空态、Quizs 一块、页头说明）；目的：这一片只加一个入口，不许顺手改运行时页的读法与只读部分；证据：V01、V02、G01、R01、scope。
- D02：作业接口接上了——`postRaw` 走传输层唯一的 `request`（请求形状与 `post` 相同、正文原样交回、401 先 reauth、断线 reject），`startJob` / `getJob` / `cancelJob` 的路径、正文（创建恰 `{"kind":"runtime-scan"}`、取消恰 `{}`）与时限（15/15/30 秒）就位，桩的五个开关行为就位；目的：作业对象不是信封，不能被归成信封，也不许另起一条请求代码；证据：V01、V02、G01、R01。
- D03：作业状态在页面之外的模块里（`src/jobs/jobStore.ts`）：在途的创建共用、已有作业不重开、每秒轮询、卸载即停、重开先查一次、已用秒数从创建回应到达时算起并存在模块里、404 按失败处理且允许重新扫描、其他失败当暂时的；目的：关掉对话框再打开要接着看同一个作业，页面上不留第二份状态；证据：V01、V02、G01。
- D04：作业卡按 §7.17 显示：运行中有不确定进度条、「已用 N 秒」、[取消]；四种结局的文字（succeeded 显示结果、failed「扫描失败」+ 内核原文、cancelled「已取消」、timed_out「超时（超过 150 秒），已停止」）；不用 `role="status"`；目的：长作业要有进度与结局，不许只显示一个空转圈；证据：V01、V02、G01。
- D05：结果表列出五个适配器各一行（列头「适配器」「路径」「版本」「操作」），路径与版本逐字（或「—」）；已登记的行显示「已登记」且无按钮；找到且没登记的行给 [登记…]；没找到的行没有按钮；读不出已登记表时不给 [登记…] 并显示「读不出已登记的 runtime，暂时不能登记」；目的：逐个登记，不做「登记全部」；证据：V01、V02、G01。
- D06：[登记…] 先关掉对话框再走既有 `runtime.add` 的预览 → 确认 → 执行 → 重读：预览的 args 只有 `runtime` 与 `adapter`（都是适配器名、不带 command），执行 `POST /api/v1/runtimes/<适配器名>/add` 的正文只有 `adapter` 与 `confirmation`，成功轻提示是既有的「已登记运行时 <适配器名>」，写完整页重读；目的：登记要能过内核的确认与幂等核对，不新造一条写流程；证据：V01、V02、G01、R01。
- D07：新增 `desktop/web/tests/jobs-api.test.ts`、`desktop/web/tests/jobs-store.test.ts`、`desktop/web/tests/jobs-scan-page.test.tsx`，覆盖 D02–D06 点名的每一项（含「连点两下只发一次创建请求」「关掉再开不再发创建请求」「查询 404 按失败处理」「取消发 cancel」「四种结局」「[登记…] 的预览 args 与执行正文」），测真实实现，不许 `skip`/`only`/`todo`；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、V02、review。
- D08：旧断言逐处改到位：t009（:2877/:2881/:2974）、t041（:320/:326/:592/:597）、t043（:459-462 的一枚）、t045（:560/:563 两处）、t049（:270-271/:472/:586）、`page-app.test.tsx`（:93/:98）、`page-runtimes-empty.test.tsx`（:110）——每处只改上面写明的那一处，其余一个字不动；目的：这些断言钉着「灰按钮 + 禁用数 5」，本片必然推翻，改法不许顺手改别的断言；证据：G01、R01、V02、scope。
- D09：所有修改都在允许集合内（可改 11 个文件、可新增 9 个文件），没有碰 forbidden_paths（`tests/test_gate_t054_*.py`、其余 44 份门禁基准、`components/**`、`shell/**`、`readonly1/**`、`readonly2/**`、其余七个页面、`mock/*.json` 与 `mock/writes.ts`/`quizs.ts`/`hub-roles.ts`、既有的写流程文件与三份既有 CSS、`live-api.test.ts` 与 `live-transport.test.ts`、`package.json` 与锁文件、`ts/packages/ui/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope、review。
- D10：`npm test`、`npm run typecheck`、`npm run build` 全过，52 份既有门禁基准照旧通过；目的：不能为了加一个入口把别处弄坏；证据：V02、V03、V04、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `jobroutes.ts` 的正文校验已经不是「键恰好」、`jobView` 的八键变了、`transport.ts` 的 `request` 形状变了、`useWriteFlow` 的 `runtime.add` 分派没了、`Dialog` 关着时不再 `return null`、`mock/runtimes.json` 的已登记名单变了），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `components/**`、`shell/**`、`readonly1/**`、既有写流程文件、其余门禁基准、`package.json` 与锁文件、`ts/packages/ui/**`）。
- 门禁端交付的 `tests/test_gate_t054_baseline.py` 与本合同的「写法钉死」出现实质冲突（例如它要求按钮文字或对话框标题换一种写法、要求创建正文多带键、要求按钮不可点）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 运行时页的禁用按钮数改完不是 4（与合同与站主任务书说的 5→4 对不上）：停下并报告实际数字，不要顺手改别的断言来凑。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t054-desktop-web-runtime-scan` 汇总，含返工版本；累计已用 0 次 → 本版留 3 次）
- max_wall_seconds_per_attempt: 10800
- max_wall_seconds_total: 32400（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 32400 秒 ≥ 本版 2 × 10800 = 21600 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 30 分钟；transport + mode + api.ts 40 分钟；mock/jobs.ts 25 分钟；jobStore.ts 35 分钟；JobCard 与 CSS 30 分钟；RuntimeScan.tsx 与 CSS 40 分钟；RuntimesPage 5 分钟；逐处改旧断言 25 分钟；三份包内测试 45 分钟；必要检查（G01、V01、V02、V03、V04、R01；R01 约 45–60 分钟、可分批跑）70 分钟；最终报告 5 分钟；总计约 345 分钟，单轮时限 10800 秒（180 分钟）——总量 32400 秒覆盖本版与返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
