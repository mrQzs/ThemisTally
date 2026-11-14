# TASK: t040-desktop-web-writes-2

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 2326220f6bc4d66fdc36e602d1295e4d5ffe29be
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端 Web 渲染层（`desktop/web`）把写流程收尾到真实模式：`desktop/web/src/writes/useWriteFlow.ts` 的重读只在非真实模式下认 `?write=` 的 reread-fail 情景（真实模式的重读失败只由真的读失败造成），确认框在 `needs_yes` 为真且没有正在运行的 attempt 时说明为什么要你确认（走现有的 notes 一栏，不新增界面元素），`desktop/web/src/api.ts` 与 `desktop/web/src/writes/useLivePreview.ts` 的两处注释改成与真实模式相符的说法，并新增真实模式的流程集成测试（用 `setLiveClientForTests` 注入假服务，覆盖成功、状态已变、过期、繁忙、断线后轮询、超时、服务出错、部分写入与 `useLivePreview` 的回归）。

## Non-goals
- 不加 `hub.set` / `hub.unset` 的分支：`useWriteFlow` 的 `confirm()` 分派链末尾仍兜底到 `setPluginEnabled`（那属 T038 B 片）。
- 不改 `desktop/web/src/live/**`（`mode.ts` 的导出集合被 T027、T034、T036、T037 钉成恰好四个）、不改 `desktop/web/src/mock/**`（22 个 `?write=` 情景值与 `needs_yes` 恒假的演示数据照旧）、不改 `WriteConfirmDialog.tsx`、`writeOutcome.ts`、`snapshots.ts`、`ProfileForm.tsx`、`profileRules.ts`。
- 不改服务端与写路由（`ts/**` 一个字都不动），不改 `desktop/web/src/api.ts` 的任何代码（只动第 246 行那一句注释）。
- 不改任何现有测试文件；本片只新增测试文件。
- 不推翻既有过渡断言：`desktop/web/tests/page-app.test.tsx:91` 与 `desktop/web/tests/readonly2-app.test.tsx:106` 两条写入口过渡用例照旧保留。
- 不改夹具模式（`liveClient()` 为 null）的任何行为：`?write=` 情景一个字都不变。
- 不改服务在 401、503 时先读正文的写法（终审不挡意见 1）。
- 不在确认框之外新增界面元素、类名或说明文字。

