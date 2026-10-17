# TASK: auth-refresh-401

<!-- 示例：展示高风险任务需要的合同深度（来自方案第 14 节）。仓库、文件、函数与基线 ID 都是假设的，
     真实仓库必须先调查并由熟悉当前认证系统的人审阅语义。认证语义未定之前不要派遣。 -->

## Identity
- plan_version: 1
- repository: example-web-client
- base_sha: 89abcdef0123456789abcdef0123456789abcdef
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: none（验收通过后交给人审阅，再决定集成）
- executor: step/step-5-preview · thinking high

## Goal
普通 API 请求收到 401 时，由共享的刷新协调器最多刷新一次，并最多重放原请求一次。并发 401、迟到 401、取消、会话切换这几种情况下，不出现重复刷新、无限重试、旧会话复活、用新会话凭据重放旧请求或永不结束的等待。

## Non-goals
- 不改变 token 的存储方式与持久化位置（`src/auth/store.ts` 只读）。
- 不改变登出流程、登录页跳转与错误提示文案。
- 不为非幂等写请求新增幂等键机制（没有服务端契约时一律不自动重放）。
- 不处理 refresh token 轮换策略本身（由 `src/auth/refresh.ts` 负责，只读）。

## Repository facts
- 入口：`src/api/client.ts` 的 `request(input: RequestSpec, init?: { signal?: AbortSignal })`，基于 fetch 的包装。
- 会话状态：`src/auth/store.ts` 已提供 `getAccessToken()`、`getTokenVersion(): number`、`getSessionGeneration(): number`、`setTokens(tokens, expectedGeneration): boolean`（代次不符返回 false 且不写入）、`markSessionExpired(reason)`。
- 刷新：`src/auth/refresh.ts` 的 `refreshTokens(signal?: AbortSignal): Promise<Tokens>`。refresh 端点本身返回 401 时抛出 `RefreshUnauthorizedError`，网络错误或 5xx 抛出 `RefreshTransientError`。
- `RequestSpec` 有 `method`、`url`、`body?: BodyInit`、`replayable?: boolean`、`idempotencyKey?: string`。
- 每个请求发出时都能从 store 读到当时的 `getSessionGeneration()` 与 `getTokenVersion()`；本任务把二者记录在请求上下文中。
- 工具链：Node 22、pnpm 9、vitest 3（fake timers 可用）、TypeScript 5 strict。
- 基线检查：`pnpm exec vitest run src/api` 通过（18 tests）；类型检查通过。

## Scope
- allowed_modified_files:
  - src/api/client.ts
- allowed_new_files:
  - src/api/refresh-coordinator.ts
  - src/api/client.refresh.test.ts
- allowed_deleted_files: 无
- forbidden_paths: src/auth/store.ts、src/auth/refresh.ts、package.json、pnpm-lock.yaml
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

| 情况 | 必须的行为 |
|---|---|
| 普通请求第一次 401 | 符合重放条件时，等待（或发起）刷新，然后最多重放一次 |
| refresh 请求本身 401 | 不递归刷新。刷新发起时的 sessionGeneration 仍是当前代次：调用 `markSessionExpired("refresh_unauthorized")`，等待者都收到 `SessionExpiredError`。代次已变化：不标记当前会话失效，等待者收到 `SessionChangedError` |
| 刷新时网络错误或 5xx | 等待者都收到 `RefreshTransientError`；不标记会话失效；后续请求可以再次触发刷新 |
| 重放后仍然 401 | 不再刷新；按会话失效处理 |
| 同一波并发 401 | 共享同一个刷新 promise，只调用一次 `refreshTokens` |
| 刷新完成后才返回的旧 token 401 | 请求发出时的 sessionGeneration 等于当前代次、且 tokenVersion 小于当前版本：直接用新 token 重放，不再刷新 |
| 账户切换后，旧会话发出的请求才收到 401 | 请求发出时的 sessionGeneration 不等于当前代次：不刷新、不重放、不标记当前会话失效，返回 `SessionChangedError` |
| 等待刷新期间请求被取消 | 该请求以 `AbortError` 结束、不重放；共享刷新不因此取消，其他等待者继续 |
| body 不可重复读取（ReadableStream）或 `replayable === false` | 不自动重放，返回原 401 对应的 `UnauthorizedError` |
| 非幂等写（POST/PATCH/DELETE）且没有 `idempotencyKey` | 不自动重放，返回 `UnauthorizedError` |
| 刷新期间发生登出或账户切换 | `setTokens` 按发起时的 sessionGeneration 写入，失败即丢弃结果；等待者收到 `SessionChangedError`，不重放 |

