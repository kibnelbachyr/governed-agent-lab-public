# ADR-001 — Explicit simulated principal and adapter boundary

Status: proposed for hardening; not a release decision.

The trusted local harness issues four ephemeral capability strings for fixed simulated principals: requester (submit), controller (propose), reviewer (decide), executor (execute). No default authority. Roles are not caller-supplied labels in decisions. Sessions rotate on reopen; persisted approvals are bound to the simulated reviewer identity and current recommendation, not a session token. The harness can issue every role by design, so this is a simulation of authorization, not authenticated people, RBAC infrastructure or multi-tenant isolation.

Recommendation integrity uses the request ID, version, policy version and serialized payload. Policy version changes invalidate older persisted approvals; migrate by re-proposing nonterminal requests, never silently grandfathering approvals. SQLite and trusted Python code are within the trusted computing base. Digest checking detects inconsistent stored records, not deliberate rewriting of all state by a database writer.

The controller accepts only exact bytes, at most 4096 bytes, of UTF-8 JSON with four exact primitive fields; duplicate keys, nonfinite numbers, control characters and unknown fields are rejected. No arbitrary provider callback executes in the controller. The default fake is fixed trusted code; explicit None represents upstream failure. The trusted harness acquires any external response outside the controller; no live provider connector is implemented. This is a data-only boundary, not OS/process isolation. Do not load untrusted Python plugins. See [threat model](threat-model.md). No actual provider credentials, network or real infrastructure.

The release tag v0.3.0 remains immutable by process. No v0.4 release, external identity provider, live model or cloud action authorized.
