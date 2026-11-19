# TASK: t057-desktop-web-runtime-record

<!-- 合同 v1：T057「[核验]：就绪检查一节加「按版本记录核验」，结果卡写明版本记录」。
     规划报告：.agent/mailbox/tasks/T057-1-plan/report.md；站主任务书：.agent/mailbox/tasks/T057/brief.md。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片只接界面：doctor-record 这一类作业服务端已有（ts/packages/ui/src/jobroutes.ts），前端加一类作业、
     一个文本框与一个 [核验] 按钮，结果块标题写「版本记录 <record>」。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: f796d69c9f2957d9c18590e0fcfb37847e308a3a
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
「CLI 运行时」页「就绪检查」一节在 [运行就绪检查] 后面接一组「按版本记录核验」：一个文本框（值形如 `<task-id>.v<N>`）与一个 [核验] 按钮（同一行，§6.5 :636）。点 [核验] 时值合 PLAN_KEY_RE 就起一个 `doctor-record` 长作业（`POST /api/v1/jobs`，正文恰 `{"kind":"doctor-record","record":"<值>"}`），这一节里用作业进度卡显示进度（失败标题「核验失败」、进度条 aria-label「核验进行中」、超时 600 秒），可以取消；值不合格时不发请求，就地提示「写成 <task-id>.v<N>，例如 logs-cat.v2」。作业结束后：有 data（succeeded，或没就绪落 failed 带 data）时显示一块，标题「版本记录 <那一行的 record>」（缺键写「—」），下面是 T056 的就绪卡（同一种卡头、八个键值行、问题、说明行）；没有 data 的失败显示内核报错原文；取消、超时照作业卡。作业排队或运行时 [核验] 禁用，空闲时一直可点（运行时页禁用按钮数照旧是 0）；[运行就绪检查] 与 [核验] 是两类作业，各管各的禁用，可以同时跑；离开这一页再回来看到的是同一个作业，不另开。

## Non-goals
- 不改本机服务与内核（`ts/packages/**`、`scripts/**` 一个字不改）：doctor-record 的路由、正文校验（`record` 必填且合 PLAN_KEY_RE）、时限 600 与命令 `config doctor --record=<task>.vN --json` 都已就位。
- 不做版本记录的下拉（服务没有列出版本记录的读接口）；这一节用文本框。
- 不做整页空态时看不到「就绪检查」一节的问题（会牵动九份旧门禁，另排一片）。
- 不做凭据录入、就绪卡里「去凭据页录入」的链接；不删 `RuntimeDoctor.tsx` 里没人用的 `DOCTOR_CARD_LABELS`（T056 门禁 S06 要的记号，等清旧门禁那一批一起删）。
- 不改视图 `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`（一个字不改）。
- 不改 `ensureJob` / `restartJob` / `useJob` / `startJob` / `cancelJob` 的签名；不加新 prop 到 JobCard。
- 不做文本框回车提交、预填、记住上次的值；不 trim 输入值。
- 不新增依赖、不改锁文件（`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字不动）。

## Repository facts
以下事实都在本回合的工作目录里逐条读过（行号按基线 a7168a13）。

### 本机服务（不改，只照它的规则写前端）
- `ts/packages/ui/src/jobroutes.ts`
  - `:22` `PLAN_KEY_RE = /^[a-z0-9][a-z0-9-]{0,63}\.v[1-9][0-9]{0,3}$/u`（前端照抄这一份）。
  - `:36` `JOB_KINDS` 六类，含 `doctor-record`；`:48-55` `JOB_TIMEOUTS` 里 `doctor-record` 是 **600**。
  - `:66` `SCHEMA["doctor-record"] = { required: ["record"], optional: [] }`——正文键**恰好**是 `kind` 与 `record`（多一个键回 400「请求体含有未知键」，少一个键回 400「请求体缺少必填键」）。
  - `:150-160` `validateJob`：`record` 不合 PLAN_KEY_RE 回 400「record 不合法」，**提示固定、不回显请求里的值**。
  - `:176-178` `buildArgv`：`doctor-record` → `["config","doctor","--record=<值>","--json"]`。
  - `:233-240` 作业落定：内核退出码 0 是 succeeded，否则 failed（reason "exit"），**信封照样带着内核的 data**。
  - `:250-253` `messages` 只留 stderr 里以 `ERROR` 或 `WARN` 开头的行（内核那句「还没有版本记录」以 `ERROR:` 开头，所以进得了 messages）。

### 内核（不改，只照它的输出形状写前端）
- `ts/packages/config/src/roles-probe.ts`
  - `:292-307` `recordReadiness`：值不合 PLAN_KEY_RE 抛 `ConfigError`；**没有版本记录时抛 `ConfigError`（`:300`「<值> 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor」）→ 退出码 1、标准输出为空 → 作业落 failed、没有 data**；有记录时那一行是 `headlessReadiness` 的无头行（`:225-289`，`mode` 固定写 `headless`）**再加一个 `record` 键**（`:305`）。
  - `:339-357` `doctor`：给了 `--record` 时 `roles` 数组**只有那一行**（其余角色不进数组）；data 是 `{ready, roles: [...]}`，没就绪时退出码 1（作业落 failed，但 data 完整）。
- `ts/packages/dispatcher/src/executor.ts:46-47` `bindingRecordRel(taskId, version)` = `.agent/runs/<task>/binding-v<N>.json`（`record` 键的值就是它）。
- `ts/packages/dispatcher/src/status.ts:16` 内核侧的 `PLAN_KEY_RE` 与 jobroutes 那份同形。
- `ts/packages/base/src/secrets.ts:52-57` `SECRET_KEY_RE` 不命中 `record`；`:129-141` `redactJsonPlain` 只把「像凭据的键」下面的**字符串**换成 `<redacted>`（布尔原样）→ **`record` 键与它的路径值原样保留**（真仓库有记录时标题能显示出来）。

### 前端现状
- `desktop/web/src/api.ts`
  - `:154` `export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models' | 'doctor';`（本片扩成五类，doctor-record **加在末尾**）。
  - `:773-787` `startJob(kind: JobKind, runtime?: string)`：真实分支 `client.postRaw<unknown>('/api/v1/jobs', body, 15)`，`:777` 的正文是 `kind === 'runtime-scan' || runtime == null || runtime === '' ? { kind } : { kind, runtime }`；201 才算建成；桩分支 `mockStartJob(kind, runtime)`。`:789` `getJob(id)`、`:803` `cancelJob(id)`。
  - 全文不许出现网络接口名（fetch / XMLHttpRequest / EventSource / WebSocket，连注释也不许——t010 `:106-110`）。
