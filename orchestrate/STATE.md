# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 11
- last_checkpoint: 2026-10-25 00:37

## Next action
*** ALL WORKERS PAUSED at 00:36 (real clock) by the user (this Claude account is near its 5 h limit and the context is degrading). NOTHING IS RUNNING. Nothing is merging; master is clean and pushed. Resume in a fresh session: run `/orchestrate`, read memory/HANDOVER-2026-10-25-0035.md first, then `DISPATCH status` (expect INTERRUPTED for engine3d-wire, docs-demo, docs-webspec).
RESUME ORDER (all on CODEX ACCOUNT 2, set `$env:CODEX_HOME="$HOME\.codex-second"` in the SAME PowerShell command as start/review; account 1 is at 7% until 1 am; ONE account at a time). Use background jobs (run_in_background) and verify the process is alive:
 1. engine3d-wire (critical path; worktree ..\sweetspot-wt\engine3d-wire keeps 12 changed files; when stopped its full suite was at 80% with 3 failures it was fixing; ran 14 min): `dispatch.ps1 start -Id engine3d-wire -Model gpt-6-sol -Effort high` then `review -Id engine3d-wire`. On PASS + review OK: commit state files, merge as a background job (one merge at a time), ruff + pytest, push, DEPLOY to the VPS (cold start about 25 s, warm up), smoke + e2e against https://sweetspotav.tech, confirm `stage` quick -> refined live. ISSUES -> one retry on account 2; second ISSUES -> ask the user.
 2. docs-webspec (worktree keeps 5 changed files; diff clean, ruff passed, was running tests) and docs-demo (1 changed file, DEMO.md; was running tests): `start -Id <id> -Model gpt-5.6-luna -Effort medium` then `review -Id <id>`; docs only; merge when OK.
 3. products-theater (worker finished earlier; branch has master merged in; check + Codex review were running): `check -Id products-theater` then `review -Id products-theater` (background), merge, then run `python tools/expand_catalog.py --db /data/av_prices.db` ON THE VPS (keys live there), copy the DB back, commit products/av_prices.db, widen PRODUCT_ROLES in backend/tests/contract/checks.py, deploy.
 4. Still paused by the user: polygon-geometry, polygon-engine, plot2d-patch-depth.
Follow-ups: docs/ENGINE_INTEGRATION_AUDIT.md rows 16-19 (plot2d, iOS, web specs, docs), root README rewrite, the iOS teammate's first Xcode build + a FULL room scan.

- iOS team (user, 2026-10-25 00:10): the iOS teammate is ONLY the builder/tester from now on; the user and the orchestrator write all Swift (branch ios-phone_context first, then master). The Swift has never been compiled: expect compile-error fix tasks from pasted Xcode output; ask the teammate to `git pull` before building and to report errors instead of pushing edits.

## Waiting on user
Nothing blocking. The user is switching to a fresh session after the pause above. Later: the iOS teammate builds ios-phone_context in Xcode (needs a FULL room scan); optional decision: Codex sandbox unelevated to end UAC prompts.

## SerpApi integration (merged on master; products-adapter merged 20:24, so the backend now loads `products` instead of the stub)
- origin/serp merged; teammate files moved to products/catalog.py, products/search.py, products/av_prices.db (2,866 listings), only change = `from . import catalog`. products/__init__.py is a docstring until products-adapter lands (backend falls back to the stub meanwhile). requests + python-dotenv pinned. ruff excludes the two teammate files.
- docs/API.md section 4 rewritten with the user's decisions (DB first, expansion if fewer than 3 matches, filters, role mapping, front-weighted value pick, pairs with pair_with, specs + dimensions in feet). Tell the teammate their files moved (1a, user approved).

## Waves 3-4 (done: lint, integrate, products-adapter, products-spend)
- products-adapter: brief encodes the value formula (q = rating + spec parts; maximise q - 0.35 price/share), dimension parsing + defaults, deadline-bound expansion thread (PRODUCTS_EXPAND_DEADLINE_S=20).
- lint: ruff.toml + ruff==0.17.2 already committed on master by the orchestrator (about 150 findings, mostly tools/validate_dto.py and backend/tests/contract/). Worker fixes findings behaviour-preserving.
- integrate: tools/e2e.py (run_e2e(client) + CLI), backend/tests/e2e (in-process + live-marked), DEMO.md with failure drills. Must itself pass ruff.
- Codex: account 1 at 21%; account 2 = CODEX_HOME=~/.codex-second (PowerShell profile function codex2). Dispatch inherits CODEX_HOME from the calling shell.

