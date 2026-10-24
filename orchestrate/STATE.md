# STATE (orchestrator-only; REWRITE IN FULL at every checkpoint, keep only currently-true facts)

- project: Sweetspot
- started: 2026-10-24 13:21
- deadline: 2026-10-25 11:30
- phase: spec   # discover | spec | plan | build | integrate | polish | done
- gates: all        # all | key | minimal
- design: high      # high | normal (high = user decides every design fork)
- wave: 0
- last_checkpoint: 2026-10-24 13:50

## Next action
Await user answers on REST-only (recommended), Gemini API vs CLI (recommend API behind classify_materials interface), SerpApi open question; then draft docs/API.md (rectangular-first room contract, engine optimize/score, products.get_products), AGENTS.md, config.json test cmd, TASKS.md, and hit GATE 2.

## Waiting on user
GATE 1 + forks: approve SPEC; confirm REST-only, Gemini API vs CLI, and what the SerpApi question is.

## Notes for a fresh session
- Team of 4: iOS (RoomPlan app, LiDAR iPhone + Xcode Mac available), physics engine (teammate, in progress), SerpApi products (teammate, in progress), Neel = backend/integration (FastAPI, Vultr, Caddy, .tech, Gemini, contract, pairing) + planning.
- Orchestrated scope = Neel's area plus the shared JSON contract. Teammates' parts are developed outside this orchestration and plug in via docs/API.md.
- PROJECT_CONTEXT.md is the seed context; sections 5-8 hold the contract, pairing and engine proposals.
