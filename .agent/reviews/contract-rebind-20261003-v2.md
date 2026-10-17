# 01-06 / 08 Contract Rebind Review v2

## Fixed base

- contract base: `296135cb8eef4cbf54585d755f3ca437f7e74a51`
- review type: planning-side contract structure review; not a Pi attempt and not a production acceptance

## Rebind result

- 18 contracts cover the three subtasks in each of 01-06.
- 21 contracts cover S0-S6 in 08.
- Each current task has a Markdown/JSON pair with an incremented version and the full current base SHA.
- Current V01 checks point to real unittest modules or the checked-in builtin test discovery; V02 is compileall and V03 is git diff check.
- Each contract states `LOCAL_REFERENCE`, `NOT_RUN`, and `BLOCKED` behavior and retains the no-production-gate rule.
- The newest pair for each of the 39 route tasks passed `python scripts/pi_dispatch.py validate` before publication (39 valid, 0 failed). A post-publication validation also reports 39 valid and 0 failed, with one expected base-selection warning per contract because commit `444d15b` publishes the contracts and review documents on top of the code candidate `296135c`.

## Evidence binding

- `.agent/runs/offline-01-06-08-20261003-expanded-all-06/`: 544 collected, 536 passed, 8 skipped; capture is bound to the current candidate and reports no drift.
- `.agent/runs/offline-01-06-08-20261003-builtin-all-06/`: 103 collected, 96 passed, 7 skipped; capture is bound to the current candidate and reports no drift.
- `.agent/reviews/offline-acceptance-20261003-final-v3.md`: current offline review and gate conclusion.

## Unexecuted scope

This rebinding does not dispatch Pi or run real provider calls, Windows/macOS native process trees, external 09/10 consumers, production dispatcher, billing, or recovery drills. Those capabilities remain `NOT_RUN/BLOCKED` and cannot produce a production PASS.
