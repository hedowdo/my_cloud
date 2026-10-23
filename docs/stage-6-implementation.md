# Stage 6 implementation milestones

Owner authorized local Stage 6 on 2026-10-22. Use branch stage-6-spatial-dashboard. No new dependencies, cloud resources, publication, merge or production changes.

## A. Shared placement contract
- [x] Add authenticated folder-position listing and CSRF-protected revision-checked position updates using existing positions table.
- [x] Keep position revision independent from file revision; require current parent so a stale drag cannot repopulate coordinates after a move.
- [x] Test unauthorized, invalid/nonfinite/bounded coordinates, first-write race, subsequent stale writes, moved/trashed items and two-member persistence.

## B. Spatial UI
- [x] Add glowing geometric core, faint SVG connections, accessible node labels/details/open, guided empty state.
- [x] Deterministic freeform placement respects saved occupied space; transform logical coordinates for fit, bounded zoom/pan, resize.
- [x] Pointer capture for node drag and empty-space pan; keyboard arrow placement plus Enter select and explicit Open; distinguish native file-drop uploads.
- [x] Refresh coordinates without changing an active drag; show conflict and explicit retry using refreshed revision and same intended coordinates.
- [x] Respect reduced motion; pause motion while dragging; cap animated nodes in larger folders; keep mobile list/grid and desktop list fallback.

## C. Acceptance
- [x] Backend integration suite before/after actual disposable PostgreSQL restore; no schema migration expected.
- [x] Frontend logic, type/build, lint/format and secret checks.
- [x] Browser two-user persistence/conflicts, drag/open/select, keyboard, zoom/pan/resize, native drop, light/dark, reduced motion and mobile regression.
- [x] Measure browser frame/long-task work at 20/100/500 nodes, record environment and measured limits; visually inspect screenshots.
- [x] Record executed results, limitations and plan checkmarks only after passing.

Approach: extend backend/app with a small position router, use existing locked authorization transactions and finite strict Pydantic inputs. A separate SpatialCanvas component owns viewport/pointer/refresh state; pure geometry helpers own deterministic placement. Reuse FileManager actions and safe previews. List/grid is the alternative for mobile, cross-folder searches and dense folders. Limit canvas to 500 matching items and disclose the limit. Existing pagination keeps all files discoverable.

Risks: stale drag after a file move, overlapping new placement near saved nodes, pointer-to-logical conversion under zoom, hidden names/accessibility, and costly effects for dense folders. Address with parent+position revision checks, occupied-area placement, pure geometry tests, explicit keyboard controls, reduced-motion support and bounded effects. Benchmarks are local browser measurements, not a universal hardware performance guarantee.

Current evidence: stage-6-verification.md. Actual native backend acceptance is 72 tests before/after restore; Linux position restoration/recreation passed. All nine browser scenarios passed sequentially, with a further settled-theme/camera check; final traces, screenshots, recovery evidence and limits are recorded in stage-6-verification.md. Stage 6 is complete locally.
