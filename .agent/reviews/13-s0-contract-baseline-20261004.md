# 13 S0 合同与证据基线复审

日期：2026-10-04
基线：`cf44ae17fa2722cd998c5991722a0db7e373d7a8`
范围：13 可选摘要 Observer 的 S0 路线图、追踪矩阵、21 份 v1 合同。

## 复核结论

S0 规划产物 **PASS（规划层）**。本结论只确认合同结构、范围和追踪设计可复核，不代表 Observer 实现、真实 provider、host push、Pi 或生产发布通过。

## 证据

- 路线图：[docs/code-kit-v2/13-execution-roadmap.md](../../docs/code-kit-v2/13-execution-roadmap.md)，七阶段、21 个子任务、依赖和真实能力门禁。
- 追踪矩阵：[docs/code-kit-v2/13-traceability-matrix.md](../../docs/code-kit-v2/13-traceability-matrix.md)，A01–A09 与 I01–I18 映射到合同和证据。
- 合同目录：`.agent/plans/13-*.v1.md` 与同名 `.json`，数量 21 对；短名重复合同已清理。
- 基线：`git rev-parse HEAD` 为 `cf44ae17fa2722cd998c5991722a0db7e373d7a8`；合同 base_sha 均与该基线一致。
- 结构验证：对 21 个 `13-*.v1` 逐一运行 `python scripts/pi_dispatch.py validate <task-id>.v1`，21/21 退出码 0。
- Scope 复核：核心 `scripts/codekit/**` 和 `schemas/**` 未列入 Pi 合同允许修改集合，按 AGENTS.md 由主模型维护；合同均明确禁止调度脚本、代理规则、原始证据和依赖变更。

## 采用边界

- Observer 默认关闭；确定性 project brief、状态、授权、预算、合同和证据仍是核心真相源。
- 离线 fixture/adapter 只能证明协议、来源、隔离、预算、去重和降级语义；不能宣称摘要模型、真实 CLI、Pi、原生 OS、host notification 或外部连接器已接入。
- `NOT_RUN/BLOCKED/STALE/INVALID` 不归约为 PASS；未运行的真实能力不放行生产 gate。
- 任何需要新增核心实现、Schema 或现有账本修改的执行合同，必须由主模型在依赖阶段通过后创建新版本并重新固定 base_sha；当前合同不扩大该所有权。

## 未运行与阻塞

- 未调用真实 observer model/provider、未读取凭据、未启用定期联网任务。
- 未验证 Windows/macOS/Linux 原生进程隔离、真实 host push、Pi 交接或外部 09/10 连接器。
- 未执行任何 Pi attempt；当前环境和用户授权只支持规划与离线实现。

## 后续门槛

S1 只能在 S0 合同被接受后实现严格协议和来源闭包；S2/S3 的并行实现必须保持核心代码由主模型维护；S6 发布 gate 必须看到真实能力的独立证据，否则结论保持 BLOCKED。
