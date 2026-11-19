# TASK: t058-desktop-web-runtimes-empty-state

<!-- 合同 v1：T058「运行时页的空态只替换「已登记」表：就绪检查与 Quizs 一块照常显示」。
     规划报告：.agent/mailbox/tasks/T058-1-plan/report.md；站主任务书：.agent/mailbox/tasks/T058/brief.md。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片只动运行时页这一个页面的空态：空态从「整页空态」改成「「已登记」那一节的空态」。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 6bcc3aa6cc836cc4bc44b2096c8a9e13c9d91478
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
「CLI 运行时」页一个 runtime 都没登记时，页面不再整页只摆一个空态：「已登记」那一节显示空态（`EmptyState`，标题逐字「还没有登记的 runtime」、说明逐字「用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）」），**替换掉原来那张「已登记的 runtime」表**；同一页面里「就绪检查」一节（[运行就绪检查]、「按版本记录核验」文本框与 [核验]）与 Quizs 一块照常渲染，视图根照旧是 `data-page="runtimes"`，页面状态照旧是 `empty`（`data-page-state="empty"`）；有 runtime 时页面与现在完全一样。

## Non-goals
- 不改别的页面的空态；不改空态的文案（标题与说明逐字照旧）。
- 不去掉运行时页的 `isEmpty`（`isEmpty={isRuntimesEmpty}` 与那一行 `const isRuntimesEmpty = …` 保留，页面状态仍是 empty）；不改 `loadRuntimes` 的并行三读与失败判定。
- 不改 `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx` 里「就绪检查」一节与 Quizs 一块的结构（`Section title="就绪检查"`、`div.rt-ready-area`、`RuntimeDoctor`、`QuizsBlock`、`WriteFlow` 照旧）；不改 `RuntimeDoctor.tsx` 与它的样式表。
- 不加 CSS、不改 `runtimes-styles.css`、不改 `components/**`。
- 不改桩（`desktop/web/src/mock/**`）、不改 `desktop/web/src/api.ts`、不改 `ts/**`、不改 `scripts/**`。
- 不碰候选 #78（T056 的 `DOCTOR_CARD_LABELS` 死常量）。
- 不加新的 `<RuntimesView …>` 直接渲染（`desktop/web/tests/page-runtimes.test.tsx` 照旧恰好 4 处），新用例放进 `desktop/web/tests/page-runtimes-empty.test.tsx`。

## Repository facts
以下事实都在本回合的工作目录里逐条读过（行号按基线 26651c5e）。

