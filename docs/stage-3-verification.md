# Stage 3 verification - 2026-10-21

Status: COMPLETE LOCALLY. Owner authorized local Stage 3 with "ok stage 3 now". Branch: stage-3-identity. No OCI resources, account upgrades, production deployment or main merge. All accounts used for verification are synthetic; no owner password has been chosen or seeded.

## Executed native and source checks

- Real portable PostgreSQL 17.11 harness: empty/idempotent Alembic upgrade through 0002_identity; runtime DML-only permissions; identity/security/concurrency tests; process restart; real pg_dump/pg_restore; disposable downgrade/re-upgrade. Latest complete pre-final-harness run: 24 Python tests passed before and after restore, with one upstream Starlette/HTTPX deprecation warning. Final harness run 4e31618cbcfe passed all 24 tests before and after restore (19.01s and 20.04s). Populated-security-history downgrade refused with the exact expected message and schema still at 0002_identity; real dump/restore recovered the synthetic account.

- Frontend: TypeScript/Vite production build, ESLint and five Node tests passed. Tests cover strict invitation-fragment parsing, exact CSRF-cookie selection, same-origin JSON mutations, 401 handling and prior health behavior. After the final browser corrections, formatter, ESLint, all five tests, TypeScript/Vite and Linux rebuild passed again.

- Hash-locked new Python dependencies installed successfully; pip check passed. Runtime requirements pip-audit and pnpm audit reported no known vulnerabilities. Actual Linux image inventory contains 28 distributions, with runtime pip removed; its separate pip-audit returned no known vulnerabilities. Installed package license metadata reviewed; no new frontend package.

- Secret-pattern scan passed. It is heuristic and is supplemented by source/log inspection.

Identity coverage includes interactive-only bootstrap/no seeded account, Argon2id parameters, public response-field allowlists, cookie flags and token rotation/digest storage; idle/absolute expiry/logout/admin revocation/deactivation; exact Origin/Host/CSRF/session binding; JSON/16 KiB actual body limits including chunked delivery; strict input/privilege rejection; generic wrong/unknown login responses; anonymous/member administrator denial; invitation expiry/revocation/single use/token-list privacy; concurrent redemption and last-slot registration; five-user count including inactive accounts; bounded outstanding invitations, peer/email throttling and spoofed-forwarding resistance; app logs exclude password/email/invite/session values.

## Corrections with evidence

1. Initial ordinary sandbox pytest run could not create its numbered temporary directory (Windows OSError before fixture execution). This was a local test-process permission boundary, not a passing test or application failure. Ran the isolated verification harness with approved normal local process permissions; subsequent real suites executed successfully.

2. First PostgreSQL identity run: 14 passed, one failed assertion after a test advanced the clock to expire a session and then moved time backward. Inspection proved the test expected expiration to act as permanent revocation after rewinding time. Corrected the test to verify logout against the actually logged-out token and recheck idle expiration with forward time. Full reruns passed.

3. ESLint rejected effect calls with hidden state updates and Date.now during render. Reworked initial fetch effects to explicit asynchronous callbacks with unmount guards, stabilized the expired-session callback, and recorded invitation status time when data is loaded. ESLint passed on rerun. A later copy edit needed Prettier formatting; formatter rerun completed.

4. The file patch tool rejected a delete/add pair targeting the same App.tsx in one patch. No partial edit was applied; wrote the intended files and verified TypeScript/Vite build. This was a tooling rejection, not a product error.

## Compose/browser gate

Fresh disposable project cloud-stage3-60b395cfd967 passed clean Linux build/start, migrations, runtime UID 10001/runtime-role DDL denial, direct/proxied readiness, all-container recreation with metadata/file persistence and container dump/restore. Prior Stage 2 containers were stopped with exact project-scoped down without -v; all named volumes preserved.

verify_identity_compose.py passed on the final backend: proxied login/invitation, identity/session continuity across recreation of all service containers, actual dump/restore of an active session digest and user into a separate disposable database, and logout revocation. The only accounts are synthetic fixtures. Raw evidence is ignored .local/compose-verification/60b395cfd967; browser credentials are private under ignored .cache and were not printed. The helper deliberately refuses to bootstrap a nonempty database.

Browser checks passed: generic wrong-password error; keyboard administrator login; create-one-time invitation/copy-value validation/Done clearing; revoke invitation; logout; same-tab invitation redemption; used-token rejection; member-only view with no administrator controls; browser refresh preserves session; mobile 390x844 layout without horizontal overflow; keyboard email-to-password navigation, Enter submit and mobile login/logout. Administrator session-revocation control executed successfully. Desktop viewport 1365x900. Evidence: [desktop login](evidence/stage-3-login-desktop.jpg), [mobile login](evidence/stage-3-login-mobile.jpg).

Two browser findings:

5. Reproduction: while signed out on the existing login tab, navigating to the valid invitation fragment left Welcome back visible and You’re invited absent. Source inspection confirmed the fragment was consumed only at module load. Added a hashchange listener with cleanup and immediate fragment removal. Repeated the identical existing-tab navigation: invitation form visible, bearer absent from the address; signup succeeded as member. Subsequent used-token submission was rejected. Frontend five tests, ESLint, TypeScript/Vite and Linux rebuild passed after correction.

6. The in-app browser command connection stalled immediately after native window.confirm was invoked during synthetic-member deactivation. This established a temporal association; a hidden dialog as the underlying cause was a hypothesis, not a verified visible prompt. The browser dialog API, Escape and tab-close recovery attempts could not dismiss it. Replaced that native dialog with inline explicit Confirm deactivation/Cancel controls, then reran formatter, ESLint, all five frontend tests, TypeScript/Vite and Linux rebuild successfully. Verified the final BinI300h bundle was loaded in a fresh tab; however the browser remained unable to activate even Sign out, confirming a broader input blockage rather than evidence of a new component failure. Requested owner help dismissing the old dialog. **Resolved on follow-up: owner reported no visible dialog; the retained browser tab accepted input again without any additional application change. Cancel preserved the active synthetic member; Confirm changed it to Deactivated and disabled its controls. Administrator logout succeeded, and a subsequent login with the deactivated member was rejected with the generic error. Stage 3 final browser acceptance passed.** API deactivation/revocation and existing-session invalidation already passed real PostgreSQL tests.

A preview reload during all-container recreation also encountered the expected temporary connection refusal and its browser error-page binding was unavailable; opened a fresh allowed localhost tab after readiness recovered. No security interstitial was bypassed.

## Practical limits

This is local development acceptance only. The explicit loopback HTTP cookie exception is enabled only for development; actual public HTTPS/Secure-cookie behavior, ARM64 execution, image/host hardening, trusted-proxy review, real daily cloud backup/full-size recovery and verified Always Free resource configuration remain release gates. File uploads/downloads, previews, quota UI and spatial experience start in later approved stages. The same-account/region backup compromise and $0 policy are unchanged.

Final documentation validation caught a Windows-encoded apostrophe byte in the report. Normalized only invalid UTF-8 bytes to their intended Unicode characters while preserving existing valid UTF-8; repeated strict UTF-8/local-link/whitespace validation passed.

Final browser evidence: [administrator after confirmed deactivation](evidence/stage-3-admin-verified.png). Preview returned to a clean signed-out screen at http://127.0.0.1:8080/; only synthetic test accounts remain. No extra application changes were needed on follow-up. Final source/backend/frontend checks were already passing; document-only acceptance updates were validated for strict UTF-8, local links and whitespace. Stage 4 requires separate owner approval.
