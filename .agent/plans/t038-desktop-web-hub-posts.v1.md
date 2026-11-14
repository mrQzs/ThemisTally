# TASK: t038-desktop-web-hub-posts

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 25762d66dfc2c88c1ee28b8877edaee933412ef0
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在「角色与模型」页加一组**只读**的「七端岗位」（六行：岗位、运行时、模型、思考档位、来源、替补，不带操作列）：`desktop/web/src/api.ts` 新增读函数 `getHubRoles()`（真实模式 `GET /api/v1/hub/roles`、时限 30 秒、不回落桩；桩模式读 `config hub show --json` 的六行夹具）；`RolesPage` 的 `loadRoles` 并行读四个（`getRoles`/`getProfiles`/`getPresets`/`getHubRoles`），七端岗位读失败时**只在这一组**显示失败信封，四个角色那一组与 profile 表照常显示；思考档位照 D11 用 `EffortPair`，effective 传 null，显示「要求 X · 生效 未知」，不拿要求的档位顶替生效。

## Non-goals
- B 片（站主另登记）：改绑定入口、`hub.unset` 恢复缺省、`useWriteFlow` 与 `snapshots` 的 hub 分支、`HubBindForm`、`page-app.test.tsx:91` 的禁用钮计数 6→7、T009 `test_d11_probe_write_entries_disabled` 的退役。
- 不改页头说明（「四个角色各用哪个 CLI 与模型；方案可以一键切换」）与页头两个按钮；不新增 `*Page.tsx`；`src/mock` 下不新增 JSON（仍恰 14 份）；`src/pages` 顶层仍恰 9 个 `*Page.tsx`。
- 不改 `ts/packages/ui`（服务端）与内核（`scripts/`）；不改 `src/writes/` 的文字表与分派；不改 `desktop/web/src/pages/readonly2/`、`shellpages/`、`src/shell/`、`src/live/`。
- 不做「CLI 运行时页：手动登记运行时」那一片；不做 Quizs 那一块（提供方档案、证书状态）；不改 `mock/writes.ts` 的情景值（仍 22 个）。
- 本片不退役任何门禁基准（理由见 Repository facts 第 5 条）。

## Repository facts
以下事实均在基线 e390582dc6 上核对过（行号按该基线）。
- 入口与调用关系：
  - `desktop/web/src/api.ts`：所有读函数在这里（`getRoles`/`getProfiles`/`getPresets` 三个读在 `:390-406` 附近）；夹具分支用 `read(command, produce)`（`:335` 附近，`?mock=loading` 挂起、`?mock=error` 回错误信封、其它模式回 `produce(mode)` 的信封）；真实分支用 `liveClient()`（非 null 即真实模式）。**T037 已落地**：`setHubRole(args:{post,profile,fallback?}, confirmation)`、`unsetHubRole(post, confirmation)`，`WriteAction` 已含 `'hub.set' | 'hub.unset'`（本片不接线，只作事实）。
  - `desktop/web/src/pages/RolesPage.tsx`：`loadRoles` 用 `Promise.all([getRoles(), getProfiles(), getPresets()])`，失败时按 `roles→profiles→presets` 顺序返回第一个失败信封；页面不传 `isEmpty`；页头说明与两个页头按钮一字不改。
  - `desktop/web/src/pages/readonly1/roles-RolesView.tsx`：`RolesViewData` 现在只有 `roles`/`profiles`/`presets` 三个字段；渲染顺序是 PresetBar → 角色卡网格（`article[data-role]`）→ `ProfilesTable` → `PresetsTable`。
  - `desktop/web/src/pages/readonly1/roles-RoleCard.tsx`：写法样板——`runtime（adapter）`、`provider/model`、思考档位一律经 `EffortPair`、缺省标签 `<Tag tone="neutral">默认</Tag>`。
  - `desktop/web/src/pages/readonly1/roles-logic.ts`：纯函数文件（`roleName`/`normalizeRole`/`profileRefs` 等），只 `import type` 自 `../../api`。
  - `desktop/web/src/components/EffortPair.tsx`：`requested` 空 → `<span class="tt-effort" data-state="none">—</span>`；`effective` 为空而 `requested` 有值 → `data-state="unknown"`，文字「要求 X · 生效 未知」。
  - `desktop/web/src/components/Table.tsx`：`<tr>` 目前只有 `key`/`tabIndex`/`data-selected`/焦点与点击处理，**没有行属性的入口**；`Table` 需要 `columns`/`rows`/`rowKey`/`aria-label`，可选 `rowHeight`、`className`（`className` 加在 `.tt-table-wrap` 滚动容器上）。
  - `desktop/web/src/mock/profiles.json`：只有两个 profile：`step-high`（runtime pi、adapter pi、provider bb、model step-5-preview、thinking high）与 `step-low`（runtime pi、adapter pi、provider bb、model step-5-mini、thinking low）。
