# ADR-001 — Explicit simulated principal and adapter boundary

Status: proposed for hardening; not a release decision.

The trusted local harness issues four ephemeral capability strings for fixed simulated principals: requester (submit), controller (propose), reviewer (decide), executor (execute). No default authority. Roles are not caller-supplied labels in decisions. Sessions rotate on reopen; persisted approvals are bound to the simulated reviewer identity and current recommendation, not a session token. The harness can issue every role by design, so this is a simulation of authorization, not authenticated people, RBAC infrastructure or multi-tenant isolation.

Recommendation integrity uses the request ID, version, policy version and serialized payload. Policy version changes invalidate older persisted approvals; migrate by re-proposing nonterminal requests, never silently grandfathering approvals. SQLite and trusted Python code are within the trusted computing base. Digest checking detects inconsistent stored records, not deliberate rewriting of all state by a database writer.

Injected Python adapter code is trusted; its output is not. Running outside the transaction does not isolate arbitrary Python. A subsequent increment will constrain the input/output interface; do not load untrusted Python plugins. No actual provider credentials, network or real infrastructure.

The release tag v0.3.0 remains immutable by process. No v0.4 release, external identity provider, live model or cloud action authorized.
