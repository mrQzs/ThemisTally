# 复审记录：t023-desktop-ui-writes-b attempt-001（七端信箱 hub）

- 合同：t023-desktop-ui-writes-b.v1（base 5edda28f31c8e107d93a800deda2acb2d51afdcf）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261026T211348331535Z-0a0c），终审报告如下

## 终审报告

# T023-7-audit-post 终审报告

## 结论：通过

候选 `t023-desktop-ui-writes-b.v1.a001`（树 23b7a428，基线 5edda28f）忠实实现合同，无越界、无弱化测试、无为过测试写的特判。门禁端无候选缺陷申报；6 处「预期抓不住」的变异逐条复核全部成立且各有另一条命令兜底。

## 一、补丁源码审查（先读源码，再看检查记录）

逐行读 candidate.patch（16 改 + 3 新，19 文件，与 scope.json A3 M16 D0 T0、越界 0 一致），对照合同逐节核对：

- **§1 api.ts**：`WriteAction` 恰七成员；四个写函数签名与一对一转交照合同；13 读函数、A 片四写函数、既有类型未动（仅改了两处描述性注释，非迁就门禁解析，不触 Forbidden）；无联网词。
- **§2 mock/writes.ts**：新增 `opArgs` 表只记四个新 action；`confirmWrite` 三查（号在表 / action 符 / args 符，`sameArgs` 比键数加逐键）任一不符 → 409、`exit_code: null`、原文逐字照 A 片 expired；**错配不删表项**（409 不消耗确认号，与战前审定口径一致）；A 片 `mockGetOperation` 反推逻辑保留（`opArgs.get(id)?.args ??` 回落，A 片 action 不进 opArgs，行为不变）；baseArgv 四分支照服务侧 `buildWriteArgv`。
- **§3 in-use**：第 20 个情景；执行 200 ok:false 退 1；`terminalEnvelope` 与 `mockGetOperation` 都接了 in-use → failed/exit；对 `config.rollback` 与 A 片三个 action 的回落消息与既有 exit1 消息**逐字节相同**（`ERROR 内核拒绝：profile step-low 不存在`，已在候选树核对 :160 与 :176），符合战前门禁「照 exit1」的既定解读。
- **§4 文字与危险样式**：`WriteSpec.title` 改可选，`open` 里 `spec.title ?? titleOf(...)`、`setDanger(dangerOf(...))`；标题/摘要/轻提示八个模板逐字照合同表格；文字表并进 `useWriteFlow.ts`（合同明文允许，allowed_new_files 不含 writeTexts.ts，解读成立）；Footer `const confirmVariant = danger ? 'danger' : 'primary'` 用满五个状态，终态按钮照 A 片；`Changes` 空变化先 summary 再回落「预览没有列出变化」（不含「没有变化」子串）；审计号未编造。
- **§5 内核原文**：三条逐字，只写在 `src/mock/writes.ts`。
- **§6 快照（按战前须知逐字段核对 D10）**：preset.remove `{active_preset, presets[].{name,active}}` 排除 description/roles；profile.remove `{id}` 排除含 adapter 的六字段；runtime.remove `{id,adapter}` 排除 source/notes/command；rollback 五读并行、roles `{role,explicit,binding}`、presets 含 roles、profiles 含 credential_env 不含 adapter、runtimes `{id,adapter}`、plugins `{id,enabled}`，整份 history 不进快照——与合同表格完全一致。`writes-snapshots-b.test.ts`（11 条）与白盒 W09 两处都核过。
- **§7 四入口**：方案表非当前行 ghost/sm Button、当前行照旧纯文本「当前方案不能删」（候选树 :86–88 核实）且不渲染按钮；profile 表 [删除] ghost/sm、[编辑] 照旧禁用；运行时 [删除…] ghost/sm、[探测][模型] 照旧禁用；历史抽屉本机文件**优先**走 DisabledAction（reason 逐字）+ RotateCcwIcon 16，非本机 Button secondary/md + 图标 16、`String(number)`；三处 reload 转交链与 `reload?` prop 齐；`WriteFlow` 各挂一份；`applyFinal` 顺序未动（W3 照 A 片）。
- **§8/§9**：readonly 视图对 api 只有 `import type`；无 fetch 等四词；A 片四份 writes-* 测试一字未改。

**硬编码/特判/空 catch/悄悄扩围检查**：previewData 对 #42 给空 binding_changes 是合同明文要求，非特判；`plugins.plugins ?? []` 是无害容错；新测试走真实 api/mock 逻辑（ghost 确认号、错对象、错 action 都断 409），无对测试输入的硬编码放行；无空异常处理。

## 二、D13/D15（门禁测不了的两条，看 diff 与执行报告）

