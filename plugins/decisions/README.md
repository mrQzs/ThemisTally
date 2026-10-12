# decisions：决策模型（Jev）的问题清单

调度工具 2.6.0 起，把“便宜但要判断”的事交给决策模型：它对一个 state 回答类型化的问题，返回概率与置信度，不写文本。本目录是声明式插件：manifest、锁文件，以及 `questions/` 下每个决策点一份问题清单。清单进完整内容锁，改一个字就要换哈希；阈值写在清单的 `thresholds` 里，代码按名字取，不散落各处。

| 清单 | 决策点 | 触发 | 输出位置 |
|---|---|---|---|
| `report-screen.json` | D1 执行报告筛查 | `run`/`collect` 收集证据时 | summary.md 的“决策”节；`on` 模式下 p ≥ 行动阈值的进“复审需要关注” |
| `mutation-equivalence.json` | D2 漏掉的变异是否等价 | `mutate` 的每条 MISSED | 结果行后缀与 `mutations.json` 的 `decision`；计数不变 |
| `run-health.json` | D3 运行健康 | `wait --assess`、`status --assess` | 进度行多一段；永不停止运行 |

三条不变量：决策只是意见，门禁不读；一切 fail-open（无 key、超时、限流、畸形或自相矛盾的回复都记为“无意见”）；只发脱敏后的相关片段，记录里不存 state 原文。

配置在 `.agent/dispatch.config.json` 的 `decisions` 对象（`mode` 为 `off | shadow | on`，缺省 `off`）；标记文件 `.agent/DECISIONS_OFF` 一票否决。实现在 `scripts/codekit/decisions.py`；设计说明 `docs/code-kit-2.6-决策插件.md`。

问题用英文写（官方文档：英语为主，中日韩准确率较低），state 里优先放代码、命令与英文事件文本。改清单后运行 `python scripts/codekit/decisions.py --check-battery plugins/decisions/questions`，再重新生成锁文件。
