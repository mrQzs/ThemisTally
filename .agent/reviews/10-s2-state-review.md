# 10 S2 登记与纯投影阶段复审

状态：`ACCEPTED_WITH_EXCEPTION`

## 已复核出口

- `ProjectJournal` 已提供单写者追加、SourceKey/event_id 幂等、连续 generation/seq 以及尾部截断恢复；S2 复用该登记边界，不再建立第二套事件账本。
- `reduce_project_events` 对已登记事件执行确定性归约：重复事件不推进游标、不增加完成状态；任务状态按 revision 单调收敛；预算按 ledger revision 替换快照而非累加；决定/预算冲突保留为 issues。
- 状态输出固定标识 `dispatch_eligibility=not_evaluated`，不会授予批准、预算或执行权限；来源核验不完整时只降低 coverage/health。
- `project-state-v1.schema.json` 与事件、来源 Schema 可解析，定向负例覆盖游标缺口和未分配事件。

## 证据

```text
python -B -m unittest tests.test_project_events tests.test_project_journal tests.test_project_sources tests.test_project_state -q
Ran 16 tests in 0.141s
OK (skipped=1)
python -m compileall -q scripts/codekit tests                         PASS
project-event/source-verification/project-state schemas             JSON parse PASS
git diff --check                                                        PASS
```

符号链接测试在不支持符号链接的宿主上跳过；不构成 Windows/macOS 原生锁、断电或跨进程证明。真实 provider、Pi、宿主通知和外部连接器继续 `NOT_RUN/BLOCKED`。

## 未覆盖与边界

- S2 尚未实现不可变 view package/current 指针、brief 字节上限、读取回执、source scanner 或 generation rebuild。
- 决定和预算仍是只读观察，03/07 仍拥有审核、准入、stop 和账本真相。
