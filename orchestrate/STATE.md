# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 11
- last_checkpoint: 2026-10-25 01:20

## Next action
Status 01:20 (all on ACCOUNT 2): products-theater RETRY 1 is RUNNING (restarted 01:13, alive, fixing the 5 review findings + passive-filter gap, then check + review). engine3d-wire retry-1 worker is finished/finishing: its review returned ISSUES again at ~01:15 (backend/app/refine.py:285 fingerprint check + result save not atomic; refine.py:92 interrupted jobs only repaired when the status endpoint is called, so GET /layout can say refining forever) = SECOND ISSUES -> awaiting user's OK for one more retry with these two findings appended. docs-demo and docs-webspec both got a SECOND ISSUES (they describe the staged quick->refined flow as live and a non-existent `complete` status); recommendation to user: HOLD both until engine3d-wire is deployed, then fix wording once and merge. Merge order once PASS + VERDICT OK: engine3d-wire, products-theater, docs. A merge needs a clean tree and a passing check at the branch tip. After engine3d-wire merges: ruff + pytest, push, deploy to the VPS, smoke + e2e against https://sweetspotav.tech, confirm `stage` quick -> refined live. After products-theater merges: run tools/expand_catalog.py on the VPS, copy the DB back, widen PRODUCT_ROLES, deploy. .pytest_* dirs in the engine3d-wire worktree are unreadable (sandbox-owned); .gitignore now ignores them. Still paused by the user: polygon-geometry, polygon-engine, plot2d-patch-depth. Handover: memory/HANDOVER-2026-10-25-0035.md.
- iOS team (user, 2026-10-25 00:10): the iOS teammate is ONLY the builder/tester from now on; the user and the orchestrator write all Swift (branch ios-phone_context first, then master). The Swift has never been compiled: expect compile-error fix tasks from pasted Xcode output; ask the teammate to `git pull` before building and to report errors instead of pushing edits.

## Waiting on user
(1) engine3d-wire: one more retry with the 2 new findings? (2) hold docs-demo + docs-webspec until engine3d-wire ships? (3) Gate 3 for web-base: read orchestrate/tasks/web-base/BRIEF.md and say go (I install zustand/qrcode.react/jsdom/testing-library first, set config.json setup/test to include webapp, then dispatch on account 2). web-pairing brief is written (QR only, no 6-char code, user 01:16); briefs still to write: web-adapter, web-view2d, web-panels, web-drag/toggle, deploy-web, web-e2e. Everything runs on Codex account 2 until it is depleted (user, logged). Later: iOS teammate builds ios-phone_context in Xcode (needs a FULL room scan).

## Web app (01:13; decisions logged in DECISIONS.md; origin/webapp merged into master locally 3b71ca5, NOT pushed; web-base row in TASKS.md = todo, wave 13)
- Teammate built a standalone 3D viewer on origin/webapp (only adds frontend/: raw three.js, meters, own JSON, GLB models, no backend/pairing/2D/panels). Decisions: (1) adopt frontend/ as base, rename to webapp/, keep raw three.js, adapter feet layout -> meter scene; (2) web teammate = tester + assets only, all web code on master; (3) Docker multi-stage npm build into web/.
- Brief + OWNS for `web-base` are committed in orchestrate/tasks/web-base/, not dispatched (waiting for the user's go at Gate 3). Later tasks to brief after it: web-adapter, web-pairing, web-view2d, web-panels, web-drag/toggle, deploy-web (Dockerfile multi-stage + smoke), web-e2e.
- Auto mode was turned off by the harness at 01:12 after repeated classifier errors; commands may prompt the user.

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
