# TASK: t045-desktop-web-hub-bind-entry

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 641c0e91dbeea39150b3d62cc61f10efc51beb70
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
角色与模型页的「七端岗位」一组每行加两个写入口：「改绑定…」（新表单：主选 + 替补 + 底部实时预览）与「恢复缺省…」（直接交给既有写流程）。改绑定的确认与执行走既有的 `useWriteFlow`（预览 → 确认 → 执行 → 重读 → 终态），成功之后页面 reload；表单位于 `desktop/web/src/writes/HubBindForm.tsx`，入口文件只放按钮。

## Non-goals
- 不做岗位「拿到了什么」（档位三值、回合预算、工具面、证书状态）。
- 不做凭据录入、资格认证；不在 profile 表单里从提供方档案选模型。
- 不改 `ts/packages/ui/**`（服务端）与内核 `scripts/**`；不改 `desktop/web/src/api.ts`、`desktop/web/src/writes/useWriteFlow.ts`、`desktop/web/src/writes/WriteConfirmDialog.tsx`、`desktop/web/src/writes/hubChangeLines.ts`、`desktop/web/src/mock/**`（桩的写情景是 A 片范围）。
- 不改 `desktop/web/src/pages/readonly1/roles-styles.css`（T038 S08 有基线前缀 sha256）；样式放新 CSS 文件。
- 不改 T038 的 `desktop/web/tests/roles-hub-logic.test.ts`；除 `tests/test_gate_t024_baseline.py` 的三处（见 Steps 第 8 步）外不改任何 `tests/test_gate_*.py`。
- 不做范围外重构；不为让测试通过而放宽既有断言。

## Repository facts
以下事实都在本回合的工作目录（基线 `5ac97d851a586be26fff13c518910c091834542e`）里逐条读过；行号按该基线。规划报告是在旧基线 `c2fad267` 上写的，**以本节为准**。

### 前端现状
- `desktop/web/src/pages/readonly1/roles-HubPosts.tsx`：`Section title="七端岗位"`；`Table className="rl-table rl-hub"`、`aria-label="七端岗位"`、`rowHeight={40}`；六列（岗位、运行时、模型、思考档位、来源、替补），行属性用 `rowAttrs` 给 `data-post`（**不用 `data-role`**）；读失败分支只出失败信封与 `pre`、**不渲染表格行、没有任何按钮**；props 现在只有 `hub: Envelope<HubRolesData>`。
- `desktop/web/src/pages/readonly1/roles-RolesView.tsx`：`:39` 渲染 `<HubPosts hub={data.hub} />`（位置在角色卡网格之后、`ProfilesTable` 之前）；`RolesView` 手上已有 `data.profiles` 与可选的 `reload`。
- `desktop/web/src/pages/RolesPage.tsx`：`:23-37` 的 `loadRoles` 并行读 `getRoles/getProfiles/getPresets/getHubRoles`，hub 的信封整个进 `data.hub`（不参与整页失败判定）→ **hub 与 profiles 来自同一次读，reload 一起刷新**。
- `desktop/web/src/pages/readonly1/roles-logic.ts`：既有导出 `hubPostName`（六个岗位中文名）、`allowedProfiles(profiles, allowedAdapters)`（只留 adapter 是字符串且在允许名单里的 profile，按输入顺序返回 id）、`normalizeHubPost`（给出 `source`、`allowedAdapters`、`profile`、`fallback` 等）。T038 S07 只要求这三个导出在位（多导出安全）且该文件只 `import type`。
- `desktop/web/src/api.ts`：
  - `PreviewData`（`:121-134`）有 `hub_changes: HubChange[]` 与 `running_turns: string[]`；`HubChange`（`:116-119`）、`HubChangeSide`（`:104-113`）、`HubChangeFallback`（`:94-102`）三个类型都从 `'../api'` 导出。
  - `setHubRole(args: { post; profile; fallback? }, confirmation)`（`:815-830`）→ 真实模式 `POST /api/v1/hub/roles/<post>`，正文 `{ profile, fallback?, confirmation }`（`fallback` 没给就不带这个键）；`unsetHubRole(post, confirmation)`（`:832-842`）→ `POST /api/v1/hub/roles/<post>/unset`，正文只有 `{ confirmation }`。
- `desktop/web/src/writes/useWriteFlow.ts`（A 片已接好，本片不改）：
  - `useWriteFlow(reload)` 返回 `{ start, flow }`；`start` 收 `WriteSpec { action, args, title? }`。
  - `confirm()` 的分支链里 `hub.set → setHubRole(...)`、`hub.unset → unsetHubRole(post, 确认号)`（排在 `setPluginEnabled` 之前）。
  - `titleOf`：`hub.set` → `改绑定 ${args.post}？`；`hub.unset` → `恢复缺省 ${args.post}？`。
  - `successTextOf`：`hub.set` → `已改绑定 ${args.post}`；`hub.unset` → `已恢复缺省 ${args.post}`。
  - `changeSummaryOf`：`hub.set` → `岗位 ${args.post} 的主绑定改成 ${args.profile}`，有替补追加 `，替补 ${fallback}`，没有追加 `，没有替补`；`hub.unset` → `岗位 ${args.post} 回到内核缺省`。
  - 预览内容 `content` 里带 `hubChanges: data.hub_changes` 与 `runningTurns: data.running_turns`；`contentOf()` 的缺省给 `[]`。
