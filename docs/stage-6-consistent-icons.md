# Stage 6 consistent icons and demo consolidation

Owner approved on 2026-10-23: collect known test/demo items into one folder, keep manually organized folders, and do not add automatic grouping. Preserve the immersive full-viewport dashboard.

## Approach and acceptance

- Preserve a complete ignored metadata snapshot before any move; authenticate through the existing local API and use revision-checked moves.
- Keep node buttons, icons, labels and focus rings at 76px screen-space size by counteracting the camera scale at the node center. Keep the core at 148px. Shared world coordinates, camera pan/zoom, logical drag conversion and API are unchanged.
- Fit reserves fixed screen margins (100px top/sides, 160px bottom for controls), rather than margins that shrink with camera scale.
- No automatic grouping, collision resolution, coordinate rearrangement or folder creation during normal browsing. Manual zoom remains optional. Arbitrarily dense or overlapping placements can still overlap; users organize these through actual folders as requested.
- Run geometry/unit, build/lint/format, actual browser size/folder/overlay/responsive checks, shared persistence/drag/conflict and rendering regressions. Inspect screenshots and verify original metadata/content preservation before completion.

## Organization evidence

Saved complete item/blob/placement snapshot in ignored .local/consistent-icons/before.json. Initial helper used a nonexistent table name file_positions, failed read-only, then was corrected to the actual positions table; snapshot passed before any move. Restricted browser initially denied loopback navigation; the approved localhost execution then succeeded.

Authenticated revision-checked moves collected 89 recognized generated items into Demo files. Known fixture names only were selected; unrecognized icon.png stayed at root. Root initially contained 90 live items. Each moved response retained ID, name, byte size and checksum; final container membership and unselected root membership were verified. No deletion or blob mutation. Full move manifests remain ignored under .local/consistent-icons for reversal with current revisions; shared root placements of moved items are cleared by the existing move API, while nested placements remain intact.

## Verification

Completed locally on branch stage-6-consistent-icons. No backend/schema/dependency changes, cloud resources, merge or production deployment.

- Nine frontend unit tests passed, including stronger fixed-screen-margin fit assertions. Production TypeScript/Vite builds (native and Linux Compose), ESLint, Prettier (37 files), heuristic secret scanning and git diff --check passed.
- All six actual headless Chrome browser scenarios passed: consistent sizes/navigation/overlays/tablet/mobile (5.2s); existing shared persistence/stale retry/drag/zoom/reduced-motion/mobile (16.4s); 20/100/500-node rendering (11.7s); native file drop/held drag/refresh/cancel/deselect (11.0s); immersive viewport/right-edge double click/actual file picker/upload/search/reset/focus (16.9s); tablet/mobile/menu/folder/logout (2.9s). Commands: pnpm --filter @personal-cloud/frontend exec playwright test consistent-icons.spec.ts spatial.spec.ts (4 passed, 47.3s) and playwright test immersive.spec.ts (2 passed, 22.3s).
- Actual node bounds stayed 76x76px through Fit, multiple zoom steps and 820x1180 tablet resizing. All 89 demo children remained fixed-size when opening the container. Desktop 1600x900 and tablet document bounds passed; mobile 390x844 retained list fallback. Details did not alter the camera transform. Browser screenshots were inspected: [desktop](evidence/consistent-icons/desktop.png), [tablet](evidence/consistent-icons/tablet.png).
- Measured active-pan/zoom p95 frame times: 5.6ms / 13.8ms / 19.5ms at 20/100/500 nodes; medians 2.8ms. All passed p95 <40ms; maxima included 144.4ms/241.8ms outliers at 100/500. This is not a universal 60 FPS guarantee. No long-task entries observed; bounded animation remains 20/40/0. Large manually crowded folders can visibly overlap at fixed size, as expected with the owner's no-grouping choice.
- Three new generated test containers were subsequently collected into the same Demo files folder; it now has 92 direct children, with root containing only Demo files and untouched icon.png. No automatic grouping behavior was added.
- Final whole-metadata comparison proved all 383 original item IDs/records preserved (only the 89 approved original root parents/revisions changed), all 93 original blob records unchanged, and all 62 unmoved saved-position records unchanged. Expected move semantics clear moved nodes' old parent placement; original positions are in the recovery manifest. Manifests and results: ignored .local/consistent-icons. These are metadata/content-reference checks, not a fresh full byte-by-byte disk audit or backup restoration.
- Backend/API remained unchanged; the historical backend/recovery tests were not rerun for this frontend refinement. Existing persistent volumes and credentials were retained.
