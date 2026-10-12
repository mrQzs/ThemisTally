# REVIEW：【task-id】 v【N】 · 【attempt-NNN】

Verdict: 【PASS | ACCEPTED_WITH_EXCEPTION | REVISE | BLOCKED | ESCALATE 中的一个】

<!-- 保存为 .agent/reviews/<task-id>/<attempt>.md。上面的 Verdict 行只能写一个结论，
     并且必须与 verdict 命令的 --verdict 参数一致。 -->

## 基本信息
- 基线：`【base_sha】`
- 候选树：`【candidate.json 中的 tree】`
- 要求的执行模型：【provider/model · thinking high】
- 实际模型：【events-summary 的 actual_models；providerThinkingLevel】
- 运行：【退出码 · 用时 / 上限 · 是否超时或取消】
- 费用：【cost.total（status）】
- 复审者：【规划/验收会话；中高风险注明 pi-reviewer 是否参与；换一家审查时写工具与模型】

## 门禁
| 门禁 | 结果 | 说明 |
|---|---|---|
| G0 输入一致 | passed / failed | |
| G1 执行完整 | | |
| G2 范围合规 | | |
| G3 行为正确 | | |
| G4 回归检查 | | 检查记录：checks/【NN】 |
| G5 质量复审 | | |
| G6 可集成 | | |

## DoD 映射
| DoD | 结果 | 证据 | 说明 |
|---|---|---|---|
| D01 | passed / failed / not_run / blocked | 【检查 ID 与日志、用例名】 | 【具体行为】 |

## 范围与质量
- 越界与警告：【scope.json 的 violations / warnings，以及处理判断】
- 测试可信度：【用例数量、是否能在旧实现上失败、有无 skip 或弱化】
- 变异检查（中高风险）：【mutations/NN：抓住 X / 漏掉 Y / 跳过 Z】
  - 漏掉的逐条写成固定格式：`<变异名> → 归因：合同遗漏 | 执行器少写 | 等价变异 | 输入观察不到 → 处理：规划端补测 <提交> | REVISE | 注明 | 探针实测`，让后续能从复审记录里统计「规划端补了几条」
- 兼容性与残余风险：【】
- 执行器自述与证据是否一致：【】

## 结论理由
【为什么给出这个结论；如果是 ACCEPTED_WITH_EXCEPTION，逐项写明豁免的门禁、理由、决定者与适用范围】

## 后续动作
- 需要修正的具体差异（REVISE）：【文件、行为、失败的检查及关键输出】
- 待决的业务或环境问题（BLOCKED / ESCALATE）：【】
- 已授权且可以继续的集成动作：【local_branch / commit / open_pr / …；未授权则写“交付候选，等待决定”】
- 人工介入：【分钟数与原因，用于 --human-minutes】
