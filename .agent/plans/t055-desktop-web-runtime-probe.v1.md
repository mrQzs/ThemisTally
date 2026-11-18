# TASK: t055-desktop-web-runtime-probe

<!-- 合同 v1：T055「[探测] 与 [模型]：运行时表每行接上作业接口」。
     规划报告：.agent/mailbox/tasks/T055-1-plan/report.md；站主任务书：.agent/mailbox/tasks/T055/brief.md。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片把 T054 的作业客户端（按 kind 存的模块级状态）泛化成「按 kind 存槽、槽里记 runtime」，
     并把运行时表两行的 [探测]、[模型] 从灰变可点。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: c92d1db1564b10052de20b2bdf497ebb852a5074
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
运行时表「已登记」里的每一行接上作业接口：来源不是 missing 的行，[探测] 从灰变可点，点了起一个 `runtime-probe` 作业（`POST /api/v1/jobs`，正文恰是 `{"kind":"runtime-probe","runtime":"<该行 ID>"}`），对话框里用作业进度卡显示进度，结束后显示探测结果（版本、命令来源、命令；pi 再加缺少的参数与支持的思考级别），`ok` 为假的 failed 也照样显示探测到的东西并点明没过的那一项；pi 行的 [模型] 同样可点，起一个 `models` 作业，结束后在对话框里列出 provider、model、是否在允许列表三列与「模型列表来自 pi --list-models，不调用模型」那一句说明。同一类作业同一时间只有一个：在跑时别的行同类按钮禁用并写明正在忙哪一个，本行重开对话框看到的是同一个作业，结束后可以重新探测、重新列。[扫描 PATH] 与运行时页其余部分一个字不变。

## Non-goals
- 不改本机服务与内核（`ts/packages/ui/**`、`scripts/**` 一个字不改）：`runtime-probe`、`models` 两类作业的路由、正文校验、时限与命令拼法都已就位。
- 不做 [运行就绪检查]、[核验]（同一套作业客户端，另排）；版本列照旧「—」。
- 不做凭据录入、资格认证、续期按钮（M6，等用户定）；不做方案表空态的 [保存当前为方案…] 按钮（画布有，另排）。
- 不改 `desktop/web/src/components/**`（`components/index.ts` 按字节冻结）、`desktop/web/src/shell/**`；新组件不进 `components/index.ts`。
- 不改 `desktop/web/src/writes/RuntimeScan.tsx`、`desktop/web/src/writes/runtime-scan.css`（[扫描 PATH] 一个字不变，按字节验收）；不改既有的写流程文件（`useWriteFlow.ts`、`WriteConfirmDialog.tsx`、`writeOutcome.ts`、`snapshots.ts`、`useLivePreview.ts`、`RuntimeForm.tsx`、`runtimeRules.ts`、`profileRules.ts`、`hubChangeLines.ts`、`HubBindForm.tsx`、`RoleBindForm.tsx`、`ProfileForm.tsx`、`PresetSaveForm.tsx` 与它们的 CSS）——本片不走写流程。
- 不改 `desktop/web/src/pages/readonly1/runtimes-logic.ts`（`canProbe` / `canModels` 规则一字不改）、`desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts`（按字节冻结）、`desktop/web/src/pages/RuntimesPage.tsx`、`desktop/web/src/mock/writes.ts`、`desktop/web/src/mock/quizs.ts`、`desktop/web/src/mock/hub-roles.ts`、`desktop/web/src/mock/*.json`（src/mock 不加 JSON）；`desktop/web/src/pages` 顶层不加 `*Page.tsx`。
- 不改 `desktop/web/src/live/**`（transport 的 `postRaw` 与 mode.ts 的四个导出照旧）、`desktop/web/src/jobs/job-card.css`。
- 不改 T054 的三份包内测试（`desktop/web/tests/jobs-api.test.ts`、`jobs-store.test.ts`、`jobs-scan-page.test.tsx`）、`desktop/web/tests/live-api.test.ts`、`live-transport.test.ts`、`live-mode.test.ts`——本片的新用例放新文件。
- 不改 `desktop/web/src/mock/runtimes.json`、`desktop/web/tests/page-runtimes-empty.test.tsx`。
- 不新增依赖、不改锁文件（`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字不动）。

## Repository facts
以下事实都在本回合的工作目录里逐条读过（行号按基线 f768e08b）。

### 本机服务（不改，只照它的规则写前端）
- `ts/packages/ui/src/jobroutes.ts`
  - `:48-55` `JOB_TIMEOUTS`：`runtime-scan` 150、`runtime-probe` 150、`models` 120（doctor 600、doctor-record 600、search 180）。
  - `:66-72` `SCHEMA`：`runtime-scan` 的 required 与 optional 都是空数组（正文只有 `kind` 一个键）；`runtime-probe` 与 `models` 的 required 恰是 `["runtime"]`、optional 空。
  - `:142-170` `validateJob`：正文必须是 JSON 对象；`kind` 在六个之内；**键恰好**（多一个键回 400「请求体含有未知键」）；`runtime` 的值要过 `TASK_ID_RE`（`pi`、`claude-code`、`codex`、`custom` 这类 ID 都合格）。
  - `:174-190` `buildArgv`：`runtime-probe` → `["config","runtime","probe",<runtime>,"--json"]`；`models` → `["config","models",<runtime>,"--json"]`。
  - `:210-240` 作业落定：内核退出码 0 是 succeeded，否则 failed（reason "exit"），**信封照样带着内核的 data**；`messages` 只留 stderr 里以 `ERROR` 或 `WARN` 开头的行。

### 内核（不改，只照它的输出形状写前端）
- `scripts/kit_roles.py`
  - `:949-975` `_runtime_probe --json`：data 是 `{runtime, adapter, source, command, version_exit_code, version}`，pi 另有 `help: {exit_code, missing_flags, thinking_levels}`，末位还有 `ok`（布尔）。`command` 是数组（已脱敏）或 null；`version` 是字符串（没有输出时是空串）；`source` 取 `env` / `local` / `path` / `missing`。`ok` 为假时退出码 1，作业因此落 failed，但 data 里仍有探测到的东西；没登记、找不到命令时是内核报错（**没有 data**）。
  - `:986-1017` `_models --json`：只有 pi 支持（其他适配器内核报错，没有 data）；data 是 `{runtime, models: [{provider, model, allowed}], allowed_executors_set}`；`allowed` 为 true / false / null（null 表示没设允许列表，即「不限制」）；疑似凭据的行 provider 与 model 都是 `<redacted>`。
  - `:777-788` `_probe_version` 与 `_probe_help`：`version` 取 `--version` 输出的第一行（没有输出是空串）；`missing_flags` 是必填参数里 `--help` 没写的那些（外加 `--no-context-files`）。

### 前端现状
- `desktop/web/src/api.ts`
  - `:154` `export type JobKind = 'runtime-scan';`（本片扩成三类）。
  - `:773-785` `startJob(kind)`：真实分支 `client.postRaw<unknown>('/api/v1/jobs', { kind }, 15)`，201 才算建成；桩分支 `mockStartJob(kind)`。`:787` `getJob(id)`（`getRaw`，15 秒）；`:801` `cancelJob(id)`（`postRaw`，30 秒，正文恰 `{}`）。
  - 全文不许出现网络接口名（fetch / XMLHttpRequest / EventSource / WebSocket，连注释也不许——t037 S03）。
- `desktop/web/src/jobs/jobStore.ts`（T054）
  - `:17` `KINDS = ['runtime-scan']`；`:19` 三个 `Record<JobKind, …>`（snaps / subscribers / inflight）。
  - `:52-77` `doCreate`：在途的创建记在 `inflight` 里共用；201 且正文是合法作业才落 `job` 与 `t0`（`t0 = Date.now()`），否则记 `createError`。
  - `:79-85` `ensureJob(kind)`：没有作业也没有在途创建时才创建；已有作业直接返回。
  - `:87-93` `restartJob(kind)`：只在作业已终态或创建失败时新建。
  - `:95-104` `cancelJob(kind)`：只发一次 cancel。
  - `:129-140` `scheduleNext`：订阅数为 0 不排；作业已终态不排；否则 `setTimeout(…, 1000)` 后查一次。**没有作业时也会排**（这是本片要改的一处）。
  - `:142-156` `startPolling` / `stopPolling`；`:158-190` `useJob(kind)`：`useSyncExternalStore` 订阅，`elapsedSeconds = Math.floor((Date.now() - t0) / 1000)`，effect 里 `subscribers[kind]++` 并 `startPolling`、卸载时 `--` 并 `stopPolling`。
  - `:192-201` `resetJobStoreForTests()`：清全部 kind 的状态与计时器。
- `desktop/web/src/jobs/JobCard.tsx`（T054）
  - `:11` `const JOB_TIMEOUT_SECONDS: Record<string, number> = { 'runtime-scan': 150 };`
  - `:41`、`:61` 失败标题逐字「扫描失败」；`:47`、`:53` 进度条 aria-label 逐字「扫描进行中」；`:66` 超时文字模板「超时（超过 ${…} 秒），已停止」。
  - props：`title / job / elapsedSeconds / createError / onCancel / children`。
- `desktop/web/src/mock/jobs.ts`（T054，119 行）：模块级作业表 + `?mock=` 五开关的状态机，不用计时器、不引 JSON；只实现 `runtime-scan`；`mockStartJob` 对别的 kind 回 400。
- `desktop/web/src/writes/RuntimeScan.tsx`（T054）：内外两层的样板——外层 `ScanRuntimesAction`（点入口先 `ensureJob('runtime-scan')` 再 `setOpen(true)`），内层 `RuntimeScanDialog`（`useJob('runtime-scan')`、`{open && <内层/>}`、JobCard、脚注 [重新扫描] 与 [关闭]）。
- `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`：`:75-76` 两个 `DisabledAction label="探测"` / `label="模型"`（`variant="ghost"`、`size="sm"`），规则来自 `runtimes-logic.ts` 的 `canProbe(source)`（来源不是 missing）与 `canModels(adapter, source)`（adapter 是 pi 且来源不是 missing）；`:103` [运行就绪检查] 仍禁用。
- `desktop/web/src/pages/readonly1/runtimes-logic.ts`：`:49-56` `canProbe` / `canModels`；`:18-23` 四个来源标签 `env→环境变量 / local→本机文件 / path→PATH / missing→找不到`。
- `desktop/web/src/shell/DisabledAction.tsx`：`:10`、`:18` `reason` 属性（缺省「第二阶段接入」），用 Tooltip 包一个 disabled 的 Button。
- `desktop/web/src/mock/runtimes.json`：已登记 `pi`（source `local`、adapter `pi`）、`claude-code`（source `path`）、`opencode`（source `missing`）。**桩下运行时页的禁用按钮恰 4 个**：pi 的 [探测] 与 [模型]、claude-code 的 [探测]、[运行就绪检查]；本片之后只剩 1 个（[运行就绪检查]）。
- `desktop/web/package.json`：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`、`npm run build` = `tsc --noEmit && vite build`；`tsconfig.json` 的 include 只有 `["src","vite.config.ts"]`（`tests/` 不过 `tsc --noEmit`）。

