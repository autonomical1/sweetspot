"""Identify equivalent listings and related speaker models."""

import re
from functools import lru_cache

DROP = {"pair", "pairs", "set", "of", "2", "speaker", "speakers", "bookshelf",
        "floorstanding", "bluetooth", "wireless", "powered", "home", "studio",
        "lifestyle", "new", "with", "and", "for", "20", "recertified", "renewed", "refurbished"}


@lru_cache(maxsize=8192)
def _parts_cached(raw_title: str, raw_brand: str) -> tuple[str, tuple[str, ...]]:
    """Remove generic title words and extract the listing brand."""
    title = re.sub(r"\b\d+(?:\.\d+)?\s*w(?:atts)?\b", " ", raw_title.lower())
    title = title.replace("2.0", " ")
    title = re.sub(r"(?<=[a-z])-(?=\d)", "", title)
    words = [word for word in re.findall(r"[a-z]+\d*[a-z\d]*|\d+[a-z]+[a-z\d]*", title)
             if word not in DROP]
    brand = (raw_brand or (words[0] if words else "")).lower()
    brand = re.sub(r"[^a-z0-9]", "", brand)
    return brand, tuple(word for word in words if word != brand)


def model_key(row: dict) -> str:
    """Use brand plus first digit-bearing model token, else three significant words.

    Pair/set wording, generic audio terms, punctuation, and watt sizes do not
    distinguish listings. This groups the same model across sellers and titles.
    """
    brand, words = _parts_cached(row["title"], str((row.get("specs") or {}).get("brand") or ""))
    return _model_key(brand, words)


@lru_cache(maxsize=8192)
def _model_key(brand: str, words: tuple[str, ...]) -> str:
    model = next((word for word in words if any(char.isdigit() for char in word)), None)
    return " ".join([brand, model] if model else [brand, *words[:3]]).strip()


def family_key(row: dict) -> tuple[str, str]:
    """Return brand and first model token prefix through its initial digits."""
    brand, words = _parts_cached(row["title"], str((row.get("specs") or {}).get("brand") or ""))
    return _family_key(brand, words)


@lru_cache(maxsize=8192)
def _family_key(brand: str, words: tuple[str, ...]) -> tuple[str, str]:
    model = next((word for word in words if any(char.isdigit() for char in word)), "")
    match = re.match(r"[a-z]*\d+", model)
    return brand, match.group() if match else ""


def same_family(row: dict, front: dict) -> bool:
    """Match series when possible, otherwise match brand."""
    brand, series = family_key(row)
    front_brand, front_series = family_key(front)
    return bool(brand and brand == front_brand and series and series == front_series)
