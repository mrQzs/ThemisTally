# 复审记录：t051-desktop-web-role-bind attempt-002（七端信箱 hub）

- 合同：t051-desktop-web-role-bind.v2（base 2990c293fca3e7454408059f90a769ec1e6d4be0）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261118T060615212567Z-4df8），终审报告如下

## 终审报告

# T051-7-audit-post 报告（终审 · attempt-002 · 候选 t051-desktop-web-role-bind.v2.a002）

audit-sonnet · 2026-11-18（UTC）· 只读复核 · 工作目录 ThemisTally-hub-t051-post-attempt-002

## 1. 结论

**结论: 通过（不退回）。** 候选补丁忠实于合同 v2 的「写法钉死」与 Behavior contract；六处旧断言与 t047/t048 三行冻结删除逐字符合合同 Steps 第 10、11 步；没有越界改文件、没有删/跳过/弱化既有断言、没有为过测试写的特判、没有空的异常处理；内核五条必要检查独立全过；战后门禁 39 条变异全被抓住，门禁端「候选缺陷」一节为空（无可裁定项）。没有阻塞项。

## 2. 本回合材料与做法

材料：合同 v2（.agent/plans/t051-desktop-web-role-bind.v2.md，428 行）、候选补丁（attempt-002/candidate.patch，1295 行）、执行概述与执行报告（attempt-002/summary.md、executor-report.md）、内核检查记录（attempt-002/checks/01/checks.json 与 G01.log）、内核基线跑（baseline/01 的 V01/R01/G01 日志）、战后门禁报告与证据（T051-6-gate-post/report.md、mutations.json、whitebox .py）、执行报告的 JEV 判断（6j-jev：no_opinion auth_failed）、一审报告（T051-4-audit-pre/report.md）、工作树里候选的实际文件内容。

做法：只用只读工具（read / grep / find / ls）。没有 shell、没有跑 pytest 与 npm、没有改任何文件。

## 3. 实现忠实于合同（逐文件核对）

| 合同条款 | 候选实际 | 判定 |
|---|---|---|
| 写法钉死 1：`WriteAction` 加 `| 'role.set'`；既有 12 个成员一个不丢 | api.ts:77 前 12 个成员逐字在位，`:77` 之后新加一行 `  | 'role.set';` | 合 |
| 写法钉死 1：`writeArgs` 数字规则扩成 `key === 'number' \|\| key === 'cadence_seconds'` | api.ts:317 逐字一致 | 合 |
| 写法钉死 1：`setRoleBinding(args, confirmation)` 签名、`/api/v1/roles/${encodeURIComponent(args.role)}`、正文 `{ ...writeArgs(w), confirmation }`、桩调 `mockSetRoleBinding` | api.ts:878-892 逐字一致；正文只由 target + 给了才有的 host / cadence_seconds + confirmation 组成 | 合 |
| 写法钉死 2：mock 四处（baseArgv / NEW_ACTIONS / previewData / mockSetRoleBinding）；`WriteScenario` 一个不加 | writes.ts:81-86（argv 逐字，含 `--host=` 与 `--cadence-seconds=` 旗标）、:129（NEW_ACTIONS 加 'role.set'，由 9 变 10）、:280-301（binding_changes 至多一项、from 取夹具显示值、两者相同不给、resources ['roles']、hub_changes []、running_turns []）、:590-598（走 confirmWrite('role.set')）；情景枚举未动（t044 S07 27 个） | 合 |
| 写法钉死 3：`LivePreview` 只加 `bindingChanges`；失败分支字面量补 `bindingChanges: []`；开头两行注释与 DEBOUNCE_MS 不动 | useLivePreview.ts:26、:39、:70；文件头两行注释与 `const DEBOUNCE_MS = 300;` 未动 | 合 |
| 写法钉死 4：RoleBindForm 从 ../api 只 import type、原因句逐字、标题 `改绑定：${roleLabel}`、两个 Select 的 label、按钮「更改…」secondary/sm、`import './hub-bind-form.css';` 放在组件 import 之后、不跨层引 src/pages | RoleBindForm.tsx:8 `import type { BindingChange, WriteArgs } from '../api';`；:13 原因句逐字（与 HubBindForm 那句不同）；:132 标题；:136/:144 两个 Select；:163 按钮；:10 CSS import 位置正确；全文件不引 src/pages；无内联 style、无 role="status"、无网络词 | 合 |
| 写法钉死 5：`allowedModes` / `profileIds` / `RoleInfo.cadenceSeconds`；只 import type | roles-logic.ts:27-45（ROLE_MODES 次序照 kit_roles）、:37（allowedModes，未知给 []）、:42（profileIds 按输入顺序滤 `_` 开头）、:82（cadenceSeconds: number \| null）、:110（只有整数才给数）；文件仍只 `import type` | 合 |
| 写法钉死 6：卡底换成 `<RoleBindAction … />`；新 props 可选；只读部分不动 | RoleCard.tsx:79-91；props 增 `candidates?` 与 `reload?` 且都可选；卡片其余 hunk 零改动 | 合 |
| 写法钉死 7：RolesView 传 candidates 与 reload；从 '../../api' 只 import type | RolesView.tsx:37-42（candidates 在 reload 之前相邻连写） | 合 |
| 写法钉死 8：三条文字逐字、快照读 getRoles()+roleSnapshot、分派排在 setPluginEnabled 兜底之前 | useWriteFlow.ts:98（`改角色绑定 ${args.role}？`）、:115（`已改角色绑定 ${args.role}`）、:134（`角色 ${args.role} 的绑定改成 ${args.target}` + host/cadence 后缀）、:202-206（快照分支）、:543-545（分派在兜底之前）；`dangerOf` 未加 role.set（非危险动作） | 合 |

