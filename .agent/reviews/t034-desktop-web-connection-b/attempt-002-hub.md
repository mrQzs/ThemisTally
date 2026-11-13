# 复审记录：t034-desktop-web-connection-b attempt-002（七端信箱 hub）

- 合同：t034-desktop-web-connection-b.v3（base 187fd9e73e3d58783c01274670a65aabfa3bca4a）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261113T154235363554Z-5309），终审报告如下

## 终审报告

# T034-7 终审（audit-post）：桌面端前端接真实服务 第 2 片

结论：**通过**。无阻塞项，不退回任何一端（执行端 / 战后门禁 / 门禁端 / 合同端 / 规划端都不退）。
本回合只读：读了候选源码、内核检查与门禁记录、战后门禁的白盒与内核变异记录、合同 v3、执行报告与内核摘要线索；未改任何文件、未跑流水线、未碰主工作区。

---

## 1. 候选是什么（先把对象钉死）

- attempt-002 的 `candidate.patch` = **0 字节**、`changes.json` = `[]`、`scope.json` = `violations: [] / ok: true / head_after: 187fd9e…`、`observations.json` 的 `skip_markers_added: []`、`assertion_lines_added: 0`。→ **执行端本轮零代码改动**，有效候选 = attempt-001 的 9 个文件（内核已把它们随返工基线 `187fd9e` 搬进仓库）。
- 我没有只看补丁文本：**在工作目录里逐个读了 7 个实现文件 + 2 个测试文件**（`useShellConnection.ts`、`App.tsx`、`TitleBar.tsx`、`PageFrame.tsx`、`OverviewPage.tsx`、`ConnectionPill.tsx`、`live/transport.ts`、`tests/live-app.test.tsx`、`tests/live-transport.test.ts`），再与 attempt-001 的 `candidate.patch` 全部 hunk 对照。
- 候选改动面（attempt-001 `changes.json`/`candidate.stat.txt`）：9 个文件（6 改 + 2 增 + 1 改测试），**全部在合同 `allowed_modified_files`/`allowed_new_files` 内**；无 `tests/**`、`ts/**`、`desktop/shell/**`、`scripts/**`、`docs/**`、`schemas/**`、`package.json`、`package-lock.json`、`src/api.ts`、`src/live/mode.ts`、`src/live/connection.ts`、`src/mock/**`、`src/shell/TabBar.tsx`、`src/shellpages/**`、`src/pages/SettingsPage.tsx` 的改动（forbidden_paths 逐条核过）。可选的 `live-shell.test.tsx` 未建（合同允许不建）。

---

## 2. 源码逐条对照合同 v3（§一–§七）

| 合同条款 | 实现落点（工作目录实读） | 判定 |
|---|---|---|
| §一 钩子形状/口径 | `useShellConnection.ts`：`export function useShellConnection(): { live: boolean; state: ConnectionState }`；`const live = liveClient() !== null;`；`const liveState = useConnectionState();`（无条件调）；`return { live, state: live ? liveState : shellConnectionState(currentMock()) };`；`ConnectionState` 从 `../components` 以 type 导入（三取值）；导入白名单逐行合规；`liveModeIsReal`/`setLiveClientForTests` 只出现在注释里（门禁与白盒都按「剥注释后查代码」口径） | 合规 |
| §二 App.tsx | meta 改 state：夹具初值 `getMetaNow()`、真实初值 `PLACEHOLDER_META = { kit_version: '—', repo_name: '—' }`（单个 U+2014）；真实模式 `if (!live) return;` 后 `getMeta()`，**仅** `alive && env.ok && env.data` 才 `setMeta`（失败保持「—」、不清空）；`alive` 卸载守卫；`offline = state === 'disconnected'`；根组件不动（不调 `liveClient()`、不引 live 模块）；去注释后无 `liveClient` 与 T012 禁词 | 合规 |
| §三 TitleBar / ConnectionPill | TitleBar `useShellConnection()`；真实模式 `pid/startedAt/stream` 三行「—」；仓库菜单真实模式只列当前 `repoName`（`checked: true`）一项、「添加仓库…」仍 `disabled: true` + `trailing: '第二阶段接入'`；夹具分支 `SHELL_RECENT_REPOS` + `checked: name === repoName` + `shellStreamText(state)` 与改前逐字同义；`ConnectionPill` 只改 `pid?: number | string;` 一行（逐字、顺序固定），三取值与「未知」兜底未动 | 合规 |
| §四 PageFrame | offline 取钩子；(a) 真实模式「重新连接」是 `Button … onClick={() => request(true)}`，夹具仍是 `DisabledAction label="重新连接" reason="接入本机服务后可用"`；(b) `err.command.length > 0 && err.exit_code !== null` 才渲染「命令（…）返回退出码」，否则只列 messages（与合同「或」口径一致）；(c) `keepStale()` = `live && offline && (phase==='data'\|\|'empty')`，信封失败路径与 Promise 被拒路径**两处**都护住，且保留旧数据/原 phase、**不切 error、不 reportPage('error')**；`exit_code: number \| null`、`actions` 联合类型与 `children(data, reload)` 签名、`data-stale`、「可能已过期」全在 | 合规 |
| §五 OverviewPage | `const { live } = useShellConnection();`；真实模式初值是**单个**「—」（`'—'` 字面量，不是模板拼接），兑现后 `${repo_name} · kit ${kit_version}`；夹具仍是 `${seed.repo_name} · kit ${seed.kit_version}`；`loadOverview`/`isOverviewEmpty` 仍是模块级 `const` 赋值；`const seed = getMetaNow();` 记号保留 | 合规 |
| §六 transport | 新增 `reauthOf(options)`（`options.host !== undefined ? options.host : typeof window === 'undefined' ? null : window.themisHost`），`runReauth()` 里调用；**创建时不再读** `window.themisHost`；三个记号（`window.themisHost`/`options.host`/`typeof window`）都在；两处 `timedOut \|\| (error as Error)?.name === 'AbortError'` 原样未动（计数仍为 2） | 合规 |
| §七 新测试 | `live-app.test.tsx` 12 条：外壳页路由零请求（含「渲染前置 disconnected 仍无横幅、无胶囊」）、meta 占位→兑现、meta 失败保持「—」、总览说明单个「—」→`live-repo · kit 9.9.9`、断线与恢复、[重新连接] 可点重跑 load、断线保留旧数据、四态各一例、夹具照旧；每例后复位（`setConnectionState('connected')`、`setLiveClientForTests(undefined)`、清 hash）；无 `skip/only/todo` | 合规 |