### 门禁与既有测试的核查结论（本片**必然**要改的那几处，逐条读过）
- `tests/test_gate_t009_baseline.py`
  - `:2854` it 标题末尾「[探测]、[模型] 禁用」；`:2861` `expect(b.disabled, textOf(b) + ' 应禁用').toBe(true)`；`:2857`、`:2867`、`:2870`、`:2873` 的按钮文字数组 `['探测','模型','删除…']` 等照旧过（按钮文字要恰是「探测」「模型」，不带「…」）。
  - `:2933-2938` `outsideWhitelist(extra)` 返回的是**可点**且不在白名单里的按钮文字；`:2939-2951` `disabledButtons()` 与 `tooltipTexts()` 只看禁用按钮（所以 [探测]、[模型] 变可点后，「第二阶段接入」的悬停断言不受影响）。
  - `:2970` it 标题「…可用按钮只有刷新、T022 接上的 [删除…] 与 T041 接上的 [手动登记…]」；`:2974` `expect(outsideWhitelist(['删除…','手动登记…','扫描 PATH'])).toEqual([])`。
- `tests/test_gate_t023_baseline.py`
  - `:297-298`（`test_s08_runtimesview_delete_wired` 里）两行 `assert re.search(r'<DisabledAction label="探测"', text)` 与 `…label="模型"…`。
  - `:783` it 标题「运行时 [删除…] 三行都可点（ghost sm），行内其余按钮禁用；标题与摘要」；`:793` `expect(b.disabled, '非 [删除…] 的行内按钮仍禁用（' + textOf(b) + '）').toBe(true)`；`:805-811` [运行就绪检查] 仍禁用照旧。
- `tests/test_gate_t045_baseline.py`
  - `:560` `if not re.search(r"it\('角色页 \d+（[^']*）?、运行时页 4、总览 0'", app_text) and "'角色页 11'" not in app_text:`；`:563` `for token, pat in (("运行时页 4", r"toBe\(4\)"), ("总览 0", r"toBe\(0\)")):`。
- `tests/test_gate_t054_baseline.py`
  - `:717` `if "export type JobKind = 'runtime-scan';" not in code:`（api.ts 的逐字记号）。
  - `:740` `("startJob", ("postRaw",), (JOBS_PATH_LIT, "{ kind }", "mockStartJob("), (r"\b15\b",))`——**创建正文的字面 `{ kind }` 要留在 startJob 的函数体里**。
  - S01（RuntimeScan.tsx）：`ensureJob('runtime-scan')` / `restartJob('runtime-scan')` / `useJob('runtime-scan')` 都是**一个参数**；只许 `import './runtime-scan.css'`；`{open && <`；`JobCard` 从 `'../jobs/JobCard'` 直接引。
  - S02（jobStore.ts）：五个 `export function`（ensureJob / restartJob / cancelJob / useJob / resetJobStoreForTests）**都要在**；`setTimeout(` 在、`setInterval(` 不在、`1000`、`clearTimeout`；已用秒数逐字 `Math.floor((Date.now() - t0) / 1000)`；`useSyncExternalStore`；从 `'../api'` 引 `startJob(` / `getJob(` / `cancelJob(`。
  - S03（JobCard.tsx / job-card.css）：props 里要有 title / onCancel / children；`role="progressbar"`；[取消]；「已用 ${…} 秒」；**「扫描失败」与「已取消」逐字在**；「超时（超过 ${…} 秒），已停止」模板在；150 的来源是整句或 `runtime-scan: 150` 的时限表（只认 JobCard / jobStore / RuntimeScan 三个文件）；只许 `import './job-card.css'`。
  - S04（api.ts）：`export function startJob(` / `getJob(` / `cancelJob(`；函数体里有 `postRaw` / `getRaw` / `mockStartJob(` / `mockGetJob(` / `mockCancelJob(`；时限 15 / 15 / 30 的数字在函数体里。
  - S05（mock/jobs.ts）：三个导出；不用计时器；不引 JSON；记号 `'runtime-scan'` / `'running'` / `'succeeded'` / `'failed'` / `'cancelled'`；文案「ERROR 扫描失败：内核报错（示意）」「作业已经结束」「没有这个作业」；五行扫描夹具的 path 与 version 逐字；`found` 与 `added` 在。
  - 探针 `:1014-1015`：扫描的创建正文**恰一个键**（`toEqual({ kind: 'runtime-scan' })` 且键数 1）；`:141` RuntimesPage 那一行逐字。
