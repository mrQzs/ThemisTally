# 08 offline planner review follow-up

Verdict: REVISE

Follow-up against `4b98152` records the fixes since the first review: offline PASS now requires a dispatcher receipt (or is mapped to `REFERENCE_ONLY`), added/deleted change rows require the corresponding content hash, seven plugin fixtures and three recipe fixtures are checked in, config policy and authorization boundary tests pass, uncertain runtime transitions require a generation fence, and unknown adapter events are retained as unsettled evidence.

Remaining blocking findings:

- The plugin fixtures are local reference data. There is no trusted catalog signature, core dispatcher registration, permission intersection, or production lock publication CAS.
- Regression and mutation modules still reduce caller-supplied statuses. They do not collect or execute tests, bind test bytes and runner identity, isolate mutation copies, classify syntax/import/environment failures, or preserve repeated/flaky outcomes.
- The projection helper remains in-memory. It is not connected to a durable outbox, consumer cursor, high-water recovery, or handoff/response-loss reconciliation.
- 01–06 still lack production persistence and full currentness/authorization, native process-tree and OS-lock evidence, provider/Pi evidence, and complete resource closure. Their stage gate remains `REVISE/BLOCKED`.
- No Pi attempt exists and the independent Codex review rollout was unavailable. The 260-check local stub dispatcher self-test is useful regression evidence but cannot release a production gate.

Therefore A01–A28 and T01–T30 remain split between `LOCAL_REFERENCE`, `REVISE/BLOCKED`, and `NOT_RUN`; no production PASS is issued.
