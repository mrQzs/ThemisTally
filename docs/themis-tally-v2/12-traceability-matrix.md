# Code-Kit v2：12 集成验收与迁移追踪矩阵

规划基线：`c71014517e3579e5bb465d277a6712c214e565b4`。增强文档只提供需求参考；以下状态是当前目标仓库实施状态，不是附录参考测试的生产验收。

## 原始 12-A01–A09

| ID | 阶段 | 验收主题 | 当前状态 | 证据/缺口 |
|---|---|---|---|---|
| 12-A01 | S0/S1/S6 | 01–11 固定候选证据完整、未完成不 PASS | PARTIAL/NOT_RUN | S0 owners; S1 target; S6 acceptance |
| 12-A02 | S0/S2/S5 | G0–G6、候选/范围/授权/检查/恢复未退化 | PARTIAL/NOT_RUN | 既有 01–11 离线资料；真实集成未运行 |
| 12-A03 | S4 | 三个首批插件离线端到端和内容验收 | LOCAL_REFERENCE | 离线 fixture 可复核；真实插件/模型未运行 |
| 12-A04 | S2/S6 | 三平台实际结果及 Windows 无 Bash | BLOCKED/NOT_RUN | 原生矩阵和真实进程未验证 |
| 12-A05 | S2/S6 | 真实不同 CLI 规划→执行链路 | BLOCKED/NOT_RUN | provider/CLI 真实调用未授权 |
| 12-A06 | S4/S6 | v1 字节/哈希、旧入口与模型选择保持 | PARTIAL | 旧测试可复核；12 迁移现场未验证 |
| 12-A07 | S3/S5/S6 | 迁移失败可回退且工作/证据不丢 | NOT_RUN | 只有离线协议/fixture 计划 |
| 12-A08 | S0/S6 | 规则、技能源/副本和执行基线一致 | PARTIAL/NOT_RUN | 需实际同步器和当前基线证据 |
| 12-A09 | S5/S6 | Observer 关闭仍可规划/执行/审核/恢复，unknown 成本保留 | BLOCKED/NOT_RUN | 真实恢复和费用不可观测场景未运行 |

## 增强建议 12-A10–A29

| ID | 阶段 | 验收主题 | 当前状态 |
|---|---|---|---|
| 12-A10 | S1 | IntegrationTarget 覆盖代码/合同/配置/检查/插件/规则/环境，跨候选拒绝 | PLANNED/NOT_RUN |
| 12-A11 | S2 | 受信目录分母固定，缺 case 为 NOT_RUN | PLANNED/NOT_RUN |
| 12-A12 | S2/S5 | 同 ID 同字节幂等，不同内容冲突并保留尝试 | PLANNED/NOT_RUN |
| 12-A13 | S2 | SKIPPED/ERROR/CANCELLED/WAIVED/STALE/来源不足不计 PASS | PLANNED/NOT_RUN |
| 12-A14 | S2/S3 | 旧失败需明确处理来源，后续 PASS 不能隐藏 | PLANNED/NOT_RUN |
| 12-A15 | S2 | 原生/WSL/容器/模拟/真实 CLI/加工样本来源不混用 | PLANNED/NOT_RUN |
| 12-A16 | S2 | 矩阵区分架构、shell、build、角色、方向 | PLANNED/NOT_RUN |
| 12-A17 | S1/S3 | Manifest 与受信闭包精确一致，碰撞/篡改拒绝 | PLANNED/NOT_RUN |
| 12-A18 | S2/S3 | 取消、continue-on-error、缺 artifact、摘要不匹配阻塞 | PLANNED/NOT_RUN |
| 12-A19 | S5 | 预检/dry-run 不执行草稿、模型、安装或修改现场 | PLANNED/NOT_RUN |
| 12-A20 | S5 | 逐字段保留已授权模型/thinking/参数，local 不改变信任 | PLANNED/NOT_RUN |
| 12-A21 | S5 | 备份覆盖工作区/索引/历史/账本并有恢复读验 | PLANNED/NOT_RUN |
| 12-A22 | S5 | before/after 与 CAS 阻止现场漂移，重复不重复注册 | PLANNED/NOT_RUN |
| 12-A23 | S5 | 响应丢失可查询原操作，旧操作不复活回退选择 | PLANNED/NOT_RUN |
| 12-A24 | S5 | START_UNKNOWN/残留阻止切换，恢复不盲杀 PID | PLANNED/NOT_RUN |
| 12-A25 | S5 | 回退检测用户修改并保留新证据/余额/撤销 | PLANNED/NOT_RUN |
| 12-A26 | S4/S6 | v2 历史按原协议读取，不支持读取器拒绝而不降格 | PLANNED/NOT_RUN |
| 12-A27 | S0/S6 | 规则/技能/生成器/副本/执行基线可复算对应 | PLANNED/NOT_RUN |
| 12-A28 | S3/S6 | 交付决定与授权分离，不自动提交/发布/付费 | PLANNED/NOT_RUN |
| 12-A29 | S6 | Observer 关闭全流程验证，unknown 费用不重复入账 | PLANNED/NOT_RUN |