- `tests/test_gate_t010_baseline.py`：`:107-110` 禁用词与禁用调用（扫 src 全文，含注释与字符串）；`:513-514` 不许渲染 `role="status"`；`:100-104` src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 `*Page.tsx`。
- `tests/test_gate_t043_baseline.py`：`:656-672` `page-runtimes.test.tsx` 恰 4 处 `<RuntimesView`、`writes-remove.test.tsx` 恰 1 处（**新用例放新文件**）；`:490-495` RuntimesView 里照旧有 `label="运行就绪检查"`、`runtime.remove`、`useWriteFlow`、两节标题；`:497` 与 t009 :3506（D13）readonly1 下的视图从 `../../api` **只许 import type**——作业调用走 jobStore 或 src/writes 下的组件，视图只放入口组件。
- `tests/test_gate_t048_baseline.py`：`:131-137` 按字节冻结 `desktop/web/src/mock/quizs.ts`、`desktop/web/src/mock/hub-roles.ts`、`desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts`、`desktop/web/tests/live-api.test.ts`、`desktop/web/package.json`、`desktop/web/package-lock.json`。
- 包内测试：`desktop/web/tests/page-app.test.tsx:91-98`（describe 标题「写入口个数（过渡）」一字不动；`:93` it 标题「…运行时页 4…」、`:98` `toBe(4)`）；`desktop/web/tests/page-runtimes.test.tsx:101` it 标题「操作规则：[删除…] 可点，其余禁用」、`:109` `expect(b.disabled, …).toBe(text(b) === '删除…' ? false : true)`；`desktop/web/tests/page-runtimes-empty.test.tsx:108-112` 只查页头三个按钮（本片不改）；`desktop/web/tests/writes-remove.test.tsx:285-298` 入口文件禁字表（不许出现「删除方案」「删除 profile」「删除运行时」「回滚配置」「已删除」「已回滚」等）。

### 工具链与锁文件
- `desktop/web` 用 npm（vitest 2.1.8、TypeScript 5.6.3、React 18.3.1；内核核实：desktop/web 已装的 vitest 是 2.1.8、react 是 18.3.1，`useSyncExternalStore` 是 React 18 的内置 hook）；仓库门禁用 `python -m pytest`。
- `dependency_changes: forbidden`：`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字都不许动（t048 还按字节冻结了前两个）。

### 基线检查
- 合同端只读，没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 合同检查在基线上的结果由内核在执行之前跑过（基线检查记录）：本片门禁在基线上应当失败（断言失败，不是收集失败）、既有门禁基准照旧通过；执行端不必再跑一遍整套测试。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/jobs/jobStore.ts
  - desktop/web/src/jobs/JobCard.tsx
  - desktop/web/src/mock/jobs.ts
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/page-runtimes.test.tsx
  - tests/test_gate_t009_baseline.py
  - tests/test_gate_t023_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t054_baseline.py
- allowed_new_files:
  - desktop/web/src/writes/RuntimeProbe.tsx
  - desktop/web/src/writes/runtime-probe.css
  - desktop/web/src/writes/RuntimeModels.tsx
  - desktop/web/src/writes/runtime-models.css
  - desktop/web/tests/jobs-probe-page.test.tsx
  - desktop/web/tests/jobs-models-page.test.tsx
  - desktop/web/tests/jobs-store-runtime.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t055_*.py
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
  - tests/test_gate_t041_baseline.py
  - tests/test_gate_t042_baseline.py
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t044_baseline.py
  - tests/test_gate_t046_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t048_baseline.py
  - tests/test_gate_t049_baseline.py
  - tests/test_gate_t050_baseline.py
  - tests/test_gate_t051_baseline.py
  - tests/test_gate_t052_baseline.py
  - tests/test_gate_t053_baseline.py
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/live/**
  - desktop/web/src/jobs/job-card.css
  - desktop/web/src/writes/RuntimeScan.tsx
  - desktop/web/src/writes/runtime-scan.css
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/RuntimeForm.tsx
  - desktop/web/src/writes/runtimeRules.ts
  - desktop/web/src/writes/profileRules.ts
  - desktop/web/src/writes/hubChangeLines.ts
  - desktop/web/src/writes/HubBindForm.tsx
  - desktop/web/src/writes/RoleBindForm.tsx
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/PresetSaveForm.tsx
  - desktop/web/src/writes/runtime-form.css
  - desktop/web/src/writes/hub-bind-form.css
  - desktop/web/src/writes/profile-form.css
  - desktop/web/src/writes/write-flow.css
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/readonly1/runtimes-logic.ts
  - desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts
  - desktop/web/src/pages/readonly1/runtimes-styles.css
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
  - desktop/web/tests/jobs-api.test.ts
  - desktop/web/tests/jobs-store.test.ts
  - desktop/web/tests/jobs-scan-page.test.tsx
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/page-runtimes-empty.test.tsx
  - desktop/web/tests/writes-remove.test.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - ts/package.json
  - ts/bun.lock
  - ts/packages/ui/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 作业客户端（`desktop/web/src/jobs/jobStore.ts`）
- 槽的形状不变（T054 的 `StoreState`）再加一个字段：`runtime: string | null`——槽里那个作业是哪个 runtime 的（扫描是 null）。`KINDS` 扩成三类：`['runtime-scan', 'runtime-probe', 'models']`；`snaps` / `subscribers` / `inflight` 三张 `Record<JobKind, …>` 同步扩成三类；`resetJobStoreForTests()` 清三类。
- **每类一个槽**（不按 runtime 各存一份）：同一类同一时间只有一个作业，这是 §8.4「同一类作业同时只能有一个」的落点。
- 导出（一律 `export function`，不写 `export async function`——t054 S02/S04 按 `export function` 认）：
  - `ensureJob(kind: JobKind, runtime?: string): Promise<JobView | null>`
  - `restartJob(kind: JobKind, runtime?: string): Promise<JobView | null>`
  - `useJob(kind: JobKind, runtime?: string): { job, elapsedSeconds, createError, creating, restart, cancel }`
  - `cancelJob(kind: JobKind): Promise<void>`（取消该 kind 当前的作业）
  - `useBusyRuntime(kind: JobKind): string | null`——**新增**：订阅「这一类正忙于哪个 runtime」。
  - `resetJobStoreForTests(): void`（既有导出，签名不变）
- 规则（**runtime 省略或为空串时，扫描那一支的行为与现在逐字一致**）：
  - `ensureJob(kind, runtime)`：
    - 槽里的作业是**本 runtime** 的（含在途创建）→ 直接返回，不另建；
    - 槽里是**别的 runtime** 的作业且**未到终态**（或创建在途）→ **不建**，返回 null（界面那头本来就灰着，store 再挡一道）；
    - 槽里是别的 runtime 的**终态**作业、或创建失败、或空 → 新建，替换掉旧的（新的 `t0`），槽里记上这个 runtime。
  - `restartJob(kind, runtime)`：只在作业已终态或创建失败时可用；带 runtime 时要求槽里作业的 runtime 相同（或槽空 / 创建失败）才新建，否则不新建。
  - `useJob(kind, runtime)`：订阅与轮询按 kind；`runtime` 只用来认「这是哪个 runtime 的视图」；返回值集合不变（T054 的包内测试照旧用）。
  - `useBusyRuntime(kind)`：返回该 kind 当前**未到终态**的作业所占的 runtime id（没有这样的作业时是 null）。快照是原始值，引用稳定；**在 effect 里也算订阅者**（`subscribers[kind]++`），这样对话框关着时作业不再被查询、别的行一直灰着的问题不会出现。
- 轮询时序（本片**唯一**的轮询改动，写死）：
  - `scheduleNext(kind)`：订阅数为 0 → 不排；作业已终态 → 不排；**没有作业（`job == null`）→ 不排计时器**（不整页常驻时空转）；否则 `setTimeout(…, 1000)` 后查一次（仍是 setTimeout 链，不用 setInterval）。
  - `startPolling` 照旧：只在有组件挂着时起；重开先查一次。
  - **对话框关着时作业照查到底**：行内入口（每一行的 [探测] / [模型] 按钮）挂载时通过 `useBusyRuntime` 订阅该 kind，因此订阅数不为 0，轮询继续；离开页面（没有订阅者）即停，回来时先查一次。
  - 改完这一处之后，T054 的既有三份包内测试（`jobs-store.test.ts`、`jobs-api.test.ts`、`jobs-scan-page.test.tsx`）与 t054 的探针**原样照过**：一个参数的 `ensureJob('runtime-scan')`、`resetJobStoreForTests()`、创建正文 `toEqual({ kind: 'runtime-scan' })`、「卸载即停」「重开先查一次」「已用秒数走格」。

### api.ts（`desktop/web/src/api.ts`）
- `export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';`（逐字；t054 :717 的门禁记号按「兼容性」一节改）。
- `startJob(kind: JobKind, runtime?: string): Promise<HttpReply<JobView>>`：
  - 真实分支仍是 `client.postRaw<unknown>('/api/v1/jobs', <正文>, 15)`；**扫描那一支的正文逐字是 `{ kind }`**（正文恰一个键，t054 :740 的记号与探针的「键数 1」都靠它）；
  - 两类新作业的正文逐字是 `{ kind, runtime }`（runtime 是该行的 id；服务要扁平正文，未知键回 400，所以正文里不许出现别的键，也不许出现 `runtime: undefined`）；
  - 201 才算建成；其它状态码的服务错误信封原样交回；桩分支 `mockStartJob(kind, runtime)`。
  - 时限 15 的字面量照旧写在函数体里（t054 S04）。
