# 复审记录：t060-desktop-shell-open-settings attempt-001（七端信箱 hub）

- 合同：t060-desktop-shell-open-settings.v2（base 2f78f8218d9efdb0c169002d1bda128802bdd984）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261119T193412110244Z-f916），终审报告如下

## 终审报告

# T060-7 终审报告（audit-sonnet）

## 结论

通过。候选 t060-desktop-shell-open-settings.v2.a001（基线 2f78f82 + candidate.patch，17 个文件）忠实实现了合同 v2 的行为契约与 Steps 1–12：宿主接口第六个函数接线齐、设置外壳窗口只此一个、生命周期三处收尾、前端新旧分支各自照旧、三个旧门禁按合同逐处改。内核五条必要检查全绿，战后门禁 34 条变异全部被白盒测试以对应断言抓住。没有发现合同违反、范围扩大、弱化测试或为过测试而写的特判。

## 1. 材料与顺序（先读源码，后看记录）

- 合同：.agent/plans/t060-desktop-shell-open-settings.v2.md（Behavior contract、Steps 1–13）、attempt-001/contract.json（16 条 DoD、5 条检查、允许/禁止集合）
- 候选源码（工作目录冻结快照）：desktop/shell/{main.js,preload.js,src/host.js,src/hostrelay.js,src/ipc.js,src/shellprotocol.js,README.md}、desktop/web/src/{live/hostSettings.ts,pages/SettingsPage.tsx}、desktop/shell/tests/{host,hostrelay,ipc,preload}.test.js、desktop/web/tests/host-settings-open.test.tsx
- 补丁与范围：candidate.patch、changes.json、scope.json、candidate.stat.txt（13 改 + 2 增，全在 allowed_modified + allowed_new 内，越界 0）
- 执行侧：executor-report.md、summary.md（内核摘要里的可疑线索逐条对过）
- 内核检查（权威）：attempt-001/checks/01/checks.json + R01/V01/V02/V03/G01 日志
- 战后门禁：T060-6-gate-post/report.md、evidence/whitebox-*.py、evidence/mutation-spec-*.json、evidence/mutate-*/mutations.json 与 34 份逐条日志
- JEV：T060-6j-jev/report.md

## 2. 实现忠实性（合同条款 → 实现位置 → 判定）

