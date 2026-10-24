# TASKS (orchestrator-only)

| id | title | model | effort | deps | wave | status | notes |
|----|-------|-------|--------|------|------|--------|-------|
| core-api | FastAPI app: store, sessions/pairing, rect+demo rooms, units.py (ft/in), room/layout endpoints, engine+products adapters with stubs, own tests per docs/TESTING.md 3.1-3.2 | gpt-6-sol | medium | | 1 | todo | owns backend/app/{main,store,sessions,rooms,engine,products,units}.py, stubs/, tests for them |
| materials | Absorption table, classify_materials (Gemini + mock + bad-response handling), photos+materials router, tests 3.5 | gpt-6-sol | medium | | 1 | todo | owns backend/app/materials.py, materials_router.py, tests |
| contracts | Contract test suite (engine, products, materials) runnable against any implementation + validate_dto tool + recorded fixtures (SerpApi, Gemini good/bad) | gpt-5.6-terra | medium | | 1 | todo | owns backend/tests/contract/**, tools/validate_dto.py, fixtures/serpapi_shopping_sample.json, fixtures/gemini_responses/**; engine/products owners run these |
| roomplan | iOS DTO (meters) -> Room JSON (feet) converter, photo-targets, listener rules, golden tests 3.6 | gpt-6-sol | high | core-api | 2 | todo | owns backend/app/roomplan.py, fixtures/roomplan_sample.json, tests; swap in real iOS sample when it arrives |
| deploy | Dockerfile, compose, Caddyfile, deploy notes, smoke.sh (3.9) | gpt-5.6-terra | medium | core-api | 2 | todo | owns deploy/*, DEPLOY.md |
| integrate | tools/e2e.py, backend/tests/e2e, demo script, failure-drill checklist | gpt-5.6-terra | medium | core-api,materials,roomplan | 3 | todo | owns tools/e2e.py, backend/tests/e2e/**, DEMO.md |

status: todo | ready | running | review | done | blocked | cut

Columns are read by the scripts: keep exactly 8 columns; write a literal pipe as \| ; ids are lowercase-with-dashes; pass tasks to `review` after a wave; mark unwanted tasks `cut`/`blocked` before `merge -All`.