- `getJob(id)` 与 `cancelJob(id)` 一个字不改。
- api.ts 全文不许出现网络接口名（连注释也不许）；既有导出与既有函数一个不改。

### 作业进度卡（`desktop/web/src/jobs/JobCard.tsx`）
- props 增加两个**可选**属性：`kind?: JobKind`（缺省 `'runtime-scan'`，所以 `RuntimeScan.tsx` 一个字不改）与 `failedDetail?: ReactNode`（failed 时给出「没过的那一项」）。
- 三张按 kind 查的表都写在 `JobCard.tsx` 里（时限照 `jobroutes.ts` 的 `JOB_TIMEOUTS`）：

| kind | 失败标题 | 进度条 aria-label | 超时秒数 |
|---|---|---|---|
| `runtime-scan` | 扫描失败 | 扫描进行中 | 150 |
| `runtime-probe` | 探测失败 | 探测进行中 | 150 |
| `models` | 列模型失败 | 列模型进行中 | 120 |

- 「扫描失败」「扫描进行中」「已取消」「超时（超过 ${…} 秒），已停止」这些字面**逐字留在 JobCard.tsx 里**（t054 S03 钉着）；`runtime-scan: 150` 这张时限表也留在 JobCard.tsx 里（t054 S03 只认 JobCard / jobStore / RuntimeScan 三个文件）。
- failed 的显示：先给 `failedDetail`（有的话），再给内核报错原文（`envelope.messages` 逐行；空时按退出码给「内核报错（退出码 N）」、`exit_code` 为 null 时给「内核报错」）。
- 不许渲染 `role="status"`；不许出现禁词；CSS（`job-card.css`）一个字不改。

### 入口与对话框（`src/writes/RuntimeProbe.tsx` + `runtime-probe.css`，`src/writes/RuntimeModels.tsx` + `runtime-models.css`）
- 两个新文件各带一个**行内入口组件**与一个**对话框**（照 T054 的内外两层：外层只放入口按钮与状态，对话框只在打开时挂载；`{open && <内层/>}`）。
- **入口组件放在 `src/writes/`（不放 readonly1）**：视图（readonly1）从 `../../api` 只许 import type，作业调用走 jobStore 或 src/writes 下的组件（t009 D13、t043 :497）。
- 每个新组件**必须 import 自己的样式表**（`import './runtime-probe.css';` / `import './runtime-models.css';`，放在组件 import 之后，照仓库里「组件带自己的样式表」的既有写法）；样式表只用既有 `--tt-*` 令牌，不写十六进制颜色与颜色函数，不写内联 `style={{`；CSS 里除 0 与 1px 外的 px 字面量同一行带出处注释。
- 入口按钮：
  - 文字逐字「探测」/「模型」（**不带「…」**——t009 :2857、:2867、:2870、:2873 的按钮文字数组照旧靠这个）；
    `variant="ghost"`、`size="sm"`（照旧那两处 DisabledAction 的口径）。
  - 本类**不忙**，或**忙于本行** → 可点的 Button；点它先 `ensureJob(kind, runtime)`（不 await 完再开框），再打开对话框。
  - 本类**忙于别的行** → `DisabledAction`，`label` 逐字「探测」/「模型」，`reason` 逐字「正在探测 <id>」/「正在列 <id> 的模型」。
- 对话框：
  - 标题逐字「探测 <id>」/「模型 <id>」（`<id>` 是该行的 runtime id）。
  - body 里放 `<JobCard kind="runtime-probe" …>` / `<JobCard kind="models" …>`（JobCard 从 `'../jobs/JobCard'` 直接引，不进 `components/index.ts`）。
  - 脚注：[重新探测] / [重新列出]（作业终态或创建失败时才可点，点了调 `restartJob(kind, runtime)`）与 [关闭]（关掉对话框，**不取消作业**）。
