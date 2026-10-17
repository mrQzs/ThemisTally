# 11 preflight and release gate review (2026-10-04)

本轮补充机器可检查的 profile preflight 与独立发布门禁：

- `preflight_profile` 区分 `READY`、`NOT_RUN`、`BLOCKED`、`VERSION_INCOMPATIBLE`、`AUTH_UNAVAILABLE`，并把请求模型、报告模型和认证状态分开；没有自动 fallback；
- `evaluate_independent_release_gate` 要求所有 preflight READY、真实模型链路、真实平台生命周期、独立复审和外部连接器同时成立；离线 fixture 不能满足这些条件；
- 对应结果新增严格 JSON Schema 和负例测试。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 65 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

当前 release gate 必然保持拒绝，因为真实模型/provider、05 进程、Pi 和外部连接器尚未运行；这是预期的生产门禁行为。
