# Stage 5 local verification - 2026-10-22

**Complete locally.** Owner-authorized responsive file manager, previews/icons and administration on branch `stage-5-file-manager`. No cloud resources, publication, main merge or Stage 6 canvas. Tests used only synthetic users/files and isolated local databases/volumes; actual .env and previous Stage 4 volumes were preserved.

## Final executed acceptance

| Gate | Executed result and evidence |
| --- | --- |
| Complete real PostgreSQL suite | **66 passed before restore (132.34 s), 66 passed after restore (141.56 s)** at `0005_media_cleanup`; ignored `.local/verification/edf2b981f3a1`. Includes the prior identity/file suite, real 499999999/500000000/500000001-byte streaming, Stage 5 query/media limits and approved-deletion retry. |
| Migration/recovery | Empty and idempotent upgrade, runtime role restrictions/readiness, restart persistence, populated-head downgrade refusal without schema change, disposable empty downgrade/re-upgrade and real pg_dump/pg_restore all passed. Applied 0001-0004 migrations were preserved. |
| Linux foundation | Clean image build, healthy proxy/API/database, private database/loopback ports, runtime non-root UID/role/DDL checks, recreation of every service container, persisted metadata/file markers and container dump/restore passed in `cloud-stage5-92c8e356b3cb`. |
| Linux file/media | Proxied binary/checksum transfer, retained replacement/recovery, rename, valid private custom icon and safely decoded PNG preview passed. File/session/pending-deletion intent survived all-container recreation; partial deletion retried successfully. A quiesced file/database snapshot restored into a separate DB/root with matching file **and custom-icon** checksums. |
| Actual Linux 500 MB | Real chunked **500000000-byte** upload and streamed download passed. API process peak RSS **141984 KiB before and after** the transfer. This is an observed API-memory bound in this test, not a guarantee for every decoder, process or host workload. Own generated large file was removed through the confirmed administrator API. |
| Browser end-to-end | **6 passed in 25.3 s**, final isolated headless Chrome run, 1440x1000 desktop, 820x1180 tablet and 390x844 mobile. Earlier five-scenario regression and supplementary grid/icon/theme smoke also passed before the final combined six-case run. |
| Frontend/source | Seven unit tests, TypeScript/Vite build, ESLint, Prettier (27 files), Ruff lint/format (37 Python files), pip check, heuristic secret scanning and documentation/link/UTF-8/whitespace checks passed. |
| Advisories/licenses | Hash-locked Python and locked pnpm audits: no known advisories. Actual Linux API inventory: **30 installed distributions**, pip-audit reported no known vulnerabilities. Pillow 13.0.0 MIT-CMU; PDF.js 6.4.299 and development-only Playwright 1.64.1 Apache-2.0. No new browser binary downloaded. OS-image/ARM64 audit remains a later release gate. |

Private Linux evidence: `.local/compose-verification/92c8e356b3cb/files-acceptance.json` and command logs. Test credentials, DB dumps, logs, traces and generated upload/media bytes remain under ignored `.cache`/`.local`. Selected screenshots contain synthetic data only and were visually inspected after acceptance:

- [Desktop file manager](evidence/stage5/desktop.png)
- [Tablet](evidence/stage5/tablet.png)
- [Mobile](evidence/stage5/mobile.png)
- [Member Recycle Bin](evidence/stage5/member-trash.png)
- [Dark grid and custom icon](evidence/stage5/grid-dark.png)

## Browser coverage

The six executable scenarios cover upload, duplicate Cancel/Keep Both/confirmed Replace (Replace disabled until explicit confirmation), download bytes, rename, New Folder, folder-picker move, subtree browsing, canceled/confirmed trash, restore destination, administrator confirmation for permanent deletion, and restoration/download of the retained original replacement bytes. Custom icons are tested both during upload and later edit/remove; clearing the optional picker resets its actual native value.

PNG previews display; the two-page PDF renders with canvas paging while its embedded action remains inactive; the browser loads valid generated WebM metadata. Unsupported file types offer download and a clear preview message. SVG disguised as PNG is rejected without setting an icon. Native tests separately cover raster signature/pixel/byte limits, metadata stripping, PDF/video range parsing and authenticated/live-ancestor access, including missing/trashed content.

Other browser checks: actual UI invitation creation/redemption/revocation and member login/logout; server-side administrator denial despite direct requests; member restore and hidden permanent-delete controls; persisted light/dark preference across reload; list/grid; server sorting/pagination; literal search/type filters; mobile tap-to-select/Open; desktop/tablet/mobile overflow; initial modal focus, focus containment/return and Escape; simulated network failure/retry; stale revision rejection; dropped file upload; cancellation; and 80/90 storage warnings. Administrator pending-job presentation/retry is exercised with a scoped mocked job; **actual** partial-unlink/CSRF/member denial/idempotent retry are separately proven on PostgreSQL, and actual pending deletion/retry/recreation is proven on Linux.

The warning UI test uses explicitly mocked 80/90 responses rather than filling the owner's disk. Backend reservation/quota/disk-reserve enforcement is separately covered against real PostgreSQL with bounded/injected storage probes. These mocks are not claims of cloud availability or physical disk exhaustion.

