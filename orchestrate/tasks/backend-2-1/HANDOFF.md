# backend-2-1 handoff

## Done
- Added `2.1` preset validation through `engine3d.PRESETS`. Quick optimization filters the existing 5.1 placement to L, R and LFE and recalculates its metrics for those roles.
- The refined runner uses speakerplacer's `--layout custom --speakers front:2 bass:1`. Its schema-2 mapper identifies the three roles as preset `2.1`.
- The custom engine run needs `--no-display` to place the front pair in the fixture room. The mapper calls speakerplacer's default display planner afterward, returning a screen and projector in the same room frame.
- Added `backend/tests/test_preset_2_1.py` covering the command, schema mapping, endpoint validation and quick role set, positions, budgeted products, matched fronts and a receiver with at least two channels. The existing products picker already builds roles and redistributes shares from the layout, so it required no code change.

## Verification
- `python -m ruff check .`: passed.
- New tests: 2 passed.
- Relevant engine, refinement and products suite excluding three pre-existing strict timing tests: 59 passed.
- Actual headless 2.1 run on `fixtures/room_rect.json`: returned L, R, LFE, a screen and a projector.
- Full `pytest -q -x`: stopped at `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax`; Windows `bash.exe` exits 1 with `E_ACCESSDENIED` before parsing the script. An unrestricted full-suite pass remains unverified.
- With the three catalog timing cases included, two existing `test_seed_demo_complete_and_fast` cases exceeded the 3 second threshold on this Windows host (about 3.9 and 4.2 seconds). Their functional assertions were not reached in that run; the rest of that targeted suite passed.

## Orchestrator notes
- Update `docs/API.md` section 2a to list `2.1` as an accepted preset and state that both quick and refined 2.1 layouts have exactly L, R and LFE. The docs currently list 5.1, 7.1 and 7.1.4 as examples.
- No files outside this task's ownership were edited.

## Design questions
- The custom 2.1 engine run cannot place the front pair with its default solid screen keepout in the fixture room. I used the engine's display planner after speaker placement to keep screen/projector output. An alternative is to change speakerplacer placement or its display collision policy, which is outside this task's ownership; post-placement display could overlap a speaker in some rooms.
