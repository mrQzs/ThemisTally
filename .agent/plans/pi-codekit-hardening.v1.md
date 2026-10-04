# TASK: pi-codekit-hardening

## Identity
- plan_version: 1
- repository: Code-Kit
- base_sha: 1c416de2a3c948ffc7f60baf8b0f52f03161f672
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: local_branch (planner will cherry-pick only after review)
- executor: bb/step-5-preview · thinking high

## Goal
由 Pi `step-5-preview` high 修复 Code-Kit 调度、发布、候选分支绑定和生产发布门禁中的已复现 fail-open/fail-wrong-receipt 缺陷，并补充最小回归测试，使 Code-Kit 能可靠串联规划、派发、审核和集成证据。

## Non-goals
- 不修改合同、`.agent/runs/`、AGENTS.md、适配器技能或 dispatch shell wrapper。
- 不添加第三方依赖，不联网，不读取凭据，不推送/合并/部署。
- 不放宽任何既有门禁；旧兼容行为若与严格证据绑定冲突，保留兼容 API 但新增入口必须 fail closed。

## Scope
- allowed_modified_files: `scripts/pi_dispatch.py`, `scripts/codekit/project_delivery.py`
- allowed_new_files: `tests/test_dispatch_hardening.py`
- forbidden_paths: `AGENTS.md`, `.agent/runs/**`, `.agents/**`, `.claude/**`, `.codex/**`, `.pi/**`, `scripts/dispatch-pi.sh`
- dependency_changes: forbidden

## Repository facts
- 当前 Code-Kit HEAD 为 `1c416de2a3c948ffc7f60baf8b0f52f03161f672`，已有 1393 passed/40 skipped 的全量证据。
- 已复现缺陷：attempt publication lookup 错把 `attempt-001` 当 task id；branch 不绑定 verdict.candidate_tree 与 candidate.json.tree；INTEGRATED 可在 ABANDONED 后用任意 ref 伪造；real_capabilities={} 时 release gate 可能误报 production_release。

## Behavior contract
- publication helper 必须从 attempt 的 `meta.json`/不可变合同元数据读取 task_id/plan_key，任何错误 task 推导都要拒绝；check/evaluate_gates/branch/collect 使用同一来源。
- branch 在通过 verdict 后必须把最新 verdict.candidate_tree 与 candidate.json.tree 精确绑定，并重新验证 candidate.patch 的 hash 和 patch→tree 结果；篡改候选元数据、换树、缺 receipt 都拒绝。
- `mark INTEGRATED` 必须确认当前状态仍为 PASS/AWE、合同明确授权 integration、ref 与已接受候选/本地分支证据可验证；ABANDONED/SUPERSEDED/INTEGRATED 或 made-up ref 一律拒绝。不要改变旧状态文件历史，只增加严格检查。
- `evaluate_release_gate` 对空/缺失 real_capabilities 必须显式 BLOCKED/NOT_RUN；生产发布不能由离线或 synthetic 通过。
- 新测试必须构造最小离线 attempt fixture 覆盖上述负例和正例，不能调用真实 provider、网络、凭据或外部仓库。
- 保留现有测试和 legacy compatibility，必要时新增辅助函数但不要删除旧证据。

## Steps
1. 阅读 AGENTS.md、pi_dispatch.py、planner publication helpers、project_delivery 和现有 dispatch/release tests，确认状态机与证据格式。
2. 在允许范围内实现严格绑定和 fail-closed 检查，保持既有 CLI/API 兼容。
3. 编写确定性的离线回归测试，至少覆盖 publication task identity、candidate tree forgery、ABANDONED/made-up integration、empty capabilities release gate。
4. 运行 V01-V05；全量测试由规划端在集成前另行运行。
5. 最后一条消息逐项报告 D01-D05、命令退出码、范围检查和未运行能力。

## Validation commands
- V01（基线应失败）：`python -c "from pathlib import Path; p=Path(r'tests/test_dispatch_hardening.py'); assert p.exists() and p.stat().st_size>0; print('PI_CODEKIT_HARDENING_ARTIFACT_OK')"`
- V02（必要）：`python -B -m pytest -q tests/test_dispatch_hardening.py`
- V03（必要）：`python -B -m pytest -q tests/test_dispatch.py tests/test_planner_publication.py tests/test_project_delivery.py`
- V04（必要）：`python -B -m compileall -q scripts/codekit scripts/pi_dispatch.py tests`
- V05（必要）：`git diff --check`

## Definition of done
- D01：发布回执按 attempt 元数据正确绑定；证据 V02、V03。
- D02：branch 绑定候选树和 patch 证明；证据 V02、V03。
- D03：INTEGRATED 状态、授权和 ref 证据 fail closed；证据 V02、V03。
- D04：空生产能力保持 BLOCKED/NOT_RUN；证据 V02、V03。
- D05：无依赖/外部副作用，编译和范围通过；证据 V04、V05。

## Stop conditions
- 需要越界修改、安装依赖、访问外部能力或出现合同/基线冲突。
- 只能通过删除/跳过测试让门禁变绿。

## Report back
最后报告 D01-D05、命令退出码、候选 diff 和未运行的生产能力。

## Budget
- max_attempts_total: 1
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 1800
- cost_budget: tracking-only

## Forbidden
- 不修改合同、AGENTS.md、`.agent/`、设计材料、dispatch shell wrapper。
- 不删除、跳过或弱化既有测试；不提交、不推送、不合并、不部署。