- `desktop/web/src/jobs/jobStore.ts`
  - `:20` `KINDS = ['runtime-scan', 'runtime-probe', 'models', 'doctor']`；`:26-31` `snaps`；`:34` `subscribers`（三张 `Record<JobKind, …>`）。
  - `:60` `doCreate`（`:61` 同步记下 `creating` 与 `runtime`，`:90-91` 在途的创建大家共用）；`:87` `ensureJob`（`:93` 同值的终态作业直接交回、不新建；`:95` 终态且值不同时才新建）；`:100` `restartJob`（**`:105` 终态且槽里的值与这次不同时直接交回旧作业、不新建**）；`:110` `cancelJob`；`:143` `scheduleNext`（`:147` 没有作业时不排计时器）；`:187` `useJob`；`:209` `useBusyRuntime`（本片这一支不用）；`:216` `resetJobStoreForTests`（**照 KINDS 复位**，不加进 KINDS 会让包内测试之间状态串）。
  - 槽是**按 kind 一类一个**，槽里记 `runtime`；对 doctor-record 来说槽里记的就是 `<task>.vN`。
- `desktop/web/src/jobs/JobCard.tsx`
  - `:12` 时限表；`:13-18` 失败标题表；`:19-24` 进度条 aria-label 表（doctor 那一支是 600 / 就绪检查失败 / 就绪检查进行中）。三张表都是 `Record<string, …>`，**漏加一类 tsc 不报**。
  - `:47` `cancelSent` 状态（取消请求发出后就地禁用 [取消]）；`:75-81` failed 分支固定显示失败标题 + `errorText(envelope)`（messages 为空时是「内核报错（退出码 N）」）；`:85` cancelled 是「已取消」；`:86` timed_out 是「超时（超过 <时限> 秒），已停止」。
- `desktop/web/src/mock/jobs.ts`
  - `:141-149` `kindFailedEnvelope`（doctor 一支；**没列出的 kind 落到列模型那一支**）；`:174-179` 模块级 `jobs` / `probeCounts` / `doctorCounts` 三个表；`:181-212` `mockStartJob`（`:183-185` probe 与 models 缺 runtime 回 400；doctor 的奇偶按 `doctorCounts.get('doctor')` 的**作业次序**算）；`:214-219` `terminalEnvelope`（**没列出的 kind 落到扫描那一支**）；`:221-244` `mockGetJob`（loading 一直 running、error 第一次查询就 failed、data/offline/empty 第一次 running 第二次终态）；`:246` `mockCancelJob`。
  - 桩里不用计时器、不引 `.json`、不出现 `WriteScenario`（T056 S04）。
- `desktop/web/src/writes/RuntimeDoctor.tsx`（T056，256 行）
  - `:15` `ROLE_NAMES`（四个角色中文名）；`:23` `SOURCE_LABELS`（四个来源标签）；`:32` `DOCTOR_CARD_LABELS`（T056 门禁要的记号，保留）；`:36` `DoctorRow`；`:56` `DoctorData`；`:74` `doctorData(job)`（判定「有 data」：data 是对象且 `roles` 是数组）；`:154` `HeadlessCard`；`:188` `SimpleRow`；`:199` `DoctorResult`（汇总 + 逐行渲染）；`:215` `export function RuntimeDoctor()`（`:233-236` 入口按钮，`:237-253` 结果区）。
- `desktop/web/src/components/TextField.tsx`（`components/index.ts:37` 已导出）：可见 label 用 `htmlFor` 关联 input；给 `error` 时 `aria-invalid` 为真并渲染错误段；**不带 list 属性、input 的角色是 textbox**（不撞 t009 `:2908` 的 `select, [role="combobox"], [role="listbox"]` 选择器）。
- `desktop/web/src/pages/readonly1/runtimes-styles.css:10` `.rt-ready-area` 是纵向 flex（`align-items: flex-start`）；`:11-17` `.rt-ready` 的规则留在页面样式表里，**不许搬走也不许改**（t009 求值）。
- `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx:104-108`：`<Section title="就绪检查">` 里 `div.rt-ready-area` 只渲染 `<RuntimeDoctor />`（本片视图不动）。

### 门禁与既有测试的核查结论（本片**必然**要改的那几处，逐行读过）
- `tests/test_gate_t009_baseline.py`
  - `:2895` it 标题「就绪检查：h2 加可点的 [运行就绪检查]（PlayIcon，secondary），虚线空框原文；没有按版本核验的下拉与 [核验]」。
  - `:2903-2908`：`[运行就绪检查]` 在这一节里、可点、data-variant 是 secondary、带 svg、空框句子逐字、**没有按版本核验的下拉**（这一行照旧）。
  - `:2909` `expect(btn(r, '核验')).toBeNull();`（本片必然推翻）。
  - `:2970` it 标题「运行时页：仍禁用的写入口悬停出「第二阶段接入」；可用按钮只有刷新、T022 接上的 [删除…]、T041 接上的 [手动登记…] 与 T055 接上的 [探测]、[模型] 与 T056 接上的 [运行就绪检查]」。
  - `:2974` `expect(outsideWhitelist(['删除…', '手动登记…', '扫描 PATH', '探测', '模型', '运行就绪检查'])).toEqual([]);`
  - `:2975` `expect(disabledButtons().length).toBe(0);`
- `tests/test_gate_t056_baseline.py`（照旧要守住的）
  - S01 `:546-596`：JobKind 取 `export type JobKind = …;` 那一行核「含这几类」；startJob 签名逐字 `(kind: JobKind, runtime?: string)`，函数体里照旧要有 `postRaw`、`{ kind }`、`{ kind, runtime }`、`mockStartJob(kind, runtime)`、`reply.status === 201`、15，**不许出现 `runtime: undefined`**。
  - S02 `:599-651`：KINDS 的正则要 scan、probe、models、doctor 依次出现（**后面可以再接**）；snaps、subscribers 两张表各有 doctor；ensureJob / restartJob / useJob / cancelJob / useBusyRuntime 的签名逐字照旧；轮询公式照旧。
  - S03 `:654-699`：JobCard 三张表里扫描、探测、列模型、就绪检查各项的字照旧在；缺省 kind 'runtime-scan'；只引 job-card.css。
  - S04 `:702-752`：桩的三个导出、四个 kind 记号、扫描夹具与 doctor 夹具的各个记号照旧；不用计时器、不引 JSON、不出现 WriteScenario。
  - S05 `:755-785`：RuntimesView 照旧引 `'../../writes/RuntimeDoctor'`、保留 div.rt-ready-area、不出现 DisabledAction 与 PlayIcon。
  - S06 `:788-856`：RuntimeDoctor.tsx 里照旧有 `ensureJob('doctor')`、`restartJob('doctor')`、`useJob('doctor')`、`kind="doctor"`、`key={job?.id ?? 'creating'}`、`import './runtime-doctor.css';`（**只引这一份样式表**），**不许出现 useBusyRuntime**，不跨层引 src/pages；T056 的逐字文案（按钮「运行就绪检查」、空框句子、离开页那句、汇总、卡头、八个键值行标签、是/否/不限制/无/可用/不可用/已接通/未接通、思考档位两句、来源四标签、角色名四项）照旧都在。
  - S07：runtime-doctor.css 的类名一律 `.rd-` 开头、只用 `--tt-` 令牌、px 字面量带出处注释、不写死颜色。
  - S09 `:892-1015`：t009 与 page-runtimes 里要保留的那些字（见下面「兼容性」一节）。
  - 包内 `desktop/web/tests/jobs-doctor-page.test.tsx` 一个字不改照样过（它只跑 doctor 作业；新的一组空闲时不渲染进度条、`<dt>`，也不发请求：`useJob` 没作业时 `doQuery` 直接返回（jobStore.ts:120-121）、`scheduleNext` 不排计时器（:148））。
