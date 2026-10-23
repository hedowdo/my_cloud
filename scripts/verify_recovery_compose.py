"""Real encrypted DB/blob/config recovery in the exact synthetic loopback preview.

Briefly stops only its API to capture consistency; restores into a NEW database/path.
Never drops source databases, deletes volumes, installs schedules or contacts cloud APIs.
"""

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
from pathlib import Path

from recovery_bundle import digest, inventory, open_bundle, run_job

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpg", type=Path, required=True)
    args = parser.parse_args()
    latest = json.loads((ROOT / ".cache/compose-latest.json").read_text(encoding="utf-8"))
    fixture = json.loads(
        (ROOT / ".cache/stage5-synthetic-fixture.json").read_text(encoding="utf-8")
    )
    if (
        not latest.get("passed")
        or latest["project"] != "cloud-stage5-92c8e356b3cb"
        or fixture["project"] != latest["project"]
        or fixture["email"] != "admin@example.com"
        or os.environ.get("DOCKER_HOST")
    ):
        raise SystemExit("Requires the exact synthetic local preview and local Docker context")
    docker = shutil.which("docker")
    if not docker:
        raise SystemExit("Docker executable is required")
    compose = [docker, "compose", "--project-name", latest["project"], "--env-file", ".env"]
    run_id = uuid.uuid4().hex[:12]
    evidence = ROOT / ".local/stage7-recovery" / run_id
    evidence.mkdir(mode=0o700, parents=True)
    snapshot = evidence / "snapshot"
    snapshot.mkdir(mode=0o700)

    def command(arguments, **options):
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            check=False,
            capture_output=False,
            stdout=options.pop("stdout", subprocess.PIPE),
            stderr=subprocess.PIPE,
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            **options,
        )
        if result.returncode:
            log = evidence / ("private-error-" + uuid.uuid4().hex + ".log")
            log.write_bytes(result.stderr)
            log.chmod(0o600)
            raise RuntimeError("Local recovery command failed; inspect private evidence")
        return result.stdout

    endpoint = command([docker, "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"])
    if not endpoint.decode().strip().startswith(("npipe://", "unix://")):
        raise SystemExit("Refusing a nonlocal Docker endpoint")

    def query(sql, database="cloud"):
        return (
            command(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "psql",
                    "-X",
                    "-U",
                    "postgres",
                    "-d",
                    database,
                    "-At",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    sql,
                ]
            )
            .decode()
            .strip()
        )

    def hashes(database="cloud"):
        tables = json.loads(
            query(
                "SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables "
                "WHERE schemaname='public'",
                database,
            )
        )
        if any(not re.fullmatch("[a-z_][a-z0-9_]*", name) for name in tables):
            raise RuntimeError("Unexpected schema identifier")
        selects = [
            f"SELECT '{table}' AS name,count(*) AS rows,"
            f"md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) "
            f'AS digest FROM "{table}" t'
            for table in tables
        ]
        return json.loads(
            query(
                "SELECT json_agg(row_to_json(t) ORDER BY name) FROM ("
                + " UNION ALL ".join(selects)
                + ") t",
                database,
            )
        )

    size = int(
        command(
            [
                *compose,
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                "from pathlib import Path; "
                "print(sum(p.stat().st_size for d in ['.objects','.staging'] "
                "for p in (Path('/srv/storage')/d).rglob('*') if p.is_file()))",
            ]
        )
    )
    if size > 64_000_000:
        raise SystemExit("Local fixture exceeds 64 MB; not a full-size backup driver")
    key = secrets.token_urlsafe(48).encode()
    key_path = evidence / "synthetic-recovery.key"
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    offline_start = time.monotonic()
    try:
        command([*compose, "stop", "api"])
        expected = hashes()
        with (snapshot / "database.dump").open("xb") as stream:
            command(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "pg_dump",
                    "-U",
                    "postgres",
                    "-d",
                    "cloud",
                    "-Fc",
                ],
                stdout=stream,
            )
        files = snapshot / "files"
        files.mkdir(mode=0o700)
        for directory in (".objects", ".staging"):
            command([*compose, "cp", "api:/srv/storage/" + directory, str(files / directory)])
        config = snapshot / "configuration"
        config.mkdir(mode=0o700)
        shutil.copyfile(ROOT / ".env", config / "development.env")
        (config / "development.env").chmod(0o600)
        # Preserve recoverable source/config while the app is not yet a published Git release.
        names = command(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
        for name in names.decode().split("\0"):
            if not name or not (ROOT / name).is_file():
                continue
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or (ROOT / relative).is_symlink():
                raise RuntimeError("Unsafe source path")
            destination = config / "release-source" / relative
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        (snapshot / "table-hashes.json").write_text(json.dumps(expected), encoding="utf-8")
    finally:
        command([*compose, "start", "--wait", "api"])
    offline_seconds = time.monotonic() - offline_start
    inventory(snapshot, limit=64_000_000)
    repository = evidence / "encrypted-repository"
    result = run_job(snapshot, repository, key, args.gpg)
    index = json.loads((repository / "index.json").read_text())
    bundle = repository / index[-1]["id"]
    restored = evidence / "isolated-restored"
    restore_start = time.monotonic()
    open_bundle(bundle, restored, key, args.gpg)
    assert inventory(snapshot) == inventory(restored)
    restored_database = "cloud_stage7_restore_" + run_id
    command(
        [
            *compose,
            "exec",
            "-T",
            "database",
            "createdb",
            "-U",
            "postgres",
            "--owner=cloud_migrator",
            restored_database,
        ]
    )
    with (restored / "database.dump").open("rb") as stream:
        command(
            [
                *compose,
                "exec",
                "-T",
                "database",
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                restored_database,
                "--no-owner",
                "--role=cloud_migrator",
                "--exit-on-error",
            ],
            stdin=stream,
        )
    assert hashes(restored_database) == expected
    assert (
        query(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
            "AND tableowner<>'cloud_migrator'",
            restored_database,
        )
        == "0"
    )
    query(
        f'REVOKE ALL ON DATABASE "{restored_database}" FROM PUBLIC; '
        f'GRANT CONNECT ON DATABASE "{restored_database}" TO cloud_app,cloud_migrator',
        restored_database,
    )
    query(
        "SET ROLE cloud_migrator; CREATE TABLE stage7_migration_probe(id integer); "
        "ALTER TABLE stage7_migration_probe ADD COLUMN checked boolean; "
        "DROP TABLE stage7_migration_probe",
        restored_database,
    )
    restored_path = "/srv/storage/.stage7-rehearsal-" + run_id
    assert re.fullmatch(r"/srv/storage/\.stage7-rehearsal-[a-f0-9]{12}", restored_path)
    # Restore as the existing unprivileged API user; never relax cap_drop or chown live storage.
    transport = evidence / "verified-files.tar"
    with tarfile.open(transport, "w") as archive:
        for name, row in inventory(restored / "files").items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = row["bytes"], 0o600
            with (restored / "files" / name).open("rb") as stream:
                archive.addfile(info, stream)
    restore_files = """import shutil,sys,tarfile
from pathlib import Path,PurePosixPath
root=Path(sys.argv[1]);root.mkdir(mode=0o700)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
 for member in archive:
  path=PurePosixPath(member.name)
  assert member.isfile() and not path.is_absolute() and '..' not in path.parts
  assert path.parts[0] in {'.objects','.staging'}
  target=root.joinpath(*path.parts);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with target.open('xb') as out,archive.extractfile(member) as source:shutil.copyfileobj(source,out)
print('Verified file snapshot restored as unprivileged API user')
"""
    with transport.open("rb") as stream:
        command(
            [*compose, "exec", "-T", "api", "python", "-c", restore_files, restored_path],
            stdin=stream,
        )
    verification = """import hashlib,json,sys,uuid
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from app.config import Settings
from app.file_store import FileStore
from app.file_service import Files
from app.identity_service import Identity
from app.identity_security import LoginInput
data=json.load(sys.stdin)
s=Settings();assert s.app_env=='development' and s.insecure_loopback_cookies
url=make_url(s.database_url.get_secret_value()).set(database=data['database'])
engine=create_engine(url,hide_parameters=True)
store=FileStore(Path(data['storage']))
with engine.connect() as c:
 rows=c.execute(text("SELECT DISTINCT b.storage_key,b.size_bytes,b.checksum_sha256 "
 "FROM blobs b JOIN items i ON (i.blob_id=b.id OR i.icon_blob_id=b.id) "
 "WHERE b.state='durable' AND i.deletion_job_id IS NULL")).mappings().all()
 for row in rows:
  with store.open(row['storage_key'],row['size_bytes']) as stream:
   assert hashlib.file_digest(stream,'sha256').hexdigest()==row['checksum_sha256']
identity=Identity(engine,s)
_,session,_=identity.login(LoginInput(email=data['email'],password=data['password']),None,
                         'stage7-isolated-restore',uuid.uuid4())
assert identity.me(session)['user']['role']=='admin'
files=Files(engine,identity,s)
assert files.browse(session,uuid.UUID('00000000-0000-0000-0000-000000000001'))
print(json.dumps({'checked_durable_blobs':len(rows),'restored_admin_access':True}))
engine.dispose()
"""
    details = json.loads(
        command(
            [*compose, "exec", "-T", "api", "python", "-c", verification],
            input=json.dumps(
                {
                    "database": restored_database,
                    "storage": restored_path,
                    "email": fixture["email"],
                    "password": fixture["password"],
                }
            ).encode(),
        )
    )
    report = {
        "passed": True,
        "project": latest["project"],
        "tables": len(expected),
        "table_rows": {row["name"]: row["rows"] for row in expected},
        "all_table_hashes_exact": True,
        "restored_tables_owned_by_migrator": True,
        "restored_migration_create_alter_drop": True,
        "all_snapshot_file_hashes_exact": True,
        "encrypted_bundle_sha256": digest(bundle),
        "snapshot_files": result["files"],
        "snapshot_bytes": result["bytes"],
        "api_offline_seconds": offline_seconds,
        "restore_seconds": time.monotonic() - restore_start,
        "restored_database": restored_database,
        **details,
        "local_rehearsal_not_native_oci": True,
    }
    (evidence / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": True,
                "evidence": str(evidence.relative_to(ROOT)),
                "tables": len(expected),
                **details,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
