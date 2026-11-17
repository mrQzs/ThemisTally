# TASK: t047-desktop-web-hub-turns

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: d9e036ca3ac12ee75390561c5ed64a371827744c
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
把 `config hub show --json` 每个岗位的 `turn` 与 `last_turn` 接进本机服务的白名单与校验器，再接进桌面端 Web 的「七端岗位」一组：每行多三列（时限与工具 | 预算 | 最近一回合，放在「替补」与 T045 的「操作」之间），思考档位格在有最近一回合时显示档位三值（要求 · 映射 · 生效）。**只做片一，不含证书状态列。**

## Non-goals
- 不做证书状态列（片二另登记 T048）；不读 `getQuizsLive`，不改 `RolesPage` 的并行四读。
- 不改内核（`scripts/**`）、不改 `ts/packages/ui/src/readroutes.ts` 与 `writeroutes.ts`、不改 `ts/packages/base/**`。
- 不改 `desktop/web/src/pages/RolesPage.tsx`、`roles-RolesView.tsx`、`roles-styles.css`、`roles-PresetsTable.tsx`、`roles-ProfilesTable.tsx`、`roles-RoleCard.tsx`、`roles-PresetBar.tsx`、`roles-PresetDiff.tsx`、`desktop/web/src/components/**`、`desktop/web/src/writes/**`、`desktop/web/src/live/**`、`desktop/web/src/shell/**`、`desktop/web/src/shellpages/**`。
- 不改 `EffortPair` 等共用组件；不改 `desktop/web/tests/roles-hub-logic.test.ts`（既有断言一条都不许推翻）；不改 `desktop/web/tests/page-app.test.tsx`。
- 不改任何 `tests/test_gate_*.py`（含本片门禁基准测试 `tests/test_gate_t047_*.py`，由门禁端交付）。
- 不改 `package.json` 与锁文件（`desktop/web/package.json`、`desktop/web/package-lock.json`、`ts/package.json`、`ts/bun.lock`）；不新增依赖。

## Repository facts
以下事实都在本回合的工作目录（基线 `29e985753e68b333a2ac2d16465f4d3be42d8385`）里逐条读过；行号按该基线。规划报告是在旧基线 `26a99bf3` 上写的，**以本节为准**，与报告对不上的条目列在最后。

### 内核（只读引用，本片不改）
- `scripts/kit_roles.py:82-90` `HUB_DEFAULTS`：六个岗位的缺省绑定（coordinator quizs/deepseek/deepseek-flash/high；planner claude-code/null/claude-opus-5-5/max；contract pi/minimax/MiniMax-M3.1-Flash/high；gate pi/cc-switch-zhipu-glm/glm-5.3/high；audit pi/minimax/MiniMax-M3.1-Flash/max；exec pi/cc-switch-step-fun/step-5-preview/high）。
- `scripts/kit_roles.py:94-100` `HUB_POST_AGENTS`：coordinator→`womovie-c8`、planner→`planner-opus`、contract→`contract-glm`、gate→`gate-sonnet`、audit→`audit-sonnet`（**exec 不在里面**）。
- `scripts/kit_roles.py:104-110` `HUB_TURN_LIMITS`：coordinator 600 秒 / (read, grep, find, ls)；planner 2400 / (Read, Grep, Glob, `Bash(npm view:*)`)；contract 2400 / (read, grep, find, ls)；gate 2400 / (read, grep, find, ls, edit, write, bash)；audit 2400 / (read, grep, find, ls)（**exec 不在里面**）。
- `scripts/kit_roles.py:113-116`：`QUIZS_TURN_BUDGETS = {max_requests: 32, max_tool_calls: 48, max_input_bytes: 2097152, max_response_bytes: 8388608, max_object_bytes: 8388608}`；`QUIZS_VIEW_BUDGETS` 把前两项改成 128；`QUIZS_VIEW_POSTS = ("contract", "audit")`。
- `scripts/kit_roles.py:1255-1265` `_hub_rows`：每行加 `row["turn"] = _hub_turn(post, row["adapter"])` 与 `row["last_turn"] = _hub_last_turn(agent_dir, post)`。
- `scripts/kit_roles.py:1268-1276` `_hub_turn`：`{"timeout_seconds": 600|2400, "tools": [...], "budgets": {...}|null}`；**budgets 只在 adapter 是 quizs 时有**（contract/audit 用 128/128 的大份，其余 quizs 岗位 32/48）；不在 `HUB_TURN_LIMITS` 的岗位（exec）整项是 `null`。
- `scripts/kit_roles.py:1279-1301` `_hub_last_turn`：从 `<repo>/.agent/mailbox/turns/<工人>/<回合>/result.json` 读（目录名倒序找第一个有 result.json 的），返回 `{"at": record["finished_at"], "adapter": "claude"→"claude-code" 否则原值, "models": record["models"], "profile": record["binding_profile"], "thinking": {"requested": record["effort_requested"], "mapped": record["effort_mapped"], "effective": record["effort_effective"]}, "fallback": record["quizs_fallback"]}`；**没有信箱、没跑完过、读不出时整项是 `null`**；exec 不在 `HUB_POST_AGENTS` 里 → `null`。`agent_dir` 是 `Repo.agent_dir` = `<repo>/.agent`（`scripts/pi_dispatch.py:1465`）。
- `scripts/kit_hub.py:2724-2731` result.json 的字段：`finished_at`（`utc_now()`，秒级、`Z` 结尾）、`adapter`、`models`、`binding_profile`、`effort_requested`、`effort_mapped`、`effort_effective`。
- `scripts/kit_hub.py:2683`：`audit["effort_effective"] = ",".join(audit.get("effective_levels") or []) or None` → **生效档位可能是逗号连起来的多个**（例如 `high,medium`）；claude 走 `:2680` 的 `claude_session_effort`（单个）。
- `scripts/kit_hub.py:2749`：`summary["quizs_fallback"] = fallback`（退回替补时的原因文字）。
- `scripts/kit_hub.py:2133-2151` `quizs_unready`：退回替补的原因文字来源；`:2145` 是 `"读不出资格证书 %s" % path`——**带本机路径**；`:2212` `effective_spec` 把它作为退回原因。
- `scripts/kit_hub.py:2356`：Quizs 回报的映射档位是 `result.thinking.mapped`（空时是 `null`）。

### 服务（`ts/packages/ui`）
- `ts/packages/ui/src/redaction.ts:101-117` `HUB_ROLES_ALLOW`：**恰 15 条**（posts 的十个绑定字段 + fallback 的六个子字段；`posts.*.fallback` 本身不登记）。
- `ts/packages/ui/src/redaction.ts:132-134` `allowNullablePreviewText`（null 放行；否则是本来就不像凭据的自由文字）；`:137-141` `allowNonNegativeMs`（毫秒时间戳，**本片不动**）；`:143-146` `allowIsoMsUtc`（**带毫秒**的 ISO，**本片不动**）。
- `ts/packages/base/src/secrets.ts:214-262`：`AllowList` 的语义是「命中路径就用校验函数验那个值；合格原样返回、不合格换 `<redacted>`；命中即整体返回，不再往里走」。所以登记 `posts.*.turn.tools.*` 就是逐个数组元素验。
- `ts/packages/base/src/secrets.ts:96-98` `tokenShaped`：凭据形状（`sk-…`、`apikey_…` 等）。

