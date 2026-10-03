# 01-06 / 08 Contract Rebind Review v3

## Fixed code base

- contract base: `8348af691d33e08f111b5cebbe852cb66f31a80b`
- review type: planning-side contract structure review; not a Pi attempt and not production acceptance

## Rebind result

- 18 contracts cover the three subtasks in each of 01-06.
- 21 contracts cover S0-S6 in 08.
- Every current task has an incremented Markdown/JSON pair with the full code candidate SHA, actual unittest checks, compileall, diff-check, and explicit offline/external gate boundaries.
- The newest pair for each of the 39 route tasks passed `python scripts/pi_dispatch.py validate` (39 valid, 0 failed before publication).

## Evidence binding

- `.agent/runs/offline-01-06-08-20261003-expanded-all-07/`: 549 collected, 541 passed, 8 skipped; complete and drift-free.
- `.agent/runs/offline-01-06-08-20261003-builtin-all-07/`: 105 collected, 98 passed, 7 skipped; complete and drift-free.
- `.agent/reviews/offline-acceptance-20261003-final-v4.md`: current offline review and gate conclusion.

## Unexecuted scope

This rebinding does not dispatch Pi or run real provider calls, native process trees, external 09/10 consumers, production dispatcher, billing, or recovery drills. These remain `NOT_RUN/BLOCKED` and cannot produce a production PASS.
