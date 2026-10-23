# Personal Cloud

Private shared storage for 1–5 invited users. Private identity, durable file services, a responsive file manager and shared spatial dashboard are implemented and tested locally. Features include safe previews/icons, activity, Recycle Bin, administrator controls, shared draggable placement, keyboard access, reduced motion and a mobile list/grid fallback.

**Deployment status (2026-10-23):** OCI infrastructure and immutable ARM64 release artifacts are prepared, and an initial native data-volume backup is verified AVAILABLE. The website is **not live**, and no production administrator exists. Automatic daily backups/rotation, a full native restore, external alerts and final public HTTPS/restart acceptance remain unfinished. Local recovery tooling is a bounded rehearsal, not the production backup worker. See [current plan](docs/plan.md), [deployment procedure](docs/deployment.md) and [backup evidence](docs/first-native-backup-approval.md).

## Local prerequisites

- Python 3.12, Node 24 and pnpm 11.25.0.
- Docker Engine with Compose v2 (Docker Desktop is free for personal use under its published eligibility rules). No Docker cloud subscription or account upgrade is required.
- Read `AGENTS.md` and `docs/plan.md` before changes.

## Start with Docker Compose

```powershell
python scripts/init_dev.py
docker compose up --build -d
docker compose ps
```

Open `http://127.0.0.1:8080`. API liveness: `http://127.0.0.1:8000/api/health/live`; readiness: `/api/health/ready`; development OpenAPI: `/docs`. All published ports bind only to loopback. PostgreSQL is not published. Compose runs the versioned migration as a separate one-shot service before the API starts. The runtime DB role cannot create schema objects.

For an existing Stage 2 `.env`, run `python scripts/init_dev.py --add-auth-secret` once; this adds a random authentication rate-key secret while preserving all existing database passwords.

The initializer generates random **local-only** passwords in ignored `.env`, refuses to overwrite existing configuration and never prints credentials. Do not copy local passwords into production. An existing PostgreSQL volume keeps the passwords from first initialization; changing `.env` is not a password-rotation procedure.

`docker compose down` stops/removes containers while preserving named database/file volumes. **Do not add `--volumes`/`-v`** unless deliberately deleting approved disposable local data. Check `docs/testing.md` for persistence and recovery verification. Do not publish this foundation on the internet: public TLS, hardening, recovery and cloud cost gates remain open, and local HTTP is deliberate.

## Create the first administrator

For a fresh local stack, run the interactive command below. In a named test project, include its exact `--project-name` before `exec`. Enter your email and choose a unique password in the terminal; hidden password prompts require a real terminal. No default account exists, and bootstrap refuses a database with any users.

```powershell
docker compose exec -it api python -m app.bootstrap
```

Sign in at `http://127.0.0.1:8080`. Administrators can create a single-use 24-hour invitation, copy it and share it privately. The link is shown once. Five registered accounts total, including deactivated accounts; deactivation signs out that person. The verification preview contains synthetic test accounts, not your personal account. Use a fresh personal stack and this interactive bootstrap for real local use. Keep real data outside the development/test preview.

