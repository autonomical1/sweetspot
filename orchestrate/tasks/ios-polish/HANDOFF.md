# ios-polish handoff

## Completed
- `SetupFormView` now explains the selected 2.1, 5.1, or 7.1 base and the selected height channels, shows a full-number example, and has a short help sheet for the numbering system.
- `ProcessingView` uses provider-neutral photo-analysis wording. `gemini_limits._busy` returns provider-neutral HTTP detail, with assertions updated in `test_gemini_limits.py`. A source scan found no user-visible `Gemini` string; remaining occurrences are internal class names or comments.
- `ARLayoutScreen` passes room width, length, and height, displays tracking state and a relocalization hint, and exposes manual alignment and scan-reset controls. `ARLayoutView.makeUIView`, `updateUIView`, `Coordinator.tapped`, `Coordinator.draw`, and the new tracking delegate callback provide floor rectangle and corner guides, manual alignment with plain corner names even for shared scan sessions, a failed-floor-raycast message, and cached drawing when content and transform are unchanged.
- Removed the `Found` rows from `ReviewScreen` and `ScanHistoryView` while keeping saved scan summaries.

## Verification
- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/test_gemini_limits.py backend/tests/test_materials.py -q --basetemp .pytest-ios-polish`: 23 passed.
- `git diff --check`: passed.
- The first full `python -m pytest -q` run hit a Windows permission error in pytest's default temporary directory. With `--basetemp .pytest-ios-polish`, one full run reported one failure before stalling near 92%; a fail-fast rerun passed through 74% and then the command runner exited with code -1 without a traceback. Full-suite status is therefore unconfirmed. The iOS app could not be compiled on this Windows host.
- The generated, untracked `.pytest-ios-polish/` directory remains. Automatic command approval rejected two attempts to delete that exact directory, including one after its absolute path was verified inside this worktree. The harness should exclude it from its commit or remove it with an authorized cleanup mechanism.

## Manual iOS test script
1. In the setup form, select each base and height option. Confirm the description and example update; open the numbers help sheet.
2. Scan a room, upload a photo, and start processing. Confirm all visible copy says photo analysis and no provider name appears. Check a busy response and retry countdown if available.
3. Open AR from a fresh scan. Confirm the cyan floor outline and four corner posts coincide with the physical walls and corners. If they do not, record how far they are shifted on x/y/z and their rotation relative to the front wall so the room frame can be corrected from evidence.
4. Move the phone quickly or cover its camera; confirm the tracking reason and re-lock hint appear. Slowly view the floor and walls until tracking returns to normal.
5. Tap **Align manually** even with a reused scan session. Tap the floor at the front-left and front-right wall corners. Confirm the outline and markers move into place. Tap away from the floor and confirm the floor-pointing message. Tap **Reset to scan alignment** and confirm the original placement returns.
6. Open the scan review and recent scan detail screens; confirm there is no `Found` field.

## Unfinished
- Device compilation and AR alignment validation require an iPhone/Xcode tester.
- The full Python suite needs a clean run in an environment with a writable pytest temporary directory and enough execution time.

## Design questions
- What color and thickness should the AR room guide use? I used thin cyan boxes (about 1.2 cm) so it is visible and easy to replace; alternatives include a different color, thinner lines, or a translucent floor mesh.
