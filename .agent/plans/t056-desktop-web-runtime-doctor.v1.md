# TASK: t056-desktop-web-runtime-doctor

<!-- 合同 v1：T056「[运行就绪检查]：就绪检查一节接上作业接口，逐个角色显示就绪卡」。
     规划报告：.agent/mailbox/tasks/T056-1-plan/report.md；站主任务书：.agent/mailbox/tasks/T056/brief.md。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片把「就绪检查」一节的 [运行就绪检查] 从灰变可点：起一个 doctor 长作业（正文恰 {"kind":"doctor"}），
     在这一节里用作业进度卡显示进度，结束后逐个角色显示就绪卡；有 data 的 failed 照样显示结果。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 7083e7aa1d3c0706df6e2354bfbd28ac72553723
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
「CLI 运行时」页「就绪检查」一节里的 [运行就绪检查] 从灰变可点：点它起一个 `doctor` 长作业（`POST /api/v1/jobs`，正文恰 `{"kind":"doctor"}`），这一节里用作业进度卡显示进度（标题「就绪检查」、失败标题「就绪检查失败」、进度条 aria-label「就绪检查进行中」、超时 600 秒），运行中另起一行写「离开这个页面作业也会继续，回来时显示结果。」；作业结束后这一节里显示一句汇总（全部就绪 / 有未就绪的角色（N 个））、每个无头角色一张就绪卡（卡头、键值行、问题列表、说明行），不是无头的角色各一行；作业因有角色没就绪落 failed 但带着 data 时照样这样显示（不是笼统的「就绪检查失败」），没有 data 的失败显示内核报错原文。作业在跑时按钮禁用，结束后再点是重新检查（新作业），离开这一页再回来看到的是同一个作业。

## Non-goals
- 不改本机服务与内核（`ts/packages/ui/**`、`ts/packages/config/**`、`scripts/**` 一个字不改）：doctor 的路由、正文校验、时限 600 与命令 `config doctor --json` 都已就位。
- 不做 [核验]（按版本记录核验，kind `doctor-record`）；不做七端岗位的就绪检查（`config doctor` 只报调度器的四个角色）。
- 不做凭据录入、就绪卡里「去凭据页录入」的链接、资格认证（M6，等用户定）；版本列照旧「—」。
- 不改 `desktop/web/src/components/**`（`components/index.ts` 按字节冻结）、`desktop/web/src/shell/**`、`desktop/web/src/live/**`、`desktop/web/src/jobs/job-card.css`、`desktop/web/src/writes/RuntimeScan.tsx` 与 `runtime-scan.css`、既有写流程文件（`useWriteFlow.ts`、`WriteConfirmDialog.tsx`、`writeOutcome.ts`、`snapshots.ts`、`useLivePreview.ts`、`RuntimeForm.tsx`、`runtimeRules.ts`、`profileRules.ts`、`hubChangeLines.ts`、`HubBindForm.tsx`、`RoleBindForm.tsx`、`ProfileForm.tsx`、`PresetSaveForm.tsx` 与它们的 CSS）、`desktop/web/src/pages/readonly1/runtimes-logic.ts`、`runtimes-quizs-logic.ts`、`runtimes-styles.css`、`desktop/web/src/pages/RuntimesPage.tsx`、`desktop/web/src/mock/writes.ts`、`mock/quizs.ts`、`mock/hub-roles.ts`、`desktop/web/src/mock/*.json`（src/mock 不加 JSON，src/mock 仍恰 14 份 JSON）；`desktop/web/src/pages` 顶层不加 `*Page.tsx`（仍恰 9 个）。
- 不改 T054/T055 的既有包内测试（`jobs-api.test.ts`、`jobs-store.test.ts`、`jobs-scan-page.test.tsx`、`jobs-store-runtime.test.ts`、`jobs-probe-page.test.tsx`、`jobs-models-page.test.tsx`）、`live-api.test.ts`、`live-transport.test.ts`、`live-mode.test.ts`、`page-runtimes-empty.test.tsx`、`writes-remove.test.tsx`、`page-static.test.ts`。
- 不改 `ts/packages/**`、`scripts/**`；不新增依赖、不改锁文件（`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字不动）。

## Repository facts
以下事实都在本回合的工作目录里逐条读过（行号按基线 cb255d54）。

### 本机服务（不改，只照它的规则写前端）
- `ts/packages/ui/src/jobroutes.ts`
  - `:31` `JOB_KINDS` 六个：`doctor`、`doctor-record`、`runtime-scan`、`runtime-probe`、`models`、`search`；`:39` `doctor` 的 argv 是 `["config","doctor","--json"]`。
  - `:48-55` `JOB_TIMEOUTS`：`doctor` 600、`doctor-record` 600、`runtime-scan` 150、`runtime-probe` 150、`models` 120、`search` 180。
  - `:69` `SCHEMA.doctor` 的 required 与 optional 都是空数组（正文只有 `kind` 一个键）；`:142-170` `validateJob` 要求正文是 JSON 对象、kind 合法、**键恰好**（多一个键回 400「请求体含有未知键」）。
  - `:173-184` `buildArgv`：`doctor` → `["config","doctor","--json"]`。
  - `:210-240` 作业落定：内核退出码 0 是 succeeded，否则 failed（reason "exit"），**信封照样带着内核的 data**；`messages` 只留 stderr 里以 `ERROR` 或 `WARN` 开头的行（doctor 因有角色没就绪退出 1 时 stderr 多半没有 ERROR 行，原文只会是「内核报错（退出码 1）」）。
  - `:227` data 过 `redactJson(parsed, allow)`，doctor 的 allow 是 undefined（`:59`），走 `redactJsonPlain`。

### 内核（不改，只照它的输出形状写前端）
- `ts/packages/config/src/roles-probe.ts`
  - `:339-357` `doctor`：data 是 `{ready, roles: [...]}`；**有角色没就绪时退出码 1**（作业落 failed，但 data 里有完整结果）。
  - `:350` 不是无头的行是 `{role, mode, problems: [], text, ready: true}`（mode 是 null 时 text 由内核写好）。
  - `:226-289` 无头行一定有 `role`、`mode`、`problems`、`profile`、`runtime`、`adapter`、`provider`、`model`、`thinking`、`connected`、`notes`、`allowed`、`credentials`、`ready`；**可能缺的键**：`command`、`source`、`version`（只在找到命令时才有，`:235-240`）、`model_listed`、`auth_ready`、`thinking_supported`（只在 adapter 是 pi 且有 provider/model 时才有，`:248-261`）。
  - `allowed` 为 null 表示没设允许列表；`credentials` 是「变量名 → 可用与否」，只有变量名，从来没有值。
  - `:300-337` 文本模式的措辞：就绪写「就绪」、未就绪写「未就绪」，允许列表 null 写「不限制」，凭据写「<变量名> 可用 / 不可用」（空时「无」），最后一行是「全部就绪」或「有未就绪的角色」。
- `ts/packages/config/src/roles-commands.ts:400-415` `roleText`：不是无头的角色的 text 形如「interactive_host · claude-code（交互宿主的模型不由 Themis 切换）」、「manual」、「disabled」、「由合同决定（没有写 roles.X）」。
- `ts/packages/base/src/secrets.ts:52-57`、`:129-141` `redactJsonPlain`：键名像凭据（`credentials` 命中）时子树里的**字符串**换成 `<redacted>`，布尔原样保留；变量名本身像令牌时键名才换成 `<redacted>`（`STEP_API_KEY` 不会）。

### 前端现状
- `desktop/web/src/api.ts`
  - `:153-154` `export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';`（本片扩成四类）。
  - `:773-787` `startJob(kind: JobKind, runtime?: string)`：真实分支 `client.postRaw<unknown>('/api/v1/jobs', body, 15)`，`:777` 的正文是 `kind === 'runtime-scan' || runtime == null || runtime === '' ? { kind } : { kind, runtime }`——**doctor 不带 runtime 时本来就发 `{ kind }`，函数体不用改**；201 才算建成；桩分支 `mockStartJob(kind, runtime)`。`:789` `getJob(id)`、`:801` `cancelJob(id)`。
  - 全文不许出现网络接口名（fetch / XMLHttpRequest / EventSource / WebSocket，连注释也不许——t037 S03）。