### 入口页 `desktop/web/src/pages/RuntimesPage.tsx`（共 77 行）
- `:1-5` 文件头注释：写的是「空态「还没有登记的 runtime」……空态（一个 runtime 都没有）也摆 Quizs 一块：EmptyState 之后接 QuizsBlock，直接挂在页面下（视图根之外）」——本片要改写这一段。
- `:6` `import { PageFrame } from '../shell/PageFrame';`；`:7-15` `import { getQuizsLive, getQuizsProviders, getRuntimes, type Envelope, type QuizsLiveData, type QuizsProvidersData, type RuntimesData } from '../api';`（**这一组逐字不变**，t054 :118-126 钉着）。
- `:16` `import { EmptyState } from '../components';`、`:18` `import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';`（本片删掉这两行）。
- `:17` `import { RuntimesView } from './readonly1/runtimes-RuntimesView';`、`:19-20` `AddRuntimeAction` / `ScanRuntimesAction`（照旧）。
- `:24-43` `const loadRuntimes = …`：`Promise.all([getRuntimes(), getQuizsProviders(), getQuizsLive()])`，只有 runtimes 失败整页失败，两个 Quizs 信封整个放进 `data.quizs`（照旧不动）。
- `:45` `const isRuntimesEmpty = (d: { runtimes: RuntimesData }) => d.runtimes.runtimes.length === 0;`（**一行、以 `;` 收尾、只看 runtimes.length、不掺 quizs**——照旧不动）。
- `:56` `isEmpty={isRuntimesEmpty}`（照旧不动，页面状态仍是 empty）。
- `:64-74` children：`{(data, reload) => isRuntimesEmpty(data) ? (<><EmptyState title="还没有登记的 runtime" description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）" /><QuizsBlock quizs={data.quizs} /></>) : (<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />)}`——本片把这一支改成**只有** RuntimesView 那一行。
- `:71` `<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />`（**逐字不变**，t054 :141 钉着，不许加属性）。
- 全文没有 `.css`（t049 S02 要求），不出现「仍禁用」（t054 :834）、不出现 t041/t049 的 BAD_ENTRY_TEXTS（t041 :127-134 / t049 :71-78：「已登记运行时」「已登记表里加上」「；命令写进本机文件」「已登记为」「ERROR: runtime」「改 adapter 要加」「只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符」「命令要写成 JSON 字符串数组」「JSON 字符串数组，第一项写命令的绝对路径」「登记运行时 ${」）、不出现「登记 runtime」（t041 :331 / t049 :278）。

### 视图 `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`（共 120 行）
- `:6` `import { Button, Table, Tag, type TableColumn } from '../../components';`（`EmptyState` 并进这一行）；`:26` `import './runtimes-styles.css';`（仍是最后一行 import）。
- `:4-5` 从 `react` 与 `../../api` **只 import type**（t043 S04 认这个口径）；本片不从 `../../api` 加任何值 import。
- `:94-103` `<Section title="已登记">` 里是 `<Table className="rt-table" aria-label="已登记的 runtime" rowHeight={40} columns={COLUMNS} rows={rows} rowKey={(r) => r.rowId} />`——本片在这一节里按 `runtimes.length === 0` 二选一。
- `:104-108` `<Section title="就绪检查">` 里是 `<div className="rt-ready-area"><RuntimeDoctor /></div>`（照旧）；`:109` `<QuizsBlock quizs={quizs} />`；`:110` `<WriteFlow flow={flow} />`（照旧）。
- 记号（t043 S04 :491-497 认）：`title="已登记"`、`title="就绪检查"`、`aria-label="已登记的 runtime"`、`rt-table`、`RuntimeDoctor`、`runtime.remove`、`useWriteFlow`、`import './runtimes-styles.css'`。
- t055 S05 / t056 S05 认：`版本: '—'`、`rt-ready-area`；不出现 `DisabledAction`、`PlayIcon`；不渲染 `role="status"`、不写内联 style（t009 D11 :2994-3011）。
- 包内三份扫描都按**全文原文**扫（注释也算），本片新增的注释与文案要避开：
  - `desktop/web/tests/page-static.test.ts:23` 把本文件列入 FILES，`:31` 的 FORBIDDEN 含 `fetch`、`eval(`、`innerHTML` 等；
  - `desktop/web/tests/writes-remove.test.tsx:284-296`：本文件不许出现「删除运行时」「已删除」等；
  - `desktop/web/tests/cleanup1-static.test.ts:77-79`：readonly1 下「登记 runtime」「删除 runtime」只许出现在 `components/actionTitle.ts`（现有文案「还没有登记的 runtime」含的是「登记的 runtime」，不在禁词表里；说明句里的「登记运行时」也不在禁词表里）。

### 外壳与组件
- `desktop/web/src/shell/PageFrame.tsx:167-170`：`if (phase === 'empty' && empty) { return <EmptyState … />; } return <>{data != null ? children(data, reload) : null}</>;`——**不传 `empty` 时 empty 阶段照样渲染 children**（所以去掉整页空态那一支之后，视图在 `data-page-state="empty"` 时照常渲染）。
- `desktop/web/src/components/EmptyState.tsx:17-20`：DOM 是 `.tt-empty`（根）、`.tt-empty__title`、`.tt-empty__desc`；`desktop/web/src/components/index.ts:45` 已导出 `EmptyState`。
- `desktop/web/src/pages/readonly1/common-Section.tsx:24-37`：渲染 `section[aria-labelledby]` 指向 `h2`（标题逐字），所以按标题找一节（`sectionNamed(root, '已登记')`）找得到。
- `desktop/web/src/components/TextField.tsx:15-31`：可见 label 用 `htmlFor` 关联 input（label 逐字「按版本记录核验」在 `<label class="tt-field__label">` 里）。
- `desktop/web/src/writes/RuntimeDoctor.tsx:248-249`：只订阅 `useJob('doctor')` 与 `useJob('doctor-record')`，**挂载时不读接口**；`:291` `disabled={running}`（[运行就绪检查]）、`:297` `disabled={recordRunning}`（[核验]）——空闲时两个按钮都**可点**（`disabled === false`）。

### 工具链与锁文件
- `desktop/web` 用 npm（`npm test` = `vitest run` 2.1.8；`npm run typecheck` = `tsc --noEmit`；`npm run build` = `tsc --noEmit && vite build` 5.4.11）；仓库门禁用 `python -m pytest`。
- `dependency_changes: forbidden`：`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock` 一个字都不许动（t049 S03 与 t043 S09 按字节冻结这两个文件）。

### 旧门禁与既有测试（本片**必然**要改的那几处，已逐行读过）
- `tests/test_gate_t049_baseline.py`
  - S02（`test_s02_runtimes_page_empty_branch`）：`:251-255` 的记号表里有 `isRuntimesEmpty(data)`、`<EmptyState`、`title="还没有登记的 runtime"`、`description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）"`、`<QuizsBlock`、`quizs={data.quizs}`；`:262-263` 是「EmptyState 在 QuizsBlock 之前」的次序检查；`:265-268` 是两个 import 的检查；`:230-246`（`isEmpty={isRuntimesEmpty}`、`const loadRuntimes = `、`const isRuntimesEmpty = `、只看 runtimes.length、不掺 quizs、以 `;` 收尾、一行）照旧成立。
  - PROBE_EMPTY（探针源码）：`:439` 的 it 标题、`:443` `expect(pageRoot(), '空态不渲染视图根').toBeNull();`、`:446-448`「`.tt-empty` 的 parentElement 就是 .tt-page」、`:442`/`:455`/`:482`/`:507`/`:531` 的 `toBe('empty')`、`:452` 的 it 标题、`:457-458`「Quizs 区块不在视图根内、直接挂 .tt-page 下」、`:483`/`:508`/`:532` 的 `expect(pageRoot()).toBeNull();`。
  - `:552-566` 的 loading / error 两组 `expect(pageRoot()).toBeNull();` **照旧成立**（loading 与 error 阶段 PageFrame 不渲染 children）。
  - S04（`:293-312`）：`page-runtimes-empty.test.tsx` 必须留着 15 个记号（`mock=empty`、`quizs=broken`、`还没有登记的 runtime`、说明逐字、`Quizs 提供方档案`、`Quizs live 套`、`Quizs 跑不起来`、`读不出`、`setLiveClientForTests`、`刷新`、`mock=loading`、`mock=error`、`readFileSync`、`Themis Tally`、`data-page="runtimes"`）；`page-quizs.test.tsx` 必须留着 `sectionNamed(frame(), 'Quizs')`、`mock=loading`、`mock=empty`，且**不许出现**「Quizs 一块也就看不到」；两个文件都不许 skip/only/todo。
- `tests/test_gate_t054_baseline.py:129-144` 的 `RUNTIMESPAGE_KEEP_MARKS`：`:131` `import { EmptyState } from '../components';`、`:133` `import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';`、`:139` `<EmptyState title="还没有登记的 runtime"`、`:140` `<QuizsBlock quizs={data.quizs} />` 四项本片必然推翻；`:137` `isEmpty={isRuntimesEmpty}` 与 `:141` RuntimesView 那一行照旧保留。
- `tests/test_gate_t043_baseline.py`
  - S03 `:459-460` 的记号表里有 `"还没有登记的 runtime"`（在 RuntimesPage.tsx 里找）——本片必然推翻（文案搬进视图了）。
  - PROBE_PAGE `:1068` 的 `toBe('empty')` 照旧；`:1069` `expect(pageRoot(), '空态不渲染视图，Quizs 一块也就看不到').toBeNull();` 本片必然推翻。
  - S04 `:491-497` 的视图记号、S08 `:656-658`（`page-runtimes.test.tsx` 恰好 4 处 `<RuntimesView …>`、`:670-672` `writes-remove.test.tsx` 恰好 1 处）照旧。
- `tests/test_gate_t041_baseline.py`
  - S05 `:327-328`：`assert EMPTY_DESC in text` 与 `assert "还没有登记的 runtime" in text` 都在 `RUNTIMESPAGE_REL`（`desktop/web/src/pages/RuntimesPage.tsx`）里找——本片要改到视图文件里找（t041 现在**没有**视图文件的路径常量，要新加一个）。
  - `:329-331` 的 BAD_ENTRY_TEXTS 与「登记 runtime」检查照旧对着 RuntimesPage.tsx。
  - PROBE_FORM `:607-616`：「空态：标题「还没有登记的 runtime」保留、说明改成指向页头的 [手动登记…]；空态下入口照样能点开表单」——空态搬进视图后仍在 frame 里，照旧成立，不用改。
- `tests/test_gate_t009_baseline.py`
  - D10（`:2894-2919`）：`:2895-2911`（就绪检查那一节的断言，含 `btn(sec, '核验')` 与 `disabled` 为 false）**一个字不动**；`:2914` 的 it 标题「runtimes 为空数组：空态「还没有登记的 runtime」加说明，不渲染视图」与 `:2919` `expect(root('runtimes')).toBeNull();` 本片必然推翻；`:2916-2917`（状态 empty、页面文本含标题）照旧。
  - TRANS1 `:3029` `expect(root(page) !== null, page + ' ?mock=' + mock + ' 视图根').toBe(state === 'data');`——本片给 **runtimes 的 empty** 开例外，别的页面照旧。
  - `:2895-2911` 与 `:2970-2977` 被 t056 S09 与 t057 S08 按**文字**钉着（不按行号），一个字都不许动；t057 `:909` 禁止 t009 里出现 `btn(r, '核验')`，`:919` 禁止出现 `'运行就绪检查']`。
- 包内 `desktop/web/tests/page-runtimes-empty.test.tsx`（现行 214 行）：(a) `:108-127`（状态 empty、标题与说明逐字、`pageRoot()` 为 null、Quizs 一块在视图根外、两张表各 2 行、无页面级出错块、页头三钮）；(b) `:129-142`（`?mock=empty&quizs=broken`）；(c) `:150-161`（注入替身：runtimes 空数组、providers 失败）；(d) `:167-190`（先空后有，点 [刷新]）；(e)、(f) 不动。文件头 `:1-4` 的注释与 (a) 的标题写着旧行为。
- 包内 `desktop/web/tests/page-quizs.test.tsx:182-191`：那个 it 的标题与两处提示语写着旧行为（「空态不渲染视图但 Quizs 一块照常」、`pageRoot()` 为 null、Quizs 在视图根外）。
- **不推翻**的过渡断言（不进允许修改范围）：`desktop/web/tests/page-app.test.tsx:91`（运行时页禁用按钮数 0）、`desktop/web/tests/readonly2-app.test.tsx:106`、t006 的 EMPTIES / P10、t009 的 TRANS2 / TRANS3。

### 基线检查
- 合同端只读、没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的（核对点与行号如上）。
- 合同检查在基线上的结果由内核在执行之前跑过（基线检查记录）：本片门禁 `tests/test_gate_t058_baseline.py` 在基线上应当失败（断言失败，不是收集失败），既有门禁基准照旧通过；**执行端不必在动手前再跑一遍整套测试**，直接按 Steps 实现，最后跑 Validation commands。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
  - desktop/web/tests/page-runtimes-empty.test.tsx
  - desktop/web/tests/page-quizs.test.tsx
  - tests/test_gate_t009_baseline.py
  - tests/test_gate_t041_baseline.py
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t049_baseline.py
  - tests/test_gate_t054_baseline.py
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t058_*.py
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
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t046_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t048_baseline.py
  - tests/test_gate_t050_baseline.py
  - tests/test_gate_t051_baseline.py
  - tests/test_gate_t052_baseline.py
  - tests/test_gate_t053_baseline.py
  - tests/test_gate_t055_baseline.py
  - tests/test_gate_t056_baseline.py
  - tests/test_gate_t057_baseline.py
  - desktop/web/tests/page-runtimes.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/writes-remove.test.tsx
  - desktop/web/tests/page-static.test.ts
  - desktop/web/tests/cleanup1-static.test.ts
  - desktop/web/tests/jobs-doctor-page.test.tsx
  - desktop/web/tests/jobs-doctor-record-page.test.tsx
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/live/**
  - desktop/web/src/api.ts
  - desktop/web/src/mock/**
  - desktop/web/src/jobs/**
  - desktop/web/src/writes/**
  - desktop/web/src/pages/readonly1/runtimes-QuizsBlock.tsx
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
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - ts/package.json
  - ts/bun.lock
  - ts/packages/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 页面（`desktop/web/src/pages/RuntimesPage.tsx`）
- children 一律是 `{(data, reload) => (<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />)}`：**RuntimesView 那一行逐字不变**（t054 :141），`{(data, reload) =>` 这个前缀照旧（t049 S02、t043 S03 的正则认它）。
- 删掉整页空态那一支（三元表达式），以及随之没用的两个 import：`import { EmptyState } from '../components';` 与 `import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';`。文件里**不许再出现** `<EmptyState` 与 `<QuizsBlock`。
- **保留** `isEmpty={isRuntimesEmpty}`（:56）与那一行 `const isRuntimesEmpty = (d: { runtimes: RuntimesData }) => d.runtimes.runtimes.length === 0;`（:45）：一行、以 `;` 收尾、只看 runtimes.length、不掺 quizs。页面状态因此仍是 `empty`（`data-page-state="empty"`）。
- `'../api'` 那一组 import（:7-15）**逐字不变**（t054 :118-126）；`loadRuntimes` 的并行三读与失败判定、`title="CLI 运行时"`、页头 description、页头两钮（`ScanRuntimesAction` / `AddRuntimeAction reload={reload}`）全照旧。
- 文件头注释（:1-5）改写成新行为：视图在空态下也渲染、空态由视图在「已登记」那一节里显示、页面状态仍是 empty、Quizs 一块在视图根里。注释里**不许出现**「仍禁用」、t041/t049 BAD_ENTRY_TEXTS 的任何一项、「登记 runtime」、「已登记运行时」、「已登记为」。
- 代码（去掉注释后）里不出现 `.css`。

### 视图（`desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`）
- `<Section title="已登记">` 里按 `runtimes.length === 0` 二选一：
  - 空：`runtimes.length === 0` → 渲染 `<EmptyState title="还没有登记的 runtime" description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）" />`（**两段文案逐字照旧**，一个字都不许改）；**该节里没有** `table[aria-label="已登记的 runtime"]`。
  - 非空：照旧渲染那张 `<Table className="rt-table" aria-label="已登记的 runtime" rowHeight={40} columns={COLUMNS} rows={rows} rowKey={(r) => r.rowId} />`（DOM 与现在一模一样）。
- `EmptyState` 从 `'../../components'` 引，**并进现有的那一行** `import { Button, Table, Tag, type TableColumn } from '../../components';`（不新开一行 import 组也可以，但 `import './runtimes-styles.css';` 必须仍是最后一行 import）。
- 「就绪检查」一节（`<Section title="就绪检查">` + `div.rt-ready-area` + `RuntimeDoctor`）、`QuizsBlock`、`WriteFlow`、列定义、`rows` 的构造、`runtime.remove` 写流程：全部照旧，一个字不动。
- 文件头注释补一句空态的说明（视图在空态下也渲染、「已登记」那一节在没登记时显示空态），**避开**包内三份扫描的禁词（`fetch`、`删除运行时`、`已删除`、`登记 runtime`、`删除 runtime`）与 t041/t049 的 BAD_ENTRY_TEXTS。
- 不新增 CSS；`runtimes-styles.css` 一个字不改。

### 页面状态与其它页面
- 一个 runtime 都没有时：`data-page-state="empty"`（照旧）、视图根 `data-page="runtimes"` **在**、「已登记」一节里是空态、「就绪检查」一节在（[运行就绪检查] 与 [核验] 都 `disabled === false`、「按版本记录核验」文本框在）、Quizs 一块在视图根里（两张表各 2 行；读失败只写在区块里，没有页面级出错块）。
- loading 与 error 阶段照旧：视图根不渲染（`PageFrame` 那时没有 children），页面级出错块照旧。
- 有 runtime 时：视图根里三节次序照旧（「已登记」「就绪检查」在前、Quizs 在其后）、页头三钮照旧、禁用按钮数照旧是 0。
- 别的页面（总览、角色、历史…）一个字不动。

### 边界输入
- `runtimes` 是空数组：走空态支（如上）。
- `runtimes` 有一条及以上：走表格支（如上）。
- Quizs 读失败（`?quizs=broken` 或注入的 providers 失败）：失败只写在 Quizs 区块里（「Quizs 跑不起来」、live 逐套「读不出」），**页面级不出错块**，页面状态不受影响；空态支下这块同样在视图根里。
- 真实模式（注入 `setLiveClientForTests` 的替身 client）与桩模式（`?mock=empty`）行为一致。
- `RuntimeDoctor` 挂载不读接口：空态下不会多发请求；空闲时 [运行就绪检查] 与 [核验] 都可点。

### 错误与重试
- 点 [刷新]（页头）后重读：先空后有时，状态从 `empty` 变 `data`，视图根里「已登记」一节从空态变成一张有一行的表、空态消失，Quizs 一块仍在视图根里。

### 并发、取消与状态变化
- 不适用：本片不引入并发、取消或新的状态机；`jobStore` 的作业槽与 `RuntimeDoctor` 的行为一个字不动。

### 兼容性（本片必然推翻的旧断言，逐处写明只改哪一处）
以下五个文件的这几处要改，**只改下面写明的那一处**，其余一个字不动：
- `tests/test_gate_t049_baseline.py`
  - S02（`:230-268`）：`:251-255` 记号表里去掉 `isRuntimesEmpty(data)`、`<EmptyState`、`title="还没有登记的 runtime"`、`description="…"`、`<QuizsBlock`、`quizs={data.quizs}` 这六项（`quizs={data.quizs}` 与 `<RuntimesView` 那一项：`<RuntimesView` 保留，`quizs={data.quizs}` 也可以留在那一项里）；改成**要求** RuntimesPage.tsx 里有 `<RuntimesView`、**没有** `<EmptyState`、**没有** `<QuizsBlock`。`:262-263` 的「EmptyState 在 QuizsBlock 之前」次序检查删掉；`:265-268` 两条 import 检查删掉。`:230-246`（`isEmpty={isRuntimesEmpty}`、两个模块级 const、`isRuntimesEmpty` 一行且只看长度不掺 quizs、以 `;` 收尾、children 前缀 `{(data, reload) =>`）**照旧成立，不动**；`:269-283`（页头两钮、禁字表、「登记 runtime」、不引 `.css`）照旧。docstring 照新行为改写一句。
  - PROBE_EMPTY：`:439` 的 it 标题与 `:443` 改成**视图根在**（`expect(pageRoot()).not.toBeNull()`）；`:446-448` 改成「`.tt-empty` 在视图根的「已登记」一节里」（用 `sectionNamed(pageRoot(), '已登记')` 找那一节，断言 `.tt-empty` 在里面）；`:452` 的 it 标题与 `:457-458` 改成「Quizs 一块在视图根里」（`sec.closest('[data-page="runtimes"]')` 是视图根）；`:442`/`:455`/`:482`/`:507`/`:531` 的 `toBe('empty')` **照旧**；`:483`、`:508`、`:532` 的 `expect(pageRoot()).toBeNull();` 改成**视图根在**；`:552-566`（loading / error）的 `pageRoot()` 为 null **照旧不动**；`:544`、`:583`（重读之后、有 runtime 时 Quizs 在视图根内）照旧。文件头 `:32-36` 与 `ASSUMPTIONS` 第一条照新行为改写一句。
- `tests/test_gate_t054_baseline.py`：S06 的 `RUNTIMESPAGE_KEEP_MARKS`（`:129-144`）去掉四项——`:131`（EmptyState import）、`:133`（QuizsBlock import）、`:139`（`<EmptyState title="还没有登记的 runtime"`）、`:140`（`<QuizsBlock quizs={data.quizs} />`）；`:137`（`isEmpty={isRuntimesEmpty}`）、`:141`（RuntimesView 那一行）、`title="CLI 运行时"`、description 与其余记号**照旧**。
- `tests/test_gate_t043_baseline.py`
  - S03 `:459-460`：记号表里去掉 `"还没有登记的 runtime"`（文案搬进视图了）；`title="CLI 运行时"`、`ScanRuntimesAction`、`AddRuntimeAction` 与 children 正则照旧。
  - PROBE_PAGE `:1069`：`expect(pageRoot(), '空态不渲染视图，Quizs 一块也就看不到').toBeNull();` 改成**视图根在**、且**Quizs 一块在视图根里**；`:1068` 的 `toBe('empty')` 照旧。`:1058` 的 it 标题照新行为改写一句。
- `tests/test_gate_t041_baseline.py`
  - S05 `:327-328`：空态的说明与标题**改到视图文件里找**（本文件现在没有这个路径常量，新加一个 `RUNTIMESVIEW_REL = f"{SRC_REL}/pages/readonly1/runtimes-RuntimesView.tsx"`），RuntimesPage.tsx 里的这两条断言删掉；`:323-326`（AddRuntimeAction / ScanRuntimesAction）与 `:329-331`（BAD_ENTRY_TEXTS、「登记 runtime」，仍对着 RuntimesPage.tsx）**照旧**；docstring 照新行为改写一句。
  - PROBE_FORM `:607-616` **照旧**，一个字不改。
- `tests/test_gate_t009_baseline.py`
  - D10 `:2914` 的 it 标题照新行为改写一句（「不渲染视图」那半句改掉）；`:2916-2917` 照旧；`:2919` `expect(root('runtimes')).toBeNull();` 改成 `expect(root('runtimes')).not.toBeNull();`。
  - TRANS1 `:3029`：`expect(root(page) !== null, …).toBe(state === 'data');` 改成**只给 runtimes 的 empty 开例外**（例如期望值写成 `state === 'data' || (page === 'runtimes' && mock === 'empty')`），overview 与 roles 的五个状态照旧。
  - `:2895-2911` 与 `:2970-2977` **一个字都不动**（t056 S09 与 t057 S08 按文字钉着）；改 t009 时**不许写出** `btn(r, '核验')` 与 `'运行就绪检查']`；**不许**在 `:2909` 之前新增一处 `btn(sec, '核验')`（t057 S08 取的是第一处）。

**不推翻、也不许改**（不进允许修改范围）：包内 `desktop/web/tests/page-app.test.tsx:91`、`desktop/web/tests/readonly2-app.test.tsx:106`、`desktop/web/tests/page-runtimes.test.tsx`（含 `:116-126`）、t009 `:2895-2911` 与 `:2970-2977`、t006 的 EMPTIES 与 P10、t009 的 TRANS2 与 TRANS3、t041 PROBE_FORM、t049 的 loading/error 两组、t043 S04/S07/S08、t055 S05、t056 S05/S09、t057 S08。

### 写法钉死（与本片门禁基准文件对表）
本片门禁由门禁端交付（`tests/test_gate_t058_baseline.py`），它不在当前基线里，由门禁那一版合同产出并集成；基线上它应当失败（断言失败，不是收集失败）。执行端第 1 步要读门禁文件（若已在本基线上）与这一节对一遍；**有出入以本合同的「写法钉死」为准，并把出入写进执行报告**；若出入是逐字文案层面的实质冲突，按 Stop conditions 停下报告。
- `desktop/web/src/pages/RuntimesPage.tsx`：有 `<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />`（逐字）、有 `isEmpty={isRuntimesEmpty}`、有 `const loadRuntimes = ` 与 `const isRuntimesEmpty = `、有 `{(data, reload) =>`、有 `title="CLI 运行时"`、有 `ScanRuntimesAction` 与 `<AddRuntimeAction reload={reload}`；**没有** `<EmptyState`、**没有** `<QuizsBlock`、**没有** `import { EmptyState } from '../components';`、**没有** `import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';`。
- `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`：有 `title="已登记"`、`title="就绪检查"`、`aria-label="已登记的 runtime"`、`rt-table`、`RuntimeDoctor`、`runtime.remove`、`useWriteFlow`、`import './runtimes-styles.css'`、`版本: '—'`、`rt-ready-area`；有 `EmptyState`（从 `'../../components'` 引）；有 `title="还没有登记的 runtime"` 与 `description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）"`；**没有** `DisabledAction`、`PlayIcon`、`role="status"`、内联 `style=`、`.css` 之外的新样式表。
- `desktop/web/tests/page-runtimes-empty.test.tsx`：留着 t049 S04 的 15 个记号；没有 skip/only/todo；桩模式与真实模式各测一遍空态。
- `desktop/web/tests/page-quizs.test.tsx`：留着 `sectionNamed(frame(), 'Quizs')`、`mock=loading`、`mock=empty`；**没有**「Quizs 一块也就看不到」；t043 S08 的记号表照旧全在。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件** `tests/test_gate_t058_baseline.py`（只读；若本基线上还没有它就跳过），把它的断言与「写法钉死」一节对一遍，有出入按上面的口径处理并写进执行报告。
2. **`desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`**：把 `EmptyState` 并进 `:6` 那一行 `import { Button, Table, Tag, type TableColumn } from '../../components';`（`import './runtimes-styles.css';` 仍是最后一行 import）；把 `:94-103` 的 `<Section title="已登记">` 改成按 `runtimes.length === 0` 二选一（空 → `<EmptyState title="还没有登记的 runtime" description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）" />`；非空 → 照旧那张 `<Table …>`）；文件头注释补一句空态说明（避开禁词）。「就绪检查」一节、`QuizsBlock`、`WriteFlow`、列与 rows 构造一个字不动。
3. **`desktop/web/src/pages/RuntimesPage.tsx`**：删掉 `import { EmptyState } from '../components';`（:16）与 `import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';`（:18）；把 `:64-74` 的 children 改成**只有** `<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />` 那一行（逐字不变，`{(data, reload) =>` 前缀照旧）；`isEmpty={isRuntimesEmpty}`、`const isRuntimesEmpty = …`、`'../api'` 那一组 import、`loadRuntimes`、页头两钮与 `title="CLI 运行时"` 照旧；改写文件头注释（:1-5）成新行为，避开「仍禁用」、BAD_ENTRY_TEXTS 与「登记 runtime」。
4. **`desktop/web/tests/page-runtimes-empty.test.tsx`**：(a) 把「视图根为 null」改成**视图根在**，并加断言——空态在「已登记」那一节里（`sectionNamed(pageRoot(), '已登记')` 里有 `.tt-empty`、标题与说明逐字）、那一节里**没有** `table[aria-label="已登记的 runtime"]`、「就绪检查」一节在视图根里（[运行就绪检查] 与 [核验] 都在、`disabled === false`、「按版本记录核验」文本框在）、Quizs 一块在视图根里（`closest('[data-page="runtimes"]')` 是视图根）、两张 Quizs 表各 2 行、页头三钮照旧；(b) 与 (c) 同样把 `pageRoot()` 为 null 改成视图根在，并补「就绪检查」一节在、两钮可点、Quizs 在视图根里的断言；(d) 改成刷新前视图根就在（空态在「已登记」一节里），刷新后状态变 `data`、「已登记」一节里出现一张有一行的表、空态消失、Quizs 仍在视图根里；(e)、(f) 不动；文件头注释与 (a) 的标题照新行为改写。**不许 skip/only/todo**；t049 S04 的 15 个记号一个都不能少（`mock=empty`、`quizs=broken`、`还没有登记的 runtime`、说明逐字、`Quizs 提供方档案`、`Quizs live 套`、`Quizs 跑不起来`、`读不出`、`setLiveClientForTests`、`刷新`、`mock=loading`、`mock=error`、`readFileSync`、`Themis Tally`、`data-page="runtimes"`）。新断言一律**限定在「已登记」那一节里**找空态，不在整个 frame 里找第一个 `.tt-empty`（Quizs 区块自己也有空态文案）。
5. **`desktop/web/tests/page-quizs.test.tsx:182-191`**：it 标题与两处提示语照新行为改写；`:189` 改成视图根在；`:190` 留住 `sectionNamed(frame(), 'Quizs')` 并加「Quizs 一块在视图根里」的断言；`mock=loading` 那一半与 `mock=empty`、`mock=loading` 两个记号照旧；**不许出现**「Quizs 一块也就看不到」；t043 S08 对这份文件的记号表照旧全在。
6. **逐处改旧门禁**（照「兼容性」一节逐条只改那一处）：`tests/test_gate_t049_baseline.py`（S02 的 `:251-268` 与 PROBE_EMPTY 的 `:439`/`:443`/`:446-448`/`:452`/`:457-458`/`:483`/`:508`/`:532`，以及文件头与 ASSUMPTIONS 的一句）、`tests/test_gate_t054_baseline.py`（`:131`/`:133`/`:139`/`:140` 四项）、`tests/test_gate_t043_baseline.py`（S03 的 `:459-460`、PROBE_PAGE 的 `:1069`、`:1058` 的标题）、`tests/test_gate_t041_baseline.py`（S05 的 `:327-328` 与新增的视图路径常量）、`tests/test_gate_t009_baseline.py`（`:2914` 的标题、`:2919`、TRANS1 的 `:3029`）。改完把仍钉着旧口径的地方再搜一遍（关键字：`toBeNull()`（限上面点名的几处）、`不渲染视图`、`空态不渲染视图`、`直接挂在 .tt-page 下`、`不在视图根内`、`EmptyState 应从`、`QuizsBlock 应从`），确认没有漏网的旧断言；`:2895-2911` 与 `:2970-2977` 一个字都不许动，也不许写出 `btn(r, '核验')` 与 `'运行就绪检查']`。
7. 跑 Validation commands 里的检查，顺序 **V03 → V04 → V01 → V02 → G01 → R01**（本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
8. 写执行报告；遇到合同未定义的行为（例如门禁端交付的 `tests/test_gate_t058_baseline.py` 与「写法钉死」有实质冲突），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- V03（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- V01（必要）：`npm test -- tests/page-runtimes-empty.test.tsx tests/page-quizs.test.tsx` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t058_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py tests/test_gate_t057_baseline.py -q` · cwd：仓库根 · 超时：3360s · 期望退出码：0 · 输出须匹配：`\d+ passed`

上面每条检查的「输出须匹配」为什么在门禁机上成立（逐条说明；门禁检查与回归检查都用 pytest 的 `-q`，成功时最后一行是「N passed」，与已验收的 T055/T056/T057 合同里同一种调用配同一个匹配，已在门禁机上成立过）：
- 前端那两条 vitest 检查是 `npm test`（= `vitest run`，desktop/web 已装 vitest 2.1.8），vitest 2.x 成功时打印「Tests  N passed」；同一个匹配在 T055、T056、T057 合同的同一种调用上验收通过过。只跑指定文件的那一条另加 `不得出现 No test files found`（vitest 找不到文件时会这么写，防止「0 个用例也是绿色」）。
- 类型检查那条是 `npm run typecheck`（= `tsc --noEmit`），成功时无输出、退出码 0；这条不写输出须匹配（没有输出可匹配），只看退出码。
- 构建那条是 `npm run build`（= `tsc --noEmit && vite build`），vite 5.4.11 成功时打印「✓ built in …」；同一个匹配在 T055、T056、T057 合同里验收通过过。构建产物在 `desktop/web/dist/`，已被 `.gitignore` 忽略，不会算成候选之外的新文件。

## Definition of done
- D01：一个 runtime 都没有时，「已登记」那一节显示空态：`.tt-empty` 在该节里，标题逐字「还没有登记的 runtime」、说明逐字「用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）」，该节里没有 `table[aria-label="已登记的 runtime"]`；目的：新装好的机器不用先登记一个 runtime 就看得到这一节的状态；证据：V01、V02、G01、R01。
- D02：同一情况下「就绪检查」一节照常渲染：它在视图根里，[运行就绪检查] 与 [核验] 都在且 `disabled === false`，「按版本记录核验」文本框在；目的：站主想先跑一遍就绪检查、看缺什么；证据：V01、V02、G01、R01。
- D03：同一情况下 Quizs 一块在视图根里（两张表各 2 行），读失败只写在区块里（「Quizs 跑不起来」、live 逐套「读不出」），没有页面级出错块；目的：Quizs 一块本来就是这个页面的一部分，不该被空态吃掉；证据：V01、V02、G01、R01。
- D04：页面状态仍是 `empty`（`data-page-state="empty"`）：`isEmpty={isRuntimesEmpty}` 与那一行 `const isRuntimesEmpty = …;` 保留，`PageFrame` 在 empty 阶段渲染 children；目的：状态语义不变，空态只是这一节的内容；证据：V01、G01、R01。
- D05：有 runtime 时页面与现在完全一样：视图根里三节次序、表与列、页头三钮、禁用按钮数 0 都照旧；目的：这一片只改空态那一支；证据：V02、R01。
- D06：`RuntimesPage.tsx` 不再有整页空态那一支与 `EmptyState`/`QuizsBlock` 两个 import，children 只渲染 RuntimesView 那一行（逐字不变），`'../api'` 那一组 import、`loadRuntimes` 与 `const isRuntimesEmpty = …;` 逐字不变；目的：入口页回到「只管读数据与页头」；证据：G01、R01、review。
- D07：五份旧门禁基准逐处改到位（t049 的 S02 与 PROBE_EMPTY、t054 的四项记号、t043 的 S03 与 PROBE_PAGE、t041 的 S05 与新增路径常量、t009 的 D10 与 TRANS1），**每处只改合同写明的那一处**，其余一个字不动；**不推翻**任何前端过渡用例（`page-app.test.tsx:91`、`readonly2-app.test.tsx:106`）与 t009 `:2895-2911`、`:2970-2977`、t056 S09、t057 S08；目的：这些旧断言钉的是「空态整页空着」，本片必然推翻，改法不许顺手改别的断言；证据：G01、R01、scope、review。
- D08：`desktop/web/tests/page-runtimes-empty.test.tsx` 覆盖 D01–D04（桩模式 `?mock=empty` 与真实模式注入替身各测一遍），t049 S04 的 15 个记号一个不少，没有 skip/only/todo；`page-quizs.test.tsx` 那个 it 改成新行为且仍留着 `sectionNamed(frame(), 'Quizs')`；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、V02、review。
- D09：所有修改都在允许集合内（可改 9 个文件、无新增、无删除），没有碰 forbidden_paths（`tests/test_gate_t058_*.py`、其余门禁基准、`page-runtimes.test.tsx`、`page-app.test.tsx`、`readonly2-app.test.tsx`、`writes-remove.test.tsx`、`page-static.test.ts`、`cleanup1-static.test.ts`、`components/**`、`shell/**`、`live/**`、`api.ts`、`mock/**`、`jobs/**`、`writes/**`、`runtimes-styles.css`、其余顶层页面、`package.json` 与锁文件、`ts/packages/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope。
- D10：`npm test`、`npm run typecheck`、`npm run build` 全过，既有门禁基准（t001–t057）照旧通过；目的：不能为了挪一个空态把别处弄坏；证据：V01、V02、V03、V04、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `PageFrame` 在 empty 阶段不再渲染 children、`EmptyState` 的 DOM 类名变了、`Section` 不再按 `aria-labelledby` 指 h2、`RuntimeDoctor` 的两个按钮在空闲时不再是 `disabled === false`、包内三份扫描的禁词表变了），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `components/**`、`shell/**`、`live/**`、`api.ts`、`mock/**`、`jobs/**`、`writes/**`、`runtimes-styles.css`、其余门禁基准、`page-runtimes.test.tsx`、`package.json` 与锁文件、`ts/packages/**`）。
- 门禁端交付的 `tests/test_gate_t058_baseline.py` 与「写法钉死」出现实质冲突（例如它要求空态挂在 `.tt-page` 下而不是「已登记」一节里、要求「就绪检查」一节在空态下仍然不渲染、要求 Quizs 一块仍在视图根之外、要求空态文案改字）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 改完之后运行时页的禁用按钮数不是 0，或空态下 [运行就绪检查] / [核验] 不是可点：停下并报告实际数字，不要顺手改别的断言来凑。
- 改完之后有 runtime 的那一支 DOM 与现在不一致（`page-runtimes.test.tsx` 或既有门禁红了）：停下并报告。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t058-desktop-web-runtimes-empty-state` 汇总，含返工版本；累计已用 0 次 → 本版留 3 次）
- max_wall_seconds_per_attempt: 10800
- max_wall_seconds_total: 32400（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 32400 秒 ≥ 本版 2 × 10800 = 21600 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读源码与门禁文件、核对事实 30 分钟；视图与入口页改动 30 分钟；两个包内测试 35 分钟；五份门禁逐处改 30 分钟；必要检查（V03、V04、V01、V02、G01、R01；R01 约 30–40 分钟、可分批跑）80 分钟；最终报告 10 分钟；总计约 215 分钟，单轮时限 10800 秒（180 分钟）——总量 32400 秒覆盖本版与返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
