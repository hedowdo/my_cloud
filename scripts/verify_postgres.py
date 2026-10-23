"""Run real migration/restart/backup/restore checks in a NEW disposable local cluster.

Supply official PostgreSQL bin directory. No installer, system service or cloud connection.
Leaves ignored evidence under .local/verification; always stops its own cluster.
"""

import argparse
import os
import secrets
import socket
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", type=Path, required=True)
    binaries = parser.parse_args().bin_dir.resolve()
    suffix = ".exe" if os.name == "nt" else ""
    for executable in ("initdb", "pg_ctl", "pg_dump", "pg_restore"):
        if not (binaries / (executable + suffix)).is_file():
            raise SystemExit(f"Missing PostgreSQL executable: {executable}")
    run_id = uuid.uuid4().hex[:12]
    workspace = ROOT / ".local" / "verification" / run_id
    workspace.mkdir(parents=True)
    cluster = workspace / "cluster"
    password = secrets.token_hex(24)
    pwfile = workspace / "init-password"
    pwfile.write_text(password, encoding="utf-8")
    pwfile.chmod(0o600)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    database = f"cloud_test_{run_id}"
    # This tool only constructs its own loopback target, never accepts an arbitrary DSN.
    env = {**os.environ, "PGPASSWORD": password, "PYTHONPATH": str(ROOT / "backend")}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def run(
        args: list[str], extra_env: dict[str, str] | None = None, *, history_guard=False
    ) -> None:
        # Windows PostgreSQL children can inherit output handles after pg_ctl exits.
        # A file avoids waiting for pipe EOF from the long-running server process.
        log = workspace / f"command-{uuid.uuid4().hex}.log"
        with log.open("w", encoding="utf-8") as output:
            completed = subprocess.run(
                args,
                cwd=ROOT,
                env={**env, **(extra_env or {})},
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                timeout=900,
            )
        if history_guard:
            diagnostic = log.read_text(encoding="utf-8")
            if completed.returncode == 0 or not any(
                message in diagnostic
                for message in ("Security history exists", "File lifecycle data exists")
            ):
                raise RuntimeError("Populated identity downgrade was not refused as expected")
            return
        if completed.returncode:
            # Output may include DSNs; keep raw diagnostics private in ignored local evidence.
            (workspace / "failed-command.log").write_text(
                log.read_text(encoding="utf-8"), encoding="utf-8"
            )
            raise RuntimeError("Verification command failed; private local evidence retained")

    def binary(name: str) -> str:
        return str(binaries / (name + suffix))

    def admin_connection(dbname: str = "postgres"):
        return psycopg.connect(
            host="127.0.0.1",
            port=port,
            user="cloud_test_admin",
            password=password,
            dbname=dbname,
            autocommit=True,
        )

    def start() -> None:
        run(
            [
                binary("pg_ctl"),
                "-D",
                str(cluster),
                "-l",
                str(workspace / "postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {port}",
                "-w",
                "start",
            ]
        )

    running = False
    try:
        run(
            [
                binary("initdb"),
                "-D",
                str(cluster),
                "-U",
                "cloud_test_admin",
                "--encoding=UTF8",
                "--locale=C",
                "--auth=scram-sha-256",
                "--pwfile",
                str(pwfile),
            ]
        )
        pwfile.unlink()  # Named generated file only; no recursive deletion.
        start()
        running = True
        with admin_connection() as connection:
            for role in ("cloud_migrator", "cloud_app"):
                connection.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
                    ).format(sql.Identifier(role), sql.Literal(password))
                )
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        with admin_connection(database) as connection:
            connection.execute("ALTER SCHEMA public OWNER TO cloud_migrator")
            connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            connection.execute("GRANT USAGE ON SCHEMA public TO cloud_app")
            connection.execute("""ALTER DEFAULT PRIVILEGES FOR ROLE cloud_migrator IN SCHEMA public
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cloud_app""")
        migrator = f"postgresql+psycopg://cloud_migrator:{password}@127.0.0.1:{port}/{database}"
        runtime = f"postgresql+psycopg://cloud_app:{password}@127.0.0.1:{port}/{database}"
        migration_env = {"MIGRATION_DATABASE_URL": migrator}
        migrate = [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini"]
        run([*migrate, "upgrade", "head"], migration_env)
        run([*migrate, "upgrade", "head"], migration_env)
        test_env = {"TEST_RUNTIME_DATABASE_URL": runtime, "TEST_DISPOSABLE_DATABASE_NAME": database}
        run([sys.executable, "-m", "pytest", "-q"], test_env)
        print("PASS: initial/idempotent migration, runtime-role constraints and ready endpoint")
        marker_id = uuid.uuid4()
        engine = create_engine(runtime, hide_parameters=True)
        with engine.begin() as connection:
            connection.execute(
                text("""INSERT INTO items (id,parent_id,kind,name,name_key)
                    VALUES (:id,'00000000-0000-0000-0000-000000000001',
                    'folder','recovery evidence','recovery evidence')"""),
                {"id": marker_id},
            )
        engine.dispose()
        run([binary("pg_ctl"), "-D", str(cluster), "-m", "fast", "-w", "stop"])
        running = False
        start()
        running = True

        def assert_marker() -> None:
            with create_engine(runtime, hide_parameters=True).connect() as connection:
                if (
                    connection.scalar(
                        text("SELECT count(*) FROM items WHERE id=:id"), {"id": marker_id}
                    )
                    != 1
                ):
                    raise RuntimeError("Persistence/recovery marker missing")

        assert_marker()
        print("PASS: PostgreSQL process restart preserves committed metadata")
        run(
            [
                sys.executable,
                "-c",
                """
import secrets
from app.config import Settings
from app.database import make_engine
from app.identity_service import Identity
settings=Settings()
engine=make_engine(settings)
Identity(engine,settings).bootstrap('recovery@example.com',secrets.token_urlsafe(24))
engine.dispose()
""",
            ],
            {"DATABASE_URL": runtime},
        )
        recovery_reservation = uuid.uuid4()
        with create_engine(runtime, hide_parameters=True).begin() as connection:
            connection.execute(
                text("""INSERT INTO upload_reservations
                (id,user_id,parent_id,reserved_bytes,state,expires_at,intent)
                SELECT :id,id,NULL,0,'aborted',
                    now()+interval '1 hour',jsonb_build_object('recovery_fixture',true)
                FROM users WHERE email_key='recovery@example.com'"""),
                {"id": recovery_reservation},
            )
        dump = workspace / "disposable.dump"
        conn_args = ["-h", "127.0.0.1", "-p", str(port), "-U", "cloud_migrator", "-d", database]
        run([binary("pg_dump"), *conn_args, "-Fc", "-f", str(dump)])
        run([*migrate, "downgrade", "base"], migration_env, history_guard=True)
        with create_engine(runtime, hide_parameters=True).begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0005_media_cleanup"
            )
            # Only this harness-created recovery fixture, in this new disposable cluster.
            connection.execute(
                text("DELETE FROM upload_reservations WHERE id=:id"), {"id": recovery_reservation}
            )
            connection.execute(text("DELETE FROM activity WHERE action='bootstrap'"))
            connection.execute(text("DELETE FROM users WHERE email_key='recovery@example.com'"))
        print("PASS: populated lifecycle downgrade refused without changing schema")
        run([*migrate, "downgrade", "base"], migration_env)
        run([*migrate, "upgrade", "head"], migration_env)
        print("PASS: disposable downgrade/base and fresh re-upgrade")
        run([binary("pg_restore"), *conn_args, "--clean", "--if-exists", "--no-owner", str(dump)])
        assert_marker()
        with create_engine(runtime, hide_parameters=True).begin() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM users WHERE email_key='recovery@example.com'")
                )
                == 1
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM upload_reservations WHERE id=:id"),
                    {"id": recovery_reservation},
                )
                == 1
            )
            connection.execute(
                text("DELETE FROM upload_reservations WHERE id=:id"), {"id": recovery_reservation}
            )
        run([sys.executable, "-m", "pytest", "-q"], test_env)
        print("PASS: real pg_dump/pg_restore recovers metadata and application readiness")
    finally:
        if running:
            run([binary("pg_ctl"), "-D", str(cluster), "-m", "fast", "-w", "stop"])
    print("Disposable cluster stopped; evidence retained under ignored .local/verification.")


if __name__ == "__main__":
    main()
