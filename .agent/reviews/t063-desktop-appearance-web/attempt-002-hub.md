# 复审记录：t063-desktop-appearance-web attempt-002（七端信箱 hub）

- 合同：t063-desktop-appearance-web.v2（base 52482ea9f708ca5d91b13f16a830c9a0aa66d730）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261120T044300894058Z-4faf），终审报告如下

## 终审报告

# T063-7-audit-post 终审报告（audit-sonnet，2026-11-20，attempt-002）

## 结论

**通过，不退回。** 候选（返工基线 52482ea9，本轮零改动）逐条满足合同 v2 的 DoD 与 Behavior contract；内核的六条必要检查全绿；战后门禁 19 条变异 19/19 被抓住；执行报告与内核记录逐条对得上，没有自述不实。D11（真窗口冒烟）按合同属 review 侧证据，站主 2026-11-20 的记录对本次逐字未变的实现有效。另有两处不挡的意见（第五节），不构成阻塞。

## 一、候选是什么

- attempt-002 的 candidate.patch 为 0 字节、scope.json 记 A0 M0 D0、head_after=52482ea9：候选就是返工基线提交（内核把 attempt-001 的 9 个文件搬到新基线上），本轮执行端没有再改任何文件。
- 9 个文件（attempt-001/candidate.stat.txt 与 changes.json）：7 个源码 + 2 个新测试，全部在合同 Scope 的允许集内；desktop/shell/**、SettingsView.tsx、T032 冻结名单里的文件一个字没碰。

## 二、DoD 逐条独立核对（以源码为据，不看自述）

| DoD | 我核到的事实 | 结论 |
|---|---|---|
| D01 密度唯一写入口 | theme.ts 的 applyDensity 只碰 document.documentElement 的 data-density：standard→removeAttribute、compact→setAttribute('data-density','compact')；无 classList/className/.style/document.body/存储/matchMedia；applyTheme 原样未动；头注释已改成「偏好由桌面外壳保存，页面只持有当前值」 | 满足 |
| D02 紧凑行高 | Table.css 现有三条之后追加三条 `:root[data-density="compact"] .tt-table[data-row-height="N"] td { height: 32/36/44px; }`，逐字带同行非空出处注释，只作用于 td；特异性 (0,4,1) 高于标准规则 (0,2,1) 且位置在后，紧凑压得住、表头 th 不受影响 | 满足 |
| D03 外壳页读+订阅 | shellBridge.ts：能力判据是十成员齐全（isCompleteShell）且 getAppearance 是函数；readAppearance 逐字段校验（theme 非法→dark、density 非法→standard，同步读不整体回 null）；抛错/回值非对象→null；shellOnAppearance 走原对象 on('appearance')、退订真退（live 标记并调 off）；SHELL_MEMBERS 与 isCompleteShell 未动，十成员旧壳仍算有外壳 | 满足 |
| D04 服务窗口读+订+存 | hostSettings.ts：hostGetAppearance/hostOnAppearance/hostSaveTheme；缺能力→null/空退订；saveTheme 只转交 pref 一个实参、结果包成 Promise、信封不拆；调用抛错→null；T060 S06 的记号（hostOpenSettings、themisHost、openSettings、typeof !== 'function'）保留 | 满足 |
| D05 起步+跟事件变 | App.tsx：懒初值 host→shell→缺省暗/标准，读外观只在这一步做一次；根上 useEffect 按 source 订阅、卸载退订；事件逐字段校验（非对象实参整个忽略、非法字段只忽略该字段）；useLayoutEffect 写主题与密度；桩模式根元素不多属性、只改内存、不写存储 | 满足 |
| D06 三档保存 | App.tsx 的 changeTheme：hostSaveTheme 非 null→调它，信封 ok===true 才切；否则 shellBridgeInstance() 非 null→saveSettings({theme:pref}) 兑现才切；两档都没有→只改内存；失败保持原主题、错误被吞（不弹提示） | 满足 |
| D07 类型与外壳 | themisShell.ts 只多了一个 export interface ShellAppearance（字段逐字），interface ThemisShell 仍恰好十成员、文件仍只导出类型；desktop/shell 未改；V02 build 绿、V04 # pass 336 # fail 0 | 满足 |
| D08 README | README.md:59 改掉了「偏好只存内存」，写清外壳保存（宿主 saveTheme／桥 saveSettings）、启动同步读、成功保存后广播、紧凑 40/44/52 各降 8 成 32/36/44；「主题」「标题栏」两词保留 | 满足 |
| D09 范围 | 改动 9 个文件全在 allowed 集合；未改任何既有测试/门禁、未退役过渡断言；R01 全量 1195 passed（T012 的两条过渡断言与 T032 的 S09 冻结名单都在其中） | 满足 |
| D10 用例与门禁 | 两个新测试文件随 V01 跑：appearance-units 17 例 + appearance-app 14 例（V01.log 逐条列出），G01 11 passed；覆盖 applyDensity、三条紧凑规则、shellBridge/hostSettings 的失败分支、App 的桩模式/服务窗口/外壳页/事件对齐/三档保存/非法取值/useLayoutEffect 静态断言 | 满足 |
| D11 真窗口冒烟 | 只能人工审阅，见第三节第 3 条 | 由站主记录承担 |

## 三、终审的几项专门核查

### 1. 全绿不等于对
- 对测试输入硬编码：两个新测试装的是假宿主/假外壳对象，断言打在真实模块与真实 html 属性上，没有把业务逻辑抄一份进测试；宿主回值非对象、字段非法、空对象事件、退订后不再收都是行为级断言。
- 空的异常处理：theme.ts / shellBridge.ts / hostSettings.ts 的 catch 都有合同要求的语义（回 null、回缺省、空退订），不是把异常吞掉装作成功；App.tsx 保存失败的分支是合同明写的「保持原主题、不弹提示」。
- 为过测试而写的特判：App.tsx 没有针对测试输入的分支；桩模式与真实模式走同一段代码；桩模式用例与真实宿主用例的断言形式一致。
- 悄悄扩大的范围：见第一节；9 个文件之外无改动。

### 2. 执行概述、内核记录与 JEV 的对账
- attempt-002 无新改动，自述与 scope.json（A0 M0 D0）、changes.json（空数组）一致。
- events-summary.json：suspicious_commands 空、temp_path_uses 空、outside_worktree_paths 空；6 条「掩盖退出码」的命令都是 git log/status/diff 与 grep 这类查看命令，不是检查命令；被忽略的新增路径只有 .pytest_cache、desktop/web/dist、ts/**/node_modules。
- 自检数字与内核日志对得上：V01 143 个测试文件（含 appearance-app 14 例、appearance-units 17 例）、V04 # tests 336 / # pass 336 / # fail 0、G01 11 passed、R01 1195 passed（内核在固定候选上跑的是合同的 60 份命令）。
- 唯一偏差：执行端自选的 R01 只跑了 56 份（1136 passed，跳过 T001 纯 Markdown 门禁），与合同命令不同；内核已在固定候选上跑全量，且执行端受「不跑全量」的指令约束，不构成阻塞。
- 主工作区 AGENT_LEARNINGS.md 在运行期间被改：不在候选的 9 个文件里；执行端全程在自己的 worktree、事件流中没有写主工作区路径，判断不是执行端写的；只作记录。

