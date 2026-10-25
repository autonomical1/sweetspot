# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 8
- last_checkpoint: 2026-10-25 02:25

## Next action
Wave 8 running since about 01:50 (02:25 added: `gemini-limits` backend and `ios-materials-wait` Swift, both gpt-6-sol medium on Codex account 1 with products-theater; ios-shop-push already merged); POLYGON WORK IS PAUSED by the user at 02:05 (polygon-geometry aborted, polygon-engine and plot2d-patch-depth blocked; ignore the polygon steps below until the user resumes; docs/API.md still contains the outline and /rooms/polygon contract, not implemented) (staggered starts; each a background `start` then `review` job): `products-theater` (gpt-6-sol high, Codex account 1), `polygon-geometry` (PAUSED/aborted), `ios-shop-push` (gpt-6-sol medium, account 1; iOS rule). On each exit read the result line and review: PASS + OK -> merge. Backend tasks: `DISPATCH merge -Id <id>` (merge master into the task branch first if master moved, then recheck), ruff + pytest. iOS task: merge task/ios-shop-push into branch ios-phone_context via ../sweetspot-ios (merge master first), push, then merge ios-phone_context into master. ISSUES -> one retry (alternate accounts); a second ISSUES -> ask the user (they usually choose: orchestrator patches, or merge with override). After polygon-geometry merges: write the polygon-engine brief (adapter passes the outline in metres to speakerplacer.optimize_layout via validate_polygon, object avoidance and clamps use point-in-polygon, acoustics per-edge reflections, treatment patches per edge, modes via the engine's polygon modal response, tests with an L-shaped room, rectangles unchanged), then dispatch it (gpt-6-sol high), then plot2d-patch-depth. After products-theater merges: run `python tools/expand_catalog.py --db <db>` ON THE VPS (keys live there; inside the api container, against /data/av_prices.db) to add centers, packages, receivers and accessories, copy the DB back and commit it as products/av_prices.db, extend `PRODUCT_ROLES` in backend/tests/contract/checks.py for the new roles, then deploy per the user's rule (push master, VPS pull + up -d --build, smoke.sh and e2e.py against https://sweetspotav.tech, check the first products request). Deploy polygon-geometry and polygon-engine together (polygon-geometry alone makes optimize ignore the outline).

## Waiting on user
Nothing blocking. TELL THE iOS TEAMMATE: their commit 8e007ee (baseURL fix) was made on a stale checkout and removed the products UI, budget and roomFrame code; it was merged keeping all code plus their baseURL (ios-phone_context b19c542); they must `git pull` before editing and not overwrite whole files. For later: build ios-phone_context in Xcode and run the device checklists (needs a FULL room scan); switch iOS AppConfig.baseURL to https://sweetspotav.tech (on ios-phone_context) and tell the iOS teammate; tell the SerpApi teammate their files moved to products/; web/3D teammates get product `dimensions`, `pair_with`, `alternatives`, `included_in` and the room `outline`; optional: Codex sandbox unelevated to avoid UAC prompts.

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
