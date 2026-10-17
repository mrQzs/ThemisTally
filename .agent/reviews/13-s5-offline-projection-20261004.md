# 13 S5 离线投影与交接复审

日期：2026-10-04
基线：`95e1fff`（observer 协议/runtime 已推送）
结论：`OFFLINE_ACCEPTED_WITH_BOUNDARY`

## 证据

- `tests/test_13_observer_projection.py`：3 项通过；确定性 brief 可读取，observer 结果不会写入 10 view，游标前进后旧结果为 `STALE`。
- `tests/test_13_observer_notifications.py`：4 项通过；无 host 时只返回 `pull/NOT_RUN`，push 被拒绝，delivery 与 read receipt 分离，blocked host 不放行 release gate。
- `tests/test_13_observer_rebuild.py`：3 项通过；新游标使用新 run 和预算，旧范围不能覆盖新游标，future cursor 拒绝且不消耗预算。
- 相关 10 回归：project views/delivery/read receipts 9 项通过；compileall 和 diff-check 通过。

## 边界

这些证据验证现有 10 投影、pull-only delivery 和内存 runtime 的离线语义。持久 observer ledger、10 outbox/cursor 生产接线、真实 host notification、跨进程恢复和 provider 均为 `NOT_RUN/BLOCKED`。因此 S5 不能提升 observer 默认状态或生产 release gate。
