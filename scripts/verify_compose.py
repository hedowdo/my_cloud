"""Verify a new disposable local Compose project; never remove its named volumes."""

import json
import os
import socket
import subprocess
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if os.environ.get("DOCKER_HOST"):
        raise SystemExit("Refusing a DOCKER_HOST override; verification must use local Docker")
    endpoint = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True
    ).strip()
    if not endpoint.startswith(("npipe://", "unix://")):
        raise SystemExit("Refusing a non-local Docker endpoint")
    for port in (8000, 8080):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(f"Port {port} already in use; leave the existing service intact")
    run_id = uuid.uuid4().hex[:12]
    project = f"cloud-stage5-{run_id}"
    evidence = ROOT / ".local" / "compose-verification" / run_id
    evidence.mkdir(parents=True)
    compose = ["docker", "compose", "--project-name", project, "--env-file", ".env"]

    def run(args: list[str]) -> str:
        result = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        log = evidence / f"command-{uuid.uuid4().hex}.log"
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Verification command failed; private evidence: {log.name}")
        return result.stdout.strip()

    def python_in_api(source: str) -> str:
        return run([*compose, "exec", "-T", "api", "python", "-c", source])

    def ready() -> None:
        for port in (8000, 8080):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health/ready", timeout=5
            ) as response:
                assert response.status == 200
                assert json.load(response) == {"status": "ready"}

    run([*compose, "config", "--quiet"])
    print(f"Building and starting disposable project {project}", flush=True)
    run([*compose, "up", "--build", "-d", "--wait", "--wait-timeout", "180"])
    ready()
    print("PASS: clean Compose build/start and direct/proxied readiness", flush=True)
    marker = str(uuid.uuid4())
    marker_name = f"stage2-{run_id}"
    source = f"""
import os
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from app.config import Settings
from app.database import make_engine
assert os.getuid() == 10001
engine = make_engine(Settings())
with engine.connect() as connection:
    assert connection.scalar(text('SELECT current_user')) == 'cloud_app'
    try:
        connection.execute(text('CREATE TABLE forbidden_ddl (id integer)'))
    except DBAPIError:
        connection.rollback()
    else:
        raise AssertionError('Runtime role allowed DDL')
    connection.execute(text(
        "INSERT INTO items (id,parent_id,kind,name,name_key) "
        "VALUES ('{marker}','00000000-0000-0000-0000-000000000001',"
        "'folder','{marker_name}','{marker_name}')"
    ))
    connection.commit()
Path('/srv/storage/{marker_name}').write_text('{marker}', encoding='utf-8')
engine.dispose()
print('metadata and file markers committed; runtime UID/role/DDL verified')
"""
    print(python_in_api(source), flush=True)
    before = run([*compose, "ps", "-q", "database", "api", "frontend"]).splitlines()
    run([*compose, "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180"])
    after = run([*compose, "ps", "-q", "database", "api", "frontend"]).splitlines()
    assert len(before) == len(after) == 3 and set(before).isdisjoint(after)
    ready()
    python_in_api(f"""
from pathlib import Path
from sqlalchemy import text
from app.config import Settings
from app.database import make_engine
with make_engine(Settings()).connect() as connection:
    assert connection.scalar(text("SELECT count(*) FROM items WHERE id='{marker}'")) == 1
assert Path('/srv/storage/{marker_name}').read_text(encoding='utf-8') == '{marker}'
""")
    print("PASS: metadata and file bytes survive recreation of all service containers", flush=True)
    dump = f"/tmp/stage2-{run_id}.dump"
    restored = f"cloud_test_{run_id}"
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
            f"SELECT count(*) FROM items WHERE id='{marker}'",
        ]
    )
    assert count == "1"
    print("PASS: container pg_dump/pg_restore recovers disposable metadata", flush=True)
    result = {
        "project": project,
        "evidence": str(evidence),
        "marker_id": marker,
        "ready_url": "http://127.0.0.1:8080",
        "passed": True,
    }
    (ROOT / ".cache" / "compose-latest.json").write_text(json.dumps(result), encoding="utf-8")
    print(
        "Stack retained for browser review. Stop only this project with compose down; no -v.",
        flush=True,
    )


if __name__ == "__main__":
    main()
