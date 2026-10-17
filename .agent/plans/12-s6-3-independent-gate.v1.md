# TASK: 12-s6-3-independent-gate

## Identity
- plan_version: 1
- repository: Code-Kit
- base_sha: c71014517e3579e5bb465d277a6712c214e565b4
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: offline-reference/dormant · thinking high; no Pi dispatch until environment gate passes
- thinking: high

## Goal
完成独立复审、恢复操作册、范围审计和发布门禁结论。

## Non-goals
- 不调用真实 provider、Pi、第二 CLI、Windows/macOS 原生进程或外部连接器；不读取凭据、不安装依赖、不写外部系统。
- 不修改 AGENTS.md、调度脚本、dispatch 配置或既有历史证据；附件文档只作需求参考。
- 不把离线 fixture、mock、配置值或宣传材料写成生产能力通过。

## Repository facts
- Current base is c71014517e3579e5bb465d277a6712c214e565b4; existing 01–11 interfaces are inputs.
- The attached enhanced document is reference material; AGENTS.md and this contract control scope.
- Real platforms, providers, Pi, processes and external connectors are unavailable and remain NOT_RUN/BLOCKED.

## Steps
1. Freeze the fixed candidate and input references.
2. Implement or verify only the listed offline records, schemas, fixtures and tests.
3. Run T01–T03, schema checks and a scope audit; record failures without masking them.

## Forbidden

## Forbidden
- AGENTS.md
- .agent/runs/**
- .agents/**
- .claude/**
- .codex/**
- .pi/**
- scripts/pi_dispatch.py
- scripts/dispatch-pi.sh
## Scope
- allowed_modified_files:
  -  docs/themis-tally-v2/12-release-runbook.md
- dependency_changes: forbidden

## Behavior contract
- B01：记录采用严格闭合 JSON、确定性字节与 SHA-256；输入缺失、冲突、漂移、截断和未知保持结构化状态。
- B02：所有结论绑定固定候选、来源、范围、环境和可复核证据；未运行不等于通过。
- B03：本任务不拥有批准、执行、预算、提交、发布或迁移权限；DeliveryDecision 不授权这些动作。
- B04：迁移预览只读；真实平台/provider/连接器结论必须是 NOT_RUN 或 BLOCKED。

## Inputs and outputs
- 输入：固定基线、已接受的01–11接口、12增强文档需求矩阵、脱敏离线fixture。

## Validation commands
- T01: `python -B -m unittest tests.test_12_integration_records -q`
- T02: `python -B -m compileall -q scripts/codekit tests`
- T03: `git diff --check`
- WSL Python 3.12: jsonschema.Draft202012Validator.check_schema for changed schemas

## Definition of done
- D01: B01–B04 有定向测试和可复核复审证据；测试覆盖至少一个最小负例。
- D02: Schema/编译/旧入口回归通过；合同 Scope 外无改动。
- D03: 真实平台、provider、Pi、进程、费用和外部连接器逐项标记 NOT_RUN/BLOCKED。

## Failure and rollback
- 保留原始输入和失败诊断；不吞错、不盲目重试、不自动换模型。
- 回滚只删除/恢复本合同新文件；不触碰既有历史证据、用户工作或真相源。

## Stop conditions
- 基线不符、前置接口未接受、需要越界修改、合同冲突、缺少环境或需要真实外部调用。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only

## Report back
- 报告命令和退出码、Scope、证据路径、故障分类、未运行能力及是否需要新合同版本。




