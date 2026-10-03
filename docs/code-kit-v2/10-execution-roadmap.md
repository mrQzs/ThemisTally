# Code-Kit v2：10 项目状态与恢复简报分阶段路线图

基线：`bbe0121c15ad9ac3b78f34c1683a08f7f81f9178`；当前离线实现推进到 `3046dc6`。附件 `10-project-state-and-brief-审阅增强版.md` 只作为需求矩阵和设计参考；不替代 `AGENTS.md`、合同或复审结论。

## 目标与边界

10 只登记受信来源、归约可重建项目状态、发布确定性视图和读取回执。它不批准、撤销、记账、领取、重试、集成、杀进程或唤醒主会话；07 是预算真相源，03/07/09 仍是授权、准入和发布权威。真实 provider、Pi、原生平台、宿主通知、断电/强杀和外部连接器保持 `NOT_RUN/BLOCKED`。

## 阶段与子任务

| 阶段 | 子任务 | 主要出口 | 依赖 |
|---|---|---|---|
| S0 规范与基线 | `10-s0-1-baseline-owners`；`10-s0-2-contract-traceability`；`10-s0-3-fixtures-environment-gates` | 路线图、所有权、A/F 矩阵、离线夹具和环境门禁 | 09 当前提交 |
| S1 来源契约 | `10-s1-1-source-schema-resource-ref`；`10-s1-2-source-verification`；`10-s1-3-source-fixtures` | ProjectEvent、SourceKey、来源核验、历史映射和严格负例 | S0 |
| S2 登记与纯投影 | `10-s2-1-event-index-append`；`10-s2-2-state-reducer`；`10-s2-3-decisions-budget` | 单写者登记、多维状态、决定和预算只读观察 | S1 |
| S3 补录与恢复 | `10-s3-1-source-scanners`；`10-s3-2-tail-recovery`；`10-s3-3-generation-rebuild` | 固定切面补录、损坏分类、重建和代际 RESET | S2 |
| S4 status/brief | `10-s4-1-atomic-view-package`；`10-s4-2-brief-renderer`；`10-s4-3-read-receipts` | 不可变视图包、current CAS、确定性 brief、读取回执 | S3 |
| S5 09/技能检查点 | `10-s5-1-authority-adapters`；`10-s5-2-project-cli-checkpoints`；`10-s5-3-legacy-compatibility` | 09/07/03/05 只读适配、查询入口、旧语义与新会话恢复 | S4 |
| S6 可选通知与验收 | `10-s6-1-delivery-platform`；`10-s6-2-fault-matrix`；`10-s6-3-independent-release-gate` | pull/平台边界、F01–F30、A01–A30、独立复审和 release gate | S5 |

## 合同与阶段门

21 份子任务各有固定 Markdown/JSON 合同，合同基线为上述完整 SHA；已派遣版本不修改，范围变化必须出新版本。每阶段先跑定向测试、Schema/严格 JSON 校验、compileall 和 `git diff --check`，再独立复审、提交和推送；后续阶段只从新提交开始。

S0 只冻结边界和证据。S1/S2 建立来源和归约；S3 做补录与恢复；S4 固定视图和简报；S5 接入 09/技能检查点；S6 只实现可选通知边界并输出验收门禁。真实能力不可用时只能记录 `NOT_RUN/BLOCKED`。

## 当前实施状态

| 阶段 | 离线状态 | 已推送提交 | 生产边界 |
|---|---|---|---|
| S0 | ACCEPTED_WITH_EXCEPTION | `6590565` | 不涉及运行能力 |
| S1 | ACCEPTED_WITH_EXCEPTION | `f32330c` | 真实来源/平台 NOT_RUN/BLOCKED |
| S2 | ACCEPTED_WITH_EXCEPTION | `23c5110` | 03/07 权威仍为只读观察 |
| S3 | ACCEPTED_WITH_EXCEPTION | `e88e557` | 断电/网络盘/原生恢复 NOT_RUN/BLOCKED |
| S4 | ACCEPTED_WITH_EXCEPTION | `eed5d33` | 宿主 current/通知接线 NOT_RUN/BLOCKED |
| S5 | ACCEPTED_WITH_EXCEPTION | `7497311` | 03/07/09/05、Pi/provider NOT_RUN/BLOCKED |
| S6 | ACCEPTED_WITH_EXCEPTION | `4d40de6` | 发布门禁 BLOCKED |

后续离线收口提交：`86c7e66`（补录、修订链、currentness、请求映射）、`fc520e5`（读取持久化、尾部备份、分页扫描、brief 脱敏）、`3046dc6`（回退防护、receipt 自校验、来源覆盖）。这些提交只提升离线 `PARTIAL` 覆盖，未解除真实发布门禁。

## 复用与禁止

优先复用 `scripts/codekit/protocols.py`、`projections.py`、`builtin_projections.py`、`projection_store.py` 的严格 JSON、游标、代际和尾部恢复原语，不建立第二套预算或授权账本。10 的 ProjectEvent、SourceScanReport、SourceVerificationSnapshot、ProjectState、DecisionRecord、ProjectViewManifest、BriefReadReceipt、DeliveryReceipt、RecoveryReport 必须绑定来源字节、范围、版本和观察边界。

不得修改 `AGENTS.md`、现有 `.agent/runs/`、旧 verdict/approval/合同、`scripts/pi_dispatch.py` 或 `scripts/dispatch-pi.sh`；不得把附件附录参考测试、07/08 离线原语或模型自述写成生产证据。
