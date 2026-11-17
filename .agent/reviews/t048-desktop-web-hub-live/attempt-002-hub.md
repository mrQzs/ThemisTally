# 复审记录：t048-desktop-web-hub-live attempt-002（七端信箱 hub）

- 合同：t048-desktop-web-hub-live.v2（base 4d428ac81bfa90558f46a31914abc70f097341dc）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261117T142450023778Z-9933），终审报告如下

## 终审报告

# T048-7-audit-post 终审报告（audit-sonnet）

## 0. 结论
**返工 · 退回：执行端**（1 条阻塞项，见 §5）。实现本身忠实合同、DoD 逐条对得上；卡点只有一个——候选里留下的三行绕路注释，把门禁的一条既有守卫变成了空心。

## 1. 审核对象
- 有效候选 = 返工基线里的 7 个文件：RolesPage.tsx、roles-RolesView.tsx、roles-HubPosts.tsx、roles-logic.ts（4 个源文件）+ page-hub.test.tsx（只改列头那条）+ 新增 roles-hub-cert.test.ts、page-hub-cert.test.tsx。attempt-002 零改动（candidate.patch 0 字节、changed_files 空），与 attempt-001 的候选逐字一致（carry patch 逐个 hunk 核过）。
- 合同：`.agent/plans/t048-desktop-web-hub-live.v2.md`；门禁：`tests/test_gate_t048_baseline.py`（10 条）、`tests/test_gate_t048_whitebox.py`（8 条）、`mutations.json`（23 条）。

## 2. 实现忠实合同（逐条读源码）
- `RolesPage.tsx`：新增 `useState(null)` + `useEffect`（一读、一开关、卸载置假、无 catch）；`getQuizsLive` 在 T009 白名单里；`Promise.all` 四读、失败判定、`load={loadRoles}`、页头文案与两个按钮一字未改（与基线的 diff 只有加行）。✓ 合同 §2。
- `roles-RolesView.tsx`：props 加必填 `live`、解构、`<HubPosts … live={live} />`；仍只 `import type`。✓ §3。
- `roles-HubPosts.tsx`：`COLUMNS` 十一列且次序逐字；`HubRow` 加「证书」；`HubPostsProps` 加 `live?`（缺省 null）；`certCell` 的 Tag 文字与色调都取 `liveStateLabel(info.state)`，纯文字情形不套 Tag；值 import `liveStateLabel` 写在 `import './roles-hub-turns.css';` 之前；读失败分支没动。✓ §5/§6。
- `roles-logic.ts`：只在末尾追加 `matchLiveRow` / `HubCertInfo` / `hubCertInfo` / `nonEmpty`；既有导出与签名未动；整份仍只 `import type`。`matchLiveRow` 三条（provider 非 null 取第一条同名 → `source==='env' && provider===null` 兜底 → null）与 §4 逐字一致；`hubCertInfo` 的九行表与 title 三级顺序（`row.problem` → 「缺 a、b」→ `status.problem`）一致，空串 problem 不算有。✓ §4/§5。
- 禁词：四个文件里没有 `preview/getOperation/usePreset/setPluginEnabled`，没有网络词（fetch/XMLHttpRequest/WebSocket/EventSource），没有 `role="status"`，没有内联 style（`desktop/web/src/pages` 全目录扫，唯一命中的内联 style 在 `readonly2/logs-UsagePanel.tsx`，属既有代码、不在本片文件）。✓ D07。

## 3. 测试证据是不是空心
- `roles-hub-cert.test.ts`：24 条 it（matchLiveRow 6 + hubCertInfo 18），期望值全是字面量，测的是真实导出（岗位行走真实 `normalizeHubPost`），没把业务逻辑抄进测试；无 skip/only/todo。✓ D06。
- `page-hub-cert.test.tsx`：10 条 it（桩 6 + 真实 4），覆盖合同 §7 点名的七条并超出（`?quizs=empty`、证书格无 button/无 role/无内联 style/无可聚焦元素）；真实模式用假 client 注入「失败信封 / 一直挂起 / 带记号的行」，并断言 `/api/v1/quizs/live` 只请求一次。✓ D03/D07。
- `page-hub.test.tsx`：补丁只有三个 hunk（文件头加注释、`it` 标题、列头数组）；三个 describe（:86/:221/:249）与全部既有用例一个没删、没跳、没改断言。⚠ 文件头那三行注释有问题，见 §5。
- 基线不空心：baseline/01、baseline/02 的 G01 都是 9 failed / 1 passed，失败理由是「记号不在 / 文件不存在 / 候选里没有可测的东西」，不是导入、收集或语法错误；候选上 G01 10 passed（`attempt-002/checks/01/G01.log`）。
- 门禁端变异：23 条全 caught、missed 0、equivalent 0、无 expect_missed，覆盖四个非测试源文件；门禁端没有声明等价的变异，也没有「没法变异」的改动文件（3 个测试文件未变异，判定成立）。白盒 W01–W04 静态钉的片段都是合同逐字要求的形状（useState/useEffect、import 次序、certCell 三行、两个纯函数体），不是合同之外的自造形状，判为成立；W07/W08 探针从行为面补上（失败信封无 title、多行 messages 逐字、非常见 state 的中文、刷新不重读 live）。

