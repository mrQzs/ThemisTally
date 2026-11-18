# TASK: t053-desktop-web-preset-save

<!-- 合同 v1：T053「[保存当前为方案…]：在界面里把当前角色绑定存成方案」。
     页头的 [保存当前为方案…] 从灰变可点（照 [新建 profile]：secondary、md、一直可点），点开「保存当前为方案」表单：
     方案名（必填）、说明（可选）、要存哪些角色（只列已写出绑定的，缺省全选）；同名要显式勾覆盖才带 force。
     Identity 的 plan_version 与 base_sha 由内核定；executor 与 integration_actions 照任务书抄。
     本片不改本机服务（writeroutes.ts 被 T047 按字节冻结），不改 PageFrame、readonly1 的只读部分与既有两个改绑定表单。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 5b2dd3c7d36b5579fd5a60941a83fa040570e58a
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
「角色与模型」页页头的 [保存当前为方案…] 变成可点的次级按钮（secondary/md，一直可点），点开「保存当前为方案」表单：方案名按内核规则当场校验、说明可选（1–200 码点）、要存哪些角色只列**已写出绑定**的角色并缺省全选；底部实时预览命令与内核提示；同名方案要用户显式勾「覆盖方案 X」才带 `force`；一个显式绑定都没有时给原因句且 [确认…] 不可点。点 [确认…] 走既有的确认框 → 执行 → 重读 → 终态，写完整页重读，方案表里出现新方案。

## Non-goals
- 不改本机服务（`ts/packages/ui/src/writeroutes.ts` 被 T047 按字节冻结）：preset.save 的路由与校验都已就位。
- 不改 `desktop/web/src/shell/PageFrame.tsx`（页头 actions 只拿得到 reload，本片靠入口自己读数据）；不改 `desktop/web/src/pages/readonly1/**` 的只读部分；不改 `desktop/web/src/writes/HubBindForm.tsx`、`RoleBindForm.tsx`、`snapshots.ts`、`useLivePreview.ts`、`WriteConfirmDialog.tsx`、`writeOutcome.ts`、`profileRules.ts`、`hub-bind-form.css`。
- 不做方案表空态的 [保存当前为方案…] 按钮（画布有，另排）；不做运行时页的扫描/探测/列模型/就绪检查；不做凭据录入与续期。
- 不新增依赖、不改锁文件；不新增桩情景（`WriteScenario` 的值一个都不许加）；不新建 CSS 文件。
- 不改 `desktop/web/src/components/**`、`desktop/web/src/mock/` 里的夹具 JSON 与 `quizs.ts`、`hub-roles.ts`。

## Repository facts
以下事实都在本回合的工作目录（基线 f8ed8e20）里逐条读过；行号按该基线。

### 本机服务（不改，只照它的规则写前端）
- `ts/packages/ui/src/writeroutes.ts`
  - `:78-93` `WRITE_ACTIONS`：`"preset.save": { required: ["name"], optional: ["description", "roles", "force"] }`（共 14 个 action）。
  - `:226-234` `validValue`：`name` 过 `TASK_ID_RE`；`description` 走 `cleanText(value, 1, 200)`（`:169-179`：按码点计数 1–200，不许 C0 控制字符（≤0x1f）、DEL（0x7f）与孤立代理项）；`roles` 走 `validRoles`（`:182-191`：非空数组、元素互不相同、每项是四个角色码之一）；**`force` 只认 JSON 布尔 `true`**。
  - `:283-288` `buildWriteArgv` 的 `preset.save` 分支：`["config","preset","save", name]`，有 `description` 加 `--description=…`，有 `roles` 加 `--roles=a,b`，`force === true` 加 `--force`。
  - `:550-553` 路由：`POST /api/v1/presets/<name>/save`；路径里的 name 与正文合并后再校验（路径参数压正文）。

### 内核（不改，只照它的提示与规则写前端）
- `scripts/kit_roles.py`
  - `:129-130` `_id_ok(value)` = `pd.TASK_ID_RE.match(value)`。
  - `:1553-1581` `_preset_save`：name 不合法 → 「方案名不合法（小写字母、数字与连字符）：…」；`--roles` 里有没写出绑定的角色 → 「这些角色还没有写出绑定：…（先 config role set）」；没有可存的 → 「roles 里还没有绑定可存：先 config role set」；同名且没 `--force` → 「方案 X 已存在：要覆盖加 --force」；成功打印「已保存方案 X：…」。不带 `--roles` 时存所有写出绑定的角色。

### 名称规则三处一致（规划端待核实项 1，已核实）
- 服务 `TASK_ID_RE` = `^[a-z0-9][a-z0-9-]{0,63}$`；内核 `_id_ok` 用同一个正则；`desktop/web/src/writes/profileRules.ts:6,12` 的 `ID_RE = /^[a-z0-9][a-z0-9-]{0,63}$/` 与 `validId(id)` 与之**逐字同规则**。表单直接用 `validId`（从 `./profileRules` 引），不另写正则。

### 前端现状
- `desktop/web/src/api.ts`
  - `:64-77` `export type WriteAction` 既有 13 个成员：`preset.use / plugin.enable / plugin.disable / preset.remove / profile.remove / runtime.remove / config.rollback / profile.add / profile.edit / hub.set / hub.unset / runtime.add / role.set`。
  - `:80` `export type WriteArgs = Record<string, string | string[]>`（装不下布尔值）。
  - `:309-320` `writeArgs`：数组非空才传、空串不传；`number` 与 `cadence_seconds` 用 `asNumber` 转 JSON 数字；其余键值原样传。预览与执行共用这一份规则（不一致时服务回 409「参数不符」）。
  - `:703-708` `preview(action, args)`：真实模式 `POST /api/v1/preview`，正文 `{ action, args: writeArgs(args) }`；桩模式 `mockPreview(action, args)`（**桩模式不套 writeArgs**，原样收 args）。
  - `:727` `usePreset(name, confirmation)`、`:751` `removePreset(name, confirmation)`：真实模式 `POST /api/v1/presets/<encodeURIComponent(name)>/<use|remove>`，正文只有 `{ confirmation }`；桩模式转 `mockUsePreset` / `mockRemovePreset`。
