# 11 S2 事件映射复审（2026-10-04）

当前代码头 `34582c0` 为 `CliEvent` 增加闭合 `to_mapping()`，Schema 夹具直接验证生产映射，不再复制字段清单。映射保留 request/run/role、事件序号、原始 ResourceRef 与半开范围、`actual_model`/`cli_model`/`provider_model` 和工具身份。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 72 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

事件映射仍只提供离线证据；真实 CLI 进程、provider 和持久生产 spool 未接入。
