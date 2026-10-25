# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 16
- last_checkpoint: 2026-10-25 04:10

## Next action
ios-qr-pairing and web-e2e are MERGED (demo-ok 77feaa0), master pushed, VPS redeployed and verified (smoke + e2e pass, `pair_url` uses sweetspotav.tech). Browser check in progress: Chrome tab 865081234 shows the QR at https://sweetspotav.tech/app/?pair (expires about 04:35; do not reload it). A background job tails the VPS API logs into the scratchpad file vps.log (task brn1biuho). When the user says they scanned: grep vps.log for the session/pairing and scan POSTs (POST /sessions/..., /rooms/scan), confirm the web page switches to the scanned room, then report. Later: ios-polish (brief has item 4, remove the "Found" rows) awaits the user's go. Cut by user: polygon-geometry, polygon-engine, plot2d-patch-depth. Remove leftover worktree dirs with `git worktree remove --force` (ios-qr-pairing, web-e2e). docs/API.md may still hold the polygon outline contract: check.

## Waiting on user
Scan the QR on the web page with the iPhone app (latest build), then do the room scan, and say when it is uploaded.

## Context
- Codex: account 1 depleted, account 2 parked, account 3 (`~/.codex-third`) in use. Check is fast (ruff + tools/smoke_tests.py + webapp tests if node_modules).
- iOS teammate is only builder/tester; user and orchestrator write all Swift (branch ios-phone_context first, then master). Swift never compiled; expect compile-error fix tasks.
- Web: teammate frontend/ adopted as webapp/, all web code on master. Pairing is QR only, per scan. Master has local commits ahead of origin until the push in step 3.
- Handover notes: memory/HANDOVER-2026-10-25-0335.md.
