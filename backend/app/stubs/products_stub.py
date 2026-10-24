"""Predictable fake catalog items, requiring no network."""


def get_products(layout: dict, budget: float, *, serpapi_key: str | None = None) -> dict:
    roles = list(dict.fromkeys(s["role"] for s in layout.get("speakers", [])))
    roles.append("screen" if layout.get("screen") else "projector")
    weights = {"L": 2, "R": 2, "C": 3, "LFE": 2, "Ls": 1, "Rs": 1, "screen": 1, "projector": 1}
    total_weight = sum(weights.get(role, 1) for role in roles)
    items = [{"role": role, "title": f"Demo {role}", "price": round(budget * weights.get(role, 1) / total_weight * 0.9, 2),
              "currency": "USD", "link": "https://example.invalid/demo", "thumbnail": None, "source": "stub"} for role in roles]
    return {"budget": budget, "total": round(sum(item["price"] for item in items), 2), "items": items}
