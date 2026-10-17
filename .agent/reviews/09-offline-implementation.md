# 09 离线实现复审记录

## 范围

- 基线：`330d3716d65e068c38a5861e2a1a4bf4c84cf043`（合同基线仍固定该 SHA；当前工作分支已有 S0 合同提交）。
- 覆盖：PlannerRequest/ContextManifest/PlanningBundle 严格协议、ResourceRef/SourceAnchor、DAG 与 ContractIR、不可变 draft/CAS、双成员 ContractCandidate、PublicationReceipt、固定字节消费门禁、readiness/repair/budget、离线 adapter、09/10 状态投影。
- 额外门禁：版本槽不复用、成员顺序与 digest/ref/bytes 闭合、严格 JSON 解码器不可降级、Schema `uniqueItems`、终止观察、`derive-json` v2 降级拒绝、request/context/bundle 跨记录绑定、可选 03 ApprovalLedger currentness/input-lock/revocation，以及公共发布到 `.agent/plans/`/`.agent/publications/` 的原子投影。
- 真实 planner/provider、Pi、原生平台、外部 09/10 连接器：`NOT_RUN/BLOCKED`，没有将离线 fixture 作为生产证据。
- `target_ref` 在离线投影中作为候选的逻辑目标绑定保存；核心发布器仍把正式文件投影到固定的 `.agent/plans/<task>.vN.*` 路径，待真实目录连接器接线时再复审物理路径映射。

## 复核命令

```text
python -m unittest tests.test_planner_protocol tests.test_planner_publication tests.test_planner_runtime tests.test_planner_adapter tests.test_planner_projection tests.test_dispatch_planner -q
python -m unittest tests.test_legacy_cli.LegacyMainEntryTest.test_LB_EXIT_002_no_subcommand_prints_help_to_stdout_exit_2 tests.test_legacy_cli.LegacyMainEntryTest.test_LB_EXIT_002_uncaught_exception_traceback_exit_1 tests.test_codekit01_fixtures.DifferentialTests.test_legacy_contract_projection_unchanged -q
python -m compileall -q scripts/codekit tests
python scripts/pi_dispatch.py validate 09-s0-1.v1
git diff --check
```

## 结果

- 新增定向测试：当前 23 项通过；其中 03 currentness/input-lock/revocation 和跨记录绑定均有回归覆盖。
- 旧 CLI/fixture 兼容回归：3 项通过。
- 21 份 `09-*.v1.md/.json` 合同：均通过 `validate`；因合同明确固定旧基线，当前 HEAD 仅产生预期 `base_sha` 警告。
- 最近一次完整回归运行 1240 项，39 项环境 skip，3 项已知 `a4fa199` 源码锁定差异；随后新增的 currentness/binding 变更由当前 23 项定向测试覆盖。
- `schemas/*planner*schema.json`、`schemas/planner-request-v1.schema.json`、`schemas/context-manifest-v1.schema.json`、`schemas/bundle-validation-report-v1.schema.json`、`schemas/contract-candidate-v1.schema.json`、`schemas/publication-receipt-v1.schema.json` 均可解析。
- Windows Python 环境没有 `jsonschema` 包，因此这里只记录 JSON 解析和协议函数验证；Draft 2020-12 的语义校验需在既有 WSL Python 3.12 环境复核。

## 门禁结论

离线实现可进入当前提交；生产发布门禁不放行。所有 planner-v2 合同必须同时存在固定 MD/JSON 字节和当前 `PublicationReceipt`，`validate`、`prepare`、`baseline`、`run` 通过同一登记校验，`derive-json` 拒绝覆盖 planner-v2；人工 v1 合同继续沿历史兼容路径。03 ApprovalLedger currentness/revocation 的真实接线、模型/provider、进程和外部连接器仍需后续具备环境后重新复审。
