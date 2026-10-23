# Stage 7 verification — local milestones passed, overall stage remains open

Date: 2026-10-23 (Africa/Cairo). Owner authorized Stage 7 and requested a visible Recycle Bin return. Branch stage-7-recovery-readiness. Scope is local implementation/rehearsal; no Oracle resources, production cutover or merge.

## Navigation correction

The Recycle Bin had a return path only inside the initially closed menu. Source/UI inspection proved there was no visible return action beside its heading. FileManager now exposes **← Dashboard**, using the existing root navigation and locked 65% preference. A wrapping trash heading keeps Dashboard and Refresh visible on narrow screens. Existing trash content and menu navigation are unchanged.

The actual trash browser scenario passed on final source in 6.1s (7.7s command): file/folder drag, cancel, 503/stale-409 safety, restore and exact downloaded bytes, desktop return to the 65% canvas, mobile return to All files, and no horizontal overflow. Final screenshots were captured after loading and visually inspected: [desktop](evidence/stage7/trash-desktop.png), [mobile](evidence/stage7/trash-mobile.png).

## Backend and operational tooling

- The first fresh disposable PostgreSQL cluster ran the pre-existing 72 tests before/after dump restoration (127.71s / 134.14s), preserving migration/restart/downgrade safety evidence. Private evidence: `.local/verification/bb73478486b9`.
- The expanded suite ran **95 tests before and after real PostgreSQL restoration** on the final policy/key/orphan-point revision (144.58s / 164.53s), including the then-23 recovery-tool cases. Private evidence: `.local/verification/abb1ddde70ee`. The existing Starlette/httpx TestClient deprecation warning remained; no test failure.
- After adding the observed Windows publish-denial regression, the **final 24 recovery-tool tests passed** in 2.95s. They include real GPG encryption/decryption, wrong-key/corrupt-ciphertext rejection, manifest hashes, unsafe paths/links/duplicate/missing/oversized content, destination admission, existing-destination preservation, four-good/fifth-slot rotation, unrelated backup protection, failed/in-flight points, changed-key/orphan/lock handling, destination-full failure alerts, interruption preservation, missed-job status and bounded publish retry. These overlap the expanded suite; do not add the counts as distinct backend tests or claim a full 96-test PostgreSQL run.

Commands: `scripts/verify_postgres.py --bin-dir .cache/postgres-runtime/pgsql/bin` with explicit RECOVERY_GPG; `pytest backend/tests/test_recovery_bundle.py -q --basetemp NEW_PRIVATE_DIRECTORY` with the same supplied executable. No global/system database was used. The local API remains development-only; no production-mode execution is claimed.

## Real encrypted combined recovery

Final `verify_recovery_compose.py` evidence: `.local/stage7-recovery/ac90a247357e/result.json`.

| Check | Observed result |
| --- | --- |
| Consistent capture | Synthetic API stopped during DB/files/config/source snapshot and resumed in finally |
| Metadata | All **13 public tables** have identical sorted-row hashes after isolated restore |
| Shared data | **130 durable blob/icon checksums** verified, including live/trash/recovery references |
| Full snapshot | **298 files, 15,984,490 bytes**, all snapshot hashes identical |
| Identity | Restored administrator login and root browsing passed |
| Future migrations | Tables owned by cloud_migrator; isolated create/alter/drop probe passed |
| Stop/capture/restart window | **22.079s**, including readiness wait; not a measured public outage SLA |
| Isolated restore phase | **11.859s** for this local fixture; no extrapolation to 100 GB/OCI |

Database table coverage includes users, sessions, invitations, activity, items, blobs, positions, upload reservations, deletion jobs, cleanup, namespace, rate limits and migration revision. All object/staging/config/source files are included in the bounded snapshot. The independent synthetic key stays outside the archive. Private plaintext fixtures and keys remain ignored locally; no source database or file volume is overwritten or deleted. The restored database/path is newly generated for each run.

The GPG bundle is **not** an implemented 100 GB production backup: it admits at most 256 MB payload, and this harness limits its fixture to 64 MB. The chosen real design remains native OCI incremental volume backups. No live off-server destination, OCI adapter, coordinated native scheduler, outside-VM notification delivery, full-size recovery or measured production RPO/RTO has passed.

## Container, dependency and rollback review

- All four actual local service containers use json-file logging capped at **3 × 10 MB**. Database and file volumes survived all-container recreation. API/frontend/migration images retain UID 10001, all dropped capabilities and no-new-privileges. Published API/frontend ports are loopback-only; PostgreSQL is private. Checked actual HostConfig and package inventory, not only YAML. Evidence: `.local/stage7-security/container-boundaries.json`.
- Locked frontend production dependency advisory report: zero known findings. Fresh all-frontend/build dependency report is `.local/stage7-all-frontend-audit.json`; final result is recorded with handover validation below. Python locked runtime audit (31 environment-applicable entries) and exact running Linux runtime inventory (30 distributions) both returned zero known findings. `pip check` reported no broken requirements. No Python/Node dependency or lockfile was changed.
- Existing Git GnuPG 2.2.29/libgcrypt 1.9.3 was used for local synthetic tests only. Its production currency/security is not approved; select a supported patched Ubuntu package before deployment. OS/base-image vulnerability scanning, actual ARM64 execution and final production image/digest review remain open.
- Local immutable-image rollback passed: an earlier frontend was rebuilt from captured recovery source into a separately tagged artifact, then prior/current artifacts each served JS assets and proxied readiness while anonymous auth was denied. Test containers used loopback ports, no persistent mounts, tmpfs and dropped capabilities; only labelled test containers were removed. Evidence: `.local/stage7-security/frontend-rollback.json`. Live preview never switched to the old image; this does not prove arbitrary backend/schema downgrade compatibility.

