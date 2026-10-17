# 12 最终离线复审与发布门禁（2026-10-04）

复审基线：`c71014517e3579e5bb465d277a6712c214e565b4`。已推送实现 HEAD：`7717674317b2d1a91918c617218062104f815ea2`。

## 已交付

- 7 阶段、21 个独立子任务合同，MD/JSON 逐份通过 `scripts/pi_dispatch.py validate`（21/21，0 warning）。
- `IntegrationTarget`、`CheckCatalog`、`CheckObservation`、`EvidenceManifest`、`CoverageReport`、`DeliveryDecision` 离线记录与闭合 Schema。
- `MigrationPreflight`、`MigrationPlan`、`MigrationOperation`、`MigrationReceipt`、`BackupSnapshot`、`HistoryIntegrityReport` 和内存 CAS/幂等账本。
- 路线图、追踪矩阵、恢复/发布操作册与 S0、集成、迁移、S6 独立复审。

## 验证证据

```text
python -B -m unittest tests.test_dispatch tests.test_dispatch_planner tests.test_planner_publication tests.test_planner_runtime tests.test_planner_protocol tests.test_integration_gates tests.test_12_integration_records tests.test_migration -q
  62 tests, OK
python -B -m compileall -q scripts/codekit tests
  OK
git diff --check
  OK
scripts/pi_dispatch.py validate .agent/plans/12-*.md
  21 contracts, 0 invalid
WSL Python 3.12 Draft202012Validator.check_schema
  8 changed schemas, OK
```

全量 `unittest discover` 曾因长时间无输出而手工停止，未宣称全量生产 PASS；既有基线中的 legacy source-lock/environment 分类继续独立记录。

## 发布门禁

离线实现门通过，生产门禁保持 `BLOCKED`。真实三平台、真实第二 CLI/provider、Pi、原生进程强杀/断电、受信采集器、外部 09/10 连接器、真实文件/SQLite/WAL 迁移、维护授权、预算和 observer 关闭场景均为 `NOT_RUN/BLOCKED`。`LOCAL_REFERENCE`、fixture 或 mock 不得升级为生产证据。

