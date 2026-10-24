# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: integrate   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 3
- last_checkpoint: 2026-10-25 03:15

## Next action
Frame decision done (option 1): schemas Frame + warnings, API.md 1a, TESTING 3.6/3.7, phoneapp 01/02/04/05/README, frame_test_vectors.json, fixtures updated (143 tests pass). roomplan brief written (gpt-6-astra high), status todo pending GATE 3. plot2d: check PASS, review ISSUES (stale optimize/products responses on room switch; patches must be translucent rects; padding 0.5 ft) + orchestrator found rotation_y treated as radians (must be DEGREES, SVG rotate(-deg)); plot2d MERGED (7d816d0, tag demo-ok); local uvicorn restarted on 127.0.0.1:8000 serving /app/plot2d/ (keep until user says stop); :8001 preview stopped. Then merge plot2d, restart local uvicorn (running 127.0.0.1:8000 until user says stop), push. Vultr VPS IP 144.202.27.51, no domain yet: deploy brief written for Caddy auto-HTTPS on 144-202-27-51.sslip.io via SITE_ADDRESS (switch to .tech later). Wave 2 ran: roomplan check FAIL only on obsolete test_rooms 501 assertion (fixed on master 'test_rooms: expect 422', merged master into task/roomplan): re-check PASS, review VERDICT OK -> merge-eligible, hold for GATE 5 together with deploy. deploy check PASS, review ISSUES (4: root-owned clone/.env in DEPLOY.md, smoke.sh cert false PASS, missing bash -n test) -> retry 1: check PASS, review ISSUES again (4 nits) -> orchestrator patched all 4 on task/deploy (GET-only root redirect, git/openssl/python3 prereqs, chained update), check PASS. Orchestrator reviewed Dockerfile/compose/DEPLOY.md: OK. Repo is public (clone needs no auth). When it exits: read summary, set PASS tasks to review, GATE 4/5, merge, push; then ask user before running DEPLOY.md over SSH (user creates server .env with keys). Actual deploy is run by orchestrator over SSH after merge, with user OK.
EELMDESKTOPSWEETSPOT-WTRE-API.

## Waiting on user
User to add API keys in /srv/sweetspot/.env on the server; decide who builds the web app (teammate vs worker).

## Notes for a fresh session
- Team of 4: iOS (RoomPlan app, LiDAR iPhone + Xcode Mac available), physics engine (teammate, in progress), SerpApi products (teammate, in progress), Neel = backend/integration (FastAPI, Vultr, Caddy, .tech, Gemini, contract, pairing) + planning.
- Orchestrated scope = Neel's area plus the shared JSON contract. Teammates' parts are developed outside this orchestration and plug in via docs/API.md.
- PROJECT_CONTEXT.md is the seed context; sections 5-8 hold the contract, pairing and engine proposals.
