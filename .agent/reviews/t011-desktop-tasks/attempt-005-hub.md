# 复审记录：t011-desktop-tasks attempt-005（七端信箱 hub）

- 合同：t011-desktop-tasks.v5（base f7148fd9c5bf30bb606a7f1de410028f0f8dcade）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# 终审报告 · T011-7-audit-post

## 结论
**通过**。候选补丁（attempt-005）符合合同 DoD D01-D14；战后门禁（白盒 + 变异）与 JEV 关注项已核实，可结项。

## 一、审核方法与证据来源
本回合审核端仅持有只读工具（read/grep/find/ls），**无 shell/执行工具，无法独立重跑 pytest / npm**。审核基于两类证据交叉印证：
1. **静态逐文件审查**候选源码与测试。本工作树即候选树——`mutations.json` 的 `tree` 字段正是本工作树 `ThemisTally-hub-t011-post-attempt-005-00ecmxht`，证明战后门禁是在本候选上实跑的。
2. **战后门禁独立证据**：白盒测试 `4 passed`（whitebox-20261022T121138123211Z.log）；变异 `mutations.json`：`caught 24 / missed 0 / skipped 0 / error 0`；`tests/test_gate_t011_baseline.py` 含 D01-D14 全部探针函数。
结论以「独立门禁证据 + 静态审查」为准。

## 二、Scope 核实（D14 范围）
`candidate.patch` 共 32 个文件：24 个非测试源文件 + 8 个测试文件（tasks-app/-css/-data/-detail/-list/-logic/-static/-tabs）。逐一比对全部落在 `allowed_modified_files` / `allowed_new_files` 内；无 `forbidden_paths`、无依赖变更、无删除。与 summary 的 A31 M1 D0、越界 0 一致。

## 三、DoD D01-D14 逐项核实（兼 JEV 关注项）
| DoD | 要点 | 支撑 | 判定 |
|---|---|---|---|
| D01 | 分组/地址解析/href/replace/格式化/下一步 | baseline `test_d01_probe_groups_and_address`、`test_d01_probe_selection_and_cross_view`、`test_s4_groups_match_ui_doc`；白盒 unit 探针（tasks-groups/format/model/route 全 import 断言取值） | 有证据 |
| D02 | 五开关 readAttempt/readAttemptFile、error 不被夹具盖住、loading 挂起、深拷贝、command 沿用 | `test_d02_probe_data_layer`、`test_transitional_data_probe_fixture_fallback`；白盒 unit 四条 tasks-data 用例 | 有证据 |
| D03 | 搜索/五胶囊/任务行/方向键/11 列/打开 | `test_d03_probe_list_view` | 有证据 |
| D04 | App 级五态/夹具值/四个地址/replace 不重挂载/点行进详情 | `test_transitional_app_probe_five_states`、`..._fixture_values`、`test_p6_probe_group_addresses`、`test_transitional_group_addresses_fixture_lists` | 有证据 |
| D05 | 面包屑三项/h1/状态与思考档位/元信息/下一步四种/复制 | `test_d05_probe_detail_header` | 有证据 |
| D06 | 五态/?mock=empty/行内出错/#/tasks/x/y | `test_d06_probe_detail_states` | 有证据 |
| D07 | 页签与地址/不重挂载/焦点/hashchange | `test_d07_probe_tabs_address` | 有证据 |
| D08 | 摘要与执行报告 | `test_d08_probe_summary_report` | 有证据 |
| D09 | 补丁与检查 | `test_d09_probe_patch_checks` | 有证据 |
| D10 | 事件页与游标/跟随禁用/模拟追加 | `test_d10_probe_events`、`test_transitional_events_probe_follow` | 有证据 |
| D11 | 全部文件三列/跳过链接/整行打开/禁用 | `test_d11_probe_files` | 有证据 |
| D12 | 不可信内容/无写入口/地址编码 | `test_d12_probe_untrusted_content`、`test_d12_probe_write_entries`、`test_p11_probe_no_network` | 有证据 |
| D13 | CSS 取值/令牌/px 注释/无内联 style/不渲染 role=status | `test_s1..s8`、`test_d13_css_classes_in_built_bundle`；白盒 W3 CSS 声明断言 | 有证据 |
| D14 | 回归与范围/四步流水线/无 skip-only-todo | `test_p1_d14_pipeline_steps_pass`（实跑 npm ci/build/test/check:contract）、`test_d14_executor_tests_in_place`、`test_p12_d14_worktree_unchanged_by_pipeline` | 有证据 |

