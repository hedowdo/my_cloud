"""Small offline guard for common credential formats; reports paths, never matched values."""

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "database credential": re.compile(rb"postgres(?:ql)?(?:\+psycopg)?://[^\s:@]+:[a-f0-9]{32,}@"),
}


def findings(data: bytes) -> list[str]:
    if b"\x00" in data:
        return []
    return [label for label, rule in RULES.items() if rule.search(data)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    staged = parser.parse_args().staged
    command = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"]
        if staged
        else ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    paths = subprocess.check_output(command, cwd=ROOT).decode().split("\x00")
    detected = False
    for name in sorted(set(filter(None, paths))):
        path = ROOT / name
        if name.startswith(".env") and name != ".env.example":
            print(f"Blocked environment file: {name}")
            detected = True
            continue
        if staged:
            data = subprocess.check_output(["git", "show", f":{name}"], cwd=ROOT)
        elif path.is_file():
            data = path.read_bytes()
        else:
            continue
        for label in findings(data):
            detected = True
            print(f"Potential {label}: {name}")
    if not detected:
        print("Secret pattern scan passed (heuristic; manual review still required).")
    return int(detected)


if __name__ == "__main__":
    raise SystemExit(main())
