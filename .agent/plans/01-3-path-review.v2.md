# TASK: 01-3-path-review

## Identity
- plan_version: 2
- repository: Code-Kit
- base_sha: 1caeb6e7ad7bfab45b0e4576a30e2f2fa05ed86b
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: step/step-5-preview · thinking high

## Goal
为 01.3 路径审阅与平台边界测试 建立离线、确定性的测试、fixture 与文档证据；不修改产品核心路径。

## Non-goals
- 不修改 schemas/**、scripts/codekit/** 或真实 provider/外部系统。
- 不安装依赖、不读取凭据、不把离线证据标为生产接线。

## Repository facts
- 入口：01-baseline-and-protocols-审阅增强版.md；产品实现位于 scripts/codekit/，本任务只增加测试、fixture、文档和外围适配器。
- 调用关系与现有约定：Python 标准库 unittest，测试按文件单独运行；unknown、NOT_RUN、BLOCKED 必须保留。
- 工具链与锁文件：Python 3.9/3.12，无项目依赖锁文件；调度器 scripts/dispatch-pi.sh。
- 基线检查：基线 SHA 为 9a75389b1907927c5ce6a779094e1c099cdc3d4b；以离线静态检查和新增文件存在性为证据。

## Scope
- allowed_modified_files:
  - docs/contracts/01-3-path-review.v2.md
- allowed_new_files:
  - tests/test_codekit01_path_review.py
  - docs/contracts/01-3-path-review.v2.md
- allowed_deleted_files: 无
- forbidden_paths: schemas/**, scripts/codekit/**, .agent/**, .agents/**, .claude/**, .codex/**, .pi/**, AGENTS.md, scripts/pi_dispatch.py, scripts/dispatch-pi.sh
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md、.agent/、.agents/、调度脚本及产品核心路径

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
- 正常输入：固定 fixture 产生确定性结果、稳定错误码和可追溯文档证据。
- 边界输入：缺失、未知、重复、乱序、过期、冲突和平台不适用输入必须保守拒绝或保留 unknown/NOT_RUN/BLOCKED。
- 错误与重试：同输入可重放；冲突不得静默覆盖；不得借缓存、fixture 或模型自述放行。
- 并发、取消与状态变化：仅以 fixture 验证既定 CAS/generation 规则，不接入真实进程。
- 兼容性：不改变现有公共 API、schemas/**、scripts/codekit/** 和既有测试；测试使用标准库。

## Steps
1. 核对 base_sha、设计文档和 Scope；不一致就停止并报告。
2. 在允许路径内编写确定性 fixture、回归测试和说明文档，逐条覆盖 Behavior contract。
3. 运行 Validation commands，记录真实输出。
4. 写执行报告；未定义语义标记 blocked。

## Validation commands
- V01（必要）：`python -c "from pathlib import Path; p=Path(r'tests/test_codekit01_path_review.py'); assert p.exists() and p.stat().st_size>0; print('TEST_ARTIFACT_OK')"` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配：`TEST_ARTIFACT_OK`
- V02（必要）：`python -c "from pathlib import Path; p=Path(r'docs/contracts/01-3-path-review.v2.md'); assert p.exists() and p.stat().st_size>0; print('DOC_ARTIFACT_OK')"` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配：`DOC_ARTIFACT_OK`
- V03（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0

- G01（必要）：`python tests/test_dispatch.py` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``

- G02（必要）：`python -m compileall -q scripts/codekit tests` · cwd：仓库根 · 超时：180s · 期望退出码：0 · 输出须匹配：``

- G03（必要）：`python -m unittest discover -s tests -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``

## Definition of done
- D01：测试与 fixture 覆盖 Behavior contract；证据：V01。
- D02：文档明确离线范围、未知状态和不宣称真实接线；证据：V02。
- D03：未修改产品核心、Schema 或依赖；证据：scope、V03。
- D04：既有测试未删除、跳过或弱化；证据：review。

## Stop conditions
- 基线、设计文档或接口与 facts 不符。
- 必须修改允许范围之外的文件、安装依赖、访问凭据或写外部系统。
- 合同语义冲突或出现未定义业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计。
- 时间分配：调查 15%，实现与 fixture 55%，检查 20%，报告 10%。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D04、自检命令结果、证据路径、遗留问题和阻塞原因。

## Forbidden
- 不修改本合同、代理规则、权限配置、调度脚本或受保护产品路径。
- 不删除、跳过或弱化测试；不提交、不推送、不合并、不部署。

