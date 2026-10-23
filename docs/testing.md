# Local verification

Tests must run before their checklist gates are checked. Skipped integration tests are not passes. Current outcomes and blockers are appended to `plan.md` after execution.

Latest executed results: [native/source evidence](stage-2-verification.md) and [final Linux Compose acceptance](stage-2-compose-verification.md). All Stage 2 local gates passed on 2026-10-21; later feature/ARM64/production/cloud recovery tests remain open.

## Direct checks

Use README's locked installation commands. Run `pnpm build`, `pnpm lint`, `pnpm format:check`, Python Ruff lint/format, `python -m pytest -q`, `python scripts/scan_secrets.py`, `pnpm audit` and `python -m pip_audit`. Review licenses with `pnpm licenses list` and Python package metadata. Do not print environment files/DSNs or post raw diagnostics containing credentials.

Backend unit test verifies liveness during DB failure, private 503 readiness output, fresh request IDs, security headers and absence of unprotected feature routes. Offline scanner tests exercise fake secret fixtures and safe empty configuration. Integration tests require a disposable PostgreSQL DB prefixed `cloud_test_`; they prove no runtime DDL/superuser, database size constraints, transaction rollback and application/file-volume persistence across app recreation.

## Native disposable PostgreSQL rehearsal

If Docker is unavailable, PostgreSQL's official Windows download page links EDB portable binaries: [PostgreSQL Windows](https://www.postgresql.org/download/windows/), [EDB archives](https://www.enterprisedb.com/download-postgresql-binaries). These are local verification tools, not a replacement deployment architecture. Keep downloads/clusters ignored, never register a Windows service or bind outside loopback.

```powershell
.venv/Scripts/python.exe scripts/verify_postgres.py --bin-dir PATH_TO_POSTGRES_BIN
```

The harness creates its own new loopback cluster/database and random credentials, never accepts a remote DSN, runs Alembic empty/repeated upgrade and the full pytest suite, seeds disposable metadata, restarts PostgreSQL, checks persistence, takes a real pg_dump, rehearses downgrade/re-upgrade, restores and verifies records/readiness again. It stops its cluster in `finally`; evidence remains in ignored `.local/verification`. No recursive cleanup or production data deletion is performed. Raw diagnostic logs remain local/private. A failed step prevents later checks being reported as passed.

This validates actual PostgreSQL SQL/migration/recovery and process persistence on Windows; it cannot prove Docker build, Compose wiring, named-volume persistence or Linux ARM64 behavior.

## Required Compose gate

After an approved Docker Engine/Compose is available:

1. Initialize ignored local `.env`; run `docker compose config --quiet` (do not print expanded credentials). Build and start the stack; inspect `docker compose ps` and health endpoints.
2. Confirm DB private network, runtime UID and DB role; inspect only non-sensitive fields. Migration service must exit successfully before API/front health.
3. Create named disposable markers through a controlled test harness in both data stores; record checksums/IDs without secrets. Recreate the API/frontend/DB containers while preserving volumes; confirm markers survive and readiness passes. A process restart alone does not prove this gate.
4. Perform disposable migration backup/restore using the rehearsal design; never run `down -v` against actual data or remove volumes as a convenience.
5. Verify browser welcome shell, keyboard retry, narrow desktop/mobile viewport, API reachable/unavailable behavior; save screenshot evidence. No fake login/upload/actions should appear before later features.

