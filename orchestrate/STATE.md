# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 3
- last_checkpoint: 2026-10-24 18:35   (real clock from `date`; older labels up to "2026-10-25 03:50" in history were mislabeled)

## Next action
Ask the user whether to brief and dispatch the wave-3 tasks: `integrate` (tools/e2e.py against https://144-202-27-51.sslip.io, backend/tests/e2e, DEMO.md with failure drills) and `lint` (ruff, see Notes). Then GATE 3 -> run -> GATE 4/5 -> merge -> push -> on the server `cd /srv/sweetspot && git pull && docker compose -f deploy/docker-compose.yml up -d --build` -> `bash deploy/smoke.sh https://144-202-27-51.sslip.io`.

## Waiting on user
1. Dispatch `integrate` and `lint` now? 2. User adds GEMINI_API_KEY and SERPAPI_KEY to /srv/sweetspot/.env on the server (never through chat). 3. Web teammate builds the React + Vite app in webapp/ from webapp_context/.

## Built and merged (master, pushed; local tag demo-ok at ac6a154; GitHub's demo-ok tag is stale because a force push was declined)
- Tasks done: core-api, materials, contracts, roomplan (scan normalization + frame), deploy files, plot2d (/app/plot2d/), engine-adapter (backend/app/engine_speakerplacer.py + backend/app/acoustics.py) around the teammate `speakerplacer` engine (merged from origin/speakerplacer, unrelated history).
- Full suite: `python -m pytest -q` = 249 passed (about 75 s; includes tests/ for the teammate engine).
- Web app is SPEC only: webapp_context/ README + 01-07 + real sample payloads. Stack: React + Vite, base /app/, built into web/ at deploy.

## Live deployment
- https://144-202-27-51.sslip.io on VPS 144.202.27.51 (Ubuntu 26.04, root SSH key works from this machine, Docker 29.9, ufw 22/80/443, existing 8 GB swap). Repo /srv/sweetspot (pull before rebuild). .env mode 600 with DOMAIN/SITE_ADDRESS = 144-202-27-51.sslip.io, DATA_DIR=/data, keys empty. Caddy Let's Encrypt cert valid to 2027-01-22. smoke.sh all PASS; optimize runs speakerplacer (~8 s); root `/` redirects to /app/plot2d/.

## Notes for a fresh session
- Team: iOS (phoneapp_context/), engine teammate (speakerplacer, merged), SerpApi teammate (products/ module NOT delivered; backend uses the products stub), web teammate (webapp_context/). Neel = backend/integration + planning; this orchestration owns backend, contracts, deploy.
- **Planned `lint` task (user request): ruff** for our Python code. Add `ruff.toml` at the repo root: `target-version = "py312"`, `line-length = 120`, `[lint] select = ["E","F","W","I","B","UP"]`, `extend-exclude = ["speakerplacer", "tests/test_speakerplacer.py"]` (teammate code, dense style; lint it only with their agreement). Pin `ruff` in backend/requirements.txt (dev). Fix existing findings in backend/, tools/, conftest.py, fix import order with `ruff check --fix`, then make the orchestrate test command `ruff check . && python -m pytest -q` so every merge is lint-gated. Do not reformat the whole tree with `ruff format` mid-hackathon (noisy diffs); `ruff format --check` optional later.
- When webapp/ lands: Node build stage in deploy/Dockerfile (copy webapp/dist into web/), .dockerignore webapp/node_modules + webapp/dist, Caddy root redirect /app/plot2d/ -> /app/, backend/tests/test_web_app.py (skips without a build).
- When products/ lands: contract tests (real products only under -m live); the adapter loads `products` automatically.
- When the real iOS scan arrives: replace fixtures/roomplan_sample.json, run tools/validate_dto.py and the roomplan tests.
- Known gaps: speakerplacer has no center model (adapter places C geometrically); Gemini model name gemini-2.5-flash unverified; no .tech domain yet.
- Tooling gotchas: Codex sandbox leaves locked `.<task>-run/` dirs (excluded via .git/info/exclude `.*-run/`); worker timeoutSec 1800; `run-wave` only starts `ready` tasks; commit DECISIONS.md before `dispatch merge`; never force-push; heredocs containing ``` fences fail in the Bash tool (write scripts to .localdata/, which is git-excluded); `MSYS_NO_PATHCONV=1` for `git show rev:path`.
- Models per user: gpt-6-sol / gpt-5.6-luna default, gpt-5.6-terra when the user asks, gpt-6-astra only for the hardest.
- Local handover notes: memory/HANDOVER-2026-10-24-1504.md (local only, git-excluded).
