# 11 第二 CLI 离线实现复审（2026-10-04）

本记录覆盖当前代码头 `cae3c70` 的离线收口。事件归一化和结算结果分别保留 `actual_model`、`cli_model`、`provider_model`；只有显式 `cli_model` 的记录可以在不依赖旧 `model` 字段的情况下结算，旧记录仍通过 `model` 作为兼容回退。CLI/provider 来源冲突会阻止结算，不能由 profile 配置值补齐真实观察。

定向验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 70 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

WSL Python 3.12.3 的 `jsonschema 4.10.3` 已对 10 个 Schema 执行 Draft 2020-12 `check_schema`：

```text
jsonschema-check-ok 10
```

这批离线证据仍只属于 `LOCAL_REFERENCE`。真实第二 CLI 模型调用、认证、费用、Pi、05 原生进程、Windows/macOS 平台链路和外部连接器保持 `NOT_RUN/BLOCKED`；因此 A06/A07、F01–F10 和生产发布门禁没有被关闭。11 的 21 份合同仍是未派遣规划材料，没有对应 `.agent/runs/` attempt 证据。
