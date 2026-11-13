# 复审记录：t032-desktop-shellpages-live attempt-002（七端信箱 hub）

- 合同：t032-desktop-shellpages-live.v2（base 5964712e488c98c560ff16da2b916a3354714fa9）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261113T020547907639Z-8262），终审报告如下

## 终审报告

# T032-7 终审报告（attempt-002，合同 t032-desktop-shellpages-live v2）

## 结论

**通过。** 候选补丁恰好 6 个文件（3 改 + 3 新，全在合同 Scope 内），逐行读过后确认忠实实现合同 v2 的 D01–D13；内核在候选树上 fresh 重跑的 V01–V04 / G01 / R01 全绿；战后门禁的 13 条白盒与 25 条变异全过。没有发现越界改范围、弱化既有测试、为过测试写的特判、悄悄扩大的改动面，也没有发现执行报告里 DoD 自述不实。阻塞项：无。

## 材料与复核方式

- 合同 v2、候选补丁（6 文件）、执行概述与执行报告、内核 checks/01 与 checks/02 的记录与日志、战后门禁报告与其白盒/变异存档、仓库里的门禁文件 `tests/test_gate_t032_baseline.py`，以及工作目录中候选落地后的 6 个文件源码。
- 本回合工具只有读/搜/列（无 bash/npm），凡「跑过」的结论都引用内核 checks/02 的记录，并逐条核对了 argv、cwd、退出码、`output_must_match` 与日志正文，再回到源码逐条对照。

## 逐条 DoD 复核（实现 → 测试/门禁证据 → 判断）

| DoD | 实现（我读到的源码） | 证据 | 判断 |
|---|---|---|---|
| D01 唯一读取点/声明点 | `shellBridge.ts:9-13` 就地 `declare global { interface Window { themisShell?: unknown } }`；`:65` `const value = window.themisShell;`。我独立 grep 了 `desktop/web/src` 全部 ts/tsx：读取与全局声明只在 shellBridge.ts，其余命中都是类型导入与 SettingsPage 的 command 字符串 `'themisShell.getState'` | 门禁 s04、执行端静态用例前两条、内核 V01 | 达成 |
| D02 十成员核对 | `isCompleteShell`：非对象 → false；`SHELL_MEMBERS.every(name => typeof v[name] === 'function')`；核不过 `return null` | 门禁 bridge 探针对 undefined/null/42/'shell'/缺任一成员/任一成员非函数逐一断言 null；冻结对象可当 WeakMap 键 | 达成 |
| D03 引用稳定与缓存 | `wrappers` 模块级 `WeakMap` 按原对象 get/set；不在原对象挂属性；`unavailableShell` 模块级单例；`resetShellBridge` 换新表且不清单例 | 门禁 bridge 探针（属性前后一致、同对象同引用、异对象异引用、reset 后换新包装但单例不变） | 达成 |
| D04 取实例顺序 | Provider → `shellBridgeInstance()` → 夹具 `stubFor(scenarioFromHash(...))` → `unavailableShell()`；`stubFor(` 全文件仅一处且只在夹具分支；`liveModeIsReal()` 每次现算、模块顶层无调用 | 门禁 context 探针（假外壳优先、Provider 最优先、成员不全回桩、真实模式 createShellStub 0 次且 shell= 不起作用、引用稳定）、执行端新测试 | 达成 |
| D05 外壳不可用实例 | 九个方法共用 `reject()` 工厂，message 逐字「没有连上外壳」；`on: () => noop` 同步返回空退订；模块级单例 | 门禁 bridge 探针（九个方法逐一 rejects、on 同步且非 Promise、两次同引用） | 达成 |
| D06 提示收窄 | 首启页 `tt-fr__err` + `role="alert"`；服务状态页错误显示在 `tt-ss__note` 说明行。设置页一字未改：仍是 `useCallback` 包的 `shell.getState().then(...)`、依赖 `[shell]`、command `['themisShell.getState']`，reject 冒给 PageFrame（有 `.catch` → 通用出错块） | 门禁 transitional s06（与基线逐字一致）+ views 探针（设置页显示「没有收到服务的回应」，不含「没有连上外壳」/「操作失败」/「返回退出码」） | 达成 |
| D07 两视图出错状态 | 首启页 getState、两处 startService、三处 pick 全部接住拒绝；错误块在 `</ol>` 之后、`tt-fr__foot` 之前；无 `data-step-error`、无 `role=status`；未新增 css 类（`tt-fr__err`/`tt-ss__note` 已在 css 里）。服务状态页 `note = noteError ?? stoppedNote(...)`；`restartService` 被拒复位 restarting；无 `role=alert` | 门禁 views 探针（位置、空 message → 「操作失败」、restart 复位、自动启动/选择失败显示在同一块） | 达成 |
| D08 退订 | 两视图订阅 effect 各恰好一处 `return off;` | 门禁 views 探针（卸载时退订各被调一次） | 达成 |
| D09 夹具行为不变 | 现有 8 份 `shellpages-*.test.*`、themisShell.ts、shellStub.ts、ShellWindow.tsx、SettingsView.tsx、PageFrame.tsx、App.tsx、`src/live/**`、vite.config.ts、构建脚本、两份静态扫描测试均未出现在候选补丁里 | 门禁 transitional s09、内核 V01 985 passed、R01 815 passed | 达成 |
| D10 静态约束 | bridge 原文无四个网络词整词（连注释也没有）；`src/shellpages/**` 无 api 导入；新文件名合规；cleanup2 禁用文字与唯一定义未被抢 | 门禁 s03/s08/s10、内核 V01 | 达成 |
| D11 构建核对 | — | 内核 checks/02：V02 `built in`、V03 `LIVE_BUILD_OK 3/3`、V04 `契约检查：通过`，均 exit 0 | 达成 |
| D12 门禁与回归 | 候选补丁不含 `tests/**` | 内核 checks/02：G01 16 passed、R01 815 passed，均 exit 0（执行端自述的 t018 抖动在 fresh 重跑里没有出现） | 达成 |
| D13 范围与卫生 | 补丁 6 文件 435+/13-，与 Scope 一致；白盒 w12 复核通过；新测试无 skip/only/todo；无写死临时路径；dist/、.pytest_cache/、ts/**/node_modules 均为 gitignore 内产物、未进候选 | 门禁 s01/s08、白盒 w11/w12/w13、内核 scope | 达成 |