Behavior contract 的细则逐条对过：模式只列该角色允许的模式（次序照 ROLE_MODES，中文名照 modeName）；无头才渲染 profile 下拉、选项是已登记 profile 的 id；预填（模式不在可选里取第一个、profile 不在候选里取第一个）；host 只在「选的是交互式宿主 ∧ 现有绑定也是交互式宿主 ∧ 现有 host 非空」时原样带；cadence_seconds 只在「scheduler_agent ∧ 选的是无头 ∧ 现有绑定也是无头 ∧ 现有值是整数」时按字符串带；底部按命令 → 本角色前后 → warnings → 错误原文的次序渲染，且只取 `bindingChanges` 里 role 等于本角色码的那一项；[确认…] 门控是「表单开着 ∧ 取值合法 ∧ 预览对应当前取值 ∧ 预览 ok」；onConfirm 里 `onClose()` 先于 `start(spec)`；`<WriteFlow flow={flow} />` 与 `<Dialog>` 平级（RoleBindForm.tsx:151-152）；执行走 `POST /api/v1/roles/<role>`；写完 reload 从 RolesView → RoleCard → RoleBindAction → useWriteFlow 一路传下去；无 profile 时 execution 入口禁用并给原因句、其余三个角色把「无头」从模式下拉里拿掉且原因句写进 Select 的 help（接 aria-describedby）；未知角色码入口禁用且不传 reason（沿用缺省提示）。

## 4. 有没有越界、弱化测试、为过测试写特判

- 范围：候选补丁 18 个文件 = 16 改 + 2 新增，全部在合同 allowed 集合（scope.json 逐个标 in_scope；内核摘要「越界 0」）。forbidden 路径零改动：tests/test_gate_t051_*.py 不在候选里；ts/packages/ui/**、scripts/**、roles-styles.css、mock/profiles.json、mock/roles.json、hubChangeLines.ts、HubBindForm.tsx、hub-bind-form.css、components/**、shell/**、live/**、package.json 与锁文件都不在 18 个文件里。附带核过：src/mock 仍恰 14 份 JSON、src/pages 顶层仍恰 9 个 *Page.tsx、src/writes 未新增 CSS 文件。
- 旧断言：六处的改动与合同 Steps 第 10 步逐字一致（见第 7 节）。t009 里删掉的 5 行是合同点名要删的「第二阶段接入」悬停块，其余全是改数字与改标题；既有断言没有一条被删掉、跳过（skip/only/todo/xit）或弱化。
- 新测试：desktop/web/tests/writes-role-bind.test.tsx 454 行 / 14 条，注入假 LiveClient（setLiveClientForTests）而不是 mock 被测组件，断言打在真实 RoleBindForm、useWriteFlow、api 的正文与真实模式路由上；期望值没有把业务逻辑抄一份进测试（allowedModes 的字面量期望写在纯函数那条用例里，其余用例用实现导出的 allowedModes/modeName 作参照）。无 skip/only/todo。
- 源码里没有 test-only 分支、没有写死测试输入、没有空 catch / 静默吞异常：RoleBindForm 里唯一的条件分支（candidates 是否为空、headless、role 是否 scheduler_agent、binding.mode 是否同模式）都对应合同条款；api.ts 的 writeArgs 仍是「转不成原样传」，没有为通过而特殊处理 cadence_seconds。

## 5. 执行报告 DoD 自述 ↔ 内核摘要线索的逐条对照

内核 attempt 摘要「复审需要关注」共三条，逐一核过：

1. **新增被 Git 忽略的路径**（.pytest_cache/、desktop/web/dist/、ts/**/node_modules/）：都在 .gitignore 内、不进候选；执行报告也照实写了 dist/ 由 V03 生成。不是问题。
2. **「删除了 9 行含断言的代码（新增 68 行）」**：逐行核过补丁，删除只出现在三类地方——t009 合同点名删的 5 行悬停块、t024/t045 里被逐字改写的行、t047/t048 的三行冻结项；没有任何别处的断言被删。数目与内核口径一致。
3. **「测试或检查命令的退出码被管道掩盖（3 条…另有 25 条探索命令也如此）」**：events-summary.json 的 masked_exit_commands 逐条看过，全部是 check: false 的探索命令（ls/grep/sed/tsc | head）；五条必要检查由内核独立跑并记录真实退出码：checks.json 里 G01/V01/V02/V03/R01 的 exit_code 全为 0，output_must_match 四项全 matched；G01.log 实录「13 passed in 32.10s」，与执行报告自述一致。

