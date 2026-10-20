# AGENTS.md — Personal Cloud Storage

## Purpose and authority
This repository contains a private, invitation-only, shared cloud storage web application with a custom spatial dashboard. These instructions govern all Codex work in this repository. Do not assume any unapproved functionality is in scope.

**MANDATORY FIRST ACTION:** Before every substantive task, read `docs/plan.md` and applicable documentation under `docs/`. If `docs/plan.md` does not exist, do not start implementing application code: first create a proposed implementation plan in `docs/plan.md` and present it for owner approval. The initial assignment after reading this file is **planning only**, not implementation. Record material decisions, deviations, progress, blockers, and verification evidence in `docs/` and keep `docs/plan.md` accurate.

## 1. Project requirements

### Users and permissions
- Private, invite-only system for **1–5 registered users**, sharing **one common storage pool and file/folder space**. No public self-registration.
- An administrator generates unique, single-use, revocable invitation links that expire after **24 hours** (initial default). Invited people create accounts with email and password.
- All invited users may browse, upload, download, create folders, rename, move, replace files (with confirmation), and send files/folders to a shared recycle bin and restore from it.
- **Only an administrator can permanently delete** files or folders. Enforce authorization on the server; never depend on UI visibility for access control.
- Shared canvas icon positions and file organization are visible to all invited users.
- Admin console: user management (view/deactivate/revoke), invitation management (create/view/revoke), storage dashboard, activity monitoring/filtering, and recycle bin management. Admin features are invisible to unauthorized users and inaccessible via API.
- Email/password authentication; secure logout, session expiration, secure password hashing, and no 2FA requirement in MVP.

### MVP file management
- Upload/download **all file types** (max **500 MB per file**, validated on the backend), create/organize folders, drag-and-drop uploads, supported file previews, search, recycle bin, and detailed activity history.
- Accept a **custom icon/image per uploaded file**; allow editing later. If unspecified, show a recognizable default file-type symbol inside a softly glowing node. Validate and safely process icons; never execute uploaded content.
- Filename collisions within the same folder: ask user to **Replace**, **Keep Both** (assign a unique name), or **Cancel**. Explicitly confirm replacement and log it. Implement replacement safely to minimize accidental loss; detail recovery behavior in the plan.
- Detailed activity records: uploads, downloads, renames, moves, folder creation, replacements, recycle-bin moves, restorations, and permanent deletion, with actor, action, target, and timestamp.
- Shared recycle bin: users may move items there and restore them; only administrator may permanently delete them. No automatic permanent deletion unless separately approved.
- Responsive web app, accessible by browser on desktop/tablet/mobile; **online only**. Downloads work offline after downloading; no offline sync/caching requirement.
- Search by filename; filters by file type, upload date/date range, and uploader; sort by name, size, and date. Collapsible advanced filters.

## 2. Limitations and non-negotiable constraints
- **Budget: strictly $0/month**, permanently free resources only. No trial-only resources, paid add-ons, unapproved subscriptions, or surprise billable infrastructure. Before provisioning, changing, resizing, or upgrading any cloud resource, establish current Always Free eligibility, explain potential costs, and obtain explicit owner approval. Never assume the provider will prevent charges.
- Provider: **Oracle Cloud Infrastructure (OCI) Always Free**; Ubuntu Linux VM. Free VM capacity/availability, quotas, and exact storage limits must be checked at deployment time. Never claim provisioning or zero-cost operation is guaranteed.
- **Target 100 GB shared storage**, subject to verified free-tier disk allocation, boot volume, database, logs, reserves, and backup overhead. Treat 100 GB as a target rather than a proven usable amount. Reject any plan that silently exceeds free quotas; bring infeasibility to owner with alternatives and trade-offs.
- **24/7 availability target**, not a guaranteed SLA. Auto-restart services after server restart or process failure; basic health checks/logging.
- **Automatic daily backups** of files, database, and essential configuration with encryption and tested restoration. Backups should be separate from primary failure domain where feasible; a backup on the same disk is not sufficient protection from disk/provider loss. **Do not promise full daily 100 GB copies within free-tier storage.** Propose realistic incremental/deduplicated strategy, retention, off-server destination, capacity calculations, and recovery tests in `docs/plan.md`; if strict $0 and safety cannot both be met, stop and request owner decision before claiming this requirement is fulfilled.
- Usage warnings at **80% and 90%**; reserve emergency space for OS/database/system operations and prevent uploads that would consume that reserve. Define thresholds based on actual usable disk capacity, not nominal advertised allowance.
- **Enhanced security:** HTTPS, Argon2id password hashing, secure cookies/sessions, authentication rate limiting and attack protection, expiring single-use invite tokens, session expiry, least privilege, SSH restrictions, firewall, monitoring, server-side authorization, validation of uploads, safe content-disposition/content-type for downloads and previews, no server execution of uploads. Implement secure-by-default protections appropriate for a public HTTPS endpoint.