- `desktop/web/src/jobs/jobStore.ts`（T055）
  - `:20` `KINDS = ['runtime-scan', 'runtime-probe', 'models']`；`:26-30` `snaps`；`:33` `subscribers`（三张 `Record<JobKind, …>`）。
  - `:52-77` `doCreate`；`:79-85` `ensureJob(kind, runtime?)`；`:87-93` `restartJob(kind, runtime?)`；`:95-104` `cancelJob(kind)`；`:129-140` `scheduleNext`（**没有作业时不排计时器**）；`:158-190` `useJob(kind, runtime?)`；`:192-201` `resetJobStoreForTests()`；另导出 `useBusyRuntime(kind)`（本片不用）。
  - 槽是**按 kind 一类一个**，槽里记 `runtime`（doctor 是 null）；`ensureJob('doctor')` / `restartJob('doctor')` / `useJob('doctor')` 都可不带 runtime。
- `desktop/web/src/jobs/JobCard.tsx`（T055）
  - `:12` 时限表 `{ 'runtime-scan': 150, 'runtime-probe': 150, models: 120 }`；`:13-17` 失败标题表（扫描失败 / 探测失败 / 列模型失败）；`:18-22` 进度条 aria-label 表（扫描进行中 / 探测进行中 / 列模型进行中）。
  - props：`title / job / elapsedSeconds / createError / onCancel / children / kind?（缺省 'runtime-scan'）/ failedDetail?`。
  - `:75-81` failed 分支固定显示 `JOB_FAILED_TITLES[kind]` 与 `errorText(job.envelope)`（messages 为空时是「内核报错（退出码 N）」）——**这正是本片要绕开的笼统失败**。
  - `:47` 有 `cancelSent` 状态（取消请求发出后就地禁用 [取消]）——作业换了要重新挂载（见「写法钉死」）。
- `desktop/web/src/mock/jobs.ts`（T055，198 行）
  - `:141-145` `mockStartJob`：不是 `runtime-scan` 又没带 runtime 的一律回 400——**doctor 不带 runtime，要放行**。
  - `:108-113` `kindFailedEnvelope`：不是 probe 的一律当成 models——**要加 doctor 一支**（没有 data，一行示意原文）。
  - `:167-172` `terminalEnvelope`：扫描恒 succeeded、探测照奇偶份、列模型恒 succeeded——**要加 doctor 一支**。
  - 五个开关的语义：`loading` 一直 running；`error` 第一次查询就 failed（没有 data）；`data`/`offline`/`empty` 第一次查询 running、第二次终态。不用计时器、不引 JSON。
- `desktop/web/src/writes/RuntimeProbe.tsx`（T055，现成的写法参照）：入口组件 + 对话框的内外两层、`ensureJob`/`restartJob`/`useJob`/`useBusyRuntime` 的用法、`JobCard` 从 `'../jobs/JobCard'` 直接引、`kind="runtime-probe"`、`import './runtime-probe.css';` 放在组件 import 之后、命令来源的四个标签照抄成一张小表（不引 `runtimes-logic.ts`）。
- `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`
  - `:1-3` 文件头注释；`:2` 从 `../../api` **只许 import type**；`:104-111` `<Section title="就绪检查">` 里一个 `div.rt-ready-area`，放 `<DisabledAction label="运行就绪检查" variant="secondary" icon={<PlayIcon width={16} height={16} />} />` 与 `p.rt-ready`（「还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据；运行入口在第二阶段接入。」）。
  - 其余照旧要守住的记号：`title="已登记"`、`title="就绪检查"`、`aria-label="已登记的 runtime"`、`rt-table`、`'runtime.remove'`、`args: { runtime`、`reload?:`、`useWriteFlow(`、`版本: '—'`、`canProbe(`/`canModels(`、`import './runtimes-styles.css'`。
- `desktop/web/src/pages/readonly1/roles-logic.ts:5-25` 角色中文名（规划审核端 / 合同端 / 执行端 / 调度代理）与模式中文名；`desktop/web/src/mock/roles.json`：四个角色（规划审核端 interactive_host、合同端 manual、执行端 headless profile step-high runtime pi adapter pi provider bb model step-5-preview thinking high、调度代理 disabled）。
- `desktop/web/src/components/Button.tsx`：`Button` 的 props 是 `variant`（primary/secondary/ghost/danger）、`size`（sm/md/lg）、`loading`、图标走 children；`data-variant` 与 `data-size` 落在 button 上。
- `desktop/web/src/shell/DisabledAction.tsx`：禁用的入口是 Tooltip 包一个 disabled 的 Button（reason 缺省「第二阶段接入」）。

### 门禁与既有测试的核查结论（本片**必然**要改的那几处，逐行读过）
- `tests/test_gate_t009_baseline.py`
  - `:2895` it 标题「就绪检查：h2 加**禁用**的 [运行就绪检查]（PlayIcon，secondary），虚线空框原文；没有按版本核验的下拉与 [核验]」；`:2904` `expect(b.disabled).toBe(true)`；`:2905` `data-variant` 是 secondary；`:2906` 带 svg（PlayIcon）；`:2907` 空框原文逐字（带「；运行入口在第二阶段接入。」）；`:2908` 没有按版本核验的下拉；`:2909` 没有 [核验]。
  - `:2970` it 标题「运行时页：仍禁用的写入口悬停出「第二阶段接入」；可用按钮只有刷新、T022 接上的 [删除…]、T041 接上的 [手动登记…] 与 T055 接上的 [探测]、[模型]」；`:2974` `expect(outsideWhitelist(['删除…','手动登记…','扫描 PATH', '探测', '模型'])).toEqual([])`；`:2975` `expect(disabledButtons().length).toBeGreaterThan(0)`；`:2976` `tooltipTexts().forEach(...)`（`:2939-2951` 的 `tooltipTexts()` 只看禁用按钮，没有禁用钮时是空转；它仍会调一次 `vi.useFakeTimers()`）。
  - `:622-625`（RUNTIMES_SPECS）就绪检查空框的三条取值规则在 **readonly1 的四份 CSS 合并后**求值：`.rt-ready` 的 `padding: var(--tt-space-5)`、`text-align: center`、`border: 1px dashed var(--tt-border-strong)`、`border-radius: var(--tt-radius-md)`、`font: var(--tt-text-sm)`、`color: var(--tt-text-3)`——**`.rt-ready` 的规则必须留在 `desktop/web/src/pages/readonly1/runtimes-styles.css`（`:11-17`），不许搬走也不许改**。
  - `:3558-3603` 样式表接线与构建产物检查只针对那四份 CSS（`CSS_FILES`），但新加的 CSS 仍要满足令牌与 px 注释规则（`:478-521`、`:833-845`）。
