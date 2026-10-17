# 13 可选摘要 Observer：离线价值评估与独立验收报告

日期：2026-10-04
固定基线：`cf44ae17fa2722cd998c5991722a0db7e373d7a8`
范围：13-s6-1、13-s6-2、13-s6-3 的离线评估、A01–A09 复核和发布门边界。

本报告只把固定 fixture 上可复核的离线结果记为 `OFFLINE_ACCEPTED_WITH_BOUNDARY`。它不把离线 adapter、内存 runtime 或测试数量当成真实 provider、宿主通知、原生隔离或生产启用证据。Observer 的默认发布状态仍为 `OFF`。

## 固定输入与价值分类

输入固定在 [evaluation.json](../../tests/fixtures/observer/evaluation.json)：一个确定性 brief、四个事件来源、游标 `1..4`、严格的 ResourceRef 和离线请求。测试对以下类别执行相同的协议绑定和来源闭包校验：

| 类别 | 固定分类 | 协议/运行时处理 |
|---|---|---|
| 完整摘要 | `CORRECT` | 所有事实有输入内来源，绑定成功 |
| 遗漏项目 | `OMITTED_WITH_REASON` | `omitted` 记录原因和来源，状态为部分结果 |
| 冲突事实 | `UNTRUSTED_CONFLICT` | 仍可结构化读取，但保留为不可信建议，不覆盖确定性 `pending` 状态 |
| 重复输入 | `DEDUPLICATED` | 同一游标和输入引用只保留一个 run，重放不增加调用预算 |
| 不确定结果 | `UNCERTAIN` | 以 hypothesis、missing information 和 `impact=unknown` 表达，不降级为事实 |
| 缺失引用 | `INVALID_MISSING_CITATION` | 无来源事实被拒绝 |
| 越界引用 | `INVALID_OUT_OF_SCOPE` | 不在请求闭包内的来源被拒绝 |
| 响应/用量未知 | `UNKNOWN_COST_DEGRADED` | `RESPONSE_LOST` 保留 unknown liability 并停止后续准入 |

价值测量状态为 `NOT_RUN`。本轮没有 token、费用、阅读时间或生产收益测量，fixture 也不提供 `token_savings` 或生产通过字段。

## A01–A09 独立复核

测试入口为 [test_13_acceptance.py](../../tests/test_13_acceptance.py)；价值分类和最小负例位于 [test_13_observer_evaluation.py](../../tests/test_13_observer_evaluation.py)。

| 验收项 | 离线结论 | 可复核证据 | 真实边界 |
|---|---|---|---|
| A01 | `OFFLINE_ACCEPTED_WITH_BOUNDARY` | 失败后确定性 brief 字节/状态不变；核心 runtime 仍可记录 `RESPONSE_LOST` | 未运行真实 profile/provider |
| A02 | `OFFLINE_ACCEPTED_WITH_BOUNDARY` | facts、hypotheses 分层，缺引用被拒绝 | 语义正确性仍需真实样本复审 |
| A03 | `OFFLINE_ACCEPTED_WITH_BOUNDARY` | `PASS`/授权/发布文字被协议拒绝；runtime 无项目状态写权限 | 未接 03/10 生产状态投影 |
| A04 | `OFFLINE_ACCEPTED_WITH_BOUNDARY` | 相同输入单飞去重；observer 完成事件不自动发起新调用 | 未运行并发进程/宿主事件总线 |
| A05 | `OFFLINE_ACCEPTED_WITH_BOUNDARY` | global 与 observer 预算同时消耗，取消/重试不清零 | 未接真实 07 账本/计费 |
| A06 | `OFFLINE_ACCEPTED_WITH_BOUNDARY` | timeout、response loss、unknown cost 和冲突均有结构化降级 | 未验证真实进程无结束事件 |
| A07 | `OFFLINE_ACCEPTED_WITH_BOUNDARY` | 新事件使旧摘要 `STALE`，原游标保持 `end=4` | 未接持久化 10 cursor/outbox |
| A08 | `BLOCKED_REAL_CAPABILITY` | fixture 明确 `host_push=BLOCKED`，只允许 pull 语义 | 没有 host adapter，未运行投递/阅读链路 |
| A09 | `BLOCKED_REAL_CAPABILITY` | 未知字段被拒绝，隔离门标记 `BLOCKED` | 未证明 OS 级只读；真实 provider/平台均 `NOT_RUN` |

`BLOCKED_REAL_CAPABILITY` 不是离线测试失败，而是发布门要求的能力证据缺失。它不得被改写成生产 PASS。

## 发布门与恢复边界

当前门禁结论：`BLOCKED`，默认保持 `OFF`。缺少精确 observer profile/provider、真实费用与预算结算、可验证的执行隔离、持久化 observer 记录、10 outbox/cursor 接线以及 host push 时，不得开启生产 observer。

关闭 observer 时停止新调用，保留已有结果供追溯；超时、取消、响应丢失或 unknown 用量不得无条件重试。恢复只能从已登记的来源游标和 run 记录重新核对，不能修改确定性事实、任务状态、审批/授权、合同、release gate 或核心预算账本。

真实 observer provider、Pi/第二 CLI、Windows/macOS 原生进程、host push、外部连接器和 token 节省评估：`NOT_RUN/BLOCKED`。本报告没有读取凭据、安装依赖或写入外部系统。

## 本轮验证

```text
python -B -m unittest tests.test_13_observer_evaluation -q   # 5 passed
python -B -m unittest tests.test_13_acceptance -q             # 14 passed (包含导入的 5 个评估用例)
```

执行器还应在固定候选上运行合同要求的 `tests.test_dispatch`、`compileall` 和 `git diff --check`；这些命令的最终阶段结论由规划端复跑并记录在独立复审中。本报告不创建或编辑 `.agent/runs/` 原始证据。
