# 08 首批任务插件执行路线图

本路线图以基线 `f52dc20058b0997a2abce80711a372bb463f0558` 为起点。附件《08 首批任务插件（审阅增强版）》只作为需求矩阵和设计参考；执行授权、文件范围和验收结论以 `AGENTS.md`、对应任务合同及独立复审为准。

## 放行策略

执行分为两个门槛：

1. 01–06 的离线实现、Schema、fixture、故障分类和可复核证据完成后，允许 08 离线子任务进入执行。
2. 真实 Pi、provider、Windows/macOS 原生进程以及 09/10 外部连接器缺失时，结果只能为 `BLOCKED`、`NOT_RUN` 或 `LOCAL_REFERENCE`；生产发布门禁保持关闭。

01–06 依次经过离线阶段门：公共协议 → 配置 profiles → 审核锁定 → CLI adapter → 跨平台运行时 → plugin manifest/lock。08 的 S0–S1 串行，S2–S4 在 S1 后可并行，S5 等待相关接线，S6 等待全部前置结果。

## 合同清单

每个条目必须同时存在 `.agent/plans/<task-id>.v1.md` 和 `.json`，并固定完整基线 SHA、Scope、验证命令、DoD、失败处理和回滚边界。

### 前置阶段 01–06

| 阶段 | 子任务合同 | 出口 |
|---|---|---|
| 01 | `01.1` 基准身份与公共协议；`01.2` 输入清单与证据包；`01.3` 兼容、G0–G6 与故障 fixture | ResourceRef、严格 JSON、不可变证据与状态边界 |
| 02 | `02.1` profile/config Schema；`02.2` role/adapter/model 能力解析；`02.3` 迁移、当前性、脱敏与平台故障 | 配置语义、环境计划和启动边界分离 |
| 03 | `03.1` approval/authorization；`03.2` input-lock/CAS/幂等；`03.3` currentness/handoff/reconcile | 审核不扩大权限，未知启动不盲目重放 |
| 04 | `04.1` adapter 协议/注册表；`04.2` 原始事件与 usage；`04.3` 离线 Pi adapter 和异常流 | stub 明确为 synthetic，历史行为保持兼容 |
| 05 | `05.1` Invocation/argv/environment；`05.2` 进程监督与 START_UNKNOWN；`05.3` 平台矩阵和故障注入 | 原生平台缺失显式阻塞 |
| 06 | `06.1` Manifest/Schema/ResourceRef；`06.2` 依赖 DAG 与 lock closure；`06.3` 权限、平台、冲突和 INT 矩阵 | 受信插件目录边界，禁止动态加载与可变别名 |

### 08 阶段

| 阶段 | 子任务合同 | 出口 |
|---|---|---|
| S0 | `08-s0-1-traceability`、`08-s0-2-interface-decisions`、`08-s0-3-fixture-environment` | 39 个合同、D08-01–04、证据和环境基线 |
| S1 | `08-s1-1-artifact-schemas`、`08-s1-2-provenance-binding`、`08-s1-3-artifact-validation` | 八类产物、来源锚点、候选绑定和负例 |
| S2 | `08-s2-1-analysis-report`、`08-s2-2-change-report`、`08-s2-3-checkplan-compiler` | 代码修复配方和 07 四阶段编译结果 |
| S3 | `08-s3-1-docs-change`、`08-s3-2-docs-checks`、`08-s3-3-docs-review-oracle` | AST/链接检查与内容复审分离 |
| S4 | `08-s4-1-regression-artifact`、`08-s4-2-mutation-plan`、`08-s4-3-regression-reduction` | 正确参考、有效变异和环境失败可区分 |
| S5 | `08-s5-1-deterministic-evidence`、`08-s5-2-platform-adapters`、`08-s5-3-failure-reconcile` | deterministic_check 证据与恢复边界 |
| S6 | `08-s6-1-catalog-readiness`、`08-s6-2-state-brief-projection`、`08-s6-3-independent-gate` | 09/10 只读投影和独立发布结论 |

## 所有权与验证

`scripts/codekit/**`、`schemas/**` 由主模型直接维护；Pi 合同只接收测试、fixture、文档和外围适配器。插件不能调用候选记录、预算、授权、验收、verdict 或证据封存入口。

每个阶段至少运行定向测试、`python -m compileall -q scripts/codekit tests`、全量 unittest、`python tests/test_dispatch.py` 和 `git diff --check`。Schema/Markdown AST 检查使用已有 WSL Python 3.12；缺少真实平台或 provider 的条目保留阻塞状态。

阶段通过独立复审后，规划端只暂存 Scope 内文件，创建阶段独立提交并推送；下一阶段以该提交为基线。
