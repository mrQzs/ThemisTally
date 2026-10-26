# TASK: t023-desktop-ui-writes-b

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 5edda28f31c8e107d93a800deda2acb2d51afdcf
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端前端（`desktop/web`）把删除与回滚的四个写入口接上 T022 已有的写确认流程（预览 → 确认 → 执行 → 重读 → 结果）：`desktop/web/src/api.ts` 新增 `removePreset`、`removeProfile`、`removeRuntime`、`rollback` 四个写函数与四个新 `WriteAction`（演示数据、不联网）；`desktop/web/src/writes/snapshots.ts` 新增四个快照投影；`useWriteFlow` / `WriteConfirmDialog` 支持「删除与回滚的确认按钮用危险样式」与按 action 拼的标题；四个入口（方案表 [删除…]、profile 表 [删除]、运行时页 [删除…]、历史抽屉 [回滚到这一条之后]）可点并走同一条流程；`?write=` 新增 `in-use` 情景。成功只在重读之后才说（W3）；确认框里不出现「没有变化」这个子串（W3b）。

## Non-goals
- 表单类与作业类入口照旧禁用、提示照旧是「第二阶段接入」：[更改…]、[保存当前为方案…]、[新建 profile]、profile [编辑]、运行时 [手动登记…]、[探测]、[模型]、[运行就绪检查]、[扫描 PATH]、[核对全部]、[重新核对]、凭据 [录入…]。
- 不做真正的网络客户端；`desktop/web/src` 下任何文件（注释也算）不出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket`。
- 13 个读函数、A 片已有的四个写函数（`preview`、`getOperation`、`usePreset`、`setPluginEnabled`）与既有类型的行为一字不改；A 片的状态机与映射表不重新设计。
- 不改 `desktop/web/src/components/index.ts`、`App.tsx`、`main.tsx`、`desktop/web/src/mock/*.json`、`desktop/web/src/pages/readonly2/history-logic.ts`（抽屉底栏「这是最新的一条，回滚后没有变化」照旧）、`docs/**`、`ts/**`、`scripts/**`、任何 `tests/test_gate_*`。
- 不新增页面文件、不新增 JSON 夹具、不改依赖与锁文件。
- 不推翻任何 `tests/test_gate_*` 的断言（T022 里 B 片的五项过渡断言已在 `04f7952` 退役；本片不需要再退役任何一条）。

## Repository facts
- 入口与签名（`desktop/web/src/api.ts`）：`export type WriteAction = 'preset.use' | 'plugin.enable' | 'plugin.disable'`（`:44`）；`preview(action: WriteAction, args: Record<string, string>): Promise<HttpReply<PreviewData>>`、`getOperation(id: string): Promise<HttpReply<OperationView>>`、`usePreset(name, confirmation)`、`setPluginEnabled(id, enabled, confirmation)`（`:240–255`）；13 个读函数 `getMeta`…`listSecrets`（`:120–218`）。
- 写流程（`desktop/web/src/writes/`）：`useWriteFlow.ts`（`WriteSpec{action, args, title}`、`start(spec)`、`flow`；`readSnapshot` 按 action 分支读快照、`confirm` 按 action 调写函数、`successTextOf` 给轻提示文字、`applyFinal` 落终态）；`WriteConfirmDialog.tsx`（`ConfirmContent`、`FlowView`、`FlowRender`、`WriteFlow`；Footer 的 [确认…] 在五个状态里都是 `variant="primary"`）；`snapshots.ts`（`presetSnapshot`、`pluginSnapshot`、`sameSnapshot`）；`writeOutcome.ts`（`classifyWrite`、`classifyTerminal`、`finalFromReread`、`errorText`、`warnLines`）。
- 演示数据（`desktop/web/src/mock/writes.ts`）：`WriteScenario` 19 个值、`writeScenario()` 从 `location.hash` 的 `?write=` 读、`baseArgv`（`preset.use` → `config preset use <name>`，插件 → `plugins enable|disable <id>`）、`writeArgv` 加 `--expect-state=<state>`、`previewData`、每个预览签发一个 43 位确认号并记进 `opActions`（号 → action）。
- 四个入口的现状：方案表 [删除…] 是 `DisabledAction variant="ghost" size="sm"`（`desktop/web/src/pages/readonly1/roles-PresetsTable.tsx:98`，当前行只写「当前方案不能删」）；profile 表 [编辑]、[删除] 都是 `DisabledAction variant="ghost" size="sm"`（`roles-ProfilesTable.tsx:72–73`）；运行时 [探测]、[模型]、[删除…] 都是 `DisabledAction variant="ghost" size="sm"`（`runtimes-RuntimesView.tsx:66–68`）；历史抽屉 [回滚到这一条之后] 是 `DisabledAction variant="secondary" size="md"` 带 `RotateCcwIcon 16`（`desktop/web/src/pages/readonly2/history-HistoryView.tsx:156–161`）。方案表已经接了 A 片流程（`useWriteFlow(reload)` + `<WriteFlow/>`，`roles-PresetsTable.tsx:44,120`）。
- `reload` 的转交链：`PageFrame` 的 `children: (data, reload) => ReactNode`（`desktop/web/src/shell/PageFrame.tsx:33`，`reload` 在 `:130–134`）；`RolesPage.tsx:46` → `roles-RolesView.tsx` → `roles-PresetBar` / `roles-PresetsTable`；`RuntimesPage.tsx` 的 children 是 `(data) => …`（要加 reload）；`HistoryPage.tsx` 的 children 是 `(data) => …`（要加 reload）。
- **重读与抽屉（已核）**：`reload()` 走 `request(true)` → `setData` → `children(data, reload)` 重渲染；同一位置、同一类型的子组件不卸载，所以 `HistoryView` 的 `openNumber`/`selectedKey` 保留——回滚成功后历史抽屉仍开着、仍是同一条，**不需要**另加状态保持。
- **确认框与抽屉不互相干扰（已核）**：`Dialog` 经 `MountLayer` 挂到 body 下（`desktop/web/src/components/Dialog.tsx:60–63`），所以确认框不是抽屉的 DOM 后代；Dialog 的 Esc `stopPropagation`（`:36–40`），Esc 只关确认框；`dismissible=false` 的阶段（执行中、确认结果中、重读中）Esc、遮罩、[取消]、关闭钮都关不掉，外层 Drawer 也不关（A 片已有用例）。
- 门禁现状（已全文核对 `tests/`）：
  - T013（`tests/test_gate_t013_baseline.py:82–96`、`:328–340`）：13 条动作说明（「删除方案」「删除 profile」「回滚配置」等）只许出现在 `desktop/web/src/components/actionTitle.ts`；扫描范围是 `src/components`、`src/pages/readonly1`、`src/pages/readonly2`——**`src/writes/` 不在扫描范围内**（`desktop/web/tests/cleanup1-static.test.ts:60` 的 `SCANNED` 同口径）。所以确认框标题与轻提示文字可以写在 `src/writes/`，但入口文件里一个字都不许写这 13 条。
  - T009：`:2511–2515` profile 表两按钮都要 `data-variant="ghost"`、`data-size="sm"`；`:2563–2575` 方案表当前行没有 [使用]、[删除…]，非当前行的 [使用]、[删除…] 是 ghost sm；`:2844–2865` 运行时页每行都有 [删除…]，`:2852` 只要求**非** [删除…] 的按钮禁用；`:2955` 角色页可用按钮白名单含「切换…」「使用」「删除…」「删除」，`:2967` 运行时页白名单含「删除…」，`:2957–2960`、`:2969` 仍禁用的按钮悬停提示必须是「第二阶段接入」。
  - T010：`:2864–2882` 抽屉 [回滚到这一条之后] 是 secondary、md、带 `RotateCcwIcon` 16（不再断言禁用）；`:2946–2947` `ALLOWED_BUTTONS` 含「回滚到这一条之后」「取消」；`:3182–3216` 的 D09 只打开历史表**第一行**（夹具里最新一条 #42，config 资源），并要求抽屉里**禁用**按钮的悬停是「第二阶段接入」——所以 #42 的回滚钮必须可点；D07 打开本机文件条目（#4）时只断言底栏文字，不断言按钮禁用。
  - T022：`:238` 只查 `WriteAction` 含三个旧成员（查包含，不查只有三个）；`:361–365` 只查 19 个情景都在；api 探针的 `FORBIDDEN`（`:500–502`）里没有本片的四个名字；`:279–289` `write-flow.css` 只用既有令牌且被源码 import。
  - T006：`:110–116` `LATER_API` 里**没有** `removePreset`/`removeProfile`/`removeRuntime`/`rollback`（不许导出的 16 个名字是 `listAttempts`、`getConfig`、`validateConfig`、`getHistoryEntry`、`getPlugin`、`checkSecret`、`subscribeEvents`、`search`、`startJob`、`getJob`、`cancelJob`、`startSecretEntry`、`setRole`、`savePreset`、`saveProfile`、`addRuntime`）；`:3313–3323` 只查 13 个读函数都在、LATER_API 的名字不出现。
- 服务侧口径（只读参照）：`ts/packages/ui/src/writeroutes.ts:80–88` 的 `WRITE_ACTIONS` 给出 args 键（`preset.remove`→`name`、`profile.remove`→`profile`、`runtime.remove`→`runtime`、`config.rollback`→`number`），`:273–307` 的 `buildWriteArgv` 给出基础 argv（`config preset remove <name>`、`config profile remove <profile>`、`config runtime remove <runtime>`、`config rollback <number>`）。
- 内核报错原文（只读参照）：`scripts/kit_roles.py:755`（runtime 被 profile 引用）、`:958`（profile 被角色或方案引用）、`:1225`（方案正在用）；前缀是 `ERROR: `（`scripts/kit_config.py:1770`），`ts/packages/ui/src/kernelenvelope.ts:26` 只留 `ERROR`/`WARN` 开头的行，原样进 `messages`。
- 夹具（`desktop/web/src/mock/`）：`presets.json` 两条（`default` 当前、`economy`）；`profiles.json` 两条（`step-high`、`step-low`）；`runtimes.json` 三条（`pi`、`claude-code`、`opencode`）；`roles.json` 的 `execution` 绑 `step-high`；`history.json` 三条（`#42` config/preset.use 最新、`#41` local/runtime.add、`#40` config/config.set）。T006 `:3326` 钉 `src/mock/` 恰有 14 份 JSON，**不许新增 JSON**；新增演示数据只能写成 `.ts`。
- UI 设计（`docs/themis-tally-3.0-桌面端-UI设计.md` 7.11）：确认框标题是「动词加对象」，内容依次是「将运行的命令」「变化」「影响与风险」，按钮 [取消] [确认…]，**删除与回滚的确认按钮用危险样式**；变化区为空时写「预览没有列出变化」（A 片口径，不含「没有变化」）。
- 工具链与锁文件：`desktop/web` 用 npm + Vite 5 + Vitest 2（jsdom）+ testing-library；脚本是 `dev` / `build`（`tsc --noEmit && vite build`）/ `test`（`vitest run`）/ `typecheck`（`tsc --noEmit`）/ `check:contract`（`node scripts/token-contract.mjs`）；`desktop/web/package-lock.json` 不许改；`desktop/web/tsconfig.json` 的 include 只有 `src` 与 `vite.config.ts`，`tests/` 不进 tsc。
- 既有前端用例里与本片相冲的四处（要在允许集合内改）：`desktop/web/tests/page-app.test.tsx:91–103`（写入口个数：角色页 12→9、运行时页 9→6、总览 0）；`desktop/web/tests/readonly2-app.test.tsx:106–131`（历史抽屉开时禁用按钮由 ['回滚到这一条之后'] 改成空）与 `:133–134`（可用按钮白名单补「回滚到这一条之后」）；`desktop/web/tests/page-runtimes.test.tsx:67–76`（[删除…] 由禁用改成可点，其余仍禁用）；`desktop/web/tests/readonly2-history.test.tsx:267–282`（最新一条 #8 的回滚钮由禁用改成可点；本机文件 #4 仍禁用，提示是「本机文件不存快照，不能回滚」）。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/HistoryPage.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/src/pages/readonly1/roles-PresetsTable.tsx
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
  - desktop/web/src/pages/readonly2/history-HistoryView.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/page-runtimes.test.tsx
  - desktop/web/tests/page-roles.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/readonly2-history.test.tsx
- allowed_new_files:
  - desktop/web/tests/writes-remove.test.tsx
  - desktop/web/tests/writes-rollback.test.tsx
  - desktop/web/tests/writes-snapshots-b.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t023_*.py
  - tests/test_gate_*.py
  - desktop/web/src/components/index.ts
  - desktop/web/src/mock/*.json
  - desktop/web/src/App.tsx
  - desktop/web/src/main.tsx
  - desktop/web/src/pages/readonly2/history-logic.ts
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - docs/**
  - ts/**
  - scripts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 既有测试文件的处置口径：`desktop/web/tests/page-app.test.tsx`、`page-runtimes.test.tsx`、`page-roles.test.tsx`、`readonly2-app.test.tsx`、`readonly2-history.test.tsx` 这五份**只照新行为改那几条断言**（禁用 → 可点、悬停提示、写入口个数、白名单），不许删用例、不许削弱别的断言；A 片的四份 `desktop/web/tests/writes-*.test.*` 一个字都不许改；`desktop/web/tests/` 下其余文件一个字都不许改。新用例一律写在新建的三个 `desktop/web/tests/writes-*.test.*` 文件里。

## Behavior contract

### 一、`desktop/web/src/api.ts` 的四个新导出

- 13 个读函数、`Envelope`、`HttpReply`、`BindingChange`、`PreviewData`、`OperationView` 一字不改。
- `export type WriteAction = 'preset.use' | 'plugin.enable' | 'plugin.disable' | 'preset.remove' | 'profile.remove' | 'runtime.remove' | 'config.rollback';`（加四个成员，旧三个保留）。
- 新增四个写函数（都返回 `Promise<HttpReply<null>>`，转给 `desktop/web/src/mock/writes.ts`，不联网）：
  - `export function removePreset(name: string, confirmation: string): Promise<HttpReply<null>>`
  - `export function removeProfile(profile: string, confirmation: string): Promise<HttpReply<null>>`
  - `export function removeRuntime(runtime: string, confirmation: string): Promise<HttpReply<null>>`
  - `export function rollback(number: number, confirmation: string): Promise<HttpReply<null>>`
- `preview(action, args)` 照旧支持全部七个 action；args 的键照服务侧：`preset.remove` 用 `{name}`、`profile.remove` 用 `{profile}`、`runtime.remove` 用 `{runtime}`、`config.rollback` 用 `{number}`（预览的 args 是字符串，`rollback` 执行时用 `Number(args.number)` 传数字）。
- 不许导出 T006 `LATER_API` 里的 16 个名字；不新增别的读函数。

### 二、四个写函数的确认号与参数（mock 侧）

- 预览签发的确认号（43 位）照旧当操作号用；**新增一张表**只记四个新 action 的 `(action, args)`。A 片三个 action 的 `getOperation` 行为（`mockGetOperation` 里按 action 反推 args）**一字不改**。
- 四个新写函数执行时：确认号不在表里、或号绑定的 action 与本次 action 不同、或 args 与本次不同（例如删错对象、rollback 用错编号）→ 返回 **409**、`exit_code: null`、`messages: ['ERROR 确认号无效、已过期或已用过：请重新预览']`（照 A 片 `expired` 情景的原文与状态码），流程据此显示「确认已失效（过期、已用过或参数不符），请重新预览」。
- 执行 argv 照服务侧的基础 argv 加 `--expect-state=<state>`：`config preset remove <name> --expect-state=<state>`、`config profile remove <profile> --expect-state=<state>`、`config runtime remove <runtime> --expect-state=<state>`、`config rollback <number> --expect-state=<state>`；预览命令加 `--dry-run --json`。

### 三、演示情景：`?write=` 的 20 个值

- 19 个旧值（`ok`、`warn`、`exit1`、`exit2`、`exit3`、`stale`、`expired`、`busy`、`closing`、`spawn`、`toolarge`、`timeout`、`drop-done`、`drop-lost`、`drop-hang`、`preview-fail`、`preview-busy`、`reread-fail`、`reread-fail-exit1`）对四个新 action 的结局照旧，与 A 片同一个映射表。
- 新增第 20 个值 `in-use`：
  - 预览：200、正常预览数据；
  - 执行：200、`ok:false`、`exit_code: 1`，`messages` 一行 `ERROR: …`（原文见第五条）；
  - `getOperation`：`failed` / `exit`；
  - 结局：重读后快照与预览时相同（夹具静态）→ 终态是**失败**，原因标签「内核拒绝」，对话框里有内核原文；**不弹轻提示**，对话框里不出现「成功」也不出现「已部分写入」。
  - `in-use` 对 A 片三个 action 一律照 `exit1` 的响应（退出 1、ERROR 行）。

### 四、确认框内容、标题与轻提示（文字一律写在 `desktop/web/src/writes/`）

- 入口文件（readonly1、readonly2）里只许出现按钮标签「删除…」「删除」「回滚到这一条之后」；**确认框标题、变化区摘要、成功轻提示一律由 `src/writes/` 按 action 与 args 拼**（T013 的 13 条动作说明不许出现在 readonly1/readonly2；`src/writes/` 不在 T013 扫描范围内）。
- 做法：`WriteSpec.title` 改成**可选**；`useWriteFlow` 在 `title` 缺省时用 `titleOf(action, args)` 补上（A 片 `roles-PresetBar.tsx` 现有的 `title` 传法照旧可用，行为不变）。`titleOf` 与 `successTextOf` 的文字表放在 `src/writes/`（例如新文件 `src/writes/writeTexts.ts`，或并进 `useWriteFlow.ts`）。
- 四个新 action 的标题、变化区摘要、成功轻提示（逐字）：

| action | 标题 | 变化区（预览没有 binding_changes 时的摘要） | 成功轻提示 |
|---|---|---|---|
| `preset.remove` | 「删除方案 economy？」 | 「方案表里去掉 economy，角色绑定不变」 | 「已删除方案 economy」 |
| `profile.remove` | 「删除 profile step-low？」 | 「profile 表里去掉 step-low」 | 「已删除 profile step-low」 |
| `runtime.remove` | 「删除运行时 pi？」 | 「已登记表里去掉 pi；本机文件里登记的命令一并删去」 | 「已删除运行时 pi」 |
| `config.rollback` | 「回滚到 #42 之后？」 | 无摘要：变化区写「预览没有列出变化」 | 「已回滚到 #42 之后」 |

  - 标题与摘要里的对象名来自 `args`（`name` / `profile` / `runtime` / `number`）。
  - 审计号：拿得到才加「 · 审计 #N」，演示里拿不到，不许编。
- `config.rollback` 的预览 `binding_changes`：夹具里最新一条（`#42`）时是空数组（所以变化区写「预览没有列出变化」），其余编号给一条演示变化 `{role: 'execution', from: 'step-low', to: 'step-high'}`。三个删除的 `binding_changes` 恒为空数组（靠变化区摘要说明）。
- **危险样式**：四个新 action 的 [确认…] 在**所有**状态（预览中、可确认、执行中、确认结果中、重读中）都用 `variant="danger"`；A 片三个 action 仍是 `variant="primary"`。做法：`FlowRender` / `WriteConfirmDialogProps` 加 `danger: boolean`，Footer 用 `variant={danger ? 'danger' : 'primary'}`；`useWriteFlow` 按 action 决定 `danger`。
- **W3b**：确认框（`[role="dialog"]` 元素内）的文字里**不出现「没有变化」这个子串**；变化区为空写「预览没有列出变化」。注意抽屉底栏那句「这是最新的一条，回滚后没有变化」在抽屉里、不在确认框里，是 T010 `:2872` 钉着的既有文案，不许改；断言「没有变化」时必须限定在确认框元素上，不许查 `document.body`。
- 命令区照旧显示去掉 `--dry-run` 与 `--json` 的写命令（`dispatchCommand`），其余（变化、影响与风险、按钮随状态变）照 A 片。

### 五、`in-use` 的内核报错原文（逐字，`ERROR: ` 前缀照 `scripts/kit_config.py:1770`）

- `profile.remove`：`ERROR: profile <profile> 被 roles.execution 引用：先改这些绑定或方案`
- `runtime.remove`：`ERROR: runtime <runtime> 被 profile step-high、step-low 引用：先改或删这些 profile`
- `preset.remove`：`ERROR: 方案 <name> 正在用：先 preset use 别的方案，或 config unset active_preset`

  - 引用对象是**固定的演示文字**（与夹具不完全对得上不算错；界面上当前方案那一行本来就没有 [删除…]，所以 `preset.remove` 的这条文案由 api 层用例验，不必走界面）。
  - 内核原文只出现在 `src/mock/writes.ts`（或 `src/writes/`），**不许**出现在 readonly1 / readonly2（`「删除方案」` 是 T013 的 13 条之一）。

### 六、快照（`desktop/web/src/writes/snapshots.ts` 的四个新投影）

规矩照 A 片：投影只留参与比对的字段并排好序；`sameSnapshot` 是纯函数。

| action | 读函数 | 比较的字段 | 排除在外 |
|---|---|---|---|
| `preset.remove` | `getPresets` | `active_preset`；`presets[].{name, active}`（按 name 排序） | `description`、`presets[].roles` |
| `profile.remove` | `getProfiles` | `profiles[].id`（按 id 排序） | `runtime`、`provider`、`model`、`options`、`credential_env`、`adapter` |
| `runtime.remove` | `getRuntimes` | `runtimes[].{id, adapter}`（按 id 排序） | `source`、`notes`、`command`（按环境变量、本机文件、PATH 解析，会自己变） |
| `config.rollback` | `getRoles`、`getPresets`、`getProfiles`、`getRuntimes`、`getPlugins` 并行读 | roles `{role, explicit, binding}`；presets `{active_preset, presets[].{name, active, roles}}`；profiles `{id, runtime, provider, model, options, credential_env}`；runtimes `{id, adapter}`；plugins `{id, enabled}` | 整份 `getHistory`（每次写都变）、status、usage、secrets、A 片列出的全部探测与时间字段 |

- 已知局限（写进执行报告的风险段）：回滚改动的键若在这五个读函数之外（例如 `pricing`），快照看不见；退出码非 0 时会判成「失败」而不是「已部分写入」。

### 七、四个入口怎么接

| 入口 | 文件 | 按钮 | 禁用条件 | 冒泡 | reload 转交 |
|---|---|---|---|---|---|
| 方案表 [删除…] | `pages/readonly1/roles-PresetsTable.tsx` | 非当前行：`Button variant="ghost" size="sm"`，`start({action:'preset.remove', args:{name}})`；**不传 title** | 当前行照旧只写「当前方案不能删」，不渲染按钮 | 表格行不可点；点 [删除…] 不展开也不收起差异面板（用例断言 `onDiff` 没被调） | 已有 `reload` |
| profile 表 [删除] | `pages/readonly1/roles-ProfilesTable.tsx` | `Button variant="ghost" size="sm"`，`start({action:'profile.remove', args:{profile: id}})`；[编辑] 照旧是 `DisabledAction` | 无（被引用由内核拒绝，界面不预先禁用） | 行不可点 | 加 `reload?` prop，由 `roles-RolesView.tsx` 转交 |
| 运行时 [删除…] | `pages/readonly1/runtimes-RuntimesView.tsx` | `Button variant="ghost" size="sm"`，`start({action:'runtime.remove', args:{runtime: id}})`；[探测]、[模型] 照旧禁用 | 无（被引用由内核拒绝） | 行不可点 | 加 `reload?` prop，由 `RuntimesPage.tsx` 转交 |
| 历史抽屉 [回滚到这一条之后] | `pages/readonly2/history-HistoryView.tsx` | `resource !== 'local'`：`Button variant="secondary" size="md"` 带 `RotateCcwIcon 16`，`start({action:'config.rollback', args:{number: String(number)}})`；`resource === 'local'`：`DisabledAction label="回滚到这一条之后" reason="本机文件不存快照，不能回滚" variant="secondary" size="md" icon={<RotateCcwIcon width={16} height={16} />}` | 只有本机文件条目禁用；**最新一条可点**（外部改动之后回滚到最新一条不是空操作）；本机文件优先，即使它也是最新一条 | 按钮在抽屉底栏，不在表格行里；点了不触发 `onRowOpen`，不改 `openNumber` 与 `selectedKey`；确认框开着时抽屉仍在、`h2` 仍是同一条 | 加 `reload?` prop，由 `HistoryPage.tsx` 转交 |

- 本机文件条目的提示文字是「本机文件不存快照，不能回滚」，**不是**「第二阶段接入」；T010 的 D09 只打开历史表第一行（`#42`，config 资源），所以这一条不与门禁相冲。
- 离线（`?mock=offline`）时四个入口照旧**可点**（同 A 片插件启停的口径）。
- 四个入口的 `useWriteFlow` 各自一份（每个组件自己调 `useWriteFlow(reload)`），一个组件里同时只跑一个流程。
- 成功之后：关框 → 弹轻提示 → 调 `reload()`（顺序照 A 片：`applyFinal` 里先 `setToast` 再 `resetFlow` 再 `reload`）；**重读之前不弹轻提示**（W3）。

### 八、必须保持的门禁与源码约束

- readonly1 / readonly2 的视图从 `../../api` **只许 `import type`**；调 `preview` 与写函数的代码只能放在 `desktop/web/src/writes/`（T009 的 `view_api_problems`）。
- 13 条动作说明只许出现在 `desktop/web/src/components/actionTitle.ts`；本片的确认框与轻提示文字写在 `src/writes/`。
- `desktop/web/src` 下不出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket`；`src/writes/write-flow.css` 只用既有 `--tt-*` 令牌，不许声明变量、不许写十六进制颜色与颜色函数（`npm run check:contract`）。
- 源码守卫（`desktop/web/tests/cleanup1-static.test.ts` 的 `TOUCHED` 含 `roles-PresetsTable.tsx` 与 `history-HistoryView.tsx`）：不写 `role="status"`、不写内联 style、不用 `matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`，字符串与注释里不写十六进制颜色与颜色函数。
- 计时相关的用例一律用假计时器；新用例的依赖注入照 A 片 `desktop/web/tests/writes-flow.test.tsx` 的写法（`vi.hoisted` + `vi.mock('../src/api')` 的 overrides 表，只替掉个别读函数）。
- 门禁 `tests/test_gate_t023_*.py` 由门禁端写，执行端不许碰。

### 九、兼容与不变

- A 片的四份 `desktop/web/tests/writes-*.test.*` 照旧全绿（流程、映射表、对话框、快照一字不改）。
- 13 个读函数、`?mock=` 的五种模式、读夹具一字不改。
- `desktop/web/src/components/index.ts` 不改；不新增页面文件；不新增 JSON 夹具。

## Steps
1. **读基线**：读 `desktop/web/src/api.ts`、`src/writes/useWriteFlow.ts`、`src/writes/WriteConfirmDialog.tsx`、`src/writes/snapshots.ts`、`src/writes/writeOutcome.ts`、`src/mock/writes.ts`、`src/pages/readonly1/roles-PresetsTable.tsx`、`roles-ProfilesTable.tsx`、`roles-RolesView.tsx`、`runtimes-RuntimesView.tsx`、`src/pages/readonly2/history-HistoryView.tsx`、`src/pages/RolesPage.tsx`、`RuntimesPage.tsx`、`HistoryPage.tsx`、`src/shell/PageFrame.tsx`、`src/shell/DisabledAction.tsx`、`src/components/Button.tsx`、`src/components/Dialog.tsx`、`src/components/actionTitle.ts`、`src/mock/{presets,profiles,runtimes,roles,history}.json`、`desktop/web/tests/writes-flow.test.tsx`、`desktop/web/tests/page-app.test.tsx`、`desktop/web/tests/readonly2-app.test.tsx`、`desktop/web/tests/readonly2-history.test.tsx`、`desktop/web/tests/page-runtimes.test.tsx`；确认本合同的符号与形状一致，**不一致就停下报告，不要照抄本文的行号**。
   - 验收：Repository facts 每一项都能对上；目的：不按旧行号改代码；风险：低。
2. **`api.ts` 与 `mock/writes.ts`**：第一节的 `WriteAction` 与四个写函数；第二节的确认号与参数核对；第三、四节的 `in-use` 情景与基础 argv。
   - 验收：`npm run typecheck` 通过；新用例里 api 段（命令含对的对象与编号、确认号对不上返回 409）；T022 的 S02、S16 照过（只查包含）；风险：碰 T006 `LATER_API`。
3. **`snapshots.ts` 四个投影**（第六节）。
   - 验收：`desktop/web/tests/writes-snapshots-b.test.ts`（每个投影两类用例：只改被排除的字段仍相同；改比较的字段就不同；回滚段专门改 history 与 runtime 的 `source`/`command`，断言仍相同）；风险：把会自己变的字段拿来比。
4. **`useWriteFlow.ts` 与 `WriteConfirmDialog.tsx`**：第四节的 `titleOf` / 摘要 / `successTextOf`（文字写在 `src/writes/`）；`danger` 标志与 Footer 的 `variant={danger ? 'danger' : 'primary'}`；`readSnapshot` 按四个新 action 分支；`confirm` 按 action 调四个新写函数（`rollback` 传 `Number(args.number)`）。**状态机与映射表一行不改**。
   - 验收：`desktop/web/tests/writes-remove.test.tsx`、`desktop/web/tests/writes-rollback.test.tsx`（四种 action 的确认框标题、[确认…] 的 `data-variant="danger"`、A 片三种仍是 `primary`）；A 片四份 `writes-*` 照跑；风险：改坏 A 片。
5. **接四个入口**（第七节），`reload` 经 `RolesPage → roles-RolesView → roles-ProfilesTable`、`RuntimesPage → RuntimesView`、`HistoryPage → HistoryView` 转交。
   - 验收：页面用例（三种删除可点、样式照旧、点按钮不冒泡、回滚时抽屉仍在且条目不变）；风险：既有门禁对样式与白名单的要求。
6. **改五份既有测试**（Repository facts 最后一条列的五处）：`page-app.test.tsx`（角色页 12→9、运行时页 9→6、总览 0，用例名照实际清单改）、`readonly2-app.test.tsx`（历史抽屉禁用按钮由 ['回滚到这一条之后'] 改成空数组；可用按钮白名单补「回滚到这一条之后」）、`page-runtimes.test.tsx`（[删除…] 可点、其余仍禁用）、`readonly2-history.test.tsx`（#8 的回滚钮可点且样式不变；#4 仍禁用、提示是「本机文件不存快照，不能回滚」）、`page-roles.test.tsx`（只断言 [编辑] 禁用，按理不用改；真要改只改那一条）。只改这几条断言，不删用例、不削弱别的断言。
   - 验收：`npm test` 全绿；风险：漏改会让既有用例红。
7. **写三个新测试文件**：`desktop/web/tests/writes-remove.test.tsx`（三种删除 + api 段）、`desktop/web/tests/writes-rollback.test.tsx`（回滚与历史抽屉）、`desktop/web/tests/writes-snapshots-b.test.ts`（四个投影）。不出现 skip/only/todo。
   - 验收：第八节变异表里每条都有用例杀掉；风险：新写法与 A 片的注入方式不一致。
8. **跑检查并写报告**：跑 Setup 与 Validation commands 的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下报告。
   - **两条硬规矩**：
     1. **遇到合同与既有测试（或门禁）冲突时**：不要越界改范围外的文件。把冲突写进执行报告的 `contract_conflicts`（哪一处、合同/门禁要求什么、实际是什么），然后继续做合同范围内能做的部分；不许为了让检查变绿去改 `tests/test_gate_*`、A 片的四份 `writes-*` 用例，或改 `desktop/web/src/api.ts` 的注释来迁就门禁的解析。
     2. **临时文件**：不许写到 `/tmp` 这类固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`；测试草稿用完立刻删掉，别留在候选里。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t023_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`node node_modules/typescript/bin/tsc --noEmit` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`^$`
- V02（必要）：`node node_modules/vitest/vitest.mjs run` · cwd：desktop/web · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run check:contract` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`契约检查：通过`
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：1200s · 期望退出码：0 · 输出须匹配：`built in`

## Definition of done
- D01：`api.ts` 新增且只新增 `removePreset`、`removeProfile`、`removeRuntime`、`rollback` 四个写函数与 `WriteAction` 的四个新成员；13 个读函数、A 片的四个写函数与既有类型一字未改；`desktop/web/src` 下仍不出现那四个联网词；证据：V01、V02、G01；目的：读侧不动是新旧两片并存的前提。
- D02：四个新写函数的确认号与参数核对生效——号不存在、action 不符或 args 不符时返回 409 且 `exit_code` 为 null（显示「确认已失效」），确认号与对象都对时按 200 走完；证据：V02；目的：杀掉「删错对象、rollback 用错编号、确认号传错」。
- D03：四个新 action 的确认框标题、变化区摘要与成功轻提示逐字照第四节（标题与轻提示一律写在 `src/writes/`，入口文件里一个字都不许写这 13 条动作说明）；证据：V02、G01；目的：T013 的「动作说明只有一份」与 T022 的「文字在 writes/ 里」两条同时守住。
- D04：四个新 action 的 [确认…] 在所有状态都是 `variant="danger"`，A 片三个 action 仍是 `variant="primary"`；证据：V02；目的：删除与回滚的确认按钮用危险样式（UI 设计 7.11）。
- D05：四个入口可点并走同一条流程——点入口只弹确认框；方案表点 [删除…] 不调 `onDiff`；历史抽屉点回滚钮不关抽屉、不换条目（`h2` 与 `selectedKey` 不变）；入口按钮样式照门禁（方案表与 profile 表 ghost/sm、运行时 ghost/sm、回滚 secondary/md + RotateCcwIcon 16）；证据：V02、R01、G01；目的：接上写入口而不破既有门禁。
- D06：本机文件条目（`resource === 'local'`）的回滚钮禁用，悬停提示是「本机文件不存快照，不能回滚」；**最新一条可点**；证据：V02、G01；目的：快照不存在的条目不许回滚，最新一条不是空操作。
- D07：成功只在重读之后才说——重读兑现之前整页没有「已删除…」/「已回滚…」；重读之后弹对应轻提示、关框、并调一次 `reload()`；证据：V02；目的：W3 是这一片的核心红线。
- D08：成功之后那一行真的从表里消失——用组件级用例注入 `reload`（或替掉的读函数）让那一行消失，断言 `reload` 被调一次、行不见了；证据：V02；目的：杀掉「成功之后不重读，删掉的行还留在表里」。
- D09：确认框里（`[role="dialog"]` 元素内）不出现「没有变化」这个子串；最新一条回滚时变化区写「预览没有列出变化」；抽屉底栏那句「这是最新的一条，回滚后没有变化」照旧在抽屉里；证据：V02；目的：W3b 的口径与断言的落点。
- D10：四个新 action 的快照只比参与比对的字段——只改被排除的字段（含 `getHistory` 整份、runtime 的 `source`/`command`、preset 的 `description`/`roles`、profile 的 runtime/provider/model/options/credential_env）仍判定相同；改比较的字段就判定不同；证据：V02；目的：杀掉「快照把会自己变的字段也拿来比」。
- D11：`in-use` 的三种内核原文照第五节逐字；执行后是「失败」并带原因标签「内核拒绝」，对话框里有内核原文，**不出现**「成功」与「已部分写入」，Toast 区为空；证据：V02；目的：杀掉「还被引用、删不掉」显示成成功。
- D12：回滚成功后历史抽屉仍开着、仍是同一条（`reload` 不卸载子组件）；确认框开着时抽屉仍在、`h2` 不变；证据：V02；目的：确认框与抽屉两层互不干扰。
- D13：既有测试只照新行为改那几条断言——`page-app.test.tsx` 的写入口个数（角色页 9、运行时页 6、总览 0）、`readonly2-app.test.tsx` 的抽屉禁用按钮与可用按钮白名单、`page-runtimes.test.tsx` 的 [删除…] 可点、`readonly2-history.test.tsx` 的最新一条可点与本机文件条目禁用；没有删除、跳过或弱化任何既有用例；A 片四份 `writes-*` 照旧全绿；证据：V02、review；目的：既有测试是别的片的契约，不能借机削弱。
- D14：所有修改都在允许集合内（新增文件都在 `allowed_new_files`，没有删文件，依赖与锁文件没动，`forbidden_paths` 里的门禁文件、`history-logic.ts`、`components/index.ts`、`mock/*.json` 一个都没动）；证据：scope；目的：越界改文件会让范围检查直接判负。
- D15：遇到合同与既有测试或门禁冲突时，执行端没有越界改范围外的文件（冲突写进执行报告的 `contract_conflicts`）；临时文件没有写到 `/tmp` 这类固定路径（用 `T=$(mktemp -d)` 并在同一条命令里删掉）；证据：review、scope；目的：上一轮 T022 的 attempt-001 就是在这两处出的问题。

D15 附带的变异对照（每条都要有用例杀掉）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| B1 | 删除或回滚的 [确认…] 不用 danger | remove 与 rollback 用例断言 `data-variant="danger"`；A 片三种断言 `primary` |
| B2 | 点入口冒泡（触发行的动作、关掉或换掉历史抽屉） | 方案表用例断言 `onDiff` 没被调；回滚用例断言抽屉仍在、`h2` 与 `selectedKey` 不变 |
| B3 | 本机文件条目也能点回滚 | rollback 用例：local 条目的按钮 disabled、提示是「本机文件不存快照，不能回滚」 |
| B4 | 最新一条的回滚被禁用；或确认框里出现「没有变化」 | rollback 用例：最新一条可点；确认框元素文字不含「没有变化」 |
| B5 | 重读之前就弹「已删除」 | 延后重读（deferred）的用例：重读兑现之前整页没有「已删除」 |
| B6 | 成功之后不重读，删掉的那一行还在表里 | 组件级用例：注入 reload，断言 `reload` 被调一次、行消失 |
| B7 | 快照把会自己变的字段也拿来比（含 `getHistory`、runtime 的 `source`/`command`） | `desktop/web/tests/writes-snapshots-b.test.ts` |
| B8 | `in-use` 显示成成功或已部分写入 | `in-use` 用例：对话框有内核原文与「内核拒绝」，没有「成功」与「已部分写入」，Toast 区为空 |
| B9 | 四个写函数的确认号或参数传错（删错对象、rollback 用错编号） | mock 的确认号核对 + 用例断言执行之后不是「确认已失效」，且命令里对象与编号正确 |
| B10 | A 片的流程与四个旧写函数被改坏 | 照跑 A 片的 `writes-dialog`、`writes-flow`、`writes-outcome`、`writes-snapshots` 四份 + T022 门禁 |
| B11 | 标题或轻提示写进 readonly1 / readonly2 | T013 门禁（13 条动作说明的唯一来源）+ 新用例断言入口文件里没有这 13 条 |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `WriteSpec` 的形状变了、`PageFrame` 的 `children` 第二个参数不是 `reload`、`Button` 没有 `danger` 变体、`DisabledAction` 没有 `reason`）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/test_gate_*`、A 片的四份 `writes-*` 用例、`desktop/web/src/components/index.ts`、`desktop/web/src/mock/*.json`、`history-logic.ts`、`docs/**`、`ts/**`）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要让 [删除…] 在界面上预先按「被引用」禁用）。
- 达到单轮时限（本版单次 3600 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；累计已用 0 次，本版至少留 2 次 attempt）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 14400（累计已用 0 秒，余 14400 秒 ≥ 2 倍单次时限，留足返工）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与核对事实 10 分钟；实现（api.ts 与 mock/writes、snapshots、useWriteFlow 与确认框）30 分钟；接四个入口 15 分钟；改五份既有测试 10 分钟；写三个新测试文件 25 分钟；必要检查（V01–V04、R01、G01）15 分钟；最终报告 5 分钟；总计 110 分钟，不超过单次时限。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D15，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：11 条变异各自由哪条用例杀掉、`?write=` 的 20 个情景对四个新 action 的实测结局、四个入口的最终写法（按钮标签、样式、禁用条件、冒泡）、快照四张投影的字段与排除字段、五份既有测试改后的断言与最终计数、`git diff --stat` 里**没有**任何 `tests/test_gate_*`、A 片的 `writes-*` 用例、`history-logic.ts`、`components/index.ts`、`mock/*.json`、`npm run check:contract` 与 `npm run build` 的输出。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件；这一项不许留空。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（既有测试只照新行为改那几条断言）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/test_gate_*`、A 片的四份 `desktop/web/tests/writes-*.test.*`、`desktop/web/src/components/index.ts`、`desktop/web/src/mock/*.json`、`desktop/web/src/pages/readonly2/history-logic.ts`、`desktop/web/src/App.tsx`、`desktop/web/src/main.tsx`、`docs/**`、`ts/**`、`scripts/**`；不在 `desktop/web/src` 下写那四个联网词；不新增页面文件、不新增 JSON 夹具、不改依赖与锁文件。
- 不把确认框标题、轻提示与 `in-use` 的内核原文写进 readonly1 / readonly2（这 13 条动作说明与内核原文只许出现在 `src/writes/` 与 `src/mock/`）。
