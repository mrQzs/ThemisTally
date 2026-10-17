# Code-Kit v2：13 可选摘要 Observer 分阶段执行路线图

基线：`cf44ae17fa2722cd998c5991722a0db7e373d7a8`（规划合同生成时的完整提交）。

本路线图把 `docs/themis-tally-v2/13-optional-observer.md` 的提议拆成七个阶段、21 个可独立验收子任务。附件文档是需求矩阵和设计参考；`AGENTS.md`、本路线图、各合同及独立复审决定授权边界。Observer 默认关闭，只消费 10 的确定性 brief、事件和来源引用，不拥有审批、执行、发布、事实写入或预算扩权能力。

## 阶段门

| 阶段 | 子任务 | 出口 | 依赖 |
|---|---|---|---|
| S0 合同与证据基线 | `13-s0-1-baseline-owners`；`13-s0-2-traceability-matrix`；`13-s0-3-fixtures-environment-gates` | 所有权、A01–A09/提议 I 项矩阵、离线夹具和真实能力门禁 | 01–12 已接受接口 |
| S1 协议与来源 | `13-s1-1-observer-request-schema`；`13-s1-2-source-bundle-validation`；`13-s1-3-observer-output-schema` | 严格请求/输出记录、ResourceRef、游标和来源闭包 | S0 |
| S2 隔离与脱敏 | `13-s2-1-readonly-context-boundary`；`13-s2-2-redaction-and-size-limits`；`13-s2-3-suggestion-fact-separation` | 只读输入、脱敏/大小限制、事实/推断/建议正交 | S1 |
| S3 调度与预算 | `13-s3-1-trigger-dedupe-singleflight`；`13-s3-2-budget-reserve-settlement`；`13-s3-3-timeout-cancel-recovery` | 阈值触发、去重、单飞、预算预留结算、超时取消和恢复 | S1、S2；可并行 |
| S4 离线适配与存储 | `13-s4-1-offline-observer-adapter`；`13-s4-2-result-extraction-and-unknowns`；`13-s4-3-observer-record-store` | 离线确定性适配器、唯一可信结果提取、可重建调用记录 | S2、S3 |
| S5 投影与交接 | `13-s5-1-project-brief-pull-integration`；`13-s5-2-host-notification-boundary`；`13-s5-3-rebuild-and-currentness` | 10 brief 拉取、宿主通知边界、过期/重建/游标语义 | S4 |
| S6 价值评估与发布门禁 | `13-s6-1-value-evaluation-fixtures`；`13-s6-2-a01-a09-independent-acceptance`；`13-s6-3-release-gate-and-runbook` | A01–A09 验收、故障矩阵、真实能力阻塞记录、关闭默认策略 | S0–S5 |

## 统一规则

- 每个子任务对应 `.agent/plans/<task-id>.v1.md` 与 `.json`；合同固定基线、范围、输入/输出、验证、DoD、失败处理和停止条件。
- 合同的 `base_sha` 固定为本路线图生成时的基线；阶段通过并提交后，后续执行合同须由规划端以新版本更新基线，不能在过期基线上派遣。
- `scripts/codekit/**`、`schemas/**` 由主模型直接维护；Pi 只处理合同允许的外围测试、fixture、文档和适配层，除非后续合同明确授予核心路径。
- 禁止修改 `AGENTS.md`、调度脚本、`.agent/`、`.agents/`、`.claude/`、`.codex/`、`.pi/`；不安装依赖、不读取凭据、不写外部系统。
- 真实 observer model/provider、第二 CLI、原生平台、Pi、host push 和外部连接器先记录 `NOT_RUN/BLOCKED`。离线 stub 只证明协议和降级，不得宣称生产接线或节省比例。
- 观察建议不能改变事实投影、任务状态、审批/授权、预算、合同或 release gate。observer 关闭、失败、超时、未知用量、响应丢失时，10 的确定性 brief 和恢复流程必须保持可用。

## 验证与提交

每个实现子任务至少运行目标 unittest、`python -B -m compileall -q scripts/codekit tests`、相关 Schema 校验和 `git diff --check`。每阶段由独立复审核对固定候选、范围、故障证据和未运行能力；阶段通过后再独立提交并推送。当前合同只完成规划，不派遣 Pi。

## 真实能力门禁

本轮不调用摘要模型，不打开后台心跳，不选择 profile，不发起真实 provider/CLI/进程/宿主通知，也不测量 token 节省。上述能力在没有单独授权、精确模型和预算前保持 `NOT_RUN/BLOCKED`；默认发布决策为关闭 observer。
