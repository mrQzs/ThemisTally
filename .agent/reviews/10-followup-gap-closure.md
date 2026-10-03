# 10 离线 GAP 收口增量复审

状态：`ACCEPTED_WITH_EXCEPTION`

本增量针对追踪矩阵中的离线 GAP，仍不改变真实集成门禁：

- `reconcile_events` 先检查来源 verification，再按 generation/cursor CAS 幂等追加；未核验来源停在 pending，冲突不会静默覆盖。
- `validate_revision_chain` 报告缺前驱、fork、跨 scope、循环和未知 head；`evaluate_currentness` 只让相关规则变化使观察变旧，无关进度不扩散。
- ProjectState 现在保留 acceptance/integration/superseded 维度；最新未核验预算/决定只标 `currentness=unknown`，不回退旧成功。
- `project_request` 只按精确 `request_id` 映射，缺字段进入 unknown，不做摘要相似度推断。
- view manifest 记录 state/brief 实际 UTF-8 字节数、展示/省略数量；brief issue 行保留来源/问题标记，并在限长不足时拒绝。

## 证据

```text
python -B -m unittest tests.test_project_events tests.test_project_journal tests.test_project_sources tests.test_project_state tests.test_project_recovery tests.test_project_views tests.test_project_commands tests.test_project_delivery tests.test_project_reconcile tests.test_project_history tests.test_project_requests -q
Ran 39 tests in 0.256s
OK (skipped=1)
python -m compileall -q scripts/codekit tests                         PASS
all schemas                                                        JSON parse PASS
git diff --check                                                        PASS
```

真实 03/07/09/05 权威、Pi/provider、原生平台、跨机器锁/断电、宿主通知和外部连接器仍为 `NOT_RUN/BLOCKED`；相关 A/F 项只能记离线 `LOCAL_REFERENCE` 或 `BLOCKED`。
