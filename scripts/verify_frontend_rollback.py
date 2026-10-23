"""Exercise previous/current LOCAL immutable frontend images on isolated loopback ports."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-image", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", args.previous_image):
        raise SystemExit("Supply an already-built immutable local image ID")
    latest = json.loads((ROOT / ".cache/compose-latest.json").read_text())
    assert latest["passed"] and latest["project"] == "cloud-stage5-92c8e356b3cb"
    docker = shutil.which("docker")
    assert docker

    def command(*arguments):
        return subprocess.check_output([docker, *arguments], cwd=ROOT, stderr=subprocess.PIPE)

    endpoint = command("context", "inspect", "--format", "{{.Endpoints.docker.Host}}").decode()
    assert endpoint.strip().startswith(("npipe://", "unix://"))
    frontend = (
        command(
            "compose",
            "--project-name",
            latest["project"],
            "--env-file",
            ".env",
            "ps",
            "-q",
            "frontend",
        )
        .decode()
        .strip()
    )
    current = json.loads(command("inspect", frontend))[0]
    network = latest["project"] + "_private"
    assert network in current["NetworkSettings"]["Networks"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    reports = []
    for image in (args.previous_image, current["Image"]):
        assert json.loads(command("image", "inspect", image))[0]["Config"]["User"] == "10001:10001"
        run_id = uuid.uuid4().hex[:12]
        name = "cloud-stage7-rollback-" + run_id
        container = None
        try:
            container = (
                command(
                    "run",
                    "-d",
                    "--pull",
                    "never",
                    "--name",
                    name,
                    "--label",
                    "mycloud.stage7.rollback=" + run_id,
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--tmpfs",
                    "/data:uid=10001,gid=10001,mode=0700",
                    "--tmpfs",
                    "/config:uid=10001,gid=10001,mode=0700",
                    "--network",
                    network,
                    "-p",
                    "127.0.0.1::8080",
                    image,
                )
                .decode()
                .strip()
            )
            data = json.loads(command("inspect", container))[0]
            assert all(mount["Type"] == "tmpfs" for mount in data["Mounts"])
            binding = data["NetworkSettings"]["Ports"]["8080/tcp"][0]
            assert binding["HostIp"] == "127.0.0.1"
            origin = "http://127.0.0.1:" + str(int(binding["HostPort"]))
            for attempt in range(30):
                try:
                    with opener.open(origin + "/api/health/ready", timeout=2) as response:
                        assert json.load(response)["status"] == "ready"
                    break
                except (OSError, urllib.error.HTTPError):
                    if attempt == 29:
                        raise
                    time.sleep(0.2)
            with opener.open(origin, timeout=5) as response:
                html = response.read().decode()
            asset = re.search(r'src="(/assets/[a-zA-Z0-9_.-]+\.js)"', html).group(1)
            with opener.open(origin + asset, timeout=5) as response:
                asset_hash = hashlib.sha256(response.read()).hexdigest()
            try:
                opener.open(origin + "/api/auth/me", timeout=5)
                raise AssertionError("Anonymous access unexpectedly allowed")
            except urllib.error.HTTPError as error:
                assert error.code == 401
            reports.append(
                {
                    "image": image,
                    "asset": asset,
                    "asset_sha256": asset_hash,
                    "ready": True,
                    "anonymous_auth_denied": True,
                }
            )
        finally:
            if container:
                owned = json.loads(command("inspect", container))[0]
                assert owned["Config"]["Labels"]["mycloud.stage7.rollback"] == run_id
                assert all(mount["Type"] == "tmpfs" for mount in owned["Mounts"])
                command("rm", "--force", container)
    evidence = ROOT / ".local/stage7-security"
    evidence.mkdir(exist_ok=True)
    (evidence / "frontend-rollback.json").write_text(json.dumps(reports, indent=2))
    print("PASS: previous/current frontend images serve assets/health; anonymous auth denied")


if __name__ == "__main__":
    main()
