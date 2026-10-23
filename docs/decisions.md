# Decision and authorization log

Date: 2026-10-20 (Africa/Cairo). Keep approvals distinct from recommendations. See `plan.md` and `capacity-and-backups.md`.

| ID | Decision / evidence | Status and consequence |
| --- | --- | --- |
| D001 | Owner said "ok lets start with stage 1" after being asked whether to approve the revised plan and begin feasibility checks. | Approved to proceed with Stage 1 planning/account investigation. Record Stage 0 plan acceptance for this scope. No application implementation or provisioning authorized; proposed implementation defaults remain open. |
| D002 | Owner confirmed "No account yet". | Fact recorded. Account-level limits, home region, billing and availability cannot yet be verified. Owner signup is the next prerequisite. No account created by the agent. |
| D003 | Owner selected "No—evaluate OCI backups first" when asked about separate backup storage. | Approved investigation preference. Evaluate Option A first; does not accept residual account/provider/region risk or approve backup resources. |
| D004 | Candidate disk model: 50 GB boot + 150 GB data with 100 GB shared pool including trash/replacements/icons; 20 GB emergency reserve within data. | Proposed. Nominal arithmetic verified separately; account eligibility and measured filesystem headroom pending. |
| D005 | Native backup candidate: four retained successful daily data recovery points + one in-flight slot. | Proposed. Requires verification of account-wide slot availability, application consistency, full-size quota-safe restore and explicit residual-risk acceptance. No independent provider-loss recovery promised. |
| D006 | Sessions: 24-hour idle/seven-day absolute expiry; normalized case-insensitive collisions; retained replacement recovery; stale coordinate writes return conflicts; file limit 500,000,000 bytes; two uploads/user and four globally. | Originally proposed during Stage 1; recorded as Stage 2 contract defaults under later D018 authorization. Corresponding Stage 3+ feature approvals/testing are still required before implementation. |
| D007 | Duck DNS + Caddy; external health alert and backup notification route within free limits. | Candidate only. No domain chosen, account registered, alert delivery configured or TLS test run. |
| D008 | Full-size native restore cannot run in parallel with the full 200 GB disk allocation. | Verified planning arithmetic, not a live cloud test. Owner-approved disposable-source procedure or reduced initial pool required before declaring recovery proven. |
| D009 | RPO wording: daily scheduling is a target; completion lag/missed runs may exceed 24 hours of recoverable-data age. | Correction to unproven guarantee. Achievable RPO needs measured capture timing and owner acceptance at recovery gate. |
| D010 | Owner completed signup, confirmed Jeddah; Free Tier trial banner supplied. Regional A1 screenshot shows limit/available 16 cores and 96 memory, both usage 0. | Account evidence recorded on 2026-10-20; supersedes D002's absent-account prerequisite. Screenshot memory unit is not labeled. Quota does not imply permanently free entitlement or physical capacity; proposed limit stays 2 OCPUs/12 GB. |
| D011 | Owner supplied Block Volume screenshot: Jeddah regional/root scope, 200 GB free storage and five free backup slots, both usage 0; general backup quota 100,000. | Evidence recorded 2026-10-20. Nominal allocation fits displayed free quotas; general backup quota is not free entitlement. No provisioning, backup-risk acceptance or successful recovery implied. |

| D012 | Subscription screenshot confirms Free Tier / Promo and start date 2026-10-20. | Evidence recorded 2026-10-20; expected calendar trial end around 2026-11-19 under Oracle's 30-day rule, or earlier credit exhaustion. Exact expiry timestamp not displayed. Personal identifiers were not copied into documentation. |

| D013 | Owner authorized browser takeover to inspect a draft. Verified Ubuntu 24.04 ARM64, A1 Always Free-eligible at 2 OCPUs/12 GB and explicit 50 GB boot/10 VPU/encryption. Estimate EUR 1.98/month excludes tier pricing. | See `oci-draft-review.md`; draft only. No resource/stack created. Cost interpretation and incomplete network/SSH/plugin configuration remain gates. |
| D014 | Asked whether owner accepts four retained daily OCI backups plus one in-flight slot and same-account/region failure risk; owner instead requested a recommendation for their vision. | Recommend this as the practical $0 starting candidate with tested restore, while keeping independent-backup limitation explicit. Acceptance is still pending; no provisioning authorization inferred. |

| D015 | Owner said "make sure i do not pay anything, and come up with the best solution or best compromise as u recommend" after the backup recommendation and disclosed account-loss limitation. | Authorizes a planning recommendation within strict $0. Select non-upgraded Free Tier and native four-daily backups as the initial candidate; preserve independent-backup/availability limitations and recovery test gates. No need to repeat the same backup-selection question. No incomplete-draft provisioning, paid fallback or application implementation authorized. See `zero-cost-policy.md`. |

| D016 | Owner instructed "ok stage one cmon". | Continue Stage 1 now; produce `stage-1-assessment.md` with selected network/agent exclusions, no-cost DNS/TLS/alarm design and 200 GB full-size disposable restore sequence. No application implementation or provisioning inferred. |
| D017 | Final planning baseline excludes optional workload-protection/log-upload/run-command integrations; basic monitoring and bounded local logs remain. Use Duck DNS/Caddy and bounded OCI notifications/absence alarms. | Planning decisions, not applied live changes. Exact creation-time eligibility, secure access, DNS/TLS, alarm delivery and restoration tests remain release gates. |

