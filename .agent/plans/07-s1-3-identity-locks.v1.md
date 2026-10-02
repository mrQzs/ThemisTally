# TASK: 07-s1-3-identity-locks

## Identity
- plan_version: 1
- repository: Code-Kit
- base_sha: 175653ebbe3059c012166dacfbf13b7eac67b41f
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: commit, push
- executor: step/step-5-preview · thinking high

## Goal
定义 host/boot/environment/worktree/module/interface/resource identity，阻断 PID 复用、路径别名和共享资源误并行。

## Non-goals
- 不读取凭据，不调用真实 provider，不安装依赖，不修改 AGENTS.md、调度脚本或合同文件。
- 不把纯模型、fixture 或离线证据标成生产接线完成。

- planner_owned_protected_paths:
  - scripts/codekit/**
  - schemas/**
- execution_lane: main-model（Pi dispatchable: false）

## Repository facts
- 入口：当前核心实现位于 scripts/codekit/；对应测试位于 tests/；参考矩阵见 docs/code-kit-v2/07-workflows-and-scheduling-审阅增强版.md。
- 调用关系：现有模块以纯校验器、SQLite 原型和注入式探针为主；真实 03/04/05/06/09/10 接线尚未完成。
- 工具链：Python 3.9/3.12，无项目依赖锁文件；调度器为 scripts/dispatch-pi.sh。
- 基线检查：定向 195 项 unittest 通过；Pi doctor 当前阻塞（模型/凭据不可用）；不得把纯原型结果写成生产 PASS。

## Scope
- allowed_modified_files:
  - tests/test_identity_locks.py
- allowed_new_files:
  - tests/test_identity_locks.py
- allowed_deleted_files: 无
- forbidden_paths: .agent/**, .agents/**, .claude/**, .codex/**, .pi/**, AGENTS.md, scripts/pi_dispatch.py, scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：使用固定、版本化、可追溯的事实和证据，输出确定性状态及原因。
- 边界输入：缺失、过期、撤销、未知、重复、乱序、别名、并发和恢复状态必须保守阻塞或保留 unknown。
- 错误与重试：错误码稳定；同键同指纹可重放，内容冲突必须拒绝；未知外部状态不得自动重试。
- 并发、取消与状态变化：所有权威状态变更使用 CAS/事务；取消和停止保留历史与迟到证据。
- 兼容性：保持已有公共 API 和 195 项现有测试；新增字段必须版本化或有兼容默认值。

## Steps
1. 核对 base_sha、符号和 Scope；不一致立即停止并报告。
2. 按 Goal 和 Behavior contract 实现最小变更，不扩大到真实外部系统。
3. 添加覆盖每条行为规则的回归测试或证据记录。
4. 运行 Validation commands，保存原始输出和失败指纹。
5. 最后一条消息写执行报告；任何未定义语义标记为 blocked。

## Validation commands
- V01（必要）：`python -m unittest tests.test_workflow tests.test_readiness tests.test_baseline_binding tests.test_git_probe tests.test_git_ancestor tests.test_coverage tests.test_claim_model tests.test_scheduler_store tests.test_parallel tests.test_budget tests.test_budget_store_v2 tests.test_retry tests.test_atomic_claim_budget tests.test_acceptance tests.test_recovery` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配：`Ran\s+[1-9]\d* tests`
- V02（必要）：`python -m compileall -q scripts/codekit tests` · cwd：仓库根 · 超时：120s · 期望退出码：0
- V03（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0

## Definition of done
- D01：定义 host/boot/environment/worktree/module/interface/resource identity，阻断 PID 复用、路径别名和共享资源误并行。；证据：V01。
- D02：未知、重复、乱序、并发或恢复输入不会被静默当作成功；证据：V01。
- D03：所有修改都在允许集合内且无依赖变化；证据：scope、V02、V03。
- D04：既有测试未删除、跳过或弱化；证据：review。

## Stop conditions
- 基线、接口或必要环境与 facts 不符。
- 必须修改未授权路径、安装依赖、访问凭据或写入外部系统。
- 合同语义冲突，或真实运行时/凭据缺失导致无法证明目标。
- 达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 时间分配：调查 15%，实现 55%，测试 20%，报告 10%。

## Forbidden
- 不修改本合同、代理规则、权限配置、调度脚本或受保护的规划路径。
- 不删除、跳过或弱化测试；不提交、不推送、不合并、不部署。

## Report back
- 逐项说明 D01–D04、自检命令结果、证据路径、遗留问题和阻塞原因。
- 执行器不得提交或推送；通过后的 commit/push 由规划端按授权完成。