- `tests/test_gate_t023_baseline.py`
  - `:805-811` it「[运行就绪检查] 照旧禁用，悬停提示「第二阶段接入」」：`:808` `expect(ready.disabled).toBe(true)`、`:809` `vi.useFakeTimers()`、`:810` `expect(await tipOf(ready)).toBe('第二阶段接入')`。
  - `:37` 与 `:1401` 两处文档串里写着「[运行就绪检查] 照旧禁用」。
  - `:97-101` `BAD_ENTRY_FRAGMENTS`（入口文件的禁字表）里**没有**就绪检查的文案，所以「逐字文案不进入口文件」是本片的写法口径（照 T055），不是这条门禁的硬要求。
- `tests/test_gate_t043_baseline.py:491-492`：`for needle in ('title="已登记"', 'title="就绪检查"', 'aria-label="已登记的 runtime"', "rt-table", "还没有运行过就绪检查", 'label="运行就绪检查"', "runtime.remove", "useWriteFlow"):`——文案挪进新组件后，这两个记号要换成新组件的记号；同一行其余记号照旧。`:497` 与 t009 D13（`:3506`）要求 readonly1 下的视图从 `../../api` **只许 import type**。
- `tests/test_gate_t045_baseline.py:560`：`if not re.search(r"it\('角色页 \d+（[^']*）?、运行时页 1、总览 0'", app_text) and "'角色页 11'" not in app_text:`；`:563` `for token, pat in (("运行时页 1", r"toBe\(1\)"), ("总览 0", r"toBe\(0\)")):`。
- `tests/test_gate_t054_baseline.py:717-718`：`if "export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';" not in code:`（逐字三类）。
- `tests/test_gate_t055_baseline.py`
  - `:109` `JOBKIND_THREE = "export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';"`；`:532-533` S01 用它逐字核 api.ts；`:926-929` S09 反查 t054 里有没有这个逐字记号。
  - `:580` S02 的 `KINDS` 正则 `KINDS[^=]*=\s*\[[^\]]*'runtime-scan'[^\]]*'runtime-probe'[^\]]*'models'[^\]]*\]`（**三类要保持原来的次序，doctor 加在末尾**；`\[[^\]]*…\]` 允许多加）。
  - `:749` S05 的记号表里有 `('label="运行就绪检查"', "[运行就绪检查] 仍禁用")`——文案挪进新组件后这一条要换掉。
  - `:918-923` S09 要 t045 里有「运行时页 1」与 `("运行时页 1", r"toBe\(1\)")`；`:932-935` 要 page-app 里有「运行时页 1」与 `.toBe(1)`。
  - S03（JobCard）与 S04（桩）只查既有记号**在位**，多加一类不红。
- `desktop/web/tests/page-app.test.tsx:91-98`：describe 标题「写入口个数（过渡）」一字不动；`:93` it 标题「…运行时页 1、总览 0」；`:98` `expect(disabled().length, '运行时页').toBe(1)`（文件里再没有别的 `.toBe(1)`）。
- `desktop/web/tests/page-runtimes.test.tsx:101-124`：`:101` it 标题「操作规则：[删除…] 与 [探测]、[模型] 都可点」、`:109` `toBe(false)`；`:115-124` 就绪检查区那一条（`:119` `expect(b?.disabled).toBe(true)`、`:123` `expect(text(sec)).toContain('还没有运行过就绪检查。')`）。

### 工具链与锁文件
- `desktop/web` 用 npm（`npm test` = `vitest run`，`npm run typecheck` = `tsc --noEmit`，`npm run build` = `tsc --noEmit && vite build`；内核核实：desktop/web 已装 vitest 2.1.8、react 18.3.1）；仓库门禁用 `python -m pytest`。
- `dependency_changes: forbidden`：`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字都不许动（t048 还按字节冻结了前两个）。

### 基线检查
- 合同端只读，没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 合同检查在基线上的结果由内核在执行之前跑过（基线检查记录）：本片门禁在基线上应当失败（断言失败，不是收集失败），既有门禁基准照旧通过；执行端不必再跑一遍整套测试。

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
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t054_baseline.py
  - tests/test_gate_t055_baseline.py
- allowed_new_files:
  - desktop/web/src/writes/RuntimeDoctor.tsx
  - desktop/web/src/writes/runtime-doctor.css
  - desktop/web/tests/jobs-doctor-page.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t056_*.py
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
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/page-runtimes-empty.test.tsx
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

### 作业客户端（`desktop/web/src/jobs/jobStore.ts` 与 `desktop/web/src/api.ts`）
- `api.ts`：`export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models' | 'doctor';`（**doctor 加在末尾**；`:153` 的注释同步改一句）。**`startJob` 的函数体一个字不改**：doctor 不带 runtime 时 `:777` 的三元本来就发 `{ kind }`，正文恰一个键。
- `jobStore.ts`：`KINDS` 扩成四类（`['runtime-scan', 'runtime-probe', 'models', 'doctor']`，次序照旧、doctor 在末尾）；`snaps`（`:26-30`）、`subscribers`（`:33`）两张 `Record<JobKind, …>` 各加 doctor 一项（少了会 tsc 报错，Vitest 不报）；`inflight` 是 `Partial<Record<…>>`，不用改。
- doctor 的槽里 `runtime` 是 null：`ensureJob('doctor')`、`restartJob('doctor')`、`useJob('doctor')` 都不带 runtime 参数（`runtime?: string` 缺省即 null）。
- 其余（T054/T055 的公式、setTimeout 链、`scheduleNext` 的「没有作业就不排计时器」、五个既有导出、`useBusyRuntime`）一字不改；既有 jobs-* 包内测试与 t054/t055 的探针照旧过。

### 作业进度卡（`desktop/web/src/jobs/JobCard.tsx`）
- 只在三张按 kind 查的表里各加 doctor 一项，不加新 prop：
  | kind | 失败标题 | 进度条 aria-label | 超时秒数 |
  |---|---|---|---|
  | `doctor` | 就绪检查失败 | 就绪检查进行中 | 600 |
- 扫描、探测、列模型三支的字面（扫描失败 / 扫描进行中 / `runtime-scan: 150` / 已取消 / 超时模板）一字不动；只引 `job-card.css`；不许渲染 `role="status"`；不许写死颜色与内联 style。
- **JobCard 的 failed 分支照旧**（失败标题 + 内核报错原文）：本片的 doctor 结果块**不经过**这个分支（见下）。

### 新组件（`desktop/web/src/writes/RuntimeDoctor.tsx` 与 `desktop/web/src/writes/runtime-doctor.css`）
- 视图（readonly1）里那一节**只渲染这个组件**：`<Section title="就绪检查">` → `<div className="rt-ready-area">` → `<RuntimeDoctor />`。逐字文案全在组件里，入口文件里不出现就绪检查的文案（照 T055 的口径）。
- 组件从 `'../../writes/RuntimeDoctor'` 被视图引入；组件从 `'../jobs/JobCard'` 直接引 JobCard，从 `'../jobs/jobStore'` 引 `ensureJob`/`restartJob`/`useJob`（doctor 这一支**不用** `useBusyRuntime`：同类只有一个作业）。
- **组件不许跨层引 `src/pages`**（不许 `from '../pages…'`、不许 `from './roles-…'`）：角色中文名与命令来源的标签照 `RuntimeProbe.tsx` 的做法，各照抄一张小表写在组件里：
  - 角色名：`planning_review` 规划审核端、`contract` 合同端、`execution` 执行端、`scheduler_agent` 调度代理（未知的原样显示）；
  - 命令来源：`env` 环境变量、`local` 本机文件、`path` PATH、`missing` 找不到。
