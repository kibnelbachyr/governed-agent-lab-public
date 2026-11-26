# Offline evaluation protocol v1.0

## Question

Does the deterministic governance controller preserve expected state, authorization, evidence references, and event traces under defined synthetic scenarios?

## Method and rubric

Run from the repository root with `python -m evals.run --output evaluation-report.json`. Each scenario begins with a fresh SQLite inventory (30 days, revision 1). The expected fields are separately versioned in cases-v1.json. A scenario passes only when all six fields match: final retention, inventory revision, action count, request status, ordered denial operations, ordered event kinds. The runner reports every expected/actual value and exits nonzero on any failure. Unexpected exceptions fail the run rather than being counted as successes.

The 16 cases include nominal changes, policy boundaries, rejected or missing approval, stale approval, replay, invalid evidence and schema, adapter failure and reopening the database. The suite deliberately uses a deterministic fake provider and white-box read-only database assertions. Run in CI on Python 3.11 and 3.13 with no provider credentials.

## Interpretation and limits

A passing run establishes conformance for these specified scenarios only. It is not a statistical accuracy measure, independent evaluation, held-out dataset, prompt-injection test, human identity test or production security assurance. Fixtures and implementation share authorship. Evidence ID/revision checks do not establish factual fidelity of generated rationales. The rubric does not measure uncertainty disclosure or semantic quality; those require a separate reviewed dataset and a real provider. Do not equate scenario coverage with exhaustiveness.

Review fixture expectations separately from controller changes. Add cases for new failure modes; never change expected results merely to obtain a pass. Record fixture version, source commit, interpreter and CI run when reporting results.

## Publication gate

The owner has confirmed source and fixture publication rights and Apache-2.0 licensing. Distribution requires verification of the clean release repository and must prominently identify the deterministic simulation and remaining authentication, adapter isolation and audit-integrity limits. No cloud expenditure or live model is needed for this evaluation.
