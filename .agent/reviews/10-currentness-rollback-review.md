# 10 currentness、回退与来源覆盖增量复审

状态：`ACCEPTED_WITH_EXCEPTION`

- view publish 在 current CAS 内拒绝同代游标回退和跨代降级；读取还核对 pointer 与 manifest 的完整闭合字段、generation、cursor 和字节长度。
- `BriefReadReceipt` 自校验绑定摘要，构造伪造 receipt ID 会被拒绝；来源覆盖缺少任一已登记 SourceKey 时保持 `unknown/partial`。
- 相关测试覆盖 current rollback、receipt binding、缺来源核验和最新预算未知边界。

证据：`tests.test_project_views`、`tests.test_read_receipts`、`tests.test_project_state` 共 13 项通过；compileall、Schema JSON parse、diff check 在前一轮通过。

真实跨平台同步、断电和宿主权限仍 `NOT_RUN/BLOCKED`。