### 前端（`desktop/web`）
- `desktop/web/src/pages/readonly1/roles-HubPosts.tsx`：`Section title="七端岗位"`；`Table className="rl-table rl-hub"`、`aria-label="七端岗位"`、`rowHeight={40}`；**七列**（岗位、运行时、模型、思考档位、来源、替补、操作——「操作」是 T045 加的，现在是最后一列）；props 是 `hub: Envelope<HubRolesData>`、`profiles?`、`reload?`；思考档位格是 `<EffortPair requested={p.thinking} effective={null} />`；行属性经 `rowAttrs` 给 `data-post`（**不用 `data-role`**）；读失败分支只出失败信封与 `pre`、零按钮；读成功分支里有 `<WriteFlow flow={flow} />`。
- `desktop/web/src/pages/readonly1/roles-RolesView.tsx:6` import `HubPosts`，`:11` import `./roles-styles.css`——**HubPosts 的样式比 roles-styles.css 先载入**。
- `desktop/web/src/pages/readonly1/roles-styles.css:69`：`.rl-hub .tt-table { min-width: 760px; }`（T038 S08 有基线前缀 sha256，**本片不动这份文件**）。
- `desktop/web/src/api.ts:166-173` `HubPostFallback`（`profile?`/`runtime?` 是可选键）；`:174-185` `HubPostRow`（十一个字段：`post`/`source`/`allowed_adapters`/`adapter`/`provider`/`model`/`thinking`/`profile`/`runtime`/`fallback`）；`:186-188` `HubRolesData`。
- `desktop/web/src/mock/hub-roles.ts`：六行（coordinator、planner、contract、gate、audit、exec），十个绑定字段的值与 `tests/test_gate_t038_baseline.py:601-617` 的 `SIX_ROWS_TS` 逐字一致；coordinator 的替补恰四键，contract 的替补六键。
- `desktop/web/src/pages/readonly1/roles-logic.ts`：三个既有导出 `hubPostName`、`allowedProfiles`、`normalizeHubPost`（T038 S07 只要求这三个在位、该文件只 `import type`）；`normalizeHubPost` 缺键按 null 归一。
- `desktop/web/src/components/EffortPair.tsx`：`requested` + `effective`（字符串或数组），`data-state` 取 `none`/`unknown`/`same`/`differs`，不同时加 warning 标签「与要求不同」。
- `desktop/web/src/components/Tag.tsx`：tone 取 `neutral`/`info`/`attention`/`success`/`warning`/`danger`/`escalate`/`brand`，渲染成 `<span class="tt-tag tt-tag--<tone>" data-tone="<tone>">`。
- `desktop/web/src/components/RelativeTime.tsx`：显示的是「N 秒前」这类**随钟变化**的相对时间——本片**不用**它（时刻一律原样显示内核给的原文）。
- `desktop/web/tests/page-hub.test.tsx:92`：列头断言恰是七列 `['岗位','运行时','模型','思考档位','来源','替补','操作']`；`:129-149` 的逐行用例断言**六行的思考档位都经 EffortPair**（`data-state="unknown"`、文字 `要求 X · 生效 未知`）。
- `desktop/web/tests/roles-hub-logic.test.ts`：既有三个 describe（`hubPostName`/`allowedProfiles`/`normalizeHubPost`），**本片不许改**。
- `desktop/web/tests/cleanup1-css.test.ts`：src 下每份 CSS 都要能从 `src/main.tsx` 顺 import 到达（新样式文件要被某个 src 模块 import）。
- `desktop/web/scripts/token-contract.mjs`：src 下所有 `.css/.ts/.tsx` 只许用 `src/styles/tokens.css` 里已定义的 `--tt-*` 令牌，不许写死颜色、不许声明令牌。

### 门禁现状（新基线上逐条核对，三处放宽**都已合入**）
1. `tests/test_gate_t031_baseline.py:430-444`：原 15 条路径**一条不许少**；多出来的路径只许满足「段数 > 3 且前三段是 `("posts","*","turn")` 或 `("posts","*","last_turn")`」。**注意**：`("posts","*","turn")` 与 `("posts","*","last_turn")` 这两层对象本身（段数 3）会被判成「别的路径」→ **turn、last_turn、budgets、thinking 这四层不许登记**。
2. `tests/test_gate_t038_baseline.py:631-637`（PROBE_LIB L1）：只比十个绑定字段（`post`、`source`、`allowed_adapters`、`adapter`、`provider`、`model`、`thinking`、`profile`、`runtime`、`fallback`），照旧 `toStrictEqual`。
3. `tests/test_gate_t038_baseline.py:925-933`（PROBE_PAGE P2）：只核 audit、exec 两行的思考档位仍是 EffortPair 的 `unknown`（文字 `要求 X · 生效 未知`）。
4. `tests/test_gate_t038_baseline.py:880`（P1）：只核**前六个**列头。
5. `tests/test_gate_t038_baseline.py:403`（S04）：`RolesPage` 里逐字要求 `Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])`。
6. `tests/test_gate_t038_baseline.py:293-338`（S08）：`roles-styles.css` 只许追加（基线前缀 sha256 + 追加部分的令牌/px 规矩）。
7. `tests/test_gate_t038_baseline.py:557-591`（S11）：改动的源码里不出现网络词、T007 禁用词、`role="status"`、内联 style。
8. `tests/test_gate_t042_baseline.py:482-489`：只查那 15 条**不缺**，不查多出来 → 加 15 条新路径不撞。
9. `tests/test_gate_t009_baseline.py:138-139`：`ALLOWED_API_READS` 已含 `getHubRoles` 与 `getQuizsLive`（本片不读 live）。

### 与规划报告对不上的条目（以本节为准）
1. `scripts/kit_hub.py` 里 effective 的逗号拼接在 **:2683**（报告写 2542）；`fallback` 的「读不出资格证书 %s」在 **:2145**（报告写 2016），退回替补的调用点在 **:2212**（报告写 2004–2022）。
2. 报告第 5 节 A1 成立：T045 的「操作」列仍在且**不是**被钉住的最后一列；本片三列插在它**前面** → 表变成**十列**（岗位、运行时、模型、思考档位、来源、替补、时限与工具、预算、最近一回合、操作）。
3. 报告第 8 节写的是加四列（含证书）→ 本片按站主决定**只加三列**。
4. 报告第 9 节步骤 4 没给 audit 的 `turn` → 按 `HUB_TURN_LIMITS` 补：2400 秒 + (read, grep, find, ls)、budgets `null`（audit 的载体是 pi）。
5. 报告没定三值格的 markup 与 `data-state`、没定时刻格式、没定 MiB 取整口径、没定 fallback 截断长度 → 本合同在「Behavior contract」里逐条钉死。
6. 报告第 5 节 A2（T043 的 `getQuizsLive`）与本片无关：T043 已合入（`api.ts` 里有 `QuizsLiveRow`），但本片不读 live。

