"""Stage 3 acceptance on the harness-owned local Compose stack, with synthetic accounts only."""

import hashlib
import http.cookiejar
import json
import os
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://127.0.0.1:8080"


def main():
    result = json.loads((ROOT / ".cache/compose-latest.json").read_text())
    project = result["project"]
    if (
        not result["passed"]
        or not project.startswith("cloud-stage3-")
        or os.environ.get("DOCKER_HOST")
    ):
        raise SystemExit("Requires a passing, disposable local Stage 3 Compose harness project")
    endpoint = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True
    ).strip()
    if not endpoint.startswith(("npipe://", "unix://")):
        raise SystemExit("Refusing non-local Docker endpoint")
    evidence = Path(result["evidence"])
    compose = ["docker", "compose", "--project-name", project, "--env-file", ".env"]

    def run(args):
        completed = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        if completed.returncode:
            (evidence / "identity-private-failure.log").write_text(
                completed.stdout + completed.stderr, encoding="utf-8"
            )
            raise RuntimeError("Compose identity check failed; private evidence retained")
        return completed.stdout.strip()

    # Rebuild source layers after native tests; dependency layers remain cached.
    run([*compose, "up", "--build", "-d", "--wait", "--wait-timeout", "180"])
    bootstrap = """
import json,secrets
from app.config import Settings
from app.database import make_engine
from app.identity_service import Identity
settings=Settings()
engine=make_engine(settings)
password=secrets.token_urlsafe(24)
Identity(engine,settings).bootstrap('admin@example.com',password)
print(json.dumps({'email':'admin@example.com','password':password}))
engine.dispose()
"""
    fixture = json.loads(run([*compose, "exec", "-T", "api", "python", "-c", bootstrap]))
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(path, method="GET", body=None):
        headers = {"Origin": ORIGIN}
        if method != "GET":
            headers["Content-Type"] = "application/json"
            for cookie in jar:
                if cookie.name == "pc_csrf_dev":
                    headers["X-CSRF-Token"] = cookie.value
        req = urllib.request.Request(
            ORIGIN + "/api" + path,
            headers=headers,
            method=method,
            data=json.dumps(body or {}).encode() if method != "GET" else None,
        )
        with opener.open(req, timeout=10) as response:
            payload = response.read()
            return json.loads(payload) if payload else None

    assert request("/auth/login", "POST", fixture)["user"]["role"] == "admin"
    assert request("/auth/me")["user"]["email"] == fixture["email"]
    session = next(cookie.value for cookie in jar if cookie.name == "pc_session_dev")
    assert all(not cookie.secure for cookie in jar)  # Explicit loopback-only development mode.
    invitation = request("/admin/invitations", "POST")
    assert invitation["token"] not in json.dumps(request("/admin/invitations"))
    run([*compose, "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180"])
    assert request("/auth/me")["user"]["email"] == fixture["email"]
    assert next(cookie.value for cookie in jar if cookie.name == "pc_session_dev") == session
    print(
        "PASS: real proxied login/invitation and session survive all-container recreation",
        flush=True,
    )
    run_id = uuid.uuid4().hex[:12]
    dump = f"/tmp/identity-{run_id}.dump"
    restored = f"cloud_test_identity_{run_id}"
    run(
        [
            *compose,
            "exec",
            "-T",
            "database",
            "pg_dump",
            "-U",
            "cloud_migrator",
            "-d",
            "cloud",
            "-Fc",
            "-f",
            dump,
        ]
    )
    run([*compose, "exec", "-T", "database", "createdb", "-U", "postgres", restored])
    run(
        [
            *compose,
            "exec",
            "-T",
            "database",
            "pg_restore",
            "-U",
            "postgres",
            "--no-owner",
            "-d",
            restored,
            dump,
        ]
    )
    hashed = hashlib.sha256(session.encode()).hexdigest()
    count = run(
        [
            *compose,
            "exec",
            "-T",
            "database",
            "psql",
            "-U",
            "postgres",
            "-d",
            restored,
            "-Atc",
            "SELECT count(*) FROM sessions s JOIN users u ON u.id=s.user_id "
            f"WHERE s.token_hash=decode('{hashed}','hex') AND u.active AND s.revoked_at IS NULL",
        ]
    )
    assert count == "1"
    print(
        "PASS: real container pg_dump/restore preserves active identity and session digests",
        flush=True,
    )
    request("/auth/logout", "POST")
    try:
        request("/auth/me")
        raise AssertionError("Logout failed to revoke access")
    except urllib.error.HTTPError as error:
        assert error.code == 401
    fixture.update(
        {
            "project": project,
            "invitation": invitation["token"],
            "guest_email": "guest-ui@example.net",
            "guest_password": uuid.uuid4().hex,
        }
    )
    (ROOT / ".cache/stage3-browser-fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
    (evidence / "identity-acceptance.json").write_text(
        json.dumps(
            {
                "passed": True,
                "project": project,
                "synthetic_accounts_only": True,
                "session_recreation": True,
                "identity_restore": True,
                "logout": True,
            }
        ),
        encoding="utf-8",
    )
    print(
        "PASS: logout revoked access; synthetic browser fixtures saved privately",
        flush=True,
    )


if __name__ == "__main__":
    main()
