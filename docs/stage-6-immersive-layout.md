# Stage 6 immersive layout refinement

Owner approved the clarified layout on 2026-10-23: canvas fills the screen, minimal visible words, navigation/upload starts closed, and file details overlay the canvas. Existing 100 GB/$0/recovery/release gates remain unchanged.

## Milestone A — layout and controls
- [x] Full viewport with no document scrolling; no permanently reserved side panels.
- [x] Closed navigation drawer with search/filter/upload/storage/theme/account/sign-out controls.
- [x] Details overlay with close/Escape and keyboard focus return; canvas transform unchanged.
- [x] Minimal floating controls and optional help, preserving accessible labels and mobile list/grid.

## Milestone B — validation
- [x] Type/build, unit, lint/format and secret checks.
- [x] Real browser desktop/tablet/mobile viewport and no-page-scroll assertions.
- [x] Drawer focus/close, details overlay/camera stability, right-edge double click, preview, upload/search, theme and list navigation.
- [x] Existing shared placement/conflict/reduced motion/performance regression and screenshots.
- [x] Record results and update plan.

Approach: change App/FileManager presentation, add a reusable modal navigation drawer, compact SpatialCanvas controls and viewport CSS. Reuse existing actions, safe previews and API. Details stay nonmodal overlays so the canvas remains accessible; navigation uses native dialog focus containment/Escape. Internal drawer/list scrolling is allowed; the dashboard itself must fit the viewport. No backend, dependency, cloud or database changes.

Risks: a details overlay covering a right-edge node between clicks, keyboard focus reaching hidden controls, lost menu features and accidental window scroll. Tests must exercise these directly. Root document layout and drawer overflow should constrain scrolling without clipping actions inside open panels.

## Implementation and executed checks

App now hides its signed-in masthead/footer and delegates sign-out to the menu. FileManager owns the initially closed drawer and overlays details rather than reserving a column. Native modal navigation has explicit Tab/Shift+Tab wrapping, Escape/backdrop dismissal and focus return. Search/filter JSX is shared and portaled into the open spatial menu; its state persists while closed. Mobile list/grid and larger utility views scroll inside the fixed application viewport. SpatialCanvas keeps the same logical coordinates and API; a small bottom control strip offers Fit/zoom and an optional pan/help menu. Success feedback clears after five seconds on the canvas.

Pointer selection highlights immediately; the details overlay waits 500ms to allow a desktop double click to open the node before a right-edge overlay could cover it. Keyboard and touch selection open details immediately. Closing details/Escape returns focus; dialogs retain their independent modal behavior. Files, accounts, database, migrations, dependencies and cloud resources are unchanged by this layout feature.

Focused immersive browser acceptance: two scenarios passed (14.9s), including exact 1600x900 and 820x1180 canvas bounds, 390x844 mobile fallback, document scroll bounds, initially closed panels, unchanged canvas dimensions/transform on overlay, real right-edge shared-position update plus double-click opening, image preview, upload/search, keyboard focus/Tab wrapping/Escape, menu internal scrolling, theme and logout. Nine existing frontend unit tests passed; TypeScript/Vite, ESLint, Prettier and secret scan passed. Final adapted regression is recorded below; this refinement is complete locally.

## Observed corrections

- First exact-viewport test measured tablet canvas x=57.39, y=32, width=705.22, height=1116 instead of 820x1180. styles.css imports after component CSS and its .shell padding won at equal specificity. Target main.app-shell explicitly to retain zero padding. The exact desktop/tablet assertions now pass.
- Native dialog boundary focus did not reliably wrap Shift+Tab from the first control to the last control in the tested Chrome. Add explicit visible/enabled-control boundary wrapping without replacing native modal inert/Escape behavior. The first/last-control and focus-return cases now pass.
- Legacy list-search tests clicked a toolbar covered by the intentionally open details overlay. The test now closes details before using that toolbar; the complete file workflow passed (13.3s). Native file actions and shared placement are unchanged.
- Legacy sign-out helper tried to click Close menu while the successful async logout was removing the drawer. Skip that redundant close for sign-out; production logout logic is unchanged. The corrected member/sign-out case passed in the final regression.

Evidence screenshots are under docs/evidence/immersive. Raw browser traces remain ignored under .local/stage5-browser/results. Existing backend/recovery evidence in stage-6-verification.md remains historical; the backend suite is not rerun for this frontend-only change.

Additional regression findings and targeted fixes:

- Opening a folder selected through filename search retained the old query and displayed no children despite successful child creation. Clear search/filter state when entering file navigation; the immersive test now opens its folder from filtered results and then verifies its child. Normalized no-filter state also exposed a previous loading bug: Reset filters or reopening the current section set loading without changing any fetch dependency. Increment the explicit refresh version on navigation and reset. The new cases repeat each action twice and require loading to finish.
- Legacy move-destination tests assumed every synthetic folder was on the first ten-row picker page. The retained preview has accumulated more fixtures, so the test now follows the real More folders pagination and verifies the returned page labels before selecting its own destination.
- Details deliberately cover some list toolbar controls and right-edge nodes. Tests now use the accessible menu Refresh action or close the overlay before dragging a covered node. Drag acceptance awaits the actual successful PATCH response rather than a previous identical success message.
- Reopening the drawer resets its optional native details-section expansion state. The optional-icon test expands that section before Clear icon. Its selected icon remains in controlled React state until cleared.
- Existing 80/90% storage warnings retain an accessible small indicator on the closed menu button, with exact usage/warning text inside the menu. No additional permanent text is added to the canvas.

The final acceptance run is sequential and uses only the exact disposable cloud-stage5-92c8e356b3cb localhost project. Repeated test runs prepare only its generated administrator email rate bucket; application rate policy and peer limits remain intact. Final fixture cleanup restores its light theme and login availability without changing its password or sessions.

## Final acceptance — complete locally (2026-10-23)

- **All 11 browser scenarios passed.** The full sequential run passed 10 cases in 1.9m; its only remaining failure was a synthetic icon fixture no longer appearing on the first name-sorted page. The test now uses actual filename search, and that final case passed in 3.5s (5.2s command). No application code changed after the 10-case run. Cases cover complete file workflows/admin isolation, responsive/keyboard/network behavior, pagination/real folder-picker paging, upload cancellation, storage-warning presentation, optional icons/grid/themes, immersive viewport/drawers, real menu file-picker upload, preview, repeated reset/current-section navigation, two-user positions/conflicts and held-drag refresh, reduced motion and rendering performance.
- **Nine frontend unit tests passed.** Production TypeScript/Vite and Linux Compose builds passed. ESLint, Prettier (36 files), heuristic secret scanning and final source/document checks passed as recorded below.
- Exact canvas bounds passed at **1600x900** and **820x1180**. Document width/height/scrollY stayed within the viewport. **390x844** uses the existing mobile list; long list/menu content scrolls internally. Opening file details does not change canvas bounds or its camera transform. Native preview dialogs still appear above details; Escape/focus return and menu first/last Tab wrapping passed.
- The desktop right-edge test saves a real shared position underneath the future overlay area, waits for its refresh, then double clicks the node and verifies folder opening. Single pointer selection defers the overlay for the double-click window while highlighting immediately; keyboard/touch details open immediately.
- Saved shared coordinates/API, permissions, storage, uploads and database schema are unchanged by the layout work. **No backend tests or cloud/recovery tests were rerun for this frontend-only refinement**; the previous 72/72 backend and restoration evidence remains in stage-6-verification.md. No new dependencies, migration, cloud resource, publication or merge.

Final active pan/zoom samples on the previously documented i7-10875H/31.9 GiB Windows machine, headless Chrome 155, 1440x1000 viewport:

| Nodes | Median ms | p95 ms | Max ms | Animated orbs |
| --- | ---: | ---: | ---: | ---: |
| 20 | 2.8 | 8.3 | 8.4 | 20 |
| 100 | 2.8 | 8.3 | 25.1 | 40 |
| 500 | 2.8 | 22.2 | 36.2 | 0 |

No observed long tasks; all passed the documented p95 <40ms gate. At 500 nodes the measured p95 is above 16.7ms, so this is not a universal 60 FPS claim; dense folders keep reduced effects and list/grid fallback. Mocked synthetic 20/100/500 metadata isolates rendering; real API persistence/conflicts are separate browser/native tests. Captured timelines/metrics are preserved under ignored .local/immersive-verification.

Screenshots visually reviewed: [desktop home](evidence/immersive/desktop-home.png), [desktop](evidence/immersive/desktop.png), [dark](evidence/immersive/desktop-dark.png), [details overlay](evidence/immersive/details-overlay.png), [navigation drawer](evidence/immersive/navigation.png), [tablet](evidence/immersive/tablet.png), [mobile](evidence/immersive/mobile.png). The canvas has no permanent masthead, footer, guidance block, storage text, search toolbar or side column. Its controls remain accessible through floating buttons/menu, with errors/conflicts available until handled and short successful-upload feedback clearing after five seconds.

Reproduction: pnpm build; pnpm test; pnpm lint; pnpm format:check; .venv/Scripts/python.exe scripts/scan_secrets.py; pnpm --filter @personal-cloud/frontend exec playwright test. The final targeted fixture case used --grep 'optional upload icon'. All browser operations use isolated Chrome profiles and the exact synthetic localhost fixture. Do not use test credentials or test fixture resets for a real deployment.

Final handover validation passed: 102 UTF-8/whitespace source/docs files, all local documentation links, completed refinement checklists, unchanged Stage 7 checklist, git diff --check, ESLint, Prettier (36 files), nine unit tests and heuristic secret scan. The final explanatory comment required a formatting pass; formatting/lint then passed. Only the generated preview administrator email counter/light theme were restored after testing; credentials/sessions and peer policy were preserved.