**没有针对探针的特判**：`src/**` 里不出现 `'live-repo'`/`'9.9.9'`/`'demo-repo'`/`'kit 2.12.0'`（这些只在执行端自己的测试文件里）；`src` 里唯一的字面量是合同规定的占位「—」。**没有空的异常处理**：`getMeta()` 走传输层「绝不 reject」的约定，`PageFrame` 的 `.catch` 分支是真实失败路径且带 `keepStale` 守卫。**没有悄悄扩大的范围**：diff 只碰合同点名的 9 个文件。

---

## 3. 内核检查与门禁记录核对

`attempt-002/checks/01/checks.json`：`candidate_tree == tree_before == tree_after`（检查未改候选）、`modified_by_checks: false`、`covers_all_required: true`、`all_required_passed: true`。

| ID | 退出码 | output_must_match | 实跑日志 |
|---|---|---|---|
| G01 | 0 | `\d+ passed` matched | `22 passed in 46.03s`（新门禁文件 blob 1212566） |
| R01 | 0 | matched | `824 passed in 1243.95s` |
| V01 | 0 | `Tests\s+[1-9]\d* passed` matched | `Test Files 105 passed / Tests 990 passed`；`live-transport.test.ts (19 tests)`、`live-app.test.tsx (12 tests)` |
| V02 | 0 | `built in` matched | `✓ built in 1.17s`（含 `tsc --noEmit`） |
| V03 | 0 | `契约检查：通过` matched | `契约检查：通过，无违规。` |

战后门禁：白盒 `tests/test_gate_t034_whitebox.py` **16 passed**（全静态、不依赖流水线夹具）；**内核自己的变异记录**（`mutations.json`）：`counts: {caught: 20, missed: 0, skipped: 0, error: 0}`，20 条每条 `exit_code: 1`（= 被测出来）、`files_left_modified: []`（变异后字节复原）。

---

## 4. 门禁端声明的变异逐条裁定（是不是真的测得出来）

