# 复审记录：t053-desktop-web-preset-save attempt-002（七端信箱 hub）

- 合同：t053-desktop-web-preset-save.v2（base 6f53dbb514dad1e18bf6ba25a4048326df62b21c）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261118T145959796779Z-6a59），终审报告如下

## 终审报告

# T053 终审报告（audit-sonnet）

结论：通过。

## 一、审读对象与候选状态
- 本回合候选补丁是空的：attempt-002/candidate.patch 0 字节，scope.json files 空（A0/M0/D0/T0），summary 写明执行端本轮零文件改动。实现来自 attempt-001 的改动，已随基线 6f53dbb5 落在工作目录；门禁端的热修补只动 tests/test_gate_t053_baseline.py（执行端 forbidden），不在候选里。
- 所以本轮终审的实际对象 = attempt-001/candidate.patch 的 14 个文件 + 工作目录里的当前源码。我逐个读了源码，不只看补丁。
- 改动集合（与合同 Scope 逐个对得上，无越界）：desktop/web/src/api.ts、src/mock/writes.ts、src/pages/RolesPage.tsx、src/writes/useWriteFlow.ts、src/writes/PresetSaveForm.tsx（新）、desktop/web/tests/page-app.test.tsx、desktop/web/tests/writes-hub-bind.test.tsx、desktop/web/tests/writes-preset-save.test.tsx（新）、tests/test_gate_t009/t024/t038/t045/t048/t051_baseline.py。

## 二、DoD → 测试 → 断言 对照表
| DoD | 由哪条测试的哪个断言证明 | 判断 |
|---|---|---|
| D01 | V01(a)：入口 disabled=false、data-variant=secondary、data-size=md；G01 S05 静态钉 RolesPage 换入口且并行四读/失败判定/load/children/页头说明/四个禁词/api 读函数白名单一字不改；t009/t024 探针：页头次序 [保存当前为方案… , 新建 profile, 刷新] | 成立 |
| D02 | V01(a)：只列读到的两个 explicit 角色、缺省全选、预览 args 的 roles 恰是这两个；V01(b)(e)：不合法不发预览、一个都没勾给原因句、没有显式绑定给原因句；G01 form 探针同款断言 | 成立 |
| D03 | V01(b)：Bad Name 当场错误句 + 不发预览；说明 201 码点错误句；V01(c)：重名显示会覆盖方案 default、不勾覆盖不可确认且不发预览、勾了正文 force 是布尔 true、改名复位覆盖勾选 | 成立 |
| D04 | V01(d)：先关表单再开确认框（标题 保存方案 demo-save？）、POST /api/v1/presets/demo-save/save 正文无 name、带 roles/description/confirmation、变化区摘要 方案表里加上 …、成功轻提示、reload 被调用；V01(d2)：覆盖流摘要与正文 force === true | 成立 |
| D05 | G01 S02/S03/S04 静态钉（api 三处、桩四处、三张文字表 + readSnapshot + 执行分派排在兜底之前）；战后白盒 W01–W08 行为钉；25 条变异逐条实测被唯一命令抓住 | 成立 |
| D06 | V01 8 条用例 (a)–(g)，无 skip/only/todo，渲染真实组件、看真实请求正文，不抄业务逻辑 | 成立 |
| D07 | 补丁逐处核对：t009/t024/t038/t045/t048/t051 与 page-app/writes-hub-bind 只改合同写明的那一处，其余没动；R01 51 份全过（1093 passed）证明没有漏网的旧口径 | 成立 |
| D08 | scope.json violations 空、warnings 空；补丁文件清单 14 个，与 allowed_modified_files/allowed_new_files 逐个对得上，没碰 forbidden_paths | 成立 |
| D09 | V02 1287 passed、V03 退出码 0、V04 built in 1.61s、R01 1093 passed | 成立 |

