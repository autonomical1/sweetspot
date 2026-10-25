"""
main.py - Fetch Google Shopping listings through SerpAPI and store them in SQLite,
with a component category and parsed specs for every listing.

Setup:
    pip install requests python-dotenv
    echo "SERPAPI_KEY=your_key" > .env      # see .env.example
    echo "GEMINI_API_KEY=your_key" >> .env  # only used by price.py's auto-expand (optional
                                            # GEMINI_MODEL, default gemini-2.5-flash)

Usage:
    python main.py                       # fetch everything in TRACKED
    python main.py --only projector      # fetch one category
    python main.py --dry-run             # list the queries without calling the API
    python main.py --resume              # after a partial run, only fetch what's missing
    python main.py --reparse             # re-run category + spec parsing on stored
                                         # listings (no API credits used)
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()  # reads SERPAPI_KEY (and optional AV_DB) from a .env file

DB_PATH = os.environ.get("AV_DB", "av_prices.db")
LOCATION = "Austin, Texas, United States"

# ---------------------------------------------------------------------------
# 1. What to track: (search query, intended category)
# ---------------------------------------------------------------------------
TRACKED = [
    # --- Projectors (7) ---
    ("Epson Home Cinema LS11000 4K laser projector", "projector"),
    ("Epson Home Cinema 5050UB 4K projector", "projector"),
    ("Epson Home Cinema 2350 4K projector", "projector"),
    ("Hisense C2 Ultra 4K ultra short throw laser projector", "projector"),
    ("XGIMI Titan 4K projector", "projector"),
    ("Sony VPL-XW5000ES 4K laser projector", "projector"),
    ("BenQ TK700STi 4K gaming projector", "projector"),
    # --- Projection screens (4) ---
    ("Elite Screens 120 inch 16:9 motorized projector screen", "projection_screen"),
    ("Elite Screens Aeon 100 inch fixed frame ALR projector screen", "projection_screen"),
    ("Silver Ticket 120 inch 16:9 fixed frame projector screen", "projection_screen"),
    ("Elite Screens Yard Master 2 100 inch outdoor projector screen", "projection_screen"),
    # --- Displays / TVs (5) ---
    ("LG C5 65 inch OLED evo TV", "display"),
    ("Samsung S90F 65 inch OLED TV", "display"),
    ("Hisense U8 65 inch Mini-LED TV", "display"),
    ("TCL QM8 65 inch Mini-LED TV", "display"),
    ("Sony Bravia 8 II 65 inch OLED TV", "display"),
    # --- Speakers (4) ---
    ("Sonos Era 100 smart speaker", "speaker"),
    ("Klipsch Reference R-51M bookshelf speakers", "speaker"),
    ("Polk Audio Signature Elite ES20 bookshelf speaker", "speaker"),
    ("Klipsch Reference R-800F floorstanding speaker", "speaker"),
    # --- Soundbars (4) ---
    ("Sonos Arc Ultra soundbar", "soundbar"),
    ("Sonos Beam Gen 2 soundbar", "soundbar"),
    ("Samsung HW-Q990F soundbar", "soundbar"),
    ("Bose Smart Ultra Soundbar", "soundbar"),
    # --- Subwoofers (3) ---
    ("SVS SB-1000 Pro subwoofer", "subwoofer"),
    ("Klipsch R-120SW subwoofer", "subwoofer"),
    ("Sonos Sub Mini subwoofer", "subwoofer"),
    # --- AV receivers (3) ---
    ("Denon AVR-S760H AV receiver", "av_receiver"),
    ("Denon AVR-X3800H AV receiver", "av_receiver"),
    ("Yamaha RX-V6A AV receiver", "av_receiver"),
    # --- Amplifier (1) ---
    ("Yamaha A-S301 integrated amplifier", "amplifier"),
    # --- Microphones (2) ---
    ("Shure MV7+ podcast microphone", "microphone"),
    ("Rode Wireless GO II microphone system", "microphone"),
    # --- Media streamers (2) ---
    ("Roku Ultra streaming player", "media_streamer"),
    ("Apple TV 4K streaming player", "media_streamer"),
    # --- Mounts (2) ---
    ("Chief RSAUB universal projector ceiling mount", "mount"),
    ("Sanus VMPL50A-B2 full motion TV wall mount", "mount"),
    # --- Cables (2) ---
    ("Belkin Ultra High Speed HDMI 2.1 cable 6 ft", "cable"),
    ("Monoprice 8K HDMI cable 10 ft", "cable"),
    # --- Switchers (1) ---
    ("OREI 4K HDMI matrix switch 4x2", "switcher"),
]

# ---------------------------------------------------------------------------
# 2. Category detection from the listing title.
#    Order matters: the first match wins, so specific/accessory patterns come first.
#    If the detected category differs from the intended one, the listing is flagged
#    (category_ok = 0) so accessories like lamps and mounts don't pollute price results.
# ---------------------------------------------------------------------------
CLASSIFY = [
    ("accessory", r"\b(replacement|lamp|bulb|remote control|carrying case|dust cover)\b"),
    ("mount", r"\b(mount|bracket)s?\b"),
    ("switcher", r"\b(hdmi )?(switch|splitter|extender|matrix)\b"),
    ("cable", r"\b(cable|cord)s?\b"),
    ("projection_screen", r"\bprojector screens?\b|\bprojection screens?\b"
                          r"|\b(motorized|electric|pull[- ]down|fixed[- ]frame|tripod) screens?\b"),
    ("projector", r"\bprojectors?\b"),
    ("soundbar", r"\bsound ?bars?\b"),
    ("subwoofer", r"\bsub-?woofers?\b"),
    ("av_receiver", r"\breceivers?\b"),
    ("amplifier", r"\bamplifiers?\b|\bamp\b"),
    ("media_streamer", r"\b(roku (ultra|express|streaming)|chromecast|fire tv stick|apple tv 4k"
                       r"|streaming (player|stick|device))\b"),
    ("speaker", r"\bspeakers?\b|\bbookshelf\b|\bfloorstanding\b"),
    ("microphone", r"\bmic(rophone)?s?\b"),
    ("display", r"\b(tv|television|oled|qled|monitor|display)\b"),
]


def classify(title):
    for category, pattern in CLASSIFY:
        if re.search(pattern, title, re.I):
            return category
    return None


# ---------------------------------------------------------------------------
# 3. Spec extraction rules.
#    Each rule produces (value_num, value_text, unit) stored under a spec name.
#    N = number, C = first matching choice, F = yes/no flag, T = captured text.
#    To track a new spec, add a rule to RULES below, then run:  python main.py --reparse
# ---------------------------------------------------------------------------
def N(name, pattern, unit=None, scale=1.0):
    return {"kind": "num", "name": name, "pattern": pattern, "unit": unit, "scale": scale}


def C(name, *choices):  # choices: (label, regex[, number])
    return {"kind": "choice", "name": name, "choices": choices}


def F(name, pattern):
    return {"kind": "flag", "name": name, "pattern": pattern}


def T(name, pattern):
    return {"kind": "text", "name": name, "pattern": pattern}


CHANNELS = {"kind": "channels"}
CHANNEL_PATTERNS = [
    r"\b(\d\.\d\.\d)\b",                                    # 5.1.2
    r"\b(\d\.\d(?:\.\d)?)\s*[- ]?(?:ch\b|channel)",         # 5.1 channel
    r"\b([2-9]\.[0-2])\s*(?:surround|soundbar|home theater|speaker system)",
]

BRANDS = ["Epson", "BenQ", "Optoma", "ViewSonic", "LG", "Samsung", "Sony", "Hisense", "TCL",
          "JVC", "XGIMI", "Anker", "Elite Screens", "Silver Ticket", "Sonos", "Bose", "Klipsch",
          "JBL", "Polk", "SVS", "Yamaha", "Denon", "Marantz", "Onkyo", "Pioneer", "Shure",
          "Rode", "Roku", "Chief", "Peerless-AV", "Monoprice", "Vizio", "Panasonic", "Samson"]

RES = C("resolution",  # value_num = vertical pixels, so ranges like 1080.. work
        ("8k", r"\b8k\b|4320p", 4320),
        ("4k", r"\b4k\b|2160p|\buhd\b|ultra hd", 2160),
        ("1440p", r"1440p|\bqhd\b|wqhd", 1440),
        ("wuxga", r"wuxga|1920\s*x\s*1200", 1200),
        ("1080p", r"1080p|full hd|\bfhd\b|1920\s*x\s*1080", 1080),
        ("wxga", r"wxga|1280\s*x\s*800", 800),
        ("720p", r"720p|hd ready|1280\s*x\s*720", 720))

DIAG = N("diagonal_in", r'\b(\d{2,3}(?:\.\d)?)\s*(?:"|”|-?\s?in(?:ch(?:es)?)?\b)', "in")
POWER = N("power_w", r"(\d[\d,]*)\s*(?:w|watts?)\b", "W")
ATMOS = F("dolby_atmos", r"dolby atmos")
BT = F("bluetooth", r"bluetooth")
WIFI = F("wifi", r"wi-?fi")

COMMON = [
    C("brand", *[(b.lower(), rf"\b{re.escape(b)}\b") for b in BRANDS]),
    C("condition",
      ("refurbished", r"refurb|renewed|reconditioned"),
      ("open_box", r"open[- ]box"),
      ("used", r"\bpre-?owned\b|\bused\b(?! with| for| in| to)"),
      ("new", r".")),  # default when nothing else matches
    T("hdmi_version", r"hdmi\s*(2\.1|2\.0|1\.4)"),
]

RULES = {
    "projector": [
        N("brightness_lumens", r"(\d[\d,]*)\s*(?:ansi\s*)?(?:lumens?|lm)\b", "lm"),
        RES,
        C("light_source", ("laser", r"\blaser\b"), ("led", r"\bled\b"), ("lamp", r"\blamp\b")),
        C("throw", ("ultra_short", r"ultra[- ]short|\bust\b"), ("short", r"short[- ]throw")),
        F("smart", r"\bsmart\b|android tv|google tv"),
        F("hdr", r"\bhdr"),
    ],
    "projection_screen": [
        DIAG,
        T("aspect_ratio", r"\b(16:9|16:10|4:3|2\.35:1|21:9)\b"),
        C("screen_type", ("motorized", r"motori[sz]ed|electric"),
          ("pull_down", r"pull[- ]down|manual"), ("tab_tensioned", r"tab[- ]tension"),
          ("portable", r"portable|tripod"), ("fixed_frame", r"fixed[- ]frame|frame")),
        F("ambient_light_rejecting", r"\balr\b|\bclr\b|ambient light rejecting|ceiling light rejecting"),
        N("gain", r"\bgain\s*(?:of\s*)?(\d\.\d+|\d)\b"),
        F("supports_4k", r"\b4k\b|\b8k\b|\buhd\b"),
    ],
    "display": [
        DIAG, RES,
        C("panel", ("oled", r"\boled\b"), ("mini_led", r"mini[- ]?led"),
          ("qled", r"\bqled\b|\bqd[- ]led\b"), ("led", r"\bled\b"), ("lcd", r"\blcd\b")),
        N("refresh_hz", r"(\d{2,3})\s*hz", "Hz"),
        F("hdr", r"\bhdr|dolby vision"),
        F("smart", r"\bsmart\b"),
    ],
    "speaker": [
        POWER, CHANNELS, ATMOS, BT, WIFI, F("airplay", r"airplay"),
        C("form_factor", ("floorstanding", r"floor[- ]?standing|tower"), ("bookshelf", r"bookshelf"),
          ("in_wall", r"in[- ]wall|in[- ]ceiling"), ("outdoor", r"outdoor|weather"),
          ("portable", r"portable")),
        N("impedance_ohm", r"(\d+)\s*(?:ohms?|Ω)", "ohm"),
    ],
    "soundbar": [POWER, CHANNELS, ATMOS, BT, WIFI, F("hdmi_arc", r"\be?arc\b"),
                 F("includes_subwoofer", r"sub-?woofer")],
    "subwoofer": [
        POWER,
        N("driver_in", r'\b(\d{1,2}(?:\.\d)?)\s*(?:"|”|-?\s?in(?:ch(?:es)?)?\b)', "in"),
        F("wireless", r"wireless|wi-?fi|bluetooth"),
    ],
    "av_receiver": [CHANNELS, POWER, ATMOS, BT, WIFI, F("supports_8k", r"\b8k\b"),
                    N("hdmi_inputs", r"(\d+)\s*hdmi\s*in(?:put)?s?")],
    "amplifier": [POWER, BT, WIFI, N("zones", r"(\d)\s*zones?")],
    "microphone": [
        C("mic_type", ("lavalier", r"lavalier|lapel"), ("gooseneck", r"gooseneck"),
          ("condenser", r"condenser"), ("dynamic", r"dynamic"), ("wireless", r"wireless")),
        C("connection", ("usb", r"\busb\b"), ("xlr", r"\bxlr\b"), ("wireless", r"wireless")),
    ],
    "media_streamer": [RES, F("dolby_vision", r"dolby vision"), ATMOS, WIFI],
    "mount": [
        N("weight_capacity_lbs", r"(\d[\d,]*)\s*(?:lbs?\b|pounds?)", "lb"),
        C("mount_type", ("ceiling", r"ceiling"), ("wall", r"wall"), ("tabletop", r"table|desk"),
          ("floor", r"floor")),
        F("tilting", r"\btilt"), F("articulating", r"articulating|full[- ]motion"),
    ],
    "cable": [
        N("length_ft", r"(\d+(?:\.\d+)?)\s*(?:ft\b|feet\b|foot\b|')", "ft"),
        F("supports_8k", r"\b8k\b"), F("has_ethernet", r"ethernet"),
    ],
    "switcher": [T("io_config", r"\b(\d{1,2}\s?x\s?\d{1,2})\b"), RES],
}


def extract_specs(category, text):
    """Return {spec_name: (value_num, value_text, unit)} parsed from listing text."""
    specs = {}
    for rule in COMMON + RULES.get(category, []):
        kind = rule["kind"]
        if kind == "num":
            m = re.search(rule["pattern"], text, re.I)
            if m:
                value = float(m.group(1).replace(",", "")) * rule["scale"]
                specs[rule["name"]] = (value, None, rule["unit"])
        elif kind == "choice":
            for choice in rule["choices"]:
                if re.search(choice[1], text, re.I):
                    number = choice[2] if len(choice) > 2 else None
                    specs[rule["name"]] = (number, choice[0], None)
                    break
        elif kind == "flag":
            if re.search(rule["pattern"], text, re.I):
                specs[rule["name"]] = (1.0, "yes", None)
        elif kind == "text":
            m = re.search(rule["pattern"], text, re.I)
            if m:
                specs[rule["name"]] = (None, re.sub(r"\s+", "", m.group(1).lower()), None)
        elif kind == "channels":
            for pattern in CHANNEL_PATTERNS:
                m = re.search(pattern, text, re.I)
                if m:
                    label = m.group(1)
                    specs["channels"] = (None, label, None)
                    specs["channel_count"] = (float(sum(int(x) for x in label.split("."))), None, None)
                    break
    return specs


# ---------------------------------------------------------------------------
# 4. Database
# ---------------------------------------------------------------------------
def init_db(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            category TEXT,            -- intended category from TRACKED
            detected_category TEXT,   -- category guessed from the title
            category_ok INTEGER,      -- 1 if the title is consistent with the intended category
            title TEXT,
            seller TEXT,
            price REAL,
            price_text TEXT,
            link TEXT,
            product_id TEXT,
            snippet TEXT,
            extensions TEXT,          -- JSON list of extra tags from the listing
            rating REAL,
            reviews INTEGER,
            delivery TEXT,
            fetched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS specs (
            listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            value_num REAL,
            value_text TEXT,
            unit TEXT,
            PRIMARY KEY (listing_id, name)
        );
        CREATE INDEX IF NOT EXISTS idx_listings_cat_price ON listings(category, price);
        CREATE INDEX IF NOT EXISTS idx_listings_query_time ON listings(query, fetched_at);
        CREATE INDEX IF NOT EXISTS idx_specs_name_num ON specs(name, value_num);
    """)
    return conn


