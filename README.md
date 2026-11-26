# Governed Agent Lab

[![Offline tests](https://github.com/kibnelbachyr/governed-agent-lab-public/actions/workflows/ci.yml/badge.svg)](https://github.com/kibnelbachyr/governed-agent-lab-public/actions/workflows/ci.yml)

**A reproducible reference implementation of the control plane around an AI-assisted workflow.**

[Experimental release v0.3.0](https://github.com/kibnelbachyr/governed-agent-lab-public/releases/tag/v0.3.0) · Apache-2.0. A fictional storage-retention change demonstrates separation between recommendation and execution authority. No external runtime dependencies, credentials, real infrastructure, or live model calls.

## Run

Python 3.11 or 3.13 (both verified in release CI):

```sh
python -m unittest discover -s tests -v
python lab.py
```

The demo asks for explicit approval of a synthetic change, records events and deletes its temporary database when finished. Use the `Lab` interface with a persistent SQLite path to exercise restart recovery.

## Architecture and boundaries

```mermaid
flowchart LR
    R[Change request] --> C[Controller]
    C --> M[Deterministic fake model]
    M --> C
    C --> P[Policy check]
    P --> H[Simulated human decision]
    H -->|Approve| X[Transactional execution]
    H -->|Reject| N[No action]
    X --> D[(Synthetic SQLite inventory)]
    C --> E[(Event log)]
    X --> E
```

A deterministic fake model receives a synthetic inventory snapshot. The controller checks typed recommendations and an illustrative 30–90 day retention rule (not legal or industry guidance). Approval binds the reviewer label to the exact recommendation digest, version and policy version. Execution checks current evidence and authorization again, and transactionally records a unique action, inventory update and event.

## Evidence and continuous integration

See [local test evidence](test-results.txt) for the repeated 14-test run and [demo summary](demo-output.txt) for the scripted affirmative demo. Imported source and tests were verified against the tested Git blob identities.

The [CI workflow](.github/workflows/ci.yml) runs unit tests and affirmative/rejected demo smoke tests on Python 3.11 and 3.13 for pull requests and pushes to main. It uses no secrets or deployment steps; GitHub-hosted runner minutes are subject to account quotas. The [public release CI run](https://github.com/kibnelbachyr/governed-agent-lab-public/actions/runs/45760999145) passed on both interpreters.

## Denial audit

Expected policy or validation denials from submit, propose, decide and execute are recorded separately after the operation rolls back. The record contains only an operation name, timestamp and a verified local request ID (or null). Unknown IDs, raw payloads and exception messages are not retained by this audit path. These records persist across database reopen; the state-transition log remains separate. This does not cover unexpected exceptions or database unavailability, and audit writing is not atomic with the preceding rollback. No security-grade or tamper-resistant logging is claimed.

The original local evidence applies to v0.1. The v0.3.0 public release CI verified 19 tests and both smoke tests per interpreter.

## Offline scenario evaluation

```sh
python -m evals.run --output evaluation-report.json
```

The [versioned fixture set](evals/cases-v1.json) defines 16 synthetic cases with expected inventory, action count, workflow state, denial records and event sequence. The runner uses a fresh SQLite database per case; any mismatch fails CI. See the [evaluation protocol](evals/README.md) for the rubric, scope and interpretation. The public v0.3.0 release CI passed all 19 unit tests, 16 scenarios and both smoke tests on Python 3.11 and 3.13. See [validation evidence](docs/validation.md) for the scope of this result. It is a control-plane regression suite, not a held-out or independently authored LLM benchmark.

## Limitations

The reviewer label is not authenticated identity; the adapter is not sandboxed from arbitrary Python code; the SQLite event log is not tamper-proof; only expected application-level denials are captured by the denial audit. Evidence validation checks synthetic identity and revision, not factual support of free-form claims. The policy is hardcoded and the sample is single-process. No live model or prompt-injection resilience has been evaluated. No cloud integration, deployment, or independently authored evaluation dataset is included. This is an experimental control-plane prototype, not a deployable security boundary.

Next: introduce explicit adapter isolation and authenticated decision boundary appropriate to the target architecture; extend failure handling and audit resilience; review the scenario set independently and expand coverage.

## License and provenance

Licensed under the [Apache License 2.0](LICENSE). This is an independently scoped, AI-assisted engineering experiment using fictional data and no employer or customer assets. The release is intended as an educational reference, not a production security product.