- `desktop/web/src/mock/writes.ts`
  - `:67` `baseArgv(action, args)`；`:129` `NEW_ACTIONS`（10 个 action，写函数的确认号核对靠它记下 `(action, args)`）；`:218` `previewData(action, args, confirmation)`；`:345` `mockPreview`；`:488-501` `sameValue` / `sameArgs`（键数相同、逐键相等，数组按顺序逐项相等）；`:503` `confirmWrite(action, args, confirmation)`（对不上回 409）；`:480` `mockUsePreset`、`:519` `mockRemovePreset`；`:61` `asStringArray`。
- `desktop/web/src/writes/useWriteFlow.ts`
  - `:87-99` `titleOf`、`:102-116` `successTextOf`、`:119-158` `changeSummaryOf`（三张文字表；`preset.remove` 那一支是 `方案表里去掉 ${args.name}，角色绑定不变`）。
  - `:165` 起 `readSnapshot(action, isReread)`：按 action 分支读快照（`preset.remove` 读 `getPresets()` 用 `presetRemoveSnapshot`；`role.set` 读 `getRoles()` 用 `roleSnapshot`；末尾兜底读 `getPlugins()` 用 `pluginSnapshot`）。
  - `confirm` 里的执行分派是一条 `spec.action === …` 长链，最后是 `setPluginEnabled` 兜底。
  - `dangerOf`：`preset.remove / profile.remove / runtime.remove / config.rollback` 是危险动作；其余 primary。
- `desktop/web/src/writes/snapshots.ts`：`presetRemoveSnapshot(presets)` = `{ active_preset, presets: [{name, active}] }`（排除 description 与 roles）。
- `desktop/web/src/writes/writeOutcome.ts`：`finalFromReread(cls, rereadOk, snapshotChanged, envelope)`：成功类看重读成不成；失败类看快照变没变（变了 → `partiallyWritten`，没变 → `failed`）。
- `desktop/web/src/writes/useLivePreview.ts`：`useLivePreview(action, args, enabled)` → `{ result, current }`；300ms 防抖；`current` 表示最近一次预览还对应当前取值。
- `desktop/web/src/writes/HubBindForm.tsx`：T052 的内外两层写法样板——外层 `useWriteFlow(reload)` + `{open && <内层 …/>}` + `<WriteFlow flow={flow} />`；内层放字段、`useLivePreview`、底部预览与 `<Dialog>`；[确认…] 先 `onClose()` 再 `start(spec)`；底部复用 `./hub-bind-form.css` 的 `hb-*` 类。
- `desktop/web/src/pages/RolesPage.tsx`：`:5` 引 `DisabledAction`；`:64-69` `actions={(reload) => (<><DisabledAction label="保存当前为方案…" /><NewProfileAction reload={reload} /></>)}`；`:26-45` 并行四读 `Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()])`，失败判定 `[roles, profiles, presets].find(...)`；`:63` `load={loadRoles}`；`:71` children 那一行 `<RolesView data={data} onDiff={diffPresets} reload={reload} live={live} />`。
- `desktop/web/src/pages/readonly1/roles-logic.ts:12` `export function roleName(code)`（planning_review 规划审核端、contract 合同端、execution 执行端、scheduler_agent 调度代理；未知码原样返回）。
- `desktop/web/src/components/Checkbox.tsx`：`role="checkbox"` 的 span，props `checked / onChange / label / disabled`。
- `desktop/web/src/components/TextField.tsx`：props `label / help? / error? / mono?` + 其余原生 input 属性。
- 夹具：`desktop/web/src/mock/roles.json` 里 `planning_review` 与 `execution` 是 `explicit: true`，`contract` 与 `scheduler_agent` 是 `false`；`desktop/web/src/mock/presets.json` 里 `default`（active）与 `economy` 两个方案。

### 门禁与既有测试的核查结论（本片**必然**要改的那几处，逐条读过）
- `tests/test_gate_t009_baseline.py`
  - `:2376-2383` 用例「页头 actions：[保存当前为方案…]、[新建 profile] 排在刷新钮之前；[保存当前为方案…] 禁用」：按钮次序断言 `['保存当前为方案…', '新建 profile', '刷新']` 成立（本片次序不变），但 `expect(buttons[0].disabled).toBe(true)` 与标题里的「禁用」要改。
  - `:2957-2969` 用例「角色页：要填表单的写入口仍禁用且悬停出「第二阶段接入」…」：`:2964` 的 `outsideWhitelist([...])` 数组要加「保存当前为方案…」（它变成可点按钮）；`:2966-2969` 的 `later = ['保存当前为方案…']` 与「悬停出第二阶段接入」三行断言在本片之后不再成立（角色页再没有这个入口，也没有别的悬停「第二阶段接入」的入口）。
  - `:3021-3031` 的五态探针只断言 `data-page-state`、`h1` 与视图根，**不按个数统计可用按钮**——本片新增的可点页头按钮不会推翻它。
- `tests/test_gate_t024_baseline.py`
  - `:301-307` 静态用例：`assert '<DisabledAction label="保存当前为方案…"' in text` 要改（入口不再是 DisabledAction）。
  - `:1088-1106` 探针：it 标题含「角色页禁用数 7」；`:1094` 页头次序断言（次序不变）；`:1095-1096` 断言 `[保存当前为方案…]` 仍禁用；`:1101` 断言悬停提示是「第二阶段接入」；`:1106` 断言角色页禁用按钮数是 7。
  - `:1109-1114` offline 用例只查 `[新建 profile]` 与 profile 行的 `[编辑]`，不查页头按钮个数。