### 工具链与锁文件
- `desktop/web` 用 npm：`npm test` = `vitest run`（vitest 2.1.8）、`npm run typecheck` = `tsc --noEmit`（TypeScript 5.6.3）、`npm run build` = `tsc --noEmit && vite build`、`npm run check:contract` = `node scripts/token-contract.mjs`。`desktop/web/tsconfig.json` 的 `include` 只有 `["src","vite.config.ts"]`——`tests/` 里的文件**不过** tsc，但会被 vitest 读到。
- `ts` 用 bun：`bun.lock`、`bun x vitest run packages/ui`（`ts/vitest.config.ts` 的 include 是 `packages/*/test/**/*.test.ts`）、`bun x tsc -p tsconfig.json --noEmit`。`ts/vitest.global-setup.mjs` 在「装好戳记与 bun.lock 不一致」时整轮停下——本片不改 `ts/package.json` 与 `ts/bun.lock`，戳记不会过期。
- 仓库门禁用 `python -m pytest`。

### 基线检查
- 本回合（合同端）没有 shell，**没有跑**任何测试；上面的结论都是逐文件只读核对得出的。
- 执行端动手前先跑 V01（`desktop/web` 的 `npm test`）与 V05/V06（`ts` 的 ui 包用例与类型检查），把结果记进执行报告；基线上本片的行为一个都不存在（没有三列、没有三值格、白名单里没有新路径）。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/redaction.ts
  - ts/packages/ui/test/redaction.test.ts
  - ts/packages/ui/test/hub-routes-real.test.ts
  - desktop/web/src/api.ts
  - desktop/web/src/mock/hub-roles.ts
  - desktop/web/src/pages/readonly1/roles-HubPosts.tsx
  - desktop/web/src/pages/readonly1/roles-logic.ts
  - desktop/web/tests/page-hub.test.tsx
