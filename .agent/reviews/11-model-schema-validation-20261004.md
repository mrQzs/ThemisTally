# 11 model identity and schema validation review (2026-10-04)

本轮把 CLI 回报模型与 provider 回报模型分开记录；收集结果不会用请求配置覆盖缺失的 CLI 身份，provider 模型冲突也会阻止结算。事件 Schema 同步增加两个可空字段。

WSL Python 3.12 的 `jsonschema 4.10.3` 已执行 Draft 2020-12 `check_schema` 与代表性记录验证：capability、preflight、probe、probe manifest、event、handoff、recovery、invocation、release gate 共 9 个 Schema 通过；probe Schema 已改为本地 `$defs`，不依赖不可解析的外部 URN 引用。

Windows 定向测试与编译检查：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 67 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

真实 provider、模型调用和原生平台仍未运行。
