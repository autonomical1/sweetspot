# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 19
- last_checkpoint: 2026-10-25 10:58

## Next action
The VPS was rebuilt (see Infrastructure). Finish it: (1) the user must correct the A record for sweetspotav.tech to 155.138.175.232 (all four authoritative nameservers still answer the typo 155.137.175.232 at 10:55); Caddy then issues the certificate by itself, so do NOT restart caddy. A background poll (task bx2douyfb) watches https://sweetspotav.tech/health. (2) Then deploy master 82ec29b to the VPS (it was cloned at 8878ec4; the merge only changes iOS Swift, so no backend redeploy is needed) and run smoke.sh + tools/e2e.py against https://sweetspotav.tech. (3) iOS tester builds ios-phone_context (82ec29b) and reports compile errors; one known risk: the `\(urlError, privacy: .private)` Logger line in BackendClient.swift may not compile (fallback `urlError.localizedDescription`). Cut by user: polygon-geometry, polygon-engine, plot2d-patch-depth; docs/API.md still lists POST /rooms/polygon (returns 405 on the server), trim it.

## Infrastructure (2026-10-25, old Vultr instance 144.202.27.51 was terminated, no backup)
New VPS root@155.138.175.232 (Ubuntu 26.04, 4 CPU, 7 GB, swap). Docker 29.9.2 + Compose, ufw 22/80/443, stack in /srv/sweetspot (deploy-api-1, deploy-caddy-1, volume deploy_sweetspot_data). .env has DOMAIN=sweetspotav.tech, SITE_ADDRESS="sweetspotav.tech, 155-138-175-232.sslip.io", Gemini + SerpApi keys set by the user (api recreated with --no-deps). Smoke and e2e pass at https://155-138-175-232.sslip.io. Hardening: unattended-upgrades, fail2ban; nightly backup /usr/local/bin/sweetspot-backup.sh (03:30, keeps 7, same host). Docs updated and committed 01fa91c. Old rooms, scans, cached refinements and pairing sessions are lost. Open choices for the user: disable SSH password + root password login, off-box backups, Docker log rotation (needs a docker restart, do after the cert).

## Merged and pushed today
ios-error-audit merged 82ec29b (pushed to master and ios-phone_context); pair-side 3D fix cdf2bd4 and docs 01fa91c are on origin and on the new VPS. Earlier: mc-pool b202b4f, speakerplacer-speed cea05ab, ios-theme, ios-polish, ios-qr-pairing, web-e2e.

## Backlog (user requests)
- mc-wire ABORTED 06:30 (branch task/mc-wire kept; restart = set `ready` + `start -Id mc-wire -Model gpt-6-sol -Effort high` with CODEX_HOME=~/.codex-third).
- Keep live AR session after history upload (iOS); AR guide colour question; L/R in the simplified layout close to the listener axis; 3D engine timeout now 360 s.
- Branch `ultrareview` exists for the user's Claude ultrareview.

## Waiting on user
Fix the A record (155.138.175.232). Decide: SSH lockdown, off-box backups, whether to restart mc-wire.

## Context
- Codex: account 1 depleted, account 2 parked, account 3 (`~/.codex-third`) in use. Check is fast (ruff + tools/smoke_tests.py + webapp tests if node_modules).
- iOS teammate is only builder/tester; user and orchestrator write all Swift (branch ios-phone_context first, then master). Swift never compiled; expect compile-error fix tasks.
- Nothing is running except the DNS/cert poll. Worktree dir C:/Users/neelm/Desktop/sweetspot-wt/ios-error-audit can be removed with `git worktree remove --force`.
- Handover notes: memory/HANDOVER-2026-10-25-0335.md.
