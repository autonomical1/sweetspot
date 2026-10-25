#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:?usage: deploy/smoke.sh BASE_URL}"
BASE_URL="${BASE_URL%/}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
run_check() {
    local name="$1"; shift; local started ended elapsed
    started="$(date +%s%3N)"
    if "$@"; then
        ended="$(date +%s%3N)"; elapsed=$((ended - started)); printf 'PASS %-42s %sms\n' "$name" "$elapsed"
    else
        ended="$(date +%s%3N)"; elapsed=$((ended - started)); printf 'FAIL %-42s %sms\n' "$name" "$elapsed" >&2; exit 1
    fi
}
json_has() {
    local file="$1"; shift
    python3 - "$file" "$@" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
for expression in sys.argv[2:]:
    value = payload
    for part in expression.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    if value is None or value == "": raise SystemExit(f"missing value: {expression}")
PY
}
health() { curl -fsS --max-time 15 "$BASE_URL/health" -o "$TMP_DIR/health" && json_has "$TMP_DIR/health" ok; }
run_check 'GET /health' health
create_session() { curl -fsS --max-time 15 -X POST "$BASE_URL/sessions" -o "$TMP_DIR/session"; json_has "$TMP_DIR/session" code pair_url; }
run_check 'POST /sessions' create_session
create_demo() { curl -fsS --max-time 15 -X POST "$BASE_URL/rooms/demo" -H 'content-type: application/json' -d '{}' -o "$TMP_DIR/room"; json_has "$TMP_DIR/room" room_id dimensions; }
run_check 'POST /rooms/demo' create_demo
ROOM_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["room_id"])' "$TMP_DIR/room")"
optimize() {
    curl -fsS --max-time 90 -X POST "$BASE_URL/rooms/$ROOM_ID/optimize" -H 'content-type: application/json' -d '{}' -o "$TMP_DIR/layout"
    python3 - "$TMP_DIR/layout" <<'PY'
import json, sys
layout = json.load(open(sys.argv[1], encoding="utf-8"))["layout"]
if layout.get("stage") not in ("quick", "refined"): raise SystemExit("invalid optimization stage")
speakers = layout["speakers"]
if len(speakers) != 6: raise SystemExit(f"expected six speakers, got {len(speakers)}")
PY
}
run_check "POST /rooms/$ROOM_ID/optimize (six speakers)" optimize
get_layout() { curl -fsS --max-time 15 "$BASE_URL/rooms/$ROOM_ID/layout" -o "$TMP_DIR/saved-layout" && json_has "$TMP_DIR/saved-layout" layout metrics; }
run_check "GET /rooms/$ROOM_ID/layout" get_layout
products() {
    curl -fsS --max-time 15 "$BASE_URL/rooms/$ROOM_ID/products?budget=1500" -o "$TMP_DIR/products"
    python3 - "$TMP_DIR/products" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1], encoding="utf-8"))
if payload["total"] > 1500: raise SystemExit(f"total exceeds budget: {payload['total']}")
PY
}
run_check "GET /rooms/$ROOM_ID/products?budget=1500" products
photo_targets() { curl -fsS --max-time 15 "$BASE_URL/rooms/$ROOM_ID/photo-targets" -o "$TMP_DIR/photo-targets" && python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))' "$TMP_DIR/photo-targets"; }
run_check "GET /rooms/$ROOM_ID/photo-targets" photo_targets
vite_app() {
    local asset_path
    curl -fsS --max-time 15 "$BASE_URL/app/" -o "$TMP_DIR/vite-index" || return 1
    asset_path="$(python3 - "$TMP_DIR/vite-index" <<'PY'
import re
import sys

html = open(sys.argv[1], encoding="utf-8").read()
if not re.search(r'<div\s+id=["\']root["\']', html, re.IGNORECASE):
    raise SystemExit("Vite root element not found")
match = re.search(r'<script[^>]+src=["\'](/app/assets/[^"\']+\.js)["\']', html, re.IGNORECASE)
if match is None:
    raise SystemExit("Vite JavaScript asset not found")
print(match.group(1))
PY
)" || return 1
    curl -fsS --max-time 15 -D "$TMP_DIR/vite-asset-headers" -o /dev/null "$BASE_URL$asset_path" \
        && grep -qiE '^content-type:.*(application|text)/(javascript|ecmascript)' "$TMP_DIR/vite-asset-headers"
}
run_check 'GET /app/ (Vite HTML and JavaScript)' vite_app
projector_model() { curl -fsS --max-time 15 "$BASE_URL/app/models/projector.glb" -o /dev/null; }
run_check 'GET /app/models/projector.glb' projector_model
if [[ "$BASE_URL" == https://* ]]; then
    certificate() {
        command -v openssl >/dev/null 2>&1 || return 1
        local host expiry; host="${BASE_URL#https://}"; host="${host%%/*}"
        expiry="$(printf '' | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null | openssl x509 -noout -enddate)" || return 1
        [[ "$expiry" == notAfter=* ]] || return 1
        printf '      %s\n' "$expiry"
    }
    run_check 'TLS certificate expiry' certificate
else
    printf 'SKIP TLS certificate expiry (HTTP URL)\n'
fi