| 合同条款 | 实现位置 | 判定 |
|---|---|---|
| Step 2 地址常量 | shellprotocol.js 的 SHELL_SETTINGS_URL（值逐字 themis-shell://app/index.html#/settings，导出紧跟 SHELL_STATUS_URL 之后） | 一致 |
| Step 3 四处接线 | preload.js 六个函数、ipc.js 的 HOST_CHANNELS/HOST_METHOD/HOST_ARITY(0)、hostrelay.js HOST_METHODS 六项（新项在末尾） | 一致 |
| Step 4 host.js | createSettingsWindow 可选注入、settingsWindow 占位在第一个 await 之前、once(closed) 只清自己、已开先 restore 再 focus、load 失败关窗回 load-failed、文件里无 parent 标识符 | 逐条一致 |
| Step 5 建窗 helper | main.js 的 createShellPageWindow 定义在 runShellPage 内（root 闭包可见）、.protocol.handle( 与 new BrowserWindow 各一处、openShellWindow 改用它且语义照旧 | 一致 |
| Step 6 设置窗口 | createSettingsWindow 同层、标题 设置、拦 page-title-updated 并 preventDefault、不设 parent、不兑现 userClosedShell | 一致 |
| Step 7 注入 | 外壳分支 onRunning 注入 createSettingsWindow，带参数分支的 onServiceReady 不注入 | 一致 |
| Step 8 来源检查与对话框 | registerShellIpc 第三个实参逐字保留 shellSenderAllowed(event, shellWin.webContents) 并追加设置窗口那一段；createShellApi 三个注入各自内联同一段 owner 表达式（变量名不是 parent） | 一致 |
| Step 9 生命周期 | 用户关服务窗口：先 settingsWin.close() 再 flow.stop()，退出码规则未动；意外退出三条分支都关设置窗口，换页成功那支是新窗口开好之后才关旧窗；服务状态事件仍只发 shellWin | 一致 |
| Step 10 前端 | hostSettings.ts 与合同代码块逐字相同（就地转型、不 declare global、不 import api、不读 themisShell）；SettingsPage.tsx 新分支用 PageFrame、command 写 host.openSettings、挂载调用在 useEffect 里、失败一行 role=alert 带 reason、新分支不调 getState；旧分支渲染与 hook 一字未改；文件里无 themisHost 字样 | 一致 |
| Step 11 包内测试与 README | preload/ipc/hostrelay/host.test.js 四个文件按合同逐处改；README 第 5 行删掉 与 openSettings() 仍没有 但保留 外壳页在本片就位，宿主表加 openSettings 行，写清唯一窗口/聚焦/随服务窗口关/只保存不重启服务，冒烟加第 5 条 | 一致 |
| Step 12 旧门禁逐处改法 | T026 的 p01/p05 与 docstring 点名的四处、T035 的 HOST_METHODS 常量与 PROBE_HOSTRELAY、T032 的 s06 退役（连合同给定的三行注释逐字） | 一致，没有顺手改别的断言 |

## 3. 范围、测试与门禁改动

- 范围：changes.json 与 candidate.patch 对齐：17 个文件 = 合同 allowed_modified(15) + allowed_new(2)；禁止集合（desktop/shell/package.json、两个锁文件、shellpages 冻结文件、src/live/transport.ts、App.tsx、PageFrame.tsx、vite.config.ts、tests/test_gate_t060_*.py 等）零改动；D09 点名的 SettingsView.tsx / App.tsx / themePref.tsx / transport.ts 一个字没动。执行端为跑 V02/V03 装过 desktop/web 的 node_modules（按既有锁文件），package.json 与锁文件零改动，且属 git 忽略路径。
- 测试没有弱化：唯一被删的断言是 T032 的 test_transitional_s06_settings_page_untouched，那是合同 Step 12 明确授权的退役（文件里留了合同给定的退役注释），执行端在 D15 里如实写了。其余既有断言只做 五个 → 六个 的计数更新与 openSettings 断言从 不许有 改成 必须是函数（这是功能本身要求的）。
- 内核检查：checks.json 里 G01、R01、V01、V02、V03 五条 exit_code 全 0、output_must_match 全 matched；R01 是全量跑的（1161 passed in 1138s），比执行端自报的相关子集更强。summary.md 里 退出码被管道掩盖 的提醒只针对执行端自己敲的命令，权威结论以 checks.json 为准，无冲突。
- summary.md 里的 删除了 14 行含断言的代码 与 主工作区 AGENT_LEARNINGS.md 变化：前者即 T032 s06 退役加 main.js 的 openShellWindow 位置搬移（执行端已披露）；后者不在候选补丁里，candidate_files_modified 为空，摘要本身把 HEAD 变动归因于别的主任务落地，不是执行端写的。

## 4. 排查：硬编码、空断言、特判、扩范围

- 硬编码测试输入：没有。外壳侧沿用 host.test.js 既有的假窗口写法，只补了 isMinimized()/restore()；前端侧装一个假的 window.themisHost，用真实计数器数调用次数。
- 空心断言：没有。新前端测试里 对 getState 的 spy 是真的能记录调用：shellContext 对同一场景返回引用稳定的桩实例（同一场景同一实例、引用稳定），桩的 getState 是对象上的普通函数，vi.spyOn 打的就是组件会取到的那个对象；旧分支那条断言还要求 getState 恰好调一次，说明桩与旧分支确实共用同一个实例。
- 为过测试而写的特判：没有。实现里没有测试名、开关、环境判断之类的旁路；host.js 的 unavailable 判定是 typeof createSettingsWindow !== function（带参数分支真的不注入），不是看调用来源。
- 空异常处理：新增代码里没有空 catch；加载失败路径关窗并回 load-failed，preload 与 ipc 的错误路径沿用既有规则。
- 范围：没有扩大，也没有静悄悄地多做功能。

## 5. DoD 自述与证据对照（JEV 两条 flag 的回应）

| DoD | 证据 | 判定 |
|---|---|---|
| D01 | V01 三个包内用例 + G01 + 白盒探针二 | 通过 |
| D02 | V01 host.test.js 六个新用例 + 白盒探针一 | 通过 |
| D03 | G01 S03 + 源码拦 page-title-updated；真窗口 1.5 秒那一下属 D16 | 实现通过，冒烟待验收 |
| D04 | G01 S04 + 源码 registerShellIpc 与三个对话框 owner | 通过 |
| D05 | G01 S05 + 源码三处生命周期（次序由白盒 test_static_main_lifecycle 钉） | 通过 |
| D06 | V01 unavailable 用例 + G01 两次 createHost 计数 | 通过 |
| D07 | V02 前端新测试 + G01 S06 | 通过 |
| D08 | V02 冻结的 shellpages-settings.test.tsx + R01 的 T012 | 通过 |
| D09 | changes.json/scope.json（那四个文件未改） | 通过 |
| D10 | candidate.patch 里三个门禁文件的 diff 与合同 Step 12 逐处对照 | 通过 |
| D11 | R01 全量 1161 passed | 通过 |
| D12 | G01 S07 + README 逐字 + R01 的 T035 S05 / T039 S06 | 通过 |
| D13 | V01 + V02 | 通过 |
| D14 | 17 个文件全在允许集合，锁文件与 package.json 零改动 | 通过 |
| D15 | 只按合同退役 T032 s06，其余断言未删未弱 | 通过 |
| D16 | 合同写明验收端做，执行端不跑真 Electron；执行端报 not_done 而不是 done | 记在验收范围，不算自述不实 |

JEV 的两条 flag 复核后不成立：自行解读两条都在合同字面之内（合同 Step 11 原文就是 假 host 形状一并改成六个、docstring 点名四处）；自述完成而无证据 的命中主要来自 D03/D16 这类 evidence 写 review 的条目，其中 D16 已如实标 not_done，其余都能对上 checks.json 与门禁记录，没有发现自述与内核摘要矛盾的地方。

## 6. 战后门禁的变异声明逐条判断

- mutations.json：34 caught / 0 missed / 0 skipped，files_left_modified 为空，baseline 与候选都 exit 0。
- 抽查 M01–M09 的日志：每条都红在对应断言上（例如 M01 红在 设置窗口的标题要是 设置、M06 红在 用户关服务窗口要先关设置窗口再 flow.stop()、M09 红在 确认框在有窗口时要真的把窗口传给 dialog.showMessageBox），不是语法错、不是导入失败、不是超时挂死。
- 白盒测试本身可信：探针一真跑 desktop/shell/src/host.js（假窗口、2 秒 withTimeout 兜底），探针二真跑 preload/ipc/hostrelay/shellprotocol；静态边界用剥注释 + 括号配平取区域，不按行号，剥注释后只认形状，行为正确的实现不会误红。
- 前端两份文件的变异由静态边界抓住（门禁机没有 vitest 依赖且不许安装），这是门禁端写明的取舍，行为级覆盖由执行端的 desktop/web/tests/host-settings-open.test.tsx 与 V02 承担；我不认为这构成本片缺陷。
- 门禁端声明等价的部分：M16 的 count=2 确实同时改坏 openSecretWindow 与 openSettings 两处同一句守卫，红在 openSettings 一侧即算抓住，不算漏；M14 的占位缺失在探针里靠 2 秒兜底快速红。逐条判断都成立。
- 没有门禁端举证的候选缺陷需要裁定（本回合输入没有这一节），也没有 白盒测试误读合同 的情形。

## 7. 不挡的意见（不写进阻塞项，由站主决定）

1. tests/test_gate_t026_baseline.py 的文件头 docstring 里还留着 新增五个函数与 reason 词表，而 README 现在是六个宿主函数。合同的 Step 12 只点名了四处描述暴露面的措辞，这句在合同列举之外；且 README_T026_NEEDLES 仍只列五个函数名，模块内部自洽，所以不改也不算错。措辞陈旧，下片动这个 docstring 时顺手改即可。
2. hostSettings.ts 的 hostOpenSettings 是 Promise.resolve(open())，open() 是先调后包：万一宿主函数同步抛错，异常会从 SettingsPage 的 open() 里冒出来而不是走 .catch。当前 preload 的 ipcRenderer.invoke 是回一个被拒的 Promise（不抛），所以现网碰不到；若站主要求更稳，写成 Promise.resolve().then(() => open()) 即可，改动很小。
3. 用户关服务窗口时，代码先 settingsWin.close() 再 await flow.stop()。服务窗口已经是最后一个窗口时，Electron 默认的 window-all-closed 退出与这个 await 存在竞争；这个次序是合同 Step 9 写死的，而且在本片之前服务窗口本来就是最后一个窗口（同样的竞争已经存在），所以不算本片引入的新风险，只是验收端做 D16 时值得看一眼服务进程有没有干净退出。
4. 白盒测试文件与 mutation-spec 按战后门禁的定位只用于本次核验、不进仓库：前端的行为级回归保护只剩执行端那份 vitest 用例。若站主希望把白盒边界也留在仓库里（例如让 T060 门禁文件覆盖前端静态边界），那是另一次范围决定，不该由本片顺手塞进候选。

## 8. 结论

通过。候选可以进入集成；D16 真窗口冒烟按合同留给验收端；第 7 节四条是不挡的意见，不构成打回理由。

Verdict: PASS
