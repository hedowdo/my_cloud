"""Read-only production checks. Never provisions, mounts, formats or starts services."""

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path


def read_configuration(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z_]+", key) or key in values:
            raise ValueError("Use unique plain KEY=value configuration entries")
        if not value or any(char in value for char in "\"'$`\r\n"):
            raise ValueError("Quoted, expanded or empty values are not supported")
        values[key] = value
    return values


def validate_configuration(values: dict[str, str]) -> None:
    hostname = values.get("CLOUD_HOST", "")
    if (
        len(hostname) > 253
        or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", hostname)
        or hostname.endswith((".local", ".localhost", ".internal", ".test"))
    ):
        raise ValueError("Set a public lowercase DNS hostname; availability is checked separately")
    for name in ("DATABASE_IMAGE", "API_IMAGE", "FRONTEND_IMAGE"):
        if not re.fullmatch(r"(?:[a-zA-Z0-9./:_-]+@)?sha256:[0-9a-f]{64}", values.get(name, "")):
            raise ValueError(f"{name} must identify an approved immutable image")
    secrets = []
    for name in (
        "POSTGRES_PASSWORD",
        "MIGRATION_PASSWORD",
        "APP_DATABASE_PASSWORD",
        "AUTH_RATE_SECRET",
    ):
        value = values.get(name, "")
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"{name} must contain 64 random hexadecimal characters")
        secrets.append(value)
    if len(set(secrets)) != len(secrets):
        raise ValueError("Database and application secrets must be independent")
    root = values.get("DATA_ROOT", "")
    if not re.fullmatch(r"/srv/[a-z0-9-]+", root):
        raise ValueError("DATA_ROOT must be a dedicated mount directly below /srv")
    pool = values.get("STORAGE_POOL_BYTES", "")
    reserve = values.get("STORAGE_RESERVE_BYTES", "")
    if not pool.isdecimal() or not 1 <= int(pool) <= 100_000_000_000:
        raise ValueError("The pool must remain within the approved 100 GB target")
    if not reserve.isdecimal() or int(reserve) < 10_000_000_000:
        raise ValueError("Production requires at least 10 GB emergency reserve")


def validate_host(values: dict[str, str], config: Path) -> None:
    if os.name != "posix":
        raise ValueError("Host acceptance requires the actual Linux deployment host")
    if stat.S_IMODE(config.stat().st_mode) & 0o077:
        raise ValueError("Production secret configuration must have mode 0600 or stricter")
    root = Path(values["DATA_ROOT"])
    if root.is_symlink() or not root.is_mount():
        raise ValueError("The data volume must already be mounted; boot-disk fallback is refused")
    expected_uuid = values.get("DATA_VOLUME_UUID", "")
    if not re.fullmatch(r"[0-9a-fA-F-]{16,64}", expected_uuid):
        raise ValueError("Record the independently verified data-filesystem UUID")
    actual_uuid = subprocess.check_output(
        ["findmnt", "-n", "-o", "UUID", "--target", str(root)], text=True, timeout=10
    ).strip()
    if actual_uuid.lower() != expected_uuid.lower():
        raise ValueError("Mounted data-filesystem UUID does not match the approved volume")
    for name, uid in (("files", 10001), ("caddy", 10001), ("postgres", 999)):
        child = root / name
        if child.is_symlink() or not child.is_dir() or child.stat().st_uid != uid:
            raise ValueError(
                f"The {name} directory has not been safely prepared on the data volume"
            )
        if stat.S_IMODE(child.stat().st_mode) & 0o077:
            raise ValueError(f"The {name} directory must be private (mode 0700)")
    usage = shutil.disk_usage(root)
    pool, reserve = int(values["STORAGE_POOL_BYTES"]), int(values["STORAGE_RESERVE_BYTES"])
    if usage.total < pool + reserve + 20_000_000_000 or usage.free < reserve + 5_000_000_000:
        raise ValueError("Measured filesystem capacity/headroom does not support the proposed pool")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument(
        "--host", action="store_true", help="Also verify actual Linux mounts/permissions"
    )
    args = parser.parse_args()
    try:
        values = read_configuration(args.env_file)
        validate_configuration(values)
        if args.host:
            validate_host(values, args.env_file)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SystemExit(
            "Preflight failed; review private configuration, mount and permissions"
        ) from None
    print(
        json.dumps(
            {
                "configuration_valid": True,
                "linux_host_verified": args.host,
                "cloud_eligibility_verified": False,
                "deployment_authorized": False,
            }
        )
    )


if __name__ == "__main__":
    main()