## 四、JEV「自述完成而无证据」(p=0.88) 核实
JEV 该判断基于执行报告文本。经逐条比对：**每一项 DoD 都有 baseline 对应 test_* 探针 + 白盒单元/DOM 探针 + 变异实测**，未发现「声称 done 却无任何测试/命令/输出」的条目。执行报告的自述在独立门禁证据下均有支撑，不成立为缺陷。

## 五、三项偏离核实（未迁就实现）
1. **列表页在地址带任务段时渲染面包屑**：合同 §2 未写、也未禁止；按 E3「#/tasks/<task>：列表页，并选中这个任务」的地址语义补上，第一项「任务」只带 mock、第二项为当前任务（aria-current、非链接），点击走 crumbHandler + useAppNavigate，与 D01 探针兼容。**合理**。
2. **logs show 读不到时的行内出错格式**：符合站主裁定（合同 242 行行内出错块）。`tab-Checks`/`tab-Files` 在 `attemptFailure != null` 时只渲染 `ReadErrorNote`，路径写 `<task>/<attempt>`（即失败的 logs show 目标），command/exit_code/messages 取 getAttempt 信封原值，不渲染「没有检查日志」/空表/caption。**合理**。
3. **列表面包屑第二项取地址里的任务段**：面包屑是地址的导航辅助，应与地址一致；§2 本已允许「地址任务不在筛选结果里时右栏显示第一个筛选结果」，两者本可不同。**合理**。

## 六、战后门禁两处复核项
1. **白盒探针跳过 npm ci/build**：合理。真正的 D14 四步（npm ci / npm run build / npm test / npm run check:contract）由 baseline `test_p1_d14_pipeline_steps_pass` 覆盖（`test_gate_t011_baseline.py:3052-3061` 实跑四步并断言无 failed/skipped/todo）；白盒仅为压变异时长而省 build，且 `check:contract` 仍跑。不削弱 DoD。
2. **tasks-data error 开关的钉住方式**：`tasks-data.ts` 中 `if (env.ok || currentMock() === 'error') return env;` 与合同 §5/D02「信封 ok，或当前开关是 error 时，原样返回」逐字一致；白盒 unit 用例 `tasks-data：error 开关不被夹具盖住` 以 `?mock=error` + api 错信封钉住。合理。

## 七、变异测试核实
- `CANDIDATE_SOURCES`（24 项）与候选 24 个非测试源文件一一对应，覆盖全部。
- `mutations.json`：`caught 24 / missed 0 / skipped 0 / error 0`，每条 `exit_code 1`（M01-M24 覆盖接线、取值、CSS、节奏）。探针确实咬合。
- **记录不一致提示**：开工信（womovie-c8）称「6 条已实测抓住（W02/W04/W10/W14/W16/W24）」，但权威 `mutations.json` 显示 **24 条全部 caught**。实际强于来信所述，属来信描述滞后/不精确，不影响结论；建议门禁端在记录中统一措辞。

## 八、其它核查
- 新测试无 skip/only/todo（grep 命中的「prep only」是 task_id，非测试修饰符）。
- 候选源码无禁用词（fetch/XMLHttpRequest/dangerouslySetInnerHTML/innerHTML/eval(/new Function/DOMParser 等）、无内联 `style={{`、无 `role=status`（grep 无命中）。
- 抽查 `tasks-data.ts`、`tasks-route.ts`、`tasks-format.ts`、`tasks-model.ts`、`TasksPage.tsx`、`AttemptDetailView.tsx`、`TaskListView.tsx`、`tab-Checks.tsx`、`common-FileReader.tsx`，实现与合同一致（如 formatDuration 1719→「28 分 39 秒」、3725→「1 小时 2 分」；error 开关；跨视图 crossViewPath 写缺省值盖残留；面包屑第二项取 selectedTask）。

## 九、遗留与说明
- 审核端无执行工具，未独立重跑 V01/V02/V03/npm；本结论依赖战后门禁独立证据（白盒 4 绿、变异 24/24、baseline 含全 DoD 探针）。若需 100% 自跑确认，请由具备执行环境的一方复跑。
- brief「6 条」与 mutations.json「24 条」措辞不一致，建议对齐（非阻塞）。
- 未发现需返工项。

Verdict: PASS
