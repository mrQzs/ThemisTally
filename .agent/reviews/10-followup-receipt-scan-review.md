# 10 读取、修复与扫描边界增量复审

状态：`ACCEPTED_WITH_EXCEPTION`

- `BriefReadReceipt` 现在绑定 view、manifest、brief 摘要和精确游标；`ReadReceiptStore` 以稳定锁持久化，同 ID 重放返回 replay，不生成第二条已读事实。
- `ProjectJournal.repair_tail` 支持 expected SHA-256、原始尾部备份和锁内重检；摘要漂移或备份冲突拒绝修复。
- `scan_source_tree` 增加固定 `after_path`/`next_page` 续扫，分页边界仍输出 `complete=false`，不能把局部页当完整范围。
- brief 展示对 secret/token/password/credential 等字段脱敏，换行和 Unicode 行分隔符转义；manifest 保存 state/brief UTF-8 实际字节数和展示/省略计数。

## 证据

```text
python -B -m unittest tests.test_project_events tests.test_project_journal tests.test_project_sources tests.test_project_state tests.test_project_recovery tests.test_project_views tests.test_project_commands tests.test_project_delivery tests.test_project_reconcile tests.test_project_history tests.test_project_requests tests.test_read_receipts -q
Ran 42 tests in 0.449s
OK (skipped=1)
python -m compileall -q scripts/codekit tests                         PASS
all schemas                                                        JSON parse PASS
git diff --check                                                        PASS
```

原生平台锁/替换、断电和外发权限仍不能由本地 fixture 证明，继续 `NOT_RUN/BLOCKED`。