- 探测结果（作业 `succeeded` 或 `failed` 但**有 data** 时显示）：
  - 「有 data」的判定：`envelope.data` 是对象，且 `data.runtime` 是字符串、`data.version_exit_code` 是数字。
  - 版本：`data.version` 是字符串；空串写逐字「版本未知」。
  - 命令来源：`data.source` 映射成四个标签 `env→环境变量 / local→本机文件 / path→PATH / missing→找不到`（与运行时表一致；这张小表写在新文件里，**runtimes-logic.ts 不改**）。
  - 命令：`data.command` 是数组时用空格连起来（等宽显示），是 null 时写逐字「—」。
  - pi（`data.help` 在）再加两行：缺少的参数（`missing_flags` 为空写逐字「无」，否则用「、」连起来）与思考级别（`thinking_levels` 用「、」连起来；为空写逐字「无」）。
  - `ok` 为假时：**同一个结果块照旧显示**，另外点明没过的那一项（措辞写死）：
    - `version_exit_code` 不是 0 → 逐字「版本命令退出码 <N>」；
    - `help.exit_code` 不是 0 → 逐字「<id> --help 退出码 <N>」；
    - `missing_flags` 非空 → 逐字「pi 缺少参数：<a、b>」。
    这几行由 `failedDetail` 传给作业卡（放在内核报错原文之前）。
  - **没有 data** 的 failed（内核报错：没登记、找不到命令、`--list-models` 退出码非 0 等）→ 只显示作业卡默认的内核报错原文（`messages` 逐行），**不显示结果块**。
- 列模型结果（作业 `succeeded` 时显示；`failed` 且有 data 时同样显示 data）：
  - 表上方逐字一行「模型列表来自 pi --list-models，不调用模型」。
  - 表格三列，列头逐字「provider」「model」「是否在允许列表」；行照 `data.models` 的次序；`allowed` 为 true 写逐字「是」、false 写逐字「否」、null 写逐字「不限制」；`<redacted>` 原样显示。
  - `data.models` 是空数组 → 表上方那一行照旧，下面写逐字「没有列出模型」。
- 逐字文案都放在 `src/writes/` 的新文件里；入口文件（`runtimes-RuntimesView.tsx`）里不许出现确认框标题、成功轻提示与内核原文（t023 S11 的禁字表；`writes-remove.test.tsx` 的禁字表同样不许出现「删除方案」「删除 profile」「删除运行时」「回滚配置」「已删除」「已回滚」）。

### 桩（`desktop/web/src/mock/jobs.ts`）
- 现有 `runtime-scan` 那一路**一字不改**（t054 S05 与它的探针照旧过）。
- 新增两类（同样不用计时器、不引 JSON、每次调用回已兑现的 Promise）：
  - `mockStartJob(kind, runtime?)`：kind 是 `runtime-probe` 或 `models` 时，**缺 runtime 或 runtime 是空串 → 回 400**（错误信封一行）；`runtime-scan` 那一支照旧。
  - 五个开关的语义照旧：`loading` 一直 running；`error` 第一次查询就 failed（**没有 data**，envelope 的 messages 是一行示意原文）；`data` / `offline` / `empty` 第一次查询 running、第二次 succeeded。
  - 探测夹具（`data` / `offline` / `empty` 三个开关用同一份形状）：
    - **默认取法（照规划报告 §3.6，合同采纳）**：同一 runtime 的探测作业**第奇数次 ok 为假、第偶数次正常**——奇数次那份：`ok:false`、`version_exit_code:1`、`version:''`、`help: {exit_code:1, missing_flags:['--no-context-files'], thinking_levels:[]}`，作业因此落 **failed 但带 data**；偶数次那份：`ok:true`、`version_exit_code:0`、`version:'0.1.2'`、`help: {exit_code:0, missing_flags:[], thinking_levels:['off','minimal','low','medium','high','xhigh','max']}`，作业落 succeeded。
    - 非 pi 的 runtime 给不带 `help` 的正常结果（`ok:true`、`version_exit_code:0`、`version:'1.0.9'`）。
  - 列模型夹具：`data.models` 四行，其中**一行 `allowed:false`**（其余 `allowed:true`），`allowed_executors_set: true`；`provider` 与 `model` 用示意值（其中一行写 `<redacted>`）。
- 桩里不许出现 `WriteScenario`、不许引 `.json`、不许加计时器；`desktop/web/src/mock/writes.ts` 一个字不改。

### 运行时视图（`desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`）
- 两处 `DisabledAction label="探测"` / `label="模型"` 换成新入口组件（`canProbe(rt.source)` 与 `canModels(rt.adapter, rt.source)` 的规则照旧，`runtimes-logic.ts` 一字不改）。
- 其余一字不改：已登记表的其余列（版本列照旧「—」）、[删除…]（走既有 `runtime.remove` 写流程）、[运行就绪检查]（仍禁用，悬停仍是「第二阶段接入」）、Quizs 一块、`useWriteFlow(reload)`、两节标题、空态。
- 文件头那句「操作全部禁用」的注释改成新的事实（探测与模型走作业接口，删除与就绪检查照旧）。

### 边界输入
- 同类作业在跑、别的行点同类按钮：按钮是禁用的，悬停逐字「正在探测 <id>」/「正在列 <id> 的模型」；**即使绕过界面直接调 `ensureJob(别的 runtime)`，store 也不建第二个作业**（返回 null）。
- 同类作业在跑、本行再点：按钮可点，重开对话框看到的是**同一个作业**（不另发创建请求）。
- 作业已结束（succeeded / failed / cancelled / timed_out）：[重新探测] / [重新列出] 可点，点了换一个作业（新的 `t0`）。
- 创建失败（400 / 503 / 断线）：对话框里显示创建失败的原因（内核报错原文），[重新探测] / [重新列出] 可点。
- 查询回 404（服务重启过）：照 T054 的做法——错误信封并进 `job.envelope`、状态落 failed，作业卡显示内核报错原文。
- 探测 `ok` 为假（failed 但有 data）：显示结果块 **并**点明没过的那一项；**不是**「只有错误原文」。
- 探测没有 data（failed，内核报错）：只显示内核报错原文。
- 列模型 `models` 是空数组：显示「模型列表来自 pi --list-models，不调用模型」与逐字「没有列出模型」。
- 行的来源是 missing：`canProbe` 为假 → 这一行**没有** [探测] 按钮（照旧）；adapter 不是 pi → 没有 [模型] 按钮（照旧）。
- 对话框关着时：DOM 里没有作业卡与结果表（内层不挂载），但作业照跑；再打开时接着显示同一个作业。
- 作业超时（timed_out）：作业卡逐字「超时（超过 150 秒），已停止」（探测）/「超时（超过 120 秒），已停止」（列模型）。

### 并发、取消与状态变化
- 同一类只许一个在跑（§8.4）：store 的槽 + 界面的禁用两头都挡。行内入口的禁用是「这一类正忙于别的 runtime」，本行不 busy。
- 轮询：setTimeout 链、每 1000 毫秒一次、卸载即停（`clearTimeout`）、重开先查一次；**没有作业时不排计时器**（本片新增的一条，避免整页常驻时空转）。
- 取消：只发一次 `POST /api/v1/jobs/<id>/cancel`；取消请求在途时 [取消] 禁用；作业的终态由下一次查询给出。
- 两个对话框互不干扰：探测与列模型是两个 kind、两个槽、两条轮询链；[扫描 PATH] 是第三个 kind，**照旧一个字不变**。
- 写流程（`runtime.remove`）与作业互不干扰。

