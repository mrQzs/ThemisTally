# 11 S1/S5 profile routing 复审（2026-10-04）

当前代码头 `3ea20c5` 收紧 `ProfileRouter.register`：必须提供与 profile adapter、role、platform、environment、required capabilities 和 model 一致的 `AdapterCapability` snapshot，并重新计算 capability digest；缺少 snapshot、adapter 不匹配、能力不足或 digest 漂移均拒绝。provider-neutral facade 仍不包含品牌分支，也不启动进程。

验证：

```text
python -B -m unittest tests.test_11_runtime_boundaries tests.test_11_second_cli tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_authorization tests.test_authorization_boundaries tests.test_planner_publication tests.test_adapters tests.test_runtime -q
Ran 108 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

Pi dispatcher、真实 provider、05 runner 和原生平台仍为 `NOT_RUN/BLOCKED`。
