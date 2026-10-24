# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: build   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 1
- last_checkpoint: 2026-10-24 19:50

## Next action
Wave 1 complete: core-api, materials, contracts all MERGED to master (tag demo-ok 926f98d), pushed. NEXT: user must decide scanned-room FRAME handling (recenter+yaw-align with a returned `frame` {yaw_deg, offset} vs keep raw world frame and add room bounds) because core-api code and the engine assume a room box [0,w]x[0,l] from the origin. Then write roomplan brief (gpt-6-astra high) and deploy brief (luna; needs Vultr IP + domain; ONE uvicorn worker; copy fixtures/ into image) and hit GATE 3. Stale worktrees: sweetspot-wt{core-api,materials,contracts}.
EELMDESKTOPSWEETSPOT-WTRE-API.

## Waiting on user
API design question (always interrupts): how scanned rooms map into the engine frame.

## Notes for a fresh session
- Team of 4: iOS (RoomPlan app, LiDAR iPhone + Xcode Mac available), physics engine (teammate, in progress), SerpApi products (teammate, in progress), Neel = backend/integration (FastAPI, Vultr, Caddy, .tech, Gemini, contract, pairing) + planning.
- Orchestrated scope = Neel's area plus the shared JSON contract. Teammates' parts are developed outside this orchestration and plug in via docs/API.md.
- PROJECT_CONTEXT.md is the seed context; sections 5-8 hold the contract, pairing and engine proposals.
