# TASK: t051-desktop-web-role-bind

<!-- 合同 v2：在 v1 上只加站主指定的三处，其余一字不动。
     1) Scope：allowed_modified_files 加 tests/test_gate_t047_baseline.py 与 tests/test_gate_t048_baseline.py，
        并从 forbidden_paths 拿掉这两份（tests/test_gate_t051_*.py 照旧禁改）；
     2) Steps 第 11 步与 D14 写死：这两份文件各自的 BASELINE_DIGESTS 字典里整行删除，共三行，
        别的行（docstring、注释、其余冻结项与断言）一个字不动，不加注释；
     3) 证据：R01 全过；这两份文件相对 base_sha 的差异恰好是删掉这三行（一审、终审专看这份差异）。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片要改某个源文件的导出形态（api.ts 的 WriteAction 与新导出、useLivePreview 的 LivePreview、snapshots 的新导出、
     roles-logic 的新导出与 RoleInfo、RoleCard 的 props），所以下面「兼容性」一节逐条列出生效的旧断言与本片必然推翻的断言，
     并在 Scope 的 allowed_modified_files 里逐字写明只改哪一处。 -->

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 2990c293fca3e7454408059f90a769ec1e6d4be0
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
「角色与模型」页四张角色卡底部的 [更改…] 从禁用变成可点：点开「改绑定：<角色中文名>」表单（先选该角色允许的模式，无头时再选已登记的 profile），底部实时预览命令与这个角色的绑定前后；[确认…] 走既有写流程（预览 → 确认 → 执行 → 重读 → 终态），执行时打 `POST /api/v1/roles/<role>`，写完整页重读。没有已登记的 profile 时无头不可选，并给出原因句；其余写入口与只读部分一个字不变。

## Non-goals
- 不做 [保存当前为方案…]（preset.save）；不做运行时页的扫描、探测、列模型、就绪检查；不做凭据录入、资格认证、续期（M6）。
- 第一版不做 host 与 cadence_seconds 的编辑框：只预填、照原样传回（站主的倾向）。
- 不改本机服务（`ts/packages/ui/**`）与内核（`scripts/**`）；不改共享组件（`components/**`、`shell/**`）；不改 `desktop/web/src/writes/WriteConfirmDialog.tsx`、`hubChangeLines.ts`、`writeOutcome.ts`、`HubBindForm.tsx`、`hub-bind-form.css`。
- 不改 `desktop/web/src/pages/readonly1/roles-styles.css`（T045 的字节冻结）、`desktop/web/src/mock/profiles.json`（字节冻结）、`desktop/web/src/writes/hubChangeLines.ts`（字节冻结）、`desktop/web/package.json` 与 `package-lock.json`。
- 不加新的桩情景（`WriteScenario` 的值一个都不许加；T044 S07 把它钉死在 27 个）。
- 不改七端岗位那一组（T044/T045 的地盘）、profile 表、方案表与运行时页。
- 不改 `tests/test_gate_t047_baseline.py` 与 `tests/test_gate_t048_baseline.py` 里除「删除三行」以外的任何内容（见 Steps 第 11 步）。

## Repository facts
以下事实都在本回合的工作目录（基线 `65c2e3bf`）里逐条读过；行号按该基线。

### 前端现状
- `desktop/web/src/pages/readonly1/roles-RoleCard.tsx`：`:78-80` 卡底是 `<DisabledAction label="更改…" variant="secondary" size="sm" />`（没有 reason，悬停出缺省的「第二阶段接入」）；props 只有 `role: RoleInfo` 与 `activePreset: string`；卡片其余部分（标签、dl、说明）只读，本片一个字不改。
- `desktop/web/src/pages/readonly1/roles-logic.ts`：`ROLE_NAMES`（`:6-11`，四个角色中文名）、`roleName`（`:13-15`）、`MODE_NAMES`（`:17-22`）、`modeName`（`:24-26`，headless→无头、interactive_host→交互式宿主、manual→手工、disabled→关闭）、`RawRole`（`:36-49`）、`RoleInfo`（`:51-68`）、`normalizeRole`（`:71-93`，`mode` 取 `binding.mode`，`host` 取 `binding.host`，`bindingProfile` 取 `binding.profile`）、`resolvedProfile`（`:96-98`，`role.profile ?? role.bindingProfile`）。既有导出 `hubPostName`/`allowedProfiles`/`normalizeHubPost`（T045 S01 钉住）与 `allowedProfiles`（按输入顺序留 adapter 在允许名单里的 profile 的 id）。
- `desktop/web/src/pages/readonly1/roles-RolesView.tsx`：`:35-39` 每张卡 `<RoleCard key={r.role} role={r} activePreset={active} />`；视图手上已有 `data.profiles.profiles` 与可选的 `reload`（props 里 `reload?: () => Promise<void>`）。
- `desktop/web/src/pages/RolesPage.tsx`：`:71` `<RolesView data={data} onDiff={diffPresets} reload={reload} live={live} />`（reload 由 PageFrame 给）；`:26-37` 的 `loadRoles` 并行读 `getRoles/getProfiles/getPresets/getHubRoles`——**profiles 与 roles 来自同一次读，reload 一起刷新**。
- `desktop/web/src/api.ts`：
  - `:63-76` `WriteAction` 既有 12 个成员（`preset.use`、`plugin.enable`、`plugin.disable`、`preset.remove`、`profile.remove`、`runtime.remove`、`config.rollback`、`profile.add`、`profile.edit`、`hub.set`、`hub.unset`、`runtime.add`）；`:78` `WriteArgs = Record<string, string | string[]>`。
  - `:86-91` `BindingChange { role; from; to }`；`:123-133` `PreviewData`（含 `binding_changes: BindingChange[]`）。
  - `:304-318` `writeArgs(args)`：数组按顺序原样传；空串与空数组不传这个键；**`key === 'number'` 的值用 `asNumber` 转成 JSON 数字**（转不成原样传）；其余键值原样传。预览与执行共用这一份规则。
  - `:378-390` `toPreviewData` 把服务的 `binding_changes`（`{role, before, after}`）映射成 `{role, from, to}`，`displayValue`（`:334-345`）取 profile → provider/model → mode → 占位符。
  - `:701-708` `preview(action, args)`；`:845-860` `setHubRole(args, confirmation)`（真实模式 `POST /api/v1/hub/roles/<post>`，正文 `{...writeArgs(w), confirmation}`；桩模式 `mockSetHubRole`）。
