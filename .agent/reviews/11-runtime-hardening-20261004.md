# 11 runtime hardening review (2026-10-04)

主模型集成复审记录，覆盖 S3/S4 的后续加固与 S5/S6 离线门禁；不是 Pi 独立复审。

本轮新增或修正：

- `RawRecordStore` 对 raw UTF-8 字节、ResourceRef SHA-256、半开范围、缺失和漂移进行离线可复核验证；
- 事件 `type` 非字符串稳定归类为 unknown，终态后事件、重复记录的模型/工具/适配器版本冲突均拒绝结算；
- `ProfileHandoff.executor_context` 复用 `protocols.validate_run_context(..., for_executor_dispatch=True)`，并检查 request/run/contract 一致性；
- `evaluate_start_gate` 在 05 runner 之前重查 executor context、handoff、profile、session、共享 `PlanningBudgetLedger` 和 stop/generation；不启动进程、不扣预算、不授予审批；
- 新增 probe schema 与 schema/failure fixtures。

验证：

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_11_schema_fixtures tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 61 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

JSON 文件可由标准库解析；Windows Python 未安装 `jsonschema`，因此没有冒充外部 Schema PASS。真实 provider、05 进程 runner、Pi dispatcher、审批账本连接和 09/10 外部连接器仍是 `NOT_RUN/BLOCKED`。