### 写法钉死（与本片门禁基准文件逐条对表）
本片门禁由门禁端交付（`tests/test_gate_t055_baseline.py`），它不在当前基线里，由门禁那一版合同产出并集成；基线上它应当失败（断言失败，不是收集失败）。执行端第 1 步要读门禁文件并与这一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
- `desktop/web/src/api.ts`：`export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';`；`export function startJob(` / `getJob(` / `cancelJob(`；`startJob` 的函数体里有 `postRaw`、`{ kind }`（字面）、`mockStartJob(`、时限 `15`；`JobState` 六个值与 `JobView` 八键照旧。
- `desktop/web/src/jobs/jobStore.ts`：五个既有 `export function`（ensureJob / restartJob / cancelJob / useJob / resetJobStoreForTests）**都在**；`setTimeout(` 在、`setInterval(` 不在、`1000`、`clearTimeout`；已用秒数逐字 `Math.floor((Date.now() - t0) / 1000)`；`useSyncExternalStore`；从 `'../api'` 引 `startJob(` / `getJob(` / `cancelJob(`；`JobKind` 在。
- `desktop/web/src/jobs/JobCard.tsx`：`export function JobCard(`；props 里有 title / onCancel / children；`role="progressbar"`；[取消]；「已用 ${…} 秒」；「扫描失败」「已取消」「超时（超过 ${…} 秒），已停止」；**只许 `import './job-card.css';`**；三张按 kind 的表里的「扫描失败」「扫描进行中」与 `runtime-scan: 150` 在。
- `desktop/web/src/mock/jobs.ts`：三个既有导出；不用计时器；不引 JSON；`'runtime-scan'` 在；既有扫描夹具与文案一字不改。
- `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`：`<DisabledAction label="探测"` 与 `<DisabledAction label="模型"` **不在**；`'runtime.remove'`、`args: { runtime` 在；`reload?:` 与 `useWriteFlow(` 在；`label="运行就绪检查"` 在；两节标题在。
- `desktop/web/src/writes/RuntimeProbe.tsx` 与 `RuntimeModels.tsx`：各自的样式表 import 都在；`{open && <`；`ensureJob(` / `restartJob(` / `useJob(` 用的是两类新 kind；`JobCard` 从 `'../jobs/JobCard'` 引；逐字文案在（见「Behavior contract」各节）。

### 兼容性（本片推翻的旧断言，逐处写明只改哪一处）
以下文件的这一处要改，**只改这一处**，其余一个字不动：
- `tests/test_gate_t023_baseline.py`
  - `:297-298`（`test_s08_runtimesview_delete_wired` 里）：`assert re.search(r'<DisabledAction label="探测"', text), "[探测] 照旧是 DisabledAction"` → `assert not re.search(r'<DisabledAction label="探测"', text), "[探测] 不应再是 DisabledAction"`；`assert re.search(r'<DisabledAction label="模型"', text), "[模型] 照旧是 DisabledAction"` → `assert not re.search(r'<DisabledAction label="模型"', text), "[模型] 不应再是 DisabledAction"`（**只加 not、把文案里的「照旧」改成「不应再是」**；`:296`、`:299-303` 照旧）。
  - `:783` 的 it 标题：「运行时 [删除…] 三行都可点（ghost sm），行内其余按钮禁用；标题与摘要」→「运行时 [删除…] 三行都可点（ghost sm），行内其余按钮也可点；标题与摘要」（只改「禁用」为「也可点」）。
  - `:793`：`expect(b.disabled, '非 [删除…] 的行内按钮仍禁用（' + textOf(b) + '）').toBe(true);` → `expect(b.disabled, '非 [删除…] 的行内按钮也可点（' + textOf(b) + '）').toBe(false);`（`toBe(true)` 改成 `toBe(false)`，提示语里的「仍禁用」改成「也可点」）。`:794-806` 照旧（[删除…] 可点、确认框标题与摘要）。
- `tests/test_gate_t009_baseline.py`
  - `:2854` 的 it 标题末尾：「…[探测]、[模型] 禁用」→「…[探测]、[模型] 可点」（只改这两个字）。
  - `:2861`：`ops.filter((b) => textOf(b) !== '删除…').forEach((b) => expect(b.disabled, textOf(b) + ' 应禁用').toBe(true));` → 同一句的 `toBe(true)` 改成 `toBe(false)`、提示语「应禁用」改成「应可点」；`:2857`、`:2867`、`:2870`、`:2873` 的按钮文字数组照旧。
  - `:2970` 的 it 标题：「运行时页：仍禁用的写入口悬停出「第二阶段接入」；可用按钮只有刷新、T022 接上的 [删除…] 与 T041 接上的 [手动登记…]」→「运行时页：仍禁用的写入口悬停出「第二阶段接入」；可用按钮只有刷新、T022 接上的 [删除…]、T041 接上的 [手动登记…] 与 T055 接上的 [探测]、[模型]」（只加最后一段；`仍禁用` 的说法照旧，因为 [运行就绪检查] 仍禁用）。
  - `:2974`：`expect(outsideWhitelist(['删除…','手动登记…','扫描 PATH'])).toEqual([]);` → `expect(outsideWhitelist(['删除…','手动登记…','扫描 PATH', '探测', '模型'])).toEqual([]);`（白名单里加「探测」「模型」）；`:2975-2976`（`disabledButtons().length` 大于 0、悬停仍是「第二阶段接入」）照旧。
- `tests/test_gate_t045_baseline.py`
  - `:560`：`if not re.search(r"it\('角色页 \d+（[^']*）?、运行时页 4、总览 0'", app_text) and "'角色页 11'" not in app_text:` → 正则里的「运行时页 4」改成「运行时页 1」（其余照旧）。
  - `:563`：`for token, pat in (("运行时页 4", r"toBe\(4\)"), ("总览 0", r"toBe\(0\)")):` → `for token, pat in (("运行时页 1", r"toBe\(1\)"), ("总览 0", r"toBe\(0\)")):`；`:553-559`、`:564-565` 照旧。
- `tests/test_gate_t054_baseline.py`
  - `:717`：`if "export type JobKind = 'runtime-scan';" not in code:` → `if "export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';" not in code:`（problems 里的文案跟着改成「api.ts 的 JobKind 应登记三类」）；`:718` 的 `JobState` 检查、`:740` 的 `("{ kind }", …)` 记号（靠扫描那一支照旧过）、`:543-548`（RuntimeScan 的三个一个参数的调用）、`:599-621`（jobStore 的五个导出等）、`:648-650`（JobCard 的「扫描失败」「已取消」）、`:659`（150 的来源）、`:777-811`（mock/jobs.ts 的记号）、`:141`（RuntimesPage 那一行）**都照旧，不许改**。
- `desktop/web/tests/page-app.test.tsx`
  - `:93` 的 it 标题里「运行时页 4」改成「运行时页 1」；`:98` 的 `expect(disabled().length, '运行时页').toBe(4)` 改成 `toBe(1)`；`:91` 的 describe 标题「写入口个数（过渡）」一字不动（t037 S06、t045 认它）；`:95` 的角色页 6 与 `:100` 的总览 0 照旧。