Docker/WSL installation is outside repository file changes and can require administrator access/restart. Docker Desktop is free for personal use under [Docker's terms](https://www.docker.com/products/personal/); no paid cloud/build subscription is permitted. If unavailable, leave Compose checks open rather than swapping PostgreSQL for SQLite or claiming a container test passed.

### Windows prerequisite history — resolved 2026-10-21

Owner completed WSL installation and restarted. Verified WSL 3.0.3.0/default version 2; reran checksum/signature-verified Docker Desktop 4.95.0 per-user installer, which returned **exit 0 / Installation succeeded**. Local Docker Linux engine 29.8.2 (x86_64) and Compose v5.6.0 are running. The earlier prerequisite blocker below is historical. Subsequent Compose runtime acceptance also passed; see the final report above.

The verified Docker Desktop 4.95.0 per-user installer returned exit 1: Windows Virtual Machine Platform is disabled. Firmware virtualization is enabled, but this Windows feature still needs administrator setup. The attempted UAC elevation was canceled before WSL setup ran.

Owner action: open PowerShell **as administrator**, run `wsl --install --no-distribution`, then restart Windows manually when requested and ready. This installs WSL without an extra Ubuntu distribution. See [Microsoft's WSL command options](https://learn.microsoft.com/en-us/windows/wsl/basic-commands) and [Docker's Windows prerequisites](https://docs.docker.com/desktop/setup/install/windows-install/). No automatic restart was requested by this task.

Afterward, resume this task: verify WSL/Virtual Machine Platform, rerun the already downloaded and checksum/signature-verified `.cache/DockerDesktopInstaller.exe` with the approved per-user WSL backend, verify Docker engine/Compose and execute the open test gate. Docker Desktop is not claimed installed from the failed pre-check. No cloud account, paid Docker subscription or sign-in is required for this local setup.

`scripts/verify_compose.py` exercises a new local-only Docker project, refuses a remote Docker endpoint or occupied test ports, and checks clean build/start, API/proxy readiness, runtime UID/role/DDL restrictions, metadata/file markers after service-container recreation, and actual container pg_dump/restore into a new disposable database. Raw output stays in ignored `.local/compose-verification`; it leaves the test stack for browser inspection and never removes named volumes. A failing command prevents a passing result file.

## Stage 3 identity acceptance

The full PostgreSQL harness now runs identity tests too. Auth fixture cleanup requires both TEST_RUNTIME_DATABASE_URL targeting loopback cloud_test_* and an exactly matching TEST_DISPOSABLE_DATABASE_NAME supplied by the harness; it refuses other databases. Fixtures clear only their disposable identity records. Native suites prove Argon2id/cookie flags, generic login, session rotation/expiry/logout/revocation, CSRF/Origin/Host/JSON/actual-byte/strict-field checks, invitation lifecycle/concurrent redemption, concurrent last-slot registration, admin/member/anonymous isolation, deactivation, counter persistence/limits and private app logs.

`verify_compose.py` creates a fresh cloud-stage3-* test project. After its foundation checks, run `scripts/verify_identity_compose.py` to rebuild final source, bootstrap a random synthetic administrator only into the empty test database, exercise proxied login/invite/logout, recreate all containers with preserved volumes, and dump/restore active identity/session digests into a separate disposable database. It leaves synthetic browser fixtures privately under ignored .cache, never prints their values, and never resets existing accounts. Browser tests use these test accounts only. See stage-3-verification.md for executed outcomes and pending gates.

Stage 3 local acceptance is complete on 2026-10-21: [executed evidence and corrections](stage-3-verification.md). The final browser follow-up verified Cancel preserves the active account, Confirm deactivates and disables target controls, administrator logout succeeds, and deactivated login is rejected. No application changes were needed on that follow-up. Later file/cloud/release gates remain open.

## Stage 4 acceptance

`verify_postgres.py` now executes the file suite too: binary roundtrips/attachments, NFC/path/name checks, collision/replace/recovery/revisions, ancestor visibility/cycles/restore, member/admin/anonymous/CSRF isolation, actual streamed 499,999,999 / 500,000,000 / 500,000,001 byte boundaries, quota/global/user reservation races, disk-space loss, partial/malformed/underdeclared uploads, filesystem/DB/uncertain-commit failures, active-writer exclusion, deletion retry and interrupted downloads. Tests run only on guarded, harness-created local databases and fixture-owned file roots, and clean their own generated-key bytes. Full suites run before and after a real dump/restore; lifecycle-populated downgrade must refuse without changing the current revision.

`verify_compose.py` creates a fresh cloud-stage4-* project and tests Linux build/readiness/runtime restrictions, all-container persistence and DB restore. Then `verify_files_compose.py` exercises actual chunked HTTP binary upload/download and replacement recovery, an unlink failure across container recreation/retry, stopped-writer DB plus file snapshot restore into an isolated database/root, and a real 500,000,000-byte streamed HTTP upload/download while comparing the API process peak RSS. It removes only its synthetic large file through the authorized API and preserves all named volumes. Synthetic test credentials and raw logs remain ignored/private; repeat runs may reuse only that exact project's privately saved synthetic account. No cloud or real owner data is used.

A local test snapshot is supplemental evidence, not an automatic encrypted off-server backup. Executed outcomes, corrections and measured memory are in stage-4-verification.md.

## Stage 5 file-manager acceptance

The PostgreSQL harness includes filtered live-tree search/sorting/pagination, server Unicode collision probes, preview/range authorization, icon metadata stripping/revisions/limits, malicious icon rejection and durable retirement retry. Full tests still exercise real 499999999/500000000/500000001 streamed bytes before/after restoration. Revision 0005_media_cleanup is additive; its populated-head rollback guard is rehearsed before any destructive disposable rollback.

verify_compose.py now creates cloud-stage5-* projects; prior stage volumes are preserved. verify_files_compose.py accepts only a passing local harness, uses a privately saved exact-project synthetic administrator, and tests custom icon/PNG decoding and their file/database restoration in addition to prior transfer/recovery checks. It stores no real owner credentials and never resets an existing user.

Browser tests use development-only Playwright with the existing installed Chrome in an isolated headless profile. The interactive UI REPLs failed to initialize; no result is claimed from them. From the workspace run `pnpm --filter @personal-cloud/frontend exec node e2e/prepare-fixtures.mjs`, then after Linux file acceptance produces the exact-project fixture run `pnpm --filter @personal-cloud/frontend exec playwright test`. Assets are synthetic PNG, WebM and a two-page vector PDF with an embedded action; no real personal files. Tests refuse other projects. Browser artifacts/traces and test credentials stay under ignored .local/.cache; selected synthetic screenshots live in docs/evidence/stage5 for visual review. Tests exercise only localhost.

Explicitly mocked storage responses test the 80/90 warning presentation without filling the owner's disk; real reservation/quota/reserve enforcement is separately covered against PostgreSQL. Failure-injected browser network responses test retry/loading behavior, not actual cloud availability. Final executed outcomes and limitations: stage-5-verification.md.

## Stage 6 acceptance

The guarded native PostgreSQL harness includes independent coordinate/file revisions, first/subsequent concurrent writes, move-away-and-back stale drag rejection, two-member visibility, idempotent occupied-area initialization, finite coordinate/security/CSRF/parent/trash checks. Run the full harness before/after actual restore; see stage-6-verification.md for the final result.

Run `pnpm --filter @personal-cloud/frontend exec playwright test` against the exact passing synthetic localhost fixture. The Stage 5 regression explicitly selects list view on desktop, while Stage 6 scenarios exercise the default spatial view. Three spatial scenarios cover real two-user HTTP conflicts/retry/polling, drag conversion, a held drag across the actual refresh interval, OS-file drop versus node drag, preview/folder double click, cancellation, keyboard/offscreen focus, light/dark, reduced motion and mobile fallback. The performance scenario uses synthetic 20/100/500 metadata/placement responses to isolate rendering cost; real API semantics and placement are separately exercised. Chrome DevTools timeline traces and requestAnimationFrame/long-task samples remain under ignored .local/stage6-browser; screenshots are in docs/evidence/stage6. These headless samples are not a physical-display/GPU or ARM64 benchmark.

`scripts/verify_positions_compose.py` accepts only the exact passing local cloud-stage5-* harness and a local Docker context. It quiesces its API, dumps the database, restores a new isolated database, compares actual position coordinates/revisions/updaters/timestamps, then recreates every container without deleting volumes and compares the source again. It never changes cloud resources or resets real accounts. Dumps are ignored private test evidence. The source database and named volumes are preserved.

## Immersive refinement acceptance (2026-10-23)

The default signed-in desktop view now fills the viewport; menu starts closed and details overlay it. e2e/menu.ts opens/closes native navigation for the existing file/spatial tests. immersive.spec.ts tests exact viewport bounds/no document scroll, initially closed overlays, keyboard wrap/Escape/focus return, real menu file-picker upload, preview, right-edge double click, search-to-folder navigation, repeated resets/current-section navigation and mobile fallback. Legacy tests close a covering overlay or use menu Refresh, follow destination-picker pages and locate retained fixtures by search. Final results/limits: stage-6-immersive-layout.md. Backend/dependencies/schema are unchanged; earlier backend/recovery evidence is not represented as a new execution.


Consistent icon refinement: e2e/consistent-icons.spec.ts measures actual 76px bounds through fit/zoom/tablet, manual folder opening, unchanged overlay camera and mobile list fallback. Existing spatial and immersive suites were rerun; [executed results](stage-6-consistent-icons.md). The known generated regression folders were consolidated after testing, keeping the retained preview root clean.


Locked canvas/trash: trash-target.spec.ts exercises fixed scale, bin hit testing, cancellation, network failure, stale revision rejection, real file/folder trash/restore, descendant access and exact restored-byte download. Existing spatial cases now exercise locked-scale pan/recenter instead of removed zoom controls; routine status assertions check accessible text rather than visible messages. [Acceptance and test-only corrections](stage-6-locked-canvas-trash.md).


Stage 7 adds backend/tests/test_recovery_bundle.py (final 24 policy/archive/encryption/failure cases), scripts/verify_recovery_compose.py (guarded real consistent encrypted snapshot plus isolated DB/blob/config/identity/migration ownership checks), and scripts/verify_frontend_rollback.py (previous/current local image isolation). GPG is explicitly supplied through RECOVERY_GPG for its real encryption test; otherwise that case is skipped, not passed. Use a fresh explicit private pytest base directory on restricted Windows sessions. Existing file-picker tests now wait for destination state before Confirm and explicitly choose list mode for file-workflow coverage after returning to spatial home. Recycle Bin test verifies visible dashboard return at desktop/mobile. [Executed evidence and remaining live gates](stage-7-verification.md).


## Stage 8 production preparation

Production/settings-preflight tests run in the full PostgreSQL harness (118 before/after restore). scripts/verify_production_compose.py creates a separate local synthetic production-profile stack, verifies TLS with an isolated local CA, secure cookies/Origin/proxy boundaries, read-only containers and session/file persistence after recreation, then stops only that stack. Its test override does not prove real host binds, public certificate issuance or OCI operations. scripts/production_preflight.py --host is a read-only gate for the actual Linux mount/UUID/ownership/headroom; no host success is claimed until executed. [Exact evidence](stage-8-verification.md).
