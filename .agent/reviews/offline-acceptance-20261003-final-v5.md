# 2026-10-03 Offline Candidate Review v5

## Fixed candidate

- candidate: `5d141298d052b291c1dba3fe35075d6303f0bbc8`
- review type: planning-side offline review; not a Pi attempt and not a `review-pi` verdict

## Raw evidence

1. `.agent/runs/offline-01-06-08-20261003-builtin-all-08/`
   - `Ran 107 tests`, `OK (skipped=7)`; 100 executed passes and 7 optional Schema dependency skips.
2. `.agent/runs/offline-01-06-08-20261003-expanded-all-08/`
   - `Ran 552 tests`, `OK (skipped=8)`; 544 executed passes and 8 optional Schema dependency skips.

Both captures returned 0, completed fully, have `baseline_consistent=true`, and have an empty drift list. `python -m compileall -q scripts/codekit tests` and `git diff --check` pass.

## Changes covered

- Built-in analysis and docs-change builders now require frozen source bytes whenever they emit SourceAnchor records, and verify the ResourceRef digest, half-open byte range, and excerpt digest. Deserializers retain envelope-only validation when no snapshot is available.
- The artifact source-byte map uses the full canonical ResourceRef tuple, rejects undeclared resources, oversized snapshots, and digest drift.
- The authorization lock-receipt probe now uses the bounded strict JSON parser; duplicate-key and malformed records cannot be treated as a valid receipt.
- Added builder-level SourceAnchor drift/missing-snapshot tests and a strict journal probe regression test.

## Contract review

The latest 39 Markdown/JSON contract pairs are rebound to the fixed candidate SHA. `python scripts/pi_dispatch.py validate` reports 39 valid, 0 failed, 0 warnings. The `08-s6-3` V01 command now names the real module `tests.test_builtin_schema_instances`.

## Conclusion

- `LOCAL_REFERENCE`: fixed offline test behavior is reproducible on the captured worktree.
- `REVISE`: no Pi attempt has produced attempt-scoped evidence or a `review-pi` verdict.
- `NOT_RUN/BLOCKED`: real Pi/provider, native process trees, production dispatcher, external 09/10 consumers, billing, and recovery drills were not run.

Final stage conclusion remains `REVISE/BLOCKED`; the production release gate remains closed.