## Repository facts
- 入口与现状（基线 94c960f，行号按该提交）：
  - `desktop/web/src/writes/useWriteFlow.ts:122-125` — `readSnapshot(action, isReread)` 在重读时直接认 `writeScenario()` 的 `reread-fail` 与 `reread-fail-exit1`，不看模式。这是真实模式下唯一的演示情景漏口（`src` 里直接调 `writeScenario()` 的只有这里与 `mock/writes.ts` 自己）。
  - `desktop/web/src/writes/useWriteFlow.ts:416-424` — `runPreview` 组 `content` 时只取 `data.binding_changes`、`data.warnings`、`data.running_attempts`、`data.notes`；`data.needs_yes` 没用。
  - `desktop/web/src/writes/useWriteFlow.ts:59-61`、`:280-323` — 轮询：`setInterval` 每 `POLL_INTERVAL_MS`（1000ms）查一次 `getOperation`，累计到 `POLL_LIMIT_MS`（120000ms）判「结果未知」；404 立即判未知；重读走 `readSnapshot(action, true)`。
  - `desktop/web/src/live/mode.ts` — `liveClient()` 优先返回 `setLiveClientForTests` 注入的值，其次才是构建期的缺省客户端；`liveModeIsReal()` 只看构建期常量，**不认测试注入**；导出集合恰好四个（`liveModeIsReal`、`liveClient`、`setLiveClientForTests`、`LiveClient`）。
  - `desktop/web/src/api.ts:236` — `toPreviewData` 把服务的 `unreadable` 接在 `notes` 后面（前端形状里没有单独的 `unreadable` 键）；`:239` — `needs_yes: preview.needs_yes === true`。
  - `desktop/web/src/api.ts:246` — 全文件唯一含「501」的一行：`// 缺任何一样（含 data 缺 preview）就原样透传，不签发确认号、不改写成 501。`（站主采纳的意见 4：把这几个字去掉，将来恢复查 501 的断言时不误伤）。
  - `desktop/web/src/api.ts:497-673` — 真实分支：预览 `POST /api/v1/preview`（正文 `{action, args}`，时限 30 秒）；`getOperation` 走 `GET /api/v1/operations/<encodeURIComponent(id)>`（`getRaw`，时限 30 秒）；十个写函数各走自己的写路由（时限 90 秒），路径参数不重复进正文。读函数（`getRoles` / `getProfiles` / `getPresets` / `getRuntimes` / `getPlugins`）在真实分支只 `client.get`，不做形状映射。
  - `desktop/web/src/writes/writeOutcome.ts:49-77` — `classifyWrite(status, body)`：409 且 `exit_code === 4` → stale；409 其他 → expired；503 → busy；400/401/403/413 → rejected；504 → timeout；500 → serverError；200 且 `ok` → 成功（有 WARN 行则 successWarn）；200 且 `ok:false` → failedExit（退出 1 或 3 → 「内核拒绝」）。`classifyTerminal(op)`：succeeded → 成功；failed 且 reason 为 `exit` → failedExit，否则 serverError；stale → stale；timed_out → timeout。`finalFromReread`：成功类重读不成 → rereadFailed；失败类重读成、快照变了 → partiallyWritten，没变 → failed，重读不成 → unknown。
  - `desktop/web/src/writes/WriteConfirmDialog.tsx:94-111` — 「影响与风险」依次渲染 running（`wf-risk`，每条一句「有 attempt 正在运行：{r}。它不受影响，但这次改动需要你确认。」）、warnings（`wf-risk`）、notes（`wf-note`，原样显示）；相位文案：`stale` → 「配置在你确认之前被改动了，请重新预览」；`expired` → 「确认已失效（过期、已用过或参数不符），请重新预览」；`confirming` → 「连接中断，正在确认结果…」；`unknown` → 「结果未知，请在历史与审计里核对」；`partiallyWritten` → 「已部分写入，结果待核实」；`rereadFailed` → 「命令已成功，但重新读取失败，请刷新」；`failed` → reason 加内核原文。
  - `desktop/web/src/writes/useLivePreview.ts:2` — 注释「只读演示数据，不联网。」在真实模式下已经不对；`:7` — `DEBOUNCE_MS = 300`；`:22-33` — `fromReply`：出错文案取信封的 `messages`，没有 messages 时是「预览失败：服务没有回应」。
  - `desktop/web/src/mock/writes.ts` — `WriteScenario` 共 22 个值（含 `reread-fail`、`reread-fail-exit1`）；`previewData` 各分支的 `needs_yes` 恒为 `false`、`running_attempts` 恒为空数组（夹具模式下确认框不会出现 needs_yes 的原因句）。
  - `desktop/web/src/mock/writes.ts:36-42` — `writeScenario()` 从 `location.hash` 的 `?write=` 取情景，认不出按 `ok`。
  - `desktop/web/src/pages/readonly1/roles-PresetBar.tsx` — `PresetBar({ presets, active, reload })`：选中的方案不是当前方案时 [切换…] 可点，走 `useWriteFlow`；`desktop/web/tests/writes-flow.test.tsx:86-98` 给了夹具模式下驱动它的写法（选 radio → [切换…] → [确认…]）。
  - 内核语义（只读，不改）：`scripts/kit_config.py:1753` — `needs_yes = bool(running or unreadable)`；`scripts/kit_config.py:910-912` 与 `scripts/kit_roles.py:460-461` — 列不出或读不到 attempt 的状态时「不能当作没有在运行的」，因此需要显式确认。
  - `desktop/web/vite.config.ts` — vitest 的 `include` 覆盖 `tests/**/*.test.{ts,tsx}`；`__THEMIS_LIVE_MODE__` 在 vitest 下是 `themis-live-fixture`（所以夹具模式下 `liveModeIsReal()` 为假、`liveClient()` 为 null，除非注入）。
  - `desktop/web/package.json` — `"test": "vitest run"`、`"typecheck": "tsc --noEmit"`、`"build": "tsc --noEmit && vite build"`；锁文件是 `desktop/web/package-lock.json`（npm）。
  - `desktop/web/tsconfig.json` — `include` 只有 `["src", "vite.config.ts"]`：`desktop/web/tests/` 不参与 `tsc --noEmit`，vitest 也不做类型检查。
