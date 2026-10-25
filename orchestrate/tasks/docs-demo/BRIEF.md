# docs-demo: refresh DEMO.md for what is built (docs only, small)

## Goal
DEMO.md (30 lines) is the demo runbook. It predates several changes. Bring it up to date, keeping it short and practical. Docs only: no code, no other files.

## Read first
DEMO.md, docs/API.md (sections 2a, 4, 6: staged quick/refined 3D layouts, products, Gemini limits, materials status), DEPLOY.md (the "Live domain" section at the end), docs/ENGINE_INTEGRATION_AUDIT.md (which engine parts are built vs planned), tools/e2e.py and deploy/smoke.sh (what they check).

## Facts to reflect (all true today unless marked PLANNED)
- The live URL is https://sweetspotav.tech (the old sslip.io host is only a fallback). Run the checks against it: `bash deploy/smoke.sh https://sweetspotav.tech` and `python tools/e2e.py https://sweetspotav.tech`.
- Warm-up: the first `optimize` after a server restart takes about 25 s (cold start); repeats are instant. Before the demo run one optimize and one products request on the demo room.
- Products come from the real SerpApi catalog (not the stub): items have specs, `dimensions` (feet), and pairs (`pair_with`). The iPhone app has a budget control and a Shop screen with swap alternatives (on branch `ios-phone_context`).
- Gemini photo classification is rate limited and de-duplicated on the server: repeated taps join one request, identical photos are cached, and a busy Gemini returns 429 with a retry time. PLANNED in the app (landing on `ios-phone_context`): a "Waiting on Gemini" progress UI and disabled buttons.
- PLANNED (task engine3d-wire): the layout is staged: a quick result immediately (`stage: quick`), then a refined 3D result about 90 s later (`stage: refined`, presets 5.1 / 7.1 / 7.1.4, real heights, overhead speakers, compliance). Mark every step that depends on this as "(after engine3d-wire)".
- Failure drills to keep or add: Gemini key missing/invalid or 429 busy (materials fall back to `unknown`), SerpApi quota exhausted (products fall back), phone offline (saved scan / demo room), server restarted mid-demo (pairing sessions live in memory: re-pair; rooms persist), browser refresh mid-demo, deploy broke (rollback to the `demo-ok` tag per DEPLOY.md), 3D refinement fails or is slow (the quick layout stays valid; PLANNED).
- Keep the original structure (pre-demo checklist, timed script, failure drills) and the "pending" markers for things that depend on the unfinished web app. Do not invent features.

## Deliverables / done when
DEMO.md updated; HANDOFF.md lists what changed and anything you could not verify. `python -m ruff check . && python -m pytest -q` still passes (no code changes). No edits outside OWNS.txt.

## Out of scope
Everything else.
