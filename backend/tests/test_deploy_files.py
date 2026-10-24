from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dockerfile_has_safe_runtime_and_healthcheck():
    dockerfile = read("deploy/Dockerfile")
    assert "--workers" in dockerfile and '"1"' in dockerfile
    assert "COPY . ." in dockerfile
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_dockerignore_excludes_runtime_secrets_and_data():
    dockerignore = read(".dockerignore")
    for entry in (".env", "data/", ".git", "memory/", ".localdata/"):
        assert entry in dockerignore


def test_compose_has_internal_api_and_persistent_caddy():
    compose = read("deploy/docker-compose.yml")
    assert "services:" in compose
    assert "api:" in compose and "caddy:" in compose
    assert '"80:80"' in compose and '"443:443"' in compose
    assert "env_file" in compose
    assert "DATA_DIR: /data" in compose
    assert "sweetspot_data" in compose
    assert "caddy_data" in compose and "caddy_config" in compose
    assert "restart: unless-stopped" in compose
    api_section = compose.split("  caddy:", 1)[0]
    assert "ports:" not in api_section


def test_caddy_routes_and_limits_requests():
    caddy = read("deploy/Caddyfile")
    assert "{$SITE_ADDRESS}" in caddy
    assert "reverse_proxy api:8000" in caddy
    assert "redir @root /app/plot2d/ 302" in caddy
    assert "25MB" in caddy


def test_smoke_script_is_bash_and_covers_required_routes():
    smoke = read("deploy/smoke.sh")
    assert "set -euo pipefail" in smoke
    for endpoint in ("/health", "/sessions", "/rooms/demo", "/optimize", "/layout", "/products?budget=1500", "/photo-targets", "/app/plot2d/"):
        assert endpoint in smoke