- 门禁口径（新基线上读到的，执行端必须守住）：
  - `tests/test_gate_t037_baseline.py` S03：api.ts 的 12 个写侧函数仍是 `export function <名>(`、没有 `unwired` 与「写操作尚未接通」、**整个文件（含注释）不许出现 `fetch`/`XMLHttpRequest`/`EventSource`/`WebSocket` 四个整词**；S04：mock 的 22 个情景值保住；S05：两份 live 测试只追加、不许 `skip`/`only`/`todo`；S06：两条写入口过渡用例与 14 份 JSON 夹具照旧。
  - `tests/test_gate_t027_baseline.py` S10：`desktop/web/src/` 下（除 `desktop/web/src/live/`）任何文件都不许出现那四个网络整词（**注释与字符串也算**）。
  - `tests/test_gate_t034_baseline.py` s02：从 `../live/mode` 只许引 `liveClient` 或 `type LiveClient`；s13：`mode.ts` 的导出集合恰好四个；s12 的源码守卫扫描只覆盖它自己那几个文件。
  - `tests/test_gate_t023_baseline.py` S03：`useWriteFlow` 仍认四个 B 片 action、`WriteSpec.title` 仍可选；`tests/test_gate_t024_baseline.py` S14：`useLivePreview.ts` 里含「300」。
  - 站主已退役的断言（提交 5825e71，含在基线里）：T027 s32、T027 s06 里查「写操作尚未接通」与 `\b501\b` 的两行、T027 s01c 的「写操作尚未接通」记号、T032 s09 的两项。**本片不要求任何退役，也不推翻任何既有断言。**
- 仓库外事实（已核实，只用来定测试写法，不作产品行为断言）：
  - `desktop/web/node_modules/@testing-library/react`（16.1.0）导出 `renderHook`（`types/index.d.ts:234`、`dist/pure.js:42`）。
  - `desktop/web/node_modules/vitest`（2.1.8）有 `vi.advanceTimersByTimeAsync` 与 `vi.setConfig`（`dist/index.d.ts:284`、`:556`）。

