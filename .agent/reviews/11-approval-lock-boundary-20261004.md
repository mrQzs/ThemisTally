# 11 S4 input-lock 故障边界复审（2026-10-04）

当前代码头 `c4a05ba` 对 `InputLock` 的结构损坏增加了 `E_INPUT_LOCK_SCHEMA` 分类。start gate 仍只核对已有 lock 的 approval ref、head generation 和输入闭包；畸形绑定、过期 generation、撤销审批和缺失 `ApprovalBinding` 都保持拒绝。

验证：

```text
python -B -m unittest tests.test_11_runtime_boundaries tests.test_authorization tests.test_authorization_boundaries tests.test_planner_publication tests.test_11_second_cli tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 107 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

真实 05 runner、Pi、provider 和原生平台仍未运行。
