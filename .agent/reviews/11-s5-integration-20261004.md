# 11 S5 integration review (2026-10-04)

这是主模型集成复审，不是 Pi 独立复审。

本阶段补充 `ProfileRouter`，按 profile id 解析注册的 adapter，不在核心调度器内写 provider 分支；同时保留既有 `OfflineAdapter` 协议作为 Pi 历史回归面，并把取消状态扩展为显式 `CANCEL_AFTER_EXIT`。真实 Pi dispatcher、进程清理和自动重试仍未接入。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 51 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

结论：S5 离线协议与历史适配器回归为 `LOCAL_REFERENCE/PARTIAL`；真实 Pi、第二 CLI 模型调用和原生平台生命周期仍为 `NOT_RUN/BLOCKED`，不可作为生产发布通过。
