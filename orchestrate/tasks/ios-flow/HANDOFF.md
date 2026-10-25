# iOS flow handoff

## Changed
- `SweetspotApp.swift`: replaced active Results navigation with setup and processing views; added base/height preset selection, background classification on leaving photos, guarded classify → optimize → AR build, stage timing, retry of the failed stage, and error return to the form. Demo, rectangle, recent scan, and offline preview routes now open the form.
- `BackendClient.swift`: `optimize(roomID:preset:)` sends `{"options":{"preset":...}}`.
- Updated `03_pairing_and_photos.md` and `README.md` to describe the flow.

## Changed functions and views
- `Flow.leavePhotos`, `Flow.buildLayout`, `Flow.compute(preset:)`, `Flow.retryProcessing`, and `Flow.performClassification` manage the form-to-AR sequence.
- `Flow.open`, `Flow.useDemo`, `Flow.makeRectangle`, and `Flow.startPreview` now open the setup form; `Flow.resetClassification` clears old work when switching rooms.
- `SetupFormView` collects budget and preset; `ProcessingView` shows progress and retry actions; `BackendClient.optimize(roomID:preset:)` sends the selected preset.

## Implementation notes
- The Xcode project enumerates Swift source files explicitly and its project file is outside OWNS.txt. The setup and processing views are in `SweetspotApp.swift` so the owned change remains part of the app target.
- Product loading remains on demand from the AR shopping screen. The processing screen shows only stages that actually run.
- The local preview still uses its existing illustrative layout after the form; it does not call the backend.

## Validation
- `python -m ruff check .`: passed.
- `git diff --check`: passed.
- `python -m pytest -q -x --basetemp .pytest_worker_tmp`: 177 passed, then `backend/tests/test_deploy_files.py::test_smoke_script_has_valid_bash_syntax` failed because this Windows host resolves `bash` to the WSL launcher, which returned access denied before checking the script. The first unrestricted run reached the same failure and was interrupted during later tests. No backend or deploy files are owned by this task.
- `python -m pytest -q --lf -x --basetemp .pytest_worker_tmp`: the one last-failed test cached from the interrupted run passed.
- `python -m pytest -q -k 'not smoke_script_has_valid_bash_syntax' --basetemp .pytest_worker_tmp`: passed the 75% mark with no failures, then made no progress for several minutes and was interrupted. No Python files were changed by this task.
- Swift/iOS SDK cannot be compiled in this Windows workspace. Verified active references to the phase cases, views, and optimize signature by `rg`.

## Manual device test
1. Scan, upload, take at least one photo, tap Finish. Verify the setup form appears immediately and classification starts in the background.
2. Set budget and each supported base/height combination. Verify 2.1 disables and clears height. Tap Build my layout once; verify classification countdown if Gemini returns 429, then placement, then AR.
3. Force classification failure and retry. Force optimize failure (including a server without 2.1 support) and verify server detail, Retry, and Back to form.
4. Repeat with Skip photos, demo room, entered rectangle, recent scan, and offline preview. Verify they all show the form and reach AR without a Results or Compute button.
5. Open Shop this setup from AR and verify the selected budget is used.

## Unfinished
- Compile and run with Xcode/iOS SDK and a LiDAR iPhone; unavailable here.

## Design questions
- none
