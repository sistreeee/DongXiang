# Repository guidance

## Purpose

This repository is a read-only Codex Cloud service diagnostic. Its current scope is connectivity, public venue configuration, and an explicitly requested check of the user's own session.

## Runtime and validation

- Use Python 3.9+ and the standard library. No third-party dependencies are required.
- Setup: `sh scripts/setup.sh`.
- Offline tests: `python3 -m unittest discover -s tests -v`.
- Public live check: `python3 cloud-location-check.py`.
- The live service host is `www.dongxiangsz.cn`; respect the environment's network policy and proxy.
- If a managed Cloud runtime skill is available, read its runtime instructions before diagnosing network access.

## Scope and credentials

- Runtime network requests in this tool are GET-only: `/api/fitness/venues` and, with `--check-session`, `/api/user`.
- Keep user data, live credentials, login responses, local app caches, and decoded third-party client packages out of this repository and logs.
- `DONGXIANG_TOKEN` belongs in the user's environment or service-scoped HTTP secret, never in source, command arguments, fixtures, or commits.
- Do not follow HTTP redirects with credentials. Do not print raw account responses or service messages.
- A reference coordinate or a successful GET does not establish that device location changed or attendance was accepted.
- Changes adding login, uploads, attendance submission, or scheduling require a new explicit user request beyond the present read-only workflow.

## Reporting

Distinguish offline tests, local live checks, and actual Codex Cloud execution. Report unperformed authentication and business-flow checks as unverified.