- `desktop/web/src/writes/WriteConfirmDialog.tsx`：「变化」一节先渲染 `changes`（binding_changes），再按 `hubChanges` 逐岗位渲染一块（小标题 `hubPostLabel(post)` + 四行 `hubChangeLines(change)`）；`changes` 空且 `hubChanges` 空时显示 `summary ?? '预览没有列出变化'`；「影响与风险」一节逐行显示 `runningTurns`。
- `desktop/web/src/writes/hubChangeLines.ts`（A 片新增，**只许复用，不许抄第二份**）：导出 `hubChangeLines(change: HubChange): string[]`（恰好四行，次序：运行时、模型、思考档位、替补；缺省一侧的每行值末尾带「（默认）」；取不到值用 `—`）与 `hubPostLabel(post: string): string`（`协调人（coordinator）` 等六个，未知码原样）。文件头注释写明：`src/writes` 不跨层引 `src/pages`，岗位中文名在这份文件里另维护一份。
- `desktop/web/src/writes/useLivePreview.ts`：开头两行注释与 `const DEBOUNCE_MS = 300;`（T040 S04、T024 S14 钉住）；`LivePreview` 现在只有 `key`、`ok`、`command`、`warnings`、`error` 五个字段——**还没有** `hubChanges` 与 `runningTurns`（本片第 3 步加）。
- `desktop/web/src/components/Select.tsx`：原生 `select`，props 有 `label`、`options: { value, label }[]`，其余原生属性透传（可以传 `disabled`）；没有占位项。
- `desktop/web/src/shell/DisabledAction.tsx`：`<DisabledAction label reason variant size icon />`；`reason` 缺省「第二阶段接入」；用 `Tooltip` 包一个 `disabled` 的 `Button`（提示在悬停 400ms 后才渲染，页面上平时没有这段文字）。**它不接受 `aria-label`**。
- `desktop/web/src/writes/RuntimeForm.tsx`：表单的现成写法（`Dialog` + `Select` + 底部 `useLivePreview` + `[确认…]` 门控：合法 + 预览对应当前取值 + 预览 ok；点 `[确认…]` 先关表单再 `start(spec)`；表单内 `<WriteFlow flow={flow} />`）。
- `desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx`：表里写入口的现成写法（组内一个 `useWriteFlow(reload)`；行内按钮 `variant="ghost" size="sm"`；`<WriteFlow flow={flow} />` 放在 `Section` 里；入口组件从 `src/writes/` 引）。
- `desktop/web/src/writes/writeOutcome.ts`：`WARN` 行 → `successWarn` → `doneWithWarning`（H3 成立）。
- 桩：`desktop/web/src/mock/hub-roles.ts` 六行（coordinator、planner、contract、gate、audit、exec）；`contract` 与 `exec` 是 `source: 'config'`，其余四行 `source: 'default'`；`contract` 的主绑定是 `quizs-m3`（**不在** `desktop/web/src/mock/profiles.json` 里）、替补是 `step-high`；`planner` 的 `allowed_adapters` 只有 `claude-code`。`desktop/web/src/mock/profiles.json` 两条 profile（`step-high`、`step-low`），adapter 都是 `pi`。
- 包内测试：`desktop/web/tests/page-app.test.tsx:91-93`（`describe('写入口个数（过渡）')` 里的角色页禁用数 **6**，`describe` 标题 T037 S06 要认，不许改）；`desktop/web/tests/page-hub.test.tsx:84`（列头断言恰是六列）、`:176`（读失败分支 `qa(sec, 'button').length === 0`）；`desktop/web/tests/roles-hub-logic.test.ts`（T038 的既有测试，不许改）。

### 内核与服务（只读引用，本片不改）
- 内核替补规则：`scripts/kit_roles.py:331-333`——`fallback` 只用于主选适配器是 `quizs` 的岗位，替补自己不能是 `quizs`；主选与替补的适配器都要在该岗位的允许名单里。
- `scripts/kit_roles.py:1045`：`config profile show --json` 的每行带 `adapter`（H1 成立）。
- 服务：`/api/v1/profiles` 只遮 `credential_env`（`ts/packages/ui/src/redaction.ts:58`），其余字段（含 `adapter`）原样透传。

### 门禁现状（在新基线上逐条核对）
- 站主 2026-11-15 的门禁准备（`c0f3ac81`，父 `c2fad267`）三处**都已在新基线上**：
  1. T038 的 `test_transitional_probe_no_write_entries` 已退役（`tests/test_gate_t038_baseline.py:1083` 与 `:1332` 只剩注释；`PROBE_SPECS`/`PROBE_ORDER` 里没有 `trans`）；
  2. T038 的 `test_s05_rolesview_hub` 只要求以 `<HubPosts hub={data.hub}` 开头（`:429-430`）；
  3. T009 的 `test_d11_probe_write_entries_disabled` 的角色页可用按钮白名单已含「改绑定…」「恢复缺省…」（`tests/test_gate_t009_baseline.py:2969`）。
- **第四处（站主三处放宽之外）**：`tests/test_gate_t024_baseline.py` 的 form 探针逐字钉「角色页禁用按钮 6」——`:1088` 的 it 标题、`:1106` 的 `expect(disabledCount, '角色页禁用按钮 9→6（page-app 的口径）').toBe(6);`、`:1609` 的 docstring。本片在桩下新增 5 个禁用按钮（planner 没有候选 → 「改绑定…」禁用 1 个；coordinator、planner、gate、audit 是缺省行 → 「恢复缺省…」禁用 4 个），角色页禁用数由 6 变 11。
  - **站主 2026-11-16 拍板**：这一处放宽由**执行端在候选里做**（照站内既有的先例：同一份门禁文件的同一处断言，由执行端在候选里放宽那一处），只许改上列三处（逐字见 Steps 第 8 步），该文件其余内容一个字不动；门禁端与站主不再代做。理由：合同端开工之后内核不再挪本任务的基线，站主合到 `themis-3.0` 的放宽到不了本片的 R01。
  - 桩下 11 的构成（已复核）：`desktop/web/src/mock/profiles.json` 两条 profile 的 adapter 都是 `pi`；coordinator（允许 quizs+pi）、contract/audit/exec（允许 pi+quizs）、gate（允许 pi）有候选 → 「改绑定…」可点；planner 只许 `claude-code`、无候选 → 「改绑定…」禁用 1 个；coordinator、planner、gate、audit 是缺省行 → 「恢复缺省…」禁用 4 个；原有 6 + 1 + 4 = 11。
  - 本片自己的门禁基准测试文件（门禁端交付，基线上还不存在；命令见 Validation commands 的 G01）**不在**可改范围，执行端不许碰。

