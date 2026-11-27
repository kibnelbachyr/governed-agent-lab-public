# Control-plane hardening acceptance — 2026-11-26

Status: engineering acceptance for the synthetic reference scope; proposed v0.4.0 experimental pre-release awaits explicit owner decision and final candidate CI. Existing v0.3.0 remains tagged at a71f33a6e9135348c2c34e8f3d2280b4a96402b5. No new release authorized by this document.

**Subsequent release verification:** [v0.4.0](https://github.com/kibnelbachyr/governed-agent-lab-public/releases/tag/v0.4.0) is published at `b0e8fe0a75fa801f00cab2951ecee16d43d57e8b`; [final CI](https://github.com/kibnelbachyr/governed-agent-lab-public/actions/runs/45909054667) passed. The original checkpoint and limitations below are retained.

## Frozen implementation evidence

Implementation commit: `c236879a225d801a98734bd5db5c3a9a5b72c212`. [Main CI 45908846081](https://github.com/kibnelbachyr/governed-agent-lab-public/actions/runs/45908846081), both jobs and all steps successful. PRs #3–#7 merged. Initial #7 CI failure was a checker false positive on regular-expression compilation; corrected with regression test before merge. Main ruleset 28194835 active: PR required, strict checks for both matrix jobs, no bypass actors; no mandatory independent reviewer.

| Acceptance item | Evidence |
| --- | --- |
| Threat model and explicit identity/adapter ADR | [Threat model](threat-model.md), [ADR-001](adr-001-control-plane.md) |
| Simulated principal binding and negative tests | Four fixed roles; missing, forged, wrong-role and old sessions denied |
| Constrained provider interface | Exact bounded UTF-8 JSON, no injected callback, strict schema and primitive types |
| Replay, stale approval, malformed data and denial tests | Approval context digest, policy invalidation, transactional concurrency and rollback tests |
| Deterministic conformance | Versioned v2 fixture; repeated normalized observations |
| Proportionate static and dependency verification | [Static verification](static-verification.md); standard-library runtime, explicit import allowlist; no third-party runtime packages |

## Verified results

| Measure | Python 3.11.18 | Python 3.13.18 |
| --- | --- | --- |
| Unit tests | 51 passed | 51 passed |
| Scenarios | 31/31 | 31/31 |
| Executions | 93/93 | 93/93 |
| Field assertions | 738/738 | 738/738 |
| Stable scenario observations | 31/31 | 31/31 |
| Tracked files / selected findings | 24 / 0 | 24 / 0 |
| Demo smoke tests | Both passed | Both passed |

Across the matrix: 102 unit test executions, 186 scenario executions and 1,476 field assertions; not distinct independent trials. Live model quality is null (unmeasured).

Fixture SHA-256: `14c64478d6d7decf3343af125d6ee82874b5be4d1ac752c35564b1b54f110b8d`.

Both original ZIPs downloaded, archive digests matched GitHub metadata and report JSON inspected on 2026-11-26. Scheduled expiry 2026-12-10. This tracked aggregate record is not the original report.

| Interpreter | Artifact ID | ZIP SHA-256 | JSON SHA-256 |
| --- | --- | --- | --- |
| 3.11 | 15159710559 | b34c84e2693d939daa9b7f5e3d99d36008b4eef9c0a7a4b266ba6e6b719a917e | 3ee41047a7d76e117548f2c1dad72c66ea55bcee8a4b48411f925c39dee09827 |
| 3.13 | 15159337327 | 574078b3cf24ee7c26bf2bead66b5c61fbd128c2fffd23ed7852be89cfe5134d | 67920cb38661c9602ac426420760c79f87bfe172566cad9f329f448c39827f3b |

## Residual limitations and decision

Simulated roles are not real authentication; trusted local harness and DB writers can bypass controls. No OS sandbox, external provider transport, signed approvals, approval expiry, tamper-resistant logs, distributed guarantees or audit availability assurance. No independently authored benchmark, live model quality, real infrastructure or production security validated. Static checks are narrow; no exhaustive secret/history/supply-chain clearance. The broader portfolio containment and rights verification remains separate; no further promotion until cleared.

Recommend v0.4.0 as an experimental pre-release only after documentation closeout merges, exact final candidate CI is green, owner accepts these limitations and explicitly authorizes publication, and outstanding portfolio promotion gate is verified. Preserve v0.3.0. No cloud expenditure or live operations.
