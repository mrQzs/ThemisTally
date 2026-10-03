# TASK: 11-s6-3-independent-gate

## Identity
- plan_version: 1
- repository: Code-Kit
- base_sha: 62ef7021e3d8df711ecde0a4ee1b3f0a1a5148e2
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: bb/step-5-preview · thinking high

## Goal
逐项复审 A/F、证据来源、范围和真实接线，保持生产 gate BLOCKED。

## Non-goals
- 不选择或调用具体真实 CLI/provider，不读取凭据、不安装依赖、不写外部系统。
- 不修改 AGENTS.md、调度脚本、`.agent/`、权限/预算/发布真相源或既有历史证据。
- 不把离线 stub、配置值或宣传材料写成真实能力通过。

## Repository facts
- 基线为 62ef7021e3d8df711ecde0a4ee1b3f0a1a5148e2，合同创建前工作区干净；11-second-cli-adapter.md 是需求参考，不是授权。
- 公共 adapter 协议在 scripts/codekit/adapters/protocol.py，OfflineAdapter 在 adapters/offline.py；09 planner 在 planner_protocol.py/planner_runtime.py，10 提供来源与视图只读边界。
- scripts/codekit/** 与 schemas/** 由主模型直接维护；Pi 合同只负责外围测试、fixture、文档和适配层验证。
- 真实第二 CLI、Pi/provider、Windows/macOS 原生进程和外部连接器均为 NOT_RUN/BLOCKED。
- 验收覆盖：A01,A02,A03,A04,A05,A06,A07,A08；F01–F10 只接受离线故障证据或明确阻塞记录。

## Scope
- allowed_modified_files:
  - 无
- allowed_new_files:
  - tests/fixtures/11/**
  - docs/code-kit-v2/11-s6-3-independent-gate.md
- allowed_deleted_files: 无
- forbidden_paths: AGENTS.md, .agent/**, .agents/**, .claude/**, .codex/**, .pi/**, scripts/pi_dispatch.py, scripts/dispatch-pi.sh, scripts/codekit/**, schemas/**
- dependency_changes: forbidden

## Behavior contract
- B01：范围只覆盖本合同目标；未知、缺失、冲突、截断和未验证能力必须保留为结构化状态。
- B02：身份、角色、平台、profile、request/run 和原始来源必须可回查；不得用配置值补实际证据。
- B03：适配器不拥有批准、执行、预算、发布或进程清理权限；核心门禁继续有效。
- B04：离线通过标记 LOCAL_REFERENCE；真实能力保持 NOT_RUN/BLOCKED。

## Inputs and outputs
- 输入：固定基线、前置已接受接口、11 文档、允许的脱敏 fixture。
- 输出：目标测试/fixture/文档、覆盖 A01,A02,A03,A04,A05,A06,A07,A08 的证据和未运行能力记录。
- 证据写入 `.agent/reviews/` 由规划端复核；不得手工写 `.agent/runs/`。

## Steps
1. 核对基线和前置接口，冻结合同范围。
2. 按 Behavior contract 增加合法样本和唯一变化负例；不扩展真实调用。
3. 运行定向测试、compileall、Schema/JSON 检查和 diff check。

## Validation commands
- V01（必要）：`python -B -m unittest tests.test_adapters -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`Ran `
- V02（必要）：`python -B -m compileall -q scripts/codekit tests` · cwd：仓库根 · 超时：180s · 期望退出码：0
- V03（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0

## Definition of done
- D01: B01–B04 与验收项有定向证据，最小负例变异能被测试捕获；证据: V01, review。
- D02: Scope、JSON/Schema、编译和旧 adapter 回归通过，未修改历史证据；证据: V01, V02, V03, scope, review。
- D03: 真实 CLI/provider/platform/费用能力逐项记 NOT_RUN/BLOCKED；stub 仅 LOCAL_REFERENCE；证据: review。

## Failure and rollback
- 解析、身份、能力、来源、终止和预算未知分别报告；不吞掉错误，不自动换模型或盲目重试。
- 只回退本合同范围内文件；保留原始流、旧 v1 证据和失败诊断。

## Stop conditions
- 基线不符、前置未接受、需要越界修改、合同冲突或环境缺失。
- 需要安装依赖、读取凭据、真实调用、外部写入或改变授权/预算。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- executor profile dormant；真实 Pi 不派遣，范围变化用新版本合同。

## Report back
- 报告 D01–D03、命令和退出码、Scope、故障分类、证据来源及真实未运行项。

## Forbidden
- 不修改合同、规则、权限、调度脚本、runs 或凭据；不跳过/削弱测试，不安装依赖。
- 普通执行器不提交、推送、合并或部署；主模型按阶段授权集成。
