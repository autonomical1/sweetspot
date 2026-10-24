# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: build   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 1
- last_checkpoint: 2026-10-24 16:20

## Next action
Read orchestrate/tasks/core-api/HANDOFF.md (on branch task/core-api), then on user OK: append the 5 review findings (orchestrate/logs/core-api/review.md) to core-api BRIEF.md, commit, set core-api ready, DISPATCH start -Id core-api -Model gpt-6-sol -Effort medium, then DISPATCH review -Id core-api. Meanwhile write briefs for materials + contracts (not dispatched until Gate 3 OK).

## Waiting on user
GATE 4: core-api check PASS but review VERDICT ISSUES (5 findings: listener/facing validation, polygon area in photo-targets, demo fixture sofa position and absorption). Retry now or inspect code first?

## Notes for a fresh session
- Team of 4: iOS (RoomPlan app, LiDAR iPhone + Xcode Mac available), physics engine (teammate, in progress), SerpApi products (teammate, in progress), Neel = backend/integration (FastAPI, Vultr, Caddy, .tech, Gemini, contract, pairing) + planning.
- Orchestrated scope = Neel's area plus the shared JSON contract. Teammates' parts are developed outside this orchestration and plug in via docs/API.md.
- PROJECT_CONTEXT.md is the seed context; sections 5-8 hold the contract, pairing and engine proposals.