| # | 变异 | 抓住它的用例 | 是不是真测得出 | 结论 |
|---|---|---|---|---|
| M01 | hook `!==` 改 `===` | w01 | 判据反了 → live 取反 → 真实模式被当夹具，w01 的整体断言失配 | 真测得出 |
| M02 | 钩子丢掉 liveState 分支 | w01 | state 恒为夹具值 → w01 整体断言失配 | 真测得出 |
| M03 | 删 `useConnectionState` 导入行 | w01 | 导入白名单逐行计数（缺一行即红） | 真测得出 |
| M04 | App 初值恒为 getMetaNow | w02 | state 初值整行不匹配 | 真测得出 |
| M05 | meta 守卫反转（夹具也调 getMeta） | w03 | `if (!live) return;` 计数变 0 | 真测得出 |
| M06 | offline 恒 false | w04 | 判定整行不匹配 | 真测得出 |
| M07 | 删 `getMeta` 导入绑定 | w04 | api 导入整行不匹配 | 真测得出 |
| M08 | TitleBar pid 恒夹具 | transitional_w08 | pid 行不匹配 | 真测得出 |
| M09 | TitleBar stream 恒夹具（「已订阅」假话） | transitional_w08 | stream 行不匹配 | 真测得出 |
| M10 | 真实模式 radio 不 checked | w06 | radio 整行不匹配 | 真测得出 |
| M11 | PageFrame 钩子换成常量 | w07 | 钩子调用行不匹配 | 真测得出 |
| M12 | keepStale 去掉 live 前提 | w09 | keepStale 整块不匹配 | 真测得出 |
| M13 | 两处 keepStale 调用改 if(false) | w09 | `if (keepStale()) {` 计数由 2 变 0（count=2 锚点） | 真测得出 |
| M14 | 信封条件 `&&` 改 `||` | w10 | 条件整行不匹配 | 真测得出 |
| M15 | [重新连接] onClick 改空函数 | w11 | Button 开标签整行不匹配 | 真测得出 |
| M16 | 说明拼成「— · kit —」 | w12 | 初值整行不匹配 | 真测得出（这条正是合同点名的反例） |
| M17 | OverviewPage 钩子被换掉 | w13 | 钩子行不匹配 | 真测得出 |
| M18 | pid 类型顺序写反 | w14 | `pid?: number \| string;` 逐字不匹配 | 真测得出 |
| M19 | reauth 只认 options.host | w15 | `reauthOf` 整体不匹配 | 真测得出 |
| M20 | 丢掉 window.themisHost 兜底 | w15 | 整块 + `window.themisHost` 计数变 0 | 真测得出 |

覆盖核对：执行端 7 个非测试实现文件**每个至少一条**变异（App 4、钩子 3、TitleBar 3、PageFrame 5、Overview 2、Pill 1、transport 2）→ **没有「没法变异所以不用测」的改动文件**。变异不止改取值：M03/M07 删 import、M11/M17 换掉钩子调用、M13 拆掉两处判定调用、M19/M20 改宿主接口取法——都打在「接线」上。清单里无 insertion-only、无 equivalent、无 expect_missed。

---

## 5. 执行报告自述 ↔ 内核摘要线索对账

内核摘要给出的三类线索，逐条对上了：

1. **临时路径**：新增被忽略路径 `.pytest_cache/**`、`desktop/web/dist/`、`ts/**/node_modules/**` —— 全是 Git 忽略的构建/依赖产物；`candidate.patch` 为空、`scope.violations=[]` → **不在候选里**，不构成范围扩大。
2. **可疑命令**：2 条检查的退出码被管道掩盖（`python -m pytest … | tail -n 45`）→ 执行器自报的退出码是推断值；**内核 checks.json 里的 exit_code 是实跑值**，5 条全 0 且 `output_must_match` 全 matched → 以内核记录为准，不退回。
3. **解读登记**：内核摘要记「执行器自行宣布了 2 处解读（`changed_files` 口径：既然本轮无改动，就把候选文件当改动面）」，而执行报告 JSON 里 `interpretations: []`（自述「本轮未新增实现决策」）→ **报告登记不完整**（见 §6.2）。但报告正文/JSON 的 `changed_files` 9 个文件 = 实际候选文件，口径本身不错，也没有据此做出错误的 DoD 自述（D01–D12 的证据与内核记录一致）→ **不挡**。

执行报告的 DoD 自述逐条与内核记录对得上：D10 的「G01/R01/V01/V02/V03 全绿」= 内核实跑值；D11 的「改动在允许集合内、无 skip/only/todo、live-transport 只追加」= `changes.json` + `candidate.patch` 的追加 hunk + 白盒 w16；D08 的「18→19 条」= V01 日志 `live-transport.test.ts (19 tests)`；D12 的「未推翻任何过渡断言、T027 s31 照旧成立」= R01 824 passed 全绿。

---

## 6. 不挡的意见（进 report，不进阻塞项）

