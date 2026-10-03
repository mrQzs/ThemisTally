# 09 CLI 规划与合同发布：实现状态

## 已推送阶段提交

| 阶段出口 | 提交 | 结果 |
|---|---|---|
| S3 发布与全入口门禁 | `c13560e` | ApprovalLedger 动作/时效、发布 ID 冲突、持久 outbox、恢复和消费入口门禁 |
| S1 协议与 S4 预算桥 | `45ce853` | PlanningBundle 闭包负例、合同草稿非空/任务绑定、`PlanningBudgetLedger` |
| 11 适配器并行基础 | `c63988a`、`32785a1` | 能力 Schema 和 Claude Code 五接口门面；不计作 09 真实 planner 通过 |

## 离线验证

```text
python -B -m unittest tests.test_planner_protocol tests.test_planner_publication tests.test_planner_runtime tests.test_planner_adapter tests.test_planner_projection tests.test_dispatch_planner -q
python -B -m unittest tests.test_11_second_cli tests.test_adapter_capability tests.test_adapters -q
python -m compileall -q scripts/codekit tests
git diff --check
```

最近一次定向结果：09 相关 31 项通过；11 适配器/旧 adapter 回归 32 项通过。Windows Python 环境没有 `jsonschema`，Draft 2020-12 Schema 语义校验仍需在既有 WSL Python 3.12 环境运行；本轮没有安装依赖。

## 仍未放行的边界

- 真实 planner/provider/Pi、真实模型调用、Windows/macOS 原生进程和外部 09/10 连接器：`NOT_RUN/BLOCKED`。
- dispatcher 只能核验持久回执、outbox 和固定字节；没有外部 ApprovalLedger 服务时，不能凭 sidecar 声称审批撤销已被在线重查。
- 06/08 插件锁/catalog 编译、跨 request 持久 task owner、完整 07 START_UNKNOWN/迟到结果接线和 10 outbox/cursor 生产连接仍为 `PARTIAL/GAP`。

这些限制保留在追踪矩阵中，不能把离线合同测试改写成生产发布 PASS。