- `desktop/web/tests/page-runtimes.test.tsx`
  - `:101` 的 it 标题「操作规则：[删除…] 可点，其余禁用」→「操作规则：[删除…] 与 [探测]、[模型] 都可点」；
  - `:109`：`expect(b.disabled, `${text(b)} 的禁用状态`).toBe(text(b) === '删除…' ? false : true);` → `expect(b.disabled, `${text(b)} 的禁用状态`).toBe(false);`（本片之后行内按钮都可点）；`:104` 的按钮文字数组（`['探测','模型','删除…']` 等）照旧。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件** `tests/test_gate_t055_baseline.py`（只读；本回合的基线上它还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/api.ts`**：`JobKind` 扩成三类（逐字 `export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';`）；`startJob(kind, runtime?)` 的扫描那一支照旧发 `{ kind }`、两类新作业发 `{ kind, runtime }`；`mockStartJob(kind, runtime)` 透传 runtime；`getJob` / `cancelJob` 与其余导出照旧；全文不许出现网络接口名。
3. **`desktop/web/src/jobs/jobStore.ts`**：`KINDS` 扩成三类；槽里加 `runtime`；`ensureJob` / `restartJob` / `useJob` 加可选 runtime 参数；新增 `useBusyRuntime(kind)`（订阅者也算订阅者）；`scheduleNext` 加一条「**没有作业就不排计时器**」；其余（T054 的公式、setTimeout 链、404 并进 envelope、五个既有导出）照旧。
4. **`desktop/web/src/jobs/JobCard.tsx`**：`kind` 可选（缺省 `'runtime-scan'`）+ `failedDetail` 可选；三张按 kind 的表（失败标题 / aria-label / 超时秒数 150·150·120）；扫描那一支的字面与 `runtime-scan: 150` 留在文件里；`job-card.css` 一个字不改。
5. **`desktop/web/src/mock/jobs.ts`**：加两类新作业与夹具（缺 runtime 回 400；探测奇偶两份；列模型四行含一行不在允许列表）；`runtime-scan` 那一路一字不改；不用计时器、不引 JSON。
6. **新建 `desktop/web/src/writes/RuntimeProbe.tsx` 与 `runtime-probe.css`**：行内入口（可点 / 忙时 DisabledAction 带 reason）+ 对话框（标题「探测 <id>」、JobCard kind="runtime-probe"、结果块与没过项、脚注 [重新探测] 与 [关闭]）；`import './runtime-probe.css';` 在位。
7. **新建 `desktop/web/src/writes/RuntimeModels.tsx` 与 `runtime-models.css`**：行内入口 + 对话框（标题「模型 <id>」、说明句「模型列表来自 pi --list-models，不调用模型」、三列表格与「是 / 否 / 不限制」、脚注 [重新列出] 与 [关闭]）；`import './runtime-models.css';` 在位。
8. **`desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`**：两处 DisabledAction 换成新入口组件；文件头注释改成新的事实；其余一字不改。
9. **逐处改旧断言**（照「兼容性」一节，逐条只改那一处）：`tests/test_gate_t023_baseline.py`（:297-298、:783、:793）、`tests/test_gate_t009_baseline.py`（:2854、:2861、:2970、:2974）、`tests/test_gate_t045_baseline.py`（:560、:563）、`tests/test_gate_t054_baseline.py`（:717）、`desktop/web/tests/page-app.test.tsx`（:93、:98）、`desktop/web/tests/page-runtimes.test.tsx`（:101、:109）；改完把仍钉着旧口径的地方再搜一遍（关键字：`DisabledAction label="探测"`、`运行时页 4`、`toBe\(4\)`、`JobKind = 'runtime-scan'`），确认没有漏网的旧断言。
10. **新增三份包内测试**（不许 `skip`/`only`/`todo`——`tests/test_gate_t002_baseline.py:1496` 会扫全部 `*.test.*`；测真实实现，不把业务逻辑抄一份进测试；不 mock 被测组件）：
    - `desktop/web/tests/jobs-store-runtime.test.ts`：`afterEach` 调 `resetJobStoreForTests()`；断言
      (a) `ensureJob('runtime-probe','pi')` 发创建请求（正文恰 `{"kind":"runtime-probe","runtime":"pi"}`）；
      (b) 同类忙着时 `ensureJob('runtime-probe','claude-code')` **不建**（返回 null、不发请求）；
      (c) 同一 runtime 重开 `ensureJob` 不另建；
      (d) 作业终态后别的 runtime 能建（旧的被替换）；
      (e) 没有作业时**不排计时器**（不每秒发查询）；
      (f) 对话框卸载后靠行内入口的订阅仍查到终态（订阅数不为 0）；
      (g) `restartJob` 在作业未终态时不新建，终态后可新建。
    - `desktop/web/tests/jobs-probe-page.test.tsx`：渲染入口组件（真模式注入假客户端 + 桩模式各一遍），断言
      (a) 点 [探测] 发 `POST /api/v1/jobs`，正文恰 `{"kind":"runtime-probe","runtime":"<该行 ID>"}`，之后每秒查同一个作业号；
      (b) 成功的结果：版本、命令来源、命令；pi 的缺少的参数与思考级别；
      (c) `ok` 为假的 failed：照样显示 data，并点明没过的那一项；
      (d) 没有 data 的 failed：显示内核报错原文、不显示结果块；
      (e) 取消与超时（150 秒）的文字；
      (f) 关掉对话框再打开：同一个作业、不再发创建请求；
      (g) 桩模式下 loading / error 两种开关的表现。
    - `desktop/web/tests/jobs-models-page.test.tsx`：断言
      (a) 点 [模型] 发 `POST /api/v1/jobs`，正文恰 `{"kind":"models","runtime":"<ID>"}`；
      (b) 结果表三列与「是 / 否 / 不限制」；
      (c) 表上方逐字「模型列表来自 pi --list-models，不调用模型」；
      (d) 超时 120 秒的文字；
      (e) 同一类在跑时**别的行**同类按钮禁用、悬停逐字「正在探测 <id>」/「正在列 <id> 的模型」，本行重开不再发创建请求，结束后能重新开。
11. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → V04 → R01**（本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
12. 写执行报告；遇到合同未定义的行为（例如门禁端交付的 `tests/test_gate_t055_baseline.py` 与合同的「写法钉死」有实质冲突），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t055_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test -- tests/jobs-store-runtime.test.ts tests/jobs-probe-page.test.tsx tests/jobs-models-page.test.tsx` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py -q` · cwd：仓库根 · 超时：3180s · 期望退出码：0 · 输出须匹配：`\d+ passed`

上面每条检查的「输出须匹配」为什么在门禁机上成立（逐条说明；门禁检查与回归检查都用 pytest 的 `-q`，成功时最后一行是「N passed」，与已验收的 T054 合同 `.agent/plans/t054-desktop-web-runtime-scan.v3.md` 里同一种调用配同一个匹配，已在门禁机上成立过）：

- 前端那两条 vitest 检查是 `npm test`（= `vitest run`，desktop/web 已装 vitest 2.1.8——内核核实表里记着版本），vitest 2.x 成功时打印「Tests  N passed」；同一个匹配在 T054 合同的同一种调用上验收通过过。只跑指定文件的那一条另加 `不得出现 No test files found`（vitest 找不到文件时会这么写，防止「0 个用例也是绿色」）。
- 类型检查那条是 `npm run typecheck`（= `tsc --noEmit`），成功时无输出、退出码 0；这条不写输出须匹配（没有输出可匹配），只看退出码。
- 构建那条是 `npm run build`（= `tsc --noEmit && vite build`），vite 5.4.11 成功时打印「✓ built in …」；同一个匹配在 T054 合同里验收通过过。

