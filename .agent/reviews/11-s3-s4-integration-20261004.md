# 11 S3/S4 integration review (2026-10-04)

这是主模型对当前工作树的集成复审记录，不是 Pi 独立复审。

## Scope

- provider-neutral `HeterogeneousAdapterFacade` routes the five adapter operations by registered identity;
- `SecondCliInvocation` freezes ResourceRef allowlists, a no-history session id, and an invocation digest covering runtime, stdin, profile, adapter, and allowlist;
- Claude event collection checks fixed request/run/role context, canonical replay equality, nested tool closure, model identity, terminal completion, usage, and exit status;
- `ProfileHandoff` and `CancellationObservation` provide read-only cross-session handoff and conservative cancellation/recovery states;
- `check_role_gate` consumes the existing `PlanningBudgetLedger`/`BudgetState` and rejects unbound, stopped, or stale generations.

## Evidence

```text
python -B -m unittest tests.test_11_second_cli tests.test_11_runtime_boundaries tests.test_adapter_capability tests.test_adapters tests.test_runtime -q
Ran 50 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

The new handoff and recovery schemas parse as JSON. Windows Python does not
have `jsonschema` installed, so external JSON Schema execution is recorded as
an environment limitation and was not replaced with a mock PASS.

## Findings and gate

- `A01`: PARTIAL — facade registration is provider-neutral; no production dispatcher registration.
- `A02`: PARTIAL — local version/help evidence exists for Claude Code 2.1.288; exact model and native platform capability remain unobserved.
- `A03–A05`: PARTIAL — offline malformed, replay, terminal, model, usage, nested tool, and ResourceRef checks are covered; persistent raw spool and 05 runner are absent.
- `A06–A07`: BLOCKED — no real second CLI model invocation, native process lifecycle, or external chain was run.
- `A08`: PARTIAL — unknown/blocked/recovery states are explicit; authentication and production fallback remain untested.
- `S5–S6`: NOT RUN — Pi historical regression, production routing, real heterogeneous chain, and independent release gate remain outstanding.

No approval, publication, execution, provider, or additional budget authority
was granted by the adapter changes.