- `tests/test_gate_t038_baseline.py`：`:109` 常量 `PAGE_HEAD_DISABLED = "保存当前为方案…"`；`:413-414` 要求 RolesPage 原文里同时有该记号与 `NewProfileAction`（按钮文字搬进 src/writes 后这条要改）。
- `tests/test_gate_t045_baseline.py`：`:125-127` 常量 `ROLES_PAGE_DISABLED = 7`；`:553-563` 核对 `page-app.test.tsx` 的角色页禁用数与 it 标题（正则 `角色页 \d+…、运行时页 5、总览 0`）；`:1231-1233` 探针 `toBe(7)`。
- `tests/test_gate_t048_baseline.py`：`:83-84` RolesPage 从 `../api` 引入的值白名单（12 个读函数）；`:92` 四个禁词 `preview / getOperation / usePreset / setPluginEnabled`（注释也算）；`:289-292` 页头三枚记号（含 `'<DisabledAction label="保存当前方案…" />'` 这一枚）；`:134-143` 按字节冻结清单（`mock/quizs.ts`、`mock/hub-roles.ts`、`runtimes-quizs-logic.ts`、`roles-styles.css`、三份既有包内测试、`package.json`、`package-lock.json`）。
- `tests/test_gate_t051_baseline.py`：`:102-106` WriteAction 既有成员包含式核对；`:160-162` 常量 `ROLES_PAGE_DISABLED = 7`；`:351-363` 桩的 `previewData` 从 `'role.set'` 起截 700 个字符找 `binding_changes` 与 `resources: ['roles']`（**新分支不许插进 role.set 分支内部**，否则会把这两枚记号挤出窗口）；`:364-368` 写函数要走既有 `confirmWrite`；`:1207` 探针 `toBe(7)`。
- `tests/test_gate_t002_baseline.py:1496`：`desktop/web` 下所有 `*.test.*` 不许 `skip`/`only`/`todo`。
- 包内测试：`desktop/web/tests/page-app.test.tsx:91-99`（describe 标题「写入口个数（过渡）」一字不动；it 标题与 `toBe(7)` 要改）；`desktop/web/tests/writes-hub-bind.test.tsx:297-317`（describe 标题「桩下角色页禁用按钮实测 7」、it 标题、构成注释与 `toBe(7)` 要改）。
- 关键字搜索（`保存当前为方案`、`preset.save`、`savePreset`、`DisabledAction`、`禁用`、`PresetsTable`、`RolesPage`，范围 `desktop/web/tests/` 与 `tests/`）：命中只有上面这些；`desktop/web/tests/cleanup1-static.test.ts:22`、`cleanup1-shared.test.ts:61`、`readonly2-logic.test.ts:237` 命中的是 `actionTitle('preset.save') === '保存方案'`（`components/actionTitle.ts` 里本来就有，本片不动）。
- 桩下角色页的禁用按钮从 7 个变成 6 个：方案条 `[切换…]` 1 + planner 的 `[改绑定…]` 1 + 四个缺省行的 `[恢复缺省…]` 4。

