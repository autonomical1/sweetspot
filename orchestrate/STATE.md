# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 16
- last_checkpoint: 2026-10-25 03:45

## Next action
User plan (03:36): (1) web-e2e resumed on Codex account 3 (`CODEX_HOME=~/.codex-third`, gpt-5.6-luna medium; background job started 03:40, `DISPATCH start -Id web-e2e`); when it finishes run `check -Id web-e2e`, then review/merge. (2) ios-qr-pairing: its branch predated the fast check, so master was merged into the worktree and `check -Id ios-qr-pairing` re-run in the background (read orchestrate/logs/ios-qr-pairing/test.log); on PASS set the task `review` in TASKS.md (it was `blocked`; the hold is lifted by the user) and `DISPATCH merge -All`. (3) Deploy: `git push origin master`, ssh VPS `cd /srv/sweetspot && git pull && docker compose -f deploy/docker-compose.yml up -d --build`, then deploy/smoke.sh + tools/e2e.py on https://144-202-27-51.sslip.io and confirm `pair_url` uses sweetspotav.tech. (4) Only after all of that: browser check of the web app; STOP and wait for the user to scan the QR with their phone and do the scan, while monitoring VPS logs (`docker compose logs -f`) for the pairing/scan POST requests.
Done this checkpoint: polygon-geometry, polygon-engine, plot2d-patch-depth CUT (user); ios-polish brief gained item 4 (remove the "Found" LabeledContent rows in ScanHistoryView.swift and SweetspotApp.swift); docs-demo/docs-webspec were already merged 02:55 (nothing to run). ios-polish is NOT started (awaits user go). docs/API.md may still contain the polygon outline contract: check and remove if unused.

## Waiting on user
Nothing now. Later: the phone QR scan during the browser check.

## Context
- Codex: account 1 depleted, account 2 parked, account 3 (`~/.codex-third`) in use. Check is fast (ruff + tools/smoke_tests.py + webapp tests if node_modules).
- iOS teammate is only builder/tester; user and orchestrator write all Swift (branch ios-phone_context first, then master). Swift never compiled; expect compile-error fix tasks.
- Web: teammate frontend/ adopted as webapp/, all web code on master. Pairing is QR only, per scan. Master has local commits ahead of origin until the push in step 3.
- Handover notes: memory/HANDOVER-2026-10-25-0335.md.
