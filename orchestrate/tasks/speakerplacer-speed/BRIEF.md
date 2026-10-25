# speakerplacer-speed: make the speakerplacer search several times faster WITHOUT changing its answers

## Why
`backend/app/engine_speakerplacer._optimize` (calls `speakerplacer.optimize_layout`) takes about 38 s for a 15 x 18 ft room and 57-75 s for a 24 x 39 ft scanned room. It is CPU-bound pure Python. It makes the quick layout miss its deadline (QUICK_OPTIMIZE_DEADLINE_S=50) and the same code backs the 3D engine runs that time out on big rooms. Target: large scan room under 25 s, 15 x 18 room under 12 s, identical output.

## Golden check (already in the repo)
`fixtures/speakerplacer_golden.json` holds the CURRENT answers (speaker positions, aims, score_db) for three rooms; `PYTHONPATH=. python tools/golden_speakerplacer.py check` re-runs them, prints the time per room and `IDENTICAL` or the differences (tolerance 1e-6). It must print IDENTICAL at the end. Do not edit the golden file or the tool.

## Profile of the large room (cProfile, 75 s total; cumulative seconds)
- `optimize._evaluate_group` 20.8 s (17,451 calls) -> `_modal_eval` 17.2 s (546 calls; `scoring.modal_response` 7.3 s own time) and `_imaging_terms` 16.7 s (12,606 calls).
- `optimize._headroom` 14.0 s (48,309 calls) -> `room_acoustics.level_components` 11.8 s (216,534 calls) -> `directivity_q` 6.8 s; `speaker_models.response_db` 7.9 s (371,826 calls, 7.5 s own).
- `optimize._wall_box_fits` 10.4 s (6,468 calls) -> `viewer3d.box_pose` 7.7 s.
- `room.validate_polygon` 6.7 s (69,489 calls: the same polygon validated over and over).
- numpy `mean` 6 s (289,414 tiny calls on short arrays).
Ideas (you decide, measure each): memoize `validate_polygon` per polygon bytes; hoist per-candidate invariants out of inner loops; memoize `response_db` / `directivity_q` on rounded-free exact keys (no rounding that changes results); replace tiny `np.mean` calls with plain arithmetic; vectorize `_headroom` over bands; cache `_wall_box_fits` / `box_pose` per (candidate, model); only if still short of target, evaluate candidates in a `concurrent.futures.ProcessPoolExecutor` (4 cores on the server) with a deterministic merge order. Keep results bit-for-bit comparable within 1e-6.

## Constraints
No new dependencies (no network; numpy/scipy are present). No behaviour or API changes; keep function signatures. Do not run the whole pytest suite (slow). Run only: `python -m ruff check .`, `python tools/smoke_tests.py`, the golden check, and `python -m pytest backend/tests/test_engine_speakerplacer.py -q`.

## Done when
Golden check prints IDENTICAL; large_scan < 25 s and rect_15x18 < 12 s on this machine (report the measured times in HANDOFF.md, before and after); ruff and the smoke tests pass.

## Out of scope
Backend adapter, web, iOS, the 3D engine CLI flags.

## Design decisions encoded here
Speed only; answers must not change.

## Files you own
`speakerplacer/*.py`, `orchestrate/tasks/speakerplacer-speed/HANDOFF.md`.
