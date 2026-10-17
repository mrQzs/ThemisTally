# TASK: 10-s0-1-baseline-owners

## Identity
- plan_version: 1
- repository: Code-Kit
- base_sha: bbe0121c15ad9ac3b78f34c1683a08f7f81f9178
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: bb/step-5-preview · thinking high

## Goal
规范与来源所有权：核对旧 status/metrics/mark/wait 和 01/03/05/07/09 的真实接口；固定只读所有权、旧语义和未实现边界。

## Non-goals
- 不读取凭据、不安装依赖、不调用真实 provider/Pi/宿主，不修改 runs、授权/预算账本或业务调度。

## Repository facts
- 当前冻结基线 bbe0121c15ad9ac3b78f34c1683a08f7f81f9178；合同创建前工作区干净。
- 现有 07/08/09 投影在 projections.py、builtin_projections.py、projection_store.py、planner_projection.py；没有 10 项目记录族、来源扫描、视图包或读取回执。
- 基线定向回归 57 项：56 通过、1 环境跳过；Windows Python 3.9.23，已有 WSL Ubuntu 24.04 可复核 Schema，禁止安装依赖。
- 依赖：none。本 v1 固定设计基线；进入下一阶段前出新版本绑定前置已接受提交，不隐式漂移。
- owner：核心 scripts/codekit/**、schemas/** 由主模型直接维护；Pi 尚未派遣，若后续委派必须另出外围合同。
- 验收覆盖：A10,A28,A30；A01–A09 原文保留，A10–A30 为采纳的增强建议；F 真实场景不以合成 PASS 代替。

## Scope
- allowed_modified_files:
  - 无
- allowed_new_files:
  - docs/themis-tally-v2/10-execution-roadmap.md
- allowed_deleted_files: 无
- forbidden_paths: AGENTS.md, .agent/**, .agents/**, .claude/**, .codex/**, .pi/**, scripts/pi_dispatch.py, scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- B01：核对旧 status/metrics/mark/wait 和 01/03/05/07/09 的真实接口；固定只读所有权、旧语义和未实现边界。
- B02：仅消费固定字节、注册来源和明确观察切面；未知/缺失/冲突不推定成功，来源字符串不是身份认证。
- B03：10 不赋予批准、执行、发布或额外预算。07 是预算真相源；brief/status 是阅读辅助，dispatch_eligibility=not_evaluated。
- B04：原始来源和旧证据只读，恢复/维护与普通查询分开；输出、回执和遥测不改变历史业务事实。

## Inputs and outputs
- 输入：固定基线、前置阶段已接受接口、原始 10 文档和 A10,A28,A30，允许范围内的离线 fixture。
- 输出：B01–B04 的实现/测试或文档、明确 LOCAL_REFERENCE/NOT_RUN/BLOCKED 结论和独立复审输入。
- 证据：命令原始输出由工具捕获；调度器证据只读；规划端报告在 .agent/reviews/，不得手工补造 runs。

## Steps
1. 确认基线及前置接口，冻结 B01–B04。
2. 仅在 Scope 中实现设计，逐规则增加合法基线和唯一变化负例；缺行为定义停止报告。
3. 运行 Validation commands 并提供真实退出码、覆盖项和未运行能力。

## Validation commands
- V01（必要）：`python -B -m unittest tests.test_projections -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`Ran `
- V02（必要）：`python -B -m compileall -q scripts/codekit tests` · cwd：仓库根 · 超时：180s · 期望退出码：0
- V03（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0

## Definition of done
- D01：B01–B04 与 A10,A28,A30 的离线覆盖有可复核定向测试或文档；最小变异不能仍通过；证据：V01、review。
- D02：Scope、严格 JSON/Schema 和编译检查通过，未改历史证据或削弱旧测试；证据：V02、V03、scope、review。
- D03：真实环境和连接器缺口逐项标 NOT_RUN/BLOCKED，合成通过仅 LOCAL_REFERENCE；证据：review。

## Failure and rollback
- 解析、来源冲突、写入 unknown、CAS 失败、环境 skip 分别报告；停止后不换 ID、不抹未知或自动重试业务调用。
- 仅回退 Scope 内代码/测试/Schema；保留前置提交、唯一原字节、确认和新生成审计记录。尾部修复不触碰 runs。

## Stop conditions
- 前置未接受、基线不符、需越界修改、合同冲突或必要环境缺失。
- 需要安装依赖、读取凭据、外部写入或改变授权/预算；达到时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- executor profile dormant；真实 Pi 不派遣，范围变更用新版本合同。

## Report back
- 逐项报告 D01–D03、命令与退出码、Scope、故障分类和真实未运行项；自述不替代独立复审。

## Forbidden
- 不修改合同、规则、权限、调度脚本、runs 或凭据；不跳过/削弱测试，不安装依赖。
- 普通执行器不提交、推送、合并或部署；主模型按已有阶段集成授权另行执行。
