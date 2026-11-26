# Validation evidence — v0.3

## Verified baseline

- [Public release CI run 45760999145](https://github.com/kibnelbachyr/governed-agent-lab-public/actions/runs/45760999145) verified the v0.3.0 release tree, tagged at commit `a71f33a6e9135348c2c34e8f3d2280b4a96402b5`.
- Both matrix jobs (Python 3.11 and 3.13) reported success for unit tests, affirmative demo, rejection demo and the versioned scenario evaluation.
- The evaluation command exits nonzero for any mismatch or unexpected error.

| Check | Python 3.11 | Python 3.13 |
| --- | --- | --- |
| 19 unit tests | Pass | Pass |
| 16 versioned scenarios | Pass | Pass |
| Affirmative demo | Pass | Pass |
| Rejection demo | Pass | Pass |

These counts describe the defined suite on each interpreter, not distinct statistical trials or accuracy of a model. The public CI job/step conclusions and test logs were verified; this is a summary, not a raw log archive. Subsequent maintenance changes require fresh CI. The v0.3.0 tag remains unchanged.

## Current development evidence

The v0.3.0 evidence above is historical. See [hardening acceptance](hardening-acceptance.md) for the later verified implementation commit, matrix results and evidence digests.

## Reproduce

From a clean checkout of the reviewed source:

```sh
python -m unittest discover -s tests -v
python -m evals.run --output evaluation-report.json
printf 'y\n' | python lab.py
printf 'n\n' | python lab.py
```

The runtime and evaluation runner use Python's standard library. No provider credentials or real cloud resources are needed. GitHub Actions uses hosted runner infrastructure, not an offline build environment.

## What this establishes

Defined deterministic controller conformance, authorization-state checks, policy boundaries, replay denial, local persistence and event/denial traces for the versioned synthetic cases.

## What this does not establish

No independently authored or held-out model-quality evaluation, authenticated human identity, adapter sandbox, tamper-resistant logs, comprehensive audit availability, prompt-injection resistance, production security or real cloud execution. No live model was evaluated. No performance or economic claim is made. Publication rights and Apache-2.0 licensing have been confirmed by the owner; v0.3.0 was published as an experimental pre-release.
