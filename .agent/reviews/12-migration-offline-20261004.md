# 12 迁移离线实现复审（2026-10-04）

状态：`LOCAL_REFERENCE`；不代表生产迁移、备份或恢复已接线。

## 范围

本次只覆盖 12 的可离线复核边界：

- `scripts/codekit/migration.py`：`MigrationPreflight`、`MigrationPlan`、`MigrationOperation`、`MigrationReceipt`、`HistoryIntegrityReport`、`BackupSnapshot` 和 `MigrationLedger`。
- 迁移计划强制使用闭合 `ResourceRef`、固定 `expected_generation`、补偿引用和 `online_calls_allowed=false`。
- `MigrationLedger` 仅在内存中执行 selection CAS；同键同指纹重放返回原事实，同键不同请求拒绝，提交后响应丢失可查询同键回执，回退分配新代际，用户改动 postimage 时拒绝回退。
- `compare_history_inventory` 只读比较 `missing / changed / unplanned_added / unreadable`，不改写旧摘要；`create_backup_snapshot` 只从调用方提供的字节生成 hash-only manifest，不读写用户文件。

## 验证

```text
python -B -m unittest tests.test_migration -q     # 8 项通过
python -B -m compileall -q scripts/codekit tests  # 通过
git diff --check                                  # 通过
wsl python3 ... Draft202012Validator.check_schema # 7 个 schema 通过
```

新增 Schema：

- `migration-preflight-v1.schema.json`
- `migration-plan-v1.schema.json`
- `migration-operation-v1.schema.json`
- `migration-receipt-v1.schema.json`
- `history-integrity-report-v1.schema.json`
- `backup-snapshot-v1.schema.json`
- `migration-records-v1.schema.json`（闭合 `oneOf` 汇总）

## 结论与限制

离线合同、字节指纹、CAS、幂等、响应丢失、备份清单和历史完整性分类均有确定性测试。实现没有接入 `UnifiedLedgerStore` 的生产迁移路径，保留其 v1 `migration_batches` 语义不变。

以下能力仍为 `NOT_RUN/BLOCKED`：真实文件/SQLite/WAL/跨账本一致备份，OS 强杀或断电恢复，用户工作树与凭据，03 维护授权、05 运行排空、07 预算，Pi/真实连接器及任何自动切换。离线 `APPLIED` 只表示内存 selection 事实，不能作为生产发布或迁移许可。
