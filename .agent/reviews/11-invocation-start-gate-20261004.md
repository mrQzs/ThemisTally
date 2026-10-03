# 11 S3 invocation start gate 复审（2026-10-04）

当前代码头 `e5d706a` 将具体 `SecondCliInvocation` 设为 executor start gate 的必需绑定。缺少 invocation 返回 `INVOCATION_UNBOUND`；存在时继续核对 request/run、role/profile、adapter、read-only scope 和 session，避免只凭上下文事实放行一个未冻结的调用。

验证：

```text
python -B -m unittest tests.test_11_runtime_boundaries tests.test_11_second_cli tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_authorization tests.test_authorization_boundaries tests.test_planner_publication tests.test_adapters tests.test_runtime -q
Ran 108 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

真实 05 runner、OS process identity 和 provider 调用仍未运行。
