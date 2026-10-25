"""Optional shopping implementation with an offline fallback."""
import importlib
import os

from .stubs import products_stub


def run_products(layout: dict, budget: float) -> dict:
    layout = {**layout, "speakers": [
        {**speaker, "role": {"Lss": "Ls", "Rss": "Rs"}.get(speaker.get("role"), speaker.get("role"))}
        for speaker in layout.get("speakers", [])
        if speaker.get("role") in {"L", "R", "C", "LFE", "Ls", "Rs", "Lss", "Rss"}
        and not (speaker.get("role") in {"Lss", "Rss"}
                 and any(other.get("role") == {"Lss": "Ls", "Rss": "Rs"}[speaker["role"]]
                         for other in layout.get("speakers", [])))]}
    backend = products_stub
    if os.getenv("PRODUCTS_BACKEND", "auto") != "stub":
        try:
            backend = importlib.import_module("products")
        except ImportError:
            pass
    try:
        return backend.get_products(layout, budget, serpapi_key=os.getenv("SERPAPI_KEY"))
    except Exception as exc:
        result = products_stub.get_products(layout, budget)
        result.setdefault("warnings", []).append(f"products fallback: {type(exc).__name__}")
        return result