- 服务与内核约定（只读，本片不改）：
  - `ts/packages/ui/src/readroutes.ts:609-612`：`api.hub.roles.get` = `GET /api/v1/hub/roles` → `config hub show --json`，时限 `DEFAULT_TIMEOUT`（30 秒）；`:641` 的 `READ_ROUTE_SPECS` 同一条也是 30 秒。
  - `ts/packages/ui/src/redaction.ts:101-117` 的 `HUB_ROLES_ALLOW`：`posts[*]` 只放行 `post`（枚举 coordinator/planner/contract/gate/audit/exec）、`source`（default/config）、`allowed_adapters[*]`、`adapter`、`provider`、`model`、`thinking`、`profile`、`runtime`，以及 `fallback` 下的 `adapter`/`provider`/`model`/`thinking`/`profile`/`runtime`。不合格的值会变成字面量 `<redacted>`，前端照字符串显示。
  - `scripts/kit_roles.py:1173-1181`（`_hub_rows`）：每行键为 `post`、`source`、`allowed_adapters`、`adapter`、`provider`、`model`、`thinking`、`profile`、`runtime`、`fallback`；缺省行的 `profile` 与 `runtime` 是 null。
  - `scripts/kit_roles.py:80-88`（`HUB_DEFAULTS`，缺省名册）：coordinator = quizs / deepseek / deepseek-flash / high，fallback = {adapter pi, provider dsf, model deepseek-flash, thinking high}（**只有这四个键**，没有 profile/runtime）；planner = claude-code / provider **null** / claude-opus-5-5 / max，fallback null；contract = pi / minimax / MiniMax-M3.1-Flash / high；gate = pi / cc-switch-zhipu-glm / glm-5.3 / high；audit = pi / minimax / MiniMax-M3.1-Flash / max；exec = pi / cc-switch-step-fun / step-5-preview / high。fallback 恒为 null 或对象。
  - `scripts/kit_roles.py:68-75`（`HUB_POST_ADAPTERS`，岗位允许的适配器）：coordinator = (quizs, pi)、planner = (claude-code,)、contract = (pi, **quizs**)、gate = (pi,)、audit = (pi, **quizs**)、exec = (pi,)。**规划报告第 1 节的表把 contract/audit 写成只许 pi，与仓库不符；本片以仓库为准**（本片只用这个名单做展示与纯函数测试，不做绑定）。
- 门禁事实：
  - `tests/test_gate_t009_baseline.py:136-138`：`ALLOWED_API_READS` 已含 `getHubRoles`（站主 2026-11-13 的门禁准备提交已随本基线落地）→ `test_d13_page_files_wiring` **不需要退役**。
  - `tests/test_gate_t009_baseline.py:1054-1067`：T009 探针的 api 替身是「展开真实模块再给每个导出套 spy」，新增导出会被自动包住；`:1120-1122` 的 `sectionNamed` 按 h2 标题精确匹配；`:1130-1139` 的 `tableRows` 作用在指定表上；`:2210`/`:2250`/`:3078` 用 `article[data-role]` 数四张角色卡（新表是 `<tr>`，不冲突）。
  - `tests/test_gate_t024_baseline.py:106`：`RolesPage.tsx` 的原文（注释也算）不许出现 `preview`、`getOperation`、`usePreset`、`setPluginEnabled`。
  - `tests/test_gate_t036_baseline.py:362-373` 与 `tests/test_gate_t024_baseline.py:119-121`：`src/mock` 恰 14 份 JSON、`src/pages` 顶层恰 9 个 `*Page.tsx`。
  - `tests/test_gate_t006_baseline.py:3310-3318`：`api.ts` 的读函数按**包含**核对（不卡恰好），加 `getHubRoles` 不破门禁；`:199-203` 的禁用词表（网络词与危险 HTML 写入/动态求值类词）里没有模型名。
