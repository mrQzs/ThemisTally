# TASK: t048-desktop-web-hub-live

## Identity
- plan_version: 3
- repository: ThemisTally
- base_sha: 4d428ac81bfa90558f46a31914abc70f097341dc
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端 Web 的「角色与模型」页里，「七端岗位」表加一列「证书」（插在「最近一回合」与「操作」之间，表变十一列）：绑在 quizs 上的岗位显示它对上的那一套 live 的状态；读不出、读取中、对不上都写明文字，不挡整张表，也不影响角色页的其余区块。hub 自己读不出时照旧走失败分支（没有表，也就没有证书列）。

## Non-goals
- 不重读证书：页头的「刷新」与写操作成功后的 reload 只重跑 `loadRoles`，**不再读一次 live**（换页回来重新挂载才会再读）。这是已知局限（规划报告 4.4 节）。
- 不做凭据录入、资格认证、续期按钮，不做「快到期」倒计时与能力上限（归 T043 与「CLI 运行时」页）。
- 不改 `desktop/web/src/api.ts`、`desktop/web/src/mock/quizs.ts`、`desktop/web/src/mock/hub-roles.ts`、`desktop/web/src/components/**`（Table、Tag、PageFrame 等）、`desktop/web/src/shell/**`、`desktop/web/src/writes/**`、`ts/packages/ui/**`、`scripts/**`（内核）。
- 不改 `desktop/web/src/pages/readonly1/roles-styles.css`（被 T047 S10 按字节冻结）；本片不需要新样式——确要加只许在 `roles-hub-turns.css` 末尾追加。
- 不改 `desktop/web/tests/roles-hub-logic.test.ts`、`desktop/web/tests/page-app.test.tsx`、`desktop/web/tests/roles-hub-turns.test.ts`、`desktop/web/tests/live-api.test.ts`（前两份与 `page-app.test.tsx` 被 T047 S10 按字节冻结）。
- 不改 `desktop/web/package.json` 与锁文件，不新增依赖，不加依赖版本。

## Repository facts
以下事实都在本回合的工作目录（基线 `22ca3413037c0804efe6045b6dd2e58bdf2e2dca`，即站主的门禁准备提交 22ca3413 之上）里逐条读过；行号按该基线。**以本节为准**，与规划报告对不上的条目列在最后。

### 前端：读 live 的那一侧（`desktop/web/src/api.ts`）
- `api.ts:233–241` `QuizsLiveStatus`：`{ state: string; problem: string | null; missing: string[]; certificate: { expires_at_ms: number | null } | null; profile: { valid_until: string | null } | null }`。
- `api.ts:242–247` `QuizsLiveRow`：`{ source: 'mailbox' | 'env'; provider: string | null; problem: string | null; status: QuizsLiveStatus | null }`。
- `api.ts:248–250` `QuizsLiveData`：`{ live: QuizsLiveRow[] }`。
- `api.ts:629–633` `getQuizsLive(): Promise<Envelope<QuizsLiveData>>`：真实模式 `client.get<QuizsLiveData>('/api/v1/quizs/live', undefined, 150)`；桩模式 `read(['config', 'quizs', 'live', '--json'], () => quizsLiveEnvelope())`。**它不 reject**（`src/live/transport.ts:2`：get 一律 resolve 成七字段信封）。
- `src/mock/quizs.ts:62–77` `quizsScenario()`：从 `location.hash` 的查询串里认 `quizs` 键，缺省或认不出按 `ok`；五个情景 `ok/expired/missing/broken/empty`。
- `src/mock/quizs.ts:39–50`：桩里**两套 live 的 provider 都是 `deepseek`**（一封 `mailbox`、一套 `env`）；`expired`/`missing` 只动 `mailbox` 那一套，`env` 那一套仍是 `ready`；`broken`（`:97–103`）两套 `status` 都是 `null`、`problem` 写「quizs live status 失败（退出码 127）：本机 PATH 上没有 quizs」；`empty`（`:104`）`live` 是空数组。
- `src/mock/quizs.ts:29–37` `liveStatus`：就绪时 `problem` 是 `null`、`missing` 是空数组。

### 前端：状态文字与色调（`desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts`）
- `:21–28` `STATE_LABELS`：`ready` → 就绪/success；`expired` → 已过期/danger；`build_mismatch` → 构建不一致/warning；`invalid` → 无效/danger；`missing` → 缺文件/warning。
- `:31–34` `liveStateLabel(state: string | null): { label: string; tone: TagTone }`：`state` 为 `null` → `{ label: '读不出', tone: 'danger' }`；认不出的 state → `{ label: '未知', tone: 'neutral' }`。
- `src/pages/readonly1/runtimes-QuizsBlock.tsx:127`、`:132`：T043 的写法是 `const state = liveStateLabel(status?.state ?? null);` 然后 `<Tag tone={state.tone}>{state.label}</Tag>`。**本片复用同一口径**。
- `src/components/Tag.tsx`：tone 取 `neutral/info/attention/success/warning/danger/escalate/brand`，渲染成 `<span class="tt-tag tt-tag--<tone>" data-tone="<tone>">`，`...rest` 透传 → **可以挂 `title`**。

