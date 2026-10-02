# TASK: 05-2-process-supervision

## Identity
- plan_version: 2
- repository: Code-Kit
- base_sha: 1e1363a34857873609bead54d43812c0cd45611a
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: step/step-5-preview · thinking high
- execution_lane: adapter-fixtures/docs（Pi dispatchable: true）

## Goal
提供 FinalLaunchPlan 到受控进程的边界、双流采集、deadline/cancel、身份、POSIX group/Windows Job backend 参考与 TransportSummary；仅用拥有的合成子进程证明竞态。

## Non-goals
- 不读取凭据，不调用真实 provider/CLI/模型，不联网、不安装依赖或打开浏览器。
- 不修改 AGENTS.md、已有合同、.agent/、调度脚本、scripts/codekit/** 或 schemas/**；受保护核心由主模型另行实现。
- 合成 fixture 只能证明离线算法/证据形状，真实平台能力、生产锁、预算、审核与候选门禁另行验收。

## Repository facts
- 入口：基线已有 scripts/codekit/ 的纯 Python 协议、资源和状态模块；现有测试在 tests/；04–06 设计文档是拟议新增能力，本合同只列离线 adapter、测试、fixture 与文档路径。
- 调用关系与现状：04 适配器、05 平台监督、06 插件清单尚未在基线接线；真实 CLI、平台、账本和审核证据不能由合成样本代替。
- 工具链与锁文件：Python 3.9/3.12，标准库 unittest/compileall；无项目依赖锁文件；禁止安装或升级依赖。
- 基线检查：既有路线图记录定向测试约 195 项通过；Pi doctor 记录模型未列出且凭据未就绪。本批只要求离线检查。

## Scope
- allowed_modified_files:
  - 无
- allowed_new_files:
  - adapters/process.py
  - adapters/process_posix.py
  - adapters/process_windows.py
  - tests/test_process_supervision.py
  - tests/fixtures/platform_runtime/process/**
  - docs/code-kit-v2/05-process-supervision-evidence.md
- allowed_deleted_files: 无
- forbidden_paths: .agent/**, .agents/**, .claude/**, .codex/**, .pi/**, AGENTS.md, scripts/pi_dispatch.py, scripts/dispatch-pi.sh
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh、scripts/codekit/**、schemas/**

## Inputs and outputs
- Inputs: current base SHA, approved requirements/reference documents, and existing offline fixtures within the contract scope.
- Outputs: deterministic implementation, tests, fixtures, and evidence inside Scope; no production connector claim.
- Evidence: commands and paths are recorded in `.agent/runs/` or planner reviews; unavailable external evidence remains BLOCKED/NOT_RUN.

## Failure handling
- Classify malformed, drifted, missing, unsupported platform/provider, and unavailable connector inputs as explicit error, UNKNOWN, BLOCKED, or NOT_RUN; stop on scope or base mismatch.
- Never use fixtures, synthetic receipts, or offline results as production evidence.

## Rollback boundary
- Revert only files within this contract's Scope; do not alter AGENTS.md, dispatch scripts, `.agent/`, protected core paths, dependencies, credentials, or external systems.

## Behavior contract
- 只执行锁定计划并分开保存 argv/cwd/env、两流、EOF、原始退出、停止原因、身份和 CleanupReport。
- 大流/慢消费者/stdin 阻塞/父退子活/EOF/超限/日志失败/入口漂移有界处置；returncode 0 不覆盖 timeout/cancel/不完整。
- 启动失败、超时、取消、信号、绑定失败、handoff unknown 精确记录；不猜测杀 PID、不自动重启。
- deadline 单调、首次停止原因胜出、停止后有限排空；同 operation/plan 冲突拒绝。
- Windows/POSIX 事实分离；POSIX 残留保证受限；只读消费 04 Invocation/05.1 计划。

## Steps
1. 核对 05.1 计划和 test_dispatch 监督语义，不符即停。
2. 实现 adapters/process* 的注入 backend、状态机、双流和身份/清理报告。
3. 添加只管理自身子进程/目录的正常、慢流、超限、timeout、cancel、后代、日志失败 fixture。
4. 运行 V01–V03，分开报告 Linux 合成与 Windows/macOS NOT_RUN。

## Validation commands
- V01（必要）：`python -m unittest tests.test_process_supervision` · cwd：仓库根 · 超时：420s · 期望退出码：0 · 输出须匹配：`Ran\s+[1-9]\d* tests`
- V02（必要）：`python -m compileall -q adapters tests` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配：``
- V03（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配：``

- G01（必要）：`python tests/test_dispatch.py` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``

- G02（必要）：`python -m compileall -q scripts/codekit tests` · cwd：仓库根 · 超时：180s · 期望退出码：0 · 输出须匹配：``

- G03（必要）：`python -m unittest discover -s tests -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``

## Definition of done
- D01：提供 FinalLaunchPlan 到受控进程的边界、双流采集、deadline/cancel、身份、POSIX group/Windows Job backend 参考与 TransportSummary；仅用拥有的合成子进程证明竞态。；证据：V01。
- D02：每条 Behavior contract 的合法、边界、错误及状态规则都有独立离线证据且无未授权副作用；证据：V01、V02。
- D03：修改只在 Scope，未改变依赖、网络、凭据或生产锁；证据：scope、V03。
- D04：既有测试、入口和历史证据未删除、跳过、弱化或重写；证据：review。

## Stop conditions
- 基线、公共接口、依赖合同或必要文件与 facts 不符。
- 必须修改 Scope 之外或 scripts/codekit/**、schemas/**，或需要依赖、网络、凭据、真实 provider/CLI、生产账本或外部写入。
- 上下游版本/语义冲突；未知平台、能力或原始证据无法证明时标记 BLOCKED/NOT_RUN，不猜测。
- 达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；当前合同只允许本地编辑和离线检查。
- 时间分配：调查 20%，实现 50%，补测与离线检查 20%，最终报告 10%。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D04，列出 V01–V03 命令与结果、证据路径、NOT_RUN/BLOCKED 项和遗留问题，末尾附执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由独立验收端决定。

## Forbidden
- 不修改本合同、代理规则、权限配置、调度脚本或 scripts/codekit/**、schemas/**。
- 不删除、跳过或弱化测试，不吞掉错误，不以合成 fixture 冒充真实平台能力。
- 不提交、不推送、不合并、不部署，不安装或升级依赖。