Nine principal light/dark text/background token pairs were measured with WCAG relative luminance: minimum **4.76:1**, all at least 4.5:1. Dark loading/footer text uses the readable muted token. This complements browser focus/layout checks, not a complete assistive-technology certification.

## Observed failures, verified causes and corrections

1. PDF.js's optional native Node canvas download timed out. Browser canvas is used, so only this optional package was excluded via documented pnpm ignoredOptionalDependencies; pinned PDF.js then installed. No age, integrity or advisory policy was disabled.
2. TypeScript proved PDF.js 6 removed isEvalSupported from its input type. Inspected installed types/source and removed the obsolete flag. Canvas-only integration includes no viewer scripting/form/annotation layer and CSP excludes unsafe-eval/inline scripts. The malicious-action PDF and normal page/video/image browser checks passed.
3. Early new tests misused the identity member helper, supplied an Origin dictionary as a header string, generated a 2 MB parametrization ID exceeding Windows's 32767-character environment limit, and tried reading a cleared anonymous CSRF cookie. Corrected the fixtures, bounded IDs and genuine anonymous request. Repeated full PostgreSQL recovery suites passed (61 focused, then 64/65/66 full as coverage grew).
4. Docker was initially stopped and was restarted. Initial Linux builds hit verified PyPI and npm download timeouts. Longer timeouts/public dependency build-cache mounts preserved frozen/hash locks and age checks; the complete build/recovery then passed. Later source-only rebuilds reused these dependency layers.
5. Both interactive UI REPLs failed before interaction with "failed to write kernel assets: The system cannot find the path specified." Browser evidence comes from development-only Playwright using the existing installed Chrome with isolated headless profiles, never the owner's real browser profile. No result is attributed to the unavailable interactive tools.
6. First browser run: icon saving succeeded, but details disappeared. The generic refresh helper cleared selected state immediately after setting the updated icon item. Icon refresh now reloads list/storage while preserving the selected updated item. Exact image/details assertion, edit/remove and final browser regression passed.
7. First browser run: New Folder input was visible but not focused. React autofocus ran before the closed native dialog was opened. Dialog now calls showModal then focuses the explicit intended input, preserving native modal containment and return focus. New Folder focus, Shift+Tab, Escape and restored trigger focus passed on mobile.
8. Pagination harness timed out locating a wrapped select by its raw label text even though the accessibility snapshot showed the correctly named combobox. Tests now use the observed accessible combobox role/name. Sorting/filter/pagination checks passed; no application behavior was relaxed.
9. Visual review showed Clear icon cleared React state but left the native filename selected. Clearing now resets both state and the native file input; the exact empty-value assertion, optional icon upload and final combined browser suite passed.
10. Repeated successful test logins exhausted the real synthetic-admin email rate bucket. Cleared only that exact synthetic bucket in the guarded disposable local project for the supplementary run; rate-limit code/configuration and peer counters remained unchanged. Native tests continue to prove actual rate enforcement. An automatically captured failure snapshot contained a generated test credential; that synthetic password was rotated and its prior administrator sessions revoked. No real owner/cloud credentials were used. Raw failure artifacts remain ignored/private.

Original failed browser evidence was preserved under ignored `.local/stage5-browser/attempt-1` before rerunning. Tests did not erase existing accounts, uploads, audit records or volumes to make assertions pass.

## Reproduction and practical limits

Run `.venv/Scripts/python.exe scripts/verify_postgres.py --bin-dir .cache/postgres-runtime/pgsql/bin` for a new guarded native DB. Local Docker on PATH: `scripts/verify_compose.py` requires unused loopback ports and creates its own project; `scripts/verify_files_compose.py` consumes only that exact passing local fixture. Browser fixture generation: `pnpm --filter @personal-cloud/frontend exec node e2e/prepare-fixtures.mjs`; browser suite: `pnpm --filter @personal-cloud/frontend exec playwright test`. Repeated independent runs still consume normal login budgets; use a fresh disposable project or wait for expiry rather than weaken authentication controls.

Preview limits are explicit: PNG/JPEG/WebP up to 10 MB/16 MP, PDFs up to 25 MB, compatible MP4/WebM subject to browser codec support. Icons up to 2 MB/4 MP become small metadata-free PNGs. Original uploads remain unchanged and downloadable up to 500 MB. PDF canvas previews have no accessible text/form layer; download the original for accessible document reading. No automatic captions or support for every codec is promised. Native image work is bounded to two jobs per API process; client PDF preparation/canvas size is bounded and workers close with the dialog.

All acceptance is local Windows/PostgreSQL plus Linux amd64 Compose. OCI/ARM64 execution, public TLS/DNS, current free-tier eligibility/capacity, measured 100 GB usable capacity, image/host hardening, automatic encrypted daily off-server backups/full-size restoration and alerts remain later release gates. The local pool is 1 GB with a 2 GB emergency reserve; local snapshots are supplemental recovery evidence, not scheduled daily backup completion. No cloud resources or paid services were created.

All Stage 5 local checklists are complete. Stage 6 visual/spatial implementation requires owner approval; no merge or deployment performed.
