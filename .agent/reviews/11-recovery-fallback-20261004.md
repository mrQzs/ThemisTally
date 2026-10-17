# 11 recovery and fallback review (2026-10-04)

本轮补充了 `RecoveryLedger` 与 `select_fallback`：同一 request/run/generation 的完全相同恢复观察返回 `REPLAY`，不同观察拒绝为冲突；fallback 不会自动选择，必须有授权、重新审核且候选 profile preflight 为 READY。CLI 模型与 provider 模型在事件和结算结果中保持独立字段。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 69 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

真实 fallback、真实重试、Pi/05 runner 和 provider 调用仍未运行，生产门禁继续阻塞。
