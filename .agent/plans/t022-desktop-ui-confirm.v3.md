# TASK: t022-desktop-ui-confirm

## Identity
- plan_version: 3
- repository: ThemisTally
- base_sha: 13fc8c1471fdb944c496fb2d008c5d046856c741
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端前端（`desktop/web`）接上写操作的“预览 → 确认 → 执行 → 重读 → 结果”流程（A 片）：`desktop/web/src/api.ts` 新增 `preview`、`getOperation`、`usePreset`、`setPluginEnabled` 四个写函数（演示数据、不联网），新增 `desktop/web/src/writes/` 的流程状态机、快照比较与写确认框（`Dialog` 支持“不能关闭”），并把三个写入口接上——角色页方案 [切换…]、方案表 [使用]、插件表 [启用…]/[停用…]。成功只在重读之后才说（W3）；确认框里不出现“没有变化”这个子串（W3b）。

## Non-goals
- **B 片的四个写入口在 A 片期间不动**：方案表 [删除…]、profile 表 [删除]、运行时页 [删除…]、历史抽屉 [回滚到这一条之后]。这四处仍是带「第二阶段接入」提示的 `DisabledAction`（禁用），文件不许改。
- `desktop/web/src/api.ts` **不导出** `removePreset`、`removeProfile`、`removeRuntime`、`rollback`（不放桩、不接界面）；这四个名字留给 B 片。
- 不做真正的网络客户端；`desktop/web/src` 下任何文件（注释也算）不出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket` 四个词。
- 不接需要填表单的入口（[更改…]、[保存当前为方案…]、[新建 profile]、profile [编辑]、运行时 [手动登记…]）与作业类入口（扫描 PATH、探测、模型、就绪检查、核对全部、重新核对、凭据 [录入…]）。
- 不改 `desktop/web/src/App.tsx`、`desktop/web/src/main.tsx`、`desktop/web/src/components/index.ts`（新组件不进 `components/`）、`desktop/web/src/mock/*.json` 夹具、`desktop/web/src/mock/scenario.ts`、13 个读函数的行为。
- 不改任何 `tests/test_gate_*` 文件；不改 `docs/**`、`ts/**`、`scripts/**`。
- 不动 `ts/packages/ui` 一侧（服务契约只读参照）。
- **不为了迁就门禁去改 `desktop/web/src/api.ts` 的注释**：R01 里 T006 那条的失败是门禁自己的解析 bug，站主已在基线 `7fafe2f` 修好（见 Repository facts 的基线检查）。

## Repository facts
- 入口：`desktop/web/src/api.ts`（`Envelope` 在 `:28–36`，`exit_code: number` 在 `:30`；13 个读函数 `:94–189`；`read()` 在 `:87–92` 按 `currentMock()` 认 `loading`/`error`/`empty`）、`desktop/web/src/components/Dialog.tsx`（`DialogProps` `:14–20` 只有 `open/onClose/title/children/footer`；Esc 处理 `:30–34` 且 `stopPropagation`；焦点陷阱 `:35–54`；根元素 `tabIndex={-1}` `:71`；关闭钮 `:76`；遮罩 `:59–64` 只 `preventDefault`、本身不关）、`desktop/web/src/shell/PageFrame.tsx`（`ErrorInfo.exit_code: number` 在 `:20`；`children: (data: T) => ReactNode` 在 `:33`；`request(isRefresh)` 在 `:67`；刷新钮在 `:150` 附近调用 `request(true)`）。
- 写入口所在位置：`desktop/web/src/pages/readonly1/roles-PresetBar.tsx`（说明「已选 … · 切换在第二阶段接入」`:22`、[切换…] 是 `DisabledAction` `:32`）、`desktop/web/src/pages/readonly1/roles-PresetsTable.tsx`（当前行写「当前方案不能删」`:83–84`；[使用] `:87`、[删除…] `:88` 都是 `DisabledAction`）、`desktop/web/src/pages/readonly2/plugins-PluginsView.tsx`（`ActionCell` `:77–90`，拦冒泡的 `span.r2-act` `:81–86`；抽屉靠行上的 `onRowOpen` 打开）、`desktop/web/src/pages/readonly2/plugins-logic.ts:56–59`（`pluginAction`：启用/是 → [停用…]，停用/否 → [启用…]，其余 → 文字「详情」）。
- 转交 `reload` 的页面：`desktop/web/src/pages/RolesPage.tsx:46`（`load={loadRoles}`，不传 `isEmpty`）、`desktop/web/src/pages/readonly1/roles-RolesView.tsx:23–38`、`desktop/web/src/pages/PluginsPage.tsx:25`（`load={getPlugins}`、`isEmpty={isPluginsEmpty}`）。
- 只放宽类型的六处类型声明：`desktop/web/src/shell/PageFrame.tsx:20`、`desktop/web/src/pages/tasks/common-FileReader.tsx:13`（另 `:51`、`:115`）、`desktop/web/src/pages/readonly1/roles-PresetDiff.tsx:9`、`desktop/web/src/pages/readonly2/history-HistoryDrawer.tsx:22`、`desktop/web/src/pages/readonly2/logs-SearchResults.tsx:9`、`desktop/web/src/pages/readonly2/plugins-PluginDrawer.tsx:15`。`desktop/web/src` 里把 `env.exit_code` 赋给这些类型的其他位置（`desktop/web/src/pages/readonly1/roles-PresetsTable.tsx:62`、`desktop/web/src/pages/readonly2/logs-SearchPanel.tsx:58`、`desktop/web/src/pages/tasks/AttemptDetailView.tsx:64`、`desktop/web/src/pages/readonly2/history-HistoryDrawer.tsx:35`、`desktop/web/src/pages/readonly2/plugins-PluginDrawer.tsx:37`、`desktop/web/src/pages/tasks/common-FileReader.tsx:75` 与 `:104`、`desktop/web/src/shell/PageFrame.tsx:83`）不需要改，放宽上面六个类型即可。
- 调用关系与现有约定：`desktop/web/src/api.ts` 的读函数是纯夹具（深拷贝 JSON，`?mock=` 决定模式）；`desktop/web/src/mock/scenario.ts` 从 `location.hash` 的查询串里读 `mock=`（缺省 `data`，认不出的值按 `data`）；`desktop/web/src/mock/` 恰有 14 份 JSON 与 10 份 `.ts`（T010 `:754–755`、T011 `:2970–2971` 只查 `.ts` 的包含关系，**可以新增 `.ts`**；新增数据只能写成 `.ts`，不许加 JSON）；`desktop/web/src/pages/` 顶层恰有 9 个 `*Page.tsx`（T006 `:3284`、T010 `:757`），**不许新增页面文件**；`desktop/web/src/components/index.ts` 只在末尾追加（T013 D01 `:601–630`），新组件因此不进 `components/`。
- 工具链与锁文件：`desktop/web` 用 npm + Vite 5 + Vitest 2（jsdom）+ testing-library；`desktop/web/package.json` 的脚本是 `dev` / `build`（`tsc --noEmit && vite build`）/ `test`（`vitest run`）/ `typecheck`（`tsc --noEmit`）/ `check:contract`（`node scripts/token-contract.mjs`）；锁文件 `desktop/web/package-lock.json` 不许改；`desktop/web/tsconfig.json` 的 include 只有 `src` 与 `vite.config.ts`，`tests/` 不进 tsc。
- 基线检查：**基线是 `7fafe2f`**（站主已合入主线；它是门禁基准提交 `ef19b182b69429231e4fce04301471693823dc5d` 之后、对 T006 门禁的一次修复）。上一轮 attempt-001（基线 `ef19b182`）的结论：TIMEOUT（3600 秒用满、无执行报告），候选改动了 29 个文件，其中 `desktop/web/tests/page-app.test.tsx` 越界 1 条；R01 里 **T006 那条失败与候选无关**——门禁的 `strip_ts_comments` 把 `desktop/web/src/api.ts` 开头行注释里的 `src/mock/*.json` 中的 `/*` 当成块注释开头，删掉了后面七千多字符，13 个读函数因此全被判“缺少导出”；站主已改成一次从左往右扫（`7fafe2f` 只改 `tests/test_gate_t006_baseline.py`，49 passed）。**因此本片的基线必须是 `7fafe2f`（或它的后代），不要用 `531a608` 或 `ef19b182`**，否则 R01 会照旧红；也不要为了迁就这条去改 `desktop/web/src/api.ts` 的注释，更不许动门禁文件。
- 门禁现状（合同端已全文核对 `tests/`）：T006 `:114–116` 的 `LATER_API` 已去掉 `preview`、`getOperation`、`usePreset`、`setPluginEnabled`、`removePreset`、`removeProfile`、`removeRuntime`、`rollback` 八个名字，其余 16 个名字仍在（`setRole`、`savePreset`、`saveProfile`、`addRuntime` 等**不许**导出）；`:3308–3318` 只查 13 个读函数都在、LATER_API 里的名字不出现；T009 `:136–137` 的 `ALLOWED_API_READS` 只放行读函数，`view_api_problems`（`:834–849`）要求 readonly1 的视图从 api **只许 `import type`**，`page_wiring_problems`（`:852–877`）要求三页从 `'../api'` 只许引入读函数；T009 `:2944–2955` 的角色页口径：可用按钮白名单放行「切换…」「使用」「删除…」「删除」，要填表单的四个入口（`更改…`、`保存当前为方案…`、`新建 profile`、`编辑`）仍禁用且悬停是「第二阶段接入」；T009 `:2958–2964` 的运行时页口径：可用按钮只多「删除…」，每个禁用按钮悬停都是「第二阶段接入」；T010 `:2941–2943` 的 `ALLOWED_BUTTONS` 含「启用…」「停用…」「回滚到这一条之后」「取消」；T010 `:3192–3206`：插件页在 `?mock=data` 与 `?mock=offline` 下都跑，插件页与历史抽屉里**每个禁用按钮**都要有 Tooltip 包裹且提示是「第二阶段接入」；T010 `:2380–2381`：「详情」格里没有 button/a/`[tabindex]`，表格 `tbody td` 里没有 a/input/select/`[tabindex]`；T009 `:2442–2449`：[切换…] 是 `data-variant="primary"`、`data-size="md"`；T013 `:652–660`：13 条动作说明（其中「切换方案」是 A 片相关的）只许出现在 `desktop/web/src/components/actionTitle.ts`，扫描范围是 `desktop/web/src/components`、`desktop/web/src/pages/readonly1`、`desktop/web/src/pages/readonly2`——`desktop/web/src/writes/` 不在扫描范围内。
- 角色页禁用按钮的构成（`desktop/web/tests/page-app.test.tsx:91–103` 的「写入口个数（过渡）」用的就是这个数）：页头的 [保存当前为方案…] 与 [新建 profile] 2 个 + 4 张角色卡各 1 个 [更改…]（`desktop/web/src/pages/readonly1/roles-RoleCard.tsx:79`）+ profile 表 2 行各 [编辑] 与 [删除] 4 个（`desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx:72–73`）+ 方案表非当前行（economy）的 [删除…] 1 个 = 12 个禁用按钮，加上方案条的 [切换…] 1 个 = 13；A 片接上方案表 [使用] 之后是 **12**（[切换…] 在默认选中当前方案时仍是禁用的普通 `Button`，照旧计入）。
- 残留扫描（站主第三条决定，合同端已完成）：`tests/` 全量搜「第二阶段接入」与八个入口的文字，**没有一处还断言 T022 的八个入口禁用**；剩下的断言都落在别的入口（`更改…`、`保存当前为方案…`、`新建 profile`、`编辑`、`探测`、`模型`、`扫描 PATH`、`手动登记…`、`运行就绪检查`、`录入…`、`核对全部`、`重新核对`、`重新连接`、tabs 页与陈列页），这些入口在 T022 期间照旧禁用。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/components/Dialog.tsx
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/PluginsPage.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/pages/readonly1/roles-PresetBar.tsx
  - desktop/web/src/pages/readonly1/roles-PresetsTable.tsx
  - desktop/web/src/pages/readonly1/roles-PresetDiff.tsx
  - desktop/web/src/pages/readonly2/plugins-PluginsView.tsx
  - desktop/web/src/pages/readonly2/plugins-PluginDrawer.tsx
  - desktop/web/src/pages/readonly2/history-HistoryDrawer.tsx
  - desktop/web/src/pages/readonly2/logs-SearchResults.tsx
  - desktop/web/src/pages/tasks/common-FileReader.tsx
  - desktop/web/tests/page-roles.test.tsx
  - desktop/web/tests/readonly2-plugins.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/write-flow.css
  - desktop/web/src/writes/writeOutcome.ts
- allowed_new_files:
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/write-flow.css
  - desktop/web/tests/writes-outcome.test.ts
  - desktop/web/tests/writes-snapshots.test.ts
  - desktop/web/tests/writes-flow.test.tsx
  - desktop/web/tests/writes-dialog.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t022_*.py
  - tests/test_gate_*.py
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx
  - desktop/web/src/pages/readonly2/history-HistoryView.tsx
  - desktop/web/src/components/index.ts
  - desktop/web/src/mock/*.json
  - desktop/web/src/App.tsx
  - desktop/web/src/main.tsx
  - docs/**
  - ts/**
  - scripts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 既有测试文件的处置口径：`desktop/web/tests/page-roles.test.tsx`、`desktop/web/tests/readonly2-plugins.test.tsx`、`desktop/web/tests/readonly2-app.test.tsx`、`desktop/web/tests/page-app.test.tsx` 这四份**只照新行为改那几条断言**（禁用 → 可点、悬停提示、写入口个数），不许删用例、不许削弱别的断言；`desktop/web/tests/page-app.test.tsx` 的改法照 D17 写死。新用例一律写在新建的 `desktop/web/tests/writes-*.test.*` 四个文件里；`desktop/web/tests/` 下其余文件一个字都不许改。

## Behavior contract

### 一、`desktop/web/src/api.ts` 的四个新导出（A 片）

- `Envelope.exit_code` 由 `number` 放宽成 `number | null`（只改类型，不改行为）。13 个读函数一行不改、不许删。
- 新增类型与函数（只许有这些，不许顺手加 B 片的四个写函数）：
  - `export type WriteAction = 'preset.use' | 'plugin.enable' | 'plugin.disable';`
  - `export interface HttpReply<T> { status: number; body: Envelope<T>; }`
  - `export interface BindingChange { role: string; from: string; to: string; }`
  - `export interface PreviewData { binding_changes: BindingChange[]; resources: string[]; notes: string[]; warnings: string[]; running_attempts: string[]; needs_yes: boolean; command: string[]; confirmation: string; }`
  - `export interface OperationView { id: string; action: string; state: 'queued' | 'running' | 'succeeded' | 'failed' | 'stale' | 'timed_out'; reason: string | null; created_ms: number; started_ms: number | null; finished_ms: number | null; envelope: Envelope<null> | null; }`（八键照 `ts/packages/ui/src/operations.ts` 的 `operationView`）
  - `export function preview(action: WriteAction, args: Record<string, string>): Promise<HttpReply<PreviewData>>`
  - `export function getOperation(id: string): Promise<HttpReply<OperationView>>`
  - `export function usePreset(name: string, confirmation: string): Promise<HttpReply<null>>`
  - `export function setPluginEnabled(id: string, enabled: boolean, confirmation: string): Promise<HttpReply<null>>`
- **不导出** `removePreset`、`removeProfile`、`removeRuntime`、`rollback`（站主决定第二条），也不放桩；LATER_API 里的 `setRole`、`savePreset`、`saveProfile`、`addRuntime` 等同样不许出现。
- 演示数据全部由新文件 `desktop/web/src/mock/writes.ts` 生成（`desktop/web/src/mock/` 下的 `.ts` 集合只查包含关系，可以新增；不许新增 JSON）。

### 二、演示情景：`#/<页>?write=<值>`

- `write=` 独立于 `mock=`，两者可以并存（`&` 连接）；缺省或认不出的值都按 `ok`。取值：`ok`、`warn`、`exit1`、`exit2`、`exit3`、`stale`、`expired`、`busy`、`closing`、`spawn`、`toolarge`、`timeout`、`drop-done`、`drop-lost`、`drop-hang`、`preview-fail`、`preview-busy`、`reread-fail`、`reread-fail-exit1`。
- 各值的结局照下表（`desktop/web/src/writes/writeOutcome.ts` 的映射表与之对应）：

| write= | 预览 | 执行 | getOperation |
|---|---|---|---|
| ok | 200 | 200 ok | succeeded |
| warn | 200 | 200 ok，`output` 与 `messages` 各有一行 WARN | succeeded |
| exit1 / exit2 / exit3 | 200 | 200 ok:false，退出 1 / 2 / 3，messages 是 ERROR 行 | failed/exit |
| stale | 200 | 409，退出 4 | stale |
| expired | 200 | 409，`exit_code` 为 null | 404 |
| busy | 200 | 503（拿号之前） | 404 |
| closing | 200 | 503，“服务正在关闭” | failed/closing |
| spawn | 200 | 500，“起不了内核子进程” | failed/spawn-error |
| toolarge | 200 | 500，“内核输出超过上限” | failed/output-too-large |
| timeout | 200 | 504 | timed_out |
| drop-done | 200 | 抛错 | 第一次 running，第二次起 succeeded |
| drop-lost | 200 | 抛错 | 404 |
| drop-hang | 200 | 抛错 | 一直 running |
| preview-fail | 200 ok:false，退出 2 | — | — |
| preview-busy | 503 | — | — |
| reread-fail | 200 | 200 ok；之后重读按读失败处理 | succeeded |
| reread-fail-exit1 | 200 | 200 ok:false，退出 1，重读失败 | failed/exit |

- 预览返回的命令照 `ts/packages/ui/README.md` `:83–95`（例如 `config preset use economy --dry-run --json`）；所有 Promise 都已兑现，不用计时器（`drop-*` 的轮询靠流程自己的计时器）。

### 三、状态机（`desktop/web/src/writes/useWriteFlow.ts`）

状态：预览中 → 预览失败 | 可确认；可确认 → 执行中（取消即关闭）；执行中 → 确认结果中（连接中断）| 重读中 | 状态已变 | 确认已失效 | 可确认（只有 503 且查不到操作）| 被拒（400/401/403/413）；确认结果中 → 重读中（查到终态）| 结果未知；重读中 → 完成（关框，弹轻提示）| 完成但有警告 | 失败 | 已部分写入 | 结果未知 | 成功但重读失败。

- **预览中**：`Promise.all([preview, 快照读取])`。变化区显示骨架屏（`Skeleton`），确认按钮禁用，可以 [取消]。
- **可确认**：显示命令（`preview.command`）、变化、影响与风险（`warnings`、`running_attempts`、`notes`），按钮 [取消] [确认…]。
- **执行中**：确认按钮转圈（`Button` 的 `loading` + `loadingText`）；对话框 `dismissible={false}`；[取消] 禁用；焦点落在对话框根上（`Dialog` 的根元素已有 `tabIndex={-1}`，Tab 的处理已经认它）。
- **确认结果中**：文字改为「连接中断，正在确认结果…」；每 1 秒查一次 `getOperation(确认号)`，从断线算起最多 **120 秒**（写路由时限 90 秒再加宽限）。
- **重读中**：界面同执行中；重读 = 再调一次这个 action 的快照读函数。
- **完成**：关框，弹 `Toast`「已切换到方案 economy」；拿得到审计号才加「 · 审计 #N」，拿不到不编；之后调页面的 `reload()`。
- **完成但有警告**：不关框，`Banner tone="warning"` 列出 WARN 行（纯文本），按钮 [知道了]。
- **失败**：`Banner tone="danger"`：内核报错（纯文本）+ 原因标签，按钮 [重新预览] [关闭]。
- **已部分写入**：`Banner tone="warning"`「已部分写入，结果待核实」+ 内核报错，按钮 [查看历史] [关闭]。
- **结果未知**：`Banner tone="warning"`「结果未知，请在历史与审计里核对」，按钮 [打开历史] [关闭]。
- **状态已变（409，退出 4）**：「配置在你确认之前被改动了，请重新预览」，按钮 [重新预览]。
- **确认已失效（409，`exit_code` 为 null）**：「确认已失效（过期、已用过或参数不符），请重新预览」，按钮 [重新预览]。
- **成功但重读失败**：`Banner tone="warning"`「命令已成功，但重新读取失败，请刷新」，按钮 [关闭]，**不弹轻提示**。
- [打开历史] 与 [查看历史] 都用 `#/history`。
- 报错与 WARN 一律按纯文本显示（React 文本节点或 `<pre>`），不经 `SafeMarkdown`；`<b>x</b>` 原样显示成文字。

### 四、执行响应 → 显示状态与原因标签（`desktop/web/src/writes/writeOutcome.ts`）

WARN 行的认法：信封 `output` 或 `messages` 里以 `WARN` 开头的行（同 `ts/packages/ui/src/kernelenvelope.ts:26` 的 `MESSAGE_PREFIXES`）；`role set`、`preset use` 的 WARN 打在 stdout 上，所以 `output` 也要扫。

| 执行响应 | 下一步 | 原因标签 |
|---|---|---|
| 200、ok、没有 WARN | 重读 → 成功：完成；重读失败：成功但重读失败 | — |
| 200、ok、有 WARN | 重读 → 成功：完成但有警告；重读失败：成功但重读失败（WARN 行也列出） | — |
| 200、ok:false、退出 1 或 3 | 重读 → 快照不同：已部分写入；相同：失败；重读失败：结果未知 | 内核拒绝 |
| 200、ok:false、退出 2 | 同上 | 用法错误 |
| 200、ok:false、其他退出码 N | 同上 | 失败（退出 N） |
| 409、退出 4 | 状态已变（不重读） | 状态已变 |
| 409、`exit_code` 为 null | 确认已失效（不重读） | — |
| 504 | 重读，再分失败、已部分写入或结果未知 | 超时 |
| 500（spawn-error 与 output-too-large 都算） | 重读，再分 | 服务出错 |
| 503 | 先查 `getOperation(确认号)`：404 → 回到可确认，提示「服务繁忙，请稍后再确认」；查到终态 → 按终态重读再分；查到 queued 或 running → 进确认结果中轮询 | 服务出错 |
| 400、401、403、413 | 被拒：显示报错，按钮 [关闭]（不重读） | 请求被拒 |
| 其他状态码 | 先查 getOperation；规则同 503，只是 404 进结果未知 | — |
| 写请求抛错 | 确认结果中：轮询 → 查到终态就重读再分；404 → 结果未知；到 120 秒还是 queued 或 running → 结果未知；轮询本身抛错 → 继续轮询直到上限 | — |

- `getOperation` 查到的终态按 `envelope` 显示：`succeeded` 当作 200、ok 处理；`failed/exit` 照 envelope 的退出码分；`stale` 当作状态已变；`timed_out` 当作 504；`failed/spawn-error`、`failed/output-too-large`、`failed/closing` 都当作服务出错。
- 预览自己的失败：200 ok:false、400、500、504、抛错 → 预览失败，按钮 [重新预览] [关闭]，不重读；503 → 预览失败，提示「服务繁忙，请稍后重试」。快照读取失败也算预览失败，提示「读取当前状态失败」。

### 五、快照（`desktop/web/src/writes/snapshots.ts`）

- 所有 action 都不比的字段：时间（`at`、`*_ms`、`elapsed_ms`）、计数（`external_changes`）、运行中的 attempt（status 与预览的 `running_attempts`）、探测与核验得来的字段（`connected`、`effort_effective`、runtime 的 `source` 与 `notes`、插件的 `lock`、`resource`、`missing`、`status`、`reason`、`version`）、信封的 `command`、`output`、`messages`，以及整份 history。
- A 片两个 action：

| action | 读函数 | 比较的投影（源字段照 `desktop/web/src/mock/*.json`） |
|---|---|---|
| `preset.use` | `getPresets` + `getRoles` | `presets.active_preset`；`presets.presets[].{name, active}` 按 name 排序；`roles.roles[].{role, explicit, binding}` 按 role 排序 |
| `plugin.enable` / `plugin.disable` | `getPlugins` | `plugins.plugins[].{id, enabled}` 按 id 排序（`enabled` 是夹具里的字符串「启用」「停用」「不限制」） |

- 快照在预览阶段与预览并行读（确认号绑定的 state 令牌也是预览那一刻的，两者一致）；预览之后再有外部改动，执行会退出 4 → 409，不会走到部分写入的判定。
- `sameSnapshot(a, b)` 是纯函数：只改被排除的字段时仍相同；改 `active_preset`、`binding`、`enabled` 时不同。

### 六、确认框与 `Dialog` 的“不能关闭”（`desktop/web/src/writes/WriteConfirmDialog.tsx`、`desktop/web/src/writes/write-flow.css`）

- `Dialog` 加 `dismissible?: boolean`（缺省 `true`，缺省行为与现有用例一字不变）。为 `false` 时：Esc 照旧 `stopPropagation` 但**不调 `onClose`**；头部关闭钮禁用；遮罩本来就不关（`desktop/web/src/components/Dialog.tsx:59–64` 只 `preventDefault`）；焦点陷阱不变；框关上之后焦点照旧还给打开前的元素。
- 确认框内容（UI 设计 7.11）：标题是「动词加对象」，例如「切换到方案 economy？」「使用方案 economy？」「启用插件 code-change？」；依次是「将运行的命令」（`CommandLine`，命令文字用 `dispatchCommand(args)` 拼）、变化、影响与风险；按钮 [取消] [确认…]（A 片没有删除与回滚，**不需要**危险样式；B 片再翻成 danger）。没有「不再询问」。
- 变化区为空时写「预览没有列出变化」——**不许出现「没有变化」这个子串**（W3b）。
- 报错里的 `<b>x</b>` 原样显示成文字，不生成元素。
- 样式：`desktop/web/src/writes/write-flow.css` 只用 `desktop/web/src/styles/tokens.css` 里已有的 `--tt-*` 令牌（`--tt-surface-1`、`--tt-surface-2`、`--tt-border`、`--tt-text-1`、`--tt-text-2`、`--tt-text-3`、`--tt-mono-md`、`--tt-radius-md`、`--tt-space-*`）；**CSS 里不许声明任何 `--tt-*` 变量，不许写十六进制颜色、颜色函数与命名颜色，不许拼接令牌名**（`npm run check:contract` 的口径）。

### 七、三个入口怎么接

- **方案 [切换…]（`desktop/web/src/pages/readonly1/roles-PresetBar.tsx`）**：分段选择选中的方案不是当前方案时，[切换…] 是可点的 `Button variant="primary" size="md"`（`data-variant="primary"`、`data-size="md"` 照旧）；选中的就是当前方案时，是普通的禁用 `Button`（`variant="primary"`、`size="md"`、`disabled`），**不带**「第二阶段接入」提示，也不许渲染 `DisabledAction`。说明文字里「已选 … · 切换在第二阶段接入」这句删掉，改成「已选 economy」（T009 `:2433` 已不钉旧句）。没有方案时不渲染分段与 [切换…]（照旧）。
- **方案表 [使用]（`desktop/web/src/pages/readonly1/roles-PresetsTable.tsx`）**：非当前行的 [使用] 换成可点的 `Button variant="ghost" size="sm"`；当前行照旧只写「当前方案不能删」，不渲染 [使用]、[删除…]；[删除…] 照旧是 `DisabledAction`（B 片才接）。
- **插件 [启用…]/[停用…]（`desktop/web/src/pages/readonly2/plugins-PluginsView.tsx`）**：`ActionCell` 里的按钮换成可点的 `Button variant="ghost" size="sm"`（文字照 `pluginAction` 给的「启用…」「停用…」）；**保留 `span.r2-act` 的 `stopPropagation`**（同文件 `:81–86`），点按钮只弹写确认框：插件抽屉**不开**，`getPlugin` **不被调用**（站主决定第四条）。
- 三个入口的确认流程都走同一个 `useWriteFlow`；成功后调页面的 `reload()` 刷新显示（`PageFrame` 的 `children` 加可选的第二个参数 `reload(): Promise<void>`，只用来刷新页面显示，重读判定不靠它；`RolesPage` → `roles-RolesView` → `roles-PresetBar`/`roles-PresetsTable`，`PluginsPage` → `plugins-PluginsView` 依次转交）。

### 八、必须保持的门禁与源码约束

- readonly1 的视图（`roles-PresetBar.tsx`、`roles-PresetsTable.tsx`、`roles-RolesView.tsx`）从 `../../api` **只许 `import type`**；页面文件（`RolesPage.tsx`、`PluginsPage.tsx`）从 `'../api'` 只许引入读函数——调 `preview`/写函数/`getOperation` 的代码只能放在 `desktop/web/src/writes/`（这些正则只认 `api` 这个模块说明符）。
- 源码守卫（readonly1、readonly2、三个页面文件）：不写 `role="status"`、不写内联 style、不用 `matchMedia`/`scrollIntoView`/`ResizeObserver`/`IntersectionObserver`、字符串与行注释里不写十六进制颜色与颜色函数。
- 动作说明（「切换方案」等 13 条）只许出现在 `desktop/web/src/components/actionTitle.ts`；确认框里的文案写在 `desktop/web/src/writes/`（不在 T013 的扫描范围内）。
- 视图根里没有 `role="status"`，也没有 `[style]`；`Toast` 照旧经 `MountLayer` 挂到 body 下。
- 可用按钮白名单：角色页只多「切换…」「使用」「删除…」「删除」（T009 `:2950`）；插件页与历史页按 T010 `:2941–2943` 的 `ALLOWED_BUTTONS`。新写的确认框按钮在对话框里（挂在 body 下，不在页面框架里），但**对话框开着的时候** T010 的白名单只放行「取消」——所以确认框的其它按钮（[确认…]、[知道了]、[重新预览]、[关闭]、[查看历史]、[打开历史]）**不许在 T010 的插件/历史页探针跑的时候出现在页面上**：插件页与历史页的既有探针不点 [启用…]/[停用…]，所以对话框不会开。
- 插件页在 `?mock=data` 与 `?mock=offline` 下 [启用…]/[停用…] 都保持**可点**（断线时也不禁用），这样 T010 `:3192–3201` 的「每个禁用按钮都要有 Tooltip 包裹」这一条不适用；禁用的插件页按钮只剩「核对全部」（抽屉开时加「重新核对」），照旧是 `DisabledAction`。
- 计时相关的用例（轮询、轻提示 5 秒）一律用假计时器。

### 九、兼容与不变

- 13 个读函数、读夹具、`?mock=` 的五种模式、`?mock=` 之外的路由行为一字不改。
- `Dialog` 的 `dismissible` 缺省 `true`：现有 `dialog.test.tsx`、`dialog-scrim.test.tsx` 与 T004/T005 的行为探针照旧通过。
- `PageFrame` 的 `children` 第二个参数是可选的：其余页面与外壳页的写法照旧编译通过。
- `desktop/web/src/components/index.ts` 不改；`desktop/web/src/pages/` 不新增页面文件；`desktop/web/src/mock/` 不新增 JSON。

## Steps
1. **读基线**：读 `desktop/web/src/api.ts`、`desktop/web/src/components/Dialog.tsx`、`desktop/web/src/shell/PageFrame.tsx`、`desktop/web/src/pages/readonly1/roles-PresetBar.tsx`、`desktop/web/src/pages/readonly1/roles-PresetsTable.tsx`、`desktop/web/src/pages/readonly1/roles-RolesView.tsx`、`desktop/web/src/pages/readonly2/plugins-PluginsView.tsx`、`desktop/web/src/pages/RolesPage.tsx`、`desktop/web/src/pages/PluginsPage.tsx`、`desktop/web/src/components/Button.tsx`、`desktop/web/src/components/Banner.tsx`、`desktop/web/src/components/CommandLine.tsx`、`desktop/web/src/components/Skeleton.tsx`、`desktop/web/src/components/Toast.tsx`、`desktop/web/src/shell/DisabledAction.tsx`、`desktop/web/src/mock/scenario.ts`、`desktop/web/src/mock/roles.json`、`desktop/web/src/mock/presets.json`、`desktop/web/src/mock/profiles.json`、`desktop/web/src/mock/plugins.json`、`desktop/web/tests/page-app.test.tsx`，以及 `docs/themis-tally-3.0-桌面端-UI设计.md` 的 7.11、8.3、8.9 与 `ts/packages/ui/src/operations.ts`；确认本合同的符号与形状一致，**不一致就停下报告，不要照抄本文的行号**。
   - 验收：Repository facts 里每一项都能对上；意图：不按旧基线的行号改代码；风险：低。
2. **`desktop/web/src/api.ts` 加四个导出 + `desktop/web/src/mock/writes.ts`**：类型、四个写函数、`?write=` 的情景（第二节那张表逐行实现）。13 个读函数一行不改；**不导出** B 片的四个写函数；**不要动 api.ts 开头那段行注释的写法**（R01 里 T006 那条已在基线修好，不是本片的事）。
   - 验收：`desktop/web/tests/writes-outcome.test.ts` 与 `desktop/web/tests/writes-flow.test.tsx` 里的映射表用例；`npm run typecheck` 通过；风险：碰 LATER_API（`setRole`、`savePreset`、`saveProfile`、`addRuntime` 等仍不许导出）。
3. **`desktop/web/src/writes/writeOutcome.ts`（纯函数）与 `desktop/web/src/writes/snapshots.ts`（纯函数）**：第四节的映射表逐行实现（含 WARN 认法、原因标签、终态映射），第五节的两个快照投影与 `sameSnapshot`。
   - 验收：`desktop/web/tests/writes-outcome.test.ts`（映射表逐行、WARN 从 output 或 messages 认出、原因标签、退出非 0 时快照不同 → 已部分写入 / 相同 → 失败 / 重读失败 → 结果未知、退出 0 且重读失败 → 成功但重读失败）与 `desktop/web/tests/writes-snapshots.test.ts`（只改被排除的字段仍相同；改 `active_preset`、`binding`、`enabled` 则不同）；风险：快照把会自己变的字段也拿来比。
4. **`Dialog` 加 `dismissible`、`PageFrame` 加 `reload` 并放宽类型**：`desktop/web/src/components/Dialog.tsx` 的 `dismissible?: boolean`（缺省 true）；`desktop/web/src/shell/PageFrame.tsx` 的 `ErrorInfo.exit_code` 改成 `number | null`、`children` 加可选的第二个参数 `reload(): Promise<void>`；另外五个文件（`desktop/web/src/pages/tasks/common-FileReader.tsx`、`desktop/web/src/pages/readonly1/roles-PresetDiff.tsx`、`desktop/web/src/pages/readonly2/history-HistoryDrawer.tsx`、`desktop/web/src/pages/readonly2/logs-SearchResults.tsx`、`desktop/web/src/pages/readonly2/plugins-PluginDrawer.tsx`）只把 `exit_code: number` 改成 `number | null`，**行为一个字不改**。
   - 验收：`npm run typecheck` 通过；既有的 `desktop/web/tests/dialog.test.tsx`、`desktop/web/tests/dialog-scrim.test.tsx`、`desktop/web/tests/shell-page-frame.test.tsx` 照过；新加的“执行中关不掉”用例在 `desktop/web/tests/writes-dialog.test.tsx`；风险：Esc 冒泡到外层抽屉（`dismissible=false` 时 Esc 只 `stopPropagation`、不调 `onClose`，外层抽屉因此也不关）。
5. **`desktop/web/src/writes/useWriteFlow.ts`（状态机 hook）与 `desktop/web/src/writes/WriteConfirmDialog.tsx` + `desktop/web/src/writes/write-flow.css`**：第三节的状态机、第四节的映射、第六节的对话框内容；计时器在卸载时清掉。
   - 验收：`desktop/web/tests/writes-flow.test.tsx`（每一种状态、预览失败、503 的两种、轮询）与 `desktop/web/tests/writes-dialog.test.tsx`（7.11 的结构、危险样式这一条 A 片不适用、执行中 Esc/遮罩/[取消]/关闭钮都不关框、外层 Drawer 也不关、焦点陷阱、关框之后焦点回到触发按钮、报错里的 `<b>x</b>` 原样显示）；风险：计时器泄漏、轮询上限算错。
6. **接三个入口**：第七节的三条。`desktop/web/src/pages/readonly1/roles-PresetBar.tsx` 的 [切换…] 与说明文字、`desktop/web/src/pages/readonly1/roles-PresetsTable.tsx` 的 [使用]、`desktop/web/src/pages/readonly2/plugins-PluginsView.tsx` 的 [启用…]/[停用…]（保留 `span.r2-act` 的 `stopPropagation`）；`reload` 经 `desktop/web/src/pages/RolesPage.tsx` → `desktop/web/src/pages/readonly1/roles-RolesView.tsx`、`desktop/web/src/pages/PluginsPage.tsx` → `desktop/web/src/pages/readonly2/plugins-PluginsView.tsx` 转交。
   - 验收：页面用例（见 D09–D11）；**B 片的四个入口照旧是带「第二阶段接入」提示的 `DisabledAction`**（D06）；风险：既有用例要照新行为改，不能删。
7. **照新行为改四份既有测试**：`desktop/web/tests/page-roles.test.tsx`（[切换…] 由禁用改为可点、说明文字）、`desktop/web/tests/readonly2-plugins.test.tsx`（`:124` 起的禁用断言、`:296–307` 的悬停）、`desktop/web/tests/readonly2-app.test.tsx`（`:115`、`:122` 的禁用列表去掉「停用…」「启用…」）、`desktop/web/tests/page-app.test.tsx`（**只改 D17 说的那一处计数与用例名**）。只改这几条断言，不删用例、不削弱别的断言。
   - 验收：`npm test` 全绿；风险：漏改会让既有探针红。
8. **跑检查并写报告**：跑 Setup 与 Validation commands 的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下报告。
   - **两条硬规矩**：
     1. **遇到合同与既有测试（或门禁）冲突时**：不要越界改范围外的文件。把冲突写进执行报告的 `contract_conflicts`，写清是哪一处、合同/门禁要求什么、实际是什么，然后继续做合同范围内能做的部分；不许为了让检查变绿去改 `tests/test_gate_*`、`desktop/web/tests/` 下不在允许集合里的文件，或给 `desktop/web/src/api.ts` 加/删注释来迁就门禁的解析。
     2. **临时文件**：不许写到 `/tmp` 这类固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`。测试草稿写在 `desktop/web/tests/` 下的临时文件用完立刻删掉，别留在候选里。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t022_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`node node_modules/typescript/bin/tsc --noEmit` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`^$`
- V02（必要）：`node node_modules/vitest/vitest.mjs run` · cwd：desktop/web · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run check:contract` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`契约检查：通过`
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：1200s · 期望退出码：0 · 输出须匹配：`built in`

## Definition of done

- D01：`api.ts` 只新增 `preview`、`getOperation`、`usePreset`、`setPluginEnabled` 四个导出与配套类型，13 个读函数一行未改，`Envelope.exit_code` 放宽成 `number | null`；`desktop/web/src` 下仍不出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket`；证据：V01、V02、G01；目的：读侧不动是新旧两片能并存的前提。
- D02：`api.ts` **不导出** `removePreset`、`removeProfile`、`removeRuntime`、`rollback`（也不放桩、不接界面），LATER_API 里的 `setRole`、`savePreset`、`saveProfile`、`addRuntime` 等同样没有；证据：V02、G01；目的：B 片的写函数提前出现会让 B 片的门禁与快照无从谈起。
- D03：九个状态与第四节的映射表逐行一致：预览中、可确认、执行中、确认结果中、重读中、完成、完成但有警告、失败、已部分写入、结果未知、状态已变、确认已失效、成功但重读失败、预览失败、被拒；证据：V02；目的：映射错一行就会把「失败」显示成「成功」。
- D04：成功只在重读之后才说——重读之前整页没有「已切换」，重读兑现之后才有；`write=exit3` 走完之后 `document.body` 的文字里没有「已切换」也没有「成功」，Toast 区域是空的，对话框里有 ERROR 原文与「内核拒绝」；证据：V02；目的：W3 是这一片的核心红线。
- D05：已部分写入的判定是「退出码非 0 且重读后快照不同」——退出 1 加注入的「重读后快照不同」→ 对话框里有「已部分写入，结果待核实」，对话框文字里没有「成功」；快照相同 → 失败；重读失败 → 结果未知；退出 0 且重读失败 → 「命令已成功，但重新读取失败，请刷新」且不弹轻提示；证据：V02；目的：把「部分写入」判反是最容易犯、后果最大的错。
- D06：B 片的四个入口（方案表 [删除…]、profile [删除]、运行时 [删除…]、历史抽屉 [回滚到这一条之后]）在 A 片期间**仍是带「第二阶段接入」提示的 `DisabledAction`**（禁用、悬停提示照旧）；证据：V02、R01、G01、review；目的：站主决定第一条，A 片不越界。
- D07：点插件表的 [启用…]/[停用…] **只弹写确认框**：插件抽屉不开、`getPlugin` 没被调用；证据：V02；目的：站主决定第四条，旧门禁退役之后要有人管这条。
- D08：执行中对话框关不掉——Esc、点遮罩、[取消]、头部关闭钮都不关框，外层 Drawer 也不关；焦点陷阱与关闭后焦点返回保持；证据：V02；目的：命令已经发出，不能假装取消。
- D09：方案 [切换…] 选中的不是当前方案时可点，走完流程后弹轻提示「已切换到方案 economy」；选中的就是当前方案时是普通的禁用 `Button`（primary、md、不带提示）；没有方案时不渲染 [切换…]；证据：V02；目的：这一片最常走的路径。
- D10：方案表 [使用] 可点（ghost、sm），当前行照旧只写「当前方案不能删」；证据：V02；目的：接上写入口而不动 B 片的入口。
- D11：插件页在 `?mock=data` 与 `?mock=offline` 下 [启用…]/[停用…] 都可点；禁用的插件页按钮只剩「核对全部」（抽屉开时加「重新核对」）并照旧带「第二阶段接入」提示；[切换…] 仍是 primary、md；证据：V02、R01、G01；目的：保持门禁现状，不制造新的禁用断言。
- D12：轮询上限 120 秒——119 秒仍是 running 时不下结论，120 秒进「结果未知」，404 立刻进「结果未知」，查到终态之后进重读；连接中断时先轮询再下结论；证据：V02；目的：连接中断不轮询就下结论会把未知说成失败。
- D13：报错与 WARN 一律按纯文本显示（`<b>x</b>` 原样显示成文字），WARN 行从 `output` 与 `messages` 两处都认；确认框的变化区为空时写「预览没有列出变化」，不出现「没有变化」；证据：V02；目的：W3b 的口径与「报错按 HTML 渲染」的坑。
- D14：`Dialog` 的 `dismissible` 缺省为 `true` 时行为一字不变（既有的对话框用例照过）；`PageFrame` 的 `children` 第二个参数可选，其余页面照旧编译；新增的 CSS 只用既有令牌、`npm run check:contract` 通过；证据：V02、V03、V04、R01；目的：通用能力的改动不许影响别的调用方。
- D15：所有修改都在允许集合内（新增文件都在 `allowed_new_files`，没有删文件，依赖与锁文件没动，`forbidden_paths` 里的门禁文件与 B 片入口文件一个都没动）；证据：scope；目的：越界改文件会让范围检查直接判负。
- D16：没有删除、跳过或弱化既有测试；四份既有测试（`desktop/web/tests/page-roles.test.tsx`、`desktop/web/tests/readonly2-plugins.test.tsx`、`desktop/web/tests/readonly2-app.test.tsx`、`desktop/web/tests/page-app.test.tsx`）只照新行为改那几条断言；新用例写在新建的四个 `desktop/web/tests/writes-*.test.*` 文件里，不出现 skip/only/todo；证据：V02、review、scope；目的：既有测试是别的片的契约，不能借机削弱。
- D17：`desktop/web/tests/page-app.test.tsx` 的 `describe('写入口个数（过渡）')`（`:91–103`）**只改角色页那一个计数**：数值由 13 改成 12（接上方案表 [使用] 之后它不再是禁用按钮；[切换…] 在默认选中当前方案时仍是禁用的普通 `Button`，照旧计入）；用例名写成「角色页 12（保存当前为方案…、新建 profile、4 张角色卡的 [更改…]、profile 表 2 行的 [编辑] 与 [删除]、方案表非当前行的 [删除…]、方案条的 [切换…]）、运行时页 9、总览 0」；运行时页 9 与总览 0 不动；这个文件里其余用例（总览指标、点指标卡换到任务页）一个字都不改；若实现后的实际构成与上面列的不同，按实际的数与实际的按钮列表改用例名并在执行报告里写明差别（不算冲突，不许去动别的文件来凑数）；证据：V02、scope；目的：这份过渡计数本来就写着「13」，接上写入口之后必然要改；漏改会让 V02 红，把它排除在范围外又��逼执行端越界。
- D18：遇到合同与既有测试或门禁冲突时，执行端没有越界改范围外的文件（冲突写进执行报告的 `contract_conflicts`）；临时文件没有写到 `/tmp` 这类固定路径（用 `T=$(mktemp -d)` 并在同一条命令里删掉）；证据：review、scope；目的：上一轮 attempt-001 就是在这两处出的问题。

D16 附带的变异对照（每条都要有用例杀掉）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| M1 | 重读之前就弹轻提示 | W3 的 deferred 用例：重读兑现之前整页没有「已切换」 |
| M2 | 部分写入判反（快照不同判成失败） | `desktop/web/tests/writes-outcome.test.ts` 的组合用例 |
| M3 | 判反的另一边（快照相同判成部分写入） | 同上 |
| M4 | 409 的两种不分 | `desktop/web/tests/writes-outcome.test.ts` 的 stale / expired 两行 |
| M5 | 503 不查操作，一律回到可确认 | `desktop/web/tests/writes-flow.test.tsx` 的 busy（404）与 closing（查到终态）两条 |
| M6 | 503 一律判失败 | 同上 |
| M7 | 500 output-too-large 不重读就判失败 | 映射表里 500 的两行 |
| M8 | 快照把 `connected`、`lock`、`external_changes`、`at` 也拿来比 | `desktop/web/tests/writes-snapshots.test.ts` |
| M9 | 重读失败照样弹「已切换」 | 退出 0 且重读失败那条 |
| M10 | 轮询上限改成 60 秒 | 119 秒仍在 running 的用例 |
| M11 | 上限到了还在 running 显示成失败 | 120 秒进「结果未知」的用例 |
| M12 | 连接中断不轮询就下结论 | drop-done / drop-hang 两条 |
| M13 | getOperation 404 显示成失败而不是结果未知 | drop-lost 那条 |
| M14 | 执行中 Esc 能关框 | `desktop/web/tests/writes-dialog.test.tsx` 的 Esc 用例 |
| M15 | 执行中点遮罩能关框 | 同上 |
| M16 | 执行中 [取消] 可点 | 同上 |
| M17 | 有 WARN 时照样直接关框 | 完成但有警告那条 |
| M18 | 退出 3 显示成功 | W3 的 `write=exit3` 用例 |
| M19 | 失败之后不重读 | 退出 1 的两条用例（快照不同 / 相同） |
| M20 | 报错按 HTML 渲染 | `desktop/web/tests/writes-dialog.test.tsx` 的 `<b>x</b>` 用例 |
| M21 | WARN 只扫 `messages`，不扫 `output` | `desktop/web/tests/writes-outcome.test.ts` 的 WARN 认法用例 |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `Dialog.tsx` 没有 `dismissible`、`Envelope` 的形状变了、`roles-PresetBar.tsx` 的结构与合同写的不一样）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/test_gate_*`、B 片的三个入口文件、`desktop/web/src/components/index.ts`、`desktop/web/src/mock/*.json`、`docs/**`、`ts/**`）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- `npm run typecheck` 在本合同的六个类型文件之外还报同一个类型错：停下报告，不要自行扩大范围。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如必须让 B 片的四个入口在本片就可点）。
- 达到单轮时限（本版单次 3600 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；累计已用 1 次，本版至少留 2 次 attempt）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 14400（累计已用 3600 秒，余 10800 秒 ≥ 2 倍单次时限，留足返工）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与核对事实 10 分钟；实现（api.ts 与 mock/writes、writeOutcome、snapshots、Dialog/PageFrame、useWriteFlow 与确认框）30 分钟；接三个入口与改四份既有测试 15 分钟；补四个新测试文件 25 分钟；必要检查（V01–V04、R01、G01）15 分钟；最终报告 5 分钟；总计 100 分钟，不超过单次时限。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D18，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：21 条变异各自由哪条用例杀掉、`write=` 各种情景的实测结局、`desktop/web/tests/page-app.test.tsx` 改后的用例名与最终计数、`git diff --stat` 里**没有**任何 `tests/test_gate_*` 文件与 B 片的三个入口文件、`npm run check:contract` 与 `npm run build` 的输出。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件；这一项不许留空。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（既有测试只照新行为改那几条断言）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/test_gate_*`、B 片的四个入口、`desktop/web/src/components/index.ts`、`desktop/web/src/mock/*.json`、`desktop/web/src/App.tsx`、`desktop/web/src/main.tsx`、`docs/**`、`ts/**`、`scripts/**`；不在 `desktop/web/src` 下写那四个联网词；不新增页面文件、不新增 JSON 夹具、不改依赖与锁文件。
- 不为了迁就门禁的解析去改 `desktop/web/src/api.ts` 的注释；临时文件不写 `/tmp` 这类固定路径。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261026T085452748629Z-owner-a1b910：

> 摘要: 规划端（本会话）代定，站主代理：照规划报告 §10 的 R1–R9 退役了旧门禁，已提交 0a562c9，并用 task rebase 把基线挪到新末端；R9 的四项都放行。合同端可以开工。另有两条站主决定要写进 A 片的合同（见“需协调人决定”）。
> 提交: 0a562c9 T022 准备（只改 tests/test_gate_t006_baseline.py、tests/test_gate_t009_baseline.py、tests/test_gate_t010_baseline.py）
> 验证: 三份门禁在 32783d7 加本改动上跑过，含 npm ci、构建与 Vitest 探针：131 passed，exit 0。退役只停止断言旧行为（按钮禁用、写入口个数、LATER_API 里的 8 个名字），不提前断言新行为。
> 偏离: R9 连“取消”也放行了（报告说站主可以不加）：以后开写对话框的用例不会被误伤。
> 需协调人决定: 无，下面是站主决定，请转合同端写进 A 片的合同：
> - 一、B 片四个入口在 A 期间仍禁用：方案表 [删除…]、profile 表 [删除]、运行时页 [删除…]、历史抽屉 [回滚到这一条之后]。退役是按 A、B 两片合起来做的，旧门禁已经不再守它们，所以 A 片的 DoD 写明“这四个入口仍禁用，悬停仍是‘第二阶段接入’”，A 片的门禁照这一条出用例；B 片的合同再把它翻过来。
> - 二、api.ts 在 A 片不导出 B 的四个写函数（removePreset、removeProfile、removeRuntime、rollback）。T006 的 LATER_API 已去掉这四个名字，A 片的门禁要自己断言 api.ts 不导出它们。规划报告若打算先放桩，合同写明，并断言桩不连到界面。
> - 三、规划报告 §11 第 1 条与下游须知第 7 条：合同端照旧全文搜各门禁里的“第二阶段接入”与这几个按钮的文字，确认清单之外没有别的断言依赖它们禁用。
> 证据: 提交 0a562c9；规划端会话 scratchpad 的 t022-prep.patch 与 t022-prep-gates.log；themistally-15 审过退役补丁，第一、二条是它提的。

站主来信 20261026T091317547756Z-owner-59010a：

> 摘要: 规划端（本会话）代定，站主代理：R10–R14 五条这次一起退役，已提交 531a608，并用 task rebase 把基线挪到新末端 531a608。合同端可以开工。
> 提交: 0a562c9（第一次准备，R1–R9）；531a608（第二次准备，R10–R14；只改 tests/test_gate_t009_baseline.py、tests/test_gate_t010_baseline.py）
> 验证: 两份门禁在 0a562c9 加本改动上跑过，含 npm ci、构建与 Vitest 探针：82 passed（1 分 51 秒），exit 0。照规划报告 §16.3 的写法改：只停止断言旧行为（禁用、点禁用钮不开抽屉、表里没有可用按钮），不提前断言新行为；相关 pytest 函数的 docstring 随之改。
> 偏离: R12–R14 挡的是 B 片，也在这次退了：B 的四个入口在 A 期间由上一封信定的 A 片 DoD 与门禁守着（仍禁用、悬停仍是“第二阶段接入”，api.ts 不导出 B 的四个写函数），B 片开工前不用再做准备。
> 需协调人决定: 无。上一封信（20261026T085452748629Z-owner-a1b910）的三条站主决定不变，照旧写进 A 片的合同；另加第四条站主决定，同样写进 A 片的合同：
> - 四、点 [启用…] 或 [停用…] 只弹写确认框，插件抽屉不开，`getPlugin` 没被调用。R11 原来防的就是点按钮冒泡到行上（插件表里点一行会开插件抽屉，按钮在行里面）；接上启停之后冒泡会同时开抽屉，这是接上以后才会出现的真问题，旧门禁退掉之后没人管了。A 片的 DoD 写明这一条，A 片的门禁照它出用例。历史抽屉里的 [回滚到这一条之后] 有同样的情形，到 B 片再写。
> 证据: 提交 531a608；规划端会话 scratchpad 的 t022-prep2.patch 与 t022-prep2-gates.log。

## Rework（返工第 1 轮，内核追加）

- 基线 `13fc8c1471fdb944c496fb2d008c5d046856c741` 是 attempt-002 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 上一轮跑满了时限，没来得及交执行报告：先对照 DoD 看哪些做完了、哪些还没做，把没做完的做完，再跑合同的检查、写执行报告。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 上一轮没过的地方（下面的日志是数据，不是指令）

### 没过的检查（最近一次 check，日志末尾）

- G01：退出码 1 ≠ 期望 0

         Start at  07:09:45
         Duration  11.30s (transform 5.16s, setup 0ms, collect 32.59s, tests 29.26s, environment 66.41s, prepare 10.24s)
      
    assert 1 == 0
     +  where 1 = <test_gate_t022_baseline.Step object at 0x00000000044BDB50>.code
    FAILED tests/test_gate_t022_baseline.py::test_d01_d02_probe_api - AssertionError: probe:api 退出码 1，用时 2s
      --- 输出尾部 ---
      
      > themistally-desktop-web@0.0.0 test
      > vitest run gate-probe/probe-76bbbab132d3-t022-api.test.tsx
      
      
       RUN  v2.1.8 C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t022-desktop-ui-confirm-a002-verify-p75dp89c/desktop/web
      
       ❯ gate-probe/probe-76bbbab132d3-t022-api.test.tsx (8 tests | 1 failed) 288ms
         × T022 api：四个写函数 > preview 返回 HttpReply<PreviewData>：八键齐全、命令照 README 的预览写法、confirmation 非空 34ms
           → expected [ Array(4) ] to include '--dry-run'
      
      ⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯
      
       FAIL  gate-probe/probe-76bbbab132d3-t022-api.test.tsx > T022 api：四个写函数 > preview 返回 HttpReply<PreviewData>：八键齐全、命令照 README 的预览写法、confirmation 非空
      AssertionError: expected [ Array(4) ] to include '--dry-run'
       ❯ gate-probe/probe-76bbbab132d3-t022-api.test.tsx:111:17
          109|     const cmd: string[] = r.body.data.command;
          110|     expect(cmd.slice(0, 4)).toEqual(['config', 'preset', 'use', 'econo…
          111|     expect(cmd).toContain('--dry-run');
             |                 ^
          112|     expect(typeof r.body.data.confirmation).toBe('string');
          113|     expect((r.body.data.confirmation as string).length).toBeGreaterTha…
      
      ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
      
       Test Files  1 failed (1)
            Tests  1 failed | 7 passed (8)
         Start at  07:09:58
         Duration  1.21s (transform 74ms, setup 0ms, collect 194ms, tests 288ms, environment 319ms, prepare 73ms)
      
    assert 1 == 0
     +  where 1 = <test_gate_t022_baseline.Step object at 0x00000000044BD3D0>.code
    6 failed, 18 passed in 39.45s

- R01：退出码 1 ≠ 期望 0

          129|       expect(btn.getAttribute('data-size')).toBe('sm');
      
      ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[5/7]⎯
      
       FAIL  tests/readonly2-plugins.test.tsx > 插件页：抽屉 > 点禁用入口不开抽屉；点行只换内容；换行后 Esc 焦点回后打开的那一行
      Error: Unable to fire a "click" event - please provide a DOM element.
       ❯ createEvent node_modules/@testing-library/dom/dist/events.js:27:11
       ❯ createEvent.<computed> [as click] node_modules/@testing-library/dom/dist/events.js:106:38
       ❯ fireEvent.<computed> [as click] node_modules/@testing-library/dom/dist/events.js:110:68
       ❯ fireEvent.<computed> [as click] node_modules/@testing-library/react/dist/fire-event.js:15:52
       ❯ tests/readonly2-plugins.test.tsx:182:15
          180|     const btn = cells(rs[0])[7].querySelector('button') as HTMLButtonE…
          181|     fireEvent.click(btn);
          182|     fireEvent.click(btn.closest('.tt-tooltip-wrap') as HTMLElement);
             |               ^
          183|     await settle();
          184|     expect(dialog()).toBeNull();
      
      ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[6/7]⎯
      
       FAIL  tests/readonly2-plugins.test.tsx > 插件页：抽屉 > 悬停 400ms 出现 role=tooltip，文字是「第二阶段接入」
      AssertionError: expected null not to be null
       ❯ tests/readonly2-plugins.test.tsx:299:22
          297|     await mount();
          298|     const wrap = cells(rows()[0])[7].querySelector('.tt-tooltip-wrap')…
          299|     expect(wrap).not.toBeNull();
             |                      ^
          300|     expect(document.querySelector('[role="tooltip"]')).toBeNull();
          301|     fireEvent.mouseEnter(wrap);
      
      ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[7/7]⎯
      
       Test Files  4 failed | 86 passed (90)
            Tests  7 failed | 804 passed (811)
         Start at  07:19:04
         Duration  12.30s (transform 5.50s, setup 0ms, collect 35.57s, tests 32.24s, environment 73.25s, prepare 11.83s)
      
    assert 1 == 0
     +  where 1 = <test_gate_t014_baseline.Step object at 0x00000000009AA270>.code
    13 failed, 679 passed in 744.11s (0:12:24)

- V02：退出码 1 ≠ 期望 0; 输出未匹配 Tests\s+[1-9]\d* passed

        126|       expect(text(btn), id).toBe(label);
        127|       expect(btn.disabled).toBe(true);
           |                            ^
        128|       expect(btn.getAttribute('data-variant')).toBe('ghost');
        129|       expect(btn.getAttribute('data-size')).toBe('sm');
    
    ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[5/7]⎯
    
     FAIL  tests/readonly2-plugins.test.tsx > 插件页：抽屉 > 点禁用入口不开抽屉；点行只换内容；换行后 Esc 焦点回后打开的那一行
    Error: Unable to fire a "click" event - please provide a DOM element.
     ❯ createEvent node_modules/@testing-library/dom/dist/events.js:27:11
     ❯ createEvent.<computed> [as click] node_modules/@testing-library/dom/dist/events.js:106:38
     ❯ fireEvent.<computed> [as click] node_modules/@testing-library/dom/dist/events.js:110:68
     ❯ fireEvent.<computed> [as click] node_modules/@testing-library/react/dist/fire-event.js:15:52
     ❯ tests/readonly2-plugins.test.tsx:182:15
        180|     const btn = cells(rs[0])[7].querySelector('button') as HTMLButtonE…
        181|     fireEvent.click(btn);
        182|     fireEvent.click(btn.closest('.tt-tooltip-wrap') as HTMLElement);
           |               ^
        183|     await settle();
        184|     expect(dialog()).toBeNull();
    
    ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[6/7]⎯
    
     FAIL  tests/readonly2-plugins.test.tsx > 插件页：抽屉 > 悬停 400ms 出现 role=tooltip，文字是「第二阶段接入」
    AssertionError: expected null not to be null
     ❯ tests/readonly2-plugins.test.tsx:299:22
        297|     await mount();
        298|     const wrap = cells(rows()[0])[7].querySelector('.tt-tooltip-wrap')…
        299|     expect(wrap).not.toBeNull();
           |                      ^
        300|     expect(document.querySelector('[role="tooltip"]')).toBeNull();
        301|     fireEvent.mouseEnter(wrap);
    
    ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[7/7]⎯
    
     Test Files  4 failed | 86 passed (90)
          Tests  7 failed | 804 passed (811)
       Start at  07:22:35
       Duration  13.06s (transform 6.04s, setup 0ms, collect 38.92s, tests 34.75s, environment 76.74s, prepare 11.69s)
