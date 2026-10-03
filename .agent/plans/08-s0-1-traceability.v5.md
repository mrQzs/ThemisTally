# TASK: 08-s0-1-traceability

## Identity
- plan_version: 5
- repository: Code-Kit
- base_sha: 8348af691d33e08f111b5cebbe852cb66f31a80b
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: step/step-5-preview · thinking high

## Goal
Offline verification of `08-s0-1-traceability` against the fixed candidate. This contract records reproducible evidence and does not claim real Pi, provider, native platform, or external connector completion.

## Non-goals
- Do not dispatch real Pi or access providers, credentials, networks, native platforms, or 09/10 connectors.
- Do not modify core scheduler, schemas, AGENTS.md, contracts, or `.agent/` raw evidence.
- Offline success cannot become a production release PASS.

## Repository facts
- The complete base is `296135cb8eef4cbf54585d755f3ca437f7e74a51` and the worktree must be clean before validation.
- Target tests: `tests.test_builtin_schema_instances, tests.test_builtin_result_boundaries`.
- Current captures: `.agent/runs/offline-01-06-08-20261003-expanded-all-07/` and `.agent/runs/offline-01-06-08-20261003-builtin-all-07/`.

## Scope
- allowed_modified_files:
  - docs/code-kit-v2/contract-evidence/08-s0-1-traceability.md
- allowed_new_files:
  - docs/code-kit-v2/contract-evidence/08-s0-1-traceability.md
- allowed_deleted_files: none
- forbidden_paths: `AGENTS.md`, `.agent/**`, `.agents/**`, `.claude/**`, `.codex/**`, `.pi/**`, `scripts/pi_dispatch.py`, `scripts/dispatch-pi.sh`
- dependency_changes: forbidden
## Inputs and outputs
- Inputs: complete base `296135cb8eef4cbf54585d755f3ca437f7e74a51`, approved requirement matrix, and the listed existing test modules.
- Outputs: V01–V03 command results and explicit `LOCAL_REFERENCE`/`NOT_RUN`/`BLOCKED` records.
- Evidence: raw `.agent/runs/` captures and `.agent/reviews/`; raw evidence is immutable.

## Failure handling
- Classify test failures, optional dependency skips, base drift, scope violations, and unavailable external capability separately.
- Stop on base mismatch or any required out-of-scope edit.
- Never use fixtures or offline results as production evidence.

## Rollback boundary
- Only test changes listed in Scope may be reverted; rules, dispatch scripts, agent directories, credentials, dependencies, and external systems remain untouched.

## Behavior contract
- Run only the listed current tests; classify failures, optional skips, and environment blocks separately.
- `compileall` and `git diff --check` must pass.
- Offline results remain `LOCAL_REFERENCE` and grant no approval, run, billing, or release permission.

## Steps
1. Verify the complete `296135cb8eef4cbf54585d755f3ca437f7e74a51`, Scope, and target modules.
2. Run V01–V03 without rewriting raw captures.
3. Record exact counts, skip reasons, failure fingerprints, and external blocks.
4. Return an execution report; mark unknown behavior `REVISE` or `BLOCKED`.

## Validation commands
- V01 (required): `python -B -m unittest tests.test_builtin_schema_instances tests.test_builtin_result_boundaries -q` · cwd: repository root · timeout: 600s · exit code: 0 · output contains `Ran `
- V02 (required): `python -B -m compileall -q scripts/codekit tests` · exit code: 0
- V03 (required): `git diff --check` · exit code: 0

## Definition of done
- D01: Target tests execute with raw output; evidence V01.
- D02: Structural and whitespace checks pass; evidence V02 and V03.
- D03: External systems remain explicitly `NOT_RUN/BLOCKED`; evidence output and review.
- D04: Candidate SHA is bound and Scope is not expanded; evidence V01 and Scope.

## Stop conditions
- HEAD is not `296135cb8eef4cbf54585d755f3ca437f7e74a51`.
- The task requires source, schema, contract, rule, dependency, or external-system changes.
- An unclassified test failure or contract conflict appears.

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- time allocation: investigation 15%, validation 65%, evidence 15%, report 5%.

## Report back
Return commands, exit codes, test counts, skip reasons, evidence paths, and remaining blocks.

## Forbidden
- Do not modify this contract, agent rules, permission configuration, or dispatch scripts.
- Do not delete, skip, or weaken tests; do not commit, push, merge, or deploy.
