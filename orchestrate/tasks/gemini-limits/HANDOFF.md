# Gemini limits handoff

## Done
- Added a process-local, thread-safe per-room in-flight registry. Concurrent requests join one classification and receive its result; failures release the entry and propagate to joiners.
- Added a 10-minute, 128-entry photo-hash cache. Cached results reapply material and absorption values to the stored room.
- Added a real-Gemini sliding-window limit (default 6 calls/minute) and concurrency cap (default 2, up to 30 seconds waiting). Rate rejection returns the specified 429 JSON body and `Retry-After` header. Mock, empty-photo, cached, joined, and no-key paths bypass the limiter.
- Added `GET /rooms/{id}/materials/status` with idle/running state, start time, elapsed seconds, and stored photo count.
- Added concurrency, cache, failure, limit, and HTTP status tests. Updated old router assertions for the new `status` field and photo-based cache behavior.

## Verification
- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/test_gemini_limits.py backend/tests/test_materials_router.py -q --basetemp .pytest_tmp`: 9 passed.
- Broader suite with a writable local pytest temp directory and the host-specific WSL bash syntax check excluded: 293 passed, 10 deselected.
- Unmodified full `python -m pytest -q` cannot pass in this Windows sandbox: pytest's default temp directory is access denied, and the deploy syntax test invokes a WSL bash launcher that exits with access denied. The local pytest temp directory was removed after testing.

## Unfinished
- None in task scope.

## Design questions
- A joiner that waits longer than the specified 120-second cap receives HTTP 504. The brief sets the cap but does not specify a status code; HTTP 503 is another possible response.