- 四份既有测试的改动恰为合同点名的断言：page-app 写入口 12→9、9→6、总览 0；readonly2-app 抽屉禁用 `['回滚到这一条之后']`→`[]`、白名单补「回滚到这一条之后」（合同 D13 明列；该用例不开抽屉故为防御性放行，不削弱保护）；page-runtimes [删除…] 可点、其余仍禁用（逐按钮断言，非删除断言）；readonly2-history #8 可点 + 样式三条保留、#4 禁用断言**新增**。无删用例、无 skip/only；「删除 6 行断言」逐行核过，全部是被替换的旧断言。page-roles 未改（其断言仍成立）。
- D15：无越界；摘要标的可疑命令 `rm -f src/writes/writeTexts.ts` 是执行器删自己中途创建、随后并入 useWriteFlow.ts 的草稿文件，最终候选无此文件、无删文件（D0），不构成违规；执行报告称无 /tmp 固定路径临时文件，diff 中无临时残留。
- 摘要的 changed_files JSON 多列 `RolesPage.tsx`，实际补丁未碰（与战后门禁发现一致）；以 candidate.patch 为准，属报告笔误，不影响 D14（scope 检查 A3 M16 D0 T0、越界 0）。
- 运行期间主工作区 `AGENT_LEARNINGS.md` 变动：不在候选补丁内、scope 越界 0，非执行器写入候选的证据；留档备查，不挡。

## 三、检查与门禁记录核对

- 执行端自述：V01–V04、G01（20 passed）、R01（713 passed）全绿。
- 战后门禁独立复跑：白盒 23 passed；vitest 97 文件/893 用例全绿；G01 复跑 19/20（P10 红为 mutation-spec.json 中途落盘的自扰，非候选问题，解释成立）；变异 20/20 全抓、`--check-anchors` 全 OK。执行自述与门禁独立记录相互印证，JEV「自述完成而无证据 p=0.91」不成立——每条 DoD 都有 V02/G01 落点且被门禁复跑证实。
- JEV「自行解读合同 p=0.94」：执行器两处解读都写进了 interpretations 且都被合同原文认可（«或并进 useWriteFlow.ts»；D13 明列白名单补条），战后门禁亦核过，不构成未申报的自行解读。

## 四、6 处「预期抓不住」的变异逐条裁定（全部成立）

| 变异 | 漏的命令 | 复核结论 |
|---|---|---|
| M02 api 去 mockRollback import | W1 | 成立。W01 的 `return mockRollback(number, confirmation)` 正则与 `\bmockRollback\b` 都被残留的函数体满足，静态测不出 import 缺失；V1 运行时 ReferenceError 抓住（writes-rollback 全红）。 |
| M18 RuntimesView 去 useWriteFlow import | W1 | 成立。W07b 断言的 `useWriteFlow(reload)`/`<WriteFlow flow={flow} />` 使用处文本仍在；V1 渲染即 ReferenceError 抓住。 |
| M13/M14/M15 三处 reload 转交 | V1 | 成立。所有 vitest 用例把 reload 直接注入组件（ProfilesHarness、HistoryView 直渲染），没有一个用例经 Page 层走转交链；静态夹具下 reload 与不 reload 数据相同，行为不可见。W08 三条字面量断言抓住。 |
| M19 reason 换「第二阶段接入」 | V1 | 成立。DisabledAction 的 reason 只进 Tooltip（title），不进 textContent；且「本机文件不存快照，不能回滚」同时由 history-logic.ts:94 的 rollbackNote（禁改文件，未动）渲染在抽屉底栏，故所有文字断言在变异下照样通过。W07c 的 `reason="…"` 字面量断言抓住。 |

六处均另有命令兜底，`unexpected_missed` 双命令皆空，无「测不出」的死角；承重件是 `tests/test_gate_t023_whitebox.py`（不得退役或放宽，已写进下游须知）。门禁端无「没法变异」的改动文件申报（12 个非测试改动文件全有变异覆盖）。

## 五、不挡的意见（留档）

1. M19 暴露的通用弱点：悬停提示类断言在 jsdom 下只能测到 title/tooltip 或静态源码，后续片若新增 DisabledAction reason，建议用例直接断言 `Tooltip` 的 content 或保留静态断言双保险。
2. `mockGetOperation` 的 A 片 args 反推（`{name:'economy'}`/`{id:'code-change'}`）是演示用魔数，本片按合同未动；将来做真网络客户端时整段会退役，无需现在处理。
3. 执行报告 JSON changed_files 与实际 diff 有一处不一致（RolesPage.tsx），建议执行器模板以 `git diff --stat` 生成该字段。

## 六、裁定

- 门禁端申报的候选缺陷：无。
- 阻塞项：无。
- **结论：通过。**

Verdict: PASS
