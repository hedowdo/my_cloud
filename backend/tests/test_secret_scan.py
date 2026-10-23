import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "scan_secrets.py"
spec = importlib.util.spec_from_file_location("secret_scan", MODULE)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def test_scanner_flags_credentials_but_not_safe_templates():
    private_key = b"-----BEGIN " + b"PRIVATE KEY-----"
    assert scanner.findings(private_key) == ["private key"]
    generated_url = b"postgresql+psycopg://cloud:" + b"a" * 48 + b"@localhost/cloud"
    assert scanner.findings(generated_url) == ["database credential"]
    assert not scanner.findings(b"POSTGRES_PASSWORD=\nDATABASE_URL=\n")
    assert not scanner.findings(b"\x00binary")
