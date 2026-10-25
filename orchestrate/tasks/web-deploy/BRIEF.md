# web-deploy: build and serve the web app in production

## Goal
The server builds `webapp/` and serves it at `https://sweetspotav.tech/app/` next to `/app/plot2d/`, via a Docker multi-stage build (user decision 2026-10-25), with smoke checks.

## Design decisions encoded
- **Multi-stage Dockerfile**: a Node stage runs `npm ci` and `npm run build` in `webapp/` (outDir `../web`, `emptyOutDir: false`, base `/app/`); the final Python stage copies the built files into `web/` next to the committed `web/plot2d/`. Build output is not committed (`.gitignore` already lists it).
- The backend already mounts `web/` at `/app` with `html=True` (backend/app/main.py). Do not change backend code; if a route is needed (for example query-string pages need none), say so in HANDOFF.md.
- Root `/` keeps redirecting to `/app/plot2d/` until the user says otherwise (Caddyfile unchanged unless you find the redirect conflicts; report instead of changing).
- Pin Node (use `node:22-alpine` or the current LTS you can confirm in `webapp/package.json` engines or the lockfile) and use a `.dockerignore` so `node_modules` and `dist` never enter the context.
- Keep the final image small; the build stage is discarded.

## Deliverables
1. Update `Dockerfile` (and `deploy/docker-compose.yml` only if needed), `.dockerignore`.
2. `deploy/smoke.sh`: add checks `GET /app/` returns HTML containing the Vite root element and `GET /app/assets/*.js` (parse the script src from the HTML) returns 200 with a JavaScript content type, plus `GET /app/models/projector.glb` 200.
3. `DEPLOY.md`: a short section "Web app build" (what is built, where it lands, how to rebuild locally with `docker compose ... build`, how to verify).
4. Python tests where possible without Docker: `backend/tests/` check that `smoke.sh` parses (the existing syntax test must keep passing or skip), and that the `Dockerfile` has both stages (string-level test).

## Done when
`python -m ruff check . && python -m pytest -q` pass. Actual image build and deploy are done by the orchestrator on the VPS afterwards.

## Out of scope
Any `webapp/src` change, backend code, Caddy certificates/domains.

## Files you own
`Dockerfile`, `.dockerignore`, `deploy/**`, `DEPLOY.md`, and a new `backend/tests/test_web_build_files.py`.