- 组件自带样式表：`import './runtime-doctor.css';` 放在组件 import 之后；类名一律以 `.rd-` 开头（不与别的样式表共用类名）；只用 `--tt-*` 令牌，不写十六进制颜色与颜色函数、不写 `style={{`；除 `0` 与 `1px` 外的 px 字面量同一行带出处注释。
- **`.rt-ready` 的规则留在 `desktop/web/src/pages/readonly1/runtimes-styles.css` 不动**（t009 把 readonly1 的四份 CSS 合并后求值 `.rt-ready` 的三条取值）；组件渲染那个虚线框时用 class `rt-ready`（页面样式表由视图加载）。
- 组件的内容与状态（**逐字文案照抄**）：
  1. **按钮**：文字始终逐字「运行就绪检查」，`variant="secondary"`、`size="md"`、图标是 `<PlayIcon width={16} height={16} />`（放在文字前）。**运行中只禁用，不换字**（旧断言按文字找按钮）。
     - 禁用条件：作业在创建中（creating）、排队（queued）或运行中（running）时按钮 `disabled`。
     - 点击：没有作业也没有创建失败 → `ensureJob('doctor')`；作业已终态（succeeded / failed / cancelled / timed_out）或创建失败 → `restartJob('doctor')`（新作业，新的 `t0`）。
  2. **没跑过时**（没有作业、没有创建失败）：不渲染 JobCard（JobCard 在 job 与 createError 都为空时会显示「已用 0 秒」的空进度条），渲染虚线框 `p.rt-ready`，里面的文字逐字「还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。」（**去掉「运行入口在第二阶段接入」**）。
  3. **运行中**（creating / queued / running）：渲染 JobCard（`kind="doctor"`、`title="就绪检查"`），另外另起一行写逐字「离开这个页面作业也会继续，回来时显示结果。」（小字、用 `--tt-text-3`）。JobCard 自己显示进度条（aria-label「就绪检查进行中」）、「已用 N 秒」与 [取消]。
  4. **JobCard 的 key**：`<JobCard key={job?.id ?? 'creating'} …>`——每个作业重新挂载。否则取消之后再点 [运行就绪检查]，新作业的 [取消] 一出来就是灰的（JobCard 内部有 `cancelSent` 状态）。
  5. **结果块**（自己渲染，不走 JobCard 的 succeeded/failed 分支）：
     - **什么时候渲染**：作业 `succeeded`，或者作业 `failed` **且 data 合法**（判据见下）。这两种状态渲染**同一个**结果块。
     - **data 合法**的判据：`job.envelope.data` 是对象，且 `data.roles` 是数组（内核报错时没有 data）。
     - **succeeded 时**结果块放在 JobCard 的 children 里（JobCard 的 succeeded 分支只渲染 children）；**failed 且有 data 时不渲染 JobCard**（免得出现笼统的「就绪检查失败」与「内核报错（退出码 1）」），直接渲染结果块。
     - **汇总**一行（结果块的第一行）：
       - `data.ready` 为真 → 逐字「全部就绪」；
       - `data.ready` 为假 → 逐字「有未就绪的角色（N 个）」，N 是 `roles` 里 `ready` 不为真的角色个数（照设计 §7.22 与内核文本模式的措辞）。
     - **无头角色**（行里有 `mode` 且 `mode === 'headless'`，或行里带 `profile`）：一张就绪卡，依次是
       - **卡头**：`✓ 就绪`（成功色）或 `✗ 未就绪`（danger 色）、角色中文名、`profile <profile>`（profile 缺失写 `profile —`），三段用「·」分隔；
       - **键值行**（`<dt>` 标签逐字，值按下表）：
         | 标签 | 值 |
         |---|---|
         | 命令 | 命令数组用空格连起来；后接「（来源：<来源标签>）」。命令缺键写「—」 |
         | 版本 | `version` 字符串；缺键写「—」 |
         | 模型在列表中 | `model_listed` 为真写「是」、为假写「否」、缺键写「—」 |
         | 登录 | `auth_ready` 为真写「是」、为假写「否」、缺键写「—」 |
         | 思考级别 | `<thinking>` 加「（本机 pi 接受这个档位）」或「（本机 pi 不接受这个档位）」（依 `thinking_supported`）；缺键写「—」 |
         | 允许列表 | `allowed` 为真写「是」、为假写「否」、为 null 写「不限制」 |
         | 凭据 | 每个变量名后写「可用」或「不可用」，用「、」连（如「STEP_API_KEY 不可用」）；一个变量都没有写「无」 |
         | 接通状态 | `connected` 为真写「已接通」、为假写「未接通」 |
       - **问题列表**：`problems` 逐条列成列表，用 danger 文字；没有就不渲染这一块。
       - **说明行**：`notes` 逐条，用 `--tt-text-3`；没有就不渲染这一块。
     - **不是无头的角色**：一行，逐字 `✓ <角色中文名> · <内核那一行 text>`（`✓`/`✗` 依该行 `ready`）；没有 `text` 就只写 `✓ <角色中文名>`。
     - 颜色只用令牌；不写 `role="status"`；不写死颜色；不写内联 style。
  6. **没有 data 的 failed**：照旧渲染 JobCard（`kind="doctor"`），显示失败标题「就绪检查失败」与内核报错原文（`envelope.messages` 逐行；空时是「内核报错（退出码 1）」）。
  7. **已取消**：JobCard 显示逐字「已取消」。**超时**：JobCard 显示逐字「超时（超过 600 秒），已停止」。**创建失败**：JobCard 显示失败标题与错误原文。

### 桩（`desktop/web/src/mock/jobs.ts`）
- `runtime-scan`、`runtime-probe`、`models` 三支**一字不改**（t054 S05 与 t055 S04 照旧过）。
- `mockStartJob`：`doctor` **不带 runtime 也要放行**（`:143` 那条 400 只对 `runtime-probe` 与 `models` 生效）；doctor 的作业照旧建（201），槽里 runtime 是 null。
- doctor 的终态信封（`terminalEnvelope` 加一支）：
  - **按 doctor 作业的次序奇偶**：第奇数次「执行端没就绪」——`data.ready` 为假、执行端一行 `ready` 为假、`credentials` 是 `{STEP_API_KEY: false}`、`problems` 有一条「凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY」、`ok` 为假、`exit_code` 为 1 → 作业落 **failed 但带 data**；
  - 第偶数次「全部就绪」——`data.ready` 为真、四个角色都 `ready` 为真、`credentials` 是 `{STEP_API_KEY: true}`、`problems` 为空、`exit_code` 为 0 → 作业落 succeeded。
  - 四个角色照 `desktop/web/src/mock/roles.json`：规划审核端（`mode` interactive_host、`text`「interactive_host · claude-code（交互宿主的模型不由 Themis 切换）」、`ready` 真）、合同端（manual / 「manual」/ 真）、执行端（headless、profile step-high、runtime pi、adapter pi、provider bb、model step-5-preview、thinking high、connected 真、command 与 source 与 version 取示意值、model_listed / auth_ready / thinking_supported 真、`allowed` 真 或 null）、调度代理（disabled / 「disabled」/ 真）。
  - 计数照 `mock/jobs.ts` 既有做法（另设一个按 doctor 作业计数的 Map）；奇偶份只看作业次序，不看 runtime。