- allowed_new_files:
  - desktop/web/src/pages/readonly1/roles-hub-turns.css
  - desktop/web/tests/roles-hub-turns.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t047_*.py
  - tests/**
  - scripts/**
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/src/writeroutes.ts
  - ts/packages/base/**
  - ts/package.json
  - ts/bun.lock
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/src/pages/RolesPage.tsx
  - desktop/web/src/pages/readonly1/roles-RolesView.tsx
  - desktop/web/src/pages/readonly1/roles-styles.css
  - desktop/web/src/pages/readonly1/roles-RoleCard.tsx
  - desktop/web/src/pages/readonly1/roles-PresetBar.tsx
  - desktop/web/src/pages/readonly1/roles-PresetDiff.tsx
  - desktop/web/src/pages/readonly1/roles-PresetsTable.tsx
  - desktop/web/src/pages/readonly1/roles-ProfilesTable.tsx
  - desktop/web/src/components/**
  - desktop/web/src/writes/**
  - desktop/web/src/live/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/tests/roles-hub-logic.test.ts
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/writes-hub-bind.test.tsx
  - desktop/web/tests/writes-hub-flow.test.tsx
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract

### 1. 服务：白名单与四个新校验器（`ts/packages/ui/src/redaction.ts`）
- 四个新校验器（都 `export function`，名字逐字照抄）：
  - `allowNonNegativeInt(value: PyValue): boolean`：`null` 放行；`bigint` 放行当 `value >= 0n`；`number` 放行当 `Number.isInteger(value) && value >= 0`；其余（字符串、布尔、对象、数组）一律 `false`。
  - `allowToolName(value: PyValue): boolean`：不是字符串 → `false`；字符串必须同时过 `/^[A-Za-z][A-Za-z0-9_-]{0,63}(\([^()\r\n]{1,128}\))?$/u`（u 标志）与 `!tokenShaped(value)`。**必须放行**：`read`、`grep`、`find`、`ls`、`edit`、`write`、`bash`、`Read`、`Grep`、`Glob`、`Bash(npm view:*)`；**必须遮掉**：像凭据的工具名（例如 `sk-abcdefghijklmnopqrstuvwxyz0123456789`）。
  - `allowIsoSecondUtc(value: PyValue): boolean`：`null` 放行；字符串必须过 `/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|\+00:00)$/u`。**必须放行**：`2026-11-15T08:00:00Z`、`2026-11-15T08:00:00+00:00`；**必须遮掉**：带毫秒的 `2026-11-15T08:00:00.000Z`、不带时区的、秒数不是两位的。
  - `allowEffortLevels(value: PyValue): boolean`：`null` 放行；字符串按 `,` 拆开，**每段 trim 后非空**且都在 `off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max` 七个档位里。**必须放行**：`high`、`high,medium`；**必须遮掉**：`high,bogus`、`high,`（空段）、`""`。
- `HUB_ROLES_ALLOW` 里**追加 15 条**路径（原有 15 条一条不许少、路径与顺序不许动；这 15 条排在原有 15 条之后）：
  1. `["posts","*","turn","timeout_seconds"]` → `allowNonNegativeInt`
  2. `["posts","*","turn","tools","*"]` → `allowToolName`
  3. `["posts","*","turn","budgets","max_requests"]` → `allowNonNegativeInt`
  4. `["posts","*","turn","budgets","max_tool_calls"]` → `allowNonNegativeInt`
  5. `["posts","*","turn","budgets","max_input_bytes"]` → `allowNonNegativeInt`
  6. `["posts","*","turn","budgets","max_response_bytes"]` → `allowNonNegativeInt`
  7. `["posts","*","turn","budgets","max_object_bytes"]` → `allowNonNegativeInt`
  8. `["posts","*","last_turn","at"]` → `allowIsoSecondUtc`
  9. `["posts","*","last_turn","adapter"]` → `HUB_ADAPTER_ENUM`（同文件既有，`null` 已放行）
  10. `["posts","*","last_turn","models","*"]` → `allowBindingName`
  11. `["posts","*","last_turn","profile"]` → `allowNullableId`
  12. `["posts","*","last_turn","thinking","requested"]` → `HUB_THINKING_ENUM`
  13. `["posts","*","last_turn","thinking","mapped"]` → `HUB_THINKING_ENUM`
  14. `["posts","*","last_turn","thinking","effective"]` → `allowEffortLevels`
  15. `["posts","*","last_turn","fallback"]` → `allowNullablePreviewText`
- **`posts.*.turn`、`posts.*.last_turn`、`posts.*.turn.budgets`、`posts.*.last_turn.thinking` 这四层对象本身不登记**（登记了会被 T031 判成「别的路径」）。
- 注释里注明出处（`scripts/kit_roles.py` 的 `_hub_turn`/`_hub_last_turn`、`scripts/kit_hub.py:2683` 的多档位拼接、`scripts/kit_hub.py:2145` 的本机路径原因文字）；`allowNonNegativeMs`、`allowIsoMsUtc`、`allowPreviewName`、`allowPreviewText`、`allowBindingName`、`allowNullableId`、`allowNullablePreviewText` 的语义一个字都不许改。

### 2. 服务：真内核夹具（`ts/packages/ui/test/hub-routes-real.test.ts`，**追加一条用例**，既有用例不动）
- 在夹具仓库的 `<repo>/.agent/mailbox/turns/womovie-c8/<回合>/result.json` 写一条回合记录（`<repo>` 是该用例 `beforeEach` 建出来的临时夹具仓库；`<回合>` 目录名随便起一个能排序的名字，例如 `20261115T080000Z-demo`），内容至少含：
  - `"finished_at": "2026-11-15T08:00:00Z"`
  - `"adapter": "quizs"`
  - `"models": ["deepseek-flash"]`
  - `"binding_profile": null`
  - `"effort_requested": "high"`
  - `"effort_mapped": "high"`
  - `"effort_effective": "high,medium"`（**逗号连起来的多个档位**）
  - `"quizs_fallback": "读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json"`（**带本机路径的原因文字**）
- 这条用例要断言：
  1. `GET /api/v1/hub/roles` 的 `data` 与直接跑 `config hub show --json` 的整份 JSON **逐字段一致**（照既有 U9 用例的 `toEqual` 口径）；
  2. coordinator 行的 `turn.timeout_seconds` 是 `600`、`turn.tools` 是 `["read","grep","find","ls"]`、`turn.budgets.max_requests` 是 `32`、`turn.budgets.max_tool_calls` 是 `48`；
  3. coordinator 行的 `last_turn.at` 是 `"2026-11-15T08:00:00Z"`、`last_turn.adapter` 是 `"quizs"`、`last_turn.models` 是 `["deepseek-flash"]`、`last_turn.thinking.mapped` 是 `"high"`、`last_turn.thinking.effective` 是 `"high,medium"`（**没被遮成 `<redacted>`**）、`last_turn.fallback` 是上面那整句原文（**没被遮**）；
  4. 其余五个岗位的 `last_turn` 是 `null`（夹具仓库里没有他们的信箱）。

### 3. 前端：类型与桩
- `desktop/web/src/api.ts`：**只加不改**。加四个接口与两个可选键：
  - `export interface HubPostBudgets { max_requests: number | null; max_tool_calls: number | null; max_input_bytes: number | null; max_response_bytes: number | null; max_object_bytes: number | null; }`
  - `export interface HubPostTurn { timeout_seconds: number | null; tools: string[]; budgets: HubPostBudgets | null; }`
  - `export interface HubPostLastTurnThinking { requested: string | null; mapped: string | null; effective: string | null; }`
  - `export interface HubPostLastTurn { at: string | null; adapter: string | null; models: string[]; profile: string | null; thinking: HubPostLastTurnThinking; fallback: string | null; }`
  - `HubPostRow` 加两个**可选**键：`turn?: HubPostTurn | null;` 与 `last_turn?: HubPostLastTurn | null;`（旧服务缺键也能编译）。
- `desktop/web/src/mock/hub-roles.ts`：**十个绑定字段一个都不许改**，只给每行加 `turn` 与 `last_turn`（逐字段照下表；键名是服务返回的 `turn` / `last_turn`）：

| 岗位 | turn | last_turn |
|---|---|---|
| coordinator | `{ timeout_seconds: 600, tools: ['read','grep','find','ls'], budgets: { max_requests: 32, max_tool_calls: 48, max_input_bytes: 2097152, max_response_bytes: 8388608, max_object_bytes: 8388608 } }` | `{ at: '2026-11-15T08:00:00Z', adapter: 'quizs', models: ['deepseek-flash'], profile: null, thinking: { requested: 'high', mapped: 'high', effective: null }, fallback: null }` |
| planner | `{ timeout_seconds: 2400, tools: ['Read','Grep','Glob','Bash(npm view:*)'], budgets: null }` | `{ at: '2026-11-15T07:30:00Z', adapter: 'claude-code', models: ['claude-opus-5-5'], profile: null, thinking: { requested: 'max', mapped: null, effective: 'max' }, fallback: null }` |
| contract | `{ timeout_seconds: 2400, tools: ['read','grep','find','ls'], budgets: { max_requests: 128, max_tool_calls: 128, max_input_bytes: 2097152, max_response_bytes: 8388608, max_object_bytes: 8388608 } }` | `{ at: '2026-11-15T09:00:00Z', adapter: 'pi', models: ['step-5-preview'], profile: 'step-high', thinking: { requested: 'high', mapped: null, effective: 'high' }, fallback: '读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json' }` |
| gate | `{ timeout_seconds: 2400, tools: ['read','grep','find','ls','edit','write','bash'], budgets: null }` | `{ at: '2026-11-15T09:15:00Z', adapter: 'pi', models: ['cc-switch-zhipu-glm/glm-5.3'], profile: null, thinking: { requested: 'high', mapped: null, effective: 'high' }, fallback: null }` |
| audit | `{ timeout_seconds: 2400, tools: ['read','grep','find','ls'], budgets: null }` | `null` |
| exec | `null` | `null` |

### 4. 前端：纯函数（`desktop/web/src/pages/readonly1/roles-logic.ts`，**只追加**）
- 三个既有导出（`hubPostName`、`allowedProfiles`、`normalizeHubPost`）的签名与行为**一字不改**；该文件仍然只 `import type`。
- `normalizeHubPost` 的返回值**加两个字段**：`turn: HubPostTurnInfo | null` 与 `lastTurn: HubPostLastTurnInfo | null`；归一规则：**缺键、类型不对、不是对象一律按 `null`**；`turn.budgets` 不是对象 → `null`；`turn.tools` 不是数组 → `[]`；`last_turn.models` 不是数组 → `[]`；`last_turn.thinking` 不是对象 → 三个档位都 `null`；`last_turn.fallback` 不是字符串 → `null`。
- 新增四个归一类型（名字逐字照抄）：`HubPostBudgetInfo`、`HubPostTurnInfo`、`HubPostLastTurnThinkingInfo`、`HubPostLastTurnInfo`（字段与 `api.ts` 的四个接口一一对应，只是 `budgets` 与 `thinking` 可空）。
- 新增九个纯函数（**名字逐字照抄**，都是纯函数、不碰 DOM 与时钟）：
  - `hubTimeoutText(turn: HubPostTurnInfo | null): string` —— `turn` 为 `null` → `'—'`；`timeout_seconds` 为 `null` → `'—'`；秒数能被 60 整除 → `` `${秒数 / 60} 分钟` ``；否则 → `` `${秒数} 秒` ``。工具为**空数组**时只给时限那一段；否则是 `` `${时限} · ${工具用「、」连起来}` ``。
  - `hubBudgetText(budgets: HubPostBudgetInfo | null): string` —— `budgets` 为 `null` → `'—'`；否则是 `` `请求 ${max_requests} · 工具调用 ${max_tool_calls} · ${入} / ${出} / ${对象} MiB` ``，其中三个字节数各自按 `Math.round(字节 / 1048576)` 换算成整数 MiB；任一项是 `null` 时该项写 `'—'`。
  - `hubMib(bytes: number | null): string` —— `null` → `'—'`；否则 `String(Math.round(bytes / 1048576))`。
  - `hubEffortTriple(lastTurn: HubPostLastTurnInfo | null): string` —— `lastTurn` 为 `null` → `'—'`；否则是 `` `要求 ${requested ?? '—'} · 映射 ${mapped ?? '—'} · 生效 ${生效文字}` ``，其中生效文字是 `effective` 按 `,` 拆开、去空白、滤掉空段后用「、」连起来；`effective` 为 `null` 或拆开没有段 → `'—'`。
  - `hubEffortDiffers(lastTurn: HubPostLastTurnInfo | null): boolean` —— `requested` 为 `null` → `false`；`effective` 拆开有段且**任一段不等于 `requested`** → `true`；`effective` 没有段而 `mapped` 非 `null` 且 `mapped !== requested` → `true`；其余 `false`。
  - `hubEffortState(lastTurn: HubPostLastTurnInfo | null): 'none' | 'unknown' | 'same' | 'differs'` —— `lastTurn` 为 `null` 或 `requested` 为 `null` → `'none'`；`effective` 没有段 → `'unknown'`；`hubEffortDiffers` 为真 → `'differs'`；否则 `'same'`。
  - `hubLastTurnText(lastTurn: HubPostLastTurnInfo | null): string` —— `lastTurn` 为 `null` → `'—'`；否则是 `` `${at ?? '—'} · ${adapter ?? '—'} · ${models 用「、」连起来（空数组写 '—'）}` ``。
  - `hubLastTurnMark(lastTurn: HubPostLastTurnInfo | null, boundAdapter: string | null): '退回替补' | '与当前绑定不同' | null` —— `lastTurn` 为 `null` → `null`；`fallback` 非 `null` → `'退回替补'`；`fallback` 为 `null` 且 `lastTurn.adapter` 与 `boundAdapter` **都非 null 且不相等** → `'与当前绑定不同'`；其余 `null`。
  - `hubFallbackExcerpt(text: string | null): { shown: string; full: string }` —— `text` 为 `null` → `{ shown: '', full: '' }`；长度 ≤ 20 → `{ shown: text, full: text }`；否则 `{ shown: text.slice(0, 20) + '…', full: text }`。
- 这些函数**不许**去改 `p.thinking`（当前绑定的要求档位）：三值格里的「要求」是 `last_turn.thinking.requested`。

### 5. 前端：视图（`desktop/web/src/pages/readonly1/roles-HubPosts.tsx`）
- 列头从七列变**十列**，次序逐字是：`岗位`、`运行时`、`模型`、`思考档位`、`来源`、`替补`、`时限与工具`、`预算`、`最近一回合`、`操作`。前六列**一个字都不改**（T038 的 P1 只核前六个列头）；T045 的「操作」列与它的两个写入口**一个字都不改**，位置仍在最后。
- **思考档位格**：
  - `lastTurn` 为 `null`（桩里是 audit、exec）→ 照旧渲染 `<EffortPair requested={p.thinking} effective={null} />`（`data-state="unknown"`、文字 `要求 X · 生效 未知`——T038 P2 要的就是这个）。
  - `lastTurn` 非 `null` → 渲染三值格：外层 `<span className="tt-effort" data-state={hubEffortState(lastTurn)}>`，里面依次是三个 `<span className="tt-effort__label">`（`要求`、`映射`、`生效`）与三个 `<span className="tt-effort__level">`（值），段与段之间是 ` · `（一个空格、一个 U+00B7、一个空格）。三个值分别来自 `hubEffortTriple` 的三段（`null` 写 `—`；生效的多个档位用「、」连起来）。`hubEffortDiffers` 为真时，在这一格**末尾**加一个 `<Tag tone="warning">与要求不同</Tag>`（文字逐字「与要求不同」）。
- **时限与工具格**：文字就是 `hubTimeoutText(p.turn)`。
- **预算格**：文字是 `hubBudgetText(p.turn?.budgets ?? null)`；其中 `入 / 出 / 对象 MiB` 这一段要单独包在一个 `<span>` 里，带 `aria-label="单次输入 2 MiB、单次回应 8 MiB、单个对象 8 MiB"`（三个数按同一换算，`null` 的项写 `—` MiB），**文字照旧**显示 `2 / 8 / 8 MiB`。
- **最近一回合格**：`hubLastTurnText(p.lastTurn)`；`hubLastTurnMark` 非 `null` 时加一个标签：`'退回替补'` 用 `<Tag tone="warning">`，`'与当前绑定不同'` 用 `<Tag tone="neutral">`；`fallback` 非 `null` 时，标签后面跟 `hubFallbackExcerpt(p.lastTurn.fallback).shown`（截断后的文字），并给**这一段文字**（不是整个格）加 `title` 等于 `hubFallbackExcerpt(...).full`（全文）。
- 表格里**不许出现可聚焦元素**（按钮、链接、`tabIndex`）——新三格里只有 `span` 与 `Tag`。
- 读失败分支、`<WriteFlow flow={flow} />`、T038 S10 的静态形状（`title="七端岗位"`、`aria-label="七端岗位"`、`rowHeight={40}`、`rl-hub`、`hubPostName`、`rowAttrs` 给的 `data-post`、**不出现 `data-role`**）一个都不许丢。
- 视图从 `../../api` **只许 `import type`**；不许出现网络词、T007 禁用词、`role="status"`、内联 style。
- 新样式文件 `desktop/web/src/pages/readonly1/roles-hub-turns.css` 在 `roles-HubPosts.tsx` 里 import（放在组件 import 之后）。因为 `roles-RolesView.tsx:6` 先 import `HubPosts`、`:11` 才 import `roles-styles.css`，**新文件里的规则必须比 `.rl-hub .tt-table` 特异性更高才生效**：放宽表宽的那条写成 `.rl-hub table.tt-table { min-width: 1120px; }`（特异性 (0,2,1) > (0,2,0)），并给 `/* 画布：七端岗位表加了「时限与工具」「预算」「最近一回合」三列 */` 这样的出处注释；新文件**只许用 `src/styles/tokens.css` 里已定义的 `--tt-*` 令牌**、不许写死颜色、不许声明令牌；除 `0` 与 `1px` 外的 px 字面量同一行要带出处注释。

### 6. 前端：包内测试
- `desktop/web/tests/page-hub.test.tsx`：**只许改两处**（列头断言、思考档位逐行断言）与其 `it()` 标题；**`describe('七端岗位（桩模式渲染 #/roles）')` 的标题一个字都不动**，别的用例（操作列按钮、data-post、位置、`?mock=empty`、读失败、四个读并行）一个字都不动。
  - 列头断言改成十列：`['岗位','运行时','模型','思考档位','来源','替补','时限与工具','预算','最近一回合','操作']`。
  - 思考档位逐行断言改成：有最近一回合的四行（coordinator、planner、contract、gate）断言三值文字**逐字**是 `要求 high · 映射 high · 生效 —`、`要求 max · 映射 — · 生效 max`、`要求 high · 映射 — · 生效 high`、`要求 high · 映射 — · 生效 high`；audit、exec 两行**照旧**断言经 EffortPair（`data-state="unknown"`、文字 `要求 max · 生效 未知` 与 `要求 high · 生效 未知`）。
  - 另外**新增**一个用例，断言三个新列的逐格文字：coordinator 的「时限与工具」是 `10 分钟 · read、grep、find、ls`、「预算」是 `请求 32 · 工具调用 48 · 2 / 8 / 8 MiB`、「最近一回合」是 `2026-11-15T08:00:00Z · quizs · deepseek-flash`；planner 的「时限与工具」是 `40 分钟 · Read、Grep、Glob、Bash(npm view:*)`、「预算」是 `—`；contract 的「预算」是 `请求 128 · 工具调用 128 · 2 / 8 / 8 MiB`，「最近一回合」那一格里有 `tt-tag--warning` 的「退回替补」与 `title` 等于完整原因文字；gate 的「时限与工具」是 `40 分钟 · read、grep、find、ls、edit、write、bash`；audit 的「时限与工具」是 `40 分钟 · read、grep、find、ls`、`exec` 的三格都是 `—`。
- **新文件 `desktop/web/tests/roles-hub-turns.test.ts`**（纯逻辑，不许 `skip`/`only`/`todo`；测试测真实实现，不许把业务逻辑抄一份进测试）：
  1. `normalizeHubPost` 的归一：旧服务缺 `turn`/`last_turn` 两个键 → 都按 `null`；`turn` 是对象但 `budgets` 缺键 → `budgets` 是 `null`；`tools` 不是数组 → `[]`；`last_turn.thinking` 缺键 → 三个档位都 `null`。
  2. `hubTimeoutText`：600 → `10 分钟`；2400 → `40 分钟`；45 → `45 秒`；`null` → `—`；空工具 → 只有时限那一段。
  3. `hubBudgetText` 与 `hubMib`：2097152 → `2`；8388608 → `8`；`null` → `—`；文本逐字是 `请求 32 · 工具调用 48 · 2 / 8 / 8 MiB`。
  4. `hubEffortTriple` / `hubEffortDiffers` / `hubEffortState`：三值逐字；`effective` 是 `high,medium` → 生效一段是 `high、medium`；`mapped` 与 `requested` 不同、`effective` 为 `null` → `differs` 为真、状态是 `differs`；`requested` 为 `null` → 状态 `none`、不判不同。
  5. `hubLastTurnText` / `hubLastTurnMark`：有 `fallback` → 标记是「退回替补」；`fallback` 为 `null` 且实际载体与绑定载体不同 → 「与当前绑定不同」；两者相同 → `null`。
  6. `hubFallbackExcerpt`：短句原样；长句 `shown` 是前 20 个字加 `…`、`full` 是全文。
  7. **真实模式不出现桩的值**：用 `setLiveClientForTests` 注入一个只回 `posts`（每行没有 `turn`/`last_turn`）的假客户端，渲染 `#/roles`，断言三个新列都是 `—`、思考档位仍是 EffortPair 的 unknown，且页面上**不出现**桩里的 `10 分钟`、`请求 32`、`2026-11-15T08:00:00Z` 这些字样。

