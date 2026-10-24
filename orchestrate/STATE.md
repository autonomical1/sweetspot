# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 3
- last_checkpoint: 2026-10-24 18:56

## Next action
On GATE 3 approval run wave 3 on the second Codex account: PowerShell `$env:CODEX_HOME="$HOME\.codex-second"; powershell -NoProfile -File "$HOME/.claude/skills/orchestrate/scripts/dispatch.ps1" run-wave -Review` (background). Then GATE 4 -> GATE 5 merge lint first, then integrate -> set config.json test to `python -m ruff check . && python -m pytest -q` -> push -> server `cd /srv/sweetspot && git pull && docker compose -f deploy/docker-compose.yml up -d --build` -> `bash deploy/smoke.sh https://144-202-27-51.sslip.io` and `python tools/e2e.py https://144-202-27-51.sslip.io`.

## Waiting on user
1. GATE 3: approve the wave-3 briefs (orchestrate/tasks/lint/BRIEF.md, orchestrate/tasks/integrate/BRIEF.md), both gpt-5.6-luna medium on account 2? 2. User adds GEMINI_API_KEY and SERPAPI_KEY to /srv/sweetspot/.env (never through chat); not done yet. 3. Web app (webapp/, React + Vite) starts after the SerpApi teammate delivers products/.

## Wave 3 (ready, not started)
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
- Known gaps: speakerplacer has no center model (adapter places C geometrically); Gemini model name gemini-2.5-flash unverified; no .tech domain yet.
- Tooling gotchas: Codex sandbox leaves locked `.<task>-run/` dirs (git-excluded); worker timeoutSec 1800; `run-wave` only starts `ready` tasks; commit DECISIONS.md before `dispatch merge`; never force-push; Bash-tool heredocs with long markdown fail: use the Write tool; `MSYS_NO_PATHCONV=1` for `git show rev:path`.
- Models per user: gpt-6-sol / gpt-5.6-luna default, gpt-5.6-terra when the user asks, gpt-6-astra only for the hardest.
