# API contract

Base prefix: `/api`. Health and Stage 3 identity endpoints are implemented; Stage 4 file endpoints below are implemented; Stage 5 previews/icons are implemented; spatial operations remain planned. Development schema is generated at `/openapi.json` and UI `/docs`. Metadata uses JSON; later transfers stream multipart content. No WebSocket dependency.

## Implemented

| Request | Result |
| --- | --- |
| GET /api/health/live | 200 `{ "status": "ok" }` independent of DB readiness. |
| GET /api/health/ready | 200 `{ "status": "ready" }` only with the expected migrated DB and a writable file volume; otherwise 503 `{ "status": "unavailable" }`. No diagnostic internals disclosed. Internal-only in production. |

Responses include generated `X-Request-ID`, `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. Identity structured errors use `{ "error": { "code": "...", "message": "...", "request_id": "UUID" } }`. Never return credentials, submitted password/token, database errors, SQL, uploaded contents or private storage paths.

## Route roadmap (implemented contracts below are authoritative)

| Area | Routes and semantics |
| --- | --- |
| Administrator (Stage 5) | GET `/admin/activity`, `/admin/storage`, `/admin/trash`. Every request role-checked. Stage 3 account/invitation routes are implemented below. |
| Browse (Stages 4/5) | GET `/items` folder/query/type/uploader/from/to/sort/direction plus cursor, bounded limit 1–100; stable `(sort field,id)` ordering; only live ancestor chains. GET `/items/{id}` returns metadata/revision and permissible actions. |
| Namespace (Stage 4) | POST `/folders`; PATCH `/items/{id}` rename/move requiring expected revision; folder create/rename key uniqueness and cycle prevention under namespace lock. |
| Transfers (Stage 4) | POST `/uploads` streamed multipart with parent, desired name, collision decision and expected target revision for replace; cancel means no mutation. Collision preflight can aid UI but final transaction rechecks. GET `/items/{id}/download` checks active membership and streams safe attachment. |
| Preview/icon (Stage 5) | GET `/items/{id}/preview`; PUT/DELETE `/items/{id}/icon`; private content authorized independently of UI. Preview formats explicitly allowlisted; unsupported content stays attachment. |
| Trash (Stage 4) | POST `/items/{id}/trash`, `/restore`; GET `/trash`; DELETE `/trash/{id}` administrator-only permanent delete with confirmation/revision. Restore collision requires explicit decision/destination. |
| Spatial (Stage 6) | GET `/folders/{id}/positions`, PATCH `/items/{id}/position` finite logical coordinates and expected revision; shared background refresh must not interrupt drag. |
| User activity/storage | GET `/activity`, `/storage`; paginated shared file activity and counted committed/reserved pool bytes, 80%/90% warnings; administrator security events excluded from ordinary-user history. |

Each route gains explicit Pydantic request/response models when its feature is implemented; OpenAPI must match executable behavior. All protected requests check active user, server-side session/expiry, CSRF/origin for mutations, target authorization and admin role where needed. Authentication failure 401, insufficient privilege 403 (or consistent 404 for unavailable item), missing resource 404, stale revision/name collision 409, invalid input 422, file limit 413, throttling 429, insufficient reserved storage 507. Cancelled upload must not return fabricated success.

Detailed activity records distinguish server stream completion from confirmed client receipt. A download log does not prove the user's device saved the whole file. Range request/preview behavior and audit aggregation are finalized with transfer implementation, not assumed from this skeleton.

## Implemented Stage 3 identity API

All paths below use /api. Identity mutations require Content-Type application/json, an exact allowed Origin and at most 16 KiB of actual body bytes. Authenticated mutations also require X-CSRF-Token from the current readable CSRF cookie. Send {} for no-field POST bodies. No public registration/bootstrap endpoint. Response models expose only the listed public fields, never password/digest records.

| Method/path | Input and response | Access |
| --- | --- | --- |
| POST /auth/login | email/password; 200 user and rotated session/CSRF cookies | Anonymous, rate limited |
| POST /auth/invitations/redeem | email/password/token; 201 member user and rotated cookies | Valid unused/unrevoked/unexpired invitation; atomic five-user cap |
| GET /auth/me | user, csrf_cookie name, expires_at | Active unexpired session |
| POST /auth/logout | {}; 204, server revocation and cleared cookies | Session + CSRF |
| PATCH /users/me/preferences | theme light/dark; 204 | Session + CSRF |
| GET /admin/users | Public user array: id/email/role/active/theme | Administrator |
| PATCH /admin/users/{id} | active=false only; 204, revoke all target sessions | Administrator + CSRF; self/last-admin protection |
| POST /admin/users/{id}/revoke-sessions | {}; 204 | Administrator + CSRF; use logout for self |
| GET /admin/invitations | Latest 100 id/created_at/expires_at/redeemed_at/revoked_at records | Administrator |
| POST /admin/invitations | {}; 201 id/token/expires_at; raw token returned once | Administrator + CSRF; max 20 outstanding |
| POST /admin/invitations/{id}/revoke | {}; 204 | Administrator + CSRF |

There is no reactivation or role-promotion API in Stage 3. A deactivated registration still counts toward five accounts. Login errors are generic 401; unavailable invitations 400, unauthorized 401, role/CSRF/origin failures 403, malformed/extra fields 422, oversized metadata 413, non-JSON 415, conflicts/capacity 409, throttling 429 with Retry-After. Invitation links put the raw token in a browser fragment, never a query string. The one-shot administrator create response is the only raw-token disclosure.

## Implemented Stage 4 file API

All routes are session-protected. JSON mutations require exact allowed Origin, session-bound X-CSRF-Token, application/json and at most 16 KiB; extra fields are rejected. Multipart uploads require the same authentication/Origin/CSRF controls before bytes are consumed. Shared file space is common to all active members; permanent deletion and deletion-job inspection require administrator role on the server.

| Method/path after /api | Input/result |
| --- | --- |
| GET /items | parent_id (root default), q literal name substring, limit 1-100, offset 0-100000; stable name_key/id order; live children only |
| GET /items/{id} | Public metadata/revision/size/checksum; excludes trashed ancestors or pending deletion |
| POST /folders | name, parent_id, collision error/keep_both; 201 public item |
| PATCH /items/{id} | expected_revision plus optional name/parent_id and collision error/keep_both; 200 item |
| POST /uploads | Streaming multipart: metadata JSON first, file second; 201 item after durable publication |
| GET /items/{id}/download | Authenticated octet-stream attachment, safe UTF-8 disposition, nosniff/CSP, Content-Length and SHA-256 ETag; opened snapshot descriptor |
| POST /items/{id}/trash | expected_revision; 200 changed item; a trashed folder hides its descendants |
| GET /trash | Explicitly trashed roots/recovery items, bounded limit/offset; pending deletion excluded |
| POST /items/{id}/restore | expected_revision, optional parent_id/name, collision error/keep_both; missing/trashed original parent requires live destination |
| DELETE /trash/{id} | Administrator, expected_revision and confirm=true; returns durable deletion job state pending/complete, not a fabricated deletion success |
| GET /admin/deletions/{id} | Administrator-only job state, item_count and non-sensitive last_error; no storage keys |
| GET /storage | used/reserved/pool/available bytes and warning_percent null/80/90 |
| GET /activity | Bounded limit/offset file events in descending time/id order; security events excluded |

Public item fields: id, parent_id, kind, name, revision, uploader_id, size_bytes, checksum_sha256, created_at, updated_at, trashed_at, replacement_of. No blob IDs, storage paths or private keys are returned. All metadata/status/event responses use explicit response schemas.

Multipart metadata: name, parent_id (root default), size_bytes (required integer 0-500,000,000), collision (error/keep_both/replace/cancel). Replace additionally requires target_id, expected_revision and confirm_replace=true. A conflicting name with default error returns 409; Keep Both is allocated again under the final transaction lock. Replace retains the stable ID and old contents as a charged trash recovery item. Cancel returns upload_cancelled/409 without creating durable metadata. Multipart filename/media type do not control storage paths or inline rendering.

Use exactly a metadata JSON form field (at most 4096 bytes, before the file) and one file part. Part headers are capped at 8192 bytes; overall wire overhead is capped at 32768 bytes beyond the file maximum. Actual bytes are counted independently of Content-Length. Underflow is 422, overrun is 413; a 30-second receive idle timeout is 408. Reserved capacity is checked before accepting file bytes; quota/disk reserve failure is 507, upload concurrency 429, stale target/revision/name/tree conflicts 409, storage I/O failure 503. Inactive/revoked/expired sessions cannot finalize an in-flight upload.

Range/inline preview delivery is not implemented: Range headers receive the normal complete 200 attachment. Previews, custom icons and full browser file UI remain Stage 5. Deactivation does not retroactively interrupt a download already authenticated/opened; new access is denied. Download history records server_stream=complete/interrupted, not verified device receipt.

## Implemented Stage 5 file-manager contracts

- GET /api/browse: parent_id, literal q, category all/folder/image/pdf/video/document/archive/other, uploader UUID, timezone-aware after/before, sort name/size/date, direction asc/desc, scope folder/all, limit 1-100 and offset 0-100000. Filter before pagination; sort-field/id order is stable. File-type filters classify filename extensions for discovery only, never to authorize content rendering. All-folder search traverses only live ancestor chains. Date controls use UTC inclusive day bounds.
- GET /api/collisions: parent_id/name returns public conflicting item or null using the server's NFC/casefold rules. A preflight is advisory; upload publication rechecks target/revision under lock.
- GET /api/folders/{id}/breadcrumbs returns live root-to-folder public metadata. GET /api/people returns at most five shared-circle id/email labels for uploader/actor attribution, including deactivated accounts; no role/password/session information.
- GET /api/events: bounded q/action/actor/after/before/limit/offset filters, shared file events only. GET /api/admin/activity adds identity/security events and requires administrator role; internal event details are not exposed. GET /api/admin/storage and /api/admin/trash require administrator role independently of UI.
- GET /api/items/{id}/preview independently checks membership/live ancestry and content signature/format. PNG/JPEG/WebP images: input up to 10,000,000 bytes/16,000,000 pixels, output first frame re-encoded as metadata-free PNG at most 2048x2048. PDF: percent-PDF header and .pdf extension, at most 25,000,000 bytes, local PDF.js canvas viewer without links/forms/annotation/scripting layers. MP4 ftyp/WebM EBML+doctype signatures and matching extensions allow native video playback, subject to browser codec support. Other content returns 415; invalid raster 422; preview-size limit 413; missing content 503. Original files are always downloadable unchanged.
- PDF/video support a single bytes=start-end/start-/suffix Range, clipped to EOF; valid requests return 206/Content-Range, invalid/multiple/oversized range headers return 416. Descriptors close on completion, cancellation or failure before iteration. Byte responses use no-store/nosniff and sandbox/default-src-none CSP, with attachment disposition on original PDF/video bytes. Images are re-encoded, never arbitrary HTML/SVG. Preview opens are not recorded as completed downloads.
- PUT /api/items/{id}/icon?expected_revision=N: exact Origin/CSRF/session before consuming the raw byte body; at most 2,000,000 actual bytes and a 30-second receive timeout. Only PNG/JPEG/WebP raster inputs, at most 4,000,000 pixels. First frame re-encoded to metadata-free PNG at most 256x256. Requires live file and current revision; reserves storage/upload slot, revalidates before publication, increments revision, logs icon_update. ItemView now includes has_icon, never a private key. GET /icon independently authorizes and returns the PNG. DELETE /icon takes JSON expected_revision and removes the icon; original file bytes remain unchanged.

Superseded/removed icons are detached transactionally and queued in revision 0005_media_cleanup before unlink. The queue only contains previously explicitly retired icons. Shared references (including replacement recovery) keep the old icon. Pending unlink remains charged against storage and reconciliation retries it; no auto-purge of ordinary trash. Icon request errors preserve existing references and use fresh DB reference checks for uncertain publication.

Metadata JSON boundaries remain 16 KiB. The raw PUT /icon path enforces its own actual-byte cap. Stage 4 uploads/downloads and identity routes retain their existing controls. PDF render preparation has a 30-second client timeout; canvas/image sizes are bounded and workers are destroyed on close. Supported previews are a convenience, not a guarantee that every file/codec can be displayed.

Administrator recovery: GET /api/admin/deletions lists only pending previously confirmed jobs, bounded limit/offset. POST /api/admin/deletions/{id}/retry takes strictly empty JSON {}, requires active administrator/Origin/CSRF, retries only an existing approved job and returns its pending/complete state. Completion is idempotent. It cannot create or broaden a deletion request. The Administration screen presents these jobs with request time, item count and a retry control.

## Implemented Stage 6 shared placement

All routes require an active session. POST/PATCH additionally require exact Origin, JSON and session-bound CSRF. Shared placement is visible/editable by all active circle members. No new dependency or schema revision; positions uses the existing table.

| Method/path | Contract |
| --- | --- |
| GET /folders/{id}/positions | Live folder only; up to 10,000 saved direct-child item_id/x/y/revision rows in stable UUID order. Excludes trash/deletion jobs; no updater identities or internal paths returned. |
| POST /folders/{id}/positions/initialize | Strict item_ids UUID array, at most 500; assign only missing live direct-child placements, ordered by creation/id, under the namespace lock. Preserve all existing placements. Golden-angle spiral stays outside the core and at least 125 logical units from occupied centers. Returns positions for requested live children. Browser requests use batches of 250 to respect the 16 KiB actual-body cap. Empty/duplicate IDs are safe; unrelated children are neither changed nor disclosed. |
| PATCH /items/{id}/position | Strict parent_id, expected_item_revision >= 1, expected_revision >= 0 (0 means absent), finite numeric x/y in [-1,000,000,1,000,000]. Stale parent, file or position revision returns 409; unavailable ancestry returns 404. Position revision increments independently of file revision. The file revision guard also rejects stale drags after a move away and back. |

Coordinate mutations do not change file contents, names, file revision, storage usage or file-event history. Existing moves clear only the moved item's position; its descendants retain coordinates within their own folders. Trash/restore retains placement while hiding it from live queries. Permanent deletion removes positions through the established deletion transaction.