- `desktop/web/src/mock/writes.ts`：`:66-101` `baseArgv`（逐条写 action 的 argv；**现在没有 `role.set` 分支**，它会落进 `profile.edit` 的兜底）；`:104-106` `writeArgv`；`:121` `NEW_ACTIONS`（九个 action）；`:210-312` `previewData`（`:272-291` 是 `hub.set`/`hub.unset` 的分支，`binding_changes` 恒空、`hub_changes` 按夹具算）；`:314+` `mockPreview`（通用情景 `preview-busy` 等照旧生效）；`:545-556` `mockSetHubRole`/`mockUnsetHubRole`。
- `desktop/web/src/mock/roles.json`：四行（planning_review 的 binding 是 `{mode:'interactive_host', host:'claude-code'}`；contract 是 `{mode:'manual'}`；execution 是 `{mode:'headless', profile:'step-high'}`；scheduler_agent 是 `{mode:'disabled'}`）。
- `desktop/web/src/mock/profiles.json`：两条（`step-high`、`step-low`，adapter 都是 `pi`）。
- `desktop/web/src/writes/useLivePreview.ts`：`:16-32` `LivePreview` 现在有 `key`、`ok`、`command`、`warnings`、`error`、`hubChanges`、`runningTurns` 七个字段；`:34-48` `fromReply`；`:66` 失败分支的字面量。开头两行注释与 `const DEBOUNCE_MS = 300;`（`:7`）由 T040/T045 钉住。
- `desktop/web/src/writes/useWriteFlow.ts`：`titleOf`（`:93-104`）、`successTextOf`（`:107-120`）、`changeSummaryOf`（`:123-151`）、`readSnapshot`（`:158-230`，`hub.set`/`hub.unset` 读 `getHubRoles` + `hubSnapshot`；**没有 `role.set` 分支**，它会落进 `getPlugins` 的兜底）、`dangerOf`（`:80-89`，`role.set` 不在危险列表里）、`confirm` 的分派链（`:400-430`，最后兜底是 `setPluginEnabled`）。
- `desktop/web/src/writes/snapshots.ts`：`presetSnapshot`（roles[].{role,explicit,binding}，按 role 排序）、`hubSnapshot`、`sameSnapshot`（JSON 字符串比较）。
- `desktop/web/src/writes/WriteConfirmDialog.tsx`：`ConfirmContent.changes: BindingChange[]`；`:81-95` 的 `Changes` 已经会逐条渲染 `role`、`from`、`→`、`to`；`changes` 与 `hubChanges` 都空时显示 `summary ?? '预览没有列出变化'`。**本片不改这个文件**——`role.set` 的预览 binding_changes 直接被它渲染。
- `desktop/web/src/writes/HubBindForm.tsx`（T045 的表单，本片只照抄结构）：`Dialog` + 两个 `Select` + 底部 `useLivePreview` + `[确认…]` 门控 + `<WriteFlow flow={flow} />`；入口组件 `HubBindAction`/`HubUnsetAction`；两个原因句常量在本文件里。
- `desktop/web/src/components/Select.tsx`：原生 `select`，props 有 `label`、`options: {value,label}[]`、**`help`**（`useFieldA11y` 把它接到 `aria-describedby`）、`error`；**不支持单项禁用**（没有 disabled 的选项）。
- `desktop/web/src/components/Dialog.tsx`：`:37` `if (!open) return null;`——对话框关着时不渲染任何按钮。
- `desktop/web/src/shell/DisabledAction.tsx`：`<DisabledAction label reason variant size icon />`；`reason` 缺省「第二阶段接入」；用 Tooltip 包一个 disabled 的 Button；**不接受 `aria-label`**。
- `desktop/web/src/shell/DisabledAction.css` 与 `desktop/web/src/writes/hub-bind-form.css`：`.hb-*` 类的样式表（`hub-bind-form.css` 里只有 `hb-` 前缀的类、只用 `--tt-*` 令牌，T045 S04 钉住）。本片**复用**它的类，不改这个文件、不新建 CSS 文件。

### 服务与内核（只读引用，本片不改）
- `ts/packages/ui/src/writeroutes.ts`：`:79` `"role.set": { required: ["role", "target"], optional: ["host", "cadence_seconds"] }`；`:228-236` 取值校验——`role` 必须是四个角色码之一；`target` 是三个模式词之一或合法的 profile id（`TASK_ID_RE`）；`host` 只能是 `claude-code`/`codex`；**`cadence_seconds` 必须是 60–86400 的整数**；`:275-280` `buildWriteArgv` 拼 `config role set <role> <target> [--host=…] [--cadence-seconds=…]`；`:538-542` 路由 `POST /api/v1/roles/<role>`（路径参数压进正文）。
- `scripts/kit_roles.py`：`:29-36` `ROLES` 与 `ROLE_MODES`（planning_review→interactive_host/headless；contract→manual/headless；execution→headless；scheduler_agent→disabled/headless）；`:1216-1246` `_role_set`——target 是模式词就切到那个模式（`--host` 只许配 interactive_host；配模式词时给 `--cadence-seconds` 直接报错），否则按无头处理、target 当 profile id（`--host` 报错；`--cadence-seconds` 只许 scheduler_agent）；**整条替换**绑定；`:1198-1213` 写入之后的提示（不拦）。
- 读路径：`GET /api/v1/roles` 不登记白名单，`binding` 原样带出；`roles-logic.ts` 现在的 `RawRole`/`RoleInfo` 不收 `cadence_seconds`（本片加）。

### 门禁现状（在本基线上逐条核对过行号与原文）
- `tests/test_gate_t009_baseline.py`：`:2365-2379`「[更改…] 是禁用的 secondary sm，悬停出「第二阶段接入」」（`:2370` 断言 `b.disabled` 为真；`:2374-2378` 悬停出「第二阶段接入」）；`:2969` 角色页**可用**按钮的白名单（`outsideWhitelist`）；`:2971` `const later = ['更改…', '保存当前为方案…'];`（`:2973-2974` 只核这两个标签的提示是「第二阶段接入」）。
- `tests/test_gate_t024_baseline.py`：`:1088` it 标题「…4 张角色卡的 [更改…] 仍禁用；角色页禁用数 11」；`:1102-1104` 四个 [更改…] 的禁用断言；`:1105-1106` 禁用数 11；`:1095-1101` [保存当前为方案…] 仍禁用（**本片不动**）；`:43` 与 `:1609` 的说明文字里写着「角色页禁用数 6 / 11」。
- `tests/test_gate_t045_baseline.py`：`:125-127` `ROLES_PAGE_DISABLED = 11`（桩下角色页禁用按钮数）；`:555-562` 核 `page-app.test.tsx` 的角色页禁用数与 it 标题（`:560` 的正则认任意数字，`'角色页 11'` 是兜底字面量）；`:1231-1233` page 探针里的「角色页禁用按钮数 11」；`:1125-1127` 探针说明；`:95-104` `BASELINE_DIGESTS` 冻结 `package.json`、`package-lock.json`、`roles-styles.css`、`mock/profiles.json`、`hubChangeLines.ts` 的字节；`:313-343` S02 钉 `useLivePreview` 的既有字段与开头两行注释；`:347-409` S03 钉 `HubBindForm.tsx`；`:412-444` S04 钉 `hub-bind-form.css`；`:741-748` S10 钉新源码的规矩。
- 包内测试：`desktop/web/tests/page-app.test.tsx:91-95`（describe 标题「写入口个数（过渡）」一字不动；`:93` 的 it 标题与 `:95` 的 `toBe(11)`）；`desktop/web/tests/page-roles.test.tsx:43`（`<RoleCard role activePreset />` 两 prop 写法下 [更改…] 禁用）；`desktop/web/tests/writes-hub-bind.test.tsx:299-317`（桩下角色页禁用按钮实测 11 与它的构成注释）。
- 其余关键字（`rl-card__foot`、`DisabledAction`、`RoleCard`、`roles-RoleCard`、`WriteAction`、`role.set`、`binding_changes`）在 `desktop/web/tests/` 与全部门禁基准里搜过：t006/t012/t019/t020/t022/t023/t024/t031/t037/t038/t041/t043/t044 对 `api.ts` 导出与 `WriteAction` 成员都是**包含式核对**（既有成员一个不许丢），**不受本片影响**；t041/t043/t044 的 `OLD_WRITE_ACTIONS` 同理。
- **（v2 追加）`tests/test_gate_t047_baseline.py` 与 `tests/test_gate_t048_baseline.py` 的字节冻结**：t047 的 `BASELINE_DIGESTS`（`:86-96`）里 `:93` 冻结 `desktop/web/tests/page-app.test.tsx`（4005 字节，sha256 `a8986dee…`）；t048 的 `BASELINE_DIGESTS`（`:130-142`）里 `:131` 冻结 `desktop/web/src/api.ts`（键 `API_REL`，36065 字节，sha256 `f12707a3…`）、`:137` 冻结 `desktop/web/tests/page-app.test.tsx`（同一个 4005 字节 / sha256 `a8986dee…`）。这两处冻结是「本片不许碰」的重复把关，而本片合法要改 `api.ts` 与 `page-app.test.tsx`——**站主 2026-11-18 批准本片解除这两处冻结**（做法见 Steps 第 11 步）。两份文件里 `BASELINE_DIGESTS` 的消费点都是逐项遍历字典（t047 `:828`、t048 `:554`），删掉这三行即解除冻结，别处没有引用这三项的断言；两份文件的其余冻结项（依赖与锁文件、`roles-styles.css`、`mock/profiles.json`、`hubChangeLines.ts`、`roles-hub-logic.test.ts`、两份桩、`runtimes-quizs-logic.ts`、`ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/src/writeroutes.ts` 等）照旧冻结。