## 门禁与内核记录的核对

1. **白盒 13 条**：多为源码文本断言（静态白盒的固有局限），行为面由门禁自带的三份 vitest 探针承担，且内核在候选树上 fresh 跑过 G01（16 passed，含 npm test 全量 + 三份探针）。不存在空心断言：探针断的是调用次数、DOM 文案、引用同一性、退订次数、Promise 原样透出。
2. **25 条变异**：覆盖执行端改动的 4 个非测试文件（bridge 10、context 5、FirstRunView 6、ServiceStatusView 4），6 条接线类（删 unavailableShell 引入、删真实例分支、第四条路换桩、on 退订转发改空、两视图 `return off` 改掉）。逐条对照 mutations.json，没有「改了却抓不住」的空转条目；25/25 抓住、0 漏 0 跳过。
3. **门禁登记的三处读法**逐条复核后维持原判：错误成功后不清除（合同只要求「被拒时显示」，夹具桩从不 reject）；messageOf 各写一份（与 D07 逐字一致，不抽公共文件避免越界）；函数形状当没有外壳（D02 写的是「不是对象 → null」）。
4. 门禁未举证任何候选缺陷（其结论是「候选通过，无候选缺陷」），本回合无须逐条裁定的候选缺陷。
5. 门禁工件 `tests/test_gate_t032_whitebox.py` 与 `mutation-spec.json` 不在候选补丁里（补丁只有 6 个文件）；门禁已声明其范围断言只对本次 attempt 成立。

## 执行报告自述 × 内核摘要线索（逐条对上）

- 「掩盖退出码的写法（1 条命令）」：一条人工 grep（唯一读取点、skip/only/todo），管道末端 `|| true` 抹掉退出码。D01/D10 的证据是 V01 的静态用例与门禁 s04/s08，不依赖这条 grep → 不构成自述不实。
- 「执行器自行宣布了 1 处解读（不重跑完整 R01），但 interpretations 为空」：R01 行如实写 exit code 1、「1 failed, 814 passed」、点名 t018 的内核 HTTP 超时用例，limitations 写明请验收端独立复跑 → 事实没隐瞒，DoD 自述与内核 fresh 结果（R01 815 passed exit 0）一致 → 不是不实；但过程性判断应写进 `interpretations`，属体例瑕疵。
- 「新增被 Git 忽略的路径 .pytest_cache/、desktop/web/dist/、ts/**/node_modules」：分别是 pytest、vite build、npm ci 的产物，都在 .gitignore 内、未进候选 → 与报告「未建临时目录、dist/ 未提交」一致。

## 不挡的意见（写进 report，不进阻塞项）

1. **转发的接收者（this）**：bridge 的通用转发是 `method(...args)`，脱离原对象调用。若 T030 的 preload 把十个成员写成对象字面量的方法并在内部用 `this` 调兄弟成员，真实外壳窗口会同步抛 TypeError（不是 reject），页面会崩而不是显示错误文案。触发条件取决于尚未落地的 T030 preload 写法，Electron contextBridge 对 `this` 的处理我在本仓库里核实不了，按不挡意见记：T030 落地时请核对；若 preload 用了 `this`，把转发改成 `method.apply(target, args)`（仓库门禁探针与静态用例都不依赖现在的写法，事后白盒文本锚点需同步更新）。
2. **错误状态成功后不清除**：合同没要求清除；真实外壳窗口里 getState 只在挂载时调一次，影响很小。
3. **执行端新测试与门禁 PROBE_CONTEXT 高度相似**：合同第十节本就规定了这 5 个用例与 vi.mock 计数手法，可接受；但两处 helper 重复，后续别只改一处。
4. **执行报告体例**：过程性判断应写进 `interpretations`。
5. **真实模式下没有外壳时设置页显示通用出错块**：合同 Non-goals 已登记的已知不足，留给主窗口经 host.openSettings() 打开设置窗口的那一片。

## 阻塞项

无。

## 遗留与局限

- 本回合没有 bash/npm 工具，未独立重跑命令；「跑过」的结论全部引用内核 checks/02 的记录（已逐条核对 argv/cwd/退出码/输出匹配与日志正文），并回到源码验证每条断言所依赖的实现。
- T030 的外壳页 preload 返回形状尚未落地：本候选只按合同假设实现（十成员核对 + 纯转发，不拆信封），若 T030 改了信封或 `cancelled` 约定，属协调人转告事项，不是本候选的缺陷。
- 门禁白盒以源码文本断言为主，其价值依赖三份 vitest 探针；本回合这些探针由内核在候选树上 fresh 跑过（checks/02 G01 16 passed），我没有单独重跑。

Verdict: PASS