- 工具链：`desktop/web/package.json`：`npm test` = `vitest run`；`npm run typecheck` = `tsc --noEmit`；`npm run build` = `tsc --noEmit && vite build`；`npm run check:contract` = `node scripts/token-contract.mjs`。`desktop/web/tsconfig.json` 的 `include` 只有 `["src","vite.config.ts"]`——**tests/ 不进 tsc**，所以 `RolesViewData` 新增必填字段不需要改既有测试的构造。
- 基线检查（合同端只读探查，未在本回合运行）：本回合没有执行环境，未跑 `npm test` / `pytest`。执行端开工第一件事是在 worktree 里跑 `npm test`（cwd `desktop/web`）与 `R01` 的门禁基准；已知失败应写用例与错误指纹。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/pages/readonly1/roles-logic.ts
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/components/Table.tsx
  - desktop/web/tests/live-api.test.ts
- allowed_new_files:
  - desktop/web/src/mock/hub-roles.ts
  - desktop/web/src/pages/readonly1/roles-HubPosts.tsx
  - desktop/web/tests/page-hub.test.tsx
  - desktop/web/tests/roles-hub-logic.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t038_*.py
  - ts/packages/ui/**
  - scripts/**
  - desktop/web/src/writes/**
  - desktop/web/src/pages/readonly2/**
  - desktop/web/src/shellpages/**
  - desktop/web/src/shell/**
  - desktop/web/src/live/**
  - desktop/web/src/mock/*.json
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：
  - 真实模式（`liveClient()` 非 null）：`getHubRoles()` 走 `client.get<HubRolesData>('/api/v1/hub/roles', undefined, 30)`，**不回落桩**；服务回的错误信封原样透传。
  - 桩模式：`getHubRoles()` 走 `read(['config','hub','show','--json'], …)`，信封 `command` 是 `['config','hub','show','--json']`、`ok=true`、`exit_code=0`、`data` 是六行的 `{posts:[…]}`。`?mock=empty` 也照样给六行；`?mock=loading` 挂起；`?mock=error` 回错误信封（`read()` 的既有行为，不另写）。
  - 页面：`loadRoles` 用 `Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()])` **并行**发四个读；前三个读里第一个坏的（`!ok || data == null`）按 `roles→profiles→presets` 顺序整页返回那个失败信封（与现在一样）；hub 的信封**整个**放进 `RolesViewData.hub`，不参与整页失败判定。
- 边界输入：
  - 行字段为 null/缺键时一律显示「—」（`runtime`、`adapter`、`provider`、`model`、`profile` 都是）。
  - 运行时列格式：`{runtime ?? '—'}（{adapter ?? '—'}）`（照 RoleCard）。
  - 模型列格式：`{provider ?? '—'}/{model ?? '—'}`；planner 的 provider 为 null → 显示 `—/claude-opus-5-5`。
  - 思考档位列：`<EffortPair requested={row.thinking} effective={null} />`；`thinking` 有值 → 显示「要求 X · 生效 未知」（`data-state="unknown"`）；`thinking` 为 null → 显示「—」（`data-state="none"`）。**不拿要求的档位顶替生效**。
  - 来源列：`source === 'default'` → `<Tag tone="neutral">默认</Tag>`；`source === 'config'` → 显示该行的 `profile` id（等宽）。
  - 替补列：`fallback` 为 null → 「—」；否则依次是「替补 profile（没有就省掉这一段）· `runtime（adapter）` · `provider/model`」三段用「 · 」连接；四键替补（coordinator 缺省行，没有 profile/runtime）→ `—（pi） · dsf/deepseek-flash`；六键替补（配置行）→ `step-low · pi（pi） · bb/step-5-mini`。替补的思考档位不出现在这一列（那一列只讲本岗位的档位）。
  - 岗位列显示中文名：coordinator 协调人、planner 规划端、contract 合同端、gate 门禁端、audit 审核端、exec 执行端；未知岗位码原样显示岗位码。
  - 七端岗位的表 `aria-label` 是「七端岗位」，`Section` 标题是「七端岗位」（不含「profile」「方案」字样，避免被按标题选区块的探针误选）；每一行带 `data-post="<岗位码>"`；列恰好六列：岗位、运行时、模型、思考档位、来源、替补（**没有操作列、没有按钮**）。
  - 这一组放在角色卡网格之后、profile 表之前。
- 错误与重试：
  - hub 读失败时，这一组显示「没能读到七端岗位：命令 {command.join(' ')} 返回退出码 {exit_code}。」并把 `messages` 放进一个 `pre`（照 `overview-ConfigChanges.tsx` 的写法）；四个角色卡、profile 表、方案表照常显示，整页仍是 `data` 态。
  - 不做重试（与现有读函数一致）。
- 并发、取消与状态变化：不适用——本片没有取消、没有并发写；四个读一次性并行，读的先后不影响渲染顺序（表格按 `posts` 的顺序渲染，桩数据按 coordinator、planner、contract、gate、audit、exec 排）。
- 兼容性：`api.ts` **只新增**导出（`HubPostRow`、`HubRolesData`、`getHubRoles`），既有导出与签名一个不改；`WriteAction` 不变；`mock/writes.ts` 的 22 个情景值不变；`src/mock` 仍恰 14 份 JSON；`src/pages` 顶层仍恰 9 个 `*Page.tsx`；既有测试文件除 `live-api.test.ts`（只加不改）外都不许改。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。
2. **api.ts 加读函数**（新代码照现有读函数的写法，不新造机制）：
   - 加类型：
     ```ts
     export interface HubPostFallback {
       adapter: string | null;
       provider: string | null;
       model: string | null;
       thinking: string | null;
       profile: string | null;
       runtime: string | null;
     }
     export interface HubPostRow {
       post: string;
       source: 'default' | 'config';
       allowed_adapters: string[];
       adapter: string | null;
       provider: string | null;
       model: string | null;
       thinking: string | null;
       profile: string | null;
       runtime: string | null;
       fallback: HubPostFallback | null;
     }
     export interface HubRolesData {
       posts: HubPostRow[];
     }
     ```
     （服务可能缺 `profile`/`runtime`/`fallback` 里的键，运行时按 null 处理。）
   - 加读函数（照 `getRoles` 的写法）：
     ```ts
     export function getHubRoles(): Promise<Envelope<HubRolesData>> {
       const client = liveClient();
       if (client) return client.get<HubRolesData>('/api/v1/hub/roles', undefined, 30);
       return read(['config', 'hub', 'show', '--json'], () =>
         okEnvelope(['config', 'hub', 'show', '--json'], clone(HUB_ROLES_POSTS)),
       );
     }
     ```
     真实分支**不**回落桩；桩分支用 `clone()` 深拷贝（照其它读函数）。
   - `import { HUB_ROLES_POSTS } from './mock/hub-roles';`（照其它夹具的 import 写法）。
3. **桩 `desktop/web/src/mock/hub-roles.ts`（新文件，只能 .ts）**：导出 `export const HUB_ROLES_POSTS: HubRolesData`，类型用 `import type { HubRolesData } from '../api';`（纯类型导入，编译后擦除，不产生运行时循环）。六行按 `scripts/kit_roles.py` 的缺省名册与 `src/mock/profiles.json` 的两个 profile 写死，逐行如下（`allowed_adapters` 按 `HUB_POST_ADAPTERS`）：
   1. coordinator：source `default`，allowed `['quizs','pi']`，adapter `quizs`，provider `deepseek`，model `deepseek-flash`，thinking `high`，profile null，runtime null，fallback `{ adapter: 'pi', provider: 'dsf', model: 'deepseek-flash', thinking: 'high', profile: null, runtime: null }`。
   2. planner：source `default`，allowed `['claude-code']`，adapter `claude-code`，provider **null**，model `claude-opus-5-5`，thinking `max`，profile null，runtime null，fallback null。
   3. contract：source `config`，allowed `['pi','quizs']`，adapter `pi`，provider `bb`，model `step-5-preview`，thinking `high`，profile `step-high`，runtime `pi`，fallback `{ adapter: 'pi', provider: 'bb', model: 'step-5-mini', thinking: 'low', profile: 'step-low', runtime: 'pi' }`。
   4. gate：source `default`，allowed `['pi']`，adapter `pi`，provider `cc-switch-zhipu-glm`，model `glm-5.3`，thinking `high`，profile null，runtime null，fallback null。
   5. audit：source `default`，allowed `['pi','quizs']`，adapter `pi`，provider `minimax`，model `MiniMax-M3.1-Flash`，thinking `max`，profile null，runtime null，fallback null。
   6. exec：source `config`，allowed `['pi']`，adapter `pi`，provider `bb`，model `step-5-mini`，thinking `low`，profile `step-low`，runtime `pi`，fallback null。
   这样覆盖了：来源是配置与缺省、带与不带替补、quizs 与 pi、provider 为 null、替补的四键与六键两种形状。行序固定为 coordinator、planner、contract、gate、audit、exec。
4. **RolesPage.tsx**：
   - `import { …, getHubRoles, type HubRolesData, … } from '../api';`（`getHubRoles` 已在 T009 的 `ALLOWED_API_READS` 里）。
   - `loadRoles` 改成并行四个读：`Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()])`；失败判定仍只看前三个（`[roles, profiles, presets].find((e) => !e.ok || e.data == null)`，顺序不变）；成功时 `data` 里多带 `hub`（整个信封）。
   - 页头说明、页头两个按钮、`PageFrame` 的用法一律不动。
   - **本文件的原文（注释也算）不许出现 `preview`、`getOperation`、`usePreset`、`setPluginEnabled`**（T024 S15）。
5. **roles-RolesView.tsx**：`RolesViewData` 加 `hub: Envelope<HubRolesData>`；在角色卡网格 `</div>` 之后、`ProfilesTable` 之前渲染 `<HubPosts hub={data.hub} />`；`import type { Envelope, HubRolesData } from '../../api'`。
6. **roles-HubPosts.tsx（新文件）**：
   - `Section title="七端岗位"`（不要 description，不加次级标签或说明文字）；内容是 `Table`，`aria-label="七端岗位"`，`className="rl-table rl-hub"`，`rowHeight={40}`。
   - 每行一个 `data-post`（见第 7 步的 Table 加法式 prop）；`rowKey` 用岗位码。
   - 列头依次：岗位、运行时、模型、思考档位、来源、替补；**没有操作列**，格子里没有按钮。
   - 字段格式按 Behavior contract 的「边界输入」逐条实现（`runtime（adapter）`、`provider/model`、EffortPair（effective 传 null）、来源 Tag「默认」/profile id、替补三段格式）。
   - 岗位列用 `roles-logic` 的 `hubPostName(post)`。
   - hub 读失败时，这一组渲染「没能读到七端岗位：命令 … 返回退出码 N。」加 `messages` 的 `pre`（照 `overview-ConfigChanges.tsx` 的 `ov-change-err` 写法，用本组自己的类名）。
   - 视图只收数据与回调：从 `../../api` 只许 `import type`（T009 `test_d13_views_do_not_call_api`）。
7. **components/Table.tsx（加法式改动）**：加一个**可选** prop `rowAttrs?: (row: Row) => Record<string, string>`，在 `<tr>` 上展开这些属性；不传时 DOM 与现在完全一样；其它行为、样式（`Table.css`）与导出集合都不改。`data-post` 由 `roles-HubPosts.tsx` 通过这个 prop 给出（`{ 'data-post': row.post }`）。若不采用这个 prop，就改用在本文件里自己写 `<table>`——但那样会丢掉共享表格的表头吸顶与焦点行为，不推荐。
8. **roles-logic.ts（纯函数）**：
   - `hubPostName(post: string): string` —— 六个中文名（协调人、规划端、合同端、门禁端、审核端、执行端），未知岗位码原样返回。
   - `allowedProfiles(profiles: readonly ProfilesData['profiles'], allowedAdapters: readonly string[]): string[]` —— 只留 `adapter` 非 null 且在 `allowedAdapters` 里的 profile，返回它们的 id；`allowedAdapters` 为空数组时返回空数组；profile 的 `adapter` 为 null（runtime 没登记）不算。
   - `normalizeHubPost(raw: HubPostRow): HubPostInfo` —— 照 `normalizeRole` 的写法把一行归一成固定字段（post、source、allowedAdapters、adapter、provider、model、thinking、profile、runtime、fallback（对象或 null）），缺键按 null 处理。
   - 本文件只 `import type` 自 `../../api`；纯函数不碰 DOM。
9. **roles-styles.css**：只加本表需要的样式，照现有写法（令牌、不写十六进制颜色、不写颜色函数、不拼接 `--tt-` 令牌名；带 px 的那一行同行写出处注释）。建议：`.rl-hub .tt-table { min-width: 760px; } /* 画布：七端岗位表最小宽 */`；本组自己的提示文字用 `.rl-hub-err` 之类类名，写法照 `.rl-note`/`.ov-change-err`。不要改现有规则。
10. **测试**：
    - `desktop/web/tests/live-api.test.ts`：读函数表加一行 `{ name: 'getHubRoles', run: () => api.getHubRoles(), path: '/api/v1/hub/roles', timeout: 30 }`；把该文件 describe 标题里的读函数个数按实际改成（现写「api.ts 的 15 个读函数（注入 fake client）」，加一个后是 16）；**既有断言一条不改、不删**。
    - `desktop/web/tests/page-hub.test.tsx`（新）：桩模式下渲染 `#/roles`，断言：七端岗位区块存在且标题是「七端岗位」；表 `aria-label="七端岗位"`；列头依次是 岗位、运行时、模型、思考档位、来源、替补（六个，没有「操作」）；六行的 `data-post` 依次是 coordinator、planner、contract、gate、audit、exec；逐行核对字段格式（null → 「—」、`pi（pi）`、`bb/step-5-preview`、planner 的 `—/claude-opus-5-5`、EffortPair 的「要求 high · 生效 未知」与 `data-state`、来源 Tag「默认」与 profile id、替补的两种形状与「—」）；这一组在角色卡之后、profile 表之前；hub 读失败（用 `setLiveClientForTests` 注入假 client 或替身 api）时只有这一组显示「没能读到七端岗位：…」，四张角色卡与 profile 表照常、整页仍是 data 态；`?mock=empty` 仍是六行；四个读是并行发出的（数调用次数）。
    - `desktop/web/tests/roles-hub-logic.test.ts`（新）：`hubPostName` 的六个中文名与未知岗位；`allowedProfiles` 的边界（adapter 为 null 不算、不在允许名单不算、允许名单为空则结果为空、coordinator 同时许 quizs 与 pi、planner 只许 claude-code）；`normalizeHubPost` 的缺键 → null 归一。
    - 不改 `page-app.test.tsx`（角色页禁用钮仍 6 个）、不改 `readonly2-app.test.tsx`、不改其它既有测试；新测试不用 `skip`/`only`/`todo`。
