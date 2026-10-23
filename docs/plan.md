# Personal Cloud Storage — staged implementation plan

Status: STAGE 8 PREPARATION IN PROGRESS — authorized 2026-10-23. Stage 7 local milestones passed; native OCI scheduling/alerts/full-size recovery remain open. Production preparation overlaps those cloud-dependent gates without waiving them. Cloud provisioning, production deployment and merges still require separate, concrete approval.

Created: 2026-10-20 (Africa/Cairo). Governing requirements: `../AGENTS.md`.

Revised: 2026-10-20 — owner said "ok proceed with planned stage 2" after reviewing the conditional feasibility recommendation. Local Stage 2 implementation is authorized. Open cloud eligibility/availability/recovery gates are preserved; this authorization does not assert unexecuted Stage 1 operational checks passed.

Completed local foundation verification on 2026-10-21 after owner installed WSL/restarted: [Compose acceptance and corrections](stage-2-compose-verification.md). All local Stage 2 checklist/test gates passed; cloud/release gates stay open.

Stage 1 findings: [capacity and backups](capacity-and-backups.md); [decisions and authorization](decisions.md). Owner created a Free Tier account currently in trial and confirmed Jeddah. Regional A1 screenshot shows core limit/available 16 and memory limit/available 96, both usage 0. These quotas are not permanent free allowances or proof of host capacity. No separate backup destination; evaluate OCI backups first. Storage/billing evidence and recovery tests remain open.

Stage 1 assessment ready for approval: [final feasibility assessment](stage-1-assessment.md). Selected minimal network/access/agent baseline, DNS/TLS/OCI alarm route and full-size quota-safe restore rehearsal are documented. Assessment/model completion does not mean live provisioning, billing, DNS/TLS or recovery checks passed. Remaining acceptance gates stay open.

## Completion and evidence rules

Owner reaffirmed strict $0 and delegated the recommended compromise on 2026-10-20. [Zero-cost policy](zero-cost-policy.md) selects the planning baseline: retain non-upgraded Free Tier, target 100 GB shared pool and four retained daily OCI recovery points, accepting that the recommendation has Oracle account/region dependency and no guaranteed availability. No paid fallback, trial-dependent service or resource creation is authorized. Remaining verification and explicit provisioning gates still apply; no additional yes/no backup question is needed merely to repeat this recommendation.

- Execute stages in dependency order. A stage is complete only when every checklist item is checked, required tests have actually passed, evidence is recorded here or in linked documents under `docs/`, and its approval gates are satisfied.
- Leave unexecuted tests and pending approvals unchecked. A written test plan is not a passing test. Record blocked tests and their impact; do not silently waive acceptance criteria.
- Before each substantive task, reread this plan and applicable documentation. Before a substantial feature, present the approach, affected files, risks, and alternatives and obtain owner approval; overall plan approval does not authorize cloud operations, destructive changes, merges, or production deployment.
- Use feature branches for substantial implementation and fixes. Run appropriate tests, Ruff, ESLint, and Prettier before proposing merges. Never merge to main without owner approval.
- For bugs: reproduce with observed evidence, investigate, distinguish hypotheses from verified root cause, explain the targeted fix and risks, obtain approval for substantial changes, then rerun the failing case and regression tests.
- Record decisions, deviations, blockers, and verification outcomes. Update this plan when scope or feasibility changes. Never include secrets, actual uploads, or private credentials in documentation or Git.

## Scope and architecture

Private, invitation-only storage for 1–5 registered users with one shared file/folder namespace and storage pool. All active users may browse, upload, download, create folders, rename, move, replace with confirmation, trash, and restore. Only administrators may permanently delete or manage users/invitations. No public registration, offline synchronization, WebSockets, automatic production updates, automatic trash purging, or unapproved features.

React + TypeScript + Vite frontend; Python + FastAPI REST backend; PostgreSQL metadata with Alembic migrations; file bytes on persistent block storage. Docker Compose runs frontend, API, and database locally before deployment to an eligible OCI Always Free Ubuntu VM. Evaluate Caddy, a permanently free subdomain, and HTTPS renewal before selecting them. Use refresh/background fetching for shared changes.

Proposed layout: `frontend/`, `backend/`, `infrastructure/`, `scripts/`, `docs/`, `README.md`, and root Compose configuration. Keep API adapters, UI components, services, authorization, persistence, and storage operations separate. Pick maintained free/open-source dependencies, check licenses/advisories and compatibility, justify additions, and lock versions when implementation starts.

Planned supporting documents, created when needed: `architecture.md`, `api.md`, `security.md`, `capacity-and-backups.md`, `testing.md`, `deployment.md`, `recovery.md`, and `decisions.md`, all under `docs/`.

## Proposed data model and integrity rules

- `users`: normalized unique email, Argon2id hash, role, active flag, theme preference, timestamps. Enforce the five-registered-user maximum transactionally; deactivation does not silently free a registration slot. Record an owner decision if account removal is later needed.
- `sessions`: opaque server-side session records, hashed session identifiers, expiry and revocation. Revoke sessions on deactivation and secure logout. Proposed defaults: 24-hour idle expiry and seven-day absolute expiry, subject to approval.
- `invitations`: hashed high-entropy token, creator, 24-hour expiry, redeemed/revoked timestamps. Single-use redemption and capacity checks occur in one transaction. Bootstrap the first administrator through a documented one-time local command, with no public bootstrap endpoint or default password.
- `items`: stable ID, parent folder, file/folder kind, display name, normalized collision key, uploader, timestamps, trash metadata, revision, and active blob/icon references. Model the root explicitly; ensure live sibling-name uniqueness, cycle prevention, valid parents, and bounded traversal. Proposed name policy: Unicode normalization and case-insensitive collision matching; reject separators, control characters, dot-path names, and excessive lengths.
- `blobs`: generated storage key, size, checksum, lifecycle state, timestamps. Never derive disk paths from supplied filenames. Store bytes outside publicly served paths.
- `positions`: shared item/folder coordinates and revision; `activity`: actor ID, action, target ID/name snapshot, UTC timestamp, request ID, and minimal action details. Preserve meaningful actor identity after deactivation.
- `upload_reservations`: concurrent in-flight capacity reservations, owner, expiry and staging state; persist enough lifecycle state to recover safely after process interruption.

Database transactions cannot atomically commit filesystem writes. Stream to a private staging file, enforce byte limits and reserved capacity during transfer, verify size/checksum, flush and atomically finalize bytes on the same filesystem, then publish metadata transactionally. Record lifecycle transitions; reconcile abandoned staging files and unreferenced blobs after a safe grace period. Do not remove referenced data during reconciliation.

Use revision preconditions for rename, move, replacement, restore, and coordinate writes. Stale updates return a conflict instead of silently overwriting another user's work. Test concurrent requests and interrupted operations.

Replacement proposal: keep the stable item ID and switch its active blob only after the new upload is durable. Preserve the previous blob as a recovery item in the shared recycle bin, retaining its original name and replacement relationship. It consumes quota until an administrator explicitly deletes it. No separate general-purpose version-history feature. Check storage for both copies before accepting replacement; if retention is infeasible, require an owner decision before weakening recovery.

Folder trash preserves the subtree; a trashed ancestor hides descendants from normal browsing/search. Restore the subtree to its original live parent, or ask for a destination if unavailable. Resolve name collisions explicitly. Permanent folder deletion requires administrator confirmation and recoverable job state for partial filesystem failures. No automatic permanent deletion.

## Proposed REST API

All protected operations authenticate the session, check active-user status and server-side authorization, validate identifiers and payloads, and return consistent errors plus request IDs. API documentation comes from FastAPI OpenAPI. Never expose storage keys or credentials to clients.

| Area | Proposed routes and behavior |
| --- | --- |
| Authentication | `POST /auth/login`, `/auth/logout`, `/auth/invitations/redeem`; `GET /auth/me`; no public signup |
| Account | `PATCH /users/me/preferences` for persisted light/dark theme |
| Browse/search | `GET /items` with folder, filename query, type, uploader, upload-date range, sort, pagination; exclude trash by default |
| File management | `POST /folders`; `POST /uploads` multipart/streaming with destination and collision decision; `GET /items/{id}`; `PATCH /items/{id}` for name/parent with revision checks |
| Content/icons | `GET /items/{id}/download`, `/preview`; `PUT /items/{id}/icon`, `DELETE /items/{id}/icon`; authorize all byte access |
| Shared placement | `GET /folders/{id}/positions`, `PATCH /items/{id}/position` with revision; bounded background refresh |
| Recycle bin | `POST /items/{id}/trash`, `/restore`; `GET /trash`; administrator-only `DELETE /trash/{id}` |
| Activity/storage | `GET /activity`, `GET /storage`; separate shared user history from administrator security/management events |
| Administration | `/admin/users`, `/admin/invitations`, `/admin/activity`, `/admin/storage`, `/admin/trash`; role-check every route |
| Operations | Minimal unauthenticated liveness, internal readiness checks; do not disclose environment details |

Collision responses provide Replace, Keep Both, or Cancel without mutating existing content. Replace requires explicit confirmation bound to the current item revision. Keep Both allocates a unique name transactionally, including concurrent collisions. Cancel has no mutation. Finalize route schemas and status codes in Stage 2.

## Threat model and security acceptance

