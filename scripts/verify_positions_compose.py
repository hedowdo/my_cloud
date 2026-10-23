"""Preserve and restore shared positions in the exact disposable localhost preview."""

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    latest = json.loads((ROOT / ".cache/compose-latest.json").read_text(encoding="utf-8"))
    project = latest["project"]
    if not latest.get("passed") or not project.startswith("cloud-stage5-"):
        raise SystemExit("Requires an exact passing disposable preview")
    docker = shutil.which("docker")
    if not docker:
        docker = str(
            Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/resources/bin/docker.exe"
        )
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def run(args, **kwargs):
        return subprocess.run(
            [docker, *args],
            cwd=ROOT,
            check=True,
            creationflags=flags,
            stderr=subprocess.PIPE,
            timeout=240,
            **kwargs,
        )

    endpoint = (
        run(
            ["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], stdout=subprocess.PIPE
        )
        .stdout.decode()
        .strip()
    )
    if not endpoint.startswith(("npipe://", "unix://")):
        raise SystemExit("Refusing a nonlocal Docker context")
    compose = ["compose", "--project-name", project, "--env-file", ".env"]
    query = """SELECT coalesce(json_agg(row_to_json(p) ORDER BY p.item_id),'[]'::json)
    FROM (SELECT item_id,x,y,revision,updated_by,updated_at FROM positions) p"""

    def positions(database="cloud"):
        return json.loads(
            run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    database,
                    "-tA",
                    "-c",
                    query,
                ],
                stdout=subprocess.PIPE,
            ).stdout
        )

    evidence = ROOT / ".local/stage6-recovery" / uuid.uuid4().hex[:12]
    evidence.mkdir(parents=True)
    restored = "cloud_stage6_restore_" + uuid.uuid4().hex[:12]
    try:
        run([*compose, "stop", "api"], stdout=subprocess.PIPE)
        expected = positions()
        if not expected:
            raise RuntimeError("Run real spatial browser workflows before recovery acceptance")
        with (evidence / "positions.dump").open("wb") as output:
            run(
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
                stdout=output,
            )
        run(
            [*compose, "exec", "-T", "database", "createdb", "-U", "postgres", restored],
            stdout=subprocess.PIPE,
        )
        with (evidence / "positions.dump").open("rb") as source:
            run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "database",
                    "pg_restore",
                    "-U",
                    "postgres",
                    "-d",
                    restored,
                    "--no-owner",
                ],
                stdin=source,
                stdout=subprocess.PIPE,
            )
        assert positions(restored) == expected
    finally:
        run(
            [*compose, "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180"],
            stdout=subprocess.PIPE,
        )
    assert positions() == expected
    (evidence / "result.json").write_text(
        json.dumps(
            {
                "passed": True,
                "project": project,
                "positions": len(expected),
                "restored_database": restored,
                "exact_position_revisions_actors_timestamps": True,
                "all_container_recreation": True,
                "isolated_postgres_restore": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"PASS: {len(expected)} positions survive recreation and isolated database restore")
    print(f"Evidence: {evidence.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
