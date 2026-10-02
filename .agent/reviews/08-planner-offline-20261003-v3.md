# 08 offline planner review v3

Verdict: `REVISE` / production gate `BLOCKED`.

This planner-side follow-up covers `ece2203` and the offline commits before
it. It records local evidence only; it is not a Pi attempt and does not replace
an independent `review-pi` verdict.

## Verified local evidence

- 127 focused 01–06/08 tests pass, including strict v2 authorization, currentness generation/hash fencing, one-time consumption, duplicate input rejection and journal recovery,
  projection JSONL recovery/handoff, explicit argv runner identity, timeout and
  flaky classification, plugin lock/resource binding, and permission/platform
  intersection.
- The broader suite excluding long lifecycle dispatcher and legacy end-to-end
  modules passes 870 tests with 34 skips (seven Windows Schema instance checks are skipped because `jsonschema` is unavailable there; WSL runs them).
- `python -m compileall -q scripts/codekit tests` and `git diff --check` pass.
- WSL Python 3.12 Draft 2020-12 meta-validation passes for 14 schemas.
- The earlier WSL local stub run recorded 260 dispatcher self-checks with zero
  failures. A Windows rerun entered the existing long lifecycle fixture and
  was stopped; it is `NOT_RUN`, not a pass.

## Scope of the new offline boundary

- `authorization_store.py` is an append-only JSONL replay store with torn-tail
  recovery, recovery-state write fencing, operation idempotency and persisted
  consumption timestamps for replay across the authorization window; it rejects
  duplicate input bindings but is not the production authorization service.
- `authorization.py` exposes a currentness check bound to the approved
  generation, record hash and decision; stale or revoked heads are rejected.
- `adapters/offline.py` requires one final terminal event, paired tool events
  and a single initial run-start event; malformed streams cannot settle as success.
- Built-in Schema instances, plugin manifests/locks/catalog rows and
  regression/mutation plans are now checked for closed, canonical input and
  recomputed summaries; check evidence stays `REFERENCE_ONLY` without a
  trusted dispatcher receipt and matching candidate/environment bindings.
- `projection_store.py` persists projection events, checkpoints and generation
  handoff, fsyncs each append, with cursor CAS and conservative reconciliation; it is not wired to
  the core dispatcher outbox.
- `offline_runner.py` runs explicit local argv commands without a shell,
  uses a small runtime environment allowlist, rejects credential-like overrides,
  and records candidate/runner/environment hashes,
  and classifies timeout/start, syntax/import and nonzero outcomes. Mutation inputs are caller-supplied
  commands; no isolated candidate mutation dispatcher is connected.
- Catalog loading now verifies manifest-bound locks and repository resource
  bytes. Permission/platform checks return a readiness projection only.

## Remaining blockers

- No Pi attempt, trusted dispatcher receipt, provider call, native Windows/macOS
  process evidence, or 09/10 external connector evidence exists.
- Core authorization/currentness/claims, process ownership, candidate and
  budget ledgers, and production outbox/consumer registration are not closed
  by the new offline stores.
- Catalog signatures/publication CAS, complete permission closure, real test
  collection and mutation isolation, and production reconcile semantics remain
  unverified.

Therefore all 01–06 and 08 stage gates remain `REVISE/BLOCKED`; offline
`PASS`-shaped fixture results remain `LOCAL_REFERENCE` or `REFERENCE_ONLY` and
cannot release production.