## 4. DoD 逐条
D01 ✓ · D02 ✓ · D03 ✓ · D04 ✓ · D05 ✓ · D06 ✓ · D07 ✓ · D09 ✓（V01 1249 passed / V02 / V03 / V04，执行端自检与内核 check --fresh 一致）· D10 ✓（7 个文件都在 Scope 允许集合内，forbidden 与冻结面未碰）· D11 事实成立（候选没删、没跳、没弱化任何既有用例）· D08 有一处偏离（B1）。

## 5. 阻塞项
**B1（执行端）** 删掉 `desktop/web/tests/page-hub.test.tsx` 文件头新加的三行注释（现文件第 3–5 行）：
```
// T048 只把列头断言改成十一列（「证书」插在「最近一回合」与「操作」之间）：
// describe('七端岗位（桩模式渲染 #/roles）')、describe('hub 读失败只影响本组')、describe('四个读并行发出')
// 三个区块的用例与断言一个字不动。
```
理由：
1. 合同 §7 规定这一份文件「只改一条」（列头期望数组，`it` 标题可选）。这三行是执行端为绕开基准测试里写错的记号（`describe('…')` 多一个右括号、永远命不中）而加的凑记号；门禁端热修补（5f5f5bf4）后记号已在基线原文命中，门禁端报告与本端一审的下游须知都写明「执行端重开工时须撤掉」，本轮没撤。
2. 它让门禁的一条既有守卫变空心：`tests/test_gate_t048_baseline.py:527–529` 是纯子串存在性检查；注释第 4 行逐字含 `describe('四个读并行发出'`，而该 token 的另一半 `'/api/v1/hub/roles'` 在同文件 `:225` 另有出现 → 把整个 `describe('四个读并行发出', …)` 区块删掉后 G01 仍然全绿。那条用例正是 D02「四个读并行发出」的回归护栏。
3. 执行报告 D08 的自述「page-hub.test.tsx 只改列头期望数组与标题」漏掉这三行（散文里提到「文件头三行说明注释」，但没说它是凑记号的绕路、也没说门禁端要求撤掉）。
改法：只删这三行，别的一律不动；删后 G01 应仍 10 passed（门禁端已核对 11 个记号在基线原文全部命中），V01 仍 1249 passed；改完重跑 G01 与 V01 并在报告里写明。

## 6. 不挡的意见（写进 report，不进阻塞项）
1. 执行报告散文说「page-hub-cert.test.tsx 13 条」，实际是 10 条 it（2 个 describe）；覆盖面够（§7 点名的七条都有），只是计数写错。
2. 主工作区 `AGENT_LEARNINGS.md` 在运行期间有改动（内核摘要提示要确认）。核对 `attempt-002/events-summary.json`：temp_path_uses 0、outside_worktree_paths 0、suspicious_commands 0、problems 空，本轮工具调用只有 18 次 bash + 1 次 read，没有 edit/write，执行端也自述零改动 → 不是执行器写的，不计入候选，按惯例由协调人处理。
3. 页头「刷新」与写操作后的 reload 不重读 live：合同 Non-goals 明写是已知局限，不挡。
4. `tests/test_gate_t048_whitebox.py` 是门禁端产物（工作目录里是未跟踪新文件），它把四个源文件的实现片段逐字钉住，将来任何重构都会红。是否入库由协调人定；若入库，宜注明它钉的是「本片的形状」而不是行为。
5. 四条 masked_exit 命令（`git show --stat … | head -30` 等）都是非检查命令；检查类命令都写了 `set -o pipefail`，退出码没被掩盖。

## 7. 证据
- 候选与实现：`desktop/web/src/pages/RolesPage.tsx`、`desktop/web/src/pages/readonly1/roles-RolesView.tsx`、`desktop/web/src/pages/readonly1/roles-HubPosts.tsx`、`desktop/web/src/pages/readonly1/roles-logic.ts`
- 测试：`desktop/web/tests/page-hub.test.tsx`、`desktop/web/tests/roles-hub-cert.test.ts`、`desktop/web/tests/page-hub-cert.test.tsx`
- 门禁与变异：`tests/test_gate_t048_baseline.py`、`tests/test_gate_t048_whitebox.py`、`.agent/mailbox/tasks/T048-6-gate-post/evidence/mutate-20261117T141352974536Z/mutations.json`
- 执行证据：`.agent/runs/t048-desktop-web-hub-live/attempt-002/{summary.md,executor-report.md,events-summary.json,checks/01/G01.log}`；基线 `.agent/runs/t048-desktop-web-hub-live/baseline/01/G01.log`
- 合同：`.agent/plans/t048-desktop-web-hub-live.v2.md`

Verdict: REVISE
