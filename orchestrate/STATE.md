# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 16
- last_checkpoint: 2026-10-25 03:58

## Next action
ios-qr-pairing MERGED 03:58 (tag demo-ok fe8b2f9; I resolved the Swift conflicts with master's setup-form flow; worktree dir left behind, remove with `git worktree remove --force`). web-e2e RUNNING (background job blxr1zocf, Codex account 3): when it ends run `check -Id web-e2e`, set `review`, `merge -Id web-e2e`. Then DEPLOY: `git push origin master`; ssh root@144.202.27.51 `cd /srv/sweetspot && git pull && docker compose -f deploy/docker-compose.yml up -d --build`; deploy/smoke.sh + tools/e2e.py on https://144-202-27-51.sslip.io; confirm `pair_url` uses sweetspotav.tech. Then browser check of the web app and STOP for the user to scan the QR on their phone and do the scan, watching VPS logs (`docker compose logs -f`) for pairing/scan POSTs. Cut by user: polygon-geometry, polygon-engine, plot2d-patch-depth. ios-polish brief has item 4 (remove the "Found" rows) and awaits the user's go. docs/API.md may still hold the polygon outline contract: check.

## Waiting on user
Nothing now. Later: the phone QR scan during the browser check.

## Context
- Codex: account 1 depleted, account 2 parked, account 3 (`~/.codex-third`) in use. Check is fast (ruff + tools/smoke_tests.py + webapp tests if node_modules).
- iOS teammate is only builder/tester; user and orchestrator write all Swift (branch ios-phone_context first, then master). Swift never compiled; expect compile-error fix tasks.
- Web: teammate frontend/ adopted as webapp/, all web code on master. Pairing is QR only, per scan. Master has local commits ahead of origin until the push in step 3.
- Handover notes: memory/HANDOVER-2026-10-25-0335.md.
