# Sweet Spot demo runbook

## Before the demo

- Use the live URL `https://sweetspotav.tech` and run `bash deploy/smoke.sh https://sweetspotav.tech`.
- Run `python tools/e2e.py https://sweetspotav.tech` and keep the output as the API health check.
- Warm the server before the audience arrives: load the demo room, run one optimize, then make one products request. The first optimize after a restart takes about 25 s; repeats are instant.
- Put the phone on cellular (or its hotspot), open the laptop browser at `/app/plot2d/`, and have a saved scan ready.
- Confirm `DATA_DIR` is persistent. Products use the real SerpApi catalog: expect specs, feet-based `dimensions`, and `pair_with`; the iPhone budget control and Shop swaps are on branch `ios-phone_context`.

## Demo script (about 5 minutes)

1. (30 s) On the laptop, create a session and show its QR/code.
2. (30 s) Scan the QR on the phone and wait for the pairing page to show ready.
3. (60 s) Scan the room, or use the saved scan if the live scan is slow.
4. (30 s) Photograph the requested surfaces and upload the photos.
5. (45 s) Run optimize and show the six speakers and screen in the 2D plot. The quick layout is valid immediately; the refined 3D result (about 90 s later, presets 5.1 / 7.1 / 7.1.4, real heights, overhead speakers, compliance) is **pending (after engine3d-wire)**.
6. (45 s) Show the AR placement on the phone (the refined 3D AR path is **pending (after engine3d-wire)**; basic AR is **pending** if the build is not available).
7. (30 s) Open the shopping list, adjust the budget, and show a swap alternative. The web shopping panel remains **pending** until the web app is finished.

## Failure drills

| Symptom | What to do | Verify |
|---|---|---|
| Gemini key missing/invalid | Continue; materials fall back to `unknown`. | The materials response contains `surfaces`; continue with the demo. |
| Gemini returns 429 busy | Wait for the returned `Retry-After` time and retry materials; this response has no `surfaces` fallback. Repeated taps join one request, and identical photos are cached. | Retry succeeds, then `python tools/e2e.py https://sweetspotav.tech` passes the materials step. |
| Gemini UI is still waiting | The "Waiting on Gemini" progress UI and disabled buttons are **pending (after ios-phone_context)**; use the saved scan and wait/retry manually. | Confirm the materials response returns `surfaces`. |
| SerpApi quota exhausted | Continue with the products fallback and its warning. | Products still satisfy `total <= budget`. |
| Phone offline | Use the saved scan or load the fixture with `POST /rooms/demo`. | Run the e2e command and confirm scan/demo optimization passes. |
| Backend restarted mid-demo | Re-pair: sessions live in memory; rooms persist. | Create a new session, then fetch the existing room or load demo. |
| Browser refreshed mid-demo | Reopen `/app/plot2d/` and use the room/session from the pairing flow. | Confirm `GET /rooms/{id}` and `GET /rooms/{id}/layout` return data. |
| 3D refinement is slow or fails | Keep showing the quick layout; the refined path is **pending (after engine3d-wire)**. | Quick layout remains valid. |
| Deploy broke | Roll back to `demo-ok` as described in `DEPLOY.md`, then rebuild the stack. | Run both live checks above. |
