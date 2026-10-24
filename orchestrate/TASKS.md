# TASKS (orchestrator-only)

| id | title | model | effort | deps | wave | status | notes |
|----|-------|-------|--------|------|------|--------|-------|
| core-api | FastAPI app: store, sessions/pairing, rect+demo rooms, room/layout endpoints, engine+products adapters with stubs | gpt-6-sol | medium | | 1 | todo | owns backend/app/{main,store,sessions,rooms,engine,products}.py, stubs/, tests |
| materials | Absorption table, classify_materials (Gemini + mock), photos+materials endpoints router | gpt-6-sol | medium | | 1 | todo | owns backend/app/materials.py, materials_router.py, tests |
| roomplan | RoomPlan CapturedRoom -> Room JSON converter + sample fixture + POST /rooms capture path | gpt-6-sol | high | core-api | 2 | todo | owns backend/app/roomplan.py, fixtures/roomplan_sample.json, tests; needs iOS sample export |
| deploy | Dockerfile, compose, Caddyfile, deploy README, smoke script | gpt-5.6-terra | medium | core-api | 2 | todo | owns deploy/*, DEPLOY.md |
| integrate | End-to-end test: pair -> upload -> optimize -> products -> materials; demo script | gpt-5.6-terra | medium | core-api,materials,roomplan | 3 | todo | owns backend/tests/e2e, DEMO.md |

status: todo | ready | running | review | done | blocked | cut

Columns are read by the scripts: keep exactly 8 columns; write a literal pipe as \| ; ids are lowercase-with-dashes; pass tasks to `review` after a wave; mark unwanted tasks `cut`/`blocked` before `merge -All`.
