# 11 release evidence binding review (2026-10-04)

本轮把 release gate 的事实输入进一步绑定到 `ResourceRef`：任何真实链路、平台生命周期、独立复审或外部连接器被标为 true 时，都必须提供对应的 SHA-256 证据引用；缺少引用会拒绝 gate。适配器直接构造未绑定 capability digest 的 profile 也不能生成 invocation。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 66 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

当前没有真实证据引用，release gate 仍拒绝；本轮只增强了离线拒绝语义，没有改变 `NOT_RUN/BLOCKED` 结论。
