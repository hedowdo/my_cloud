"""Create random local credentials; never overwrite an existing environment file."""

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    path = ROOT / ".env"
    if "--add-auth-secret" in sys.argv:
        existing = path.read_text(encoding="utf-8")
        if any(line.startswith("AUTH_RATE_SECRET=") for line in existing.splitlines()):
            print("Existing authentication secret preserved.")
            return
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"\nAUTH_RATE_SECRET={secrets.token_hex(32)}\n")
        print("Added random local authentication secret; database credentials preserved.")
        return
    administrator, migrator, application = (secrets.token_hex(24) for _ in range(3))
    contents = (
        "# Generated development-only configuration; never use in production.\n"
        f"POSTGRES_PASSWORD={administrator}\n"
        f"MIGRATION_PASSWORD={migrator}\n"
        f"APP_DATABASE_PASSWORD={application}\n"
        f"DATABASE_URL=postgresql+psycopg://cloud_app:{application}@127.0.0.1:5432/cloud\n"
        f"MIGRATION_DATABASE_URL=postgresql+psycopg://cloud_migrator:{migrator}"
        "@127.0.0.1:5432/cloud\n"
        "STORAGE_ROOT=.local/storage\nAPP_ENV=development\n"
        f"AUTH_RATE_SECRET={secrets.token_hex(32)}\n"
    )
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit("Existing .env preserved; no changes made") from None
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(contents)
    print("Created ignored .env with random local-only credentials (values not printed).")


if __name__ == "__main__":
    main()