### 工具链与锁文件
- `desktop/web` 用 npm：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`（TypeScript 5.6.3）、`npm run build` = `tsc --noEmit && vite build`。
- `desktop/web/tsconfig.json` 的 `include` 只有 `["src", "vite.config.ts"]`：`tests/` 里的文件不过 `tsc --noEmit`，但 vitest 会读到。
- 仓库门禁用 `python -m pytest`；本片不改任何依赖清单与锁文件（`dependency_changes: forbidden`）。

### 基线检查
- 本回合（合同端）只读，没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 执行端动手前先在 `desktop/web` 跑一次 `npm test`（基线应全绿：T050 已结项），把结果记进执行报告；基线上本片的行为一个都不存在（没有 `role.set`、没有角色卡的 [更改…] 表单）。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/pages/readonly1/roles-logic.ts
  - desktop/web/src/pages/readonly1/roles-RoleCard.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/tests/page-roles.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/writes-hub-bind.test.tsx
  - tests/test_gate_t009_baseline.py
  - tests/test_gate_t024_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t048_baseline.py
- allowed_new_files:
  - desktop/web/src/writes/RoleBindForm.tsx
  - desktop/web/tests/writes-role-bind.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t051_*.py
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
  - tests/test_gate_t025_baseline.py
  - tests/test_gate_t026_baseline.py
  - tests/test_gate_t027_baseline.py
  - tests/test_gate_t028_baseline.py
  - tests/test_gate_t029_baseline.py
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
  - tests/test_gate_t049_baseline.py
  - tests/test_gate_t050_baseline.py
  - ts/packages/ui/**
  - scripts/**
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/readonly1/roles-HubPosts.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/src/pages/readonly1/roles-PresetBar.tsx
  - desktop/web/src/writes/HubBindForm.tsx
  - desktop/web/src/writes/hub-bind-form.css
  - desktop/web/src/writes/hubChangeLines.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/mock/profiles.json
  - desktop/web/src/mock/roles.json
  - desktop/web/src/mock/hub-roles.ts
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/src/live/**
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：
  - **入口**：四张角色卡底部的 [更改…] 变成可点的 `Button`（`variant="secondary"`、`size="sm"`，textContent 恰为「更改…」，U+2026）。点它打开对话框，标题 `改绑定：<角色中文名>`（角色中文名由入口文件算好当 prop 传进 `src/writes`，`src/writes` 不跨层引 `src/pages`）。
  - **模式**：对话框里第一个字段是 `Select`（label「模式」），选项只列**这个角色允许的模式**（四个角色的允许模式照 `scripts/kit_roles.py:31-36`：planning_review→交互式宿主、无头；contract→手工、无头；execution→无头；scheduler_agent→关闭、无头），中文名照 `roles-logic.ts` 的 `modeName`；次序照上表。
  - **profile**：选了「无头」时，第二个字段是 `Select`（label「profile」），选项是**全部已登记的 profile 的 id**（按 profiles 的输入顺序；**滤掉以 `_` 开头的 id**——内核把它们当未登记）；没选「无头」时这一个字段不渲染。
  - **预填**：模式——现有模式在可选列表里就用它，否则取第一个可选；profile——现有绑定 profile（`resolvedProfile`）在候选里就用它，否则取第一个候选。
  - **写参数**（`WriteArgs`，键名与服务侧 `role.set` 的键一一对应）：
    - 选的是无头：`target` = 选中的 profile id；**不带** `host`。
    - 选的是模式词（交互式宿主/手工/关闭）：`target` = 该模式词；**不带** `profile`。
    - `host`：只在「选的是交互式宿主」且「现有绑定也是交互式宿主」且「现有 host 非空」时带上现有 host 的值（照原样传回，不给用户编辑）。
    - `cadence_seconds`：只在「角色是 scheduler_agent」且「选的是无头」且「现有绑定也是无头」且「现有 cadence_seconds 是整数」时带上现有值（照原样传回）。按**字符串**放进 `WriteArgs`，由 `writeArgs` 转成 JSON 数字（与 `number` 键同一条规则；预览与执行共用同一份规则，否则服务按确认号记的 argv 对不上、回 409）。
  - **表单底部实时预览**：`useLivePreview('role.set', args, enabled)`，`enabled` 是「表单开着且取值合法」。依次显示：
    - 将运行的命令（`result.command`，`useLivePreview` 已经去掉 `--dry-run` 与 `--json`）；
    - **这个角色**的绑定前后：`result.bindingChanges` 里 `role` 等于本角色码的那一项，显示成一行「from → to」（只有这一项；本角色没有项时不显示这一节）；
    - `result.warnings` 原样逐行；
    - `result.error` 原样（出错时显示错误行，不显示命令）。
  - **`[确认…]` 的门控**：表单开着、取值合法、预览对应当前取值（`current`）、预览 `ok`。点它：**先关掉表单对话框**，再 `start({ action: 'role.set', args })`；表单里放 `<WriteFlow flow={flow} />`。
  - **确认框与执行**（既有 `useWriteFlow` 的语义，不另造）：确认框标题 `改角色绑定 <role>？`；成功轻提示（重读兑现之后才说）`已改角色绑定 <role>`；变化区摘要 `角色 <role> 的绑定改成 <target>`，带了 `host` 追加 `（宿主 <host>）`，带了 `cadence_seconds` 追加 `（间隔 <n> 秒）`；预览没有 binding_changes 时变化区回落到这个摘要。`role.set` 不是危险动作（确认钮是 primary，与 `hub.set` 同款）。
  - **执行**：真实模式 `POST /api/v1/roles/<encodeURIComponent(role)>`，正文**恰好**是 `target`、可选的 `host`、可选的 `cadence_seconds`、加上 `confirmation`（`role` 是路径参数，不重复进正文；`cadence_seconds` 是 JSON 数字）。桩模式走 `mockSetRoleBinding`。
  - **重读**：预览与重读各读一次 `getRoles()`，投影是 `roles[].{role, explicit, binding}`（按 role 排序）；执行成功之后页面 reload（`RolesView` → `RoleCard` → `RoleBindAction` 的 `reload` prop 传下去，roles 与 profiles 一起刷新）。
  - **写完的界面**：角色卡照旧渲染（新的 profile、runtime、模型、思考档位由既有 `normalizeRole` 归一后显示）。
- 边界输入：
  - **没有已登记的 profile**（候选为空）：
    - `execution`（只允许无头）：**可选模式为空** → 入口渲染成**禁用的** `DisabledAction`（`label="更改…"`、`variant="secondary"`、`size="sm"`），悬停给出原因句（逐字见「写法钉死」第 4 条）。
    - 其余三个角色：把「无头」从模式列表里**拿掉**（`Select` 不支持单项禁用），入口仍然可点；原因句写在模式 `Select` 的 `help` 里（`Select` 的 help 会接到 `aria-describedby`）。
  - **未知角色码**（不在 `ROLE_MODES` 里）：可选模式为空 → 入口渲染成禁用的 `DisabledAction`，**不传 reason**（沿用缺省的「第二阶段接入」）；卡片其余部分照旧渲染（未知模式与未知角色码的既有行为一个字不改）。
  - **现有模式不在可选列表里**（例如 execution 没写进配置、mode 是空串）：预填落到第一个可选模式。
  - **现有 profile 不在候选里**：预填落到第一个候选。
  - **从交互式宿主切到别的模式**：不带 `host`（内核对模式词配 `--host` 直接报错）。
  - **从无头切到别的模式**：不带 `cadence_seconds`（内核对模式词配 `--cadence-seconds` 直接报错）。
  - **scheduler_agent 从无头切到无头（换 profile）**：照原样传回 cadence_seconds（内核整条替换，不传就丢）。
  - **对话框关着时**：表单的字段、候选、提示一律不渲染（页面上只有那四个入口按钮与既有的一组）。
  - **kernel 拒绝**（模式与角色不配、profile 没登记、host 非法、cadence 不在 60–86400）：服务端回 400，预览与执行都把原文显示出来；**界面不替内核猜**。
- 错误与重试：
  - 预览失败（服务没回应、非 200、信封 `ok` 为假）：底部显示错误原文（`预览失败：服务没有回应` 或信封 `messages` 原文），`[确认…]` 不可点；不自动重试。
  - 写流程失败（409/5xx/超时/拒绝/过期）：照既有 `useWriteFlow` 与 `WriteConfirmDialog` 的分支显示，**不加新分支、不改既有文案**；表单对话框已经关了，重开还是上次的值（由表单自己的 state 决定）。
  - `binding_changes` 里没有本角色的项：底部不显示前后对比那一节（不编第二份文案）；确认框回落到变化摘要。
- 并发、取消与状态变化：不适用——本片不加并发；表单一次只开一个（点入口开、关掉即丢弃未确认的取值）；`useWriteFlow` 的轮询、计时器与卸载清理照旧（一个字节不改）。
- 兼容性：
  - `api.ts`：`WriteAction` 加 `'role.set'`，**既有 12 个成员一个不许丢**（t041/t043/t044 的 `OLD_WRITE_ACTIONS` 是包含式核对）；既有导出（`preview`、`getOperation`、`removeRuntime`、`addProfile`、`setHubRole`、`getRuntimes` 等）签名与行为不变；新导出是 `setRoleBinding`。
  - `writeArgs`：只是把 `cadence_seconds` 也纳入「转成 JSON 数字」的那条规则（与 `number` 键同一条）；既有键的规则不变，既有动作的预览与执行行为不变。
  - `useLivePreview.ts`：只**加**一个字段 `bindingChanges: BindingChange[]`；既有七个字段语义不变；开头两行注释、`const DEBOUNCE_MS = 300;`、防抖与序号丢弃逻辑一个不动（T040/T045 钉住）。
  - `snapshots.ts`：只**加**一个导出 `roleSnapshot(roles)`；既有导出不变。
  - `useWriteFlow.ts`：只**加** `role.set` 的三个文字分支、一个快照分支、一个执行分派分支；既有动作的文字与分支不变。
  - `roles-logic.ts`：只**加**导出（`ROLE_MODES`/`allowedModes`/`profileIds`）与 `RoleInfo.cadenceSeconds` 一个字段；既有导出 `hubPostName`/`allowedProfiles`/`normalizeHubPost` 与既有 `RoleInfo` 字段语义不变；`normalizeRole` 既有字段的取值规则不变（`cadence_seconds` 只在是整数时给数，其余一律 `null`）；该文件仍然只 `import type`。
  - `RoleCard` 的 props 新增 `candidates?` 与 `reload?`（**都可空**）：`<RoleCard role activePreset />` 这个既有两 prop 写法照样能编译、照样渲染（没有候选时 planning_review/contract/scheduler_agent 的 [更改…] 仍可点——它们还能切到非无头的模式；execution 的入口禁用）。
  - `desktop/web/src/mock` 仍恰 14 份 JSON；`desktop/web/src/pages` 顶层仍恰 9 个 `*Page.tsx`；`desktop/web/src/writes` 不新增 CSS 文件（复用 `hub-bind-form.css` 的 `.hb-*` 类）；`package.json` 与锁文件不变。
  - **本片必然推翻的旧断言**（站主没有在开工前做门禁准备，由执行端在候选里逐处改；逐字新文见 Steps 第 10 步，别的一行不动）：
    1. `tests/test_gate_t009_baseline.py`：`:2370`（[更改…] 由禁用变可点）、`:2374-2378`（不再有「第二阶段接入」的悬停提示，这几行删掉）、`:2969`（可点按钮白名单加「更改…」）、`:2971`（`later` 里去掉「更改…」，[保存当前为方案…] 照旧禁用、悬停照旧）。
    2. `tests/test_gate_t024_baseline.py`：`:1088`（it 标题）、`:1104`（四个 [更改…] 可点）、`:1105-1106`（角色页禁用数 11→7 与说明文字）。
    3. `tests/test_gate_t045_baseline.py`：`:125-127`（`ROLES_PAGE_DISABLED = 7` 与注释）、`:559`（提示里的「（桩下 6+5）」改成新口径）、`:1231-1233`（page 探针的 it 标题与 `toBe(7)`）。
    4. `desktop/web/tests/page-roles.test.tsx:43`（两 prop 写法下 [更改…] 可点）。
    5. `desktop/web/tests/page-app.test.tsx:93-95`（it 标题与 `toBe(7)`；**describe 标题「写入口个数（过渡）」一字不动**）。
    6. `desktop/web/tests/writes-hub-bind.test.tsx:299-317`（describe 标题、it 标题、构成注释与 `toBe(7)`）。
    7. **桩下角色页禁用数的构成**：11 − 4 = **7**（页头 [保存当前为方案…] 1 + 方案条 [切换…] 1 + planner 的「改绑定…」1 + 四个缺省行的「恢复缺省…」4）。四张角色卡的 [更改…] 变成可点后不再计入禁用数。
  - **本片合法要改、但被 t047/t048 字节冻结挡住的两个文件**（站主 2026-11-18 批准解除那两处冻结，做法见 Steps 第 11 步）：`desktop/web/src/api.ts`（t048 `:131` 冻结）与 `desktop/web/tests/page-app.test.tsx`（t047 `:93`、t048 `:137` 冻结）。**只删那三行冻结项**，两份门禁文件的其余内容一字不动。
- **写法钉死**（门禁按源码文本查这几处，逐字照抄）：
  1. `desktop/web/src/api.ts`：`WriteAction` 联合类型里加一行 `  | 'role.set'`；新增 `export function setRoleBinding(`，签名是 `(args: { role: string; target: string; host?: string; cadence_seconds?: string }, confirmation: string)`；真实模式的路径写成 `` `/api/v1/roles/${encodeURIComponent(args.role)}` ``，正文是 `{ ...writeArgs(w), confirmation }`（`w` 里只有 `target`、给了才有的 `host`、给了才有的 `cadence_seconds`）；桩模式调 `mockSetRoleBinding`。
  2. `desktop/web/src/mock/writes.ts`：`baseArgv` 里加 `role.set` 分支——`['config', 'role', 'set', s.role, s.target]`，有 `host` 就追加 `'--host=' + s.host`，有 `cadence_seconds` 就追加 `'--cadence-seconds=' + s.cadence_seconds`；`NEW_ACTIONS` 加 `'role.set'`；`previewData` 里加 `role.set` 分支（`binding_changes` 至多一项 `{ role, from, to }`，`from` 取夹具 `roles.json` 里这个角色当前绑定的显示值（无头取 profile，其余取 mode，取不到给 `—`），`to` 取 `target`；两者相同就不给这一项；`resources: ['roles']`；`hub_changes: []`；`running_turns: []`）；新增 `export function mockSetRoleBinding(args, confirmation)`，内部走既有的 `confirmWrite('role.set', ...)`；**`WriteScenario` 的值一个都不许加**。
  3. `desktop/web/src/writes/useLivePreview.ts`：`LivePreview` 接口里加一行 `  bindingChanges: BindingChange[];`；`fromReply` 里写 `bindingChanges: data?.binding_changes ?? [],`；`useEffect` 里失败分支的字面量补 `bindingChanges: [],`；开头两行注释与 `DEBOUNCE_MS` 一字不动；`import` 那行扩成含 `type BindingChange`。
  4. `desktop/web/src/writes/RoleBindForm.tsx`（新）：从 `../api` **只 `import type`**；导出 `export function RoleBindAction(`；原因句常量逐字为 `没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile`（与 `HubBindForm.tsx` 里那句逐字不同）；对话框标题 `改绑定：${roleLabel}`；两个 `Select` 的 label 分别是「模式」与「profile」；按钮 textContent 恰为「更改…」，`variant="secondary"`、`size="sm"`；样式复用 `import './hub-bind-form.css';`（放在组件 import 之后，位置照 `HubBindForm.tsx`）；不跨层引 `src/pages`；不写死颜色、不出现网络词与 `role="status"`。
  5. `desktop/web/src/pages/readonly1/roles-logic.ts`：新导出写成 `export function allowedModes(code: string): string[]`（未知角色给 `[]`）与 `export function profileIds(profiles: readonly ProfilesData['profiles'][number][]): string[]`（按输入顺序返回 id，滤掉以 `_` 开头的）；`RoleInfo` 加 `cadenceSeconds: number | null`；该文件只 `import type`。
  6. `desktop/web/src/pages/readonly1/roles-RoleCard.tsx`：卡底换成 `<RoleBindAction … />`；新 props `candidates?` 与 `reload?` 都可选；只读部分（标题、标签、dl、说明）一个字不改。
  7. `desktop/web/src/pages/readonly1/roles-RolesView.tsx`：给每张卡传 `candidates={profileIds(data.profiles.profiles)}` 与 `reload={reload}`；从 `'../../api'` 只 `import type`。
  8. `desktop/web/src/writes/useWriteFlow.ts`：三条文字逐字——`改角色绑定 ${args.role}？`、`已改角色绑定 ${args.role}`、`角色 ${args.role} 的绑定改成 ${args.target}`；快照分支读 `getRoles()` + `roleSnapshot`；执行分派里 `role.set` 分支排在 `setPluginEnabled` 兜底之前。
- **执行端口径约束**：桩下角色页禁用数若**实测不是 7**，不许改产品行为或藏按钮去凑数，也不许改别的数字凑数；把实测值与逐项构成照实写进执行报告的 `contract_conflicts`（同时在 `interpretations` 里写清实测值与差异），交战后门禁与终审裁定。放宽那几处时以合同给的**新文逐字**为准（不要顺手改同文件里的其他说明文字）。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件**（只读；基线上还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/api.ts`**：`WriteAction` 加 `'role.set'`；`writeArgs` 的数字规则扩成 `key === 'number' || key === 'cadence_seconds'`；新增 `export function setRoleBinding(args, confirmation)`（真实模式 `POST /api/v1/roles/<role>`，正文 `target` + 可选 `host` + 可选 `cadence_seconds` + `confirmation`；桩模式 `mockSetRoleBinding`）；既有导出与成员一个不动。
3. **`desktop/web/src/mock/writes.ts`**：`baseArgv` 加 `role.set` 分支；`NEW_ACTIONS` 加 `'role.set'`；`previewData` 加 `role.set` 分支；新增 `export function mockSetRoleBinding`（走既有 `confirmWrite`）；**不加桩情景**。
4. **`desktop/web/src/writes/useLivePreview.ts`**：只加 `bindingChanges: BindingChange[]` 一个字段（`LivePreview`、`fromReply`、失败分支字面量三处）；既有字段、开头两行注释、`DEBOUNCE_MS` 一个不动。
5. **`desktop/web/src/writes/snapshots.ts`**：新增 `export interface RoleSnapshot` 与 `export function roleSnapshot(roles: RolesData): RoleSnapshot`（投影 `roles[].{role, explicit, binding}`，按 role 排序；既有导出不变）。
6. **`desktop/web/src/writes/useWriteFlow.ts`**：`readSnapshot` 加 `role.set` 分支（`getRoles()` + `roleSnapshot`）；`titleOf`/`successTextOf`/`changeSummaryOf` 加 `role.set` 三条文字（逐字见「写法钉死」第 8 条）；`confirm` 的分派链里加 `role.set → setRoleBinding(...)`（排在 `setPluginEnabled` 兜底之前）；既有分支一个不动。
7. **`desktop/web/src/pages/readonly1/roles-logic.ts`**：加 `ROLE_MODES` 表（注释写明出自 `scripts/kit_roles.py:31-36`）、`allowedModes`、`profileIds`；`RoleInfo` 加 `cadenceSeconds`（`RawRole.binding` 也收 `cadence_seconds`）；既有导出与既有字段语义不变；只 `import type`。
8. **新建 `desktop/web/src/writes/RoleBindForm.tsx`**（照 `HubBindForm.tsx` 的结构）：
   - 导出 `RoleBindAction`（props：`role`、`roleLabel`、`modes: readonly {value,label}[]`、`candidates: readonly string[]`、现有绑定 `{mode, profile, host, cadenceSeconds}`、`reload?`）；
   - 可选模式 = `modes` 去掉「无头」（候选为空时）；可选模式为空时渲染禁用的 `DisabledAction`（未知角色不传 reason；只有 execution 且没有候选时传原因句）；
   - 对话框：模式 `Select`（label「模式」）、无头时 profile `Select`（label「profile」）；底部按 Behavior contract 显示命令、本角色的前后、warnings、错误原文；`[确认…]` 门控与「先关表单再 start」的次序照 Behavior contract；表单里放 `<WriteFlow flow={flow} />`；
   - 预填与参数组装（host / cadence_seconds 的原样传回规则）照 Behavior contract；样式复用 `hub-bind-form.css` 的 `.hb-*` 类。
9. **`desktop/web/src/pages/readonly1/roles-RoleCard.tsx`**：卡底换成 `<RoleBindAction … />`（新 props `candidates?`、`reload?` 都可选）；只读部分一个字不改。
   **`desktop/web/src/pages/readonly1/roles-RolesView.tsx`**：给每张卡传 `candidates` 与 `reload`。
10. **改六处旧断言**（逐字照抄，别的一行不动）：
    - **`tests/test_gate_t009_baseline.py`**：
      - `:2365` 的 it 标题改成：
        ```ts
          it('[更改…] 是可点的 secondary sm', async () => {
        ```
      - `:2370` 改成 `      expect(b.disabled).toBe(false);`
      - 删掉 `:2374-2378` 这五行（`vi.useFakeTimers();` 起、到 `expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('第二阶段接入');` 止），保留收尾的 `});`。
      - `:2969` 改成：
        ```ts
            expect(outsideWhitelist(['切换…', '使用', '删除…', '删除', '新建 profile', '编辑', '改绑定…', '恢复缺省…', '更改…'])).toEqual([]);
        ```
      - `:2971` 改成 `    const later = ['保存当前为方案…'];`
      - **这个文件里的其余一切都不许动**（别的断言、别的 `it()` 标题、别的说明文字、夹具、探针）。
    - **`tests/test_gate_t024_baseline.py`**：
      - `:1088` 的 it 标题改成：
        ```ts
          it('两个入口的样式与仍在禁用的入口：页头次序照旧、[新建 profile] secondary/md 可点；4 张角色卡的 [更改…] 可点；角色页禁用数 7', async () => {
        ```
      - `:1104` 改成 `    for (const c of changes) expect(c.disabled, '[更改…] 可点（T051 接上）').toBe(false);`
      - `:1105` 的 `const disabledCount = buttons(pageFrame()).filter((b) => b.disabled).length;` **不动**；`:1106` 改成：
        ```ts
            expect(disabledCount, '角色页禁用按钮 9→6→11→7（T051 接上 4 个 [更改…]；page-app 的口径）').toBe(7);
        ```
      - `:1095-1101`（[保存当前为方案…] 仍禁用）与 `:1102-1103`（四个 [更改…] 的个数是 4）**不动**；其余一切不许动。
    - **`tests/test_gate_t045_baseline.py`**：
      - `:125-127` 的注释与常量改成：
        ```python
        # 桩下角色页禁用按钮数（page-app 的口径）：页头「保存当前为方案…」与方案条的「切换…」2 个 +
        # planner 无候选的「改绑定…」1 个 + coordinator/planner/gate/audit 缺省行的「恢复缺省…」4 个 = 7
        ROLES_PAGE_DISABLED = 7
        ```
      - `:559` 改成 `        problems.append(f"page-app.test.tsx 的角色页禁用数应是 {ROLES_PAGE_DISABLED}（桩下 2+1+4）")`
      - `:1231-1233` 改成：
        ```ts
          it('角色页禁用按钮数 7（page-app 的口径：2 旧 + planner 改绑定… + 4 个缺省行恢复缺省…）', async () => {
            await mountApp('#/roles');
            expect(qa(frame(), 'button').filter((b: any) => b.disabled).length).toBe(7);
          });
        ```
      - `:560-562` 的标题正则认任意数字（`'角色页 7'` 仍匹配 `角色页 \d+（…）、运行时页 5、总览 0`），**不用改**；`:96`、`:161`、`:165`、`:724` 这些说明文字里的「禁用数 11」是说明、不是断言，**不动**；其余一切不许动。
    - **`desktop/web/tests/page-roles.test.tsx:43`** 改成 `    expect(btn(c, '更改…')?.disabled, '[更改…] 可点（没有候选时仍可切到交互式宿主）').toBe(false);`
    - **`desktop/web/tests/page-app.test.tsx:93-95`**：
      ```ts
        it('角色页 7（保存当前为方案…、方案条的 [切换…]、planner 改绑定…、4 个缺省行恢复缺省…）、运行时页 5、总览 0', async () => {
          await mount('#/roles');
          expect(disabled().length, '角色页').toBe(7);
      ```
      **`:91` 的 describe 标题「写入口个数（过渡）」一字不动**；运行时页 5 与总览 0 照旧。
    - **`desktop/web/tests/writes-hub-bind.test.tsx:299-317`**：`describe('桩下角色页禁用按钮实测 11', …)` 改成 `describe('桩下角色页禁用按钮实测 7', …)`；it 标题改成 `it('整页 button[disabled] 是 7（2 旧 + planner 改绑定… 1 + 4 个缺省行恢复缺省…）', …)`；构成注释改成：
      ```ts
          // 构成：页头「保存当前为方案…」1 + 方案条的「切换…」1 = 2；
          // planner 只许 claude-code、无 profile 候选 → 「改绑定…」1；
          // coordinator/planner/gate/audit 是缺省行 → 「恢复缺省…」4。合计 7。
      ```
      `expect(disabled.length, '桩下角色页禁用按钮实测').toBe(11);` 改成 `.toBe(7);`；`bindDisabled`/`unsetDisabled` 两条断言**不动**。
11. **解除 t047/t048 对 `api.ts` 与 `page-app.test.tsx` 的字节冻结**（站主 2026-11-18 批准；**只删这三行，别的行一个字不动**）：
    - **`tests/test_gate_t047_baseline.py`**：在 `BASELINE_DIGESTS` 字典（`:86-96`）里**整行删掉** `:93` 这一行：
      ```python
          f"{TESTS_REL}/page-app.test.tsx": (4005, "a8986dee7f02a1f43579ae8249a9f51ab0158c873e5b7525fda31edd458698e9"),
      ```
    - **`tests/test_gate_t048_baseline.py`**：在 `BASELINE_DIGESTS` 字典（`:130-142`）里**整行删掉** `:131` 与 `:137` 这两行：
      ```python
          API_REL: (36065, "f12707a3f00d94355d74058053b9f9307cd01c970ef193da05f75529957e69ce"),
      ```
      ```python
          f"{TESTS_REL}/page-app.test.tsx": (4005, "a8986dee7f02a1f43579ae8249a9f51ab0158c873e5b7525fda31edd458698e9"),
      ```
    - 这两份文件里**其余一切都不许动**：docstring、注释、`BASELINE_DIGESTS` 的其余冻结项、别的断言、别的 `it()` 标题、探针、夹具一个字不动；**不加注释**、不改写成等值表达式、不动行序、不动缩进风格。
    - **不许借机放宽别的冻结项或任何断言**：两份文件里其余的字节冻结（依赖与锁文件、`roles-styles.css`、`mock/profiles.json`、`hubChangeLines.ts`、`roles-hub-logic.test.ts`、两份桩、`runtimes-quizs-logic.ts`、`ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/src/writeroutes.ts` 等）照旧有效。
    - 结果：这两份文件相对 `base_sha` 的差异**恰好**是上面这三行被删除（`git diff` 的内容就是这三行，别的一行都不许有）；一审、终审专看这份差异。
12. **新增 `desktop/web/tests/writes-role-bind.test.tsx`**（不许 `skip`/`only`/`todo`；测真实实现，不把业务逻辑抄一份进测试）：
    - `allowedModes` 与 `profileIds` 的边界：四个角色各自的允许模式（次序照 `ROLE_MODES`）、未知角色给 `[]`；`profileIds` 按输入顺序、滤掉以 `_` 开头的 id。
    - 四个角色各自只列允许的模式（中文名照 `modeName`；execution 只有「无头」）。
    - 选无头再选 profile：底部预览出现命令与**本角色**的前后两侧；warnings 原文照显示。
    - 确认后（真实模式，注入假客户端）调 `POST /api/v1/roles/<role>`：正文的键**恰好**是 `target`（+ 预填的 `host` 或 `cadence_seconds`）+ `confirmation`；`cadence_seconds` 是 JSON 数字；`role` 不进正文。
    - planning_review 原来是 interactive_host、host=claude-code：保持 interactive_host 时带 `host`，切到 headless 时不带。
    - scheduler_agent 原来是无头、cadence=3600：保持无头时带 `cadence_seconds`，切到 disabled 时不带。
    - 写完重读：`GET /api/v1/roles` 的次数增加。
    - 没有 profile 时：contract/planning_review/scheduler_agent 的模式下拉里没有「无头」，原因句可见；execution 的入口禁用，悬停出原因句。
    - 对话框关着时不渲染候选与多余的按钮。
13. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → R01**（本 worktree 里若没有 `node_modules`，先在 `desktop/web` 跑一次 `npm ci --no-audit --no-fund`）。R01 的墙钟可能逼近 2940 秒上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
14. 写执行报告；遇到合同未定义的行为（例如服务回的字段形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t051_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py -q` · cwd：仓库根 · 超时：2940s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：`api.ts` 有 `role.set` 这个写动作与 `setRoleBinding` 写函数（真实模式 `POST /api/v1/roles/<role>`，正文 `target` + 可选 `host` + 可选 `cadence_seconds` + `confirmation`；`cadence_seconds` 是 JSON 数字）；`writeArgs` 把 `cadence_seconds` 与 `number` 同一条规则转数字；既有 12 个 `WriteAction` 成员与既有导出一个不丢；目的：预览与执行必须用同一份参数规则，否则服务按确认号记的 argv 对不上、回 409；证据：V01、V02、R01、scope
- D02：`mock/writes.ts` 认 `role.set`（`baseArgv`、`NEW_ACTIONS`、`previewData`、`mockSetRoleBinding` 四处），桩里能走完预览 → 确认 → 执行；**`WriteScenario` 一个值都不加**；目的：桩模式的角色页也要能演示这条写入口（T044 S07 把情景数钉死在 27）；证据：V01、R01
- D03：`useLivePreview` 只多 `bindingChanges` 一个字段，既有七个字段与开头两行注释、`DEBOUNCE_MS` 一个不动；`snapshots.ts` 只多 `roleSnapshot` 一个导出；目的：表单底部要显示这个角色的绑定前后，但不能碰既有预览的时序与快照口径；证据：V01、R01、review
- D04：`useWriteFlow` 认 `role.set`：三条文字（`改角色绑定 <role>？` / `已改角色绑定 <role>` / `角色 <role> 的绑定改成 <target>`）、快照读 `getRoles()` + `roleSnapshot`、执行分派到 `setRoleBinding`；既有动作的文字与分支不变；`role.set` 不是危险动作；目的：写流程的语义一个字都不许另造；证据：V01、G01、R01
- D05：`roles-logic.ts` 新增 `allowedModes`（四个角色各自的允许模式、未知角色给 `[]`）与 `profileIds`（按输入顺序、滤掉以 `_` 开头的 id），`RoleInfo` 加 `cadenceSeconds`（整数才给数，其余 `null`）；既有导出与既有字段语义不变；只 `import type`；目的：模式与候选是内核的硬规则，界面上先按同一份规则算出来；证据：V01、R01
- D06：四张角色卡的 [更改…] 是可点的 secondary/sm 按钮，点开「改绑定：<角色中文名>」：模式只列该角色允许的模式，无头时再选已登记的 profile；底部实时预览显示命令、**本角色**的绑定前后、warnings 原文、错误原文；`[确认…]` 门控是「取值合法 + 预览对应当前取值 + 预览 ok」，点它先关表单再 `start`；目的：这是本页唯一接上的角色写入口，预览与门控照 HubBindForm 的既有形状；证据：V01、G01
- D07：换绑定不悄悄丢字段：模式预填现有模式（不在可选里就取第一个）、profile 预填现有 profile（不在候选里就取第一个）；仍选交互式宿主时照原样传回 `host`，仍选无头（scheduler_agent）时照原样传回 `cadence_seconds`，切到别的模式就不带这两个键；目的：内核是整条替换绑定，不传就丢；证据：V01
- D08：没有已登记的 profile 时：execution 的入口禁用并悬停出原因句，其余三个角色的模式下拉里没有「无头」且原因句在 `Select` 的 help 里；原因句只写在 `src/writes/RoleBindForm.tsx` 里，与 `HubBindForm.tsx` 那句逐字不同；目的：没有 profile 时无头这条路本来就走不通，界面要先说清楚；证据：V01、G01
- D09：写完重读整页（`getRoles` 的次数增加，`reload` 传下去，roles 与 profiles 一起刷新），成功轻提示在重读兑现之后才说；目的：卡片上要看到新的 profile 与模型；证据：V01
- D10：六处旧断言照新行为改（t009 四处、t024 四处、t045 三处、page-roles 一处、page-app 三处、writes-hub-bind 五处；逐字新文见 Steps 第 10 步），两个 describe 标题（「写入口个数（过渡）」与「桩下角色页禁用按钮实测」）照旧只改数字不改标题结构，既有断言没被删、跳过或弱化；目的：本片必然把角色页禁用数从 11 变成 7、把 [更改…] 变成可点，不改这些断言任何合规实现都过不了 R01；证据：R01、scope、review
- D11：新增 `desktop/web/tests/writes-role-bind.test.tsx`，覆盖 D06–D09 点名的每一项（四个角色的模式、profile 候选、预览的前后、正文的键与数字类型、host/cadence 的原样传回、重读、没有 profile 时的两种形态、对话框关着不渲染）；不用 `skip`/`only`/`todo`；测真实实现；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、review
- D12：所有修改都在允许集合内（可改 16 个文件、可新增 2 个文件），没有碰 forbidden_paths（`tests/test_gate_t051_*.py`、其余 45 份门禁基准、`ts/packages/ui/**`、`scripts/**`、`roles-styles.css`、`mock/profiles.json`、`mock/roles.json`、`hubChangeLines.ts`、`HubBindForm.tsx`、`hub-bind-form.css`、`components/**`、`shell/**`、`live/**`、`package.json` 与锁文件）；`package.json` 与锁文件不变；目的：这一片不许顺手改别的片的地盘；证据：scope、review
- D13：新代码守既有源码规矩：`RoleBindForm.tsx` 从 `../api` 只 `import type`、不碰 DOM 与时钟、不出现网络词与危险写入类词、不写死颜色、不出现 `role="status"`；复用 `hub-bind-form.css` 的 `.hb-*` 类，不新建 CSS 文件、不改 `roles-styles.css`；`desktop/web/src/mock` 仍恰 14 份 JSON、`desktop/web/src/pages` 顶层仍恰 9 个 `*Page.tsx`；目的：不破 T006/T009/T013/T038/T044/T045 的长期门禁；证据：V01、V03、R01、review
- D14：`tests/test_gate_t047_baseline.py` 与 `tests/test_gate_t048_baseline.py` 相对 `base_sha` 的差异**恰好**是删掉三行——t047 删 `BASELINE_DIGESTS` 里 `f"{TESTS_REL}/page-app.test.tsx": (4005, "a8986dee…")` 那一行；t048 删 `API_REL: (36065, "f12707a3…")` 那一行与同一行 `f"{TESTS_REL}/page-app.test.tsx": (4005, "a8986dee…")`；两份文件的其余行（docstring、注释、其余冻结项与断言）一个字不动、不加注释；这两处对 `api.ts` 与 `page-app.test.tsx` 的字节冻结按站主批准解除；目的：本片合法要改这两个文件，那两处冻结是「本片不许碰」的重复把关，留在那里任何合规实现都过不了 R01；证据：R01、scope、review

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `api.ts` 里没有 `WriteAction`/`writeArgs`、`useWriteFlow` 的 confirm 没有 `role.set` 分支、`roles-logic.ts` 没有 `modeName`、`mock/writes.ts` 里没有 `NEW_ACTIONS`/`baseArgv`/`previewData`），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `ts/packages/ui`、`scripts/`、`components/**`、`shell/**`、`roles-styles.css`、`mock/profiles.json`、`hubChangeLines.ts`、`HubBindForm.tsx`、`hub-bind-form.css`、t009/t024/t045/t047/t048 以外的任何门禁测试文件）。
- 那六处旧断言在工作目录里**已经不是**合同写的样子（例如行号变了、那几处不再是描述「角色页禁用数」与「[更改…]」的地方、或者已经被别的改动放宽成 7）：停下并报告，不要顺手改别的断言或探针来"对上"。
- `tests/test_gate_t047_baseline.py` 或 `tests/test_gate_t048_baseline.py` 里 `BASELINE_DIGESTS` 的那三行在工作目录里**已经不是**合同写的样子（行号变了、值变了、或者那几行已经不在了）：停下并报告，不要顺手改别的冻结项来"对上"。
- 门禁端交付的本片门禁基准测试文件与本合同的「写法钉死」一节出现实质冲突（例如它要求的前后对比字段名与本合同给的不一致）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在本片显示角色的思考档位编辑框、要做凭据录入、或要把 [保存当前为方案…] 做成可点）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t051-desktop-web-role-bind` 汇总，含返工版本；累计已用 1 次 → 本版留 2 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（按 task-id 跨版本累计；累计已用 2514 秒 → 剩余 13686 秒 ≥ 本版 2 × 5400 = 10800 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 15 分钟；实现（api/mock/useLivePreview/snapshots/useWriteFlow/roles-logic/RoleBindForm/RoleCard/RolesView）50 分钟；六处旧断言的逐字改动 15 分钟；三行字节冻结删除 5 分钟；新包内测试 25 分钟；必要检查（G01、V01、V02、V03、R01，R01 约 25–40 分钟、可分批跑）35 分钟；最终报告 5 分钟；总计约 150 分钟，单轮时限 5400 秒（90 分钟）——总量 16200 秒覆盖本版与两次返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

<!-- 站主决定（原文，20261118T041634359258Z-owner-8ea995；内核另附一份）：
答复 T051 的两件事（记为站主决定，合同末尾附原文）：走合同出新版本，我指定 2-contract 返工；门禁端随后照下面第二条重交。

一、R01（站主的错：任务书只让按关键字搜，漏了 T047、T048 门禁对 api.ts、page-app.test.tsx 的字节冻结）。那两处冻结是当时“本片不许碰”的重复把关，本片合法要改这两个文件，冻结去掉。合同 v2 在 v1 上只加下面这些，其余一字不动：
1. allowed_modified_files 加 tests/test_gate_t047_baseline.py、tests/test_gate_t048_baseline.py，并从 forbidden_paths 拿掉这两份（本片自己的 tests/test_gate_t051_baseline.py 照旧禁改）。
2. Steps 与 DoD 写死：这两份文件各自的 BASELINE_DIGESTS 字典里整行删除，共三行，别的行（docstring、注释、其余冻结项与断言）一个字不动，不加注释：
   - t047：键为 f"{TESTS_REL}/page-app.test.tsx"、值 (4005, "a8986dee…") 的那一行；
   - t048：键为 API_REL、值 (36065, "f12707a3…") 的那一行，与键为 f"{TESTS_REL}/page-app.test.tsx"、值 (4005, "a8986dee…") 的那一行。
   整行原文由合同端从两份文件里逐字抄进合同。
3. 证据：R01 全过；这两份文件的差异恰好是删掉这三行（一审、终审专看这份差异）。

二、G01：探针确实错在门禁端。tests/test_gate_t051_baseline.py 真实模式那条“planning_review 保持交互式宿主…”里，await openForm('planning_review'); 之后直接 await confirmWrite('planning_review');，没等预览；同一文件别处打开表单后都先 await sleep(450); await flush(); 再点 [确认…]。合同重交后门禁端重交基准测试：以上一版基准（提交 7d568441 里的 tests/test_gate_t051_baseline.py，用 git show 取出）为准原样交，只在这两行之间补 await sleep(450);、await flush(); 两行（缩进照上下文），不改别的、不加断言、不迁就实现。上一版一审已判过的部分照旧作数，一审重点看合同 v2 的新增范围与这两行测试差异。 -->

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261118T041634359258Z-owner-8ea995：

> 答复 T051 的两件事（记为站主决定，合同末尾附原文）：走合同出新版本，我指定 2-contract 返工；门禁端随后照下面第二条重交。
>
> 一、R01（站主的错：任务书只让按关键字搜，漏了 T047、T048 门禁对 api.ts、page-app.test.tsx 的字节冻结）。那两处冻结是当时“本片不许碰”的重复把关，本片合法要改这两个文件，冻结去掉。合同 v2 在 v1 上只加下面这些，其余一字不动：
> 1. allowed_modified_files 加 tests/test_gate_t047_baseline.py、tests/test_gate_t048_baseline.py，并从 forbidden_paths 拿掉这两份（本片自己的 tests/test_gate_t051_baseline.py 照旧禁改）。
> 2. Steps 与 DoD 写死：这两份文件各自的 BASELINE_DIGESTS 字典里整行删除，共三行，别的行（docstring、注释、其余冻结项与断言）一个字不动，不加注释：
>    - t047：键为 f"{TESTS_REL}/page-app.test.tsx"、值 (4005, "a8986dee…") 的那一行；
>    - t048：键为 API_REL、值 (36065, "f12707a3…") 的那一行，与键为 f"{TESTS_REL}/page-app.test.tsx"、值 (4005, "a8986dee…") 的那一行。
>    整行原文由合同端从两份文件里逐字抄进合同。
> 3. 证据：R01 全过；这两份文件的差异恰好是删掉这三行（一审、终审专看这份差异）。
>
> 二、G01：探针确实错在门禁端。tests/test_gate_t051_baseline.py 真实模式那条“planning_review 保持交互式宿主…”里，`await openForm('planning_review');` 之后直接 `await confirmWrite('planning_review');`，没等预览；同一文件别处打开表单后都先 `await sleep(450);` `await flush();` 再点 [确认…]。合同重交后门禁端重交基准测试：以上一版基准（提交 7d568441 里的 tests/test_gate_t051_baseline.py，用 git show 取出）为准原样交，只在这两行之间补 `await sleep(450);`、`await flush();` 两行（缩进照上下文），不改别的、不加断言、不迁就实现。上一版一审已判过的部分照旧作数，一审重点看合同 v2 的新增范围与这两行测试差异。
