# TASK: t044-desktop-web-hub-bind

## Identity
- plan_version: 3
- repository: ThemisTally
- base_sha: 3a486c4330cdb1dccae70d08645ca36b31d89d3f
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
让桌面端前端的**写流程**认识七端岗位的改绑定与恢复缺省：`desktop/web/src/api.ts` 的 `PreviewData` 加 `hub_changes` 与 `running_turns`（照服务形状映射）；`src/writes/snapshots.ts` 加 `hubSnapshot`；`src/writes/useWriteFlow.ts` 让 `hub.set` / `hub.unset` 读 `getHubRoles`、执行走 `setHubRole` / `unsetHubRole`（不再误落到 `setPluginEnabled`），并把 `needs_yes` 的原因句条件放宽成「没有在跑的 attempt 且没有在跑的回合」；`src/writes/WriteConfirmDialog.tsx` 在「变化」一节按岗位显示前后对比、在「影响与风险」一节逐行显示在跑的回合；新增纯逻辑文件 `src/writes/hubChangeLines.ts`；`src/mock/writes.ts` 给 `hub.set` / `hub.unset` 的预览按夹具算前后对比并加四个岗位情景。

## Non-goals
- **不加**「七端岗位」一组的入口与表单（不新建 `HubBindForm.tsx`、不改 `src/pages/readonly1/roles-HubPosts.tsx`、不改 `src/pages/readonly1/roles-logic.ts`、不改 `src/pages/RolesPage.tsx`）：那是站主另登记的 T045（B 片）。
- 不实现替补候选的筛法（主选是 quizs 才能选替补、替补不能是 quizs，内核规则见 `scripts/kit_roles.py:332-333`）；本片只在桩数据里体现，桩里的替补只出现在主选是 quizs 的岗位上。
- 不改 `src/writes/useLivePreview.ts`（`LivePreview` 的形状与实时预览在 B 片才扩）。
- 不改 `ts/packages/ui`、`scripts/**`、任何门禁测试（`tests/test_gate_t0*.py`）、`desktop/web/src/mock/*.json`（仍恰 14 份）、`desktop/web/src/mock/scenario.ts`、`desktop/web/src/mock/hub-roles.ts`。
- 不改 `desktop/web/tests/page-app.test.tsx`、`desktop/web/tests/page-hub.test.tsx`、`desktop/web/tests/live-api.test.ts`、`desktop/web/tests/writes-live-flow.test.tsx`、`desktop/web/tests/writes-live-preview.test.tsx`。
- 不动 T040 锁定的原因句（`有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。`）的字，只放宽它的出现条件。
- 不改既有门禁断言：T038 的 `test_transitional_probe_no_write_entries`（退役）与 `test_s05_rolesview_hub`（放宽）、T009 的 `test_d11_probe_write_entries_disabled`（白名单加两项）都由 T045 处理，本片一条都不碰。
- 不动 `src/mock/writes.ts` 里**既有**演示数据（既有 23 个情景值、既有文案里的 `step-low` 字面量、一个字节都不改）；本片只**新增**岗位桩数据。

## Repository facts
以下事实都在本回合的工作目录（基线 `185d077722609384f479a9b981fec6fc18ee8a68`）里逐条读过；行号按该基线。规划报告是在旧基线 `c2fad267` 上写的，行号有偏移（见本节末的差异表），**以本节为准**。

### 前端现状
- `desktop/web/src/api.ts`：
  - `:63-77` `WriteAction` 已含 `'hub.set'` 与 `'hub.unset'`（本片不改这个联合类型）。
  - `:94-102` `PreviewData` 现在八个字段：`binding_changes`、`resources`、`notes`、`warnings`、`running_attempts`、`needs_yes`、`command`、`confirmation`；**没有** `hub_changes` 与 `running_turns`。
  - `:278-306` `toPreviewData(preview, command, confirmation)`：`:299` `notes: [...stringsOf(preview.notes), ...stringsOf(preview.unreadable)]`（unreadable 并进 notes）；`:301` `running_attempts: stringsOf(preview.running_attempts)`；`:302` `needs_yes: preview.needs_yes === true`；`:290-297` 既有 `resources` 映射不去重；`:275-277` `displayValue` 给一条绑定的显示值（`profile` → `provider/model` → `mode` → `—`）。
  - `:143-157` `HubPostRow`（`post`、`source: 'default' | 'config'`、`allowed_adapters`、`adapter`、`provider`、`model`、`thinking`、`profile`、`runtime`、`fallback: HubPostFallback | null`）与 `HubRolesData { posts: HubPostRow[] }`；`HubPostFallback` 的 `profile` 与 `runtime` 是**可选键**（缺省行的替补只有四键）。
  - `:477-482` `getHubRoles()`：真实模式 `GET /api/v1/hub/roles`（30 秒），桩模式 `config hub show --json`。
  - `:732-747` `setHubRole(args: { post; profile; fallback? }, confirmation)`：真实模式 `POST /api/v1/hub/roles/<post>`，正文 `{ profile, fallback? , confirmation }`（`fallback` 没给就不带这个键；`writeArgs` 的空串规则照旧）。
  - `:749-757` `unsetHubRole(post, confirmation)`：真实模式 `POST /api/v1/hub/roles/<post>/unset`，正文只有 `{ confirmation }`。
- `desktop/web/src/writes/useWriteFlow.ts`：
  - `:80-90` `titleOf(action, args)`、`:92-104` `successTextOf`、`:106-134` `changeSummaryOf`——三个表都**没有** `hub.set` / `hub.unset` 的分支（`changeSummaryOf` 对这两个动作返回 `null`，确认框回落到「预览没有列出变化」）。
  - `:136-197` `readSnapshot(action, isReread)`：`preset.use`/`preset.remove`/`profile.remove`/`runtime.remove`/`runtime.add`/`config.rollback`/`profile.add`/`profile.edit` 各有分支，**其余动作**（含 `hub.set`/`hub.unset`）落到末尾的 `getPlugins()` 分支（`:194-197`）。
  - `:438-440` 原因句的条件是 `data.needs_yes === true && data.running_attempts.length === 0`；原因句原文（逐字）：`有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。`（**基线是「条件一行、原因句下一行」；本片要改成同一行，见「写法钉死」第 3 条**）。
  - `:441-449` 组 `content`：`command`（去掉 `--dry-run` 与 `--json`）、`changes: data.binding_changes`、`summary: changeSummaryOf(...) ?? undefined`、`warnings: data.warnings`、`running: data.running_attempts`、`notes`。
  - `:480-496` `confirm()` 的分支链（一条嵌套三元）：`preset.use` → `preset.remove` → `profile.remove` → `runtime.remove` → `config.rollback` → `profile.add` → `profile.edit` → `runtime.add` → **末端 `setPluginEnabled(sargs.id, …)`**（`hub.set`/`hub.unset` 现在会落到这里）。
- `desktop/web/src/writes/WriteConfirmDialog.tsx`：
  - `:9-16` `ConfirmContent`：`command`、`changes: BindingChange[]`、`summary?`、`warnings`、`running`、`notes`；**没有**岗位前后对比与在跑的回合。
  - `:78-92` `Changes({ changes, summary })`：有 `changes` 就逐行渲染 `role / from / → / to`，没有就渲染 `summary ?? '预览没有列出变化'`。
  - `:94-110` `Risks({ content })`：`hasRisk = warnings.length > 0 || running.length > 0 || notes.length > 0`；`:100-102` 把 `running` 逐行渲染成 `有 attempt 正在运行：{r}。它不受影响，但这次改动需要你确认。`；warnings 原样、notes 走 `.wf-note`。