- `kindFailedEnvelope` 加 doctor 一支：`error` 开关下 doctor 落 failed、**没有 data**，一行示意原文（例如「ERROR 就绪检查失败：内核报错（示意）」）。
- 五个开关的语义照旧：`loading` 一直 running；`error` 第一次查询就 failed（没有 data）；`data`/`offline`/`empty` 第一次查询 running、第二次终态（doctor 的终态照上面的奇偶份）。
- 桩里不许出现 `WriteScenario`、不许引 `.json`、不许加计时器；`desktop/web/src/mock/writes.ts` 一个字不改。

### 运行时视图（`desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`）
- `<Section title="就绪检查">` 里那一节只渲染 `<RuntimeDoctor />`（`div.rt-ready-area` 保留在视图里）；`DisabledAction` 与 `PlayIcon` 不再用到时把它们的 import 删掉（`DisabledAction` 只在这一处用过，删干净）；`:1-3` 的文件头注释改成新的事实。
- 其余一字不改：已登记表（七列、版本列照旧「—」）、每行的 [探测]、[模型]、[删除…]（`runtime.remove` 写流程）、Quizs 一块、空态、三节次序（已登记、就绪检查、Quizs）、`useWriteFlow(reload)`、两节标题、`import './runtimes-styles.css'`。

### 边界输入
- 作业在跑（同类的作业同时只一个，§8.4）：按钮禁用；[取消] 只发一次 `POST /api/v1/jobs/<id>/cancel`，取消请求在途时 [取消] 禁用。
- 作业已结束（succeeded / failed / cancelled / timed_out）：按钮可点，点了是**新作业**（`restartJob`，新的 `t0`、新的作业号）；此时再点 [取消] 不存在。
- 创建失败（400 / 503 / 断线）：JobCard 显示失败标题与错误原文；按钮可点，点了重建。
- 查询回 404（服务重启过）：照 T055 的做法——错误信封并进 `job.envelope`、状态落 failed，于是显示内核报错原文（没有 data）。
- 作业因有角色没就绪落 failed 且带 data：**显示结果块**（汇总写「有未就绪的角色（N 个）」、问题列表照显示），**不显示**「就绪检查失败」与「内核报错（退出码 1）」。
- failed 且没有 data：显示内核报错原文，不显示结果块。
- 无头行缺键（找不到命令 → 没有 command/source/version；不是 pi 或缺 provider/model → 没有 model_listed/auth_ready/thinking_supported）：缺键一律写「—」，不报错、不留空。
- `allowed` 为 null：写「不限制」；`credentials` 为空：写「无」。
- 离开这一页再回来：作业在模块里（`jobStore` 按 kind 存槽），回来时看到的是**同一个作业**（还在跑就是进度，跑完就是结果），**不再发创建请求**；正在跑的作业离开页面时照旧在模块里跑完。
- 页面上没有 [核验] 按钮、没有按版本核验的下拉（t009 D10 照旧）。

### 并发、取消与状态变化
- 同一类只许一个在跑：doctor 一个槽，界面上按钮禁用 + store 的槽两头都挡（`ensureJob('doctor')` 在已有未终态作业时直接返回那个作业，不另建）。
- 轮询：setTimeout 链、每 1000 毫秒一次、卸载即停（`clearTimeout`）、重开先查一次；没有作业时不排计时器（T055 的口径照旧）。
- 取消：只发一次取消请求；作业的终态由下一次查询给出；取消后再点按钮是新作业（新作业的 [取消] 可点，见「JobCard 的 key」）。

### 写法钉死（与本片门禁基准文件逐条对表）
本片门禁由门禁端交付（`tests/test_gate_t056_baseline.py`），它不在当前基线里，由门禁那一版合同产出并集成；基线上它应当失败（断言失败，不是收集失败）。执行端第 1 步要读门禁文件并与这一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
- `desktop/web/src/api.ts`：`export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models' | 'doctor';`；`export function startJob(` / `getJob(` / `cancelJob(`；`startJob` 的函数体里有 `postRaw`、`{ kind }`（字面）、`{ kind, runtime }`、`mockStartJob(kind, runtime)`、时限 `15`；**不许出现 `runtime: undefined`**；`JobState` 六个值与 `JobView` 八键照旧。
- `desktop/web/src/jobs/jobStore.ts`：五个既有 `export function`（ensureJob / restartJob / cancelJob / useJob / resetJobStoreForTests）与 `useBusyRuntime` 都在；`KINDS` 四类且次序是 scan、probe、models、doctor；`snaps` 与 `subscribers` 各有 doctor 一项；`setTimeout(` 在、`setInterval(` 不在、`1000`、`clearTimeout`；已用秒数逐字 `Math.floor((Date.now() - t0) / 1000)`；`useSyncExternalStore`；从 `'../api'` 引 `startJob(` / `getJob(` / `cancelJob(`；`JobKind` 在。
- `desktop/web/src/jobs/JobCard.tsx`：`export function JobCard(`；props 里有 title / onCancel / children / kind / failedDetail；`role="progressbar"`；[取消]；「已用 ${…} 秒」；「扫描失败」「已取消」「超时（超过 ${…} 秒），已停止」；三张表里有 doctor 的「就绪检查失败」「就绪检查进行中」与 600；`runtime-scan: 150` 照旧在；**只许 `import './job-card.css';`**。
- `desktop/web/src/mock/jobs.ts`：三个既有导出；不用计时器；不引 JSON；`'runtime-scan'`、`'runtime-probe'`、`'models'`、`'doctor'` 都在；既有扫描夹具与文案一字不改。
- `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`：`<DisabledAction label="运行就绪检查"` **不在**；`'../../writes/RuntimeDoctor'` 在；`'runtime.remove'`、`args: { runtime`、`reload?:`、`useWriteFlow(`、`canProbe(`、`canModels(`、`"已登记"`、`"就绪检查"`、`版本: '—'`、`import './runtimes-styles.css'` 都在。
- `desktop/web/src/writes/RuntimeDoctor.tsx`：`import './runtime-doctor.css';` 在位；`ensureJob(` / `restartJob(` / `useJob(` 用的是 `'doctor'`；`JobCard` 从 `'../jobs/JobCard'` 引；`kind="doctor"`；`key={job?.id ?? 'creating'}`；逐字文案在（「运行就绪检查」「就绪检查」「就绪检查失败」「就绪检查进行中」「离开这个页面作业也会继续，回来时显示结果。」「还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。」「全部就绪」「有未就绪的角色」「就绪」「未就绪」「是」「否」「不限制」「无」「可用」「不可用」「已接通」「未接通」「本机 pi 接受这个档位」「本机 pi 不接受这个档位」「命令」「版本」「模型在列表中」「登录」「思考级别」「允许列表」「凭据」「接通状态」「环境变量」「本机文件」「PATH」「找不到」「规划审核端」「合同端」「执行端」「调度代理」）；不出现 `role="status"`、不写死颜色、不写内联 style、不跨层引 `src/pages`。
- `desktop/web/src/writes/runtime-doctor.css`：只用 `--tt-*` 令牌；类名以 `.rd-` 开头且不与别的样式表共用；除 0 与 1px 外的 px 字面量同行带出处注释。

