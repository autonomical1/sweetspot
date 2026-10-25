# engine3d-core handoff

## Completed

- Added `backend/app/engine3d.py` with a pure CLI command builder, a headless subprocess runner, preset validation, temp directory cleanup, timeout handling, and a pure schema 2 mapper. The runner uses `MPLBACKEND=Agg`, a temp directory under `$DATA_DIR/tmp`, and the repository root as the default subprocess working directory.
- Added fast tests for CLI arguments and material presets, both recorded scenes, schema rejection, subprocess success and cleanup, timeout, and exit-code diagnostics. Added an opt-in real engine test marked `slow` and `live`; `pytest.ini` excludes `live` by default, but does not exclude `slow` alone.
- No endpoint, schema, teammate package, or existing adapter files changed.

## Verified axes and materials

The existing adapter maps engine `(u, v)` to backend `(x, z)` as `x=u`, `z=room.length-v`. Schema 2 adds engine up `w`, which maps to backend `y=w`. Therefore the CLI receives `--length=room.width` and `--width=room.length`; backend north `-z` is engine north `+v`. The recorded CLI scenes have engine x spanning 15 ft and engine y spanning 12 ft, so they physically map to a backend room **15 ft wide, 12 ft long**. The brief's requested 12 ft wide, 15 ft long interpretation conflicts with the recorded geometry and the current adapter; the mapper rejects mismatched dimensions rather than distorting placements.

| Backend material | Engine preset |
| --- | --- |
| drywall | drywall |
| glass | glass |
| brick | concrete |
| carpet | carpet |
| hardwood | tile |
| tile | tile |
| curtain | curtain |
| unknown or unmapped | drywall |

Walls use the most common mapped wall preset. Floor and ceiling use their own surface preset, defaulting to drywall when absent.

## Runtime and possible speedups

One profiled real 5.1 CLI run (15 x 12 x 9 ft, `--fast --no-show --no-view3d`) took **125.7 s under cProfile**. Its CLI placement phase reported **12.1 s**; the remaining approximately **113.6 s** covered report/plot work plus profiler overhead. A separate unprofiled end-to-end `run_scene` test for a 12 x 15 x 9 ft backend room took **98.6 s**, under the 150 s timeout. These machines/inputs differ from the brief's 74 s measurement, so use the timeout margin.

Top 10 cumulative functions from cProfile (seconds; inclusive times overlap):

| Function | Cumulative s |
| --- | ---: |
| `optimize._imaging_terms` | 41.73 |
| `optimize._first_order_reflection_gain` | 16.60 |
| `room.validate_polygon` | 14.83 |
| `room_acoustics.level_components` | 10.60 |
| `viewer3d.wall_frame` | 10.50 |
| `optimize._headroom` | 9.67 |
| `optimize._modal_eval` | 9.44 |
| `numpy.roll` | 9.06 |
| `pyroomacoustics.compute_ism_rir` | 7.26 |
| `pyroomacoustics.libroom.rir_builder` | 7.06 |

Three concrete future speedups, requiring teammate coordination before changes: (1) add a CLI flag that stops after writing layout JSON and skips all PNG plots and the 3D view; (2) keep `--fast` and benchmark a coarser wall/height candidate grid in the optimizer; (3) cache or batch repeated polygon validation and first-order reflection/headroom calculations across candidate placements.

## Verification and unfinished work

- `python -m ruff check .` passed.
- Focused fast tests passed (7 tests). Real `slow`/`live` 5.1 test passed (98.57 s).
- A full `python -m pytest -x -q --basetemp .pytest-engine3d-tmp` run reached 161 passes, then failed in **existing** `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax`: `bash` resolved to `C:\WINDOWS\system32\bash.EXE`, whose WSL launcher returned access denied in this sandbox. This file is outside OWNS.txt. Excluding that one environment-dependent test, the full suite passed: **344 passed, 11 deselected** in 7m 16s.
- The follow-up task must widen `schemas.py` to retain optional 3D fields and wire background refinement into endpoints. This task intentionally returns plain dicts.

## Design questions

- The recorded scene dimensions conflict with the brief's requested backend 12 x 15 ft test room. I preserved the existing adapter's unit-scale coordinate mapping and tested recordings against a 15 x 12 ft backend room. Alternatives: replace the recordings with a `--length 12 --width 15` engine run, or revise the brief's dimensions; rescaling or rotating these particular recorded scenes would make their front wall or physical distances wrong.
- The engine has no `hardwood` or `brick` material preset. I mapped hardwood to `tile` and brick to `concrete` as reversible approximations. Alternatives: add new measured presets in the teammate engine or pass explicit absorption coefficients when that CLI supports them.
