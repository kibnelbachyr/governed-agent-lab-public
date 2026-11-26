# Security policy

This project is an experimental control-plane prototype. It is not a production security boundary. The v0.3.0 reviewer labels are not authenticated; current development uses simulated role sessions and bounded provider JSON, not real authentication or an OS sandbox; the SQLite event log is not tamper-proof. Use fictional data only.

For a suspected vulnerability, do not post exploit details, credentials or sensitive information in a public issue. If private vulnerability reporting is enabled, use the repository Security tab; otherwise ask the maintainer for a private reporting channel in a minimal issue. Include the affected commit, expected and actual behavior, impact and a safe synthetic reproduction in the private report.

No guaranteed response time or production support is offered. See [README](README.md) and [validation evidence](docs/validation.md) for known limitations.
