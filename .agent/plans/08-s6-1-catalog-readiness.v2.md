# TASK: 08-s6-1-catalog-readiness

## Identity
- plan_version: 2
- repository: Code-Kit
- base_sha: 86a92fcb8cc062a15063685e9b762d5780bb0b53
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: commit, push
- executor: step/step-5-preview · thinking high

## Goal
实现七插件目录、三配方选择和 09 readiness 投影，明确能力、限制、证据和缺口。

## Non-goals
- 不修改既有 07 调度、G0–G6、授权、预算、候选记录或 verdict 核心语义。
- 不读取凭据，不安装依赖，不访问网络或真实 provider，不把 synthetic 证据标成生产完成。

## Repository facts
- 入口：`scripts/codekit/`、`schemas/`、`tests/`；当前 07 workflow 和调度器已存在。
- 08 插件只能生成业务产物和 CheckPlan；核心调度器拥有候选、授权、预算、检查登记和 verdict。
- Windows Python 3.9 缺 `jsonschema`/`markdown-it-py`；WSL Python 3.12 可执行离线 Schema/AST 检查。
- Pi、Windows/macOS 原生环境、provider 和 09/10 真实连接器缺失时只能记录 BLOCKED/NOT_RUN。

## Scope
- allowed_modified_files:
  - tests/test_builtin_catalog.py
  - docs/code-kit-v2/08-09-readiness.md
- allowed_new_files:
  - tests/test_builtin_catalog.py
  - docs/code-kit-v2/08-09-readiness.md
- allowed_deleted_files: 无
- forbidden_paths: .agent/**,.agents/**,.claude/**,.codex/**,.pi/**,AGENTS.md,scripts/pi_dispatch.py,scripts/dispatch-pi.sh
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

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
- 输入、输出、版本和身份字段必须确定性、封闭并可用 sha256 复核。
- 候选、来源、检查集和环境漂移必须拒绝旧结果复用；未知状态保留为 UNKNOWN/BLOCKED。
- 离线 fixture、synthetic、LOCAL_REFERENCE、NOT_RUN 与生产 PASS 必须分开；不得绕过 03/05/07 核心门禁。

## Steps
1. 核对完整 base_sha、现有 01–07 接口和 Scope；不一致立即停止。
2. 按 S0 决策和 Behavior contract 实现最小离线变更，不扩展真实外部系统。
3. 添加覆盖每条规则的正例、负例、漂移和未知状态测试。
4. 运行 Validation commands，保存命令、返回码和证据路径。
5. 以执行报告说明未运行平台、provider 或连接器，不把它们记为 PASS。

## Validation commands
- V01（必要）：`python -m compileall -q scripts/codekit tests` · cwd：仓库根 · 超时：180s · 期望退出码：0 · 输出须匹配：``
- V02（必要）：`python -m unittest discover -s tests -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``
- V03（必要）：`python tests/test_dispatch.py` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``
- V04（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配：``

## Definition of done
- D01：目标接口/产物和全部行为规则在允许文件内实现，并有正负例证据；证据：V01, V02。
- D02：漂移、越界、重复、缺失、未知和伪造输入不能静默成功；证据：V02, V03。
- D03：离线结果与真实平台/provider/生产接线状态明确分离；证据：V02, scope。
- D04：既有测试未删除、跳过或弱化，改动范围可由 scope 报告复核；证据：V03, V04, scope。

## Stop conditions
- 基线、接口、Scope 或必要环境与 Repository facts 不符。
- 必须修改禁止路径、安装依赖、访问凭据或外部系统。
- 合同语义冲突、测试失败无法归属，或达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 时间分配：调查 15%，实现 55%，验证 20%，报告 10%。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D04、命令与结果、证据路径、遗留问题和阻塞原因。

## Forbidden
- 不修改本合同、代理规则、权限配置或调度脚本。
- 不删除、跳过或弱化测试；不提交、不推送、不合并、不部署。

