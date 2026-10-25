"""Static deployment checks for the production Vite build."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_has_disposable_node_build_stage() -> None:
    dockerfile = (ROOT / "deploy" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:22-alpine AS web-build" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm run build" in dockerfile
    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY --from=web-build /build/web/ /app/web/" in dockerfile


def test_smoke_script_checks_vite_html_asset_and_model() -> None:
    smoke = (ROOT / "deploy" / "smoke.sh").read_text(encoding="utf-8")

    assert '"$BASE_URL/app/"' in smoke
    assert "Vite root element not found" in smoke
    assert "/app/assets/" in smoke
    assert "content-type:" in smoke
    assert "/app/models/projector.glb" in smoke
