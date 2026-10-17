# 11 invocation snapshot review (2026-10-04)

本轮将 Invocation 快照扩展为严格记录，包含平台、WSL/native 环境类型、环境变量名称集合、能力摘要、session、stdin SHA-256、ResourceRef allowlist 和最终 invocation SHA-256；增加闭合 Schema 与 profile/环境/资源负例。

同时，offline capability 即使带有 synthetic model/auth facts，也只会得到 `NOT_RUN`，不能伪装成 `READY`。release gate 仍要求真实模型链路、平台生命周期、独立复审和外部连接器。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 66 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```