### 7. 边界输入
- 服务旧版本没有 `turn`/`last_turn` 两个键 → 前端按 `null` 处理（两个键都是**可选**的）。
- `turn` 有、`budgets` 是 `null`（载体不是 quizs）→ 「预算」格是 `—`。
- `last_turn` 有、`models` 是空数组 → 「最近一回合」的模型一段是 `—`。
- `last_turn.fallback` 里有本机路径 → 服务按 `allowNullablePreviewText` **放行**（不遮）；界面上截断显示、`title` 给全文。
- `effective` 是逗号连起来的多个档位 → 服务**放行**（逐段校验），界面上用「、」连起来显示。
- `timeout_seconds` 是负数或小数、时刻带毫秒、`effective` 里有非法档位、工具名像凭据 → 服务把这些值换成 `<redacted>`；前端照常显示（显示的是 `<redacted>` 那一串）。
- hub 读失败 → 整组照旧只出失败信封与 `pre`，**零行零按钮**（既有断言照旧）。
- `getQuizsLive` **不许**加进 `Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])`（T038 S04 的逐字断言）；本片根本不用 live。

### 8. 错误与重试
- 服务侧不合格的值一律换成 `<redacted>`（既有语义），不抛错、不重试。
- 前端读到形状不对的 `turn`/`last_turn` 一律按 `null`/空值处理，不抛错、不显示半截数据。
- 读失败分支、`useWriteFlow`、写流程一个字都不改。

