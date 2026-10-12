# TASK: 【待填：task-id】

<!-- 保存为 .agent/plans/<task-id>.vN.md。章节标题（英文）由校验器检查，不要改名；所有【待填…】都要替换。
     Pi 读这份 Markdown，调度器执行 JSON，校验器会逐项比较二者（见 contract-guide.md 第九节）：
     Identity 中的版本、基线、风险、授权与执行模型，Scope 中的路径与依赖策略，Budget 的三个数值，
     以及每个检查的命令参数，都必须与 JSON 一致。 -->

## Identity
- plan_version: 【待填：N】
- repository: 【待填：仓库名】
- base_sha: 【待填：40 或 64 位完整提交 ID】
- risk_level: 【待填：low | medium | high】
- authorized_actions: local_edit, local_test
- integration_actions: 【待填：none | local_branch | commit | open_pr | …（只写用户已经授权的）】
- executor: 【待填：provider/model】 · thinking high

## Goal
【待填：用可观察的输入、输出与状态变化描述目标，一到三句】

## Non-goals
- 【待填：本次明确不改变的行为、接口与模块】

## Repository facts
- 入口：【待填：路径与符号】
- 调用关系与现有约定：【待填】
- 工具链与锁文件：【待填：版本与路径】
- 基线检查：【待填：命令、结果；已知失败写用例与错误指纹】

## Scope
- allowed_modified_files:
  - 【待填：确切路径，每行一个】
- allowed_new_files:
  - 【待填：确切路径】
- allowed_deleted_files: 无
- forbidden_paths: 【待填：可选，额外禁止的路径】
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：【待填】
- 边界输入：【待填】
- 错误与重试：【待填】
- 并发、取消与状态变化：【待填：或写“不适用”及理由】
- 兼容性：【待填：公开 API、数据与格式】

<!-- 校验/权限/摘要任务按 test-design.md 写与规则 ID 对应的证据：合法基线、唯一变化、
     精确错误或结果、最小变异及预期失败用例。不要在多处重写同一行为。 -->

## Steps
1. 读取 Repository facts 中的文件，确认签名与基线一致；不一致就停止并报告。
2. 【待填：按已确定设计实现的最小变更】
3. 【待填：需要补充的回归测试及其位置】
4. 运行 Validation commands 中与改动相关的检查，记录命令与结果。
5. 写执行报告；遇到合同未定义的行为，停止并报告。

## Setup
<!-- 可选。prepare 阶段在 worktree 中运行的准备命令（例如安装依赖），derive-json 会把这一节转写成 JSON 的 setup；
     validate 不比较它。没有准备命令时整节删掉。 -->
- S01：`【待填：如 npm ci --no-audit --no-fund】` · cwd：仓库根 · 超时：900s

## Validation commands

必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。需要截短输出又要保留真实退出码时，直接运行检查命令即可（工具会返回完整输出与退出码）；确要截短，写成 `T=$(mktemp -d); <命令> > "$T/out" 2>&1; echo "exit=$?"; tail -n 20 "$T/out"; rm -rf "$T"`，删除之后不再接任何命令，也不要写到 `/tmp/v01.txt` 这类固定路径。不要自己做变异检查（故意改坏实现，包括把仓库复制到临时目录去改）：验收端会在固定候选上做。

- V01（必要）：`【待填：命令】` · cwd：仓库根 · 超时：【待填】s · 期望退出码：0 · 输出须匹配：`【待填：如 Tests \d+ passed】`

## Definition of done
- D01：【待填：行为】；证据：V01 中的【待填：用例】；目的：【待填：过了检查不是目标，真正要保住的是什么】。
- D02：所有修改都在允许集合内；证据：scope（调度器生成的范围报告）。
- D03：没有删除、跳过或弱化既有测试；证据：review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: 【待填：金额与币种，或 tracking-only】
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：【待填：调查、实现与补测、必要检查、最终报告的预计用时；总计不超过单轮时限】

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