## 不变量 I01–I12

| ID | 约束 | 覆盖子任务 | 目标状态 |
|---|---|---|---|
| I01 | 单模块通过不自动合成为集成通过 | 12-s1-1, 12-s6-1 | 必须验证 |
| I02 | 历史 PASS 只证明当时输入 | 12-s1-1, 12-s4-3 | 必须验证 |
| I03 | 未运行/跳过/取消/未知/例外/失败不是 PASS | 12-s2-2, 12-s6-2 | 必须验证 |
| I04 | A04/A05 缺真实证据不能完整 | 12-s2-2, 12-s6-3 | BLOCKED 直到实测 |
| I05 | 部分交付不倒改要求或隐去缺口 | 12-s3-2, 12-s6-3 | 必须验证 |
| I06 | v1 字节、摘要、状态、用量不变 | 12-s4-3, 12-s6-1 | 必须验证 |
| I07 | 迁移预览不执行动作或修改现场 | 12-s5-1, 12-s5-2 | 必须验证 |
| I08 | 新动作重核授权、锁、预算；回退非降级通道 | 12-s5-1, 12-s5-3 | 必须验证 |
| I09 | UNKNOWN/未清理时不解冲突、不重派 | 12-s5-1, 12-s5-3 | 必须验证 |
| I10 | 当前用户内容优先；冲突停止 | 12-s5-1, 12-s5-3 | 必须验证 |
| I11 | 规则/技能同步，验收对实际版本 | 12-s4-1, 12-s6-1 | 必须验证 |
| I12 | Observer 关闭仍可恢复；成本不可见写 unknown | 12-s6-3 | 必须验证 |

## 故障/真实场景 IT01–IT36

| 范围 | 覆盖阶段 | 当前状态 |
|---|---|---|
| IT01–IT10 | S1/S2/S3：候选、目录、摘要、归档安全 | NOT_RUN；离线负例可执行 |
| IT11–IT20 | S2/S6：平台、shell、取消、异构真实链路、插件坏例 | BLOCKED/NOT_RUN；真实平台与 CLI 未授权 |
| IT21–IT32 | S5/S6：CAS、用户改动、WAL、断电、并发、回退 | NOT_RUN；仅计划离线注入 |
| IT33–IT36 | S4/S6：v1 兼容、规则副本、Observer 恢复 | NOT_RUN；需目标现场/当前基线 |

## 责任与证据边界

- `scripts/codekit/**`、`schemas/**`、核心调度器和 03/05/07/09/10 真相源由主模型直接维护；外围合同只修改 fixtures、测试和文档。
- 每个 case 绑定固定 target、输入闭包、实际环境、命令/观察、oracle、结果、未完成原因和审阅来源；参考附录测试不计目标项目 PASS。
- 真实 provider、Pi、原生平台、迁移现场、凭据/预算/外部连接器保持 `NOT_RUN/BLOCKED`；离线证据标 `LOCAL_REFERENCE`。