### 9. 并发、取消与状态变化
不适用——本片不加并发、不加读、不加计时器；本片不引入 `getQuizsLive` 的单独读取（那是片二）。

### 10. 兼容性
- `HUB_ROLES_ALLOW` 原有 15 条路径与它们的校验函数语义一字不改（只追加 15 条新的）；`allowNonNegativeMs`、`allowIsoMsUtc`、`allowPreviewName`、`allowPreviewText`、`allowBindingName`、`allowNullableId`、`allowNullablePreviewText` 的行为一字不改。
- `HubPostRow` 只**加**两个可选键，既有十一个字段的类型一字不改；`HubRolesData` 不变。
- `roles-logic.ts` 的三个既有导出签名与行为不变，只新增类型与九个纯函数；该文件仍只 `import type`。
- `HubPosts` 的 props 不变（`hub`、`profiles?`、`reload?`）；`RolesView` 与 `RolesPage` 一字不改。
- 前六列与「操作」列的文字与入口一字不改；新增三列插在「替补」与「操作」之间。
- `desktop/web/src/mock` 仍恰 14 份 JSON；`desktop/web/src/pages` 顶层仍恰 9 个 `*Page.tsx`；`package.json` 与锁文件不变。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。**再读一遍门禁端交付的本片门禁基准测试文件**（`tests/test_gate_t047_baseline.py`，只读；基线上还不存在就跳过），把它的断言与本合同的「写法钉死」一节对一遍；有出入以本合同的「写法钉死」为准，并把出入写进执行报告。
2. **先跑基线**：在 `desktop/web` 跑 `npm test`、在 `ts` 跑 `bun x vitest run packages/ui` 与 `bun x tsc -p tsconfig.json --noEmit`，把结果记进执行报告（基线应全绿；本片的行为一个都还不存在）。
3. **`ts/packages/ui/src/redaction.ts`**：按 Behavior contract 第 1 节写四个新校验器（名字逐字照抄）与 15 条新路径；原有 15 条一条不许少；四层对象不许登记；注释注明出处。
4. **`ts/packages/ui/test/redaction.test.ts`**（**追加**一个 describe，既有断言一条不许改）：
   - 合格值原样放行：`turn.timeout_seconds` = 600；`turn.tools` = `['read','grep','find','ls','edit','write','bash','Read','Grep','Glob','Bash(npm view:*)']`；`turn.budgets` 的五项 = 32/48/2097152/8388608/8388608；`last_turn.at` = `2026-11-15T08:00:00Z` 与 `2026-11-15T08:00:00+00:00`；`last_turn.adapter` = `quizs`；`last_turn.models` = `['deepseek-flash']`；`last_turn.profile` = `null`；`last_turn.thinking.requested` = `high`、`mapped` = `high`、`effective` = `high,medium`；`last_turn.fallback` = 一句带本机路径的原因文字。
   - 不合格值变 `<redacted>`：`timeout_seconds` = -1 与 1.5；`at` = `2026-11-15T08:00:00.000Z`；`effective` = `high,bogus`；`tools` 里放一个像凭据的工具名（`sk-abcdefghijklmnopqrstuvwxyz0123456789`）。
   - 原有 15 条一条不少：断言 `HUB_ROLES_ALLOW` 里那 15 条路径都在（逐条比对路径元组），并断言白名单里**没有** `posts.*.turn`、`posts.*.last_turn`、`posts.*.turn.budgets`、`posts.*.last_turn.thinking` 这四个对象层。
