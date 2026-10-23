# Stage 6 locked canvas and drag-to-trash

Owner request, 2026-10-23: lock canvas at 65%, remove zoom adjustment, add a bottom-left rubbish-bin drag target, remove bottom-left routine status updates. Authorized locally on branch stage-6-locked-canvas-trash.

## Changes

- api/spatial.ts returns a constant 0.65 scale for all framing, including empty/distant items and viewport sizes; removed obsolete adjustable zoom utilities. SpatialCanvas also enforces the fixed scale in every camera mutation. Resize and keyboard reveal retain it; dragging empty space still pans. More controls contains Recenter and pan/help, with no zoom buttons, percentage or Fit all.
- Fixed-size icons/core remain unchanged. Recenter moves the camera at 65% and cannot fit arbitrarily distant items onto one screen. Users retain manual folders, pan, keyboard focus reveal and mobile list/grid; no automatic clustering or saved-coordinate changes.
- Bottom-left accessible Recycle Bin button opens the existing trash view. Pointer capture retains node dragging while bounding-box hit testing highlights the bin. A moved node released inside it restores its pre-drag coordinate locally, then invokes the existing authenticated revision-checked trash API. Cancelling never trashes or saves; dropping elsewhere keeps normal persisted placement behavior.
- FileManager coordinates busy state, shared-list refresh and session expiry. Failed/stale trash actions retain the item and original placement and surface an error. Folder trash keeps subtree recoverable; permanent delete remains a separate admin action.
- Routine placement messages remain in a clipped screen-reader live region. Visible failures use a dismissible alert above the canvas; stale placement conflict actions remain available.

## Acceptance stages

- [x] Constant 65% geometry, no zoom UI and fixed node size through resize/recenter/focus/pan.
- [x] Real file/folder drag-to-trash and restoration preserve bytes/children; pointer cancel and failed/stale writes retain item/position.
- [x] Shared persistence/conflicts, native file uploads, reduced motion, responsive immersive UI and rendering regression.
- [x] Unit/build/lint/format/security pattern checks and visual inspection; record exact results and limitations.

Only the exact disposable loopback preview is used. No backend/schema/dependency/cloud/production changes. Browser test data is synthetic and retained under Demo files; no permanent deletion is required by these tests.


## Executed verification — complete locally

- Nine frontend unit tests passed. New geometry cases cover empty/sparse/distant placements at desktop/tablet/small dimensions, constant 0.65 and exact drag conversion. TypeScript/Vite native and Linux Compose builds passed. ESLint, Prettier (38 files), heuristic secret scanning and git diff --check passed.
- Six existing browser scenarios passed together in the seven-case run: fixed node size/recenter/tablet (4.9s), full immersive viewport/right-edge open/upload/focus (15.0s), tablet/mobile/menu/logout (2.7s), shared placement/stale retry/pan/reduced-motion/mobile (15.4s), fixed-scale 20/100/500 rendering (9.0s), and file drop/refresh-held-drag/cancel (10.5s). The new seventh scenario initially timed out on a test-only menu/toolbar assumption; corrected to click the Spatial view toolbar directly. Its final navigation assertion also needed the actual icon-prefixed All files label. Application code did not change after those six passed.
- Final targeted trash scenario passed in 5.7s (7.5s command), including an actual post-restore download with exact original text bytes. Verified 65% after wheel, recenter and resize; absent zoom/Fit buttons; bin highlight; pointer cancel (zero trash requests, exact original positions); synthetic 503 (visible error, unchanged item/position); real stale revision 409 (no trash); real file and folder drops (200); descendants unavailable while parent trashed; restoration re-exposes descendants and file checksum; downloaded bytes exactly match. Clicking bin opens actual shared recycle-bin UI. Routine placement live region is clipped, with no bottom-left visible message.
- Repeated synthetic logins reached the existing email rate threshold once; exact generated administrator email bucket was reset with the guarded local helper, and acceptance reran successfully. Credentials, sessions, peer limits and application rate policy were retained. A preliminary run was interrupted to correct test selectors; it is not claimed as a pass.
- Actual locked-scale active-pan rendering p95 frame times at 20/100/500 nodes: 2.9/8.3/5.6ms, median 2.8ms; maxima 2.9/11.2/13.9ms, no observed long tasks. All passed p95 <40ms; 20/40/0 animated nodes. Existing local Chrome155/hardware and synthetic renderer isolation apply. Fixed scale can leave distant nodes outside the viewport; this is deliberate, with manual pan/keyboard reveal/list available.
- Visually reviewed [final desktop](evidence/locked-canvas/desktop.png): bottom-left outlined rubbish bin, no zoom buttons/percentage/status strip, optional More controls at bottom center. Final root contains Demo files and untouched icon.png; three new generated root regression folders were collected into Demo files using existing revision-checked moves. Trash-test folders were created directly inside Demo files.
- No fresh backend unit/recovery/cloud tests were run for this frontend-only refinement. Existing API authorization and revisions are exercised by real browser requests; no migration, dependency, cloud resource, production deployment, merge or permanent deletion.

Reproduction: pnpm test; pnpm build; pnpm lint; pnpm format:check; .venv/Scripts/python.exe scripts/scan_secrets.py; pnpm --filter @personal-cloud/frontend exec playwright test consistent-icons.spec.ts immersive.spec.ts spatial.spec.ts trash-target.spec.ts. Final targeted command: playwright test trash-target.spec.ts. Tests use only the exact disposable local preview and generated fixture credentials. Persistent database/file volumes are preserved.