- `desktop/web/src/writes/snapshots.ts`：既有 `presetSnapshot`/`pluginSnapshot`/`presetRemoveSnapshot`/`profileRemoveSnapshot`/`runtimeRemoveSnapshot`/`profileSnapshot`/`rollbackSnapshot` 与 `sameSnapshot`（`JSON.stringify` 比较）；排序用文件里的 `byKey`（`String(a[key]).localeCompare(String(b[key])`）；既有 `ProfileSnapshot` 用的是「interface + 嵌套对象逐字段换行」的写法（照它写）。
- `desktop/web/src/writes/writeOutcome.ts`：`:23-27` `warnLines` 扫 `output` 与 `messages` 里以 `WARN` 开头的行；`:43-48` `classifyWrite` 在 200 且 `ok` 时按 `warnLines` 的长度给 `successWarn`（→ `doneWithWarning`）。
- `desktop/web/src/writes/write-flow.css`（基线 1597 字节，只用 `--tt-*` 令牌，既有类名一律 `wf-` 前缀）：既有令牌有 `--tt-space-1..4`、`--tt-text-1/2/3`、`--tt-text-sm`、`--tt-text-caption`、`--tt-text-caption-strong`、`--tt-text-sm-medium`、`--tt-mono-md`、`--tt-radius-sm`、`--tt-surface-2`；既有类名 `.wf-content`、`.wf-section`、`.wf-label`、`.wf-changes`、`.wf-changes__empty`、`.wf-change`、`.wf-change__role`、`.wf-change__from`、`.wf-change__to`、`.wf-change__arrow`、`.wf-risk`、`.wf-note`、`.wf-warn-line`、`.wf-error`、`.wf-reason`、`.wf-partial`。
- `desktop/web/src/mock/writes.ts`：
  - `:6-29` `WriteScenario` 与 `:31-34` `SCENARIOS`（现 23 个取值：`ok`、`warn`、`exit1`…`preview-registered`）；`:36-49` `writeScenario()` 只认 hash 查询串里的 `write` 键。
  - `:39-52` `baseArgv`：`hub.set` → `['config','hub','set', post, profile]`（有 `fallback` 再加 `--fallback=<id>`）；`hub.unset` → `['config','hub','unset', post]`。
  - `:124-200` `previewData(action, args, confirmation)`：**共 6 处返回的 `PreviewData` 字面量**（`:128` preset.use、`:141` config.rollback、`:154` profile.add/edit、`:167` runtime.add、`:180` hub.set/unset、`:192` 三个删除与插件启停的兜底），每一处都要补 `hub_changes` 与 `running_turns` 两个字段；`:178-190` 的 `hub.set`/`hub.unset` 分支是**空壳**（`binding_changes: []`、`resources: ['hub']`、`running_attempts: []`、`needs_yes: false`）。
  - 既有演示文案里的 `step-low` 共 6 处（`:129`、`:142` 的 `binding_changes`，`:256` 的 in-use 文案，`:258`、`:283`、`:290` 的错误文案）——**本片一个字都不改**。
  - `:203-…` `mockPreview`：`preview-warn` 情景给 `data.warnings` 注入一行 WARN。
- `desktop/web/src/mock/hub-roles.ts`：六行名册（`coordinator`/`planner`/`contract`/`gate`/`audit`/`exec`），`contract` 与 `exec` 两行 `source: 'config'`（其余四行 `source: 'default'`）；`contract` 行：主绑定 `profile: 'quizs-m3'`、`runtime: 'quizs'`、`adapter: 'quizs'`、`provider: 'minimax'`、`model: 'MiniMax-M3.1-Flash'`、`thinking: 'high'`，替补 `{ profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }`；`exec` 行：主绑定 `profile: 'step-high'`、`runtime: 'pi'`、`adapter: 'pi'`、`provider: 'bb'`、`model: 'step-5-preview'`、`thinking: 'high'`，替补 `null`。
- `desktop/web/src/mock/profiles.json`：两条 profile（`step-high`、`step-low`），每行有 `id`、`runtime`、`adapter`、`provider`、`model`、`options.thinking`、`credential_env`。
- `desktop/web/tsconfig.json`：`include` 只有 `["src","vite.config.ts"]`（`tests/` 不过 `tsc --noEmit`，但**运行时**会读到新增字段）；`resolveJsonModule: true`，JSON 导入照 `src/api.ts:5-15` 的现成写法（`import profilesJson from './profiles.json';`）。
- `desktop/web/src/pages/readonly1/roles-logic.ts`：`hubPostName(code)` 给六个岗位中文名（协调人/规划端/合同端/门禁端/审核端/执行端，未知码原样）；`allowedProfiles`；`normalizeHubPost`。T038 的 `test_s07_roles_logic_pure_fns` 钉住这三个导出与「只 `import type`」，**本片不改这个文件**（`src/writes/` 也不跨层引 `src/pages/`，见 Steps 第 5 步的决定）。
- `desktop/web/tests/`：
  - `live-api.test.ts:275-291` 是 T037 的预览映射断言（逐字段 `toEqual`）——**本片不改这个文件**，加字段不影响它。
  - `writes-live-flow.test.tsx:383-408` 是 T040 的三种情形：① `unreadable` 有值 → 原因句逐字排在 notes 第一条；② `running_attempts` 有值 → 不出原因句、`.wf-note` 为 0；③ `needs_yes` 为假 → 不出原因句、也没有「影响与风险」。
  - `writes-flow.test.tsx:120-140` 自己造了一份预览 `data`（含既有八字段，**没有** `hub_changes`/`running_turns`）——**第一处要补的夹具**。
  - `writes-profile-form.test.tsx:385` 的 `pvEnv()` 也自己造了一份同样的预览 `data`——**第二处要补的夹具**。
  - `writes-dialog.test.tsx:31` 的 `CONTENT`（`ConfirmContent` 类型）只有 `command`/`changes`/`warnings`/`running`/`notes`——**第三处要补的夹具**（本版新增；上一版漏了它，确认框读 `content.runningTurns.length` 时会抛 `undefined.length`）。
- 门禁文件（**只读参考**）：`tests/test_gate_t044_baseline.py` 是门禁端写的验收文件（内核会把它做成基线提交；执行端**只许读、不许改**）。它对写法有几处硬要求（`export interface` 与字段行首、原因句与条件同一行、`action === 'hub.set' || action === 'hub.unset'` 的写法、`hubChanges: data.hub_changes` 的字面、CSS 三条选择器各自独立等），本合同的「写法钉死」一节已经把同一批要求写死——**开工前先读它一遍**（见 Steps 第 1 步），两边口径不一致时以本合同的「写法钉死」为准，并写进执行报告。
- 工具链：`desktop/web` 用 npm（`npm test` = `vitest run`，`npm run typecheck` = `tsc --noEmit`，`npm run build` = `tsc --noEmit && vite build`）；仓库门禁用 `python -m pytest`。本片不改任何依赖清单与锁文件。

