# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: build   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 1
- last_checkpoint: 2026-10-24 17:55

## Next action
core-api merged (e55744c) and pushed. Briefs for materials + contracts written, tasks ready. After GATE 3 OK: DISPATCH run-wave -Review (background, both in parallel). Then wave 2 briefs: roomplan (gpt-6-astra high), deploy (luna); deploy needs Vultr IP and domain from user (not yet created).
EELMDESKTOPSWEETSPOT-WTRE-API.

## Waiting on user
GATE 3: approve materials + contracts briefs (orchestrate/tasks/materials and contracts) and dispatch wave 1.

## Notes for a fresh session
- Team of 4: iOS (RoomPlan app, LiDAR iPhone + Xcode Mac available), physics engine (teammate, in progress), SerpApi products (teammate, in progress), Neel = backend/integration (FastAPI, Vultr, Caddy, .tech, Gemini, contract, pairing) + planning.
- Orchestrated scope = Neel's area plus the shared JSON contract. Teammates' parts are developed outside this orchestration and plug in via docs/API.md.
- PROJECT_CONTEXT.md is the seed context; sections 5-8 hold the contract, pairing and engine proposals.
