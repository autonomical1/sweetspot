# web-deploy handoff

## Completed

- Added a `node:22-alpine` `web-build` stage to `deploy/Dockerfile`. It runs
  `npm ci` and `npm run build` in `webapp/`, then copies the generated `web/`
  files into the final Python image without replacing the committed
  `web/plot2d/` content.
- Expanded `.dockerignore` to exclude Node dependency, Vite cache, and local
  build-output directories.
- Extended `deploy/smoke.sh` to verify `/app/` has Vite's root element, parse
  its hashed JavaScript source, fetch that asset with a JavaScript content type,
  and fetch `/app/models/projector.glb`.
- Documented the production web-app build, rebuild command, and verification in
  `DEPLOY.md`.
- Added static regression tests in `backend/tests/test_web_build_files.py`.

## Verification

- `npm --prefix webapp run build` passed. Vite reported only its existing
  large-chunk warning and emitted ignored output under `web/`.
- `python -m pytest backend/tests/test_web_build_files.py -q` passed (2 tests).
- `python -m ruff check .` passed.
- The existing `backend/tests/test_deploy_files.py` bash-syntax check cannot
  execute in this Windows sandbox: `C:\\WINDOWS\\system32\\bash.EXE` fails to
  create a WSL instance with `E_ACCESSDENIED`. This is environmental, not a
  shell syntax diagnostic. The full pytest invocation likewise did not finish
  reporting before the sandbox runner ended it after showing 39 passing dots.

## Unfinished

- Docker image build and deployed smoke test remain for the orchestrator/VPS as
  requested by the brief.
- Running the local TypeScript build rewrote the unowned
  `webapp/tsconfig.app.tsbuildinfo`; I restored its original content, but the
  patch mechanism changed its final newline, so Git still reports a one-line
  end-of-file-only modification. The harness should restore that unowned file
  before committing this task.

## Design questions

- none