### 前端：角色页四个文件（现状）
- `src/pages/RolesPage.tsx:23–41` `loadRoles`：`Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()])`；失败判定 `[roles, profiles, presets].find((e) => !e.ok || e.data == null)`；hub 的信封整个放进 `data.hub`。`:48–56` `<PageFrame … load={loadRoles}>`，children 是 `{(data, reload) => <RolesView data={data} onDiff={diffPresets} reload={reload} />}`。**目前没有 hooks。**
- `src/pages/readonly1/roles-RolesView.tsx:14–25` `RolesViewProps`（`data`/`onDiff`/`reload?`）；`:41` `<HubPosts hub={data.hub} profiles={data.profiles.profiles} reload={reload} />`；`:12` import `./roles-styles.css`。
- `src/pages/readonly1/roles-HubPosts.tsx:33–44` `HubRow`（十个字段）；`:50–62` `COLUMNS` 十字段（岗位、运行时、模型、思考档位、来源、替补、时限与工具、预算、最近一回合、操作）；`:151–156` `HubPostsProps`（`hub`、`profiles?`、`reload?`）；`:161–240` 组件（读成功分支渲染 `<Table … rows={hub.data.posts.map(…)}>`，读失败分支是 `.rl-hub-err` 一块）；`:29` `import './roles-hub-turns.css';`（**在组件 import 之后**，T047 S07 会查它后面不许再有 `./` 相对 import）。
- `src/pages/readonly1/roles-logic.ts`：既有导出 `hubPostName`、`allowedProfiles`、`normalizeHubPost`、T045 的 `hubFallbackCandidates`、T047 的九个纯函数（`hubTimeoutText` 等）；**整份文件只 `import type`**（T038 S07）。
- `src/mock/hub-roles.ts`：六行的 adapter/provider —— coordinator `quizs`/`deepseek`；planner `claude-code`/`null`；contract `quizs`/`minimax`（配置行，profile `quizs-m3`）；gate `pi`/`cc-switch-zhipu-glm`；audit `pi`/`minimax`；exec `pi`/`bb`。

### 内核（只读引用，本片不改）
- `scripts/kit_hub.py:2117–2134` `quizs_live_files`：这个提供方的三份 live 文件——先找信箱 `quizs-live/<提供方>/`，三份都在就用；不全时退回环境变量给的那一套；环境那一套的提供方档案认得出是别家的（`owner` 在 `QUIZS_PROFILE_IDS` 里且不等于本提供方）就不用。
- `scripts/kit_roles.py:1446–1470` `_quizs_live_sets`：信箱 `quizs-live/` 下每个目录一行（目录名就是 provider，按名字排），再加环境变量给的那一行（`provider` 起初是 `null`；读得出 status 时按 `QUIZS_PROFILE_IDS` 反查，认不出仍是 `null`）。
- `scripts/kit_roles.py:1488–1497` `_quizs_live` 的文字输出：`note = row["problem"] or ("缺 " + "、".join(missing) if missing else status.get("problem"))` —— **note 的取值顺序是 `row.problem` → 「缺 a、b」→ `status.problem`**，取第一个有的。

### 门禁现状（新基线上逐条核对，22ca3413 已放宽并合入）
1. `tests/test_gate_t045_baseline.py:512–517`（S06）：RolesView 只钉 `<HubPosts hub={data.hub} profiles={data.profiles.profiles} reload={reload} … />` 的前三个 prop，后面**可以追加** prop。
2. `tests/test_gate_t045_baseline.py:536–541`（S07）：`page-hub.test.tsx` 的列头断言**十列、十一列都认**（十一列 = 在「最近一回合」与「操作」之间插「证书」）。
3. `tests/test_gate_t047_baseline.py:176–178`（`HUB_HEADERS_T048`）、`:313–314`（`PAGE_HUB_HEADERS_LINE_T048`）、`:690–693`（S07）：`roles-HubPosts.tsx` 里 `COLUMNS` 的 header 逐字元组必须**恰是**那十列或那十一列。
4. `tests/test_gate_t047_baseline.py:832–836`（S10）：`RolesPage` 的 `Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])` 与 `load={loadRoles}` 一字不改；**不再**要求 RolesPage/RolesView 字节冻结，也**不再**禁止 `getQuizsLive`。
5. `tests/test_gate_t047_baseline.py:86–95`（`BASELINE_DIGESTS`）：按字节冻结的是 `desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock`、`roles-styles.css`、`desktop/web/tests/roles-hub-logic.test.ts`、`desktop/web/tests/page-app.test.tsx`、`ts/packages/ui/src/readroutes.ts`、`writeroutes.ts`。
6. `tests/test_gate_t038_baseline.py:405`（S04）：`Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])` 逐字；`:407`：失败判定只看前三个；`:429`（S05）：RolesView 以 `<HubPosts hub={data.hub}` 开头；`:434–437`：HubPosts 在角色卡网格之后、ProfilesTable 之前；`:876`（P1）：只核**前六个**列头；`:110`：RolesPage 原文不许出现 `preview`/`getOperation`/`usePreset`/`setPluginEnabled`（注释也算）；`:578–591`（S11）：RolesPage/RolesView/HubPosts/roles-logic 等文件里不许出现网络词、T007 禁用词、`role="status"`、内联 style；`:465`（S07）：roles-logic 只 `import type`。
7. `tests/test_gate_t009_baseline.py:138–139`：`ALLOWED_API_READS` 已含 `getQuizsLive`；`:875–890`：`load` 必须是命名的模块级函数（`load={loadRoles}`）、从 `../api` 只许引白名单里的读函数。
8. `tests/test_gate_t047_baseline.py:753–781`（S08）：`roles-hub-turns.css` 只许用已定义的 `--tt-*` 令牌、不写死颜色、不声明令牌；除 `0` 与 `1px` 外的 px 字面量同一行要带出处注释；`:761` 要求那条 `.rl-hub table.tt-table { min-width: 1120px; }` 仍在。

