# 11 S3 invocation identity 复审（2026-10-04）

当前代码头 `60dffbb` 在 executor start gate 重核对 invocation 的 capability digest、platform 和 environment kind，使 invocation、profile、preflight 三者必须同源；漂移或缺失会拒绝，避免只凭 profile id 复用不同环境快照。

验证：

```text
python -B -m unittest tests.test_11_runtime_boundaries tests.test_11_second_cli tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_authorization tests.test_authorization_boundaries tests.test_planner_publication tests.test_adapters tests.test_runtime -q
Ran 108 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

真实 process identity 和 05 runner 仍未运行。
