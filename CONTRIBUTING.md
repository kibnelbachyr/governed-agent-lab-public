# Contributing

This experimental reference explores deterministic control-plane behavior, not live model quality or a production security boundary. Keep examples fictional and reproducible.

- Discuss substantial changes before opening a PR; describe the affected policy, state transition or trust boundary.
- Run `python -m unittest discover -s tests -v` and `python -m evals.run --output evaluation-report.json`.
- Check affirmative and rejection paths using `python lab.py`. Both matrix jobs on Python 3.11 and 3.13 should pass.
- Do not commit credentials, private data, customer material or generated reports containing sensitive content.
- Contributions must be independently authorized for distribution under Apache-2.0. Preserve third-party attribution and licensing.
- Clearly separate measured evidence from proposed features and limitations.

See [validation evidence](docs/validation.md) and [evaluation protocol](evals/README.md).
