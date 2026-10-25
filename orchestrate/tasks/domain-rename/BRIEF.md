# domain-rename: use sweetspotav.tech everywhere (sslip.io only as the documented fallback)

## Goal
The project now lives at https://sweetspotav.tech (live since 2026-10-24, certificate from Let's Encrypt via Caddy). Remove the old `144-202-27-51.sslip.io` references from docs and config examples so teammates copy the right address. The server keeps `144-202-27-51.sslip.io` as a FALLBACK in `SITE_ADDRESS`; that stays and is documented once.

## Read first
`grep -rIn sslip .` (excluding `.git`, `.localdata`, `orchestrate/logs`). Known files: DEPLOY.md (lines 7, 10, 20, 62, 63, 90, 111 and the "Live domain" section at the end), .env.example (lines 2 and 4), webapp_context/README.md (line 12).

## Rules
- DEPLOY.md: every command, URL and example uses `https://sweetspotav.tech` / `DOMAIN=sweetspotav.tech` and `SITE_ADDRESS="sweetspotav.tech, 144-202-27-51.sslip.io"` (the fallback stays in that one value). Fix the stale sentences ("until the web app exists", "API keys still empty", "optimize about 8 s": keys are set, `GEMINI_MODEL=gemini-3.8-flash`, the first optimize after a restart takes about 25 s, repeats are instant). Keep the "Live domain" section and make it the single place that explains the sslip.io fallback and the `.env.bak-pre-domain` file. The DNS steps for a NEW domain section can stay generic (`yourname.tech`).
- .env.example: `DOMAIN=sweetspotav.tech` with the comment explaining it, `SITE_ADDRESS` comment example `"sweetspotav.tech, 144-202-27-51.sslip.io"`. Keep `localhost` as the default VALUES for local dev.
- webapp_context/README.md: replace the example host with `sweetspotav.tech`.
- Do NOT edit orchestrate/DECISIONS.md, STATE.md, TASKS.md, any other task's BRIEF/HANDOFF (history), memory/, or code (deploy/smoke.sh and tools/e2e.py take the URL as an argument; the iOS app already uses sweetspotav.tech). Do not touch the server.
- `backend/tests/test_deploy_files.py` checks DEPLOY.md/.env.example text: update only if an assertion encodes the old host, and keep the test intent.

## Deliverables / done when
The files above updated; `grep -rIn sslip .` (excluding history files listed) shows only the single intended fallback mentions in DEPLOY.md and `.env.example`; `python -m ruff check . && python -m pytest -q` passes; HANDOFF.md lists what changed.

## Out of scope
Everything else.
