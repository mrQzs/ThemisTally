# 复审记录：t061-desktop-appearance-settings attempt-002（七端信箱 hub）

- 合同：t061-desktop-appearance-settings.v3（base a71725f08809a8f1d9411efc69e639a789a9ef24）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261119T225251889796Z-ddde），终审报告如下

## 终审报告

# T061-7-audit-post 终审报告（片 A：外壳侧，候选 a71725f0）

## 1. 结论

通过。没有发现会导致打回的问题：实现忠实于合同 v3 的 Behavior contract 与 Steps，改动范围在允许集合内，既有测试没有被删除、跳过或偷弱化，内核四条检查全绿，战后门禁的白盒与变异证据扎实，执行报告的 DoD 自述与代码、内核记录逐条对得上。

第 8 节列 6 条不挡的意见（其中 1 条是合同 Steps 12 点名的一处测试文件没改、1 条是 README 一句旧数字，其余是记账与口径提醒）。

## 2. 审查对象与证据来源

- 候选：`a71725f0`（= attempt-001 的 25 文件改动，基线 `16bf543b`；attempt-002 的 candidate.patch 为 0 字节、changes.json 为 `[]`、scope.json counts 全 0——返工轮没再改代码，只补了执行报告与核验）。
- 合同：`.agent/plans/t061-desktop-appearance-settings.v3.md`（Behavior contract、Steps 1–16、DoD D01–D10、站主决定、Rework 第 1 轮）。
- 内核检查：`attempt-002/checks/01/checks.json` 与 V01/V02/G01/R01 四份日志（都在候选树 `2f42e6b9` 上跑，tree_before == tree_after）。
- 战后门禁：`.agent/mailbox/tasks/T061-6-gate-post/report.md`、白盒文件 `evidence/whitebox-20261119T225138100234Z.py`、变异记录 `evidence/mutate-.../mutations.json`。
- 执行侧：`attempt-002/executor-report.md`、`summary.md`、`events-summary.json`。

## 3. 候选补丁逐条对照合同

逐文件读过补丁全文与仓库现状，结论如下（合同条款在括号里）：