- `tests/test_gate_t010_baseline.py:97-110`：源码守卫扫 `desktop/web/src/**/*.{ts,tsx}` 全文（含注释与字符串）：禁词（innerHTML、eval( 等）、网络接口按整词（fetch、XMLHttpRequest、EventSource、WebSocket）、`role=status`、matchMedia 等、十六进制颜色与颜色函数、`--tt-` 令牌拼接。
- `tests/test_gate_t023_baseline.py:97-101`、`:331-349`：入口文件（pages/readonly1、pages/readonly2 与三个顶层页面）的禁字表里没有就绪检查的文案；S11 **只扫入口文件，不扫 src/writes/** → 内核那句「还没有版本记录」只许写在桩里，界面显示 messages 原文，不写死。
- `tests/test_gate_t038_baseline.py`：`src/mock` 恰 14 份 JSON、`src/pages` 顶层恰 9 个 `*Page.tsx`（本片不加 JSON、不加页面）。
- `tests/test_gate_t045_baseline.py` 与包内 `desktop/web/tests/page-app.test.tsx:91-98`：运行时页禁用按钮数照旧是 **0**（空闲时 [核验] 可点才不撞）；`desktop/web/tests/readonly2-app.test.tsx:106` 与运行时页无关。**这两处是过渡断言，本片一条都不推翻，不进允许修改范围。**
- `desktop/web/tests/page-runtimes.test.tsx`：`:116` it 标题「[运行就绪检查] 可点 secondary 带 PlayIcon，虚线空框，无按版本核验下拉」；`:119` `expect(b?.disabled).toBe(false);`；`:120` data-variant；`:123` 空框句子；`:124` 不放下拉；`:125` `expect(btn(container, '核验')).toBeUndefined();`（本片必然推翻）。

### 工具链与锁文件
- `desktop/web` 用 npm（`npm test` = `vitest run` 2.1.8；`npm run typecheck` = `tsc --noEmit`；`npm run build` = `tsc --noEmit && vite build` 5.4.11；`npm run check:contract` = node 脚本）；仓库门禁用 `python -m pytest`。
- `dependency_changes: forbidden`：`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字都不许动。

### 基线检查
- 合同端只读，没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 合同检查在基线上的结果由内核在执行之前跑过（基线检查记录）：本片门禁 `tests/test_gate_t057_baseline.py` 在基线上应当失败（断言失败，不是收集失败），既有门禁基准照旧通过；**执行端不必再跑一遍整套测试**。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/jobs/jobStore.ts
  - desktop/web/src/jobs/JobCard.tsx
  - desktop/web/src/mock/jobs.ts
  - desktop/web/src/writes/RuntimeDoctor.tsx
  - desktop/web/src/writes/runtime-doctor.css
  - tests/test_gate_t009_baseline.py
  - desktop/web/tests/page-runtimes.test.tsx
- allowed_new_files:
  - desktop/web/tests/jobs-doctor-record-page.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t057_*.py
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
  - tests/test_gate_t041_baseline.py
  - tests/test_gate_t042_baseline.py
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t044_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t046_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t048_baseline.py
  - tests/test_gate_t049_baseline.py
  - tests/test_gate_t050_baseline.py
  - tests/test_gate_t051_baseline.py
  - tests/test_gate_t052_baseline.py
  - tests/test_gate_t053_baseline.py
  - tests/test_gate_t054_baseline.py
  - tests/test_gate_t055_baseline.py
  - tests/test_gate_t056_baseline.py
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/live/**
  - desktop/web/src/jobs/job-card.css
  - desktop/web/src/writes/RuntimeScan.tsx
  - desktop/web/src/writes/runtime-scan.css
  - desktop/web/src/writes/RuntimeProbe.tsx
  - desktop/web/src/writes/runtime-probe.css
  - desktop/web/src/writes/RuntimeModels.tsx
  - desktop/web/src/writes/runtime-models.css
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
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
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
  - desktop/web/tests/jobs-store-runtime.test.ts
  - desktop/web/tests/jobs-probe-page.test.tsx
  - desktop/web/tests/jobs-models-page.test.tsx
  - desktop/web/tests/jobs-doctor-page.test.tsx
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/page-runtimes-empty.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/writes-remove.test.tsx
  - desktop/web/tests/page-static.test.ts
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - ts/package.json
  - ts/bun.lock
  - ts/packages/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 作业客户端（`desktop/web/src/api.ts` 与 `desktop/web/src/jobs/jobStore.ts`）
- `api.ts`：`export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models' | 'doctor' | 'doctor-record';`（**doctor-record 加在末尾**；`:153` 的注释同步改一句：「服务还有两类」改成「服务还有一类」）。
- `api.ts` 的 `startJob`：**签名逐字不改** `(kind: JobKind, runtime?: string)`；正文多一支——kind 是 `doctor-record` 且第二个参数非空时发 `{ kind, record: runtime }`，其余照旧（扫描那一支与不带值的 doctor 仍发 `{ kind }`，探测与列模型仍发 `{ kind, runtime }`）。**原有的 `{ kind }` 与 `{ kind, runtime }` 两个字面必须留在函数体里**（t056 S01 认它们），**不许出现 `runtime: undefined`**。`postRaw`、时限 15、`reply.status === 201`、桩分支 `mockStartJob(kind, runtime)`、`getJob` / `cancelJob` 全部照旧。
- **第二个参数的含义**（写在 `startJob` 上方的注释里）：「第二个参数是这一类作业的对象：探测、列模型是 runtime id，按版本记录核验是 <task>.vN」。
- `jobStore.ts`：`KINDS` 扩成五类（`['runtime-scan', 'runtime-probe', 'models', 'doctor', 'doctor-record']`，次序照旧、doctor-record 在末尾）；`snaps`（`:26-31`）与 `subscribers`（`:34`）两张 `Record<JobKind, …>` 各加 doctor-record 一项（少了 tsc 会报错）；`inflight` 是 `Partial<Record<…>>`，不用改。
- **签名一个字不改**：`ensureJob(kind, runtime?)`、`restartJob(kind, runtime?)`、`useJob(kind, runtime?)`、`cancelJob(kind)`、`useBusyRuntime(kind)`、`resetJobStoreForTests()` 全照旧；T054/T055/T056 的公式（setTimeout 链、每 1000 毫秒、`clearTimeout`、`Math.floor((Date.now() - t0) / 1000)`、`useSyncExternalStore`、「没有作业时不排计时器」）一字不改。
- **doctor-record 这一支的状态语义**（照 `jobStore.ts` 既有逻辑推出，执行端照此实现，不许另造一套）：
  - 没有作业、没有创建失败 → 点 [核验] 起一个新作业；
  - 作业已终态（succeeded / failed / cancelled / timed_out）且**值相同** → 起一个新作业（新的 `t0`、新的作业号）；
  - 作业已终态且**值不同** → 起一个新作业（槽里的旧作业被丢掉）；
  - 作业在跑（queued / running）且值相同 → 不新建，沿用那个作业；
  - 作业在跑且值不同 → 不新建（同类同时只一个）；
  - 创建失败 → 再点重建。
  - **实现口径**：点 [核验] 时依次调 `restartJob('doctor-record', 值)` 与 `ensureJob('doctor-record', 值)`。理由：`restartJob`（`:100-107`）在终态且同值时新建、终态且异值时交回旧作业；`ensureJob`（`:87-97`）在终态且异值时新建、终态且同值时交回旧作业；两者合起来覆盖上面五种情形；在途的创建由 `:90-91` 共用，**不会建出两个**。执行端可以换写法，但上面五种情形都要有测试。
  - 槽里记的 `runtime` 对 doctor-record 就是 `<task>.vN`。

### 作业进度卡（`desktop/web/src/jobs/JobCard.tsx`）
- 只在三张按 kind 查的表里各加 doctor-record 一项，不加新 prop：
  | kind | 失败标题 | 进度条 aria-label | 超时秒数 |
  |---|---|---|---|
  | `doctor-record` | 核验失败 | 核验进行中 | 600 |
- 扫描、探测、列模型、就绪检查四支的字面（扫描失败 / 探测失败 / 列模型失败 / 就绪检查失败 / 各自的进度条名字 / `runtime-scan: 150` / `doctor: 600` / 已取消 / 超时模板）一字不动；只引 `job-card.css`；不许渲染 `role="status"`；不许写死颜色与内联 style。

### 界面（`desktop/web/src/writes/RuntimeDoctor.tsx` 与 `desktop/web/src/writes/runtime-doctor.css`）
- 入口与结果**都在 `RuntimeDoctor.tsx` 里**（同一节、复用 HeadlessCard，不另起文件互相引用）；**视图 `runtimes-RuntimesView.tsx` 一个字不改**（`div.rt-ready-area` 里已经只渲染 `<RuntimeDoctor />`）。
- 组件从 `'../components'` 引 `Button` 与 `TextField`（`components/index.ts` 已导出，**按字节冻结，不许改**）；从 `'../jobs/JobCard'` 引 JobCard；从 `'../jobs/jobStore'` 引 `ensureJob` / `restartJob` / `useJob` / `cancelJob`。
- **不许出现 `useBusyRuntime`**（t056 S06）；**不许跨层引 `src/pages`**（角色名与来源标签照抄的小表照旧留在组件里）；**只引 `./runtime-doctor.css`**（T056 的样式表接线照旧，不引第二份）。
- 入口一行（§6.5 :636 同一行）：组件根部新增一个横排容器（类名 `.rd-entries`），里面依次是
  - [运行就绪检查]（T056 的按钮原样：文字逐字「运行就绪检查」、`variant="secondary"`、`size="md"`、`PlayIcon width={16} height={16}`、运行中只禁用不换字）；
  - 核验组（类名 `.rd-record`）：`TextField`（label 逐字「按版本记录核验」、`mono`、**不带 `list` 属性**、不预填、值不 trim）+ 一个 Button（文字逐字「核验」、`variant="secondary"`、`size="md"`、不带图标）。
- **PLAN_KEY_RE**：照 `ts/packages/ui/src/jobroutes.ts:22` 抄一份放在用到它的文件里（`RuntimeDoctor.tsx`）：`/^[a-z0-9][a-z0-9-]{0,63}\.v[1-9][0-9]{0,3}$/u`。
- 点 [核验]：
  - 值**不合格**（空值、大写、没有 `.v`、`v0` 等）：**不发任何请求**，把提示写进 TextField 的 `error`，逐字「写成 <task-id>.v<N>，例如 logs-cat.v2」；
  - 值**合格**：清掉提示，按上面的口径起作业；
  - 提示在**改了文本框**（onChange）或**点了一个合格的值**时清掉。
- [核验] 的禁用条件：**只看 doctor-record 这一类作业**是否在创建（creating）、排队（queued）或运行（running）；**空闲时一直可点**（值不合格靠点了之后的提示，不靠禁用——运行时页的禁用按钮数照旧是 0）。[运行就绪检查] 与 [核验] 各管各的禁用，**可以同时跑**。
- 作业卡：`useJob('doctor-record')` 管状态；JobCard 用 `kind="doctor-record"`、`title="版本记录核验"`、`key={job?.id ?? 'creating'}`（每个作业重新挂载，否则取消之后再点新作业的 [取消] 一出来就是灰的）；[取消] 走 `cancelJob('doctor-record')`。
- 结果块（自己渲染，不走 JobCard 的 succeeded/failed 分支）：
  - **有 data 的判据**：与 T056 同一套——`job.envelope.data` 是对象且 `data.roles` 是数组（内核报错时没有 data）。
  - **什么时候渲染**：作业 `succeeded`，或者作业 `failed` **且有 data**（内核的记录没就绪时退出码 1，data 完整）。
  - **succeeded 时**结果块放在 JobCard 的 children 里；**failed 且有 data 时不渲染 JobCard**（免得出现笼统的「核验失败」与「内核报错（退出码 1）」），直接渲染结果块——与 doctor 一个写法。
  - **结果块的内容**：
    - 第一行标题：逐字「版本记录 」+ `data.roles[0].record`（**缺键写「—」**；内核给的值形如 `.agent/runs/logs-cat/binding-v2.json`）；
    - 下面**每行一张 HeadlessCard**（复用 T056 的那张卡：卡头 ✓/✗ 与角色名与 profile、八个键值行、问题列表、说明行）；行是头less 的判定沿用 doctor 的那一套（`mode === 'headless'` 或有 `profile` → HeadlessCard，否则一行）；
    - **不加汇总行**（不写「全部就绪」「有未就绪的角色（N 个）」）——记录核验只有一行，不用汇总。
  - **没有 data 的 failed**：照旧渲染 JobCard（`kind="doctor-record"`、`title="版本记录核验"`），显示失败标题「核验失败」与**内核报错原文**（`envelope.messages` 逐行；空时是「内核报错（退出码 N）」）。**界面不写死内核那句「还没有版本记录」**（t023 S11 的口径：内核原文只在桩里，界面显示 messages 原文）。
  - **已取消**：JobCard 显示逐字「已取消」。**超时**：JobCard 显示逐字「超时（超过 600 秒），已停止」。**创建失败**：JobCard 显示失败标题与错误原文。
  - 结果区放在 doctor 的结果区**下面**，用**自己的容器**（类名 `.rd-record-body`），方便测试限定范围。
- **只加不删**：T056 的记号与逐字文案一个字不许删——`ensureJob('doctor')` / `restartJob('doctor')` / `useJob('doctor')` / `kind="doctor"` / `key={job?.id ?? 'creating'}` / `import './runtime-doctor.css';` / 角色名四项 / 来源四标签 / 八个键值行标签 / 「运行就绪检查」「就绪检查」「就绪检查失败」「就绪检查进行中」「离开这个页面作业也会继续，回来时显示结果。」「还没有运行过就绪检查。…」「全部就绪」「有未就绪的角色」「✓ 就绪」「✗ 未就绪」「是」「否」「不限制」「无」「可用」「不可用」「已接通」「未接通」「本机 pi 接受这个档位」「本机 pi 不接受这个档位」「—」等。
- 样式（`runtime-doctor.css`）：新加的类一律以 `.rd-` 开头（本片新增 `.rd-entries`、`.rd-record`、`.rd-record-body`）；只用 `--tt-*` 令牌；不写死颜色、不写颜色函数、不写内联 style；除 `0` 与 `1px` 外的 px 字面量同一行带出处注释；`.rt-ready` 的规则留在 `desktop/web/src/pages/readonly1/runtimes-styles.css` 不动。

### 桩（`desktop/web/src/mock/jobs.ts`）
- `runtime-scan`、`runtime-probe`、`models`、`doctor` 四支**一字不改**（t054/t055/t056 的 S04 照旧过）。
- `mockStartJob`：`doctor-record` **不带记录值**时回 **400**（正文键是 `kind` + `record`，服务缺 `record` 会回 400；桩照同样的规则回 400，一行示意原文）。probe 与 models 缺 runtime 回 400 的那一支照旧。
- doctor-record 的终态信封（`terminalEnvelope` 加一支）：
  - **记录是 `logs-cat.v2`**（设计里的例子）：给**有 data** 的结果——data 是 `{ready, roles: [那一行]}`，那一行是 doctor 的无头行（`doctorHeadlessRow`）**加一个 `record` 键**，值 `.agent/runs/logs-cat/binding-v2.json`；**奇数次没就绪**（`ready` 为假、凭据不可用、退出码 1 → 作业落 **failed 但带 data**），**偶数次就绪**（`ready` 为真、退出码 0 → succeeded）。**计数独立**：另起一个按记录值计数的表，**不许动 `doctorCounts`**（t056 的 stub 探针依赖 doctor 按作业次序算奇偶）。
  - **别的记录**（不是 `logs-cat.v2`）：落 **failed、没有 data**，`messages` 一行逐字 `ERROR: <记录> 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor`（照内核 `roles-probe.ts:300` 的那句；这是桩里的示意原文，界面只显示 messages 原文）。
- `kindFailedEnvelope` 加 doctor-record 一支：`error` 开关下 doctor-record 落 failed、**没有 data**，一行示意原文（例如「ERROR 核验失败：内核报错（示意）」）。
- 五个开关的语义照旧：`loading` 一直 running；`error` 第一次查询就 failed（没有 data）；`data`/`offline`/`empty` 第一次查询 running、第二次终态（doctor-record 的终态照上面的规则）。
- 桩里不许出现 `WriteScenario`、不许引 `.json`、不许加计时器；`desktop/web/src/mock/writes.ts` 一个字不改。

### 边界输入
- 值不合格（空、大写、没有 `.v`、`v0`、超长、含空格）：**不发创建请求**，就地提示「写成 <task-id>.v<N>，例如 logs-cat.v2」（提示放在 TextField 的 `error` 里，控件 `aria-invalid` 为真）。
- 值合格但服务回 400（例如桩里缺记录值、或真实服务认为 `record` 不合法）：显示失败标题「核验失败」与错误原文；[核验] 仍可点，点了重建。
- 作业在跑：doctor-record 这一类的 [核验] 禁用；[取消] 只发一次取消请求，取消请求在途时 [取消] 禁用（JobCard 内部管）；**doctor 那一类的按钮不受影响**（可以同时跑）。
- 作业已结束（succeeded / failed / cancelled / timed_out）：[核验] 可点，点了是**新作业**（新的创建请求、新的作业号）；值换了也是新作业。
- 取消：JobCard 显示「已取消」；超时：JobCard 显示「超时（超过 600 秒），已停止」。
- 查询回 404（服务重启过）：照 T056 的做法——错误信封并进 `job.envelope`、状态落 failed，于是显示内核报错原文（没有 data）。
- failed 且**没有** data：显示内核报错原文，不显示结果块。
- failed 且**有** data：显示结果块（标题「版本记录 <record>」+ 就绪卡），**不显示**笼统的「核验失败」。
- 记录那一行缺键（找不到命令 → 没有 command/source/version；不是 pi 或缺 provider/model → 没有 model_listed/auth_ready/thinking_supported）：缺键一律写「—」，不报错、不留空；`allowed` 为 null 写「不限制」；`credentials` 为空写「无」。
- 离开这一页再回来：作业在模块里（`jobStore` 按 kind 存槽），回来时看到的是**同一个作业**（还在跑就是进度，跑完就是结果），**不再发创建请求**。
- 页面上没有版本记录的下拉（t009 :2908 照旧）。

### 并发、取消与状态变化
- 同一类只许一个在跑：doctor-record 一个槽，界面上 [核验] 禁用 + store 的槽两头都挡；doctor 另一个槽，两类互不影响。
- 轮询：setTimeout 链、每 1000 毫秒一次、卸载即停（`clearTimeout`）、重开先查一次；没有作业时不排计时器（T055 的口径照旧）。
- 取消：只发一次取消请求；作业的终态由下一次查询给出；取消后再点 [核验] 是新作业（新作业的 [取消] 可点，见「JobCard 的 key」）。

### 写法钉死（与本片门禁基准文件对表）
本片门禁由门禁端交付（`tests/test_gate_t057_baseline.py`），它不在当前基线里，由门禁那一版合同产出并集成；基线上它应当失败（断言失败，不是收集失败）。执行端第 1 步要读门禁文件并与这一节对一遍；**有出入以本合同的「写法钉死」为准，并把出入写进执行报告**；若出入是逐字文案层面的实质冲突，按 Stop conditions 停下报告。
- `desktop/web/src/api.ts`：`export type JobKind = …;` 那一行含 `'runtime-scan'`、`'runtime-probe'`、`'models'`、`'doctor'`、`'doctor-record'`；`export function startJob(` / `getJob(` / `cancelJob(`；`startJob` 的函数体里有 `postRaw`、`{ kind }`（字面）、`{ kind, runtime }`、`{ kind, record: runtime }`、`mockStartJob(kind, runtime)`、时限 `15`；**不许出现 `runtime: undefined`**；`JobState` 六个值与 `JobView` 八键照旧。
- `desktop/web/src/jobs/jobStore.ts`：五个既有 `export function`（ensureJob / restartJob / cancelJob / useJob / resetJobStoreForTests）与 `useBusyRuntime` 都在；`KINDS` 五类且次序是 scan、probe、models、doctor、doctor-record；`snaps` 与 `subscribers` 各有 doctor-record 一项；`setTimeout(` 在、`setInterval(` 不在、`1000`、`clearTimeout`；已用秒数逐字 `Math.floor((Date.now() - t0) / 1000)`；`useSyncExternalStore`；从 `'../api'` 引 `startJob(` / `getJob(` / `cancelJob(`。
- `desktop/web/src/jobs/JobCard.tsx`：`export function JobCard(`；props 里有 title / onCancel / children / kind / failedDetail；`role="progressbar"`；[取消]；「已用 ${…} 秒」；「扫描失败」「已取消」「超时（超过 ${…} 秒），已停止」；三张表里有 doctor-record 的「核验失败」「核验进行中」与 600；`runtime-scan: 150` 与 `doctor: 600` 照旧在；**只许 `import './job-card.css';`**。
- `desktop/web/src/mock/jobs.ts`：三个既有导出；不用计时器；不引 JSON；`'runtime-scan'`、`'runtime-probe'`、`'models'`、`'doctor'`、`'doctor-record'` 都在；既有扫描夹具与 doctor 夹具的文案一字不改；doctor-record 的记录值、`.agent/runs/logs-cat/binding-v2.json` 与「还没有版本记录」那句在桩里。
- `desktop/web/src/writes/RuntimeDoctor.tsx`：`import './runtime-doctor.css';` 在位；`ensureJob(` / `restartJob(` / `useJob(` 里既有 `'doctor'` 那一支照旧，又有 `'doctor-record'` 那一支；`JobCard` 从 `'../jobs/JobCard'` 引；`kind="doctor"` 与 `kind="doctor-record"` 都在；`key={job?.id ?? 'creating'}` 在；逐字文案在（「运行就绪检查」「按版本记录核验」「核验」「核验失败」「核验进行中」「版本记录」「写成 <task-id>.v<N>，例如 logs-cat.v2」+ T056 的全部文案）；不出现 `role="status"`、不写死颜色、不写内联 style、不跨层引 `src/pages`、**不出现 useBusyRuntime**。
- `desktop/web/src/writes/runtime-doctor.css`：只用 `--tt-` 令牌；类名以 `.rd-` 开头；除 0 与 1px 外的 px 字面量同行带出处注释。

### 兼容性（本片推翻的旧断言，逐处写明只改哪一处）
以下文件的这一处要改，**只改这一处**，其余一个字不动：
- `tests/test_gate_t009_baseline.py`
  - `:2895` 的 it 标题：前半「就绪检查：h2 加可点的 [运行就绪检查]（PlayIcon，secondary），虚线空框原文」一字不动（t056 门禁 S09 认它），只把末尾「；没有按版本核验的下拉与 [核验]」改成本片的说法：「；按版本记录核验是文本框加可点的 [核验]，没有下拉」。
  - `:2909`：`expect(btn(r, '核验')).toBeNull();` → 在「就绪检查」这一节里找到 [核验] 按钮、**不为 null**、**`disabled` 为 false**（例如 `const v = btn(sec, '核验'); expect(v).not.toBeNull(); expect(v.disabled).toBe(false);`）。`:2903-2908` 一字不动（尤其 `:2908` 不放下拉那一行照旧）。
  - `:2970` 的 it 标题：在末尾「与 T056 接上的 [运行就绪检查]」后面接本片 → 「…与 T056 接上的 [运行就绪检查] 与 T057 接上的 [核验]」。「与 T055 接上的 [探测]、[模型]」这一段一字不动（t055 门禁认它）。
  - `:2974`：白名单 `['删除…', '手动登记…', '扫描 PATH', '探测', '模型', '运行就绪检查']` → 在**'运行就绪检查' 后面**加 `'核验'`（**"'扫描 PATH', '探测', '模型'" 与 "'模型', '运行就绪检查'" 要照旧连着写**，t055、t056 门禁认它们）。
  - `:2975`：`expect(disabledButtons().length).toBe(0);` **一字不动**（空闲时 [核验] 可点，禁用按钮数照旧是 0；t056 门禁认它）。
- `desktop/web/tests/page-runtimes.test.tsx`
  - `:116` 的 it 标题：前半「[运行就绪检查] 可点 secondary 带 PlayIcon，虚线空框」一字不动（t056 门禁认它），只把末尾「，无按版本核验下拉」改成「，按版本记录核验是文本框加可点的 [核验]，无下拉」。
  - `:125`：`expect(btn(container, '核验')).toBeUndefined();` → 改成 [核验] **在**这一节里、**可点**（`expect(btn(container, '核验')).toBeTruthy();` 并断言 `disabled` 为 false）。`:120`、`:123`、`:124` 一字不动（t056 门禁认它们）。

**不推翻的旧断言**（不许改，也不进允许修改范围）：包内 `desktop/web/tests/page-app.test.tsx:91-98`（运行时页禁用按钮数 0）、`desktop/web/tests/readonly2-app.test.tsx:106`；t009 `:2903-2908`、`:2975`；t056 的 S01–S08 各段与 S09 里点名要保留的那些字。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件** `tests/test_gate_t057_baseline.py`（只读；本回合的基线上它还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/api.ts`**：`JobKind` 末尾加 `'doctor-record'`（逐字 `export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models' | 'doctor' | 'doctor-record';`）；`:153` 的注释改一句；`startJob` 的正文多一支 `{ kind, record: runtime }`（原有的 `{ kind }` 与 `{ kind, runtime }` 两个字面保留，**不许出现 `runtime: undefined`**）；在 `startJob` 上方写明第二个参数的含义；`getJob` / `cancelJob` 与其余导出照旧；全文不许出现网络接口名。
3. **`desktop/web/src/jobs/jobStore.ts`**：`KINDS` 末尾加 doctor-record；`snaps` 与 `subscribers` 各加 doctor-record 一项；槽里「runtime」的注释扩写成「这一类作业的对象」；签名与逻辑都不动。
4. **`desktop/web/src/jobs/JobCard.tsx`**：三张按 kind 的表各加 doctor-record（600、核验失败、核验进行中）；其余四支的字面与 `job-card.css` 一个字不改。
5. **`desktop/web/src/mock/jobs.ts`**：doctor-record 缺记录值回 400；`logs-cat.v2` 给有 data 的结果（那一行加 `record: '.agent/runs/logs-cat/binding-v2.json'`，奇数次没就绪落 failed 带 data、偶数次就绪 succeeded，**计数独立于 doctor**）；别的记录落 failed、没有 data，messages 一行「ERROR: <记录> 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor」；`kindFailedEnvelope` 与 `terminalEnvelope` 各加 doctor-record 一支；其余四支一字不改；不用计时器、不引 JSON、不碰 `mock/writes.ts`。
6. **`desktop/web/src/writes/RuntimeDoctor.tsx`**：加 PLAN_KEY_RE；加横排容器 `.rd-entries`（[运行就绪检查] 原样 + 核验组 `.rd-record`）；核验组里是 TextField（label「按版本记录核验」）与 [核验] 按钮（逐字「核验」）；点 [核验]：不合格就只设 error 提示「写成 <task-id>.v<N>，例如 logs-cat.v2」且不发请求，合格就依次 `restartJob('doctor-record', 值)`、`ensureJob('doctor-record', 值)`；`useJob('doctor-record')` 管状态，JobCard 用 `kind="doctor-record"`、`title="版本记录核验"`、`key={job?.id ?? 'creating'}`；结果块（标题「版本记录 <record>」+ 每行一张 HeadlessCard、不加汇总行）在自己的容器 `.rd-record-body` 里；有 data 的 failed 走结果块、没有 data 的 failed 与取消与超时交给 JobCard；T056 的记号与文案一个字不许删；不用 useBusyRuntime；只引 `./runtime-doctor.css`。
7. **`desktop/web/src/writes/runtime-doctor.css`**：加 `.rd-entries`、`.rd-record`、`.rd-record-body` 三条规则（横排容器用 flex + `var(--tt-space-*)`；标题用 `--tt-text-*`）；只用 `--tt-` 令牌；不写死颜色；px 字面量带出处注释或干脆不用。
8. **逐处改旧断言**（照「兼容性」一节，逐条只改那一处）：`tests/test_gate_t009_baseline.py`（:2895、:2909、:2970、:2974）与 `desktop/web/tests/page-runtimes.test.tsx`（:116、:125）；改完把仍钉着旧口径的地方再搜一遍（关键字：`btn(r, '核验')`、`toBeUndefined`、`没有按版本核验的下拉`、`无按版本核验下拉`、`'运行就绪检查']`），确认没有漏网的旧断言。
9. **新增包内测试 `desktop/web/tests/jobs-doctor-record-page.test.tsx`**（写法照 `desktop/web/tests/jobs-doctor-page.test.tsx` 的 harness：真实模式注入假客户端 `setLiveClientForTests`，桩模式走 `?mock=`；不许 `skip`/`only`/`todo`；测真实实现，不 mock 被测组件），覆盖：
   (a) 填 `logs-cat.v2` 点 [核验]：发 `POST /api/v1/jobs`、正文**恰两个键** `{"kind":"doctor-record","record":"logs-cat.v2"}`，之后每秒查同一个作业号；
   (b) 运行中 [核验] 禁用、有「已用 N 秒」与 [取消]、[运行就绪检查] 照旧可点；
   (c) succeeded：标题「版本记录 .agent/runs/logs-cat/binding-v2.json」与就绪卡（八个键值行、问题、说明行）；
   (d) failed 带 data：照样显示结果块、卡头 ✗ 未就绪、问题列表在、**不显示**「核验失败」；
   (e) failed 没有 data：显示内核报错原文、不显示结果块；
   (f) 已取消显示「已取消」；超时显示「超时（超过 600 秒），已停止」；
   (g) 空值、大写、没有 .v、v0 点 [核验] **不发请求**、出提示；
   (h) 卸载再挂载看到同一个作业、不再发创建请求；结束后同值再点、换值再点，都只发**一次**新的创建请求；
   (i) 桩模式：`logs-cat.v2` 的奇偶两支、别的记录落「还没有版本记录」、doctor-record 缺记录值回 400、两类作业同时跑。
10. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → V04 → R01**（本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
11. 写执行报告；遇到合同未定义的行为（例如门禁端交付的 `tests/test_gate_t057_baseline.py` 与合同的「写法钉死」有实质冲突），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t057_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test -- tests/jobs-doctor-record-page.test.tsx` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py -q` · cwd：仓库根 · 超时：3300s · 期望退出码：0 · 输出须匹配：`\d+ passed`

上面每条检查的「输出须匹配」为什么在门禁机上成立（逐条说明；门禁检查与回归检查都用 pytest 的 `-q`，成功时最后一行是「N passed」，与已验收的 T055/T056 合同里同一种调用配同一个匹配，已在门禁机上成立过）：
- 前端那三条 vitest 检查是 `npm test`（= `vitest run`，desktop/web 已装 vitest 2.1.8——内核核实表里记着版本），vitest 2.x 成功时打印「Tests  N passed」；同一个匹配在 T055、T056 合同的同一种调用上验收通过过。只跑指定文件的那一条另加 `不得出现 No test files found`（vitest 找不到文件时会这么写，防止「0 个用例也是绿色」）。
- 类型检查那条是 `npm run typecheck`（= `tsc --noEmit`），成功时无输出、退出码 0；这条不写输出须匹配（没有输出可匹配），只看退出码。
- 构建那条是 `npm run build`（= `tsc --noEmit && vite build`），vite 5.4.11 成功时打印「✓ built in …」；同一个匹配在 T055、T056 合同里验收通过过。

## Definition of done
- D01：「就绪检查」一节里有一组「按版本记录核验」：一个文本框（可见 label 逐字「按版本记录核验」，无障碍名称在）与一个 [核验] 按钮（逐字「核验」），与 [运行就绪检查] 同一行；文本框不预填、不带下拉；目的：按某个合同版本当初记下的执行模型核验它现在还能不能跑（设计 §6.5 :636）；证据：V01、V02、G01、R01。
- D02：点 [核验]：值合 PLAN_KEY_RE 时发 `POST /api/v1/jobs`、正文**恰两个键** `{"kind":"doctor-record","record":"<值>"}`，随后每秒查同一个作业号；值不合格时**不发请求**，就地提示「写成 <task-id>.v<N>，例如 logs-cat.v2」；目的：不把不合法的值发给服务，也不给用户一个没有解释的 400；证据：V01、V02、G01。
- D03：作业在跑时 [核验] 禁用，作业卡显示进度（aria-label 逐字「核验进行中」）、「已用 N 秒」与 [取消]；空闲时 [核验] 一直可点（运行时页禁用按钮数照旧是 0）；[运行就绪检查] 与 [核验] 可以同时跑；目的：§8.4「同一类作业同时只能有一个」与「空闲时可点」；证据：V01、V02、G01、R01。
- D04：作业结束后这一节里，有 data 时显示一块，标题逐字「版本记录 <record>」（缺键写「—」），下面是 T056 的就绪卡（卡头、��个键值行、问题、说明行），不加汇总行；没有 data 的失败显示内核报错原文；取消与超时照作业卡；目的：重试已有版本记录的合同之前先核对记录（AGENTS.md 的要求）；证据：V01、V02、G01。
- D05：离开这一页再回来看到的是同一个作业、不再发创建请求；结束后再点（含换值再点）是新作业、只发一次创建请求；目的：作业在模块里跑、结果不丢，也不会误建第二个作业；证据：V01、V02、G01。
- D06：作业客户端多一类 doctor-record（`JobKind` 五类、`KINDS`/`snaps`/`subscribers` 各一项、JobCard 三张表各一项：失败标题「核验失败」、aria-label「核验进行中」、超时 600）；扫描、探测、列模型、就绪检查四支一个字不变（T054–T056 的既有包内测试与探针原样照过）；目的：四类作业共用一张卡与一个槽，别的片不受影响；证据：V01、V02、V03、G01、R01、scope。
- D07：桩里 doctor-record 放行（缺记录值回 400）、`logs-cat.v2` 奇数次没就绪（落 failed 带 data）、偶数次就绪，别的记录落 failed 且没有 data（messages 一行「还没有版本记录」），error 开关落 failed 且没有 data；doctor 那一支的奇偶计数一个字不改；目的：没有真服务时也能看到两种结局，且不破坏 T056 的桩探针；证据：V01、V02、G01。
- D08：入口与结果都在 `RuntimeDoctor.tsx`（视图 `runtimes-RuntimesView.tsx` 一个字不改）；新样式只加在 `runtime-doctor.css`（类名以 `.rd-` 开头、只用 `--tt-*` 令牌、不写死颜色与内联 style、不跨层引 `src/pages`、不用 useBusyRuntime）；T056 的记号与逐字文案一个字没删；目的：这一片只加核验这一组，别顺手改别处；证据：V02、V04、G01、R01、scope。
- D09：新增 `desktop/web/tests/jobs-doctor-record-page.test.tsx`，覆盖 D01–D05 点名的每一项（含「有 data 与没有 data 两支」「取消与超时」「卸载再挂载是同一个作业」「结束后同值再点与换值再点」「值不合格不发请求」「桩的两支与 400」），测真实实现，不许 `skip`/`only`/`todo`；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、V02、review。
- D10：旧断言逐处改到位：`tests/test_gate_t009_baseline.py`（:2895、:2909、:2970、:2974）与 `desktop/web/tests/page-runtimes.test.tsx`（:116、:125）——每处只改上面写明的那一处，其余一个字不动；**不推翻**任何过渡断言（包内 page-app:91-98、readonly2-app:106）与 t009 `:2903-2908`、`:2975`、t056 S01–S08；目的：这些断言钉着「没有 [核验]」，本片必然推翻，改法不许顺手改别的断言；证据：G01、R01、V02、scope。
- D11：所有修改都在允许集合内（可改 8 个文件、可新增 1 个文件），没有碰 forbidden_paths（`tests/test_gate_t057_*.py`、其余 55 份门禁基准、`components/**`、`shell/**`、`live/**`、`job-card.css`、T054–T056 的写入口组件与 CSS、既有写流程文件与 CSS、`runtimes-logic.ts`、`runtimes-styles.css`、视图 `runtimes-RuntimesView.tsx`、`RuntimesPage.tsx`、`mock/*.json` 与 `mock/writes.ts`/`quizs.ts`/`hub-roles.ts`、T054–T056 的既有包内测试与 `live-*.test.ts`、`page-app.test.tsx`、`readonly2-app.test.tsx`、`package.json` 与锁文件、`ts/packages/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope、review。
- D12：`npm test`、`npm run typecheck`、`npm run build` 全过，既有门禁基准照旧通过；目的：不能为了接一个入口把别处弄坏；证据：V02、V03、V04、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `jobroutes.ts` 的 doctor-record 不再是「键恰好 kind+record」、`JOB_TIMEOUTS` 的 doctor-record 不是 600、`roles-probe.ts` 的 record 行不再带 `record` 键、`redactJsonPlain` 开始遮 `record`、`jobStore.ts` 的 `restartJob`/`ensureJob` 语义变了、`JobCard.tsx` 的字面变了、`mock/jobs.ts` 的 400 分支变了），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `components/**`、`shell/**`、`live/**`、`runtimes-RuntimesView.tsx`、`runtimes-styles.css`、`runtimes-logic.ts`、既有写流程文件、其余门禁基准、`package.json` 与锁文件、`ts/packages/**`）。
- 门禁端交付的 `tests/test_gate_t057_baseline.py` 与本合同的「写法钉死」出现实质冲突（例如它要求失败标题或进度条名字换一种写法、要求创建正文多带键或换成 `runtime` 键、要求 [核验] 不可点、要求结果块经过 JobCard 的失败分支、要求标题不含「版本记录」）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 运行时页的禁用按钮数改完不是 0（与合同和站主任务书说的「空闲时 [核验] 可点」对不上）：停下并报告实际数字，不要顺手改别的断言来凑。
- 换值再点没有建出新作业（restartJob 的语义与 Repository facts 不符）：停下并报告。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t057-desktop-web-runtime-record` 汇总，含返工版本；累计已用 0 次 → 本版留 3 次）
- max_wall_seconds_per_attempt: 10800
- max_wall_seconds_total: 32400（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 32400 秒 ≥ 本版 2 × 10800 = 21600 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 30 分钟；api.ts 与 jobStore.ts 20 分钟；JobCard.tsx 10 分钟；mock/jobs.ts 25 分钟；RuntimeDoctor.tsx 与 CSS 50 分钟；逐处改旧断言 20 分钟；新包内测试 55 分钟；必要检查（G01、V01、V02、V03、V04、R01；R01 约 45–60 分钟、可分批跑）70 分钟；最终报告 5 分钟；总计约 285 分钟，单轮时限 10800 秒（180 分钟）——总量 32400 秒覆盖本版与返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