另外核了两件事：

- **没有「临时路径」线索**：摘要的复审关注里没有临时路径项；候选与新增测试里没有写死绝对路径（grep `C:\`、`/tmp/` 无命中；门禁与白盒文件用 `Path(__file__).resolve().parents[1]`）。
- **执行报告的 limitations 第一条**（未亲自跑动手前的基线 npm test）：内核自己的 baseline/01/V01.log 已证明基线绿（Test Files 129 passed / Tests 1252 passed，0 failed），且执行端自述的「改完源码首次 npm test 其余 1249 条全过」与 1252 − 3 恰好对上（那 3 条正是合同点名要改的 page-roles:43、page-app 禁用数 11、writes-hub-bind 禁用数 11）。自述与内核记录一致，没有「报 done 却没做」的情形；字面偏离见第 8 节第 4 条（不挡）。

结论：执行报告的 DoD 自述（D01–D14 全 done）与内核记录、候选源码三方对得上，没有不实自述。

## 6. 战后门禁的裁定

- **变异清单**：mutations.json 逐条 id → status 全是 caught，汇总 caught 39 / missed 0 / skipped 0 / error 0。覆盖面与执行端改动的 9 个非测试源文件对得上（api.ts 4、mock/writes.ts 5、useLivePreview 2、snapshots 1、useWriteFlow 5、roles-logic 4、RoleCard 3、RolesView 1、RoleBindForm 14），另有 5 条接线变异（去掉 import、撤 NEW_ACTIONS 注册、分派改走 setPluginEnabled 兜底、去掉 CSS import），说明接线也在覆盖范围。
- **等价变异 / 没法变异的文件**：门禁端没有声明任何等价变异，也没有声明任何「没法变异」的改动文件，因此本回合没有需要逐条裁定的等价主张。我另核了一遍这 9 个文件的改动都确有对应变异，不存在「改了但没人测」的部分。
- **候选缺陷**：门禁端「候选缺陷」一节写「未发现」，本回合输入里没有需要逐条裁定的候选缺陷；我独立复核源码与门禁记录，也没有发现新缺陷。
- **白盒测试本身**：tests/test_gate_t051_whitebox.py 483 行 / 9 条用例，无 skip/xfail/todo、无绝对路径，断言打在源码文本与接线点上。它是文本层白盒，只承担「记号在位/边界条件逐字写对」，行为证明仍由 G01 的两份探针（真实模式 unit 与 page）与新增的包内测试承担——两层并存，没有拿白盒冒充行为证明。

## 7. 一审判过的人工审阅项，本回合的复核结果

一审把 D10、D11、D12、D14 判为「只能人工审阅」，本回合逐项复核：

- **D10（六处旧断言）**：候选补丁里的实际改动——t009：`it` 标题改成「[更改…] 是可点的 secondary sm」、`expect(b.disabled).toBe(false)`、删掉那 5 行悬停块、`outsideWhitelist([... '更改…'])`、`const later = ['保存当前为方案…'];`；t024：it 标题、`expect(c.disabled, '[更改…] 可点（T051 接上）').toBe(false)`、`toBe(7)`（注释文案照合同给的新文）；t045：ROLES_PAGE_DISABLED = 7 与两行注释、`:559` 的「（桩下 2+1+4）」、探针 it 标题与 `toBe(7)`；page-roles.test.tsx:43；page-app.test.tsx 的 it 标题与 `toBe(7)`（describe 标题「写入口个数（过渡）」一字不动）；writes-hub-bind.test.tsx 的 describe 标题「桩下角色页禁用按钮实测 7」、it 标题与构成注释、`toBe(7)`（bindDisabled/unsetDisabled 两条断言未动）。逐字与合同 Steps 第 10 步一致，没有顺手改同文件里的其他说明文字，既有断言零删除零弱化。**通过。**
- **D11（新增包内测试）**：454 行 / 14 条，覆盖合同第 12 步点名的每一项：allowedModes 与 profileIds 边界、四个角色各自只列允许的模式且预填现有模式、选无头再选 profile 后底部出现命令与本角色前后与 warnings 原文、真实模式 POST /api/v1/roles/<role> 且正文键恰为 target（+预填的 host 或 cadence_seconds）+confirmation、cadence_seconds 是 JSON 数字、role 不进正文、planning_review 保持交互式宿主带 host / 切无头不带、scheduler_agent 保持无头带 cadence / 切关闭不带、写完 getRoles 次数增加、无 profile 时 execution 入口禁用并悬停出原因句而其余三个角色模式下拉无「无头」且原因句在 help、对话框关着不渲染候选与多余按钮、reload 被调用。测真实实现、无 skip/only/todo。**通过。**
- **D12（范围）**：见第 4 节。**通过。**
- **D14（t047/t048 的差异恰是三行删除）**：候选补丁里 t047 只有一个 hunk（删 `f"{TESTS_REL}/page-app.test.tsx": (4005, "a8986dee…")` 一行），t048 只有一个 hunk（删 `API_REL: (36065, "f12707a3…")` 与同一行 page-app 冻结项两行），删的原文与合同引文逐字相同（含缩进）；两份文件的其余行（docstring、注释、其余冻结项与断言）一字未动、未加注释、未动行序。**通过。**

其余 DoD（D01–D09、D13）由 G01 的九条静态用例加两份探针、V01 的 1266 条测试、R01 的 1073 条与内核 scope 把关，本回合另按源码复核过第 3 节的写法钉死逐条，与一审的映射表一致。

## 8. 建议（不挡，不进阻塞项）

1. 战后门禁的白盒文件 `tests/test_gate_t051_whitebox.py` 是门禁端的交付物，不在候选补丁的 18 个文件里（候选树只有 16 改 + 2 新增），但已落在工作树的仓库侧。集成时默认随片带过去：源码不再改，它会继续过；带与不带都不影响产品行为，但带走能留一份本片的回归资产。
2. `profileIds` 直接 `p.id.startsWith('_')`，假定 id 是字符串；服务回的行若缺 id 会抛 TypeError。这与既有 `allowedProfiles`（同样直接取 `p.id`）是同一风险等级，不新增风险类别，也没有具体触发路径。
3. 合同 v2 的 Repository facts 仍写「基线 65c2e3bf」，而 Identity 的 base_sha 已被内核改成 2990c293（一审已提）。两者只差本片门禁文件一个，源码事实不变，不影响执行。
4. 执行端未亲自跑动手前的基线 npm test（合同「基线检查」的字面要求），已由内核 baseline/01 的 1252 条全过独立补证，实际风险为零；但字面偏离建议在下一版合同里改成「内核基线跑过即可」，免得每片都背一次。
5. 门禁文件的 ASSUMPTIONS 里「探针直接点「知道了」」那句已过时（探针现在走 done，不再点这两个字样）。一审已提，仍未改，不影响正确性。

## 9. 本回合做了什么与没做什么

- 做了：只读复核。读候选补丁全文（1295 行）、9 个源码文件与 3 个包内测试文件的实际内容、5 个门禁文件的逐字差异、内核 checks.json 与 G01.log、内核 baseline/01 的三份日志、战后门禁报告与 mutations.json 与白盒测试文件、合同 v2 全文、一审报告、执行报告与执行概述。
- 没做：没有 shell，没有跑 pytest 与 npm（一条命令都没跑），没有改任何文件；变异结果只核了 mutations.json 的汇总与逐条 status，没有自己重跑变异；白盒测试逐条读过结构与关键断言，没有逐行重写它的 483 行。

Verdict: PASS
