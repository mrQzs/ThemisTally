# TASK: 13-s3-1-trigger-dedupe-singleflight

## Identity
- plan_version: 1
- repository: Code-Kit
- base_sha: cf44ae17fa2722cd998c5991722a0db7e373d7a8
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: bb/step-5-preview · thinking high
- thinking: high

## Goal
按阈值、阶段边界或主模型显式请求触发 Observer，并以 request、游标、来源集合和配置指纹去重。

## Non-goals
- 不调用真实 observer model/provider、Pi、第二 CLI、原生平台、host push 或外部连接器；不读取凭据、不安装依赖、不写外部系统。
- 不改变 10 的确定性事实投影、03 授权/锁、07 预算所有权、正式合同/审核/发布状态；附件文档不扩大授权。

## Repository facts
- 基线：cf44ae17fa2722cd998c5991722a0db7e373d7a8；当前 01–12 已接受接口及 13 文档为输入，Observer 尚未形成生产接线。
- 入口与约定：10 提供 project brief/event/cursor，04 提供调用事件，07 提供预算，03 提供授权；本任务只在 Scope 内实现。
- 工具链：Python 3.9/3.12、现有 unittest、compileall、pi_dispatch 合同校验；不新增依赖。
- 基线检查：执行前运行 V02–V04；真实模型和原生平台能力保持 NOT_RUN/BLOCKED。

## Scope
- allowed_modified_files:
  - 无
- allowed_new_files:
  - tests/test_13_observer_scheduler.py
- allowed_deleted_files: 无
- forbidden_paths: AGENTS.md, .agent/runs/**, .agents/**, .claude/**, .codex/**, .pi/**, scripts/pi_dispatch.py, scripts/dispatch-pi.sh
- dependency_changes: forbidden
## Behavior contract
- B01：相同输入不重复消费预算；并发相同范围只有一个活动请求；Observer 自身完成事件不会再次触发同范围；新事件留到下一游标。
- B02：输入：ObserverRequest、项目事件游标、S3 预算接口。
- B03：输出：触发/去重/单飞调度器及并发测试。
- B04：失败保留结构化状态并停止；不吞错、不盲目重试、不自动换模型；回滚只触碰本合同 Scope 内新文件。

## Steps
1. 读取 Repository facts 与固定基线，确认前置阶段已接受；不一致即停止并报告。
2. 按 B01–B04 实现 实现触发去重与单飞，只修改 Scope 内文件。
3. 补充并运行 tests.test_13_observer_scheduler 的正负和最小变异测试；保留失败分类与证据。
4. 运行 Validation commands，检查范围、编译与既有回归。
5. 写执行报告；遇到未定义行为、真实能力需求或合同冲突即停止。

## Validation commands
- V01（必要）：python -B -m unittest tests.test_13_observer_scheduler -q · cwd：仓库根 · 超时：600s · 期望退出码：0
- V02（必要）：python -B -m unittest tests.test_dispatch -q · cwd：仓库根 · 超时：600s · 期望退出码：0
- V03（必要）：python -B -m compileall -q scripts/codekit tests · cwd：仓库根 · 超时：180s · 期望退出码：0
- V04（必要）：git diff --check · cwd：仓库根 · 超时：60s · 期望退出码：0

## Definition of done
- D01：实现触发去重与单飞 的行为契约及最小负例可复核；证据：V01、review。
- D02：编译、既有调度器回归与 diff 检查通过，且所有改动在允许集合内；证据：V02、V03、V04、scope。
- D03：失败/未知/未运行真实能力有明确状态和证据，不把离线夹具写成生产 PASS；证据：review。

## Stop conditions
- 基线、前置接口、签名或必要文件与 Repository facts 不符。
- 必须修改 Scope 外文件、安装依赖、读取凭据、写外部系统或调用真实模型/平台才能继续。
- 行为、DoD 或输入输出定义冲突；停止并记录 contract_conflicts。
- 达到单轮时间上限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 时间分配：调查 15 分钟；实现与补测 50 分钟；验证 20 分钟；报告 10 分钟。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D03、命令与退出码、Scope、证据路径、失败分类、NOT_RUN/BLOCKED 能力及是否需要新合同版本。

## Forbidden
- 不修改本合同、AGENTS.md、代理规则、调度脚本、权限配置或 agent runs 原始证据。
- 不删除、跳过或弱化测试来获得通过；不提交、不推送、不合并、不部署。
- 不更换模型/提供商，不调用未授权的外部服务，不读取或输出凭据。
