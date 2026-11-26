# Offline evaluation protocol v2.0

## Question

Does the deterministic governance controller preserve expected state, authorization, evidence references, and event traces under defined synthetic scenarios?

## Method and rubric

Run from the repository root with `python -m evals.run --output evaluation-report.json`. Each scenario begins with a fresh SQLite inventory (30 days, revision 1). The expected fields are separately versioned in cases-v2.json. The 16 original cases retain six assertions (final retention, inventory revision, action count, request status, ordered denial operations, ordered event kinds); the 15 added cases also check per-step outcomes, recommendation version, reviewer and approval presence. Each case runs three times by default on fresh databases. A case passes only if every typed assertion matches and normalized observation hashes are identical across repetitions. The report includes the fixture SHA-256, counts, per-run expected/actual values and digests; any failure exits nonzero. Unexpected exceptions fail the run rather than being counted as successes.

The 31 cases include role/session misuse, provider authority fields, duplicate keys, oversized/nonfinite/wrong-type payloads, corrupted approval or recommendation, competing inventory changes and terminal requests, in addition to nominal changes, policy boundaries, rejected or missing approval, stale approval, replay, invalid evidence and schema, adapter failure and reopening the database. The suite deliberately uses a deterministic fake provider and white-box database assertions and deliberate synthetic record corruption in designated scenarios. Run in CI on Python 3.11 and 3.13 with no provider credentials.

## Interpretation and limits

A passing run establishes conformance for these specified scenarios only. It is not a statistical accuracy measure, independent evaluation, held-out dataset, prompt-injection test, human identity test or production security assurance. Fixtures and implementation share authorship. Evidence ID/revision checks do not establish factual fidelity of generated rationales. The rubric does not measure uncertainty disclosure or semantic quality; those require a separate reviewed dataset and a real provider. Do not equate scenario coverage with exhaustiveness.

Review fixture expectations separately from controller changes. Add cases for new failure modes; never change expected results merely to obtain a pass. Record fixture version, source commit, interpreter and CI run when reporting results.

## Publication gate

The owner has confirmed source and fixture publication rights and Apache-2.0 licensing. Distribution requires verification of the clean release repository and must prominently identify the deterministic simulation and remaining authentication, adapter isolation and audit-integrity limits. No cloud expenditure or live model is needed for this evaluation.
