# 3D engine integration audit (started 2026-10-24 23:35)

The teammate's `speakerplacer` branch is merged into master (3D heights, presets 5.1 to 9.1.6, real centre model, compliance, receiver delay/trim, screen/projector estimate, room materials). It changes assumptions across the whole project. Contract: `docs/API.md` section 2a. Facts: a full engine run takes about 74 s (5.1) to 94 s (7.1.4) headless with `--fast`, so results are STAGED: a quick result immediately, a refined 3D result in the background.

Status: `todo` / `running` / `done` / `n/a`. Owner: the task or person.

## Backend
| # | Where | What must change | Status / owner |
|---|---|---|---|
| 1 | `backend/app/engine3d.py` (new) | run the CLI headless, map schema-2 JSON to our layout (roles, feet, our frame, extras) | running: engine3d-core |
| 2 | `backend/app/engine_speakerplacer.py`, `engine.py` | keep as the QUICK path; add the refined path: preset/standard options, background job, one-at-a-time queue, cache per (room, listener, preset, standard, materials), failure fallback to quick result | todo: engine3d-wire |
| 3 | `backend/app/schemas.py` `Role = Literal[L R C LFE Ls Rs]` | widen to `Lss Rss Lrs Rrs Ltf Rtf Ltr Rtr Ltm Rtm LFE2`; Layout/speaker optional extras; `stage`, `preset` | todo: engine3d-wire |
| 4 | `backend/app/rooms.py`, `main.py` routes | `POST optimize` options `{preset, standard}`, `GET optimize/status`, `GET layout` returns `stage`; refined result replaces quick one | todo: engine3d-wire |
| 5 | `backend/app/acoustics.py` (`/score`, drag) | ITU target table only knows L R C Ls Rs LFE; must handle extra roles and 3D positions without errors; stays fast | todo: engine3d-wire |
| 6 | `backend/app/stubs/engine_stub.py` | fallback keeps six roles; accept `preset` option and return it | todo: engine3d-wire |
| 7 | `backend/app/store.py` | persist layout `stage`, job state and the refined result cache | todo: engine3d-wire |
| 8 | materials -> engine materials | map our surface materials to the engine's presets (`--materials`) | running: engine3d-core |
| 9 | `products/*` (recommender) | roles for Lss/Rss/Lrs/Rrs/Ltf/Rtf/Ltr/Rtr/LFE2: category mapping, pairs (Lss+Rss, Lrs+Rrs, Ltf+Rtf, Ltr+Rtr), shares, overhead speakers (in-ceiling/Atmos) listings, `PRODUCT_ROLES` | paused: products-theater (add roles after engine3d-wire) |
| 10 | `backend/tests/contract/checks.py` `ROLES`, `full_51`, `PRODUCT_ROLES`, `test_engine_contract.py` | accept the new roles and optional fields; keep 5.1 strict | todo: engine3d-wire |
| 11 | e2e `tools/e2e.py`, `backend/tests/e2e` | exactly six roles assumption; add staged flow (quick then wait for refined with a time cap), preset 7.1.4 case | todo |
| 12 | `deploy/smoke.sh` | `len(speakers) != 6`, `--max-time 60`; add status/refined check with long cap | todo |
| 13 | Deploy / capacity | engine runs 75-95 s of CPU: check VPS cores/RAM, run ONE job at a time, temp dir cleanup, no `output/` in image (done), timeouts, engine failure must not take the API down | todo (orchestrator) |
| 14 | `fixtures/engine/*.json` | recorded engine outputs for tests (added) | done |
| 15 | Polygon rooms | engine supports `--room-polygon-json`, but modal scoring needs a 4-corner room; polygon work stays PAUSED until the engine is wired | paused |

## Clients
| # | Where | What must change | Status / owner |
|---|---|---|---|
| 16 | `web/plot2d` | draw the new roles and heights, show `stage` (quick/refining/refined) and a preset selector, projector, compliance table | todo |
| 17 | `Sweetspot_iOS_App` (branch `ios-phone_context`) | shop roles list (`CaptureViews.swift` has the six + screen/projector), AR boxes should use engine `size` when no product dimensions, poll for `refined`, optional preset picker, decode extra fields, longer timeouts | todo |
| 18 | `webapp_context/*.md` (web teammate spec) | `03_data_and_coordinates.md` lists six roles; `04_3d_view.md` hard-codes box sizes (use `size`); `01` role colours; `02_api_reference.md` needs stage/status and presets | todo |
| 19 | docs | `SPEC.md`, `TESTING.md`, `DEPLOY.md`, `PROJECT_CONTEXT.md`, `DEMO.md` (six speakers wording and timings), root `README.md` (stub) | todo |

## Teammate asks (engine owner)
1. Expose a programmatic entry point (a `run_scene(config) -> dict` that returns the schema-2 dict) so the backend need not spawn a CLI process.
2. A switch to skip plot/PNG output (about 10 s of each run) and a faster mode for interactive use.
3. Confirm polygon-room support and modal scoring for non-rectangular rooms (needed by the paused polygon work).
4. Confirm the channel naming (`Lss/Rss/Lrs/Rrs/Ltf/...`) is final.
