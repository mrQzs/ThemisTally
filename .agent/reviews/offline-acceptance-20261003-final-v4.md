# 2026-10-03 Offline Candidate Review v4

## Fixed candidate

- candidate: `8348af691d33e08f111b5cebbe852cb66f31a80b`
- review type: planning-side offline review; not a Pi attempt and not a `review-pi` verdict

## Raw evidence

1. `.agent/runs/offline-01-06-08-20261003-builtin-all-07/`
   - `Ran 105 tests`, `OK (skipped=7)`; 98 executed passes and 7 optional Schema dependency skips.
2. `.agent/runs/offline-01-06-08-20261003-expanded-all-07/`
   - `Ran 549 tests`, `OK (skipped=8)`; 541 executed passes and 8 optional Schema dependency skips.

Both captures returned 0, completed fully, have `baseline_consistent=true`, and have an empty drift list. Compileall and diff-check pass for the candidate.

## Changes covered

- `8348af6`: platform reconciliation now validates a closed persisted observation, connection/execution-mode consistency, safe command text, environment digest, and canonical failure fields.
- `8348af6`: authorization journal replay uses strict JSON and rejects duplicate keys, oversized/deep/non-finite complete records while retaining durable-prefix handling for an uncommitted tail.

## Contract review

The 18 01-06 contracts and 21 08 contracts have current Markdown/JSON pairs rebound to this candidate. The newest pair for each task passed `python scripts/pi_dispatch.py validate` (39 valid, 0 failed before publication).

## Conclusion

- `LOCAL_REFERENCE`: the offline test suites and the new runtime/journal boundary checks are reproducible on the fixed worktree.
- `REVISE`: no independent Pi attempt has produced attempt-scoped evidence or a `review-pi` verdict.
- `NOT_RUN/BLOCKED`: real Pi/provider, native process trees, production dispatcher, external 09/10 consumers, billing, and recovery drills were not run.

Final stage conclusion remains `REVISE/BLOCKED`; the production release gate remains closed.