### 服务与内核（只读引用，本片不改）
- 预览 JSON 的形状：`scripts/kit_config.py:1740-1761` 的 `run_in_write_mode` 在 `--dry-run --json` 下把 handler 的 stdout 收进 `text`；`:1764-1779` 的 `_preview_payload` 给出 `hub_changes`、`running_turns`、`unreadable`、`needs_yes = bool(running or turns or unreadable)`、`warnings`（取 `text` 里以 `WARN  ` 开头的行、去掉前缀）、`notes`。
- 岗位前后：`scripts/kit_roles.py:424-433` 的 `hub_side` 给出 `source`（`default`/`config`）+ 六个字段（`profile`、`runtime`、`adapter`、`provider`、`model`、`thinking`）+ `fallback`（同六个字段或 `None`）；`:436-444` 的 `hub_changes` 给出前后不同的岗位各一项 `{post, before, after}`。
- 内核缺省：`scripts/kit_roles.py:82-90` 的 `HUB_DEFAULTS`：`coordinator`（adapter quizs / provider deepseek / model deepseek-flash / thinking high / fallback {adapter pi, provider dsf, model deepseek-flash, thinking high}）、`planner`（claude-code / null / claude-opus-5-5 / max / 无）、`contract`（pi / minimax / MiniMax-M3.1-Flash / high / 无）、`gate`（pi / cc-switch-zhipu-glm / glm-5.3 / high / 无）、`audit`（pi / minimax / MiniMax-M3.1-Flash / max / 无）、`exec`（pi / cc-switch-step-fun / step-5-preview / high / 无）。
- 写动作：`scripts/kit_roles.py:1340-1356` 的 `_hub_set`（**整条替换**：`hub_roles[post] = {profile}`，只有传了 `--fallback` 才带替补，所以不传替补就清掉原来的替补）；`:1359-1375` 的 `_hub_unset`。
- 同模型警告：`scripts/kit_roles.py:1330-1337` 的 `_hub_warnings`——只在改的是 `contract` 或 `audit`、且这两个岗位的 `(provider, model)` 相同时报 `合同端与审核端用的是同一个模型（%s/%s）：审核少一层独立性；照样生效`；`_hub_set` 与 `_hub_unset` 都把它打成 `WARN  …` 行。
- 替补规则：`scripts/kit_roles.py:332-333`——`fallback` 只用于主选适配器是 `quizs` 的岗位，替补自己不能是 `quizs`。
- 在跑的回合：`scripts/kit_roles.py` 的 `hub_running_turns`（每个有回合在跑的岗位一句，形如 `审核端（audit）：2 个回合在跑`；执行端不算）。
- 服务端白名单：`ts/packages/ui/src/redaction.ts:201-232` 的 `PREVIEW_ALLOW` 放行 `hub_changes.*.post`、两侧的 `source`/`profile`/`runtime`/`adapter`/`provider`/`model`/`thinking`、两侧 `fallback` 的同样六个字段，以及 `running_turns[*]`；`ts/packages/ui/test/redaction.test.ts:130-158` 钉住了这个形状。

### 规划报告 H1–H6 的核实结论
- **H1 成立**：前端夹具 `src/mock/profiles.json` 每行都带 `adapter`；`roles-logic.ts` 的 `allowedProfiles` 按 `adapter` 筛（T038 已落地且被 `test_s07_roles_logic_pure_fns` 与 T038 的 lib 探针钉住）。本片只在**桩**里从 `profiles.json` 取 `adapter`/`runtime`/`provider`/`model`/`options.thinking` 算 after 侧。
- **H2 成立**：`scripts/kit_config.py:1740-1779`（dry-run 预览收 stdout、`WARN  ` 行去前缀进 `warnings`）+ `scripts/kit_roles.py:1340-1356`（`_hub_set` 打印 `WARN  <同模型警告>`）。所以 `hub.set` 的预览 `warnings` 里确实有同模型警告。
- **H3 成立**：`writes/writeOutcome.ts:23-27` 的 `warnLines` 与 `:43-48` 的 `classifyWrite`——执行输出里的 `WARN` 行被判成 `successWarn`，走 `doneWithWarning`。
- **H4 不属本片**：`DisabledAction` 能否带自定义 tooltip 是 B 片「改绑定…」禁用按钮的事。
- **H5 不撞**（站主 2026-11-15 已核）：T009 的 `TRANS2` 只核夹具里的值、不数角色页按钮；`TRANS3` 只钉总览页 0 个禁用按钮。本片不改角色页、不加任何按钮。
- **H6 已核**：`api.ts` 的 `PreviewData` 仍没有 `hub_changes`/`running_turns`；`tests/test_gate_t009_baseline.py` 的 `ALLOWED_API_READS` 已含 `getHubRoles`；`tests/test_gate_t038_baseline.py` 的 `api_exports_problems` 只要求「既有导出齐全 + 本片新导出在位」，**多导出不红**（本片新增的三个类型导出安全）。

### 与规划报告（旧基线 c2fad267）的行号差异
| 东西 | 规划报告写的 | 新基线（185d077722） |
|---|---|---|
| `api.ts` `PreviewData` | :93-102 | :94-102 |
| `api.ts` `toPreviewData` | :245-273 | :278-306 |
| `api.ts` `setHubRole`/`unsetHubRole` | :684-711 | :732-757 |
| `useWriteFlow.ts` `titleOf`/`successTextOf`/`changeSummaryOf` | :74 / :92 / :108 | :80 / :92 / :106 |
| `useWriteFlow.ts` `readSnapshot` | :191 附近 | :136 起（`:194-197` 是落到的 getPlugins 分支） |
| `useWriteFlow.ts` 原因句条件 | :438 | :438（一致） |
| `useWriteFlow.ts` confirm 分支链末端 | :497 | :480（分支链起点） |
| `mock/writes.ts` hub 空壳 | :178-190 | :178-190（一致） |
| 内核替补规则 | `kit_roles.py:316` | `kit_roles.py:332-333` |
| 内核 hub set 整条替换 | `kit_roles.py:1288-1296` | `kit_roles.py:1340-1356` |

导出名、函数签名、既有文案一个没变；上表只是行号偏移。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/write-flow.css
  - desktop/web/src/mock/writes.ts
  - desktop/web/tests/writes-flow.test.tsx
  - desktop/web/tests/writes-profile-form.test.tsx
  - desktop/web/tests/writes-dialog.test.tsx
