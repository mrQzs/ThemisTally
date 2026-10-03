# 01-06 / 08 Contract Rebind Review v4

## Fixed code base

- contract base: `5d141298d052b291c1dba3fe35075d6303f0bbc8`
- review type: planning-side contract structure review; not a Pi attempt and not production acceptance

## Rebind result

- 18 contracts cover the three subtasks in each of 01-06.
- 21 contracts cover S0-S6 in 08.
- Every current task has an incremented Markdown/JSON pair with the full candidate SHA repeated consistently in identity, repository facts, inputs, steps, stop conditions, and machine fields.
- The newest pair for each of the 39 route tasks passed `python scripts/pi_dispatch.py validate`: 39 valid, 0 failed, 0 warnings.
- `08-s6-3` V01 is bound to `python -B -m unittest tests.test_builtin_schema_instances -q`; the obsolete `discover_builtin` token is absent.

## Evidence binding

- `.agent/runs/offline-01-06-08-20261003-expanded-all-08/`: 552 collected, 544 passed, 8 skipped; complete and drift-free.
- `.agent/runs/offline-01-06-08-20261003-builtin-all-08/`: 107 collected, 100 passed, 7 skipped; complete and drift-free.
- `.agent/reviews/offline-acceptance-20261003-final-v5.md`: current offline review and gate conclusion.

## Unexecuted scope

This rebinding does not dispatch Pi or run real provider calls, native process trees, external 09/10 consumers, production dispatcher, billing, or recovery drills. These remain `NOT_RUN/BLOCKED` and cannot produce a production PASS.