def build_text(title, snippet, extensions):
    return " ".join([title or "", snippet or "", *map(str, extensions or [])])


def store_specs(conn, listing_id, category, text):
    rows = [(listing_id, name, num, txt, unit)
            for name, (num, txt, unit) in extract_specs(category, text).items()]
    conn.executemany(
        "INSERT OR REPLACE INTO specs (listing_id, name, value_num, value_text, unit) "
        "VALUES (?, ?, ?, ?, ?)", rows)


def fetch_listings(query, api_key):
    params = {
        "engine": "google_shopping",
        "q": query,
        "location": LOCATION,
        "gl": "us",
        "hl": "en",
        "api_key": api_key,
    }
    r = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("shopping_results", [])


def save_listings(conn, query, category, listings):
    fetched_at = datetime.now(timezone.utc).isoformat()  # one timestamp per query per run
    saved = flagged = 0
    for item in listings:
        price = item.get("extracted_price")
        if price is None:
            continue
        title = item.get("title") or ""
        snippet = item.get("snippet") or ""
        extensions = item.get("extensions") or []
        detected = classify(title)
        ok = 1 if detected in (None, category) else 0
        cur = conn.execute(
            """INSERT INTO listings (query, category, detected_category, category_ok, title, seller,
                   price, price_text, link, product_id, snippet, extensions, rating, reviews,
                   delivery, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (query, category, detected, ok, title, item.get("source"), price, item.get("price"),
             item.get("product_link") or item.get("link"), item.get("product_id"), snippet,
             json.dumps(extensions), item.get("rating"), item.get("reviews"),
             item.get("delivery"), fetched_at))
        store_specs(conn, cur.lastrowid, category, build_text(title, snippet, extensions))
        saved += 1
        flagged += 0 if ok else 1
    conn.commit()
    return saved, flagged


def reparse(conn):
    """Re-run classification and spec extraction on stored listings (no API calls)."""
    rows = conn.execute("SELECT id, category, title, snippet, extensions FROM listings").fetchall()
    for listing_id, category, title, snippet, extensions in rows:
        detected = classify(title or "")
        ok = 1 if detected in (None, category) else 0
        conn.execute("UPDATE listings SET detected_category = ?, category_ok = ? WHERE id = ?",
                     (detected, ok, listing_id))
        conn.execute("DELETE FROM specs WHERE listing_id = ?", (listing_id,))
        store_specs(conn, listing_id, category, build_text(title, snippet, json.loads(extensions or "[]")))
    conn.commit()
    print(f"Re-parsed {len(rows)} listings.")


def recently_fetched(conn, query, hours):
    row = conn.execute("SELECT MAX(fetched_at) FROM listings WHERE query = ?", (query,)).fetchone()
    if not row or not row[0]:
        return False
    age = datetime.now(timezone.utc) - datetime.fromisoformat(row[0])
    return age.total_seconds() < hours * 3600


def fetch_with_retry(query, api_key, attempts=3):
    for attempt in range(1, attempts + 1):
        try:
            return fetch_listings(query, api_key)
        except Exception as exc:
            # Don't retry when Google simply has no results, or on the last attempt
            if attempt == attempts or "hasn't returned any results" in str(exc):
                raise
            time.sleep(3 * attempt)


# ---------------------------------------------------------------------------
# 5. Gemini discovery: when price.py finds too few matches, ask Gemini (with Google
#    Search grounding) which real products fit the restrictions, then run each product
#    through the normal SerpAPI -> save_listings path so it is stored and spec-parsed.
# ---------------------------------------------------------------------------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def spec_names(category):
    """Spec names the parser can extract for a category (so Gemini only reasons about those)."""
    names = [r["name"] for r in COMMON + RULES.get(category, []) if "name" in r]
    if any(r["kind"] == "channels" for r in RULES.get(category, [])):
        names += ["channels", "channel_count"]
    return names


def build_gemini_prompt(category, price, specs, count, known_queries):
    lines = [
        f"You are helping an AV integrator find real, currently sold products in the category "
        f"'{category}' available to buy new in the United States.",
        "Use Google Search to find specific products (exact brand + model) that satisfy these "
        "customer restrictions:",
    ]
    if price is not None:
        lines.append(f"- price (USD): {price}")
    for name, value in (specs or {}).items():
        lines.append(f"- {name}: {value}")
    lines += [
        "",
        "Restriction syntax: 'A..B' = between A and B, 'A..' = at least A, '..B' = at most B, "
        "a bare number = exactly that, a word = text match. For 'resolution' the number is "
        "vertical pixels (2160 = 4K, 1080 = 1080p). 'diagonal_in' is inches.",
        f"Spec names we track for this category: {', '.join(spec_names(category))}.",
        "",
        f"Return up to {count} DIFFERENT products. Prefer products that meet every restriction "
        "according to the manufacturer's published specs, and that retail near the price range.",
    ]
    if known_queries:
        lines.append("We already have these, so do NOT suggest them again:")
        lines += [f"- {q}" for q in known_queries[:40]]
    lines += [
        "",
        "Respond with ONLY a JSON array, no prose and no markdown. Each element:",
        '{"query": "<brand + exact model + key spec words, usable as a Google Shopping search>"}',
        'Example: [{"query": "Epson Home Cinema 2350 4K PRO-UHD projector 2800 lumens"}]',
    ]
    return "\n".join(lines)


def ask_gemini(prompt, api_key, attempts=3):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],  # web grounding
        "generationConfig": {"temperature": 0.2},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    url = GEMINI_URL.format(model=GEMINI_MODEL)
    for attempt in range(1, attempts + 1):
        r = requests.post(url, headers=headers, json=body, timeout=90)
        if r.status_code in (429, 500, 503) and attempt < attempts:
            time.sleep(3 * attempt)
            continue
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data.get('promptFeedback', data)}")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)


def parse_queries(text):
    """Pull the JSON array out of Gemini's reply (grounded replies can't force JSON mode)."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON array in Gemini reply: {text[:200]!r}")
    items = json.loads(text[start:end + 1])
    queries, seen = [], set()
    for item in items:
        q = item.get("query") if isinstance(item, dict) else item
        q = " ".join(str(q or "").split())
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
    return queries


