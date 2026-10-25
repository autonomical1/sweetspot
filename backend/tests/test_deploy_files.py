import re
import shutil
import subprocess
from pathlib import Path

import pytest

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
    assert "redir @root /app/ 302" in caddy
    assert "25MB" in caddy


def test_smoke_script_is_bash_and_covers_required_routes():
    smoke = read("deploy/smoke.sh")
    assert "set -euo pipefail" in smoke
    for endpoint in ("/health", "/sessions", "/rooms/demo", "/optimize", "/layout", "/products?budget=1500", "/photo-targets", "/app/"):  # noqa: E501  # preserve behavior while retaining the existing expression
        assert endpoint in smoke
    assert re.search(r'\[\[ "\$expiry" == notAfter=\* \]\] \|\| return 1', smoke)
    assert "command -v openssl >/dev/null 2>&1 || return 1" in smoke


def test_smoke_script_has_valid_bash_syntax():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not installed")
    result = subprocess.run([bash, "-n", str(ROOT / "deploy/smoke.sh")], capture_output=True, check=False)
    if result.returncode == 127 and "system32" in bash.lower():
        pytest.skip("bash resolves to the WSL launcher without an installed distro")
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def test_deploy_checkout_and_env_are_owned_by_deploy_user():
    instructions = read("DEPLOY.md")
    assert 'sudo install -d -o "$USER" -g "$USER" /srv/sweetspot' in instructions
    assert "git clone https://github.com/autonomical1/sweetspot.git /srv/sweetspot" in instructions
    assert "sudo git clone" not in instructions
    assert "sudo cp /srv/sweetspot/.env.example" not in instructions
    assert "chmod 600 /srv/sweetspot/.env" in instructions
