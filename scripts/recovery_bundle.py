"""Bounded, encrypted LOCAL recovery rehearsal; not a 100 GB production backup driver.

Uses an operator-supplied GnuPG executable and an independent high-entropy recovery key.
No cloud, network, scheduler installation, external alert delivery or existing-data restore.
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

LIMIT = 256_000_000  # Deliberately bounded local rehearsal, not a full-size cloud strategy.
MAX_FILES = 10_000


class RecoveryError(Exception):
    pass


def sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in name.split("/"))
        or any(char in name for char in "\\:\x00")
        or any(part.rstrip(" .") != part for part in path.parts)
        or any(
            re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?", p) for p in path.parts
        )
    ):
        raise RecoveryError("unsafe_archive_path")
    return path


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise RecoveryError("unsafe_directory")


def inventory(source, limit=LIMIT):
    if source.is_symlink() or not source.is_dir():
        raise RecoveryError("invalid_source")
    rows, total = {}, 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise RecoveryError("symlink_source")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RecoveryError("nonregular_source")
        name = path.relative_to(source).as_posix()
        safe_name(name)
        size = path.stat().st_size
        total += size
        if total > limit or len(rows) >= MAX_FILES:
            raise RecoveryError("rehearsal_capacity_exceeded")
        rows[name] = {"bytes": size, "sha256": digest(path)}
    if not rows:
        raise RecoveryError("empty_snapshot")
    return rows


def gpg_path(binary, path):
    value = Path(path).as_posix()
    if os.name == "nt" and Path(binary).parent.parent.name == "usr":
        return "/" + value[0].lower() + value[2:]
    return value


def gpg_file(binary, key, source, target, *, decrypt=False, limit=LIMIT):
    # A short OS-private directory avoids the verified Windows agent socket path limit.
    with tempfile.TemporaryDirectory(prefix="pc-gpg-") as temporary:
        home = Path(temporary)
        try:
            return _gpg_file(binary, home, key, source, target, decrypt=decrypt, limit=limit)
        finally:
            control = Path(binary).with_name("gpgconf.exe" if os.name == "nt" else "gpgconf")
            if control.is_file():
                with suppress(OSError, subprocess.SubprocessError):
                    subprocess.run(
                        [str(control), "--homedir", gpg_path(binary, home), "--kill", "gpg-agent"],
                        check=False,
                        timeout=10,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )


def _gpg_file(binary, home, key, source, target, *, decrypt=False, limit=LIMIT):
    if len(key) < 32 or b"\n" in key or b"\r" in key:
        raise RecoveryError("recovery_key_requires_32_random_bytes_without_newlines")
    private_directory(home)

    command = [
        str(binary),
        "--no-options",
        "--homedir",
        gpg_path(binary, home),
        "--batch",
        "--pinentry-mode",
        "loopback",
        "--no-symkey-cache",
        "--passphrase-fd",
        "0",
        "--output",
        gpg_path(binary, target),
    ]
    if decrypt:
        command += ["--max-output", str(limit + 2_000_000), "--decrypt", gpg_path(binary, source)]
    else:
        command += [
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "--s2k-mode",
            "3",
            "--s2k-digest-algo",
            "SHA256",
            "--compress-algo",
            "none",
            gpg_path(binary, source),
        ]
    result = subprocess.run(
        command,
        input=key + b"\n",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=300,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        # Do not log GPG output, paths, config contents or key material.
        raise RecoveryError("decrypt_or_integrity_failed" if decrypt else "encryption_failed")


def validate_archive(archive, limit=LIMIT):
    entries = archive.getmembers()
    if len(entries) > MAX_FILES + 1 or any(not entry.isfile() for entry in entries):
        raise RecoveryError("invalid_archive_members")
    names = [entry.name for entry in entries]
    if len(set(names)) != len(names) or "manifest.json" not in names:
        raise RecoveryError("invalid_archive_manifest")
    total = 0
    for entry in entries:
        safe_name(entry.name)
        total += entry.size
        if total > limit + 2_000_000:
            raise RecoveryError("restore_capacity_exceeded")
    member = archive.getmember("manifest.json")
    if member.size > 2_000_000:
        raise RecoveryError("manifest_too_large")
    try:
        manifest = json.load(archive.extractfile(member))
        rows = manifest["files"]
        if manifest["version"] != 1 or set(names) != {"manifest.json", *rows}:
            raise ValueError
        for name, row in rows.items():
            entry = archive.getmember(name)
            if not name.startswith("snapshot/") or entry.size != row["bytes"]:
                raise ValueError
            with archive.extractfile(entry) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
                    raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise RecoveryError("manifest_checksum_mismatch") from error
    return rows


def publish_directory(source, destination, *, attempts=None):
    attempts = min(6, max(1, attempts if attempts is not None else (6 if os.name == "nt" else 1)))
    for attempt in range(attempts):
        if destination.exists() or destination.is_symlink():
            raise RecoveryError("restore_destination_changed")
        try:
            source.rename(destination)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.1 * (attempt + 1))


def open_bundle(bundle, destination, key, binary, *, limit=LIMIT):
    if destination.exists() or destination.is_symlink():
        raise RecoveryError("restore_requires_new_destination")
    private_directory(destination.parent)
    if bundle.stat().st_size > limit + 4_000_000:
        raise RecoveryError("encrypted_bundle_too_large")
    with tempfile.TemporaryDirectory(prefix="restore-", dir=destination.parent) as tmp:
        work = Path(tmp)
        plain = work / "decrypted.tar"
        gpg_file(binary, key, bundle, plain, decrypt=True, limit=limit)
        with tarfile.open(plain, "r:") as archive:
            rows = validate_archive(archive, limit)
            restored = work / "verified"
            restored.mkdir(mode=0o700)
            # All members/checksums validated before any file is exposed to the caller.
            for name in rows:
                output = restored.joinpath(*PurePosixPath(name).parts[1:])
                output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with output.open("xb") as target, archive.extractfile(name) as source:
                    shutil.copyfileobj(source, target, 1_048_576)
                output.chmod(0o600)
        publish_directory(restored, destination)
    return rows


def seal_bundle(source, target, key, binary, *, limit=LIMIT):
    source = source.resolve(strict=True)
    if target.exists() or target.is_symlink() or target.resolve().is_relative_to(source):
        raise RecoveryError("invalid_bundle_destination")
    rows = inventory(source, limit)
    private_directory(target.parent)
    required = sum(row["bytes"] for row in rows.values()) * 3 + 8_000_000
    if shutil.disk_usage(target.parent).free < required:
        raise RecoveryError("destination_full")
    with tempfile.TemporaryDirectory(prefix="capture-", dir=target.parent) as tmp:
        work = Path(tmp)
        plain, encrypted = work / "snapshot.tar", work / "snapshot.gpg"
        with tarfile.open(plain, "w", format=tarfile.PAX_FORMAT) as archive:
            data = json.dumps(
                {"version": 1, "files": {"snapshot/" + k: v for k, v in rows.items()}}
            ).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mode = len(data), 0o600
            archive.addfile(info, io.BytesIO(data))
            for name, row in rows.items():
                info = tarfile.TarInfo("snapshot/" + name)
                info.size, info.mode = row["bytes"], 0o600
                with (source / name).open("rb") as stream:
                    archive.addfile(info, stream)
        if inventory(source, limit) != rows:
            raise RecoveryError("snapshot_changed_during_capture")
        gpg_file(binary, key, plain, encrypted)
        open_bundle(encrypted, work / "roundtrip", key, binary, limit=limit)
        encrypted.chmod(0o600)
        with encrypted.open("r+b") as stream:
            os.fsync(stream.fileno())
        # Hard link creation refuses an existing final target, including concurrent creation.
        os.link(encrypted, target)
        sync_directory(target.parent)
    return {
        "sha256": digest(target),
        "files": len(rows),
        "bytes": sum(row["bytes"] for row in rows.values()),
    }


def rotation_plan(points, new_id, volume):
    """Provider-independent policy; inventory MUST include all boot/data backup resources."""
    if len(points) > 5 or len({point["id"] for point in points}) != len(points):
        raise RecoveryError("invalid_backup_inventory")
    new = next((p for p in points if p["id"] == new_id), None)
    if not new or new["state"] != "AVAILABLE" or not new["managed"] or new["volume"] != volume:
        raise RecoveryError("new_backup_not_verified")
    eligible = sorted(
        (p for p in points if p["managed"] and p["volume"] == volume and p["state"] == "AVAILABLE"),
        key=lambda p: (p["captured_at"], p["id"]),
    )
    if eligible[-1]["id"] != new_id:
        raise RecoveryError("new_backup_not_latest")
    return [p["id"] for p in eligible[:-4]]


def capture_allowed(points):
    if len(points) >= 5 or any(p["state"] not in {"AVAILABLE", "FAULTY"} for p in points):
        raise RecoveryError("no_verified_free_backup_slot")


def atomic_json(path, data):
    partial = path.with_name(path.name + "." + uuid.uuid4().hex + ".partial")
    with partial.open("x", encoding="utf-8") as stream:
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    partial.chmod(0o600)
    os.replace(partial, path)
    sync_directory(path.parent)


def monitor(state, now=None):
    now = time.time() if now is None else now
    captured = state.get("last_good_at")
    if not captured or now - captured > 26 * 3600:
        return "missed_or_stale_backup"
    if state.get("status") != "complete":
        return "backup_failed_or_interrupted"
    return "healthy"


def run_job(source, repository, key, binary):
    """One local rehearsal capture; never installs a timer or calls a provider."""
    if repository.resolve().is_relative_to(source.resolve()):
        raise RecoveryError("repository_inside_snapshot")
    private_directory(repository)
    lock = repository / "job.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RecoveryError("job_locked_operator_review_required") from error
    os.close(descriptor)
    state_path, index_path = repository / "state.json", repository / "index.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    started = time.time()
    try:
        index = json.loads(index_path.read_text()) if index_path.exists() else []
        key_id = hashlib.sha256(key).hexdigest()[:16]
        if {p.name for p in repository.glob("point-*.gpg")} != {p["id"] for p in index}:
            raise RecoveryError("unindexed_recovery_point_operator_review")
        for point in index:
            if point.get("key_id") != key_id:
                raise RecoveryError("recovery_key_changed_operator_review")
            if not re.fullmatch(r"point-[a-f0-9]{32}\.gpg", point["id"]):
                raise RecoveryError("invalid_repository_index")
            if digest(repository / point["id"]) != point["sha256"]:
                raise RecoveryError("existing_backup_corruption")
        capture_allowed(index)
        state.update(status="running", started_at=started)
        atomic_json(state_path, state)
        name = "point-" + uuid.uuid4().hex + ".gpg"
        result = seal_bundle(source, repository / name, key, binary)
        point = {
            "id": name,
            "key_id": key_id,
            "sha256": result["sha256"],
            "captured_at": started,
            "state": "AVAILABLE",
            "managed": True,
            "volume": "local-rehearsal",
        }
        index.append(point)
        # Publish new verified point before retention. An interrupted rotation leaves five intact.
        atomic_json(index_path, index)
        remove = rotation_plan(index, name, "local-rehearsal")
        for identifier in remove:
            (repository / identifier).unlink()
        atomic_json(index_path, [p for p in index if p["id"] not in remove])
        state.update(
            status="complete",
            last_good_at=started,
            duration_seconds=time.time() - started,
            latest_id=name,
        )
        state.pop("reason", None)
        atomic_json(state_path, state)
        return result
    except Exception as error:
        state.update(
            status="failed",
            reason=str(error) if isinstance(error, RecoveryError) else "operational_failure",
        )
        atomic_json(state_path, state)
        atomic_json(
            repository / "alert.json",
            {"event": "backup_failed", "at": time.time(), "reason": state["reason"]},
        )
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["seal", "open", "run", "check"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--gpg", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check":
            state_file = args.target / "state.json"
            state = json.loads(state_file.read_text()) if state_file.exists() else {}
            event = monitor(state)
            if event != "healthy":
                private_directory(args.target)
                atomic_json(args.target / "alert.json", {"event": event, "at": time.time()})
            print(json.dumps({"health": event, "checked_at": datetime.now(UTC).isoformat()}))
            return 0 if event == "healthy" else 3
        if not args.source or not args.key_file or not args.gpg:
            parser.error("source, key-file and gpg are required for captures/restores")
        key = args.key_file.read_bytes().rstrip(b"\r\n")
        operation = {"seal": seal_bundle, "open": open_bundle, "run": run_job}[args.command]
        result = operation(args.source, args.target, key, args.gpg)
        print(
            json.dumps(
                {
                    "result": "verified",
                    "entries": len(result) if args.command == "open" else result["files"],
                }
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "result": "failed",
                    "reason": str(error)
                    if isinstance(error, RecoveryError)
                    else "operational_failure",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
