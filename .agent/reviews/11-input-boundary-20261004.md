# 11 S5 输入边界复审（2026-10-04）

当前代码头 `6e8d96a` 补齐了恢复与 fallback 控制器的离线输入边界。`select_fallback` 对非法 profile id 抛出 `E_FALLBACK_SCHEMA`，对 malformed `PreflightResult` 或非布尔授权输入返回 `FALLBACK_INPUT_INVALID`；`RecoveryLedger.record` 对非 `CancellationObservation` 返回 `E_RECOVERY_SCHEMA`。这些错误不会通过 `AttributeError` 泄漏未分类状态。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 71 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

本轮仍为离线 `LOCAL_REFERENCE`；真实 fallback、重试、进程恢复、Pi dispatcher、provider 和外部连接器保持 `NOT_RUN/BLOCKED`。