### 与规划报告对不上的条目（以本节为准）
1. 规划第 5 节 A1–A8 **全部成立**；A2、A3 已由站主拍板（见 Behavior contract 第 1 节）。
2. 规划 4.3 节「未知 state 原样显示、色调 warning」与站主决定 A3（「认不出是未知」）冲突：**按站主决定**，认不出的 state 取 `liveStateLabel` 的「未知/neutral」，不再原样显示 state 字符串。规划 4.3 自拟的中文名（有效/过期/与当前构建对不上/无效/缺文件）**作废**，一律用 `liveStateLabel` 的文字。
3. 规划第 3 节写的 `scripts/kit_hub.py:1959–1976` 现在是 **:2117–2134**（行号已漂移，规则不变）；`scripts/kit_roles.py:1446–1501` 现在是 **:1446–1497**。
4. 规划第 4.2 节的匹配规则**成立**：provider 精确对上 → `source` 为 `env` 且 `provider` 为 `null` 的那一条兜底 → 都没有就「没有 live 文件」。桩的 ok 夹具里 `env` 那一套的 provider 是 `deepseek`（不是 null），所以契约（minimax）**在每个情景下都是「没有 live 文件」**（含 `?quizs=broken`）。
5. 规划第 10 节页面测试第 3 条「quizs 两格读不出」**只对失败信封成立**；`?quizs=broken` 下 coordinator 是 Tag「读不出」（那一套对上了但 `status` 是 null）、contract 是「没有 live 文件」。

