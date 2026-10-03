# 10 S3 补录与恢复阶段复审

状态：`ACCEPTED_WITH_EXCEPTION`

## 已复核出口

- `scan_source_tree` 使用固定 `cutoff_ns`、有界 `max_entries`、排序遍历和原始字节 SHA-256；达到上限、遇到权限/符号链接/读错误或 cutoff 外文件时明确 `complete=false`。
- `rebuild_generation` 只从干净来源日志写入独立目标，保留业务事件摘要但提升 generation，并返回 `reset_required=true`；不会覆盖来源或把尾部不完整日志当作可重建证据。
- 尾部截断仍由 S2 `ProjectJournal.repair_tail` 在写锁和 CAS 预期下处理；中间损坏保持拒绝。
- source-scan/recovery-report Schema 可解析，测试覆盖确定性扫描、局部扫描、尾部阻塞、代际重建和游标 RESET。

## 证据

```text
python -B -m unittest tests.test_project_events tests.test_project_journal tests.test_project_sources tests.test_project_state tests.test_project_recovery -q
Ran 20 tests in 0.200s
OK (skipped=1)
python -m compileall -q scripts/codekit tests                         PASS
five 10 schemas                                                       JSON parse PASS
git diff --check                                                        PASS
```

符号链接 fixture 在宿主不支持时跳过；实际网络盘、跨进程断电、Windows/macOS 原生恢复仍 `NOT_RUN/BLOCKED`。

## 未覆盖与边界

- S3 不负责 view package/current 指针、brief 限长、读取回执、通知或 09/07/03 权威连接。
- `cutoff_ns` 是扫描范围边界，不是文件身份；文件摘要仍以读取到的完整字节为准。
