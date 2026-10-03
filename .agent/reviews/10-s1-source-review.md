# 10 S1 来源契约阶段复审

状态：`ACCEPTED_WITH_EXCEPTION`

## 已复核出口

- `ProjectEvent` 使用闭合字段、严格 JSON、固定 `SourceKey` 和内容派生的事件摘要。
- `ProjectJournal` 使用跨平台写锁、连续 generation/seq、幂等追加，并区分尾部截断、游标缺口、事件冲突和同 SourceKey 漂移。
- `verify_source_ref` 只以文件原始字节计算 SHA-256；缺失、读取不完整、摘要漂移、越界/符号链接和无路径分别保留为可审计状态。
- ProjectEvent 与 SourceVerification Schema 文件均可解析，业务路径复用 01 的安全校验。

## 证据

```text
python -B -m unittest tests.test_project_events tests.test_project_journal tests.test_project_sources -q
Ran 12 tests in 0.138s
OK (skipped=1)
python -m compileall -q scripts/codekit tests                         PASS
project-event-v1.schema.json + source-verification-v1.schema.json      JSON parse PASS
git diff --check                                                        PASS
```

跳过项是宿主不支持符号链接时的离线 fixture；不代表真实平台通过。真实跨进程断电、网络盘、Windows/macOS 原生行为仍为 `NOT_RUN/BLOCKED`，F01–F30 不改变状态。

## 未覆盖与边界

- S1 不负责项目状态归约、视图 current 指针、brief、读取回执或 09/07/03 权威接线。
- 当前阶段没有运行真实 provider、Pi、宿主通知或外部连接器。
- 来源扫描范围/分页/固定截止将在 S3 实现；符号链接拒绝是离线安全边界，不是原生平台证据。
