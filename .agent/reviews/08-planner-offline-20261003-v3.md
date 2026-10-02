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
- `a414b04` adds a runtime `authorization.integration.local_branch` gate and
  verifies the prepared contract hash before branch-side Git writes. The
  dispatcher stub suite passes 258 checks on Windows and 263 checks under WSL.
- The broader suite excluding long lifecycle dispatcher and legacy end-to-end
  modules passes 870 tests with 34 skips (seven Windows Schema instance checks are skipped because `jsonschema` is unavailable there; WSL runs them).
- The required Windows `python -m unittest discover -s tests -q` run completed
  1029 tests with 38 skips and three expected legacy source-lock failures: the
  locked `a4fa199` digest cannot match after the authorized `pi_dispatch.py`
  change. This is recorded as not-all-green rather than a production pass.
- `python -m compileall -q scripts/codekit tests` and `git diff --check` pass.
- WSL Python 3.12 Draft 2020-12 meta-validation passes for 14 schemas.
- The latest dispatcher self-check evidence is the 263-check WSL run and the
  258-check Windows run above; both completed with zero failures. These are
  local stub runs, not Pi production evidence.

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
- `3347906` closes the documentation artifact boundary: docs-check source paths
  must have exact ResourceRef coverage, finding payloads are closed and
  recomputed, canonical ResourceRef collisions are rejected, and the offline
  docs-change/review-bundle builders refuse an explicit production `PASS`.
  The resulting 93-test focused suite passes on Windows; this is local fixture
  evidence only.
- `1fb8c6e` closes SourceAnchor provenance for AnalysisReport and docs-change:
  anchors must point to an exactly declared `source_refs` entry. The expanded
  focused suite passes 100 tests on Windows; no file-byte or production review
  claim is made by this check.
- `1371ce6` closes the review-oracle observation envelope and bounds check IDs,
  test maps, bindings, and statuses. Malformed or unhashable inputs now produce
  explicit `E_CHECK_*` errors instead of leaking type errors or readiness.
- `739cc91` adds list-versus-set collection regressions so callers cannot widen
  those closed ID-set inputs without a failing test.
- `242a2f4` rejects duplicate, unsorted, or non-text derived arrays in
  regression plans before result reduction; the regression/mutation boundary
  suite passes 30 tests.
- `2bdee7d` hardens platform observations, failure classifications, and
  deterministic-check evidence against loose booleans, unbounded text, malformed
  receipts, and non-mapping evidence. The S4/S5 focused checks pass 31 tests;
  no dispatcher receipt is inferred.
- `e5f89ef` hardens the in-memory projection path against non-mapping or
  non-canonical event payloads and loose state/brief fields. The S6 projection
  checks pass 17 tests; this remains a read-only offline projection.
- `f060b94` requires canonical plugin-lock ordering and rejects duplicate
  permission or non-text platform policy inputs. Plugin boundary checks pass 23
  tests; Windows Schema instance checks remain environment-skipped.
- `29ade8d` closes deterministic-check evidence fields and bounds identity,
  output, and reason values. The S5 focused checks pass 17 tests; no trusted
  dispatcher receipt is inferred.
- `811ab7a` closes the durable projection state boundary for cursors, source
  vectors, verification/as-of values, issue lists, and boolean flags. This is
  still a read-only offline projection.
- `b2b9dff` closes catalog input types, recipe compile-receipt identity/version
  fields, and projection event sequence boundaries. The related S4/S5/S6
  regression set passes 37 tests; these are main-model offline checks, not Pi
  attempt evidence.
- `b396873` rejects malformed inventory, plan, summary, and result sequence
  inputs before regression reduction; this extends the offline S4 boundary.
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
- A docs-check record is still a local reference until a trusted dispatcher
  receipt is supplied; the new builder checks prevent a plugin caller from
  manufacturing that receipt or status.

The 39 v1 contracts are historical planning drafts from an older base and have
no attempt evidence; they must be superseded by current-base v2 contracts before
any dispatch. Therefore all 01–06 and 08 stage gates remain `REVISE/BLOCKED`; offline
`PASS`-shaped fixture results remain `LOCAL_REFERENCE` or `REFERENCE_ONLY` and
cannot release production.
