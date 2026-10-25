# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 11
- last_checkpoint: 2026-10-25 00:33

## Next action
State at 00:33 (real clock); nothing is merging in the main tree. A new handover exists: memory/HANDOVER-2026-10-25-0035.md (read it first in a fresh session). MERGED today: engine3d-core (b95d880), domain-rename (971fdda), ios-phone_context with ios-materials-wait (bdc50a2). ALL WORKERS RUN ON CODEX ACCOUNT 2 (reset to 95% at 00:30; account 1 is at 7% until 1 am; one account at a time because the sandbox users are shared). RUNNING on account 2: (1) `engine3d-wire` (critical path; gpt-6-sol high; background job bg1yfo7m4 start+review): on exit read result + review; PASS + OK -> merge as a BACKGROUND job (commit state files first; verify the process is alive), ruff + pytest, push, DEPLOY to the VPS (cold start ~25 s; warm up), smoke + e2e against https://sweetspotav.tech, check `stage` quick -> refined live; ISSUES -> one retry on account 2, a second ISSUES -> ask the user. (2) `products-theater` (user resumed 00:32; master merged into its branch; background job bfp48beqr runs check then review): then merge, run `python tools/expand_catalog.py --db /data/av_prices.db` ON THE VPS (keys live there), copy the DB back and commit products/av_prices.db, widen PRODUCT_ROLES in backend/tests/contract/checks.py, deploy. (3) `docs-demo` (resumed on account 2 at 00:30 from its partial DEMO.md edits; job b3878a1ym). (4) `docs-webspec` (account-1 attempt failed: no changes because the sandbox launches were cancelled; rerun on account 2 started 00:32; job in the background). Docs tasks: Codex review, then merge when OK. Paused: polygon-geometry, polygon-engine, plot2d-patch-depth (user). Follow-ups after engine3d-wire: docs/ENGINE_INTEGRATION_AUDIT.md rows 16-19 (plot2d, iOS, web specs, docs), root README rewrite, first Xcode build by the iOS teammate (compile errors), FULL room scan. LESSON: run `dispatch merge`/`check` ONLY as background jobs and verify the process is alive; one merge at a time.

- iOS team (user, 2026-10-25 00:10): the iOS teammate is ONLY the builder/tester from now on; the user and the orchestrator write all Swift (branch ios-phone_context first, then master). The Swift has never been compiled: expect compile-error fix tasks from pasted Xcode output; ask the teammate to `git pull` before building and to report errors instead of pushing edits.

## Waiting on user
Nothing blocking. The staged engine design is confirmed. The engine and SerpApi teammates are done (integration is on the user and orchestrator). Later: build ios-phone_context in Xcode (needs a FULL room scan); tell the iOS and web teammates about the new roles and fields once engine3d-wire lands.

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
