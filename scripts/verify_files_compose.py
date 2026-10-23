"""Exercise Stage 4 against a fresh harness-owned Linux Compose stack, with synthetic data only."""

import ast
import hashlib
import http.client
import http.cookiejar
import io
import json
import os
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://127.0.0.1:8080"


def main():
    latest = json.loads((ROOT / ".cache/compose-latest.json").read_text(encoding="utf-8"))
    project = latest["project"]
    if (
        not latest["passed"]
        or not project.startswith(("cloud-stage4-", "cloud-stage5-"))
        or os.environ.get("DOCKER_HOST")
    ):
        raise SystemExit("Requires a passing fresh local Compose harness")
    endpoint = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True
    ).strip()
    if not endpoint.startswith(("npipe://", "unix://")):
        raise SystemExit("Refusing a non-local Docker endpoint")
    evidence = Path(latest["evidence"])
    compose = ["docker", "compose", "--project-name", project, "--env-file", ".env"]

    def run(arguments):
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
        log = evidence / f"files-command-{uuid.uuid4().hex}.log"
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Local files verification failed; private evidence {log.name}")
        return result.stdout.strip()

    def api_python(source):
        ast.parse(source)
        return run([*compose, "exec", "-T", "api", "python", "-c", source])

    run([*compose, "up", "--build", "-d", "--wait", "--wait-timeout", "180"])
    fixture_path = ROOT / ".cache/stage5-synthetic-fixture.json"
    previous = json.loads(fixture_path.read_text(encoding="utf-8")) if fixture_path.exists() else {}
    if previous.get("project") == project:
        fixture = {key: previous[key] for key in ("email", "password")}
    else:
        fixture = json.loads(
            api_python("""
import json,secrets
from app.config import Settings
from app.database import make_engine
from app.identity_service import Identity
settings=Settings(); engine=make_engine(settings); password=secrets.token_urlsafe(24)
Identity(engine,settings).bootstrap('admin@example.com',password)
print(json.dumps({'email':'admin@example.com','password':password}))
engine.dispose()
""")
        )
    fixture_path.write_text(json.dumps({**fixture, "project": project}), encoding="utf-8")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def headers():
        values = {
            "Origin": ORIGIN,
            "Content-Type": "application/json",
            "Cookie": "; ".join(f"{cookie.name}={cookie.value}" for cookie in jar),
        }
        values["X-CSRF-Token"] = next(
            (cookie.value for cookie in jar if cookie.name == "pc_csrf_dev"), ""
        )
        return values

    def request(path, method="GET", body=None, expected=200):
        req = urllib.request.Request(
            ORIGIN + "/api" + path,
            method=method,
            headers=headers(),
            data=json.dumps(body or {}).encode() if method != "GET" else None,
        )
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == expected, (path, response.status)
            result = response.read()
            return json.loads(result) if result else None

    def upload(name, data=None, size=None, **options):
        size = len(data) if data is not None else size
        metadata = {"name": name, "size_bytes": size, **options}
        prefix = (
            b'--verification\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'
            + json.dumps(metadata).encode()
            + b'\r\n--verification\r\nContent-Disposition: form-data; name="file"; '
            b'filename="ignored"\r\n\r\n'
        )
        connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=300)
        connection.putrequest("POST", "/api/uploads")
        values = headers()
        values["Content-Type"] = "multipart/form-data; boundary=verification"
        values["Transfer-Encoding"] = "chunked"
        for name, value in values.items():
            connection.putheader(name, value)
        connection.endheaders()

        def send(chunk):
            connection.send(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")

        send(prefix)
        remaining = size
        while remaining:
            amount = min(65536, remaining)
            send(
                data[size - remaining : size - remaining + amount]
                if data is not None
                else b"x" * amount
            )
            remaining -= amount
        send(b"\r\n--verification--\r\n")
        connection.send(b"0\r\n\r\n")
        response = connection.getresponse()
        body = response.read()
        status = response.status
        connection.close()
        assert status == 201, (status, body.decode(errors="replace"))
        return json.loads(body)

    def checksum(item):
        connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=120)
        connection.request("GET", f"/api/items/{item['id']}/download", headers=headers())
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type") == "application/octet-stream"
        assert response.getheader("Content-Disposition").startswith("attachment;")
        result = hashlib.sha256()
        size = 0
        while chunk := response.read(65536):
            result.update(chunk)
            size += len(chunk)
        connection.close()
        assert size == item["size_bytes"] and result.hexdigest() == item["checksum_sha256"]
        return result.hexdigest()

    request("/auth/login", "POST", fixture)
    parent = request(
        "/folders", "POST", {"name": "Stage 4 verification " + uuid.uuid4().hex[:8]}, 201
    )
    payload = bytes(range(256)) * 1025 + b"\x00\xffinert binary"
    original = upload("original.bin", payload, parent_id=parent["id"])
    checksum(original)
    replaced = upload(
        "original.bin",
        b"replacement",
        parent_id=parent["id"],
        collision="replace",
        target_id=original["id"],
        expected_revision=1,
        confirm_replace=True,
    )
    assert replaced["id"] == original["id"] and replaced["revision"] == 2
    recovery = next(item for item in request("/trash") if item["replacement_of"] == original["id"])
    restored = request(
        f"/items/{recovery['id']}/restore",
        "POST",
        {"expected_revision": 1, "name": "recovered.bin"},
    )
    assert checksum(restored) == hashlib.sha256(payload).hexdigest()
    moved = request(
        f"/items/{restored['id']}",
        "PATCH",
        {"expected_revision": restored["revision"], "name": "persisted.bin"},
    )
    image = io.BytesIO()
    Image.new("RGB", (24, 24), "blue").save(image, format="PNG")
    icon_headers = {**headers(), "Content-Type": "application/octet-stream"}
    icon_request = urllib.request.Request(
        ORIGIN + f"/api/items/{moved['id']}/icon?expected_revision={moved['revision']}",
        data=image.getvalue(),
        headers=icon_headers,
        method="PUT",
    )
    with opener.open(icon_request, timeout=30) as response:
        assert response.status == 200
        moved = json.load(response)
        assert moved["has_icon"] is True

    def icon_checksum():
        req = urllib.request.Request(ORIGIN + f"/api/items/{moved['id']}/icon", headers=headers())
        with opener.open(req, timeout=30) as response:
            assert response.headers["Content-Type"] == "image/png"
            return hashlib.sha256(response.read()).hexdigest()

    icon_hash = icon_checksum()
    preview_item = upload("preview.png", image.getvalue(), parent_id=parent["id"])
    req = urllib.request.Request(
        ORIGIN + f"/api/items/{preview_item['id']}/preview", headers=headers()
    )
    with opener.open(req, timeout=30) as response:
        assert response.status == 200 and response.headers["Content-Type"] == "image/png"
        with Image.open(io.BytesIO(response.read())) as decoded:
            assert decoded.size == (24, 24)
    print(
        "PASS: real binary transfer, replacement recovery, rename and safe custom icon/preview",
        flush=True,
    )

    remove = upload("pending-delete.bin", b"pending", parent_id=parent["id"])
    remove = request(f"/items/{remove['id']}/trash", "POST", {"expected_revision": 1})
    identifier = remove["id"]
    restrict = f"""
import uuid
from sqlalchemy import text
from app.config import Settings
from app.database import make_engine
from app.file_store import FileStore
settings=Settings(); engine=make_engine(settings)
with engine.connect() as connection:
    query='SELECT b.storage_key FROM blobs b JOIN items i ON i.blob_id=b.id WHERE i.id=:id'
    key=connection.scalar(text(query),{{'id':uuid.UUID('{identifier}')}})
FileStore(settings.storage_root).paths(key)[1].parent.chmod(0o500)
engine.dispose()
"""
    api_python(restrict)
    job = request(
        f"/trash/{identifier}", "DELETE", {"expected_revision": remove["revision"], "confirm": True}
    )
    assert job["state"] == "pending" and job["last_error"] == "storage_unavailable"
    run([*compose, "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180"])
    assert request(f"/admin/deletions/{job['id']}")["state"] == "pending"
    assert checksum(moved) == hashlib.sha256(payload).hexdigest()
    assert icon_checksum() == icon_hash
    api_python(restrict.replace("0o500", "0o700"))
    run([*compose, "exec", "-T", "api", "python", "-m", "app.reconcile"])
    assert request(f"/admin/deletions/{job['id']}")["state"] == "complete"
    print(
        "PASS: bytes/session and pending deletion survive recreation; retry completes",
        flush=True,
    )

    run_id = uuid.uuid4().hex[:12]
    archive = f"/srv/storage/verification-{run_id}.tar"
    restored_db = f"cloud_test_files_{run_id}"
    run([*compose, "stop", "api"])
    # API is stopped: no application writer can race this small test snapshot.
    run(
        [
            *compose,
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "api",
            "python",
            "-c",
            f"import tarfile; t=tarfile.open('{archive}','w'); "
            "t.add('/srv/storage/.objects',arcname='.objects'); t.close()",
        ]
    )
    dump = f"/tmp/files-{run_id}.dump"
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
    run([*compose, "exec", "-T", "database", "createdb", "-U", "postgres", restored_db])
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
            restored_db,
            dump,
        ]
    )
    run([*compose, "start", "--wait", "api"])
    verify = f"""
import hashlib,tarfile,uuid
from pathlib import Path

from PIL import Image
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine
from app.config import Settings
from app.database import make_engine
from app.file_store import FileStore
settings=Settings()
url=make_url(settings.database_url.get_secret_value()).set(database='{restored_db}')
restored=Path('/srv/storage/.restore-{run_id}')
restored.mkdir()
with tarfile.open('{archive}') as archive:
    assert all(entry.name=='.objects' or entry.name.startswith('.objects/')
               for entry in archive.getmembers())
    archive.extractall(restored,filter='data')
engine=create_engine(url,hide_parameters=True)
with engine.connect() as connection:
    query=('SELECT b.storage_key,b.size_bytes,b.checksum_sha256 FROM blobs b '
           'JOIN items i ON i.blob_id=b.id WHERE i.id=:id')
    row=connection.execute(text(query),{{'id':uuid.UUID('{moved["id"]}')}}).mappings().one()
    with FileStore(restored).open(row['storage_key'],row['size_bytes']) as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()==row['checksum_sha256']
    icon_query=('SELECT b.storage_key,b.size_bytes,b.checksum_sha256 FROM blobs b '
           'JOIN items i ON i.icon_blob_id=b.id WHERE i.id=:id')
    icon_row=connection.execute(text(icon_query),{{'id':uuid.UUID('{moved["id"]}')}}).mappings().one()
    with FileStore(restored).open(icon_row['storage_key'],icon_row['size_bytes']) as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()==icon_row['checksum_sha256']
    assert icon_row['checksum_sha256']=='{icon_hash}'
    assert connection.scalar(text("SELECT count(*) FROM users WHERE active AND role='admin'"))==1
engine.dispose()
print('isolated metadata and file snapshot restored with matching checksum')
"""
    api_python(verify)
    print(
        "PASS: isolated PostgreSQL/file snapshot restore has matching checksum",
        flush=True,
    )

    def memory():
        return int(
            api_python(
                "from pathlib import Path; lines=Path('/proc/1/status').read_text().splitlines(); "
                "print(next(line.split()[1] for line in lines if line.startswith('VmHWM:')))"
            )
        )

    before = memory()
    large = upload("500MB-boundary.bin", size=500_000_000, parent_id=parent["id"])
    checksum(large)
    after = memory()
    assert after - before < 96 * 1024, (before, after)
    removed = request(f"/items/{large['id']}/trash", "POST", {"expected_revision": 1})
    assert (
        request(
            f"/trash/{large['id']}",
            "DELETE",
            {"expected_revision": removed["revision"], "confirm": True},
        )["state"]
        == "complete"
    )
    print(
        f"PASS: Linux 500 MB roundtrip; API peak RSS {before} -> {after} KiB",
        flush=True,
    )
    request("/auth/logout", "POST", expected=204)
    request("/items", expected=401)
    report = {
        "passed": True,
        "project": project,
        "binary_roundtrip": True,
        "replacement_recovery": True,
        "container_recreation": True,
        "pending_delete_recovery": True,
        "isolated_db_file_restore": True,
        "custom_icon_preview_persistence_restore": True,
        "actual_file_bytes": 500_000_000,
        "api_peak_rss_before_kib": before,
        "api_peak_rss_after_kib": after,
    }
    (evidence / "files-acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "File/media Linux acceptance passed. Synthetic preview retained; no volumes removed.",
        flush=True,
    )


if __name__ == "__main__":
    main()
