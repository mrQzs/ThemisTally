# 11 S6 preflight/start gate 复审（2026-10-04）

当前代码头 `9904261` 将 `PreflightResult` 绑定到 executor start gate。缺少 preflight、状态不是 `READY`、adapter/role/platform/model 不一致或 capability digest 漂移都会拒绝；因此 help/version 探针、配置模型和 `NOT_RUN` 记录不能绕过启动门。

验证：

```text
python -B -m unittest tests.test_11_runtime_boundaries tests.test_11_second_cli tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_authorization tests.test_authorization_boundaries tests.test_planner_publication tests.test_adapters tests.test_runtime -q
Ran 108 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

这仍是离线 gate 证据；真实模型调用、05 runner、Pi、原生平台和 provider 没有执行。