| D018 | Owner explicitly said "ok proceed with planned stage 2" after the conditional assessment and local-development recommendation. | Approved local Stage 2 foundation and reasonable documented contract defaults. Feature branch `stage-2-foundation`; no later features, cloud writes, deployment or main merge authorized. Pending operational Stage 1 checks remain release gates rather than fabricated passes. |
| D019 | Docker executable absent from PATH/standard install path; WSL reports not installed. Owner answered "Install Docker Desktop" to the explicit installation question. | Downloaded official 4.95.0 installer after winget downloader stalled; verified published SHA-256 and Valid Authenticode signature. Per-user installer exited 1: VirtualMachinePlatform disabled, administrator setup/restart required. WSL elevation was canceled before setup started. No automatic reboot or successful Docker installation. Cached installer ready after owner completes the OS prerequisite; see `testing.md`. Native PostgreSQL testing is additional evidence, not a substitute for Compose tests. |

Historical checkpoint after Stage 3: Stage 4 required owner authorization, subsequently recorded as D023 below. Windows and Compose gates were resolved on 2026-10-21; see final acceptance below. Cloud resources remain unprovisioned.

Follow-up: owner clarified that no UAC prompt appeared. A fresh `wsl --status` still reports WSL not installed; no setup completion/exit marker exists. The launch returned cancellation, but this does not prove the owner deliberately canceled anything. Use manual administrator PowerShell rather than assume the prompt was visible or approved.

2026-10-21: owner reports WSL installed/restarted. Verified WSL 3.0.3.0/default 2, Docker Desktop installer exit 0, Docker 29.8.2 local Linux x86_64 engine and Compose v5.6.0. Windows prerequisite blocker is resolved. Remaining Stage 2 tests ran in a new disposable local Compose project; no cloud writes or later feature approval inferred.

| D020 | Completed Stage 2 local acceptance on 2026-10-21. | Clean Linux Compose build/start, empty/idempotent migration, runtime-role/UID/capability/port checks, metadata/file persistence across recreation, actual container backup/restore and desktop/mobile/unavailable/recovery browser tests passed. Removed unnecessary Caddy file capability and obsolete runtime pip; fixed Windows verification log decoding. Actual runtime Python inventory audit: zero known findings. See `stage-2-compose-verification.md`. Stage 3, public deployment, cloud writes and main merge still require their approvals. |

| D021 | Owner explicitly said "ok stage 3 now" on 2026-10-21. | Authorizes planned local identity, invitations, sessions and administrator controls on stage-3-identity. Scope/files/risks recorded in stage-3-implementation.md. Tests use disposable local databases/projects and synthetic accounts only; existing volumes preserved. No real owner password chosen by the agent, no Stage 4+, cloud writes, main merge or deployment. |

| D022 | Completed Stage 3 local acceptance on 2026-10-21. | All identity/security/concurrency and persistence/recovery gates passed: 24 backend tests before/after real restore, five frontend tests, Linux Compose recreation/session/identity recovery, audits and desktop/mobile/browser workflows. Follow-up resolved the browser-input test blockage; inline cancellation/deactivation, logout and inactive-login rejection verified. See stage-3-verification.md. No Stage 4, cloud writes, main merge or production deployment authorized. |

| D023 | Owner said "ok lets proceed with stage 4" on 2026-10-22. | Authorizes planned local durable file API and its integration/recovery testing on stage-4-file-service. No Stage 5 UI, OCI writes, deployment or main merge. Scope and protocol are recorded in stage-4-implementation.md. |
| D024 | Real deleted-parent regression proved active upload reservation dropped prematurely under CASCADE. | Preserve applied 0003 and add immutable 0004_transfer_parents with nullable SET NULL parent. Transfer keeps its slot/bytes until cleanup and rejects finalization into a removed destination. Exact regression and recovery testing recorded in stage-4-verification.md. |

| D025 | Completed Stage 4 local acceptance on 2026-10-22. | Final 0004 revision: 53 backend tests before/after restore; real Linux 500 MB transfer, recreation and file/database restoration passed. Source/frontend/dependency checks passed; see stage-4-verification.md. Stage 5, cloud provisioning, main merge and deployment remain gated. |

| D026 | Owner said "ok lets proceed" after the next-stage explanation on 2026-10-22. | Authorizes local Stage 5 responsive file manager, previews/icons and administration on stage-5-file-manager, including necessary API/migration extensions and tests. Scope, safeguards and milestones: stage-5-implementation.md. No Stage 6, cloud writes, publication, main merge or production deployment. |

| D027 | Stage 5 review identified a missing administrator retry path for safely retained partial deletions. | Within the authorized administrator/recovery scope, expose only pending already-confirmed jobs and a CSRF/role-protected idempotent retry; no new permanent-deletion intent. Existing original confirmation is retained. Acceptance includes denied member/CSRF requests and completion/retry. |

