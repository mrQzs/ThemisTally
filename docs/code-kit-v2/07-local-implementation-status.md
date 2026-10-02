# 07 本地实现阶段记录

记录时间：2026-10-02。基线提交：`02ca295`（S0 合同与证据基线）。

本轮由规划端在 Pi 环境阻塞时直接完成离线边界实现。Pi doctor 记录在 `.agent/environment.md`：当前 `step/step-5-preview` 不可用且凭据未就绪，因此没有派遣执行器，也没有把本轮纯 Python/SQLite 证据当作真实 provider、进程、平台锁或外部系统接线完成。

已完成并可复核的局部结果：

- S1.3：`identity.py` 提供 host、boot、environment、worktree、process、resource 的版本化不透明身份；PID-only、缺失事实和未知资源保持阻塞。
- S1.1/S1.2：`currentness.py` 和 `baseline_use.py` 将固定 Git/祖先/覆盖率事实与当前授权、代际及显式多上游合流接受记录组合；未知、撤销、候选漂移和缺少合流记录保持等待或阻塞。
- S2.1 的离线候选：`unified_ledger.py` 在 atomic v2 账本上增加 schema v3 manifest、attempt 生命周期、cursor CAS 和迁移批次；取消、停止、generation fencing、证据冲突、游标跳跃和幂等重放有测试保护。
- S3.1/S3.3 的离线候选：`provider_economics.py` 提供 provider/economic-call identity、可见性、观察重放/镜像/冲突、发票行与整数金额分摊；空观察集和未知覆盖率不会宣称完整。
- S5.1/S5.2 的离线候选：`projections.py` 分离 refine/planner/execute readiness，提供连续 outbox 序列、generation fencing、event-id 冲突检测、cursor 与权威行重建；state/brief 明确保留 source coverage、预算未知和 `dispatch_eligibility=not_evaluated`。
- S4.1 的离线候选：`runtime_lease.py` 要求完整 boot-bound process identity；过期但仍存活的 owner 保持占用，liveness unknown 阻塞，只有明确死亡且代际/owner/token 匹配才允许回收。
- S4.3 的离线候选：`resume_recovery.py` 要求 generation、backup/journal/resource/auth 高水位、历史保留、预算不增加、资源收敛和外部范围清空事实全部满足才允许 resume。
- 预算 reducer 修复了最高修订版本出现未知值后，迟到的低版本事实改写 current subtotal 的问题，并有持久化回归用例。

本轮定向验证：252 项通过，1 项明确跳过（Windows/macOS 实际适配器与 OS 锁）。另有调度器独立回归命令；全量历史套件仍保留既知的两个基线失败：Python 3.9 缺少 `sys.stdlib_module_names` 的无副作用导入检查，以及旧等待行为测试。

仍未完成：真实 Git currentness（HEAD/dirty/untracked/浅克隆等组合接线）、多上游授权/撤销与显式合流、真实 PID/boot/OS 锁、provider 隐藏调用发现、跨阶段 09/10 投影、outbox 消费重建和 F01–F30 故障注入。对应矩阵继续保持 `LOCAL_PARTIAL` 或 `NOT_RUN`，不升级为 `PASS`。
