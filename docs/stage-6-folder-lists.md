# Stage 6 folder lists

Owner confirmed on 2026-10-23: folders open in list view, individual files keep their previews, and the main dashboard stays spatial.

The targeted change is in FileManager.navigate: file navigation resets grid, sets spatial preference only for the root, and preserves existing filter-reset/loading logic. Double click, details Open and breadcrumbs use this path. Returning through All files therefore restores the locked-65% canvas on desktop; mobile still uses the responsive list. Explicit view controls remain available inside a folder. No file content, saved positions, API, schema or dependencies change.

## Acceptance

- [x] Root canvas to folder list; nested navigation resets grid to list.
- [x] File preview and details Open retain intended behavior; breadcrumb and menu return restore root canvas.
- [x] Existing canvas/trash/immersive tests opt into folder canvas explicitly and pass; mobile fallback passes.
- [x] Frontend unit/build/lint/format/security-pattern checks and screenshot inspection pass; record exact evidence.

New folder-lists.spec.ts creates its synthetic data inside Demo files, opens an uploaded PNG preview, tests nested folder entry from grid through details Open, returns by breadcrumb/menu, checks root scale/bin, and checks mobile fallback. The existing spatial suites explicitly choose Spatial view where they are testing canvas internals rather than navigation defaults.

No Stage 7, cloud resource, merge or deployment is authorized by this refinement. Local frontend preview rebuild preserves all persistent volumes. Executed results below.


## Executed results (2026-10-23)

Nine frontend unit tests, Linux Compose production TypeScript/Vite build, ESLint, Prettier (39 files), heuristic secret scan and git diff --check passed. Frontend-only change; no backend/recovery/cloud tests rerun.

Seven existing browser scenarios passed in the full eight-case command (1.6m): fixed-size/recenter/tablet (5.1s), immersive viewport/right-edge/actual upload/focus (17.8s), tablet/mobile/menu/logout (3.0s), shared persistence/stale conflict/pan/reduced motion (16.1s), 20/100/500 rendering (9.8s), native file drop/held refresh/cancel (10.6s), and trash cancel/error/stale/real file+folder restore/exact download (6.1s).

The new folder-list test initially expected an empty UL to have visible height, then used exact breadcrumb names without their CSS slash separator. Both were test assumptions: actual list navigation and preview worked; assertions now check the empty list's existence and match unique breadcrumb labels including their decorative suffix. Final targeted folder-lists.spec.ts passed in 5.1s (7.2s command), without application changes after the seven-case regression. Verified root canvas → folder list, nested details Open from grid → list, PNG preview, parent breadcrumb → list, All files breadcrumb/menu → locked-65% root canvas/bin, and mobile fallback. All eight cases passed in aggregate; the initial full command exited nonzero for the test correction described above.

Visually inspected [folder list screenshot](evidence/folder-lists/folder.png). Synthetic folder-list fixtures were created inside Demo files; three new generated root regression folders were subsequently moved into Demo files, leaving only Demo files and untouched icon.png at root. Generated administrator login bucket/light theme restored without changing credentials or peer policy.

Reproduce: pnpm test; pnpm lint; pnpm format:check; pnpm --filter @personal-cloud/frontend exec playwright test folder-lists.spec.ts consistent-icons.spec.ts immersive.spec.ts spatial.spec.ts trash-target.spec.ts. Existing spatial tests explicitly opt into folder canvas for their internals; default folder browsing remains list. Only the two navigation preference setters alter application behavior.
