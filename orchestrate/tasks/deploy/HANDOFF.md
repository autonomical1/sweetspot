# Handoff

## What I did

- Added the two-service Docker Compose deployment with a non-root Python API image, one Uvicorn worker, persistent `/data`, and persistent Caddy certificate/config volumes.
- Added Caddy automatic HTTPS configuration, gzip compression, 25 MB request limit, root redirect, and API reverse proxy.
- Added the Bash smoke test covering health, pairing, demo room, optimize, saved layout, products, photo targets, web HTML, and HTTPS certificate expiry.
- Added fresh-Ubuntu setup, update, rollback, domain switch, operations, persistence, and smoke-test instructions in `DEPLOY.md`.
- Added offline structural tests in `backend/tests/test_deploy_files.py`.

## Unfinished

- The VPS deployment itself was not run because this worker has no network access, as required by the brief.
- Full `python -m pytest backend -q` was attempted: 129 passed, 7 skipped, 8 deselected, 1 xfailed, and 21 existing tests errored because the Windows sandbox denied pytest access to `AppData\Local\Temp\pytest-of-neelm`. The deploy-specific test file passes (5/5), and `bash -n deploy/smoke.sh` passes.

## Design questions

- none