## 三、源码审读：是否忠实于合同
- 入口（PresetSaveForm.tsx / RolesPage.tsx）：页头第一个按钮换成 PresetSaveAction（secondary/md、任何态都可点），RolesPage 只删 DisabledAction 的 import、加 PresetSaveAction 与 roleName 两个 import、页头一行；并行四读、失败判定、load、children 行、页头说明、四个禁词、../api 的读函数白名单一字未动。角色中文名走 prop，src/writes 不跨层引 src/pages。
- 表单：内外两层（内层只在打开时挂载，关掉即丢弃未保存取值）、四个字段、逐字提示句全部在位、预填按当时读到的数据、方案名一改即复位覆盖勾选、canPreview 六项、[确认…] 门控含 current/result.ok/onClose、先关表单再 start、底部复用 hub-bind-form.css 的 hb-* 类（类名逐个核对都存在）、没有内联 style、没有写死颜色、没有禁词。
- 参数与接线：writeArgs 加了一条 force 规则（只有字符串 true 转 JSON 布尔 true，排在数字兜底之前，number/cadence_seconds/asNumber 的既有规则没动）；savePreset 真实模式路径 /api/v1/presets/<name>/save、正文 { ...writeArgs(w), confirmation } 且 w 不含 name，桩模式走 mockSavePreset；桩的 baseArgv 分支逐字照服务（--description=/--roles=/--force）、NEW_ACTIONS 加成员、previewData 分支在 role.set 之外、mockSavePreset 走 confirmWrite；useWriteFlow 三张文字表、readSnapshot（getPresets + presetRemoveSnapshot）、执行分派排在 setPluginEnabled 兜底之前，dangerOf 未动。
- 没有为过测试写的特判、没有把业务逻辑抄进测试、没有空异常处理：预览/执行失败、读不出、服务报错都走既有分支并显示原文。

## 四、检查与门禁记录核对
- 独立日志（attempt-002/checks/01/）：G01 10 passed；V01 8 passed；V02 1287 passed；V03 无输出退出码 0；V04 built in 1.61s；R01 1093 passed in 1242.10s。与执行报告的自述一致。
- 战后门禁：白盒 10 passed；mutations.json 里 25 条 status 全为 caught，files_left_modified 空、not_run 空，没有 equivalent、没有 expect_missed；5 个非测试文件全覆盖（api.ts 5、mock/writes.ts 7、useWriteFlow.ts 5、RolesPage.tsx 2、PresetSaveForm.tsx 6）；既有 8 份测试文件按仓库惯例不配变异（它们由 V01/V02/R01 覆盖，合理）。
- 门禁端自述 api-save-body 曾静态漏网、改成在 savePreset 函数体切片里钉：我核了实现里只有 savePreset 一处 { ...writeArgs(w), confirmation } 形态（其余写函数各有自己的 w 变量），锚点唯一性成立，这一条我没有异议。
- 本回合输入没有‘门禁端举证的候选缺陷’一节，门禁端 candidate_defects 为空，与我的源码审读结论一致。

## 五、执行报告自述与内核摘要线索逐条对账
- 可疑命令 rm -f .g01.log .r01.log; git status --porcelain=v1 --untracked-files=all; echo clean：删的是执行端自建的日志文件，位置在工作目录内，与自述‘自建日志文件已删除、git status 干净’对得上。
- 新增被忽略路径：.pytest_cache/、desktop/web/dist/、ts/node_modules/——都是 gitignore 的测试产物与依赖目录，不是越界改动（scope.json violations 空）。
- interpretation_mentions 1 条：执行端最后一条消息里的‘合同矛盾与自行裁定 → contract_conflicts：无’段落被解析器当成解读，内容与执行报告一致，属解析误报，不是漏报解读。
- D01–D09 的自述与日志、补丁逐处核对都对得上，没有‘报 done 但实际没做’的情况。

## 六、发现（不挡，供站主决定）
1. 表单一打开、方案名还空时就显示‘方案名要填’；合同逐字要求空名给这句，实现合规，但与 T052 HubBindForm（不合法才提示）的手感不同。若想更顺，可加一个‘用户动过该字段’的门（多十来行）。
2. 底部错误行 hb-preview__error 没有包在 .hb-preview 容器里（T052 的 HubBindForm 是包着的），只是少一点行间距，可读性不受影响；执行端已在报告里记了这条。
3. 门禁 S01 的正则没收尾引号（preset.savex 也会命中）——一审已记为非阻断，风险由 S02 的 WriteAction 断言与 V03 typecheck 兜住。
4. 执行报告写 R01 用时 1250.45s，日志是 1242.10s；结论（1093 passed 全过）一致，属自述数字的小出入。
5. 合同 D09 写‘52 份既有门禁基准’，而 R01 命令实际列 51 份（t001–t028、t030–t052；仓库里没有 t029）。执行端按 51 份报并跑齐，是合同措辞与检查不一致，不是候选缺陷。

## 七、结论
实现忠实于合同 v2，DoD 逐条有测试与断言兜住，六项检查与战后门禁记录互相印证，无越界、无弱化测试、无为过测试的特判。结论：通过，不退回任何一端。

Verdict: PASS
