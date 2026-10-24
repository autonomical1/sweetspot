# deploy: Docker Compose + Caddy (auto-HTTPS) for the Vultr VPS

## Goal
Files and instructions that let anyone run the backend on the Vultr VPS (Ubuntu 24.04, IP 144.202.27.51) behind Caddy with automatic HTTPS, today on the free hostname `144-202-27-51.sslip.io` and later on a .tech domain by changing one env var. Plus a smoke test script. You cannot reach the server (no network): write files, docs and tests only; the orchestrator runs the deploy.

## Read first
docs/API.md sections 6-8, docs/TESTING.md section 3.9, .env.example (shared; do not edit), backend/requirements.txt, backend/app/main.py (serves `web/` at `/app`), backend/app/rooms.py (`/rooms/demo` reads `fixtures/`), backend/app/roomplan.py may appear later and loads `tools/validate_dto.py` from the repo root.

## Design decisions this brief encodes (do not change)
- Two services in `deploy/docker-compose.yml`: `api` (built from the repo root with `deploy/Dockerfile`) and `caddy` (official `caddy:2` image). Only Caddy publishes ports 80 and 443; `api` is internal on 8000.
- **Exactly one uvicorn worker** (`--workers 1`): pairing sessions live in process memory. Add `--proxy-headers --forwarded-allow-ips="*"`.
- Image copies the whole repo minus a `.dockerignore` list, so `backend/`, `fixtures/`, `web/`, `tools/` and the future teammate packages `speakerplacer/` and `products/` are included automatically when they exist. Excluded: `.git`, `.env`, `data/`, `.localdata/`, `memory/`, `orchestrate/`, `__pycache__`, `.pytest_cache`, `*.pyc`, `phoneapp_context/`, `docs/`.
- Persistent data in a named volume mounted at `/data` with `DATA_DIR=/data`. Caddy certificates in named volumes (`caddy_data`, `caddy_config`) so restarts do not re-issue certificates.
- Secrets only from `/srv/sweetspot/.env` on the server (`env_file: ../.env` relative to `deploy/`); nothing secret in the repo or the image.
- Caddyfile site address comes from env `SITE_ADDRESS` (comma-separated list allowed). Behaviour: `encode gzip`, `reverse_proxy api:8000`, `GET /` redirects (302) to `/app/plot2d/` for now, request body limit 25 MB (photos).
- Python base image `python:3.12-slim`; non-root user; `HEALTHCHECK` hitting `/health` with Python's urllib (no curl in slim).

## Deliverables
1. `deploy/Dockerfile`, `.dockerignore` (repo root), `deploy/docker-compose.yml`, `deploy/Caddyfile` as above. `restart: unless-stopped` on both services; api depends on nothing external.
2. `deploy/smoke.sh BASE_URL`: bash, `set -euo pipefail`, uses curl and python3 for JSON. Steps, each printing PASS/FAIL with timing: `GET /health`; `POST /sessions` (has code and pair_url); `POST /rooms/demo`; `POST /rooms/{id}/optimize` (six speakers); `GET /rooms/{id}/layout`; `GET /rooms/{id}/products?budget=1500` (total <= budget); `GET /rooms/{id}/photo-targets`; `GET /app/plot2d/` returns HTML; for https URLs, the certificate expiry date (via `curl -vI` or openssl if present). Exit non-zero on any failure.
3. `DEPLOY.md` (repo root): (a) one-time server setup on Ubuntu 24.04 (apt Docker Engine + compose plugin from Docker's official repo, `ufw` allow 22/80/443, 2 GB swap file, clone the repo into `/srv/sweetspot`, create `/srv/sweetspot/.env` from `.env.example` with `DOMAIN=144-202-27-51.sslip.io` and `SITE_ADDRESS=144-202-27-51.sslip.io`, `docker compose -f deploy/docker-compose.yml up -d --build`); (b) update: `git pull && docker compose ... up -d --build`; (c) rollback to tag `demo-ok`; (d) switching to a .tech domain: DNS A record to 144.202.27.51, set `SITE_ADDRESS="yourname.tech, 144-202-27-51.sslip.io"` and `DOMAIN=yourname.tech`, `up -d`; (e) logs, restart, where data lives; (f) running `deploy/smoke.sh https://144-202-27-51.sslip.io`. Keep commands copy-pasteable.
4. `backend/tests/test_deploy_files.py` (no Docker, no network): Dockerfile uses `--workers 1`, copies the repo root, sets a non-root user and HEALTHCHECK; `.dockerignore` lists `.env`, `data/`, `.git`, `memory/`, `.localdata/`; compose has services `api` and `caddy`, only caddy maps 80/443, uses `env_file`, `DATA_DIR=/data`, named volumes (text/regex checks; do not add PyYAML); Caddyfile references `{$SITE_ADDRESS}`, `reverse_proxy api:8000`, the `/` redirect and a body limit; `smoke.sh` passes `bash -n` when bash exists (skip otherwise) and contains every endpoint listed above.

## Done when
`python -m pytest backend -q` passes; the files are complete enough that the orchestrator can follow DEPLOY.md on a fresh Ubuntu 24.04 VPS without guessing; no edits outside OWNS.txt.

## Out of scope
Running anything on the server, CI, Kubernetes, managed databases, monitoring stacks, the .tech purchase. Put unsettled choices (image size trade-offs, redirect target, body limit) under `## Design questions` in HANDOFF.md.

---
## RETRY 1 (2026-10-24): fix list. Keep what works; change only what is listed; add tests where possible.

The Codex review (VERDICT: ISSUES) found:
1. **Root-owned checkout** (`DEPLOY.md` ~l.38): `sudo git clone` makes `/srv/sweetspot` root-owned, so the documented `git pull`/rollback fail for the non-root user. Create the directory with sudo, `chown` it to the deploy user, then clone as that user (or document running everything as root consistently; prefer a non-root `deploy` user in the `docker` group). Make every later command in DEPLOY.md consistent with that ownership.
2. **Root-owned `.env`** (~l.71): the `sed -i` domain-switch commands must work for the same user; `.env` owned by that user with mode 600.
3. **False PASS on certificate check** (`deploy/smoke.sh` ~l.64): if no expiry date can be obtained, that step must FAIL (non-zero exit), never print PASS. Only skip it (print SKIP) for `http://` URLs.
4. **Missing `bash -n` check** (`backend/tests/test_deploy_files.py` ~l.45): run `bash -n deploy/smoke.sh` via `subprocess` when `shutil.which("bash")` finds bash, skip otherwise; also assert the expiry step's failure path exits non-zero (text/regex check is fine).