### 规划报告假设的核实结论
- **A1 成立**：`PreviewData` 的 `hub_changes: HubChange[]` 与 `running_turns: string[]` 已在位（`api.ts:132-133`）。
- **A2 成立（A 片已导出，不抄第二份）**：前后对比纯逻辑是 `desktop/web/src/writes/hubChangeLines.ts` 的 `hubChangeLines(change: HubChange): string[]`（输入一个 `HubChange`，输出恰好四行文字）与 `hubPostLabel(post: string): string`。本片的表单底部与「恢复缺省…」的确认框都用它。
- **A3 成立**：`useWriteFlow` 的 confirm 分支、标题、轻提示、变化区摘要、快照与重读都已认识 `hub.set`/`hub.unset`（见上）。**用户选出的绑定与现有相同、`hub_changes` 为空时**：确认框的「变化」区回落到 `changeSummaryOf` 给的摘要（`hub.set` → 「岗位 <post> 的主绑定改成 <profile>，没有替补」；`hub.unset` → 「岗位 <post> 回到内核缺省」），本片的表单底部在 `hub_changes` 里没有本岗位的项时**不显示**前后对比那一节（不编第二份文案）。
- **H1、H3 成立**（见上）。
- **H6**：T042/T043/T044 都已结项，新基线上 `api.ts`、T009 白名单、`page-app.test.tsx` 的现状就是本节写的。
- **H7**：桩下角色页禁用按钮由 6 变 11（见上）。
- **H8**：除 `page-app.test.tsx:91` 与 `page-hub.test.tsx:84` 外没有别的包内测试数角色页或七端岗位一组的按钮；T038 的 page 探针只核**前六个**列头（`tests/test_gate_t038_baseline.py:880`）。
- **H9**：WriteFlow 关着、且没有轻提示时不渲染任何按钮；读失败分支整组照旧零按钮（`page-hub.test.tsx:176`）。
- **H10**：hub 与 profiles 同一次 `loadRoles`；reload 之后两份一起刷新（`RolesPage.tsx:23-37`）。
- **T038 S10/S11/S07 保留**：`title="七端岗位"`、`aria-label="七端岗位"`、`rowHeight={40}`、`rl-hub`、`hubPostName` 都要在；不出现 `data-role`；`roles-HubPosts.tsx`、`roles-RolesView.tsx`、`roles-logic.ts` 不出现网络词、T007 禁用词、`role="status"`、内联 style；`roles-logic.ts` 的三个既有导出不动、只许 `import type`。

