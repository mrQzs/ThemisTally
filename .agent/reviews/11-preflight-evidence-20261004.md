# 11 S1/S6 能力证据预检复审（2026-10-04）

当前代码头 `8cfe42a` 收紧了 `preflight_profile` 的 READY 条件：调用方传入的 `reported_model`、版本布尔值和认证状态不能替代 capability 的 `observed` 来源；请求模型时还必须观察 `model_identity`，所需能力缺少观察证据时返回 `NOT_RUN` 并保留 `EVIDENCE_NOT_OBSERVED:*` 原因。离线或 synthetic 能力仍不能通过生产预检。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 72 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

真实模型、认证、费用、平台进程和外部连接器仍为 `NOT_RUN/BLOCKED`；本轮没有读取凭据或发起模型调用。
