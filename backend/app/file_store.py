"""Generated-key filesystem operations, isolated from metadata and user names."""

import os
import re
import shutil
import stat


class FileStore:
    def __init__(self, root):
        self.root = root.resolve()
        self.staging = self.directory(self.root / ".staging")
        self.objects = self.directory(self.root / ".objects")

    def directory(self, path):
        if path.is_symlink():
            raise OSError("Private storage directory must not be a symbolic link")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.is_dir() or path.is_symlink():
            raise OSError("Invalid private storage directory")
        return path

    def paths(self, key):
        if not re.fullmatch("[a-f0-9]{64}", key):
            raise ValueError("Invalid private storage key")
        parent = self.directory(self.objects / key[:2])
        return self.staging / key, parent / key

    def create(self, key):
        staging, _ = self.paths(key)
        descriptor = os.open(
            staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        return os.fdopen(descriptor, "wb", buffering=0)

    def free(self):
        return shutil.disk_usage(self.root).free

    def sync_dir(self, directory):
        if os.name != "nt":
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def publish(self, key):
        staging, final = self.paths(key)
        if staging.is_symlink() or final.exists() or final.is_symlink():
            raise OSError("Unsafe storage finalization")
        os.replace(staging, final)
        self.sync_dir(final.parent)
        self.sync_dir(self.staging)

    def open(self, key, expected_size):
        _, final = self.paths(key)
        descriptor = os.open(final, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        stream = os.fdopen(descriptor, "rb")
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size or final.is_symlink():
            stream.close()
            raise OSError("File integrity check failed")
        return stream

    def discard(self, key):
        for path in self.paths(key):
            if path.is_symlink():
                raise OSError("Unsafe private storage path")
            path.unlink(missing_ok=True)
            self.sync_dir(path.parent)
