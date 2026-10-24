"""Optional shopping implementation with an offline fallback."""
import importlib
import os

from .stubs import products_stub


def run_products(layout: dict, budget: float) -> dict:
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
