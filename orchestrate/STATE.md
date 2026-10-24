# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: build   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 1
- last_checkpoint: 2026-10-24 21:00

## Next action
plot2d worker done: check PASS, review ISSUES (4 minor findings: stale optimize/products responses after switching rooms, plot.js:324,329; treatment patches must be translucent rectangles, l.129; fit padding 0.7 ft should be 0.5 ft, l.182). Awaiting user OK to retry once (append findings to plot2d BRIEF, start gpt-6-sol medium + review), then merge, restart local uvicorn (running on 127.0.0.1:8000 until user says stop), push. Wave 1 complete: core-api, materials, contracts all MERGED to master (tag demo-ok 926f98d), pushed. NEXT: user must decide scanned-room FRAME handling (recenter+yaw-align with a returned `frame` {yaw_deg, offset} vs keep raw world frame and add room bounds) because core-api code and the engine assume a room box [0,w]x[0,l] from the origin. Then write roomplan brief (gpt-6-astra high) and deploy brief (luna; needs Vultr IP + domain; ONE uvicorn worker; copy fixtures/ into image) and hit GATE 3. Stale worktrees: sweetspot-wt{core-api,materials,contracts}.
EELMDESKTOPSWEETSPOT-WTRE-API.

## Waiting on user
Gate 4 plot2d: retry the worker with the 4 findings (recommended), patch myself, or merge as is? Also still open: scan frame option 1/2/3 and Vultr IP + domain.

## Notes for a fresh session
- Team of 4: iOS (RoomPlan app, LiDAR iPhone + Xcode Mac available), physics engine (teammate, in progress), SerpApi products (teammate, in progress), Neel = backend/integration (FastAPI, Vultr, Caddy, .tech, Gemini, contract, pairing) + planning.
- Orchestrated scope = Neel's area plus the shared JSON contract. Teammates' parts are developed outside this orchestration and plug in via docs/API.md.
- PROJECT_CONTEXT.md is the seed context; sections 5-8 hold the contract, pairing and engine proposals.
