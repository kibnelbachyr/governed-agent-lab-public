# Threat model — synthetic control plane

Scope: local single-store retention workflow on the development branch; the v0.3.0 release predates this design. Assets: inventory state, recommendation digest, approval decision, role sessions, action uniqueness and event records. Only a synthetic SQLite update can execute. No provider network, credentials or cloud integration.

| Boundary / threat | Control | Residual risk |
| --- | --- | --- |
| Caller attempts unauthorized operation | Explicit simulated per-instance sessions; fixed role matrix; deny by default | Harness issues all sessions; no external authentication or process isolation |
| Provider response tries to confer authority | Exact bounded UTF-8 JSON bytes; four fields; no callable or dynamic tool dispatch; unknown fields rejected | Trusted application code and harness can bypass interfaces; rationale may mislead reviewer |
| Ambiguous or malformed provider output | Duplicate keys, nonfinite numbers, wrong primitive types, malformed UTF-8, control characters and oversized payload denied | Bound applies after bytes acquired; no external transport or upstream timeout |
| Stale or replayed approval | Request/version/policy/payload digest recomputed, separate approval-context digest binds request, version, policy, recommendation and reviewer; current inventory policy, transaction and unique action | Trusted DB writer can forge complete state; no cryptographic approval signature or expiry |
| Concurrent changes | SQLite immediate transaction, proposal version and state recheck, current inventory revision check | Local single-store only; two-connection race and injected event-write failure regressions; no distributed guarantees |
| Audit leakage or failure | Expected denials record sanitized operation and known request ID; raw invalid output not stored | Accepted rationale is persisted; use fictional data only; not tamper-proof, rollback and denial log not atomic |
| Supply-chain or arbitrary Python | Standard library runtime, fixed fake model, no injected provider callbacks | Python runtime, imports, CI and trusted harness remain TCB; no sandbox |
| Denial of service | Provider payload length and primitive checks | No overall resource limits, rate limiting, process supervision or production availability guarantee |

No live-model factuality, prompt-injection resilience, authenticated human identity, external service isolation, production security or cloud execution is claimed. Expected database write failures propagate; transaction rollback is tested, but operational recovery and denial-log availability are not guaranteed. Expanded conformance and static verification are planned. See [ADR-001](adr-001-control-plane.md).