## Browser release regression

All **14 browser scenarios passed in aggregate**. Five of six file workflows passed in the initial file batch; the desktop workflow passed its corrected targeted run in 14.2s. Eight canvas/list/immersive/trash cases passed together (1.2m): 4.8 / 4.4 / 15.9 / 3.8 / 15.9 / 8.6 / 10.3 / 6.3s. The final return-button screenshot run passed again in 6.1s. Native file chooser/upload, collisions/preview/download, role isolation, pagination/warnings, optional icons, mobile/keyboard, folder defaults, saved positions/conflicts, drag cancellation and trash restoration were exercised.

The desktop file-test failure was traced to a destination-picker layout update: no PATCH was sent; its Confirm click raced the two destination fetches. The helper now waits for the selected destination label before confirmation. File workflows explicitly select list mode after All files, respecting the recently approved spatial-home default. No application move logic was changed to make the test pass.

Actual 20/100/500-node fixed-scale active-pan p95 frame samples: 2.9 / 8.3 / 5.6ms on the previously documented local machine/Chrome155 harness; no observed long tasks. This synthetic renderer measurement is not a universal 60 FPS promise or native storage benchmark. Prior 500 MB transfer and recovery evidence remains in Stage 4/5 reports; no new 100 GB or native-volume test is implied.

## Failures investigated and corrected

1. Sandbox pytest could not create its default temporary directory; reran in a fresh explicit private workspace base. Restricted GPG process setup was rerun under approved local execution.
2. Synthetic probes proved Git/MSYS GPG rejected Windows drive syntax for the agent, then rejected long agent-home paths. POSIX path conversion and a short private OS temporary agent home fixed the respective errors. Own temporary agents are cleaned up; no user's existing agent is killed.
3. Windows fsync rejected a read-only file descriptor; encrypted publication now flushes a writable descriptor before linking. Encryption/integrity checks remain enabled.
4. First isolated file copy needed ownership changes that the API's dropped capabilities correctly forbade. File restoration now streams already-validated files as UID 10001, without adding capabilities or changing primary storage permissions.
5. Restore review found administrator-owned tables would obstruct subsequent migrations. New isolated databases and restored tables now belong to cloud_migrator; explicit role grants and create/alter/drop are checked.
6. Windows denied final publication of one verified directory. The exact same snapshot succeeded unchanged on repeat, proving a transient denial; the responsible external process was not identified. A bounded PermissionError retry handles that publish step, while existing destinations/permanent errors remain protected. Final 24 tests and full combined recovery passed.
7. Compose preflight caught a YAML insertion accidentally matching a nested migrate dependency. Corrected indentation before a successful actual recreation/config inspection; the stale browser run started by that failed shell sequence was interrupted and is not counted as acceptance.
8. The build config digest was not an inspectable retained previous image reference. Rollback testing rebuilt from the captured source and retained a separately tagged, inspectable immutable artifact. Production artifact retention remains an explicit runbook requirement.

## Remaining gates — Stage 7 is not complete

The disabled sample timers were parsed for configuration structure only. They have not been installed/enabled, verified on the eventual systemd host or shown to refresh/capture live application data automatically. Local job-age status and bounded last-failure JSON are not delivered outside-host alerts or production data RPO proof.

No approved OCI data volume, CLI authentication, independent destination or notification channel is configured. A read-only console inventory attempt failed at browser-tool initialization before Oracle state was inspected. Fresh account/region/resource/free-eligibility checks, exact approved configuration and resource-specific approval are still required. Native scheduling/adapter, capture/slot rotation, host-down/missed-job delivery, quota-safe full-size restore and RPO/RTO acceptance remain open. Current development startup/TLS/named-volume layout cannot be deployed publicly; production secret/host/data-volume/ARM64/image gates also remain open. [Runbook](recovery-runbook.md), [implementation](stage-7-implementation.md), [plan](plan.md).


Owner account update (2026-10-23): the owner confirms the account is still non-upgraded Free Tier and no cloud resources have been created since the previous review. This is owner-reported status, not an independently inspected console inventory, current SKU/capacity verification or resource-creation approval. Both browser connections failed to initialize with "failed to write kernel assets: The system cannot find the path specified. (os error 3)" before Oracle state could be read. Live gates remain unchecked.

## Final handover validation

Fresh all-frontend/build dependency audit returned zero known findings in every severity; locked Python and running Linux package reports likewise returned zero. Final Ruff lint/format (44 files), ESLint, Prettier (39 files), nine frontend unit tests, 24 recovery-tool tests, secret scan and explicit source UTF-8/whitespace/local-document-link checks passed. The 95-test PostgreSQL suite passed before and after restoration; the final 24-test subset overlaps that suite and is not a claimed full 96-test run. Actual monitor CLI returned 0 for healthy state and 3 for the missed-job fixture, with a private alert record; no outside-host delivery occurred. These results complete local milestones only.