不变量：
- 每个请求记录发出时的 sessionGeneration；刷新、标记会话失效、重放之前都要核对代次，旧会话的失败或迟到响应不能影响新会话，也不能用新会话的凭据重放旧请求；
- refresh 请求不经过 401 拦截；
- 新 token 写入前必须核对会话代次；
- 单个请求取消不影响共享刷新；
- 所有错误路径都让等待者结束，不留下永不 resolve 的 promise；
- `refreshInFlight` 在成功与失败后都被清理。

## Steps
1. 读取 `src/api/client.ts`、`src/auth/store.ts`、`src/auth/refresh.ts`，确认 Repository facts 中的签名全部存在；缺任何一个就停止，报告“规划缺口”，不要自行设计替代接口。
2. 新建 `src/api/refresh-coordinator.ts`：导出 `createRefreshCoordinator(deps)`，内部维护 `refreshInFlight`，按 Behavior contract 处理成功、`RefreshUnauthorizedError`、`RefreshTransientError` 与代次失效。
3. 修改 `src/api/client.ts`：记录请求发出时的 tokenVersion；401 时按上表判断是否可重放；`retryCount` 最大为 1；refresh 请求不走拦截。
4. 新建 `src/api/client.refresh.test.ts`：用 fake fetch 与可控 promise 覆盖 A01–A12，用例名以验收 ID 开头；并发、迟到与会话切换场景用手动 resolve 控制时序，不用真实定时等待。
5. 运行 V01–V03，记录结果；写执行报告。

## Validation commands
- V01（必要）：`pnpm exec vitest run src/api/client.refresh.test.ts` · 超时：300s · 期望退出码：0 · 输出须匹配 `Tests\s+(1[2-9]|[2-9]\d|\d{3,}) passed`（A01–A12 至少 12 个用例）
- V02（必要）：`pnpm exec vitest run src/api` · 超时：600s · 期望退出码：0 · 既有 client 测试保持通过
- V03（必要）：`pnpm exec tsc --noEmit -p tsconfig.json` · 超时：300s · 期望退出码：0

验收矩阵（V01 中用例名须以这些 ID 开头）：

| ID | 场景 | 必须观察到 |
|---|---|---|
| A01 | 没有 401 | 不调用 refresh |
| A02 | 401 → 刷新成功 → 重放成功 | 原请求最多发出两次，第二次带新 token |
| A03 | refresh 本身 401 | 不递归；会话标记失效；等待者收到 SessionExpiredError |
| A04 | 刷新网络失败 | 等待者都收到 RefreshTransientError；下一次请求可以再次刷新 |
| A05 | 多个旧 token 请求同时 401 | refreshTokens 只调用一次 |
| A06 | 刷新完成后另一个旧请求才返回 401 | 直接用新 token 重放，refresh 调用次数不变 |
| A07 | 重放再次 401 | 没有第三次原请求，也没有第二次刷新 |
| A08 | 等待刷新时请求取消 | 该请求 AbortError 且不重放；其他等待者正常完成 |
| A09 | 刷新中登出或切换账户 | 旧结果不写入新会话；等待者收到 SessionChangedError |
| A10 | 不可重放的 body，或没有幂等键的 POST | 不静默重复发送，返回 UnauthorizedError |
| A11 | 账户切换后，旧会话发起的刷新才返回 401 | 新会话不被标记失效；旧会话的等待者收到 SessionChangedError |
| A12 | 账户切换后，旧会话发出的请求才收到 401 | 不刷新、不用新会话凭据重放；返回 SessionChangedError |

## Definition of done
- D01：A01–A12 全部通过；证据：V01。
- D02：既有 API 客户端测试不回归；证据：V02。
- D03：类型检查通过，`request` 签名不变；证据：V03。
- D04：所有修改都在允许集合内，store 与 refresh 模块未被修改；证据：scope。
- D05：并发与取消路径没有泄漏的 promise、没有吞掉的错误，测试断言调用次数而不只是结果；证据：review。

## Stop conditions
- Repository facts 中的任何接口不存在或语义不同（这是规划缺口）。
- 需要修改 `src/auth/store.ts`、`src/auth/refresh.ts` 或其他禁止路径才能完成。
- 发现上表没有覆盖、且会影响会话安全的情况（例如服务端返回新的错误码语义）。
- 需要新增依赖或修改测试配置。
- 达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 3600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计

## Report back
- 最后一条消息是执行报告：逐项说明 D01–D05，并逐条列出 A01–A12 对应的用例名与自检结果，末尾附执行说明规定的 JSON 代码块。
- 如在第 1 步停止，写清缺少的接口与建议的规划决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试；并发用例不用 sleep 碰运气。
- 不提交、推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