### 兼容性（本片推翻的旧断言，逐处写明只改哪一处）
以下文件的这一处要改，**只改这一处**，其余一个字不动：
- `tests/test_gate_t009_baseline.py`
  - `:2895` 的 it 标题：「就绪检查：h2 加禁用的 [运行就绪检查]（PlayIcon，secondary），虚线空框原文；没有按版本核验的下拉与 [核验]」→「就绪检查：h2 加可点的 [运行就绪检查]（PlayIcon，secondary），虚线空框原文；没有按版本核验的下拉与 [核验]」（只把「禁用」改成「可点」）。
  - `:2904`：`expect(b.disabled).toBe(true);` → `expect(b.disabled).toBe(false);`（只改 `true`→`false`）；`:2905`（data-variant 是 secondary）、`:2906`（带 svg）照旧。
  - `:2907`：`expect(textOf(sec)).toContain('还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据；运行入口在第二阶段接入。');` → 同一句的 `toContain` 里换成「还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。」（**去掉「；运行入口在第二阶段接入」**）；`:2908`、`:2909` 照旧。
  - `:2970` 的 it 标题：保留「…与 T055 接上的 [探测]、[模型]」这一段（T055 门禁 S09 认它），后面再接本片 → 「运行时页：仍禁用的写入口悬停出「第二阶段接入」；可用按钮只有刷新、T022 接上的 [删除…]、T041 接上的 [手动登记…]、T055 接上的 [探测]、[模型] 与 T056 接上的 [运行就绪检查]」。
  - `:2974`：`expect(outsideWhitelist(['删除…','手动登记…','扫描 PATH', '探测', '模型'])).toEqual([]);` → 白名单里在「'模型'」后面加「'运行就绪检查'」（**"'扫描 PATH', '探测', '模型'" 要照旧连着写**，T055 门禁 S09 认它）。
  - `:2975`：`expect(disabledButtons().length).toBeGreaterThan(0);` → `expect(disabledButtons().length).toBe(0);`；`:2976` 的 `tooltipTexts().forEach(...)` 可以留着不动（没有禁用钮时是空转；它仍会调一次 `vi.useFakeTimers()`，可以留着）。
- `tests/test_gate_t023_baseline.py`
  - `:805` 的 it 标题：「[运行就绪检查] 照旧禁用，悬停提示「第二阶段接入」」→「[运行就绪检查] 可点（secondary 带 PlayIcon），空框原文照旧」。
  - `:808`：`expect(ready.disabled).toBe(true);` → `expect(ready.disabled).toBe(false);`；**删掉 `:809`（`vi.useFakeTimers();`）与 `:810`（悬停提示断言）两行**。
  - `:37` 文档串里「[编辑]/[探测]/[运行就绪检查] 照旧禁用提示「第二阶段接入」」改成「[编辑] 照旧禁用提示「第二阶段接入」、[运行就绪检查] 可点」；`:1401` 文档串里「[编辑]/[运行就绪检查] 照旧禁用」改成「[编辑] 照旧禁用、[运行就绪检查] 可点」。这两处只是文档串。
- `tests/test_gate_t043_baseline.py`
  - `:491-492` 的记号元组：把 `"还没有运行过就绪检查"` 与 `'label="运行就绪检查"'` 这两个记号换成新组件的记号 `"RuntimeDoctor"`（视图里 `import { RuntimeDoctor } from '../../writes/RuntimeDoctor';` 就含它），其余记号（`title="已登记"`、`title="就绪检查"`、`aria-label="已登记的 runtime"`、`rt-table`、`runtime.remove`、`useWriteFlow`）照旧。
- `tests/test_gate_t045_baseline.py`
  - `:560`：`if not re.search(r"it\('角色页 \d+（[^']*）?、运行时页 1、总览 0'", app_text) and "'角色页 11'" not in app_text:` → 正则里的「运行时页 1」改成「运行时页 0」（其余照旧）。
  - `:563`：`for token, pat in (("运行时页 1", r"toBe\(1\)"), ("总览 0", r"toBe\(0\)")):` → `for token, pat in (("运行时页 0", r"toBe\(0\)"), ("总览 0", r"toBe\(0\)")):`；`:553-559`、`:564-565` 照旧。
- `tests/test_gate_t054_baseline.py`
  - `:717-718` 的 JobKind 逐字断言改成**「含这几类」**（后面接 doctor-record、search 的片不必再改这一处）：
    ```python
    jk = re.search(r"export type JobKind = ([^;]+);", code)
    if jk is None:
        problems.append("api.ts 应有 export type JobKind = …")
    else:
        for kind in ("runtime-scan", "runtime-probe", "models", "doctor"):
            if f"'{kind}'" not in jk.group(1):
                problems.append(f"api.ts 的 JobKind 应含 '{kind}'")
    ```
    （把原来那两行 `if "export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';" not in code:` 与它的 problems 换成上面这段；`:718` 的旧文案随之为本段取代。`:719` 起的 `JobState`、`JobView`、`toJobView`、`startJob`/`getJob`/`cancelJob` 各项**都照旧，不许改**。）
- `tests/test_gate_t055_baseline.py`
  - `:109`：`JOBKIND_THREE = "export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';"` → `JOBKINDS = ("runtime-scan", "runtime-probe", "models", "doctor")`（改成「含这几类」的元组）。
  - `:532-533`：S01 里那两行改成
    ```python
    jk = re.search(r"export type JobKind = ([^;]+);", code)
    if jk is None:
        problems.append("api.ts 应有 export type JobKind = …")
    else:
        for kind in JOBKINDS:
            if f"'{kind}'" not in jk.group(1):
                problems.append(f"api.ts 的 JobKind 应含 '{kind}'")
    ```
  - `:749`：S05 的记号表里把 `('label="运行就绪检查"', "[运行就绪检查] 仍禁用"),` 换成 `("'../../writes/RuntimeDoctor'", "就绪检查走新组件"),`（同一行其余记号照旧）。
  - `:918-923`（S09 反查 t045）：`"运行时页 1" not in t045` → `"运行时页 0" not in t045`；`'("运行时页 1", r"toBe\(1\)")' not in t045` → `'("运行时页 0", r"toBe\(0\)")' not in t045`；`if "运行时页 4" in t045:` 照旧，并**加**一条 `if "运行时页 1" in t045:` 的残留检查。
  - `:926-929`（S09 反查 t054）：`if f'if "{JOBKIND_THREE}" not in code:' not in t054:` → `if "export type JobKind = ([^;]+);" not in t054:`（t054 改成按那一行核对「含这几类」）；`:927` 的 problems 文案跟着改；`:928-929` 的旧记号残留检查（`"export type JobKind = 'runtime-scan';"` 不该再残留）照旧。
  - `:930-935`（S09 反查包内 page-app）：`if ".toBe(1)" not in app_test or "运行时页 4" in app_test:` → `if "expect(disabled().length, '运行时页').toBe(0)" not in app_test or "运行时页 1" in app_test:`（运行时页那一条改成 `toBe(0)`，且不应再残留「运行时页 1」）；`:931` 附近的 problems 文案跟着改。
  - `:889-893` 的 S09 文档串里「运行时页 4→1」「toBe(1)」的说法改成「运行时页 1→0」「toBe(0)」（只是文档串）。
  - S02、S03、S04、S06、S07、S08 各段**都照旧，不许改**（KINDS 的正则允许多加一类；JobCard 与桩只查既有记号在位）。