### 3. D11 的独立结论（任务书点名要的一项）
- 合同 D11 的证据栏写的是 review；站主 2026-11-20 来信已把 attempt-001 的候选与 T065 的修复合在一起跑过真窗口冒烟，三段 25/25、8/8、9/9 全过，并逐项列了首帧亮紧凑、紧凑行高 32/36/44、两窗双向跟随、标题栏存主题、重启读回、缺省暗标准都成立（见合同「站主决定」）。
- attempt-002 的实现与 attempt-001 逐字相同（返工基线就是 attempt-001 的候选搬运，本轮零改动；返工基线与 attempt-001 的差别只有门禁测试文件的读法热修补），因此该记录对本次候选有效。
- 冒烟脚本 ui/smoke61_chain.sh 不在仓库里，我无法复跑；jsdom 量不出真实行高与首帧不闪，这一项在仓库内不可机械验证，只能由站主的真窗口记录承担。
- 结论：D11 接受站主 2026-11-20 的记录作为证据；执行报告把 D11 标 done 并注明「证据属 review 侧」，与合同的证据栏一致，不算自述不实。

### 4. 战后门禁的声明逐条裁定
- 19 条变异逐条临时套用后 19/19 非零退出（mutations.json：caught 19 / missed 0 / skipped 0 / error 0，各条 count_found = count_expected = 1），无 equivalent、无 unmutated：声明属实。
- 7 个改动的非测试文件每个至少一条变异，接线/挂载类也在内（M09 事件名改错、M13 来源判据取反、M17 摘掉 applyDensity、M18 拆掉根上订阅、M06 绕过十成员核对）：没有测不出来的空档。
- 门禁端声明等价的两处执行端解读：单一 appearance 状态对象（合同写「两个状态」，行为等价，D05 全满足）；订阅绑定初读选定的 source（合同字面是「优先 hostOnAppearance，没这个能力再 shellOnAppearance」）。见第五节第 1 条。
- 门禁端把 D11 留给 review 侧，与我的独立结论一致；战后白盒与变异清单只用于本次核验、不进仓库，我不对它们提「应当留在仓库」的意见。