Threats include unauthenticated internet attackers, compromised invited users, stolen sessions/invites, malicious filenames and uploads, unsafe previews, concurrent writes, disk exhaustion, leaked secrets/backups, and host/provider loss.

Controls: HTTPS; Argon2id; Secure/HttpOnly/SameSite cookies; CSRF protection and origin checks for cookie-authenticated mutations; restrictive CORS; bounded session lifetime; session/invite token hashing; single-use expiring invitations; login/invite rate limits and proxy request limits; generic authentication errors; server-side role and active-user checks; parameterized database access; upload byte counting; safe generated disk paths; least-privilege containers/database/host accounts; private database; restricted SSH and firewall.

Accept all file types for storage, including executable formats, but never execute them. Use attachment downloads with safe content disposition, defensive MIME handling and `nosniff`. Preview only explicitly supported images/PDFs/videos in an isolated, restrictive rendering context; HTML/SVG/scripts and unsupported content download as attachments. Safely decode, bound dimensions/pixels and size, and re-encode custom raster icons; reject active image formats. Document supported preview formats and test malicious content and authorization bypass attempts.

Structured logs include timestamp, severity and correlation ID without passwords, tokens, contents, or unnecessary personal data. Restrict security diagnostics and backups. Add pre-commit secret scanning, safe `.env.example` templates, separate development/production secrets, rotation and incident procedures.

## Capacity, cost, and backups — unresolved release gates

Current public provider documentation was reviewed on 2026-10-20; findings and sources are below. Owner screenshots verify account status and scoped quota usage; signed-in draft review verifies the candidate configuration. Complete account-wide billing/dependency eligibility and physical capacity remain unverified. This plan makes no promise of provisioning, 100 GB usable storage, or guaranteed zero-cost operation. Reverify official terms and the owner's account before deployment.

Before provisioning/changing/resizing/upgrading any cloud resource: establish current Always Free eligibility, calculate potential charges (including disk, snapshots, networking/egress, addresses, backup destinations, DNS and optional services), explain risks, and obtain explicit owner approval. Never assume alerts or provider limits prevent charges. Trials and promotional credits cannot satisfy permanent $0/month.

Capacity model, using consistently documented GB/GiB units:

`user_budget = verified_free_allocated_disk - boot_OS - database - bounded_logs - emergency_reserve - upload_staging - locally_required_backup_cache - other_overhead`

Stored active bytes, trash, replaced recovery copies, and custom icons all consume user budget. Count in-flight reservations separately to avoid oversubscription. File metadata and disk free-space checks must both permit a write. Define emergency reserve from measured system/DB needs in Stage 1, keep it unavailable to uploads, and reject safely when either quota or disk headroom is exhausted. Warn at 80% and 90% of approved usable user budget. Target 100 GB only if the calculation supports it; otherwise present lower-capacity or owner-supplied-storage alternatives.

Backup design must be selected from the alternatives below before implementation. Preferred provider-independent option: encrypted, incremental/deduplicated daily backup to a separately verified permanently free off-server destination in a separate failure domain where feasible. Capture database, all referenced file/icon/recovery blobs, and essential configuration; keep encryption recovery keys separately and securely. Seven daily and four weekly recovery points are an optional proposal only for a destination with adequate verified capacity; they do not fit the five-resource OCI volume-backup allowance. No full 100 GB daily-copy assumption.

`required_backup_capacity >= initial_referenced_bytes + retained_unique_changed_bytes + DB/config_history + index/encryption_overhead + safety_margin`

Deduplication cannot guarantee savings for compressed/media files or high churn. Measure representative and worst-case change rates. Prevent pruning needed blobs until a consistent database snapshot and corresponding file manifest are protected. Coordinate daily backups with mutations/deletions through a short maintenance lock or a verified snapshot/manifest strategy; test consistency and document the selected method.

Test restoration on an isolated destination: retrieve keys, restore database/config/blobs, verify checksums and permissions, then exercise login, browse, and downloads. Daily scheduling targets roughly a 24-hour recovery interval; a strict maximum 24-hour RPO remains unproven because backup completion lag and missed jobs can make recoverable data older. Monitor the latest completed capture's age, alert before the approved limit, and measure the achievable RPO/recovery time before acceptance. Same-disk copies are supplemental and do not satisfy disk/provider-loss recovery.

If strict $0, usable capacity, and off-server daily recovery cannot all be met, block release and request an explicit owner decision. Do not call the backup requirement fulfilled or silently weaken it.

### Public-source feasibility findings (checked 2026-10-20)