| D028 | Completed Stage 5 local acceptance on 2026-10-22. | Final 66 backend tests before/after restore, seven frontend unit and six browser scenarios passed. Linux 500 MB transfer/recreation and file/icon restoration passed, along with source/advisory/secret checks. Exact corrections, rate-limiter test-fixture reset and synthetic credential rotation are recorded in stage-5-verification.md. No Stage 6, cloud provisioning, main merge or deployment inferred. |

| D029 | Owner said "okay lets go next stage go go go" on 2026-10-22. | Authorizes local Stage 6 spatial dashboard on stage-6-spatial-dashboard. Existing schema and dependencies suffice; scope, risks and tests are in stage-6-implementation.md. No Stage 7, cloud resources, merge or deployment authorization inferred. |
| D030 | Stage 6 concurrency review identified that parent plus reset position revision alone cannot detect an item moved away and back. Browser testing also reproduced first-click details resize moving nodes before double-click. | Include current item revision alongside the independent position revision; a file change requires explicit refresh. Keep a stable desktop details column to preserve pointer targets. Theme changes preserve the viewport; keyboard focus reveals offscreen nodes. Exact acceptance and corrections: stage-6-verification.md. |

| D031 | Completed Stage 6 local acceptance on 2026-10-22. | 72 native tests before/after restore, nine frontend unit and all nine browser scenarios passed; 86 positions survived Linux recreation/restore. Active-pan/zoom p95 at 20/100/500 nodes was 2.9/8.3/13.9ms on documented hardware after disabling the dense-folder core pulse. Source/quality/visual checks passed; see stage-6-verification.md. Stage 7, cloud provisioning, merge and deployment retain approval gates. |

| D032 | Owner clarified the desired main screen and answered layout questions on 2026-10-23. | Authorizes local Stage 6 refinement: full viewport/minimal floating controls, navigation/upload initially closed, details overlaid when accessed. Search/storage/account move into the menu; no document scrolling on the dashboard. Supersedes the reserved desktop details column from D030, while preserving pointer stability through delayed single-click details. Acceptance: stage-6-immersive-layout.md. No Stage 7, backend, cloud, merge or deployment authorization inferred. |

| D033 | Completed the owner-authorized immersive refinement on 2026-10-23. | Viewport/overlay/menu/file-picker/focus and repeated-reset/navigation checks pass; all eleven browser cases and nine frontend unit tests pass after targeted fixture corrections. Measured pan/zoom p95 8.3/8.3/22.2ms at 20/100/500 nodes. Full report: stage-6-immersive-layout.md. Stage 7 and cloud/release/merge approvals remain open. |


## D034 — Manual organization and consistent icons (2026-10-23)

Owner chose consolidation of only test/demo items and explicitly declined automatic grouping, expecting modest quantities organized into larger folders. Keep fixed 76px screen-space nodes, initial framing and optional zoom/pan. Preserve saved coordinates, folder semantics and user content; no automatic clustering or rearrangement. Execution and acceptance: [consistent icons](stage-6-consistent-icons.md).


## D035 — Locked 65% and spatial recycle bin (2026-10-23)

Owner explicitly replaced adjustable camera scale with 65%, requested a bottom-left bin for dragging items to shared trash, and removed visible routine status messages. Keep fixed icon size and manual folders. Panning, fixed-scale Recenter and keyboard reveal preserve access to distant nodes; no automatic fit scaling. Bin moves are reversible and revision-checked. Visible errors/conflicts remain separate from screen-reader-only routine status. [Executed acceptance](stage-6-locked-canvas-trash.md).


## D036 — Folder lists with spatial home (2026-10-23)

Owner confirmed folders open as lists and files retain previews. Navigation resets grid and selects spatial only for the root, so breadcrumb/menu return restores the desktop 65% dashboard. Explicit view controls remain available. No changes to shared placements or stored content. [Acceptance](stage-6-folder-lists.md).


## D037 — Stage 7 local authorization and visible dashboard return (2026-10-23)

Owner requested an obvious Recycle Bin → dashboard action and authorized Stage 7. Implement/test local encrypted recovery, monitoring/retention policies, rollback and security review; retain all live OCI cost/configuration/resource/production/merge gates. Native OCI remains the chosen full-size backup design. The bounded local bundle and disabled static-sample timers are rehearsal tools, not daily 100 GB application backups. Native adapter/scheduling, outside-host alerts and quota-safe full-size restoration remain open. [Execution](stage-7-implementation.md), [tests](stage-7-verification.md).


## D038 — Stage 8 preparation and free DNS (2026-10-23)

Owner authorized Stage 8 and registered hedowdohub.duckdns.org after selecting free DuckDNS. Its current A answer matches the owner-provided connection; it must be changed to the approved VM address after provisioning. Prepare/test production settings, separate Compose/Caddy, mount/config preflight and architecture artifacts locally. This overlap is necessary because Stage 7 native resource tests require a host; it does not waive those tests or final eligibility, resource-specific cost approval, deployment or merge gates. No real credentials or owner IP are copied into repository documentation. [Deployment procedure](deployment.md), [Stage 8 evidence](stage-8-verification.md).