## 3. Technical decisions
- **Frontend:** React + TypeScript + Vite; responsive custom UI.
- **Backend:** Python + FastAPI; REST API. JSON for application metadata, multipart/streaming transfers for files; document via FastAPI OpenAPI. Authenticate/authorize each protected endpoint. No WebSockets required for MVP; refresh/background fetch is adequate.
- **Database:** PostgreSQL for users, folder trees, file metadata, invitations, permissions, audit/activity, trash status, and saved positions. **Actual file contents on persistent block storage**, not in database.
- **Deploy:** Docker + Docker Compose for frontend, API, and PostgreSQL with appropriately persisted DB and file volumes. No Kubernetes. Run locally and test before deploying to OCI.
- **Host:** OCI Always Free Ubuntu VM with eligible persistent cloud disk; free subdomain and HTTPS; evaluate a reverse proxy such as Caddy and a suitable free DNS/subdomain provider. Verify domain and TLS renewal feasibility.
- **Updates:** Manual deployments with Codex assistance **only after owner approval**, with preserved data and documented rollback/recovery procedures. No automatic production deployment.
- **Repository:** One GitHub monorepo with `frontend/`, `backend/`, `infrastructure/`, `scripts/`, `docs/`, root `AGENTS.md`, `README.md`, and Compose configuration. This is a conceptual structure; refine in the approved plan. Never commit actual uploads, database data, secrets, or private credentials.
- **Schema migrations:** Versioned Alembic migrations, tested locally with verified backup and realistic recovery plan before production. Explicit approval for destructive operations.

## 4. Design scheme and UX
- **Overall:** polished but **simple, intuitive, calm, and usable**; artistic but practical. Avoid clutter and excessive effects.
- **Desktop visual:** freeform spatial dashboard centered on a **minimal futuristic glowing abstract/geometric core** (inspired by a brain/black hole without literally depicting either). Files appear as floating nodes, connected to core with **faint thin glowing lines that brighten on hover/selection**.
- **Icons:** custom image/icon optional for every file on upload and editable later; otherwise conventional type symbol in glowing node. File names **hidden by default**; show full name on hover and make discoverable via touch, keyboard focus, and accessibility text.
- **Motion:** slow **gentle floating plus very subtle vibration/pulse**, unsynchronized, low amplitude. Motion is relative to saved placement; pause visual motion during drag. Support `prefers-reduced-motion` and accessible focus/contrast.
- **Placement:** newly added files automatically placed in available areas around the core; users can **drag icons anywhere** (not grid-snapped), and shared coordinates persist across refresh and login. Dragging existing icons and dropping files to upload are distinct interactions. Define behavior for conflicts, small viewports, zoom, and many files in the implementation plan.
- **Single click:** selects and highlights connection, opens **right-side details panel** (name, type, size, thumbnail, actions). **Double click:** opens a file or folder. Supported images/PDFs/videos display **large centered modal preview**; unsupported file types offer metadata/download. Click empty canvas to deselect. On touch: tap/select and explicit Open action; accessible keyboard alternative.
- **Sidebar:** collapsible. Contains search, Upload, New Folder, Activity History, Recycle Bin, admin-only dashboard, storage consumption/progress bar, light/dark toggle, and user/account menu. Search's advanced filters are collapsible.
- **Colors:** soft blue and lavender. **Light mode is default**: off-white `#F8F9FC`, pale blue `#DDE7FF`, soft blue `#AFC7E8`, lavender `#B9ADF0` as initial design tokens; derive readable dark charcoal/navy mode with complementary accents. Persist each user's theme choice. Meet readable contrast/focus requirements despite pale decorative colors.
- **Mobile:** traditional, responsive file list/grid with compact menu and full core file-management functionality (rather than the artistic spatial canvas).
- **Empty state:** softly animated central core and clear **Upload your first file** CTA, with subtle guidance.
- **Performance:** practical 60 FPS goal on capable devices without sacrificing functionality. Avoid excessive React renders, lazy-load previews, stream transfer, efficient drawing of connections, and throttle/limit costly animation and render effects. Measure before deep optimization.

