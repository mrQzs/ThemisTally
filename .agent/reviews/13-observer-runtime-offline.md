# 13 Observer runtime 离线复审

状态：`OFFLINE_ACCEPTED_WITH_BOUNDARY`

## 范围

本复审覆盖 `scripts/codekit/observer_runtime.py` 与 `scripts/codekit/observer.py` facade 的离线调度边界。实现只保存内存中的请求、游标和运行记录，不调用 provider、CLI、Pi、宿主通知或项目状态写入口。

## 已验证

- 同一固定输入去除 `request_id` 后使用确定性 digest 去重；活动请求 single-flight，重放不再次 reserve；
- 全局预算与 observer 子预算在提交前按次数和预留时限双重检查，失败仍消耗预留；
- timeout、cancel、response_lost 且无费用结算时保留 `unknown_cost` 并停止后续 admission；
- 事件只推进 high-water；摘要记录实际源游标，新事件抵达后 `latest()` 返回 `STALE`，不伪装覆盖最新进度；
- 请求/输出通过协议 validator 绑定项目、brief、source refs 与游标；未来游标拒绝；
- `project_state` 固定为空且无修改接口，失败、取消和响应丢失不改变项目事实；
- 超过保留时限的迟到成功响应降级为 `TIMED_OUT`，不进入摘要结果；
- 定向测试 `test_13_observer_protocol.py` 与 `test_13_observer_runtime.py` 共 16 项通过（协议 7 项、runtime 9 项）；compileall、diff-check 和 WSL Draft 2020-12 schema check 通过。

## 边界与阻塞

真实 observer model/provider、第二 CLI、Pi、跨平台只读进程隔离、宿主 push、持久化账本、10 outbox/cursor 接线和生产预算结算为 `NOT_RUN/BLOCKED`。内存 runtime 不能证明进程崩溃后的持久 single-flight 或实际费用；未知责任需由未来 reconciler 提供结算后才能解除停止。
