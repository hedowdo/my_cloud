import hashlib
import io
import json
import os
import tarfile
from pathlib import Path

import pytest
from scripts import recovery_bundle as recovery


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "a/../b",
        "C:/file",
        "a\\b",
        "a//b",
        "a/./b",
        "NUL",
        "com1.txt",
        "a/b.",
    ],
)
def test_restore_rejects_unsafe_cross_platform_paths(name):
    with pytest.raises(recovery.RecoveryError):
        recovery.safe_name(name)


def archive_bytes(entries):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w") as archive:
        for name, data, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    result.seek(0)
    return result


@pytest.mark.parametrize(
    "variant", ["checksum", "missing", "duplicate", "link", "traversal", "size", "capacity"]
)
def test_restore_rejects_corruption_links_missing_files_and_capacity(variant):
    payload = b"original content"
    row = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    entries = [("snapshot/file", payload, tarfile.REGTYPE)]
    if variant == "checksum":
        row["sha256"] = "0" * 64
    elif variant == "size":
        row["bytes"] += 1
    elif variant == "missing":
        entries = []
    elif variant == "duplicate":
        entries *= 2
    elif variant == "link":
        entries[0] = ("snapshot/file", payload, tarfile.SYMTYPE)
    elif variant == "traversal":
        entries[0] = ("../escape", payload, tarfile.REGTYPE)
    manifest = json.dumps({"version": 1, "files": {"snapshot/file": row}}).encode()
    entries.append(("manifest.json", manifest, tarfile.REGTYPE))
    with (
        tarfile.open(fileobj=archive_bytes(entries), mode="r:") as archive,
        pytest.raises(recovery.RecoveryError),
    ):
        recovery.validate_archive(archive, -2_000_000 if variant == "capacity" else recovery.LIMIT)


def point(number, **changes):
    return {
        "id": str(number),
        "managed": True,
        "volume": "data",
        "state": "AVAILABLE",
        "captured_at": number,
        **changes,
    }


def test_global_slots_and_verified_four_plus_one_rotation():
    points = [point(i) for i in range(4)]
    recovery.capture_allowed(points)
    with pytest.raises(recovery.RecoveryError):
        recovery.capture_allowed([*points, point(4)])
    assert recovery.rotation_plan([*points, point(4)], "4", "data") == ["0"]
    assert (
        recovery.rotation_plan(
            [point(0, managed=False), *[point(i) for i in range(1, 5)]], "4", "data"
        )
        == []
    )
    with pytest.raises(recovery.RecoveryError):
        recovery.rotation_plan([*points, point(4, state="FAULTY")], "4", "data")
    with pytest.raises(recovery.RecoveryError):
        recovery.capture_allowed([point(0, state="CREATING")])


def test_monitor_detects_missing_missed_and_interrupted_jobs():
    assert recovery.monitor({}, 200_000) == "missed_or_stale_backup"
    assert recovery.monitor({"last_good_at": 1, "status": "complete"}, 200_000) != "healthy"
    assert recovery.monitor({"last_good_at": 190_000, "status": "running"}, 200_000) != "healthy"
    assert recovery.monitor({"last_good_at": 190_000, "status": "failed"}, 200_000) != "healthy"
    assert recovery.monitor({"last_good_at": 190_000, "status": "complete"}, 200_000) == "healthy"


def fake_seal(source, target, key, binary):
    target.write_bytes(b"synthetic verified ciphertext " + target.name.encode())
    return {"files": 1, "bytes": 1, "sha256": recovery.digest(target)}


def test_rotation_runs_only_after_verified_capture_and_failure_preserves_points(
    tmp_path, monkeypatch
):
    original_seal = recovery.seal_bundle
    monkeypatch.setattr(recovery, "seal_bundle", fake_seal)
    repository = tmp_path / "repository"
    source = tmp_path / "source"
    source.mkdir()
    (source / "payload").write_bytes(b"synthetic")
    for _ in range(5):
        recovery.run_job(source, repository, b"test", "test")
    index = json.loads((repository / "index.json").read_text())
    assert len(index) == 4
    assert len(list(repository.glob("point-*.gpg"))) == 4
    previous = {p["id"]: (repository / p["id"]).read_bytes() for p in index}
    with pytest.raises(recovery.RecoveryError, match="key_changed"):
        recovery.run_job(source, repository, b"different recovery key", "test")
    assert json.loads((repository / "index.json").read_text()) == index
    monkeypatch.setattr(recovery, "seal_bundle", original_seal)
    monkeypatch.setattr(recovery.shutil, "disk_usage", lambda p: type("Usage", (), {"free": 0})())
    with pytest.raises(recovery.RecoveryError, match="destination_full"):
        recovery.run_job(source, repository, b"test", "test")
    assert json.loads((repository / "alert.json").read_text())["reason"] == "destination_full"
    assert previous == {p["id"]: (repository / p["id"]).read_bytes() for p in index}

    def interrupted(*args, **kwargs):
        args[1].write_bytes(b"unindexed interrupted capture")
        raise OSError("private diagnostic must not enter alert")

    monkeypatch.setattr(recovery, "seal_bundle", interrupted)
    with pytest.raises(OSError):
        recovery.run_job(source, repository, b"test", "test")
    assert previous == {p["id"]: (repository / p["id"]).read_bytes() for p in index}
    assert json.loads((repository / "alert.json").read_text())["reason"] == "operational_failure"
    assert "private diagnostic" not in (repository / "alert.json").read_text()
    assert not (repository / "job.lock").exists()
    with pytest.raises(recovery.RecoveryError, match="unindexed"):
        recovery.run_job(source, repository, b"test", "test")