## 5. Coding standards and Codex operating protocol

### Architecture and quality
- Clean, modular design. Keep UI components, client API access, backend domain/service logic, authorization, database persistence, and file storage operations clearly separated. Favor reusable, understandable components; avoid needless abstractions, premature microservices, and duplicate code.
- Python: **Ruff** lint/format. Frontend: **ESLint + Prettier**. Check before proposing merges.
- Controlled dependencies: favor established, maintained, free, open-source packages; justify new packages, assess compatibility/license/security advisories, lock versions, verify after changes. No unnecessary dependencies.
- Strict secret management: development and production secrets separate, no hardcoded secrets, no committed `.env`/keys, least privilege, rotation procedures, pre-commit secret scanning, and never expose secrets in docs, logs, or responses. Provide safe example templates without secrets.
- Logging: structured timestamps, severity and request/correlation IDs; user-friendly error messages separate from secure diagnostic details. Never log credentials, tokens, sensitive file contents, or unnecessary personal data.

### Tests and evidence-first debugging — MANDATORY
- Balanced automated testing: unit tests of important logic, integration tests for API/DB/storage, and a few end-to-end tests covering invitations/login, upload, duplicate handling, browse, rename/move, preview/download, search, trash/restore, admin-only permanent delete, and authorization. Run relevant tests after changes; never claim a test passed unless it was executed.
- For **every bug or error**: (1) reproduce/prove the failure with exact observed evidence; (2) inspect logs, tests, traces, and code; (3) identify a **verified root cause** and distinguish it from hypotheses; (4) explain a targeted fix, why it addresses the proven cause, affected files and risks; (5) obtain approval before a substantial code change; (6) implement; (7) **prove resolution** by repeating the failing case and running regression tests; (8) report actual evidence. No guessing, symptom-patching, unsupported certainty, or claims of success without verification.
- If evidence is insufficient, explain what is unknown, what evidence is needed, and the safe investigation steps before attempting a speculative fix.

### Approval, planning, and scope
- **On first run: write a plan, not code.** Read this file and `docs/plan.md` if present; if absent, draft `docs/plan.md`. Include phases, task dependencies, acceptance criteria, data model, API design, frontend interaction implementation, threat model, free-tier resource/billing verification, capacity/backup feasibility, test plan, deployment/recovery plan, and clear owner approval checkpoints. Present plan for approval before building the app.
- **Always review `docs/plan.md` before proceeding** on subsequent tasks. All planning/execution documents go under `docs/` (except the repository-level `AGENTS.md` and normal root setup files like `README.md`). Maintain practical documentation: architecture, APIs, deploy, testing, decisions. Avoid comments/documents that merely restate obvious code.
- For each substantial feature or change, explain proposed approach, files affected, risks and alternatives **before coding**, and obtain owner approval. Investigate blockers with evidence, propose justified options, and escalate significant changes. Document unresolved blockers in `docs/plan.md`.
- **Strict MVP scope:** implement only approved requirements. Do not independently add features, services, architectural expansions, or paid options. Propose and seek approval first.
- Feature branches for substantial work and fixes; keep `main` stable. Descriptive commits. Test and review changes before proposing a merge; **never merge to `main` or deploy to production without owner approval**.
- Protect data: preserve volumes and files through deployments; test versioned migrations, verify backups before risky operations, and plan recovery. No destructive cloud, database, file-storage, or secret changes without explicit approval.

### End-of-task report
After each development task provide a concise structured report specifying:
1. **Work done** and why, mapped to approved requirements / `docs/plan.md`.
2. **Files changed** and significant design consequences.
3. **Verification evidence**: actual commands/tests run, outcomes, and explicit untested items.
4. **Remaining issues, limitations, and risks**.
5. **Plan updates**, next step, and any owner decision needed.
For a bug fix add before/after reproduction evidence, verified root cause, rationale for correction, and proof of resolution.

## Initial Codex instruction
**Do not implement the application yet.** Inspect this repository and this `AGENTS.md`. Draft a comprehensive but practical `docs/plan.md` for review, including explicit validation of strict $0 OCI Always Free deployment, realistic capacity (100 GB goal plus reserve), automatic daily backup feasibility, security, data integrity and recovery, interactive dashboard, task sequencing, test/acceptance criteria, and points requiring owner approval. Clearly flag conflicts or infeasible constraints rather than silently weakening them. End with a summary and ask for approval of the plan before creating application code or cloud resources.
