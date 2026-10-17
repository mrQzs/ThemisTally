# 11 S4 ApprovalBinding 复审（2026-10-04）

当前代码头 `e1ae43d` 将 03 `ApprovalLedger` 的只读 currentness 事实接入 executor start gate。`ApprovalBinding` 固定 scope、generation、record hash、动作和输入 ResourceRef，可携带既有 `InputLock`；start gate 只执行 `assert_current`、动作/输入可消费性检查和 lock generation/闭包核对。缺少 binding、审批撤销、generation 漂移、动作未审阅或输入不一致均拒绝，adapter 不创建或修改批准状态。

验证：

```text
python -B -m unittest tests.test_11_runtime_boundaries tests.test_authorization tests.test_authorization_boundaries tests.test_11_second_cli tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 97 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

09 PlanningService 的真实启动入口、Pi、provider 和原生进程仍未接入；本轮只验证离线门禁事实。