1. **合同 §1 的括号与 `src/live/mode.ts` 的实际语义不一致（合同端，下版顺手改）**：合同写「注入 `null` 表示明确不发请求，**也算真实模式**」，但 `live/mode.ts` 的 `liveClient()` 在 `injected === null` 时**返回 null** → `live = liveClient() !== null` 得 false → 走的是**夹具**分支（既有 `tests/live-mode.test.ts:38-41` 就钉着「`setLiveClientForTests(null)` → `liveClient()` 是 null」）。实现采用的判据与门禁 s02、白盒 w01（`const live = liveClient() !== null;`）逐字一致，生产构建不注入 → **无产品影响**，只是合同文字自相矛盾。
2. **执行报告的 `interpretations` 未登记**：内核摘要记 2 条解读、报告写「无」。属报告登记不完整（不是 DoD 自述不实），不影响结论。
3. **连接状态初值是 `'connected'`（`src/live/connection.ts`，T027 定的、本片不可改）**：真实模式首帧在第一个响应回来之前，胶囊就显示「已连接」。本片 Non-goals 明确不做 `reconnecting` 状态 → 不挡；但 SSE/事件流片宜另立口径。
4. **真实模式下 `getMeta()` 会发两次**：App 挂载时取一次（标题栏/TabBar），`OverviewPage` 自己又取一次（说明）。这是 §5 保留的既有写法，不是本片新增 → 观察项；若要收敛只需动 `OverviewPage`。
5. **白盒文件逐字钉源码文本**（含缩进），后续片改这 7 个文件必然红 → 门禁端已登记为预期护栏；合并时注意它会随基线进仓，下一片的合同/门禁要同步改。
6. **合同 v3 头注释仍写「本版是 v2」「v2 相对 v1 的唯一实质改动」**，与 `plan_version: 3` 不符（一审已提、v3 未改）→ 顺手改。
7. **执行端自己的 `live-app.test.tsx`**：夹具那条用例名写「也不调 getMeta」，但没直接断言 getMeta 的调用次数（靠 T012 探针与 `calls` 数组间接覆盖）→ 用例名略超实。

---

## 7. DoD 自述核对（实现落点 → 证据）

| DoD | 实现落点 | 证据 | 判定 |
|---|---|---|---|
| D01 连接状态接进界面 | App/TitleBar/PageFrame 均取钩子 state；传输层成功/失败上报 | PROBE_STATES 离线例、PROBE_FRAME 真实例、s03/s04、w04/w07 | 覆盖（TabBar 自身指示仍只有 token 级覆盖，见一审遗留） |
| D02 钩子形状与口径 | 见 §一 钩子行 | s02、PROBE_HOOK、w01、M01–M03 | 覆盖 |
| D03 meta 异步 | `PLACEHOLDER_META` + 成功才填；说明初值单个「—」 | s04/s08、PROBE_APP、PROBE_STATES、w02/w03/w12、M04/M05/M16 | 覆盖 |
| D04 夹具模式零变化 | App 夹具短路；夹具分支逐字未变 | T012 探针（R01 内）、PROBE_APP 夹具例、PROBE_FRAME 夹具两例、M04/M05 | 覆盖 |
| D05 标题栏真实模式不显示夹具值 | 三行「—」、只列当前仓库、`pid?: number \| string` | s05/s06、PROBE_SHELL、transitional_w08、w05/w06/w14、M08–M10/M18 | 覆盖 |
| D06 四态与断线保旧 | PageFrame 四态、合成信封、断线保旧、可点重连 | PROBE_STATES、PROBE_FRAME、w09–w11、M11–M15 | 覆盖 |
| D07 外壳页零请求 | 根组件不挂 ServiceApp | PROBE_APP 外壳页例、执行端 live-app 首例 | 覆盖 |
| D08 宿主接口调用时取 | `reauthOf` 调用时取 | s09/s10、PROBE_TRANSPORT 3 条、w15、M19/M20、追加的第 19 条用例 | 覆盖 |
| D09 静态守卫 | 无网络整词/`role=status`/禁调/颜色；App 去注释无 `liveClient` | s12 + R01 的 T006 d08/d14、T012 | 覆盖 |
| D10 门禁与回归全绿 | — | 内核 G01/R01/V01/V02/V03 全绿 + scope | 覆盖 |
| D11 范围与卫生 | 9 文件全在允许集合；无 skip/only/todo；无临时文件进候选 | scope.json、changes.json、w16、V01 日志 | 覆盖 |
| D12 推翻清单为零 | 未退役任何断言；T027 s31 照旧 | R01 全绿、门禁里无退役 | 覆盖（「未退役」这一条为人工审阅，我核了门禁与白盒里没有对本片断言的退役改动） |

---

## 8. 结论

终审：**通过**。实现忠实于合同 v3；内核五条检查与门禁记录自洽；战后门禁的白盒与变异清单覆盖全部 7 个实现文件且 20 条变异都被真的测出来；没有硬编码探针值、没有空心异常处理、没有范围扩大、没有削弱既有测试。**无阻塞项，不退回任何一端。**

Verdict: PASS
