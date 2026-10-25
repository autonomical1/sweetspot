# Handoff: domain-rename

## Done

- Updated `DEPLOY.md` active URLs, setup commands, smoke-test commands, domain values, and current deployment notes to use `sweetspotav.tech`.
- Updated the deployment notes for the live configured API keys, `GEMINI_MODEL=gemini-3.8-flash`, and optimize timing (about 25 seconds after restart; repeats instant).
- Kept the `144-202-27-51.sslip.io` fallback in the documented `SITE_ADDRESS` value and the Live domain explanation, including `.env.bak-pre-domain`.
- Updated `.env.example` comments to describe the live domain while preserving `localhost` as both default values.
- Updated the web app context hosting URL.
- `backend/tests/test_deploy_files.py` did not contain an old-host assertion, so it was unchanged.

## Verification

- `python -m ruff check .`: passed.
- `python -m pytest backend/tests/test_deploy_files.py -q`: 6 passed, 1 failed because this Windows environment resolves `bash` to `C:\WINDOWS\system32\bash.EXE`, which returns exit code 1 with an access-denied WSL error for the syntax check.
- Full `python -m pytest -q` was attempted; it produced unrelated errors/failures in the existing suite and then stalled in a long-running test, so it was interrupted after a bounded wait.

## Unfinished

- None within the owned files. The full-suite failures need separate investigation if required.

## Design questions

- none