## Built and merged (master, pushed; local tag demo-ok at ac6a154; GitHub's demo-ok tag is stale because a force push was declined)
- Tasks done: core-api, materials, contracts, roomplan, deploy, plot2d (/app/plot2d/), engine-adapter (backend/app/engine_speakerplacer.py + acoustics.py) around the teammate `speakerplacer` engine.
- Full suite: `python -m pytest -q` = 249 passed (about 75 s).
- Web app is SPEC only: webapp_context/ README + 01-07 + sample payloads. Stack: React + Vite, base /app/, built into web/ at deploy.

## Live deployment
- https://144-202-27-51.sslip.io on VPS 144.202.27.51 (Ubuntu 26.04, root SSH key works from this machine, Docker, ufw 22/80/443, 8 GB swap). Repo /srv/sweetspot (pull before rebuild). .env mode 600 with DOMAIN/SITE_ADDRESS = 144-202-27-51.sslip.io, DATA_DIR=/data, keys empty. Caddy cert valid to 2027-01-22. smoke.sh all PASS; optimize ~8 s; `/` redirects to /app/plot2d/.

## Notes for a fresh session
- Team: iOS (phoneapp_context/), engine teammate (speakerplacer, merged), SerpApi teammate (products/ NOT delivered; backend uses the stub), web teammate (webapp_context/). Neel = backend/integration + planning.
- Lint policy: ruff (py312, line 120, E F W I B UP), speakerplacer + tests/test_speakerplacer.py excluded (teammate code); no tree-wide `ruff format` mid-hackathon.
- When webapp/ lands: Node build stage in deploy/Dockerfile (copy webapp/dist into web/), .dockerignore webapp/node_modules + webapp/dist, Caddy root redirect /app/plot2d/ -> /app/, backend/tests/test_web_app.py (skips without a build).
- When products/ lands: contract tests (real products only under -m live); the adapter loads `products` automatically.
- When the real iOS scan arrives: replace fixtures/roomplan_sample.json, run tools/validate_dto.py and the roomplan tests.
- Known gaps: speakerplacer has no center model (adapter places C geometrically); Gemini model is gemini-3.8-flash (2.5 retired), credits added and verified; no .tech domain yet.
- Tooling gotchas: dispatcher shell resolves `bash` to the WSL launcher (system32\bash.EXE, exit 127): tests must not require it; first account-2 Codex run triggers ~10 UAC prompts (one-time); Codex sandbox leaves locked `.<task>-run/` dirs (git-excluded); worker timeoutSec 1800; `run-wave` only starts `ready` tasks; commit DECISIONS.md before `dispatch merge`; never force-push; Bash-tool heredocs with long markdown fail: use the Write tool; `MSYS_NO_PATHCONV=1` for `git show rev:path`.
- Codex accounts (user rule): with 2+ tasks, spread workers across account 1 (CODEX_HOME unset) and account 2 (CODEX_HOME=~/.codex-second) using parallel `start -Id` calls, then `review -Id`; run-wave alone uses one account.
- Codex UAC (corrected 22:46): staggering is NOT enough; concurrent workers on BOTH accounts make every command re-provision the shared sandbox users (UAC every ~10 s). Run workers on ONE account at a time (several tasks on the same account are fine) and switch accounts only when the other has no running worker. `abort` leaves the chained review process alive: kill it; fallback idea: `[windows] sandbox = "unelevated"` in both config.toml (user decision pending).
- Deploy rule (user): once backend merges are complete, push master and redeploy the VPS (git pull + docker compose up -d --build), then smoke.sh and tools/e2e.py against https://144-202-27-51.sslip.io.
- Codex quota (user, 2026-10-24 ~23:15): account 1 at 7%, resets at 1 am (local); until then run ALL workers on account 2 (CODEX_HOME=$HOME/.codex-second), one account at a time. Local clock note: `date` shows 23:xx on 10-24 when older STATE labels read 02:xx on 10-25 (labels were ahead by about 3 hours); the deadline 2026-10-25 11:30 is on the real clock.
- Models per user: gpt-6-sol / gpt-5.6-luna default, gpt-5.6-terra when the user asks, gpt-6-astra only for the hardest.