## 四、JEV 三项【需关注】的独立结论

1. 自行解读合同 p=0.92：判据说执行端「没有把它列成冲突或提问」，但执行端确实在 interpretations 里逐条列了并给了理由，报告与事件流对得上；合同本身也把命名与函数拆分这类实现细节豁免。两处解读我逐条核过（第五节），不成立为退回理由。
2. 自述完成而无证据 p=0.91：我把 D01–D11 的自述与内核日志、源码、白盒与变异记录逐条对上，只有 D11 的证据来自 review 侧（站主记录在合同里可查），其余每条都有可核证据。不成立。
3. 误导程度 2.26/3：按「独立检查发现不了、且会改变结论」的口径查了三处：首帧不闪与真实行高（只有站主真窗口，已由站主记录覆盖）；「读外观只做一次」（实现确实只调一次）；桥档 saveSettings 被拒的分支（仓库用例与仓库门禁都没单独覆盖，但战后白盒覆盖了、变异 M16 把它抓住，行为正确）。第三处是覆盖缺口而不是缺陷，见第五节第 2 条。

## 五、不挡的意见（不构成阻塞项）

1. 订阅来源绑在初读选定的 source 上，与合同字面有一种形态不同：宿主有 getAppearance、没有 onAppearance、且外壳桥同时在时，合同字面会退回订阅桥，候选实现会拿到空退订等于不订。现实中宿主九成员成套、外壳十一成员成套，两个桥不同窗（服务窗口只有 themisHost，外壳页窗口只有 themisShell），合同也未定义这种病态形态，战后门禁未对该形态设断言。建议以后要么在 hostSettings 侧暴露「有没有 onAppearance 能力」的判据，要么在合同里把该形态定死；本片不改。
2. 桥档 saveSettings 被拒（保持原主题、不弹提示）这一条仓库里没有回归用例：候选的 appearance-app.test.tsx 只覆盖桥档兑现（宿主档的 ok:false 与被拒有覆盖），tests/test_gate_t063_baseline.py 的 app 探针同样只覆盖桥档兑现。战后白盒（本次核验用、不进仓库）覆盖了它，变异 M16 也把它抓住，行为经两路验证正确。若要长期防回归，建议把这条补进 desktop/web/tests/appearance-app.test.tsx 或门禁基线。
3. 门禁文件 tests/test_gate_t063_baseline.py 的模块 docstring 仍写「合同 v1、基线 9da7f2a3」，纯文档遗留（一审已记，不据此打回）。
4. 合同预算：attempts 4 已用 2 次（attempt-001、attempt-002），还剩 2 次；累计墙钟 7500 秒已用约 3780 秒（1800 + 1978），够再走一次完整单轮。

## 六、只读

本回合只读：读了合同 v2、7 个改动源码、2 个新测试、README、内核 checks 与门禁/白盒/变异记录、执行报告与 JSON、events-summary、JEV 与一审报告；没有改任何文件、没有跑命令。

Verdict: PASS
