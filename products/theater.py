"""Eligibility and compatibility rules for a complete home theater."""

import math
import re

from .value import NEUTRAL_SPEC, clamp, number

PASSIVE_EXCLUSIONS = ("bluetooth", "wireless", "wi-fi", "wifi", "airplay", "usb",
                      "powered", "active", "computer", "desktop", "gaming", "portable",
                      "smart", "party", "karaoke", "soundbar", "alexa", "sonos")
RECEIVER_EXCLUSIONS = ("manual", "cover", "remote", "case", "for parts", "non working")
RECEIVER_CHANNEL_BONUS = 0.25
RECEIVER_HDMI_BONUS = 0.12
RECEIVER_ATMOS_BONUS = 0.08
RECEIVER_WIFI_BONUS = 0.05


def passive_speaker(row: dict) -> bool:
    title = row.get("title", "").lower()
    specs = row.get("specs") or {}
    spec_values = " ".join(str(value).lower() for value in specs.values())
    return not any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", title)
                   or re.search(rf"(?<!\w){re.escape(term)}(?!\w)", spec_values)
                   or str(specs.get(term, "")).lower() in {"yes", "true", "1"}
                   for term in PASSIVE_EXCLUSIONS)


def bundle_roles(title: str, pair: tuple[str, str] = ("L", "R")) -> tuple[str, ...]:
    """Return only roles that the title clearly says are included."""
    lower = title.lower()
    if (re.search(r"\b5\.1(?:\.\d+)?\b", lower)
            and re.search(r"home theater|\bsystem\b|\bpackage\b", lower)):
        roles = ("C", "L", "R", "Ls", "Rs")
        return roles + ("LFE",) if re.search(r"sub-?woofer|\bsub\b", lower) else roles
    if re.search(r"\bpairs?\b|\(2\)|set of 2", lower):
        if re.search(r"\b(?:with|\+)\s+(?:[\w-]+\s+){0,3}center\b", lower):
            return ("C", "L", "R")
        return pair
    return ()


def receiver_channels(row: dict) -> int | None:
    specs = row.get("specs") or {}
    label = str(specs.get("channels") or "")
    match = re.search(r"\b(\d+)\s*\.\s*\d+", label)
    if match:
        return int(match.group(1))
    count = number(specs.get("channel_count"))
    return max(0, int(count) - 2) if count is not None else None


def receiver_eligible(row: dict, needed: int, projector: dict | None = None) -> bool:
    title = row.get("title", "").lower()
    if row.get("price", 0) < 150 or any(word in title for word in RECEIVER_EXCLUSIONS):
        return False
    channels = receiver_channels(row)
    if channels is not None and channels < needed:
        return False
    if projector and number((projector.get("specs") or {}).get("resolution")) and (
            number((projector.get("specs") or {}).get("resolution")) >= 2160):
        specs = row.get("specs") or {}
        copy = " ".join((title, str(specs))).lower()
        if "1080p" in copy and not re.search(r"4k|8k|2160|4320|uhd", copy):
            return False
    return True


def receiver_quality(row: dict, needed: int) -> float:
    specs = row.get("specs") or {}
    rating = number(row.get("rating")) or 4.0
    reviews = number(row.get("reviews")) or 0
    bayes = (rating * reviews + 4.0 * 20) / (reviews + 20)
    copy = " ".join((row.get("title", ""), str(specs))).lower()
    channels = receiver_channels(row)
    return clamp(0.45 * clamp((bayes - 3) / 2)
                 + RECEIVER_CHANNEL_BONUS * (NEUTRAL_SPEC if channels is None else min(1, channels / needed))
                 + RECEIVER_HDMI_BONUS * (1 if re.search(r"hdmi\s*2\.1|\b8k\b", copy) else NEUTRAL_SPEC)
                 + RECEIVER_ATMOS_BONUS * (1 if "atmos" in copy else NEUTRAL_SPEC)
                 + RECEIVER_WIFI_BONUS * (1 if re.search(r"wi-?fi", copy) else NEUTRAL_SPEC))


def choose_tv(tv_rows: list[dict], screen: dict | None, combined_share: float) -> dict | None:
    if not screen:
        return None
    target = math.hypot(screen["width"], screen["height"]) * 12
    eligible = [row for row in tv_rows if row["price"] <= combined_share
                and (number((row.get("specs") or {}).get("diagonal_in")) or 0) >= 0.9 * target]
    return max(eligible, key=lambda row: (number(row.get("rating")) or 4) - row["price"] / combined_share,
               default=None)