def test_interrupted_lock_blocks_overlapping_job_and_repository_cannot_contain_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(recovery.RecoveryError, match="repository_inside"):
        recovery.run_job(source, source / "repo", b"key", "gpg")
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "job.lock").touch()
    with pytest.raises(recovery.RecoveryError, match="locked"):
        recovery.run_job(source, repository, b"key", "gpg")


def test_destination_full_inventory_limit_and_existing_restore_are_safe(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_bytes(b"payload")
    with pytest.raises(recovery.RecoveryError, match="capacity"):
        recovery.inventory(source, limit=1)
    monkeypatch.setattr(recovery.shutil, "disk_usage", lambda p: type("Usage", (), {"free": 0})())
    with pytest.raises(recovery.RecoveryError, match="destination_full"):
        recovery.seal_bundle(source, tmp_path / "copy.gpg", b"key", "gpg")
    assert not (tmp_path / "copy.gpg").exists()
    with pytest.raises(recovery.RecoveryError, match="new_destination"):
        recovery.open_bundle(tmp_path / "copy.gpg", source, b"key", "gpg")
    assert (source / "data").read_bytes() == b"payload"


@pytest.mark.skipif(
    not os.environ.get("RECOVERY_GPG"), reason="requires explicitly supplied local GPG"
)
def test_real_encryption_restore_wrong_key_and_ciphertext_corruption(tmp_path):
    binary = Path(os.environ["RECOVERY_GPG"])
    source = tmp_path / "source"
    source.mkdir()
    secret = b"synthetic-recovery-configuration-and-blob"
    (source / ".env").write_bytes(secret)
    (source / "files").mkdir()
    (source / "files/data.bin").write_bytes(bytes(range(256)) * 100)
    key = b"b" * 48
    bundle = tmp_path / "point.gpg"
    result = recovery.seal_bundle(source, bundle, key, binary)
    assert result["files"] == 2
    assert secret not in bundle.read_bytes()
    restored = tmp_path / "restored"
    recovery.open_bundle(bundle, restored, key, binary)
    assert recovery.inventory(source) == recovery.inventory(restored)
    with pytest.raises(recovery.RecoveryError):
        recovery.open_bundle(bundle, tmp_path / "wrong-key", b"c" * 48, binary)
    assert not (tmp_path / "wrong-key").exists()
    corrupted = bytearray(bundle.read_bytes())
    corrupted[len(corrupted) // 2] ^= 1
    broken = tmp_path / "broken.gpg"
    broken.write_bytes(corrupted)
    with pytest.raises(recovery.RecoveryError):
        recovery.open_bundle(broken, tmp_path / "corrupt-restore", key, binary)
    assert not (tmp_path / "corrupt-restore").exists()


def test_transient_publish_denial_retries_without_overwriting_existing_destination(
    tmp_path, monkeypatch
):
    source = tmp_path / "verified"
    source.mkdir()
    (source / "file").write_bytes(b"verified")
    target = tmp_path / "restored"
    rename = Path.rename
    attempts = []

    def temporarily_locked(path, destination):
        if path == source and len(attempts) < 2:
            attempts.append(True)
            raise PermissionError("synthetic transient publish denial")
        return rename(path, destination)

    monkeypatch.setattr(Path, "rename", temporarily_locked)
    monkeypatch.setattr(recovery.time, "sleep", lambda delay: None)
    recovery.publish_directory(source, target, attempts=3)
    assert (target / "file").read_bytes() == b"verified"
    source.mkdir()
    (source / "another").write_bytes(b"new")
    with pytest.raises(recovery.RecoveryError, match="destination_changed"):
        recovery.publish_directory(source, target, attempts=3)
    assert (source / "another").read_bytes() == b"new" and (
        target / "file"
    ).read_bytes() == b"verified"
