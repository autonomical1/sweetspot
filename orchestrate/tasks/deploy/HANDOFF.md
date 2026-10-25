# Handoff

## What I did

- Added the two-service Docker Compose deployment with a non-root Python API image, one Uvicorn worker, persistent `/data`, and persistent Caddy certificate/config volumes.
- Added Caddy automatic HTTPS configuration, gzip compression, 25 MB request limit, root redirect, and API reverse proxy.
- Added the Bash smoke test covering health, pairing, demo room, optimize, saved layout, products, photo targets, web HTML, and HTTPS certificate expiry.
- Added fresh-Ubuntu setup, update, rollback, domain switch, operations, persistence, and smoke-test instructions in `DEPLOY.md`.
- Added offline structural tests in `backend/tests/test_deploy_files.py`.
- Retry 1: changed the setup to clone as the deploy user into a user-owned `/srv/sweetspot`, create a user-owned mode-600 `.env`, and use Docker after re-login grants group access. Updates, rollback, and domain edits now use the same user.
- Retry 1: HTTPS smoke tests fail if OpenSSL is missing or no certificate expiry can be read; HTTP tests report a TLS skip. Added Bash syntax, expiry failure-path, and ownership regression tests.

## Unfinished

- The VPS deployment itself was not run because this worker has no network access, as required by the brief.
- `python -m pytest backend -q` still hits a Windows sandbox permission error in the default pytest temp directory. Running with a fresh `--basetemp` under `%TEMP%` passes: 152 passed, 7 skipped, 8 deselected, 1 xfailed. The deploy-specific file passes (7/7).

## Design questions

- none