### 工具链与锁文件
- `desktop/web` 用 npm：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`（TypeScript 5.6.3）、`npm run build` = `tsc --noEmit && vite build`、`npm run check:contract` = `node scripts/token-contract.mjs`（新 CSS 只许用 `desktop/web/src/styles/tokens.css` 里已定义的 `--tt-*` 令牌，不许写死颜色、不许声明令牌）。
- `desktop/web/tsconfig.json` 的 `include` 只有 `["src", "vite.config.ts"]`：`tests/` 里的文件**不过** `tsc --noEmit`，但运行时会被 vitest 读到。
- 仓库门禁用 `python -m pytest`；本片不改任何依赖清单与锁文件（`dependency_changes: forbidden`）。

### 基线检查
- 本回合（合同端）没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 执行端在动手前先在 `desktop/web` 跑一次 `npm test`（基线应全绿：T044 已结项），把结果记进执行报告；基线上本片的行为一个都不存在（没有「操作」列、没有两个按钮、没有 `hubFallbackCandidates`）。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/readonly1/roles-logic.ts
  - desktop/web/src/pages/readonly1/roles-HubPosts.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/tests/page-hub.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - tests/test_gate_t024_baseline.py
- allowed_new_files:
  - desktop/web/src/writes/HubBindForm.tsx
  - desktop/web/src/writes/hub-bind-form.css
  - desktop/web/tests/roles-hub-candidates.test.ts
  - desktop/web/tests/writes-hub-bind.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t045_*.py
  - tests/test_gate_t001_baseline.py
  - tests/test_gate_t002_baseline.py
  - tests/test_gate_t003_baseline.py
  - tests/test_gate_t004_baseline.py
  - tests/test_gate_t005_baseline.py
  - tests/test_gate_t006_baseline.py
  - tests/test_gate_t007_baseline.py
  - tests/test_gate_t008_baseline.py
  - tests/test_gate_t009_baseline.py
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
  - ts/packages/ui/**
  - scripts/**
  - desktop/web/src/api.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/hubChangeLines.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/mock/**
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/src/live/**
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/tests/roles-hub-logic.test.ts
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/writes-dialog.test.tsx
  - desktop/web/tests/writes-flow.test.tsx
  - desktop/web/tests/writes-live-flow.test.tsx
  - desktop/web/tests/writes-live-preview.test.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：
  - **主选候选**：`allowedProfiles(profiles, allowedAdapters)`（现成函数，按 profiles 输入顺序；adapter 不是字符串或不在允许名单里的不算）。
  - **替补候选**（新纯函数 `hubFallbackCandidates(profiles, allowedAdapters, mainProfileId)`，放在 `roles-logic.ts`）：主选 profile 在 `profiles` 里查到的 adapter 是 `'quizs'` 时，返回 `allowedProfiles(profiles, allowedAdapters 去掉 'quizs')`；否则（主选不是 quizs、主选查不到、主选的 adapter 不是字符串、允许名单为空）返回**空数组**。**不许**把 quizs 放进替补候选，也不许给出不在允许名单里的替补。
  - **表单预填**：来源是配置（`source === 'config'`）且现有主绑定在主选候选里 → 预填它；否则预填第一个候选（没有候选则空）。替补：来源是配置且现有替补在替补候选里 → 预填它；否则空。理由：内核的 `hub set` 整条替换绑定，不传替补会清掉原来的替补。
  - **切换主选**：主选改成非 quizs 的 profile 时，替补清空且替补下拉禁用；改成 quizs 的 profile 时替补恢复可选（当前替补若不在新候选里则清空）。
  - **写参数**：`args = { post, profile }`；替补非空才加 `fallback`（替补为空串或没选时不带这个键）。
  - **表单底部实时预览**：`useLivePreview('hub.set', args, enabled)`，`enabled` 是主选非空。依次显示：
    - 将运行的命令（`result.command`，已由 `useLivePreview` 去掉 `--dry-run` 与 `--json`）；
    - 这个岗位的前后对比：`result.hubChanges` 里 `post` 等于本岗位的那一项，用 A 片的 `hubChangeLines(change)` 渲染四行（**复用，不许抄第二份**；`hubChanges` 里没有本岗位的项时不显示这一节）；
    - `result.warnings` 原样逐行；
    - `result.runningTurns` 原样逐行；
    - `result.error` 原样（出错时显示错误行，不显示命令）。
  - **`[确认…]` 的门控**：主选非空 **且** 预览对应当前取值（`current`）**且** 预览 `ok`。点它：先关掉表单对话框，再 `start({ action: 'hub.set', args })`；表单内放 `<WriteFlow flow={flow} />`。
  - **「恢复缺省…」**：来源是配置的行可点 → `start({ action: 'hub.unset', args: { post } })`；来源是缺省的行渲染成**禁用**的 `DisabledAction`，并给出禁用原因句（原因句在 `src/writes/` 里，入口文件不写这句）。确认框与执行由既有 `useWriteFlow` 处理（标题「恢复缺省 <post>？」、轻提示「已恢复缺省 <post>」、变化区显示岗位前后对比）。
  - **「改绑定…」**：有主选候选时可点（`variant="ghost"`、`size="sm"`，与 profile 表里的写入口同款）；没有候选时渲染成**禁用**的 `DisabledAction`，原因句与下一步写在 `src/writes/` 里。
  - **成功之后**：`useWriteFlow` 的重读兑现后调 `reload`（由 `RolesView` → `HubPosts` → `useWriteFlow(reload)` 传下去），页面重新读 hub 与 profiles。
- 边界输入：
  - `profiles` 为空数组：六行的「改绑定…」都禁用（没有候选）；「恢复缺省…」按来源照旧。
  - 某个岗位的 `allowed_adapters` 里没有任何 profile 的适配器（桩里是 `planner`）：该行「改绑定…」禁用，其余行照旧。
  - 现有主绑定不在候选里（桩里 `contract` 的 `quizs-m3` 不在 `desktop/web/src/mock/profiles.json` 里）：预填落到第一个候选。
  - 现有替补不在替补候选里：预填为空（不选替补）。
  - 替补候选为空（主选不是 quizs，或没有非 quizs 的候选）：替补下拉禁用，只有一项「不设替补」。
  - hub 读失败：整组照旧**不渲染表格行、不渲染任何按钮**（`page-hub.test.tsx:176` 的断言照旧）。
  - 对话框关着时：表单的字段、候选、提示一律不渲染（页面上只有那六个入口按钮）。
- 错误与重试：
  - 预览失败（服务没回应、非 200、信封 `ok` 为假）：底部显示错误原文（`预览失败：服务没有回应` 或信封 `messages` 原文），`[确认…]` 不可点；不重试。
  - 写流程失败（409/5xx/超时/拒绝）：照既有 `useWriteFlow` 与 `WriteConfirmDialog` 的分支显示，**不加新分支、不改文案**；表单对话框已经关了，重开还是上次的值（由表单自己的 state 决定）。
  - 预览里的 `hub_changes`/`running_turns` 缺键或形状不对：`useLivePreview` 按空数组处理，不抛错。
- 并发、取消与状态变化：不适用——本片不加并发；表单一次只开一个（点入口开、关掉即丢弃未确认的取值）；`useWriteFlow` 的轮询、计时器与卸载清理照旧（一个字节不改）。
- 兼容性：
  - `roles-logic.ts` 的三个既有导出（`hubPostName`、`allowedProfiles`、`normalizeHubPost`）签名与行为不变，只**新增**一个导出 `hubFallbackCandidates`；该文件仍然只 `import type`。
  - `useLivePreview.ts` 只**加**两个字段（`hubChanges: HubChange[]`、`runningTurns: string[]`），既有五个字段语义不变；开头两行注释、`const DEBOUNCE_MS = 300;`、防抖与序号丢弃逻辑一个不动；既有调用方（`ProfileForm`、`RuntimeForm`）不受影响。
  - `HubPosts` 的 props 新增 `profiles` 与 `reload`（都可空：`profiles` 缺省空数组、`reload` 缺省 `undefined`）；`RolesView` 传 `profiles={data.profiles.profiles}` 与 `reload={reload}`；T038 的 S05 只要求 `<HubPosts hub={data.hub}` 开头，照旧满足。
  - 前六个列头一字不改，新增的第七列头是「操作」。
  - 两个按钮的 **textContent 必须恰为「改绑定…」与「恢复缺省…」**（U+2026 的省略号）；**按钮里不许放岗位名**（含视觉隐藏的 span）；可访问名称沿用既有机制（`DisabledAction` 的 tooltip 提示），本片不给按钮加 `aria-label`（`DisabledAction` 不接受该 prop）。
  - 页面文字里不出现 `desktop/web/src/mock/profiles.json` 里档位为 low 的那条 profile 的 id（`step-low`）：对话框关着时不渲染候选，tooltip 与原因句里也不列候选 id。
  - `desktop/web/src/mock` 仍恰 14 份 JSON；`desktop/web/src/pages` 顶层仍恰 9 个 `*Page.tsx`；`package.json` 与锁文件不变。
  - **`tests/test_gate_t024_baseline.py` 的这一处放宽由执行端在候选里做**（站主 2026-11-16 拍板）：只把「角色页禁用按钮」的计数期望从 6 抬到 11（`:1106` 的 `.toBe(6)` → `.toBe(11)`，附带的说明串与 `:1088` 的 it 标题、`:1609` 的 docstring 里的同一个数一起改，逐字见 Steps 第 8 步）。这对应本片新增的 5 个禁用入口（planner 没有候选 → 「改绑定…」禁用 1 个；coordinator、planner、gate、audit 四个缺省行 → 「恢复缺省…」禁用 4 个）；**不放宽任何行为断言**（该文件里其余的断言、夹具、探针与说明一个字都不动），**不给产品行为留余地**（不许把禁用入口藏起来、不许把缺省行的「恢复缺省…」改成可点）。R01 的期望退出码仍是 0，改完这一处 T024 应全绿。
  - **执行端口径约束**：桩下角色页禁用数若**实测不是 11**，不许改产品行为或藏按钮/改禁用态去凑数，也不许改别的数字凑数；把实测值与逐项构成照实写进执行报告的 `contract_conflicts`（同时在 `interpretations` 里写清实测值与差异），交战后门禁与终审裁定。放宽那三处时以合同给的**新文逐字**为准（不要顺手改同文件里的其他说明文字，包括文件头 `:43` 的那句「角色页禁用数 6」——它不在授权范围内，是说明文字、不是断言）。
- **写法钉死**（门禁按源码文本查这几处，逐字照抄）：
  1. `desktop/web/src/pages/readonly1/roles-logic.ts`：新导出写成 `export function hubFallbackCandidates(`，函数体里要有 `allowedProfiles(` 与一个 `'quizs'` 的字面量比较；该文件只 `import type`。
  2. `desktop/web/src/writes/useLivePreview.ts`：`LivePreview` 接口里加 `hubChanges: HubChange[]` 与 `runningTurns: string[]`（各占一行、行首是字段名）；`import` 那行扩成含 `type HubChange`；`fromReply` 里写 `hubChanges: data?.hub_changes ?? []` 与 `runningTurns: data?.running_turns ?? []`；`useEffect` 里那个失败分支的字面量也要给 `hubChanges: []`、`runningTurns: []`；开头两行注释与 `const DEBOUNCE_MS = 300;` 一字不动。
  3. `desktop/web/src/writes/HubBindForm.tsx`：`import type { ... } from '../api';` 只引类型（`HubChange`、`ProfilesData`、`WriteArgs` 等）；`import { hubChangeLines } from './hubChangeLines';`；`import './hub-bind-form.css';`（样式表放在组件 import 之后）；导出 `HubBindAction` 与 `HubUnsetAction` 两个组件，以及两个禁用原因句常量（逐字见 Behavior contract）。
  4. `desktop/web/src/pages/readonly1/roles-HubPosts.tsx`：第七列的 key 与 header 都写 `操作`（照 profile 表的写法）；`Section title="七端岗位"`、`aria-label="七端岗位"`、`rowHeight={40}`、`rl-hub`、`hubPostName`、`rowAttrs` 给的 `data-post` 一个都不许丢；**不出现** `data-role`；`<WriteFlow flow={flow} />` 只在读成功的分支里渲染。
  5. `desktop/web/src/pages/readonly1/roles-RolesView.tsx`：`<HubPosts hub={data.hub} profiles={data.profiles.profiles} reload={reload} />`（位置不动）；从 `'../../api'` 只 `import type`。
  6. `desktop/web/src/writes/hub-bind-form.css`：只用 `--tt-*` 令牌、不声明令牌、不写死颜色；px 尽量不写（要写只能写 `0` 或 `1px`，其余按仓库规矩在同行写出处注释）；类名一律 `hb-` 前缀。
  7. `desktop/web/tests/page-hub.test.tsx`：列头断言改成七列（末尾是「操作」），`it()` 标题跟着改；**`describe('七端岗位（桩模式渲染 #/roles）')` 的 describe 标题不动**。
  8. `desktop/web/tests/page-app.test.tsx`：角色页禁用数 `6` 改成 `11`，`it()` 标题跟着改；**`describe('写入口个数（过渡）')` 的 describe 标题不动**（T037 S06 要认它）。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件**（只读；基线上还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/pages/readonly1/roles-logic.ts`**：加一个导出 `hubFallbackCandidates(profiles, allowedAdapters, mainProfileId)`（签名与算法照 Behavior contract 与「写法钉死」第 1 条）；三个既有导出一字不动；只 `import type`。
3. **`desktop/web/src/writes/useLivePreview.ts`**：只加 `hubChanges` 与 `runningTurns` 两个字段（「写法钉死」第 2 条）；防抖、序号、开头两行注释、`DEBOUNCE_MS = 300` 一个不动。
4. **新建 `desktop/web/src/writes/HubBindForm.tsx` 与 `desktop/web/src/writes/hub-bind-form.css`**（照 `RuntimeForm.tsx` 的写法）：
   - 表单对话框：主选 `Select`（标签「主绑定」，选项是主选候选）、替补 `Select`（标签「替补」，第一项是「不设替补」（值为空串），其余是替补候选；替补候选为空时整个下拉 `disabled`）；底部按 Behavior contract 显示命令、前后对比（复用 `hubChangeLines`）、warnings、running_turns、错误原文；`[确认…]` 的门控与「先关表单再 start」的次序照 Behavior contract；`<WriteFlow flow={flow} />` 放在表单里。
   - 预填与切换主选时替补清空的规则照 Behavior contract。
   - 入口组件 `HubBindAction`：有候选时是可点的「改绑定…」（`ghost`/`sm`）并打开表单；没有候选时是 `DisabledAction`（`label="改绑定…"`、`variant="ghost"`、`size="sm"`、`reason` 是常量）。
   - 入口组件 `HubUnsetAction`：来源是配置时可点的「恢复缺省…」（`ghost`/`sm`），点它调 `onStart({ action: 'hub.unset', args: { post } })`；否则是 `DisabledAction`（`label="恢复缺省…"`、`variant="ghost"`、`size="sm"`、`reason` 是常量）。
   - 两个禁用原因句常量（逐字）：
     - 改绑定没有候选：`没有能用在这个岗位的 profile：先在「CLI 运行时」页登记运行时，再新建 profile`
     - 恢复缺省不可用：`这个岗位现在用的是内核缺省，没有要恢复的配置`
   - 岗位中文名由入口文件算好当 prop 传进来（`src/writes` 不跨层引 `src/pages`）；对话框标题由本文件拼：`改绑定：<岗位中文名>`。
5. **`desktop/web/src/pages/readonly1/roles-HubPosts.tsx`**：加第七列「操作」与 props `profiles`、`reload`；组内一个 `useWriteFlow(reload)`（照 `roles-ProfilesTable.tsx`）；「操作」格里放 `<HubBindAction …>` 与 `<HubUnsetAction …>`（两个组件都在 `src/writes/` 里，入口文件不写逐字句子）；读成功的分支里放 `<WriteFlow flow={flow} />`；读失败的分支照旧零按钮；T038 S10 的静态形状一个不少。
6. **`desktop/web/src/pages/readonly1/roles-RolesView.tsx`**：改成 `<HubPosts hub={data.hub} profiles={data.profiles.profiles} reload={reload} />`（位置不动）。
7. **改两处包内测试**（只改这两处断言与标题，不动别的）：
   - `desktop/web/tests/page-hub.test.tsx`：列头断言改七列（末尾「操作」）、`it()` 标题跟着改；**再补一条**用例：操作列里每行有两个按钮，textContent 恰是「改绑定…」与「恢复缺省…」；`planner` 行的「改绑定…」是禁用的；`contract` 与 `exec` 行的「恢复缺省…」可点、其余四行禁用；读失败分支零按钮的既有断言照旧。
   - `desktop/web/tests/page-app.test.tsx`：角色页禁用数 `6` 改 `11`、`it()` 标题跟着改；**`describe('写入口个数（过渡）')` 的标题不动**；运行时页 5 与总览页 0 照旧。
8. **`tests/test_gate_t024_baseline.py`（站主 2026-11-16 拍板：这一处放宽由执行端在候选里做；只许改下面三处，该文件其余内容一个字不动）**：
   - `:1088` 的 `it()` 标题——把标题末尾的「角色页禁用数 6」改成「角色页禁用数 11」：
     ```ts
     it('两个入口的样式与仍在禁用的入口：页头次序照旧、[新建 profile] secondary/md 可点；4 张角色卡的 [更改…] 仍禁用；角色页禁用数 11', async () => {
     ```
   - `:1105-1106`——`:1105` 的 `const disabledCount = buttons(pageFrame()).filter((b) => b.disabled).length;` **不动**；`:1106` 改成：
     ```ts
         expect(disabledCount, '角色页禁用按钮 9→6→11（T045 新增 5 个禁用入口；page-app 的口径）').toBe(11);
     ```
   - `:1609` 的 docstring——把「（角色页禁用数 6）」改成「（角色页禁用数 11）」，这一行改成：
     ```text
         对话框关着时页里不渲染任何按钮、两个入口的样式与仍在禁用的入口（角色页禁用数 11）、offline 照旧可点。"""
     ```
   - **这个文件里的其余一切都不许动**：别的断言、别的 `it()` 标题、别的 docstring、夹具、探针、文件头说明（`:43` 的「角色页禁用数 6」是说明文字，**不在**授权范围内，保持原样）。改完在执行报告里写清：这个文件的改动只有一个 hunk（三处），没有别的改动。
   - 改完之后跑 T024 单文件（`python -m pytest tests/test_gate_t024_baseline.py -q`，cwd 仓库根），把结果记进执行报告。
9. **新增两个测试文件**（都不许 `skip`/`only`/`todo`）：
   - `desktop/web/tests/roles-hub-candidates.test.ts`：`hubFallbackCandidates` 的边界——主选是 quizs 时候选是允许名单去掉 quizs 的那几个；主选不是 quizs（pi）时为空；主选查不到时为空；主选的 adapter 不是字符串时为空；允许名单为空时为空；候选里不含 quizs、不出允许名单；`allowedProfiles` 与 `hubPostName` 的既有行为没变（各点一条即可）。
   - `desktop/web/tests/writes-hub-bind.test.tsx`：入口与表单的组件测试——
     - 两个按钮的 textContent 恰是「改绑定…」「恢复缺省…」；没有候选时「改绑定…」禁用、悬停出原因句；缺省行的「恢复缺省…」禁用、悬停出原因句；配置行的「恢复缺省…」可点。
     - 表单：主选候选项只有允许名单里的 profile；主选是 quizs 时替补候选项里没有 quizs；主选不是 quizs 时替补下拉禁用；配置行预填现有主选与替补（现有主绑定不在候选里时落第一个候选）；改主选为非 quizs 时替补清空。
     - 底部：命令（去掉 `--dry-run`/`--json`）、前后对比四行（与 `hubChangeLines` 的输出一致）、warnings、running_turns、报错原文。
     - 真实模式（`setLiveClientForTests` 注入假客户端）：确认后发 `POST /api/v1/hub/roles/<post>`，正文带 `profile`，只有选了替补才带 `fallback`；「恢复缺省…」走 `POST /api/v1/hub/roles/<post>/unset`；成功之后 reload（页面重新读了 hub）。
     - `useLivePreview` 的两个新字段：预览的 `hub_changes`/`running_turns` 原样出现在结果里。
     - **桩下角色页禁用按钮的实测值**：在 `#/roles`（桩模式）数一遍整页的 `button[disabled]`，断言它是 11，并把这 11 个的构成写进测试注释（页头「保存当前为方案…」1 个 + 4 张角色卡的「更改…」+ 方案条的「切换…」= 6；planner 的「改绑定…」1 个；coordinator、planner、gate、audit 的「恢复缺省…」4 个）。**若实测不是 11**：不要改产品行为、不要改这个断言去迁就实现，照实写进执行报告的 `contract_conflicts`（并写清实测值与逐项构成），交战后门禁与终审裁定。
10. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → R01**（本 worktree 里若没有 `node_modules`，先在 `desktop/web` 跑一次 `npm ci --no-audit --no-fund`），记录命令与结果。R01 的墙钟实测可能逼近 1800 秒上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
11. 写执行报告；遇到合同未定义的行为（例如服务回的字段形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t045_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t049_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：`hubFallbackCandidates` 是纯函数：主选适配器是 quizs 时返回允许名单去掉 quizs 的候选，否则返回空数组；`allowedProfiles`、`hubPostName`、`normalizeHubPost` 三个既有导出与行为不变；`roles-logic.ts` 仍只 `import type`；目的：替补的资格是内核的硬规则（`scripts/kit_roles.py:331-333`），界面上先挡住比让内核拒绝好；证据：V01、V02、R01、scope
- D02：`useLivePreview` 只多两个字段（`hubChanges`、`runningTurns`），预览带这两个字段时原样出现在结果里；开头两行注释、`DEBOUNCE_MS = 300`、防抖与序号丢弃逻辑一字未改；T040 的预览探针照旧通过；目的：表单底部要显示前后对比与在跑的回合，但不能碰既有预览的时序；证据：V01、R01、review
- D03：表单按 Behavior contract 筛候选与预填（配置行预填现有主选与替补；现有主绑定不在候选里时落第一个候选；主选改成非 quizs 时替补清空并禁用）；写参数是 `{ post, profile }`，替补非空才带 `fallback`；目的：`hub set` 整条替换绑定，不预填就会把用户原来的替补悄悄清掉；证据：V01
- D04：表单底部显示命令、这个岗位的前后对比（**复用 A 片的 `hubChangeLines`**）、warnings、running_turns、错误原文；`[确认…]` 的门控是「主选非空 + 预览对应当前取值 + 预览 ok」，点它先关表单再 `start({action:'hub.set', args})`；目的：用户要在确认之前看见这次绑定改成了什么、会不会撞上同一个模型；证据：V01、G01
- D05：「七端岗位」一组加第七列「操作」，每行两个入口：textContent 恰是「改绑定…」与「恢复缺省…」；没有候选时「改绑定…」禁用并有原因句；缺省行的「恢复缺省…」禁用并有原因句，配置行可点；按钮里没有岗位名；读失败分支整组照旧零按钮；目的：这是本页唯一的写入口，白名单按 textContent 匹配，多一个字就撞 T009 D11；证据：V01、G01、R01
- D06：确认与执行走既有写流程：`hub.set` 发 `POST /api/v1/hub/roles/<post>`（正文带 `profile`，选了替补才带 `fallback`）、`hub.unset` 发 `POST /api/v1/hub/roles/<post>/unset`；确认框显示岗位前后对比与标题/摘要/轻提示（A 片既有文案）；成功之后页面 reload（hub 与 profiles 一起刷新）；目的：这一片只是入口与表单，写流程的语义一个字都不许另造；证据：V01、G01
- D07：两处包内测试照新行为改（`page-hub.test.tsx` 的列头变七列、`page-app.test.tsx` 的角色页禁用数变 11），两处 `it()` 标题跟着改，两个 `describe` 标题（`七端岗位（桩模式渲染 #/roles）` 与 `写入口个数（过渡）`）**一个字都不动**；既有断言没被删、跳过或弱化；目的：T037 S06 要认那个 describe 标题；证据：V01、R01、review
- D08：新增两个测试文件（纯函数一个、组件一个），覆盖 D01–D06 点名的每一项（含桩下禁用按钮的实测值 11 与它的构成）；不用 `skip`/`only`/`todo`；测试测真实实现（不把业务逻辑抄一份进测试）；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、review
- D09：所有修改都在允许集合内（**可改 7 个文件**——6 个前端文件 + `tests/test_gate_t024_baseline.py` 的三处放宽；可新增 4 个文件），没有碰 forbidden_paths（除 t024 外的全部 `tests/test_gate_*.py`（含 `tests/test_gate_t045_*.py`）、`api.ts`、`useWriteFlow.ts`、`WriteConfirmDialog.tsx`、`hubChangeLines.ts`、`mock/**`、`roles-styles.css`、`roles-hub-logic.test.ts`、`ts/packages/ui/**`、`scripts/**`）；`package.json` 与锁文件不变；目的：这一片不许顺手改别的片的地盘；证据：scope、review
- D10：新代码守既有源码规矩：`HubBindForm.tsx` 只 `import type` 引 `../api`、不碰 DOM 与时钟、不出现网络词与危险 HTML 写入类词；`hub-bind-form.css` 只用 `--tt-*` 令牌、不写死颜色、不声明令牌；`roles-*` 三个文件不出现网络词、T007 禁用词、`role="status"`、内联 style；`desktop/web/src` 下不渲染 `role=status`；目的：不破 T006/T009/T013/T038 的长期门禁；证据：V01、V03、R01、review
- D11：T038 S10/S11/S07 的静态形状保住（`title="七端岗位"`、`aria-label="七端岗位"`、`rowHeight={40}`、`rl-hub`、`hubPostName`、不出现 `data-role`；前六个列头不变；`roles-logic.ts` 三个导出不动、只许 `import type`）；站主已合入的三处放宽在新基线上照旧有效（T038 的 trans 探针已退役、S05 只要求 `<HubPosts hub={data.hub}` 开头、T009 D11 白名单含两个按钮）；目的：这一片是在 T038 的形状上加一列，不是重画这一组；证据：R01、G01
- D12：**执行端在候选里做 T024 的这一处放宽**：`tests/test_gate_t024_baseline.py` 只改三处（`:1088` 的 it 标题、`:1106` 的期望值与附带说明串、`:1609` 的 docstring，把「角色页禁用按钮」的计数期望从 6 抬到 11），该文件其余内容一个字不动（改动只有一个 hunk）；R01 因此全绿（期望退出码 0 不变）；这一处只抬计数期望，**不放宽任何行为断言、不给产品行为留余地**（不许把禁用入口藏起来、不许把缺省行的「恢复缺省…」改成可点）；若桩下实测的禁用数不是 11，**不许改产品行为或别的数字去凑数**，照实写进执行报告的 `contract_conflicts`（并写清实测值与逐项构成），交战后门禁与终审裁定；由谁改、怎么改，站内已经拍板（2026-11-16：同一份门禁文件的同一处断言由执行端在候选里放宽）；目的：本片必然把角色页禁用数从 6 变成 11，这条门禁断言必须跟着更新，否则任何合规实现都过不了 R01；证据：R01、scope、review

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `api.ts` 里没有 `hub_changes`/`running_turns`、`hubChangeLines.ts` 不存在或没有导出 `hubChangeLines`、`useWriteFlow` 的 confirm 没有 `hub.set`/`hub.unset` 分支、`roles-logic.ts` 没有 `allowedProfiles`），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `api.ts`、`useWriteFlow.ts`、`WriteConfirmDialog.tsx`、`hubChangeLines.ts`、`mock/**`、`roles-styles.css`、`ts/packages/ui`、`scripts/`、t024 以外的任何门禁测试文件、`roles-hub-logic.test.ts`）。
- `tests/test_gate_t024_baseline.py` 的那三处在工作目录里**已经不是**合同写的样子（例如行号变了、那三处不再是描述「角色页禁用数」的地方、或者已经被别的改动放宽成 11）：停下并报告，不要顺手改别的断言或探针来"对上"。
- 门禁端交付的本片门禁基准测试文件与本合同的「写法钉死」一节出现实质冲突（例如它要求的前后对比函数名与本合同给的不一致）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在本片显示岗位「拿到了什么」、要做凭据录入、或要在缺省行把「恢复缺省…」做成可点）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t045-desktop-web-hub-bind-entry` 汇总，含返工版本；本 task-id 累计已用 0 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（按 task-id 跨版本累计；累计已用 0 秒 = 3 × 5400）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 15 分钟；实现（roles-logic 纯函数、useLivePreview 两个字段、HubBindForm + CSS、操作列与 prop、两处包内测试）45 分钟；T024 三处放宽 5 分钟；补测（两个新测试文件）20 分钟；必要检查（G01、V01、V02、V03、R01，R01 约 27 分钟、可分批跑）25 分钟；最终报告 5 分钟；总计约 115 分钟，单轮时限 5400 秒（90 分钟）——总量 16200 秒覆盖本版与两次返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261115T052904844555Z-owner-dd2f67：

> 站主答复（2026-11-15）：
> 1. 门禁准备已合入主分支 themis-3.0，提交 c0f3ac81（快进，父提交 c2fad267）。只改了两份门禁文件，三条都做了：
>    ① T038：PROBE_TRANS、它在 PROBE_SPECS 里的条目、PROBE_ORDER 里的 "trans" 都删了；test_transitional_probe_no_write_entries 退役，原位留一行注释写明为 T045 退役。
>    ② T038 test_s05_rolesview_hub：RolesView 只要求含 `<HubPosts hub={data.hub}` 开头（原来逐字钉 `<HubPosts hub={data.hub} />`），B 片可以加 profiles、reload 等 prop。
>    ③ T009 test_d11_probe_write_entries_disabled：角色页可用按钮白名单加了“改绑定…”“恢复缺省…”。
>    合入前站主单跑过：T038 17 条过，T009 16 条过。三条都是放宽，现有代码照样过。合入之后 hub 照例在新末端跑全量门禁回归，结果有问题站主再写信。
> 2. 合同端照你说的等 T044 结项、内核挪基线、写信通知之后再开。A1–A3 在新基线上由合同端核对，这样安排认可。
> 3. 文件边界：T042（本机服务的 Quizs 读路由）→ T043（CLI 运行时页的 Quizs 一块）→ T044（A 片）→ T045，全靠 --after 串行，T045 的合同基线会带上前三片已合入的改动，没有并行冲突。你列的允许修改范围认可：roles-logic.ts、roles-HubPosts.tsx、roles-RolesView.tsx、writes/useLivePreview.ts、page-hub.test.tsx、page-app.test.tsx，新文件 writes/HubBindForm.tsx（加新的 CSS 与测试）；roles-styles.css 默认不改，useLivePreview.ts 开头两行不动。T044 如果改到了 useLivePreview.ts，合同端以新基线的实际内容为准。
> 4. 照站主上一次的决定：替补照内核 kit_roles.py:316 的筛法（主选是 quizs 才能选替补，替补候选里去掉 quizs）；page-app.test.tsx:91 与 page-hub.test.tsx:84 两处包内测试照新行为改，describe 标题不动。

站主来信 20261116T074547419914Z-owner-0912f4：

> 站主决定（2026-11-16，回 20261116T074407582232Z-womovie-c8-189014）：A、B 都不走，照 T044 昨天的先例（t022 那一处放宽）出合同 v2。
> 1. 合同端返工出 v2：把 `tests/test_gate_t024_baseline.py` 加进 allowed_modified_files，只许改这一处断言与它的文字：`:1105-1106` 的 `expect(disabledCount, '角色页禁用按钮 9→6（page-app 的口径）').toBe(6)` 期望 6 改 11，说明补成「9→6→11（T045 新增 5 个禁用入口）」；`:1088` 的 it 标题「角色页禁用数 6」改 11；`:1609` 附近的 docstring 若写着这个数照改。别的断言、夹具与说明一个字不动。D12 改写成：执行端在候选里做这一处放宽，R01 照跑、应全绿；「兼容性」一节补上这条。
> 2. 不走 A 的原因（站主核过）：合同端开工之后内核不再挪本任务的基线（task rebase 拒绝），站主合到 themis-3.0 的放宽到不了本片的 R01（R01 在本片基线 5407feb89b 上跑）；内核也不许门禁端的基准提交带别的文件。B 会白耗一次 attempt。
> 3. 门禁端的 `tests/test_gate_t045_baseline.py` 与它在基线上「13 红 1 绿」的结论不受影响；v2 之后照内核的次序走（门禁照原样重交、JEV、一审），一审照常开工。
> 4. 执行端实际做出的禁用数若不是 11，不许为凑数改产品行为（藏入口、改禁用态）：照实写进报告的 interpretations 或 contract_conflicts，交战后门禁与终审裁定。