5. **`ts/packages/ui/test/hub-routes-real.test.ts`**：按 Behavior contract 第 2 节追加一条用例（写 result.json 夹具 + 逐字段一致 + 五个断言）。
6. **`desktop/web/src/api.ts`**：按 Behavior contract 第 3 节加四个接口与两个可选键，别的一字不改。
7. **`desktop/web/src/mock/hub-roles.ts`**：按 Behavior contract 第 3 节的表给六行加 `turn` 与 `last_turn`；十个绑定字段一个都不许改。
8. **`desktop/web/src/pages/readonly1/roles-logic.ts`**：给 `normalizeHubPost` 加 `turn`/`lastTurn` 两个字段（归一规则照 Behavior contract 第 4 节），加四个归一类型与九个纯函数（名字与行为逐字照抄）；三个既有导出与 `import type` 规矩照旧。
9. **`desktop/web/src/pages/readonly1/roles-HubPosts.tsx`**：按 Behavior contract 第 5 节加三列与三值格（新列插在「替补」与「操作」之间），import 新样式文件；前六列、「操作」列、读失败分支、静态形状照旧。
10. **新建 `desktop/web/src/pages/readonly1/roles-hub-turns.css`**：只许用已定义的 `--tt-*` 令牌；放宽表宽的那条写成 `.rl-hub table.tt-table { min-width: 1120px; }` 并带出处注释；px 字面量按仓库规矩处理。
11. **新建 `desktop/web/tests/roles-hub-turns.test.ts`**：按 Behavior contract 第 6 节的七组用例（含真实模式不出现桩的值）。
12. **`desktop/web/tests/page-hub.test.tsx`**：按 Behavior contract 第 6 节改两处断言与标题，并新增一个新列逐格文字的用例；`describe` 标题不动。
13. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → V04 → V05 → V06 → V07 → R01**（本 worktree 里若没有依赖，先跑 Setup 的两条准备命令）；R01 墙钟上限 2760 秒，可以分批跑（文件集合不许少，每批 cwd 照旧是仓库根），但报告里要逐批列出结果并给出合并结论（全过才算 R01 过），不许漏跑任何文件、不许用 `-x`/`--lf` 代替。
14. 写执行报告；遇到合同未定义的行为（例如服务回的字段形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s
- S02：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t047_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t049_baseline.py -q` · cwd：仓库根 · 超时：2760s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- V04（必要）：`npm run check:contract` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V05（必要）：`bun x vitest run packages/ui/test/redaction.test.ts packages/ui/test/hub-routes-real.test.ts` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V06（必要）：`bun x vitest run packages/ui` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V07（必要）：`bun x tsc -p tsconfig.json --noEmit` · cwd：ts · 超时：900s · 期望退出码：0

## Definition of done
- D01：服务白名单登记 15 条新路径（逐条见 Behavior contract 第 1 节），四个新校验器（`allowNonNegativeInt`、`allowToolName`、`allowIsoSecondUtc`、`allowEffortLevels`）行为逐字照抄；原有 15 条路径一条不少、语义不变；`posts.*.turn`、`posts.*.last_turn`、`posts.*.turn.budgets`、`posts.*.last_turn.thinking` 四层对象不登记；证据：V05、V06、R01、G01；目的：不合格的值不能原样流到界面上，而 T031 的新判法要求这四层不登记，登记了任何合规实现都过不了 R01。
- D02：`ts/packages/ui/test/redaction.test.ts` 追加的用例逐项覆盖：15 条新路径的合格值原样放行（多个档位的 `high,medium`、秒级 `Z` 与 `+00:00` 两种时刻、带本机路径的 fallback 文字、`Bash(npm view:*)` 工具名），不合格值（负数、小数、带毫秒、`high,bogus`、像凭据的工具名）变 `<redacted>`；原有 15 条一条不少；证据：V05、V06；目的：过了检查不是目标，界面上不能出现内核没给过的形状。
- D03：真内核夹具（`hub-routes-real` 追加的那条）里有一回合带 `effort_mapped`、`effective` 写 `high,medium`、带 `quizs_fallback`；读路由与 `config hub show --json` 逐字段一致，且这些值没被遮成 `<redacted>`；证据：V05、V06、R01；目的：白名单放行了什么要由真内核的输出作证，不是由单元测试里的假数据作证。
- D04：`desktop/web/src/api.ts` 加了四个接口与 `HubPostRow` 的两个**可选**键（旧服务缺键也能编译）；既有字段与类型一字不改；证据：V02、V03、V07、scope。
- D05：桩的六行加了 `turn` 与 `last_turn`（逐字段照 Behavior contract 第 3 节的表），十个绑定字段一个都没改；证据：V01、R01、G01；目的：T038 的 PROBE_LIB 只比十个绑定字段，桩的绑定值不能为了新列而改动。
- D06：`roles-logic.ts` 的九个纯函数（`hubTimeoutText`、`hubBudgetText`、`hubMib`、`hubEffortTriple`、`hubEffortDiffers`、`hubEffortState`、`hubLastTurnText`、`hubLastTurnMark`、`hubFallbackExcerpt`）与 `normalizeHubPost` 的 `turn`/`lastTurn` 归一行为逐字照合同；三个既有导出不变、该文件仍只 `import type`；证据：V01、V02、V06、review；目的：显示逻辑要能脱离 DOM 单测，界面上算出来的每一格都要有一个能断言的纯函数。
- D07：「七端岗位」一组是十列（岗位、运行时、模型、思考档位、来源、替补、时限与工具、预算、最近一回合、操作）；前六列与「操作」列一个字不改；有最近一回合的四行显示三值（要求 · 映射 · 生效），没有最近一回合的 audit、exec 两行照旧经 EffortPair（`data-state="unknown"`、文字 `要求 X · 生效 未知`）；证据：V01、G01、R01；目的：T038 P2 只核 audit、exec 两行，前六格是既有承诺，不能借加列之机改动。
- D08：三个新格的口径逐条照合同：时限（能被 60 整除写「N 分钟」，否则「N 秒」）与工具（「、」连接）；预算（`请求 N · 工具调用 N · X / Y / Z MiB`，MiB 按 `Math.round(字节/1048576)`，那一段带 `aria-label="单次输入 2 MiB、单次回应 8 MiB、单个对象 8 MiB"`）；最近一回合（`时刻 · 实际载体 · 模型`，时刻原样显示内核给的秒级 UTC 原文，退回替补是 warning Tag、带原因文字截断显示且 `title` 给全文，载体与当前绑定不同是 neutral Tag「与当前绑定不同」）；证据：V01、V03、V04、review；目的：这三个格是用户判断「这个岗位这一回合拿到了什么」的唯一入口，数字与文字的口径不许各写各的。
- D09：新样式文件 `roles-hub-turns.css` 只用已定义的 `--tt-*` 令牌、不写死颜色、不声明令牌；放宽表宽的规则是 `.rl-hub table.tt-table { min-width: 1120px; }`（比 `roles-styles.css:69` 的 `.rl-hub .tt-table` 特异性更高，才不会被它盖掉）；`roles-styles.css` 一个字节都没改；证据：V03、V04、R01、scope；目的：T038 S08 给 roles-styles.css 钉了基线前缀 sha256，且新样式比旧样式先载入，规则写不对就等于没写。
- D10：`desktop/web/tests/page-hub.test.tsx` 只改了两处断言（列头、思考档位逐行）与它们的 `it()` 标题，并新增一个新列逐格文字的用例；`describe('七端岗位（桩模式渲染 #/roles）')` 的标题不动；既有断言没被删、跳过或弱化；新文件 `desktop/web/tests/roles-hub-turns.test.ts` 覆盖 D06–D08 的每一项（含真实模式不出现桩的值）；证据：V01、review；目的：验收看的是行为有没有被测住，不是测试文件在不在。
- D11：新代码守既有源码规矩：`roles-HubPosts.tsx` 从 `../../api` 只 `import type`、不出现网络词与 T007 禁用词、`role="status"`、内联 style、`data-role`；表格新格里没有可聚焦元素；页面文字里不出现 `step-low`；目的：不破 T006/T009/T013/T038 的长期门禁；证据：V01、V03、V04、R01、review。
- D12：`RolesPage` 的并行四读一字不改（`getQuizsLive` 没有被加进 `Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])`）；本片不读 live、不加证书列、不改 `RolesView`；证据：R01、G01、scope；目的：证书列是片二（T048）的事，这一版不许顺手做。
- D13：所有修改都在允许集合内（可改 8 个文件、可新增 2 个文件），没有碰 forbidden_paths（`tests/**` 含 `tests/test_gate_t047_*.py`、`scripts/**`、`ts/packages/base/**`、`desktop/web/src/components/**`、`desktop/web/src/writes/**`、`desktop/web/src/live/**`、`desktop/web/src/shell/**`、`desktop/web/src/shellpages/**`、`roles-styles.css`、`roles-RolesView.tsx`、`RolesPage.tsx`、`roles-hub-logic.test.ts`、`page-app.test.tsx` 等）；`package.json` 与锁文件不变；证据：scope、review；目的：这一片不许顺手改别的片的地盘。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `redaction.ts` 里没有 `HUB_ROLES_ALLOW`/`HUB_ADAPTER_ENUM`/`HUB_THINKING_ENUM`/`allowBindingName`/`allowNullableId`/`allowNullablePreviewText`、`roles-logic.ts` 里没有 `hubPostName`/`allowedProfiles`/`normalizeHubPost`、`api.ts` 里没有 `HubPostRow`/`HubPostFallback`/`HubRolesData`、三处门禁放宽在新基线上不是合同写的那个形态），特别是这些文件被改名或整体挪了位置（停下报告，由合同端出下一版改 Scope 里的确切路径，不要自己猜名字）。
- 必须修改允许范围之外的文件才能继续（例如要动 `readroutes.ts`、`RolesPage.tsx`、`roles-RolesView.tsx`、`roles-styles.css`、`roles-hub-logic.test.ts`、任何 `tests/test_gate_*.py`）。
- 门禁端交付的 `tests/test_gate_t047_baseline.py` 与本合同的「写法钉死」一节出现实质冲突（例如它要求的导出名或列头与本合同给的不一致）：停下并报告（不要自己改门禁文件，也不要私自换一种写法绕过）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要做证书列、要在缺省行显示最近一回合、要在 `Promise.all` 里加 live 读取）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id `t047-desktop-web-hub-turns` 汇总，含返工版本；本 task-id 累计已用 0 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（按 task-id 跨版本累计；累计已用 0 秒 = 3 × 5400，覆盖本版与两次返工）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与门禁文件、核对事实 15 分钟；实现（四个校验器与 15 条路径、白名单测试、真内核夹具、api 类型、桩、roles-logic 纯函数、HubPosts 三列与三值格、新样式）45 分钟；补测（新逻辑测试文件、page-hub 两处改）20 分钟；必要检查（V01–V07 与 R01，R01 约 27 分钟、可分批跑）25 分钟；最终报告 5 分钟；总计约 110 分钟，单轮时限 5400 秒（90 分钟）——总量 16200 秒覆盖本版与两次返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D13，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261115T103010042769Z-owner-9c1b1f：

> 站主决定（2026-11-15）：
> 1. 拆法认可。T047 只做片一：规划报告第 9 节第 1–6 步。
>    - 服务：15 条新路径与新校验器（含 allowNonNegativeInt）；hub-routes-real 追加一条。
>    - 前端：api.ts 的类型；桩六行加 turn、last_turn；roles-logic 的归一与纯函数；“七端岗位”加三列与三值格。
>    - 不加证书列。合同照片一写，合同端照常等 T045 结项、内核挪基线、写信再开工。
> 2. 片二（第 7 步，证书列）站主另登记 T048（--after T047）。它的任务书附上这份规划报告的片二部分，以及第 8 节证书一格的摆法。
> 3. 三处门禁都放宽，不退役。站主在 T047 合同开工前合入门禁准备，口径如下：
>    - T031 test_static_redaction_allowlist :430–442：原 15 条一条不许少；多出来的路径只许在 posts.*.turn 与 posts.*.last_turn 之下，别处多一条照旧不过。
>    - T038 PROBE_LIB L1 :627–634：六行只比十个绑定字段（post、source、allowed_adapters、adapter、provider、model、thinking、profile、runtime、fallback），照旧 toStrictEqual。
>    - T038 PROBE_PAGE P2 :918–927：只核 audit、exec 两行的思考档位仍是 EffortPair 的 unknown。桩里这两行的 last_turn 是 null（第 9 节第 4 步）。
> 4. 前六格不改，T038 P2 :900–916 核的运行时、模型、替补文字照旧。新列放在“替补”与“操作”之间。page-hub.test.tsx 的列头与思考档位逐行两处写进合同的允许修改范围，describe 标题不动。
> 5. 第 4 节的两条事实写进合同的约束：
>    - effective 可能是逗号连起来的几个档位：拆开，逐段校验、逐段显示；
>    - fallback 的原因文字可能带本机路径：照 allowNullablePreviewText 放行，界面截断显示，title 给全文。