## Scope
- allowed_modified_files:
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/api.ts
- allowed_new_files:
  - desktop/web/tests/writes-live-flow.test.tsx
  - desktop/web/tests/writes-live-preview.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t040_*.py
  - desktop/web/src/live/**
  - desktop/web/src/mock/**
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/writeOutcome.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/profileRules.ts
  - desktop/web/src/writes/write-flow.css
  - desktop/web/src/writes/profile-form.css
  - desktop/web/src/pages/**
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/shellpages/**
  - desktop/web/src/App.tsx
  - desktop/web/tests/writes-flow.test.tsx
  - desktop/web/tests/writes-dialog.test.tsx
  - desktop/web/tests/writes-outcome.test.ts
  - desktop/web/tests/writes-remove.test.tsx
  - desktop/web/tests/writes-rollback.test.tsx
  - desktop/web/tests/writes-profile-api.test.ts
  - desktop/web/tests/writes-profile-form.test.tsx
  - desktop/web/tests/writes-snapshots.test.ts
  - desktop/web/tests/writes-snapshots-b.test.ts
  - desktop/web/tests/live-api.test.ts
  - desktop/web/tests/live-transport.test.ts
  - desktop/web/tests/live-mode.test.ts
  - desktop/web/tests/live-readers.test.ts
  - desktop/web/tests/live-connection.test.ts
  - desktop/web/tests/live-events.test.ts
  - desktop/web/tests/live-events-hook.test.tsx
  - desktop/web/tests/live-app.test.tsx
  - desktop/web/tests/live-pages-live.test.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/shell-no-network.test.ts
  - desktop/web/vite.config.ts
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/tsconfig.json
  - desktop/web/scripts/**
  - ts/**
  - docs/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 补充规则（写在范围里，路径同上）：`desktop/web/tests/` 下除上面两个新增文件以外的一切文件一个都不许修改或删除；不新增第三个测试文件。

## Behavior contract
- 正常输入：
  - **真实模式门（`desktop/web/src/writes/useWriteFlow.ts`）**
    - 判据用 `liveClient()`：`import { liveClient } from '../live/mode';`（只引这一个符号，与 `desktop/web/src/shell/useShellConnection.ts` 的写法一致），**不用 `liveModeIsReal()`**——后者不认测试注入，且 `desktop/web/src/api.ts` 走桩分支也是以 `liveClient()` 为空为准。
    - `readSnapshot(action, isReread)` 里的重读演示情景（`reread-fail`、`reread-fail-exit1`）**只在 `liveClient() === null`（非真实模式）时认**；真实模式下这两个情景一律不认。
    - 真实模式下重读失败只由真的读失败造成：读函数 reject，或读回来的信封 `ok` 为假、`data` 为空。
    - 夹具模式（`liveClient()` 为 null）的一切行为一字不变：`?write=reread-fail` 与 `?write=reread-fail-exit1` 仍按演示数据失败。
    - 注释要写明判据与理由（为什么用 `liveClient()` 而不是 `liveModeIsReal()`）；注释里不许出现四个网络整词。
  - **needs_yes 的原因（同一文件，`runPreview` 组 `content` 的地方）**
    - 触发条件：`data.needs_yes === true` **且** `data.running_attempts.length === 0`。
    - 触发时在 `notes` 最前面加一句**逐字固定**的文字：
      `有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。`
    - 这句话排在 `data.notes` 的最前面（`api.ts` 已把服务的 `unreadable` 并进 `notes`，所以这句在那些原样的路径行之前）。
    - `running_attempts` 非空时**不加**这句（running 那一行本来就写着「这次改动需要你确认」，不重复）。
    - `needs_yes` 为假时**不加**这句。
    - 走现有的 `notes` 一栏（渲染成 `wf-note` 的段落）：不新增界面元素、不新增类名、不改 `WriteConfirmDialog.tsx`。
    - 夹具模式下 `needs_yes` 恒为假，所以这句在夹具模式里永远不出现（既有测试不受影响）。
  - **`desktop/web/src/api.ts` 的注释（只动第 246 行这一句）**
    - 改成：`// 缺任何一样（含 data 缺 preview）就原样透传：不签发确认号，状态码与信封都不改。`
    - **去注释后 `api.ts` 逐字不变**（代码、导出、类型、夹具分支一律不动）。
    - 改完后 `desktop/web/src/api.ts` 里不再出现「501」这三个字符；也不出现四个网络整词。
  - **`desktop/web/src/writes/useLivePreview.ts` 的注释（只动第 2 行这一句）**
    - 改成：`// 夹具模式下读演示数据，真实模式下走服务的预览。`
    - `DEBOUNCE_MS = 300` 与其余代码一字不改（文件里仍含「300」，T024 S14 依赖它）。
  - **新测试（`desktop/web/tests/writes-live-flow.test.tsx`；`desktop/web/tests/writes-live-preview.test.tsx`）**
    - 手段：只用 `setLiveClientForTests` 注入假客户端（`desktop/web/src/live/mode.ts`）；**不许 `vi.mock` `../src/api`、`../src/writes/useWriteFlow`、`../src/live/mode`**——测的就是真实现。
    - 假客户端实现 `get`、`post`、`getRaw` 三个方法，记录每次调用的路径、正文与时限，并能按路径编排返回值（兑现 / reject / 挂起 / 按次序轮换）。
    - 夹具（`beforeEach`）：`setLiveClientForTests(fake)`、`vi.useFakeTimers()`、`window.location.hash = ''`；`afterEach`：`cleanup()`、`setLiveClientForTests(undefined)`、`vi.useRealTimers()`、清空 hash。
    - 驱动方式照 `desktop/web/tests/writes-flow.test.tsx:54-98` 的写法（`settle`、`advance` 用 `vi.advanceTimersByTimeAsync`、选 radio → [切换…] → [确认…]），不靠固定等待。
    - 假服务要给的读数据：`/api/v1/presets` 与 `/api/v1/roles` 返回 `desktop/web/src/mock/presets.json`、`roles.json` 的形状（真实分支的读函数不做映射，直接把信封的 `data` 当成 `PresetsData` / `RolesData` 用）；要表达「快照变了」就让执行后的读返回与执行前不同的内容，要表达「重读失败」就让读 reject 或回 `ok:false`。
    - 必测情形与期望（文案逐字照 `WriteConfirmDialog.tsx` 与 `writeOutcome.ts`）：

      | 用例 | 假服务编排 | 期望 |
      |---|---|---|
      | 成功（W3） | 预览 200（`data.preview` + `data.confirmation`，信封顶层带 `command`）；执行 200 `ok:true`；重读先挂起后兑现 | 预览发 `POST /api/v1/preview`，正文 `{action:'preset.use', args:{name:'economy'}}`；框里「将运行的命令」去掉 `--dry-run` 与 `--json`；确认后发 `POST /api/v1/presets/economy/use`，正文 `{confirmation}`，时限 90 秒；重读挂起时整页没有「已切换」，兑现后才出轻提示「已切换到方案 economy」 |
      | 状态已变 | 执行 409，信封 `exit_code: 4` | 显示「配置在你确认之前被改动了，请重新预览」，有 [重新预览]；**不再重读**（读的调用次数不增） |
      | 过期 | 执行 409，信封 `exit_code: null` | 显示「确认已失效（过期、已用过或参数不符），请重新预览」 |
      | 繁忙 | 执行 503；随后查 `GET /api/v1/operations/<确认号>` 得 404 | 回到可确认状态，显示「服务繁忙，请稍后再确认」 |
      | 断线后轮询 | 执行 reject | 显示「连接中断，正在确认结果…」，[取消] 禁用；推进 1000ms 查一次操作（路径带确认号），先回 running，再推进 1000ms 回 succeeded | 重读后出轻提示「已切换到方案 economy」 |
      | 轮询到 120 秒 | 操作查询一直回 running | 119 秒时仍在「连接中断，正在确认结果…」；120 秒时显示「结果未知，请在历史与审计里核对」，有 [打开历史] |
      | 服务出错 | 执行 500 | 重读后显示失败横幅，原因「服务出错」 |
      | 超时 | 执行 504 | 重读后显示失败横幅，原因「超时」 |
      | 部分写入 | 执行 200 `ok:false`、`exit_code: 1`；重读后快照变了 | 显示「已部分写入，结果待核实」，有 [查看历史] |
      | 内核拒绝 | 执行 200 `ok:false`、`exit_code: 1`；重读后快照没变 | 显示失败横幅，原因「内核拒绝」 |
      | 真实模式门 | `window.location.hash` 带 `?write=reread-fail`；执行 200 `ok:true`；读正常 | 照常重读并出轻提示，**不出现**「重新读取失败」 |
      | 真实模式下的重读失败 | 执行 200 `ok:true`；重读的读 reject 或回 `ok:false` | 显示「命令已成功，但重新读取失败，请刷新」 |
      | needs_yes：有状态读不出来 | 预览的 `preview.needs_yes` 为真、`running_attempts` 为空、`unreadable` 有一条 | 框里有那句逐字的原因句，且它排在原样路径行之前 |
      | needs_yes：正在运行 | 预览的 `preview.needs_yes` 为真、`running_attempts` 非空 | 只有 running 那行（照旧带「这次改动需要你确认」），**不出现**原因句 |
      | needs_yes：否 | 预览的 `preview.needs_yes` 为假 | 不出现原因句 |
    - `desktop/web/tests/writes-live-preview.test.tsx`（`useLivePreview` 在真实模式下的回归，可与流程用例放同一份文件，但文件名要是这两个之一）：
      | 用例 | 编排 | 期望 |
      |---|---|---|
      | 300ms 防抖 | 注入假客户端 | 299ms 时没有预览请求；到 300ms 时恰好发一次 `POST /api/v1/preview`（正文是 `{action, args}`） |
      | 命令去开关 | 预览回 200，data.preview 有内容、信封顶层带 `command` | 返回的命令里没有 `--dry-run` 与 `--json` |
      | 400 错误信封 | 预览回 400，信封 messages 有原文 | 错误行显示 messages 原文 |
      | 没有回应 | 预览 post reject | 错误行是「预览失败：服务没有回应」 |
    - 测试文件里不许出现 `skip` / `only` / `todo`；不许把业务逻辑抄一份进测试（断言打在真实的 `useWriteFlow` / `useLivePreview` 与真实的 `api.ts` 上）。
- 边界输入：
  - 夹具模式（`liveClient()` 为 null）：`?write=` 的 22 个情景一字不变，`desktop/web/tests/writes-flow.test.tsx` 与 T022/T023/T024 的流程探针照旧全绿。
  - 真实模式下 `location.hash` 里带 `?write=`：一律不认（演示情景只在夹具模式有效）。
  - 真实模式下 `needs_yes` 为真且 `running_attempts` 非空：不加原因句（这是已知局限：读不到的那几行仍原样显示，分辨它们要改 `api.ts` 的预览映射，本片不许改）。
  - 服务回 200 但 `ok:false`（内核拒绝）：走 `failedExit`，不重读成功。
  - 服务回 503：走 busy 分支，先查一次操作；查不到（404）才回到可确认。
  - 操作查询 404：直接判「结果未知」。
  - 操作查询 reject：继续轮询到 120 秒判「结果未知」。
  - 预览 400 / 500：状态码与信封原样透传，界面显示「预览失败」加内核原文（这条已有分支，本片不改）。
  - 预览 reject：显示「预览失败：服务没有回应」（已有分支，本片不改）。
  - 真实模式下 `data.command` 缺 `--dry-run` 或 `--json`：照旧按原样过滤（两个开关各滤一次）。
- 错误与重试：
  - 本片不引入任何自动重试；轮询节奏（1000ms、上限 120 秒）、超时判定与「结果未知」的语义一律照 `useWriteFlow.ts` 现状，不改。
  - 传输层（`desktop/web/src/live/transport.ts`）一个字不动：`post` / `getRaw` 拿不到回应时 reject，`get` 永不 reject。
  - 新测试里的假客户端不吞错误：reject 的分支要能被断言到。
- 并发、取消与状态变化：
  - `useWriteFlow` 的既有语义不变：一次流程一个 `flowRef` 序号，旧流程的回应按 `isCurrent` 丢弃；轮询计时器在卸载与流程重置时清掉。
  - 新测试用假计时器推进轮询时，要一次推进一个周期并冲刷微任务（照 `desktop/web/tests/writes-flow.test.tsx` 的 `advance` 写法：`await act(async () => { await vi.advanceTimersByTimeAsync(ms); })`）。
  - `afterEach` 必须 `setLiveClientForTests(undefined)`，否则注入会漏到别的用例文件（每个测试文件独立模块注册表，但同文件内的用例会串）。
- 兼容性：
  - `desktop/web/src/live/mode.ts` 的导出集合仍是四个（不碰这个文件）。
  - `desktop/web/src/api.ts` 的十个写函数、`preview`、`getOperation` 的签名与行为一字不变；`PreviewData`、`OperationView`、`Envelope`、`WriteAction`、`WriteArgs` 的形状不变。
  - `desktop/web/src/writes/useWriteFlow.ts` 对外的形状不变：`useWriteFlow(reload?)` 仍回 `{ start, flow }`；`WriteSpec` 的 `title` 仍可选。
  - 确认框的 DOM 结构、类名与文案一字不改（只多一句 notes 里的段落）。
  - 夹具模式（`liveClient()` 为 null）的返回值与状态码一字不变。

## Steps
1. 读 Repository facts 里列的文件（`desktop/web/src/writes/{useWriteFlow,useLivePreview,writeOutcome,WriteConfirmDialog}.ts(x)`、`desktop/web/src/live/mode.ts`、`desktop/web/src/api.ts`、`desktop/web/src/mock/writes.ts`、`desktop/web/src/pages/readonly1/roles-PresetBar.tsx`、`desktop/web/tests/writes-flow.test.tsx`、`desktop/web/tests/live-app.test.tsx`、`desktop/web/vite.config.ts`、`desktop/web/package.json`），确认签名与行号与基线一致；不一致就停止并报告。
2. 改 `desktop/web/src/writes/useWriteFlow.ts`：
   - 加 `import { liveClient } from '../live/mode';`（只引这一个符号）。
   - `readSnapshot` 的重读演示情景加上 `liveClient() === null` 的前提，注释写明判据与理由。
   - `runPreview` 组 `content` 时按 Behavior contract 的触发条件，在 `notes` 最前面加那句逐字的原因句；不新增界面元素与类名。
   - 其余代码一字不改。
3. 改 `desktop/web/src/api.ts` 第 246 行那一句注释（去注释后逐字不变，文件里不再有「501」）。
4. 改 `desktop/web/src/writes/useLivePreview.ts` 第 2 行那一句注释（`DEBOUNCE_MS = 300` 与其余代码不动）。
5. 新增 `desktop/web/tests/writes-live-flow.test.tsx`：按 Behavior contract 的表实现假客户端与必测情形（成功、状态已变、过期、繁忙、断线后轮询、轮询到 120 秒、服务出错、超时、部分写入、内核拒绝、真实模式门、真实模式下的重读失败、needs_yes 的三种情形）。
6. 新增 `desktop/web/tests/writes-live-preview.test.tsx`（或把预览用例放进上一份文件）：300ms 防抖、命令去开关、400 信封、没有回应。
7. 跑 Validation commands 里的 V01、V02（必要时加跑 G01 的门禁文件），记录命令与结果。
8. 写执行报告：逐项说明 D01…D13，列出自检命令与结果、遗留问题。

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t040_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`$`

## Definition of done
- D01：真实模式下不认 `?write=` 的重读演示情景：`readSnapshot` 的 `reread-fail` 与 `reread-fail-exit1` 只在 `liveClient() === null` 时认；真实模式的重读失败只由真的读失败（reject 或 `ok:false`）造成。证据：V01 中 `writes-live-flow.test.tsx` 的「真实模式门」与「真实模式下的重读失败」两条用例；目的：真实服务上不因为 URL 里的演示参数造出一次假的「重新读取失败」。
- D02：`needs_yes` 为真且没有正在运行的 attempt 时，确认框的 notes 第一行是逐字的那句「有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。」；running 非空时不加；`needs_yes` 为假时不加；不新增界面元素与类名。证据：V01 中 needs_yes 的三条用例、G01；目的：用户看得见为什么这次要他确认（内核的语义是「列不出来就不当作没有在运行」），而不是只看到一串路径。
- D03：`desktop/web/src/api.ts` 只改了第 246 行那一句注释，去注释后逐字不变，文件里不再出现「501」，也不出现四个网络整词。证据：G01、V01；目的：站主采纳的终审意见 4 落地（将来恢复查 501 的断言时不误伤），且不碰 api.ts 的任何行为。
- D04：`desktop/web/src/writes/useLivePreview.ts` 第 2 行的注释改成「夹具模式下读演示数据，真实模式下走服务的预览。」；`DEBOUNCE_MS = 300` 与其余代码一字不变。证据：V01、G01；目的：注释不再说假话，同时保住 T024 S14 依赖的「300」记号。
- D05：新测试只经 `setLiveClientForTests` 注入假客户端，不 `vi.mock` 被测模块；假客户端实现 `get`/`post`/`getRaw` 并记录路径、正文与时限；两份新测试没有 `skip`/`only`/`todo`。证据：V01、scope；目的：测的是真实现，不是把业务逻辑抄一份进测试。
- D06：真实模式下预览发 `POST /api/v1/preview`（正文 `{action, args}`），执行发 `POST /api/v1/presets/economy/use`（正文 `{confirmation}`，时限 90 秒），断线后查 `GET /api/v1/operations/<确认号>`。证据：V01 中「成功」用例的路径与正文断言；目的：写操作真的按服务的路由发出去，且参数与预览时一致。
- D07：成功只在重读之后才说（W3）：重读挂起时整页没有「已切换」，重读兑现后才出轻提示「已切换到方案 economy」。证据：V01 中「成功」用例；目的：界面不提前宣布成功。
- D08：状态已变、过期、繁忙、断线后轮询、轮询到 120 秒、服务出错、超时、部分写入、内核拒绝这九条各有断言，界面文案与按钮照 Behavior contract 的表。证据：V01；目的：真窗口里碰不到的分支（断线、过期、繁忙、部分写入）从此有回归保护。
- D09：真实模式下重读失败（读 reject 或 `ok:false`）显示「命令已成功，但重新读取失败，请刷新」，与 D01 的演示情景分开。证据：V01 中「真实模式下的重读失败」用例；目的：真的失败不会被当成演示失败，两者的处置不同。
- D10：`useLivePreview` 在真实模式下：299ms 不发预览、300ms 恰好发一次；返回的命令去掉 `--dry-run` 与 `--json`；400 信封显示 messages 原文；post reject 显示「预览失败：服务没有回应」。证据：V01 中预览那组用例；目的：表单底部的实时预览在真实服务上也通。
- D11：夹具模式一字不变：`?write=` 的 22 个情景照旧，既有测试文件一个都没改（`desktop/web/tests/writes-flow.test.tsx` 等全绿），两条写入口过渡用例照旧。证据：V01、G01、R01、scope；目的：不推翻既有门禁与过渡断言，也不影响别的片。
- D12：改动都在允许集合内（3 个源文件 + 最多 2 个新测试文件）；禁改清单里的文件一个都没动；没有删除或重命名文件；依赖清单与锁文件没变；`desktop/web/src/` 下（除 `src/live/`）没有四个网络整词。证据：scope、G01；目的：不越权、不惊动 T038 A 片。
- D13：`npm test`、`npm run typecheck`、门禁 G01 与回归 R01 全绿。证据：V01、V02、G01、R01；目的：既有前端行为没被写流程收尾碰坏，既有门禁不被本片推翻。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `useWriteFlow.ts` 的重读情景不在 `:122-125`、`api.ts` 的「501」不在第 246 行、`mode.ts` 的导出集合不是四个、`WriteConfirmDialog.tsx` 的风险区顺序不是 running → warnings → notes）。
- 必须修改允许范围之外的文件才能继续（例如要让 `api.ts` 把 `unreadable` 单独透出、或要给 `hub.set` 加分支）。
- `desktop/web` 的依赖在工作目录里装不上，导致 V01/V02 跑不起来：如实报告（不要联网装依赖、不要改锁文件）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如服务多回一种状态码、或预览 JSON 里出现合同没列的键）。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本；本片此前已用 0 次）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 7200
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与门禁 600s、改 `useWriteFlow.ts` 600s、两处注释 180s、写流程测试 1200s、写预览测试 480s、跑 V01/V02 与门禁 420s、写执行报告 120s；总计 3600s，单轮时限 3600s。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D13，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