### 工具链与锁文件
- `desktop/web` 用 npm（`desktop/web/package.json`）：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`（TypeScript 5.6.3）、`npm run build` = `tsc --noEmit && vite build`（vite 5.4.11）、`npm run check:contract` = `node scripts/token-contract.mjs`。`desktop/web/tsconfig.json` 的 `include` 只有 `["src","vite.config.ts"]` —— `tests/` 下的文件不过 tsc，但会被 vitest 读到。
- 仓库门禁用 `python -m pytest`。本片只跑 `desktop/web` 的 npm 命令与仓库根的 pytest。

### 基线检查
- 本回合（合同端）没有命令执行工具，**没有跑**任何测试；上面的结论都是逐文件只读核对得出的。
- 站主的门禁准备提交上三份门禁全过、47 份门禁基准 1059 条全过（站主放行信 20261117T091530840758Z-owner-748456 的记录）。
- 执行端动手前先跑 V01（`desktop/web` 的 `npm test`）与 V02/V03/V04，把结果记进执行报告。基线上本片的行为一个都还不存在：没有「证书」列、没有 `getQuizsLive` 的单独读。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/pages/readonly1/roles-HubPosts.tsx
  - desktop/web/src/pages/readonly1/roles-logic.ts
  - desktop/web/src/pages/readonly1/roles-hub-turns.css
  - desktop/web/tests/page-hub.test.tsx
  - desktop/web/tests/page-hub-cert.test.tsx
  - desktop/web/tests/roles-hub-cert.test.ts
- allowed_new_files:
  - desktop/web/tests/roles-hub-cert.test.ts
  - desktop/web/tests/page-hub-cert.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t048_*.py
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
  - tests/test_gate_t043_baseline.py
  - tests/test_gate_t044_baseline.py
  - tests/test_gate_t045_baseline.py
  - tests/test_gate_t046_baseline.py
  - tests/test_gate_t047_baseline.py
  - tests/test_gate_t049_baseline.py
  - scripts/**
  - ts/packages/ui/**
  - ts/packages/base/**
  - ts/package.json
  - ts/bun.lock
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/src/api.ts
  - desktop/web/src/mock/**
  - desktop/web/src/components/**
  - desktop/web/src/writes/**
  - desktop/web/src/live/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/src/pages/OverviewPage.tsx
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/pages/readonly1/roles-RoleCard.tsx
  - desktop/web/src/pages/readonly1/roles-PresetBar.tsx
  - desktop/web/src/pages/readonly1/roles-PresetDiff.tsx
  - desktop/web/src/pages/readonly1/roles-PresetsTable.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/src/pages/readonly1/runtimes-QuizsBlock.tsx
  - desktop/web/src/pages/readonly1/runtimes-quizs-logic.ts
  - desktop/web/tests/roles-hub-logic.test.ts
  - desktop/web/tests/roles-hub-turns.test.ts
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/page-static.test.ts
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 1. 站主已定的事（写死，不许再议）
- **A2（夹具事实）**：ok 夹具的两套 live 的 provider 都是 `deepseek`；契约（minimax）在**每个**情景下都是「没有 live 文件」（含 `?quizs=broken`）。规划第 10 节页面测试第 3 条「quizs 两格读不出」**只对失败信封**成立。
- **A3（文字与色调）**：对上的那一套，Tag 的文字与色调**一律取** `liveStateLabel(status?.state ?? null)`：就绪（success）、已过期（danger）、构建不一致（warning）、无效（danger）、缺文件（warning）；`status` 为 `null` → 「读不出」（danger）；认不出的 state → 「未知」（neutral）。**规划 4.3 节自拟的中文名作废**。
- **门禁准备（22ca3413）已合入**：列头十列、十一列都认（「证书」在「最近一回合」与「操作」之间）；T045 只钉 HubPosts 的前三个 prop（后面可追加 `live={live}`）；T047 不再冻结 RolesView/RolesPage、不再禁止 `getQuizsLive`，仍钉并行四读与 `load={loadRoles}`。本片**不改任何门禁文件**。
- `roles-styles.css` 仍被按字节冻结；本片不需要新样式，确要加只许在 `roles-hub-turns.css` 末尾追加。

### 2. 前端：`RolesPage` 单独读一次 live
- 在 `RolesPage` 组件里加 `useState` + `useEffect`：
  - `const [live, setLive] = useState<Envelope<QuizsLiveData> | null>(null);` —— **null 表示读取中**。
  - `useEffect(() => { let on = true; getQuizsLive().then((env) => { if (on) setLive(env); }); return () => { on = false; }; }, []);` —— 只在挂载时读一次；`get` 不 reject，**不写 catch**；卸载之后不写状态。
- `Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()])` **一字不改**（T038 S04、T047 S10）；失败判定 `[roles, profiles, presets].find((e) => !e.ok || e.data == null)` 一字不改；`load={loadRoles}` 一字不改（仍是模块级命名函数，T009）。
- 从 `../api` 引入的值只许是 `ALLOWED_API_READS` 里的读函数（`getQuizsLive` 已在白名单里，T009 :138–139）；类型用 `type QuizsLiveData` 引入。
- 页头说明「四个角色各用哪个 CLI 与模型；方案可以一键切换」、两个页头按钮（`DisabledAction label="保存当前为方案…"`、`NewProfileAction`）与 children 签名（`(data, reload) => …`）一字不改。
- 传下去：`<RolesView data={data} onDiff={diffPresets} reload={reload} live={live} />`。
- RolesPage 原文（注释也算）**不许出现** `preview`、`getOperation`、`usePreset`、`setPluginEnabled`（含 "step-5-preview"）；四个文件都不许出现网络词、T007 禁用词、`role="status"`、内联 style。

### 3. 前端：`RolesView` 透传
- `RolesViewProps` 加 `live: Envelope<QuizsLiveData> | null;`。
- 渲染照旧以 `<HubPosts hub={data.hub} …` 开头，追加 `live={live}`：`<HubPosts hub={data.hub} profiles={data.profiles.profiles} reload={reload} live={live} />`（T045 S06 的正则允许在 `reload={reload}` 之后追加 `prop={…}`；T038 S05 只认前缀 `<HubPostshub={data.hub}`）。
- HubPosts 仍在角色卡网格之后、ProfilesTable 之前；`RolesView` 从 `../../api` **只 `import type`**。

### 4. 前端：纯逻辑（`roles-logic.ts`，**只在文件末尾追加**）
- 既有导出（`hubPostName`、`allowedProfiles`、`normalizeHubPost`、`hubFallbackCandidates`、T047 的九个纯函数）签名与行为**一字不改**；整份文件仍然**只 `import type`**（从 `../../api` 引 `Envelope`、`QuizsLiveData`、`QuizsLiveRow` 等类型）。
- 新增导出（名字逐字照抄）：
  - `export function matchLiveRow(rows: readonly QuizsLiveRow[], provider: string | null): QuizsLiveRow | null`
    1. `provider` 非 `null` 时：在 `rows` 里找**第一条** `row.provider === provider` 的行，找到就返回它（行序即服务端给的顺序：信箱在前、`env` 在后，所以同名时信箱那一套优先）。
    2. 否则（或没找到）：在 `rows` 里找**第一条** `row.source === 'env' && row.provider === null` 的行，找到就返回它（认不出是谁家的那一套，hub 会退回去用它）。
    3. 都没有：返回 `null`。
    （岗位 `provider` 为 `null` 时第 1 条不命中，直接走第 2 条。）
  - `export interface HubCertInfo { text: string; state: string | null; tagged: boolean; title: string | null; }`
  - `export function hubCertInfo(post: HubPostInfo, live: Envelope<QuizsLiveData> | null): HubCertInfo` —— 逐条按第 5 节的表返回：
    - 纯文字情形：`text` 是要显示的字，`state` 是 `null`，`tagged` 是 `false`，`title` 是 `null` 或那一段说明文字。
    - Tag 情形：`text` 是空串，`state` 是 `row.status?.state ?? null`（**可能仍是 `null`**），`tagged` 是 `true`，`title` 是按取值顺序取到的第一个说明文字或 `null`。
- 两个函数都是纯函数：不碰 DOM、不碰时钟、不引依赖。

### 5. 前端：证书格显示规则（逐条钉死）
| 情形 | 结果 | title |
|---|---|---|
| 岗位的 `adapter` 不是 `quizs` | 纯文字 `—` | 无 |
| `live` 为 `null`（还没回来） | 纯文字 `读取中` | 无 |
| `live.ok` 为假 | 纯文字 `读不出` | `live.messages` 用换行连起来；messages 为空则无 title |
| `live.ok` 为真但 `live.data` 为 `null` | 纯文字 `读不出` | 同上（messages 为空则无 title） |
| `live.ok` 为真、`data` 有、`data.live` 不是数组 | 纯文字 `读不出` | 同上 |
| 对不上任何一套（第 4 节第 3 条） | 纯文字 `没有 live 文件` | 无 |
| 对上的那一套，`status` 是 `null` | **Tag**，文字与色调取 `liveStateLabel(null)` = 「读出不来」→ 准确说：**「读不出」，danger** | `row.problem` → 「缺 a、b」→ `status.problem`（取第一个有的） |
| 对上的那一套，`status.state` 是五个枚举之一 | **Tag**，文字与色调取 `liveStateLabel(status.state)` | 同上 |
| 对上的那一套，`status.state` 是别的字符串 | **Tag**，文字与色调取 `liveStateLabel(该字符串)` = 「未知」、neutral | 同上 |

- **title 取值顺序**（照 `scripts/kit_roles.py:1495–1497` 的 note 口径）：① `row.problem`（非空字符串）；② `status.missing` 是非空数组时写 `缺 ` + `missing.join('、')`；③ `status.problem`（非空字符串）；三个都没有则不给 title。
- **纯文字与 Tag 的区别**：只有「对上的那一套」才用 Tag；「读不出（信封层）」「读取中」「没有 live 文件」「—」都是**纯文字**（没有 `.tt-tag` 元素）。
- 证书格里**不许**有按钮、链接或任何可聚焦元素；不许 `role="status"`；不许内联 style；不许写死颜色。

### 6. 前端：`roles-HubPosts.tsx` 的改动
- `COLUMNS` 变**十一列**，次序逐字是：`岗位`、`运行时`、`模型`、`思考档位`、`来源`、`替补`、`时限与工具`、`预算`、`最近一回合`、`证书`、`操作`（T047 S07 逐字比对的就是这个元组）。前六列与「操作」列的内容**一字不改**。
- `HubRow` 加一个字段 `证书: ReactNode;`（放在 `最近一回合` 之后、`操作` 之前）。
- `HubPostsProps` 加 `live?: Envelope<QuizsLiveData> | null;`（可空，缺省 `null`；`hub`、`profiles?`、`reload?` 一字不改，T045 S05 只查这三个 prop 在不在）。
- 渲染：新增一个本文件内的格函数（例如 `certCell(p, live)`）：`const info = hubCertInfo(p, live);` —— `info.tagged` 为真时渲染 `<Tag tone={liveStateLabel(info.state).tone} title={info.title ?? undefined}>{liveStateLabel(info.state).label}</Tag>`；否则渲染 `<span title={info.title ?? undefined}>{info.text}</span>`。
- **新的 import**：`import { liveStateLabel } from './runtimes-quizs-logic';` —— 必须写在 `import './roles-hub-turns.css';` **之前**（站主决定；T047 S07 也查 css import 之后不许再有 `./` 相对 import）。这一行是**值导入**，只有 `roles-HubPosts.tsx` 允许（`roles-logic.ts` 仍然只 `import type`）。
- 读失败分支（`.rl-hub-err` 那块）、`<WriteFlow flow={flow} />`、T038 S10 的静态形状（`title="七端岗位"`、`aria-label="七端岗位"`、`rowHeight={40}`、`rl-table rl-hub`、`hubPostName`、`rowAttrs` 给的 `data-post`、**不出现 `data-role`**）一个都不许丢。
- `roles-HubPosts.tsx` 从 `../../api` **只 `import type`**（`Envelope`、`HubRolesData`、`ProfilesData`、`QuizsLiveData`）。
- 本片**不需要**改样式；若确有必要，只许在 `roles-hub-turns.css` **末尾追加**：只用 `src/styles/tokens.css` 里已定义的 `--tt-*` 令牌、不写死颜色、不声明令牌、除 `0` 与 `1px` 外的 px 字面量同一行带出处注释，并且 T047 S08 钉住的那条 `.rl-hub table.tt-table { min-width: 1120px; }` 必须在。

### 7. 前端：包内测试
- **`desktop/web/tests/page-hub.test.tsx`**：**只改一条**——第 92 行那条列头断言的期望数组，从十列改成十一列：`['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '证书', '操作']`。该 `it` 的标题可以一并改成「十一列…」（可选）；**其余用例与断言一个字都不许动**（`describe('七端岗位（桩模式渲染 #/roles）')` 的标题、按钮用例、data-post、位置、`?mock=empty`、读失败、四个读并行）。
- **新文件 `desktop/web/tests/roles-hub-cert.test.ts`**（纯逻辑，不许 `skip`/`only`/`todo`；测真实实现，不许把业务逻辑抄一份进测试）：至少覆盖
  1. `matchLiveRow`：provider 精确对上；信箱与 `env` 同名时取信箱（第一条）；对不上时用 `source==='env' && provider===null` 的那条兜底；`env` 那条 provider 不是 `null` 时**不**兜底（结果 `null`）；岗位 provider 为 `null` 时用 `env` 那条；`rows` 是空数组时 `null`。
  2. `hubCertInfo`：非 quizs → 纯文字 `—`；`live` 为 `null` → 纯文字 `读取中`；信封 `ok:false` → 纯文字 `读不出` 且 title 是 messages；`ok:true` 但 `data` 为 `null` → 纯文字 `读不出`；`data.live` 不是数组 → 纯文字 `读不出`；对不上 → 纯文字 `没有 live 文件`；对上的一套 `status` 为 `null` → `tagged` 为真、`state` 为 `null`、title 是 `row.problem`；五个 state 各自的 `state` 取值（`ready`/`expired`/`build_mismatch`/`invalid`/`missing`）与未知 state 原样传给 `liveStateLabel`；title 取值顺序（`row.problem` 优先于「缺 a、b」，「缺 a、b」优先于 `status.problem`，三个都没有时 `null`）。
  3. 期望值写成**字面量**（例如 `'读不出'`、`'没有 live 文件'`、`'缺 qualification.json'`），不要照抄业务逻辑。
- **新文件 `desktop/web/tests/page-hub-cert.test.tsx`**（页面，桩模式与真实模式，挂 App 渲染 `#/roles`；每个用例自带全部辅助函数，不跨文件共享作用域）：至少覆盖这七条
  1. 桩模式（`#/roles`）：列头里「证书」在「最近一回合」与「操作」之间（整列头逐字是十一列）；coordinator 那格是 Tag「就绪」（`data-tone="success"`）、contract 那格是纯文字「没有 live 文件」、其余四行是「—」。
  2. 桩模式 `?quizs=expired`：coordinator 是 Tag「已过期」（danger）；`?quizs=missing`：coordinator 是 Tag「缺文件」（warning）且 title 是「缺 qualification.json」；contract 两情景都是「没有 live 文件」。
  3. 桩模式 `?quizs=broken`：coordinator 是 Tag「读不出」（danger），title 是「quizs live status 失败（退出码 127）：本机 PATH 上没有 quizs」；contract 是「没有 live 文件」。
  4. 真实模式：假 client 对 `/api/v1/quizs/live` 回**失败信封** → 两个 quizs 格都是**纯文字**「读不出」（title 是 messages），整张表、六行、角色卡、profile 表照常，整页是 `data` 态。
  5. 真实模式：假 client 对 `/api/v1/quizs/live` **一直挂起** → 两个 quizs 格都是「读取中」，整张表照常渲染。
  6. 真实模式：假 client 对 `/api/v1/quizs/live` 回带记号的行（例如 `[{source:'mailbox',provider:'deepseek',status:{state:'ready',…}}, {source:'env',provider:null,status:{state:'expired',…}}]`）→ coordinator 是 Tag「就绪」、contract（provider `minimax`）用 `env` 那条兜底是 Tag「已过期」、其余四行「—」；并且 `/api/v1/quizs/live` **只请求一次**。
  7. 真实模式：hub 读失败 → 照旧是失败块，**没有「证书」列头**，也没有证书格；证书格里没有 `button`、没有 `role="status"`。
  - 期望值写成**字面量**；桩模式的 `?quizs=` 情景由 `location.hash` 选（照 `src/mock/quizs.ts:62–77`）。

### 8. 边界输入
- 服务旧版本没有 live 的两套 → `data.live` 是空数组 → 没有任何一套对得上 → quizs 格写「没有 live 文件」。
- `provider` 为 `null` 的岗位（桩里没有）→ 第 1 条不命中，走 `env` 兜底。
- `status.missing` 是空数组 → 不给「缺 …」的 title（走 `status.problem`）。
- `messages` 是空数组 → 失败信封的「读不出」不带 title。
- `state` 是服务遮成的 `<redacted>` 之类 → `liveStateLabel` 认不出 → Tag「未知」（neutral）。

### 9. 错误与重试
- `getQuizsLive` 不 reject（`src/live/transport.ts:2`）：不写 catch，不重试；读不出就在格子里写「读不出」，**不影响**「七端岗位」其余各格、角色卡、profile 表、方案表。
- hub 自己读失败 → 照旧只这一组显示失败信封与 messages（`pre`），**没有证书列**、零按钮。
- live 读失败**不参与**整页失败判定（整页失败只看 roles/profiles/presets 三个读）。

### 10. 并发、取消与状态变化
- live 只在 `RolesPage` 挂载时读一次；`useEffect` 的清理函数把「还该不该写状态」的开关置假，卸载后不写状态（不触发 setState 警告）。
- 页头「刷新」与写操作后的 reload 只重跑 `loadRoles`（PageFrame 的 load 语义不变），**不重读 live**——这是本片明确的已知局限（Non-goals）。
- `getQuizsLive` 与 `loadRoles` 是两条并行的读，互不等待：live 晚回来时页面已经渲染，证书格从「读取中」变成实况。

### 11. 兼容性
- `HubPosts` 的 props 只**加** `live?`；`hub`、`profiles?`、`reload?` 一字不改；`RolesView` 的 props 只**加** `live`（必填，null 表示读取中）。
- `roles-logic.ts` 只**追加**两个导出与一个接口，既有导出与签名不变；该文件仍只 `import type`。
- `api.ts`、`src/mock/**`、`Table`、`Tag`、`PageFrame`、`roles-styles.css` 一个字节都不改；`desktop/web/src/mock` 仍恰 14 份 JSON；`desktop/web/src/pages` 顶层仍恰 9 个 `*Page.tsx`；依赖与锁文件不变。

## Steps
1. 读 Repository facts 里的文件（`api.ts`、`mock/quizs.ts`、`runtimes-quizs-logic.ts`、`roles-HubPosts.tsx`、`roles-logic.ts`、`RolesPage.tsx`、`roles-RolesView.tsx`、`mock/hub-roles.ts`），确认签名与本基线一致；不一致就停下并报告，不要自己改事实。**再读一遍门禁端交付的本片门禁基准测试文件**（`tests/test_gate_t048_baseline.py`，只读；基线上还不存在就跳过），把它的断言与本合同的 Behavior contract 第 1、5 节对一遍；有出入以本合同为准，并把出入写进执行报告。
2. **先跑基线**：在 `desktop/web` 跑 `npm test`、`npm run typecheck`、`npm run build`、`npm run check:contract`，把结果记进执行报告（基线应全绿；本片的行为一个都还不存在）。
3. **`roles-logic.ts`**：在文件**末尾追加** `matchLiveRow`、`HubCertInfo`、`hubCertInfo`（签名与行为照 Behavior contract 第 4、5 节）；`import type` 里补 `Envelope`、`QuizsLiveData`、`QuizsLiveRow`；既有导出与签名一字不改。
4. **`roles-HubPosts.tsx`**：`COLUMNS` 改十一列、`HubRow` 加 `证书`、`HubPostsProps` 加 `live?`、加格函数与新 import（`liveStateLabel` 放在 css import 之前）；读失败分支、`<WriteFlow flow={flow} />`、静态形状照旧。
5. **`roles-RolesView.tsx`**：`RolesViewProps` 加 `live`，`<HubPosts … live={live} />`；位置与 import type 规矩照旧。
6. **`RolesPage.tsx`**：按 Behavior contract 第 2 节加 `useState` + `useEffect` 单独读一次 `getQuizsLive`，把 `live` 传给 `RolesView`；并行四读、失败判定、`load={loadRoles}`、页头一字不改。
7. **`tests/page-hub.test.tsx`**：只改列头那一条的期望数组（十一列）。
8. **新文件 `tests/roles-hub-cert.test.ts`** 与 **`tests/page-hub-cert.test.tsx`**：按 Behavior contract 第 7 节写用例（期望值写字面量；纯逻辑与页面各一组）。
9. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → V04 → R01**；R01 墙钟上限 2820 秒，可以分批跑（文件集合不许少，每批 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
10. 写执行报告；遇到合同未定义的行为（例如服务回的 live 行形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t048_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t049_baseline.py -q` · cwd：仓库根 · 超时：2820s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：600s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`
- V04（必要）：`npm run check:contract` · cwd：desktop/web · 超时：300s · 期望退出码：0

## Definition of done
- D01：「七端岗位」表是十一列，次序逐字是 `岗位、运行时、模型、思考档位、来源、替补、时限与工具、预算、最近一回合、证书、操作`；前六列与「操作」列一个字都没改；证据：V01、G01、R01；目的：列的次序与既有列的稳定性是站主要求的可见形状，T047 S07 逐字比对的就是这个元组。
- D02：live 只在 `RolesPage` 挂载时读一次（不进 `Promise.all` 四读、不改 `load={loadRoles}`、不改前三个读的失败判定），经 `RolesView` 透传到 `HubPosts`；证据：G01、R01、V01、scope；目的：既有门禁钉死了并行四读与 load 的形态，撞了就是全红。
- D03：两个 quizs 岗位的证书格按第 5 节的表逐条对上：桩 ok → coordinator Tag「就绪」、contract「没有 live 文件」；`?quizs=expired` → 「已过期」；`?quizs=missing` → 「缺文件」且 title 是「缺 qualification.json」；`?quizs=broken` → coordinator Tag「读不出」、contract「没有 live 文件」；失败信封 → 两格纯文字「读不出」；挂起 → 两格「读取中」；非 quizs 四行 → 「—」；证据：V01；目的：证书状态要真读出来，读不出也要写明，不许用占位糊过去。
- D04：Tag 的文字与色调一律取 `liveStateLabel(status?.state ?? null)`（就绪/已过期/构建不一致/无效/缺文件；null 是读不出；认不出是未知），不另起一套中文名；证据：V01、review；目的：两页说同一句话，是站主 2026-11-17 的决定。
- D05：title 的取值顺序是 `row.problem` → 「缺 a、b」→ `status.problem`，与 `scripts/kit_roles.py:1495–1497` 的 note 口径一致；证据：V01、review；目的：界面与 `config quizs live` 说的是同一件事。
- D06：纯逻辑（`matchLiveRow`、`hubCertInfo`）的用例覆盖第 4、5 节的每一行（provider 精确对上、信箱优先、`env` 且 provider 为 null 才兜底、五个 state、未知 state、status 为 null、信封失败、data 为 null、live 为 null、非 quizs、没有 live 文件、title 取值顺序），期望值写成字面量；证据：V01；目的：判断逻辑要能脱离 DOM 单测，界面上算出来的每一格都要有一个能断言的纯函数。
- D07：hub 读失败时照旧是失败块，没有「证书」列头也没有证书格；证书格里没有 button、没有 `role="status"`、没有内联 style、没有可聚焦元素；四个文件里没有网络词、T007 禁用词与 RolesPage 的四个禁词；证据：V01、R01、G01；目的：证书读不出不挡整张表，也不破既有源码规矩。
- D08：`desktop/web/tests/page-hub.test.tsx` 只改了列头那一条的期望数组（十一列），其余用例与断言一条没删、没跳过、没弱化；两个新测试文件在位且不出现 `skip`/`only`/`todo`；证据：V01、review；目的：验收看的是行为有没有被测住，不是测试文件在不在。
- D09：`desktop/web` 的 `npm test`、`npm run typecheck`、`npm run build`、`npm run check:contract` 全过；证据：V01、V02、V03、V04。
- D10：所有修改都在允许集合内（可改 6 个文件、可新增 2 个文件），没有碰 forbidden_paths（`tests/test_gate_*.py`、`scripts/**`、`ts/packages/**`、`api.ts`、`src/mock/**`、`components/**`、`roles-styles.css`、被冻结的包内测试等）；依赖与锁文件没变；证据：scope。
- D11：没有删除、跳过或弱化既有测试；证据：review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `api.ts` 里没有 `getQuizsLive`/`QuizsLiveData`、`runtimes-quizs-logic.ts` 里没有 `liveStateLabel`、`roles-HubPosts.tsx` 的 `COLUMNS` 不是十列、门禁的放宽不在新基线上），停下并报告（由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `api.ts`、`src/mock/**`、`roles-styles.css`、`runtimes-quizs-logic.ts`、任何 `tests/test_gate_*.py`、任何依赖或锁文件）。
- 门禁端交付的 `tests/test_gate_t048_baseline.py` 与本合同的第 1、5 节冲突（两边说法不同且无法同时满足），停下并报告。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如 live 行的形状与 `QuizsLiveRow` 对不上）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；本版已用掉 0 次）
- max_wall_seconds_per_attempt: 2700
- max_wall_seconds_total: 6000
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：读代码与核对门禁 15 分钟；实现四个源文件 30 分钟；写两份新测试与改一条既有断言 45 分钟；跑 V01–V04 与 R01 45 分钟；写执行报告 10 分钟；总计约 145 分钟（单轮上限 2700 秒 = 45 分钟，够一次做完，留一次返工）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261115T104242619938Z-owner-67a1bf：

> 站主决定（2026-11-15）：
> 1. 门禁准备由站主做。
>    - T047 结项、内核把基线挪到新末端之后，站主在新基线上补搜：T043、T045、T047 的门禁基准，以及它们新加的包内测试。关键字照你列的，再加“证书”“操作”“COLUMNS”。
>    - 撞到的断言由站主合入门禁准备，然后另写一封回信放行合同端。
>    - 那封放行信到之前，不开工合同端。内核挪基线的通知先到也照等。
> 2. 三类放宽的口径照你列的。实际撞到哪条，以新基线上搜到的为准：
>    - (a) 钉死“七端岗位”列头全集的断言：期望数组里加“证书”，位置在 T047 的三列之后、“操作”之前；
>    - (b) 逐字钉 HubPosts 属性写法的断言：放宽成只钉 `<HubPosts hub={data.hub}` 前缀，容许后面追加 live；
>    - (c) 钉 RolesPage 读法的断言：容许用 useState/useEffect 单独读一次 getQuizsLive。`Promise.all` 四读、失败判定、`load={loadRoles}` 一字不动。
> 3. 规划报告的测试设计与第 6 节的假设照写进合同，由合同端在新基线上核对。

站主来信 20261117T091530840758Z-owner-748456：

> 站主放行（2026-11-17，答 20261117T083517200832Z-womovie-c8-cbfb85；记为站主决定）：
>
> 1. 门禁准备已合入：提交 22ca3413，只改 T045、T047 两份门禁；T048 的基线已挪到它上面。实际撞到并放宽的：
>    - (a) 列头全集：T045 S07，T047 S07、S09 与页面探针。十列、十一列都认，“证书”在“最近一回合”与“操作”之间。
>    - (b) T045 S06 只钉 hub、profiles、reload 三个 prop，后面可以追加 live={live}。T038 S05 本来只钉前缀。
>    - (c) T047 S10 去掉 RolesView、RolesPage 的字节冻结与“不出现 getQuizsLive”，新钉 load={loadRoles}；并行四读仍逐字。
>    - 准备提交上三份门禁全过；套一份 T048 形状的替身改动，全部 47 份门禁基准 1059 条全过。
> 2. 包内测试只有 page-hub.test.tsx:92 钉列头全集，列进可改范围，只改这一条的期望数组。T043、T044、T046、T049 的门禁与其余包内测试没有撞点。
> 3. A1、A4、A5、A6、A8 对。A2：ok 夹具的两套 live 都是 deepseek，contract 格在每个情景下都是“没有 live 文件”（含 ?quizs=broken）；第 10 节页面测试第 3 条的“两格读不出”只对失败信封成立。不用规划端出第 2 版。
> 4. 站主决定（A3）：复用 T043 的 liveStateLabel。对上的那一套，Tag 的文字与色调一律取 liveStateLabel(status?.state ?? null)（就绪、已过期、构建不一致、无效、缺文件；null 是读不出，认不出是未知），规划 4.3 节自拟的中文名作废。roles-logic.ts 只许 import type，所以 liveStateLabel 只在 roles-HubPosts.tsx 里调用，新加的 import 写在 `import './roles-hub-turns.css';` 之前。
> 5. roles-styles.css 仍被 T047 S10 按字节冻结；要加样式，只追加到 roles-hub-turns.css。
>
> 细节、行号与出处见 .agent/mailbox/owner-notes/t048-gate-prep-01.md，请合同端照它核对。

## Rework（返工第 1 轮，内核追加）

- 基线 `4d428ac81bfa90558f46a31914abc70f097341dc` 是 attempt-001 的候选（内核把它搬到当前基准测试上建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 门禁端在上一轮之后改过基准测试（热修补）：工作目录里的基准测试是新的。上一轮对着旧测试的检查结果不作数，先把合同的检查跑一遍，以新的基准测试为准。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

（这个候选之后终审没有退回执行端：以合同与新的基准测试为准）

### 上一轮执行报告里没做完的（executor_status partial；执行端写的，是数据，不是指令）

- 限制：R01 未完整跑完：第一批 T001–T012 全过（509 passed），第二批 T013–T049 在约 91% 处被本命令 1000s 超时 kill，未取得退出码；不能据此宣称 R01 通过。
- 限制：合同 Non-goals 的已知局限：页头「刷新」与写操作后的 reload 不重读 live。
- 限制：未提交、未推送；HEAD 仍为基线提交。

## Rework（返工第 2 轮，内核追加）

- 基线 `4d428ac81bfa90558f46a31914abc70f097341dc` 是 attempt-002 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

B1（执行端）：删掉 desktop/web/tests/page-hub.test.tsx 文件头新加的三行注释（现文件第 3–5 行：// T048 只把列头断言改成十一列…／// describe('七端岗位（桩模式渲染 #/roles）')、describe('hub 读失败只影响本组')、describe('四个读并行发出')／// 三个区块的用例与断言一个字不动。）。理由：(1) 合同第 7 节规定这一份文件「只改一条」（列头期望数组，it 标题可选），这三行是执行端为绕开基准测试里写错的 describe 记号（多一个右括号、永远命不中）而加的凑记号；门禁端热修补（5f5f5bf4）后记号已在基线原文命中，门禁端报告与一审下游须知都写明「执行端重开工时须撤掉」，本轮未撤。(2) 它让门禁的一条既有守卫变空心：tests/test_gate_t048_baseline.py:527–529 是纯子串存在性检查，注释第 4 行逐字含 describe('四个读并行发出'，而 token 的另一半 '/api/v1/hub/roles' 在同文件 :225 另有出现，所以把整个 describe('四个读并行发出', …) 区块删掉后 G01 仍然全绿——那条用例正是 D02 的回归护栏。(3) 执行报告 D08 的自述「page-hub.test.tsx 只改列头期望数组与标题」漏掉这三行。改法：只删这三行，别的一律不动，改后重跑 G01 与 V01 并在报告里写明结果。
