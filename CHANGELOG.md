# Changelog

## v0.4.0 — published experimental pre-release

- Explicit simulated principal sessions and role validation; bounded JSON provider data interface.
- Approval-context integrity, policy-version invalidation and transactional adverse-state regressions.
- 31 scenarios, repeated three times, with typed assertions and observation digests.
- Narrow static source checks and matrix evidence uploads; see [hardening acceptance](docs/hardening-acceptance.md).
- Breaking development API changes: operation sessions required; injected model callbacks removed; prior policy approvals require fresh proposal and decision.

## v0.3.0 — published experimental pre-release

- Added 16 separately versioned synthetic controller scenarios and machine-readable evaluation output.
- Added scenario evaluation to the existing CI matrix.
- Verified 19 unit tests, 16 scenarios and both smoke tests on Python 3.11 and 3.13.

## v0.2 — development milestone

- Added persistent application-level denial audit with minimized records.
- Added five negative-path tests; verified 19 tests and both smoke tests in CI.

## v0.1 — development milestone

- Implemented typed recommendations, explicit approval, deterministic policy, simulated retention changes and transactional SQLite evidence.
- Verified 14 unit tests and both smoke tests in CI.

v0.4.0 and v0.3.0 are published experimental pre-releases. [Current release](https://github.com/kibnelbachyr/governed-agent-lab-public/releases/tag/v0.4.0). Development milestones are not production readiness.