### 工具链与锁文件
- `desktop/web` 用 npm：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`（TypeScript 5.6.3）、`npm run build` = `tsc --noEmit && vite build`。
- `desktop/web/tsconfig.json` 的 `include` 只有 `["src", "vite.config.ts"]`：`tests/` 里的文件不过 `tsc --noEmit`，但 vitest 会读到。
- 仓库门禁用 `python -m pytest`；本片不改任何依赖清单与锁文件（`dependency_changes: forbidden`）。

### 基线检查
- 本回合（合同端）只读，没有 shell，没有跑 `npm test` 与 `pytest`；上面的结论都是逐文件只读核对得出的。
- 合同检查在基线上的结果由内核在执行之前跑过（基线检查记录）；执行端不必再跑一遍整套测试。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/writes-hub-bind.test.tsx
  - tests/test_gate_t009_baseline.py
  - tests/test_gate_t024_baseline.py
  - tests/test_gate_t038_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t048_baseline.py
  - tests/test_gate_t051_baseline.py
- allowed_new_files:
  - desktop/web/src/writes/PresetSaveForm.tsx
  - desktop/web/tests/writes-preset-save.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t053_*.py
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
  - tests/test_gate_t030_baseline.py
  - tests/test_gate_t031_baseline.py
  - tests/test_gate_t032_baseline.py
  - tests/test_gate_t033_baseline.py
  - tests/test_gate_t034_baseline.py
  - tests/test_gate_t035_baseline.py
  - tests/test_gate_t036_baseline.py
  - tests/test_gate_t037_baseline.py
  - tests/test_gate_t039_baseline.py
  - tests/test_gate_t040_baseline.py
  - tests/test_gate_t041_baseline.py
  - tests/test_gate_t042_baseline.py
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t044_baseline.py
  - tests/test_gate_t046_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t049_baseline.py
  - tests/test_gate_t050_baseline.py
  - tests/test_gate_t052_baseline.py
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/live/**
  - desktop/web/src/mock/*.json
  - desktop/web/src/mock/quizs.ts
  - desktop/web/src/mock/hub-roles.ts
  - desktop/web/src/writes/HubBindForm.tsx
  - desktop/web/src/writes/RoleBindForm.tsx
  - desktop/web/src/writes/hub-bind-form.css
  - desktop/web/src/writes/profileRules.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/RuntimeForm.tsx
  - desktop/web/src/writes/hubChangeLines.ts
  - desktop/web/tests/roles-hub-logic.test.ts
  - desktop/web/tests/roles-hub-turns.test.ts
  - desktop/web/tests/live-api.test.ts
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - ts/package.json
  - ts/bun.lock
  - ts/packages/ui/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 入口
- 页头第一个按钮从 `<DisabledAction label="保存当前为方案…" />` 换成 `src/writes/PresetSaveForm.tsx` 导出的 `PresetSaveAction`；按钮文字逐字「保存当前为方案…」，`variant="secondary"`、`size="md"`，**一直可点**（加载、出错、离线各态都可点，与 [新建 profile] 同口径）。
- 页头按钮次序不变：`['保存当前为方案…', '新建 profile', '刷新']`。
- `RolesPage.tsx` 删掉 `DisabledAction` 的 import；新增 `import { PresetSaveAction } from '../writes/PresetSaveForm';` 与 `import { roleName } from './readonly1/roles-logic';`（只引 `roleName` 一个值）；页头写成 `<PresetSaveAction reload={reload} roleLabel={roleName} />`。
- `RolesPage.tsx` 的其余部分一字不改：并行四读、失败判定、`load={loadRoles}`、children 那一行、页头说明原文、四个禁词（`preview`、`getOperation`、`usePreset`、`setPluginEnabled`，注释也算）一个都不许出现；从 `'../api'` 引入的值仍只许是那 12 个读函数白名单里的。
- 角色中文名由 `roleLabel` prop 传进表单（`src/writes` 不跨层引 `src/pages`）；`roleLabel(code)` 的取值照 `roles-logic.ts` 的 `roleName`。

### 表单（对话框标题逐字「保存当前为方案」）
- 内外两层写法照 T052：外层组件只做 `const { start, flow } = useWriteFlow(reload);`、`{open && <PresetSaveFormDialog … onConfirm={start} />}`、`<WriteFlow flow={flow} />`；内层组件只在打开时挂载，字段状态、预填、底部预览都在内层。
- 内层挂载时用 `Promise.all([getRoles(), getPresets()])` 各读一次：三种状态——读取中（底部显示「预览中…」）、读到、读不出（给原因句「读不出当前的角色绑定与方案列表：稍后再试」，[确认…] 不可点）。
- 字段一：**方案名**（`TextField`，`label="方案名"`，`mono`）。取值非空且 `validId(name)` 为真才合法。空 → 错误句「方案名要填」；非空但不合法 → 错误句「方案名不合法：小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符」。不合法时不调预览，[确认…] 不可点。
- 字段二：**说明**（`TextField`，`label="说明"`）。按码点计数 ≤200 且不含 C0 控制字符（≤0x1f）、DEL（0x7f）与孤立代理项才合法（与服务 `cleanText(value, 1, 200)` 同一口径）。超长或含控制字符 → 错误句「说明最多 200 个字，不能有控制字符」。**空说明不算错**：不传这个键即可。
- 字段三：**要存的角色**。只列读到的 `explicit === true` 的角色，次序照读到的次序；每个角色一个 `Checkbox`，`label` 是角色中文名 `roleLabel(code)`；缺省全选。一个都没勾 → 原因句「还没有勾要存的角色」，不调预览，[确认…] 不可点。
- 一个显式绑定都没有时（读到的 roles 里 `explicit === true` 的一个都没有）→ 原因句「还没有写出绑定的角色：先在角色卡上用 [更改…] 写出绑定」，不调预览，[确认…] 不可点。
- 字段四：**覆盖**。方案名在读到的 presets 名单里 → 表单上显示「会覆盖方案 X」，并给一个 `Checkbox`，`label` 逐字「覆盖方案 X」。没勾 → 不调预览、[确认…] 不可点；勾了才带 `force`。**方案名一改就把这个勾复位成没勾**（否则改个名会带着 force 走）。
- 每次打开都重算：表单关掉（[取消]、Esc、点 [确认…]）后未保存的取值与勾选状态一并丢弃；再打开时按**当时**读到的 roles 与 presets 重新算（角色清单、缺省全选、重名判断、覆盖勾选都重置）。取消后再开、外部改了绑定后再开，都按当时的数据预填。

### 参数与预览
- `buildArgs()` 返回 `{ name, roles }`：
  - `roles` **一律显式带**（全选也带），按读到的角色次序排；不带 `roles` 的那次预览/执行与服务要求不符。
  - `description` 非空才带（空串不传这个键）。
  - `force` 只在「重名且勾了覆盖」时才带，值是字符串 `'true'`。
- 预览用 `useLivePreview('preset.save', args, canPreview)`；`canPreview` = 读到了数据 && 显式角色至少一个 && 至少勾了一个 && 方案名合法 && 说明合法 &&（不重名 || 勾了覆盖）。
- 底部显示：`dispatchCommand(result.command)`、警告行、内核报错原文；样式复用 `./hub-bind-form.css` 的 `hb-*` 类（不新建 CSS 文件、不写内联 `style={{`、不写死颜色）。
- [确认…] 可点的条件 = `canPreview && current && result !== null && result.ok`；点 [确认…] **先关表单，再 `start(spec)`**（同一批更新里）。
- 内核的报错原文照显示：预览阶段在表单底部显示「ERROR …」原文（[确认…] 随之不可点）；执行阶段走既有确认框与终态（`failed` / `partiallyWritten` / `unknown` 等分支照旧）。

### 写流程（useWriteFlow 的三处接线）
- `titleOf`：`preset.save` → 逐字 `保存方案 ${args.name}？`。
- `successTextOf`：`preset.save` → 逐字 `已保存方案 ${args.name}`。
- `changeSummaryOf`：`preset.save` → 不覆盖时 `方案表里加上 ${args.name}：存 ${roles.join('、')}`；带 force（覆盖）时 `覆盖方案 ${args.name}：存 ${roles.join('、')}`（`roles` 照 `args.roles` 的数组，次序照表单给的次序）。
- `readSnapshot`：`preset.save` 读 `getPresets()`，用 `presetRemoveSnapshot`（`snapshots.ts` 不改）。成功类不看快照变化；失败类按既有语义（快照变了 → 部分写入）。
- 执行分派：`preset.save` → `savePreset(...)`，加在 `setPluginEnabled` 兜底之前（既有 action 的分派与文字一个都不改）。
- `dangerOf` 不改：保存方案不是危险动作（覆盖也用 primary 样式）。
- 写完由 `useWriteFlow(reload)` 触发整页重读（页头拿到的那个 reload），重读后方案表里出现新方案。

### api.ts（三个改动，其余不动）
- `WriteAction` 加一行 `  | 'preset.save'`（既有 13 个成员一个不丢）。
- `writeArgs` 加一条规则：`force` 键的值是 `'true'` 时转成 JSON 布尔 `true`（其余键值原样传）；`number`、`cadence_seconds` 转数字的既有规则、空串与空数组不传的既有规则一个都不改。预览与执行共用这一份规则。
- 新导出 `export function savePreset(args: { name: string; roles: string[]; description?: string; force?: string }, confirmation: string): Promise<HttpReply<null>>`：
  - 真实模式：`POST /api/v1/presets/${encodeURIComponent(args.name)}/save`，正文恰是 `{ ...writeArgs(w), confirmation }`，`w` 是 `args` 去掉 `name`（name 走路径段，服务会把路径参数压正文）。
  - 桩模式：`mockSavePreset(args, confirmation)`（args 含 `name`，与预览时收的那一份逐键相同）。

### 桩（mock/writes.ts，四处改动）
- `baseArgv` 加 `preset.save` 分支，逐字照服务 `buildWriteArgv`：`['config','preset','save', name]`，有说明加 `--description=<说明>`，有 roles 加 `--roles=<roles.join(',')>`，`force === 'true'` 时加 `--force`。
- `NEW_ACTIONS` 加 `'preset.save'`（写函数的确认号与参数核对靠它）。
- `previewData` 加 `preset.save` 分支：`binding_changes: []`、`resources: ['presets']`；**这个分支不许插进 `'role.set'` 分支内部**（t051 S02 从 `'role.set'` 起取 700 字符找 `binding_changes` 与 `resources: ['roles']`），放在 role.set 分支之前或整个 role.set 分支之后都行。
- 新导出 `mockSavePreset(args, confirmation)` → `confirmWrite('preset.save', args, confirmation)`。
- `WriteScenario` 恰 27 个值，一个都不加；代码（去注释）里不出现 `step-low`；桩数据（`src/mock/*.json`）一个字不改。

### 兼容性（本片推翻的旧断言，逐处写明只改哪一处）
以下文件的这一处要改，**只改这一处**，其余一个字不动：
- `tests/test_gate_t009_baseline.py`
  - `:2376` 的 it 标题里「[保存当前为方案…] 禁用」改成「[保存当前为方案…] 可点」；`:2381` 的 `expect(buttons[0].disabled).toBe(true)` 改成 `toBe(false)`（可加 `data-variant` 为 `secondary`、`data-size` 为 `md` 的断言）。`:2380` 的按钮次序断言照旧。
  - `:2957` 的 it 标题里「要填表单的写入口仍禁用且悬停出「第二阶段接入」」这一段删掉（角色页再没有这个入口），改成「可用按钮只在白名单里」这一段即可；`:2964` 的 `outsideWhitelist([...])` 数组里加 `'保存当前为方案…'`；`:2966-2969` 的 `later` 与三行 tips 断言删掉。`:2965` 的 `expect(disabledButtons().length).toBeGreaterThan(0)` 照旧（还有 6 个禁用按钮）。
- `tests/test_gate_t024_baseline.py`
  - `:305` 的 `assert '<DisabledAction label="保存当前为方案…"' in text` 改成断言 RolesPage 原文里有 `'PresetSaveAction'`（不许靠加注释凑记号——注释也算正文，所以只能用真记号）。
  - `:1088` 的 it 标题里「角色页禁用数 7」改成 6；`:1095-1096` 改成断言 `[保存当前为方案…]` 可点（`disabled` 为 false）、`data-variant` 为 `secondary`、`data-size` 为 `md`；`:1101` 的 `tipOf(save)` 那句删掉（save 不再禁用，没有提示）；`:1106` 的 `toBe(7)` 改成 `toBe(6)`。`:1094` 的页头次序断言照旧。
- `tests/test_gate_t038_baseline.py`
  - `:109` 的常量 `PAGE_HEAD_DISABLED = "保存当前为方案…"` 改成页头入口的记号 `'PresetSaveAction'`；`:413-414` 改成「页头两个按钮（PresetSaveAction、NewProfileAction）应照旧」——即 `PresetSaveAction` 与 `NewProfileAction` 都在 RolesPage 原文里。
- `tests/test_gate_t045_baseline.py`
  - `:125-127` 的常量 `ROLES_PAGE_DISABLED = 7` 改成 6（注释里的构成同步改成「方案条的「切换…」1 + planner 的「改绑定…」1 + 四个缺省行的「恢复缺省…」4 = 6」）。
  - `:1231-1233` 的探针 it 标题里的 7 改成 6，`toBe(7)` 改成 `toBe(6)`。`:553-563` 的 page-app 核对（禁用数与 it 标题正则）不用改——它跟常量走。
- `tests/test_gate_t048_baseline.py`
  - `:289-292` 的页头三枚记号里，`'<DisabledAction label="保存当前为方案…" />'` 这一枚换成 `'<PresetSaveAction'`（RolesPage 里写的是 `<PresetSaveAction reload={reload} roleLabel={roleName} />`）；另两枚照旧。
- `tests/test_gate_t051_baseline.py`
  - `:160-162` 的常量 `ROLES_PAGE_DISABLED = 7` 改成 6（注释里的构成同步改成 6 的构成）。
  - `:1207` 的探针 `toBe(7)` 改成 `toBe(6)`（它那一句的 it 标题里的 7 也改）。
- `desktop/web/tests/page-app.test.tsx`
  - `:93` 的 it 标题改成「角色页 6（方案条的 [切换…]、planner 改绑定…、4 个缺省行恢复缺省…）、运行时页 5、总览 0」；`:95` 的 `toBe(7)` 改成 `toBe(6)`。`:91` 的 describe 标题「写入口个数（过渡）」一字不动（t045 S07 钉着）。
- `desktop/web/tests/writes-hub-bind.test.tsx`
  - `:297` 附近的构成注释、`:299` 的 describe 标题「桩下角色页禁用按钮实测 7」改成 6；`:311` 的 it 标题与构成注释改成 6 的构成（方案条 [切换…] 1 + planner 改绑定… 1 + 四个缺省行恢复缺省… 4 = 6）；`:317` 的 `toBe(7)` 改成 `toBe(6)`。`:318-320` 的两条构成断言照旧。

### 边界输入
- 一个显式绑定都没有：给原因句、[确认…] 不可点、不调预览（页头入口仍可点）。
- 方案名与现有方案重名：显示「会覆盖方案 X」，不勾覆盖就不调预览、[确认…] 不可点；勾了才带 `force`。
- 方案名改了：覆盖勾选复位成没勾（不带着 force 走）。
- 说明留空：不传 `description` 键（服务端 `description` 必须是 1–200 码点，空串会被拒）。
- 说明超过 200 码点或含控制字符：当场错误句、不调预览。
- 打开之后别人新建了同名方案：内核在预览或执行时报「方案 X 已存在：要覆盖加 --force」，原文照显示，不悄悄覆盖。
- 读不出（`getRoles()` 或 `getPresets()` 失败）：给原因句、[确认…] 不可点。
- 对话框关着时：DOM 里没有这个表单的任何字段与 [取消]/[确认…]（`Dialog` 关着时 `return null`，内层组件根本不挂载）。
- 预览失败（服务没回应 / 信封 ok 为假）：底部显示错误原文，[确认…] 不可点，不自动重试（照既有表单）。
- 写流程失败（409 / 5xx / 超时 / 拒绝 / 过期）：照既有 `useWriteFlow` 与 `WriteConfirmDialog` 的分支显示，不加新分支、不改既有文案。

### 并发、取消与状态变化
不适用——本片不加并发、不加计时器（除既有 `useLivePreview` 的 300ms 防抖）、不加网络调用；同一时刻只有一个开着的表单（关掉即丢弃未确认的取值，内层组件随之卸载）。

### 写法钉死（门禁与包内测试按源码文本查这几处，逐字照抄）
1. `desktop/web/src/writes/PresetSaveForm.tsx`（新文件）：
   - 只导出 `PresetSaveAction`（外加必要的类型导出），入口按钮文字逐字「保存当前为方案…」，有 `variant="secondary"` 与 `size="md"`。
   - 对话框标题逐字「保存当前为方案」；字段 `label="方案名"` 与 `label="说明"`；`useLivePreview('preset.save', …)` 在位；`<WriteFlow flow={flow} />` 在位；[确认…] 的门控里能看到 `current`、`result.ok`、`onClose`。
   - 逐字提示句在位：「方案名要填」「方案名不合法：小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符」「说明最多 200 个字，不能有控制字符」「还没有写出绑定的角色：先在角色卡上用 [更改…] 写出绑定」「还没有勾要存的角色」「会覆盖方案」「覆盖方案 X」。
   - 复用 `import './hub-bind-form.css';`；不新建 CSS 文件；不写内联 `style={{`；不写死颜色；不出现禁词（`XMLHttpRequest` / `EventSource` / `WebSocket` / `dangerouslySetInnerHTML` / `innerHTML` / `outerHTML` / `insertAdjacentHTML` / `eval(` / `new Function` / `document.write` / `srcdoc` / `DOMParser` / `matchMedia` / `scrollIntoView` / `ResizeObserver` / `IntersectionObserver` / `role="status"`）；不跨层引 `src/pages`（角色中文名走 prop）。
2. `desktop/web/src/api.ts`：`WriteAction` 加 `  | 'preset.save'`；`writeArgs` 里有 `force` 这一条规则（`'true'` → 布尔 `true`），`number`/`cadence_seconds`/`asNumber(` 仍在；新导出 `export function savePreset(`，真实模式路径 `/api/v1/presets/${encodeURIComponent(args.name)}/save`，正文 `{ ...writeArgs(w), confirmation }`，桩模式 `mockSavePreset(`。
3. `desktop/web/src/mock/writes.ts`：`baseArgv` 有 `preset.save` 分支（`config`、`preset`、`save`、name、`--description=`、`--roles=`、`--force`）；`NEW_ACTIONS` 里有 `'preset.save'`；`previewData` 有 `preset.save` 分支（`binding_changes: []`、`resources: ['presets']`）；新导出 `export function mockSavePreset(`，走 `confirmWrite('preset.save', …)`；`WriteScenario` 仍是 27 个值；代码里不出现 `step-low`。
4. `desktop/web/src/writes/useWriteFlow.ts`：三张文字表各有 `preset.save` 一支（`保存方案 ${args.name}？` / `已保存方案 ${args.name}` / 方案表里加上或覆盖的那句）；`readSnapshot` 有 `preset.save` 分支（`getPresets()` + `presetRemoveSnapshot`）；执行分派有 `preset.save` → `savePreset(...)`（排在 `setPluginEnabled` 兜底之前）；既有动作的分支与文字一个不改。
5. `desktop/web/src/pages/RolesPage.tsx`：`<PresetSaveAction reload={reload} roleLabel={roleName} />`；`NewProfileAction reload={reload}` 照旧；页头说明原文照旧；不再出现 `DisabledAction`；四个禁词一个都不出现。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件** `tests/test_gate_t053_baseline.py`（只读；基线上还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **`desktop/web/src/api.ts`**：加 `WriteAction` 的 `  | 'preset.save'`；`writeArgs` 加 `force` 这一条规则（`'true'` → 布尔 `true`，其余规则不动）；新导出 `savePreset`（真实模式 `POST /api/v1/presets/${encodeURIComponent(args.name)}/save`，正文 `{ ...writeArgs(w), confirmation }`，`w` 不含 `name`；桩模式 `mockSavePreset(args, confirmation)`）。
3. **`desktop/web/src/mock/writes.ts`**：`baseArgv` 的 `preset.save` 分支、`NEW_ACTIONS` 加 `'preset.save'`、`previewData` 的 `preset.save` 分支（不插进 role.set 分支内部）、新导出 `mockSavePreset`。
4. **`desktop/web/src/writes/useWriteFlow.ts`**：三张文字表加 `preset.save` 一支；`readSnapshot` 加 `preset.save` 分支（`getPresets()` + `presetRemoveSnapshot`）；执行分派加 `preset.save` → `savePreset(...)`；既有分支与文字一个不改。
5. **新建 `desktop/web/src/writes/PresetSaveForm.tsx`**：照「写法钉死」第 1 条与 Behavior contract 的「表单」一节实现（内外两层、四个字段、逐字提示、预填与重置规则、底部预览、[确认…] 门控与先关后 start）。复用 `./hub-bind-form.css` 的 `hb-*` 类，不新建 CSS。
6. **`desktop/web/src/pages/RolesPage.tsx`**：删 `DisabledAction` 的 import 与那一行；加 `PresetSaveAction` 与 `roleName` 两个 import；页头第一个按钮换成 `<PresetSaveAction reload={reload} roleLabel={roleName} />`。其余一字不改（并行四读、失败判定、`load={loadRoles}`、children 那一行、页头说明原文、四个禁词、api 读函数白名单）。
7. **新建 `desktop/web/tests/writes-preset-save.test.tsx`**（不许 `skip`/`only`/`todo`——`tests/test_gate_t002_baseline.py:1496` 会扫全部 `*.test.*`；测真实实现，不把业务逻辑抄一份进测试；不 mock 被测组件）：
   - 用 `@testing-library/react` 的 `render` 渲染 `PresetSaveAction`（不挂整页 App），用 `setLiveClientForTests` 注入假服务记录预览请求与写请求（照 `desktop/web/tests/writes-role-bind.test.tsx` 的写法）。
   - (a) 只列已显式绑定的角色（桩下是 planning_review 与 execution）、缺省全选；预览请求的 args 里 `roles` 恰是这两个、按读到的次序。
   - (b) 方案名不合规（如 `Bad Name`）时当场出现错误句、[确认…] 不可点、不发预览请求。
   - (c) 方案名与现有方案重名（`default`）：表单上出现「会覆盖方案 default」，不勾覆盖时 [确认…] 不可点；勾上「覆盖方案 default」后预览/执行的 args 里带 `force: 'true'`（用假客户端看真实正文里 `force` 是布尔 `true`）。
   - (d) 点 [确认…]：表单关上、确认框开上（标题 `保存方案 <name>？`），确认后发 `POST /api/v1/presets/<name>/save`，正文带所选 `roles` 与 `description`，写完 `reload` 被调用。
   - (e) 一个显式绑定都没有时（假客户端让 `getRoles` 返回没有 explicit 的四行）：表单给原因句、[确认…] 不可点、不发预览请求。
   - (f) T052 的三种情形：取消后再开（回到缺省全选、覆盖勾选复位）、外部改了绑定后再开（按新的角色清单预填）、写完后再开（按当时的数据预填）。
   - **测试陷阱**：受控控件的取值不能只看 DOM，要断言**预览/执行请求的 args** 与 [确认…] 的可点状态；等防抖用真实计时器 `await sleep(450)` 再 `await flush()`（照现有表单测试的写法），不用假计时器。
   - **桩下的已知限制**：桩不改夹具（`src/mock/presets.json` 冻结），所以重读后方案表里不会真的多出新方案；用例断言请求正文与 `reload` 被调用，不断言方案表内容。
8. **逐处改旧断言**（照「兼容性」一节，逐条只改那一处）：
   - `tests/test_gate_t009_baseline.py`（:2376 的标题与 :2381、:2957 的标题与 :2964 的白名单、:2966-2969 四行）；
   - `tests/test_gate_t024_baseline.py`（:305、:1088 的标题、:1095-1096、:1101、:1106）；
   - `tests/test_gate_t038_baseline.py`（:109 的常量、:413-414）；
   - `tests/test_gate_t045_baseline.py`（:125-127 的常量、:1231-1233 的探针）；
   - `tests/test_gate_t048_baseline.py`（:289-292 的三枚记号里换掉 DisabledAction 那一枚）；
   - `tests/test_gate_t051_baseline.py`（:160-162 的常量、:1207 的探针）；
   - `desktop/web/tests/page-app.test.tsx`（:93 的标题、:95 的数）与 `desktop/web/tests/writes-hub-bind.test.tsx`（:297 的注释、:299 的 describe 标题、:311 的 it 标题与构成注释、:317 的数）。
   - 改完把每个文件里仍然钉着「7」或「禁用」的旧口径再搜一遍（关键字：保存当前为方案、第二阶段接入、ROLES_PAGE_DISABLED、toBe(7)），确认没有漏网的旧断言。
9. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → V04 → R01**（本 worktree 里若没有 `node_modules`，先跑 Setup 里的 `npm ci`）。R01 的墙钟可能逼近上限：可以分批跑（文件集合不许少，每批的 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
10. 写执行报告；遇到合同未定义的行为（例如门禁端交付的 `tests/test_gate_t053_baseline.py` 与合同的「写法钉死」有实质冲突），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t053_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test -- tests/writes-preset-save.test.tsx` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`，不得出现：`No test files found`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V04（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py -q` · cwd：仓库根 · 超时：3060s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：页头 [保存当前为方案…] 是可点的 secondary/md 按钮（一直可点，页头次序不变），点开「保存当前为方案」表单；RolesPage 的其余部分一字不改（并行四读、失败判定、`load={loadRoles}`、children 那一行、页头说明、四个禁词、api 读函数白名单）；目的：这一片只加一个入口，不许顺手改角色页的读法与只读部分；证据：V01、V02、G01、R01、scope。
- D02：表单只列已显式写出绑定的角色、缺省全选；一个显式绑定都没有时给原因句且 [确认…] 不可点；不合法时不调预览；目的：内核只存写出绑定的角色，界面不许让用户存不存在的绑定；证据：V01、V02、G01。
- D03：方案名按内核规则（`validId`）当场校验、说明按 1–200 码点且无控制字符校验，错误句逐字显示；重名时显示「会覆盖方案 X」，不勾覆盖就不调预览、[确认…] 不可点，勾了才带 `force: 'true'`，改方案名时覆盖勾选复位；目的：不悄悄覆盖同名方案，也不让内核回 400；证据：V01、V02、G01。
- D04：预览 → 确认 → 执行 → 重读 → 终态走既有写流程（先关表单再 start）；确认框标题「保存方案 <name>？」、成功轻提示「已保存方案 <name>」、变化区摘要有「方案表里加上」/「覆盖方案」两种；写完整页重读；目的：不新造一条写流程，写完方案表要出现新方案；证据：V01、V02、G01、R01。
- D05：`api.ts` 的 `preset.save` 成员、`writeArgs` 的 force→布尔 true 规则与 `savePreset`（真实模式路径与正文、桩模式 mockSavePreset）就位；桩的 `baseArgv`/`NEW_ACTIONS`/`previewData`/`mockSavePreset` 就位，`WriteScenario` 仍 27 个值、代码里不出现 `step-low`；`useWriteFlow` 的三张文字表、`readSnapshot` 分支与执行分派就位，既有动作的分支与文字一个不改；目的：预览与执行必须同一份参数（否则服务回 409），既有动作不许被碰；证据：G01、R01、V02。
- D06：新增 `desktop/web/tests/writes-preset-save.test.tsx`，覆盖 D02–D04 点名的每一项（含「同名勾覆盖后正文带 force: true」「没有显式绑定时给原因句」「取消后再开与外部改动后再开都按当时的数据预填」），测真实实现，不许 `skip`/`only`/`todo`；目的：验收看的是行为有没有被测住，不是测试文件在不在；证据：V01、V02、review。
- D07：旧断言逐处改到位：t009（:2376/:2381、:2957/:2964/:2966-2969）、t024（:305、:1088/:1095-1096/:1101/:1106）、t038（:109、:413-414）、t045（:125-127、:1231-1233）、t048（:289-292）、t051（:160-162、:1207）、`page-app.test.tsx`（:93/:95）、`writes-hub-bind.test.tsx`（:297/:299/:311/:317）——每处只改上面写明的那一处，其余一个字不动；目的：这些断言钉着「灰按钮 + 禁用数 7」，本片必然推翻，改法不许顺手改别的断言；证据：G01、R01、V02、scope。
- D08：所有修改都在允许集合内（可改 5 个源文件与 8 份既有测试/门禁文件，可新增 2 个文件），没有碰 forbidden_paths（`tests/test_gate_t053_*.py`、其余 45 份门禁基准、`readonly1/**`、`components/**`、`shell/**`、`live/**`、桩的 JSON 与 `quizs.ts`/`hub-roles.ts`、既有两个改绑定表单、`snapshots.ts`、`useLivePreview.ts`、`hub-bind-form.css`、`profileRules.ts`、`package.json` 与锁文件、`ts/packages/ui/**`、`scripts/**`）；目的：这一片不许顺手改别的片的地盘；证据：scope、review。
- D09：`npm test`、`npm run typecheck`、`npm run build` 全过，52 份既有门禁基准全过；目的：不能为了加一个入口把别处弄坏；证据：V02、V03、V04、R01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `writeArgs` 已经不是那份形状、服务侧 `preset.save` 的必填/可选键变了、`presetRemoveSnapshot` 不存在、`useLivePreview` 的签名变了、`Dialog` 关着时不再 `return null`），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `readonly1/**`、`components/**`、`snapshots.ts`、`useLivePreview.ts`、其余门禁基准、`package.json` 与锁文件、`ts/packages/ui/**`）。
- 门禁端交付的 `tests/test_gate_t053_baseline.py` 与本合同的「写法钉死」一节出现实质冲突（例如它要求按钮文字或对话框标题换一种写法、要求 `roles` 不显式带、要求 force 用别的写法）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id `t053-desktop-web-preset-save` 汇总，含返工版本；累计已用 0 次 → 本版留 2 次）
- max_wall_seconds_per_attempt: 9000
- max_wall_seconds_total: 18000（按 task-id 跨版本累计；累计已用 0 秒 → 剩余 18000 秒 ≥ 本版 2 × 9000 = 18000 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 25 分钟；实现 api/mock/useWriteFlow/RolesPage 40 分钟；新表单文件 35 分钟；新包内测试六条用例 35 分钟；逐处改旧断言 25 分钟；必要检查（G01、V01、V02、V03、V04、R01；R01 约 45–60 分钟、可分批跑）60 分钟；最终报告 5 分钟；总计约 225 分钟，单轮时限 9000 秒（150 分钟）——总量 18000 秒覆盖本版与一次返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D09，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
