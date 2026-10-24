# Engine adapter handoff

## Status

Completed retry-1 review fixes:

- Engine optimizer failures now return `engine_stub.optimize(room)["layout"]`, with acoustics metrics and the required failure warning. `_safe_fallback_layout` is used only if the stub itself raises.
- Object avoidance preserves the original wall line and slides only along it, respects a 0.5 ft end margin, and warns when no legal along-wall position exists.
- Treatment patches are emitted only for wall and window reflections.
- Sabine absorption area replaces covered wall area with window/door/opening area, avoiding double counting.
- Added regression tests for each behavior.

## Verification

- `python -m pytest backend/tests/test_acoustics.py backend/tests/test_engine_speakerplacer.py -q` — 8 passed.
- `python -m pytest backend/tests/contract/test_engine_contract.py -q` — completed with the expected xfail.
- `python -m pytest -q` — 222 passed, 1 failed, 24 errors, 1 xfailed. The 24 errors are sandbox `PermissionError` failures while pytest tries to scan `C:\Users\neelm\AppData\Local\Temp\pytest-of-neelm`. The one failure is the existing real-engine near-west-wall degenerate-room contract test: it expects the previous angle-safe fallback, whereas this retry brief explicitly requires the stub layout when speakerplacer raises. No out-of-scope files were edited to resolve that conflict.

## Design questions

- none
