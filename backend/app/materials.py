"""Surface material classification and octave-band absorption."""

import io
import json
import os
from types import SimpleNamespace
from typing import Any

from PIL import Image, UnidentifiedImageError

MATERIALS = ["drywall", "glass", "brick", "carpet", "hardwood", "tile", "curtain", "unknown"]
BANDS = ("125", "250", "500", "1000", "2000", "4000")
MIN_CONFIDENCE = 0.5

# Approximate typical octave-band absorption coefficients, not from a single cited measurement.
_VALUES = {
    "drywall": (0.05, 0.06, 0.08, 0.09, 0.09, 0.09),
    "hardwood": (0.15, 0.11, 0.10, 0.07, 0.06, 0.07),
    "glass": (0.35, 0.25, 0.18, 0.12, 0.07, 0.04),
    "brick": (0.03, 0.03, 0.03, 0.04, 0.05, 0.07),
    "carpet": (0.02, 0.06, 0.14, 0.37, 0.60, 0.65),
    "tile": (0.01, 0.01, 0.01, 0.01, 0.02, 0.02),
    "curtain": (0.07, 0.31, 0.49, 0.75, 0.70, 0.60),
    "unknown": (0.05, 0.06, 0.08, 0.09, 0.09, 0.09),
}
ABSORPTION: dict[str, dict[str, float]] = {
    material: dict(zip(BANDS, values, strict=False)) for material, values in _VALUES.items()
}

PROMPT = (
    "Classify the material visible in each surface photo. Return only strict JSON as "
    '[{"surface_id": str, "material": enum, "confidence": number 0..1}]. '
    "Use exactly one entry per supplied surface_id. Allowed materials: "
    + ", ".join(MATERIALS) + "."
)


def _unknown(ids: list[str]) -> list[dict]:
    return [{"surface_id": surface_id, "material": "unknown", "confidence": 0.0} for surface_id in ids]


def parse_model_output(text: str, expected_ids: list[str]) -> list[dict]:
    """Extract the first usable JSON result and normalize it to the requested ids."""
    ids = list(dict.fromkeys(expected_ids))
    decoder = json.JSONDecoder()
    payload: Any = None
    for index, char in enumerate(text or ""):
        if char not in "[{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[index:])
        except (ValueError, TypeError):
            continue
        if isinstance(candidate, list) or (isinstance(candidate, dict) and isinstance(candidate.get("surfaces"), list)):
            payload = candidate
            break
    if isinstance(payload, dict):
        payload = payload["surfaces"]
    if not isinstance(payload, list):
        return _unknown(ids)
    found: dict[str, dict] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        surface_id = item.get("surface_id")
        if surface_id not in ids or surface_id in found:
            continue
        material = item.get("material")
        if material not in MATERIALS:
            material = "unknown"
        confidence = item.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            confidence = 0.0
        if confidence != confidence:  # NaN
            confidence = 0.0
        found[surface_id] = {"surface_id": surface_id, "material": material, "confidence": confidence}
    return [found.get(surface_id, _unknown([surface_id])[0]) for surface_id in ids]


def prepare_image(data: bytes) -> bytes:
    """Encode an image as a bounded RGB JPEG for storage and classification."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("file is not an image") from exc
    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=70)
    return output.getvalue()


class MockClassifier:
    def classify(self, photos: list[dict]) -> list[dict]:
        results = []
        for photo in photos:
            surface_id = photo["surface_id"]
            if "floor" in surface_id:
                material, confidence = "hardwood", 0.9
            elif "window" in surface_id:
                material, confidence = "glass", 0.9
            elif "ceiling" in surface_id:
                material, confidence = "drywall", 0.9
            else:
                material, confidence = "drywall", 0.8
            results.append({"surface_id": surface_id, "material": material, "confidence": confidence})
        return results


class GeminiClassifier:
    def __init__(self, client: Any = None, api_key: str | None = None):
        self.client = client
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")

    def classify(self, photos: list[dict]) -> list[dict]:
        ids = [photo["surface_id"] for photo in photos]
        if not photos:
            return []
        if not self.api_key and self.client is None:
            return _unknown(ids)
        try:
            # SDK is optional in offline tests. Client creation also sets the request timeout.
            try:
                from google import genai
                from google.genai import types
            except ImportError:
                if self.client is None:
                    return _unknown(ids)
                # Injectable fake clients can exercise request formatting without the SDK.
                types = SimpleNamespace(
                    Part=SimpleNamespace(
                        from_text=lambda text: SimpleNamespace(text=text),
                        from_bytes=lambda data, mime_type: SimpleNamespace(
                            inline_data=SimpleNamespace(data=data, mime_type=mime_type)),
                    ),
                    Content=lambda role, parts: SimpleNamespace(role=role, parts=parts),
                    GenerateContentConfig=lambda response_mime_type: SimpleNamespace(
                        response_mime_type=response_mime_type),
                )

            client = self.client or genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=20_000))
            parts: list[Any] = [types.Part.from_text(text=PROMPT)]
            for photo in photos:
                parts.append(types.Part.from_text(text=f"surface_id: {photo['surface_id']}"))
                parts.append(types.Part.from_bytes(data=photo["image_bytes"], mime_type=photo["mime"]))
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return parse_model_output(response.text or "", ids)
        except Exception:
            return _unknown(ids)


def classify_materials(photos: list[dict], backend: str | None = None) -> list[dict]:
    selected = backend or os.getenv("MATERIALS_BACKEND", "gemini")
    classifier = MockClassifier() if selected == "mock" else GeminiClassifier()
    return classifier.classify(photos)
