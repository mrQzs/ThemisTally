# TASK: t024-desktop-ui-forms

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: b222d975ced43b9c1f7d7bbfab1031a690eea6f4
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端前端（`desktop/web`）把「要填表单的写入口」里的两个接上 T022/T023 已有的写流程：`desktop/web/src/api.ts` 放宽写参数类型（新增 `WriteArgs`）并新增 `addProfile`、`editProfile` 两个写函数与 `profile.add`、`profile.edit` 两个 `WriteAction`；新增一个 profile 表单对话框（新建与编辑两用），底部实时显示内核预览（命令、警告、报错原文），[确认…] 交给 A 片确认框走「预览 → 确认 → 执行 → 重读 → 终态」；角色页页头 [新建 profile] 与 profile 表 [编辑] 变为可点；`?write=` 新增 `preview-warn` 与 `preview-invalid` 两个情景。

## Non-goals
- `runtime.add`、`role.set`、`preset.save` 三片不在本片：[更改…]、[保存当前为方案…]、[手动登记…] 照旧是 `DisabledAction`，禁用、悬停提示照旧是「第二阶段接入」。
- 所有作业类入口照旧禁用、悬停「第二阶段接入」：[扫描 PATH]、[探测]、[模型]、[运行就绪检查]、插件核对、凭据 [录入…]。
- 模型下拉由「列出模型」作业填充，本片只手填模型，旁边常显「手填的模型没有核实」。
- 不做真正的网络客户端；`desktop/web/src` 下任何文件（注释也算）不出现 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket`。
- 13 个读函数、T022/T023 的七个写函数（`preview`、`getOperation`、`usePreset`、`setPluginEnabled`、`removePreset`、`removeProfile`、`removeRuntime`、`rollback`）与既有类型的行为一字不改；`preview` 的参数类型只是**放宽**（`Record<string,string>` → `WriteArgs`），已有调用处与行为不变。
- T022/T023 的状态机、映射表、快照口径、W3/W3b 规矩不重新设计。
- 不改 `desktop/web/src/components/index.ts`、`desktop/web/src/mock/*.json`、`desktop/web/src/App.tsx`、`desktop/web/src/main.tsx`、`docs/**`、`ts/**`、`scripts/**`、任何 `tests/test_gate_*`；不新增页面文件（`src/pages` 顶层 `*Page.tsx` 的个数不变）、不新增 JSON 夹具、不改依赖与锁文件。

## Repository facts
- 入口与签名（`desktop/web/src/api.ts`）：`export type WriteAction`（七个成员：`preset.use`、`plugin.enable`、`plugin.disable`、`preset.remove`、`profile.remove`、`runtime.remove`、`config.rollback`）；`export function preview(action: WriteAction, args: Record<string, string>): Promise<HttpReply<PreviewData>>`；`usePreset(name, confirmation)`；`removePreset` / `removeProfile` / `removeRuntime` / `rollback`；13 个读函数 `getMeta`…`listSecrets`；类型 `Envelope`、`HttpReply`、`PreviewData`、`OperationView`。
- 写流程（`desktop/web/src/writes/`）：`useWriteFlow.ts`——`export interface WriteSpec { action: WriteAction; args: Record<string, string>; title?: string }`；`useWriteFlow(reload?)` 交出 `{ start(spec), flow }`；`titleOf` / `successTextOf` / `changeSummaryOf` / `dangerOf` / `readSnapshot` / `confirm`（按 action 分派写函数）/ `applyFinal`（先 `setToast` 再 `resetFlow` 再 `reload`）；`WriteConfirmDialog.tsx`——`ConfirmContent{command,changes,summary?,warnings,running,notes}`、`FlowView`、`FlowRender`、`WriteFlow`（对话框 + Toast）；`snapshots.ts`——`presetSnapshot` / `pluginSnapshot` / `presetRemoveSnapshot` / `profileRemoveSnapshot` / `runtimeRemoveSnapshot` / `rollbackSnapshot` / `sameSnapshot`；`writeOutcome.ts`——`classifyWrite`（400 → `rejected`）/ `classifyTerminal` / `finalFromReread` / `errorText` / `warnLines`。
- 演示数据（`desktop/web/src/mock/writes.ts`）：`WriteScenario` 现有 20 个值（`ok`、`warn`、`exit1`、`exit2`、`exit3`、`stale`、`expired`、`busy`、`closing`、`spawn`、`toolarge`、`timeout`、`drop-done`、`drop-lost`、`drop-hang`、`preview-fail`、`preview-busy`、`reread-fail`、`reread-fail-exit1`、`in-use`）；`baseArgv(action, args)`；`writeArgv`（加 `--expect-state=<state>`）；`opActions`（号 → action）与 `opArgs`（号 → `(action,args)`，只记 `NEW_ACTIONS` 里的 action）；`sameArgs`（现按字符串逐键比）；`confirmWrite`（号/action/args 不符 → 409 + `ERROR 确认号无效、已过期或已用过：请重新预览`）；`mockPreview`（`preview-fail` 是 200 + `ok:false` + 退出码 2；`preview-busy` 是 503）。
- 页面与入口：`desktop/web/src/shell/PageFrame.tsx`——`export interface PageFrameProps<T>` 里 `actions?: ReactNode`；`children: (data, reload) => ReactNode`；`reload()` 走 `request(true)`；页头按钮次序照 `actions` 里的次序，刷新钮在最后。
- `desktop/web/src/pages/RolesPage.tsx`：页头 `actions` 现在是 `<DisabledAction label="保存当前为方案…" />` 与 `<DisabledAction label="新建 profile" />`（次序照旧）。
- `desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx`：[编辑] 是 `<DisabledAction label="编辑" variant="ghost" size="sm" />`；本组件自己调 `useWriteFlow(reload)` 并渲染 `<WriteFlow flow={flow} />`；`reload?` prop 由上层转交。
- `desktop/web/src/shell/DisabledAction.tsx`：缺省 `variant='secondary'`、`size='md'`、`reason='第二阶段接入'`。
- 组件（`desktop/web/src/components/index.ts`）：**没有**标签输入组件；可用的是 `Button`、`Tag`、`TextField`（`label`/`help`/`error`/`mono`）、`Select`（`label`/`options[{value,label}]`/`help`/`error`）、`SegmentedControl`（`options`/`value`/`onChange`/`aria-label`，段是 `button role="radio"`）、`Dialog`（`open`/`onClose`/`title`/`footer`/`dismissible`；`open` 为假时**不渲染任何东西**，对话框经 `MountLayer` 挂到 body 下）、`Toast`。
- 服务侧口径（只读参照，`ts/packages/ui/src/writeroutes.ts`）：`WRITE_ACTIONS`——`profile.add` 必填 `profile`、`runtime`、`model`，可选 `thinking`、`credential_env`；`profile.edit` 必填 `profile`，可选 `runtime`、`model`、`thinking`、`credential_env`；`buildWriteArgv`——`profile.add` → `config profile add <id> --runtime=<r> --model=<m> [--thinking=<t>] [--credential-env=<n>]…`，`profile.edit` → `config profile edit <id> [--runtime=…] [--model=…] [--thinking=…] [--credential-env=…]…`（`--credential-env` 一项一个，按数组顺序）；`validModel`（在第一个 `/` 处切成两段，两段都过 `^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$`）；`validCredentialEnv`（非空数组，空数组不合法）。
- 内核原式（只读参照，`scripts/pi_dispatch.py`）：`TASK_ID_RE = ^[a-z0-9][a-z0-9-]{0,63}$`；`ENV_NAME_RE = ^[A-Za-z_][A-Za-z0-9_]{0,127}$`。
- 夹具（`desktop/web/src/mock/`）：`profiles.json` 两条（`step-high`：runtime `pi`、provider `bb`、model `step-5-preview`、thinking `high`、credential_env `["STEP_API_KEY"]`；`step-low`：thinking `low`）；`runtimes.json` 三条（`pi`、`claude-code`、`opencode`）。
- 门禁现状（已核 `tests/`）：
  - T009：页头按钮次序与文案是 `['保存当前为方案…', '新建 profile', '刷新']`（`tests/test_gate_t009_baseline.py:2369-2377`；[新建 profile] 禁用那条已退役）；profile 表 [编辑]、[删除] 两个按钮都要 `data-variant="ghost"`、`data-size="sm"`（`:2508-2516`；[编辑] 禁用那条已退役）；角色页可用按钮白名单是 `['切换…','使用','删除…','删除','新建 profile','编辑']`（`:2955`），仍要填表单的入口只有 `['更改…','保存当前为方案…']` 且悬停必须是「第二阶段接入」（`:2957-2959`）；页面（`RolesPage` 等）从 `../api` 只许调读函数（`:857-882`），readonly1 视图从 `../../api` 只许 `import type`（`:839-854`）。
  - T022：页面与 readonly1 视图（`RolesPage.tsx`、`PluginsPage.tsx`、`roles-PresetBar.tsx`、`roles-PresetsTable.tsx`、`roles-RolesView.tsx`）的源码里**不许出现** `preview`、`getOperation`、`usePreset`、`setPluginEnabled` 四个词（`tests/test_gate_t022_baseline.py:352-357`，注释也算）；`components/index.ts` 不许引用 `src/writes/`（`:330`）；`src/mock/` 的 JSON 份数与 `src/pages` 顶层页面个数不变（`:332-336`）；api 探针的 `FORBIDDEN`（`:500-502`）里没有 `addProfile` / `editProfile`，但有 `saveProfile`、`addRuntime`、`setRole`、`savePreset`（新写函数不许用这四个名字）。
  - T023：入口文件（`src/pages/readonly1`、`src/pages/readonly2` 整个目录，加 `RolesPage.tsx`、`RuntimesPage.tsx`、`HistoryPage.tsx`）里不许出现「删除方案」「删除 profile」「删除运行时」「回滚配置」「已删除」「已回滚」等字样（`tests/test_gate_t023_baseline.py:93-101`、`:336-349`）；S07 仍要求 `roles-ProfilesTable.tsx` 自己调 `useWriteFlow(` 并保留 `reload?:`（`:285-288`）。
  - T013：`desktop/web/src/components/actionTitle.ts` 是 13 条动作说明的唯一来源；扫描范围是 `src/components`、`src/pages/readonly1`、`src/pages/readonly2`（`tests/test_gate_t013_baseline.py:657-664` 与 `desktop/web/tests/cleanup1-static.test.ts:77-79`）；所以 `roles-ProfilesTable.tsx`（含注释）里不许出现「新建 profile」「修改 profile」。
  - 静态扫描：`cleanup1-static.test.ts` 的 `SCANNED` 只含 `components`、`readonly1`、`readonly2`；`page-static.test.ts:7-29` 是固定清单，含 `pages/readonly1/roles-ProfilesTable.tsx`，**不含** `src/writes/`。`src/writes/` 下的新文件不受这两份扫描约束，但仍受 W4（只用既有 `--tt-*` 令牌、不写十六进制颜色与颜色函数）与「不出现那四个联网词」约束。
- 工具链与锁文件：`desktop/web` 用 npm + Vite 5 + Vitest 2（jsdom）+ testing-library；脚本 `dev` / `build`（`tsc --noEmit && vite build`）/ `test`（`vitest run`）/ `typecheck` / `check:contract`（`node scripts/token-contract.mjs`）；`desktop/web/package.json` 与 `package-lock.json` 不许改；`tsconfig.json` 的 include 只有 `src` 与 `vite.config.ts`（`tests/` 不进 tsc）。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/tests/page-roles.test.tsx
  - desktop/web/tests/page-app.test.tsx
- allowed_new_files:
  - desktop/web/src/writes/profileRules.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/profile-form.css
  - desktop/web/tests/writes-profile-form.test.tsx
  - desktop/web/tests/writes-profile-api.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t024_*.py
  - tests/test_gate_*.py
  - desktop/web/src/components/index.ts
  - desktop/web/src/mock/*.json
  - desktop/web/src/App.tsx
  - desktop/web/src/main.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - docs/**
  - ts/**
  - scripts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 既有测试文件的处置口径：`desktop/web/tests/page-roles.test.tsx` 与 `desktop/web/tests/page-app.test.tsx` **只照新行为改那几条断言**（[编辑] 由禁用改成可点且仍是 ghost/sm；角色页禁用按钮个数 9→6、用例名照改）；T022/T023 的七份 `desktop/web/tests/writes-*.test.*` 一个字都不许改；`desktop/web/tests/` 下其余文件一个字都不许改；新用例一律写在新建的两份 `desktop/web/tests/writes-profile-*.test.*` 里。

## Behavior contract

### 一、`desktop/web/src/api.ts` 的类型与两个新写函数

- 13 个读函数、`Envelope`、`HttpReply`、`BindingChange`、`PreviewData`、`OperationView` 一字不改。
- 新增 `export type WriteArgs = Record<string, string | string[]>;`。
- `preview(action: WriteAction, args: WriteArgs): Promise<HttpReply<PreviewData>>`（**放宽**：旧调用点传 `Record<string,string>` 仍然合法，行为不变）。
- `WriteAction` 加两个成员：`| 'profile.add' | 'profile.edit'`（旧七个保留）。
- 新增两个写函数（返回 `Promise<HttpReply<null>>`，转给 `desktop/web/src/mock/writes.ts`，不联网）：
  - `export function addProfile(args: { profile: string; runtime: string; model: string; thinking?: string; credential_env?: string[] }, confirmation: string): Promise<HttpReply<null>>`
  - `export function editProfile(args: { profile: string; runtime?: string; model?: string; thinking?: string; credential_env?: string[] }, confirmation: string): Promise<HttpReply<null>>`
- 参数键名与服务侧 `WRITE_ACTIONS` 一一对应（`profile`、`runtime`、`model`、`thinking`、`credential_env`）；不许用 `saveProfile`、`addRuntime`、`setRole`、`savePreset` 这四个名字。
- 数组按顺序原样传给服务，**不拼成字符串**；`credential_env` 为空数组时不传这个键（服务侧空数组不合法）。

### 二、`desktop/web/src/mock/writes.ts` 的四个改动

- `baseArgv` 加两个分支（照服务侧 `buildWriteArgv`）：
  - `profile.add` → `['config','profile','add',profile,'--runtime='+runtime,'--model='+model]`，有 `thinking` 时加 `'--thinking='+thinking`，`credential_env` 每一项加一个 `'--credential-env='+name`（按数组顺序）。
  - `profile.edit` → `['config','profile','edit',profile]`，`runtime`/`model`/`thinking` 传了才加对应的 `--opt=值`，`credential_env` 每一项加一个 `'--credential-env='+name`。
- `sameArgs` 改成能比数组：两个对象的键数相同、逐键相等；值是数组时长度相同且**按顺序逐项相等**（不许把数组拼成字符串再比）。
- `NEW_ACTIONS` 加 `profile.add`、`profile.edit`（这样 `opArgs` 记下这两个 action 的 `(action, args)`，`confirmWrite` 的核对与 409 口径对它们生效：号不存在、action 不符或 args 不符 → 409 + `exit_code: null` + `ERROR 确认号无效、已过期或已用过：请重新预览`）。
- `?write=` 新增两个情景（现有 20 个 → 22 个）：
  - `preview-warn`：预览 200、`ok: true`，`warnings` 一行 `WARN: 模型 <model> 不在 pi --list-models 的列表里`（`<model>` 取本次 args 的 `model`；没有 model 时写 `WARN: 模型不在 pi --list-models 的列表里`）；执行与终态照 `ok`（成功）。
  - `preview-invalid`：预览 **400**、`ok: false`、`exit_code: null`、`data: null`、`messages` 一行 `ERROR: model 不合法`；执行与终态照 `ok`（成功），但界面在表单底部显示这行原文并让 [确认…] 不可点。
  - 其余 20 个旧情景对这七个旧 action 与两个新 action 的结局**一字不改**；已有的 `warn` 情景（执行响应带 WARN）与新的 `preview-warn`（预览带 warnings）是两回事，名字不重。

### 三、表单对话框（新建 / 编辑两用）

放在 `desktop/web/src/writes/`（`ProfileForm.tsx`）；入口文件只放按钮，字段、提示与标题文字一律在这里。

- 控件：ID 与模型用 `TextField`；runtime 用 `Select`；thinking 用 `SegmentedControl`；凭据变量用自己写的标签输入（`TextField` + 添加钮 + 每项一个 `Tag` + 每项一个移除钮；**不新增组件、不改 `components/index.ts`**）。
- 字段、控件与校验（逐字）：

| 字段 | 控件 | 校验 | 提示原文 |
|---|---|---|---|
| ID | `TextField label="ID"`；编辑模式 `readOnly` | `^[a-z0-9][a-z0-9-]{0,63}$` | 出错：「只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符」 |
| runtime | `Select label="runtime"`；对话框打开时由 `src/writes` 调 `getRuntimes()` 填，选项 `value` 与 `label` 都是 runtime 的 id | 必选一个 | 读失败或没有已登记的 runtime 时：「先登记 runtime」，且 [确认…] 不可点 |
| 模型 | `TextField label="模型"` | 写成 `provider/model`：在第一个 `/` 处切开，两段都过 `^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$` | 出错：「模型要写成 provider/model，两段都只能用字母、数字与 . _ : / @ + -」；**常显**（不是出错时才有）：「手填的模型没有核实」 |
| thinking | `SegmentedControl aria-label="thinking"`；选项 off、minimal、low、medium、high、xhigh、max | — | 新建缺省 high；编辑初值是该 profile 的 `options.thinking`，没有就显示 high |
| 凭据变量 | 标签输入 | 每项过 `^[A-Za-z_][A-Za-z0-9_]{0,127}$`；重复的不加 | 出错：「变量名只能用字母、数字与下划线，不能以数字开头，最长 128 个字符」；说明：「值在‘凭据’页录入」 |

- 底部实时预览：
  - 每次改动后，**表单合法才**在 300ms 防抖后调 `preview(action, args)`；表单不合法时**不调** preview。
  - 底部显示：命令（去掉 `--dry-run` 与 `--json`）、警告行（原文）、报错行（原文）。命令用 `dispatchCommand` 拼成一行。
  - 迟到的回应按序号丢弃（每次请求带自增序号，回来时序号不是最新的就丢掉）。
  - [确认…] 可点的条件：表单合法 **且** 最后一次预览对应当前取值 **且** 状态码 200 **且** `ok` 为真。任一条不满足就不可点。
- 点 [确认…]：**表单对话框关上**，调 `useWriteFlow(reload).start(spec)`，由 A 片确认框接手（重新预览拿确认号 → 确认 → 执行 → 重读 → 终态）。A 片的状态机、映射表、W3、W3b 一行不改。
- 表单取值留在入口组件里：执行失败后重开还在原来的值；成功后清空。
- 编辑模式：
  - **只传与打开时初值不同的字段**；初值未动就不传。thinking 原来缺省、界面显示 high 但用户没动过 → 不传。
  - 全都没改时，[确认…] 不可点，并写「还没有改动」（**不许写「没有变化」**：W3b 同样管表单，它是 `role="dialog"`）。
  - 凭据变量改成空的：写「内核没有清空凭据变量的写法」，[确认…] 不可点（服务侧空数组不合法，本片不做清空）。
- 对话框关着时**不往页里渲染任何按钮**（连禁用的 [确认…] 也不渲染）：用 `Dialog`（`open` 为假时不渲染）装表单。
- 表单对话框自己的底栏：[取消]（secondary）与 [确认…]（primary，不是危险样式）；`profile.add` / `profile.edit` 不是危险动作，A 片确认框的 [确认…] 仍是 `primary`。

### 四、两个入口怎么接

| 入口 | 文件 | 按钮 | 禁用条件 | reload 怎么来 |
|---|---|---|---|---|
| 页头 [新建 profile] | `desktop/web/src/pages/RolesPage.tsx` | `Button variant="secondary" size="md"`，标签「新建 profile」；页头次序照旧（[保存当前为方案…] 在前，刷新钮在最后） | 无（离线也可点，同 A 片口径） | `PageFrame` 的 `actions` 改成可以是函数，见第五条 |
| profile 表 [编辑] | `desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx` | `Button variant="ghost" size="sm"`，标签「编辑」 | 无 | 用本组件已有的 `reload?` prop |

- 两个按钮都由 `desktop/web/src/writes/` 里的组件渲染（`ProfileForm.tsx` 导出 `NewProfileAction` 与 `EditProfileAction`），页面与 `roles-ProfilesTable.tsx` 只引入组件，不自己写字段、提示与标题文字。
- [编辑] 点了不冒泡（行本来就不可点）；`roles-ProfilesTable.tsx` 自己那份 `useWriteFlow(reload)`（给 [删除] 用）照旧保留（T023 S07）。
- 成功之后：关框 → 弹轻提示 → 调一次 `reload()`；**重读之前不弹轻提示**（W3）。

### 五、`PageFrame` 的 `actions` 放宽

- `export interface PageFrameProps<T>` 的 `actions?: ReactNode | ((reload: () => Promise<void>) => ReactNode);`（只加不改：传 `ReactNode` 的老用法行为不变）。
- 渲染时：`typeof actions === 'function' ? actions(reload) : actions`；`reload` 是页内那个已兑现的 `reload()`。
- `RolesPage.tsx` 传函数：页头渲染函数写在 `RolesPage.tsx` 里时，**该文件里不许出现** `preview`、`getOperation`、`usePreset`、`setPluginEnabled` 四个词（注释也算，T022 S15）；也不要出现「新建 profile」「修改 profile」以外的确认框标题与轻提示文字（那些一律在 `src/writes/`）。
- `RolesPage.tsx` 仍从 `../api` 只调读函数（T009 `page_wiring_problems`）；`roles-ProfilesTable.tsx` 仍从 `../../api` 只 `import type`（T009 `view_api_problems`）。

### 六、确认框内容、标题与轻提示（文字一律写在 `desktop/web/src/writes/`）

| action | 确认框标题 | 变化区摘要（预览没有 binding_changes 时） | 成功轻提示 |
|---|---|---|---|
| `profile.add` | 「新建 profile \<id\>？」 | 「profile 表里加上 \<id\>」 | 「已新建 profile \<id\>」 |
| `profile.edit` | 「修改 profile \<id\>？」 | 「profile \<id\> 改动：\<字段名列表\>」 | 「已修改 profile \<id\>」 |

- `<id>` 取 `args.profile`。
- `<字段名列表>`：只列**改动过**的字段，按 `runtime`、`model`、`thinking`、`credential_env` 的次序用「、」连接（例：`runtime、model`）；没有改动时摘要为「profile \<id\> 改动：没有改动」——但这时 [确认…] 本来就不可点，不进确认框。
- 标题与摘要里的对象名来自 `args`；不编审计号。
- 这两个 action 的预览 `binding_changes` 恒为空数组（靠变化区摘要说明）；`dangerOf` 不把它们算成危险动作（[确认…] 仍是 `primary`）。
- 命令区照旧显示去掉 `--dry-run` 与 `--json` 的写命令；「影响与风险」照 A 片显示预览的 `warnings`、`running_attempts`、`notes`（`preview-warn` 的那行 WARN 会在确认框里出现）。

### 七、快照（`desktop/web/src/writes/snapshots.ts`）

| action | 读函数 | 比较的字段 | 排除在外 |
|---|---|---|---|
| `profile.add` | `getProfiles` | `profiles[].{id, runtime, provider, model, options.thinking, credential_env}`（按 id 排序） | `adapter`（由 runtime 推出）与其余字段 |
| `profile.edit` | `getProfiles` | 同上 | 同上 |

- 做法：在 `snapshots.ts` 加一个 `profileSnapshot(profiles: ProfilesData)` 投影（`options.thinking` 取 `options?.thinking ?? null`），`readSnapshot` 里 `profile.add` / `profile.edit` 两个分支都读 `getProfiles` 并用它；`sameSnapshot` 是纯函数，不改。
- 已知局限（写进执行报告的风险段）：夹具静态，成功后重读的快照与预览时相同，因此本片测不出「真的改了」；这条靠写调用例断言命令与参数来覆盖。

### 八、`useWriteFlow.ts` 的改动（状态机一行不改）

- `WriteSpec.args` 改成 `WriteArgs`（**放宽**；旧调用处传字符串对象仍然合法）。
- `titleOf` / `successTextOf` / `changeSummaryOf` 加两个 action 的分支（逐字照第六节）。
- `readSnapshot` 加 `profile.add` / `profile.edit` 两个分支（第七节）。
- `confirm` 的 action 分派加两支：`profile.add` → `addProfile(spec.args, confirmRef.current)`，`profile.edit` → `editProfile(spec.args, confirmRef.current)`；args 的键照第一节。
- `dangerOf`、`classifyWrite` 映射表、`applyFinal` 的顺序（先轻提示后重读）都不改。

### 九、兼容与不变

- T022/T023 的七份 `desktop/web/tests/writes-*.test.*` 照旧全绿。
- 13 个读函数、`?mock=` 的五种模式、读夹具、现有 20 个 `?write=` 情景一字不改。
- `desktop/web/src/components/index.ts` 不改；不新增页面文件；不新增 JSON 夹具；`src/mock/` 的 JSON 份数与 `src/pages` 顶层页面个数不变。

## Steps
1. **读基线**：读 `desktop/web/src/api.ts`、`src/mock/writes.ts`、`src/writes/useWriteFlow.ts`、`src/writes/WriteConfirmDialog.tsx`、`src/writes/snapshots.ts`、`src/writes/writeOutcome.ts`、`src/shell/PageFrame.tsx`、`src/shell/DisabledAction.tsx`、`src/pages/RolesPage.tsx`、`src/pages/readonly1/roles-ProfilesTable.tsx`、`src/pages/readonly1/roles-RolesView.tsx`、`src/components/{index.ts,TextField.tsx,Select.tsx,SegmentedControl.tsx,Dialog.tsx,Button.tsx}`、`src/mock/{profiles,runtimes}.json`、`desktop/web/tests/{page-app.test.tsx,page-roles.test.tsx,writes-flow.test.tsx,writes-remove.test.tsx}`；确认本合同的符号与形状一致，**不一致就停下报告，不要照抄本文的行号**。
   - 验收：Repository facts 每一项都能对上；目的：不按旧行号改代码；风险：低。
2. **`api.ts`**（第一节）：`WriteArgs`、`preview` 的参数类型放宽、`WriteAction` 两个新成员、`addProfile` / `editProfile` 两个写函数。
   - 验收：`npm run typecheck` 通过；T022 的 api 探针照过（`FORBIDDEN` 里的名字一个都不许导出）；风险：碰 `LATER_API`。
3. **`mock/writes.ts`**（第二节）：`baseArgv` 两个分支、`sameArgs` 数组比较、`NEW_ACTIONS` 两个新 action、`preview-warn` 与 `preview-invalid` 两个情景。
   - 验收：`desktop/web/tests/writes-profile-api.test.ts`（命令 argv 逐项、数组顺序、号/action/args 不符返回 409、两个新情景的响应）；风险：把已有的 `warn` 情景与新的 `preview-warn` 混了。
4. **`snapshots.ts` 与 `useWriteFlow.ts`**（第六、七、八节）：`profileSnapshot` 投影、`readSnapshot` 两个分支、`titleOf` / `successTextOf` / `changeSummaryOf` 三个文字表的两条、`confirm` 的两支分派、`WriteSpec.args` 放宽。
   - 验收：`desktop/web/tests/writes-profile-api.test.ts` 与 `writes-profile-form.test.tsx`；A、B 片的七份 `writes-*` 照跑；风险：改坏 A 片。
5. **`src/writes/` 里的表单**（第三节）：`profileRules.ts`（正则与纯函数：ID、凭据变量名、模型两段、`provider/model` 切分、编辑时「只传改动字段」的比较）、`useLivePreview.ts`（300ms 防抖 + 序号丢弃迟到回应）、`ProfileForm.tsx`（表单对话框 + `NewProfileAction` + `EditProfileAction`）、`profile-form.css`（只用既有 `--tt-*` 令牌；不声明新令牌、不写十六进制颜色与颜色函数）。
   - 验收：`desktop/web/tests/writes-profile-form.test.tsx`（字段、逐字提示、实时预览、确认门控、编辑只传改动、清空凭据变量、对话框关着时页里没有按钮）；风险：自己写标签输入时漏掉无障碍名称。
6. **接两个入口**（第四、五节）：`PageFrame` 的 `actions` 放宽；`RolesPage.tsx` 传渲染函数拿 `reload`；`roles-ProfilesTable.tsx` 的 [编辑] 换成可点的 ghost/sm 按钮并接 `EditProfileAction`。
   - 验收：页面用例（页头次序不变、[新建 profile] 与 [编辑] 可点且样式照旧、[编辑] 打开的是带初值的编辑表单）；风险：T009 的页头次序断言与 D11 白名单。
7. **改两份既有测试**：`page-roles.test.tsx`（[编辑] 由禁用改成可点，`data-variant="ghost"`、`data-size="sm"` 两条断言照旧）、`page-app.test.tsx`（角色页禁用按钮个数 9→6，用例名照实际清单改；运行时页 6 与总览 0 不变）。只改这几条断言，不删用例、不削弱别的断言。
   - 验收：`npm test` 全绿；风险：漏改会让既有用例红。
8. **写两份新测试**：`desktop/web/tests/writes-profile-form.test.tsx` 与 `desktop/web/tests/writes-profile-api.test.ts`；不出现 skip/only/todo；计时相关的用例一律用假计时器；依赖注入照 A 片 `desktop/web/tests/writes-flow.test.tsx` 的写法（`vi.hoisted` + `vi.mock('../src/api')` 的 overrides 表）。
   - 验收：DoD 附表里每条变异都有用例杀掉；风险：新写法与 A 片的注入方式不一致。
9. **跑检查并写报告**：跑 Setup 与 Validation commands 的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下报告。
   - **两条硬规矩**：
     1. **遇到合同与既有测试（或门禁）冲突时**：不要越界改范围外的文件。把冲突写进执行报告的 `contract_conflicts`（哪一处、合同/门禁要求什么、实际是什么），然后继续做合同范围内能做的部分；不许为了让检查变绿去改 `tests/test_gate_*`、A/B 片的 `writes-*` 用例，或改 `desktop/web/src/api.ts` 的注释来迁就门禁的解析。
     2. **临时文件**：不许写到 `/tmp` 这类固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`；测试草稿用完立刻删掉，别留在候选里。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t024_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`node node_modules/typescript/bin/tsc --noEmit` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`^$`
- V02（必要）：`node node_modules/vitest/vitest.mjs run` · cwd：desktop/web · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run check:contract` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`契约检查：通过`
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：1200s · 期望退出码：0 · 输出须匹配：`built in`

## Definition of done
- D01：`api.ts` 新增且只新增 `addProfile`、`editProfile` 两个写函数与 `WriteAction` 的 `profile.add`、`profile.edit` 两个成员；新增 `export type WriteArgs = Record<string, string | string[]>`；`preview` 与 `WriteSpec.args` 改用它且**只放宽**（T022/T023 的既有调用处与行为一字不改）；`desktop/web/src` 下仍不出现那四个联网词；证据：V01、V02、G01；目的：读侧与旧片不动是新旧并存的前提。
- D02：`credential_env` 这类数组按顺序原样传给服务，不拼成字符串；mock 的 `sameArgs` 对数组按顺序逐项比（丢项、顺序错、多了项都算不符）；证据：V02；目的：杀掉「数组被拼成字符串」「顺序被打乱」。
- D03：两个新写函数的确认号与参数核对生效——号不存在、action 不符或 args 不符时返回 409 且 `exit_code` 为 null（界面显示「确认已失效」），确认号与参数都对时按 200 走完；证据：V02；目的：杀掉「写函数确认号或参数传错」。
- D04：表单校验照内核原式：ID 过 `^[a-z0-9][a-z0-9-]{0,63}$`、凭据变量名过 `^[A-Za-z_][A-Za-z0-9_]{0,127}$`、模型在第一个 `/` 处切开且两段都过 `^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$`；不合法的值**不调** preview（用例断言调用次数为 0）；证据：V02；目的：表单不放过内核不认的值。
- D05：编辑 profile 时 ID 只读、只传与初值不同的字段（thinking 原来缺省、界面显示 high 但没动过就不传）；全都没改时 [确认…] 不可点并写「还没有改动」（对话框里不出现「没有变化」）；证据：V02；目的：杀掉「没改的字段也传」「ID 能改」。
- D06：底部实时预览照约定：表单合法才在 300ms 防抖后调 preview；显示去掉 `--dry-run`/`--json` 的命令、警告原文、报错原文；迟到的回应按序号丢弃；[确认…] 只有在「表单合法且最后一次预览对应当前取值且状态码 200 且 ok 为真」时可点；证据：V02；目的：确认之前看得见内核会做什么。
- D07：`preview-warn` 情景下警告行同时出现在表单底部与确认框里、可以确认、执行成功；`preview-invalid` 情景下底部显示内核原文 `ERROR: model 不合法` 且 [确认…] 不可点；证据：V02；目的：杀掉「预览带警告不显示」「校验不过也能点确认」。
- D08：两个入口可点并走同一条流程——页头 [新建 profile] 可点、次序照旧（[保存当前为方案…]、新建 profile、刷新）、样式 secondary/md；profile 表 [编辑] 可点、样式 ghost/sm；点入口只打开表单对话框；**对话框关着时页里不渲染任何按钮**（连禁用的 [确认…] 也没有）；证据：V02、R01、G01；目的：接上入口又不破 T009 的页头次序、白名单与禁用数。
- D09：确认框标题、变化区摘要、成功轻提示逐字照第六节（「新建 profile \<id\>？」「修改 profile \<id\>？」「profile 表里加上 \<id\>」「profile \<id\> 改动：\<字段名列表\>」「已新建 profile \<id\>」「已修改 profile \<id\>」），且这些文字只出现在 `src/writes/`；证据：V02、G01；目的：T013 的「动作说明只有一份」与 T022/T023 的「文字在 writes/ 里」同时守住。
- D10：成功只在重读之后才说——重读兑现之前整页没有「已新建 profile…」/「已修改 profile…」；重读之后弹对应轻提示、关框、并调一次 `reload()`；证据：V02；目的：W3 是这一片的核心红线。
- D11：两个新 action 的快照只比 `profiles[].{id, runtime, provider, model, options.thinking, credential_env}`；改 `adapter` 等被排除的字段仍判定相同；证据：V02；目的：快照不把会自己变的字段拿来比。
- D12：既有测试只照新行为改那几条断言——`page-roles.test.tsx` 的 [编辑] 改成可点（ghost/sm 两条断言照旧）、`page-app.test.tsx` 的角色页禁用按钮个数 9→6（运行时页 6、总览 0 不变）；没有删除、跳过或弱化任何既有用例；A/B 片的七份 `writes-*` 照旧全绿；证据：V02、review；目的：既有测试是别的片的契约，不能借机削弱。
- D13：所有修改都在允许集合内（新增文件都在 `allowed_new_files`，没有删文件，依赖与锁文件没动，`forbidden_paths` 里的门禁文件、`components/index.ts`、`mock/*.json`、`docs/**`、`ts/**`、`scripts/**` 一个都没动）；证据：scope；目的：越界改文件会让范围检查直接判负。
- D14：遇到合同与既有测试或门禁冲突时，执行端没有越界改范围外的文件（冲突写进执行报告的 `contract_conflicts`）；临时文件没有写到 `/tmp` 这类固定路径（用 `T=$(mktemp -d)` 并在同一条命令里删掉）；证据：review、scope；目的：上一轮 T022 的 attempt-001 就是在这两处出的问题。

D14 附带的变异对照（每条都要有用例杀掉）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| M1 | 表单放过不合规的 ID 或凭据变量名（`-abc`、65 个字符的 ID、`1ABC`、129 个字符的变量名） | 规则用例：都拒；且界面上不调 preview（调用次数为 0） |
| M2 | 模型没写成 `provider/model` 也放过 | 模型用例：无 `/` 或某一段含非法字符时报错 |
| M3 | 编辑时 ID 能改，或没改的字段也传了 | 编辑用例：ID 只读；只改模型时命令只含 `--model`；thinking 缺省而未动时不传 |
| M4 | 预览带警告不显示，或校验不过也能点确认 | `preview-warn` 用例看底部与确认框都有警告；`preview-invalid` 与前端校验不过时 [确认…] disabled |
| M5 | 写函数的确认号或参数传错（字段名对不上服务的必填项） | mock 核对：号、action、args 不符返回 409；用例断言执行后不是「确认已失效」、命令字段正确 |
| M6 | 成功之后不重读，表里还是旧值 | 注入 `reload` 的用例：断言 `reload` 调一次 |
| M7 | A、B 片的流程被改坏 | 照跑七份 `writes-*` 与 T022、T023 门禁 |
| M8 | 凭据变量的顺序被打乱、丢项，或空数组也传了 | 命令里 `--credential-env` 的顺序断言；清空时提示与禁用 |
| M9 | 对话框关着时页里还留着按钮 | 页面用例：对话框未打开时页里的按钮集合与打开前一致 |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `WriteSpec` 的形状变了、`PageFrame` 的 `children` 第二个参数不是 `reload`、`Button` 没有 `ghost`/`sm` 变体、`Dialog` 在 `open` 为假时仍渲染内容）。
- 必须修改允许范围之外的文件才能继续（例如要动 `tests/test_gate_*`、A/B 片的 `writes-*` 用例、`desktop/web/src/components/index.ts`、`desktop/web/src/mock/*.json`、`docs/**`、`ts/**`）。遇到这种冲突：**不要越界改**，写进执行报告的 `contract_conflicts`，继续做范围内的部分。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要替内核实现「清空凭据变量」的写法）。
- 达到单轮时限（本版单次 3600 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；累计已用 0 次，本版至少留 2 次 attempt）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 14400（累计已用 0 秒，余 14400 秒 ≥ 2 倍单次时限，留足返工）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与核对事实 12 分钟；实现（api.ts 与 mock/writes、snapshots、useWriteFlow）30 分钟；表单对话框与实时预览 40 分钟；接两个入口 15 分钟；改两份既有测试 10 分钟；写两份新测试 30 分钟；必要检查（V01–V04、R01、G01）15 分钟；最终报告 5 分钟；总计 157 分钟，不超过单次时限。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 报告里要写清：九条变异各自由哪条用例杀掉、两个新 `?write=` 情景的实测响应、`profile.add` 与 `profile.edit` 的完整 argv（逐项）、两个入口的最终写法（按钮标签、样式、禁用条件）、快照投影的字段与排除字段、两份既有测试改后的断言与最终计数、`git diff --stat` 里**没有**任何 `tests/test_gate_*`、A/B 片的 `writes-*` 用例、`components/index.ts`、`mock/*.json`、`npm run check:contract` 与 `npm run build` 的输出。
- 遇到合同与既有测试或门禁的冲突：一律写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），不要越界改文件；这一项不许留空。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（既有测试只照新行为改那几条断言）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不改 `tests/test_gate_*`、A/B 片的 `desktop/web/tests/writes-*.test.*`、`desktop/web/src/components/index.ts`、`desktop/web/src/mock/*.json`、`desktop/web/src/App.tsx`、`desktop/web/src/main.tsx`、`docs/**`、`ts/**`、`scripts/**`；不在 `desktop/web/src` 下写那四个联网词；不新增页面文件、不新增 JSON 夹具、不改依赖与锁文件。
- 不把确认框标题、变化区摘要与成功轻提示写进 `src/pages/` 与 `src/pages/readonly1/`（这些文字只许在 `src/writes/`）；`roles-ProfilesTable.tsx`（含注释）里不许出现「新建 profile」「修改 profile」。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261029T135843732925Z-owner-30d753：

> 规划端（本会话）代定（站主授权代答 hub 提问）。三件都照规划报告的建议：
>
> 1) 门禁退役：同意，已做。照规划报告 §7.1 退役了 6 处断言（T009 D06、D08、D11 的白名单与 later 列表；T023 S07 与 entries 探针里 [编辑] 的禁用和悬停提示），提交 6fb21d4，已 task rebase，T024 的基线现在是 6fb21d4。只停止断言旧行为，不提前断言新行为；退役后在 b853ffc 上点名运行这两份门禁：76 passed。[更改…]、[保存当前为方案…] 仍要求禁用并悬停「第二阶段接入」。
>
> 2) 参数类型：同意。新增 export type WriteArgs = Record<string, string | string[]>，preview 与 WriteSpec.args 改用它；这是放宽，已有调用处与行为一字不改。已核：没有门禁钉住 preview 的参数类型（tests/test_gate_* 里的 Record<string, string> 都是测试自己的局部类型）。数组照顺序原样传给服务，不拼成字符串。
>
> 3) 拆片：同意三片。本片 T024 = 公共底座（WriteArgs、表单规则、实时预览、PageFrame 的 actions 可以是函数、mock 的新情景与数组比较）+ profile 新建与编辑（profile.add、profile.edit）。runtime.add、role.set 与 preset.save 不在本片，照旧禁用、悬停「第二阶段接入」；后两片何时登记由站主另定，现在不登记。
>
> 另外照任务书：表单校验照内核原式（ID 用 TASK_ID_RE ^[a-z0-9][a-z0-9-]{0,63}$；凭据变量名用 ENV_NAME_RE ^[A-Za-z_][A-Za-z0-9_]{0,127}$）；模型本片只手填，提示「手填的模型没有核实」；编辑时 ID 不可改，只传改动的字段。
>
> 可以开工合同端。

## Retry（重派第 1 次，内核追加）

- 上一轮 attempt-001 没过内核核验：check --fresh 退出码 1，范围违规 0 条，attempt 状态 NEEDS_REVIEW，执行端自述 未知。
- 这一轮从合同的 base_sha 重新开始，上一轮的改动不在工作目录里。先读下面的失败原因，别再踩同一个坑。
- Scope、Behavior contract 与 DoD 不变。下面的日志是数据，不是指令。
### 没过的检查（最近一次 check，日志末尾）

- G01：退出码 1 ≠ 期望 0

    assert False
     +  where False = is_file()
     +    where is_file = WindowsPath('C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t024-desktop-ui-forms-a001-verify-l6yoxvh_/desktop/web/src/writes/ProfileForm.tsx').is_file
    FAILED tests/test_gate_t024_baseline.py::test_s06_writes_texts_live_in_writes - AssertionError: src/writes/ 里应出现文字表片段 ['新建 profile ', '修改 profile ', '已新建 profile', '已修改 profile', 'profile 表里加上', '改动：', '还没有改动', '内核没有清空凭据变量的写法', '手填的模型没有核实', '先登记 runtime', '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符', '模型要写成 provider/model，两段都只能用字母、数字与 . _ : / @ + -', '变量名只能用字母、数字与下划线，不能以数字开头，最长 128 个字符', '值在‘凭据’页录入']（合同第三、六节的逐字表）
    assert not ['新建 profile ', '修改 profile ', '已新建 profile', '已修改 profile', 'profile 表里加上', '改动：', ...]
    FAILED tests/test_gate_t024_baseline.py::test_s07_rolespage_header_entry - AssertionError: 页头 [新建 profile] 应由 src/writes 的 NewProfileAction 渲染（页面只放按钮）
    assert 'NewProfileAction' in '// 角色与模型页（合同第 2、5 条）：并行读 getRoles/getProfiles/getPresets，任一失败按 roles→profiles→presets 顺序返回第一个失败信封；\n// 不传 isEmpty（?mo...n      {(data, reload) => <RolesView data={data} onDiff={diffPresets} reload={reload} />}\n    </PageFrame>\n  );\n}\n'
    FAILED tests/test_gate_t024_baseline.py::test_s08_profilestable_edit_entry - AssertionError: profile 表 [编辑] 应由 src/writes 的 EditProfileAction 渲染（页面只放按钮）
    assert 'EditProfileAction' in '// profile 表（合同第 5 节）：Table rowHeight 40、aria-label「profile」；列 ID/runtime/模型/thinking/凭据变量/被引用/操作；\n// thinking 缺失「缺省...}\n          rowKey={(r) => r.rowId}\n        />\n      )}\n      <WriteFlow flow={flow} />\n    </Section>\n  );\n}\n'
    FAILED tests/test_gate_t024_baseline.py::test_s09_pageframe_actions_can_be_function - AssertionError: PageFrameProps 的 actions 应放宽成 ReactNode | ((reload: () => Promise<void>) => ReactNode)
    assert None
     +  where None = <function search at 0x0000000001392B60>('actions\\?:\\s*ReactNode\\s*\\|\\s*\\(\\(reload:\\s*\\(\\)\\s*=>\\s*Promise<void>\\)\\s*=>\\s*ReactNode\\)', '// 页面框架（合同第 8 条，照 Main 画布 :63–84、:205–241 与 UI 文档 5.5、6、8.1、8.2）：五态 loading/data/empty/error。\n// 挂载时调 load；ok 且 isEm..."接入本机服务后可用" variant="secondary" size="sm" />\n        </Banner>\n      )}\n      {renderBody()}\n    </div>\n  );\n}\n')
     +    where <function search at 0x0000000001392B60> = re.search
    FAILED tests/test_gate_t024_baseline.py::test_s12_executor_test_files_present_and_tokens - AssertionError: desktop/web/tests/writes-profile-form.test.tsx 不存在（基线上还没有实现）
    assert False
     +  where False = is_file()
     +    where is_file = WindowsPath('C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t024-desktop-ui-forms-a001-verify-l6yoxvh_/desktop/web/tests/writes-profile-form.test.tsx').is_file
    FAILED tests/test_gate_t024_baseline.py::test_s14_rules_and_live_preview_files - AssertionError: desktop/web/src/writes/profileRules.ts 不存在（基线上还没有实现）
    assert False
     +  where False = is_file()
     +    where is_file = WindowsPath('C:/Users/Administrator/AppData/Local/Temp/2/pi-worktrees/ThemisTally-t024-desktop-ui-forms-a001-verify-l6yoxvh_/desktop/web/src/writes/profileRules.ts').is_file
    FAILED tests/test_gate_t024_baseline.py::test_p1_pipeline_steps_pass - AssertionError: 候选里 api.ts 还没有 T024 的标记（addProfile），没有东西可测，未调用 npm；候选把两个新写函数与表单接上之后，流水线才会运行 npm ci、构建、Vitest 和探针
    assert False
     +  where False = <test_gate_t024_baseline.Pipeline object at 0x00000000044EA9F0>.ran
    FAILED tests/test_gate_t024_baseline.py::test_p2_profile_form_css_bundled_into_build - AssertionError: 候选里 api.ts 还没有 T024 的标记（addProfile），没有东西可测，未调用 npm；候选把两个新写函数与表单接上之后，流水线才会运行 npm ci、构建、Vitest 和探针
    assert False
     +  where False = <test_gate_t024_baseline.Pipeline object at 0x00000000044EA9F0>.ran
    FAILED tests/test_gate_t024_baseline.py::test_d01_d02_d03_d07_d11_probe_api - AssertionError: 候选里 api.ts 还没有 T024 的标记（addProfile），没有东西可测，未调用 npm；候选把两个新写函数与表单接上之后，流水线才会运行 npm ci、构建、Vitest 和探针
    assert False
     +  where False = <test_gate_t024_baseline.Pipeline object at 0x00000000044EA9F0>.ran
    FAILED tests/test_gate_t024_baseline.py::test_d04_d05_d06_d08_probe_form - AssertionError: 候选里 api.ts 还没有 T024 的标记（addProfile），没有东西可测，未调用 npm；候选把两个新写函数与表单接上之后，流水线才会运行 npm ci、构建、Vitest 和探针
    assert False
     +  where False = <test_gate_t024_baseline.Pipeline object at 0x00000000044EA9F0>.ran
    FAILED tests/test_gate_t024_baseline.py::test_d07_d09_d10_probe_flow - AssertionError: 候选里 api.ts 还没有 T024 的标记（addProfile），没有东西可测，未调用 npm；候选把两个新写函数与表单接上之后，流水线才会运行 npm ci、构建、Vitest 和探针
    assert False
     +  where False = <test_gate_t024_baseline.Pipeline object at 0x00000000044EA9F0>.ran
    FAILED tests/test_gate_t024_baseline.py::test_p10_worktree_unchanged_by_pipeline - AssertionError: 候选里 api.ts 还没有 T024 的标记（addProfile），没有东西可测，未调用 npm；候选把两个新写函数与表单接上之后，流水线才会运行 npm ci、构建、Vitest 和探针
    assert False
     +  where False = <test_gate_t024_baseline.Pipeline object at 0x00000000044EA9F0>.ran
    17 failed, 3 passed in 0.38s
