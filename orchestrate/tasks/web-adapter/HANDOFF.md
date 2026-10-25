# Web adapter handoff

## Done
- Added a pure `layoutToScene` mapper for backend room, layout, and metrics. It converts feet to meters and centers the room frame, including surfaces, furniture, all speaker roles, screen, projector, seats, patches, and reflection paths.
- Connected the 3D canvas to the existing API room/layout store. The legacy saved scene remains available until an API layout arrives. The backend renderer updates objects by content signature instead of tearing down the canvas for each layout update.
- Added polygon surfaces, role-colored speaker models with box fallback, labels and floor lines, wall-facing screen and patches, aimed projector, selection and highlights, seat POV, and top view. Copied the requested sample/engine fixtures and added Vitest adapter tests.
- Web checks: `npm test` (18 passed), `npm run typecheck` (passed); `python -m ruff check .` passed.

## Unfinished / integration notes
- The existing sidebar and viewport callout still read the saved example config, so backend speaker role details are absent from those panels. Those files are outside this task's ownership; the canvas selection does update the shared `selected` store value.
- No visual browser/WebGL QA was possible in this worker run. The contract mapping and speaker counts were verified in Vitest.
- The full Python suite was interrupted after passing 75% because a later test stalled. A rerun with a writable pytest temp directory and `-x` reached 177 passing tests, then failed in `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax`: Windows `bash.exe` returned access denied. This is unrelated to scene code. The initial Python run also hit permission errors in the default pytest temp directory; a local test temp directory fixed those errors and was removed afterward.

## Design questions
- The viewer has no `showReflections` control or prop. I made the scene show the selected speaker's reflection paths by default and accept an optional `showReflections` prop for all paths. Alternatives: add a viewer/store toggle, or always show all paths.