11. 跑 Validation commands 里与改动相关的检查（V01、V02、G01、R01），记录命令与结果。
12. 写执行报告；遇到合同未定义的行为（例如服务回的字段形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Validation commands
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（可选）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t038_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配:`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配:`\d+ passed`

## Definition of done
- D01：`getHubRoles()` 两条分支都成立：真实模式 `GET /api/v1/hub/roles`、时限 30 秒、失败不回落到桩；桩模式命令是 `config hub show --json` 并给六行、`?mock=empty` 仍是六行。证据：V01（live-api.test.ts 的读函数表与新测试）、G01；目的：真实模式下页面不能拿桩里的岗位名册当真名册显示。
- D02：七端岗位的桩是 `src/mock/hub-roles.ts`（.ts），`src/mock` 仍恰 14 份 JSON、`src/pages` 顶层仍恰 9 个 `*Page.tsx`。证据：G01、R01；目的：不破坏仓库对夹具数量与页面数量的既有约定。
- D03：页面并行发出四个读；前三个读的失败顺序仍是 `roles→profiles→presets`；hub 读失败只在七端岗位这一组显示失败信封，四个角色卡、profile 表、方案表与整页 data 态照常。证据：V01、G01；目的：旧内核没有 `config hub` 时这一页仍然可用。
- D04：七端岗位表六行，列头恰好是 岗位、运行时、模型、思考档位、来源、替补（没有操作列、没有按钮），每行带 `data-post`，位置在角色卡网格之后、profile 表之前。证据：V01、G01；目的：这一组是只读的展示，不提前做 B 片的写入口。
- D05：六行字段逐个对上：null 显示「—」；运行时是 `runtime（adapter）`；模型是 `provider/model`；planner 的 provider 为 null（模型列 `—/claude-opus-5-5`）；思考档位经 `EffortPair` 且 effective 为 null（有要求时显示「要求 X · 生效 未知」，thinking 为 null 时是「—」）；缺省行来源是 Tag「默认」、配置行来源是 profile id；替补 null 是「—」，四键与六键两种形状都按第 6 步的格式显示。证据：V01、G01；目的：D11 要求与生效并列，生效未知不能拿要求顶替。
- D06：纯函数 `hubPostName`（六个中文名，未知岗位原样）、`allowedProfiles`（adapter 为 null 不算、不在允许名单不算、允许名单为空则空、coordinator 同时许 quizs 与 pi、planner 只许 claude-code）、`normalizeHubPost`（缺键归 null）都有测试。证据：V01；目的：筛 profile 与行字段归一是 B 片要复用的逻辑，先把边界钉住。
- D07：新代码守既有源码规矩：`RolesPage.tsx` 原文（注释也算）不出现 `preview`/`getOperation`/`usePreset`/`setPluginEnabled`；src 下不出现网络词与危险 HTML 写入/动态求值类词；新文件不写内联 style、不渲染 `role=status`；CSS 不写十六进制颜色与颜色函数、不拼接 `--tt-` 令牌名，带 px 的行有出处注释。证据：G01、R01；目的：不破 T006/T009/T024 的长期门禁。
- D08：既有测试没被删、跳过或弱化：角色页禁用钮仍是 6 个（`page-app.test.tsx:91` 不改）、`readonly2-app.test.tsx` 不改、`live-api.test.ts` 只加不改；新测试不用 skip/only/todo。证据：V01、review；目的：既有断言是长期保护，不能为了新功能放松。
- D09：所有修改都在允许集合内（7 个可改文件、4 个可新增文件），没有碰 forbidden_paths。证据：scope。
- D10：没有删除、跳过或弱化既有测试；没有新增或升级依赖（`package.json` 与锁文件不变）。证据：review、scope。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如服务回的字段形状与合同写的类型对不上、或 `ALLOWED_API_READS` 里没有 `getHubRoles`）。
- 必须修改允许范围之外的文件才能继续（例如要动 `src/writes/`、`ts/packages/ui`、既有门禁测试或 `mock/*.json`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在 A 片里加写入口）。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，含返工版本；本片此前已用 0 次）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 7200
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：调查与读现有代码 15 分钟；实现（api.ts、桩、页面、视图、纯函数、Table 的加法式 prop）35 分钟；补测 30 分钟；必要检查（V01/V02/G01/R01）25 分钟；最终报告 10 分钟；总计约 115 分钟，单轮时限 3600 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261113T204135334289Z-owner-1e569a：

> 站主答复：
>
> 1. T038 只做 A 片：getHubRoles、桩（src/mock/hub-roles.ts）、loadRoles 并行读四个、只读的“七端岗位”一组（不带操作列）、roles-logic 的纯函数与测试。B 片（改绑定、替补、恢复缺省、禁用入口与原因、useWriteFlow 与 snapshots 的 hub 分支、page-app.test.tsx:91 的计数）等 A 片落地后站主另登记；你问的第二、三条到那时再定。
> 2. 第一条同意：站主把 T009 test_d13_page_files_wiring 的 ALLOWED_API_READS 加上 getHubRoles，单独一个门禁准备提交合入主分支（正在等落地锁）。T037 结项时内核把基线挪到新末端，会包含这次准备；合同端在新基线上核对即可。
> 3. 规划报告第 2 节的设计默认照写进合同，补一条：岗位的中文名照信箱的叫法——coordinator 协调人、planner 规划端、contract 合同端、gate 门禁端、audit 审核端、exec 执行端（第 5 节假设 4 不用再查）。
> 4. 第 7 节建议的“CLI 运行时页：手动登记运行时”同意另开一片，站主在 A 片之后登记：它和 B 片都要改 api.ts 与 desktop/web，排开免得互相撞。
> 5. 第 8 节的服务与内核缺口（hub.set 的预览没有岗位的前后对比、没有“这个岗位此刻有回合在跑”的提示）记进站主的内核待办，不挡本片。
