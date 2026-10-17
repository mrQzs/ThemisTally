# 13 S6 离线价值与独立验收复审

日期：2026-10-04
基线：`3132cba`
结论：`OFFLINE_ACCEPTED_WITH_BOUNDARY`

## 证据

- 固定 fixture：[tests/fixtures/observer/evaluation.json](../../tests/fixtures/observer/evaluation.json)，测量状态保持 `NOT_RUN`，不含 token savings 或 production pass 字段。
- 价值分类测试：`test_13_observer_evaluation.py` 5 项通过；覆盖完整、遗漏、冲突、重复、不确定、缺引用、越界引用和 unknown cost。
- A01–A09 独立测试：`test_13_acceptance.py` 9 项通过；失败、去重、预算、stale、pull-only 和隔离阻塞均保持结构化边界。
- `python -B -m unittest tests.test_13_observer_evaluation tests.test_13_acceptance -q` 合计 14 项通过；compileall 和 diff-check 通过。

## 发布门

当前 release gate 为 `BLOCKED`，observer 默认 `OFF`。真实 observer provider、Pi/第二 CLI、Windows/macOS 原生隔离、host push、持久化记录、10 outbox/cursor 接线和 token/费用收益测量仍为 `NOT_RUN/BLOCKED`。离线 fixture 和测试不构成生产 PASS，也不改变事实、授权、预算、审批或交付状态。
