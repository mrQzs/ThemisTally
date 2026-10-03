# 13 Observer 离线实现与阶段门复审

日期：2026-10-04
规划基线：`cf44ae17fa2722cd998c5991722a0db7e373d7a8`
结论：`OFFLINE_ACCEPTED_WITH_BOUNDARY`

## 已交付

- S0 路线图、追踪矩阵和 21 对 `.md/.json` 合同；逐份 `python scripts/pi_dispatch.py validate` 结果为 21/21 通过，JSON 全部可解析。
- S1/S2 离线协议：闭合 `ObserverRequest`、`ObserverOutput`、`ObserverSuggestion`，严格 JSON、ResourceRef/字节摘要、游标和来源闭包、事实/假设/风险/问题/建议分层，以及伪 PASS/授权/发布语句拒绝。
- S3/S4 离线 runtime：输入去重、single-flight、全局和 observer 预算预留、超时/取消/响应丢失未知费用停止、高水位和 stale、迟到响应降级；runtime 不拥有项目状态写权限。
- 四个 Draft 2020-12 Schema、16 项 observer 定向测试、协议/runtime 独立复审。

## 验证证据

```text
python -B -m unittest discover -s tests -p 'test_13_observer*.py' -q
Ran 16 tests ... OK

pytest -q -p no:cacheprovider \
  tests/test_project_views.py tests/test_project_delivery.py tests/test_read_receipts.py \
  tests/test_project_state.py tests/test_project_events.py tests/test_project_sources.py \
  tests/test_project_commands.py tests/test_project_history.py tests/test_project_reconcile.py \
  tests/test_integration_gates.py
47 passed, 1 skipped

python -B -m compileall -q scripts/codekit tests
git diff --check
wsl.exe python3 ... Draft202012Validator.check_schema(...)
observer-schema-ok 4
```

关联 project journal/recovery/requests/projections 与 legacy events/gates 回归为 83 passed、1 failed；唯一失败是既有 `tests/test_legacy_events.py::SourceFactsTests::test_legacy_source_is_locked_revision` 的 locked revision 摘要不匹配（pi_dispatch 当前 sha256 `90a5b152...`，测试锁定 `a00d6934...`），归属于既有 baseline/环境事实，不由 observer 变更引入。全量 `unittest discover` 未在本轮完成，不据此宣称全量通过。

## 边界与未运行能力

真实 observer model/provider、第二 CLI、Pi 执行、Windows/macOS 原生隔离、宿主 push、持久化 observer ledger、10 outbox/cursor 接线、价值评估和外部连接器均为 `NOT_RUN/BLOCKED`。observer 默认关闭；离线 runtime 与 fixture 不构成生产发布 PASS，也不能提升核心审批、预算、任务状态或 release gate。

S5/S6 合同仍是后续工作；若要继续接入持久化账本、10 投影或真实平台，必须以新的基线和合同版本重新规划、复审和放行。