- **src/settings.js**：DEFAULT_SETTINGS.theme 改 "dark"、density 仍 "standard"；新增并导出纯函数 `appearanceOf`（返回新对象）；THEME_VALUES/DENSITY_VALUES/PATCH_KEYS/SETTINGS_FILE_KEYS 一行未动。（Steps 2）
- **src/window.js**：新增并导出 `backgroundFor(theme, systemDark)`——dark→#0C111A、light→#F3F5F9、system 与任何非法值（含 undefined）按 systemDark。（Steps 3）
- **src/ipc.js**：HOST_CHANNELS 末尾加 `themis-host:save-theme`（共七、冻结）、HOST_METHOD/HOST_ARITY 各加一项、导出两个外观常量；registerHostIpc 仍只 handle。（Steps 4）
- **src/shellipc.js**：SHELL_CHANNELS 仍恰好九个、顺序不变；导出两个外观常量（字面量不进通道表）。（Steps 5）
- **src/hostrelay.js**：HOST_METHODS 末尾加 saveTheme（共七）；无当前 host 时 saveTheme 回 forbidden、clear 后回 forbidden。（Steps 6）
- **src/host.js**：新增可选注入 `saveTheme` 与编排（bad-args → unavailable → 转交 → 注入抛错回 internal）；返回对象七个成员、saveTheme 最后。（Steps 7）
- **src/shellapi.js**：新增可选注入 `onAppearanceChange` 与 `initialSettings`（深拷贝、给了就一次 store.load 都不发生）；saveSettings 写盘成功且 theme/density 变了才回调一次（两个字段都是新值）、回调抛错吞掉；返回成员仍十个。（Steps 8）
- **preload.js**：themisHost 九个函数，模块级恰好一个 `ipcRenderer.on("themis-host:appearance")` + Set；getAppearance 用 sendSync、调用时才取；源码里没有 removeListener / .off(；仍自包含、仍恰好一次 exposeInMainWorld、仍无 ipcRenderer.send。（Steps 9）
- **shell-preload.js**：themisShell 十一个成员，模块级两个 ipcRenderer.on（service-state、appearance）各带一个 Set；on 认两个事件名，别名回空退订函数且不注册。（Steps 10）
- **main.js**：electron 解构加 nativeTheme；外壳分支 `const initialSettings = store.load().settings;` 逐字一致、`currentAppearance = appearanceOf(initialSettings)`；两处同步读取注册在 `await openShellWindow(SHELL_START_URL)` **之前**（一审非阻塞意见 1 已落实）；每个处理函数先 `event.returnValue = null` 再 try/catch、catch 里也回 null，两处覆盖成 currentAppearance 且判 isDestroyed；带参数分支那处恒答 null。三个发送点各写一遍、各自判 isDestroyed、负载只有外观对象一个实参。`createHost` 只在外壳分支注入 saveTheme（逐字 `api.saveSettings({ theme: pref })`，成功取 `value.settings.theme`/`value.settings.density`），带参数分支的 createHost 里连 saveTheme 这个词都没有。建窗：外壳页/设置窗与外壳分支服务窗用 `backgroundFor(currentAppearance.theme, …)`，带参数分支服务窗用 `backgroundFor("dark", …)`，凭据窗不设；guardedWindow 五处、new BrowserWindow 一处、.protocol.handle( 一处。（Steps 11）
- **六份旧门禁**：逐处按 Steps 13 改（ipcMain.on 禁令按站主口径收窄成「只许 main.js、通道只许那两个读取字面量」；preload 的「不许有 ipcRenderer.on」改成「恰好一个、频道 themis-host:appearance」；T060 的 settingsWin 发送禁令收窄成只禁 SERVICE_STATE_CHANNEL；T030 P04 与 shellpreload 的成员集合断言放宽为「+getAppearance」并写明 T063 恢复条件）。T028 只改缺省主题三处；T032/T012 未动。（Steps 13）
- **README**：新增「## 外观」段（五个通道字面量、外观对象、saveTheme 信封与 reason 词表、同步读取回 null 的语义、背景色取值、appearanceOf/backgroundFor/getAppearance/onAppearance/saveTheme），既有 needle 未丢；与新形状冲突的旧句子（六→九、十→十一）改写。（Steps 14）

**范围**：25 个文件全在 allowed_modified_files 内（scope.json violations 空、warnings 空、A0/D0/T0），没有新增文件，没有碰 desktop/web/**、package.json、锁文件、依赖。**desktop/shell 下除 main.js 外没有任何 .js 含字面 ipcMain.on**（全仓 grep 复核过，含注释）。

## 4. DoD → 证据 映射（终审版，候选 a71725f0 上实际跑过的）

| DoD | 证据 | 实际结果 | 判定 |
| --- | --- | --- | --- |
| D01 缺省暗 | V01（settings.test.js / shellapi.test.js 各一条）+ G01 S01/P01 | V01 336 pass；G01 17 passed | 可证 |
| D02 两分支注册同步读取、每条路径都答 | G01 S07（静态）+ 站主真窗口核读值（合同写明本片无 main.js 单测） | S07 通过：三处、通道白名单、returnValue 每路径都设 | 结构可证；运行期由站主补（合同范围内写不出 main.js 单测） |
| D03 变了才广播、三个发送点 | V01（shellapi.test.js 六条回调矩阵）+ G01 S08 + 战后白盒 W01 | V01/G01/白盒全绿；W01 钉住三个发送点的单实参负载与 isDestroyed | 可证 |
| D04 saveTheme 四种结局 | V01（host.test.js 六条、hostrelay.test.js 三条）+ G01 P03/P04 | 336 pass | 可证 |
| D05 backgroundFor 与建窗背景色 | V01（window.test.js 十条）+ G01 S09 + 白盒 W01 | 暗/亮/system/非法值/undefined 全覆盖；凭据窗不设 | 可证 |
| D06 外壳单测全过 | V01 | # pass 336 / # fail 0 / # skipped 0 | 可证 |
| D07 旧门禁与全套回归绿、T032/T012 未退役 | V02 + R01 | V02 66 passed；R01 全套 **1178 passed**（t012/t032 在内，两文件未被改动） | 可证 |
| D08 范围 | scope.json + 逐文件核对 | violations 空，25 文件全在允许集 | 可证（人工＋内核） |
| D09 没删/跳/弱化测试 | 逐份门禁 diff + 外壳测试 diff | 无用例被删或 skip；四处口径收窄均有合同 Steps 13 与站主授权 | 人工可证（见第 8 节意见 3） |
| D10 README | V02 + G01 S10 + 人工扫 | 旧 needle 全绿；新段记号齐 | 可证 |

## 5. 检查与门禁记录核对

- **内核 checks.json**（候选树 2f42e6b9）：V01 exit 0、`# pass \d+` matched、`# fail [1-9]` 未匹配；V02 exit 0、66 passed；G01 exit 0、17 passed；R01 exit 0、**1178 passed in 1130.20s**（t001–t060 全套）；covers_all_required=true、all_required_passed=true、modified_by_checks=false、candidate_files_modified 空。
- **空心基线**：G01 在基线 16bf543b 上是 17 条全失败（缺功能的断言失败，不是文件缺失/导入失败），候选上 17 passed——前后对应成立。
- **战后门禁**：白盒 3 条（W01 静态钉 main.js 的「值」的接线与 import 接线，W02/W03 探针真跑 shellapi 与两份 preload）全过；变异 43 条 **caught 43 / missed 0 / skipped 0 / error 0**，无 equivalent、无 unmutated（11 个非测试文件全部有变异打上去，含 6 条「去 import / 去导出 / 去注册」的接线变异）。门禁端没有提任何「测不出来的等价变异」，也没有「不用测的文件」，本轮无待裁定的候选缺陷。
- **门禁强度未被偷换**：T026/T030/T033/T035 的 ipcMain.on 禁令收窄时仍带「只许 main.js + 通道白名单 + 其余 .js 一处不许有」三重限制；preload 的监听禁令从「一律不许」变成「恰好一个且频道逐字」，比原来更具体，不是变松。
- **留在仓库当回归测试的残留**：六份门禁里没有相对基线的改动范围断言，也没有共享页面上的整页否定；「恰好」类断言只针对 main.js 内部形状（本片自己引入/保持的不变量）与 preload自身，片 B（T063）只碰 desktop/web，不受影响。

## 6. 执行报告自述核对（含 JEV线索对账）

- **DoD 逐条**：D01–D10 的 note 与代码/日志逐条对得上（见第 4 节）。D02 的「无 main.js 单测（合同写死）」与合同「本片没有 main.js 的单测」一节一致；D07 的 note 写明「全量 R01 交验收端」，而内核在同候选树上跑了全套并1178 passed——**D07「全套回归也绿」由内核记录背书，不属自述无据**。
- **JEV 6j-jev**：「自述完成而无证据 p=0.90（0.80，【需关注】）」——逐条核完不成立：每条 DoD 都有对应命令或内核记录；唯一「无独立证据」的两条（D08 范围、D09 未弱化测试）合同本身就定为人工审阅项，本终审已逐份 diff 核过，结论一致。D07 的 R01 由执行端跑子集、内核跑全套，两边记录都在。
- **内核摘要线索对账**：「掩盖退出码的写法（10 条）」——events-summary.json 的 masked_exit_commands逐条看过，全是 grep/查看类命令（不是测试或检查命令），执行报告的四条自检命令都写了真实命令与退出码，无自述不实；「临时路径」「可疑命令」「工作区外路径」三处计数均为 0（temp_path_uses=[]、suspicious_commands=[]、outside_worktree_paths=[]），执行端没有往工作区外写文件；attempt-001 摘要里的「删除 29 行含断言的代码」经逐份 diff 核对，删的都是被授权替换的旧断言（六→九、十个→十一个、ipcMain.on 禁令收窄），没有一条既有用例被悄悄删掉。
- **返工轮的性质**：合同 Rework 第 1 轮要求「DoD 都做完了就直接写执行报告，不要把已经通过的检查从头再跑一遍」——attempt-002 没改代码、只补报告并跑相关子集，符合该指示；执行报告的 limitations 已如实披露全量 R01 未跑。

## 7. 逐文件找茬的结果（有没有为过测试而写的特判）

- 没有特判：backgroundFor 与 appearanceOf 是无分支副作用的纯函数；广播的三个发送点是合同逐字要求的三行，不是为了迎合「host_sends≥1 / shell_sends≥2」而凑数；白盒 W01 钉的是「值从哪来」而不是形状。
- 没有空的异常处理：三处同步读取的 catch 都真的把 returnValue 设回 null（渲染进程会卡住等答复，这条不能空）；host.saveTheme 的 catch 回 internal；shellapi 的回调异常被吞但返回值不变（合同明写）。
- 没有硬编码测试输入：shellapi.test.js 的探针用真 store 夹具；门禁探针用 vm 真跑 preload 源码并注入假 ipcRenderer。
- 没有悄悄扩大的范围：25 个文件，无新增文件，无 web 侧改动。

## 8. 非阻塞意见（不挡）

1. **合同 Steps 12 点名的 desktop/shell/tests/shellipc.test.js 没改**：该条要求「补两个新常量的逐字断言；断言它们不进 SHELL_CHANNELS（仍九个）」。现状是文件里没有这两条断言（其余「注册只用 handle、恰好九个通道、零次 on」本来就有）。覆盖并不缺——同样两条在仓库门禁 tests/test_gate_t061_baseline.py 的 S03（静态）与 P05（探针）里，变异 M11/M12 改这两个常量的值都被抓住——但合同逐字要求的那一处没照做。连带一个小错：shell-preload.js 本片新加的注释写「两处一致由 tests/shellipc.test.js 比对」，而该文件并没有这条比对（实际在门禁文件里）。建议片 B 或下一轮把注释与断言对齐（改一行注释或补三条断言），本轮不挡。
2. **README:186「宿主接口（createHost 建的五个函数）」是旧数**：本片把 host 扩到七个；这句在本片之前就不准（当时是六个），本片让它更不准。既有 needle 仍全绿、D10 满足，只是文档与形状对不上；建议顺手改成七个。
3. **D09 的文字与补丁实际放宽项数不一致**：D09 只提「唯一放宽的两处成员集合断言」，补丁里另有四处有授权的口径收窄（T026/T030/T033/T035 的 ipcMain.on 禁令按站主 20261119T200051871799Z-owner-150ec7 决定2 收窄、T060 的 settingsWin 发送禁令按 Steps 13-2 收窄、preload「不许有 ipcRenderer.on」按 Steps 13 改成「恰好一个」）。这些收窄都是合同与站主明文要求的，不是偷工；但 D09 文字至今没按一审意见补写，将来按字面核会起争议。给合同端留个记录。
4. **执行报告把相关子集回归标成 R01**：合同 R01 是 t001–t060 全套，执行端那条只跑了 T012/T032/T039/T002/T006/T034（292 passed），编号与合同检查号不对应，容易被误读成「R01 已跑」。内核在同候选树上另跑了全套并 1178 passed，结论不受影响。
5. **门禁正则松一格**：T026/T030/T033/T035 新增的 `IPC_MAIN_ON_RE` 要求后面带「(」，旧禁令是词边界（`ipcMain\s*\.\s*on\b`）。于是别的 .js 里注释写「ipcMain.on」（不带括号）不再被这四份判红。语义上的调用仍被兜住（T061 门禁 S07 用词级正则扫全仓 .js，除 main.js 一处不许有），本片也真的没有在别处写这个字样；只是口径上比旧禁令松了一格，可留意。
6. **战后门禁的执行环境说明**：门禁端因本工作目录 scripts/kernel-impl.json 指向未装好的 TS 实现，改把官方 scripts/pi_dispatch.py 连同一份全 python 的 kernel-impl.json 复制进 .agent/runs/_scratch/（Git 忽略）执行，跑完已删；判定逻辑与官方脚本一致，非合同偏离，记录备查。

## 9. 结论

通过。候选可进集成；片 B（T063）按下游须知核对三处恢复条件即可。

Verdict: PASS
