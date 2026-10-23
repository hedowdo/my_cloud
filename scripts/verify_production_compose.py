"""Exercise the production profile in a NEW local synthetic project with local-CA TLS.

Never uses public ACME, changes DNS, touches OCI or removes persistent volumes.
Test-only overrides replace host binds/public ports with new volumes/loopback ports.
"""

import http.client
import json
import os
import secrets
import socket
import ssl
import subprocess
import uuid
from pathlib import Path

from production_preflight import validate_configuration

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.environ.get("DOCKER_HOST"):
        raise SystemExit("Refusing remote Docker overrides")
    docker = os.environ.get("STAGE8_DOCKER", "docker")
    endpoint = subprocess.check_output(
        [docker, "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True
    ).strip()
    if not endpoint.startswith(("npipe://", "unix://")):
        raise SystemExit("Local Docker is required")
    run_id = uuid.uuid4().hex[:12]
    project = f"cloud-stage8-{run_id}"
    evidence = ROOT / ".local" / "stage8" / run_id
    evidence.mkdir(parents=True)

    def run(args, source=None):
        result = subprocess.run(
            [docker, *args],
            cwd=ROOT,
            input=source,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        log = evidence / f"command-{uuid.uuid4().hex}.log"
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Command failed; private evidence {log}")
        return result.stdout.strip()

    def inspect_image(name):
        return json.loads(run(["image", "inspect", name]))[0]["Id"]

    preview = json.loads((ROOT / ".cache/compose-latest.json").read_text())
    if preview["project"] != "cloud-stage5-92c8e356b3cb" or not preview["passed"]:
        raise SystemExit("The documented synthetic preview must be identified")
    preview_id = run(["compose", "-p", preview["project"], "ps", "-q", "frontend"])
    frontend_image = json.loads(run(["inspect", preview_id]))[0]["Image"]
    values = {
        "CLOUD_HOST": "stage8-fixture.duckdns.org",
        "DATA_ROOT": "/srv/stage8-fixture",
        "DATABASE_IMAGE": inspect_image("postgres:17.11-bookworm"),
        "API_IMAGE": inspect_image("cloud-stage8-api:candidate"),
        "FRONTEND_IMAGE": frontend_image,
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "MIGRATION_PASSWORD": secrets.token_hex(32),
        "APP_DATABASE_PASSWORD": secrets.token_hex(32),
        "AUTH_RATE_SECRET": secrets.token_hex(32),
        "STORAGE_POOL_BYTES": "100000000000",
        "STORAGE_RESERVE_BYTES": "10000000000",
    }
    env = evidence / "synthetic.env"
    env.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    env.chmod(0o600)
    validate_configuration(values)
    base = ["compose", "-p", project, "--env-file", str(env), "-f", "compose.production.yaml"]
    rendered = json.loads(run([*base, "config", "--format", "json"]))
    assert set(rendered["services"]) == {"database", "migrate", "api", "frontend"}
    for name in ("database", "migrate", "api"):
        assert not rendered["services"][name].get("ports")
    for name in ("database", "api", "frontend"):
        mounts = rendered["services"][name]["volumes"]
        data_mount = next(m for m in mounts if m["source"].startswith(values["DATA_ROOT"]))
        assert data_mount["type"] == "bind" and data_mount["bind"]["create_host_path"] is False
    assert rendered["networks"]["backend"]["internal"] is True
    tls = evidence / "Caddyfile"
    tls.write_text(
        (ROOT / "infrastructure/Caddyfile.production")
        .read_text()
        .replace("{\n", "{\n    local_certs\n", 1),
        encoding="utf-8",
    )
    holders = []
    for _ in range(2):
        holder = socket.socket()
        holder.bind(("127.0.0.1", 0))
        holders.append(holder)
    http_port, https_port = [h.getsockname()[1] for h in holders]
    override = evidence / "test-override.yaml"
    # JSON is used for scalar paths, not shell quoting. This file is Compose YAML.
    override.write_text(
        f"""services:
  database:
    volumes: !override
      - fixture_db:/var/lib/postgresql/data
      - type: bind
        source: {json.dumps((ROOT / "infrastructure/postgres/init-roles.sql").as_posix())}
        target: /docker-entrypoint-initdb.d/10-roles.sql
        read_only: true
  api:
    volumes: !override [fixture_files:/srv/storage]
  frontend:
    ports: !override ['127.0.0.1:{http_port}:80', '127.0.0.1:{https_port}:443']
    volumes: !override
      - type: bind
        source: {json.dumps(str(tls).replace(chr(92), "/"))}
        target: /etc/caddy/Caddyfile
        read_only: true
      - fixture_caddy:/data
volumes:
  fixture_db: {{}}
  fixture_files: {{}}
  fixture_caddy: {{}}
""",
        encoding="utf-8",
    )
    compose = [*base, "-f", str(override)]
    # New, uniquely labelled fixture volumes only; never prepare an existing project.
    for short in ("files", "caddy"):
        volume = f"{project}_fixture_{short}"
        assert run(["volume", "ls", "-q", "--filter", f"name=^{volume}$"]) == ""
        run(["volume", "create", "--label", f"stage8.fixture={run_id}", volume])
        run(
            [
                "run",
                "--rm",
                "--network",
                "none",
                "--user",
                "0:0",
                "--mount",
                f"type=volume,src={volume},dst=/fixture",
                values["API_IMAGE"],
                "python",
                "-c",
                "import os; os.chown('/fixture',10001,10001); os.chmod('/fixture',0o700)",
            ]
        )
    run([*compose, "config", "--quiet"])
    for holder in holders:
        holder.close()
    try:
        run([*compose, "up", "-d", "--wait", "--wait-timeout", "150", "--pull", "never"])
        ca = evidence / "local-ca.crt"
        ca.write_text(
            run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "frontend",
                    "cat",
                    "/data/caddy/pki/authorities/local/root.crt",
                ]
            ),
            encoding="utf-8",
        )
        context = ssl.create_default_context(cafile=str(ca))

        class LoopbackTLS(http.client.HTTPSConnection):
            def connect(self):
                raw = socket.create_connection(("127.0.0.1", https_port), timeout=10)
                self.sock = context.wrap_socket(raw, server_hostname=values["CLOUD_HOST"])

        def request(path, method="GET", payload=None, headers=None):
            connection = LoopbackTLS(values["CLOUD_HOST"], timeout=10)
            body = json.dumps(payload) if payload is not None else None
            all_headers = {"Host": values["CLOUD_HOST"], **(headers or {})}
            if body is not None:
                all_headers["Content-Type"] = "application/json"
            try:
                connection.request(method, path, body, all_headers)
                response = connection.getresponse()
                return response.status, response.getheaders(), response.read()
            finally:
                connection.close()

        assert request("/api/health/ready")[0] == 200
        assert request("/api/items")[0] == 401
        status, headers, body = request("/")
        assert status == 200 and b"<html" in body
        assert dict(headers)["Strict-Transport-Security"] == "max-age=31536000"
        plain = http.client.HTTPConnection("127.0.0.1", http_port, timeout=10)
        plain.request("GET", "/", headers={"Host": values["CLOUD_HOST"]})
        redirect = plain.getresponse()
        assert redirect.status == 308
        assert redirect.getheader("Location") == f"https://{values['CLOUD_HOST']}/"
        plain.close()
        password = secrets.token_urlsafe(32)
        fixture = {"email": "stage8-admin@example.com", "password": password, "marker": run_id}
        run(
            [
                *compose,
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                """
import json, sys
from pathlib import Path
from app.config import Settings
from app.database import make_engine
from app.identity_service import Identity
data=json.load(sys.stdin)
settings=Settings()
assert settings.app_env=='production' and not settings.insecure_loopback_cookies
engine=make_engine(settings)
Identity(engine,settings).bootstrap(data['email'],data['password'])
Path('/srv/storage/stage8-marker').write_text(data['marker'])
engine.dispose()
""",
            ],
            json.dumps(fixture),
        )
        status, headers, _ = request(
            "/api/auth/login",
            "POST",
            {
                "email": fixture["email"],
                "password": password,
            },
            {"Origin": f"https://{values['CLOUD_HOST']}", "X-Forwarded-For": "198.51.100.123"},
        )
        assert status == 200
        cookies = [value for name, value in headers if name.lower() == "set-cookie"]
        assert len(cookies) == 2 and all(
            "Secure" in cookie and "SameSite=strict" in cookie for cookie in cookies
        )
        assert any(
            cookie.startswith("__Host-pc_session=") and "HttpOnly" in cookie for cookie in cookies
        )
        cookie_header = "; ".join(cookie.split(";", 1)[0] for cookie in cookies)
        assert request("/api/auth/me", headers={"Cookie": cookie_header})[0] == 200
        assert request("/api/items", headers={"Cookie": cookie_header})[0] == 200
        assert (
            request(
                "/api/auth/login",
                "POST",
                {"email": fixture["email"], "password": password},
                {"Origin": "https://attacker.example.com"},
            )[0]
            == 403
        )
        run(
            [
                *compose,
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                """
import hashlib,hmac,os
from sqlalchemy import text
from app.config import Settings
from app.database import make_engine
s=Settings(); engine=make_engine(s)
forged=hmac.digest(s.auth_rate_secret.get_secret_value().encode(),
                  b'login:peer:198.51.100.123',hashlib.sha256)
with engine.connect() as c:
    query=text('SELECT count(*) FROM auth_rate_limits WHERE key_hash=:key')
    assert c.scalar(query,{'key':forged})==0
assert os.getuid()==10001
engine.dispose()
""",
            ]
        )
        run(
            [
                *compose,
                "up",
                "-d",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "150",
                "--pull",
                "never",
            ]
        )
        assert request("/api/auth/me", headers={"Cookie": cookie_header})[0] == 200
        assert run([*compose, "exec", "-T", "api", "cat", "/srv/storage/stage8-marker"]) == run_id
        for name in ("api", "frontend", "migrate"):
            identity = run([*compose, "ps", "-a", "-q", name])
            actual = json.loads(run(["inspect", identity]))[0]
            assert actual["Config"]["User"] == "10001:10001"
            assert actual["HostConfig"]["ReadonlyRootfs"] is True
            assert actual["HostConfig"]["CapDrop"] == ["ALL"]
        result = {
            "passed": True,
            "project": project,
            "local_ca_tls_verified": True,
            "secure_cookies": True,
            "https_redirect": True,
            "spoofed_forwarded_ip_rejected": True,
            "session_and_file_survive_recreation": True,
            "public_acme_verified": False,
            "actual_host_bind_mounts_verified": False,
            "cloud_resources_created": False,
        }
        (evidence / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        run([*compose, "stop"])
        print(f"Synthetic project stopped; volumes and private evidence retained: {evidence}")


if __name__ == "__main__":
    main()
