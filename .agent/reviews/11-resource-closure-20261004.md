# 11 S3 invocation resource closure 复审（2026-10-04）

当前代码头 `943278d` 要求 executor invocation 的 `resource_allowlist` 与 handoff 批准的输入 ResourceRef 集合完全相等；遗漏或新增资源都会返回 `INVOCATION_RESOURCE_MISMATCH`。该检查与 capability/platform/session/profile 绑定一起执行，保持最小资源闭包。

验证：

```text
python -B -m unittest tests.test_11_runtime_boundaries tests.test_11_second_cli tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_authorization tests.test_authorization_boundaries tests.test_planner_publication tests.test_adapters tests.test_runtime -q
Ran 108 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

真实 runtime runner 和 OS 资源观察仍未执行。