- `desktop/web/tests/page-app.test.tsx`
  - `:93` 的 it 标题里「运行时页 1」改成「运行时页 0」；`:98` 的 `expect(disabled().length, '运行时页').toBe(1)` 改成 `toBe(0)`；`:91` 的 describe 标题「写入口个数（过渡）」一字不动（t037 S06、t045 认它）；`:96` 的角色页 6 与 `:100` 的总览 0 照旧。
- `desktop/web/tests/page-runtimes.test.tsx`
  - `:115` 的 it 标题「[运行就绪检查] 禁用 secondary 带 PlayIcon，虚线空框，无按版本核验下拉」→「[运行就绪检查] 可点 secondary 带 PlayIcon，虚线空框，无按版本核验下拉」；
  - `:119` `expect(b?.disabled).toBe(true);` → `expect(b?.disabled).toBe(false);`；
  - `:120`（data-variant 是 secondary）、`:121`（带 svg）、`:123`（`toContain('还没有运行过就绪检查。')`）、`:124`（没有下拉、没有 [核验]）照旧。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件** `tests/test_gate_t056_baseline.py`（只读；本回合的基线上它还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/api.ts`**：`JobKind` 扩成四类（逐字 `export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models' | 'doctor';`）；`:153` 的注释同步改一句；`startJob` 的函数体**一个字不改**；`getJob` / `cancelJob` 与其余导出照旧；全文不许出现网络接口名。
3. **`desktop/web/src/jobs/jobStore.ts`**：`KINDS` 扩成四类（doctor 在末尾）；`snaps` 与 `subscribers` 各加 doctor 一项；其余（T055 的公式、setTimeout 链、404 并进 envelope、六个导出）照旧。
4. **`desktop/web/src/jobs/JobCard.tsx`**：三张按 kind 的表各加 doctor 一项（失败标题「就绪检查失败」、aria-label「就绪检查进行中」、超时 600）；扫描那一支的字面与 `runtime-scan: 150` 留在文件里；`job-card.css` 一个字不改。
5. **`desktop/web/src/mock/jobs.ts`**：放行 doctor（`:143` 的 400 只挡 probe 与 models）；`kindFailedEnvelope` 与 `terminalEnvelope` 各加 doctor 一支（奇偶两份：奇数次执行端没就绪、落 failed 带 data；偶数次全部就绪）；`runtime-scan`、`runtime-probe`、`models` 三支一字不改；不用计时器、不引 JSON。
6. **新建 `desktop/web/src/writes/RuntimeDoctor.tsx` 与 `desktop/web/src/writes/runtime-doctor.css`**：按钮（逐字「运行就绪检查」、secondary/md、PlayIcon 16、运行中禁用）、没跑过时的虚线框与新句子、运行中那句「离开这个页面作业也会继续，回来时显示结果。」、`useJob('doctor')`、`<JobCard key={job?.id ?? 'creating'} kind="doctor" …>`、结果块（汇总、就绪卡、其他角色一行）、有 data 的 failed 走自己的结果块、没有 data 的失败与取消与超时交给 JobCard；`import './runtime-doctor.css';` 在位；角色名与来源标签各照抄一张小表；不跨层引 `src/pages`。
7. **`desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`**：「就绪检查」一节只渲染 `<RuntimeDoctor />`；删掉不再用的 `DisabledAction` 与 `PlayIcon` import；文件头注释改成新的事实；其余一字不改。
8. **逐处改旧断言**（照「兼容性」一节，逐条只改那一处）：`tests/test_gate_t009_baseline.py`（:2895、:2904、:2907、:2970、:2974、:2975）、`tests/test_gate_t023_baseline.py`（:805、:808、:809-810、:37、:1401）、`tests/test_gate_t043_baseline.py`（:491-492）、`tests/test_gate_t045_baseline.py`（:560、:563）、`tests/test_gate_t054_baseline.py`（:717-718）、`tests/test_gate_t055_baseline.py`（:109、:532-533、:749、:918-923、:926-929、:930-935、:889-893 的文档串）、`desktop/web/tests/page-app.test.tsx`（:93、:98）、`desktop/web/tests/page-runtimes.test.tsx`（:115、:119）；改完把仍钉着旧口径的地方再搜一遍（关键字：`运行就绪检查`、`第二阶段接入`、`运行时页 1`、`toBe\(1\)`、`export type JobKind = 'runtime-scan' \| 'runtime-probe' \| 'models';`、`label="运行就绪检查"`），确认没有漏网的旧断言。
9. **新增包内测试 `desktop/web/tests/jobs-doctor-page.test.tsx`**（写法照 `desktop/web/tests/jobs-probe-page.test.tsx` 的 harness：真实模式注入假客户端 `setLiveClientForTests`，桩模式走 `?mock=`；不许 `skip`/`only`/`todo`——`tests/test_gate_t002_baseline.py` 会扫全部 `*.test.*`；测真实实现，不 mock 被测组件），覆盖：
   (a) 点 [运行就绪检查] 发 `POST /api/v1/jobs`、正文恰 `{"kind":"doctor"}`，之后每秒查同一个作业号；
   (b) 运行中按钮禁用、显示「已用 N 秒」与 [取消]，另有「离开这个页面作业也会继续，回来时显示结果。」那一行；
   (c) succeeded：汇总「全部就绪」、无头角色的就绪卡（八个键值行、凭据的「可用 / 不可用」、允许列表 null 写「不限制」、思考级别那一行）、其他角色各一行；
   (d) failed 带 data：照样显示结果块、汇总写「有未就绪的角色（N 个）」、问题列表在、**没有**「就绪检查失败」；
   (e) failed 没有 data：显示内核报错原文、不显示结果块；
   (f) 已取消显示「已取消」；超时显示「超时（超过 600 秒），已停止」；
   (g) 卸载再挂载看到同一个作业、不再发创建请求；结束后再点发新的创建请求；
   (h) 取消之后再点：新作业的 [取消] 可点（JobCard 按作业号重新挂载）；
   (i) 缺键写「—」、允许列表 null 写「不限制」、凭据为空写「无」；
   (j) 桩模式：`?mock=loading` 一直 running、`?mock=error` 落 failed 且没有 data。
10. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → V04 → R01**（本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
11. 写执行报告；遇到合同未定义的行为（例如门禁端交付的 `tests/test_gate_t056_baseline.py` 与合同的「写法钉死」有实质冲突），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t056_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test -- tests/jobs-doctor-page.test.tsx` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py -q` · cwd：仓库根 · 超时：3240s · 期望退出码：0 · 输出须匹配：`\d+ passed`

上面每条检查的「输出须匹配」为什么在门禁机上成立（逐条说明；门禁检查与回归检查都用 pytest 的 `-q`，成功时最后一行是「N passed」，与已验收的 T055 合同 `.agent/plans/t055-desktop-web-runtime-probe.v1.md` 里同一种调用配同一个匹配，已在门禁机上成立过）：
- 前端那三条 vitest 检查是 `npm test`（= `vitest run`，desktop/web 已装 vitest 2.1.8——内核核实表里记着版本），vitest 2.x 成功时打印「Tests  N passed」；同一个匹配在 T055 合同的同一种调用上验收通过过。只跑指定文件的那一条另加 `不得出现 No test files found`（vitest 找不到文件时会这么写，防止「0 个用例也是绿色」）。
- 类型检查那条是 `npm run typecheck`（= `tsc --noEmit`），成功时无输出、退出码 0；这条不写输出须匹配（没有输出可匹配），只看退出码。
- 构建那条是 `npm run build`（= `tsc --noEmit && vite build`），vite 5.4.11 成功时打印「✓ built in …」；同一个匹配在 T055 合同里验收通过过。

