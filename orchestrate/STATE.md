# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 19
- last_checkpoint: 2026-10-25 11:25

## Next action
sweetspotav.tech is LIVE with a Let's Encrypt cert (issued 16:06 UTC after one caddy restart; A record 155.138.175.232 fixed by the user; some resolvers may cache the old 137 address for a while). Smoke passes with the address pinned (local openssl TLS-expiry check fails only because this PC resolves the old IP). Remaining: (1) iOS tester builds ios-phone_context (caec963 = master dca0e2b) and reports compile errors; known risk: `\(urlError, privacy: .private)` Logger line in BackendClient.swift (fallback `urlError.localizedDescription`). (2) Multicore speakerplacer is NOT wired: speakerplacer/parallel.py (mc-pool) is merged but unused; mc-wire was aborted and awaits the user's go (`set ready` + `start -Id mc-wire -Model gpt-6-sol -Effort high`, CODEX_HOME=~/.codex-third). (3) docs/API.md still lists POST /rooms/polygon (405 on server): trim. Cut by user: polygon-geometry, polygon-engine, plot2d-patch-depth.

## Infrastructure (2026-10-25, old Vultr instance 144.202.27.51 was terminated, no backup)
New VPS root@155.138.175.232 (Ubuntu 26.04, 4 CPU, 7 GB, swap). Docker 29.9.2 + Compose, ufw 22/80/443, stack in /srv/sweetspot (deploy-api-1, deploy-caddy-1, volume deploy_sweetspot_data). .env has DOMAIN=sweetspotav.tech, SITE_ADDRESS="sweetspotav.tech, 155-138-175-232.sslip.io", Gemini + SerpApi keys set by the user (api recreated with --no-deps). Smoke and e2e pass at https://155-138-175-232.sslip.io. Hardening: unattended-upgrades, fail2ban; nightly backup /usr/local/bin/sweetspot-backup.sh (03:30, keeps 7, same host). Docs updated and committed 01fa91c. Old rooms, scans, cached refinements and pairing sessions are lost. Open choices for the user: disable SSH password + root password login, off-box backups, Docker log rotation (needs a docker restart, do after the cert).

## Merged and pushed today
ios-error-audit merged 82ec29b; 11:21 iOS scan history shows the latest room id per scan (ScanHistoryView.swift, caec963, merged to master as dca0e2b, both pushed); pair-side 3D fix cdf2bd4 and docs 01fa91c are on origin and on the new VPS. Earlier: mc-pool b202b4f, speakerplacer-speed cea05ab, ios-theme, ios-polish, ios-qr-pairing, web-e2e.

## Backlog (user requests)
- mc-wire ABORTED 06:30 (branch task/mc-wire kept; restart = set `ready` + `start -Id mc-wire -Model gpt-6-sol -Effort high` with CODEX_HOME=~/.codex-third).
- Keep live AR session after history upload (iOS); AR guide colour question; L/R in the simplified layout close to the listener axis; 3D engine timeout now 360 s.
- Branch `ultrareview` exists for the user's Claude ultrareview.

## Waiting on user
Decide: restart mc-wire (multicore), SSH lockdown (password + root login still on), off-box backups, Docker log rotation. iOS tester results.

## Context
- Codex: account 1 depleted, account 2 parked, account 3 (`~/.codex-third`) in use. Check is fast (ruff + tools/smoke_tests.py + webapp tests if node_modules).
- iOS teammate is only builder/tester; user and orchestrator write all Swift (branch ios-phone_context first, then master). Swift never compiled; expect compile-error fix tasks.
- Nothing is running. Worktree dir C:/Users/neelm/Desktop/sweetspot-wt/ios-error-audit can be removed with `git worktree remove --force`.
- Handover notes: memory/HANDOVER-2026-10-25-0335.md.
