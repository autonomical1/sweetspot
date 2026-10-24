# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: plan   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 0
- last_checkpoint: 2026-10-24 15:05

## Next action
GATE 2: user approves task table (orchestrate/TASKS.md), docs/API.md (feet, no WebSocket) and docs/TESTING.md. Then write BRIEF.md + OWNS.txt per wave-1 task (core-api, materials, contracts) and hit GATE 3.

## Waiting on user
GATE 2: approve plan, API (feet units, DTO in meters, photo-targets), TESTING.md; give Codex quota.

## Notes for a fresh session
- Team of 4: iOS (RoomPlan app, LiDAR iPhone + Xcode Mac available), physics engine (teammate, in progress), SerpApi products (teammate, in progress), Neel = backend/integration (FastAPI, Vultr, Caddy, .tech, Gemini, contract, pairing) + planning.
- Orchestrated scope = Neel's area plus the shared JSON contract. Teammates' parts are developed outside this orchestration and plug in via docs/API.md.
- PROJECT_CONTEXT.md is the seed context; sections 5-8 hold the contract, pairing and engine proposals.
