# 2026-10-03 Offline Candidate Review v3

## Fixed candidate

- candidate: `296135cb8eef4cbf54585d755f3ca437f7e74a51`
- remote branch: `origin/master`
- review type: planning-side offline review; not a Pi attempt and not a `review-pi` verdict

## Raw evidence

1. `.agent/runs/offline-01-06-08-20261003-builtin-all-06/`
   - command: `python -B -m unittest discover -s tests -p "test_builtin_*.py" -q`
   - `Ran 103 tests`, `OK (skipped=7)`; 96 executed passes and 7 optional Schema dependency skips.
2. `.agent/runs/offline-01-06-08-20261003-expanded-all-06/`
   - 01-06/08 offline expanded combination used by the current contracts.
   - `Ran 544 tests`, `OK (skipped=8)`; 536 executed passes and 8 optional Schema dependency skips.

Both captures have `run.returncode=0`, `execution_status=complete`, `timed_out=false`, `comparison.baseline_consistent=true`, and an empty drift list. The targeted runtime and artifact checks are included in the expanded command. `python -m compileall -q scripts/codekit tests` and `git diff --check` pass for the candidate.

## Changes covered

- `d44a7a9`: `SourceAnchor` can bind a frozen resource byte string, checking the complete resource digest, the half-open range, and the excerpt digest.
- `296135c`: `InvocationSpec` stores argv as an immutable tuple, so a caller cannot mutate the locked command or its digest after construction.

## Contract review

The 18 01-06 contracts and 21 08 contracts have current Markdown/JSON pairs rebound to this candidate. The newest pair for each task passed `python scripts/pi_dispatch.py validate`; the current contract set is 39/39 valid. Older versions remain historical and are not treated as current.

## Conclusion

- `LOCAL_REFERENCE`: the listed offline tests, SourceAnchor byte binding, InvocationSpec argv freezing, and existing schema/fixture boundary checks are reproducible on the fixed worktree.
- `REVISE`: the contract set is structurally current, but no independent Pi attempt has produced attempt-scoped evidence or a `review-pi` verdict.
- `NOT_RUN/BLOCKED`: real Pi/provider, Windows/macOS native process trees, production dispatcher, external 09/10 consumers, billing, and recovery drills were not run.

Final stage conclusion remains `REVISE/BLOCKED`; the production release gate remains closed.