def suggest_queries(conn, category, price=None, specs=None, count=5):
    """Ask Gemini for new product search queries matching the restrictions."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    known = [r[0] for r in conn.execute(
        "SELECT DISTINCT query FROM listings WHERE category = ?", (category,))]
    known_lower = {q.lower() for q in known}
    reply = ask_gemini(build_gemini_prompt(category, price, specs, count, known), api_key)
    return [q for q in parse_queries(reply) if q.lower() not in known_lower][:count]


def expand_catalog(conn, category, price=None, specs=None, max_queries=5):
    """
    Gemini finds products -> SerpAPI fetches listings -> save_listings stores + parses specs.
    Returns the number of listings saved (0 if nothing could be added).
    Costs 1 Gemini call + up to `max_queries` SerpAPI searches.
    """
    serp_key = os.environ.get("SERPAPI_KEY")
    if not serp_key:
        raise RuntimeError("SERPAPI_KEY is not set")
    queries = suggest_queries(conn, category, price, specs, max_queries)
    if not queries:
        print("  Gemini suggested no new products.")
        return 0
    total = 0
    for query in queries:
        try:
            saved, flagged = save_listings(conn, query, category, fetch_with_retry(query, serp_key))
            total += saved
            print(f"  + {query}: saved {saved} listings ({flagged} flagged off-category)")
        except Exception as exc:
            print(f"  ! {query}: FAILED - {exc}")
        time.sleep(0.5)
    return total


def main():
    parser = argparse.ArgumentParser(description="Fetch AV listings and store them with specs.")
    parser.add_argument("--only", help="only fetch this category (e.g. projector)")
    parser.add_argument("--resume", action="store_true",
                        help="skip queries already fetched in the last 12 hours (use after a partial run)")
    parser.add_argument("--dry-run", action="store_true", help="list what would be fetched, no API calls")
    parser.add_argument("--reparse", action="store_true", help="re-parse stored listings, no API calls")
    args = parser.parse_args()

    todo = [(q, c) for q, c in TRACKED if not args.only or c == args.only]

    if args.dry_run:
        for i, (query, category) in enumerate(todo, 1):
            print(f"{i:>2}. [{category}] {query}")
        print(f"\n{len(todo)} queries = {len(todo)} SerpAPI searches.")
        return

    conn = init_db()
    if args.reparse:
        reparse(conn)
        return

    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        sys.exit("Set the SERPAPI_KEY environment variable first.")

    stats = {"listings": 0, "flagged": 0, "skipped": 0}
    failed = []
    for i, (query, category) in enumerate(todo, 1):
        prefix = f"[{i}/{len(todo)}] [{category}] {query}"
        if args.resume and recently_fetched(conn, query, 12):
            stats["skipped"] += 1
            print(f"{prefix}: skipped (fetched recently)")
            continue
        try:
            saved, flagged = save_listings(conn, query, category, fetch_with_retry(query, api_key))
            stats["listings"] += saved
            stats["flagged"] += flagged
            print(f"{prefix}: saved {saved} listings ({flagged} flagged as off-category)")
        except Exception as exc:
            failed.append(query)
            print(f"{prefix}: FAILED - {exc}")
        time.sleep(0.5)  # be gentle with the API

    print(f"\nDone. {len(todo) - len(failed) - stats['skipped']} queries fetched, "
          f"{stats['skipped']} skipped, {len(failed)} failed. "
          f"{stats['listings']} listings stored ({stats['flagged']} flagged off-category).")
    if failed:
        print("Failed queries:")
        for q in failed:
            print(f"  - {q}")
        print("Re-run with --resume to retry only the missing ones.")
        sys.exit(1)


if __name__ == "__main__":
    main()