## Development and checks

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements-dev.lock
pnpm install --frozen-lockfile
pnpm build
pnpm lint
pnpm format:check
.venv/Scripts/python.exe -m ruff check backend scripts
.venv/Scripts/python.exe -m ruff format --check backend scripts
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/scan_secrets.py
.venv/Scripts/python.exe -m pre_commit install
```

Activate the venv before committing so the local secret-scanning pre-commit hook uses its Python. The heuristic scanner catches common keys/generated database credentials; it complements manual review and does not prove no secrets exist. Dependency locks pin installed versions/hashes; regenerate and audit intentionally, not during application startup.

For frontend iteration against the loopback API, run `pnpm dev` and open its reported localhost address. Native backend development can run `.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log` against an explicitly configured local PostgreSQL connection. No SQLite substitute is used.

## Documentation

- `docs/architecture.md`: schema, transactions, service boundaries and future feature contracts.
- `docs/api.md`: implemented endpoints versus planned authenticated API.
- `docs/security.md`: development boundary and security requirements.
- `docs/testing.md`: executable checks and honest verification status.
- `docs/stage-3-implementation.md`: authorized identity scope and security defaults.
- `docs/stage-3-verification.md`: Stage 3 acceptance evidence and limitations.
- `docs/stage-2-compose-verification.md`: completed local acceptance, fixes and desktop/mobile evidence.
- `docs/dependencies.md`: dependency purpose, licensing and audit procedure.
- `docs/plan.md`: stage checklists, approvals and evidence.
- `docs/zero-cost-policy.md`: strict $0 hosting policy; local setup is not cloud provisioning approval.


## Stage 4 local file backend

The file API is documented in `docs/api.md` and development OpenAPI. Uploads stream metadata JSON followed by file bytes as multipart, with actual 500,000,000-byte maximum, authenticated private downloads, collision/recovery, folders, trash/restore and administrator-only permanent deletion. Stage 5 provides the browser file manager described below.

Local defaults are a 1,000,000,000-byte shared test pool and a 2,000,000,000-byte emergency reserve. Compose accepts STORAGE_POOL_BYTES/STORAGE_RESERVE_BYTES from local configuration; these do not establish 100 GB of cloud capacity. Trash/recovery bytes count toward the pool. Existing Stage 3 named volumes are preserved; migrations 0003_files and 0004_transfer_parents add file lifecycle support while preserving identity data. No default account is seeded. Do not apply destructive rollback to populated data.

To resume registered abandoned staging cleanup and already-confirmed pending deletion jobs in the exact intended local project:

```powershell
docker compose exec -T api python -m app.reconcile
```

The command never auto-purges ordinary trash. Preserve database and file volumes together. Daily encrypted off-server backups and actual OCI deployment remain later acceptance gates. See `docs/stage-4-implementation.md` and `docs/stage-4-verification.md`.

## Stage 5 file manager (local acceptance complete)

The signed-in application now has All files, Activity, shared Recycle Bin and administrator navigation; a responsive details panel; file/folder actions; upload/drop progress and explicit duplicate decisions; server-side name/type/uploader/date filters and stable sorting/pagination. Light/dark preference is saved to your account. The artistic spatial canvas remains Stage 6.

Open supported images/PDFs/videos in a centered preview; download originals for unsupported formats, large previews or incompatible codecs. Image previews accept PNG/JPEG/WebP up to 10 MB, PDFs up to 25 MB, and video supports browser-compatible MP4/WebM. Custom icons accept PNG/JPEG/WebP up to 2 MB; they are re-encoded to small metadata-free PNGs and counted against shared storage. Original uploads remain unchanged.

See docs/stage-5-implementation.md and docs/stage-5-verification.md for scope, test gates and actual evidence. No cloud deployment or 100 GB capacity claim. Do not treat a passing local snapshot test as scheduled daily backup completion.

Stage 6 is complete locally: [executed tests, performance and recovery](docs/stage-6-verification.md). Desktop defaults to spatial view; use List view for name scanning or dense folders. Mobile remains list/grid. Stage 7 security/daily backup readiness and Stage 8 approved OCI deployment remain pending.

The desktop dashboard now fills the screen with navigation closed. Open the floating menu for search, uploads, storage and account controls; file details appear as an overlay. The dashboard has no page scrolling; menus and mobile list views scroll internally. [Layout verification](docs/stage-6-immersive-layout.md).


The canvas is locked at 65% with no zoom adjustment. Drag nodes into the bottom-left rubbish bin to move them to the shared Recycle Bin; click that icon to browse and restore discarded items. Drag empty space to pan; More controls offers Recenter and keyboard-friendly pan buttons. Routine placement status no longer appears on the canvas. [Verification and limits](docs/stage-6-locked-canvas-trash.md).


Folders now open as lists by default; individual files retain previews. Use All files to return to the desktop canvas. [Folder navigation verification](docs/stage-6-folder-lists.md).


Stage 7 is in progress: Recycle Bin has a visible **← Dashboard** return. Local encrypted database/files/config recovery, ownership checks, failure policies, package/container review and rollback rehearsal passed. Native OCI daily backups, outside-VM alerts, full-size recovery and production gates remain open; no cloud resources were created. [Verification](docs/stage-7-verification.md), [recovery runbook](docs/recovery-runbook.md).


Stage 8 preparation is authorized: a separate production profile and local TLS/persistence/security rehearsal are implemented. Use [the deployment procedure](docs/deployment.md) and [executed evidence](docs/stage-8-verification.md); do not publish the development Compose stack. Cloud resource approval, real host/DNS/TLS and Stage 7 native backup/alert/recovery gates remain open. No cloud resources were created.
