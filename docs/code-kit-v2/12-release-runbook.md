# 12 恢复与发布操作册

1. 固定候选、`IntegrationTarget`、可信 `CheckCatalog` 和输入闭包；若任一 SHA、环境或规则漂移，停止并标记 `STALE`。
2. 读取 `EvidenceManifest` 和 `CoverageReport`。缺失、未运行、未知、取消、WAIVED、部分或阻塞状态都不能升级为 PASS。
3. 迁移只先执行 `MigrationPreflight` 与只读 `MigrationPlan`；确认备份摘要、规则当前性、维护授权、排空和预算证据均来自真实拥有者。当前离线实现不具备这些生产权限。
4. 真正执行时使用 operation id、expected generation 和幂等键；响应丢失时查询同键回执，禁止重复切换；CAS 冲突或用户修改 postimage 时停止回退。
5. `HistoryIntegrityReport` 出现 missing、changed、unplanned_added 或 unreadable 时保持阻塞，保留旧哈希和原始证据，等待人工复审。
6. 只有真实三平台、第二 CLI、Pi/provider、连接器和目标项目证据齐全，且独立复审更新为放行，才可讨论生产发布；本轮状态为 `NOT_RUN/BLOCKED`。

