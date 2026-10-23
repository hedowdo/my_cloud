# Stage 5 implementation - 2026-10-22

Owner authorized "ok lets proceed" after the Stage 5-8 sequence and Stage 5 scope explanations. Branch stage-5-file-manager. Local existing checkout only; preserve volumes and secrets. No cloud resources, publication, main merge or Stage 6 spatial canvas.

## Milestones and acceptance checklists

### 1. Browse/search contracts
- [x] Extend server browse with bounded type/date/uploader filters and stable name/size/date sorting; add shared uploader directory and bounded filtered activity/admin views.
- [x] Test filters across pagination, invalid input, ancestor visibility and member/admin isolation against real PostgreSQL.

### 2. File manager and transfers
- [x] Build responsive sidebar, breadcrumbs, list/grid, selectable details, folder picker and revision-aware rename/move/trash/restore/delete dialogs.
- [x] Implement actual multipart metadata-first uploads with progress/cancel/errors and explicit Replace/Keep Both/Cancel, including revalidation on races.
- [x] Test browser upload/browse/download, all duplicate decisions, mutations, stale/error/loading paths and keyboard/touch access.

### 3. Preview and custom icons
- [x] Add independently authenticated format allowlists, bounded image decode/re-encode, PDF canvas rendering without a scripting layer and safe video/range delivery. Unsupported files remain downloadable.
- [x] Implement optional on-upload and later edit/remove icons: bounded raster inputs, stripping metadata via PNG re-encoding, quota/reservation accounting and durable retirement cleanup.
- [x] Test spoofed MIME/extensions, SVG/HTML rejection, bad images/decompression limits, byte ranges, private access, stale icon edits, failure/recovery and content integrity. Original uploads remain unchanged.

### 4. Activity, administration and acceptance
- [x] Add shared activity filters, Recycle Bin, storage/warnings, administrator people/invitation/storage/activity management and per-user persisted light/dark choice.
- [x] Verify desktop/tablet/mobile, focus/Escape/dialogs, touch Open, contrast and error recovery; execute full backend/frontend/Compose recovery and dependency/secret/quality checks.
- [x] Record actual evidence and mark Stage 5 complete only after all gates pass.

## Design and risks

Keep established React/TypeScript/FastAPI/PostgreSQL/Caddy architecture and blue/lavender tokens. Feature UI belongs in separate components and API helpers. Previews must not render arbitrary HTML/SVG or execute PDF scripting. Images use bounded Pillow decode and metadata-free PNG output; PDF pages use local PDF.js canvas rendering without annotation/form/scripting layers and a CSP excluding eval/inline scripts; video uses independently authenticated byte ranges with a signature/extension allowlist. Limits and fallback messages are explicit. New Pillow/PDF.js packages require lock/license/advisory review. No external CDN or preview service.

Custom icons use existing private blob storage and shared quota. New additive migration journals superseded icon blob cleanup; detach is committed before unlink, unreferenced old bytes remain charged until retry succeeds. No automatic deletion of ordinary trash/recovery. Namespace/session/revision checks occur again at publication. All transfer cleanup preserves uncertain committed references.

Tests use synthetic users and isolated local file/database roots. Production ARM64, HTTPS, current OCI free-tier capacity and scheduled daily encrypted cloud backup/full-size restore remain later release gates. The 100 GB target is not a measured local capacity.

All local gates passed; [executed evidence, corrections and limits](stage-5-verification.md). Stage 6 and all cloud/release operations remain gated.