## Definition of done
- D01：运行时表有 [探测] 的行，[探测] 是可点的 ghost/sm 按钮（文字逐字「探测」，不带「…」），点它起 `runtime-probe` 作业（正文恰 `{"kind":"runtime-probe","runtime":"<该行 ID>"}`），对话框标题逐字「探测 <id>」，作业卡显示进度、已用秒数与 [取消]；有 [模型] 的行（pi）同样可点，标题逐字「模型 <id>」，正文恰 `{"kind":"models","runtime":"<ID>"}`；目的：配模型前先知道这个运行时能不能用、它列得出哪些模型；证据：V01、V02、G01、R01、scope。
- D02：探测结果在对话框里显示版本、命令来源、命令，pi 再加缺少的参数与思考级别；`ok` 为假的 failed 照样显示这些并点明没过的那一项（版本命令退出码 / --help 退出码 / 缺少参数）；没有 data 的 failed 只显示内核报错原文；目的：探测失败也要看得见探测到了什么；证据：V01、V02、G01。
- D03：列模型结果是一张三列表格（provider、model、是否在允许列表：true 写「是」、false 写「否」、null 写「不限制」），表上方逐字「模型列表来自 pi --list-models，不调用模型」；目的：不调用模型也能知道有哪些模型可用；证据：V01、V02、G01。
- D04：同一类作业同一时间只有一个——别的行同类按钮禁用并悬停写明正在忙哪一个（逐字「正在探测 <id>」/「正在列 <id> 的模型」），store 也不建第二个作业；本行重开对话框看到的是同一个作业、不另发创建请求；结束后能重新探测、重新列；目的：§8.4「同一类作业同时只能有一个」；证据：V01、V02、G01。
- D05：作业客户端按 kind 存槽、槽里记 runtime（每类一个槽）；行内入口的订阅也算订阅者（对话框关着时作业照查到底、别的行不会一直灰着）；**没有作业时不排 1 秒计时器**；T054 的既有三份包内测试（jobs-store / jobs-api / jobs-scan-page）与 t054 探针原样照过；目的：长作业的状态在模块里一份，页面不留第二份状态，也不许整页常驻时空转；证据：V01、V02、G01、R01。
- D06：作业卡按 kind 取失败标题（扫描失败 / 探测失败 / 列模型失败）、进度条 aria-label（扫描进行中 / 探测进行中 / 列模型进行中）与超时秒数（150 / 150 / 120）；扫描那一支的字面与行为一个字不变（`RuntimeScan.tsx` 与 `job-card.css` 按字节未改）；目的：三类作业共用一张卡，扫描照旧；证据：V01、V02、G01、R01、scope。
- D07：[扫描 PATH] 一个字不变（`desktop/web/src/writes/RuntimeScan.tsx` 与 `runtime-scan.css` 未改，既有扫描用例照过），运行时页其余部分（已登记表的其余列、版本列照旧「—」、[删除…]、[运行就绪检查] 仍禁用、Quizs 一块、空态）不变；目的：这一片只加两个入口，不许顺手改别处；证据：V02、R01、scope。
- D08：桩里两类新作业与夹具就位（缺 runtime 回 400；探测同一 runtime 奇数次 ok 为假、偶数次正常；列模型四行含一行不在允许列表），`runtime-scan` 那一路一字不改；目的：没有真服务时也能看到两种结局；证据：V01、V02、G01。
- D09：新增 `desktop/web/tests/jobs-store-runtime.test.ts`、`jobs-probe-page.test.tsx`、`jobs-models-page.test.tsx`，覆盖 D02–D05 点名的每一项（含「同类忙时别的 runtime 不建」「同 runtime 重开不另建」「终态后别的 runtime 能建」「没有作业时没有计时器」「关掉对话框靠行内订阅仍查到终态」「有 data 与没有 data 两支」「取消与超时」「别的行禁用与悬停文字」），测真实实现，不许 `skip`/`only`/`todo`；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、V02、review。
- D10：旧断言逐处改到位：t023（:297-298、:783、:793）、t009（:2854、:2861、:2970、:2974）、t045（:560、:563）、t054（:717）、`desktop/web/tests/page-app.test.tsx`（:93、:98）、`desktop/web/tests/page-runtimes.test.tsx`（:101、:109）——每处只改上面写明的那一处，其余一个字不动；目的：这些断言钉着「灰按钮 + 禁用数 4」，本片必然推翻，改法不许顺手改别的断言；证据：G01、R01、V02、scope。
- D11：所有修改都在允许集合内（可改 11 个文件、可新增 7 个文件），没有碰 forbidden_paths（`tests/test_gate_t055_*.py`、其余 44 份门禁基准、`components/**`、`shell/**`、`live/**`、`job-card.css`、`RuntimeScan.tsx` 与 `runtime-scan.css`、既有的写流程文件与 CSS、`runtimes-logic.ts`、`RuntimesPage.tsx`、`mock/*.json` 与 `mock/writes.ts`/`quizs.ts`/`hub-roles.ts`、T054 的三份包内测试与 `live-*.test.ts`、`package.json` 与锁文件、`ts/packages/ui/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope、review。
- D12：`npm test`、`npm run typecheck`、`npm run build` 全过，既有门禁基准照旧通过；目的：不能为了加两个入口把别处弄坏；证据：V02、V03、V04、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `jobroutes.ts` 的正文校验已经不是「键恰好」、`JOB_TIMEOUTS` 的两个数变了、`kit_roles.py` 的探测或列模型 data 形状变了、`jobStore.ts` 的 `scheduleNext` 已经不是「没有作业也排计时器」的写法、`JobCard.tsx` 的字面变了、`runtimes-logic.ts` 的 `canProbe`/`canModels` 变了、mock 的三行 runtime 变了），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `components/**`、`shell/**`、`live/**`、`RuntimeScan.tsx`、`runtimes-logic.ts`、既有写流程文件、其余门禁基准、`package.json` 与锁文件、`ts/packages/ui/**`）。
- 门禁端交付的 `tests/test_gate_t055_baseline.py` 与本合同的「写法钉死」出现实质冲突（例如它要求按钮文字或对话框标题换一种写法、要求创建正文多带键、要求按钮不可点、要求某个导出写成别的形状、要求作业客户端按 runtime 各存一份）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 运行时页的禁用按钮数改完不是 1（与合同与站主任务书说的 4→1 对不上）：停下并报告实际数字，不要顺手改别的断言来凑。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t055-desktop-web-runtime-probe` 汇总，含返工版本；累计已用 0 次 → 本版留 3 次）
- max_wall_seconds_per_attempt: 10800
- max_wall_seconds_total: 32400（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 32400 秒 ≥ 本版 2 × 10800 = 21600 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 30 分钟；api.ts 与 jobStore.ts 35 分钟；JobCard.tsx 15 分钟；mock/jobs.ts 25 分钟；RuntimeProbe.tsx 与 CSS 45 分钟；RuntimeModels.tsx 与 CSS 30 分钟；RuntimesView 10 分钟；逐处改旧断言 25 分钟；三份包内测试 55 分钟；必要检查（G01、V01、V02、V03、V04、R01；R01 约 45–60 分钟、可分批跑）70 分钟；最终报告 5 分钟；总计约 345 分钟，单轮时限 10800 秒（180 分钟）——总量 32400 秒覆盖本版与返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