Oracle documents 2 OCPUs/12 GB Arm capacity (1,500 OCPU-hours/9,000 GB-hours monthly), 200 GB combined boot/block storage, five combined volume backups, 20 GB Object Storage for Always-Free-only accounts, and 10 TB monthly outbound traffic. Resources depend on home-region eligibility/capacity. Low-use VMs may be reclaimed after seven days under the documented idle criteria. These are published allowances, not account-level verification. [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

Always Free differs from the time-limited trial. Keep the account unupgraded unless separately approved; trial credits cannot establish permanent affordability. [Oracle Free Tier lifecycle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm).

Oracle volume backups are incremental-capable, encrypted, stored regionally in Object Storage, and restorable independently of the source volume. They support application quiescing and backup policies. Treat them separately from an ordinary bucket backup; validate the account's included backup eligibility before scheduling. [Oracle volume-backup documentation](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumebackups.htm).

Inference: a small single-VM installation is technically plausible at $0 within the published allowances, subject to account checks and successful tests. The complete requirement set is **conditionally feasible, not verified end to end**. Independent protection against Oracle account/provider loss remains unresolved; 24/7 service cannot be guaranteed on reclaimable free compute. Do not create artificial load to evade reclamation.

### Illustrative disk ledger and boundary calculations

This is planning arithmetic using decimal GB, not measured usable filesystem capacity or an approved allocation. Oracle's page differs on minimum boot size in different sections; use a conservative 50 GB boot proposal and verify the console. [Oracle block-volume allowance](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

| Allocation | Illustrative GB | Purpose |
| --- | ---: | --- |
| Boot volume | 50 | Ubuntu, container images and bounded host logs; monitor its free space separately |
| Data volume | 150 | Persistent database, files and application recovery material |
| Within data: user pool | 100 | Active files **plus** trash, retained replacement bytes and custom icons |
| Within data: DB and bounded application logs | 10 | Proposed budget; growth requires monitoring and a revised ledger |
| Within data: emergency reserve | 20 | Not available to uploads; validate against DB and maintenance needs |
| Within data: staging/backup workspace | 10 | Includes concurrent transfer reservations; stream backups rather than assume a full local copy |
| Within data: filesystem/uncertainty headroom | 10 | Placeholder to replace with actual measurements |

The data-volume subtotals equal 150 GB; total allocated cloud volumes equal 200 GB. At a 100 GB approved pool, warnings occur at 80 GB and 90 GB counted usage. A maximum-size replacement needs capacity for the retained old bytes and the new bytes; reject it safely when headroom is insufficient. A displayed 100 GB pool does not promise 100 GB of active files if trash/recovery items consume space.

Proposed initial transfer limit: two simultaneous uploads per user and four globally; 500 MB means 500,000,000 file bytes (multipart overhead excluded). Four maximum uploads reserve 2,000,000,000 bytes before additional workspace margin. Test actual memory use and streaming/backpressure; adjust these proposed limits only through a recorded decision.

An ordinary 20 GB backup bucket cannot protect an arbitrary, incompressible 100 GB baseline. A separately supplied 200 GB destination could, for example, budget 100 GB baseline + 56 GB retained unique changes + 20 GB overhead/margin = 176 GB; this is a workload illustration, not evidence that a free 200 GB destination exists. Measure churn across the actual retention window; deduplication cannot fix an undersized baseline destination.

### Backup alternatives and decisions required

| Option | Feasibility and protection | Acceptance requirement |
| --- | --- | --- |
| A — OCI native volume backups | Candidate at $0 within five combined backup resources. Put DB, blobs, icons and encrypted essential configuration on the data volume so a coherent recovery point can cover application state; rebuild the boot environment from versioned setup. Survives source-volume loss, but shares Oracle account/provider/region risks. | Owner accepts residual failure domains; verify account eligibility, app-consistent capture and recovery without paid overflow. Proposed four retained daily data-volume backups with one slot reserved for the next backup; shared boot backups reduce this budget. Never delete the last known good backup to make room. |
| B — encrypted independent incremental repository | Best protection from Oracle account/provider loss, but no adequate permanently free destination has been established. Existing owner storage might work if capacity, daily connectivity, bandwidth, reliability and access are proven. | Verify destination and retained-change ledger, separate keys, automatic daily execution and isolated restoration. Existing hardware still requires owner acceptance of power/connectivity and any incremental costs. |
| C — only ordinary free OCI Object Storage | Insufficient for the arbitrary 100 GB baseline. | Reject for the 100 GB target. A smaller pool would require explicit owner-approved scope change and a capacity/retention calculation. |

For Option A, application-consistent capture requires a tested sequence: block writes, finish or abort transfers safely, flush/checkpoint or stop PostgreSQL as required by the selected method, capture the coherent volume, then resume only at a provider-documented safe point. A live disk snapshot alone is not proof of application consistency. Restore validation must verify the DB-to-blob references and checksums.

**Restore capacity is a separate $0 gate.** Allocating 50 + 150 GB leaves no free block quota for an additional 150 GB test-restore volume. Do not create it and assume it is free. Rehearse on local owner-provided disk or an explicitly approved smaller cloud test layout with quota headroom. Production disaster recovery may require releasing a failed source volume before restoring; this is destructive, requires fresh explicit approval, and must preserve a verified backup. Document how the owner can recover when the original account or regional capacity is unavailable. No paid temporary restore resource is implied by plan approval.

Local restoration applies to a portable Option B repository; do not assume an OCI native volume backup can be downloaded and restored as a local disk. Option A requires an approved cloud restore rehearsal, initially with disposable small volumes that fit the quota. A small-volume test proves the mechanism, not full-size recovery: the eventual data-volume restore must also be demonstrated under an approved quota-safe procedure before claiming complete recovery validation. If this needs an early test resource, obtain separate provisioning approval and recheck costs before Stage 7; Stage 8 remains production deployment. If a full-size rehearsal cannot be performed without risking data or incurring charges, leave recovery acceptance blocked and seek an owner decision.

### DNS, TLS and operational cost boundary

Duck DNS advertises free dynamic DNS with scripted updates; it is a candidate subdomain provider, not yet selected or registered. [Duck DNS FAQ](https://www.duckdns.org/faqs.jsp). Caddy supports automatic public certificates and renewal when DNS, reachable ports 80/443 and persistent writable certificate storage are correct. [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https). Validate subdomain availability and ACME staging issuance/renewal before production; no purchased domain is required by this proposal.

Proposed minimal hosting uses a public VM with Caddy and private DB/container networking; no managed PostgreSQL, paid load balancer, NAT gateway, paid DNS zone, cross-region backup or premium monitoring is required. Before approval, price-check the exact public IP, network path, volume performance settings, backup policy, telemetry and notification choices against current terms. Account-wide consumption matters, including unrelated resources. Alerts and quotas are supporting controls, not a universal hard spending cap. Count downloads and independent backups together when forecasting egress; use warnings and an approved safe transfer ceiling below the verified free allowance.

## Technical risk register

| Risk / priority | Consequence | Mitigation and proof required |
| --- | --- | --- |
| Free capacity or account eligibility unavailable — release blocker | No deployable free VM | Read-only account/home-region/usage checks; provisioning only after approval. Wait or seek an explicit revised requirement; never silently select a paid shape. |
| Reclamation, account loss or regional outage — high | Extended downtime or lost access to backups | Honest availability target, actionable external health alert, documented rebuild and independent-backup decision. Service restart policies cannot solve provider reclamation. |
| Backup retention/restore quota conflict — release blocker | Daily backups stop or restoration incurs cost | Select Option A/B, count backup slots and restore disk headroom, rehearse full restore under an approved $0 layout. |
| Disk exhaustion / retained replacement growth — high | Database failure or lost writes | Count all pool bytes, reserve transfers transactionally, monitor both filesystems, cap logs, test thresholds and low-disk recovery. No automatic permanent trash deletion. |
| DB/filesystem commits diverge — high | Missing bytes, orphan blobs or corrupt metadata | Durable staging/lifecycle records, checksums, atomic same-filesystem finalization, transactional metadata and crash-injection reconciliation tests. |
| Concurrent edits and folder operations — high | Overwrites, cycles, broken restores | Revision preconditions, transactional uniqueness and namespace locks where needed; simultaneous upload/move/restore/trash race tests. |
| Hostile uploads/previews/icons and session theft — high | Code execution, XSS or unauthorized access | Private byte storage, safe downloads, isolated allowlisted previews, bounded image decoding, CSRF/session controls and direct API attack tests. |
| Arm/container compatibility or memory pressure — medium | Build/runtime failure or exhausted VM | Verify ARM64 images/packages; stream transfers and limit image/PDF processing and Argon2 concurrency; load-test target architecture before deployment. |
| Large-folder canvas and hidden names — medium | Poor performance or inaccessible file navigation | Keyboard/touch labels/actions, list fallback, bounded rendering, measured 20/100/500-item workloads and reduced motion. |
| DNS/TLS/alert dependency failure — medium | Inaccessible service or unnoticed failed backups | Verify no-cost service terms, persistent TLS state, staging renewal test and an alert path that still works when the VM is down. |

No failure mode is considered mitigated solely because this table proposes a control. Record actual test evidence in its stage before closure.

## Stages and completion checklists

### Stage 0 — repository review and proposed plan

Dependencies: none. Deliverable: this document only.

- [x] Read the complete repository `AGENTS.md` and inspect tracked files and existing documentation.
- [x] Establish that no existing `docs/plan.md` or application implementation is present.
- [x] Draft stages, dependencies, task checklists, test gates, architecture, data/API design, security, UX, cost/capacity/backup feasibility, and recovery plan.
- [x] Validate this document's required sections, stage checklists and test gates; record executed evidence below.
- [x] Obtain owner approval to proceed with the plan's Stage 1 feasibility work; see D001 in `decisions.md` (2026-10-20). Proposed defaults and implementation approval remain later gates.

Test gate: inspect repository status/diff, check plan content and Markdown checkbox structure, verify every stage has an explicit test gate, and confirm no application files were introduced. Draft validation can pass while this stage remains incomplete pending approval.

### Stage 1 — feasibility and owner decisions

Dependencies: Stage 0 approval. Deliverables: `capacity-and-backups.md`, `decisions.md`.

- [x] Review dated official OCI public terms, Ubuntu listing, storage/network allowances, backup mechanism and budget behavior; record sources and limits in `capacity-and-backups.md`.
- [ ] Finish account eligibility/usage, exact console configuration costs and home-region capacity checks. Signup complete; Free Tier trial banner and Jeddah A1 regional quota screenshot reviewed (16 cores/96 memory, zero usage). Storage/backup usage, trial expiry and configuration eligibility remain pending. Runtime ARM64 compatibility remains a later test gate.
- [x] Calculate proposed disk allocations, 100 GB pool, emergency reserve, simultaneous-upload allowance, trash/replacement overhead, and 80%/90% warning denominators; validate model scenarios. These are proposed budgets, not measured usable capacity.
- [ ] Select and verify backup Option A or B, including owner acceptance of residual failure domains, retention/slot budget, restore quota/destination, key recovery and daily-job/alert feasibility. Reject insufficient Option C for 100 GB.
- [ ] Verify free subdomain eligibility, DNS control and unattended TLS renewal feasibility.
- [x] Finish documented network/access/optional-agent baseline and select Duck DNS/Caddy plus OCI Monitoring/Notifications alarm design; see `stage-1-assessment.md`. Live DNS ownership/renewal, delivery and access verification stay unchecked until an approved host/account exists.
- [x] Define full-size pre-user-data restore rehearsal within 200 GB and source-removal approval boundary; preserve Stage 7 actual recovery test gate.
- [ ] Approve capacity, backup retention/destination, collision/name policy, session defaults, and shared-coordinate conflict behavior; record blockers and alternatives.
- [ ] Obtain separate explicit approval before any cloud resource operation; defer provisioning until Stage 8 when possible.
- [ ] Execute and record feasibility tests; owner accepts the feasibility findings before infrastructure commitments.

Test gate: independently reconcile the capacity and cost ledger against dated provider/account evidence; model empty, near-full, concurrent-upload, replacement, high-churn and retention-full scenarios. Where a destination is available, test encrypted sample backup/restore without provisioning resources. Unavailable account or destination access remains a blocker, not a pass.

### Stage 2 — detailed contracts and local foundation

Dependencies: Stage 1 decisions. Deliverables: repository scaffold, architecture/API/security/testing documents, Compose development setup.

- [x] Present implementation scope/files/risks for approval; establish feature branch `stage-2-foundation` after owner's explicit approval.
- [x] Finalize schema, endpoint/error contract baseline, migration strategy, storage lifecycle and concurrency invariants in `architecture.md`, `api.md`, and `security.md`. Detailed business-route schemas are added with their later stages, not advertised as implemented health routes.
- [x] Record threat-model controls, preview allowlist, administrator bootstrap, quota reservations and recovery defaults under the approved Stage 2 contract scope (D018); corresponding feature/deployment gates still apply.
- [x] Create frontend/backend/infrastructure/scripts structure, dependency locks, safe configuration examples, secret scanning, lint/format/type checks, and meaningful test setup.
- [x] Configure persistent PostgreSQL and file volumes, least-privilege services, local health checks, and OpenAPI. Configuration exists; actual Compose verification remains required below.
- [x] Execute foundation tests and record evidence before marking complete: [native/source evidence](stage-2-verification.md) and [Linux Compose/browser acceptance](stage-2-compose-verification.md).

Test gate: clean local Compose startup/restart, API readiness, PostgreSQL connectivity, migration upgrade from empty database, disposable migration recovery rehearsal, frontend production build, lint/format/type checks, and secret-scan checks. Demonstrate persisted sample data survives service recreation without removing volumes.

### Stage 3 — identity, invitations and authorization

Dependencies: Stage 2. Deliverables: identity services/API and accessible login/invitation flows. Owner authorization and scope: [Stage 3 implementation](stage-3-implementation.md).

- [x] Obtain feature approval with affected files and risks; implement first-admin bootstrap and email/password authentication using Argon2id.
- [x] Implement sessions, secure logout/expiry/revocation, CSRF/origin controls, rate limits, and active-user checks.
- [x] Implement administrator-created/viewable/revocable single-use 24-hour invitations and transactional registration limit.
- [x] Implement protected routing and administrator-only API policies; hide administration UI from other users.
- [x] Execute identity and authorization tests and record evidence before marking complete.

Test gate: invitation signup/login/logout end-to-end; expired/revoked/reused/concurrently redeemed invitations; five-user registration race; invalid login/rate limits; expired/revoked sessions; CSRF attempts; unauthenticated and non-admin direct API access; user deactivation taking effect on existing sessions. Verify secrets/tokens do not appear in logs.

Evidence: [Stage 3 verification](stage-3-verification.md). Native 24-test suites, five frontend tests, Linux persistence/identity recovery and core browser flows passed. Final inline Cancel/Confirm, administrator logout and deactivated-login browser checks passed after browser input recovered. All Stage 3 local checklist/test gates are complete.

### Stage 4 — durable shared file operations and activity

Dependencies: Stage 3. Deliverables: file services/API, transfer and integrity tests.

- [x] Obtain feature approval; implement folder trees, streamed upload/download, persisted bytes/metadata, safe naming and authenticated content access.
- [x] Enforce 500 MB per-file maximum on backend bytes actually received; document exact byte threshold and client agreement.
- [x] Implement Replace/Keep Both/Cancel with explicit confirmation, revision checks, retained replacement recovery items, and concurrent uniqueness.
- [x] Implement rename/move, quota reservations, staging reconciliation, cycle protection, trash/restore and administrator-only permanent deletion.
- [x] Record successful uploads/downloads/renames/moves/folder creation/replacement/trash/restore/permanent deletion with actor/action/target/time. Define interrupted-download audit semantics honestly; do not imply confirmed client receipt.
- [x] Execute integrity/API/DB/storage tests and record evidence before marking complete.

Test gate: arbitrary binary round trips with checksum comparison; file limit below/at/above threshold including unknown content length; near-full disk and concurrent quota enforcement; all collision decisions/races; stale replacement; partial uploads and crash/restart reconciliation; folder cycles; subtree trash/restore and missing-parent collisions; admin/non-admin permanent deletion; download/preview ID authorization; audit completeness; failed filesystem/DB finalization preserves existing data.

Evidence: [Stage 4 verification](stage-4-verification.md). Final schema 0004 passed all 53 backend tests before/after real restore; Linux 500 MB transfer, persistence and file/database recovery passed. File UI and previews remain Stage 5.

### Stage 5 — usable file manager, previews and administration

Dependencies: Stage 4. Deliverables: responsive functional UI before spatial polish.

- [x] Obtain feature approval; implement desktop details panel, collapsible sidebar, mobile list/grid and full shared file actions.
- [x] Implement upload/drop interactions, progress/errors, New Folder, confirmation dialogs, file search, collapsible type/date/uploader filters, sorting and pagination.
- [x] Implement safe centered image/PDF/video previews, unsupported-file metadata/download, and validated upload/edit/remove custom icons with conventional type defaults.
- [x] Implement Activity History, Recycle Bin, storage usage/warnings, account controls, default light theme and persisted per-user light/dark choice.
- [x] Implement administrator user/invitation management, storage dashboard, activity filters and recycle-bin management.
- [x] Execute UI, accessibility and security tests and record evidence before marking complete.

Test gate: browser end-to-end coverage of upload, duplicate decisions, browse, rename/move, preview/download, search/filter/sort, icon edits, trash/restore and admin deletion. Check desktop/tablet/mobile layouts, keyboard focus/dialog handling, touch Open actions, readable contrast, loading/error states, malicious icon/preview inputs, and direct unauthorized admin requests.

Evidence: [Stage 5 verification](stage-5-verification.md). Final 66-test PostgreSQL suite passed before/after restoration; seven frontend unit and six browser end-to-end scenarios passed. Linux file/icon recovery, pending deletion/recreation and actual 500 MB roundtrip passed. Stage 6 remains unapproved.

### Stage 6 — shared spatial dashboard and visual polish

Dependencies: Stage 5. Deliverables: desktop spatial canvas and verified responsive fallback.

- [x] Obtain approval for the visual/interaction implementation and performance measurement approach. Owner said "okay lets go next stage go go go" on 2026-10-22; see stage-6-implementation.md.
- [x] Implement abstract geometric glowing core, soft blue/lavender tokens, restrained faint connectors, hover/selection highlighting and guided empty-state upload CTA.
- [x] Hide filenames visually by default; expose full names on hover/focus/touch selection and through accessibility labels. Single click selects/details; double click opens; empty canvas deselects; keyboard has equivalent actions.
- [x] Implement freeform dragging and deterministic available-area placement of new items; persist shared folder coordinates independently of decorative motion.
- [x] Use a logical coordinate space with fit-to-content and bounded zoom/pan; keep offscreen items discoverable. Use list/grid on mobile; preserve shared logical placement across viewport changes.
- [x] Distinguish OS file-drop upload from existing-node drag. Pause motion during drag; support reduced motion and unsynchronized low-amplitude floating/pulse.
- [x] Apply revision checks to position updates; on stale drag show conflict and refresh, allowing an explicit retry. Background refresh must not move a node underneath an active drag.
- [x] Benchmark representative small and larger folders (for example 20, 100 and 500 items); bound drawing/animation work and offer a usable list fallback as needed.
- [x] Execute interaction/accessibility/performance tests and record evidence before marking complete.

Test gate: two-user shared-placement persistence across refresh/login; concurrent drags; resize/zoom/pan; automatic placement without overlap where space exists; drag/drop distinction; all click/touch/keyboard behaviors; reduced-motion mode; light/dark contrast; responsive fallback; browser performance traces on documented hardware. Aim for practical 60 FPS on capable devices and report measured limits.

### Stage 7 — integrated security, backups and recovery rehearsal

Dependencies: Stages 1–6. Deliverables: tested daily backup job, recovery runbook, release evidence.

- [x] Obtain local Stage 7 implementation approval (2026-10-23); execution and limitations are recorded below.
- [ ] Implement and prove actual coordinated daily native backups, approved retention, outside-VM monitoring/failure delivery on approved resources. Local tools/log limits do not satisfy this live gate.
- [ ] Test off-server storage with representative data and measured retained-change capacity; document encryption-key storage/recovery.
- [ ] Restore into an isolated environment; verify checksums, DB/file manifest consistency, user access, icons, positions, trash and recovery copies.
- [ ] Rehearse application rollback, versioned migration recovery and restart behavior without deleting production-like volumes.
- [ ] Review full authorization matrix, safe previews/downloads, dependencies/secrets, host/container least privilege and operational documentation.
- [ ] Execute the release test suite and record evidence; block release for unresolved cost, backup, integrity or security requirements.

Test gate: unit/integration tests plus the core end-to-end workflows; daily-job execution, missed-job and destination-full alerts; restore after simulated primary-data loss; corruption detection; interrupted-backup recovery; measured recovery time and recovery point; backup retention correctness; no cloud resource changes without separate approval. A scheduler configuration alone does not prove daily backups work.

### Stage 8 — approved OCI deployment and operational acceptance

Dependencies: Stage 7 and all feasibility blockers resolved. Deliverables: explicitly approved production deployment and handover.

- [ ] Reverify current Always Free eligibility, quota/region capacity, exact resource configuration, disk ledger and all possible charges; present evidence and obtain explicit provisioning approval.
- [ ] Configure approved Ubuntu VM/storage, firewall/SSH restrictions, private database, least privilege, production secrets, free DNS and HTTPS.
- [ ] Configure Compose persistence, restart policies, health monitoring, usage warnings, bounded logs, daily backups and actionable alerts.
- [ ] Present exact release, migration, verified backup and rollback procedure; obtain explicit production deployment approval. Obtain merge approval separately if merging.
- [ ] Deploy approved artifacts manually and execute post-deploy acceptance checks with disposable test data.
- [ ] Verify TLS renewal path, process/host restart recovery, first scheduled backup and isolated restore; provide owner runbooks for invitations, recovery, updates and secret rotation.
- [ ] Record observed uptime limits, approved usable capacity, measured recovery time, recurring cost checks and any limitations; obtain operational acceptance.

Test gate: external HTTPS and authentication checks, direct unauthorized API attempts, sample upload/checksum download, collision/recycle-bin/admin flows, data survival after service/VM restart, 80%/90% warnings and safe upload rejection via controlled tests, restricted SSH/ports, renewal rehearsal and successful scheduled off-server backup/restore. Do not fill production disk or destroy live data for testing. 24/7 remains a target, not an SLA.

## Verification log

### Milestone acceptance summary

These exit criteria supplement every stage's task checklist and test gate. Evidence must include command/tool, date, environment, observed outcome and remaining limitations; any required failing or unexecuted check prevents completion.

| Stage | Reviewable milestone | Acceptance criteria |
| --- | --- | --- |
| 0 | Approved implementation proposal | Required plan sections/checklists validated and owner approval recorded; application files absent during planning. |
| 1 | Feasibility decision | Account/resource ledger supports $0; usable pool, backup option/retention, restore destination, failure-domain trade-offs, DNS/TLS and alert route approved. Unresolved feasibility blocks implementation progression. |
| 2 | Reproducible local foundation | Fresh setup/build/checks pass, migrations work on disposable DB, volumes survive recreation, and schema/API/security contracts are reviewable. |
| 3 | Private invitation-only access | Identity test gate passes; expired/reused invites, sixth registrations, inactive users and unauthorized administrator requests are rejected server-side. |
| 4 | Durable file service | Round-trip checksums match; concurrent collisions and crash cases preserve prior content; quota/reserve, trash/restore, deletion permissions and audit tests pass. |
| 5 | Complete responsive file manager | Core browser workflows pass on documented desktop/mobile viewports; safe preview/icon handling, keyboard operation and admin isolation pass. |
| 6 | Shared spatial experience | Two-user placement/conflict tests, touch/keyboard/reduced-motion checks and documented performance measurements pass; full file access remains usable through fallback. |
| 7 | Recoverable release candidate | Full required suite passes; successful daily-job execution, failure alert and isolated DB/blob/config restore proven; recovery time measured and residual risks accepted. |
| 8 | Accepted production service | Fresh cloud/deploy approvals recorded; actual configuration remains eligible/free; HTTPS, restart persistence, external smoke/security checks and scheduled backup/restore pass. |

### Executed checks

| Date | Scope | Executed evidence and result |
| --- | --- | --- |
| 2026-10-22 | Stage 6 completion | Shared saved spatial placements, core/connectors, drag/zoom/pan, stale-write retry, keyboard/reduced motion and mobile/list fallback complete locally. Final 72 backend tests before/after restore, nine frontend unit tests and all nine browser scenarios passed. Active-pan/zoom p95 2.9/8.3/13.9ms at 20/100/500 nodes on documented local hardware; 86 real placements survived Linux recreation/isolated restore. See stage-6-verification.md. Stage 7+, cloud and merge gates remain open. |
| 2026-10-22 | Stage 5 completion | Responsive file manager, filters/sorting/pagination, upload/drop/collision choices, previews/icons, trash/restore/admin deletion/retry, activity/admin and persisted themes complete locally. Final 66 backend tests before/after real restore; seven frontend unit and six browser scenarios passed. Linux non-root/private ports/recreation, matching file/icon snapshot restoration and real 500 MB transfer passed (API peak RSS 141984 KiB before/after). Quality, 30-distribution runtime advisory, secret/link/encoding checks passed. See stage-5-verification.md. Cloud/release/Stage 6 gates remain open. |
| 2026-10-22 | Stage 4 completion | Durable private file API, full 500,000,000-byte streaming, collision/recovery, quota/reserve, trash/restore and confirmed administrator deletion passed. Final revision: 53 backend tests before and after real PostgreSQL restore. Linux 500 MB roundtrip, all-container recreation, pending-delete recovery and isolated file/database restore passed; API peak RSS 138376 KiB before/after. Five frontend tests, build/lint/format, secret scanning, pip check and actual 29-package Linux advisory audit passed. See stage-4-verification.md. No cloud resources or Stage 5 UI. |
| 2026-10-21 | Stage 3 completion | Implemented identity and minimal administrator UI. Real PostgreSQL: 24 tests pass before/after restore; populated-history downgrade safely refused; identity recovered. Frontend five tests, TypeScript/Vite, ESLint/Ruff/format/secret scans pass. Linux Compose and authenticated sessions survive all-container recreation; container identity backup/restore passes. Actual 28-distribution Linux inventory and locked frontend/Python advisories report no known findings. Desktop/mobile invitation/login/logout/member/admin checks pass after same-tab fragment fix. On follow-up browser input recovered; inline Cancel/Confirm, deactivated state/disabled controls, administrator logout and deactivated-login rejection passed. Stage 3 complete locally. See stage-3-verification.md. |
| 2026-10-21 | Stage 2 completion | Docker/WSL verified and clean Linux Compose build/start/migration/health passed after targeted Caddy file-capability and Windows UTF-8 diagnostic fixes. Actual API image's obsolete pip removed; 22 installed Python distributions audited with zero known findings. Database/file markers survived recreation of all three service containers; real container dump/restore recovered metadata. Inspected private ports/non-root/capability restrictions/restart policies. Desktop/mobile, keyboard retry and stopped/restarted-API unavailable/recovery checks passed. Ruff, secret scanning, local documentation links and source/docs whitespace passed. See `stage-2-compose-verification.md`. Stage 2 complete locally; no cloud writes, later features, merge or deployment. |
| 2026-10-20 | Stage 2 local foundation | See [execution evidence](stage-2-verification.md): frontend build/type/lint/format and 2 tests pass; desktop/mobile browser smoke captured. Ruff passes. Real native PostgreSQL migration/restart/dump/restore rehearsal passes with all 7 Python tests before and after restoration, including log privacy. Secret scanner/hook, exact installed lock comparison, package compatibility and final dependency audits pass (0 known vulnerabilities). Downloaded/checksum/signature-verified Docker installer exited 1 because VirtualMachinePlatform is disabled; WSL elevation was canceled before setup started. Owner administrator setup/restart required. Compose build/start/recreation/named-volume and Linux/ARM64 tests remain unexecuted. Stage 2 is not complete. |
| 2026-10-20 | Stage 1 final assessment | Created `stage-1-assessment.md` covering minimal network/SSH/agent baseline, Duck DNS/Caddy, OCI outside-VM alarms and full-size serial restore within quota. Fresh browser inspection confirms draft remains unsubmitted. First PowerShell model run stopped at an array-expression parsing error in the test command; parenthesized arithmetic in that command and reran the full model successfully. Passed compute/disk/pool/warning/concurrency/trash/replacement/backup-slot/failed-capture/rotation/restore/churn/monitoring/email models, all local links and whitespace, nine stage gates/checklists, docs-only additions and `git diff --check`. No production controls or live backup/connectivity tests claimed. Assessment ready for owner review; Stage 1 acceptance and unverified resource gates remain unchecked. |
| 2026-10-20 | Signed-in draft review | Reached OCI draft Review, verified 2 OCPUs/12 GB ARM64 A1 and explicit 50 GB/10 VPU/encrypted boot; captured EUR 1.98/month estimate excluding tier pricing. No Create/Save as stack submission. Recorded incomplete network/SSH/data/optional-plugin configuration in `oci-draft-review.md`. Local document/evidence links, full-file whitespace, nine stage test gates/checklists and `git diff --check` passed. Runtime, physical capacity, billing and recovery acceptance remain unproven. |
| 2026-10-20 | Stage 1 feasibility work | Owner confirmed no OCI account and no independent backup storage; approved evaluating OCI backups first. Created `capacity-and-backups.md` and `decisions.md`. Refreshed official hosting/backup/DNS/TLS/budget sources; exact numeric pricing was incomplete in the fetched price list and remains open. PowerShell assertions passed for monthly compute, disk ledger, pool boundaries, warnings, reservations, retained replacements/trash, reserve rejection model, backup slots, restore quota and churn examples. These were arithmetic models, not application/cloud tests. All nine stage checklists/test gates/dependencies, local Markdown links, full-document whitespace checks, docs-only changes and `git diff --check` passed. Account, provisioning, backup/restore and DNS/TLS operation remain untested. |
| 2026-10-20 | Initial inspection | Read complete `AGENTS.md`; checked ancestor instruction paths and repository files. `git status --short` was clean; `git branch --show-current` returned `main`; `git ls-files` returned only `AGENTS.md`. No existing docs or application code found. |
| 2026-10-20 | Draft validation | Executed PowerShell assertions: nine stages (0–8), each with dependencies, checkboxes and a test gate; eight required content sections present; `git ls-files --others --exclude-standard` showed only `docs/plan.md`. `git diff --check` passed for tracked changes; a separate full-plan line scan passed for trailing whitespace because the new plan is untracked. No application files introduced. |
| 2026-10-20 | Public feasibility research | Read official Oracle Always Free, Free Tier lifecycle and volume-backup documentation, Duck DNS FAQ and Caddy automatic HTTPS documentation linked above. Published allowances support a conditional hosting proposal; account availability/billing and actual backup/restore remain untested. |
| 2026-10-20 | Revised plan validation | Executed PowerShell assertions: all nine stages retain dependencies/checklists/test gates; all nine milestone acceptance rows exist; risk, feasibility and restore-capacity sections present. Verified illustrative arithmetic: 50 + 150 = 200 GB, data subdivisions = 150 GB, four maximum uploads = 2,000,000,000 bytes, example independent backup budget = 176 GB. Full-file whitespace scan and `git diff --check` passed. Git checks confirmed only untracked `docs/plan.md` changed and no tracked files changed. |

Local foundation application tests and disposable PostgreSQL backup/restore checks have been executed as recorded above. Stages 2-4 local API/identity and Docker acceptance are documented in their verification reports. Stage 5 browser file workflows have passed locally. Authenticated provider/resource checks, OCI backups/full-size restoration and deployment checks remain unexecuted. Public documentation research is evidence of published terms only.

## Current blockers and approval checkpoints

1. Owner authorized local Stage 2 on 2026-10-20 after the conditional Stage 1 review. Stage 3 identity was subsequently authorized on 2026-10-21 and Stage 4 file services on 2026-10-22; Stage 5 was authorized on 2026-10-22; Stage 6+ features, merges and cloud operations retain their gates.
2. Cloud eligibility/consumption rechecks, physical capacity, measured headroom, DNS/TLS, alerts and full backup restoration remain release gates. Owner permitted local Stage 2 despite these explicitly documented operational checks; they are not marked passed or silently waived.
3. Stage 2 contract defaults are recorded in `architecture.md` and `security.md` under D018; Stage 3 identity passed local acceptance and Stage 4 file services were authorized; Stage 5 file screens/previews have passed local acceptance; Stage 6 spatial features require approval. D015 selected the four-daily native backup planning compromise. Its actual resources, consistency, failure-domain and restore acceptance remain release gates; seven-daily/four-weekly retention is not available under the five-backup allowance.
4. Later substantial implementation, cloud operations, destructive actions/migrations, main merges and production deployments retain their explicit approval gates from `AGENTS.md`.

Latest account evidence (2026-10-20): owner-provided Block Volume screenshot, Jeddah regional/root scope, shows free volume quota 200 GB (usage 0, available 200), free backups 5 (usage 0, available 5), and general backup count limit 100,000 (usage 0). The general limit is not a free entitlement. This supports the nominal 50+150 GB allocation and five-slot backup proposal; exact eligibility, measured capacity and recovery remain unproven.

Subscription evidence (2026-10-20): supplied screenshot confirms Free Tier, account type Promo, start date 2026-10-20. Applying Oracle's 30-day rule gives expected calendar expiry around 2026-11-19 unless credits are exhausted earlier; exact expiry timestamp was not displayed. No personal/account identifiers copied into docs.

Draft inspection completed: [OCI draft review](oci-draft-review.md). Verified unsubmitted Ubuntu 24.04 ARM64 A1 configuration at 2 OCPUs/12 GB and 50 GB Balanced boot with in-transit encryption. Console estimate EUR 1.98/month is a boot-volume estimate excluding tier pricing; documented free quota supports a discount interpretation, not a whole-system $0 guarantee. Draft lacks public access/SSH keys/data volume; optional agent settings need cost/security review. Create and Save as stack were not clicked.

Next action: finish Stage 7 native OCI implementation/acceptance on freshly verified, separately approved resources. Owner authorized Stage 7 locally on 2026-10-23; see stage-7-verification.md. Stage 6 evidence: [verification](stage-6-verification.md). The retained synthetic preview is http://127.0.0.1:8080 in disposable cloud-stage5-92c8e356b3cb; Stage 6 screenshots and executed evidence are linked in stage-6-verification.md. No real owner password is seeded. ARM64/OCI eligibility/capacity, host/image hardening, TLS/DNS and daily/full-size cloud recovery remain later release gates. No cloud resources, main merge or production deployment authorized.

Stage 6 completion: [implementation milestones](stage-6-implementation.md) and [executed acceptance](stage-6-verification.md). Prior references to Stage 6 awaiting approval above are historical; Stage 6 is now complete locally. Stage 7 and cloud/release approvals remain open.

## Stage 6 layout refinement — authorized 2026-10-23

Owner clarified: the dashboard is the main screen, fills the viewport without page scrolling, uses minimal words/floating controls, starts navigation/upload closed, and shows accessed file details as an overlay. Search/storage/account controls belong in the menu. This authorizes local UI refinement, not Stage 7 or cloud operations.

- [x] Full-viewport spatial default without masthead/footer/guide/sidebar space or page scrolling.
- [x] Navigation/upload drawer initially closed; search, filters, storage and account/sign-out available inside it.
- [x] File details overlay never resize/recenter the canvas; explicit close/Escape and accessible focus behavior.
- [x] Compact floating menu and canvas controls; details/help only when requested; mobile list/grid remains functional.
- [x] Test viewport bounds, overlays, keyboard/menu/actions, click/double-click, uploads, search, responsive fallback and existing spatial persistence/performance; visually inspect results.
- [x] Record actual results before marking this refinement complete.

Implementation/evidence: [immersive layout refinement](stage-6-immersive-layout.md). Feature branch stage-6-immersive-layout. No API/schema/dependency change is planned.

Layout refinement completed locally on 2026-10-23: full-viewport/closed-menu/overlay acceptance, all eleven browser scenarios, nine unit tests and source checks passed. Actual limits, corrected regressions and final screenshots: [refinement verification](stage-6-immersive-layout.md). Stage 7+, cloud operations and merges remain unapproved.


## Stage 6 clutter and sizing refinement — requested 2026-10-23

Owner requests consolidating the visible folders and consistent readable node sizes without routine zoom. Owner approved collecting only test/demo items into one folder and explicitly declined automatic grouping. Keep manual folder organization, consistent 76px screen-space icons, automatic initial framing and optional camera controls; do not change saved placements to resolve crowding.

Inspection: the retained local preview has 90 live root items, including repeated Canvas inputs, Spatial, Immersive, Pagination, Folder and Stage verification fixtures. Current SpatialCanvas applies camera scale to entire node buttons; fit() reduces zoom as coordinate extents grow, shrinking icons and their hit targets. No data or application code has changed for this request.

### Milestone A — confirm scope and preserve organization
- [x] Resolve the pending grouping choice and record the chosen behavior.
- [x] Before moves, save an ignored metadata manifest of selected IDs, parents, names and revisions; use authenticated revision-checked moves and retain all content.
- [x] Verify selected items appear under one container and unselected items keep their original parent; no deletions.

### Milestone B — consistent readable canvas
- [x] Keep node icons and interaction targets at a consistent screen size while preserving saved shared coordinates and drag behavior.
- [x] Define crowded-folder behavior based on the owner's grouping choice; do not silently shrink icons or rearrange persisted positions.
- [x] Preserve full viewport, closed menu, details overlay, keyboard/reduced-motion behavior and mobile list/grid.

### Milestone C — acceptance
- [x] Run relevant geometry/unit, build/lint/format and browser checks; verify actual icon bounds, crowded folders, resize, select/open/drag and shared placement.
- [x] Verify grouping preserves IDs/content and document before/after results; inspect desktop/tablet visuals and no document scrolling.
- [x] Record actual evidence before marking this refinement complete. Stage 7/cloud/merge gates remain unchanged.


Completed locally: 92 generated root items consolidated into Demo files across initial cleanup and regression cleanup; unrecognized icon.png preserved. Fixed 76px screen-space nodes and manual organization verified through six browser cases and nine unit tests. Original 383 items, 93 blob records and 62 unmoved positions passed metadata preservation checks. Exact results and limitations: [consistent icons and demo cleanup](stage-6-consistent-icons.md).


## Stage 6 locked canvas and trash target — authorized 2026-10-23

Owner requests exactly 65% canvas scale with no zoom adjustment, a bottom-left rubbish-bin drag target, and removal of bottom-left status updates. Preserve manually organized folders and fixed readable icons. Implementation uses existing revision-checked trash API; recycle-bin actions remain reversible, never permanent deletion. Panning/recentering remain available for offscreen items, with keyboard focus reveal at the same fixed scale.

- [x] Lock every camera path (initialization, resize, pan, focus, recenter) to 0.65; remove adjustable zoom controls.
- [x] Add accessible bottom-left recycle-bin button and pointer drag hit detection/highlight; cancelled/outside drops never trash, failed/stale actions display errors and preserve placement.
- [x] Remove visible routine placement status; retain screen-reader announcements and separate visible failures/conflicts.
- [x] Verify exact scale, no zoom UI/wheel changes, real file/folder trash/restore, cancelled/failed/stale drops, ordinary drag persistence, keyboard/mobile/viewport and rendering regression.
- [x] Document executed checks and review visuals before completion; preserve test fixtures under Demo files. No cloud/schema/dependency/merge changes.


Complete locally: exact 65% fixed scale, reversible trash target and hidden routine status verified through seven aggregate browser scenarios and nine unit tests. Test corrections, actual restored-byte download, performance, screenshots and limits: [locked canvas and trash verification](stage-6-locked-canvas-trash.md). No Stage 7/cloud/merge approval implied.


## Stage 6 folder list default — authorized 2026-10-23

Owner clarified that folders should open as lists while individual files retain previews; root dashboard remains the locked-65% canvas. FileManager navigation will choose list (not grid) for non-root folders and canvas for root. Existing explicit view controls remain available; saved placements and content are unchanged.

- [x] Apply folder-list/root-canvas navigation defaults consistently to double click, details Open and breadcrumbs.
- [x] Verify nested folder lists, file previews and return to root canvas; keep mobile list fallback.
- [x] Run relevant frontend/browser checks and document evidence before completion. No Stage 7/cloud/merge work implied.


Complete locally: eight aggregate browser scenarios, nine unit tests, production frontend build and quality checks passed. [Folder-list verification](stage-6-folder-lists.md) includes corrected test assumptions and exact results. Stage 7 remains the next unapproved development stage.


## Stage 7 execution — authorized 2026-10-23

Owner requested a visible Recycle Bin → dashboard route and authorized Stage 7. Plan local recovery/security implementation now; no cloud resources, external messages, main merge or production deployment authorized. The OCI native-backup design remains four good points plus one in-flight slot. No approved OCI data volume, live CLI credentials, independent destination or notification channel exists; native capture/full-size restore and outside-VM delivery remain open acceptance gates, not substitutes for local tests.

### A — navigation correction
- [x] Add visible Back to dashboard button in Recycle Bin, retaining the menu route.
- [x] Prove desktop/mobile return, 65% desktop canvas and retained trash entries.

### B — recoverable local operational tooling
- [x] Implement bounded encrypted recovery bundles, explicit manifest/checksum verification and safe isolated restore; never extract into existing data.
- [x] Implement backup-slot/retention/age/failure state rules and local job monitoring without any implicit cloud resource creation or external sending.
- [x] Test corruption, wrong keys, interrupted/full destination and retention failures while preserving last good recovery points.

### C — integration and security rehearsal
- [x] Capture a consistent real disposable PostgreSQL/files/config snapshot; encrypted roundtrip and isolated restore verify users, files/icons/checksums, positions, trash/recovery metadata.
- [x] Run complete required local backend/frontend/browser checks, review authorization/container/dependency/secrets/log boundaries and record evidence.
- [x] Document recovery/key custody, scheduling/alert adapter and rollback runbooks with deployment-specific gates.

### D — live release gates (unverified)
- [ ] Fresh eligible/free OCI configuration approved before any native capture/restore.
- [ ] Native daily-job execution and retention/slot behavior, outside-VM failure/missed-job alert delivery, quota-safe full-size restoration and observed RPO/RTO verified.
- [ ] Stage 7 acceptance only after all required gates pass; local rehearsal alone does not complete this stage.


Stage 7 local milestones A–C passed: visible dashboard return; encrypted isolated recovery and migration ownership; 95 backend tests before/after PostgreSQL restore plus final 24 recovery-tool checks; 14 aggregate browser scenarios; bounded container logs, current package advisories and isolated frontend rollback. Native adapter/scheduler/outside-VM alerts and full-size OCI restore remain unimplemented/unverified behind D; Stage 7 is not complete. See [execution](stage-7-implementation.md), [evidence](stage-7-verification.md) and [runbook](recovery-runbook.md). No cloud resource, production cutover or merge.


Owner account update (2026-10-23): the owner confirms the account is still non-upgraded Free Tier and no cloud resources have been created since the previous review. This is owner-reported status, not an independently inspected console inventory, current SKU/capacity verification or resource-creation approval. Both browser connections failed to initialize with "failed to write kernel assets: The system cannot find the path specified. (os error 3)" before Oracle state could be read. Live gates remain unchecked.


## Stage 8 execution — preparation authorized 2026-10-23

Owner requested Stage 8 and selected a free DuckDNS address, hedowdohub.duckdns.org. Public DNS resolves to the owner-provided current connection address (not an OCI VM); no IPv6 answer was observed. No account/token was accessed or DNS changed by the agent. Stage 7's native backup/alert/full-size recovery gates remain open; cloud-dependent tests will require approved infrastructure. Starting Stage 8 preparation does not claim Stage 7 completion or authorize a final unreviewed resource configuration.

### A — production configuration and local rehearsal
- [x] Add production settings with secure cookies, one HTTPS origin, least-privilege runtime role and absolute storage root; preserve local development behavior.
- [x] Prepare a separate production Compose/Caddy profile with private API/database, bounded logs, read-only application roots, retained image references and data-volume bind guards.
- [x] Verify local TLS, HTTP redirect, authentication/Origin/proxy boundaries and persistence after container replacement in a new isolated synthetic project.
- [x] Run full PostgreSQL regression before/after restoration and document exact evidence.
- [x] Finish ARM64 image builds/emulated dependency execution and final source verification; native OCI execution remains a host acceptance gate.

### B — exact cloud configuration approval
- [ ] Independently inspect current subscription, all relevant existing usage, exact Jeddah draft/eligibility/costs, storage performance/address choices and SSH source.
- [ ] Present the final resource configuration and cost reconciliation, then obtain resource-specific approval before Create/Save/any cloud write.

### C — host, backup and public acceptance
- [ ] Provision only the approved resources; verify SSH/host image, measured data-volume capacity/UUID/permissions and startup mount dependencies.
- [ ] Point the registered name at the actual VM, verify public HTTPS/renewal and provision separate private production credentials.
- [ ] Complete Stage 7 native daily backup/retention/alerts/full-size recovery acceptance, then approved release deployment and host restart/rollback/end-to-end acceptance.
- [ ] Complete owner operational handover. No Stage 7/8 completion, cloud write, deployment or merge inferred from local preparation.

Current preparation evidence and actual unverified gates: [Stage 8 verification](stage-8-verification.md), [deployment procedure](deployment.md). Browser initialization again failed before OCI state could be inspected; owner-assisted fresh console evidence is required unless that connection is repaired.

Stage 8 preparation milestone A passed locally: 118 backend tests before/after database restore, isolated production-profile HTTPS/authentication/forwarding/persistence acceptance, both ARM64 builds and emulated binary checks, final Ruff/Prettier/secret/source checks. The working preview remains healthy. Milestones B/C and Stage 7 live gates remain unchecked. Next: fresh Jeddah console review and resource-specific cost approval; no cloud writes or production release yet.


## Live OCI progress — 2026-10-23

Owner completed the reviewed VCN/public subnet/internet gateway and default internet route through the console. Supplied security-list screenshots show SSH restricted to the owner's supplied /32, stateful public TCP 80/443 and retained ICMP rules. A fresh instance review showed Ubuntu 24.04 Minimal aarch64, A1 Flex 2 OCPUs/12 GB, existing public subnet, public IPv4 enabled, 50 GB Balanced boot/10 VPU with in-transit encryption and only Compute Instance Monitoring enabled. Published free allowances and the displayed EUR 1.98 estimate's tier-pricing exclusion were explained before the owner submitted Create. Owner screenshots confirm creation succeeded and instance Running. This supersedes earlier statements that no cloud resources exist; no additional cloud resource operation is inferred as approved.

SSH read-only checks succeeded using the newly owner-generated private key in Downloads; key contents were never printed or copied into the repository. Host: aarch64, Ubuntu 24.04.5 LTS, 2 CPUs, about 11 GiB reported RAM, cloud-init done, 50 GB boot disk with approximately 47 GiB root free. No separate data disk or Docker executable was present. Administrative access worked; effective SSH config has passwordauthentication no and pubkeyauthentication yes. SSH and rpcbind listeners were observed; the supplied OCI ingress list does not admit public rpcbind. Host firewall/patch/service hardening and external acceptance are still pending.

The first observed ED25519 host key is pinned in ignored .local/stage8/host-check/known_hosts; subsequent SSH used StrictHostKeyChecking=yes. This is trust on first use, not independent console fingerprint validation. Independently verify before sensitive release/configuration transfer. All remote commands this turn were read-only; no package, daemon, storage, DNS or application deployment change was made. Native backup/alerts/full-size restore and Stage 7/8 completion remain open. Next storage proposal: a separate eligible 150 GB data volume, giving 50+150=200 GB combined; review its exact form/eligibility and obtain specific approval before creation/attachment or filesystem initialization.


## Approved data-volume initialization — 2026-10-23

Owner supplied screenshots of the created 150 GB hedowdo-data volume, Available/Always Free, Balanced 10 VPU, Oracle-managed encryption, auto-tune/reservations/replication off and no backup policy. Owner attached it paravirtualized read/write to the reviewed VM with in-transit encryption. Read-only SSH inspection identified a separate 161061273600-byte /dev/sdb by its stable by-id serial, no partitions/mounts/filesystem signatures; the 50 GB boot disk remained separate. Owner explicitly approved ext4 initialization/mount after explanation.

The guarded script checked exact serial-derived by-id path, size, disk type, no signatures/mount and no existing target/fstab entry before non-forced ext4 initialization. Created filesystem UUID 63c9b747-a658-4a0d-8b1f-1a1dcc8a2ea9, mounted /srv/my-cloud-data and backed up /etc/fstab before adding the UUID mount with nodev,nosuid,noexec,_netdev. Created private files/caddy directories owned by 10001, postgres by 999 and root-owned configuration/releases directories. No extra resource or disk resize was performed.

First execution completed initialization/mount but exited 1 on a trailing carriage-return line introduced by the PowerShell text pipeline. It also revealed that the mounted ext4 root retained default mode 0755 despite the pre-mount directory mode. No formatting retry was attempted. Follow-up used exact LF bytes over subprocess stdin, set the mounted root to 0700 and tested UUID/ownership/mode after a controlled unmount/remount of this unused volume. findmnt --verify reported no errors/warnings. Final checks passed: root/files/caddy/postgres all mode 0700, intended owners, UUID correct and mount flags retained. Private evidence: .local/stage8/host-check/data-volume-verification.txt.

Measured filesystem total 157396975616 bytes, available 149327085568 bytes (about 149.3 decimal GB / 139.1 GiB). This supports the proposed 100 decimal GB pool with further DB/configuration/emergency headroom, subject to later measured operational checks. Persistent fstab remount passed; a full host reboot/missing-volume startup test has not run. No application/database/Docker install, production configuration/secret transfer, DNS update, native backup or release deployment occurred in this step. Native backup/alerts/recovery, independent host-key validation and Stage 7/8 release gates stay open.


Owner requested finishing deployment. Public DNS now resolves hedowdohub.duckdns.org to the approved VM; no IPv6 answer observed. The combined Docker/host-hardening execution was rejected by automatic approval review before running, requiring explicit scope approval because it installs a repository/daemon and changes persistent SSH/services. No host installation or SSH change from that rejected command occurred. Concrete proposal: [host approval scope](stage-8-host-approval.md). Await specific approval; DNS verification and proposal preparation completed independently.


## Approved host software and security controls — 2026-10-23

Owner explicitly approved the exact host scope in stage-8-host-approval.md after automatic approval review rejected the previous broad command. The resubmitted approved command ran: official Docker apt repository, Docker Engine/CLI 29.9.2, Compose 5.6.1, containerd 2.4.2 and Buildx 0.38.1 were installed. Docker is active/enabled, RequiresMountsFor=/srv/my-cloud-data is present, default logs are bounded to 3x10 MB, and journal caps were configured. The existing SSH key remains installed; sshd validation passed, root login/password authentication are disabled, and a fresh independent SSH connection succeeded. rpcbind service/socket are inactive and no longer listen on 111. Data-volume UUID/owners/private modes remained correct. A fresh native ARM64 hello-world container passed and was removed after completion; no app/database container was started. No host reboot occurred.

The initial local wrapper could not print a Unicode arrow in the install log using Windows cp1252. The remote log contained HOST_SOFTWARE_INSTALLED and effective SSH values; no installer rerun was attempted. Wrapper output was corrected to UTF-8 and the separate fresh-login/runtime checks passed. Private evidence: .local/stage8/install-host.sh.log and check-host.sh.log. Public application start, native backup IAM/capture/alerts/restore and release acceptance remain pending.

Owner explicitly supplied the operational alert email destination, including a test notification. The address is stored only in ignored local operational configuration. No subscription, external message or alarm has been created/sent yet. Native OCI API authorization remains absent; [backup-access preparation](oci-backup-access.md) records the next reviewed IAM steps.


## Native release preparation — 2026-10-23

Prepared immutable ARM64 API/frontend image archive (117103104 bytes), source archive and SHA-256 manifests; 146 selected source/config/document files, with ignored runtime files/private credentials and docs/evidence excluded. Transferred into a new private staging directory, then verified all archive and restored-source hashes on the VM before loading images. Root-owned staged release is /srv/my-cloud-data/releases/20261023-stage8. No public app or database was started. The initial staging preflight ran before SCP finished and refused the absent manifest without changes; after transfer completed the same checks passed. A Docker inspection template assumed an optional PostgreSQL Config.User field existed and stopped after image loading; a corrected inspection and separate native runtime checks passed without re-extracting/replacing the staged release.

Native OCI ARM64 checks passed for application/Psycopg import, Pillow encoding, Argon2 hashing/verification and Caddy execution. Image IDs match the local tested ARM64 artifacts; PostgreSQL 17.11-bookworm resolved to immutable sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27, ARM64, with postgres UID 999 verified. API/frontend run as UID 10001. Evidence: .local/stage8/stage-release.sh.log and check-release.sh.log. OS/image advisory review and the actual full-stack cloud workflow/recovery tests remain open; binary checks alone do not complete them.

Generated four independent new production secrets directly on the host into root-only mode-0600 /srv/my-cloud-data/configuration/production.env; no secret contents were printed, copied into Git or reused from development. Config fixes the real hostname/mount UUID, 100000000000-byte pool, 10000000000-byte reserve and immutable local image IDs. Actual Linux host preflight passed UUID/mount/private-owner/mode/measured-capacity checks; production Compose config --quiet also passed. Private evidence: .local/stage8/configure-release.sh.log. No first administrator was created. Public application startup, TLS, independent recovery-material custody, native backup API authorization/adapter/scheduling/alerts and full-size restore remain pending. Owner-provided email authorizes operational alerts/test notification, but no message/subscription was created.

Next dependency: owner-assisted OCI identity-domain dynamic-group/policy preparation, since browser runtime remains unavailable and SSH alone grants no OCI API privilege. See oci-backup-access.md. Do not create snapshots, delete recovery points, add monitoring resources or start production merely because host preparation passed.

Owner screenshots now confirm the single-instance dynamic group, Active hedowdo-backups compartment, and reviewed existing data-volume move into that compartment. Post-move read-only SSH verified the same mounted filesystem UUID, capacity and protective mount flags. Six restricted policy statements were presented for owner submission; successful policy creation/API authorization has not yet been evidenced. OCI SDK is absent on the host and local Python. No native backup, retention deletion, monitoring resource or public app start occurred; these acceptance gates remain open. See oci-backup-access.md for the source-volume compartment correction and current evidence.

Subsequent screenshots confirm the policy Active and its complete six restricted statements. Live read-only SDK authentication/inventory passed at 14:18 UTC: source data volume AVAILABLE, 150 GB, 10 VPU, correct compartment; zero combined boot/block backups across both Active compartments in the home region. An isolated, hash-locked OCI SDK 2.189.0 environment was installed on the existing VM; pip check and a 25-package OSV advisory query passed with no known findings. This supersedes the absent-SDK/API status above; backup creation/deletion and recovery are still untested. Local SDK download hit a proven full C: disk; only our hash-verified generated image-transfer archive was removed (remote archive/images retained), leaving about 279 MB locally. See oci-backup-access.md for evidence and first-native-backup-approval.md for the exact next cloud operation awaiting specific approval. No native backup/scheduler/alert or production app has been activated.

Prepared the guarded single-baseline capture after owner said "ok finish up". Automatic approval review rejected the command before execution because that broad instruction was insufficiently explicit for the specific cloud-resource mutation/cost-quota risk. No backup was created and no rejected operation was rerouted/retried. Exact script and procedure are reviewable; owner must explicitly approve the single Oracle backup before submission. Production, daily backup/recovery and outside-host alert gates remain open.

Owner then explicitly approved the exact single Oracle data-volume backup. Fresh quota/source/mount/idle-app checks passed and a single idempotent FULL baseline capture was accepted at 14:25:28 UTC. Independent GetVolumeBackup polling observed CREATING then AVAILABLE at 14:26:11 UTC, with correct source identity and 150 GB source size (4 GB unique backup size). No deletion, restored disk, schedule, alert or production startup occurred. This supersedes the pending first-backup status above, but full restoration, native daily coordination/retention, external alerting and launch acceptance remain open. The five-slot allowance is now expected to have one occupied slot; re-inventory before any further creation. See first-native-backup-approval.md for private evidence and quota-safe-restore-review.md for the next proposed cloud recovery operation.

Prepared the next restore decision concretely: full parallel restoration would exceed the 200 GB live-volume allowance, so the proposed prelaunch drill must release the unused data disk before restoring its 150 GB replacement. No destructive operation is approved or executed. Before asking for that specific decision, preserved a root-private safety copy on the existing server boot disk: all 151 files/118652776 bytes and directory UID/GID/modes/hash manifests matched, source unchanged and still mounted. Exact source UUID/no containers/no nested mounts/boot reserve guards passed. The available native backup remains retained. This reversible preparation does not demonstrate native restoration; see quota-safe-restore-review.md for the complete proposed sequence, capacity and availability risks.

Owner requested completion without further manual work and deferred password setup until the end. Rechecked both supported computer/browser control entry points after local disk space recovered: mcp__node_repl Computer Use initialization and cua_repl getState both fail before session creation with "failed to write kernel assets: The system cannot find the path specified. (os error 3)". No browser input occurred. A narrowly scoped read-only check found no installed OCI CLI command and no standard user .oci/config; no credentials were searched for or read. Available tool metadata contains no Oracle connector. Existing VM instance-principal rights deliberately do not authorize volume detach/delete/restore or notification resource management. Do not widen IAM, use hidden browser credentials or bypass these limits. No destructive restore action, notification setup or production startup was attempted in this turn. Password setup remains deferred as requested; final operational completion still needs working authorized Oracle control and recovery/alerts/release evidence. Do not claim the project finished or the website live.

Owner subsequently asked to commit the current project to GitHub. Preserve the implementation, test/evidence documentation and current incomplete deployment status on stage-8-deployment-readiness; do not merge main or activate any cloud deployment. Actual runtime data, .env/private keys, ignored .local/.cache evidence and SDK operational state remain excluded. Updated the README's outdated no-cloud-infrastructure statement to distinguish prepared resources/verified initial backup from the website's not-live status. A possible limited initial launch was discussed, but no launch, recovery deletion or acceptance-gate waiver occurred.

Checkpoint validation: Ruff lint/format passed; frontend ESLint/Prettier, production build and all 9 frontend unit tests passed. Selected Python identity primitives/production settings/preflight/recovery/secret-scanner tests passed 49/49, including real synthetic encryption/decryption, wrong-key and ciphertext-corruption checks. The first sandboxed attempt could not allocate its default pytest temporary directory; a workspace-temp rerun then hit the already documented GPG long temporary-path limitation. Repeating the same 49 tests with workspace pytest fixtures and the normal 36-character OS-private GPG temp directory passed (12.52 s), with no application code change. One existing Starlette/httpx deprecation warning remains. Existing full PostgreSQL/Compose/browser evidence is retained; those broader suites were not repeated for the checkpoint's README/status and trailing-blank-line cleanup. Common-secret scans and manual exclusion/template review passed; final staged scan/diff checks precede commit. No production acceptance claim is added.