- allowed_new_files:
  - desktop/web/src/writes/hubChangeLines.ts
  - desktop/web/tests/writes-hub-api.test.ts
  - desktop/web/tests/writes-hub-logic.test.ts
  - desktop/web/tests/writes-hub-flow.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t044_*.py
  - ts/packages/ui/**
  - scripts/**
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/scenario.ts
  - desktop/web/src/mock/hub-roles.ts
  - desktop/web/src/pages/**
  - desktop/web/src/components/**
  - desktop/web/src/live/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/page-hub.test.tsx
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/writes-live-flow.test.tsx
  - desktop/web/tests/writes-live-preview.test.tsx
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：
  - **预览映射（api.ts）**：真实模式的预览 JSON 里 `hub_changes` 与 `running_turns` 照服务形状映射进 `PreviewData`：
    - `hub_changes: HubChange[]`，每项 `{ post: string; before: HubChangeSide | null; after: HubChangeSide | null }`；
    - `HubChangeSide = { source: 'default' | 'config' | null; profile: string | null; runtime: string | null; adapter: string | null; provider: string | null; model: string | null; thinking: string | null; fallback: HubChangeFallback | null }`；
    - `HubChangeFallback = { profile: string | null; runtime: string | null; adapter: string | null; provider: string | null; model: string | null; thinking: string | null }`；
    - `running_turns: string[]`（只留字符串项，次序照服务给的）。
    - 映射规则（缺键或类型不对时）：`post` 不是字符串 → **跳过这一项**；`before`/`after` 不是对象 → 该侧为 `null`；一侧里的 `source` 不是 `'default'` 也不是 `'config'` → `null`；一侧里其余六个字段不是字符串 → `null`；`fallback` 不是对象 → `null`；`fallback` 里六个字段不是字符串 → `null`。
    - `notes` 仍照旧并入 `unreadable`；`binding_changes`/`resources`/`warnings`/`running_attempts`/`needs_yes`/`command`/`confirmation` 的映射一个不改。
  - **快照（snapshots.ts）**：`hubSnapshot(hub: HubRolesData): HubSnapshot`；只留 `post`、`source`、`profile`、`fallback_profile` 四个字段，按 `post` 排序（用文件里既有的 `byKey` 口径：`localeCompare`）；`fallback_profile` 取 `row.fallback?.profile ?? null`；纯函数，不碰 DOM、不取时钟。
  - **写流程（useWriteFlow.ts）**：
    - `readSnapshot`：`hub.set` 与 `hub.unset` 读 `getHubRoles()`；读失败（`!ok || !data`）→ `{ ok: false }`（与既有分支同口径）；成功 → `{ ok: true, snapshot: hubSnapshot(hub.data) }`；这个分支排在 `getPlugins()` 兜底分支**之前**。
    - `confirm()` 的分支链：`hub.set` → `setHubRole({ post, profile, ...(fallback ? { fallback } : {}) }, 确认号)`；`hub.unset` → `unsetHubRole(post, 确认号)`；两者都排在 `setPluginEnabled` **之前**（`hub.set`/`hub.unset` 不再落到插件启停）。
    - 标题（`titleOf`）：`hub.set` → `改绑定 ${args.post}？`；`hub.unset` → `恢复缺省 ${args.post}？`。
    - 成功轻提示（`successTextOf`）：`hub.set` → `已改绑定 ${args.post}`；`hub.unset` → `已恢复缺省 ${args.post}`。
    - 变化区摘要（`changeSummaryOf`）：`hub.set` → `岗位 ${args.post} 的主绑定改成 ${args.profile}`，有替补时追加 `，替补 ${args.fallback}`，没有替补时追加 `，没有替补`；`hub.unset` → `岗位 ${args.post} 回到内核缺省`。
    - 确认框内容（`content`）加两个字段：`hubChanges: data.hub_changes`、`runningTurns: data.running_turns`。
    - 原因句的条件改成 `data.needs_yes === true && data.running_attempts.length === 0 && data.running_turns.length === 0`；**原因句一字不改**（`有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。`），仍排在 `notes` 最前面。
  - **确认框（WriteConfirmDialog.tsx）**：
    - `ConfirmContent` 加两个必填字段：`hubChanges: HubChange[]`、`runningTurns: string[]`（`contentOf()` 里给 `[]`）。
    - 「变化」一节的排法：先照旧渲染 `changes`（binding_changes）的行；再按 `hubChanges` 的次序逐岗位渲染一块（每个岗位一个小标题行 + 四行前后对比）；`changes` 为空且 `hubChanges` 非空时**不显示**「预览没有列出变化」也不显示 `summary`；两者都空时显示 `summary ?? '预览没有列出变化'`（照旧）。
    - 每个岗位的小标题行：`hubPostLabel(change.post)`（六个岗位是 `协调人（coordinator）`、`规划端（planner）`、`合同端（contract）`、`门禁端（gate）`、`审核端（audit）`、`执行端（exec）`；未知岗位码原样返回该码，不加括号）。
    - 「影响与风险」一节：`runningTurns` 逐行渲染，每行是 `{turn}。在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认。`；`hasRisk` 也要算 `content.runningTurns.length > 0`；`warnings` 与 `notes` 原样（不动 `有 attempt 正在运行：…` 那行的文案）。
  - **前后对比的纯逻辑（hubChangeLines.ts）**：`hubChangeLines(change: HubChange): string[]` 恰好返回四行，次序固定：
    1. `运行时：{前 runtime ?? '—'} · {前 adapter ?? '—'} → {后 runtime ?? '—'} · {后 adapter ?? '—'}`
    2. `模型：{前 provider ?? '—'}/{前 model ?? '—'} → {后 provider ?? '—'}/{后 model ?? '—'}`
    3. `思考档位：{前 thinking ?? '—'} → {后 thinking ?? '—'}`
    4. `替补：{前替补文字} → {后替补文字}`
    - 替补文字：该侧 `fallback` 为 `null` → `—`；`fallback.profile` 非空 → 该 profile id；否则 `${fallback.runtime ?? '—'} · ${fallback.provider ?? '—'}/${fallback.model ?? '—'}`。
    - 「默认」标记：**按侧生效**——某一侧的 `source === 'default'` 时，**该侧四行的值末尾各加一个「（默认）」**（含替补行；该侧没有替补时那一行是 `—（默认）`）；`source` 为 `null` 的侧不标；整侧为 `null` 的那一侧按全 `null` 处理（值全是 `—`，不标「默认」）。例：`运行时：pi · pi（默认） → quizs · quizs`。
    - 文件里还导出 `hubPostLabel(post: string): string`（上面的岗位中文名）。
    - 纯函数：不碰 DOM、不取时钟、不引 `ts/packages/ui`；岗位中文名表**在本文件里另维护一份**（理由见 Steps 第 5 步）。
- 边界输入：
  - 服务的 `hub_changes` 一项里 `post` 不是字符串 → 整项跳过（不显示半条）。
  - 侧的字段缺失或类型不对 → 该字段为 `null`，显示 `—`。
  - `fallback` 为 `null` → 替补一行显示 `—`。
  - `running_turns` 里有非字符串项 → 跳过该项；空数组 → 不出「影响与风险」（除非有 warnings/notes）。
  - `hub.set` 的 args 里没有 `fallback` → 不带这个键（`api.ts` 的 `setHubRole` 与 `writeArgs` 的规则照旧）；`fallback` 是空串 → 也不带。
  - 桩模式（`liveClient()` 为 null）：`hub.set`/`hub.unset` 的预览按夹具算 `hub_changes`：
    - **before**：`src/mock/hub-roles.ts` 里该 `post` 的一行 → `{ source: 行.source, profile, runtime, adapter, provider, model, thinking, fallback }`（`fallback` 为 `null` 或同形状的六字段；缺省行的替补只有四键，取不到 `profile`/`runtime` 就当 `null`）。
    - **after（`hub.set`）**：`source` 恒 `'config'`；`profile` 恒取 `args.profile`（**即使这个 id 不在 `profiles.json` 里也照取**）；`runtime`/`adapter`/`provider`/`model`/`thinking` 取 `args.profile` 在 `src/mock/profiles.json` 里那一行（`thinking` 取 `options?.thinking ?? null`），**表里没有就全部为 `null`**；`fallback`：`args.fallback` 给了就取它在 `profiles.json` 里那一行的同六字段（取不到就 `null`），没给就是 `null`。
    - **after（`hub.unset`）**：内核缺省 → `{ source: 'default', profile: null, runtime: null, adapter, provider, model, thinking, fallback }`，六个字段照 `scripts/kit_roles.py:82-90` 的 `HUB_DEFAULTS`（桩里另放一份表，注释写明出处）。
    - `args.post` 不在夹具的六行里 → `hub_changes` 是空数组（不崩）。
    - 桩里**新写的岗位桩数据**（hub 分支的 after 侧、缺省表、替补 profile）只用 `profiles.json` 的 `step-high` 一条，**不引入 `step-low` 这个 id**；`src/mock/writes.ts` 里**既有**演示文案（既有 `binding_changes` 与错误文案）里的 `step-low` **保留不动，一个字节都不改**。
  - 桩的情景（`src/mock/writes.ts` 的 `WriteScenario` 与 `SCENARIOS` 同步加四个取值，**既有 23 个一个不改、也不许加名单外的取值**）：
    - `hub-ok`：岗位写预览的普通 ok——`hub_changes` 有前后对比、`needs_yes` 假、无警告、无在跑的回合。**它与默认 `ok` 情景下的岗位预览行为一致**，显式列出来是为了让 URL 能直接点名岗位情景（开发与测试按 `?write=hub-ok` 复现）。
    - `hub-warn`：在 `hub-ok` 的基础上，`warnings` 里给一条同模型警告：`合同端与审核端用的是同一个模型（bb/step-5-preview）：审核少一层独立性；照样生效`。
    - `hub-running`：在 `hub-ok` 的基础上，`running_turns` 给一句 `审核端（audit）：2 个回合在跑`，且 `needs_yes` 为真。
    - `hub-unset`：显式的「恢复缺省」ok——`hub.unset` 的预览 `before` 取夹具该行、`after` 取缺省（**与默认 `ok` 情景下 hub.unset 的行为一致**，显式列名便于点名）。
    - 其余既有情景值一个不改（`reread-fail`、`reread-fail-exit1` 等照旧，T040 的 `test_s06_fixture_mode_reread_kept` 依赖它们）。
  - 真实模式：桩的结果一律不出现（`mockPreview` 只在 `liveClient()` 为 null 时被调用，既有行为）。
- 错误与重试：
  - `getHubRoles()` 读失败 → 预览阶段显示「读取当前状态失败」（既有文案），不进入确认框。
  - `hub.set`/`hub.unset` 执行失败（409/5xx/超时）→ 照既有写流程的分类处理（`classifyWrite`），不新增分支。
  - 服务回的预览里 `hub_changes`/`running_turns` 缺键或形状不对 → 按上面的映射规则归 null 或跳过，**不抛错**、不让预览失败。
  - 不做重试（与既有写流程一致）。
- 并发、取消与状态变化：不适用——本片不加写入口、不引入新的并发；`useWriteFlow` 的轮询、计时器与卸载清理照旧（一个字节不改）。
- 兼容性：
  - `api.ts` **只增不改**：既有导出与签名一个不改；`PreviewData` **加两个必填字段**（`hub_changes`、`running_turns`）——这会让「自己造预览数据」的三处既有测试夹具（`tests/writes-flow.test.tsx:125`、`tests/writes-profile-form.test.tsx:385`、`src/mock/writes.ts` 里的 6 处字面量）必须补这两个字段；走 `api.ts` 映射的路径（真实模式、`live-api.test.ts`、`writes-live-flow.test.tsx`）不受影响。
  - `ConfirmContent` 加两个必填字段 `hubChanges`、`runningTurns`；`contentOf()` 的缺省值给 `[]`；`tests/writes-dialog.test.tsx:31` 的 `CONTENT` 夹具必须补这两个字段（否则确认框读 `content.runningTurns.length` 会抛错）。
  - `src/mock` 仍恰 14 份 JSON；`src/pages` 顶层仍恰 9 个 `*Page.tsx`；`mock/writes.ts` 的既有 23 个情景值一个不改（只加四个）。
  - T040 锁定的原因句一字不改（只放宽条件）；T037 的预览映射断言照旧通过；T038 的既有断言与门禁测试文件一个不改。
  - `package.json` 与锁文件不变（`dependency_changes: forbidden`）。
- **写法钉死**（验收的门禁按源码文本查这几处，逐字照抄，别自己换写法）：
  1. `api.ts`：三个类型用 `export interface`；`PreviewData` 里两字段各占一行、行首是字段名、**不是可选**（`hub_changes: HubChange[]` 与 `running_turns: string[]`）；`toPreviewData` 里要有 `hub_changes`、`running_turns`、`stringsOf(preview.running_turns)`、`stringsOf(preview.unreadable)`、`needs_yes: preview.needs_yes === true`，并有两个叫 `hubChangeOf` 与 `hubSideOf` 的辅助函数。
  2. `snapshots.ts`：`HubSnapshot` 用 interface，**嵌套对象逐字段换行**（照文件里既有的 `ProfileSnapshot` 的写法）：
     ```ts
     export interface HubSnapshot {
       posts: Array<{
         post: string;
         source: string;
         profile: string | null;
         fallback_profile: string | null;
       }>;
     }
     ```
     `hubSnapshot` 函数体里要有 `byKey` 与 `row.fallback?.profile ?? null`；`HubRolesData` 用 `import type` 从 `../api` 引（扩写文件里已有的那条 `import type { … } from '../api';`）。
  3. `useWriteFlow.ts`：
     - `readSnapshot` 里的 hub 分支写成 `if (action === 'hub.set' || action === 'hub.unset') {`（这一行的右边 600 字符内要出现 `getHubRoles()`、800 字符内要出现 `hubSnapshot`），并且这个分支排在 `getPlugins()` 兜底分支**之前**。
     - `content` 里写 `hubChanges: data.hub_changes` 与 `runningTurns: data.running_turns`（这两个字面量照抄）。
     - **原因句那一行必须同时含三个条件片段与原因句原文**（同一物理行，**不许把原因句提成常量**，也不许把条件拆到下一行）：
       ```ts
       const notes = data.needs_yes === true && data.running_attempts.length === 0 && data.running_turns.length === 0 ? ['有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。', ...data.notes] : data.notes;
       ```
     - `contentOf()` 的缺省 `ConfirmContent` 里写 `hubChanges: []` 与 `runningTurns: []`。
  4. `WriteConfirmDialog.tsx`：`import type { BindingChange, HubChange } from '../api';`、`import { hubChangeLines, hubPostLabel } from './hubChangeLines';`；`ConfirmContent` 里 `hubChanges: HubChange[]` 与 `runningTurns: string[]` 各占一行、行首是字段名、**不是可选**；`Changes` 组件的 props 里带 `hubChanges`（这个函数体里要出现 `hubChanges`）；`Risks` 组件的函数体里要出现 `runningTurns`、`content.runningTurns.length > 0`、逐字后半句 `在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认。`，并且 `有 attempt 正在运行：` 那行一字不改；岗位块的类名用 `wf-hub` 前缀。
  5. `write-flow.css`：**只在文件末尾追加**，三条规则各自独立成块（选择器后面紧跟一个空格再跟 `{`）：
     ```css
     .wf-hub { … }
     .wf-hub__post { … }
     .wf-hub__line { … }
     ```
     只用 `--tt-*` 令牌、不声明令牌、不写死颜色；**尽量不写 px**（要写就只能写 `0` 或 `1px`，其余 px 所在行要带出处注释）。
  6. `src/mock/writes.ts`：`WriteScenario` 联合里恰 27 个取值（既有 23 个 + `hub-ok`/`hub-warn`/`hub-running`/`hub-unset`，**不许加别的**），`SCENARIOS` 里也有这四个；`import { HUB_ROLES_POSTS } from './hub-roles';`、`import profilesJson from './profiles.json';`；缺省表旁有注释写明「出自 scripts/kit_roles.py」；`previewData` 里的 hub 分支写成 `if (action === 'hub.set' || action === 'hub.unset') {`（这一行右边 1400 字符内要出现 `hub_changes`）；文件里逐字出现 `合同端与审核端用的是同一个模型（bb/step-5-preview）：审核少一层独立性；照样生效` 与 `审核端（audit）：2 个回合在跑`；既有函数 `mockPreview`/`mockSetHubRole`/`mockUnsetHubRole`/`confirmWrite`/`mockGetOperation` 一个都不删。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍 `tests/test_gate_t044_baseline.py`（门禁端写的验收文件，只读；不存在就跳过）**，把它的 S01–S10 与两份探针的断言跟本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/api.ts`**：
   - 加三个导出类型（放在 `PreviewData` 附近，名字照 Behavior contract）：
     ```ts
     export interface HubChangeFallback {
       profile: string | null;
       runtime: string | null;
       adapter: string | null;
       provider: string | null;
       model: string | null;
       thinking: string | null;
     }
     export interface HubChangeSide {
       source: 'default' | 'config' | null;
       profile: string | null;
       runtime: string | null;
       adapter: string | null;
       provider: string | null;
       model: string | null;
       thinking: string | null;
       fallback: HubChangeFallback | null;
     }
     export interface HubChange {
       post: string;
       before: HubChangeSide | null;
       after: HubChangeSide | null;
     }
     ```
   - `PreviewData` 加两个必填字段 `hub_changes: HubChange[]` 与 `running_turns: string[]`（各占一行、行首是字段名）。
   - `toPreviewData` 里加映射：写两个小函数（`hubChangeOf(value: unknown): HubChange | null` 与 `hubSideOf(value: unknown): HubChangeSide | null`，必要时再加 `hubFallbackOf`），按 Behavior contract 的规则处理缺键与类型不对；`hub_changes` 用 `preview.hub_changes`（不是数组就当空数组，数组里逐项映射、映射不出 `post` 的跳过）；`running_turns` 用既有的 `stringsOf(preview.running_turns)`。
   - `notes`、`binding_changes`、`resources`、`warnings`、`running_attempts`、`needs_yes`、`command`、`confirmation` 的映射一个不改；`unreadable` 照旧并进 `notes`。
3. **`desktop/web/src/writes/snapshots.ts`**：加 `hubSnapshot(hub: HubRolesData): HubSnapshot`（`HubRolesData` 用 `import type` 从 `../api` 引；文件已有的 `import type { … } from '../api';` 那行照旧扩写）。`HubSnapshot` 的 interface 写法照「写法钉死」第 2 条逐字写。只留 `post`、`source`、`profile`、`fallback_profile` 四个字段，按 `post` 排序（用既有的 `byKey`），`fallback_profile` 取 `row.fallback?.profile ?? null`。
4. **`desktop/web/src/writes/useWriteFlow.ts`**：
   - `readSnapshot`：在 `profile.add || profile.edit` 那个分支之后、`getPlugins()` 那个兜底分支之前，加 `hub.set`/`hub.unset` 的分支（分支条件照「写法钉死」第 3 条写；读 `getHubRoles()`，失败返回 `{ ok: false }`，成功返回 `hubSnapshot`）。
   - `titleOf`/`successTextOf`/`changeSummaryOf`：按 Behavior contract 的逐字文案补 `hub.set`/`hub.unset` 两条。
   - `confirm()` 的分支链：在 `runtime.add` 之后加 `hub.set`（`setHubRole`）与 `hub.unset`（`unsetHubRole`），末端仍是 `setPluginEnabled`（但这两个动作不再落到它）。`fallback` 只在有值时带（`args.fallback` 非空串）。
   - 组 `content` 时加 `hubChanges: data.hub_changes` 与 `runningTurns: data.running_turns`；原因句那一行照「写法钉死」第 3 条**逐字**写（同一物理行，条件三段 + 原因句原文；原因句原文一字不改）。
   - `contentOf()` 的缺省 `ConfirmContent` 补 `hubChanges: []`、`runningTurns: []`。
   - 轮询、计时器、`classifyWrite`/`classifyTerminal`/`finalFromReread` 一个不改。
5. **`desktop/web/src/writes/hubChangeLines.ts`（新文件）**：
   - `import type { HubChange } from '../api';`（只 `import type`，不引运行时 api）。
   - 导出 `hubChangeLines(change: HubChange): string[]`（四行，次序与文案照 Behavior contract；「默认」标记按侧生效、该侧四行都加；`—` 兜底；替补文字规则照写）。
   - 导出 `hubPostLabel(post: string): string`（六个岗位中文名 + 括号里的岗位码；未知码原样返回）。
   - 岗位中文名表在本文件里另维护一份的**理由**（写进文件注释）：`hubPostName` 在 `src/pages/readonly1/roles-logic.ts`（T038 钉了那里的三个导出与「只 import type」），`src/writes/` 不跨层引 `src/pages/`（本仓库现在没有这种依赖），所以这里维护一份同样的六个名字；B 片的表单仍用 `hubPostName`，两处不要各改一份。
6. **`desktop/web/src/writes/WriteConfirmDialog.tsx`**：
   - `ConfirmContent` 加 `hubChanges: HubChange[]`、`runningTurns: string[]`（各占一行；写法照「写法钉死」第 4 条）。
   - 「变化」一节：`changes` 照旧渲染；`hubChanges` 非空时逐岗位渲染一块（小标题行 `hubPostLabel(post)` + 四行 `hubChangeLines(change)`，类名用 `wf-hub`/`wf-hub__post`/`wf-hub__line`）；`changes` 空且 `hubChanges` 非空时不显示空态文案与 `summary`；两者都空时照旧显示 `summary ?? '预览没有列出变化'`。
   - 「影响与风险」一节：`runningTurns` 逐行渲染成 `{turn}。在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认。`；`hasRisk` 加上 `content.runningTurns.length > 0`；`warnings` 与 `notes` 原样；`有 attempt 正在运行：…` 那行一字不改。
   - 报错与 WARN 一律按纯文本显示（照现有写法，不经 SafeMarkdown）。
7. **`desktop/web/src/writes/write-flow.css`**：**只在文件末尾追加** `.wf-hub`、`.wf-hub__post`、`.wf-hub__line` 三条规则（各自独立成块，既有规则一条不改，基线 1597 字节原样保留）；只用 `--tt-*` 令牌、不声明令牌、不写死颜色；不写十六进制颜色；px 字面量尽量不写（要写只能写 `0` 或 `1px`，其余按仓库规矩带出处注释）；类名一律 `wf-` 前缀。
8. **`desktop/web/src/mock/writes.ts`**：
   - `WriteScenario` 与 `SCENARIOS` 加四个取值 `hub-ok`、`hub-warn`、`hub-running`、`hub-unset`（既有 23 个一个不改，也不加别的取值）。
   - `previewData` 里的 6 处 `PreviewData` 字面量（`:128`、`:141`、`:154`、`:167`、`:180`、`:192`）**每处**都补 `hub_changes: []` 与 `running_turns: []`（`PreviewData` 变必填后不补会过不了类型检查）。
   - `previewData` 的 `hub.set`/`hub.unset` 分支（现 `:178-190`）改成按夹具算 `hub_changes`（分支条件照「写法钉死」第 6 条写；before/after 的算法照 Behavior contract 边界输入）；`after` 用 `src/mock/profiles.json` 的 `step-high` 一行与 `args.fallback` 指定的替补（替补也只能是 `step-high`；**新写的桩数据里不出现 `step-low`**；既有演示文案里的 `step-low` 保留不动）；`after` 取缺省时用桩里另放的一份 `HUB_DEFAULTS` 表（照 `scripts/kit_roles.py:82-90`，注释写明出处）；`args.post` 不在六行里 → `hub_changes` 为空数组。
   - 情景加成：`hub-warn` 给 `warnings` 一条 `合同端与审核端用的是同一个模型（bb/step-5-preview）：审核少一层独立性；照样生效`；`hub-running` 给 `running_turns` 一句 `审核端（audit）：2 个回合在跑` 且 `needs_yes` 为真；`hub-ok` 与 `hub-unset` 与默认 `ok` 下的岗位预览行为一致（显式别名，注释写明）。
   - 桩的 import：加 `import { HUB_ROLES_POSTS } from './hub-roles';` 与 `import profilesJson from './profiles.json';`（`hub-roles.ts` 只 `import type` 来自 `../api`，编译后擦除，不会产生运行时循环）。
9. **既有测试夹具补字段**（各加一行，不改既有断言）：
   - `desktop/web/tests/writes-flow.test.tsx:125` 附近的那份预览 `data`：加 `hub_changes: []`、`running_turns: []`。
   - `desktop/web/tests/writes-profile-form.test.tsx:385` 的 `pvEnv()`：同样加这两个字段。
   - `desktop/web/tests/writes-dialog.test.tsx:31` 的 `CONTENT`（`ConfirmContent` 夹具）：加 `hubChanges: []`、`runningTurns: []`（**第三处，漏了它确认框会读 `content.runningTurns.length` 抛错**）。
10. **新测试**（三个文件，都不许 `skip`/`only`/`todo`）：
    - `desktop/web/tests/writes-hub-api.test.ts`：用 `setLiveClientForTests` 注入假服务（照 `tests/writes-live-flow.test.tsx` 的写法）断言：
      - `api.preview('hub.set', { post: 'contract', profile: 'step-high' })` 的 `data.hub_changes` 映射：post、`before`/`after` 的 `source`/六字段/替补逐字段对上服务给的形状；
      - 缺键与类型不对的兜底：`post` 不是字符串的项被跳过；侧里非字符串字段归 `null`；`fallback` 不是对象归 `null`；缺 `hub_changes`/`running_turns` 键时两个字段是 `[]`；
      - `notes` 仍并入 `unreadable`（既有行为照旧）；
      - 写路由：`api.setHubRole({ post: 'contract', profile: 'step-high', fallback: 'step-low' }, 'c1')` → `POST /api/v1/hub/roles/contract`、正文 `{ profile: 'step-high', fallback: 'step-low', confirmation: 'c1' }`；不带 `fallback` 时正文里没有 `fallback` 键；`api.unsetHubRole('contract', 'c1')` → `POST /api/v1/hub/roles/contract/unset`、正文 `{ confirmation: 'c1' }`。
    - `desktop/web/tests/writes-hub-logic.test.ts`：`hubSnapshot` 的投影与排序（`posts` 按 `post` 排、只有四个字段、替补的 profile 为 null 时是 null）；`hubChangeLines` 的四行文案（有替补、无替补显示「—」、缺省一侧标「默认」（该侧四行都带）、侧为 null 时全是「—」且不标「默认」、替补文字两种拼法）；`hubPostLabel` 的六个中文名与未知码原样。
    - `desktop/web/tests/writes-hub-flow.test.tsx`：真实模式（注入假服务）挂载写流程，断言：
      - `hub.set` 确认后发的是 `POST /api/v1/hub/roles/<post>`（正文带确认号），**没有** `POST /api/v1/plugins/...`（不再误调 `setPluginEnabled`）；`hub.unset` 发的是 `.../unset`；
      - 确认框「变化」一节显示岗位前后对比（四个维度都在、缺省一侧有「默认」）；
      - `needs_yes` 的两种说法：预览的 `unreadable` 有值 → 原因句逐字出现（在 `.wf-note` 的第一条）；预览的 `running_turns` 有值 → **不出**原因句、Risks 里逐行显示那句「在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认」；
      - 桩情景（`api.preview` 走 `mockPreview`）：`hub-warn` 的 `warnings` 有那条同模型警告、`hub-running` 的 `running_turns` 有一句且 `needs_yes` 为真、`hub.unset` 的 `after` 是缺省（`source: 'default'`、`profile: null`）、桩的新数据里不出现 `step-low`。
11. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → R01**（G01 的流水线会先在验证工作区的 `desktop/web` 里 `npm ci`；本 worktree 里若没有 `node_modules`，先在 `desktop/web` 跑一次 `npm ci --no-audit --no-fund`），记录命令与结果。
12. 写执行报告；遇到合同未定义的行为（例如服务回的字段形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t044_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：`PreviewData` 加了 `hub_changes` 与 `running_turns`，`toPreviewData` 照服务形状映射（post 非字符串跳过该项、侧与字段缺键/类型不对归 null、替补不是对象归 null），`unreadable` 照旧并进 `notes`，既有字段与 T037 的映射断言照旧通过；证据：V01、V02、G01；目的：确认框要显示的东西必须与服务真的给的东西一致，形状不对时宁可显示「—」也不崩。
- D02：`hubSnapshot` 是纯函数，投影只有 `post`/`source`/`profile`/`fallback_profile`，按 `post` 排序；证据：V01；目的：重读比对只认参与比对的字段，不把会自己变的字段算进「变了没有」。
- D03：`hub.set` 走 `POST /api/v1/hub/roles/<post>`、`hub.unset` 走 `POST /api/v1/hub/roles/<post>/unset`，正文带确认号；两个动作的 `readSnapshot` 读 `getHubRoles`；`titleOf`/`successTextOf`/`changeSummaryOf` 补了这两个动作；**没有**再落到 `setPluginEnabled`；证据：V01、G01；目的：写错分支会悄悄调插件启停——那是最坏的一种错（改错东西还不报错）。
- D04：原因句一字未改，条件放宽成「没有在跑的 attempt 且没有在跑的回合」；`running_turns` 有内容时不出原因句，Risks 里逐行显示「在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认」；`running_attempts` 有值时的既有说法照旧；T040 的三种情形照旧通过；证据：V01、R01、G01；目的：有在跑的回合时原因句是错的（不是「状态读不出来」），但不能改那句话，只能换一种说法。
- D05：确认框「变化」一节在 `hubChanges` 非空时按岗位显示前后对比（运行时、模型、思考档位、替补；无替补显示「—」；缺省一侧标「默认」），`changes` 空且 `hubChanges` 非空时不显示「预览没有列出变化」；warnings 与 notes 原样；证据：V01、G01；目的：用户要在确认之前看见这次改动到底改了什么。
- D06：`hubChangeLines(change)` 是纯函数，恰好四行、次序固定，兜底与「默认」标记照合同（按侧生效，该侧四行都带）；`hubPostLabel` 给六个岗位中文名；证据：V01；目的：确认框与将来的表单底部共用同一份前后对比文字，不能各写一套。
- D07：桩的 `hub.set`/`hub.unset` 预览按夹具算 `hub_changes`（before 取夹具该行、after 取所选 profile 或缺省），四个岗位情景 `hub-ok`/`hub-warn`/`hub-running`/`hub-unset` 在 `WriteScenario` 与 `SCENARIOS` 里都在，既有 23 个情景值一个不改；`src/mock` 仍恰 14 份 JSON；桩只在 `liveClient()` 为 null 时生效；证据：V01、G01、R01；目的：开发与测试要能按 URL 复现四种岗位情景，真实模式不能看到桩的结果。
- D08：既有测试没被删、跳过或弱化：T040 的三种情形、T037 的预览映射断言、T038 的既有断言照旧通过；只给三处自己造数据的既有夹具（`writes-flow.test.tsx`、`writes-profile-form.test.tsx`、`writes-dialog.test.tsx`）补了 `hub_changes`/`running_turns`（第三处是 `ConfirmContent` 夹具，漏了它确认框会抛 `undefined.length`），既有断言一条没改；新测试不用 skip/only/todo；证据：V01、R01、review；目的：既有断言是长期保护，不能为了新功能放松。
- D09：所有修改都在允许集合内（9 个可改文件、4 个可新增文件），没有碰 `forbidden_paths`（含 `tests/test_gate_t044_*.py`、`ts/packages/ui/**`、`scripts/**`、`src/pages/**`、`src/mock/*.json`、`src/mock/hub-roles.ts`、`page-app.test.tsx`、`page-hub.test.tsx`、`live-api.test.ts`、`writes-live-flow.test.tsx`）；`package.json` 与锁文件不变；证据：scope、G01、R01；目的：这一片不许顺手改别的片的地盘，也不许提前做 B 片。
- D10：新代码守既有源码规矩：`src/writes/hubChangeLines.ts` 只 `import type`、不碰 DOM 与时钟；`src/mock/writes.ts` 不出现网络词与危险 HTML 写入/动态求值类词（`page-static.test.ts` 按子串查）；`write-flow.css` 只在末尾追加、只用令牌、带 px 的行有出处注释；`src` 下不渲染 `role=status`、不调 `matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`；证据：G01、R01、V02；目的：不破 T006/T009/T013/T023/T037 的长期门禁。
- D11：`hub.set` 不再调 `setPluginEnabled` 有测试证明（断言发出的路径是 `/api/v1/hub/roles/<post>`、没有 `/api/v1/plugins/...`）；`hub.unset` 的路径与正文（只有确认号）也有断言；证据：V01；目的：这是本片最容易错也最危险的一处。
- D12：**新写的**岗位桩数据（hub 分支的 after 侧、缺省表、替补 profile）只用 `profiles.json` 的 `step-high` 一条，**不引入 `step-low` 这个 id**；**既有**演示文案里的 `step-low`（`src/mock/writes.ts` 的 6 处）保留不动；替补只出现在主选适配器是 `quizs` 的岗位上（内核 `scripts/kit_roles.py:332-333` 的口径在本片只体现在桩数据里，不实现筛法）；证据：V01、G01；目的：桩数据也要守内核的规则，且新数据不能让桩撞上 T009 D09 拿来当独有串的 id，同时既有演示数据一个字都不改。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `desktop/web/src/api.ts` 里没有 `setHubRole`/`unsetHubRole`/`getHubRoles`，或 `PreviewData` 的既有字段与本节写的不一样），特别是：这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `ts/packages/ui`、`scripts/`、`src/pages/**`、`src/mock/*.json`、`src/mock/hub-roles.ts`、既有门禁测试、`page-app.test.tsx`、`page-hub.test.tsx`、`live-api.test.ts`、`writes-live-flow.test.tsx`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在本片加写入口、加禁用按钮或实现替补筛法）。
- 门禁文件 `tests/test_gate_t044_baseline.py` 与本合同的「写法钉死」一节出现实质冲突（例如它要求的原因句写法与本合同给的逐字写法互斥）：停下并报告（不要自己去改门禁文件，也不要私自换一种写法绕过）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，含返工版本；累计已用 0 次——本版留 2 次实现与定点返工，余量 1 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（3 次 × 5400；累计已用 0 秒，本版可用 16200 秒 ≥ 2×5400）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码、门禁文件与核对事实 12 分钟；实现（api.ts、snapshots、useWriteFlow、确认框、hubChangeLines、mock 桩）28 分钟；补测（三个新测试文件 + 三处既有夹具）18 分钟；必要检查（G01、V01、V02、V03、R01，其中 R01 约 23 分钟）25 分钟；最终报告 5 分钟；总计约 88 分钟，单轮时限 5400 秒（90 分钟）。

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

站主来信 20261115T035640491556Z-owner-b371f1：

> 站主决定（2026-11-15）：
> 1. 拆法认可。T044 只做 A 片：规划报告第 3 节第 1–6 步（api.ts 的 PreviewData 加 hub_changes、running_turns 与映射；hubSnapshot；useWriteFlow 认 hub.set、hub.unset，needs_yes 的两种说法；写确认框按岗位显示前后对比与在跑的回合；前后对比的纯逻辑；桩的岗位情景）。不加“七端岗位”一组的入口与表单。合同照 A 片写，合同端照常等内核挪基线、写信再开工。
> 2. B 片（第 7–10 步）站主另登记 T045（--after T044），任务书附上这份规划报告的 B 片部分。B 片撞的三条门禁由站主在 T045 合同开工前合入门禁准备：T038 的 test_transitional_probe_no_write_entries 退役；T038 的 test_s05_rolesview_hub 放宽为只要求以 `<HubPosts hub={data.hub}` 开头；T009 的 test_d11_probe_write_entries_disabled 角色页可用按钮白名单加“改绑定…”“恢复缺省…”。A 片不推翻任何门禁，T044 不用等它。
> 3. 替补的筛法照内核 kit_roles.py:316 的规则：主选是 quizs 才能选替补，替补候选去掉 quizs；主选不是 quizs 时替补禁用。这条写进 T045 的合同；A 片的桩照这条出数据（替补只出现在主选是 quizs 的岗位上）。
> 4. 两处包内测试（page-app.test.tsx:91 角色页的写入口个数、page-hub.test.tsx:84 的六列列头）写进 T045 合同的允许修改范围，照新行为改，describe 标题不动。
> 另：假设 H5 站主核过，不撞。T009 的 TRANS2 只核夹具里的值，不数角色页的按钮；TRANS3 现在只钉总览页 0 个禁用按钮。
