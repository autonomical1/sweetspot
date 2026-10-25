# Sweet Spot demo runbook

## Before the demo

- Confirm the server is up and run `bash deploy/smoke.sh <url>`.
- Run `python tools/e2e.py <url>` and keep the output as the API health check.
- Put the phone on cellular (or its hotspot), open the laptop browser at `/app/plot2d/`, and have a saved scan ready.
- Confirm `DATA_DIR` is persistent and the server has the mock providers available. The web app shopping panel and real product catalog are **pending** until those teammates finish.

## Demo script (about 5 minutes)

1. (30 s) On the laptop, create a session and show its QR/code.
2. (30 s) Scan the QR on the phone and wait for the pairing page to show ready.
3. (60 s) Scan the room, or use the saved scan if the live scan is slow.
4. (30 s) Photograph the requested surfaces and upload the photos.
5. (45 s) Run optimize and show the six speakers and screen in the 2D plot (the unfinished web viewer/AR presentation is **pending**).
6. (45 s) Show the AR placement on the phone (AR integration is **pending** if the build is not available).
7. (30 s) Open the shopping list; live products are **pending**, so the stub list is the expected fallback.

## Failure drills

| Symptom | What to do | Verify |
|---|---|---|
| Gemini key missing or invalid | Leave the mock/unknown material provider enabled; continue with the saved scan. | `python tools/e2e.py <url>` passes the materials step and returns `surfaces`. |
| SerpApi quota exhausted | Use the products stub and continue the layout demo. | The products step passes with `total <= budget` and a warning is acceptable. |
| Wi-Fi is off | Put the phone on its hotspot/cellular network and retry pairing. | Scan the QR again and confirm the session becomes `ready`. |
| Live scan fails | Use the saved scan, or load the fixture with `POST /rooms/demo`. | Run `python tools/e2e.py <url>` and confirm scan/demo optimization passes. |
| Backend restarted mid-demo | Re-pair: sessions are in memory; rooms persist in `/data`. | Create a new session, then fetch the existing room or load demo. |
| Browser refreshed mid-demo | Reopen `/app/plot2d/` and use the room/session shown by the pairing flow. | Confirm `GET /rooms/{id}` and `GET /rooms/{id}/layout` return data. |
| Deploy broke | Roll back to `demo-ok` as described in `DEPLOY.md`, then rebuild the stack. | Run `bash deploy/smoke.sh <url>` followed by the e2e command. |