## Definition of done
- D01：「就绪检查」一节的 [运行就绪检查] 是可点的 secondary/md 按钮（文字逐字「运行就绪检查」、带 PlayIcon 16），点它发 `POST /api/v1/jobs`、正文恰 `{"kind":"doctor"}`，随后每秒查同一个作业号；作业卡显示进度（aria-label 逐字「就绪检查进行中」）、「已用 N 秒」与 [取消]；目的：配好模型之后能真的跑一次就绪检查，而不是看一个灰按钮；证据：V01、V02、G01。
- D02：作业在跑时按钮禁用；结束后再点是新作业（新的创建请求）；离开这一页再回来看到的是同一个作业、不再发创建请求；目的：§8.4「同一类作业同时只能有一个」与「离开页面后作业继续运行」；证据：V01、V02、G01。
- D03：作业结束后这一节里显示一句汇总（全部就绪 / 有未就绪的角色（N 个））、每个无头角色一张就绪卡（卡头 ✓/✗ 与角色名与 profile；八个键值行；问题列表；说明行）、不是无头的角色各一行（✓/✗ + 角色中文名 + 内核那一行 text）；缺键写「—」、允许列表 null 写「不限制」、凭据写「变量名 可用 / 不可用」、凭据为空写「无」；目的：逐个角色看清楚能不能跑；证据：V01、V02、G01。
- D04：作业因有角色没就绪落 failed 但带着 data 时，照样显示结果块（汇总写有未就绪的角色、问题列表在），**不显示**笼统的「就绪检查失败」；没有 data 的失败显示内核报错原文；目的：失败也要看得见到底缺什么；证据：V01、V02、G01。
- D05：没跑过时那一节仍是虚线框，文字逐字「还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。」（去掉「运行入口在第二阶段接入」）；运行中另起一行写「离开这个页面作业也会继续，回来时显示结果。」；目的：这一节的版式照设计 §7.22 与 §8.4；证据：V01、V02、G01、R01。
- D06：作业客户端多一类 doctor（`JobKind` 四类、`KINDS`/`snaps`/`subscribers` 各一项、JobCard 三张表各一项：失败标题「就绪检查失败」、aria-label「就绪检查进行中」、超时 600）；扫描、探测、列模型三支一个字不变（T054/T055 的既有包内测试与探针原样照过）；目的：三类作业共用一张卡与一个槽，别的片不受影响；证据：V01、V02、V03、G01、R01、scope。
- D07：桩里 doctor 放行（不带 runtime 也能建）、奇数次执行端没就绪（凭据不可用、落 failed 带 data）、偶数次全部就绪，error 开关落 failed 且没有 data；扫描那一支一字不改；目的：没有真服务时也能看到两种结局；证据：V01、V02、G01。
- D08：视图里那一节只渲染新组件（逐字文案不进入口文件、视图从 `../../api` 仍只 import type、其余一字不改）；新组件自带样式表（只用 `--tt-*` 令牌、类名以 `.rd-` 开头、不写死颜色与内联 style、不跨层引 `src/pages`）；`.rt-ready` 的规则留在 runtimes-styles.css 不动；目的：这一片只加就绪检查，别顺手改别处；证据：V02、V04、G01、R01、scope。
- D09：新增 `desktop/web/tests/jobs-doctor-page.test.tsx`，覆盖 D01–D05 点名的每一项（含「有 data 与没有 data 两支」「取消与超时」「卸载再挂载是同一个作业」「结束后再点是新作业」「取消后再点新作业的 [取消] 可点」「缺键写「—」」「桩的 loading 与 error」），测真实实现，不许 `skip`/`only`/`todo`；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、V02、review。
- D10：旧断言逐处改到位：t009（:2895、:2904、:2907、:2970、:2974、:2975）、t023（:805、:808-810、:37、:1401）、t043（:491-492）、t045（:560、:563）、t054（:717-718）、t055（:109、:532-533、:749、:918-923、:926-929、:930-935、:889-893）、`desktop/web/tests/page-app.test.tsx`（:93、:98）、`desktop/web/tests/page-runtimes.test.tsx`（:115、:119）——每处只改上面写明的那一处，其余一个字不动；JobKind 的断言改成「含这几类」，后面再接 doctor-record、search 的片不必再改；目的：这些断言钉着「灰按钮 + 禁用数 1」，本片必然推翻，改法不许顺手改别的断言；证据：G01、R01、V02、scope。
- D11：所有修改都在允许集合内（可改 13 个文件、可新增 3 个文件），没有碰 forbidden_paths（`tests/test_gate_t056_*.py`、其余 52 份门禁基准、`components/**`、`shell/**`、`live/**`、`job-card.css`、T054/T055 的写入口组件与 CSS、既有写流程文件与 CSS、`runtimes-logic.ts`、`runtimes-styles.css`、`RuntimesPage.tsx`、`mock/*.json` 与 `mock/writes.ts`/`quizs.ts`/`hub-roles.ts`、T054/T055 的六份包内测试与 `live-*.test.ts`、`page-runtimes-empty.test.tsx`、`writes-remove.test.tsx`、`package.json` 与锁文件、`ts/packages/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope、review。
- D12：`npm test`、`npm run typecheck`、`npm run build` 全过，既有门禁基准照旧通过；目的：不能为了接一个入口把别处弄坏；证据：V02、V03、V04、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `jobroutes.ts` 的正文校验已经不是「键恰好」、`JOB_TIMEOUTS` 的 doctor 不是 600、`roles-probe.ts` 的 doctor data 形状变了、`redactJsonPlain` 不再保留布尔、`jobStore.ts` 的 `scheduleNext` 已经不是「没有作业也排计时器」的写法、`JobCard.tsx` 的字面变了、`runtimes-logic.ts` 的 `canProbe`/`canModels` 变了、`mock/jobs.ts` 的 400 分支变了），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `components/**`、`shell/**`、`live/**`、`RuntimeProbe.tsx`、`RuntimeModels.tsx`、`runtimes-logic.ts`、`runtimes-styles.css`、既有写流程文件、其余门禁基准、`package.json` 与锁文件、`ts/packages/**`）。
- 门禁端交付的 `tests/test_gate_t056_baseline.py` 与本合同的「写法钉死」出现实质冲突（例如它要求按钮文字或卡片措辞换一种写法、要求创建正文多带键、要求按钮不可点、要求结果块经过 JobCard 的失败分支、要求某个导出写成别的形状）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 运行时页的禁用按钮数改完不是 0（与合同与站主任务书说的 1→0 对不上）：停下并报告实际数字，不要顺手改别的断言来凑。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t056-desktop-web-runtime-doctor` 汇总，含返工版本；累计已用 0 次 → 本版留 3 次）
- max_wall_seconds_per_attempt: 10800
- max_wall_seconds_total: 32400（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 32400 秒 ≥ 本版 2 × 10800 = 21600 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 35 分钟；api.ts 与 jobStore.ts 25 分钟；JobCard.tsx 15 分钟；mock/jobs.ts 30 分钟；RuntimeDoctor.tsx 与 CSS 60 分钟；RuntimesView 15 分钟；逐处改旧断言 30 分钟；新包内测试 60 分钟；必要检查（G01、V01、V02、V03、V04、R01；R01 约 45–60 分钟、可分批跑）70 分钟；最终报告 5 分钟；总计约 345 分钟，单轮时限 10800 秒（180 分钟）——总量 32400 秒覆盖本版与返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
