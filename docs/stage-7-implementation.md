# Stage 7 implementation — local milestones complete, live gates open

Owner authorized Stage 7 on 2026-10-23 and requested an obvious return from Recycle Bin. Branch: stage-7-recovery-readiness. No cloud/provisioning/production/merge approval inferred.

- [x] Visible, responsive Dashboard return in Recycle Bin; existing menu route retained.
- [x] Bounded local encrypted bundle, manifest validation, new-destination restore, failure/slot/retention/monitor state and safe publish behavior.
- [x] Real consistent PostgreSQL/files/config capture and isolated encrypted restore, including migration ownership and administrator access.
- [x] Local release/browser/security checks, bounded container logs, independent frontend rollback artifact rehearsal and operational runbook.
- [ ] Native OCI adapter, actual coordinated daily scheduling and outside-VM notification route implemented against approved resources.
- [ ] Actual free eligibility/volume/quota/cost reconciliation and resource-specific approval.
- [ ] Native capture, five-slot/four-point retention, missed/failed-job delivery and quota-safe full-size restore tested; observed RPO/RTO accepted.
- [ ] Production profile/host/TLS/data-volume/ARM64/image security gates passed and Stage 7 accepted.

## Changed boundaries

FileManager adds a Back to dashboard action only in Recycle Bin, using existing navigation defaults (65% root canvas / mobile list). A wrapping trash heading keeps both actions visible on narrow screens. Browser coverage verifies desktop/mobile navigation without deleting trash entries.

scripts/recovery_bundle.py contains bounded standard-library packaging and operator-supplied GnuPG invocation. Keys pass through stdin, not arguments/logs; separate short private agent homes accommodate the verified Windows MSYS path/socket limits and are cleaned up. Restores validate all content before publication, reject unsafe paths/links/duplicates and never overwrite destinations. Windows transient publish denial receives a bounded retry; permanent denial still fails. Existing good points survive all capture failures. Owned repository index/key/digest validation, interruption locks and a fifth capture slot guard rotation; unknown/orphan points or changed keys require review.

scripts/verify_recovery_compose.py captures the exact synthetic local project, resumes API in finally, verifies encrypted recovery into a new database/path, preserves migration ownership and all source data. scripts/verify_frontend_rollback.py serves prior/current immutable local artifacts in isolated labelled test containers without persistent mounts. backend/tests/test_recovery_bundle.py tests both real encryption and operational failure policies. pyproject.toml adds repository root to test imports only; no app dependency changes.

compose.yaml now bounds every service's json-file logs to three 10 MB files; no database/activity-history retention or data purge is introduced. API/frontend/migration runtime restrictions and private published ports remain intact. Disabled systemd sample-rehearsal units are under infrastructure/backup; they neither capture fresh live data nor implement native OCI scheduling and are not installed.

## Limitations that prevent completion

The selected production design remains OCI-native incremental backups, four retained good points plus one capture slot, in the same provider/account/region. The 256 MB local bundle and 64 MB integration-fixture caps are deliberate; this is not a full-copy workaround for 100 GB. Scheduled execution, outside-host alert delivery and native full restoration cannot be inferred from local tests. No live OCI volume or CLI authentication is configured; a read-only browser inventory attempt failed at tool initialization, before inspecting/changing Oracle state.

Stage 7's live tests depend on separately approved disposable resources before production acceptance, so they cannot be satisfied by marking local tooling complete and jumping to deployment. Keep these gates open or explicitly authorize a freshly verified quota-safe test configuration; do not silently waive or move them. Full resource/production constraints and key custody are in [runbook](recovery-runbook.md). Exact executed outcomes: [verification](stage-7-verification.md).
