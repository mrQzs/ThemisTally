# 10 S5 权威适配与检查点阶段复审

状态：`ACCEPTED_WITH_EXCEPTION`

## 已复核出口

- `AuthorityObservation` 将 approval/readiness/planning/runtime 作为只读来源，缺失或未知时保留状态和原因，不转换成通过或权限。
- `project_status` 与 `project_checkpoint` 只消费当前 view package，输出固定 manifest/brief 摘要和 `dispatch_eligibility=not_evaluated`；重复相同输入的 checkpoint ID 稳定。
- `load_registered_legacy_state` 要求显式 `source_class=legacy`、登记标志和精确 SHA-256，历史路径不会因 v2 字段或文件存在而自动降级放行。
- authority/checkpoint Schema 和离线测试覆盖未接线、字节漂移和只读边界。

## 证据

```text
python -B -m unittest tests.test_project_events tests.test_project_journal tests.test_project_sources tests.test_project_state tests.test_project_recovery tests.test_project_views tests.test_project_commands -q
Ran 26 tests in 0.211s
OK (skipped=1)
python -m compileall -q scripts/codekit tests                         PASS
nine 10 schemas                                                        JSON parse PASS
git diff --check                                                        PASS
```

真实 03/07/09/05 适配、Pi/provider、宿主 CLI 和外部连接器仍为 `NOT_RUN/BLOCKED`。离线 authority observation 只记录边界，不冒充生产来源。

## 未覆盖与边界

- S5 没有修改 `scripts/pi_dispatch.py` 或旧合同入口；兼容加载器是显式登记的只读门禁。
- 10 不承担审批、预算、调度、进程控制或外部发布动作。
